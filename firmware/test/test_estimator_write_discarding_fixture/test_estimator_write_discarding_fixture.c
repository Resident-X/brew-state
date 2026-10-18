/*
 * The estimator's admission, driven directly against a structure that answers
 * every read and every write admission makes and does not keep what it is
 * given.
 *
 * Every other suite exercising estimator_init is driven against a structure
 * whose writes store what they are handed, or refuse outright and are turned
 * away by the call itself. None of them can show that a write reporting
 * success is checked for what it left behind. Carrying the shapes that can is
 * what `write_discarding_fixture` was built for, so the suite that owns the
 * only structure carrying them is the suite that owns this.
 *
 * The one structure carries each shape through its description: how many
 * writes it keeps, whether the ones after are refused, and whether it holds
 * not-a-number to begin with. Each test states the description it loads.
 */
#include <unity.h>

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "estimator.h"
#include "estimator_limits.h"
#include "hw_interface.h"
#include "plant_model.h"

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

/* More writes than admission can make, so every one of them is kept. */
#define KEEPS_EVERY_WRITE 1000

static plant_parameters_t parameters;
static estimator_limits_t limits;

/* Load this structure's description with the write behaviour the test names. */
static void load(float seed, int writes_kept, int later_writes_refused, int seed_undefined)
{
    char description[192];
    plant_parameter_error_t parameter_fault;

    (void)snprintf(description, sizeof(description),
                   "outlet.value_c = %g\nheater.gain = 2.5\nwrites.kept = %d\n"
                   "writes.later_refused = %d\nseed.undefined = %d\n",
                   (double)seed, writes_kept, later_writes_refused, seed_undefined);
    TEST_ASSERT_TRUE_MESSAGE(
        plant_parameters_load(description, strlen(description), &parameters, &parameter_fault),
        "this suite's own description did not load");
}

static uint32_t bits_of(float value)
{
    uint32_t bits = 0u;
    memcpy(&bits, &value, sizeof(bits));
    return bits;
}

/* What the correction-target state holds, as the stored pattern. Read through
 * the seam, as every consumer of a model must. */
static uint32_t held_bits(const plant_model_t *model)
{
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &value));
    return bits_of(value);
}

void setUp(void)
{
    estimator_limits_error_t limits_fault;
    TEST_ASSERT_TRUE(estimator_limits_load(LIMITS_DECLARATION, sizeof(LIMITS_DECLARATION) - 1u,
                                           &limits, &limits_fault));
}

void tearDown(void) {}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C1: A structure is refused admission
/// if the correction-target state does not carry the value written to it.
///
/// With no write kept, `write_discarding_fixture` answers every write with
/// success and leaves the accumulator where it was. Every probe that only asks
/// whether the write was accepted passes it; before the value written was read
/// back, it was admitted and then had every correction against it dropped
/// exactly as completely as a structure that refused the write. What has to
/// hold now is that it is refused.
static void test_a_structure_that_accepts_the_write_and_keeps_nothing_is_refused(void)
{
    load(21.5f, 0, 0, 0);

    /*
     * Pin the shape this structure is required to carry before asking anything
     * of admission. Without this, a refusal below could not be told apart from
     * one for a refused write or an unanswered read, which would leave this
     * suite verifying a check that already existed.
     */
    plant_model_t model;
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &value),
        "this structure no longer answers a read of the correction-target state");
    TEST_ASSERT_TRUE_MESSAGE(
        plant_model_set_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, value + 1.0f),
        "this structure now refuses the write, so it no longer isolates a write that is accepted");
    float after = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &after));
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(
        bits_of(value), bits_of(after),
        "this structure now keeps what it is written, so it no longer carries the defect shape");

    estimator_t estimator;
    TEST_ASSERT_FALSE_MESSAGE(estimator_init(&estimator, &parameters, &limits),
                              "a structure whose accepted write kept nothing was admitted, so "
                              "admission is proving the write accepted without proving it taken");

    TEST_ASSERT_EQUAL_UINT32_MESSAGE(bits_of(21.5f), held_bits(&estimator.model),
                                     "the model moved, so this refusal is not the one for a write "
                                     "that kept nothing");
}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C1: A structure is refused admission
/// if the correction-target state does not carry the value written to it.
///
/// The estimator's own promise is that a refused instance answers nothing,
/// however late the refusal came. Asked here because this refusal comes after
/// every read and the write have answered, so an instance left half brought up
/// would be left that way by this path if by any.
static void test_a_refused_instance_answers_nothing(void)
{
    load(21.5f, 0, 0, 0);

    estimator_t estimator;
    float value = -1.0f;

    TEST_ASSERT_FALSE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_FALSE_MESSAGE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value),
        "an instance refused for a write that was not kept still answered a reconstruction");
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, value);

    const plant_actuation_t actuation = {{0u}};
    TEST_ASSERT_FALSE_MESSAGE(estimator_step(&estimator, &actuation, 10u),
                              "a step ran against an instance admission refused");
}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C1: A structure is refused admission
/// if the correction-target state does not carry the value written to it.
///
/// A held zero is the value a probe that wrote a fixed zero, or that wrote
/// back a value derived by arithmetic on the held one, would fail to
/// distinguish from a state that discarded the write. The structure still
/// discards, so it is still refused with zero held.
static void test_a_held_zero_does_not_let_a_discarded_write_pass(void)
{
    load(0.0f, 0, 0, 0);

    estimator_t estimator;
    TEST_ASSERT_FALSE(estimator_init(&estimator, &parameters, &limits));
}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C1: A structure is refused admission
/// if the correction-target state does not carry the value written to it.
///
/// The same for a held not-a-number, which equals nothing, itself included: a
/// state that discarded the write and was compared by numeric equality could
/// never read back as the held value and would be refused for the wrong
/// reason, while one compared by pattern has to be refused for the right one.
static void test_a_held_not_a_number_does_not_let_a_discarded_write_pass(void)
{
    load(0.0f, 0, 0, 1);

    estimator_t estimator;
    TEST_ASSERT_FALSE(estimator_init(&estimator, &parameters, &limits));
}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C3: A structure is refused admission
/// if the correction-target state does not read back as the value it held
/// after the probe restores it.
///
/// With the first write kept and every later one discarded, the write of the
/// differing value reads back as written and passes the first step. The
/// restore reports success and leaves the state holding the differing value,
/// so it does not read back as the held one. The structure is refused, with
/// the displaced value visibly left in it, which is why the instance must not
/// be usable afterwards.
static void test_a_structure_whose_restore_does_not_read_back_is_refused(void)
{
    load(21.5f, 1, 0, 0);

    estimator_t estimator;
    float value = -1.0f;

    TEST_ASSERT_FALSE_MESSAGE(estimator_init(&estimator, &parameters, &limits),
                              "a structure whose restore did not read back as the held value was "
                              "admitted");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(
        bits_of(estimator_admission_probe_value(21.5f)), held_bits(&estimator.model),
        "the model was not left displaced, so this test did not reach the restore it exists for");
    TEST_ASSERT_FALSE_MESSAGE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value),
        "an instance whose model was displaced by the probe answered a reconstruction");
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, value);
}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C3: A structure is refused admission
/// if the correction-target state does not read back as the value it held
/// after the probe restores it.
///
/// The restore can also be refused outright, which is a different return from
/// the same step: the first write is kept and the one after it fails.
static void test_a_structure_whose_restore_is_refused_is_refused_at_admission(void)
{
    load(21.5f, 1, 1, 0);

    estimator_t estimator;
    TEST_ASSERT_FALSE_MESSAGE(estimator_init(&estimator, &parameters, &limits),
                              "a structure that refused the restore was admitted");
    TEST_ASSERT_EQUAL_UINT32_MESSAGE(
        bits_of(estimator_admission_probe_value(21.5f)), held_bits(&estimator.model),
        "the model was not left displaced, so the refusal did not come at the restore");
}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C3: A structure is refused admission
/// if the correction-target state does not read back as the value it held
/// after the probe restores it.
///
/// A held not-a-number is restored and recognised as restored. This is the
/// case a restore compared by numeric equality fails for a structure that did
/// everything right, since not-a-number equals nothing, so it is the case that
/// pins the comparison to the stored pattern.
///
/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C2: Every structure the estimator
/// already admits keeps being admitted, and is left as its initialisation set
/// it. The accumulator is left holding the pattern initialisation seeded.
static void test_a_held_not_a_number_is_restored_and_admitted(void)
{
    load(0.0f, KEEPS_EVERY_WRITE, 0, 1);

    plant_model_t initialised;
    TEST_ASSERT_TRUE(plant_model_init(&initialised, &parameters));
    float seeded = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(&initialised, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C,
                                       &seeded));
    TEST_ASSERT_TRUE_MESSAGE(isnan(seeded),
                             "the structure was not seeded with not-a-number, so nothing is shown");

    estimator_t estimator;
    TEST_ASSERT_TRUE_MESSAGE(estimator_init(&estimator, &parameters, &limits),
                             "a structure that keeps what it is written and held not-a-number was "
                             "refused");
    TEST_ASSERT_EQUAL_UINT32(bits_of(seeded), held_bits(&estimator.model));
}

/// SOL-ADMISSION-PROVES-CORRECTION-TAKEN.C2: Every structure the estimator
/// already admits keeps being admitted, and is left as its initialisation set
/// it.
///
/// The control for every refusal above: the same structure, keeping every
/// write, is admitted. Without it the refusals could be a probe that refuses
/// everything. Held values include zero, since a restore that landed on a
/// different pattern of zero would pass a numeric comparison.
static void test_a_structure_that_keeps_every_write_is_admitted_unchanged(void)
{
    const float seeds[] = {0.0f, 21.5f, -40.0f, 250.0f};

    for (size_t at = 0u; at < sizeof(seeds) / sizeof(seeds[0]); at++) {
        plant_model_t initialised;
        estimator_t estimator;
        char message[80];

        load(seeds[at], KEEPS_EVERY_WRITE, 0, 0);
        TEST_ASSERT_TRUE(plant_model_init(&initialised, &parameters));

        (void)snprintf(message, sizeof(message),
                       "a structure keeping every write was refused (seed %zu)", at);
        TEST_ASSERT_TRUE_MESSAGE(estimator_init(&estimator, &parameters, &limits), message);
        TEST_ASSERT_EQUAL_UINT32_MESSAGE(held_bits(&initialised), held_bits(&estimator.model),
                                         "admission left the model displaced from its initialisation");
    }
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_a_structure_that_accepts_the_write_and_keeps_nothing_is_refused);
    RUN_TEST(test_a_refused_instance_answers_nothing);
    RUN_TEST(test_a_held_zero_does_not_let_a_discarded_write_pass);
    RUN_TEST(test_a_held_not_a_number_does_not_let_a_discarded_write_pass);
    RUN_TEST(test_a_structure_whose_restore_does_not_read_back_is_refused);
    RUN_TEST(test_a_structure_whose_restore_is_refused_is_refused_at_admission);
    RUN_TEST(test_a_held_not_a_number_is_restored_and_admitted);
    RUN_TEST(test_a_structure_that_keeps_every_write_is_admitted_unchanged);
    return UNITY_END();
}
