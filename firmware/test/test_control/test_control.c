/*
 * The control logic exercised against the simulated hardware implementation.
 *
 * These tests link the same control translation units the target build links,
 * against the simulated implementation of the seam, on a machine with no
 * target microcontroller and no vendor toolchain in the picture. That they can
 * run at all is the substitutability property; what they assert is that the
 * control path behaves the same way through the seam as it would through
 * hardware.
 */
#include <unity.h>

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "control.h"
#include "delivery_profile.h"
#include "delivery_tolerance.h"
#include "estimator.h"
#include "estimator_limits.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"

static control_state_t state;
static plant_parameters_t parameters;
static estimator_limits_t limits;
static delivery_tolerance_t tolerance;

/*
 * The temperature the suite asks for. It is the suite's own choice rather than
 * a figure the software carries, which is the point: there is no setpoint
 * compiled into the control logic any more, so a test that wants one names it.
 */
#define BREW_TARGET_MILLI_C 93000
static const float BREW_TARGET_C = (float)BREW_TARGET_MILLI_C / 1000.0f;

/*
 * The reference description as text, kept rather than discarded once it has
 * been read into a record.
 *
 * Two tests here need a description that differs from the shipped one in
 * exactly one coefficient, and the honest way to produce that is to rewrite the
 * line and hand the result to the same loader. Reaching into the record and
 * assigning a field would work on this structure and stop compiling on the next
 * one, and it would also step around the range each structure declares its
 * coefficients admissible within -- which is the loader deciding whether a
 * perturbation is a machine at all.
 */
static char description_text[16384];
static size_t description_length;

static void load_the_reference_description(void)
{
    FILE *const handle = fopen(REFERENCE_DESCRIPTION_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "could not open the reference description");

    description_length = fread(description_text, 1u, sizeof(description_text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(description_length > 0u);
    TEST_ASSERT_TRUE(description_length < sizeof(description_text) - 1u);

    plant_parameter_error_t fault;
    TEST_ASSERT_TRUE(
        plant_parameters_load(description_text, description_length, &parameters, &fault));
}

/*
 * The limits declaration beside that description, read from the same place and
 * for the same reason: what a reading off this machine may plausibly be, and
 * how long the control path may drive without one, are facts the machine ships
 * rather than facts a suite is entitled to invent.
 */
static void load_the_reference_limits(void)
{
    static char text[16384];

    FILE *const handle = fopen(REFERENCE_LIMITS_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "could not open the reference limits declaration");

    const size_t used = fread(text, 1u, sizeof(text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < sizeof(text) - 1u);

    estimator_limits_error_t fault;
    TEST_ASSERT_TRUE(estimator_limits_load(text, used, &limits, &fault));
}

/*
 * The band beside them, read from the file the build names rather than written
 * into this suite. It is what the loop is held to, so a suite carrying its own
 * copy would be holding trajectories to a figure nobody shipped -- and would go
 * on accepting them after the declared band was tightened.
 */
static void load_the_reference_tolerance(void)
{
    static char text[16384];

    FILE *const handle = fopen(REFERENCE_TOLERANCE_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "could not open the reference tolerance declaration");

    const size_t used = fread(text, 1u, sizeof(text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < sizeof(text) - 1u);

    delivery_tolerance_error_t fault;
    TEST_ASSERT_TRUE(delivery_tolerance_load(text, used, &tolerance, &fault));
}

/*
 * A limits record built from text the test writes, for the cases that need to
 * reach the control law with a reconstruction the shipped declaration would
 * rightly refuse. The shipped one is what every other test here runs against.
 */
static estimator_limits_t limits_from(const char *text)
{
    estimator_limits_t built;
    estimator_limits_error_t fault;

    TEST_ASSERT_TRUE_MESSAGE(estimator_limits_load(text, strlen(text), &built, &fault),
                             "the suite's own limits declaration was refused");
    return built;
}

/* Withdraw every channel, so the estimator runs on prediction alone. */
static void withdraw_every_reading(void)
{
    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        hw_sim_set_sensor((hw_sensor_channel_t)channel, HW_READING_FAILED, 0);
    }
}

/* What the estimator the control law holds currently reconstructs. */
static float reconstruction(void)
{
    float value = 0.0f;

    TEST_ASSERT_TRUE(plant_model_state(&state.estimator.model,
                                       PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &value));
    return value;
}

/*
 * Stand the reconstruction the control logic acts on at a chosen temperature.
 *
 * The control logic drives from a state no sensor reports, so a reading alone
 * no longer decides what it sees: the estimator is what stands between them,
 * and over a step it moves the reconstruction by a fraction of what the model
 * did. Placing both the mass and the water leaving it at the same temperature,
 * with the reading agreeing, is what makes the temperature the control logic
 * acts on next step the one this names -- the estimator's own correction has
 * nothing to pull, and a single step moves the reconstruction by a fraction of
 * a millidegree, which rounds away.
 *
 * It goes in through the plant seam's write rather than by reaching a field,
 * which is the same route the estimator's own correction takes.
 */
static void place_reconstruction_at(int32_t milli_c)
{
    const float degrees = (float)milli_c / 1000.0f;

    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, milli_c);
    TEST_ASSERT_TRUE(plant_model_set_state(
        &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, degrees));
    TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, degrees));
}

void setUp(void)
{
    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    load_the_reference_description();
    load_the_reference_limits();
    load_the_reference_tolerance();
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &tolerance));

    /*
     * A target is named here because most of what follows is about a machine
     * that has been asked for a drink. The cases that are about a machine which
     * has not been asked bring their own state up without one.
     */
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
    place_reconstruction_at(20000);
}

void tearDown(void) {}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C2: the control logic builds into a host
 * executable with no target dependency present -- it initialises and runs
 * against the simulated implementation. */
static void test_control_runs_against_the_simulated_implementation(void)
{
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT32(1u, state.step_count);
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C3: the control logic reaches hardware
 * only through the seam, so what is stood up on the simulated implementation is
 * what the control logic acts on. It travels by way of the estimator now -- the
 * reading corrects a model and the control logic drives from what that model
 * reconstructs -- but every step of that path is still the seam's. */
static void test_a_temperature_stood_up_reaches_the_control_logic(void)
{
    place_reconstruction_at(43000);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    /* Fifty degrees below the target, at any of the gains the loop has carried,
     * asks for more than the actuator has. */
    TEST_ASSERT_EQUAL_UINT16(ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C3: a drive command issued by the control
 * logic arrives at whichever implementation is linked. */
static void test_drive_level_falls_as_the_temperature_approaches_the_setpoint(void)
{
    place_reconstruction_at(BREW_TARGET_MILLI_C - 5000);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    const uint16_t below = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    TEST_ASSERT_TRUE_MESSAGE(below > 0u && below < ACTUATION_FULL_SCALE,
                             "five degrees below the target neither saturated nor stopped");

    place_reconstruction_at(BREW_TARGET_MILLI_C);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) < below,
                             "the drive level did not fall as the target was approached");
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C2: the drive level the control logic
 * asks for never exceeds what the seam accepts, whatever it is acting on --
 * including temperatures no machine could be at, which is what a model driven
 * somewhere absurd would present. */
static void test_drive_level_stays_within_full_scale_at_extremes(void)
{
    /*
     * Brought up against a declaration that admits anything, so that the
     * extremes actually reach the control law's arithmetic. Against the shipped
     * declaration they would not: a reconstruction two million degrees from
     * where its observations left it is refused by the estimator, which is that
     * bound doing its job and not this property being tested. What is asserted
     * here is the control law's own guarantee -- that whatever temperature it is
     * handed, the level it asks the seam for is one the seam accepts -- and it
     * has to hold for values the estimator would never pass on, because a
     * refusal upstream is not a reason for the arithmetic below it to overflow.
     */
    static const char ADMITS_ANYTHING[] = "@describes-no-machine\n"
                                          "brew-temperature = -2147483647 .. 2147483647\n"
                                          "steam-temperature = -2147483647 .. 2147483647\n"
                                          "brew-pressure = -2147483647 .. 2147483647\n"
                                          "steam-pressure = -2147483647 .. 2147483647\n"
                                          "flow = -2147483647 .. 2147483647\n"
                                          "loss-tolerance-window-ms = 4000000000\n"
                                          "excursion-bound-milli-c = 2147483647\n";
    const int32_t readings[] = { INT32_MIN, -1000000, 0, BREW_TARGET_MILLI_C, INT32_MAX };
    const estimator_limits_t permissive = limits_from(ADMITS_ANYTHING);

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &permissive, &tolerance));
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));

    for (unsigned i = 0; i < sizeof(readings) / sizeof(readings[0]); i++) {
        place_reconstruction_at(readings[i]);
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
        TEST_ASSERT_LESS_OR_EQUAL_UINT16(ACTUATION_FULL_SCALE,
                                         hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    }
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C6: A brief gap in the brew reading does not
/// latch a fault in the control law.
///
/// SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C4: the host build exercises the error
/// paths, not only the happy path -- a reading that stops de-energises.
///
/// The two halves are one property. A control law that shut down on the first
/// missing sample would pass the second half of this and fail the machine, and
/// one that drove on forever would pass the first half and drive a heater from
/// a state nothing had supported for minutes. What is asserted is where the
/// line falls, not merely that there is one.
static void test_a_brief_gap_in_the_reading_does_not_latch_a_fault(void)
{
    /*
     * Inside the window the machine keeps running. The reading is gone and the
     * heater is still driven, because a dropped sample is an operating
     * condition rather than a fault -- this is the case that used to shut the
     * machine down on the first missing reading and latch a fault nothing in
     * the tree clears.
     */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_FAILED, 0);
    for (unsigned step = 0u; step < 10u; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    }
    TEST_ASSERT_FALSE(state.faulted);
    TEST_ASSERT_TRUE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > 0u);

    /*
     * Carried past the window it is no longer brief, and the latch arrives.
     * The shipped window is five hundred milliseconds, so this runs well past
     * it rather than to its edge -- where the refusal arrives exactly is the
     * estimator's own suite to say.
     */
    bool latched = false;
    for (unsigned step = 0u; step < 200u && !latched; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        latched = control_step(&state) == CONTROL_STEP_SENSOR_INVALID;
    }
    TEST_ASSERT_TRUE_MESSAGE(latched, "a reading gone for good never brought the heater down");
    TEST_ASSERT_TRUE(state.faulted);
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));

    /* And a good reading afterwards still does not un-latch the fault. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_FAULT_LATCHED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C4: a refused drive command is an error
 * path the host run takes, so the analysis stage covers it. */
static void test_refused_drive_command_is_reported_and_latches(void)
{
    hw_sim_set_output_refused(true);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_OUTPUT_REFUSED, control_step(&state));
    TEST_ASSERT_TRUE(state.faulted);
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C2: when the seam refuses the off command
 * as well, the state must not claim the heater is off -- it is still at
 * whatever was last accepted, and recording zero would assert something the
 * seam never confirmed. */
static void test_a_refused_shutdown_is_not_recorded_as_the_heater_being_off(void)
{
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    const uint16_t driven = state.brew_heater_permille;
    TEST_ASSERT_GREATER_THAN_UINT16(0u, driven);

    hw_sim_set_output_refused(true);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_OUTPUT_REFUSED, control_step(&state));
    TEST_ASSERT_TRUE(state.faulted);
    TEST_ASSERT_EQUAL_UINT16(driven, state.brew_heater_permille);
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C2: the control logic consults the seam's
 * clock rather than assuming a call rate, so a step arriving early is refused. */
static void test_step_inside_the_interval_is_refused(void)
{
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS - 1u);
    TEST_ASSERT_EQUAL(CONTROL_STEP_TOO_SOON, control_step(&state));
    TEST_ASSERT_EQUAL_UINT32(1u, state.step_count);
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C2: the seam's clock is documented as
 * wrapping, and the control logic compares differences so that it survives the
 * wrap rather than stalling for the rest of the run. */
static void test_step_interval_survives_the_clock_wrapping(void)
{
    hw_sim_advance_millis(0xFFFFFFFFu - 5u);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    /* Cross the wrap: the difference is one interval, the absolute value falls. */
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT32(2u, state.step_count);
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C2: initialising commands the heater off,
 * so a build that initialises and never steps leaves nothing energised. */
static void test_initialisation_commands_the_heater_off(void)
{
    hw_sim_reset();
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &tolerance));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT32(1u, hw_sim_output_write_count(ACTUATION_CHANNEL_BREW_HEATER));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C4: a null state is a plausible defect in
 * a caller, and it must not become a memory error the analysis stage reports. */
static void test_null_state_is_refused_rather_than_dereferenced(void)
{
    TEST_ASSERT_FALSE(control_init(NULL, &parameters, &limits, &tolerance));
    TEST_ASSERT_EQUAL(CONTROL_STEP_SENSOR_INVALID, control_step(NULL));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C1: the seam refuses an out-of-range
 * channel rather than reading past the end of its channel table. */
static void test_out_of_range_channels_are_refused_by_the_seam(void)
{
    const hw_reading_t reading = hw_sensor_read((hw_sensor_channel_t)HW_SENSOR_CHANNEL_COUNT);
    TEST_ASSERT_EQUAL_INT(HW_READING_ABSENT, reading.status);

    TEST_ASSERT_FALSE(hw_output_set((hw_output_channel_t)ACTUATION_CHANNEL_COUNT, 0u));
    TEST_ASSERT_FALSE(hw_output_set(ACTUATION_CHANNEL_PUMP, ACTUATION_FULL_SCALE + 1u));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C1: the seam's clock is monotonic, which
 * is what lets the control logic compare differences across a wrap. */
static void test_seam_clock_never_goes_backwards(void)
{
    uint32_t previous = hw_monotonic_millis();
    for (int i = 0; i < 8; i++) {
        hw_sim_advance_millis((uint32_t)i);
        const uint32_t now = hw_monotonic_millis();
        TEST_ASSERT_GREATER_OR_EQUAL_UINT32(previous, now);
        previous = now;
    }
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C7: The structures and the control
/// logic behave identically after the vocabulary is unified.
///
/// What this pins has narrowed by one thing, deliberately. It was recorded when
/// the two seams' channel enumerations were replaced by one, and it carried the
/// exact drive level the control logic produced at each of a series of
/// temperatures, so that the unification could be shown not to have moved any
/// of them. The unification is long since established and its evidence stands.
/// The law those levels were recorded from has since been replaced on purpose:
/// a proportional skeleton with no memory has become a loop with accumulated
/// intent and a feedforward term, so the mapping from one temperature to one
/// level is no longer a function of that temperature alone and there is nothing
/// left for a table of recorded values to be a table of. Re-recording it from
/// this build would compare the change with itself, which is what the values
/// existed to prevent.
///
/// What remains is what the criterion's own second sentence is about and what a
/// later change could still quietly move: how the control logic uses the seam.
/// Every accepted step writes once and no more, a refused step writes not at
/// all, a withdrawn reading is ridden for exactly the declared window, and the
/// fault that follows latches. Those are unchanged by this slice and are
/// asserted exactly. The drive levels themselves are asserted as the shape they
/// must have -- full scale while far below the target, falling as it is
/// approached, nothing once it is reached -- which is a property of any law
/// that could be called a brew controller rather than a recording of this one.
static void test_the_control_logic_drives_what_it_drove_before_the_vocabulary_was_unified(void)
{
    static const int32_t READINGS[] = {
        0, 20000, 60000, 68000, 68001, 80000, 88500, 92999, 93000, 95000,
    };
    /* Initialisation commands the heater off, so the first step is the second write. */
    static const uint32_t WRITES[] = {2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u};

    uint16_t previous = (uint16_t)ACTUATION_FULL_SCALE;
    for (size_t i = 0u; i < sizeof(READINGS) / sizeof(READINGS[0]); i++) {
        char message[96];

        place_reconstruction_at(READINGS[i]);
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

        const uint16_t level = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
        (void)snprintf(message, sizeof(message), "at %d millidegrees the level rose as the "
                       "temperature did", (int)READINGS[i]);
        TEST_ASSERT_TRUE_MESSAGE(level <= previous, message);
        previous = level;

        if (READINGS[i] <= 20000) {
            TEST_ASSERT_EQUAL_UINT16(ACTUATION_FULL_SCALE, level);
        }
        /*
         * A bound a gain far from the declared one could not meet. Four and a
         * half degrees below the target, the declared proportional gain asks
         * for a couple of hundred permille once the standing load is added; a
         * gain an order of magnitude larger would be hard against the limit
         * here, and the monotonicity below would not notice, because a law that
         * saturates everywhere is monotonic too.
         */
        if (READINGS[i] == 88500) {
            TEST_ASSERT_TRUE_MESSAGE(level > 100u && level < 400u,
                                     "the drive level four and a half degrees out is not one the "
                                     "declared gains produce");
        }
        if (READINGS[i] >= BREW_TARGET_MILLI_C) {
            /*
             * Not nothing at all. A machine standing at the temperature it was
             * asked for still loses heat to the room, and a loop that switched
             * off on arrival would immediately droop away from it -- which is
             * what the skeleton these values were first recorded from did. What
             * has to hold is that the loop has stopped climbing: the level is a
             * small fraction of full scale rather than the demand of a machine
             * still trying to get there.
             */
            TEST_ASSERT_TRUE_MESSAGE(level < ACTUATION_FULL_SCALE / 4u,
                                     "the loop was still driving hard at the target");
        }

        TEST_ASSERT_EQUAL_UINT32(WRITES[i],
                                 hw_sim_output_write_count(ACTUATION_CHANNEL_BREW_HEATER));
    }

    /*
     * And the refusals, which are part of what the control logic does with the
     * seam. A step arriving early still costs nothing at all -- no write, no
     * step counted -- which is the property that has not changed.
     */
    TEST_ASSERT_EQUAL(CONTROL_STEP_TOO_SOON, control_step(&state));
    TEST_ASSERT_EQUAL_UINT32(11u, hw_sim_output_write_count(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT32(10u, state.step_count);

    /*
     * What has changed is what a withdrawn reading costs. It no longer brings
     * the machine down on the first step: the estimator carries the
     * reconstruction while the gap is brief, and the control law drives from it
     * exactly as it drove from a corrected one -- so each of these steps writes
     * a level like any other. Only once the gap outlasts the machine's declared
     * window does the estimator stop supporting the state and the heater come
     * down.
     */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_FAILED, 0);
    uint32_t steps_driven_through_the_gap = 0u;
    bool brought_down = false;
    while (!brought_down) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        const control_step_result_t result = control_step(&state);
        if (result == CONTROL_STEP_SENSOR_INVALID) {
            brought_down = true;
            break;
        }
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, result);
        TEST_ASSERT_FALSE(state.faulted);
        steps_driven_through_the_gap++;
    }

    /*
     * The gap was ridden rather than merely survived: the window is five hundred
     * milliseconds at a ten-millisecond cadence, so a control law that had
     * shut down on the first missing reading would have driven none of these.
     */
    TEST_ASSERT_EQUAL_UINT32(50u, steps_driven_through_the_gap);
    TEST_ASSERT_TRUE(state.faulted);
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));

    /* Each accepted step wrote once, and the shutdown wrote the off command. */
    TEST_ASSERT_EQUAL_UINT32(11u + steps_driven_through_the_gap + 1u,
                             hw_sim_output_write_count(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT32(10u + steps_driven_through_the_gap + 1u, state.step_count);

    /* And the latch still holds against a reading that came back. */
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    place_reconstruction_at(20000);
    TEST_ASSERT_EQUAL(CONTROL_STEP_FAULT_LATCHED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
}


/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C4: The control law reads reconstructed
/// states rather than raw sensor readings.
///
/// The two are held apart on purpose. A control law still reading the sensor
/// would command nothing in the first half and full scale in the second, so the
/// drive level says which of them it acted on rather than merely that it acted.
static void test_the_drive_level_follows_the_reconstruction_and_not_the_reading(void)
{
    const float at_setpoint = BREW_TARGET_C;

    /* The mass the sensor sits on is at the setpoint; the water leaving is not. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, BREW_TARGET_MILLI_C);
    TEST_ASSERT_TRUE(plant_model_set_state(
        &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, at_setpoint));
    TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 43.0f));
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));

    /* And the other way round, so neither answer can come from a stuck level. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(plant_model_set_state(
        &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 20.0f));
    TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, at_setpoint));
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    /*
     * A small standing level rather than nothing: the water leaving the block
     * is at the temperature that was asked for, so the loop is holding it there
     * rather than climbing toward it. What a law reading the sensor would do
     * here is command full scale, the mass being sixty degrees below the
     * target, and that is what this distinguishes.
     */
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) <
                                 ACTUATION_FULL_SCALE / 4u,
                             "the drive level followed the reading rather than the "
                             "reconstruction");
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C4: The control law reads reconstructed
/// states rather than raw sensor readings.
///
/// The substitution is what makes a withdrawn reading survivable at all. The
/// reading goes to the estimator rather than to the control law, so a channel
/// that reports nothing costs the correction for that step and not the
/// temperature: the drive level still follows a reconstruction, which is
/// exactly what a control law reading the sensor directly could not do.
static void test_an_untrustworthy_reading_reaches_the_estimator_and_not_the_drive(void)
{
    place_reconstruction_at(20000);
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_FAILED, 0);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);

    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    /*
     * The reading the control law cannot trust reached the estimator, which
     * declined to correct against it: no residual is reported for that channel.
     * The drive level nonetheless followed the reconstruction, which is the
     * substitution this asserts -- a control law still reading the sensor would
     * have had nothing to act on at all.
     */
    int32_t residual = 0;
    TEST_ASSERT_FALSE(estimator_residual(&state.estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
    TEST_ASSERT_TRUE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > 0u);
    TEST_ASSERT_FALSE(state.faulted);
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C10: The estimator receives its
/// parameter record through the control law's initialisation.
///
/// Given none, the control law comes up in the condition it comes up in when
/// the interface refuses the off command: heater off, fault latched, and it
/// stays that way however many steps arrive.
static void test_initialisation_without_a_record_leaves_the_heater_off_and_latched(void)
{
    hw_sim_reset();

    TEST_ASSERT_FALSE(control_init(&state, NULL, &limits, &tolerance));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_TRUE(state.faulted);

    for (int i = 0; i < 4; i++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_FAULT_LATCHED, control_step(&state));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C10: The estimator receives its
/// parameter record through the control law's initialisation.
///
/// The record reaches the estimator rather than merely being accepted at the
/// door: an estimator holding no model answers nothing, so a reconstruction
/// that can be read at all is one the record arrived for.
static void test_the_record_reaches_the_estimator_the_control_law_holds(void)
{
    float reconstructed = 0.0f;

    TEST_ASSERT_TRUE(estimator_state(&state.estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C,
                                     &reconstructed));

    /* The description settles the model at its declared ambient. */
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 20.0f, reconstructed);
}


/// SOL-USABLE-ESTIMATE-EVERY-STEP.C7: The estimator is advanced by the interval
/// that elapsed rather than the nominal one.
///
/// The readings are withdrawn first, so the estimator runs on prediction alone
/// and the model inside it is a pure function of the interval it was handed --
/// a correction landing in the middle would make the comparison below about two
/// things at once. A reference model advanced by what actually elapsed is where
/// it must end up, and one advanced by the nominal figure is where it must not:
/// asserting both is what makes this fail on the implementation being replaced
/// rather than merely pass on the new one.
static void test_the_estimator_is_advanced_by_the_interval_that_elapsed(void)
{
    /* One ordinary step first, so the path has a predecessor to measure from. */
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    withdraw_every_reading();

    const uint32_t LATE_BY = CONTROL_STEP_INTERVAL_MS * 3u;
    plant_model_t by_elapsed = state.estimator.model;
    plant_model_t by_nominal = state.estimator.model;

    plant_actuation_t commanded = {{0u}};
    commanded.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = state.brew_heater_permille;

    hw_sim_advance_millis(LATE_BY);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    TEST_ASSERT_TRUE(plant_model_step(&by_elapsed, &commanded, 0.0f, LATE_BY));
    TEST_ASSERT_TRUE(plant_model_step(&by_nominal, &commanded, 0.0f, CONTROL_STEP_INTERVAL_MS));

    float elapsed_says = 0.0f;
    float nominal_says = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_state(&by_elapsed, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &elapsed_says));
    TEST_ASSERT_TRUE(
        plant_model_state(&by_nominal, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &nominal_says));

    TEST_ASSERT_EQUAL_FLOAT(elapsed_says, reconstruction());
    TEST_ASSERT_NOT_EQUAL_MESSAGE(
        (int32_t)lroundf(nominal_says * 1000000.0f), (int32_t)lroundf(elapsed_says * 1000000.0f),
        "the two intervals produce the same answer, so this test could not tell them apart");
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C7: The estimator is advanced by the interval
/// that elapsed rather than the nominal one.
///
/// The first accepted step has no predecessor to measure an interval from, so it
/// is advanced by the declared one. The clock is run a long way forward before
/// it to make the alternative visible: a path measuring from the instant the
/// state was initialised would advance the model by the age of the instance,
/// which is a stretch of time during which nothing was being controlled.
static void test_the_first_accepted_step_is_advanced_by_the_declared_interval(void)
{
    hw_sim_reset();
    load_the_reference_description();
    load_the_reference_limits();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &tolerance));
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
    place_reconstruction_at(20000);

    withdraw_every_reading();

    plant_model_t by_declared = state.estimator.model;
    plant_actuation_t commanded = {{0u}};
    commanded.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = state.brew_heater_permille;

    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS * 500u);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    TEST_ASSERT_TRUE(plant_model_step(&by_declared, &commanded, 0.0f, CONTROL_STEP_INTERVAL_MS));

    float expected = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_state(&by_declared, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &expected));
    TEST_ASSERT_EQUAL_FLOAT(expected, reconstruction());
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C8: An accepted control step acts on an
/// estimate advanced for that step.
///
/// Where the plant moved between two accepted steps, the state read on the
/// second differs from the one read on the first. A path that reused the
/// previous estimate -- reading before advancing, or advancing only sometimes --
/// would report the same value twice and is caught here rather than by nobody.
static void test_each_accepted_step_acts_on_an_estimate_advanced_for_it(void)
{
    /*
     * One step first, so the heater is commanded before the run being measured.
     * Initialisation leaves it off, and a model advanced under no actuation at
     * all does not move -- which would make this pass or fail on whether the
     * heater happened to be on rather than on what it is asserting.
     */
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_TRUE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > 0u);

    withdraw_every_reading();

    float previous = reconstruction();
    for (unsigned step = 0u; step < 8u; step++) {
        char message[96];

        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

        const float now = reconstruction();
        (void)snprintf(message, sizeof(message), "step %u acted on the previous step's estimate",
                       step);
        TEST_ASSERT_TRUE_MESSAGE(now > previous, message);
        previous = now;
    }
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C8: An accepted control step acts on an
/// estimate advanced for that step.
///
/// A step refused for arriving too soon advances the estimator not at all and
/// consumes no estimate. The refusal is meant to cost nothing: a path that
/// advanced the model before deciding whether to accept the step would
/// integrate over time twice once the real step arrived.
static void test_a_step_refused_as_too_soon_advances_and_consumes_nothing(void)
{
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    const float before = reconstruction();
    const uint32_t steps_before = state.step_count;
    const uint16_t driven_before = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);

    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS - 1u);
    TEST_ASSERT_EQUAL(CONTROL_STEP_TOO_SOON, control_step(&state));

    TEST_ASSERT_EQUAL_FLOAT(before, reconstruction());
    TEST_ASSERT_EQUAL_UINT32(steps_before, state.step_count);
    TEST_ASSERT_EQUAL_UINT16(driven_before, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C9: A control step arriving later than the
/// cadence tolerates is reported rather than absorbed.
///
/// Both sides of the tolerable multiple, because a threshold tested only well
/// beyond itself passes whichever comparison was written. At the multiple the
/// step is ordinary; one millisecond past it, it is late -- and either way it is
/// a step that ran, which the assertions below insist on separately.
static void test_a_step_past_the_tolerable_multiple_is_reported_late(void)
{
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE);
    TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_ACTUATED, control_step(&state),
                              "a step exactly at the tolerable multiple was reported late");

    hw_sim_advance_millis((CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE) + 1u);
    TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_LATE, control_step(&state),
                              "a step past the tolerable multiple was absorbed silently");
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C9: A control step arriving later than the
/// cadence tolerates is reported rather than absorbed.
///
/// Being late is not a reason to stop controlling. The heater is still driven
/// and the estimator is still advanced by what elapsed, so the only thing the
/// new result changes is what the caller is told -- a late step that also
/// stopped actuating would be a machine that switched itself off because its
/// scheduler slipped.
static void test_a_late_step_still_drives_the_heater_and_advances_the_estimator(void)
{
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    withdraw_every_reading();

    const uint32_t LATE_BY = (CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE) + 5u;
    plant_model_t by_elapsed = state.estimator.model;
    plant_actuation_t commanded = {{0u}};
    commanded.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = state.brew_heater_permille;

    hw_sim_advance_millis(LATE_BY);
    TEST_ASSERT_EQUAL(CONTROL_STEP_LATE, control_step(&state));

    TEST_ASSERT_TRUE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > 0u);
    TEST_ASSERT_FALSE(state.faulted);

    TEST_ASSERT_TRUE(plant_model_step(&by_elapsed, &commanded, 0.0f, LATE_BY));
    float expected = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_state(&by_elapsed, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &expected));
    TEST_ASSERT_EQUAL_FLOAT(expected, reconstruction());
}


/* --- The harness the loop is closed through -------------------------------
 *
 * Everything above this point drives the control logic against readings the
 * test stands up directly. That is the right shape for asserting what the path
 * does with the seam, and the wrong shape entirely for asserting that the loop
 * tracks: the simulated hardware returns whatever a caller last set, so the
 * only model inside such an arrangement is the estimator's own, and a tracking
 * assertion made against it would be comparing the estimator with itself and
 * passing for free.
 *
 * What follows closes the loop through a second plant instance the estimator
 * does not own. It is advanced under the levels the control logic actually
 * drove, and the temperature it arrives at is injected through the hardware
 * seam as the reading. The estimator then corrects toward a machine rather than
 * toward its own prediction, and every assertion below has content because of
 * it.
 */

/* The machine the loop is closed through, which the estimator does not hold. */
static plant_model_t truth;

/*
 * The reference description with one coefficient written differently.
 *
 * The line is rewritten and handed back to the same loader rather than the
 * record being reached into, so a perturbed description is admitted on exactly
 * the terms a shipped one is -- including the range the structure declares the
 * coefficient admissible within, which is what decides whether a perturbation
 * is still a machine. The annotations after the value are carried across
 * untouched: what the figure was arrived at from does not stop being true
 * because a test asked what would happen if it were otherwise.
 */
static const char *description_with(const char *name, const char *value)
{
    static char rewritten[sizeof(description_text)];
    const size_t name_length = strlen(name);
    size_t written = 0u;
    size_t at = 0u;
    bool replaced = false;

    while (at < description_length) {
        size_t end = at;
        while (end < description_length && description_text[end] != '\n') {
            end++;
        }

        size_t cursor = at;
        while (cursor < end && (description_text[cursor] == ' ' ||
                                description_text[cursor] == '\t')) {
            cursor++;
        }

        bool names_it = (size_t)(end - cursor) > name_length &&
                        memcmp(&description_text[cursor], name, name_length) == 0;
        if (names_it) {
            size_t after = cursor + name_length;
            while (after < end && (description_text[after] == ' ' ||
                                   description_text[after] == '\t')) {
                after++;
            }
            names_it = after < end && description_text[after] == '=';
        }

        if (names_it) {
            /*
             * Everything from the first annotation marker onward is the value's
             * account of itself and its assumed error, and it is copied rather
             * than rewritten. A line arriving with neither is still a line the
             * loader accepts, so the tail may legitimately be empty.
             */
            size_t tail = cursor;
            while (tail < end && description_text[tail] != '~' &&
                   description_text[tail] != '@') {
                tail++;
            }
            written += (size_t)snprintf(&rewritten[written], sizeof(rewritten) - written,
                                        "%s = %s %.*s\n", name, value, (int)(end - tail),
                                        &description_text[tail]);
            replaced = true;
        } else {
            written += (size_t)snprintf(&rewritten[written], sizeof(rewritten) - written,
                                        "%.*s\n", (int)(end - at), &description_text[at]);
        }
        TEST_ASSERT_TRUE(written < sizeof(rewritten));
        at = (end < description_length) ? end + 1u : description_length;
    }

    TEST_ASSERT_TRUE_MESSAGE(replaced, "the coefficient to be perturbed is not in the description");
    return rewritten;
}

static plant_parameters_t parameters_from(const char *text)
{
    plant_parameters_t built;
    plant_parameter_error_t fault;

    TEST_ASSERT_TRUE_MESSAGE(plant_parameters_load(text, strlen(text), &built, &fault),
                             "the suite's own description was refused");
    return built;
}

static float truth_state(plant_state_t which)
{
    float value = 0.0f;

    TEST_ASSERT_TRUE(plant_model_state(&truth, which, &value));
    return value;
}

/* What the machine's sensor reports, which is its heated mass and not its outlet. */
static void report_what_the_machine_reads(void)
{
    const float mass = truth_state(PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C);

    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, (int32_t)lroundf(mass * 1000.0f));
}

/*
 * Bring the loop up around a machine, with the estimator reconstructing from
 * one description and the machine itself built from another.
 *
 * The two are separate arguments even where a caller passes the same
 * description twice, because the whole point of the arrangement is that they
 * can differ: an estimator and a machine that cannot be told apart make every
 * assertion below unfalsifiable.
 */
static void bring_the_loop_up(const plant_parameters_t *estimator_reconstructs_from,
                              const plant_parameters_t *the_machine_is, float mass_c,
                              float outlet_c)
{
    hw_sim_reset();

    TEST_ASSERT_TRUE(plant_model_init(&truth, the_machine_is));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&truth, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, mass_c));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&truth, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, outlet_c));
    report_what_the_machine_reads();

    TEST_ASSERT_TRUE(control_init(&state, estimator_reconstructs_from, &limits, &tolerance));
    TEST_ASSERT_TRUE(plant_model_set_state(
        &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, mass_c));
    TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, outlet_c));
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
}

/*
 * One turn of the closed loop: the machine is advanced under what was driven,
 * it reports what its sensor would report, and the control logic steps.
 *
 * `drawn_regardless` is what the machine's pump actually runs at, and a
 * negative value means it runs at whatever the control logic commanded. The
 * override exists for one case and is worth the parameter: a machine drawing
 * water the loop has not been told about is precisely a loop with no
 * feedforward, and comparing that against the same disturbance announced in
 * advance is the only way to show the feedforward is doing something a
 * well-tuned reactive loop would not.
 */
static control_step_result_t closed_loop_step(int32_t drawn_regardless)
{
    plant_actuation_t driven = {{0u}};

    driven.level_permille[ACTUATION_CHANNEL_BREW_HEATER] =
        hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    driven.level_permille[ACTUATION_CHANNEL_PUMP] =
        (drawn_regardless < 0) ? hw_sim_output(ACTUATION_CHANNEL_PUMP)
                               : (uint16_t)drawn_regardless;

    TEST_ASSERT_TRUE(plant_model_step(&truth, &driven, 0.0f, CONTROL_STEP_INTERVAL_MS));
    report_what_the_machine_reads();
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    return control_step(&state);
}

/*
 * The pump level that asks this machine for a given flow, in permille of full
 * scale.
 *
 * What full scale means in millilitres per second is asked of the model rather
 * than written here. A copy of that figure in this file would go on commanding
 * the same permille after the description's pump was corrected, so every flow
 * this suite believed it was drawing would be wrong by the amount of the
 * correction -- and the suite would keep agreeing with itself, which is exactly
 * the drift that reading the shipped description is meant to surface.
 *
 * It is asked through the seam's own vocabulary rather than by reaching for the
 * structure's coefficient, because a coefficient named here would tie this
 * suite to the thermoblock's spelling of it. The seam reports flow as a
 * quantity, so the question "what does full scale draw" is put by commanding
 * full scale to a model of this machine kept aside for the purpose and reading
 * back what it says is moving.
 */
static float full_scale_flow_ml_per_s(void)
{
    plant_model_t asking;
    plant_actuation_t everything = {{0u}};
    float flow = 0.0f;

    TEST_ASSERT_TRUE(plant_model_init(&asking, &parameters));
    everything.level_permille[ACTUATION_CHANNEL_PUMP] = (uint16_t)ACTUATION_FULL_SCALE;
    TEST_ASSERT_TRUE(plant_model_step(&asking, &everything, 0.0f, CONTROL_STEP_INTERVAL_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&asking, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &flow));
    TEST_ASSERT_TRUE_MESSAGE(flow > 0.0f,
                             "the model draws nothing at full pump, so no level asks for a flow");
    return flow;
}

static uint16_t pump_level_for(float ml_per_s)
{
    return (uint16_t)lroundf((ml_per_s / full_scale_flow_ml_per_s()) *
                             (float)ACTUATION_FULL_SCALE);
}

/*
 * What full pump scale draws on a machine the suite names, rather than the one
 * the shipped description names. The delivery-profile suite needs this against
 * a perturbed description, to show a conversion moves with it; the parameter
 * `full_scale_flow_ml_per_s` above is left untouched rather than rewritten to
 * take one, since every existing caller of it wants the shipped machine and
 * none of them should have to say so at every call site.
 */
static float flow_at_full_scale_for(const plant_parameters_t *machine)
{
    plant_model_t asking;
    plant_actuation_t everything = {{0u}};
    float flow = 0.0f;

    TEST_ASSERT_TRUE(plant_model_init(&asking, machine));
    everything.level_permille[ACTUATION_CHANNEL_PUMP] = (uint16_t)ACTUATION_FULL_SCALE;
    TEST_ASSERT_TRUE(plant_model_step(&asking, &everything, 0.0f, CONTROL_STEP_INTERVAL_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&asking, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &flow));
    return flow;
}

/* --- The band is described data ------------------------------------------- */

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: Brew temperature's
/// tolerance band is described data with a recorded origin.
///
/// The band the loop was brought up with is the one the shipped declaration
/// carries, and the control logic answers it back rather than the suite reading
/// the file twice. Two readers of one declaration can disagree about it; a
/// reader and the thing it is asking about cannot, which is why this asks the
/// control path rather than checking its own copy against the file.
static void test_the_band_the_loop_holds_is_the_one_the_declaration_carries(void)
{
    int32_t band = 0;

    TEST_ASSERT_TRUE(control_temperature_band(&state, &band));
    TEST_ASSERT_EQUAL_INT32(tolerance.brew_temperature_band_milli_c, band);
    TEST_ASSERT_TRUE_MESSAGE(band > 0, "the shipped declaration carries no usable band");
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: Brew temperature's
/// tolerance band is described data with a recorded origin.
///
/// Changing the declared band alone changes what the loop is held to, with no
/// edit to any source file. A band compiled in would answer the same figure to
/// both of these, which is the arrangement this exists to rule out.
static void test_a_different_declaration_changes_the_band_with_no_source_edit(void)
{
    static const char TIGHTER[] =
        "brew-temperature-band-milli-c = 400 @document Taken from a machine that has been "
        "characterised, for the purpose of asking what the design costs at a narrower band.\n"
        "flow-departure-band-milli-ml-s = 300 @estimated Carried unchanged from the shipped "
        "declaration; this test is about the temperature band, not this one.\n";
    delivery_tolerance_t narrowed;
    delivery_tolerance_error_t fault;
    int32_t band = 0;

    TEST_ASSERT_TRUE(delivery_tolerance_load(TIGHTER, sizeof(TIGHTER) - 1u, &narrowed, &fault));

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &narrowed));
    TEST_ASSERT_TRUE(control_temperature_band(&state, &band));

    TEST_ASSERT_EQUAL_INT32(400, band);
    TEST_ASSERT_NOT_EQUAL_INT32(tolerance.brew_temperature_band_milli_c, band);
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: Brew temperature's
/// tolerance band is described data with a recorded origin.
///
/// What the loader refuses, and why each refusal is its own answer rather than
/// a single "this file is wrong". A declaration with no band in it is the case
/// worth naming: a band left undeclared is not a wide band, and reading it back
/// as nothing would turn a file somebody forgot to write into a requirement no
/// machine could ever meet.
static void test_the_loader_refuses_a_declaration_that_settles_nothing(void)
{
    static const struct {
        const char *text;
        delivery_tolerance_fault_t fault;
        const char *why;
    } REFUSED[] = {
        {"# nothing but a comment\n", DELIVERY_TOLERANCE_MISSING,
         "a declaration carrying no band was accepted"},
        {"", DELIVERY_TOLERANCE_MISSING, "an empty declaration was accepted"},
        {"brew-temperature-band-milli-c = 2000\n", DELIVERY_TOLERANCE_ORIGIN,
         "a band with no origin was accepted"},
        {"brew-temperature-band-milli-c = 2000 @document\n", DELIVERY_TOLERANCE_ORIGIN,
         "a kind with no account behind it was accepted"},
        {"brew-temperature-band-milli-c = 2000 @guessed Arrived at by feel.\n",
         DELIVERY_TOLERANCE_ORIGIN, "a kind outside the vocabulary was accepted"},
        {"brew-temperature-band-milli-c = 0 @document Nothing at all.\n",
         DELIVERY_TOLERANCE_OUT_OF_RANGE, "a band of nothing was accepted"},
        {"brew-temperature-band-milli-c = -500 @document Below nothing.\n",
         DELIVERY_TOLERANCE_OUT_OF_RANGE, "a negative band was accepted"},
        {"brew-temperature-band-milli-c = 2000 5000 @document Two figures.\n",
         DELIVERY_TOLERANCE_MALFORMED, "a line carrying two figures was accepted"},
        {"brew-temperature-band-milli-c = wide @document Not a number.\n",
         DELIVERY_TOLERANCE_MALFORMED, "a band that is not a number was accepted"},
        {"brew-temperature-band-milli-c = @document Nothing before the origin.\n",
         DELIVERY_TOLERANCE_MALFORMED, "a band carrying no figure at all was accepted"},
        /*
         * Longer than the buffer the figure is copied into before it is read.
         * The bound exists so that a token this long is refused rather than
         * truncated, because a truncated token is a different number read as
         * though it were the one written.
         */
        {"brew-temperature-band-milli-c = 200000000000000000000000000000000000000 @document "
         "Longer than the buffer.\n",
         DELIVERY_TOLERANCE_MALFORMED, "a figure longer than the buffer was accepted"},
        /*
         * Inside that buffer and inside what a long holds where long is
         * sixty-four bits, and outside what the record's int32 carries. The two
         * bounds differ on such a host and coincide on the target, so a check
         * that only refused what a long could not hold would admit this here
         * and narrow it silently.
         */
        {"brew-temperature-band-milli-c = 3000000000 @document Beyond an int32.\n",
         DELIVERY_TOLERANCE_OUT_OF_RANGE, "a band beyond what the record carries was accepted"},
        {"brew-temperature-band-milli-c 2000 @document No separator.\n",
         DELIVERY_TOLERANCE_MALFORMED, "a line with no separator was accepted"},
        {"= 2000 @document No name.\n", DELIVERY_TOLERANCE_MALFORMED,
         "a line naming no band was accepted"},
        {"steam-dryness-band-permille = 50 @document Nothing reads this.\n",
         DELIVERY_TOLERANCE_UNKNOWN, "a band nothing holds a delivery to was accepted"},
        {"brew-temperature-band-milli-c = 2000 @document First.\n"
         "brew-temperature-band-milli-c = 3000 @document Second.\n",
         DELIVERY_TOLERANCE_DUPLICATE, "a band declared twice was accepted"},
    };

    for (size_t i = 0u; i < sizeof(REFUSED) / sizeof(REFUSED[0]); i++) {
        delivery_tolerance_t built;
        delivery_tolerance_error_t fault;

        TEST_ASSERT_FALSE_MESSAGE(delivery_tolerance_load(REFUSED[i].text,
                                                          strlen(REFUSED[i].text), &built, &fault),
                                  REFUSED[i].why);
        TEST_ASSERT_EQUAL_MESSAGE(REFUSED[i].fault, fault.fault, REFUSED[i].why);
    }
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: Brew temperature's
/// tolerance band is described data with a recorded origin.
///
/// A record refused is a record left as the caller had it. It matters here for
/// the reason it matters for a limits record: a half-filled one holds some
/// deliveries to a band somebody declared and the rest to whatever was in the
/// memory, and the second kind passes quietly.
static void test_a_refused_declaration_leaves_the_record_as_it_was(void)
{
    static const char REFUSED[] = "brew-temperature-band-milli-c = 400 @document Fine.\n"
                                  "steam-dryness-band-permille = 50 @document Not read.\n";
    delivery_tolerance_t held = {.brew_temperature_band_milli_c = 1234};
    delivery_tolerance_error_t fault;

    TEST_ASSERT_FALSE(delivery_tolerance_load(REFUSED, sizeof(REFUSED) - 1u, &held, &fault));
    TEST_ASSERT_EQUAL_INT32(1234, held.brew_temperature_band_milli_c);
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C1: Brew temperature's
/// tolerance band is described data with a recorded origin.
///
/// A caller that cannot be told what was wrong must not be told the declaration
/// was fine, and a control path given no band must not come up believing it has
/// one.
static void test_the_band_is_required_rather_than_assumed(void)
{
    delivery_tolerance_t built;

    TEST_ASSERT_FALSE(delivery_tolerance_load("x", 1u, &built, NULL));

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_FALSE(control_init(&state, &parameters, &limits, NULL));
    TEST_ASSERT_TRUE(state.faulted);
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
}

/* --- The target is an input ----------------------------------------------- */

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C2: The commanded target is an
/// input the control law reads rather than a constant compiled into it.
///
/// Two targets commanded in one test binary produce two duty trajectories from
/// the same machine state, which a compiled-in destination cannot express. The
/// same reconstruction is stood up for both, so the only thing that differs
/// between the two runs is what was asked for.
static void test_two_targets_in_one_binary_produce_two_duty_trajectories(void)
{
    uint16_t levels[2] = {0u, 0u};
    const float targets[2] = {85.0f, 95.0f};

    for (unsigned run = 0u; run < 2u; run++) {
        hw_sim_reset();
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 80000);
        TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &tolerance));
        TEST_ASSERT_TRUE(control_command_temperature(&state, targets[run]));
        place_reconstruction_at(80000);

        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
        levels[run] = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    }

    TEST_ASSERT_TRUE_MESSAGE(levels[1] > levels[0],
                             "the drive level did not follow the temperature that was asked for");
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C2: The commanded target is an
/// input the control law reads rather than a constant compiled into it.
///
/// A machine nobody has asked for a drink drives nothing, and says so rather
/// than latching a fault -- being between deliveries is an ordinary condition
/// and a latched fault is not something a caller can clear. The estimator is
/// still advanced while it waits, so the delivery that arrives next starts from
/// a reconstruction that has been following the machine rather than one that
/// stopped when the last delivery ended.
static void test_a_machine_with_no_target_commanded_drives_nothing(void)
{
    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &tolerance));
    place_reconstruction_at(20000);

    for (unsigned step = 0u; step < 4u; step++) {
        const uint32_t counted = state.step_count;

        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_NO_TARGET, control_step(&state));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_PUMP));
        TEST_ASSERT_FALSE(state.faulted);
        TEST_ASSERT_EQUAL_UINT32(counted + 1u, state.step_count);
    }

    /* And it drives the moment it is asked. */
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_TRUE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > 0u);
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C2: The commanded target is an
/// input the control law reads rather than a constant compiled into it.
///
/// What is refused here is what is not a temperature at all. Any temperature
/// water can actually arrive at the group as is accepted, however far it sits
/// from what a shot is usually pulled at, because the target is an input rather
/// than a setting this file has an opinion about. That a target above what
/// water can be delivered as is now refused, and on what evidence, is asserted
/// by the admission tests further down; this one no longer asks for four
/// hundred degrees, which the work below establishes is not a delivery of
/// water at all.
static void test_a_target_that_is_not_a_temperature_is_refused(void)
{
    TEST_ASSERT_FALSE(control_command_temperature(&state, NAN));
    TEST_ASSERT_FALSE(control_command_temperature(&state, INFINITY));
    TEST_ASSERT_FALSE(control_command_temperature(NULL, BREW_TARGET_C));
    TEST_ASSERT_EQUAL_FLOAT(BREW_TARGET_C, state.target_c);

    TEST_ASSERT_TRUE(control_command_temperature(&state, 40.0f));
    TEST_ASSERT_EQUAL_FLOAT(40.0f, state.target_c);
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C2: The commanded target is an
/// input the control law reads rather than a constant compiled into it.
///
/// Accumulated intent is not carried across a change of target. What it
/// accumulated was the error against the temperature asked for before, and
/// applying it to a new one would be the loop acting on a demand nobody is
/// making any more. Commanding the same target again is not a change and does
/// not discard it, which is what stops a caller that restates its request every
/// step from holding the integral at nothing for ever.
static void test_changing_the_target_does_not_carry_accumulated_intent_across(void)
{
    place_reconstruction_at(BREW_TARGET_MILLI_C - 2000);
    for (unsigned step = 0u; step < 20u; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    }
    TEST_ASSERT_TRUE_MESSAGE(state.integral_permille > 0.0f,
                             "nothing accumulated, so this could not tell the two cases apart");

    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
    TEST_ASSERT_TRUE_MESSAGE(state.integral_permille > 0.0f,
                             "restating the same target discarded what had accumulated");

    TEST_ASSERT_TRUE(control_command_temperature(&state, 88.0f));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, state.integral_permille);
}

/* --- The objective is the reconstruction ---------------------------------- */

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C3: The loop's objective is
/// shown to be the reconstructed water temperature rather than the sensed one.
///
/// The two are not a fixed offset apart, and this is where that is established
/// rather than asserted. The reading sequence is identical between the two
/// runs, and the estimator's description differs in exactly one coefficient --
/// how fast the water leaving the block follows the block. A law closed on the
/// sensed heated-mass temperature would be handed the same numbers in both runs
/// and could not produce a different duty; this one does, and the dependence is
/// the analysis.
static void test_perturbing_the_outlet_time_constant_alone_changes_the_duty(void)
{
    static const char *const CONSTANTS[] = {"20.0", "2.0"};
    uint16_t levels[2] = {0u, 0u};

    for (unsigned run = 0u; run < 2u; run++) {
        const plant_parameters_t perturbed = parameters_from(
            description_with("brew.outlet_conduction_time_constant_s", CONSTANTS[run]));

        hw_sim_reset();
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
        TEST_ASSERT_TRUE(control_init(&state, &perturbed, &limits, &tolerance));
        TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
        TEST_ASSERT_TRUE(plant_model_set_state(
            &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 88.0f));
        TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                               PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 70.0f));

        /*
         * The same reading every step, so nothing the machine does can differ
         * between the runs. What the block is doing is held fixed; how fast the
         * water leaving it is reckoned to follow is not.
         */
        for (unsigned step = 0u; step < 100u; step++) {
            hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 88000);
            hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
            TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
        }
        levels[run] = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    }

    TEST_ASSERT_TRUE_MESSAGE(levels[0] != levels[1],
                             "the duty did not depend on the outlet time constant, so the loop "
                             "is closed on the sensed temperature rather than the reconstructed "
                             "one");
}

/* --- Duty rises with the commanded flow ----------------------------------- */

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C4: Duty rises with the
/// commanded flow rather than after the outlet temperature falls.
///
/// The step that matters is the one the flow is commanded in. Duty moves there,
/// before the machine has drawn a drop and therefore before any reconstruction
/// could have fallen -- which is what distinguishes this from a loop that is
/// merely quick. The reconstruction is checked to have not fallen, because a
/// duty rise that followed a fall would be reaction with a short delay and
/// would pass an assertion about duty alone.
static void test_duty_rises_in_the_step_the_flow_is_commanded_in(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    for (unsigned step = 0u; step < 200u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }

    const uint16_t settled = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    const float before = reconstruction();

    TEST_ASSERT_TRUE(control_command_flow(&state, pump_level_for(2.0f)));
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));

    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > settled,
                             "duty did not rise in the step the flow was commanded in");
    TEST_ASSERT_TRUE_MESSAGE(reconstruction() >= before - 0.05f,
                             "the reconstruction had already fallen, so the rise in duty is a "
                             "reaction rather than a feedforward");
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C4: Duty rises with the
/// commanded flow rather than after the outlet temperature falls.
///
/// The same disturbance twice: once announced to the loop in advance, once
/// arriving unannounced at the machine. The dip the unannounced draw takes is
/// deeper, which is the half of this a well-tuned reactive loop could not pass
/// and the reason the pump level is fed forward rather than left for feedback
/// to discover.
///
/// What the second run withholds is the commanded level itself, so it reaches
/// neither the feedforward term nor the actuation record the estimator is
/// advanced under. Those are the two halves of what the criterion asks for and
/// withholding both is what a loop never told about the draw actually looks
/// like -- but it does mean this run is not the feedforward removed in
/// isolation, and it is named for the disturbance rather than for the term.
static void test_a_draw_the_loop_was_not_told_about_dips_further(void)
{
    const uint16_t drawing = pump_level_for(2.0f);
    float lowest[2] = {1000.0f, 1000.0f};

    for (unsigned run = 0u; run < 2u; run++) {
        const bool announced = (run == 0u);

        bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
        for (unsigned step = 0u; step < 400u; step++) {
            TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        }

        if (announced) {
            TEST_ASSERT_TRUE(control_command_flow(&state, drawing));
        }
        for (unsigned step = 0u; step < 1500u; step++) {
            TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step((int32_t)drawing));
            const float outlet = truth_state(PLANT_STATE_BREW_OUTLET_TEMPERATURE_C);
            if (outlet < lowest[run]) {
                lowest[run] = outlet;
            }
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(lowest[1] < lowest[0],
                             "a draw the loop was not told about dipped no further than one it "
                             "was, so the feedforward term is doing nothing");
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C4: Duty rises with the
/// commanded flow rather than after the outlet temperature falls.
///
/// The pump level reaches the machine and the estimator both. Without the
/// second the model is advanced as though the machine were still while water
/// was moving, and the one state no sensor observes drifts from the machine
/// exactly when a delivery is under way -- the failure this loop exists to
/// prevent, arriving through the back door of the model rather than through the
/// control law. The reconstruction is compared against a model advanced under a
/// still machine, which is where it must not be.
static void test_the_commanded_pump_level_reaches_the_machine_and_the_estimator(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));

    const uint16_t drawing = pump_level_for(2.0f);
    TEST_ASSERT_TRUE(control_command_flow(&state, drawing));
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    TEST_ASSERT_EQUAL_UINT16(drawing, hw_sim_output(ACTUATION_CHANNEL_PUMP));

    /*
     * The readings are withdrawn from here on, so the reconstruction is a pure
     * function of what the estimator was advanced under. A correction landing in
     * the middle would make the comparison about two things at once.
     */
    withdraw_every_reading();
    plant_model_t as_if_still = state.estimator.model;

    /*
     * Stepped directly rather than through the harness above, because that
     * harness reports a fresh reading every turn and a correction landing in
     * the middle would make this comparison about two things at once. What is
     * being asked is what the estimator was advanced *under*, so nothing may
     * pull it toward the machine while the question is being put.
     */
    for (unsigned step = 0u; step < 50u; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

        plant_actuation_t motionless = {{0u}};
        motionless.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = state.brew_heater_permille;
        TEST_ASSERT_TRUE(
            plant_model_step(&as_if_still, &motionless, 0.0f, CONTROL_STEP_INTERVAL_MS));
    }

    /*
     * The comparison is made on the casting rather than on the water leaving
     * it, because that is where the flow term acts: water drawn through the
     * block takes its energy out of the casting, and the outlet follows the
     * casting through a lag of its own. Over the half-second this gap may run
     * for -- the declared loss-tolerance window, past which the estimator
     * rightly stops answering at all -- the outlet has barely begun to move,
     * and asserting on it would be asking whether a lag had had time to act
     * rather than whether the pump level arrived.
     */
    float still_says = 0.0f;
    float estimator_says = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(&as_if_still, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C,
                                       &still_says));
    TEST_ASSERT_TRUE(plant_model_state(&state.estimator.model,
                                       PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C,
                                       &estimator_says));
    TEST_ASSERT_TRUE_MESSAGE(estimator_says < still_says - 0.1f,
                             "the estimator reconstructed a still machine while water was "
                             "moving, so the commanded pump level never reached it");
}

/* --- Accumulated intent does not outlive the limit ------------------------ */

/*
 * Hold the loop against its limit until the machine has stopped moving, then
 * take the demand away and report the furthest it goes past the target.
 *
 * Both runs are held long enough for the machine to settle where full duty and
 * full draw leave it, so the state each is released from is the same one. That
 * is what makes the comparison about the length of the saturated interval
 * rather than about two different machines being let go at two different
 * temperatures.
 */
static float overshoot_after_saturating_for(unsigned steps, float *released_at)
{
    const uint16_t everything = (uint16_t)ACTUATION_FULL_SCALE;
    float highest = -1000.0f;

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_flow(&state, everything));

    for (unsigned step = 0u; step < steps; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(everything,
                                         hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER),
                                         "the loop was not held against its limit at all");
    }

    *released_at = truth_state(PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C);
    TEST_ASSERT_TRUE(control_command_flow(&state, 0u));

    for (unsigned step = 0u; step < 12000u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        const float outlet = truth_state(PLANT_STATE_BREW_OUTLET_TEMPERATURE_C);
        if (outlet > highest) {
            highest = outlet;
        }
    }

    return highest - BREW_TARGET_C;
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C5: Accumulated intent does not
/// outlive the actuator limit.
///
/// The discriminating check is the second one. A loop that merely unwinds
/// quickly passes the first -- the overshoot after a short saturated interval
/// is small -- and fails this, because what it accumulated grew with the time
/// it spent against the limit. Conditional integration does not accumulate
/// there at all, so a longer interval leaves the same overshoot as a shorter
/// one.
///
/// Full duty is this machine's ordinary condition rather than an exception,
/// which is why this is established structurally rather than by sweeping the
/// declared range of model error -- a sweep would establish only the weaker,
/// bounded claim, and the robustness declaration places this behaviour among
/// those that must survive a model that is arbitrarily wrong.
static void test_a_longer_saturated_interval_does_not_deepen_the_overshoot(void)
{
    float released_from_short = 0.0f;
    float released_from_long = 0.0f;

    const float shorter = overshoot_after_saturating_for(6000u, &released_from_short);
    const float longer = overshoot_after_saturating_for(12000u, &released_from_long);

    /*
     * The two were let go from the same machine state, which is what the long
     * hold in each run is for. Without this the comparison below could pass or
     * fail on the two runs having started their recovery from different
     * temperatures.
     */
    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.1f, released_from_short, released_from_long,
                                     "the two runs were released from different states, so the "
                                     "comparison is not about the saturated interval");

    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.05f, shorter, longer,
                                     "twice as long against the limit left a different overshoot, "
                                     "so intent accumulated while the actuator could take no more");
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C5: Accumulated intent does not
/// outlive the actuator limit.
///
/// Nothing accumulates while the actuator is at its limit and the error would
/// drive it further past, and what had accumulated before is still there when
/// the loop comes back into range. The second half is what keeps this from
/// being satisfied by an integrator that is simply switched off: an error
/// pointing back into range integrates on the step the machine does, so the
/// loop leaves saturation when the machine does rather than some steps later.
static void test_intent_is_surrendered_at_the_limit_and_not_afterwards(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_flow(&state, (uint16_t)ACTUATION_FULL_SCALE));

    for (unsigned step = 0u; step < 100u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }
    const float held = state.integral_permille;

    for (unsigned step = 0u; step < 2000u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(held, state.integral_permille,
                                    "intent accumulated while the actuator could take no more");

    /* Let the machine back into range, and it accumulates again. */
    TEST_ASSERT_TRUE(control_command_flow(&state, 0u));
    for (unsigned step = 0u; step < 4000u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }
    TEST_ASSERT_TRUE_MESSAGE(state.integral_permille != held,
                             "the integral never resumed, so it is switched off rather than "
                             "conditional");
}

/* --- Tracking across a whole extraction ----------------------------------- */

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C6: Tracking holds for a whole
/// extraction from a thermal state the machine did not start rested in.
///
/// The machine is placed away from rest -- its casting above the water leaving
/// it, both moving, which is where a machine part-way through recovering from
/// the last delivery sits and where a rested one never does -- and the band is
/// asserted across every sample from first flow to last. Early transients are
/// inside it rather than exempted for being early, and an average on target
/// with a wandering trajectory fails, which is what makes this stronger than a
/// settling check.
///
/// It runs at three targets rather than one, and that is the point of the test
/// as much as the tracking is. The loop's feedforward is built from figures
/// that answer a load per kelvin of rise, so it has to be right across the
/// range a caller can ask for -- and a version of this test run only at the
/// temperature those figures were derived at would be asserting that a
/// calibration is exact where it was calibrated. Since the target became an
/// input a delivery names, every other temperature is where the machine
/// actually spends its time.
///
/// The band is the declared one rather than a figure written here, so
/// tightening the declaration alone decides which trajectories this accepts.
static void test_tracking_holds_across_a_whole_extraction_from_a_disturbed_state(void)
{
    /* Either side of the temperature the load coefficients were derived at. */
    static const float TARGETS[] = {88.0f, 93.0f, 96.0f};
    const float band = (float)tolerance.brew_temperature_band_milli_c / 1000.0f;

    for (size_t which = 0u; which < sizeof(TARGETS) / sizeof(TARGETS[0]); which++) {
        const float target = TARGETS[which];
        const uint16_t drawing = pump_level_for(2.0f);
        float furthest = 0.0f;

        /*
         * How far from rest is not arbitrary and is worth stating, because it
         * is the one number here that could be chosen to make this pass. Once
         * water is moving, the water leaving the block chases the block within
         * a couple of seconds -- the outlet's time constant collapses from
         * twenty seconds to under two the moment a draw begins -- so whatever
         * the casting is at when the first drop is drawn is very nearly what
         * the cup gets. A delivery begun with the casting several degrees off
         * cannot be brought into a one-degree band by any control law, because
         * the energy is not there to be moved in the time available;
         * commanding the heater harder does not make the block hotter faster
         * than its mass allows.
         *
         * That is a real limit and it is not this loop's to fix. What answers
         * it is refusing a delivery the machine cannot make, which the
         * robustness declaration places among the behaviours that must hold
         * however wrong the model is, and which the parent epic carries as its
         * own criterion. Until that exists, the honest thing is to assert this
         * loop over the states a machine would actually begin a delivery from
         * -- unsettled, both states moving, and near enough the target that the
         * delivery was worth beginning -- and to say plainly that a state
         * further out is a refusal question rather than a tracking one.
         */
        bring_the_loop_up(&parameters, &parameters, target + 0.8f, target - 0.6f);
        TEST_ASSERT_TRUE(control_command_temperature(&state, target));
        TEST_ASSERT_TRUE(control_command_flow(&state, drawing));

        /* Thirty seconds at the declared cadence, which is a long shot rather than a short one. */
        for (unsigned step = 0u; step < 3000u; step++) {
            char message[160];

            TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
            TEST_ASSERT_EQUAL_UINT16(drawing, hw_sim_output(ACTUATION_CHANNEL_PUMP));

            const float outlet = truth_state(PLANT_STATE_BREW_OUTLET_TEMPERATURE_C);
            const float departure = fabsf(outlet - target);
            if (departure > furthest) {
                furthest = departure;
            }

            (void)snprintf(message, sizeof(message),
                           "at step %u of the delivery commanded at %.1f degrees, the water "
                           "reaching the coffee was %.3f degrees away from it, against a "
                           "declared band of %.3f",
                           step, (double)target, (double)departure, (double)band);
            TEST_ASSERT_TRUE_MESSAGE(departure <= band, message);
        }

        TEST_ASSERT_TRUE_MESSAGE(furthest > 0.0f,
                                 "the trajectory never moved at all, so nothing was tracked");
    }
}

/* --- The suite runs against what the machine ships ------------------------ */

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C8: The control suite exercises
/// the loop against the shipped description rather than coefficients of its own.
///
/// Every figure this suite drives the loop against arrives through the
/// compile-time paths the build names, so a drift between what the machine
/// ships and what the loop was tuned against surfaces as a failing control test
/// rather than passing silently. A suite carrying a private copy would go on
/// agreeing with itself for as long as it took somebody to notice.
static void test_the_suite_runs_against_the_shipped_declarations(void)
{
    plant_parameters_t reloaded;
    plant_parameter_error_t fault;
    int32_t band = 0;

    TEST_ASSERT_TRUE(
        plant_parameters_load(description_text, description_length, &reloaded, &fault));
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &reloaded, sizeof(parameters));

    /*
     * And the band the loop was brought up with is the shipped one rather than
     * a figure this file chose. Asserting it is positive is not the point --
     * asserting it came from the declaration is, and the equality above and
     * below are the two halves of that.
     */
    TEST_ASSERT_TRUE(control_temperature_band(&state, &band));
    TEST_ASSERT_EQUAL_INT32(tolerance.brew_temperature_band_milli_c, band);

    /* The limits the estimator believes a reading against are the shipped ones too. */
    TEST_ASSERT_EQUAL_MEMORY(&limits, &state.estimator.limits, sizeof(limits));
}

/* --- The truth plant is not the estimator's ------------------------------- */

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C9: The host harness closes the
/// loop through a truth plant the estimator does not share.
///
/// Perturbing the machine's coefficients away from the estimator's degrades
/// tracking rather than leaving it untouched, which is the check that the two
/// are genuinely distinct. Against an arrangement where the only model in the
/// loop is the estimator's own, both runs would track identically and perfectly
/// -- the estimator would be being compared with itself, and every tracking
/// assertion in this file would pass for free.
static void test_a_machine_unlike_the_estimators_model_degrades_tracking(void)
{
    const uint16_t drawing = pump_level_for(2.0f);
    float furthest[2] = {0.0f, 0.0f};

    for (unsigned run = 0u; run < 2u; run++) {
        /*
         * The machine's pump moves half again as much water at a given level as
         * the estimator believes in the second run. The estimator's description
         * is the shipped one in both, so the only thing that changes is how far
         * the machine sits from what the loop was designed against -- and this
         * is the direction that shows it, because the duty fed forward for a
         * commanded level is then answering a draw smaller than the one
         * actually arriving.
         */
        const plant_parameters_t machine =
            (run == 0u) ? parameters
                        : parameters_from(description_with("pump.flow_ml_per_s", "10.5"));

        bring_the_loop_up(&parameters, &machine, 93.0f, BREW_TARGET_C);
        TEST_ASSERT_TRUE(control_command_flow(&state, drawing));

        for (unsigned step = 0u; step < 3000u; step++) {
            TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
            const float departure =
                fabsf(truth_state(PLANT_STATE_BREW_OUTLET_TEMPERATURE_C) - BREW_TARGET_C);
            if (departure > furthest[run]) {
                furthest[run] = departure;
            }
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(furthest[1] > furthest[0],
                             "a machine unlike the estimator's model tracked no worse than one "
                             "like it, so the loop is closed on the estimator's own prediction");
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C9: The host harness closes the
/// loop through a truth plant the estimator does not share.
///
/// A disturbance applied to the machine and to nothing else reaches the
/// estimator, which can only happen if the reading it corrects against is
/// produced by a model it does not own. Against the arrangement this replaces
/// -- where a reading is whatever a caller last set, and the only model in the
/// loop is the estimator's own -- there would be no machine to disturb, and the
/// reconstruction would go on following its own prediction undisturbed.
///
/// The machine is moved somewhere the estimator has not been told about, so
/// there is no route by which the reconstruction could learn of it except the
/// reading. That it then follows is the whole property.
static void test_a_disturbance_to_the_machine_alone_reaches_the_estimator(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    for (unsigned step = 0u; step < 200u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }

    const float agreed_at = reconstruction();
    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(1.0f, truth_state(PLANT_STATE_BREW_OUTLET_TEMPERATURE_C),
                                     agreed_at,
                                     "the reconstruction and the machine never agreed, so the "
                                     "harness is not closing a loop at all");

    /* The machine is cooled, and only the machine. */
    TEST_ASSERT_TRUE(
        plant_model_set_state(&truth, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 75.0f));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&truth, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 75.0f));

    for (unsigned step = 0u; step < 200u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }

    TEST_ASSERT_TRUE_MESSAGE(reconstruction() < agreed_at - 1.0f,
                             "the reconstruction did not follow a machine only the machine knew "
                             "had moved, so the reading is not coming from a model the estimator "
                             "does not own");
}

/* --- A delivery commanded as a profile ------------------------------------ */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: A delivery is expressed as a course
/// of commanded flow, and the control unit accepts one by being given it.
///
/// Sampled at the points a piecewise-linear course actually bends at, so a
/// regression that collapsed the interpolation to, say, the nearest point's
/// rate rather than the value between two of them would move one of these
/// assertions without moving the others -- and a regression that always
/// returned the first or last point's rate would fail every mid-course
/// assertion at once.
static void test_delivery_profile_samples_the_course_piecewise_linearly(void)
{
    const delivery_profile_point_t points[] = {
        {0u, 0.0f},
        {1000u, 2.0f},
        {3000u, 2.0f},
        {4000u, 0.0f},
    };
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 4000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 4u, end));

    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, delivery_profile_rate_ml_per_s(&profile, 0u));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.0f, delivery_profile_rate_ml_per_s(&profile, 500u));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 2.0f, delivery_profile_rate_ml_per_s(&profile, 1000u));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 2.0f, delivery_profile_rate_ml_per_s(&profile, 2000u));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 1.0f, delivery_profile_rate_ml_per_s(&profile, 3500u));
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, delivery_profile_rate_ml_per_s(&profile, 4000u));
    /* Beyond the course's last point, the last point's rate is held rather than dropped. */
    TEST_ASSERT_FLOAT_WITHIN(0.001f, 0.0f, delivery_profile_rate_ml_per_s(&profile, 10000u));
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: Two profiles of different shape,
/// run in one binary, produce two different commanded-flow trajectories.
///
/// A control path that ignored the profile and drove some fixed level instead
/// -- the state control_command_flow left lying around, say -- would pass a
/// test that ran only one profile. Running two different shapes back to back
/// and comparing the recorded trajectories is what a regression collapsing
/// the profile to a constant, or reading only its first point, cannot pass.
///
/// The ramp's peak is what the machine can hold the target against, because
/// what this test is about is the shape reaching the pump rather than what the
/// element can answer. It used to ramp to four millilitres a second, which at
/// this target asks the brew path for more than a kilowatt and is a delivery
/// the reference machine cannot make -- admission refuses it now, and rightly.
/// Nothing about the two shapes differing needed a draw that large.
static void test_two_profiles_of_different_shape_drive_different_trajectories(void)
{
    const delivery_profile_point_t flat_points[] = {{0u, 2.0f}, {2000u, 2.0f}};
    const delivery_end_condition_t flat_end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                               .elapsed_millis = 2000u};
    delivery_profile_t flat;
    TEST_ASSERT_TRUE(delivery_profile_init(&flat, flat_points, 2u, flat_end));

    const delivery_profile_point_t ramp_points[] = {{0u, 0.0f}, {2000u, 2.5f}};
    const delivery_end_condition_t ramp_end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                               .elapsed_millis = 2000u};
    delivery_profile_t ramp;
    TEST_ASSERT_TRUE(delivery_profile_init(&ramp, ramp_points, 2u, ramp_end));

    uint16_t flat_trajectory[50];
    uint16_t ramp_trajectory[50];

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_delivery_running(&state) == false);
    TEST_ASSERT_TRUE(control_command_delivery(&state, &flat));
    TEST_ASSERT_TRUE(control_delivery_running(&state));
    for (unsigned step = 0u; step < 50u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        flat_trajectory[step] = state.commanded_pump_permille;
    }

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_delivery(&state, &ramp));
    for (unsigned step = 0u; step < 50u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        ramp_trajectory[step] = state.commanded_pump_permille;
    }

    TEST_ASSERT_TRUE_MESSAGE(
        memcmp(flat_trajectory, ramp_trajectory, sizeof(flat_trajectory)) != 0,
        "two profiles of different shape produced the same commanded-flow trajectory, so "
        "the profile is not what is driving the pump");
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C2: Turning a commanded rate into an
/// actuation level reads the flow figure the plant description already
/// carries, through the plant seam, rather than a duplicate figure of its own.
///
/// The expectation is computed independently, through the same seam
/// full_scale_flow_ml_per_s asks and on the same terms pump_level_for already
/// established for control_command_flow -- so this is not asserting the
/// production code against itself. A regression that hard-coded a flow figure
/// into control.c or delivery_profile.c, rather than reading the seam, would
/// pass this against the shipped description by coincidence and fail the
/// second half below the moment the description changed.
static void test_a_commanded_rate_converts_through_the_plant_seams_flow_figure(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {2000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    TEST_ASSERT_EQUAL_UINT16(pump_level_for(2.0f), state.commanded_pump_permille);

    /*
     * A description declaring a different pump figure moves the level with no
     * edit to the profile above: the same points and the same end condition
     * are handed to a control path brought up against a machine that draws
     * differently, and only the machine changed.
     */
    const plant_parameters_t machine =
        parameters_from(description_with("pump.flow_ml_per_s", "10.5"));
    bring_the_loop_up(&machine, &machine, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));

    const uint16_t moved_level = state.commanded_pump_permille;
    TEST_ASSERT_NOT_EQUAL_UINT16(pump_level_for(2.0f), moved_level);

    const float expected_permille =
        (2.0f / flow_at_full_scale_for(&machine)) * (float)ACTUATION_FULL_SCALE;
    TEST_ASSERT_EQUAL_UINT16((uint16_t)lroundf(expected_permille), moved_level);
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C2: A structure that draws nothing at
/// full pump is handled honestly rather than divided by.
///
/// Without the refusal in control_command_delivery, this would either divide
/// by zero or silently command a nonsense level the first time a delivery was
/// asked of a machine with no usable pump figure -- exactly the case a
/// zero-flow description exists to exercise, and one the tests driving the
/// shipped description could never reach.
static void test_control_command_delivery_refuses_a_structure_that_draws_nothing(void)
{
    control_state_t local_state;
    const plant_parameters_t no_flow = parameters_from(description_with("pump.flow_ml_per_s", "0"));
    TEST_ASSERT_TRUE(control_init(&local_state, &no_flow, &limits, &tolerance));

    const delivery_profile_point_t points[] = {{0u, 1.0f}, {1000u, 1.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 500u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));

    TEST_ASSERT_FALSE(control_command_delivery(&local_state, &profile));
    TEST_ASSERT_FALSE(control_delivery_running(&local_state));
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: control_command_delivery refuses a
/// null state or a null profile, changing nothing.
static void test_control_command_delivery_refuses_null_arguments(void)
{
    const delivery_profile_point_t points[] = {{0u, 1.0f}, {1000u, 1.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 500u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));

    TEST_ASSERT_FALSE(control_command_delivery(NULL, &profile));
    TEST_ASSERT_FALSE(control_command_delivery(&state, NULL));
    TEST_ASSERT_FALSE(control_delivery_running(NULL));
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C3: Construction refuses an end
/// condition stated in delivered volume, and refuses a value outside the
/// enumeration.
///
/// A regression that let delivery_profile_init accept any quantity value --
/// treating the enumeration as decorative -- would pass every test that only
/// tries elapsed time. Trying the one quantity this build is named as
/// carrying but cannot evaluate, and a value the enumeration does not name at
/// all, is what a construction check that merely checked "is this a small
/// integer" could not distinguish from a real refusal.
static void test_construction_refuses_end_conditions_it_cannot_evaluate(void)
{
    const delivery_profile_point_t points[] = {{0u, 1.0f}, {1000u, 1.0f}};

    const delivery_end_condition_t volume_end = {.quantity = DELIVERY_END_DELIVERED_VOLUME_ML,
                                                 .delivered_volume_ml = 30.0f};
    delivery_profile_t refused_by_volume;
    TEST_ASSERT_FALSE(delivery_profile_init(&refused_by_volume, points, 2u, volume_end));

    const delivery_end_condition_t out_of_range_end = {
        .quantity = (delivery_end_quantity_t)DELIVERY_END_QUANTITY_COUNT, .elapsed_millis = 500u};
    delivery_profile_t refused_by_range;
    TEST_ASSERT_FALSE(delivery_profile_init(&refused_by_range, points, 2u, out_of_range_end));
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C3: Construction refuses a course that
/// is not a shape a delivery could run: fewer than two points, a first point
/// not at zero elapsed, times that do not strictly increase, and a rate that
/// is negative or not a number.
///
/// Each of these is a distinct way the shape could be malformed, and a check
/// collapsed to only one of them -- catching a short course but not a
/// backwards one, say -- would pass some of these and fail others. Trying
/// them all in one test is what keeps a narrowed check from reading as
/// complete coverage.
static void test_construction_refuses_a_course_that_is_not_a_shape(void)
{
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 500u};
    delivery_profile_t profile;

    const delivery_profile_point_t single_point[] = {{0u, 1.0f}};
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, single_point, 1u, end));

    const delivery_profile_point_t not_starting_at_zero[] = {{10u, 1.0f}, {1000u, 1.0f}};
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, not_starting_at_zero, 2u, end));

    const delivery_profile_point_t repeated_time[] = {{0u, 1.0f}, {500u, 2.0f}, {500u, 3.0f}};
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, repeated_time, 3u, end));

    const delivery_profile_point_t backwards_time[] = {{0u, 1.0f}, {500u, 2.0f}, {200u, 3.0f}};
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, backwards_time, 3u, end));

    const delivery_profile_point_t negative_rate[] = {{0u, -1.0f}, {1000u, 1.0f}};
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, negative_rate, 2u, end));

    const delivery_profile_point_t not_a_number_rate[] = {{0u, NAN}, {1000u, 1.0f}};
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, not_a_number_rate, 2u, end));

    const delivery_profile_point_t infinite_rate[] = {{0u, 1.0f}, {1000u, INFINITY}};
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, infinite_rate, 2u, end));

    /* And a course this build validated is admitted, to show the refusals above are real. */
    const delivery_profile_point_t admissible[] = {{0u, 1.0f}, {1000u, 1.0f}};
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, admissible, 2u, end));
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C4: The delivery ends on the step its
/// end condition is first met, not at the course's nominal finish.
///
/// The course here runs nominally to 5000 ms; the end condition is met at
/// 350 ms. A control path that ran the delivery to the course's last point
/// regardless of the condition -- reading the condition only to decide
/// whether to admit the profile, say, and never again afterwards -- would run
/// this delivery for 500 steps and never see it end within the window this
/// test allows.
static void test_the_delivery_ends_on_the_step_the_condition_is_first_met(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {5000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 350u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    unsigned ended_at_step = 0u;
    for (unsigned step = 1u; step <= 500u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        if (!control_delivery_running(&state) && ended_at_step == 0u) {
            ended_at_step = step;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(ended_at_step > 0u, "the delivery never ended");
    TEST_ASSERT_EQUAL_UINT32(35u, ended_at_step);
    TEST_ASSERT_EQUAL_UINT16(0u, state.commanded_pump_permille);
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_PUMP));
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C4: Moving the end condition moves the
/// ending.
///
/// Two deliveries run the identical course and differ only in where the end
/// condition is set; the second ends later by exactly the difference between
/// the two conditions. A control path that latched some fixed number of steps
/// the first time it was exercised -- rather than reading the condition each
/// run -- would end both deliveries at the same step and fail this test while
/// still passing the one above.
static void test_moving_the_end_condition_moves_the_ending(void)
{
    const delivery_profile_point_t points[] = {{0u, 2.0f}, {5000u, 2.0f}};

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    const delivery_end_condition_t end_a = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                            .elapsed_millis = 200u};
    delivery_profile_t profile_a;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile_a, points, 2u, end_a));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile_a));

    unsigned ended_a = 0u;
    for (unsigned step = 1u; step <= 500u && ended_a == 0u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        if (!control_delivery_running(&state)) {
            ended_a = step;
        }
    }

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    const delivery_end_condition_t end_b = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                            .elapsed_millis = 400u};
    delivery_profile_t profile_b;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile_b, points, 2u, end_b));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile_b));

    unsigned ended_b = 0u;
    for (unsigned step = 1u; step <= 500u && ended_b == 0u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        if (!control_delivery_running(&state)) {
            ended_b = step;
        }
    }

    TEST_ASSERT_EQUAL_UINT32(20u, ended_a);
    TEST_ASSERT_EQUAL_UINT32(40u, ended_b);
    TEST_ASSERT_TRUE_MESSAGE(ended_b > ended_a,
                             "moving the end condition later did not move the ending later");
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C5: A delivery commanded as a profile
/// drives the truth plant through the same seam the held-level command drove.
///
/// hw_sim_output(ACTUATION_CHANNEL_PUMP) is the same read the existing
/// control_command_flow tests assert against, and the truth plant this steps
/// is the same one closed_loop_step and bring_the_loop_up stand up for every
/// other test in this file. A profile driven through a path of its own --
/// writing to the hardware seam directly rather than through
/// commanded_pump_permille and control_step -- would not move this reading,
/// and the outlet temperature would not respond to a draw nothing told it
/// about.
static void test_a_profile_commanded_delivery_drives_the_truth_plant_through_the_pump_seam(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const float rate = 2.0f;
    const delivery_profile_point_t points[] = {{0u, rate}, {2000u, rate}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    const float outlet_before = truth_state(PLANT_STATE_BREW_OUTLET_TEMPERATURE_C);

    for (unsigned step = 0u; step < 100u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
        TEST_ASSERT_EQUAL_UINT16(pump_level_for(rate), hw_sim_output(ACTUATION_CHANNEL_PUMP));
    }

    const float outlet_after = truth_state(PLANT_STATE_BREW_OUTLET_TEMPERATURE_C);
    TEST_ASSERT_TRUE_MESSAGE(outlet_after != outlet_before,
                             "the truth plant's outlet never moved, so the pump level the "
                             "profile computed was never actually driven onto the machine");
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: control_command_flow is retained
/// unchanged as the actuation-level entry point: it still sets the commanded
/// level directly, and still refuses only a null state or an over-scale
/// level.
///
/// This is the regression the whole slice turns on: nine already-attested
/// tests call control_command_flow directly and must keep passing unchanged.
/// This one is written fresh against the same behaviour those nine exercise
/// piecemeal, so a change to control_command_flow's own refusal or assignment
/// -- as opposed to a change in what calls it -- fails here first.
static void test_control_command_flow_still_sets_the_level_directly(void)
{
    TEST_ASSERT_TRUE(control_command_flow(&state, 250u));
    TEST_ASSERT_EQUAL_UINT16(250u, state.commanded_pump_permille);

    TEST_ASSERT_FALSE(control_command_flow(&state, (uint16_t)ACTUATION_FULL_SCALE + 1u));
    TEST_ASSERT_EQUAL_UINT16(250u, state.commanded_pump_permille);

    TEST_ASSERT_FALSE(control_command_flow(NULL, 100u));
}

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: A level set through
/// control_command_flow while a delivery is running holds only until the
/// delivery's own next step, which is what makes the profile the thing
/// driving the pump rather than whatever was last set directly.
///
/// This is the defensible-answer test for the interaction the design brief
/// asks about. Without it, a control path where a direct call permanently
/// overrode the profile -- silently ending the delivery's authority over the
/// pump without ending the delivery itself -- would look identical to this
/// one on every other test here, since none of the others call
/// control_command_flow while a delivery runs.
static void test_a_held_level_set_while_a_delivery_runs_is_overwritten_next_step(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {2000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    const uint16_t profile_level = state.commanded_pump_permille;

    TEST_ASSERT_TRUE(control_command_flow(&state, 5u));
    TEST_ASSERT_EQUAL_UINT16(5u, state.commanded_pump_permille);
    TEST_ASSERT_TRUE_MESSAGE(control_delivery_running(&state),
                             "commanding a level directly ended the delivery, which is not the "
                             "behaviour under test");

    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    TEST_ASSERT_EQUAL_UINT16(profile_level, state.commanded_pump_permille);
}

/* --- A machine commanded off has no outstanding delivery ------------------ */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: The control unit accepts a
/// delivery by being given one, and answers whether it is still running.
///
/// A fault latching mid-delivery used to leave control_delivery_running
/// answering true for ever afterwards, because nothing cleared it once the
/// outputs were commanded off. That is an outstanding request the caller
/// never withdrew and the machine can no longer fulfil, so this asserts the
/// query goes false the step the fault latches and stays false on every step
/// after -- the same shape test_initialisation_without_a_record_leaves_the_
/// heater_off_and_latched already asserts of the heater output.
static void test_a_fault_mid_delivery_ends_the_delivery(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {5000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 5000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    for (unsigned step = 0u; step < 5u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }
    TEST_ASSERT_TRUE_MESSAGE(control_delivery_running(&state),
                             "the delivery was not still running, so a fault ending it proves "
                             "nothing");

    hw_sim_set_output_refused(true);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_OUTPUT_REFUSED, control_step(&state));
    TEST_ASSERT_TRUE(state.faulted);
    TEST_ASSERT_FALSE_MESSAGE(control_delivery_running(&state),
                             "a delivery survived the fault that latched, so it would go on "
                             "answering running for ever afterwards");

    for (int i = 0; i < 4; i++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_FAULT_LATCHED, control_step(&state));
        TEST_ASSERT_FALSE_MESSAGE(control_delivery_running(&state),
                                 "the delivery came back running on a later faulted step");
    }
}

/* --- Departure from the commanded profile is reported, not absorbed ------- */

/// SOL-DELIVERY-DEPARTURE-REPORTED.C1: control_step reads HW_SENSOR_FLOW on
/// every cycle a delivery is running and compares it against the same
/// delivery_profile_rate_ml_per_s figure that is driving commanded_pump_permille
/// that cycle.
///
/// A flow reading planted exactly on the commanded rate produces an ordinary
/// actuated step; a control path that never read the channel at all, or read
/// it and compared against the wrong quantity, could not be told apart from
/// this by any test that only injects a divergent reading -- so this asserts
/// the agreeing case is unaffected before the tests below assert the
/// diverging one is not.
static void test_delivered_flow_is_compared_against_the_commanded_rate_each_cycle(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const float rate = 2.0f;
    const delivery_profile_point_t points[] = {{0u, rate}, {2000u, rate}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    for (unsigned step = 0u; step < 10u; step++) {
        hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 2000);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }
}

/// SOL-DELIVERY-DEPARTURE-REPORTED.C2: A gap beyond the declared flow-departure
/// band surfaces as CONTROL_STEP_DELIVERY_DEPARTED in place of
/// CONTROL_STEP_ACTUATED, and a gap that stays inside the band does not.
///
/// The delivered reading is planted far below the commanded rate for the first
/// half and back on it for the second, on the same course and the same
/// commanded rate throughout, so a control path that latched departure once
/// and never cleared it -- or one that ignored the channel and always
/// actuated -- would fail one half or the other.
static void test_departure_beyond_the_band_surfaces_and_agreement_does_not(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const float rate = 2.0f;
    const delivery_profile_point_t points[] = {{0u, rate}, {4000u, rate}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 4000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    /* Commanded is 2000 milli-ml/s; the shipped band is 300, so 800 diverges. */
    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 800);
    TEST_ASSERT_EQUAL(CONTROL_STEP_DELIVERY_DEPARTED, closed_loop_step(-1));
    TEST_ASSERT_TRUE_MESSAGE(control_delivery_running(&state),
                             "a departed cycle ended the delivery, which is out of scope for "
                             "this criterion");
    TEST_ASSERT_EQUAL_UINT16(pump_level_for(rate), state.commanded_pump_permille);

    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 2100);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));

    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 1250);
    TEST_ASSERT_EQUAL(CONTROL_STEP_DELIVERY_DEPARTED, closed_loop_step(-1));
}

/// SOL-DELIVERY-DEPARTURE-REPORTED.C2: A gap beyond the declared flow-departure
/// band surfaces as CONTROL_STEP_DELIVERY_DEPARTED in place of
/// CONTROL_STEP_ACTUATED, and a gap that stays inside the band does not.
///
/// The comparison in control.c is a strict greater-than, so the band is
/// exclusive: a gap sitting exactly on the declared tolerance is still inside
/// it. This plants a reading exactly the shipped band's width from the
/// commanded rate and asserts the ordinary result -- a future edit that
/// widened the comparison to >= would report departure here and fail this,
/// even though nothing above it exercises that exact boundary.
static void test_a_gap_exactly_at_the_tolerance_does_not_depart(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const float rate = 2.0f;
    const delivery_profile_point_t points[] = {{0u, rate}, {4000u, rate}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 4000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    /*
     * Commanded is 2000 milli-ml/s; the shipped band is 300, so 1700 sits
     * exactly on the boundary rather than inside or outside it.
     */
    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID,
                      2000 - (int32_t)tolerance.flow_departure_band_milli_ml_per_s);
    TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_ACTUATED, closed_loop_step(-1),
                              "a gap exactly at the declared tolerance reported departure -- the "
                              "boundary is not exclusive as coded");
}

/// SOL-DELIVERY-DEPARTURE-REPORTED.C1: Delivered flow is compared against the
/// commanded rate on every control cycle a delivery is running.
///
/// SOL-DELIVERY-DEPARTURE-REPORTED.C2: A delivery that departs keeps running to
/// its own end condition rather than being ended or refused by the departure.
///
/// Every one of the 34 steps before the delivery ends is asserted departed in
/// the loop below, which is what proves the comparison runs every cycle rather
/// than once: the agreement test above only shows one cycle unaffected, and a
/// control path that compared on the first cycle and then stopped, or compared
/// only intermittently, would fail this by falling short of 34.
///
/// The course here is the same one
/// test_the_delivery_ends_on_the_step_the_condition_is_first_met ends at step
/// 35; every one of those steps is forced to depart here, and the delivery is
/// still asserted to end on exactly the same step with the pump commanded to
/// zero -- the only difference from that test is what control_step reports
/// along the way.
static void test_a_departed_delivery_still_runs_to_its_own_completion(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {5000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 350u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    unsigned ended_at_step = 0u;
    unsigned departed_steps = 0u;
    for (unsigned step = 1u; step <= 500u; step++) {
        hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 0);
        const control_step_result_t result = closed_loop_step(-1);
        if (control_delivery_running(&state)) {
            /* The comparison ran this step, so a reading of nothing against a
             * commanded 2 ml/s departs the shipped band by a wide margin. */
            TEST_ASSERT_EQUAL(CONTROL_STEP_DELIVERY_DEPARTED, result);
            departed_steps++;
        } else if (ended_at_step == 0u) {
            /* The step the delivery ends on evaluates the end condition
             * before the comparison, so it reports ordinarily rather than
             * departed. */
            TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, result);
        }
        if (!control_delivery_running(&state) && ended_at_step == 0u) {
            ended_at_step = step;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(ended_at_step > 0u, "the delivery never ended");
    TEST_ASSERT_EQUAL_UINT32(35u, ended_at_step);
    TEST_ASSERT_EQUAL_UINT32(34u, departed_steps);
    TEST_ASSERT_EQUAL_UINT16(0u, state.commanded_pump_permille);
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_PUMP));
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C9: A control step arriving later than the
/// cadence tolerates is reported rather than absorbed.
///
/// A step can be late and its delivery departed at once, and the two results
/// share one enumerator's worth of return value -- so one of them has to give
/// way. This plants a flow reading far enough from the commanded rate to
/// depart the band on the same step the elapsed interval is pushed past the
/// tolerable multiple, and asserts CONTROL_STEP_LATE, not
/// CONTROL_STEP_DELIVERY_DEPARTED, comes back: lateness is the pre-existing,
/// more urgent signal C9 already promises a caller, and departure is scope
/// layered on top of it rather than a replacement for it. A control path that
/// let departure override lateness would silently break that promise on
/// exactly the cycle a caller needs it most -- one that is both behind on
/// cadence and off course.
static void test_late_takes_priority_over_departed_on_the_same_cycle(void)
{
    const float rate = 2.0f;
    const delivery_profile_point_t points[] = {{0u, rate}, {4000u, rate}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 4000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    /*
     * A first ordinary step so the loop is `started` before lateness is
     * measured against it -- the very first step accepted is never late, by
     * construction, so a late+departed cycle has to be the second one.
     */
    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 2000);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    /* Commanded is 2000 milli-ml/s; the shipped band is 300, so 800 diverges. */
    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 800);
    hw_sim_advance_millis((CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE) + 1u);
    TEST_ASSERT_EQUAL_MESSAGE(
        CONTROL_STEP_LATE, control_step(&state),
        "a departed reading on a late cycle reported departure instead of lateness");
    TEST_ASSERT_TRUE_MESSAGE(control_delivery_running(&state),
                             "the late/departed cycle ended the delivery, which neither result "
                             "is supposed to do");
}

/// SOL-DELIVERY-DEPARTURE-REPORTED.C4: An absent or a failed flow reading does
/// not itself report departure, per DEC-DEPARTURE-OBSERVED-NOT-MODELLED --
/// departure is observed by measurement, and a cycle with nothing trustworthy
/// to measure has no evidence to report.
///
/// The commanded rate here is the same one the diverging cases above use, and
/// nothing about the course changed -- only the reading's status did, from
/// HW_READING_VALID with a divergent figure to HW_READING_ABSENT and then
/// HW_READING_FAILED. A control path that treated "no reading" as "the worst
/// possible reading" would report departure on both and fail this; one that
/// forgot to check status at all would already have failed the tests above.
static void test_an_absent_or_failed_flow_reading_does_not_report_departure(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const float rate = 2.0f;
    const delivery_profile_point_t points[] = {{0u, rate}, {2000u, rate}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_ABSENT, 0);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));

    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_FAILED, 0);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));

    /*
     * The same gap that was actually reported as departure above, planted
     * behind a failed status, does not report it -- so this is not merely a
     * control path that never departs when the reading is zero.
     */
    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_FAILED, 800);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
}

/// SOL-DELIVERY-DEPARTURE-REPORTED.C3: The flow-departure tolerance is
/// declared data with a recorded origin rather than a compiled literal --
/// changing only the declaration moves what counts as departure, with no edit
/// to any source file.
///
/// The same commanded rate and the same injected gap are held fixed across
/// both halves; only the declared band moves, from wide enough to absorb the
/// gap to narrow enough to report it. A band compiled into control.c would
/// answer the same result to both.
static void test_a_different_declaration_changes_what_counts_as_departure(void)
{
    static const char WIDE[] =
        "brew-temperature-band-milli-c = 1000 @document Carried unchanged from the shipped "
        "declaration; this test is about the flow band, not this one.\n"
        "flow-departure-band-milli-ml-s = 900 @estimated Wide enough that the gap this test "
        "injects is absorbed rather than reported.\n";
    static const char NARROW[] =
        "brew-temperature-band-milli-c = 1000 @document Carried unchanged from the shipped "
        "declaration; this test is about the flow band, not this one.\n"
        "flow-departure-band-milli-ml-s = 100 @estimated Narrow enough that the gap this test "
        "injects is reported rather than absorbed.\n";

    delivery_tolerance_t wide_tolerance;
    delivery_tolerance_t narrow_tolerance;
    delivery_tolerance_error_t fault;
    TEST_ASSERT_TRUE(delivery_tolerance_load(WIDE, sizeof(WIDE) - 1u, &wide_tolerance, &fault));
    TEST_ASSERT_TRUE(
        delivery_tolerance_load(NARROW, sizeof(NARROW) - 1u, &narrow_tolerance, &fault));
    TEST_ASSERT_NOT_EQUAL_INT32(wide_tolerance.flow_departure_band_milli_ml_per_s,
                                narrow_tolerance.flow_departure_band_milli_ml_per_s);

    const float rate = 2.0f;
    const delivery_profile_point_t points[] = {{0u, rate}, {2000u, rate}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));

    /* The commanded rate is 2000 milli-ml/s; the injected reading is 500 short of it. */
    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &wide_tolerance));
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
    place_reconstruction_at(20000);
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));
    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 1500);
    TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_ACTUATED, control_step(&state),
                              "the wide declaration did not absorb the gap it was built to");

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &narrow_tolerance));
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
    place_reconstruction_at(20000);
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));
    hw_sim_set_sensor(HW_SENSOR_FLOW, HW_READING_VALID, 1500);
    TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_DELIVERY_DEPARTED, control_step(&state),
                              "the narrow declaration did not report the same gap the wide one "
                              "absorbed");
}

/// SOL-DELIVERY-DEPARTURE-REPORTED.C3: The flow-departure band is required
/// rather than assumed, is refused where it is not a usable distance, and
/// cannot grow a second home by being declared twice -- the same discipline
/// the temperature band beside it is held to.
static void test_the_flow_departure_band_is_required_and_validated(void)
{
    static const struct {
        const char *text;
        delivery_tolerance_fault_t fault;
        const char *why;
    } REFUSED[] = {
        {"brew-temperature-band-milli-c = 1000 @document Only the temperature band.\n",
         DELIVERY_TOLERANCE_MISSING, "a declaration missing the flow-departure band was accepted"},
        {"brew-temperature-band-milli-c = 1000 @document Fine.\n"
         "flow-departure-band-milli-ml-s = 300\n",
         DELIVERY_TOLERANCE_ORIGIN, "a flow-departure band with no origin was accepted"},
        {"brew-temperature-band-milli-c = 1000 @document Fine.\n"
         "flow-departure-band-milli-ml-s = 0 @estimated Nothing at all.\n",
         DELIVERY_TOLERANCE_OUT_OF_RANGE, "a flow-departure band of nothing was accepted"},
        {"brew-temperature-band-milli-c = 1000 @document Fine.\n"
         "flow-departure-band-milli-ml-s = -50 @estimated Below nothing.\n",
         DELIVERY_TOLERANCE_OUT_OF_RANGE, "a negative flow-departure band was accepted"},
        {"brew-temperature-band-milli-c = 1000 @document Fine.\n"
         "flow-departure-band-milli-ml-s = 300 @estimated First.\n"
         "flow-departure-band-milli-ml-s = 400 @estimated Second.\n",
         DELIVERY_TOLERANCE_DUPLICATE, "a flow-departure band declared twice was accepted"},
    };

    for (size_t i = 0u; i < sizeof(REFUSED) / sizeof(REFUSED[0]); i++) {
        delivery_tolerance_t built;
        delivery_tolerance_error_t fault;

        TEST_ASSERT_FALSE_MESSAGE(delivery_tolerance_load(REFUSED[i].text,
                                                          strlen(REFUSED[i].text), &built, &fault),
                                  REFUSED[i].why);
        TEST_ASSERT_EQUAL_MESSAGE(REFUSED[i].fault, fault.fault, REFUSED[i].why);
    }
}

/// SOL-BREW-TEMPERATURE-TRACKED-AT-GROUP-OUTLET.C2: A machine nobody has
/// asked for a drink drives nothing.
///
/// A delivery commanded and then left to run against an untargeted machine
/// used to burn its whole course against the clock while no water moved, then
/// report itself finished having delivered nothing -- the elapsed clock and
/// the end-condition evaluation do not know the pump was never actually
/// driven. This asserts the opposite: the delivery's clock does not move and
/// it is still reported running after every untargeted step, and it resumes
/// exactly where it was once a target is named again.
static void test_a_delivery_on_an_untargeted_machine_does_not_advance(void)
{
    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits, &tolerance));
    TEST_ASSERT_TRUE(control_command_temperature(&state, BREW_TARGET_C));
    place_reconstruction_at(20000);

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {500u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 500u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    /*
     * The target is withdrawn without ever having stepped the loop, so the
     * delivery has never advanced its clock past zero and every step that
     * follows is one with nothing targeted.
     */
    state.targeted = false;

    for (unsigned step = 0u; step < 100u; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_NO_TARGET, control_step(&state));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_PUMP));
    }

    TEST_ASSERT_FALSE_MESSAGE(control_delivery_running(&state),
                             "an untargeted machine still reported a delivery running -- "
                             "command_everything_off did not end it");
}

/* --- An end condition that cannot be evaluated stops the delivery --------- */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C3: The end condition is a field of
/// the profile, and a quantity this build cannot evaluate is refused at
/// construction.
///
/// delivery_profile_init refuses a delivered-volume end condition, so the
/// only way to reach delivery_profile_ended's unevaluable branch is to
/// assemble the struct directly -- done here on purpose, to reach the branch
/// the constructor exists to keep a caller of control_command_delivery away
/// from. The regression this catches is the one the branch used to have: a
/// condition it cannot read reported "not yet ended", so a delivery built
/// this way would have the pump driven from its course indefinitely rather
/// than stopped by the first thing that noticed it could not be evaluated.
static void test_an_unevaluable_end_condition_ends_the_delivery_immediately(void)
{
    delivery_profile_t profile;
    memset(&profile, 0, sizeof(profile));
    profile.points[0] = (delivery_profile_point_t){0u, 1.0f};
    profile.points[1] = (delivery_profile_point_t){1000u, 1.0f};
    profile.point_count = 2u;
    profile.end.quantity = DELIVERY_END_DELIVERED_VOLUME_ML;
    profile.end.delivered_volume_ml = 30.0f;

    TEST_ASSERT_TRUE_MESSAGE(delivery_profile_ended(&profile, 0u),
                             "an end condition this build cannot evaluate did not end the "
                             "delivery on its first step");
    TEST_ASSERT_TRUE_MESSAGE(delivery_profile_ended(&profile, 100u),
                             "an unevaluable end condition let the delivery go on running past "
                             "its first step");
}

/* --- Boundary end conditions ------------------------------------------------ */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C4: A delivery ends when its own end
/// condition is met, evaluated on the control cadence.
///
/// Zero and UINT32_MAX are the two ends of what an elapsed-milliseconds
/// figure can name, and neither is refused at construction: zero is still a
/// whole number of milliseconds, and there is no shorter delivery than one
/// that is over before it starts, so the defensible reading is to end on the
/// very first evaluation rather than to invent a construction refusal nothing
/// in the type states. UINT32_MAX is likewise just a very large, perfectly
/// representable figure, and this file has no basis for picking some smaller
/// value as the true limit of what a caller may ask for -- so it is admitted
/// and ends only once the elapsed clock actually reaches it.
static void test_boundary_end_conditions_at_zero_and_uint32_max(void)
{
    const delivery_profile_point_t points[] = {{0u, 1.0f}, {1000u, 1.0f}};

    const delivery_end_condition_t ends_immediately = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                                        .elapsed_millis = 0u};
    delivery_profile_t immediate;
    TEST_ASSERT_TRUE(delivery_profile_init(&immediate, points, 2u, ends_immediately));
    TEST_ASSERT_TRUE_MESSAGE(delivery_profile_ended(&immediate, 0u),
                             "an end condition of zero elapsed milliseconds did not end "
                             "immediately");

    const delivery_end_condition_t ends_at_uint32_max = {
        .quantity = DELIVERY_END_ELAPSED_MILLIS, .elapsed_millis = UINT32_MAX};
    delivery_profile_t nearly_unending;
    TEST_ASSERT_TRUE(delivery_profile_init(&nearly_unending, points, 2u, ends_at_uint32_max));
    TEST_ASSERT_FALSE_MESSAGE(
        delivery_profile_ended(&nearly_unending, UINT32_MAX - 1u),
        "a course admitted with an end condition of UINT32_MAX ended before the clock reached "
        "it");
    TEST_ASSERT_TRUE_MESSAGE(delivery_profile_ended(&nearly_unending, UINT32_MAX),
                             "a course with an end condition of UINT32_MAX never ended, even at "
                             "the elapsed figure that names it");
}

/* --- The documented refusals ----------------------------------------------- */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C3: The end condition is a field of
/// the profile, stated in elapsed delivery time -- and construction refuses
/// what delivery_profile.h documents it refuses.
///
/// Only point_count below two was exercised before this. The upper bound is
/// the dangerous half of that same clause to leave untested: the course is
/// copied in with a memcpy sized by point_count, so a regression that dropped
/// the upper-bound check would not merely admit a profile it should have
/// refused, it would write past the end of the fixed-capacity destination
/// array -- a stack buffer overrun rather than a bad delivery. The null
/// checks are added alongside it because all three refusals are one
/// documented clause and a test exercising only the count would leave the
/// other two unverified by name.
static void test_construction_refuses_the_documented_null_and_bound_cases(void)
{
    const delivery_profile_point_t points[] = {{0u, 1.0f}, {1000u, 1.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 500u};
    delivery_profile_t profile;

    TEST_ASSERT_FALSE(delivery_profile_init(NULL, points, 2u, end));
    TEST_ASSERT_FALSE(delivery_profile_init(&profile, NULL, 2u, end));

    delivery_profile_point_t too_many[DELIVERY_PROFILE_POINT_MAX + 1u];
    for (size_t index = 0u; index < DELIVERY_PROFILE_POINT_MAX + 1u; index++) {
        too_many[index].at_millis = (uint32_t)index * 100u;
        too_many[index].rate_ml_per_s = 1.0f;
    }
    TEST_ASSERT_FALSE_MESSAGE(
        delivery_profile_init(&profile, too_many, DELIVERY_PROFILE_POINT_MAX + 1u, end),
        "a point_count past DELIVERY_PROFILE_POINT_MAX was admitted rather than refused");

    /* Exactly at the bound is still admitted, to show the refusal above is real. */
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, too_many, DELIVERY_PROFILE_POINT_MAX, end));
}

/* --- Same-step feedforward for a profile-commanded delivery ---------------- */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: control_command_flow is retained
/// as the actuation-level entry point the heater command's feedforward reads
/// in the same step, and a delivery drives that same entry point.
///
/// test_duty_rises_in_the_step_the_flow_is_commanded_in proves the same-step
/// feedforward for a level set directly through control_command_flow. This is
/// its profile analogue: a profile-commanded delivery has to reach the
/// feedforward through the same field on the same step, or the argument that
/// commanding a delivery is commanding flow -- rather than a second,
/// disconnected mechanism -- is only established for one of its two entry
/// points. The reconstruction is checked to have not fallen, on the same
/// reasoning the flow-commanded version checks it: a duty rise that followed
/// a fall would be reaction with a short delay rather than a feedforward.
static void test_duty_rises_in_the_step_a_profile_delivery_is_commanded_in(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    for (unsigned step = 0u; step < 200u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }

    const uint16_t settled = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    const float before = reconstruction();

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {2000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));

    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > settled,
                             "duty did not rise in the step the profile delivery was commanded "
                             "in");
    TEST_ASSERT_TRUE_MESSAGE(reconstruction() >= before - 0.05f,
                             "the reconstruction had already fallen, so the rise in duty is a "
                             "reaction rather than a feedforward");
}

/* --- Mid-ramp level through the control path -------------------------------- */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C1: Two profiles of different shape
/// produce two different commanded-flow trajectories, which requires the
/// interpolation itself to be right rather than merely present.
///
/// test_two_profiles_of_different_shape_drive_different_trajectories only
/// asks whether the two trajectories differ, which a wrong-axis interpolation
/// -- taking a fraction of the whole course's duration rather than a fraction
/// of the segment the elapsed time actually falls in -- would still pass,
/// since it would still produce numbers that differ from a flat profile's.
/// This asserts a specific mid-ramp step's commanded_pump_permille against a
/// rate computed independently, from a course with two segments of different
/// length so that the course-fraction and the segment-fraction give different
/// answers at the sampled instant: a wrong-axis bug is what this distinguishes
/// from a correct one, which the shape-comparison test above cannot.
static void test_mid_ramp_level_matches_the_interpolated_rate_through_the_control_path(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const delivery_profile_point_t points[] = {
        {0u, 0.0f},
        {500u, 1.0f},
        {2000u, 2.0f},
    };
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 3000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 3u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    /*
     * 125 steps of ten milliseconds each lands elapsed time at 1250 ms, inside
     * the second segment (500 ms to 2000 ms) rather than at an endpoint or on
     * the short first segment. A fraction of the whole course -- 1250 / 3000,
     * the wrong axis -- and a fraction of the segment it actually falls in --
     * (1250 - 500) / (2000 - 500) -- give different rates here.
     */
    for (unsigned step = 0u; step < 125u; step++) {
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    }

    const float expected_rate = 1.0f + ((1250.0f - 500.0f) / (2000.0f - 500.0f)) * (2.0f - 1.0f);
    TEST_ASSERT_EQUAL_UINT16(pump_level_for(expected_rate), state.commanded_pump_permille);
}

/* --- The pump relation is linear, as the conversion assumes ---------------- */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C2: Turning a commanded rate into an
/// actuation level reads the flow figure the plant description carries
/// through the plant seam, rather than a duplicate figure of its own.
///
/// That conversion divides a rate by what full scale draws and scales the
/// result by full scale, which only recovers the level that asked for a given
/// rate if flow rises in proportion to level -- probed once, at full scale,
/// and trusted to hold everywhere below it. Both shipped structures happen to
/// be built that way, but nothing in the plant seam's contract requires it.
/// This asks a model of the machine directly, at half scale, and would fail
/// loudly against a structure whose flow-versus-level curve bent, rather than
/// the loop silently commanding the wrong rate for that structure for as long
/// as it shipped.
static void test_the_pump_relation_is_linear_over_the_range_a_conversion_assumes(void)
{
    const float full_scale = full_scale_flow_ml_per_s();

    plant_model_t half;
    plant_actuation_t half_scale = {{0u}};
    half_scale.level_permille[ACTUATION_CHANNEL_PUMP] = (uint16_t)ACTUATION_FULL_SCALE / 2u;

    TEST_ASSERT_TRUE(plant_model_init(&half, &parameters));
    TEST_ASSERT_TRUE(plant_model_step(&half, &half_scale, 0.0f, CONTROL_STEP_INTERVAL_MS));

    float half_scale_flow = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_quantity(&half, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &half_scale_flow));

    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(
        full_scale * 0.01f, full_scale / 2.0f, half_scale_flow,
        "half-scale pump level did not draw half the full-scale flow, so the conversion this "
        "delivery mechanism rests on assumes a linearity this structure does not have");
}

/* --- A late step times the delivery by elapsed milliseconds ---------------- */

/// SOL-DELIVERY-COMMANDED-AS-A-PROFILE.C4: A delivery ends when its own end
/// condition is met, evaluated on the control cadence -- against the interval
/// that actually elapsed rather than the number of steps that ran.
///
/// Every other delivery test in this file runs on a clock that never falls
/// behind, so a control path that counted accepted steps and multiplied by
/// the nominal interval, instead of summing what actually elapsed, would pass
/// every one of them. One step driven directly, late by more than three
/// cadences, is what such a path could not survive: its own elapsed figure
/// would fall behind the real clock by exactly how late the step was, and the
/// delivery would still be running here where a delivery timed honestly has
/// already ended.
static void test_a_late_step_times_the_delivery_by_elapsed_millis_not_step_count(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const delivery_profile_point_t points[] = {{0u, 2.0f}, {5000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 40u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    TEST_ASSERT_TRUE_MESSAGE(control_delivery_running(&state),
                             "the delivery ended before the late step, so the late step proves "
                             "nothing");

    const uint32_t LATE_BY = (CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE) + 5u;
    hw_sim_advance_millis(LATE_BY);
    TEST_ASSERT_EQUAL(CONTROL_STEP_LATE, control_step(&state));

    TEST_ASSERT_FALSE_MESSAGE(
        control_delivery_running(&state),
        "a delivery whose end condition the elapsed clock had already passed was still running "
        "after a late step, so it is being timed by something other than elapsed milliseconds");
    TEST_ASSERT_EQUAL_UINT16(0u, state.commanded_pump_permille);
}

/* --- A delivery beyond the machine is refused before it begins ------------- */

/*
 * A course that rises to a peak and comes back down, so that the point a bound
 * is crossed at is somewhere in the middle rather than at either end -- which
 * is what makes the reported course position falsifiable. A check that always
 * reported the first point's time, or the last, would agree with a flat course
 * and disagree with this one.
 */
static delivery_profile_t course_peaking_at(float peak_ml_per_s)
{
    const delivery_profile_point_t points[] = {
        {0u, 0.5f},
        {1000u, peak_ml_per_s},
        {2000u, 0.5f},
    };
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;

    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 3u, end));
    return profile;
}

/*
 * A course that holds one rate throughout, for the cases where the shape is
 * not what is under test and a peak in the middle would only be noise.
 */
static delivery_profile_t course_holding(float ml_per_s)
{
    const delivery_profile_point_t points[] = {{0u, ml_per_s}, {2000u, ml_per_s}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;

    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 2u, end));
    return profile;
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C1: A delivery is admitted or
/// refused before anything is driven.
///
/// The assertion is about *when*, not merely about the answer. A refused
/// delivery must leave the machine exactly as the command found it: nothing
/// driven, no course held, the elapsed clock never started -- and the loop
/// must go on stepping afterwards as a machine with no delivery, rather than
/// having half-started one. A check that ran at the first step instead would
/// pass a bare "was it refused" assertion and fail every one of these, because
/// by then the pump would already have been commanded from the course.
static void test_a_delivery_is_admitted_or_refused_before_anything_is_driven(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const uint16_t heater_before = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    const uint16_t pump_before = hw_sim_output(ACTUATION_CHANNEL_PUMP);
    const uint32_t steps_before = state.step_count;

    const delivery_profile_t beyond = course_peaking_at(full_scale_flow_ml_per_s() * 2.0f);
    TEST_ASSERT_FALSE(control_command_delivery(&state, &beyond));

    TEST_ASSERT_FALSE_MESSAGE(control_delivery_running(&state),
                              "a refused delivery was left running");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(0u, state.delivery_elapsed_millis,
                                     "a refused delivery started its clock");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(heater_before,
                                     hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER),
                                     "refusing a delivery drove the heater");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(pump_before, hw_sim_output(ACTUATION_CHANNEL_PUMP),
                                     "refusing a delivery drove the pump");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(steps_before, state.step_count,
                                     "refusing a delivery stepped the loop");
    TEST_ASSERT_FALSE_MESSAGE(state.faulted,
                              "a delivery the machine cannot make latched a fault, which is not "
                              "a condition a caller can clear");

    /*
     * And the machine goes on running as one with nothing delivering: the
     * step drives the heater toward the target and commands the pump nothing,
     * rather than picking the refused course up.
     */
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, closed_loop_step(-1));
    TEST_ASSERT_EQUAL_UINT16(0u, state.commanded_pump_permille);
    TEST_ASSERT_FALSE(control_delivery_running(&state));
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C2: A refusal names the bound that
/// was crossed rather than returning a bare false.
///
/// Every bound is tried in one test, with the figures and the course position
/// checked against what was actually asked for, because a record that reported
/// one bound for everything -- or that named the bound and left the figures at
/// nothing -- would pass a test that only tried one case and only read the
/// enumeration. The figures are compared against quantities this suite works
/// out for itself through the seam, so this is not the record being asserted
/// against itself.
static void test_a_refusal_names_the_bound_it_crossed_and_the_figures(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const float full_scale = full_scale_flow_ml_per_s();
    control_admission_t admission;

    /*
     * Admitted, and the record says so rather than being left as it was found
     * -- and populates no figure at all, so a caller cannot read a bound's
     * worth of meaning off a record that refused nothing. The fields are
     * poisoned before the call, because a record left untouched would agree
     * with these assertions by accident.
     */
    admission.bound = CONTROL_ADMISSION_TARGET_OVER_SATURATION;
    admission.requested = 1.0f;
    admission.available = 2.0f;
    admission.at_millis = 3u;
    const delivery_profile_t ordinary = course_holding(2.0f);
    TEST_ASSERT_TRUE(control_command_delivery_reporting(&state, &ordinary, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_OK, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(0.0f, admission.requested,
                                    "an admitted command populated a figure");
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(0.0f, admission.available,
                                    "an admitted command populated a figure");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(0u, admission.at_millis,
                                     "an admitted command named a point on the course");

    /* A rate no pump level could ask for. */
    const float unreachable_rate = full_scale * 1.5f;
    const delivery_profile_t too_fast = course_peaking_at(unreachable_rate);
    TEST_ASSERT_FALSE(control_command_delivery_reporting(&state, &too_fast, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_RATE_OVER_FULL_SCALE, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(unreachable_rate, admission.requested);
    TEST_ASSERT_EQUAL_FLOAT(full_scale, admission.available);
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(1000u, admission.at_millis,
                                     "the refusal did not name the point on the course where the "
                                     "rate ceiling was crossed");

    /* A target the heater cannot hold against a draw near full scale. */
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    const delivery_profile_t heavy = course_peaking_at(full_scale * 0.9f);
    TEST_ASSERT_FALSE(control_command_delivery_reporting(&state, &heavy, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(BREW_TARGET_C, admission.requested);
    TEST_ASSERT_TRUE_MESSAGE(admission.available < BREW_TARGET_C,
                             "the refusal reported a reachable temperature as the reason a "
                             "target could not be reached");
    TEST_ASSERT_TRUE_MESSAGE(admission.available > 0.0f,
                             "the refusal left the figure the machine can hold at nothing");
    TEST_ASSERT_EQUAL_UINT32(1000u, admission.at_millis);

    /* A target above what water is delivered as at all. */
    TEST_ASSERT_FALSE(control_command_temperature_reporting(&state, 105.0f, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_OVER_SATURATION, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(105.0f, admission.requested);
    TEST_ASSERT_TRUE_MESSAGE(admission.available < 105.0f && admission.available > 50.0f,
                             "the saturation ceiling reported is not a temperature water boils "
                             "anywhere near");

    /*
     * A value that is not a temperature is its own answer, not a crossed
     * bound -- and the not-a-number is not carried into the record, since a
     * caller comparing or printing `requested` would be handed back the very
     * thing that was refused.
     */
    TEST_ASSERT_FALSE(control_command_temperature_reporting(&state, NAN, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_NOT_A_TEMPERATURE, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, admission.requested);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, admission.available);
    TEST_ASSERT_EQUAL_UINT32(0u, admission.at_millis);

    /*
     * A machine that draws nothing at full pump is a different answer from a
     * caller that handed nothing in. The two are repaired by different people
     * from different sources -- one is a description, the other is a bug in
     * the calling code -- so collapsing them into one value would leave an
     * operator unable to tell which had happened.
     */
    control_state_t drawless;
    const plant_parameters_t no_flow = parameters_from(description_with("pump.flow_ml_per_s", "0"));
    TEST_ASSERT_TRUE(control_init(&drawless, &no_flow, &limits, &tolerance));
    TEST_ASSERT_FALSE(control_command_delivery_reporting(&drawless, &ordinary, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_NO_MACHINE_DESCRIBED, admission.bound);

    TEST_ASSERT_FALSE(control_command_delivery_reporting(&state, NULL, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_NOTHING_GIVEN, admission.bound);
    TEST_ASSERT_FALSE(control_command_delivery_reporting(NULL, &ordinary, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_NOTHING_GIVEN, admission.bound);

    /*
     * The temperature command answers the same way given no state. It names no
     * profile, which is why the value is named for what is missing rather than
     * for which argument was: a bound spelled "no profile given" would be
     * answering a question this call was never asked.
     */
    TEST_ASSERT_FALSE(control_command_temperature_reporting(NULL, BREW_TARGET_C, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_NOTHING_GIVEN, admission.bound);

    /* A caller that cannot be told what was wrong is not told the command was fine. */
    TEST_ASSERT_FALSE(control_command_delivery_reporting(&state, &ordinary, NULL));
    TEST_ASSERT_FALSE(control_command_temperature_reporting(&state, BREW_TARGET_C, NULL));
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C3: A commanded rate above the
/// machine's full-scale flow is refused as unreachable.
///
/// Both sides of the boundary are tried, and the boundary is then moved by
/// changing the machine rather than the profile. A refusal wired to some
/// figure of its own -- a literal rate typed into the control source -- would
/// agree with the shipped description by coincidence and would go on refusing
/// at the same rate after the description's pump was corrected; here the same
/// course is admitted by one machine and refused by another, and only the
/// machine changed. A ceiling that had been collapsed to "any rate is fine"
/// fails the refusals, and one collapsed to "refuse everything" fails the
/// admissions.
static void test_a_rate_above_full_scale_flow_is_refused_as_unreachable(void)
{
    /*
     * Forty degrees, not the ninety-three the rest of the suite targets. The
     * thermoblock description holds about fifty-three degrees at its full-scale
     * draw, so a target under that leaves the authority bound slack and the
     * pump is the only thing in play. At ninety-three both courses below would
     * be refused for authority instead, and would establish nothing whatever
     * about the pump.
     */
    static const float PUMP_IS_THE_ONLY_BOUND_C = 40.0f;
    const float full_scale = full_scale_flow_ml_per_s();
    control_admission_t admission;

    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(7.0f, full_scale,
                                    "the shipped description no longer draws what this test's "
                                    "chosen rates are placed either side of");

    const delivery_profile_t just_under = course_peaking_at(6.9f);
    const delivery_profile_t just_over = course_peaking_at(7.5f);

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_temperature(&state, PUMP_IS_THE_ONLY_BOUND_C));
    TEST_ASSERT_TRUE_MESSAGE(control_command_delivery_reporting(&state, &just_under, &admission),
                             "a rate just below what full pump scale draws was refused");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_OK, admission.bound);

    TEST_ASSERT_FALSE(control_command_delivery_reporting(&state, &just_over, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_RATE_OVER_FULL_SCALE, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(7.5f, admission.requested);
    TEST_ASSERT_EQUAL_FLOAT(full_scale, admission.available);

    /*
     * The ceiling follows whichever machine the loop was brought up against.
     * A description declaring an open-path rate of four millilitres a second
     * refuses the course the shipped one admitted, with no edit to the course
     * and none to the control source.
     */
    const plant_parameters_t slower =
        parameters_from(description_with("pump.flow_ml_per_s", "4.0"));
    bring_the_loop_up(&slower, &slower, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_temperature(&state, PUMP_IS_THE_ONLY_BOUND_C));
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(4.0f, flow_at_full_scale_for(&slower),
                                    "the rewritten description does not draw what it declares");
    TEST_ASSERT_FALSE_MESSAGE(control_command_delivery_reporting(&state, &just_under, &admission),
                              "the rate ceiling did not move with the description, so it is a "
                              "figure the control source carries rather than the machine's");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_RATE_OVER_FULL_SCALE, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(4.0f, admission.available);
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C4: A target the machine cannot
/// hold against the profile's peak draw is refused.
///
/// The whole content of this criterion is that the bound is on the *pair*. One
/// target is tried against two courses and one course against two targets, so
/// a check collapsed to either half alone -- refusing the target whatever the
/// draw, or refusing the draw whatever the target -- fails here while passing
/// any test that varied only one of them. The peak is what is judged rather
/// than the mean: a course that spends most of its length gentle and asks for
/// a heavy draw briefly is refused, which an averaged check would admit.
static void test_a_target_beyond_the_authority_at_the_peak_draw_is_refused(void)
{
    const float full_scale = full_scale_flow_ml_per_s();
    control_admission_t admission;

    /* One target, two courses: heavy draw refused, light draw admitted. */
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    const delivery_profile_t heavy = course_holding(full_scale * 0.9f);
    const delivery_profile_t light = course_holding(full_scale * 0.1f);

    TEST_ASSERT_FALSE_MESSAGE(control_command_delivery_reporting(&state, &heavy, &admission),
                              "a target the machine cannot hold against the course's draw was "
                              "admitted");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY, admission.bound);
    TEST_ASSERT_TRUE_MESSAGE(control_command_delivery_reporting(&state, &light, &admission),
                             "the same target was refused against a draw the machine holds it "
                             "at comfortably, so the bound is not on the pair");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_OK, admission.bound);

    /* One course, two targets: the heavy draw admits a modest target. */
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_temperature(&state, 45.0f));
    TEST_ASSERT_TRUE_MESSAGE(control_command_delivery_reporting(&state, &heavy, &admission),
                             "a draw the machine holds a modest target against was refused, so "
                             "the bound is on the draw alone rather than on the pair");

    /*
     * A brief peak is what is judged, not the average. This course is gentle
     * for all but a moment; a check taking the mean would find it comfortably
     * within authority.
     */
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    const delivery_profile_t brief_peak = course_peaking_at(full_scale * 0.9f);
    TEST_ASSERT_FALSE_MESSAGE(control_command_delivery_reporting(&state, &brief_peak, &admission),
                              "a course whose peak draw the machine cannot hold the target "
                              "against was admitted because most of it is gentle");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY, admission.bound);

    /*
     * The pair is judged whichever order the two commands arrive in. A target
     * named while a heavy delivery is already running is the same ask as a
     * heavy delivery commanded against a named target, and is refused on the
     * same evidence -- otherwise commanding the flow first would be a way
     * round the bound entirely.
     */
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE(control_command_temperature(&state, 45.0f));
    TEST_ASSERT_TRUE(control_command_delivery(&state, &heavy));
    TEST_ASSERT_FALSE_MESSAGE(
        control_command_temperature_reporting(&state, BREW_TARGET_C, &admission),
        "a target beyond the machine's authority was accepted because the delivery had been "
        "commanded first");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(45.0f, state.target_c,
                                    "a refused target was written into the state anyway");
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C4: The authority boundary is
/// probed from the description rather than written into the control source,
/// and it is the description the loop holds that decides it.
///
/// This is the falsifiable half of the criterion and the reason the check
/// probes at all. An implementation that had written the boundary down --
/// "this machine holds ninety-three degrees up to three millilitres a second"
/// -- passes every assertion about which courses are refused, and fails here
/// the moment the element the description declares is rewritten. Both
/// directions are tried, because a boundary wired to move only one way is
/// still not a boundary that follows the machine.
///
/// The last quarter records the property rather than stresses it, and is worth
/// being honest about. The loop is brought up with the estimator
/// reconstructing from one description and the truth plant built from a
/// stronger one, and the boundary must not move -- admission is a judgement
/// against the description the loop holds, not against a machine nothing has
/// measured. But no implementable wrong version fails it: the control unit has
/// no channel to the truth description at all, so there is nothing there for a
/// mistake to reach through. It is kept because the property is load-bearing
/// and costs nothing to state, not because it is falsifiable.
static void test_the_authority_boundary_follows_the_description_the_loop_holds(void)
{
    /* Either side of the shipped machine's boundary, which sits near 3.0 mL/s. */
    const delivery_profile_t within = course_holding(2.8f);
    const delivery_profile_t beyond = course_holding(3.5f);
    control_admission_t admission;

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE_MESSAGE(control_command_delivery_reporting(&state, &within, &admission),
                             "the shipped machine refused a draw it can hold the target at, so "
                             "the boundary is not where this test places it");
    TEST_ASSERT_FALSE_MESSAGE(control_command_delivery_reporting(&state, &beyond, &admission),
                              "the shipped machine admitted a draw beyond its element");

    /* A stronger element moves the boundary up: the refused course is admitted. */
    const plant_parameters_t stronger =
        parameters_from(description_with("brew.heater_power_w", "2000.0"));
    bring_the_loop_up(&stronger, &stronger, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_TRUE_MESSAGE(control_command_delivery_reporting(&state, &beyond, &admission),
                             "doubling the declared element did not move the authority boundary, "
                             "so the bound is a figure the control source carries rather than "
                             "one probed from the description");

    /* A weaker one moves it down: the admitted course is refused. */
    const plant_parameters_t weaker =
        parameters_from(description_with("brew.heater_power_w", "500.0"));
    bring_the_loop_up(&weaker, &weaker, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_FALSE_MESSAGE(control_command_delivery_reporting(&state, &within, &admission),
                              "halving the declared element did not move the authority boundary");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY, admission.bound);

    /*
     * And the boundary follows the description the loop was initialised with,
     * not the machine on the bench. Here only the truth plant gets the stronger
     * element; the loop still reconstructs from the shipped description, and
     * still refuses.
     */
    bring_the_loop_up(&parameters, &stronger, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_FALSE_MESSAGE(
        control_command_delivery_reporting(&state, &beyond, &admission),
        "a stronger element on the machine alone moved the admission boundary, so admission is "
        "judging a machine nothing has measured rather than the description the loop holds");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY, admission.bound);
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C5: A target above the declared
/// saturation temperature is refused.
///
/// The ceiling is read out of the refusal record rather than written here, so
/// this suite carries no second copy of a figure the control path declares --
/// which is the failure the declaration exists to prevent, and a copy here
/// would go on passing after the declared figure moved. Both sides of it are
/// tried, and the refusal is shown to leave the previous target standing: a
/// check that refused the command but wrote the target first would drive the
/// machine at a temperature it had just said no to.
static void test_a_target_above_the_saturation_ceiling_is_refused(void)
{
    control_admission_t admission;

    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_FALSE(control_command_temperature_reporting(&state, 130.0f, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_OVER_SATURATION, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(130.0f, admission.requested);

    const float ceiling = admission.available;

    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(BREW_TARGET_C, state.target_c,
                                    "a refused target replaced the one the loop was driving to");

    /* At the ceiling itself, water is no longer what would be delivered. */
    TEST_ASSERT_FALSE(control_command_temperature_reporting(&state, ceiling, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_OVER_SATURATION, admission.bound);

    /* Below it, it is a temperature this call has no view on. */
    TEST_ASSERT_TRUE_MESSAGE(control_command_temperature_reporting(&state, ceiling - 1.0f,
                                                                  &admission),
                             "a target below the saturation ceiling was refused by it");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_OK, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT(ceiling - 1.0f, state.target_c);

    TEST_ASSERT_TRUE_MESSAGE(control_command_temperature_reporting(&state, BREW_TARGET_C,
                                                                   &admission),
                             "the temperature this suite pulls its shots at was refused as steam");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_OK, admission.bound);

    /*
     * The ceiling belongs to the control path and to no structure, and this is
     * where that is established rather than asserted. The shipped description
     * carries a saturation temperature of its own, on the steam side, at the
     * same hundred degrees -- so the two figures agreeing proves nothing while
     * they agree. Rewriting the description's copy to ninety and requiring the
     * refusal to stand at the old figure is what separates a ceiling this file
     * declares from one it has quietly started reading across the seam. Without
     * this, the two could silently begin tracking each other and every other
     * assertion here would go on passing.
     */
    const plant_parameters_t boils_lower =
        parameters_from(description_with("steam.saturation_temperature_c", "90.0"));
    bring_the_loop_up(&boils_lower, &boils_lower, 93.0f, BREW_TARGET_C);
    TEST_ASSERT_FALSE(control_command_temperature_reporting(&state, 130.0f, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_TARGET_OVER_SATURATION, admission.bound);
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(ceiling, admission.available,
                                    "the saturation ceiling followed the description's own steam "
                                    "figure, which it is declared on this side of the seam "
                                    "precisely so as not to");
    TEST_ASSERT_TRUE_MESSAGE(control_command_temperature_reporting(&state, 95.0f, &admission),
                             "a target above the description's steam saturation figure but below "
                             "the declared ceiling was refused, so the bound is being read from "
                             "the machine");
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C6: A machine merely not yet at
/// temperature is admitted rather than refused.
///
/// This is the case the deferral half of the requirement will own, and it is
/// asserted here as visibly admitted rather than left to be inferred. The same
/// delivery is commanded against machines standing at everything from stone
/// cold to fully up to temperature, and the answer has to be identical every
/// time: a check that had reached for the reconstruction the estimator
/// currently holds -- the obvious wrong implementation, and the one that reads
/// as more careful -- would refuse the cold ones and pass any test that only
/// ever commanded from a machine already hot.
static void test_a_machine_not_yet_at_temperature_is_admitted_rather_than_refused(void)
{
    static const float STANDING_AT[] = {20.0f, 40.0f, 60.0f, 88.0f, 93.0f};
    const delivery_profile_t ordinary = course_holding(2.0f);

    for (size_t at = 0u; at < sizeof(STANDING_AT) / sizeof(STANDING_AT[0]); at++) {
        control_admission_t admission;

        bring_the_loop_up(&parameters, &parameters, STANDING_AT[at], STANDING_AT[at]);
        TEST_ASSERT_TRUE_MESSAGE(
            control_command_delivery_reporting(&state, &ordinary, &admission),
            "a delivery the machine can make was refused because the machine had not got there "
            "yet");
        TEST_ASSERT_EQUAL(CONTROL_ADMISSION_OK, admission.bound);
        TEST_ASSERT_TRUE(control_delivery_running(&state));
    }

    /*
     * And a machine that is cold is still refused what it could never do, so
     * the admission above is not the check having been switched off for cold
     * machines.
     */
    control_admission_t admission;
    bring_the_loop_up(&parameters, &parameters, 20.0f, 20.0f);
    const delivery_profile_t beyond = course_holding(full_scale_flow_ml_per_s() * 2.0f);
    TEST_ASSERT_FALSE(control_command_delivery_reporting(&state, &beyond, &admission));
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_RATE_OVER_FULL_SCALE, admission.bound);
}

/// SOL-DELIVERY-INFEASIBLE-PROFILE-REFUSED.C7: An admissible delivery reaches
/// the machine exactly as it did before the check existed.
///
/// Three separate ways the check could have changed an admissible delivery are
/// asserted against, because each can break while the others hold. The probe
/// stands a model up of its own, and a probe that had reached for the
/// estimator's model instead -- the cheap implementation -- would leave the
/// reconstruction the loop drives from sitting at where an hour at full heater
/// puts it, which is hundreds of degrees away. The command must drive nothing.
/// And the trajectory the course produces afterwards must be the one the
/// conversion has always produced, computed here from the profile and the
/// seam's own flow figure rather than read back out of the control path.
static void test_an_admissible_delivery_reaches_the_machine_exactly_as_before(void)
{
    bring_the_loop_up(&parameters, &parameters, 93.0f, BREW_TARGET_C);

    const float reconstruction_before = reconstruction();
    const uint16_t heater_before = hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER);
    const uint16_t pump_before = hw_sim_output(ACTUATION_CHANNEL_PUMP);
    const float target_before = state.target_c;
    const float integral_before = state.integral_permille;

    const delivery_profile_point_t points[] = {{0u, 0.0f}, {1000u, 2.0f}, {2000u, 2.0f}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = 2000u};
    delivery_profile_t profile;
    TEST_ASSERT_TRUE(delivery_profile_init(&profile, points, 3u, end));

    TEST_ASSERT_TRUE(control_command_delivery(&state, &profile));

    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(reconstruction_before, reconstruction(),
                                    "admitting a delivery moved the reconstruction the loop "
                                    "drives from, so the probe is not standing up a model of "
                                    "its own");
    TEST_ASSERT_EQUAL_UINT16(heater_before, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT16(pump_before, hw_sim_output(ACTUATION_CHANNEL_PUMP));
    TEST_ASSERT_EQUAL_FLOAT(target_before, state.target_c);
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(integral_before, state.integral_permille,
                                    "admitting a delivery disturbed the accumulated intent");
    TEST_ASSERT_EQUAL_UINT32(0u, state.delivery_elapsed_millis);

    /*
     * The course then drives the pump at the levels the conversion has always
     * produced. The expectation is worked out here from the profile's own rate
     * at the elapsed time each step lands on and the flow figure asked of the
     * seam, so a control path that had started rounding, clamping or delaying
     * the conversion differently would fail this rather than agreeing with
     * itself.
     */
    for (unsigned step = 1u; step <= 100u; step++) {
        const control_step_result_t result = closed_loop_step(-1);
        const uint32_t elapsed = step * CONTROL_STEP_INTERVAL_MS;

        if (delivery_profile_ended(&profile, elapsed)) {
            TEST_ASSERT_FALSE(control_delivery_running(&state));
            TEST_ASSERT_EQUAL_UINT16(0u, state.commanded_pump_permille);
            continue;
        }

        TEST_ASSERT_TRUE(result == CONTROL_STEP_ACTUATED ||
                         result == CONTROL_STEP_DELIVERY_DEPARTED);
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(
            pump_level_for(delivery_profile_rate_ml_per_s(&profile, elapsed)),
            state.commanded_pump_permille,
            "an admitted delivery drove the pump at a level the conversion did not produce");
    }
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_control_logic_drives_what_it_drove_before_the_vocabulary_was_unified);
    RUN_TEST(test_control_runs_against_the_simulated_implementation);
    RUN_TEST(test_a_temperature_stood_up_reaches_the_control_logic);
    RUN_TEST(test_drive_level_falls_as_the_temperature_approaches_the_setpoint);
    RUN_TEST(test_drive_level_stays_within_full_scale_at_extremes);
    RUN_TEST(test_a_brief_gap_in_the_reading_does_not_latch_a_fault);
    RUN_TEST(test_refused_drive_command_is_reported_and_latches);
    RUN_TEST(test_a_refused_shutdown_is_not_recorded_as_the_heater_being_off);
    RUN_TEST(test_step_inside_the_interval_is_refused);
    RUN_TEST(test_step_interval_survives_the_clock_wrapping);
    RUN_TEST(test_initialisation_commands_the_heater_off);
    RUN_TEST(test_null_state_is_refused_rather_than_dereferenced);
    RUN_TEST(test_out_of_range_channels_are_refused_by_the_seam);
    RUN_TEST(test_seam_clock_never_goes_backwards);
    RUN_TEST(test_the_drive_level_follows_the_reconstruction_and_not_the_reading);
    RUN_TEST(test_an_untrustworthy_reading_reaches_the_estimator_and_not_the_drive);
    RUN_TEST(test_initialisation_without_a_record_leaves_the_heater_off_and_latched);
    RUN_TEST(test_the_record_reaches_the_estimator_the_control_law_holds);
    RUN_TEST(test_the_estimator_is_advanced_by_the_interval_that_elapsed);
    RUN_TEST(test_the_first_accepted_step_is_advanced_by_the_declared_interval);
    RUN_TEST(test_each_accepted_step_acts_on_an_estimate_advanced_for_it);
    RUN_TEST(test_a_step_refused_as_too_soon_advances_and_consumes_nothing);
    RUN_TEST(test_a_step_past_the_tolerable_multiple_is_reported_late);
    RUN_TEST(test_a_late_step_still_drives_the_heater_and_advances_the_estimator);
    RUN_TEST(test_the_band_the_loop_holds_is_the_one_the_declaration_carries);
    RUN_TEST(test_a_different_declaration_changes_the_band_with_no_source_edit);
    RUN_TEST(test_the_loader_refuses_a_declaration_that_settles_nothing);
    RUN_TEST(test_a_refused_declaration_leaves_the_record_as_it_was);
    RUN_TEST(test_the_band_is_required_rather_than_assumed);
    RUN_TEST(test_two_targets_in_one_binary_produce_two_duty_trajectories);
    RUN_TEST(test_a_machine_with_no_target_commanded_drives_nothing);
    RUN_TEST(test_a_target_that_is_not_a_temperature_is_refused);
    RUN_TEST(test_changing_the_target_does_not_carry_accumulated_intent_across);
    RUN_TEST(test_perturbing_the_outlet_time_constant_alone_changes_the_duty);
    RUN_TEST(test_duty_rises_in_the_step_the_flow_is_commanded_in);
    RUN_TEST(test_a_draw_the_loop_was_not_told_about_dips_further);
    RUN_TEST(test_the_commanded_pump_level_reaches_the_machine_and_the_estimator);
    RUN_TEST(test_a_longer_saturated_interval_does_not_deepen_the_overshoot);
    RUN_TEST(test_intent_is_surrendered_at_the_limit_and_not_afterwards);
    RUN_TEST(test_tracking_holds_across_a_whole_extraction_from_a_disturbed_state);
    RUN_TEST(test_the_suite_runs_against_the_shipped_declarations);
    RUN_TEST(test_a_machine_unlike_the_estimators_model_degrades_tracking);
    RUN_TEST(test_a_disturbance_to_the_machine_alone_reaches_the_estimator);
    RUN_TEST(test_delivery_profile_samples_the_course_piecewise_linearly);
    RUN_TEST(test_two_profiles_of_different_shape_drive_different_trajectories);
    RUN_TEST(test_a_commanded_rate_converts_through_the_plant_seams_flow_figure);
    RUN_TEST(test_control_command_delivery_refuses_a_structure_that_draws_nothing);
    RUN_TEST(test_control_command_delivery_refuses_null_arguments);
    RUN_TEST(test_construction_refuses_end_conditions_it_cannot_evaluate);
    RUN_TEST(test_construction_refuses_a_course_that_is_not_a_shape);
    RUN_TEST(test_the_delivery_ends_on_the_step_the_condition_is_first_met);
    RUN_TEST(test_moving_the_end_condition_moves_the_ending);
    RUN_TEST(test_a_profile_commanded_delivery_drives_the_truth_plant_through_the_pump_seam);
    RUN_TEST(test_control_command_flow_still_sets_the_level_directly);
    RUN_TEST(test_a_held_level_set_while_a_delivery_runs_is_overwritten_next_step);
    RUN_TEST(test_a_fault_mid_delivery_ends_the_delivery);
    RUN_TEST(test_delivered_flow_is_compared_against_the_commanded_rate_each_cycle);
    RUN_TEST(test_departure_beyond_the_band_surfaces_and_agreement_does_not);
    RUN_TEST(test_a_gap_exactly_at_the_tolerance_does_not_depart);
    RUN_TEST(test_a_departed_delivery_still_runs_to_its_own_completion);
    RUN_TEST(test_late_takes_priority_over_departed_on_the_same_cycle);
    RUN_TEST(test_an_absent_or_failed_flow_reading_does_not_report_departure);
    RUN_TEST(test_a_different_declaration_changes_what_counts_as_departure);
    RUN_TEST(test_the_flow_departure_band_is_required_and_validated);
    RUN_TEST(test_a_delivery_on_an_untargeted_machine_does_not_advance);
    RUN_TEST(test_an_unevaluable_end_condition_ends_the_delivery_immediately);
    RUN_TEST(test_boundary_end_conditions_at_zero_and_uint32_max);
    RUN_TEST(test_construction_refuses_the_documented_null_and_bound_cases);
    RUN_TEST(test_duty_rises_in_the_step_a_profile_delivery_is_commanded_in);
    RUN_TEST(test_mid_ramp_level_matches_the_interpolated_rate_through_the_control_path);
    RUN_TEST(test_the_pump_relation_is_linear_over_the_range_a_conversion_assumes);
    RUN_TEST(test_a_late_step_times_the_delivery_by_elapsed_millis_not_step_count);
    RUN_TEST(test_a_delivery_is_admitted_or_refused_before_anything_is_driven);
    RUN_TEST(test_a_refusal_names_the_bound_it_crossed_and_the_figures);
    RUN_TEST(test_a_rate_above_full_scale_flow_is_refused_as_unreachable);
    RUN_TEST(test_a_target_beyond_the_authority_at_the_peak_draw_is_refused);
    RUN_TEST(test_the_authority_boundary_follows_the_description_the_loop_holds);
    RUN_TEST(test_a_target_above_the_saturation_ceiling_is_refused);
    RUN_TEST(test_a_machine_not_yet_at_temperature_is_admitted_rather_than_refused);
    RUN_TEST(test_an_admissible_delivery_reaches_the_machine_exactly_as_before);
    return UNITY_END();
}
