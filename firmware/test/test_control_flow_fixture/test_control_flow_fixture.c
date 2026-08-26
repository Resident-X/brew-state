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
 * pump channel, and the one state the estimator reconstructs. What is
 * asserted here is the thing neither of the other two suites can be: that a
 * demand for the spout is admitted immediately while an extraction at the
 * group is running, on a structure real enough for control_init to accept.
 */
#include <unity.h>

#include "control.h"
#include "delivery_profile.h"
#include "delivery_tolerance.h"
#include "estimator_limits.h"
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
                                         "steam-knob = 0 .. 1000\n"
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

/* A control_state_t brought up against this structure, ready to command. */
static void bring_the_machine_up(control_state_t *state)
{
    plant_parameters_t parameters;
    plant_parameter_error_t parameter_fault;
    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &parameter_fault));

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

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_a_demand_not_sharing_the_mass_is_admitted_immediately_while_a_delivery_runs);
    return UNITY_END();
}
