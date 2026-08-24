/*
 * The seam driven against a structure that answers fewer actuation channels
 * than the machine has.
 *
 * The actuation vocabulary belongs to the machine, so a structure of a given
 * architecture need not answer all of it. Everything about that case -- that a
 * command on an unanswered channel is refused rather than absorbed, that the
 * refusal names the channel, and that commanding nothing of an absent actuator
 * is not an error -- can only be exercised against a structure that leaves a
 * channel unanswered. The structure describing the reference machine answers
 * every channel, so these tests would pass unconditionally there, which is
 * indistinguishable from not having them.
 *
 * Nothing here names a structure symbol, and which channels the structure
 * answers is read through the seam rather than assumed -- so this suite states
 * what the seam does with a narrow declaration rather than what one structure's
 * declaration happens to be. The one thing it does carry of the structure
 * this environment builds is a description of its coefficients, as text, on the
 * same footing the machine-describing structure's coefficients are carried on.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include <unity.h>

#include "estimator.h"
#include "estimator_limits.h"
#include "plant_model.h"

#define STEP_MS 100u

/* Enough steps that a quantity has moved well away from where it started. */
#define SETTLE_STEPS 25

static plant_parameters_t parameters;
static actuation_channel_set_t answered;

/*
 * An admissible description for the structure this environment builds, as text
 * rather than as symbols -- the seam is not reached around by knowing what a
 * coefficient is called, which is the same footing test_plant carries the
 * machine-describing structure's coefficients on.
 *
 * The value is non-zero deliberately: a coefficient of zero can leave a
 * structure's quantities standing still whatever it is commanded, which would
 * let the tests below pass by the model never moving at all.
 */
static const char DESCRIPTION[] = "fixture.gain = 2.5\n";

/* The lowest channel the structure does not answer. */
static actuation_channel_t unanswered_channel(void)
{
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        if ((answered & ACTUATION_CHANNEL_BIT(channel)) == 0u) {
            return (actuation_channel_t)channel;
        }
    }
    TEST_FAIL_MESSAGE("this structure answers every channel, so the refusal cannot be exercised");
    return ACTUATION_CHANNEL_COUNT;
}

/* The lowest channel the structure does answer. */
static actuation_channel_t answered_channel(void)
{
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        if ((answered & ACTUATION_CHANNEL_BIT(channel)) != 0u) {
            return (actuation_channel_t)channel;
        }
    }
    TEST_FAIL_MESSAGE("this structure answers nothing, so no step could ever run");
    return ACTUATION_CHANNEL_COUNT;
}

static void read_all(const plant_model_t *model, float out[PLANT_QUANTITY_COUNT])
{
    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_TRUE(plant_model_quantity(model, (plant_quantity_t)quantity, &out[quantity]));
    }
}

static void initialise(plant_model_t *model)
{
    TEST_ASSERT_TRUE(plant_model_init(model, &parameters));
}

void setUp(void)
{
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    answered = plant_structure_actuation_channels();
}

void tearDown(void) {}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C2: The plant-model seam carries each
/// structure's statement of the channels it answers.
/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C3: Every structure behind the seam
/// declares which actuation channels it answers.
static void test_the_seam_reports_a_narrower_set_than_the_machine_has(void)
{
    /* Reached through the seam, without including a structure's own header. */
    TEST_ASSERT_NOT_EQUAL(0u, answered);

    for (unsigned channel = (unsigned)ACTUATION_CHANNEL_COUNT; channel < 32u; channel++) {
        TEST_ASSERT_EQUAL_UINT32(0u, answered & ACTUATION_CHANNEL_BIT(channel));
    }

    /* Narrower than the vocabulary, which is what makes this suite's subject one. */
    unsigned count = 0u;
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        count += (answered & ACTUATION_CHANNEL_BIT(channel)) != 0u ? 1u : 0u;
    }
    TEST_ASSERT_TRUE(count < (unsigned)ACTUATION_CHANNEL_COUNT);
}

/// SOL-PLANT-STEAM-DRAW-CHANNELS.C6: Boiler and fixture correctly refuse the
/// new steam-feed channel.
static void test_the_steam_feed_channel_is_refused_here_too(void)
{
    plant_model_t model;
    plant_step_error_t refusal;
    plant_actuation_t feeding = {{0u}};

    /*
     * This structure describes no machine and answers only the one channel a
     * heater acts on; the steam-side feed pump the new channel commands is
     * not among what it declares, and its answered-channel macro is not
     * extended to include it, so the same mechanism that already refuses
     * every other channel this structure leaves unanswered refuses this one.
     */
    TEST_ASSERT_EQUAL_UINT32(0u, answered & ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_STEAM_PUMP));

    feeding.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = ACTUATION_FULL_SCALE;
    initialise(&model);
    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &feeding, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_CHANNEL_UNANSWERED, refusal.fault);
    TEST_ASSERT_EQUAL(ACTUATION_CHANNEL_STEAM_PUMP, refusal.channel);
}

/// SOL-PLANT-STEAM-DRAW-CHANNELS.C1: Every plant structure's step accepts a
/// steam-demand rate the control law never sets.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C5: The new interfaces are exercised end to
/// end on the host verification tier.
static void test_a_steam_demand_alone_is_accepted(void)
{
    plant_model_t model;
    plant_step_error_t refusal;
    plant_actuation_t idle = {{0u}};

    /*
     * No channel commanded, so the only thing this step could be refused for
     * is the demand itself -- and nothing refuses it, whatever this structure
     * answers, because it is a step argument rather than a member of the
     * actuation record admissibility checks against.
     */
    initialise(&model);
    TEST_ASSERT_TRUE(plant_model_step_reporting(&model, &idle, 250.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_OK, refusal.fault);
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C4: A non-zero command on an
/// unanswered channel is refused and the model does not advance.
static void test_a_command_on_an_unanswered_channel_refuses_and_moves_nothing(void)
{
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];
    plant_step_error_t refusal;
    plant_actuation_t actuation = {{0u}};

    initialise(&model);
    /* Away from the initial state, so a step that ran would be visible. */
    actuation.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;
    for (int i = 0; i < SETTLE_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, STEP_MS));
    }
    read_all(&model, before);

    /* The same command, plus a level on a channel this structure does not answer. */
    actuation.level_permille[unanswered_channel()] = ACTUATION_FULL_SCALE;
    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &actuation, 0.0f, STEP_MS, &refusal));

    read_all(&model, after);
    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C4: A non-zero command on an
/// unanswered channel is refused and the model does not advance.
static void test_a_refused_command_is_not_applied_with_the_unanswered_channel_dropped(void)
{
    plant_model_t refused_instance;
    plant_model_t untouched_instance;
    plant_model_t stepped_instance;
    float refused_values[PLANT_QUANTITY_COUNT];
    float untouched_values[PLANT_QUANTITY_COUNT];
    float stepped_values[PLANT_QUANTITY_COUNT];
    plant_step_error_t refusal;
    plant_actuation_t answered_only = {{0u}};
    plant_actuation_t with_unanswered = {{0u}};

    answered_only.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;
    with_unanswered = answered_only;
    with_unanswered.level_permille[unanswered_channel()] = ACTUATION_FULL_SCALE;

    initialise(&refused_instance);
    initialise(&stepped_instance);

    TEST_ASSERT_FALSE(
        plant_model_step_reporting(&refused_instance, &with_unanswered, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_TRUE(plant_model_step(&stepped_instance, &answered_only, 0.0f, STEP_MS));

    read_all(&refused_instance, refused_values);
    read_all(&stepped_instance, stepped_values);

    /*
     * The instance that was refused must be where it started, not where the
     * command would have taken it with the unanswered channel quietly dropped.
     * That is checked against an instance that was never stepped at all: the
     * refused one must read identically to it on every quantity, and the
     * stepped one must have moved off it somewhere.
     *
     * It was once checked by requiring the refused and stepped instances to
     * differ on every quantity, which held while every quantity here answered
     * from the accumulator. Two of them no longer do, each for its own reason:
     * this structure answers no pump channel, so the rate water is drawn is a
     * constant zero, and it models nothing a draw could act on, so the rate
     * steam is drawn is a constant zero as well however large a demand a step
     * is given. Neither can differ between two instances, and either would make
     * the old form fail without anything being wrong. A constant is not
     * evidence either way, and asking it to be is what the form below avoids.
     */
    initialise(&untouched_instance);
    read_all(&untouched_instance, untouched_values);

    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_EQUAL_FLOAT(untouched_values[quantity], refused_values[quantity]);
    }

    /*
     * The accepted step moved every quantity that can move. Only the two rates
     * are excluded, and only because this structure reports each of them as a
     * constant zero -- a figure that cannot differ between any two instances and
     * is therefore evidence of nothing either way. They are named one by one
     * rather than skipped as a class, and the excluded ones are still required
     * to be equal rather than merely passed over: a structure that began
     * answering either rate from its accumulator would be caught here, which is
     * the whole reason the exclusion is not simply a gap.
     *
     * Excluding the constants rather than asking merely that something moved,
     * because a structure that advanced one quantity and froze the rest is
     * exactly what this is here to catch.
     */
    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        if (quantity == (int)PLANT_QUANTITY_BREW_FLOW_ML_PER_S ||
            quantity == (int)PLANT_QUANTITY_STEAM_DRAW_ML_PER_S) {
            TEST_ASSERT_EQUAL_FLOAT(untouched_values[quantity], stepped_values[quantity]);
            continue;
        }
        TEST_ASSERT_TRUE(stepped_values[quantity] != untouched_values[quantity]);
    }
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C5: A refused command reports which
/// channel had nowhere to land.
static void test_a_refusal_names_the_channel_that_had_nowhere_to_land(void)
{
    plant_model_t model;
    plant_step_error_t refusal;
    plant_actuation_t actuation = {{0u}};
    const actuation_channel_t absent = unanswered_channel();

    initialise(&model);
    actuation.level_permille[absent] = 1u;

    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &actuation, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_CHANNEL_UNANSWERED, refusal.fault);
    TEST_ASSERT_EQUAL(absent, refusal.channel);
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C5: A refused command reports which
/// channel had nowhere to land.
static void test_an_unanswered_channel_is_told_apart_from_the_other_refusals(void)
{
    plant_model_t model;
    plant_step_error_t refusal;
    plant_actuation_t runnable = {{0u}};
    plant_actuation_t over_scale = {{0u}};

    initialise(&model);
    runnable.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;
    over_scale.level_permille[answered_channel()] = ACTUATION_FULL_SCALE + 1u;

    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &runnable, 0.0f, 0u, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_ZERO_INTERVAL, refusal.fault);
    TEST_ASSERT_EQUAL(ACTUATION_CHANNEL_COUNT, refusal.channel);

    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, NULL, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_NOT_STEPPABLE, refusal.fault);
    TEST_ASSERT_EQUAL(ACTUATION_CHANNEL_COUNT, refusal.channel);

    TEST_ASSERT_FALSE(plant_model_step_reporting(NULL, &runnable, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_NOT_STEPPABLE, refusal.fault);

    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &over_scale, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_LEVEL_OVER_SCALE, refusal.fault);
    TEST_ASSERT_EQUAL(answered_channel(), refusal.channel);

    /* A step that runs says so rather than leaving the record from last time. */
    TEST_ASSERT_TRUE(plant_model_step_reporting(&model, &runnable, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_OK, refusal.fault);
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C5: A refused command reports which
/// channel had nowhere to land.
static void test_a_command_with_two_faults_reports_the_same_one_every_time(void)
{
    plant_model_t model;
    plant_actuation_t actuation = {{0u}};
    const actuation_channel_t absent = unanswered_channel();

    initialise(&model);
    /* Beyond full scale, and on a channel this structure does not answer. */
    actuation.level_permille[absent] = ACTUATION_FULL_SCALE + 1u;

    for (int repeat = 0; repeat < 8; repeat++) {
        plant_step_error_t refusal;
        memset(&refusal, 0xFF, sizeof(refusal));
        TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &actuation, 0.0f, STEP_MS, &refusal));
        TEST_ASSERT_EQUAL(PLANT_STEP_LEVEL_OVER_SCALE, refusal.fault);
        TEST_ASSERT_EQUAL(absent, refusal.channel);
    }
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C6: A zero level on an unanswered
/// channel advances the model normally.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C2: The demand input defaults to zero and
/// changes no existing behaviour when unset. Both instances below are driven
/// with the demand argument at zero and land on the same trajectory, which is
/// what this structure's existing behaviour already was.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C4: Every existing actuation channel behaves
/// unchanged on every structure. This loop zeroes every unanswered channel
/// this structure has, over the whole vocabulary rather than a fixed list, so
/// the new steam-feed channel -- unanswered here, the same as it was before
/// this structure had one more channel to leave unanswered -- is already
/// among them without the test having named it.
static void test_zeroing_an_unanswered_channel_gives_the_same_trajectory(void)
{
    plant_model_t zeroed_instance;
    plant_model_t untouched_instance;
    float zeroed_values[PLANT_QUANTITY_COUNT];
    float untouched_values[PLANT_QUANTITY_COUNT];
    plant_actuation_t zeroed = {{0u}};
    plant_actuation_t untouched = {{0u}};

    /*
     * A caller that zeroes every channel it does not use is the ordinary shape
     * of a control law driving a subset of the machine, and what it must get is
     * a step that runs. That is the whole claim, and the assertion below that
     * carries it is PLANT_STEP_OK on the zeroed instance: an implementation
     * treating a zero on an unanswered channel as a command refuses there.
     *
     * The two instances are stepped and compared as well, which pins that the
     * trajectory is the one the same command produces rather than merely some
     * trajectory -- but the two actuations are equal by construction, since a
     * level of zero is what an unset channel already carries. Nothing about
     * that comparison could fail on its own.
     */
    untouched.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;
    zeroed = untouched;
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        if ((answered & ACTUATION_CHANNEL_BIT(channel)) == 0u) {
            zeroed.level_permille[channel] = 0u;
        }
    }

    initialise(&zeroed_instance);
    initialise(&untouched_instance);

    for (int i = 0; i < SETTLE_STEPS; i++) {
        plant_step_error_t refusal;
        TEST_ASSERT_TRUE(plant_model_step_reporting(&zeroed_instance, &zeroed, 0.0f, STEP_MS, &refusal));
        TEST_ASSERT_EQUAL(PLANT_STEP_OK, refusal.fault);
        TEST_ASSERT_TRUE(plant_model_step(&untouched_instance, &untouched, 0.0f, STEP_MS));
    }

    read_all(&zeroed_instance, zeroed_values);
    read_all(&untouched_instance, untouched_values);
    TEST_ASSERT_EQUAL_MEMORY(untouched_values, zeroed_values, sizeof(untouched_values));
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C4: A non-zero command on an
/// unanswered channel is refused and the model does not advance.
static void test_the_form_without_a_record_refuses_exactly_what_the_reporting_form_does(void)
{
    plant_model_t plain_instance;
    plant_model_t reporting_instance;
    float plain_values[PLANT_QUANTITY_COUNT];
    float reporting_values[PLANT_QUANTITY_COUNT];
    plant_actuation_t unanswered = {{0u}};
    plant_actuation_t runnable = {{0u}};

    unanswered.level_permille[unanswered_channel()] = ACTUATION_FULL_SCALE;
    runnable.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;

    initialise(&plain_instance);
    initialise(&reporting_instance);

    for (int i = 0; i < SETTLE_STEPS; i++) {
        plant_step_error_t refusal;
        TEST_ASSERT_FALSE(plant_model_step(&plain_instance, &unanswered, 0.0f, STEP_MS));
        TEST_ASSERT_FALSE(
            plant_model_step_reporting(&reporting_instance, &unanswered, 0.0f, STEP_MS, &refusal));
        TEST_ASSERT_TRUE(plant_model_step(&plain_instance, &runnable, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(
            plant_model_step_reporting(&reporting_instance, &runnable, 0.0f, STEP_MS, &refusal));
    }

    read_all(&plain_instance, plain_values);
    read_all(&reporting_instance, reporting_values);
    TEST_ASSERT_EQUAL_MEMORY(reporting_values, plain_values, sizeof(reporting_values));

    /* A null record is refused rather than written through. */
    TEST_ASSERT_FALSE(plant_model_step_reporting(&reporting_instance, &runnable, 0.0f, STEP_MS, NULL));
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C3: Every plant structure answers the state
/// accessor.
///
/// This structure describes no machine, and it keeps one state rather than the
/// five the vocabulary names. That is why the refusal is exercised here: the
/// structures that describe a machine keep nearly all of them, so a refusal
/// demonstrated only against those would be demonstrated against almost
/// nothing -- the same reason this structure's actuation declaration is narrower
/// than the channel vocabulary.
///
/// Nothing here says which state it keeps. That is the structure's own answer,
/// and a test naming it would be asserting one structure's shape rather than
/// what the seam does with a narrow one.
static void test_a_structure_keeping_fewer_states_answers_some_and_refuses_others(void)
{
    const float SENTINEL = -999.0f;
    plant_model_t model;
    int answered_states = 0;
    int refused_states = 0;

    plant_actuation_t driving = {{0u}};
    driving.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;

    initialise(&model);
    for (int i = 0; i < SETTLE_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &driving, 0.0f, STEP_MS));
    }

    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        float value = SENTINEL;
        char message[96];

        (void)snprintf(message, sizeof(message), "state %d", state);
        if (plant_model_state(&model, (plant_state_t)state, &value)) {
            /* Answered, so it carries something the structure actually keeps
             * rather than the sentinel it was handed. */
            TEST_ASSERT_TRUE_MESSAGE(value != SENTINEL, message);
            TEST_ASSERT_TRUE_MESSAGE(isfinite(value), message);
            answered_states++;
        } else {
            /* Refused, so what the caller passed is exactly as it was. Zeroing
             * it is the failure this is written against: a caller cannot tell a
             * zero it was given from a state that happens to be zero. */
            TEST_ASSERT_EQUAL_FLOAT_MESSAGE(SENTINEL, value, message);
            refused_states++;
        }
    }

    /* Both cases occurred, so neither branch above passed by never running. */
    TEST_ASSERT_TRUE(answered_states > 0);
    TEST_ASSERT_TRUE(refused_states > 0);
    TEST_ASSERT_EQUAL_INT(PLANT_STATE_COUNT, answered_states + refused_states);
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C3: Every plant structure answers the state
/// accessor.
///
/// A state this structure does keep is still refused before the instance has
/// been initialised, on the terms plant_model_quantity already refuses one. The
/// refusal for an uninitialised instance and the refusal for a state the
/// structure does not keep are different things, and an implementation that
/// checked only the second would answer this one from a record that was never
/// populated.
static void test_a_state_read_before_initialisation_is_refused(void)
{
    const float SENTINEL = -555.0f;
    plant_model_t uninitialised;

    memset(&uninitialised, 0, sizeof(uninitialised));
    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        float value = SENTINEL;
        TEST_ASSERT_FALSE(plant_model_state(&uninitialised, (plant_state_t)state, &value));
        TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// A structure keeping fewer states than the vocabulary names answers the write
/// exactly where it answers the read, and refuses it everywhere else. A write
/// quietly dropped would leave a caller believing a correction it made was
/// taken, which is worse than being told the structure has nowhere to put it.
static void test_a_structure_keeping_fewer_states_answers_some_writes_and_refuses_others(void)
{
    const float SENTINEL = -999.0f;
    plant_parameters_t parameters;
    plant_parameter_error_t fault;
    plant_model_t model;

    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    unsigned accepted = 0u;
    unsigned refused = 0u;
    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        float held = SENTINEL;
        const bool readable = plant_model_state(&model, (plant_state_t)state, &held);

        if (readable) {
            float read_back = SENTINEL;
            TEST_ASSERT_TRUE(plant_model_set_state(&model, (plant_state_t)state, held + 7.5f));
            TEST_ASSERT_TRUE(plant_model_state(&model, (plant_state_t)state, &read_back));
            TEST_ASSERT_EQUAL_FLOAT(held + 7.5f, read_back);
            accepted++;
        } else {
            TEST_ASSERT_FALSE(plant_model_set_state(&model, (plant_state_t)state, 1.0f));
            refused++;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(accepted > 0u, "this structure accepted no write at all");
    TEST_ASSERT_TRUE_MESSAGE(refused > 0u, "this structure refused no write, so nothing was shown");
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// The refusals that do not depend on which states a structure keeps: an
/// instance that was never initialised, and a state outside the vocabulary.
static void test_a_state_written_before_initialisation_is_refused(void)
{
    plant_model_t uninitialised;
    plant_parameters_t parameters;
    plant_parameter_error_t fault;
    plant_model_t model;

    memset(&uninitialised, 0, sizeof(uninitialised));
    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        TEST_ASSERT_FALSE(plant_model_set_state(&uninitialised, (plant_state_t)state, 1.0f));
    }
    TEST_ASSERT_FALSE(plant_model_set_state(NULL, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 1.0f));

    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_FALSE(plant_model_set_state(&model, (plant_state_t)PLANT_STATE_COUNT, 1.0f));
}

/*
 * A limits declaration for the estimator to be brought up against. It carries
 * the statement that exempts it from accounting for its figures, because this
 * suite describes no machine and the numbers below mean nothing: what is being
 * established here is that the structure is refused, and an estimator refused
 * for want of a limits record would be refused for the wrong reason.
 */
static const char LIMITS_DECLARATION[] = "@describes-no-machine\n"
                                         "brew-temperature = -10000 .. 250000\n"
                                         "steam-temperature = -10000 .. 250000\n"
                                         "brew-pressure = -1000 .. 20000\n"
                                         "steam-pressure = -1000 .. 20000\n"
                                         "loss-tolerance-window-ms = 500\n"
                                         "excursion-bound-milli-c = 15000\n";

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C12: The estimator refuses a structure
/// that lacks the state it reconstructs.
///
/// This structure keeps no state for the water leaving the mass, so an
/// estimator has nothing here to reconstruct. It refuses rather than running on
/// whichever state this structure does keep, and an instance that refused
/// answers nothing afterwards.
static void test_the_estimator_refuses_a_structure_without_the_state_it_reconstructs(void)
{
    const float SENTINEL = -999.0f;
    plant_parameters_t parameters;
    plant_parameter_error_t fault;
    estimator_t estimator;
    float value = SENTINEL;

    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));

    estimator_limits_t limits;
    estimator_limits_error_t limits_fault;
    TEST_ASSERT_TRUE(estimator_limits_load(LIMITS_DECLARATION, sizeof(LIMITS_DECLARATION) - 1u,
                                           &limits, &limits_fault));

    TEST_ASSERT_FALSE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);

    const plant_actuation_t idle = {{0u}};
    TEST_ASSERT_FALSE(estimator_step(&estimator, &idle, 100u));

    int32_t residual = 0;
    TEST_ASSERT_FALSE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
}

/// SOL-PLANT-FLOW-REPORTED.C2: Every plant structure answers the flow quantity.
///
/// The structure that describes no machine answers it too, and answers zero.
/// It is the case the contract is hardest on: this structure answers no pump
/// channel, so there is no commanded level for a rate to be derived from and
/// nothing it could honestly report as moving. Refusing is still not open to
/// it -- a quantity is the machine's vocabulary and every structure answers
/// every one -- so the answer is the honest figure, which is none.
///
/// Checked under a command as well as at rest, and after a refusal, so a
/// structure that reported the accumulator here rather than nothing is caught
/// wherever the accumulator has moved.
static void test_the_structure_describing_no_machine_answers_the_drawn_rate_as_zero(void)
{
    plant_model_t model;
    plant_actuation_t answered = {{0u}};
    plant_actuation_t unanswered = {{0u}};
    plant_step_error_t refusal;
    float drawn = -1.0f;

    initialise(&model);
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    /* Driven hard on the channel it does answer, so the accumulator is well
     * away from zero: a structure answering the rate from it fails here. */
    answered.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;
    for (int i = 0; i < 20; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &answered, 0.0f, STEP_MS));
    }

    float accumulated = 0.0f;
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &accumulated));
    TEST_ASSERT_TRUE(accumulated != 0.0f);

    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    /* And after a refused command, which advances nothing. */
    unanswered.level_permille[unanswered_channel()] = ACTUATION_FULL_SCALE;
    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &unanswered, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C2: Every plant structure answers the
/// steam-draw quantity, the fixture included.
///
/// The structure that describes no machine answers it too, and answers zero. It
/// reaches that answer from the opposite direction to the water rate beside it:
/// that one has no commanded level to be derived from, whereas this structure is
/// handed a demand on every step, because the demand is a step argument every
/// structure takes whatever it models. What it does with the demand is nothing --
/// it has no mass for a draw to cool and no path for one to vent -- so no steam
/// leaves it however hard a caller asks.
///
/// Driven hard on the channel it does answer and given a large demand at the same
/// time, so both plausible wrong answers are live: a structure reporting its
/// accumulator fails on the first, and one echoing the demand it was handed fails
/// on the second. Refusing is not open to it either, which is what the returned
/// true asserts.
static void test_the_structure_describing_no_machine_answers_the_steam_draw_rate_as_zero(void)
{
    plant_model_t model;
    plant_actuation_t answered = {{0u}};
    float drawn = -1.0f;
    float accumulated = 0.0f;

    initialise(&model);
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    answered.level_permille[answered_channel()] = ACTUATION_FULL_SCALE;
    for (int i = 0; i < 20; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &answered, 9.0f, STEP_MS));
    }

    /* The accumulator is well away from zero by now, so a structure answering
     * the rate from it is caught rather than passing by coincidence. */
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &accumulated));
    TEST_ASSERT_TRUE(accumulated != 0.0f);

    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C1, C4: no shipped structure serves its
/// delivery points from separate masses, so the structure written for the
/// tests carries the independent-mass arrangement instead. It declares both
/// points, as any structure serving them must.
static void test_the_structure_describing_no_machine_declares_both_delivery_points(void)
{
    plant_delivery_point_set_t served = plant_structure_delivery_points();

    TEST_ASSERT_TRUE((served & PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_GROUP)) != 0u);
    TEST_ASSERT_TRUE(
        (served & PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT)) != 0u);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C2: the two points answer distinct mass
/// identifiers -- independent reservoirs rather than one shared casting.
static void test_the_structure_describing_no_machine_answers_distinct_masses(void)
{
    plant_heated_mass_id_t group_mass = 0u;
    plant_heated_mass_id_t spout_mass = 0u;

    TEST_ASSERT_TRUE(
        plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_GROUP, &group_mass));
    TEST_ASSERT_TRUE(
        plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, &spout_mass));
    TEST_ASSERT_TRUE(group_mass != spout_mass);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C4: the independent-mass arrangement is what
/// proves the query can answer no-contention at all -- no shipped structure
/// could be shown to fail this the way the thermoblock's shared casting could
/// only ever pass it.
static void test_the_structure_describing_no_machine_answers_no_contention(void)
{
    bool share = true;

    TEST_ASSERT_TRUE(plant_delivery_points_share_mass(
        PLANT_DELIVERY_POINT_GROUP, PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, &share));
    TEST_ASSERT_FALSE(share);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_structure_describing_no_machine_answers_the_drawn_rate_as_zero);
    RUN_TEST(test_the_structure_describing_no_machine_answers_the_steam_draw_rate_as_zero);
    RUN_TEST(test_the_seam_reports_a_narrower_set_than_the_machine_has);
    RUN_TEST(test_the_steam_feed_channel_is_refused_here_too);
    RUN_TEST(test_a_steam_demand_alone_is_accepted);
    RUN_TEST(test_a_structure_keeping_fewer_states_answers_some_and_refuses_others);
    RUN_TEST(test_a_state_read_before_initialisation_is_refused);
    RUN_TEST(test_a_command_on_an_unanswered_channel_refuses_and_moves_nothing);
    RUN_TEST(test_a_refused_command_is_not_applied_with_the_unanswered_channel_dropped);
    RUN_TEST(test_a_refusal_names_the_channel_that_had_nowhere_to_land);
    RUN_TEST(test_an_unanswered_channel_is_told_apart_from_the_other_refusals);
    RUN_TEST(test_a_command_with_two_faults_reports_the_same_one_every_time);
    RUN_TEST(test_zeroing_an_unanswered_channel_gives_the_same_trajectory);
    RUN_TEST(test_the_form_without_a_record_refuses_exactly_what_the_reporting_form_does);
    RUN_TEST(test_a_structure_keeping_fewer_states_answers_some_writes_and_refuses_others);
    RUN_TEST(test_a_state_written_before_initialisation_is_refused);
    RUN_TEST(test_the_estimator_refuses_a_structure_without_the_state_it_reconstructs);
    RUN_TEST(test_the_structure_describing_no_machine_declares_both_delivery_points);
    RUN_TEST(test_the_structure_describing_no_machine_answers_distinct_masses);
    RUN_TEST(test_the_structure_describing_no_machine_answers_no_contention);
    return UNITY_END();
}
