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
#include "estimator.h"
#include "estimator_limits.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"

static control_state_t state;
static plant_parameters_t parameters;
static estimator_limits_t limits;

static void load_the_reference_description(void)
{
    static char text[16384];

    FILE *const handle = fopen(REFERENCE_DESCRIPTION_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "could not open the reference description");

    const size_t used = fread(text, 1u, sizeof(text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < sizeof(text) - 1u);

    plant_parameter_error_t fault;
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &parameters, &fault));
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
        hw_sim_set_sensor((hw_sensor_channel_t)channel, false, 0);
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

    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, milli_c);
    TEST_ASSERT_TRUE(plant_model_set_state(
        &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, degrees));
    TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, degrees));
}

void setUp(void)
{
    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    load_the_reference_description();
    load_the_reference_limits();
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits));
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

    /* 50 degrees below the setpoint at 40 permille per degree saturates the drive. */
    TEST_ASSERT_EQUAL_UINT16(ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C3: a drive command issued by the control
 * logic arrives at whichever implementation is linked. */
static void test_drive_level_falls_as_the_temperature_approaches_the_setpoint(void)
{
    place_reconstruction_at(CONTROL_BREW_SETPOINT_MILLI_C - 5000);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(200u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));

    place_reconstruction_at(CONTROL_BREW_SETPOINT_MILLI_C);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
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
                                          "loss-tolerance-window-ms = 4000000000\n"
                                          "excursion-bound-milli-c = 2147483647\n";
    const int32_t readings[] = { INT32_MIN, -1000000, 0, CONTROL_BREW_SETPOINT_MILLI_C, INT32_MAX };
    const estimator_limits_t permissive = limits_from(ADMITS_ANYTHING);

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &permissive));

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
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
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
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
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
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT32(1u, hw_sim_output_write_count(ACTUATION_CHANNEL_BREW_HEATER));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C4: a null state is a plausible defect in
 * a caller, and it must not become a memory error the analysis stage reports. */
static void test_null_state_is_refused_rather_than_dereferenced(void)
{
    TEST_ASSERT_FALSE(control_init(NULL, &parameters, &limits));
    TEST_ASSERT_EQUAL(CONTROL_STEP_SENSOR_INVALID, control_step(NULL));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C1: the seam refuses an out-of-range
 * channel rather than reading past the end of its channel table. */
static void test_out_of_range_channels_are_refused_by_the_seam(void)
{
    const hw_reading_t reading = hw_sensor_read((hw_sensor_channel_t)HW_SENSOR_CHANNEL_COUNT);
    TEST_ASSERT_FALSE(reading.valid);

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
static void test_the_control_logic_drives_what_it_drove_before_the_vocabulary_was_unified(void)
{
    /*
     * A climb from cold to past the setpoint, and what the control logic drove
     * on the brew heater at each temperature -- recorded from the build as it
     * stood before the two seams' channel enumerations were replaced by one,
     * and carried here as values. Regenerating them from this build would
     * compare the change with itself and pass whatever it did to the control
     * law.
     *
     * What the temperature arrives by has since changed: the control logic
     * drives from a reconstructed state rather than from the reading, so each
     * one is stood up in the estimator rather than on the sensor. The mapping
     * from a temperature to a drive level is what these values pin, and that is
     * what has to be unchanged -- both by the vocabulary unification these were
     * recorded for, and by the estimator being put in front of it.
     *
     * The write counts are here for the same reason as the levels: a change
     * that drove the right level a different number of times would be a change
     * to what reaches the hardware, and the levels alone would not show it.
     */
    static const int32_t READINGS[] = {
        0, 20000, 60000, 68000, 68001, 80000, 88500, 92999, 93000, 95000,
    };
    static const uint16_t LEVELS[] = {
        1000u, 1000u, 1000u, 1000u, 960u, 520u, 160u, 0u, 0u, 0u,
    };
    /* Initialisation commands the heater off, so the first step is the second write. */
    static const uint32_t WRITES[] = {2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u};

    for (size_t i = 0u; i < sizeof(READINGS) / sizeof(READINGS[0]); i++) {
        place_reconstruction_at(READINGS[i]);
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
        TEST_ASSERT_EQUAL_UINT16(LEVELS[i], hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
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
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
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
    const float at_setpoint = (float)CONTROL_BREW_SETPOINT_MILLI_C / 1000.0f;

    /* The mass the sensor sits on is at the setpoint; the water leaving is not. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, CONTROL_BREW_SETPOINT_MILLI_C);
    TEST_ASSERT_TRUE(plant_model_set_state(
        &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, at_setpoint));
    TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 43.0f));
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));

    /* And the other way round, so neither answer can come from a stuck level. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    TEST_ASSERT_TRUE(plant_model_set_state(
        &state.estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 20.0f));
    TEST_ASSERT_TRUE(plant_model_set_state(&state.estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, at_setpoint));
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
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
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
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

    TEST_ASSERT_FALSE(control_init(&state, NULL, &limits));
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
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    TEST_ASSERT_TRUE(control_init(&state, &parameters, &limits));
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
    return UNITY_END();
}
