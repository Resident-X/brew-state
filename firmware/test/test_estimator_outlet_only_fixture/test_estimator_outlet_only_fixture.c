/*
 * The estimator's admission, driven directly against a structure built to
 * answer one half of a reconstruction's pairing and refuse the other.
 *
 * Every other suite exercising estimator_init is driven against a structure
 * that answers both names the estimator reaches a reconstructed value by, or
 * against `fixture`/`boiler`, which answer neither and so are refused before
 * the pairing this suite is about is ever reached -- their refusal proves
 * only that the *first* probe still works, on the same terms it always has.
 * Nothing else in the tree can drive the second probe at all: proving it
 * exists is what `outlet_only_fixture` was built for, so the suite that owns
 * the only structure carrying that shape is the suite that owns this.
 */
#include <unity.h>

#include <stdio.h>

#include "estimator.h"
#include "estimator_limits.h"
#include "hw_interface.h"
#include "plant_model.h"

/*
 * This structure's own description, as text rather than as symbols -- the
 * seam is not reached around by knowing what a coefficient is called. The
 * value is arbitrary; what matters is only that a value is present for
 * estimator_init's reachability probe to read back.
 */
static const char DESCRIPTION[] = "outlet.value_c = 21.5\nheater.gain = 2.5\n";

/*
 * A limits declaration for the estimator to be brought up against. It carries
 * the statement that exempts it from accounting for its figures, because this
 * structure describes no machine and the numbers below mean nothing: what is
 * established in this suite is admission, and an estimator refused for want
 * of a limits record would refuse for the wrong reason.
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

static plant_parameters_t parameters;
static estimator_limits_t limits;

void setUp(void)
{
    plant_parameter_error_t parameter_fault;
    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &parameter_fault));

    estimator_limits_error_t limits_fault;
    TEST_ASSERT_TRUE(estimator_limits_load(LIMITS_DECLARATION, sizeof(LIMITS_DECLARATION) - 1u,
                                           &limits, &limits_fault));
}

void tearDown(void) {}

/// SOL-ADMISSION-PROVES-FULL-PAIRING.C1: A structure is refused admission if
/// it cannot answer every state a value it reconstructs will be corrected
/// through, not only the state the reconstruction itself names.
///
/// `outlet_only_fixture` answers PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, the
/// name estimator_init's reachability check has always probed, and refuses
/// PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, the name the per-step
/// correction writes toward for the identical reconstructed value. Before the
/// widened check this structure would have been admitted -- it satisfies the
/// one probe that ran -- and then had every correction against it silently
/// dropped for want of a state to land on. What has to hold now is that the
/// second name is asked too, and a structure answering only the first is
/// refused here rather than admitted and left to fault-latch later.
static void test_a_structure_answering_only_the_reconstruction_name_is_refused(void)
{
    /*
     * Pin the shape this structure is required to carry before asking
     * anything of admission. Without this, a refusal below could not be told
     * apart from the one `fixture`/`boiler` already trigger by refusing the
     * *reconstruction*-target name -- the probe the check has always run --
     * which would leave this suite verifying the old check rather than the
     * widened one if this structure's shape ever drifted.
     */
    plant_model_t model;
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &value),
        "this structure no longer answers the reconstruction-target state, so it can no "
        "longer distinguish the widened check from the original one");
    TEST_ASSERT_FALSE_MESSAGE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &value),
        "this structure now answers the correction-target state too, so it no longer "
        "carries the defect shape this suite exists to catch");

    estimator_t estimator;
    TEST_ASSERT_FALSE_MESSAGE(
        estimator_init(&estimator, &parameters, &limits),
        "a structure refusing the correction-target state was admitted, so the widened "
        "reachability check is not asking for it");
}

/// SOL-ADMISSION-PROVES-FULL-PAIRING.C1: A structure is refused admission if
/// it cannot answer every state a value it reconstructs will be corrected
/// through, not only the state the reconstruction itself names.
///
/// The estimator's own promise is that a refused instance answers nothing,
/// however early the refusal came. Asked here because the promise is easy to
/// break precisely for a structure that partly succeeds -- one that satisfied
/// the first probe before failing the second could plausibly leave the
/// instance half brought up rather than refusing.
static void test_a_refused_instance_answers_nothing(void)
{
    estimator_t estimator;
    float value = -1.0f;

    TEST_ASSERT_FALSE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_FALSE_MESSAGE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value),
        "an instance refused for want of the correction-target state still answered a "
        "reconstruction");
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, value);

    const plant_actuation_t actuation = {{0u}};
    TEST_ASSERT_FALSE_MESSAGE(estimator_step(&estimator, &actuation, 10u),
                             "a step ran against an instance the reachability check refused");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_a_structure_answering_only_the_reconstruction_name_is_refused);
    RUN_TEST(test_a_refused_instance_answers_nothing);
    return UNITY_END();
}
