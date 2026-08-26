/*
 * The steam feed-withhold gate exercised against the structure that
 * describes the reference machine.
 *
 * No control law drives either steam channel outside this file today, so
 * there is no sibling harness to extend: this suite is the first to close
 * the loop between a steam control law and the plant model, and it does so
 * on the same terms test_control.c and test_estimator.c already close it for
 * the brew side -- a truth instance advanced through the plant seam, its
 * channels stood up on the simulated hardware implementation, and the law
 * under test driven only through hw_interface.h.
 *
 * What can be established here is that the gate withholds feed below the
 * declared threshold regardless of a real draw being open, holds an existing
 * pressure deficit rather than letting an open wand widen it further, enables
 * feed the same step the threshold is reached, and reads that threshold as
 * data a declaration can move rather than a figure compiled into the law.
 * What cannot be established here is whether nine hundred milli-bar is the
 * right threshold for a real machine: nothing has been on a bench, and
 * steam_control.declaration says so.
 */
#include <unity.h>

#include <stdio.h>
#include <string.h>

#include "estimator_limits.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"
#include "steam_control.h"
#include "steam_control_declaration.h"

/* The interval every step in this suite advances by. */
#define STEP_INTERVAL_MS 10u

/*
 * A steam temperature comfortably above the reference description's own
 * saturation relation, and comfortably below the two hundred degrees
 * thermoblock.params records the steam thermostat as permitting -- chosen
 * without reaching for either coefficient by name, and confirmed against the
 * plant seam's own quantity below rather than assumed. High enough that the
 * rested pressure it produces clears the declared ready threshold.
 */
#define STEAM_TEMPERATURE_READY_C 180.0f

/*
 * A steam temperature whose rested pressure sits comfortably below the
 * declared ready threshold even once a real draw has sagged it further --
 * confirmed against the plant seam's own quantity below rather than assumed.
 * Used only where a test needs the gate to go on withholding feed while it
 * primes a real, nonzero deficit against the truth plant directly.
 */
#define STEAM_TEMPERATURE_BELOW_READY_C 115.0f

static plant_parameters_t parameters;
static estimator_limits_t limits;
static steam_control_declaration_t declaration;

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

static void load_the_reference_steam_control_declaration(void)
{
    static char text[4096];

    FILE *const handle = fopen(REFERENCE_STEAM_CONTROL_DECLARATION_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "could not open the reference steam control declaration");

    const size_t used = fread(text, 1u, sizeof(text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < sizeof(text) - 1u);

    steam_control_declaration_error_t fault;
    TEST_ASSERT_TRUE(steam_control_declaration_load(text, used, &declaration, &fault));
}

/*
 * A declaration built from text the test writes, for the cases that need a
 * threshold other than the shipped one, or a malformed line the loader is
 * required to refuse. The shipped one is what every other test here runs
 * against.
 */
static bool declaration_from(const char *text, steam_control_declaration_t *built,
                             steam_control_declaration_error_t *fault)
{
    return steam_control_declaration_load(text, strlen(text), built, fault);
}

void setUp(void)
{
    hw_sim_reset();
    load_the_reference_description();
    load_the_reference_limits();
    load_the_reference_steam_control_declaration();
}

void tearDown(void) {}

/// SOL-SIM-STEAM-READINESS-GATE.C1: Steam feed is withheld while measured
/// pressure sits below the declared ready threshold.
///
/// SOL-SIM-STEAM-READINESS-GATE.C5: The feed-withhold policy is exercised in
/// host simulation against the plant model before any hardware exists.
///
/// A truth instance of the reference structure is held at rest, well below
/// the declared threshold, and a real draw is opened against it -- a
/// nonzero steam demand handed to the plant seam on every step, exactly the
/// argument the operator's wand supplies. The gate reads the truth's own
/// pressure by way of the simulated hardware implementation and is asserted
/// to withhold feed on every step regardless: nothing in this test drives
/// the wand through the gate at all, which is the same statement C1's own
/// text makes about the control law.
static void test_feed_withheld_while_pressure_stays_below_threshold_with_the_wand_open(void)
{
    plant_model_t truth;
    steam_control_state_t gate;

    TEST_ASSERT_TRUE(plant_model_init(&truth, &parameters));
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    const plant_actuation_t idle = {{0u}};

    for (int step = 0; step < 20; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&truth, &idle, 3.0f, STEP_INTERVAL_MS));

        float pressure_bar = 0.0f;
        TEST_ASSERT_TRUE(plant_model_quantity(&truth, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &pressure_bar));
        TEST_ASSERT_TRUE_MESSAGE((int32_t)(pressure_bar * 1000.0f) < declaration.ready_pressure_milli_bar,
                                 "the truth plant reached the ready threshold at rest, which this test did not intend");
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                          (int32_t)(pressure_bar * 1000.0f));

        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

        hw_sim_advance_millis(STEP_INTERVAL_MS);
    }
}

/// SOL-SIM-STEAM-READINESS-GATE.C1: Steam feed is withheld while measured
/// pressure sits below the declared ready threshold.
///
/// The boundary itself: a reading one milli-bar below the declared threshold
/// still withholds feed. This is the case an off-by-one in the comparison
/// would first show up on, which a test set comfortably below the threshold
/// would never catch.
static void test_feed_withheld_one_milli_bar_below_threshold(void)
{
    steam_control_state_t gate;
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                      declaration.ready_pressure_milli_bar - 1);

    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
}

/// SOL-SIM-STEAM-READINESS-GATE.C2: Steam feed is enabled once measured
/// pressure reaches the declared ready threshold.
///
/// One instance stepped across the boundary: withheld a milli-bar below it,
/// enabled on the very step the reading reaches it exactly, and still
/// enabled comfortably above it. The middle assertion is C2's own test in
/// its own words -- feed becomes available on the same step the threshold is
/// crossed -- and the two either side of it are the regression protection: a
/// gate that enabled a step early or a step late would still pass a test
/// that only checked the boundary in isolation.
static void test_feed_enabled_the_same_step_pressure_reaches_threshold(void)
{
    steam_control_state_t gate;
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                      declaration.ready_pressure_milli_bar - 1);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, declaration.ready_pressure_milli_bar);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16((uint16_t)ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                      declaration.ready_pressure_milli_bar + 500);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16((uint16_t)ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
}

/// SOL-SIM-STEAM-READINESS-GATE.C2: Steam feed is enabled once measured
/// pressure reaches the declared ready threshold.
///
/// Exercised against the truth plant rather than an injected reading, on the
/// same terms C1's own plant-backed test is: the block is driven to a real
/// temperature the plant seam alone establishes exceeds the threshold, and
/// the gate is read back from what the simulated hardware implementation
/// reports for it.
static void test_feed_enabled_against_the_plant_models_own_truth(void)
{
    plant_model_t truth;
    steam_control_state_t gate;

    TEST_ASSERT_TRUE(plant_model_init(&truth, &parameters));
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));
    TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C,
                                           STEAM_TEMPERATURE_READY_C));

    const plant_actuation_t idle = {{0u}};
    TEST_ASSERT_TRUE(plant_model_step(&truth, &idle, 0.0f, STEP_INTERVAL_MS));

    float pressure_bar = 0.0f;
    TEST_ASSERT_TRUE(plant_model_quantity(&truth, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &pressure_bar));
    TEST_ASSERT_TRUE_MESSAGE((int32_t)(pressure_bar * 1000.0f) > declaration.ready_pressure_milli_bar,
                             "the chosen steam temperature did not clear the declared threshold");

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, (int32_t)(pressure_bar * 1000.0f));
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16((uint16_t)ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
}

/// SOL-SIM-STEAM-READINESS-GATE.C3: Withholding feed holds the pressure
/// deficit rather than letting an open wand widen it.
///
/// The truth plant is first driven with feed actually enabled and the wand
/// open, so the deficit genuinely grows and measured pressure genuinely sags
/// below the saturation relation -- a test starting from a rested, zero
/// deficit state would prove nothing, since a deficit that cannot grow either
/// way looks the same as one being held, and this criterion's own text says
/// so. Feed is then withheld while the wand stays open, driven only through
/// the gate under test rather than set directly, and pressure is asserted not
/// to fall any further: with the feed pump commanded at nothing the plant's
/// own deficit relation is charged at nothing regardless of demand, so a
/// pressure that goes on sagging here would mean the gate is not actually
/// reaching zero on the channel the plant reads.
static void test_withheld_feed_holds_an_existing_deficit_against_an_open_wand(void)
{
    plant_model_t truth;
    steam_control_state_t gate;

    TEST_ASSERT_TRUE(plant_model_init(&truth, &parameters));
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));
    TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C,
                                           STEAM_TEMPERATURE_BELOW_READY_C));

    /*
     * Primed by driving the truth plant's actuation directly rather than
     * through the gate: this phase's whole purpose is to reach a state where
     * the deficit is already nonzero, which the gate itself -- withholding
     * feed below the threshold -- would never produce. The temperature is
     * chosen so the rested pressure it carries, and what a real draw sags it
     * to, both stay below the declared threshold: the gate is asked to
     * withhold feed throughout the phase that follows, not to enable it.
     */
    plant_actuation_t feeding = {{0u}};
    feeding.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = (uint16_t)ACTUATION_FULL_SCALE;

    for (int step = 0; step < 5; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&truth, &feeding, 3.0f, STEP_INTERVAL_MS));
    }

    float primed_bar = 0.0f;
    TEST_ASSERT_TRUE(plant_model_quantity(&truth, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &primed_bar));
    TEST_ASSERT_TRUE_MESSAGE((int32_t)(primed_bar * 1000.0f) < declaration.ready_pressure_milli_bar,
                             "priming left the truth plant at or above the ready threshold, which this test did not intend");

    /*
     * Confirms the priming actually produced a nonzero deficit -- primed_bar
     * below the pressure a rested block at this temperature would carry --
     * which is the state this criterion's own text requires the test to
     * start from. Read through the same seam quantity the gate is fed
     * through, against a second instance rested at the same starting
     * temperature, rather than the internal deficit field the plant seam
     * does not expose to a consumer outside src/plant.
     */
    plant_model_t rested;
    TEST_ASSERT_TRUE(plant_model_init(&rested, &parameters));
    TEST_ASSERT_TRUE(plant_model_set_state(&rested, PLANT_STATE_STEAM_TEMPERATURE_C,
                                           STEAM_TEMPERATURE_BELOW_READY_C));
    const plant_actuation_t idle = {{0u}};
    TEST_ASSERT_TRUE(plant_model_step(&rested, &idle, 0.0f, STEP_INTERVAL_MS));
    float rested_saturation_bar = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_quantity(&rested, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &rested_saturation_bar));
    TEST_ASSERT_TRUE_MESSAGE(primed_bar < rested_saturation_bar - 0.01f,
                             "priming did not produce a nonzero deficit to hold");

    /*
     * Feed is now driven only through the gate under test, reading the truth
     * plant's own pressure back at each step, with the wand still open
     * throughout. A tolerance rather than exact equality because the block
     * goes on losing a little to ambient even with feed withheld; it is an
     * order of magnitude below the drift a still-growing deficit would show
     * over the same steps at this priming rate, so a regression that charged
     * the deficit against demand rather than made rate would still fail it.
     */
    for (int step = 0; step < 5; step++) {
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, (int32_t)(primed_bar * 1000.0f));
        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

        plant_actuation_t withheld = {{0u}};
        withheld.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] =
            hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        TEST_ASSERT_TRUE(plant_model_step(&truth, &withheld, 3.0f, STEP_INTERVAL_MS));

        float held_bar = 0.0f;
        TEST_ASSERT_TRUE(plant_model_quantity(&truth, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &held_bar));
        TEST_ASSERT_FLOAT_WITHIN(0.002f, primed_bar, held_bar);
        primed_bar = held_bar;
    }
}

/// SOL-SIM-STEAM-READINESS-GATE.C4: The ready threshold is declared data
/// with a recorded origin, read by the control law rather than compiled
/// into it.
///
/// Two gates, brought up from two declarations that differ in nothing but
/// the threshold, are handed the same pressure reading -- one sitting
/// between the two thresholds -- and are asserted to disagree about whether
/// feed is withheld. Nothing here is rebuilt: both declarations are read at
/// runtime by the same loader, which is what "read by the control law
/// rather than compiled into it" is standing in for.
static void test_declared_threshold_moves_the_feed_boundary(void)
{
    steam_control_declaration_t low;
    steam_control_declaration_t high;
    steam_control_declaration_error_t fault;

    TEST_ASSERT_TRUE(declaration_from("ready-pressure-bar = 500 milli-bar @estimated a lower threshold this test chose\n",
                                      &low, &fault));
    TEST_ASSERT_TRUE(declaration_from("ready-pressure-bar = 1500 milli-bar @estimated a higher threshold this test chose\n",
                                      &high, &fault));

    steam_control_state_t gate_low;
    steam_control_state_t gate_high;
    TEST_ASSERT_TRUE(steam_control_init(&gate_low, &limits, &low));
    TEST_ASSERT_TRUE(steam_control_init(&gate_high, &limits, &high));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, 1000);

    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate_low));
    TEST_ASSERT_EQUAL_UINT16((uint16_t)ACTUATION_FULL_SCALE, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate_high));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
}

/// SOL-SIM-STEAM-READINESS-GATE.C4: The ready threshold is declared data
/// with a recorded origin, read by the control law rather than compiled
/// into it.
///
/// The loader's own refusals, table-driven across every fault this project's
/// declaration grammar shares with every other one: a line with no `=` at
/// all, one naming nothing this grammar reads, a threshold given twice, one
/// outside the admissible span, one in the wrong unit, one with no account of
/// where it came from, and a declaration that never names the threshold at
/// all. A grammar that accepted any of these would let a load-bearing figure
/// arrive with nothing asserting it, which is the whole failure this
/// declaration exists to prevent -- see steam_control_declaration.h.
static void test_declaration_loader_refuses_malformed_declarations(void)
{
    static const struct {
        const char *text;
        steam_control_declaration_fault_t fault;
    } CASES[] = {
        {"ready-pressure-bar 900 milli-bar @estimated an account\n", STEAM_CONTROL_DECLARATION_MALFORMED},
        {"ready-pressure-bar = @estimated an account\n", STEAM_CONTROL_DECLARATION_MALFORMED},
        {"ready-pressure-bar = 900 milli-bar @estimated an account\n"
         "ready-pressure-bar = 950 milli-bar @estimated a second account\n",
         STEAM_CONTROL_DECLARATION_DUPLICATE},
        {"boiler-pressure-bar = 900 milli-bar @estimated an account\n", STEAM_CONTROL_DECLARATION_UNKNOWN},
        {"ready-pressure-bar = 20000 milli-bar @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"ready-pressure-bar = 900 milli-c @estimated an account\n", STEAM_CONTROL_DECLARATION_UNIT_MISMATCH},
        {"ready-pressure-bar = 900 milli-bar\n", STEAM_CONTROL_DECLARATION_ORIGIN},
        {"ready-pressure-bar = 900 milli-bar @invented an account\n", STEAM_CONTROL_DECLARATION_ORIGIN},
        {"", STEAM_CONTROL_DECLARATION_MISSING},
    };

    for (size_t i = 0u; i < sizeof(CASES) / sizeof(CASES[0]); i++) {
        steam_control_declaration_t built;
        steam_control_declaration_error_t fault;
        TEST_ASSERT_FALSE_MESSAGE(declaration_from(CASES[i].text, &built, &fault), CASES[i].text);
        TEST_ASSERT_EQUAL_MESSAGE(CASES[i].fault, fault.fault, CASES[i].text);
    }
}

/// SOL-SIM-STEAM-READINESS-GATE.C5: The feed-withhold policy is exercised in
/// host simulation against the plant model before any hardware exists.
///
/// The gate builds into a host executable with no target dependency present,
/// initialises and steps against the simulated implementation alone, on the
/// same terms test_control.c's own C2-equivalent test is for the brew side.
static void test_gate_runs_against_the_simulated_implementation_with_no_target_dependency(void)
{
    steam_control_state_t gate;
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, 0);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
}

/// SOL-SIM-STEAM-READINESS-GATE.C1: Steam feed is withheld while measured
/// pressure sits below the declared ready threshold.
///
/// An absent, failed, or implausible reading is not evidence the steam side
/// has reached the threshold, so the gate withholds feed on every one of
/// them rather than acting on a figure it has no reason to believe -- the
/// same softer failure C1's own account prefers to a draw that starts
/// acceptable and degrades. A caller that read this as "whatever the last
/// trustworthy reading said" would enable feed on a machine this gate has no
/// present evidence is ready.
static void test_feed_withheld_on_an_untrustworthy_reading(void)
{
    steam_control_state_t gate;
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    const int32_t above_declared_bounds = limits.high_milli[HW_SENSOR_STEAM_PRESSURE] + 1000;

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_ABSENT, 0);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_FAILED, declaration.ready_pressure_milli_bar + 1000);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, above_declared_bounds);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&gate));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
}

/// Regression protection for steam_control_init's own refusals: a caller
/// handed no limits record or no declaration is refused with the outputs
/// left commanded off rather than left at whatever they were, on the same
/// terms control_init already refuses a null tolerance record.
static void test_init_is_refused_and_leaves_feed_off_without_either_record(void)
{
    steam_control_state_t gate;

    TEST_ASSERT_FALSE(steam_control_init(&gate, NULL, &declaration));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(&gate, &limits, NULL));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(NULL, &limits, &declaration));
}

/// Regression protection for steam_control_step's own error path: a refused
/// drive command is reported as STEAM_CONTROL_STEP_OUTPUT_REFUSED rather than
/// folded into STEAM_CONTROL_STEP_ACTUATED, on the same terms
/// test_control.c's own test_refused_drive_command_is_reported_and_latches
/// covers control_step's identical case. This is the error path the host run
/// takes when the interface rejects a level, not a case either C1-C5's own
/// text names, but a caller has to be able to tell it apart from an ordinary
/// step or it cannot tell the machine is not doing what it was just told.
static void test_output_refused_is_reported_rather_than_folded_into_actuated(void)
{
    steam_control_state_t gate;
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    hw_sim_set_output_refused(true);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, 0);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_OUTPUT_REFUSED, steam_control_step(&gate));
}

/// Regression protection for steam_control_init's own refusal of the initial
/// off command: the instance is still handed back usable -- `configured` is
/// set and a subsequent step is not treated as uninitialised -- but the
/// return value itself is false, on the same terms control_init returns
/// false from a refused off command while leaving the rest of the state
/// usable. A caller reading only the boolean and assuming the channel is
/// therefore off would be wrong; steam_control.h's own account of this is
/// what this test holds the implementation to.
static void test_init_reports_a_refused_off_command_but_leaves_the_gate_usable(void)
{
    steam_control_state_t gate;

    hw_sim_set_output_refused(true);
    TEST_ASSERT_FALSE(steam_control_init(&gate, &limits, &declaration));

    hw_sim_set_output_refused(false);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, 0);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_feed_withheld_while_pressure_stays_below_threshold_with_the_wand_open);
    RUN_TEST(test_feed_withheld_one_milli_bar_below_threshold);
    RUN_TEST(test_feed_enabled_the_same_step_pressure_reaches_threshold);
    RUN_TEST(test_feed_enabled_against_the_plant_models_own_truth);
    RUN_TEST(test_withheld_feed_holds_an_existing_deficit_against_an_open_wand);
    RUN_TEST(test_declared_threshold_moves_the_feed_boundary);
    RUN_TEST(test_declaration_loader_refuses_malformed_declarations);
    RUN_TEST(test_gate_runs_against_the_simulated_implementation_with_no_target_dependency);
    RUN_TEST(test_feed_withheld_on_an_untrustworthy_reading);
    RUN_TEST(test_init_is_refused_and_leaves_feed_off_without_either_record);
    RUN_TEST(test_output_refused_is_reported_rather_than_folded_into_actuated);
    RUN_TEST(test_init_reports_a_refused_off_command_but_leaves_the_gate_usable);
    return UNITY_END();
}
