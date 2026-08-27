/*
 * The control path's admission, driven end to end against a structure that
 * serves its two points from two heated masses and answers enough of the
 * seam for control_init to come up.
 *
 * The wide suite brings a real loop up against the structure describing the
 * reference machine, which routes both delivery points out of one casting --
 * every contention answer there is "yes", so it can prove a demand is held
 * and later resumed, but it can never prove the opposite: that a demand for a
 * point not sharing a mass with what is running is admitted immediately. The
 * narrow suite beside this one proves the two points here do not share a mass,
 * through the exact seam call the contention question is asked of -- but it
 * asks that of the `fixture` structure alone, and `fixture` answers no pump
 * channel and keeps no state the estimator reconstructs, so
 * control_command_delivery_reporting is refused CONTROL_ADMISSION_NO_MACHINE_
 * DESCRIBED before contention is ever reached and control_init cannot come up
 * on it at all. Neither suite drives the branch this one does.
 *
 * This structure -- flow_fixture, declared alongside fixture rather than
 * inside it, for the reasons its own header gives -- answers just enough of
 * the seam for control_init to succeed and a real admission to be asked: a
 * pump channel, and one accumulator answered under both names the estimator
 * reaches it by -- see the cases below for why both matter. What is asserted
 * here is the thing neither of the other two suites can be: that a
 * demand for the spout is admitted immediately while an extraction at the
 * group is running, on a structure real enough for control_init to accept.
 *
 * The cases after that one are here for the other half of "real enough". A
 * structure control_init accepts is thereafter driven by a loop that reads the
 * sensors and corrects toward them, and being accepted at start-up is no
 * guarantee the correction ever lands: the check that admits a structure and
 * the correction that runs against it ask the seam for the brew reconstruction
 * under two different names, and a structure answering only the first is
 * admitted and then never corrected. Nothing else in the tree can say so,
 * because the wide and boiler suites are driven against structures that answer
 * both names and the narrow suite's structure is refused before a step is ever
 * taken. So the suite that owns the only accepted narrow structure is the suite
 * that owns this.
 */
#include <unity.h>

#include "control.h"
#include "delivery_profile.h"
#include "delivery_tolerance.h"
#include "estimator.h"
#include "estimator_limits.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"

void setUp(void) {}
void tearDown(void) {}

/*
 * An admissible description for this structure, as text rather than as
 * symbols -- the seam is not reached around by knowing what a coefficient is
 * called. The pump figure is what lets probe_full_scale_flow_ml_per_s find a
 * positive figure and control_init succeed; see plant_structure.h.
 */
static const char DESCRIPTION[] = "fixture.gain = 2.5\npump.flow_ml_per_s = 7.0\n";

/*
 * A limits declaration for the estimator to be brought up against. It carries
 * the statement that exempts it from accounting for its figures, because this
 * structure describes no machine and the numbers below mean nothing: what is
 * established in this suite is admission, and an estimator refused for want
 * of a limits record would refuse control_init for the wrong reason.
 */
static const char LIMITS_DECLARATION[] = "@describes-no-machine\n"
                                         "brew-temperature = -10000 .. 250000\n"
                                         "steam-temperature = -10000 .. 250000\n"
                                         "brew-pressure = -1000 .. 20000\n"
                                         "steam-pressure = -1000 .. 20000\n"
                                         "flow = -1000 .. 20000\n"
                                         "loss-tolerance-window-ms = 500\n"
                                         "excursion-bound-milli-c = 15000\n";

/*
 * A steady course at a stated rate, arriving at a stated point over a stated
 * duration. The duration is a parameter, rather than fixed, so two courses
 * commanded in the same test are told apart by more than the point they name.
 */
static delivery_profile_t steady_course(float rate_ml_per_s, uint32_t elapsed_millis,
                                        plant_delivery_point_t served_at)
{
    const delivery_profile_point_t points[] = {{0u, rate_ml_per_s},
                                               {elapsed_millis, rate_ml_per_s}};
    const delivery_end_condition_t end = {.quantity = DELIVERY_END_ELAPSED_MILLIS,
                                          .elapsed_millis = elapsed_millis};
    delivery_profile_t course;

    TEST_ASSERT_TRUE(delivery_profile_init(&course, points, 2u, end, served_at));
    return course;
}

/*
 * This structure's own description, loaded and asserted admissible. Shared by
 * every caller that needs a plant_parameters_t for it, whether or not they go
 * on to bring a whole control_state_t up.
 */
static void load_this_structures_parameters(plant_parameters_t *parameters)
{
    plant_parameter_error_t parameter_fault;
    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, parameters, &parameter_fault));
}

/* A control_state_t brought up against this structure, ready to command. */
static void bring_the_machine_up(control_state_t *state)
{
    plant_parameters_t parameters;
    load_this_structures_parameters(&parameters);

    estimator_limits_t limits;
    estimator_limits_error_t limits_fault;
    TEST_ASSERT_TRUE(estimator_limits_load(LIMITS_DECLARATION, sizeof(LIMITS_DECLARATION) - 1u,
                                           &limits, &limits_fault));

    /*
     * Zero-valued and never loaded from a declaration: nothing this suite
     * commands ever names a temperature, so admission never reaches the band
     * this record would be judged against -- see admit_delivery's targeted
     * guard in control.c. control_init asks only that the pointer is not
     * null.
     */
    const delivery_tolerance_t tolerance = {0};

    TEST_ASSERT_TRUE_MESSAGE(
        control_init(state, &parameters, &limits, &tolerance),
        "control_init was refused against a structure built to let it succeed -- see "
        "flow_fixture's own header for what it answers and why");
}

/// SOL-SHARED-MASS-CONTENTION-SERIALISED.C3: A demand for a point not sharing
/// a mass with what is running is admitted immediately, unaffected by any
/// hold.
///
/// An extraction is commanded at the group and left running. A hot water
/// demand commanded against the spout while it runs is asserted admitted on
/// the spot: control_command_delivery_reporting reports CONTROL_ADMISSION_OK,
/// what control_step would advance is now the hot water course rather than
/// the extraction, and nothing is reported held. Every one of those three is
/// the opposite of what the wide suite's held-demand cases assert of the same
/// calls made against the reference machine's own structure, which is what
/// makes this evidence about contention being asked of the seam rather than
/// compiled in: an implementation that held every second demand
/// unconditionally would pass every case in the wide suite and fail every one
/// of these.
static void test_a_demand_not_sharing_the_mass_is_admitted_immediately_while_a_delivery_runs(void)
{
    control_state_t state;
    bring_the_machine_up(&state);

    delivery_profile_t extraction = steady_course(1.0f, 2000u, PLANT_DELIVERY_POINT_GROUP);
    TEST_ASSERT_TRUE(control_command_delivery(&state, &extraction));
    TEST_ASSERT_TRUE(control_delivery_running(&state));
    TEST_ASSERT_EQUAL(PLANT_DELIVERY_POINT_GROUP, state.delivery.served_at);

    delivery_profile_t hot_water = steady_course(2.0f, 45000u, PLANT_DELIVERY_POINT_HOT_WATER_SPOUT);
    control_admission_t admission;
    TEST_ASSERT_TRUE_MESSAGE(
        control_command_delivery_reporting(&state, &hot_water, &admission),
        "a demand for a point not sharing a mass with what is running was refused rather than "
        "admitted");
    TEST_ASSERT_EQUAL(CONTROL_ADMISSION_OK, admission.bound);

    TEST_ASSERT_TRUE_MESSAGE(control_delivery_running(&state),
                             "the demand admitted at the spout left nothing running at all");
    TEST_ASSERT_EQUAL_MESSAGE(
        PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, state.delivery.served_at,
        "what control_step would advance is still the extraction, so the demand for the spout "
        "was not started immediately");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(
        45000u, state.delivery.end.elapsed_millis,
        "what is running is not the course that was just admitted");

    delivery_profile_t held;
    plant_delivery_point_t held_against = PLANT_DELIVERY_POINT_COUNT;
    TEST_ASSERT_FALSE_MESSAGE(
        control_delivery_held(&state, &held, &held_against),
        "a demand for a point not sharing a mass with what was running was reported held");
}

/*
 * An ordinary brew temperature for the loop to drive toward, and an ordinary
 * reading for it to be corrected by. Neither is a claim about a drink or about
 * this structure, which describes no machine: what they are for is to be far
 * enough apart that the heater is driven every step, so a step that stops
 * actuating has stopped for a reason other than having arrived.
 */
#define DRIVING_TARGET_C 93.0f
#define STEADY_READING_MILLI_C 20000

/*
 * How many steps a gap is ridden for before the reading is restored. The suite's
 * declaration above states a five-hundred millisecond window and the control
 * interval is ten, so fifty steps is where the loss stops being brief; this sits
 * well inside that rather than at its edge, because where exactly the line falls
 * is the estimator's own suite to say and this one only asks which side of it a
 * short gap lands on.
 */
#define STEPS_INSIDE_THE_WINDOW 30u

/* A machine brought up with a valid reading present and a target commanded. */
static void bring_the_machine_up_driving(control_state_t *state)
{
    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, STEADY_READING_MILLI_C);
    bring_the_machine_up(state);
    TEST_ASSERT_TRUE_MESSAGE(control_command_temperature(state, DRIVING_TARGET_C),
                             "the target this suite drives toward was refused");
}

/// SOL-FLOW-FIXTURE-STATE-CORRECTABLE.C1: A structure control_init accepts as
/// reconstructing a state answers that state to the estimator's own correction
/// path.
///
/// The seam is asked for the brew reconstruction under both the names the
/// estimator uses for it: the water on its way out, which control_init's
/// reachability check probes before admitting a structure, and the mass being
/// heated, which the per-step correction writes because that is where a sensor
/// can be placed. Answering one and refusing the other is admissible to
/// control_init and useless to the loop that follows it, which is the state this
/// structure was in.
///
/// Each name is written and both are read back afterwards, in both directions.
/// A structure that answered the second name off some other value -- a second
/// field, a constant, a zero -- would satisfy a test that only asked whether the
/// name was answered, and would still drop every correction on the floor. What
/// has to hold is that a write under either name is the value a read under the
/// other returns.
static void test_both_names_the_estimator_uses_reach_the_one_kept_state(void)
{
    plant_parameters_t parameters;
    load_this_structures_parameters(&parameters);

    plant_model_t model;
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    float outlet = 0.0f;
    float heated_mass = 0.0f;
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &outlet),
        "the state control_init's reachability check probes is refused, so nothing comes up");
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &heated_mass),
        "the state the estimator's correction writes is refused, so every correction against this "
        "structure is dropped");

    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_set_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 64.0f),
        "a write under the name the correction uses was refused");
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &outlet));
    TEST_ASSERT_TRUE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &heated_mass));
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(
        64.0f, outlet,
        "what the correction wrote is not what the reconstruction reads back, so the two names "
        "reach different values");
    TEST_ASSERT_EQUAL_FLOAT(64.0f, heated_mass);

    /* And the other way round, so neither name is a write nothing reads. */
    TEST_ASSERT_TRUE(plant_model_set_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 21.5f));
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &outlet));
    TEST_ASSERT_TRUE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &heated_mass));
    TEST_ASSERT_EQUAL_FLOAT(21.5f, outlet);
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(21.5f, heated_mass,
                                    "the two names have come apart, so this structure is keeping "
                                    "two brew states rather than the one it declares");

    /*
     * The states this structure answers no channel for stay refused, both to a
     * read and to a write. Widening the brew side is not licence to widen the
     * rest: a structure that answered everything would be a structure no
     * refusal could ever be shown against, and the seam's refusal is what the
     * suite beside this one exists to establish.
     */
    float refused = 0.0f;
    TEST_ASSERT_FALSE(plant_model_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, &refused));
    TEST_ASSERT_FALSE(plant_model_state(&model, PLANT_STATE_BREW_PRESSURE_BAR, &refused));
    TEST_ASSERT_FALSE(plant_model_state(&model, PLANT_STATE_STEAM_PRESSURE_BAR, &refused));
    TEST_ASSERT_FALSE(plant_model_set_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, 1.0f));
    TEST_ASSERT_FALSE(plant_model_set_state(&model, PLANT_STATE_BREW_PRESSURE_BAR, 1.0f));
    TEST_ASSERT_FALSE(plant_model_set_state(&model, PLANT_STATE_STEAM_PRESSURE_BAR, 1.0f));
}

/// SOL-FLOW-FIXTURE-STATE-CORRECTABLE.C1: A structure control_init accepts as
/// reconstructing a state answers that state to the estimator's own correction
/// path.
///
/// The seam-level case above says the two names meet on one value; this says the
/// running loop actually gets there. A reading that is valid and inside the
/// declared span is present on every step, and the residual the estimator
/// reports is what proves the correction happened -- it is recorded only when
/// the correction was applied, so a structure refusing the corrected state
/// reports none however good the reading was.
///
/// Then the loop is run for eight times STEPS_INSIDE_THE_WINDOW -- two hundred
/// and forty steps, comfortably longer than the window itself, which is fifty
/// steps at this interval -- with that reading never once missing. That is
/// the case the defect actually presented as: every correction dropped, the
/// state recorded as unobserved on every step, and the machine brought down
/// partway through for want of an observation that was arriving the whole
/// time. A structure whose correction lands drives all the way through
/// instead.
///
/// SOL-ADMISSION-PROVES-FULL-PAIRING.C2: Every structure the estimator
/// already admits keeps being admitted, unchanged. flow_fixture is the
/// structure that most needed re-checking under the widened admission test --
/// it is the one structure in the tree that ever exhibited the defect that
/// check now guards against -- and unlike the seam-level case above, this
/// goes through control_init and so would fail outright if the widened check
/// ever newly refused it: bring_the_machine_up_driving asserts control_init
/// succeeds, and every step below depends on that admission having held.
static void test_a_valid_reading_is_incorporated_on_every_step(void)
{
    control_state_t state;
    bring_the_machine_up_driving(&state);

    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));

    int32_t residual_milli = 0;
    TEST_ASSERT_TRUE_MESSAGE(
        estimator_residual(&state.estimator, HW_SENSOR_BREW_TEMPERATURE, &residual_milli),
        "no residual was reported for a channel that read valid and in bounds, so the correction "
        "reached no state and the reading was discarded");

    for (unsigned step = 0u; step < STEPS_INSIDE_THE_WINDOW * 8u; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_ACTUATED, control_step(&state),
                                  "a step stopped actuating while the reading was present on every "
                                  "one, so the reconstruction was starved by corrections that "
                                  "never landed rather than by a gap");
    }
    TEST_ASSERT_FALSE_MESSAGE(state.faulted,
                              "a continuously observed machine latched a fault it can never leave");
    TEST_ASSERT_TRUE_MESSAGE(
        hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > 0u,
        "the heater sat idle despite the reading being thirty degrees under the commanded target, "
        "which only happens if the correction driving the loop never reached the state");
}

/// SOL-FLOW-FIXTURE-STATE-CORRECTABLE.C2: A brief gap in the brew reading
/// against native_flow_fixture behaves the same as it already does against
/// every other structure.
///
/// Three phases, because the property is where the line falls rather than that
/// there is one -- the same shape the wide suite asserts against the reference
/// machine's own structure, asked here of the structure that could not answer it
/// before. The reading stops and the machine keeps driving, because a dropped
/// sample is an operating condition. It comes back before the window elapses and
/// nothing is latched, which is the half that fails against a structure whose
/// corrections never landed: there the fault arrives regardless of whether the
/// sensor recovered, because it was never the gap that starved the state. Only
/// when the reading is gone for good does the estimator withdraw the
/// reconstruction and the heater come down.
static void test_a_brief_gap_rides_through_and_only_a_sustained_one_brings_the_machine_down(void)
{
    control_state_t state;
    bring_the_machine_up_driving(&state);

    for (unsigned step = 0u; step < STEPS_INSIDE_THE_WINDOW; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL(CONTROL_STEP_ACTUATED, control_step(&state));
    }

    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_FAILED, 0);
    for (unsigned step = 0u; step < STEPS_INSIDE_THE_WINDOW; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_ACTUATED, control_step(&state),
                                  "a brief gap in the reading brought the machine down");
    }
    TEST_ASSERT_FALSE_MESSAGE(
        state.faulted,
        "the gap has not yet reached the window's length, so a fault already latched here would "
        "mean the window was not being honoured at all");

    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, STEADY_READING_MILLI_C);
    for (unsigned step = 0u; step < STEPS_INSIDE_THE_WINDOW * 4u; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        TEST_ASSERT_EQUAL_MESSAGE(CONTROL_STEP_ACTUATED, control_step(&state),
                                  "the sensor recovered inside the window and the machine came "
                                  "down anyway, so the recovery was not being incorporated");
    }
    TEST_ASSERT_FALSE_MESSAGE(state.faulted,
                              "a gap the sensor recovered from inside the window still latched");

    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_FAILED, 0);
    bool latched = false;
    /*
     * Four times the window's fifty steps, so the fault is certain to have
     * latched with margin to spare -- the loop exits as soon as it does, so
     * this bounds how long a broken latch is ridden for rather than setting
     * how long a working one takes.
     */
    for (unsigned step = 0u; step < 200u && !latched; step++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        latched = control_step(&state) == CONTROL_STEP_SENSOR_INVALID;
    }
    TEST_ASSERT_TRUE_MESSAGE(latched, "a reading gone for good was ridden indefinitely");
    TEST_ASSERT_TRUE_MESSAGE(
        state.faulted,
        "control_step reported the sensor invalid without the machine's own fault flag following "
        "it, so the fault state and the step outcome have come apart");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER),
                                     "the heater stayed on through a fault");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_a_demand_not_sharing_the_mass_is_admitted_immediately_while_a_delivery_runs);
    RUN_TEST(test_both_names_the_estimator_uses_reach_the_one_kept_state);
    RUN_TEST(test_a_valid_reading_is_incorporated_on_every_step);
    RUN_TEST(test_a_brief_gap_rides_through_and_only_a_sustained_one_brings_the_machine_down);
    return UNITY_END();
}
