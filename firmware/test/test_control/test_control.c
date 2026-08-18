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

#include <stdio.h>

#include "control.h"
#include "estimator.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"

static control_state_t state;
static plant_parameters_t parameters;

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
    TEST_ASSERT_TRUE(control_init(&state, &parameters));
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
    const int32_t readings[] = { INT32_MIN, -1000000, 0, CONTROL_BREW_SETPOINT_MILLI_C, INT32_MAX };

    for (unsigned i = 0; i < sizeof(readings) / sizeof(readings[0]); i++) {
        place_reconstruction_at(readings[i]);
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
        TEST_ASSERT_LESS_OR_EQUAL_UINT16(ACTUATION_FULL_SCALE,
                                         hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    }
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C4: the host build exercises the error
 * paths, not only the happy path -- an untrustworthy reading de-energises. */
static void test_invalid_reading_de_energises_and_latches(void)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_SENSOR_INVALID, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));

    /* A good reading afterwards does not un-latch the fault. */
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
    TEST_ASSERT_TRUE(control_init(&state, &parameters));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT32(1u, hw_sim_output_write_count(ACTUATION_CHANNEL_BREW_HEATER));
}

/* SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C4: a null state is a plausible defect in
 * a caller, and it must not become a memory error the analysis stage reports. */
static void test_null_state_is_refused_rather_than_dereferenced(void)
{
    TEST_ASSERT_FALSE(control_init(NULL, &parameters));
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

    /* And the refusals, which are part of what the control logic does with the seam. */
    TEST_ASSERT_EQUAL(CONTROL_STEP_TOO_SOON, control_step(&state));
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
    TEST_ASSERT_EQUAL(CONTROL_STEP_SENSOR_INVALID, control_step(&state));
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    place_reconstruction_at(20000);
    TEST_ASSERT_EQUAL(CONTROL_STEP_FAULT_LATCHED, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT32(13u, hw_sim_output_write_count(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_EQUAL_UINT32(12u, state.step_count);
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
/// The substitution must not have cost the refusal that was there before it. An
/// untrustworthy reading is one the estimator cannot correct against, and the
/// control law still treats that as no temperature to act on rather than
/// driving from a prediction nothing has checked.
static void test_an_untrustworthy_reading_still_refuses_though_a_reconstruction_exists(void)
{
    place_reconstruction_at(20000);
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);

    TEST_ASSERT_EQUAL(CONTROL_STEP_SENSOR_INVALID, control_step(&state));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER));
    TEST_ASSERT_TRUE(state.faulted);
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

    TEST_ASSERT_FALSE(control_init(&state, NULL));
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

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_control_logic_drives_what_it_drove_before_the_vocabulary_was_unified);
    RUN_TEST(test_control_runs_against_the_simulated_implementation);
    RUN_TEST(test_a_temperature_stood_up_reaches_the_control_logic);
    RUN_TEST(test_drive_level_falls_as_the_temperature_approaches_the_setpoint);
    RUN_TEST(test_drive_level_stays_within_full_scale_at_extremes);
    RUN_TEST(test_invalid_reading_de_energises_and_latches);
    RUN_TEST(test_refused_drive_command_is_reported_and_latches);
    RUN_TEST(test_a_refused_shutdown_is_not_recorded_as_the_heater_being_off);
    RUN_TEST(test_step_inside_the_interval_is_refused);
    RUN_TEST(test_step_interval_survives_the_clock_wrapping);
    RUN_TEST(test_initialisation_commands_the_heater_off);
    RUN_TEST(test_null_state_is_refused_rather_than_dereferenced);
    RUN_TEST(test_out_of_range_channels_are_refused_by_the_seam);
    RUN_TEST(test_seam_clock_never_goes_backwards);
    RUN_TEST(test_the_drive_level_follows_the_reconstruction_and_not_the_reading);
    RUN_TEST(test_an_untrustworthy_reading_still_refuses_though_a_reconstruction_exists);
    RUN_TEST(test_initialisation_without_a_record_leaves_the_heater_off_and_latched);
    RUN_TEST(test_the_record_reaches_the_estimator_the_control_law_holds);
    return UNITY_END();
}
