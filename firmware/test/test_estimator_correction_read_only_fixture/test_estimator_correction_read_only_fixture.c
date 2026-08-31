/*
 * The estimator's admission, driven directly against a structure that answers
 * a read of every state admission probes and refuses the one write it makes.
 *
 * Every other suite exercising estimator_init is driven against a structure
 * whose reads and writes answer and refuse the same states in the same pairs:
 * `thermoblock` and `flow_fixture` answer both names on both, `fixture`,
 * `boiler` and `outlet_only_fixture` refuse a name on both and are turned away
 * by a read before any write is reached. None of them can reach the write at
 * all, so none of them can show it is asked for. Carrying the one shape that
 * can is what `correction_read_only_fixture` was built for, so the suite that
 * owns the only structure carrying that shape is the suite that owns this.
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
 * admission's probes to read back.
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

/// SOL-ADMISSION-PROVES-CORRECTION-WRITABLE.C1: A structure is refused
/// admission if it cannot write the correction-target state for a value it
/// reconstructs, not only read it.
///
/// `correction_read_only_fixture` answers a read of
/// PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, the state the reconstruction is held
/// as, and a read of PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, the state the
/// per-step correction is applied through -- so every read the widened
/// reachability check makes succeeds against it. It refuses the write the
/// correction ends with. Before the write was probed, this structure was
/// admitted on the strength of those reads and then had every correction
/// against it dropped by plant_model_set_state's own refusal, one call further
/// down correct_against: the reading arrives, the correction is computed, and
/// nothing takes it. What has to hold now is that the write is asked for at
/// admission, and a structure answering only the reads is refused here rather
/// than admitted and left to fault-latch later.
static void test_a_structure_refusing_the_correction_write_is_refused(void)
{
    /*
     * Pin the shape this structure is required to carry before asking
     * anything of admission. Without this, a refusal below could not be told
     * apart from the one `fixture`, `boiler` and `outlet_only_fixture` already
     * trigger by refusing a *read* -- the probes the check already ran before
     * this criterion -- which would leave this suite verifying the previous
     * check rather than the write beside it, if this structure's shape ever
     * drifted.
     */
    plant_model_t model;
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &value),
        "this structure no longer answers a read of the reconstruction-target state, so a "
        "refusal below is the original check's rather than the write probe's");
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &value),
        "this structure no longer answers a read of the correction-target state, so a refusal "
        "below is the widened read probe's rather than the write probe's");
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_set_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, value),
        "this structure now refuses a write of the reconstruction-target state too, so it no "
        "longer isolates the correction-target write");
    TEST_ASSERT_FALSE_MESSAGE(
        plant_model_set_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, value),
        "this structure now answers a write of the correction-target state, so it no longer "
        "carries the defect shape this suite exists to catch");

    estimator_t estimator;
    TEST_ASSERT_FALSE_MESSAGE(
        estimator_init(&estimator, &parameters, &limits),
        "a structure refusing a write of the correction-target state was admitted, so "
        "admission is reading that state without proving it can be written");
}

/// SOL-ADMISSION-PROVES-CORRECTION-WRITABLE.C1: A structure is refused
/// admission if it cannot write the correction-target state for a value it
/// reconstructs, not only read it.
///
/// The estimator's own promise is that a refused instance answers nothing,
/// however late the refusal came. Asked here because this refusal is the
/// latest one admission can reach -- the structure satisfied every read before
/// it -- so an instance left half brought up would be left that way by this
/// path if by any.
static void test_a_refused_instance_answers_nothing(void)
{
    estimator_t estimator;
    float value = -1.0f;

    TEST_ASSERT_FALSE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_FALSE_MESSAGE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value),
        "an instance refused for want of a writable correction-target state still answered a "
        "reconstruction");
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, value);

    const plant_actuation_t actuation = {{0u}};
    TEST_ASSERT_FALSE_MESSAGE(estimator_step(&estimator, &actuation, 10u),
                              "a step ran against an instance admission refused");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_a_structure_refusing_the_correction_write_is_refused);
    RUN_TEST(test_a_refused_instance_answers_nothing);
    return UNITY_END();
}
