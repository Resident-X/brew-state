/*
 * The plant model exercised through the plant-model seam.
 *
 * Everything here reaches the model through plant_model.h and nothing names a
 * structure symbol, so these tests would link unchanged against a different
 * structure. What they assert about the trajectory is fixed independently of
 * what the structure says about itself: that rest stays at rest, that heat
 * raises temperatures, and that the same inputs give the same outputs. Whether
 * the trajectory matches a real machine is a question for a real machine.
 *
 * The coefficient names below are the thermoblock structure's, which is the
 * structure this environment builds. They are text in a description rather
 * than symbols in the source: the seam is not reached around by knowing what a
 * coefficient is called.
 *
 * Every description these tests use is generated from the one table below, so
 * a coefficient cannot be present in the table and absent from a fixture, and
 * perturbing one coefficient is changing one number rather than editing a
 * string by hand.
 */
#include <stdio.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#include <unity.h>

#include "plant_model.h"
#include "plant_robustness.h"

/* One coefficient of the structure under test, and an admissible value for it. */
typedef struct {
    const char *name;
    double value;
} coefficient_t;

/*
 * Admissible, plausible, and describing no machine. Deliberately not the
 * reference machine's own figures, which live in the description under params/
 * and are exercised on their own terms at the end of this file: what matters
 * here is only that these are accepted and that changing any one of them is
 * visible, and coupling that to the machine's numbers would mean every
 * commissioned measurement edited a test.
 */
static const coefficient_t NOMINAL[] = {
    {"ambient_temperature_c", 20.0},
    {"brew.thermal_mass_j_per_k", 420.0},
    {"brew.heater_power_w", 1200.0},
    {"brew.loss_w_per_k", 1.5},
    {"brew.outlet_held_volume_ml", 6.0},
    {"brew.outlet_conduction_time_constant_s", 15.0},
    {"steam.thermal_mass_j_per_k", 900.0},
    {"steam.heater_power_w", 1400.0},
    {"steam.loss_w_per_k", 2.2},
    {"pump.pressure_bar", 9.0},
    {"pump.flow_ml_per_s", 6.0},
    {"brew.pressure_time_constant_s", 0.8},
    /*
     * Deliberately not the same number as the ambient two lines above. They are
     * separate quantities, and a table that gave them one value would let a
     * structure reading ambient where it should read the feed pass every test
     * here -- which is the substitution the description says outright it must
     * not make.
     */
    {"water.feed_temperature_c", 18.0},
    {"water.heat_capacity_j_per_ml_k", 4.15},
    /*
     * Deliberately not the shipped figure either, and deliberately a long way
     * from the heat capacity above it: what a millilitre costs to boil and what
     * it costs to warm by a kelvin are separate coefficients, and a table that
     * put them near one another would let a structure reading the wrong one pass
     * an assertion made against the right one.
     */
    {"water.latent_heat_j_per_ml", 2000.0},
    {"steam.saturation_temperature_c", 100.0},
    {"steam.pressure_bar_per_k", 0.035},
    {"steam.pressure_fall_bar_per_ml", 0.02},
    /*
     * Deliberately not the same number as the brew pump's flow four lines up.
     * They are the two pumps' full-scale rates and a structure that read one
     * where it should read the other would be feeding the steam block off the
     * coffee pump, which is the substitution these two coefficients exist to
     * keep apart. Deliberately above the draw rate the tests below use as well,
     * so that a draw at a fully commanded feed is bounded by the demand rather
     * than by this figure, and the tests that want the bound to bind command a
     * duty that makes it bind rather than relying on the coefficient's size.
     */
    {"steam.feed_flow_ml_per_s", 5.0},
};

#define COEFFICIENT_COUNT (sizeof(NOMINAL) / sizeof(NOMINAL[0]))

/* Passed as the scaled index when no coefficient is to be perturbed. */
#define SCALE_NOTHING COEFFICIENT_COUNT

/* Room for the longest description these tests build, with slack. */
#define DESCRIPTION_MAX 2048

#define STEP_MS 100u

/*
 * Long enough that every coefficient has reached the trajectory: the steam mass
 * climbs past its saturation temperature, so the coefficients that only matter
 * above saturation matter, while the pressure time constant still shows in the
 * early steps the signature covers.
 */
#define TRAJECTORY_STEPS 1200

/* Short runs, where the criteria only need a step or a few dozen. */
#define SHORT_STEPS 40

/*
 * Long enough that the coffee side has stopped moving at any coefficients these
 * tests use, so a comparison against an energy balance is against where the
 * model settled rather than against a point on its way there.
 */
#define SETTLED_STEPS 5000

/*
 * And long enough to be well into a transient without being through it, which is
 * where a coefficient that only shapes the way there has anything to say.
 */
#define TRANSIENT_STEPS 400

static const plant_actuation_t AT_REST = {{0u, 0u, 0u, 0u}};
static const plant_actuation_t HEATING = {{ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, 0u, 0u}};
/*
 * Heat and both pumps together, so no coefficient is left out of the trajectory.
 * The steam feed is commanded here for that reason and not as scenery, and it is
 * commanded low on purpose. What the steam side gives up to a draw is the lower
 * of the demand and this channel's rate, so a feed commanded at full scale would
 * sit above the small demand the trajectories below are driven at, the bound
 * would never bind, and `steam.feed_flow_ml_per_s` would be a coefficient no
 * trajectory could see. A hundredth of full scale against a nominal five
 * millilitres a second is a twentieth of a millilitre a second, which is under
 * that demand -- so the bound binds, the feed sets the draw, and perturbing
 * either the feed's coefficient or the cost of what it feeds moves the run.
 */
static const plant_actuation_t WORKING = {{ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE,
                                           ACTUATION_FULL_SCALE / 2u,
                                           ACTUATION_FULL_SCALE / 100u}};
/*
 * Heating with the steam feed running and the brew pump shut: the state a draw
 * is actually taken in. Kept apart from HEATING rather than folded into it
 * because the difference between the two is exactly what the feed bound is, and
 * a test that wants a draw honoured and a test that wants one refused for want
 * of feed have to be able to say which they mean.
 */
static const plant_actuation_t DRAWING = {{ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, 0u,
                                           ACTUATION_FULL_SCALE}};
/* Nothing heated, nothing pumped through the group, and the steam feed open. */
static const plant_actuation_t FEEDING = {{0u, 0u, 0u, ACTUATION_FULL_SCALE}};
/*
 * Everything the machine has, with the steam feed at full rather than throttled:
 * WORKING with the bound taken off. Tests that need both sides running at once
 * and a draw actually honoured belong here -- WORKING's throttled feed exists so
 * that a small demand reaches the feed coefficient, and a draw taken against it
 * is clamped to a twentieth of a millilitre a second, which is not a draw those
 * tests are about.
 */
static const plant_actuation_t WORKING_AND_FEEDING = {
    {ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE / 2u,
     ACTUATION_FULL_SCALE}};

static plant_parameters_t parameters;
static plant_parameter_error_t error;
static char valid_text[DESCRIPTION_MAX];
static size_t valid_length;

/*
 * Write a description of the nominal coefficients, with the one at
 * `scaled_index` multiplied by `factor`. Values are written to nine significant
 * figures, which round-trips a single-precision value exactly, so a difference
 * in an outcome is a difference in the coefficient rather than in its spelling.
 */
static size_t describe(char *out, size_t capacity, size_t scaled_index, double factor)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const double value = (i == scaled_index) ? NOMINAL[i].value * factor : NOMINAL[i].value;
        const int written =
            snprintf(out + used, capacity - used, "%s = %.9g\n", NOMINAL[i].name, value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

void setUp(void)
{
    memset(&parameters, 0, sizeof(parameters));
    memset(&error, 0, sizeof(error));
    valid_length = describe(valid_text, sizeof(valid_text), SCALE_NOTHING, 1.0);
    TEST_ASSERT_TRUE(plant_parameters_load(valid_text, valid_length, &parameters, &error));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, error.fault);
}

void tearDown(void) {}

/* Read every quantity the model exposes into `out`. */
static void read_all(const plant_model_t *model, float out[PLANT_QUANTITY_COUNT])
{
    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_TRUE(plant_model_quantity(model, (plant_quantity_t)quantity, &out[quantity]));
    }
}

/*
 * Read every state the structure keeps into `out`, and require it to keep them
 * all. This structure does; a structure that did not would refuse, and the
 * suites driving those are where that is exercised.
 */
static void read_all_states(const plant_model_t *model, float out[PLANT_STATE_COUNT])
{
    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        TEST_ASSERT_TRUE(plant_model_state(model, (plant_state_t)state, &out[state]));
    }
}

/* The casting the element acts on, which is also the quantity this machine reports. */
static float heated_mass(const plant_model_t *model)
{
    float value = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_state(model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &value));
    return value;
}

/* Run `steps` steps under one actuation and leave the quantities in `out`. */
static void run(plant_model_t *model, const plant_actuation_t *actuation, int steps,
                float out[PLANT_QUANTITY_COUNT])
{
    for (int i = 0; i < steps; i++) {
        TEST_ASSERT_TRUE(plant_model_step(model, actuation, 0.0f, STEP_MS));
    }
    read_all(model, out);
}

/*
 * The rate every signature below is taken with the steam wand open at.
 *
 * Not zero, and that is the whole reason it is named. Two of this structure's
 * coefficients are read by no relation at all with the wand shut -- what the
 * steam drawn off the block costs it, and what that draw costs the steam path in
 * pressure -- so a signature taken at no demand would report both as
 * coefficients nothing reads, which is a wrong conclusion drawn from a true
 * observation about the run that was made.
 *
 * The figure is small on purpose. A large draw holds the steam mass below
 * saturation for the whole of the runs these signatures are taken over, and the
 * pressure relation is then sitting on its floor throughout -- so the pressure
 * coefficient would still reach nothing, for a second reason. At this rate the
 * mass passes saturation part-way through the longer runs and both coefficients
 * are in the trajectory.
 */
#define SIGNATURE_STEAM_DEMAND_ML_PER_S 0.1f

/*
 * A number standing for the whole trajectory rather than its endpoint.
 *
 * Every quantity at every step is folded in, because a coefficient can matter
 * to the path without mattering to where the path ends: a time constant
 * changes how fast a pressure settles and not what it settles at, so comparing
 * final values alone would report it as unused.
 *
 * The accumulator is deliberately wider than the states it sums. It is a
 * comparison device rather than part of the model, and summing thousands of
 * single-precision values into a single-precision total would lose the small
 * differences this exists to detect -- which would quietly blind the check that
 * every coefficient reaches the equations.
 *
 * Taken over the states rather than over the quantities, because what these
 * tests ask is whether a coefficient reaches the equations, and a coefficient
 * can reach them without reaching anything the machine exposes. The outlet time
 * constant is exactly that: it acts on the water on its way to the group, which
 * is downstream of every quantity and feeds back into none of them. Summing the
 * quantities would report that coefficient as unread -- a wrong conclusion from
 * a true observation, since it is read and what it changes is a state no
 * quantity carries. That the machine cannot see it either is a real limit and
 * is stated where it belongs, among the omissions in params/thermoblock.md.
 */
static double signature(plant_model_t *model, const plant_actuation_t *actuation, int steps)
{
    double total = 0.0;

    for (int i = 0; i < steps; i++) {
        float states[PLANT_STATE_COUNT];
        float quantities[PLANT_QUANTITY_COUNT];
        TEST_ASSERT_TRUE(
            plant_model_step(model, actuation, SIGNATURE_STEAM_DEMAND_ML_PER_S, STEP_MS));
        read_all_states(model, states);
        for (int state = 0; state < PLANT_STATE_COUNT; state++) {
            total += states[state];
        }
        /*
         * The quantities as well as the states, because the two vocabularies
         * do not cover each other. A structure may produce a quantity from
         * something it never integrates -- the rate water is drawn is exactly
         * that, being a function of the commanded pump level and of no state --
         * so a signature taken over the states alone is blind to any
         * coefficient reaching only such a quantity, and would report it inert.
         */
        read_all(model, quantities);
        for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
            total += quantities[quantity];
        }
    }
    return total;
}

/* The signature of a run under one description. */
static double signature_of(const char *text, size_t length, const plant_actuation_t *actuation,
                           int steps)
{
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, length, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));
    return signature(&model, actuation, steps);
}

/*
 * A description in which every coefficient is an admissible placeholder except
 * the one at `index`, which is written out verbatim. Used to drive a single
 * coefficient's value through the parser without disturbing the others.
 *
 * The placeholder is each coefficient's own nominal value rather than one number
 * standing in for all of them. It used to be a bare 1.0, which worked only while
 * every coefficient in the table had a range containing it -- and what a
 * millilitre of water costs to boil does not, because that range is drawn around
 * water's own figure and a millilitre that cost one joule to vaporise is not
 * water. A shared placeholder is a quiet dependency of the whole bound-discovery
 * machinery on a property no coefficient owes.
 */
static size_t describe_with(size_t index, const char *token, char *out, size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        char placeholder[32];
        TEST_ASSERT_TRUE(
            snprintf(placeholder, sizeof(placeholder), "%.17g", NOMINAL[i].value) > 0);
        const int written = snprintf(out + used, capacity - used, "%s = %s\n", NOMINAL[i].name,
                                     i == index ? token : placeholder);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: the structure runs on the host
 * -- a model instance initialises and advances over a sequence of steps to
 * completion. */
static void test_the_model_advances_over_a_sequence_of_steps(void)
{
    plant_model_t model;
    float quantities[PLANT_QUANTITY_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    run(&model, &WORKING, TRAJECTORY_STEPS, quantities);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: a step taken with no actuation
 * and no external influence leaves every quantity the model exposes
 * unchanged. */
static void test_a_step_at_rest_changes_nothing(void)
{
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    read_all(&model, before);
    TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, 0.0f, STEP_MS));
    read_all(&model, after);

    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: many steps at rest change
 * nothing either -- a source or sink too small to see in one step would
 * accumulate over hundreds. */
static void test_many_steps_at_rest_change_nothing(void)
{
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    read_all(&model, before);
    run(&model, &AT_REST, TRAJECTORY_STEPS, after);

    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: rest stays at rest at an
 * ambient the rest of the suite does not use, so the property cannot be
 * holding because one temperature happens to be written into the equations. */
static void test_rest_stays_at_rest_at_a_different_ambient(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];

    /* Scale ambient alone; every other coefficient stays where it was. */
    const size_t length = describe(text, sizeof(text), 0u, 1.9);

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, length, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));
    read_all(&model, before);
    run(&model, &AT_REST, TRAJECTORY_STEPS, after);

    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: a step taken with heat applied
 * raises the temperature quantities and lowers none of them. */
static void test_heat_raises_the_temperatures_and_lowers_nothing(void)
{
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    read_all(&model, before);
    TEST_ASSERT_TRUE(plant_model_step(&model, &HEATING, 0.0f, STEP_MS));
    read_all(&model, after);

    TEST_ASSERT_TRUE(after[PLANT_QUANTITY_BREW_TEMPERATURE_C] >
                     before[PLANT_QUANTITY_BREW_TEMPERATURE_C]);
    TEST_ASSERT_TRUE(after[PLANT_QUANTITY_STEAM_TEMPERATURE_C] >
                     before[PLANT_QUANTITY_STEAM_TEMPERATURE_C]);

    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_TRUE(after[quantity] >= before[quantity]);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: the same step sequence run
 * twice from the same initial state and inputs reproduces the same trajectory
 * exactly. */
static void test_the_same_inputs_reproduce_the_same_trajectory(void)
{
    plant_model_t first;
    plant_model_t second;
    float one[PLANT_QUANTITY_COUNT];
    float two[PLANT_QUANTITY_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&first, &parameters));
    TEST_ASSERT_TRUE(plant_model_init(&second, &parameters));
    run(&first, &WORKING, TRAJECTORY_STEPS, one);
    run(&second, &WORKING, TRAJECTORY_STEPS, two);

    TEST_ASSERT_EQUAL_MEMORY(one, two, sizeof(one));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: a step is refused rather than
 * clamped when an actuation channel is beyond full scale, and refusing changes
 * nothing. */
static void test_an_actuation_beyond_full_scale_is_refused_and_changes_nothing(void)
{
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];
    const plant_actuation_t over_scale = {{ACTUATION_FULL_SCALE + 1u, 0u, 0u}};

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    read_all(&model, before);
    TEST_ASSERT_FALSE(plant_model_step(&model, &over_scale, 0.0f, STEP_MS));
    read_all(&model, after);

    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: an uninitialised instance is
 * not usable, and a zero-length step is refused. */
static void test_an_uninitialised_instance_and_a_zero_step_are_refused(void)
{
    plant_model_t model;
    float value = 0.0f;

    memset(&model, 0, sizeof(model));
    TEST_ASSERT_FALSE(plant_model_step(&model, &HEATING, 0.0f, STEP_MS));
    TEST_ASSERT_FALSE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &value));

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_FALSE(plant_model_step(&model, &HEATING, 0.0f, 0u));
    TEST_ASSERT_FALSE(plant_model_quantity(&model, PLANT_QUANTITY_COUNT, &value));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C3: the equations read their
 * coefficients from the record, so two descriptions differing in a single
 * coefficient give two different trajectories from the same code. */
static void test_one_changed_coefficient_changes_the_trajectory(void)
{
    char variant[DESCRIPTION_MAX];
    /* brew.heater_power_w is index 2 in the table above. */
    const size_t length = describe(variant, sizeof(variant), 2u, 1.1);

    const double nominal = signature_of(valid_text, valid_length, &WORKING, TRAJECTORY_STEPS);
    const double changed = signature_of(variant, length, &WORKING, TRAJECTORY_STEPS);

    TEST_ASSERT_TRUE(nominal != changed);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C3: *every* coefficient the
 * structure declares reaches the equations. Perturbing any one of them alone
 * changes the trajectory, which is what a coefficient quietly written into the
 * equations would fail -- requiring each name to be present in the description
 * only proves the parameter table lists it, not that anything reads it. */
static void test_every_coefficient_reaches_the_equations(void)
{
    const double nominal = signature_of(valid_text, valid_length, &WORKING, TRAJECTORY_STEPS);

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        char variant[DESCRIPTION_MAX];
        const size_t length = describe(variant, sizeof(variant), i, 1.1);
        const double perturbed = signature_of(variant, length, &WORKING, TRAJECTORY_STEPS);

        if (nominal == perturbed) {
            char message[128];
            (void)snprintf(message, sizeof(message),
                           "changing %s alone did not change the trajectory", NOMINAL[i].name);
            TEST_FAIL_MESSAGE(message);
        }
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C3: a description carrying comments
 * and blank lines is read the same as one without them, so the artefact a
 * machine ships with can be commented. */
static void test_comments_and_blank_lines_do_not_change_what_is_read(void)
{
    char commented[DESCRIPTION_MAX + 64];
    const int prefix = snprintf(commented, sizeof(commented), "# a comment\n\n");

    TEST_ASSERT_TRUE(prefix > 0);
    memcpy(commented + prefix, valid_text, valid_length);

    const double plain = signature_of(valid_text, valid_length, &WORKING, SHORT_STEPS);
    const double with_comments =
        signature_of(commented, (size_t)prefix + valid_length, &WORKING, SHORT_STEPS);

    TEST_ASSERT_TRUE(plain == with_comments);
}

/* Everything but the named line of the valid description, so one omission can
 * be tested without writing out another description by hand. */
static size_t description_without(const char *omitted, char *out, size_t capacity)
{
    const char *cursor = valid_text;
    const char *limit = valid_text + valid_length;
    size_t used = 0u;

    while (cursor < limit) {
        const char *newline = memchr(cursor, '\n', (size_t)(limit - cursor));
        const size_t length =
            (newline != NULL) ? (size_t)(newline - cursor) + 1u : (size_t)(limit - cursor);
        if (strncmp(cursor, omitted, strlen(omitted)) != 0) {
            TEST_ASSERT_TRUE(used + length < capacity);
            memcpy(out + used, cursor, length);
            used += length;
        }
        cursor += length;
    }
    out[used] = '\0';
    return used;
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a description omitting a
 * coefficient the structure requires is refused, the missing one is named, and
 * nothing is assumed for it. Every coefficient is required, not just the one
 * that happens to be tested. */
static void test_omitting_any_single_coefficient_is_refused(void)
{
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        char reduced[DESCRIPTION_MAX];
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        const size_t length = description_without(NOMINAL[i].name, reduced, sizeof(reduced));

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_FALSE(plant_parameters_load(reduced, length, &loaded, &fault));
        TEST_ASSERT_EQUAL(PLANT_PARAMETER_MISSING, fault.fault);
        TEST_ASSERT_EQUAL_STRING(NOMINAL[i].name, fault.parameter);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a coefficient outside the range
 * the structure declares is refused, and the refusal carries the range so the
 * report is actionable. */
static void test_a_coefficient_outside_its_range_is_refused_with_the_range(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    /* brew.heater_power_w far beyond the power any espresso machine draws. */
    const size_t length = describe(text, sizeof(text), 2u, 1000.0);

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(text, length, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault);
    TEST_ASSERT_EQUAL_STRING("brew.heater_power_w", fault.parameter);
    TEST_ASSERT_EQUAL_UINT32(3u, fault.line);
    TEST_ASSERT_TRUE(fault.value == (float)(NOMINAL[2].value * 1000.0));
    TEST_ASSERT_TRUE(fault.maximum < fault.value);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a value that compares false to
 * both ends of the admissible range is refused rather than run. A not-a-number
 * is what a calibration tool that divided by zero emits; accepted, it would
 * initialise a model whose every quantity reads NaN while the refusal reported
 * nothing wrong. */
static void test_a_not_a_number_is_refused_rather_than_run(void)
{
    static const char *const spellings[] = {"nan", "-nan", "NAN", "nan(0x1)", "inf", "-inf"};

    for (size_t i = 0u; i < sizeof(spellings) / sizeof(spellings[0]); i++) {
        char text[DESCRIPTION_MAX];
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        const size_t used = describe_with(1u, spellings[i], text, sizeof(text));

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_FALSE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_EQUAL(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault);
        TEST_ASSERT_EQUAL_STRING(NOMINAL[1].name, fault.parameter);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a value the type cannot hold at
 * all is refused rather than delivered as the zero or the infinity it collapsed
 * to. A coefficient quietly turned into zero is not the coefficient the
 * description asked for, and nothing downstream could tell the difference. */
static void test_a_value_that_collapses_to_zero_is_refused(void)
{
    /* brew.loss_w_per_k admits zero, so an underflow would otherwise be taken
     * for a legitimate reading of this description rather than a refusal. */
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    const size_t used = describe_with(3u, "1e-60", text, sizeof(text));

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault);
    TEST_ASSERT_EQUAL_STRING(NOMINAL[3].name, fault.parameter);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a value inside the range its
 * structure declares is accepted even when holding it costs precision. The
 * refusal above is about what the type cannot carry at all, not about what it
 * carries approximately -- confusing the two would reject values the structure
 * itself calls admissible. */
static void test_a_value_below_full_precision_is_still_accepted(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    const size_t used = describe_with(3u, "1e-38", text, sizeof(text));

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a description that cannot be
 * parsed at all is refused, and the fault points at the line. */
static void test_an_unparsable_description_is_refused_at_its_line(void)
{
    static const struct {
        const char *text;
        plant_parameter_fault_t fault;
        uint32_t line;
    } cases[] = {
        {"ambient_temperature_c = 20.0\nthis line has no separator\n", PLANT_PARAMETER_MALFORMED,
         2u},
        {"ambient_temperature_c = not-a-number\n", PLANT_PARAMETER_MALFORMED, 1u},
        {"ambient_temperature_c = 20.0 30.0\n", PLANT_PARAMETER_MALFORMED, 1u},
        {" = 20.0\n", PLANT_PARAMETER_MALFORMED, 1u},
        {"ambient_temperature_c =\n", PLANT_PARAMETER_MALFORMED, 1u},
        {"not_a_coefficient = 1.0\n", PLANT_PARAMETER_UNKNOWN, 1u},
        {"ambient_temperature_c = 20.0\nambient_temperature_c = 21.0\n", PLANT_PARAMETER_DUPLICATE,
         2u},
    };

    for (size_t i = 0u; i < sizeof(cases) / sizeof(cases[0]); i++) {
        plant_parameters_t loaded;
        plant_parameter_error_t fault;

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_FALSE(
            plant_parameters_load(cases[i].text, strlen(cases[i].text), &loaded, &fault));
        TEST_ASSERT_EQUAL(cases[i].fault, fault.fault);
        TEST_ASSERT_EQUAL_UINT32(cases[i].line, fault.line);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a refused description
 * substitutes no value -- the record it was refused into is left exactly as it
 * was, rather than half filled in. */
static void test_a_refusal_leaves_the_record_untouched(void)
{
    static const char partial[] = "ambient_temperature_c = 45.0\n";

    plant_parameters_t record = parameters;
    plant_parameter_error_t fault;
    plant_model_t before_model;
    plant_model_t after_model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&before_model, &record));
    run(&before_model, &WORKING, SHORT_STEPS, before);

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(partial, strlen(partial), &record, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MISSING, fault.fault);

    TEST_ASSERT_TRUE(plant_model_init(&after_model, &record));
    run(&after_model, &WORKING, SHORT_STEPS, after);

    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: an empty description is a
 * refusal rather than a record of defaults. */
static void test_an_empty_description_is_refused(void)
{
    plant_parameters_t loaded;
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load("", 0u, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MISSING, fault.fault);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C3: a name reached past leading
 * blanks is the same name. A description written with its lines indented -- by
 * a generator that lines values up, or by hand -- describes the same machine as
 * one written flush left, and a loader that stopped trimming would refuse every
 * line of it as unknown rather than say what was wrong. */
static void test_leading_blanks_do_not_change_what_is_read(void)
{
    char indented[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    size_t used = 0u;

    /* An indented comment too: the line is recognised as a comment only after
     * the blanks in front of it have been stepped over. */
    const int header = snprintf(indented, sizeof(indented), "   \t# an indented comment\n");
    TEST_ASSERT_TRUE(header > 0);
    used += (size_t)header;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written = snprintf(indented + used, sizeof(indented) - used, "  \t%s = %.9g\n",
                                     NOMINAL[i].name, NOMINAL[i].value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < sizeof(indented));
    }

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(indented, used, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &loaded, sizeof(parameters));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C3: the description is the span it
 * was given and not a string. A file whose last line has no newline after it is
 * ordinary, and the loader is told a length rather than left to find a
 * terminator -- so the last line has to be read without stepping past the span
 * to look for one. The byte after the span is set to something that is not a
 * newline here, because a loader reading one character too far is invisible
 * against a buffer that happens to hold the newline it was looking for. */
static void test_a_final_line_without_a_newline_is_read(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    size_t used = describe(text, sizeof(text), SCALE_NOTHING, 1.0);

    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_EQUAL_CHAR('\n', text[used - 1u]);
    used--;
    text[used] = '#';

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &loaded, sizeof(parameters));
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a line that is not a setting is
 * refused, and the refusal quotes the line. The quoted text is the whole
 * content of the report for a line with no separator -- there is no name to
 * give -- so a report carrying the wrong span names the wrong thing to whoever
 * has to fix the file. */
static void test_a_line_with_no_separator_is_refused_quoting_the_line(void)
{
    static const char TEXT[] = "ambient_temperature_c 20\n";
    plant_parameters_t loaded;
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(TEXT, sizeof(TEXT) - 1u, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MALFORMED, fault.fault);
    TEST_ASSERT_EQUAL_UINT32(1u, fault.line);
    TEST_ASSERT_EQUAL_STRING("ambient_temperature_c 20", fault.parameter);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a setting with no name is
 * refused quoting the line, for the same reason -- an empty name is not a name
 * the report could give instead. */
static void test_a_setting_with_no_name_is_refused_quoting_the_line(void)
{
    static const char TEXT[] = "= 20\n";
    plant_parameters_t loaded;
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(TEXT, sizeof(TEXT) - 1u, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MALFORMED, fault.fault);
    TEST_ASSERT_EQUAL_UINT32(1u, fault.line);
    TEST_ASSERT_EQUAL_STRING("= 20", fault.parameter);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: the bounds a structure declares
 * are admissible values and not the first refused ones.
 *
 * The bisection further down finds whichever boundary the loader happens to
 * enforce, and shows that it enforces one. That is a different claim from this.
 * A loader refusing its own declared maximum would still have a boundary to
 * find, one value away from the right one, and every property sampled inside
 * the range would still pass. The declared bound itself is what a calibration
 * tool writes out when a measurement lands at the end of the admissible span,
 * so refusing it rejects a description the structure says is fine.
 *
 * Both bounds are learned through the seam by provoking a refusal, so nothing
 * here duplicates a number the structure could change. */
static void test_the_declared_bounds_are_themselves_admissible(void)
{
    char text[DESCRIPTION_MAX];
    char token[32];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    /* brew.heater_power_w, far beyond the power any espresso machine draws, so
     * the refusal reports the range rather than anything about this value. */
    size_t used = describe_with(2u, "1e12", text, sizeof(text));

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault);

    const float bounds[] = {fault.minimum, fault.maximum};
    TEST_ASSERT_TRUE(bounds[0] < bounds[1]);

    /* Nine significant figures round-trip a single-precision value exactly, so
     * what is offered back is the bound itself and not a neighbour of it. */
    for (size_t i = 0u; i < sizeof(bounds) / sizeof(bounds[0]); i++) {
        TEST_ASSERT_TRUE(snprintf(token, sizeof(token), "%.9g", (double)bounds[i]) > 0);
        used = describe_with(2u, token, text, sizeof(text));

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: the structure asks for far fewer
 * parameters than the loader will admit.
 *
 * The loader caps how many parameters a structure may declare, because it
 * tracks which ones were supplied in a fixed-width bitmask. Nothing else here
 * approaches that cap, and several things quietly rely on nothing doing so --
 * including the reading that a mutation of the cap's comparison cannot change
 * what any build of this program does. That reading is only true while the
 * structures stay well clear of it, so this asserts the clearance rather than
 * leaving it as a property somebody would have to notice going away.
 *
 * The count is the test's own table, which the omission test above pins to the
 * structure's: every name in it is one the structure requires, and omitting any
 * one of them is refused. */
static void test_the_structure_declares_far_fewer_parameters_than_the_loader_admits(void)
{
    /* Conservative: well under the cap, and well over what a machine this size
     * plausibly grows to. Raising it is a decision, not a formality. */
    TEST_ASSERT_TRUE(COEFFICIENT_COUNT <= 32u);
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: a value token longer than the
 * loader can hold is refused rather than copied.
 *
 * The loader parses a token by copying it into a fixed buffer first, so the
 * length it will take is a boundary of its own -- one nothing else here
 * approaches, since every other description is written by a generator that
 * produces short numbers. A token at or past that length is the input that
 * would overrun the buffer, and it is offered here across a span wide enough to
 * sit either side of wherever the limit falls, so that no number naming the
 * limit has to be repeated in this file to aim at it. */
static void test_a_value_token_longer_than_the_loader_holds_is_refused(void)
{
    /* Comfortably past any buffer a token this short would be copied into. */
    char token[256];

    for (size_t length = 32u; length < sizeof(token) - 1u; length++) {
        char text[DESCRIPTION_MAX];
        plant_parameters_t loaded;
        plant_parameter_error_t fault;

        /*
         * A number far outside any admissible range. Whether this is refused as
         * unreadable or as out of range depends on whether the loader could
         * hold it at all -- but refused it must be, at every length.
         */
        memset(token, '9', length);
        token[length] = '\0';
        size_t used = describe_with(2u, token, text, sizeof(text));

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_FALSE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_TRUE(fault.fault == PLANT_PARAMETER_MALFORMED ||
                         fault.fault == PLANT_PARAMETER_OUT_OF_RANGE);

        /*
         * The nominal value of the same coefficient, padded out to the same
         * length with zeros after a decimal point -- a different spelling of
         * the same number. Magnitude cannot be what refuses this one, so its
         * length is the only thing left under test. Where it is short enough to
         * hold, the record that arrives has to be the one the nominal
         * description produces: a loader that copied as much as it had room for
         * and parsed that would read a truncation of the number and deliver a
         * different coefficient without reporting anything.
         */
        int written = snprintf(token, sizeof(token), "%.9g", NOMINAL[2].value);
        TEST_ASSERT_TRUE(written > 0);
        size_t spelled = (size_t)written;
        if (spelled >= length) {
            continue;
        }
        if (strchr(token, '.') == NULL && strchr(token, 'e') == NULL) {
            token[spelled++] = '.';
        }
        while (spelled < length) {
            token[spelled++] = '0';
        }
        token[spelled] = '\0';

        used = 0u;
        for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
            if (i == 2u) {
                written = snprintf(text + used, sizeof(text) - used, "%s = %s\n", NOMINAL[i].name,
                                   token);
            } else {
                written = snprintf(text + used, sizeof(text) - used, "%s = %.9g\n", NOMINAL[i].name,
                                   NOMINAL[i].value);
            }
            TEST_ASSERT_TRUE(written > 0);
            used += (size_t)written;
            TEST_ASSERT_TRUE(used < sizeof(text));
        }

        memset(&fault, 0, sizeof(fault));
        if (plant_parameters_load(text, used, &loaded, &fault)) {
            TEST_ASSERT_EQUAL_MEMORY(&parameters, &loaded, sizeof(parameters));
        } else {
            TEST_ASSERT_EQUAL(PLANT_PARAMETER_MALFORMED, fault.fault);
        }
    }
}

/* ---------------------------------------------------------------------------
 * Properties over the range each coefficient declares admissible.
 *
 * The tests above fix every coefficient at one nominal value. A structure that
 * satisfies an invariant there can still violate it elsewhere inside the range
 * it declares for itself, and the declared range is a claim the structure makes
 * that nothing would otherwise check.
 *
 * The bounds are discovered through the seam rather than copied from the
 * structure: a description is offered and either accepted or refused, and the
 * boundary is found by bisection. Copying the numbers into this file would
 * duplicate a claim that can drift, and reading them from the structure's own
 * table would mean naming a symbol the seam exists to keep out of consumers.
 *
 * Generation is from a fixed seed, so a failure names a case that can be
 * reproduced exactly rather than one that appeared once.
 * ------------------------------------------------------------------------ */

#define PROPERTY_CASES 128
#define PROPERTY_SEED 0x5EEDu

/* Corners with each coefficient independently at one bound or the other. */
#define MIXED_CORNERS 64

/* Far outside anything a coefficient of this structure could admit. */
#define CERTAINLY_REFUSED 1.0e12

/* Enough halvings to carry the starting width down past the precision the
 * comparison is made in; too few silently converges on the anchor instead of
 * on the bound, and every sample then comes from a single point. */
#define BISECTION_STEPS 200

static uint32_t rng_state;

static void rng_seed(uint32_t seed)
{
    rng_state = seed != 0u ? seed : 1u;
}

/* xorshift32: small, deterministic, and adequate for spreading sample points. */
static uint32_t rng_next(void)
{
    uint32_t x = rng_state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    rng_state = x;
    return x;
}

static double rng_unit(void)
{
    return (double)(rng_next() >> 8) / (double)(1u << 24);
}

/* A description with every coefficient admissible except the one under test. */
static bool accepts(size_t index, double value)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        int written;
        if (i == index) {
            written = snprintf(text + used, sizeof(text) - used, "%s = %.17g\n", NOMINAL[i].name,
                               value);
        } else {
            /* Each coefficient's own nominal value, for the reason describe_with
             * above gives: no single placeholder is inside every declared range,
             * and one that happened to be would be an accident this machinery
             * should not rest on. */
            written = snprintf(text + used, sizeof(text) - used, "%s = %.17g\n", NOMINAL[i].name,
                               NOMINAL[i].value);
        }
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < sizeof(text));
    }

    memset(&fault, 0, sizeof(fault));
    return plant_parameters_load(text, used, &loaded, &fault);
}

/*
 * The widest interval the structure accepts for one coefficient, found by
 * bisecting between a value it takes and one it refuses.
 */
static void discover_bounds(size_t index, double *low, double *high)
{
    const double anchor = NOMINAL[index].value;
    TEST_ASSERT_TRUE(accepts(index, anchor));

    double inside = anchor;
    double outside = CERTAINLY_REFUSED;
    TEST_ASSERT_FALSE(accepts(index, outside));
    for (int i = 0; i < BISECTION_STEPS; i++) {
        const double middle = inside + (outside - inside) / 2.0;
        if (accepts(index, middle)) {
            inside = middle;
        } else {
            outside = middle;
        }
    }
    *high = inside;

    inside = anchor;
    outside = -CERTAINLY_REFUSED;
    TEST_ASSERT_FALSE(accepts(index, outside));
    for (int i = 0; i < BISECTION_STEPS; i++) {
        const double middle = inside + (outside - inside) / 2.0;
        if (accepts(index, middle)) {
            inside = middle;
        } else {
            outside = middle;
        }
    }
    /*
     * A description naming a value too small for this type to hold is refused,
     * so bisecting downwards stops at the smallest value that survives being
     * read rather than at the bound itself. Where the bound is zero, zero is
     * still accepted -- it is asking for nothing, not asking for something
     * unrepresentable -- and it lies below everything bisection can reach. The
     * accepted set is therefore not one interval, and the bound is zero.
     */
    if (accepts(index, 0.0) && 0.0 < inside) {
        inside = 0.0;
    }
    *low = inside;
}

/* A description drawing every coefficient uniformly from its declared range. */
static size_t describe_sampled(const double *low, const double *high, char *out, size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const double value = low[i] + rng_unit() * (high[i] - low[i]);
        const int written =
            snprintf(out + used, capacity - used, "%s = %.17g\n", NOMINAL[i].name, value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

/*
 * The description for one deliberate corner of the declared space: `pick`
 * chooses each coefficient's low or high bound. Uniform sampling reaches these
 * with vanishing probability -- the two that break a naive integrator have
 * likelihoods around a thousandth per case -- and they are exactly where a
 * range's promise is cheapest to break.
 */
static size_t describe_corner(const double *low, const double *high, bool take_high, char *out,
                              size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const double value = take_high ? high[i] : low[i];
        const int written =
            snprintf(out + used, capacity - used, "%s = %.17g\n", NOMINAL[i].name, value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

/*
 * Every coefficient at one bound or the other, chosen independently.
 *
 * The corners that matter are not the all-low and all-high ones. A step that
 * assumes a constant rate destabilises when the mass is small *and* the loss
 * large -- a mixed corner, which both uniform sampling and the two extreme
 * corners miss, and which each-bound-alone misses too because the other
 * coefficients stay nominal and hold it stable.
 */
static size_t describe_mixed_corner(const double *low, const double *high, char *out,
                                    size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const double value = (rng_next() & 1u) != 0u ? high[i] : low[i];
        const int written =
            snprintf(out + used, capacity - used, "%s = %.17g\n", NOMINAL[i].name, value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

/* One coefficient at a bound, the rest nominal -- so a single extreme is not
 * masked by the others also being extreme. */
static size_t describe_at_bound(const double *bounds, size_t index, char *out, size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const double value = (i == index) ? bounds[i] : NOMINAL[i].value;
        const int written =
            snprintf(out + used, capacity - used, "%s = %.17g\n", NOMINAL[i].name, value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

/* A description of exactly these coefficient values, in table order. */
static size_t describe_values(const double *values, char *out, size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written =
            snprintf(out + used, capacity - used, "%s = %.17g\n", NOMINAL[i].name, values[i]);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

static void all_bounds(double *low, double *high)
{
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        discover_bounds(i, &low[i], &high[i]);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C4: the range a structure declares
 * for a coefficient is the range it enforces -- a value inside is accepted and
 * one just beyond is refused, at both ends of every coefficient. */
static void test_every_declared_bound_is_enforced_at_its_edge(void)
{
    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];

    all_bounds(low, high);

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        char message[200];

        (void)snprintf(message, sizeof(message), "%s: bounds [%.17g, %.17g]", NOMINAL[i].name,
                       low[i], high[i]);
        TEST_ASSERT_TRUE_MESSAGE(accepts(i, low[i]), message);
        TEST_ASSERT_TRUE_MESSAGE(accepts(i, high[i]), message);
        /* One representable step out, which is what "immediately beyond" means
         * for a value the comparison is made on. A relative epsilon would be
         * many steps wide at the larger bounds and would leave the edge itself
         * untested. */
        TEST_ASSERT_FALSE_MESSAGE(accepts(i, nextafterf((float)low[i], -INFINITY)), message);
        TEST_ASSERT_FALSE_MESSAGE(accepts(i, nextafterf((float)high[i], INFINITY)), message);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: a step taken with no actuation
 * and no external influence leaves every quantity unchanged, for any set of
 * coefficients the structure calls admissible rather than only the nominal one.
 * An initial state that is not an equilibrium of the structure's own equations
 * shows up here and nowhere else. */
static void test_rest_stays_at_rest_across_the_declared_range(void)
{
    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];

    all_bounds(low, high);
    rng_seed(PROPERTY_SEED);

    for (int c = 0; c < PROPERTY_CASES; c++) {
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        plant_model_t model;
        float before[PLANT_QUANTITY_COUNT];
        float after[PLANT_QUANTITY_COUNT];
        const size_t used = describe_sampled(low, high, text, sizeof(text));

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));
        read_all(&model, before);
        TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, 0.0f, STEP_MS));
        read_all(&model, after);

        if (memcmp(before, after, sizeof(before)) != 0) {
            char message[160];
            (void)snprintf(message, sizeof(message),
                           "case %d: a step at rest moved the model; description was:\n%s", c,
                           text);
            TEST_FAIL_MESSAGE(message);
        }
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: the same inputs reproduce the
 * same trajectory exactly, for any admissible set of coefficients. */
static void test_determinism_across_the_declared_range(void)
{
    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];

    all_bounds(low, high);
    rng_seed(PROPERTY_SEED);

    for (int c = 0; c < PROPERTY_CASES; c++) {
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        plant_model_t first;
        plant_model_t second;
        float one[PLANT_QUANTITY_COUNT];
        float two[PLANT_QUANTITY_COUNT];
        const size_t used = describe_sampled(low, high, text, sizeof(text));

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_TRUE(plant_model_init(&first, &loaded));
        TEST_ASSERT_TRUE(plant_model_init(&second, &loaded));
        run(&first, &WORKING, SHORT_STEPS, one);
        run(&second, &WORKING, SHORT_STEPS, two);
        TEST_ASSERT_EQUAL_MEMORY(one, two, sizeof(one));

        /*
         * Two identical computations agree even when both diverge, because a
         * not-a-number has the same bits either time. Without this the
         * comparison above would be satisfied by a model that had stopped
         * describing anything.
         */
        for (int q = 0; q < PLANT_QUANTITY_COUNT; q++) {
            if (!isfinite(one[q])) {
                char message[220];
                (void)snprintf(message, sizeof(message),
                               "case %d: quantity %d left the finite range; description was:\n%s",
                               c, q, text);
                TEST_FAIL_MESSAGE(message);
            }
        }
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: the model stays finite at the
 * corners of the space it declares admissible, and at each bound taken alone.
 * A step taken as though the rate held constant across it does not merely lose
 * accuracy when the step is long against the time constant -- it alternates
 * sign and grows without bound -- and the coefficients that provoke it are
 * reached by uniform sampling about once in a thousand cases. */
static void test_the_corners_of_the_declared_range_stay_finite(void)
{
    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];

    all_bounds(low, high);

    rng_seed(PROPERTY_SEED);

    for (int corner = 0; corner < 2 + 2 * (int)COEFFICIENT_COUNT + MIXED_CORNERS; corner++) {
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        plant_model_t model;
        float quantities[PLANT_QUANTITY_COUNT];
        size_t used;

        if (corner == 0) {
            used = describe_corner(low, high, false, text, sizeof(text));
        } else if (corner == 1) {
            used = describe_corner(low, high, true, text, sizeof(text));
        } else if (corner < 2 + 2 * (int)COEFFICIENT_COUNT) {
            const size_t index = (size_t)(corner - 2) / 2u;
            used = describe_at_bound(((corner - 2) % 2 == 0) ? low : high, index, text,
                                     sizeof(text));
        } else {
            used = describe_mixed_corner(low, high, text, sizeof(text));
        }

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));
        run(&model, &WORKING, TRAJECTORY_STEPS, quantities);

        for (int q = 0; q < PLANT_QUANTITY_COUNT; q++) {
            if (!isfinite(quantities[q])) {
                char message[220];
                (void)snprintf(message, sizeof(message),
                               "corner %d: quantity %d left the finite range; description was:\n%s",
                               corner, q, text);
                TEST_FAIL_MESSAGE(message);
            }
        }
    }
}

/* Indices into the coefficient table, for the closed-form comparison below. */
#define I_AMBIENT 0u
#define I_BREW_MASS 1u
#define I_BREW_POWER 2u
#define I_BREW_LOSS 3u
#define I_BREW_HELD_VOLUME 4u
#define I_BREW_CONDUCTION_TAU 5u
#define I_STEAM_MASS 6u
#define I_STEAM_LOSS 8u
#define I_PUMP_FLOW 10u
#define I_WATER_FEED 12u
#define I_WATER_HEAT_CAPACITY 13u
#define I_WATER_LATENT_HEAT 14u
#define I_STEAM_SATURATION 15u
#define I_STEAM_BAR_PER_K 16u
#define I_STEAM_PRESSURE_FALL 17u
#define I_STEAM_FEED_FLOW 18u

/* Long enough that a per-step error becomes visible in the distance travelled. */
#define ACCUMULATION_STEPS 200

/* Comfortably above what single precision accumulates over that many steps, and
 * far below the error a mis-conditioned settled fraction introduces. */
#define ACCUMULATED_TOLERANCE 1.0e-3

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: a step lands where the closed
 * form of the structure's own equation says it should, across the range the
 * structure declares admissible and across step lengths spanning four orders of
 * magnitude.
 *
 * Rest, monotonicity and determinism are all satisfied by a step that is merely
 * in the right direction, so a step can be badly wrong and pass every other
 * property here. That is not hypothetical: computing the settled fraction as
 * one minus the exponential rather than through expm1 throws away the leading
 * digits for a short step, and is wrong in the third significant figure at a
 * step a thousandth of the time constant -- worse than the constant-rate
 * assumption it replaced, and invisible to every other test in this file.
 *
 * The comparison is over a run of steps rather than one, and against how far
 * the quantity moved rather than where it ended up. A per-step error of a few
 * percent on an increment that is itself small disappears entirely against the
 * absolute temperature; it only becomes visible once it has accumulated, which
 * is exactly how it would reach a machine. */
static void test_a_step_matches_the_closed_form_across_the_declared_range(void)
{
    /*
     * A millisecond step is deliberately absent. At that rate the temperature
     * increment is a few tens of the smallest change this type can represent at
     * the values a hot machine reaches, so each addition discards a percent or
     * so of it, and the comparison would be measuring the arithmetic's
     * resolution rather than the equation's accuracy. That resolution is a real
     * constraint on how fast the model can usefully be stepped; it is not what
     * this test is about.
     */
    static const uint32_t intervals_ms[] = {10u, 100u, 1000u};
    const plant_actuation_t brew_only = {{ACTUATION_FULL_SCALE, 0u, 0u}};

    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];
    double values[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];

    int compared = 0;

    all_bounds(low, high);
    rng_seed(PROPERTY_SEED);

    for (int c = 0; c < PROPERTY_CASES; c++) {
        for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
            values[i] = low[i] + rng_unit() * (high[i] - low[i]);
        }
        const size_t used = describe_values(values, text, sizeof(text));

        for (size_t k = 0u; k < sizeof(intervals_ms) / sizeof(intervals_ms[0]); k++) {
            plant_parameters_t loaded;
            plant_parameter_error_t fault;
            plant_model_t model;
            float before[PLANT_QUANTITY_COUNT];
            float after[PLANT_QUANTITY_COUNT];

            memset(&fault, 0, sizeof(fault));
            TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
            TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

            /* Off the equilibrium first: at rest the closed form is trivially
             * matched by any step, so it would establish nothing. */
            for (int warm = 0; warm < 5; warm++) {
                TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 0.0f, 100u));
            }
            read_all(&model, before);
            for (int n = 0; n < ACCUMULATION_STEPS; n++) {
                TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 0.0f, intervals_ms[k]));
            }
            read_all(&model, after);

            const double seconds =
                ((double)intervals_ms[k] * (double)ACCUMULATION_STEPS) / 1000.0;
            const double ambient = values[I_AMBIENT];
            const double mass = values[I_BREW_MASS];
            const double power = values[I_BREW_POWER];
            const double loss = values[I_BREW_LOSS];
            const double from = (double)before[PLANT_QUANTITY_BREW_TEMPERATURE_C];

            double expected;
            if (loss > 0.0) {
                const double settling = ambient + power / loss;
                expected = settling + (from - settling) * exp(-(loss * seconds) / mass);
            } else {
                expected = from + (power * seconds) / mass;
            }

            const double got = (double)after[PLANT_QUANTITY_BREW_TEMPERATURE_C];
            /* Against the distance travelled, not the absolute value: the
             * latter is dominated by where the run started and would hide the
             * error entirely. */
            const double moved = fabs(expected - from);

            /*
             * Some admissible coefficients move the temperature so little per
             * step that the increment is a few of the smallest changes this
             * type can represent at that value. Each addition then discards a
             * noticeable share of it, and what accumulates is the arithmetic's
             * resolution rather than the equation's error -- comparing it would
             * report the former as though it were the latter. The test is on
             * the increment rather than the total for exactly that reason: a
             * long run of unrepresentably small steps still travels a
             * measurable distance while being mostly rounding. Those cases are
             * skipped, and the count of the ones that were not is asserted
             * below so that skipping cannot quietly become the whole test.
             */
            const float magnitude = fabsf(after[PLANT_QUANTITY_BREW_TEMPERATURE_C]) + 1.0f;
            const double resolution = (double)(nextafterf(magnitude, INFINITY) - magnitude);
            if ((moved / (double)ACCUMULATION_STEPS) < 1000.0 * resolution) {
                continue;
            }
            compared++;

            const double error = fabs(got - expected) / moved;

            if (!(error < ACCUMULATED_TOLERANCE)) {
                char message[240];
                (void)snprintf(message, sizeof(message),
                               "case %d at %ums x%d: moved %.9g, closed form moved %.9g, "
                               "relative error %.3g",
                               c, intervals_ms[k], ACCUMULATION_STEPS, got - from,
                               expected - from, error);
                TEST_FAIL_MESSAGE(message);
            }
        }
    }

    /* Enough of the sampled space was actually measurable to mean something. */
    TEST_ASSERT_TRUE_MESSAGE(compared > PROPERTY_CASES / 4,
                             "too few sampled cases moved far enough per step to compare");
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: the step stays accurate where
 * the settled fraction is worst conditioned -- a step far shorter than the time
 * constant, which is the ordinary case for a thermal mass under a control loop.
 *
 * Fixed coefficients rather than sampled ones, because the region that exposes
 * this is a small corner of the declared space and leaving it to chance would
 * mean a test that finds the defect in some runs and not others. */
static void test_a_short_step_against_a_long_time_constant_stays_accurate(void)
{
    const plant_actuation_t brew_only = {{ACTUATION_FULL_SCALE, 0u, 0u}};
    double values[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        values[i] = NOMINAL[i].value;
    }
    /* A large mass with a small loss: the step is then ten-thousandths of a
     * time constant, where one minus the exponential has thrown away most of
     * its significant digits. */
    values[I_BREW_MASS] = 5000.0;
    values[I_BREW_LOSS] = 5.0;
    values[I_BREW_POWER] = 2000.0;

    const size_t used = describe_values(values, text, sizeof(text));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];

    read_all(&model, before);
    for (int n = 0; n < ACCUMULATION_STEPS; n++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 0.0f, 10u));
    }
    read_all(&model, after);

    const double from = (double)before[PLANT_QUANTITY_BREW_TEMPERATURE_C];
    const double seconds = (10.0 * (double)ACCUMULATION_STEPS) / 1000.0;
    const double settling = values[I_AMBIENT] + values[I_BREW_POWER] / values[I_BREW_LOSS];
    const double expected =
        settling + (from - settling) * exp(-(values[I_BREW_LOSS] * seconds) / values[I_BREW_MASS]);
    const double got = (double)after[PLANT_QUANTITY_BREW_TEMPERATURE_C];
    const double error = fabs(got - expected) / fabs(expected - from);

    if (!(error < 1.0e-4)) {
        char message[220];
        (void)snprintf(message, sizeof(message),
                       "moved %.9g, closed form moved %.9g, relative error %.3g", got - from,
                       expected - from, error);
        TEST_FAIL_MESSAGE(message);
    }
}

/* SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C2: rest stays at rest at the
 * corners too, where an initial state that is not an equilibrium is most
 * likely to show. */
static void test_the_corners_of_the_declared_range_stay_at_rest(void)
{
    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];

    all_bounds(low, high);

    for (int corner = 0; corner < 2; corner++) {
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        plant_model_t model;
        float before[PLANT_QUANTITY_COUNT];
        float after[PLANT_QUANTITY_COUNT];
        const size_t used = describe_corner(low, high, corner == 1, text, sizeof(text));

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));
        read_all(&model, before);
        TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, 0.0f, STEP_MS));
        read_all(&model, after);
        TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
    }
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C1: The machine's actuation channels
/// are one enumerated set both seams speak.
static void test_the_actuation_channels_are_one_enumerated_set(void)
{
    /*
     * The channels are addressable by value with a terminating count, which is
     * what lets a structure state which it answers and a refusal name one. A
     * set of separately named fields could carry the same three levels and none
     * of those sentences.
     */
    TEST_ASSERT_TRUE((unsigned)ACTUATION_CHANNEL_COUNT > 0u);
    TEST_ASSERT_EQUAL(0, (int)ACTUATION_CHANNEL_BREW_HEATER);

    plant_actuation_t actuation = {{0u}};
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        actuation.level_permille[channel] = (uint16_t)(channel + 1u);
    }
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        TEST_ASSERT_EQUAL_UINT16((uint16_t)(channel + 1u), actuation.level_permille[channel]);
    }

    /*
     * One scale for the whole vocabulary. A per-seam copy is what this replaces,
     * and the level that is one beyond it is the level the seam refuses -- so a
     * second scale drifting from this one would move where the refusal falls.
     */
    plant_actuation_t at_scale = {{0u}};
    plant_actuation_t beyond_scale = {{0u}};
    plant_model_t model;

    at_scale.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = ACTUATION_FULL_SCALE;
    beyond_scale.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = ACTUATION_FULL_SCALE + 1u;
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(plant_model_step(&model, &at_scale, 0.0f, STEP_MS));
    TEST_ASSERT_FALSE(plant_model_step(&model, &beyond_scale, 0.0f, STEP_MS));
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C2: The plant-model seam carries each
/// structure's statement of the channels it answers.
/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C3: Every structure behind the seam
/// declares which actuation channels it answers.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C3: A dedicated actuation channel commands
/// thermoblock's steam-side feed pump. This loop is written over the whole
/// vocabulary rather than over a fixed list, so the steam-side feed pump
/// channel is exercised here without the test having named it.
static void test_the_structure_states_which_channels_it_answers(void)
{
    const actuation_channel_set_t answered = plant_structure_actuation_channels();

    /* Reached through the seam, not by including a structure's own header. */
    TEST_ASSERT_NOT_EQUAL(0u, answered);

    /* Nothing outside the vocabulary is claimed. */
    for (unsigned channel = (unsigned)ACTUATION_CHANNEL_COUNT; channel < 32u; channel++) {
        TEST_ASSERT_EQUAL_UINT32(0u, answered & ACTUATION_CHANNEL_BIT(channel));
    }

    /*
     * This structure describes the reference machine, which has every channel
     * the vocabulary carries -- so every one of them is commandable here, and
     * the refusal of an unanswered channel is exercised where it can fail, in
     * the suite driving a structure that declares fewer.
     */
    plant_model_t model;
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        plant_step_error_t refusal;
        plant_actuation_t one_channel = {{0u}};

        TEST_ASSERT_NOT_EQUAL(0u, answered & ACTUATION_CHANNEL_BIT(channel));
        one_channel.level_permille[channel] = ACTUATION_FULL_SCALE;
        TEST_ASSERT_TRUE(plant_model_step_reporting(&model, &one_channel, 0.0f, STEP_MS, &refusal));
        TEST_ASSERT_EQUAL(PLANT_STEP_OK, refusal.fault);
    }
}

/// SOL-PLANT-STEAM-DRAW-CHANNELS.C1: Every plant structure's step accepts a
/// steam-demand rate the control law never sets.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C5: The new interfaces are exercised end to
/// end on the host verification tier.
static void test_a_steam_demand_and_a_steam_feed_command_are_both_accepted(void)
{
    plant_model_t model;
    plant_step_error_t refusal;
    plant_actuation_t feeding = {{0u}};

    /*
     * A non-zero level on the new channel, commanded alongside a non-zero
     * demand. Neither has a relation reading it yet -- that is
     * SOL-PLANT-STEAM-DRAW-ENERGY's and SOL-PLANT-STEAM-DRAW-REPORTED's work --
     * so what this test can show is that both reach as far as the structure's
     * own step: the call is accepted rather than refused at the boundary, which
     * is the only outcome the seam's admissibility check ties either value to
     * this early. A demand on a channel the actuation record has no member for
     * cannot be refused there, so acceptance here is that value reaching the
     * structure's internal state; the feed channel reaching it is what the
     * admissibility check passing on a level thermoblock now declares in
     * PLANT_STRUCTURE_ACTUATION_CHANNELS demonstrates.
     */
    feeding.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = ACTUATION_FULL_SCALE / 2u;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(
        plant_model_step_reporting(&model, &feeding, 250.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_OK, refusal.fault);
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C7: The structures and the control
/// logic behave identically after the vocabulary is unified.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C2: The demand input defaults to zero and
/// changes no existing behaviour when unset.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C4: Every existing actuation channel behaves
/// unchanged on every structure.
static void test_the_trajectory_is_what_it_was_before_the_vocabulary_was_unified(void)
{
    /*
     * Recorded from the build as it stood before the actuation vocabulary was
     * unified, and carried here as values rather than regenerated: regenerating
     * them from this build would compare the change with itself and pass
     * whatever it did to the equations. Written as hexadecimal literals because
     * they are exact -- nothing here touches an equation, so a difference of one
     * bit is a difference this test exists to report.
     *
     * Kept rather than retaken when the coffee side gained the water on its way
     * to the group. That state is downstream of everything these columns record
     * and enters none of it, so every figure below is produced by arithmetic the
     * change did not touch -- which is what makes keeping the recording a claim
     * rather than a convenience. A recording retaken from the build that moved
     * the equations would have compared the change with itself.
     *
     * Kept again, on the same reasoning, when the seam gained the rate water is
     * drawn. The four recorded columns were unchanged byte for byte: that rate
     * entered none of the relations that produce them, so a description carrying
     * the coefficient behind it gave the same trajectory as one without it. The
     * fifth column is not a recording and was not read off a run. It is
     * arithmetic a reader can do: the coefficient below is 8 mL/s, the pump is
     * commanded at half scale under WORKING and at nothing under the other two,
     * so the rate is exactly 4 and exactly 0, and both are exact in binary. A
     * figure that had to be read off a run would have been the change checking
     * itself.
     *
     * Retaken -- for the first time -- when the water drawn through the casting
     * started taking energy out of it. That reasoning has run out, and saying so
     * is the point of this paragraph: the whole of the previous two changes'
     * claim was that flow entered none of these relations, and it now enters two
     * of them. Keeping the recording would have been asserting the change did
     * nothing, which is the opposite of what it is for.
     *
     * Kept again when the step gained the steam-demand argument and thermoblock
     * gained the steam-side feed channel. Every row below is driven with the
     * demand at zero -- the fixtures below command no other channel -- and the
     * new channel was at that time not among AT_REST, HEATING or WORKING's
     * commanded levels either, so on the same reasoning as the rate drawn before
     * it, neither entered any relation these figures come from. Both were wired
     * only as far as being accepted; nothing read either.
     *
     * Kept a further time when a relation began reading that channel and WORKING
     * gained a commanded level on it, which is the one retention here that is not
     * about a term being absent. The channel is now read, and the reason these
     * figures are unchanged is arithmetic rather than architectural: what the
     * feed sets a bound on is the rate steam is drawn at, the bound is the lower
     * of that rate and the demand, and every row below is driven at a demand of
     * exactly zero. The lower of zero and anything is zero, so the two relations
     * the feed reaches are entered with the same rate they were entered with
     * before the channel was wired -- and the coffee side, which is what most of
     * these columns are, never reaches that channel at all.
     *
     * And kept a third time -- unchanged byte for byte, and this is the strongest
     * claim the recording has made yet -- when the steam side gained a term for
     * what a draw costs it and the steam path's pressure gained a state of its
     * own. The demand is still zero on every row, and at zero demand both of
     * those are required to be exactly the equations that were here before: the
     * latent term is a coefficient multiplied by an exact zero, and the pressure
     * is the saturation relation less a gap that a step with nothing drawn sets
     * to nothing rather than decays. If either reduced only nearly, or if the
     * gap survived a step at no demand, the steam column of the last three rows
     * would move -- so this recording is now also where the reversion the whole
     * pressure change turns on would be caught having failed. The two
     * coefficients those relations read are in the description below at values
     * that would be visible if anything read them, which is what makes the rows
     * being unchanged mean something.
     *
     * What the retaken figures have to be read against, row by row, because the
     * rows are not all in the same position:
     *
     * The two AT_REST rows are unchanged byte for byte, and that is still a
     * claim rather than a convenience. Nothing is drawn at rest, so the new
     * terms are multiplied by an exact zero and the pair sits at an equilibrium
     * of its own equations. A machine standing still that has started to move is
     * the failure a flow term is most likely to introduce, and it would show
     * here first.
     *
     * The HEATING row's steam column is unchanged byte for byte -- the steam
     * mass gained no term and shares no arithmetic with the coffee side, so any
     * movement there would be the change reaching across. Its brew column moved
     * in its last few bits: from 0x1.c8693p+4 to 0x1.c8692p+4, about half a part
     * in a million. Nothing is drawn under HEATING either, so the equations
     * being evaluated are the ones this row was recorded under -- what changed
     * is the arithmetic that evaluates them. The casting and the water are now
     * advanced as one coupled pair, and with nothing drawn that pair separates
     * back into the two independent relations exactly, on paper. It does not
     * separate back into the same rounding: the coupled form reaches the same
     * closed form through a different sequence of single-precision operations,
     * and a handful of units in the last place is what that costs. That was
     * worth chasing down rather than accepting, because a much larger movement
     * here would have meant the zero-draw case was not reducing at all. The
     * reduction itself is asserted properly, against arithmetic rather than
     * against a recording, in the test that compares a closed pump against the
     * uncoupled closed forms -- this row is only where it would be noticed.
     *
     * The two WORKING rows moved substantially, and are meant to. The pump is at
     * half scale there, 4 mL/s of water is being drawn through a casting held at
     * 1200 W, and where that used to climb to about 297 degrees it now heads for
     * somewhere in the eighties instead -- which is the droop the description
     * said it was understating and the reason for the whole change. The figure it
     * heads for is one a reader can work out with the coefficients below and no
     * run: at rest the water leaving is at the casting's own temperature, so the
     * balance is 1200 = 1.5·(T − 20) + 4·4.15·(T − 18), which settles at 84.46.
     * The last row is not that figure and is not meant to be read as it. It is
     * 116 s of WORKING actuation in, which is a little over five multiples of
     * this pair's slow time constant of roughly 22 s, so it is still short of
     * where it is going -- about a third of a kelvin short, at 84.19. Close
     * enough that the hand-computed balance says what the row is for, and not so
     * close that the two are the same number.
     */
    static const float EXPECTED[][PLANT_QUANTITY_COUNT] = {
        {0x1.4p+4f, 0x1.4p+4f, 0x0p+0f, 0x0p+0f, 0x0p+0f},
        {0x1.4p+4f, 0x1.4p+4f, 0x0p+0f, 0x0p+0f, 0x0p+0f},
        {0x1.c8692p+4f, 0x1.8a64c2p+4f, 0x0p+0f, 0x0p+0f, 0x0p+0f},
        {0x1.5108f2p+5f, 0x1.0ec6eap+5f, 0x1.1fd73ap+2f, 0x0p+0f, 0x1p+2f},
        {0x1.50bfb6p+6f, 0x1.693cd6p+7f, 0x1.1ffff8p+2f, 0x1.692c1cp+1f, 0x1p+2f},
    };
    static const int STEPS[] = {0, 10, 30, 60, 1100};
    static const plant_actuation_t *const UNDER[] = {&AT_REST, &AT_REST, &HEATING, &WORKING,
                                                     &WORKING};

    plant_model_t model;
    float values[PLANT_QUANTITY_COUNT];

    /*
     * The description is the one the recording was made under, spelled here
     * rather than taken from the table above so that changing a nominal value
     * for another test's sake cannot silently move what this one compares.
     */
    static const char DESCRIPTION[] = "ambient_temperature_c = 20\n"
                                      "brew.thermal_mass_j_per_k = 420\n"
                                      "brew.heater_power_w = 1200\n"
                                      "brew.loss_w_per_k = 1.5\n"
                                      "brew.outlet_held_volume_ml = 6\n"
                                      "brew.outlet_conduction_time_constant_s = 15\n"
                                      "steam.thermal_mass_j_per_k = 900\n"
                                      "steam.heater_power_w = 1400\n"
                                      "steam.loss_w_per_k = 2.2\n"
                                      "pump.pressure_bar = 9\n"
                                      "pump.flow_ml_per_s = 8\n"
                                      "brew.pressure_time_constant_s = 0.8\n"
                                      "water.feed_temperature_c = 18\n"
                                      "water.heat_capacity_j_per_ml_k = 4.15\n"
                                      "water.latent_heat_j_per_ml = 2000\n"
                                      "steam.saturation_temperature_c = 100\n"
                                      "steam.pressure_bar_per_k = 0.035\n"
                                      "steam.pressure_fall_bar_per_ml = 0.02\n"
                                      "steam.feed_flow_ml_per_s = 5\n";
    plant_parameters_t recorded;
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &recorded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &recorded));

    for (size_t checkpoint = 0u; checkpoint < sizeof(STEPS) / sizeof(STEPS[0]); checkpoint++) {
        for (int i = 0; i < STEPS[checkpoint]; i++) {
            TEST_ASSERT_TRUE(plant_model_step(&model, UNDER[checkpoint], 0.0f, STEP_MS));
        }
        read_all(&model, values);
        /*
         * Compared as stored rather than within a tolerance: a tolerance would
         * accept exactly the quiet drift in the equations this exists to refuse.
         */
        TEST_ASSERT_EQUAL_MEMORY(EXPECTED[checkpoint], values, sizeof(values));
    }
}

/* --- The origin recorded against a value ---------------------------------- */

/*
 * Write the nominal description with an origin against every value, so that
 * what is loaded differs from `valid_text` in nothing but the annotations.
 * `kind` and `account` are what every line carries, which is what lets one
 * malformed spelling be driven through a whole description at once.
 */
static size_t describe_with_origin(char *out, size_t capacity, const char *kind,
                                   const char *account)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written = snprintf(out + used, capacity - used, "%s = %.9g @%s%s%s\n",
                                     NOMINAL[i].name, NOMINAL[i].value, kind,
                                     (account[0] != '\0') ? " " : "", account);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

static void load_expecting_success(const char *text, size_t length, plant_parameters_t *into)
{
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    memset(into, 0, sizeof(*into));
    TEST_ASSERT_TRUE(plant_parameters_load(text, length, into, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C6: every refusal the parameter loader already makes survives the grammar extension
static void test_an_origin_against_a_value_changes_nothing_that_is_read(void)
{
    char annotated[DESCRIPTION_MAX];
    plant_parameters_t with_origins;

    const size_t used =
        describe_with_origin(annotated, sizeof(annotated), "document", "service manual p.24");
    load_expecting_success(annotated, used, &with_origins);

    /*
     * Compared against the record the same coefficients produce unannotated:
     * the account travels with the value in the file and reaches the record in
     * nothing but its own absence.
     */
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &with_origins, sizeof(parameters));
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C6: every refusal the parameter loader already makes survives the grammar extension
static void test_two_accounts_of_the_same_value_read_the_same(void)
{
    char first[DESCRIPTION_MAX];
    char second[DESCRIPTION_MAX];
    plant_parameters_t from_first;
    plant_parameters_t from_second;

    load_expecting_success(first, describe_with_origin(first, sizeof(first), "document", "p.24"),
                           &from_first);
    load_expecting_success(
        second,
        describe_with_origin(second, sizeof(second), "estimated", "a comparable machine, at rest"),
        &from_second);

    TEST_ASSERT_EQUAL_MEMORY(&from_first, &from_second, sizeof(from_first));
}

/*
 * One malformed annotation, driven through a description that is otherwise the
 * valid one. Each case asserts the fault, the coefficient named, and that the
 * caller's record is untouched -- the last because an annotation fault arriving
 * after the value has been read is exactly where a half-filled record could
 * escape.
 */
static void expect_origin_refusal(const char *kind, const char *account)
{
    char annotated[DESCRIPTION_MAX];
    plant_parameters_t untouched;
    plant_parameters_t before;
    plant_parameter_error_t fault;

    const size_t used = describe_with_origin(annotated, sizeof(annotated), kind, account);
    memset(&untouched, 0xA5, sizeof(untouched));
    before = untouched;
    memset(&fault, 0, sizeof(fault));

    TEST_ASSERT_FALSE(plant_parameters_load(annotated, used, &untouched, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_ORIGIN, fault.fault);
    /* The first coefficient is where the description first goes wrong. */
    TEST_ASSERT_EQUAL_STRING(NOMINAL[0].name, fault.parameter);
    TEST_ASSERT_EQUAL_UINT32(1u, fault.line);
    TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C3: an estimated value in the reference description is distinguishable from a measured one
static void test_an_origin_of_an_undeclared_kind_is_refused(void)
{
    /*
     * The kind is the whole of the estimated-versus-measured distinction, so a
     * word nobody declared is refused rather than carried. `measured_ish` is
     * the dangerous shape: it reads as a measurement to someone skimming and is
     * one to nothing.
     */
    expect_origin_refusal("guessed", "a comparable machine");
    expect_origin_refusal("measured_ish", "the bench, roughly");
    expect_origin_refusal("Document", "p.24");
    expect_origin_refusal("documented", "p.24");
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C6: every refusal the parameter loader already makes survives the grammar extension
static void test_an_origin_with_no_kind_or_no_account_is_refused(void)
{
    /* A marker and nothing after it. */
    expect_origin_refusal("", "");
    /* A kind with nothing behind it is a label, not an account. */
    expect_origin_refusal("document", "");
    expect_origin_refusal("estimated", "");
    expect_origin_refusal("measured", "");
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C6: every refusal the parameter loader already makes survives the grammar extension
static void test_a_statement_the_description_cannot_make_is_refused(void)
{
    static const char *const CASES[] = {
        "@describes-a-machine\n",
        "@describes-no-machine-really\n",
        "@\n",
        "@ exempt\n",
    };
    char text[DESCRIPTION_MAX];

    for (size_t i = 0u; i < sizeof(CASES) / sizeof(CASES[0]); i++) {
        plant_parameters_t untouched;
        plant_parameters_t before;
        plant_parameter_error_t fault;
        const int written = snprintf(text, sizeof(text), "%s", CASES[i]);
        TEST_ASSERT_TRUE(written > 0);
        const size_t used =
            (size_t)written +
            describe(text + written, sizeof(text) - (size_t)written, SCALE_NOTHING, 1.0);

        memset(&untouched, 0xA5, sizeof(untouched));
        before = untouched;
        memset(&fault, 0, sizeof(fault));

        TEST_ASSERT_FALSE(plant_parameters_load(text, used, &untouched, &fault));
        TEST_ASSERT_EQUAL(PLANT_PARAMETER_ORIGIN, fault.fault);
        TEST_ASSERT_EQUAL_UINT32(1u, fault.line);
        TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));

        /*
         * And what it reports the refusal against is the offending line itself,
         * to its own length. Asserting only the fault leaves the reported text
         * free to be the line plus whatever follows it in the description, which
         * is what a wrong length here produces -- a refusal naming the right
         * line and quoting the wrong thing, which is worse than quoting nothing.
         */
        char expected[PLANT_PARAMETER_NAME_MAX];
        const size_t line_length = strlen(CASES[i]) - 1u; /* Without the newline. */
        TEST_ASSERT_TRUE(line_length < sizeof(expected));
        memcpy(expected, CASES[i], line_length);
        expected[line_length] = '\0';
        TEST_ASSERT_EQUAL_STRING(expected, fault.parameter);
    }
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: the origin parser reads the span it was
/// given and not a string, so a final annotated line with no newline after it is
/// read on the same terms as any other.
static void test_a_final_annotated_line_without_a_newline_is_read(void)
{
    /*
     * The span discipline the loader was given a test for is exercised here
     * through the annotation grammar, which arrived later and reaches further
     * into the line than anything that test covers -- the kind is scanned to the
     * end of the span, so a scan that steps one past it is looking at whatever
     * follows.
     *
     * The byte after the span is set to something that is neither a newline nor a
     * blank, for the reason the unannotated case gives: a parser reading one
     * character too far is invisible against a buffer that happens to hold what
     * it was looking for.
     */
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    size_t used =
        describe_with_origin(text, sizeof(text), "estimated", "a comparable machine");

    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_EQUAL_CHAR('\n', text[used - 1u]);
    used--;
    text[used] = '#';

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &loaded, sizeof(parameters));
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: a test earns its place by being capable of
/// failing on a plausible defect -- an annotation whose kind is separated from the
/// marker by whitespace is read, so removing the skip that allows it is a change
/// some test objects to.
static void test_an_origin_separated_from_its_marker_by_blanks_is_read(void)
{
    /*
     * Every description this project ships writes the marker hard against the
     * kind, so nothing exercised the loader's skipping of what lies between them
     * until this. The grammar admits it, an author will eventually write it, and
     * a loader that refused it would refuse an honest description for a reason
     * nothing states.
     */
    static const char *const SEPARATORS[] = {" ", "  ", "\t", " \t "};

    for (size_t i = 0u; i < sizeof(SEPARATORS) / sizeof(SEPARATORS[0]); i++) {
        char kind[16];
        char annotated[DESCRIPTION_MAX];
        plant_parameters_t loaded;

        const int written = snprintf(kind, sizeof(kind), "%sestimated", SEPARATORS[i]);
        TEST_ASSERT_TRUE(written > 0);

        const size_t used = describe_with_origin(annotated, sizeof(annotated), kind,
                                                 "a comparable machine, at rest");
        load_expecting_success(annotated, used, &loaded);
        /* Read the same as the unannotated description: the separator is not content. */
        TEST_ASSERT_EQUAL_MEMORY(&parameters, &loaded, sizeof(parameters));
    }
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C2: every value in the reference description carries the origin of that value
static void test_a_description_claiming_no_machine_is_read_like_any_other(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t exempt;

    const int written = snprintf(text, sizeof(text), "@describes-no-machine\n");
    TEST_ASSERT_TRUE(written > 0);
    const size_t used =
        (size_t)written +
        describe(text + written, sizeof(text) - (size_t)written, SCALE_NOTHING, 1.0);

    /*
     * The statement exempts a description from accounting for its values; it
     * does not change what the loader reads out of one. Which descriptions are
     * entitled to carry it is settled where they live, not here.
     */
    load_expecting_success(text, used, &exempt);
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &exempt, sizeof(parameters));
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C6: every refusal the parameter loader already makes survives the grammar extension
static void test_every_refusal_still_fires_on_a_line_carrying_an_origin(void)
{
    /*
     * The worst outcome available to this slice is a grammar extension that
     * quietly relaxed a refusal, because nothing else it asserts would notice.
     * So each refusal the loader made before is driven again with a
     * well-formed origin on the offending line: the annotation must not become
     * a way past the check that would otherwise have caught the value.
     */
    static const struct {
        const char *line;
        plant_parameter_fault_t fault;
        const char *parameter;
        /*
         * The coefficient the offending line supplies, left out of the
         * description before it so that the fault under test is the one that
         * fires. Null where the line names none, and for the duplicate case,
         * which needs the coefficient present to be a duplicate of.
         */
        const char *displaces;
    } CASES[] = {
        /* A name this structure does not have. */
        {"not.a.coefficient = 1.0 @document p.24\n", PLANT_PARAMETER_UNKNOWN, "not.a.coefficient",
         NULL},
        /* A value outside the range the structure declares. */
        {"brew.thermal_mass_j_per_k = -5.0 @document p.24\n", PLANT_PARAMETER_OUT_OF_RANGE,
         "brew.thermal_mass_j_per_k", "brew.thermal_mass_j_per_k"},
        /* A value that is not a number at all. */
        {"brew.heater_power_w = twelve @document p.24\n", PLANT_PARAMETER_MALFORMED,
         "brew.heater_power_w", "brew.heater_power_w"},
        /* A token with a second number behind it, before the annotation. */
        {"brew.heater_power_w = 1.0 2.0 @document p.24\n", PLANT_PARAMETER_MALFORMED,
         "brew.heater_power_w", "brew.heater_power_w"},
        /* A not-a-number, which every comparison against a bound accepts. */
        {"brew.loss_w_per_k = nan @estimated a comparable machine\n", PLANT_PARAMETER_OUT_OF_RANGE,
         "brew.loss_w_per_k", "brew.loss_w_per_k"},
        /* A coefficient given twice, annotated the second time. */
        {"ambient_temperature_c = 21.0 @document p.24\n", PLANT_PARAMETER_DUPLICATE,
         "ambient_temperature_c", NULL},
        /* A line with no separator at all, carrying what looks like an origin. */
        {"brew.heater_power_w 1200 @document p.24\n", PLANT_PARAMETER_MALFORMED,
         "brew.heater_power_w 1200 @document p.24", NULL},
        /* An empty name, which the marker does not excuse. */
        {" = 1200 @document p.24\n", PLANT_PARAMETER_MALFORMED, "= 1200 @document p.24", NULL},
        /*
         * An empty value with a well-formed origin. The likeliest place for the
         * extension to swallow one: the annotation is the only thing on the
         * line after the separator, and an account is not a value.
         */
        {"brew.heater_power_w = @document p.24\n", PLANT_PARAMETER_MALFORMED,
         "brew.heater_power_w", "brew.heater_power_w"},
    };

    for (size_t i = 0u; i < sizeof(CASES) / sizeof(CASES[0]); i++) {
        char text[DESCRIPTION_MAX];
        plant_parameters_t untouched;
        plant_parameters_t before;
        plant_parameter_error_t fault;
        size_t used = 0u;

        /*
         * The offending line follows an otherwise valid description, so nothing
         * before it is what the refusal is about. Every line of that prefix
         * carries an origin too: the refusal has to survive a description that
         * is annotated throughout, not only one where the offending line is the
         * single annotated one.
         */
        for (size_t c = 0u; c < COEFFICIENT_COUNT; c++) {
            if (CASES[i].displaces != NULL &&
                strcmp(NOMINAL[c].name, CASES[i].displaces) == 0) {
                continue;
            }
            const int line = snprintf(text + used, sizeof(text) - used,
                                      "%s = %.9g @document p.24\n", NOMINAL[c].name,
                                      NOMINAL[c].value);
            TEST_ASSERT_TRUE(line > 0);
            used += (size_t)line;
        }

        const int written = snprintf(text + used, sizeof(text) - used, "%s", CASES[i].line);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;

        memset(&untouched, 0xA5, sizeof(untouched));
        before = untouched;
        memset(&fault, 0, sizeof(fault));

        TEST_ASSERT_FALSE(plant_parameters_load(text, used, &untouched, &fault));
        TEST_ASSERT_EQUAL(CASES[i].fault, fault.fault);
        TEST_ASSERT_EQUAL_STRING(CASES[i].parameter, fault.parameter);
        TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));
    }
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C6: every refusal the parameter loader already makes survives the grammar extension
static void test_an_annotated_refusal_still_reports_the_range_it_was_outside(void)
{
    /*
     * The refusals carry more than a fault code: an out-of-range value is
     * reported with what arrived and the bounds it missed, which is what makes
     * one actionable. A regression that kept the refusal and stopped populating
     * those would pass every assertion above.
     */
    char text[DESCRIPTION_MAX];
    plant_parameters_t untouched;
    plant_parameter_error_t fault;
    size_t used = 0u;

    for (size_t i = 1u; i < COEFFICIENT_COUNT; i++) {
        const int written = snprintf(text + used, sizeof(text) - used,
                                     "%s = %.9g @estimated a comparable machine\n",
                                     NOMINAL[i].name, NOMINAL[i].value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
    }
    /* Ambient is declared admissible between -40 and 60. */
    const int written = snprintf(text + used, sizeof(text) - used,
                                 "%s = 250.0 @document p.24\n", NOMINAL[0].name);
    TEST_ASSERT_TRUE(written > 0);
    used += (size_t)written;

    memset(&untouched, 0xA5, sizeof(untouched));
    memset(&fault, 0, sizeof(fault));

    TEST_ASSERT_FALSE(plant_parameters_load(text, used, &untouched, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault);
    TEST_ASSERT_EQUAL_STRING(NOMINAL[0].name, fault.parameter);
    TEST_ASSERT_EQUAL_FLOAT(250.0f, fault.value);
    TEST_ASSERT_TRUE(fault.minimum < fault.maximum);
    TEST_ASSERT_TRUE(fault.value > fault.maximum);
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C3: an estimated value in the reference description is distinguishable from a measured one
static void test_a_description_mixing_the_kinds_is_read_like_any_other(void)
{
    /*
     * The state commissioning produces, which the distinction has to survive:
     * measured values displacing estimates one at a time while the rest stand.
     * A description part-way through that is the ordinary case, not an odd one,
     * so every kind appears here at once and the record is the same one the
     * unannotated description gives.
     */
    static const char *const KINDS[] = {"document", "estimated", "measured"};
    char text[DESCRIPTION_MAX];
    plant_parameters_t mixed;
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written =
            snprintf(text + used, sizeof(text) - used, "%s = %.9g @%s what it came from\n",
                     NOMINAL[i].name, NOMINAL[i].value, KINDS[i % 3u]);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
    }

    load_expecting_success(text, used, &mixed);
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &mixed, sizeof(parameters));
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C6: every refusal the parameter loader already makes survives the grammar extension
static void test_a_coefficient_omitted_from_an_annotated_description_is_still_refused(void)
{
    /*
     * The refusal with no line to point at. An annotated description short of a
     * coefficient is as incomplete as a bare one, and the origins it does carry
     * buy it nothing.
     */
    for (size_t omitted = 0u; omitted < COEFFICIENT_COUNT; omitted++) {
        char text[DESCRIPTION_MAX];
        plant_parameters_t untouched;
        plant_parameters_t before;
        plant_parameter_error_t fault;
        size_t used = 0u;

        for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
            if (i == omitted) {
                continue;
            }
            const int written =
                snprintf(text + used, sizeof(text) - used, "%s = %.9g @document p.24\n",
                         NOMINAL[i].name, NOMINAL[i].value);
            TEST_ASSERT_TRUE(written > 0);
            used += (size_t)written;
        }

        memset(&untouched, 0xA5, sizeof(untouched));
        before = untouched;
        memset(&fault, 0, sizeof(fault));

        TEST_ASSERT_FALSE(plant_parameters_load(text, used, &untouched, &fault));
        TEST_ASSERT_EQUAL(PLANT_PARAMETER_MISSING, fault.fault);
        TEST_ASSERT_EQUAL_STRING(NOMINAL[omitted].name, fault.parameter);
        TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));
    }
}

/* --- The error the design assumes against a value ------------------------- */

/*
 * A different assumed error for each coefficient, so that a budget read back
 * cannot be right by accident. Were every value to carry the same figure, an
 * implementation that answered from the wrong index -- or from the first entry
 * for everything -- would pass every assertion below.
 */
static float error_for(size_t index)
{
    return 0.01f * (float)(index + 1u);
}

/*
 * Write the nominal description with an assumed error against every value, so
 * that what is loaded differs from `valid_text` in nothing but the annotations.
 */
static size_t describe_with_errors(char *out, size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written = snprintf(out + used, capacity - used, "%s = %.9g ~ %.9g\n",
                                     NOMINAL[i].name, NOMINAL[i].value, (double)error_for(i));
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

/*
 * The same, with one spelling of the figure written against every value, which
 * is what lets one inadmissible annotation be driven through a whole
 * description at once.
 */
static size_t describe_with_error_text(char *out, size_t capacity, const char *figure)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written = snprintf(out + used, capacity - used, "%s = %.9g ~%s%s\n",
                                     NOMINAL[i].name, NOMINAL[i].value,
                                     (figure[0] != '\0') ? " " : "", figure);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < capacity);
    }
    return used;
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C2: a consumer holding only the seam header can ask, for any coefficient the loaded description carries, what error the design assumes for it
static void test_the_assumed_error_of_every_coefficient_is_readable(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    const size_t used = describe_with_errors(text, sizeof(text));
    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    /*
     * Asked for by the name the description calls it, which is the only handle
     * a consumer has that does not come from a structure's own header.
     */
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        float assumed = -1.0f;
        TEST_ASSERT_TRUE(plant_parameter_budget_for(&budget, NOMINAL[i].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT(error_for(i), assumed);
    }
}

/* --- Writing a coefficient by the position the budget record is indexed by -- */

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: a corner outside the
/// range the structure declares admissible is refused rather than clamped back
/// to the edge of it.
///
/// This is the safety-relevant half of plant_parameter_scale and nothing else
/// asserts it. A record clamped back would be a machine the caller did not ask
/// for, reported as though it were the corner it did: work sizing a protection
/// bound against a corner has to be able to tell "the description does not admit
/// that corner" from "here is the corner", and the two demand opposite
/// responses. A clamp would answer true and hand back the second while meaning
/// the first, and the bound would then be sized against a machine the
/// description never claimed.
static void test_a_scale_outside_the_declared_range_is_refused_rather_than_clamped(void)
{
    plant_parameters_t before = parameters;
    plant_parameters_t after;

    /*
     * A factor no structure could admit at any position: whatever range a
     * coefficient is declared within, this carries it out of it. The position
     * swept is every one the structure has, so this does not turn on which
     * coefficient happens to sit where.
     */
    for (size_t at = 0u; at < COEFFICIENT_COUNT; at++) {
        after = before;
        TEST_ASSERT_FALSE_MESSAGE(plant_parameter_scale(&after, at, 1.0e30f),
                                  NOMINAL[at].name);
        TEST_ASSERT_EQUAL_MEMORY_MESSAGE(&before, &after, sizeof(after), NOMINAL[at].name);

        after = before;
        TEST_ASSERT_FALSE_MESSAGE(plant_parameter_scale(&after, at, -1.0e30f),
                                  NOMINAL[at].name);
        TEST_ASSERT_EQUAL_MEMORY_MESSAGE(&before, &after, sizeof(after), NOMINAL[at].name);
    }

    /* And a factor that is not a number at all writes nothing either. */
    after = before;
    TEST_ASSERT_FALSE(plant_parameter_scale(&after, 0u, 0.0f / 0.0f));
    TEST_ASSERT_FALSE(plant_parameter_scale(&after, 0u, 1.0f / 0.0f));
    TEST_ASSERT_EQUAL_MEMORY(&before, &after, sizeof(after));
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: a corner inside the
/// declared range is written, at the position the budget record is indexed by,
/// and each position writes a different coefficient.
///
/// The complement of the case above, and it is what says the refusal there is a
/// range check rather than a call that never writes anything. That every
/// position writes somewhere different is asserted rather than assumed: two
/// positions landing on one field would send a corner to a coefficient that is
/// not the one the budget record's own index named, and every figure taken off
/// that corner would be attributed to the wrong coefficient while reading
/// perfectly plausibly.
///
/// A factor of exactly one is a corner of the machine itself and writes nothing,
/// which is the case that separates "wrote the same value" from "wrote nothing
/// at all".
static void test_a_scale_inside_the_declared_range_writes_that_coefficient_alone(void)
{
    static plant_parameters_t scaled[COEFFICIENT_COUNT];

    for (size_t at = 0u; at < COEFFICIENT_COUNT; at++) {
        plant_parameters_t unchanged = parameters;

        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_scale(&unchanged, at, 1.0f), NOMINAL[at].name);
        TEST_ASSERT_EQUAL_MEMORY_MESSAGE(&parameters, &unchanged, sizeof(unchanged),
                                         NOMINAL[at].name);

        scaled[at] = parameters;
        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_scale(&scaled[at], at, 0.9f), NOMINAL[at].name);
        TEST_ASSERT_TRUE_MESSAGE(memcmp(&scaled[at], &parameters, sizeof(parameters)) != 0,
                                 NOMINAL[at].name);
    }

    for (size_t at = 0u; at < COEFFICIENT_COUNT; at++) {
        for (size_t other = at + 1u; other < COEFFICIENT_COUNT; other++) {
            TEST_ASSERT_TRUE_MESSAGE(
                memcmp(&scaled[at], &scaled[other], sizeof(parameters)) != 0,
                "two positions wrote the same field, so a corner at one of them is a corner at "
                "a coefficient the budget record did not name");
        }
    }
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: the seam refuses a
/// position it does not have and a record it was given nowhere to write.
///
/// A position past the structure's last is the one a caller walking a budget
/// record reaches when the record and the structure have come apart, and a
/// write accepted there would be a write into whatever sits past the record.
static void test_scaling_refuses_a_position_this_structure_does_not_have(void)
{
    plant_parameters_t scaled = parameters;

    TEST_ASSERT_FALSE(plant_parameter_scale(&scaled, COEFFICIENT_COUNT, 1.0f));
    TEST_ASSERT_FALSE(plant_parameter_scale(&scaled, COEFFICIENT_COUNT + 1u, 1.0f));
    TEST_ASSERT_FALSE(plant_parameter_scale(NULL, 0u, 1.0f));
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &scaled, sizeof(scaled));
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: the position a
/// coefficient occupies is answered by the name the description calls it, and
/// nothing else is answered at all.
///
/// The bridge between the seam's two ways of naming a coefficient, exercised
/// directly rather than only through the corner machinery that leans on it. Two
/// coefficients answering the same position, or a position past the structure's
/// count, would send a corner to the wrong coefficient silently.
static void test_the_position_of_every_coefficient_is_answered_by_name(void)
{
    bool seen[COEFFICIENT_COUNT];
    size_t at = 12345u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        seen[i] = false;
    }
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_position(NOMINAL[i].name, &at),
                                 NOMINAL[i].name);
        TEST_ASSERT_TRUE_MESSAGE(at < COEFFICIENT_COUNT, NOMINAL[i].name);
        TEST_ASSERT_FALSE_MESSAGE(seen[at], "two coefficients answer the same position");
        seen[at] = true;
    }

    at = 12345u;
    TEST_ASSERT_FALSE(plant_parameter_position("not.a.coefficient", &at));
    TEST_ASSERT_FALSE(plant_parameter_position("", &at));
    TEST_ASSERT_FALSE(plant_parameter_position(NULL, &at));
    TEST_ASSERT_FALSE(plant_parameter_position(NOMINAL[0].name, NULL));
    TEST_ASSERT_EQUAL_UINT(12345u, at);
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: whether the
/// coefficient at a position is one the supply drives is answered for every
/// position the structure has, and refused past its last.
///
/// The one relationship between two coefficients this seam carries, exercised
/// directly. A structure naming no such coefficient answers false for every
/// position -- a statement about that structure rather than a refusal -- and
/// the two are told apart here by the call answering true while writing false.
static void test_whether_a_position_is_supply_driven_is_answered_for_every_one(void)
{
    unsigned driven_count = 0u;
    bool driven = true;

    for (size_t at = 0u; at < COEFFICIENT_COUNT; at++) {
        driven = true;
        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_supply_driven(at, &driven), NOMINAL[at].name);
        if (driven) {
            driven_count++;
        }
    }
    TEST_ASSERT_TRUE_MESSAGE(driven_count > 1u,
                             "this structure reports at most one supply-driven coefficient, so "
                             "the joint corner it exists for moves nothing together");

    driven = true;
    TEST_ASSERT_FALSE(plant_parameter_supply_driven(COEFFICIENT_COUNT, &driven));
    TEST_ASSERT_FALSE(plant_parameter_supply_driven(COEFFICIENT_COUNT + 1u, &driven));
    TEST_ASSERT_FALSE(plant_parameter_supply_driven(0u, NULL));
    TEST_ASSERT_TRUE(driven);
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C2: a name the structure does not have is refused rather than answered
static void test_a_coefficient_the_structure_does_not_have_is_refused(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;
    float assumed = 12.0f;

    const size_t used = describe_with_errors(text, sizeof(text));
    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));

    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, "not.a.coefficient", &assumed));
    /* Nothing is written to a destination the answer did not fill. */
    TEST_ASSERT_EQUAL_FLOAT(12.0f, assumed);

    /*
     * A name that is a leading part of one the structure has, and one that
     * extends it. Both are the failure a comparison over the shorter of two
     * lengths would let through, and either would report a coefficient's error
     * against a coefficient that is not it.
     */
    char shortened[PLANT_PARAMETER_NAME_MAX];
    (void)snprintf(shortened, sizeof(shortened), "%s", NOMINAL[1].name);
    shortened[strlen(shortened) - 1u] = '\0';
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, shortened, &assumed));

    char extended[PLANT_PARAMETER_NAME_MAX];
    (void)snprintf(extended, sizeof(extended), "%s_x", NOMINAL[1].name);
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, extended, &assumed));

    /* An empty name is not the first coefficient. */
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, "", &assumed));
    TEST_ASSERT_EQUAL_FLOAT(12.0f, assumed);
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C2: a coefficient the description carried no error for reads as undeclared rather than as an error of zero
static void test_a_value_with_no_error_is_undeclared_rather_than_zero(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;
    size_t used = 0u;

    /*
     * The first coefficient carries nothing, the second carries an error of
     * zero, and the rest carry ordinary figures. The two are opposite claims --
     * "nobody has said how wrong this may be" against "the description says
     * this one is exact" -- and a caller sizing a margin has to act differently
     * on each, so the seam must not answer them alike.
     */
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        int written;
        if (i == 0u) {
            written = snprintf(text + used, sizeof(text) - used, "%s = %.9g\n", NOMINAL[i].name,
                               NOMINAL[i].value);
        } else if (i == 1u) {
            written = snprintf(text + used, sizeof(text) - used, "%s = %.9g ~ 0.0\n",
                               NOMINAL[i].name, NOMINAL[i].value);
        } else {
            written = snprintf(text + used, sizeof(text) - used, "%s = %.9g ~ %.9g\n",
                               NOMINAL[i].name, NOMINAL[i].value, (double)error_for(i));
        }
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < sizeof(text));
    }

    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    /* A description with an annotation missing is not a refused description. */
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    float assumed = 7.0f;
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, NOMINAL[0].name, &assumed));
    TEST_ASSERT_EQUAL_FLOAT(7.0f, assumed);

    TEST_ASSERT_TRUE(plant_parameter_budget_for(&budget, NOMINAL[1].name, &assumed));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, assumed);

    for (size_t i = 2u; i < COEFFICIENT_COUNT; i++) {
        TEST_ASSERT_TRUE(plant_parameter_budget_for(&budget, NOMINAL[i].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT(error_for(i), assumed);
    }
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C2: a record no description was ever read into answers nothing
static void test_a_budget_never_loaded_answers_nothing(void)
{
    plant_parameter_budget_t empty;
    float assumed = 3.0f;

    /*
     * The shape a caller that forgot to load one is holding. Answering from it
     * would report the design as assuming an error of nothing for every
     * coefficient in the model, which is the most dangerous possible reading of
     * a description that was never read.
     */
    memset(&empty, 0, sizeof(empty));
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&empty, NOMINAL[0].name, &assumed));
    TEST_ASSERT_EQUAL_FLOAT(3.0f, assumed);

    /* And a null record, or nowhere to put the answer, is not a crash. */
    TEST_ASSERT_FALSE(plant_parameter_budget_for(NULL, NOMINAL[0].name, &assumed));
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&empty, NULL, &assumed));
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&empty, NOMINAL[0].name, NULL));
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C2: the budget is read from the same description on the same terms, and a description the model would refuse yields no budget
static void test_a_refused_description_yields_no_budget(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_budget_t before;
    plant_parameter_error_t fault;

    /* One coefficient short: refused by the loader, and refused here. */
    size_t used = 0u;
    for (size_t i = 1u; i < COEFFICIENT_COUNT; i++) {
        const int written = snprintf(text + used, sizeof(text) - used, "%s = %.9g ~ %.9g\n",
                                     NOMINAL[i].name, NOMINAL[i].value, (double)error_for(i));
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
    }

    memset(&budget, 0xA5, sizeof(budget));
    before = budget;
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameter_budget_load(text, used, &budget, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MISSING, fault.fault);
    TEST_ASSERT_EQUAL_STRING(NOMINAL[0].name, fault.parameter);
    TEST_ASSERT_EQUAL_MEMORY(&before, &budget, sizeof(before));

    /* Nowhere to put the record, and no record of the fault, are both refused. */
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameter_budget_load(text, used, NULL, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MALFORMED, fault.fault);
    TEST_ASSERT_FALSE(plant_parameter_budget_load(text, used, &budget, NULL));
}

/*
 * One inadmissible figure, driven through a description that is otherwise the
 * valid one, through both of the seam's loaders. Both are asserted because the
 * refusal belongs to the grammar rather than to the operation: a description
 * that loaded as a parameter record while being refused as a budget would be a
 * description the two halves of the seam disagree about.
 */
static void expect_assumed_error_refusal(const char *figure)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t untouched;
    plant_parameters_t before;
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    const size_t used = describe_with_error_text(text, sizeof(text), figure);

    memset(&untouched, 0xA5, sizeof(untouched));
    before = untouched;
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(text, used, &untouched, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_ASSUMED_ERROR, fault.fault);
    /* The first coefficient is where the description first goes wrong. */
    TEST_ASSERT_EQUAL_STRING(NOMINAL[0].name, fault.parameter);
    TEST_ASSERT_EQUAL_UINT32(1u, fault.line);
    TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));

    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameter_budget_load(text, used, &budget, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_ASSUMED_ERROR, fault.fault);
    TEST_ASSERT_EQUAL_STRING(NOMINAL[0].name, fault.parameter);
    TEST_ASSERT_EQUAL_UINT32(1u, fault.line);
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: an assumed error that is absent after its marker, unreadable, negative or not finite is refused, and the coefficient and line are reported
static void test_an_assumed_error_that_cannot_stand_is_refused(void)
{
    /* The marker with nothing behind it: it reads as declared and says nothing. */
    expect_assumed_error_refusal("");

    /* Not a number at all, and a number with something after it. */
    expect_assumed_error_refusal("a fifth");
    expect_assumed_error_refusal("0.2x");
    expect_assumed_error_refusal("0.2 0.3");
    expect_assumed_error_refusal("%");

    /* There is no distance shorter than none. */
    expect_assumed_error_refusal("-0.1");
    expect_assumed_error_refusal("-0.0001");

    /*
     * A not-a-number passes every comparison written the other way round, and
     * an infinity says the value may be wrong by an unbounded amount, which is
     * a finding about the description rather than a wide margin.
     */
    expect_assumed_error_refusal("nan");
    expect_assumed_error_refusal("inf");
    expect_assumed_error_refusal("-inf");

    /* And a figure spelled beyond what this type can hold at all. */
    expect_assumed_error_refusal("1e999");
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: an error of zero, and one larger than the value it stands against, are both admissible
static void test_the_admissible_extremes_of_an_assumed_error_are_taken(void)
{
    static const char *const FIGURES[] = {"0", "0.0", "1", "2.5", "1e-30", "1e30"};
    char text[DESCRIPTION_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    /*
     * Nothing here caps the figure. A coefficient nobody has measured can be a
     * factor out rather than a percentage -- a loss estimated from geometry
     * with the conduction path left out is the case in this very description --
     * and a limit in the loader would be the loader inventing a judgement that
     * belongs to whoever wrote the description.
     */
    for (size_t i = 0u; i < sizeof(FIGURES) / sizeof(FIGURES[0]); i++) {
        const size_t used = describe_with_error_text(text, sizeof(text), FIGURES[i]);
        memset(&budget, 0, sizeof(budget));
        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));
        TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

        float assumed = -1.0f;
        TEST_ASSERT_TRUE(plant_parameter_budget_for(&budget, NOMINAL[0].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT((float)atof(FIGURES[i]), assumed);
    }
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: an assumed error against a value changes nothing about the value that is read
static void test_an_assumed_error_changes_nothing_that_is_read(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t with_errors;

    const size_t used = describe_with_errors(text, sizeof(text));
    load_expecting_success(text, used, &with_errors);

    /*
     * Compared against the record the same coefficients produce unannotated:
     * the figure travels with the value in the file and reaches the parameter
     * record in nothing but its own absence.
     */
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &with_errors, sizeof(parameters));
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: the value token ends at whichever annotation comes first, so every refusal the loader already makes survives the extension
static void test_every_refusal_still_fires_on_a_line_carrying_an_assumed_error(void)
{
    /*
     * The refusals a grammar extension is most likely to lose, each driven on a
     * line that also carries a well-formed assumed error: the annotation must
     * not become a way for a bad value to reach the record, and the value token
     * must not run past the marker and take the figure in with it.
     *
     * `displaces` names the coefficient the offending line stands in for, so
     * that a line meant to be refused for its value is not refused for being a
     * second setting of a coefficient the prefix already supplied.
     */
    static const struct {
        const char *line;
        plant_parameter_fault_t fault;
        const char *parameter;
        const char *displaces;
    } CASES[] = {
        {"not.a.coefficient = 1.0 ~ 0.2\n", PLANT_PARAMETER_UNKNOWN, "not.a.coefficient", NULL},
        {"brew.thermal_mass_j_per_k = -5.0 ~ 0.2\n", PLANT_PARAMETER_OUT_OF_RANGE,
         "brew.thermal_mass_j_per_k", "brew.thermal_mass_j_per_k"},
        {"brew.heater_power_w = twelve ~ 0.2\n", PLANT_PARAMETER_MALFORMED, "brew.heater_power_w",
         "brew.heater_power_w"},
        /* The one that matters most: a second number in the value token. */
        {"brew.heater_power_w = 1.0 2.0 ~ 0.2\n", PLANT_PARAMETER_MALFORMED,
         "brew.heater_power_w", "brew.heater_power_w"},
        {"brew.loss_w_per_k = nan ~ 0.2\n", PLANT_PARAMETER_OUT_OF_RANGE, "brew.loss_w_per_k",
         "brew.loss_w_per_k"},
        /* A coefficient given twice, with the figure on the second of them. */
        {"ambient_temperature_c = 21.0 ~ 0.2\n", PLANT_PARAMETER_DUPLICATE,
         "ambient_temperature_c", NULL},
        /* An empty value, with the figure sitting where the value should be. */
        {"brew.heater_power_w = ~ 0.2\n", PLANT_PARAMETER_MALFORMED, "brew.heater_power_w",
         "brew.heater_power_w"},
    };

    for (size_t c = 0u; c < sizeof(CASES) / sizeof(CASES[0]); c++) {
        char text[DESCRIPTION_MAX];
        plant_parameters_t untouched;
        plant_parameters_t before;
        plant_parameter_error_t fault;
        size_t used = 0u;
        uint32_t lines = 0u;

        /*
         * The offending line follows an otherwise valid description, every line
         * of which carries an assumed error too: the refusal has to survive a
         * description that is annotated throughout, not only one where the
         * offending line is the single annotated one.
         */
        for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
            if (CASES[c].displaces != NULL && strcmp(NOMINAL[i].name, CASES[c].displaces) == 0) {
                continue;
            }
            const int written = snprintf(text + used, sizeof(text) - used, "%s = %.9g ~ %.9g\n",
                                         NOMINAL[i].name, NOMINAL[i].value, (double)error_for(i));
            TEST_ASSERT_TRUE(written > 0);
            used += (size_t)written;
            lines++;
        }
        const int appended = snprintf(text + used, sizeof(text) - used, "%s", CASES[c].line);
        TEST_ASSERT_TRUE(appended > 0);
        used += (size_t)appended;
        lines++;
        TEST_ASSERT_TRUE(used < sizeof(text));

        memset(&untouched, 0xA5, sizeof(untouched));
        before = untouched;
        memset(&fault, 0, sizeof(fault));

        TEST_ASSERT_FALSE(plant_parameters_load(text, used, &untouched, &fault));
        TEST_ASSERT_EQUAL(CASES[c].fault, fault.fault);
        TEST_ASSERT_EQUAL_STRING(CASES[c].parameter, fault.parameter);
        TEST_ASSERT_EQUAL_UINT32(lines, fault.line);
        TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));
    }
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: the two annotations are read in the order the grammar fixes, and a line carrying both is read as both
static void test_a_line_carries_both_annotations_in_the_fixed_order(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t record;
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written =
            snprintf(text + used, sizeof(text) - used, "%s = %.9g ~ %.9g @document p.24\n",
                     NOMINAL[i].name, NOMINAL[i].value, (double)error_for(i));
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < sizeof(text));
    }

    load_expecting_success(text, used, &record);
    TEST_ASSERT_EQUAL_MEMORY(&parameters, &record, sizeof(parameters));

    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        float assumed = -1.0f;
        TEST_ASSERT_TRUE(plant_parameter_budget_for(&budget, NOMINAL[i].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT(error_for(i), assumed);
    }
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: a marker inside an origin's account is prose rather than a second annotation
static void test_a_marker_inside_an_account_is_part_of_the_account(void)
{
    char text[DESCRIPTION_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;
    size_t used = 0u;

    /*
     * The order is fixed because an account is free text running to the end of
     * the line. A description writing the error after the origin has written it
     * inside somebody's sentence about a service manual, and it reads as no
     * error at all -- which is what it is. Reading it would mean the grammar
     * had no fixed order, and an account mentioning a tilde would then change
     * what the design assumes.
     */
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written =
            snprintf(text + used, sizeof(text) - used, "%s = %.9g @estimated within ~ 0.5\n",
                     NOMINAL[i].name, NOMINAL[i].value);
        TEST_ASSERT_TRUE(written > 0);
        used += (size_t)written;
        TEST_ASSERT_TRUE(used < sizeof(text));
    }

    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        float assumed = 9.0f;
        TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, NOMINAL[i].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT(9.0f, assumed);
    }
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: the figure is reached past the blanks around it, and a final annotated line without a newline is read
static void test_an_assumed_error_is_read_however_it_is_spaced(void)
{
    static const char *const SPACINGS[] = {"~0.25", "~ 0.25", "~\t0.25", "   ~   0.25   "};
    char text[DESCRIPTION_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    for (size_t s = 0u; s < sizeof(SPACINGS) / sizeof(SPACINGS[0]); s++) {
        size_t used = 0u;
        for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
            const int written = snprintf(text + used, sizeof(text) - used, "%s = %.9g %s\n",
                                         NOMINAL[i].name, NOMINAL[i].value, SPACINGS[s]);
            TEST_ASSERT_TRUE(written > 0);
            used += (size_t)written;
            TEST_ASSERT_TRUE(used < sizeof(text));
        }
        /* The last line loses its newline, so the span is what is read. */
        used--;

        memset(&budget, 0, sizeof(budget));
        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));

        float assumed = -1.0f;
        TEST_ASSERT_TRUE(
            plant_parameter_budget_for(&budget, NOMINAL[COEFFICIENT_COUNT - 1u].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT(0.25f, assumed);
    }
}

/* --- The behaviours a wrong model is not permitted to take away ----------- */

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C4: the classes a behaviour is declared in are one enumerated vocabulary, and each has exactly one word
static void test_the_robustness_classes_are_one_enumerated_set(void)
{
    static const char *const WORDS[] = PLANT_ROBUSTNESS_KIND_WORDS;

    /*
     * The words and the classes are two halves of one vocabulary, edited
     * separately. A class added without its word would read one entry past this
     * array; a word belonging to no class would let a declaration classify a
     * behaviour as something the design does not distinguish.
     */
    TEST_ASSERT_EQUAL_UINT32((uint32_t)PLANT_ROBUSTNESS_KIND_COUNT,
                             (uint32_t)(sizeof(WORDS) / sizeof(WORDS[0])));

    for (size_t i = 0u; i < sizeof(WORDS) / sizeof(WORDS[0]); i++) {
        TEST_ASSERT_NOT_NULL(WORDS[i]);
        TEST_ASSERT_TRUE(WORDS[i][0] != '\0');
        for (size_t j = i + 1u; j < sizeof(WORDS) / sizeof(WORDS[0]); j++) {
            /*
             * Two classes sharing a word would collapse the distinction while
             * the vocabulary went on declaring two of them, and every behaviour
             * carrying that word would be classified as both.
             */
            TEST_ASSERT_FALSE(strcmp(WORDS[i], WORDS[j]) == 0);
        }
    }

    TEST_ASSERT_EQUAL_STRING("invariant", WORDS[PLANT_ROBUSTNESS_INVARIANT]);
    TEST_ASSERT_EQUAL_STRING("degrading", WORDS[PLANT_ROBUSTNESS_DEGRADING]);
}

/* --- The reference machine's own description ------------------------------ */

/* Room for the description on disk, which carries an account against every
 * value and is therefore far longer than the ones built above. */
#define REFERENCE_MAX 16384

/*
 * And room for the statement beside it, which is prose and an order larger than
 * the values it accounts for.
 */
#define STATEMENT_MAX 65536

/*
 * Read the description the build names, which is the file the reference
 * machine's numbers live in rather than a copy of them.
 */
static size_t read_reference_description(char *out, size_t capacity)
{
    FILE *const handle = fopen(REFERENCE_DESCRIPTION_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "the reference description named by the build is absent");
    const size_t used = fread(out, 1u, capacity - 1u, handle);
    (void)fclose(handle);
    /*
     * A description that filled the buffer was truncated, and a truncated one
     * would be refused for a reason that has nothing to do with the file.
     */
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < capacity - 1u);
    out[used] = '\0';
    return used;
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C4: the reference description is admissible to the structure it describes and advances a model instance
/// SOL-PLANT-DESCRIPTION-BASELINE.C5: the host build and the model's tests run against the reference description
static void test_the_reference_description_is_admissible_and_advances_a_model(void)
{
    char text[REFERENCE_MAX];
    plant_parameters_t reference;
    plant_parameter_error_t fault;
    plant_model_t model;
    float values[PLANT_QUANTITY_COUNT];

    const size_t used = read_reference_description(text, sizeof(text));

    /*
     * Nothing missing, nothing outside the structure's declared ranges, and no
     * line refused -- the annotations included, which is what makes the origins
     * a property of a file the code actually reads rather than of a document
     * beside it. This is what catches the description drifting from the code on
     * the day the structure's coefficient set changes, which is otherwise
     * silent because nothing else reads it.
     */
    memset(&reference, 0, sizeof(reference));
    memset(&fault, 0, sizeof(fault));
    if (!plant_parameters_load(text, used, &reference, &fault)) {
        char message[192];
        (void)snprintf(message, sizeof(message),
                       "the reference description was refused: fault %d at line %u, coefficient "
                       "'%s'",
                       (int)fault.fault, (unsigned)fault.line, fault.parameter);
        TEST_FAIL_MESSAGE(message);
    }
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    TEST_ASSERT_TRUE(plant_model_init(&model, &reference));

    /* Read through the seam rather than out of the record: what the instance
     * started from is a quantity the model exposes, not a field to reach for. */
    float initial[PLANT_QUANTITY_COUNT];
    read_all(&model, initial);

    for (int i = 0; i < TRAJECTORY_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &WORKING, 0.0f, STEP_MS));
    }

    /* And it answers every quantity the seam enumerates, with a number. */
    read_all(&model, values);
    for (size_t quantity = 0u; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_TRUE(isfinite(values[quantity]));
    }
    /*
     * The masses were driven for two minutes. A description that reached the
     * model as zeroes, or an instance answering with its own initial state,
     * would not have moved.
     */
    TEST_ASSERT_TRUE(values[PLANT_QUANTITY_BREW_TEMPERATURE_C] >
                     initial[PLANT_QUANTITY_BREW_TEMPERATURE_C]);
}

/// SOL-ONBOARD-PLANT-MODEL-IDENTITY.C4: the target parses its description through the same loader the host tier uses, refused on the same terms, and a refused record leaves no usable model rather than defaults
static void test_the_carried_description_is_refused_on_the_loaders_own_terms(void)
{
    /*
     * The machine carries these bytes compiled in and reads them back through
     * this loader, because there is no filesystem on the target to open a
     * description from. Nothing on the machine can report what it made of them,
     * so the terms it is refused on are established here, against the same
     * bytes and the same parser rather than against a description written for
     * the occasion: a suite carrying its own text would go on passing after the
     * file the machine actually carries had drifted away from it.
     *
     * Each damaged form below is one of the loader's declared refusals, and the
     * fault is asserted rather than merely the refusal. Two damaged forms can
     * be refused for the same reason -- appending a name the description
     * already carries is a duplicate long before it is out of range -- and an
     * assertion that only asks whether something was refused cannot tell that
     * apart from the case it was written for.
     */
    static const char POISON = '\xa5';
    char text[REFERENCE_MAX];
    const size_t used = read_reference_description(text, sizeof(text));

    /* A coefficient this structure has, whose value can be replaced in place so
     * that the damaged form is out of range rather than repeated. */
    static const char IN_RANGE[] = "brew.thermal_mass_j_per_k = 320.0";
    static const char OUT_OF_RANGE[] = "brew.thermal_mass_j_per_k = -1.0";
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(text, IN_RANGE),
                                 "the description no longer carries the value this replaces");

    char damaged[REFERENCE_MAX];
    struct {
        const char *what;
        const char *appended;
        const char *replace_with;
        plant_parameter_fault_t expected;
    } const cases[] = {
        {"a line that cannot be parsed", "this line is not a name and a value\n", NULL,
         PLANT_PARAMETER_MALFORMED},
        {"a name the structure does not have", "definitely.not.a.parameter = 1.0\n", NULL,
         PLANT_PARAMETER_UNKNOWN},
        {"a name given twice", "brew.heater_power_w = 900.0\n", NULL, PLANT_PARAMETER_DUPLICATE},
        {"a value outside the structure's declared range", NULL, OUT_OF_RANGE,
         PLANT_PARAMETER_OUT_OF_RANGE},
    };

    for (size_t i = 0u; i < sizeof(cases) / sizeof(cases[0]); i++) {
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        size_t length;

        if (cases[i].appended != NULL) {
            const size_t appended = strlen(cases[i].appended);
            TEST_ASSERT_TRUE(used + appended < sizeof(damaged));
            memcpy(damaged, text, used);
            memcpy(damaged + used, cases[i].appended, appended);
            length = used + appended;
        } else {
            const char *const at = strstr(text, IN_RANGE);
            const size_t before = (size_t)(at - text);
            const size_t replacement = strlen(cases[i].replace_with);
            const size_t after = used - before - strlen(IN_RANGE);
            TEST_ASSERT_TRUE(before + replacement + after < sizeof(damaged));
            memcpy(damaged, text, before);
            memcpy(damaged + before, cases[i].replace_with, replacement);
            memcpy(damaged + before + replacement, at + strlen(IN_RANGE), after);
            length = before + replacement + after;
        }

        memset(&loaded, POISON, sizeof(loaded));
        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_FALSE_MESSAGE(plant_parameters_load(damaged, length, &loaded, &fault),
                                  cases[i].what);
        TEST_ASSERT_EQUAL_MESSAGE(cases[i].expected, fault.fault, cases[i].what);

        /*
         * And nothing was written. The header promises no value is assumed for
         * a coefficient that is missing or rejected; this asks the stronger
         * question the machine's position actually depends on, which is that a
         * caller with no second description to fall back on finds the record as
         * it left it rather than partly filled.
         */
        const unsigned char *const bytes = (const unsigned char *)&loaded;
        for (size_t offset = 0u; offset < sizeof(loaded); offset++) {
            TEST_ASSERT_EQUAL_HEX8_MESSAGE((unsigned char)POISON, bytes[offset], cases[i].what);
        }
    }

    /*
     * And a description truncated at one of its coefficients, which is the
     * refusal the cases above cannot reach: each of those leaves the required
     * set complete and adds something on top of it. Truncating removes that
     * coefficient and every one after it, which is enough to be missing one.
     */
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    const char *const line = strstr(text, "brew.heater_power_w");
    TEST_ASSERT_NOT_NULL(line);
    const size_t before = (size_t)(line - text);

    memcpy(damaged, text, before);
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(damaged, before, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MISSING, fault.fault);
}

/// SOL-PLANT-DESCRIPTION-BASELINE.C5: the host build and the model's tests run against the reference description
static void test_the_reference_description_claims_a_machine(void)
{
    char text[REFERENCE_MAX];

    (void)read_reference_description(text, sizeof(text));

    /*
     * The description these tests are run against is the one carrying the
     * machine's own figures, not a placeholder that exempts itself. Were it to
     * pick up the exemption, every value in it would stop owing an account and
     * the check that reads it would fall silent while still passing -- so the
     * suite that runs against it is where that is refused.
     */
    TEST_ASSERT_NULL_MESSAGE(strstr(text, "@describes-no-machine"),
                             "the reference description exempts itself from carrying origins");
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C5: the description under params/ carries an assumed error for every coefficient its structure requires, and it is readable through the seam
static void test_the_reference_description_states_how_wrong_every_value_may_be(void)
{
    char text[REFERENCE_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    const size_t used = read_reference_description(text, sizeof(text));

    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    if (!plant_parameter_budget_load(text, used, &budget, &fault)) {
        char message[192];
        (void)snprintf(message, sizeof(message),
                       "the reference description was refused: fault %d at line %u, coefficient "
                       "'%s'",
                       (int)fault.fault, (unsigned)fault.line, fault.parameter);
        TEST_FAIL_MESSAGE(message);
    }

    /*
     * Every coefficient the structure requires, not merely the ones the file
     * happens to annotate. This is what catches the description gaining a
     * coefficient without gaining a judgement about how wrong it may be -- the
     * build check reads the file, and this reads the file the build hands the
     * suite, and two defences are worth having over a property nothing else
     * would notice losing.
     */
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        float assumed = -1.0f;
        char message[128];
        (void)snprintf(message, sizeof(message), "'%s' declares no assumed error",
                       NOMINAL[i].name);
        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_budget_for(&budget, NOMINAL[i].name, &assumed),
                                 message);
        /*
         * A fraction of the value, so it is finite and not negative. Nothing
         * here asserts a particular figure: choosing them is a judgement argued
         * in thermoblock.md, and pinning one in a test would mean revising an
         * assumption edited a test.
         */
        TEST_ASSERT_TRUE(isfinite(assumed));
        TEST_ASSERT_TRUE(assumed >= 0.0f);
    }
}

/* --- The states this structure keeps, and the seam that reaches them ------- */

/*
 * Describe the nominal coefficients with one of them replaced. Everything else
 * is the nominal table, so a difference between two runs built this way is that
 * coefficient and nothing else.
 */
static size_t describe_with_one(char *out, size_t capacity, size_t index, double value)
{
    double values[COEFFICIENT_COUNT];

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        values[i] = NOMINAL[i].value;
    }
    values[index] = value;
    return describe_values(values, out, capacity);
}

/* The water on its way to the group, which no quantity carries. */
static float outlet(const plant_model_t *model)
{
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &value));
    return value;
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C1: The reference structure distinguishes the
/// heated mass from the water leaving it.
///
/// A step change in heater duty from rest, watched at every step. The casting
/// rises the moment the element is commanded, and it is the casting this machine
/// senses and reports; the water the group receives has to be carried there by
/// that casting and so is always behind it while it is climbing. Two states read
/// from one field would be equal at every step, which is the defect this is
/// written against -- and it is not a hypothetical one, since it is precisely
/// what this structure did before.
static void test_the_water_on_its_way_to_the_group_trails_the_heated_mass(void)
{
    const plant_actuation_t brew_only = {{ACTUATION_FULL_SCALE, 0u, 0u}};
    plant_model_t model;
    float water = 0.0f;
    float reported = 0.0f;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    /* At rest the two are the same: a machine that has stood still has no
     * gradient in it, so equality here is the state being right rather than the
     * distinction being absent. */
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &reported));
    TEST_ASSERT_EQUAL_FLOAT(reported, outlet(&model));

    for (int step = 0; step < SHORT_STEPS; step++) {
        const float previous_water = water;

        TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 0.0f, STEP_MS));
        water = outlet(&model);
        TEST_ASSERT_TRUE(
            plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &reported));

        /* Rising, so the trailing below is a lag rather than a failure to move
         * at all -- water pinned at ambient would also always be below the
         * casting. The first step has nothing before it to rise from. */
        if (step > 0) {
            TEST_ASSERT_TRUE(water > previous_water);
        }
        TEST_ASSERT_TRUE(water < reported);
    }

    /*
     * And the quantity the seam exposes is the casting rather than the water.
     * This machine's brew sensor is in the casting, so a model reporting the
     * water under that name would be predicting something nothing observes --
     * and the estimator built on it would difference a prediction of the stream
     * against a reading of the metal, carrying this very lag as a standing bias
     * in the residual that exists to detect drift.
     */
    TEST_ASSERT_EQUAL_FLOAT(reported, heated_mass(&model));
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C1: The reference structure distinguishes the
/// heated mass from the water leaving it.
///
/// The lag is the one the description asks for, not merely some lag. Compared
/// against the closed form of the two relations composed -- a first-order mass
/// driving a first-order follower -- which is arithmetic derived on paper rather
/// than the expression the structure evaluates. A time constant entered
/// inverted, or the pressure path's constant used by mistake, satisfies the
/// trailing test above and fails this one.
///
/// Run with the pump closed, which is the case the composed closed form
/// describes: with nothing being drawn the two relations are the pair they
/// always were, the lag is the no-draw conduction constant alone, and the
/// casting does not depend on the water. What the structure evaluates is the
/// coupled step, so this is also the check that the coupled step reduces to the
/// uncoupled pair where the pair is uncoupled.
static void test_the_water_follows_the_casting_by_its_own_time_constant(void)
{
    /* Both poles well inside the run, and both far longer than the step, so the
     * step-wise relaxation is close to the continuous solution it approximates. */
    const double mass = 100.0;
    const double loss = 5.0;
    const double power = 400.0;
    const double tau_outlet = 2.0;
    const uint32_t interval_ms = 10u;

    const plant_actuation_t brew_only = {{ACTUATION_FULL_SCALE, 0u, 0u}};
    double values[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        values[i] = NOMINAL[i].value;
    }
    values[I_BREW_MASS] = mass;
    values[I_BREW_LOSS] = loss;
    values[I_BREW_POWER] = power;
    values[I_BREW_CONDUCTION_TAU] = tau_outlet;

    const size_t used = describe_values(values, text, sizeof(text));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

    const double start = values[I_AMBIENT];
    const double settling = start + power / loss;
    const double tau_casting = mass / loss;

    /* Sampled at a few multiples of the shorter pole, where the two curves are
     * furthest apart and a wrong constant has nowhere to hide. */
    static const int SAMPLES_AT[] = {100, 300, 1000, 3000};

    int taken = 0;
    for (size_t s = 0u; s < sizeof(SAMPLES_AT) / sizeof(SAMPLES_AT[0]); s++) {
        while (taken < SAMPLES_AT[s]) {
            TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 0.0f, interval_ms));
            taken++;
        }

        const double seconds = ((double)taken * (double)interval_ms) / 1000.0;
        const double casting_decay = exp(-seconds / tau_casting);
        const double outlet_decay = exp(-seconds / tau_outlet);
        /*
         * Two first-order lags in series, from a common starting temperature:
         * the casting relaxes towards its settling value, and the water relaxes
         * towards the casting. The weights below are what solving that pair
         * gives and reduce to the casting's own curve as the outlet constant
         * vanishes.
         */
        const double expected =
            settling + (start - settling) *
                           ((tau_casting * casting_decay - tau_outlet * outlet_decay) /
                            (tau_casting - tau_outlet));

        const double got = (double)outlet(&model);
        const double travelled = fabs(expected - start);
        const double relative = fabs(got - expected) / travelled;
        if (!(relative < 5.0e-3)) {
            char message[220];
            (void)snprintf(message, sizeof(message),
                           "at %.3g s: water %.9g, closed form %.9g, relative error %.3g",
                           seconds, got, expected, relative);
            TEST_FAIL_MESSAGE(message);
        }

        /* The casting itself still satisfies its own curve, so a discrepancy
         * above is in the following rather than in what is being followed. */
        const double casting_expected = settling + (start - settling) * casting_decay;
        const double casting_relative =
            fabs((double)heated_mass(&model) - casting_expected) / fabs(casting_expected - start);
        if (!(casting_relative < 5.0e-3)) {
            char message[220];
            (void)snprintf(message, sizeof(message),
                           "at %.3g s: casting %.9g, closed form %.9g, relative error %.3g",
                           seconds, (double)heated_mass(&model), casting_expected,
                           casting_relative);
            TEST_FAIL_MESSAGE(message);
        }
    }
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C1: The reference structure distinguishes the
/// heated mass from the water leaving it.
///
/// The coefficient is what sets how far apart the two states are, and it acts in
/// the direction it claims to. A shorter constant leaves the water closer to the
/// casting at the same point in the same transient; a constant entered as its
/// reciprocal, or one that never reaches the equation at all, does not.
///
/// With the pump closed, so the constant being varied is the whole of the lag.
/// That is the no-draw conduction constant now, and it is the case in which it
/// is the only thing setting the gap -- the draw-dependent test below is where
/// the other half of the relation is exercised.
static void test_a_shorter_outlet_time_constant_brings_the_water_closer(void)
{
    static const double TAUS[] = {0.2, 1.0, 5.0};
    const plant_actuation_t brew_only = {{ACTUATION_FULL_SCALE, 0u, 0u}};
    double gaps[sizeof(TAUS) / sizeof(TAUS[0])];

    for (size_t t = 0u; t < sizeof(TAUS) / sizeof(TAUS[0]); t++) {
        char text[DESCRIPTION_MAX];
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        plant_model_t model;

        const size_t used =
            describe_with_one(text, sizeof(text), I_BREW_CONDUCTION_TAU, TAUS[t]);
        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

        for (int step = 0; step < SHORT_STEPS; step++) {
            TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 0.0f, STEP_MS));
        }
        gaps[t] = (double)heated_mass(&model) - (double)outlet(&model);

        /* Behind, at every constant sampled -- the ordering below would also be
         * satisfied by three water temperatures that had all overshot. */
        TEST_ASSERT_TRUE(gaps[t] > 0.0);
    }

    for (size_t t = 1u; t < sizeof(TAUS) / sizeof(TAUS[0]); t++) {
        char message[160];
        (void)snprintf(message, sizeof(message),
                       "a constant of %.3g s left a gap of %.9g, and %.3g s left %.9g",
                       TAUS[t - 1u], gaps[t - 1u], TAUS[t], gaps[t]);
        TEST_ASSERT_TRUE_MESSAGE(gaps[t] > gaps[t - 1u], message);
    }
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C2: The plant seam declares a vocabulary for
/// the states a structure keeps.
///
/// The substance of the split is that a state exists with no quantity against
/// it. If the two vocabularies ever carried the same members, there would be
/// nothing for an estimator to reconstruct that a consumer could not already
/// read, and the second vocabulary would be a synonym for the first.
static void test_the_state_vocabulary_carries_what_the_quantities_cannot(void)
{
    const float SENTINEL = -4321.0f;
    plant_model_t model;

    /*
     * The claim is about membership rather than size, and it is asserted that
     * way. It was once written as a count -- more states than quantities --
     * which held while every quantity was read from a state and the outlet was
     * the only member either vocabulary had to itself. It stopped holding when
     * the seam gained the rate water is drawn, which is a quantity no state
     * carries: the counts are now equal and the substance is unchanged, and a
     * test comparing them would have reported the split had closed at the
     * moment it widened. The two vocabularies overlap; neither contains the
     * other; and that is what is checked below, once in each direction.
     *
     * The state no quantity carries, checked by putting a value into the
     * outlet that nothing else holds and finding it in no quantity.
     */
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, SENTINEL));
    {
        float quantities[PLANT_QUANTITY_COUNT];
        read_all(&model, quantities);
        for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
            TEST_ASSERT_NOT_EQUAL_FLOAT(SENTINEL, quantities[quantity]);
        }
    }

    /*
     * And the quantity no state carries. The rate water is drawn is produced
     * from what the pump was commanded rather than from anything integrated, so
     * no member of the state vocabulary answers with it -- checked by
     * commanding a draw, reading the rate back, and finding it in no state.
     * Guarded on the rate being non-zero first, since a rate of zero would find
     * itself absent from the states for the wrong reason.
     */
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(plant_model_step(&model, &WORKING, 0.0f, STEP_MS));
    {
        float drawn = 0.0f;
        float states[PLANT_STATE_COUNT];
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
        TEST_ASSERT_TRUE(drawn > 0.0f);
        read_all_states(&model, states);
        for (int state = 0; state < PLANT_STATE_COUNT; state++) {
            TEST_ASSERT_NOT_EQUAL_FLOAT(drawn, states[state]);
        }
    }

    /* Enumerated from zero and dense, so a caller may walk the vocabulary
     * rather than having to know the names in it. */
    TEST_ASSERT_EQUAL_INT(0, (int)PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C);

    /*
     * Every member of the vocabulary is either answered or refused, and a
     * refusal writes nothing. A structure that let an enumerated state fall
     * through to a default would return whatever the caller's variable already
     * held while saying it had succeeded, which is the failure a vocabulary
     * walked by index makes possible and nothing else here would catch.
     */
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        float value = SENTINEL;
        char message[96];

        (void)snprintf(message, sizeof(message), "state %d neither answered nor refused cleanly",
                       state);
        if (plant_model_state(&model, (plant_state_t)state, &value)) {
            TEST_ASSERT_TRUE_MESSAGE(isfinite(value), message);
        } else {
            TEST_ASSERT_EQUAL_FLOAT_MESSAGE(SENTINEL, value, message);
        }
    }
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C3: Every plant structure answers the state
/// accessor.
///
/// Every state comes back carrying what it names, not merely a finite number.
/// A state accessor is a switch of assignments, so the defect it invites is a
/// case wired to the wrong field -- steam temperature answering a pressure, the
/// two pressures crossed. That produces no arithmetic for the operator sweep to
/// mutate and passes every property asserted about the trajectory, so it is
/// caught here or nowhere.
///
/// The model is driven to a point where all five states are distinct before
/// anything is compared, because a structure at rest has several of them equal
/// and a crossed pair would read correctly.
static void test_every_state_carries_the_quantity_it_names(void)
{
    const plant_actuation_t working = {
        {ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE / 2u}};
    plant_model_t model;
    float states[PLANT_STATE_COUNT];
    float quantities[PLANT_QUANTITY_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    for (int step = 0; step < TRAJECTORY_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &working, 0.0f, STEP_MS));
    }
    read_all_states(&model, states);
    read_all(&model, quantities);

    /* Distinct, so an equality below is a wiring that is right rather than two
     * numbers that happen to coincide. */
    for (int a = 0; a < PLANT_STATE_COUNT; a++) {
        for (int b = a + 1; b < PLANT_STATE_COUNT; b++) {
            char message[112];
            (void)snprintf(message, sizeof(message),
                           "states %d and %d are equal, so a crossed pair would not show", a, b);
            TEST_ASSERT_TRUE_MESSAGE(states[a] != states[b], message);
        }
    }

    /*
     * Each state this structure exposes as a quantity answers with the same
     * number through both routes. Reading the same field twice is exactly what
     * is wanted here -- the claim is that the two routes agree about which
     * field, not that they are computed apart.
     */
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_BREW_TEMPERATURE_C],
                            states[PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C]);
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_STEAM_TEMPERATURE_C],
                            states[PLANT_STATE_STEAM_TEMPERATURE_C]);
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_BREW_PRESSURE_BAR],
                            states[PLANT_STATE_BREW_PRESSURE_BAR]);
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_STEAM_PRESSURE_BAR],
                            states[PLANT_STATE_STEAM_PRESSURE_BAR]);

    /*
     * The one with no quantity against it is pinned by what it is: the water on
     * its way to the group sits between the casting it came from and the
     * ambient the machine started at, and it is neither of them.
     */
    const float water = states[PLANT_STATE_BREW_OUTLET_TEMPERATURE_C];
    TEST_ASSERT_TRUE((double)water > NOMINAL[I_AMBIENT].value);
    TEST_ASSERT_TRUE(water < states[PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C]);
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C3: Every plant structure answers the state
/// accessor.
///
/// A read this structure will not answer -- a null instance, a null
/// destination, an instance never initialised, or a value outside the
/// vocabulary -- is refused on the terms plant_model_quantity already refuses
/// one, and leaves what the caller passed exactly as it was. Writing a zero
/// into it would be indistinguishable from a state that happens to be zero.
static void test_a_state_read_that_cannot_be_answered_is_refused_and_writes_nothing(void)
{
    const float SENTINEL = -12345.0f;
    plant_model_t uninitialised;
    plant_model_t model;
    float value = SENTINEL;

    memset(&uninitialised, 0, sizeof(uninitialised));
    TEST_ASSERT_FALSE(
        plant_model_state(&uninitialised, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &value));
    TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);

    TEST_ASSERT_FALSE(plant_model_state(NULL, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &value));
    TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_FALSE(plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, NULL));

    TEST_ASSERT_FALSE(plant_model_state(&model, PLANT_STATE_COUNT, &value));
    TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);
    TEST_ASSERT_FALSE(plant_model_state(&model, (plant_state_t)(PLANT_STATE_COUNT + 7), &value));
    TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C4: A consumer reads a structure's state
/// through the seam rather than around it.
///
/// This file is a consumer: it sits outside src/plant, includes no structure's
/// own header, and names no field or function the thermoblock structure owns. It reaches the water on its way to the group all the same, which is
/// what the work that reconstructs that temperature will need. The other half
/// of this criterion is not written here and cannot be: that naming those
/// fields directly fails the build is what check_plant_encapsulation.py
/// enforces over this file among the rest.
static void test_the_unreported_state_is_reachable_through_the_seam_alone(void)
{
    const plant_actuation_t brew_only = {{ACTUATION_FULL_SCALE, 0u, 0u}};
    plant_model_t model;
    float reported = 0.0f;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    for (int step = 0; step < SHORT_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 0.0f, STEP_MS));
    }

    const float water = outlet(&model);
    TEST_ASSERT_TRUE(isfinite(water));
    /* Above where it started, taken from the table the description was written
     * from rather than from the loaded record: naming a field of that record is
     * the very thing this criterion says a consumer must not do, and the
     * encapsulation check refuses the build for it. */
    TEST_ASSERT_TRUE((double)water > NOMINAL[I_AMBIENT].value);

    /*
     * And no quantity carries it, which is what makes it worth reconstructing:
     * a consumer holding only the quantities cannot obtain this number by any
     * route, so the seam operation is the only way to it rather than a second
     * way to something already reachable.
     */
    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        char message[96];

        TEST_ASSERT_TRUE(plant_model_quantity(&model, (plant_quantity_t)quantity, &reported));
        (void)snprintf(message, sizeof(message), "quantity %d carries the water after all",
                       quantity);
        TEST_ASSERT_TRUE_MESSAGE(reported != water, message);
    }
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: the positional constants above index the
/// coefficient table, and nothing but this ties the two together. A coefficient
/// inserted into that table silently re-points every one of them, and the
/// closed-form comparisons would then be checking the wrong equation against the
/// wrong numbers while still passing.
static void test_the_coefficient_indices_name_what_they_claim(void)
{
    TEST_ASSERT_EQUAL_STRING("ambient_temperature_c", NOMINAL[I_AMBIENT].name);
    TEST_ASSERT_EQUAL_STRING("brew.thermal_mass_j_per_k", NOMINAL[I_BREW_MASS].name);
    TEST_ASSERT_EQUAL_STRING("brew.heater_power_w", NOMINAL[I_BREW_POWER].name);
    TEST_ASSERT_EQUAL_STRING("brew.loss_w_per_k", NOMINAL[I_BREW_LOSS].name);
    TEST_ASSERT_EQUAL_STRING("brew.outlet_held_volume_ml", NOMINAL[I_BREW_HELD_VOLUME].name);
    TEST_ASSERT_EQUAL_STRING("brew.outlet_conduction_time_constant_s",
                             NOMINAL[I_BREW_CONDUCTION_TAU].name);
    TEST_ASSERT_EQUAL_STRING("pump.flow_ml_per_s", NOMINAL[I_PUMP_FLOW].name);
    TEST_ASSERT_EQUAL_STRING("water.feed_temperature_c", NOMINAL[I_WATER_FEED].name);
    TEST_ASSERT_EQUAL_STRING("water.heat_capacity_j_per_ml_k",
                             NOMINAL[I_WATER_HEAT_CAPACITY].name);
    TEST_ASSERT_EQUAL_STRING("steam.thermal_mass_j_per_k", NOMINAL[I_STEAM_MASS].name);
    TEST_ASSERT_EQUAL_STRING("steam.loss_w_per_k", NOMINAL[I_STEAM_LOSS].name);
    TEST_ASSERT_EQUAL_STRING("water.latent_heat_j_per_ml", NOMINAL[I_WATER_LATENT_HEAT].name);
    TEST_ASSERT_EQUAL_STRING("steam.saturation_temperature_c", NOMINAL[I_STEAM_SATURATION].name);
    TEST_ASSERT_EQUAL_STRING("steam.pressure_bar_per_k", NOMINAL[I_STEAM_BAR_PER_K].name);
    TEST_ASSERT_EQUAL_STRING("steam.pressure_fall_bar_per_ml",
                             NOMINAL[I_STEAM_PRESSURE_FALL].name);
}

/* --- What the description says about the new coefficient ------------------ */

/* Read a file the build named, into `out`. Returns how many bytes were read. */
static size_t read_named_file(const char *path, char *out, size_t capacity)
{
    FILE *const handle = fopen(path, "rb");
    char message[256];

    (void)snprintf(message, sizeof(message), "could not open %s", path);
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, message);

    const size_t used = fread(out, 1u, capacity - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < capacity - 1u);
    out[used] = '\0';
    return used;
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C5: The new coefficient carries its range,
/// origin and assumed error.
/// SOL-PLANT-FLOW-ENERGY-BALANCE.C8: The stepped structure stays admissible with
/// a draw open -- load-time range validation continues to accept every new
/// coefficient.
///
/// The range is the structure's own and is read here the way every other bound
/// in this file is read -- by driving the loader either side of it, which names
/// no structure symbol. A coefficient with no declared range would be accepted
/// at any value, including ones that divide; this asserts that none of the four
/// coefficients the flow term brought with it is in that state.
///
/// Each is checked for the shape its own relation needs rather than for a range
/// in general. Two of them divide, so their ranges have to exclude zero from
/// below; the other two do not divide and are bounded because a value outside
/// the band is a description of something that is not this machine and not
/// water. A single loop asserting "some range exists" would pass on a floor of
/// zero for a divisor, which is the one failure that matters here.
static void test_the_flow_terms_coefficients_carry_enforced_admissible_ranges(void)
{
    /* The two that appear in a denominator, and so may not reach zero. */
    static const size_t DIVIDES[] = {I_BREW_HELD_VOLUME, I_BREW_CONDUCTION_TAU};
    /* And every coefficient the flow term added, divisor or not. */
    static const size_t ALL[] = {I_BREW_HELD_VOLUME, I_BREW_CONDUCTION_TAU, I_WATER_FEED,
                                 I_WATER_HEAT_CAPACITY};

    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];

    all_bounds(low, high);

    for (size_t d = 0u; d < sizeof(DIVIDES) / sizeof(DIVIDES[0]); d++) {
        char message[160];
        (void)snprintf(message, sizeof(message), "%s reaches zero from below",
                       NOMINAL[DIVIDES[d]].name);
        TEST_ASSERT_TRUE_MESSAGE(low[DIVIDES[d]] > 0.0, message);
    }

    for (size_t i = 0u; i < sizeof(ALL) / sizeof(ALL[0]); i++) {
        const size_t index = ALL[i];
        const double minimum = low[index];
        const double maximum = high[index];
        char message[160];

        (void)snprintf(message, sizeof(message), "%s: bounds [%.17g, %.17g]", NOMINAL[index].name,
                       minimum, maximum);
        TEST_ASSERT_TRUE_MESSAGE(maximum > minimum, message);
        TEST_ASSERT_TRUE_MESSAGE(isfinite(maximum), message);

        /* Enforced, not merely declared: either side of it is refused, and the
         * refusal names the coefficient rather than some neighbour. */
        for (int side = 0; side < 2; side++) {
            char text[DESCRIPTION_MAX];
            plant_parameters_t loaded;
            plant_parameter_error_t fault;
            const double outside =
                side == 0 ? minimum - (maximum - minimum) : maximum + (maximum - minimum);

            const size_t used = describe_with_one(text, sizeof(text), index, outside);
            memset(&fault, 0, sizeof(fault));
            TEST_ASSERT_FALSE_MESSAGE(plant_parameters_load(text, used, &loaded, &fault), message);
            TEST_ASSERT_EQUAL(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault);
            TEST_ASSERT_EQUAL_STRING(NOMINAL[index].name, fault.parameter);
        }
    }
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C5: The new coefficient carries its range,
/// origin and assumed error.
///
/// The assumed error is kept after the description is read, so the suite can
/// require the shipped description to declare one for this coefficient rather
/// than leaving it to the build check alone. The origin is not kept -- which
/// values are accounted for is a question about a file -- so that half is
/// check_parameter_origins.py's, and tools/mutate.py holds a defect proving it
/// bites.
static void test_the_shipped_description_declares_an_assumed_error_for_the_new_coefficient(void)
{
    /*
     * Every coefficient the flow term brought with it, including the two water
     * properties. A property of water is still a figure this description chose,
     * and one carrying no declared error would read as exact -- which is a claim
     * nobody is entitled to make about a single number standing in for something
     * that moves with temperature.
     */
    static const char *const REQUIRED[] = {
        "brew.outlet_held_volume_ml",
        "brew.outlet_conduction_time_constant_s",
        "water.feed_temperature_c",
        "water.heat_capacity_j_per_ml_k",
    };

    char text[REFERENCE_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    const size_t used = read_named_file(REFERENCE_DESCRIPTION_PATH, text, sizeof(text));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));

    for (size_t i = 0u; i < sizeof(REQUIRED) / sizeof(REQUIRED[0]); i++) {
        char message[160];
        float assumed = -1.0f;

        (void)snprintf(message, sizeof(message),
                       "the shipped description declares no assumed error for %s", REQUIRED[i]);
        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_budget_for(&budget, REQUIRED[i], &assumed),
                                 message);
        TEST_ASSERT_TRUE(isfinite(assumed));
        /*
         * Above zero. A declared error of nothing is a claim that a coefficient
         * is exact, and none of these is. The figures themselves are judgements
         * argued in the statement beside the description and are not pinned
         * here.
         */
        TEST_ASSERT_TRUE_MESSAGE(assumed > 0.0f, message);
    }
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C6: The description's narrative and its
/// variant carry the new coefficient.
///
/// A coefficient can be added to the list of values and left out of the account
/// of what they mean, and out of the near-copy that establishes the values are
/// read rather than compiled in. Both are separate files and neither is
/// exercised by loading the description, so a suite that only loaded it would
/// pass while the description had stopped describing itself.
static void test_the_statement_and_the_variant_carry_every_coefficient(void)
{
    char statement[STATEMENT_MAX];
    char variant[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;

    (void)read_named_file(REFERENCE_STATEMENT_PATH, statement, sizeof(statement));
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        char message[160];
        (void)snprintf(message, sizeof(message), "%s names nothing for '%s'",
                       REFERENCE_STATEMENT_PATH, NOMINAL[i].name);
        TEST_ASSERT_NOT_NULL_MESSAGE(strstr(statement, NOMINAL[i].name), message);
    }

    /*
     * The variant is accepted by the same loader, which is what establishes it
     * carries the same set of names: a description missing any coefficient the
     * structure requires is refused, and one naming a coefficient the structure
     * does not have is refused too. That is the property the parameters-are-data
     * comparison rests on -- the pair has to differ in a value rather than in
     * which coefficients it mentions.
     */
    const size_t used = read_named_file(REFERENCE_VARIANT_PATH, variant, sizeof(variant));
    memset(&fault, 0, sizeof(fault));
    if (!plant_parameters_load(variant, used, &loaded, &fault)) {
        char message[192];
        (void)snprintf(message, sizeof(message),
                       "%s was refused: fault %d at line %u, coefficient '%s'",
                       REFERENCE_VARIANT_PATH, (int)fault.fault, (unsigned)fault.line,
                       fault.parameter);
        TEST_FAIL_MESSAGE(message);
    }
}


/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// This structure keeps every state the vocabulary names, so every one of them
/// takes a write and reads back what was written. Correcting a reconstruction
/// is what the write exists for, and a state that could not be written could
/// not be corrected.
static void test_every_state_this_structure_keeps_takes_a_write(void)
{
    plant_model_t model;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        float held = 0.0f;
        float read_back = 0.0f;

        TEST_ASSERT_TRUE(plant_model_state(&model, (plant_state_t)state, &held));
        TEST_ASSERT_TRUE(plant_model_set_state(&model, (plant_state_t)state, held + 11.5f));
        TEST_ASSERT_TRUE(plant_model_state(&model, (plant_state_t)state, &read_back));
        TEST_ASSERT_EQUAL_FLOAT(held + 11.5f, read_back);
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// Written to one state, nothing else moves. A write that carried into its
/// neighbours would make a correction to one channel silently a correction to
/// all of them, and the estimator would be acting on states nothing observed.
static void test_writing_one_state_leaves_the_others_where_they_were(void)
{
    plant_model_t model;
    float before[PLANT_STATE_COUNT];

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        TEST_ASSERT_TRUE(plant_model_state(&model, (plant_state_t)state, &before[state]));
    }

    TEST_ASSERT_TRUE(
        plant_model_set_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 71.25f));

    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        float now = 0.0f;
        TEST_ASSERT_TRUE(plant_model_state(&model, (plant_state_t)state, &now));
        if (state == PLANT_STATE_BREW_OUTLET_TEMPERATURE_C) {
            TEST_ASSERT_EQUAL_FLOAT(71.25f, now);
        } else {
            TEST_ASSERT_EQUAL_FLOAT(before[state], now);
        }
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// The refusals the write shares with the read: no instance, an instance that
/// was never initialised, and a state outside the vocabulary. Each changes
/// nothing rather than writing somewhere unintended.
static void test_a_state_written_to_an_instance_that_cannot_take_it_is_refused(void)
{
    plant_model_t model;
    plant_model_t uninitialised;

    memset(&uninitialised, 0, sizeof(uninitialised));
    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        TEST_ASSERT_FALSE(plant_model_set_state(&uninitialised, (plant_state_t)state, 1.0f));
    }
    TEST_ASSERT_FALSE(plant_model_set_state(NULL, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 1.0f));

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    float outlet_before = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &outlet_before));
    TEST_ASSERT_FALSE(plant_model_set_state(&model, (plant_state_t)PLANT_STATE_COUNT, 1.0f));
    TEST_ASSERT_FALSE(plant_model_set_state(&model, (plant_state_t)(PLANT_STATE_COUNT + 1), 1.0f));

    float outlet_after = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &outlet_after));
    TEST_ASSERT_EQUAL_FLOAT(outlet_before, outlet_after);
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// A written state is what the equations carry forward, not a value the next
/// step discards. The water leaving is put somewhere the equations would not
/// have taken it, and the step after is asked whether it started from there.
static void test_a_written_state_is_what_the_next_step_advances_from(void)
{
    plant_model_t model;
    plant_model_t untouched;
    plant_actuation_t heating = {{0u}};

    heating.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = ACTUATION_FULL_SCALE;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(plant_model_init(&untouched, &parameters));

    TEST_ASSERT_TRUE(plant_model_set_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 5.0f));
    TEST_ASSERT_TRUE(plant_model_step(&model, &heating, 0.0f, 100u));
    TEST_ASSERT_TRUE(plant_model_step(&untouched, &heating, 0.0f, 100u));

    float advanced = 0.0f;
    float unwritten = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &advanced));
    TEST_ASSERT_TRUE(
        plant_model_state(&untouched, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &unwritten));

    /* It carried the written value forward: still far below where the same step
     * takes an instance that was not written to, and moved up from where it was
     * put rather than snapping back. */
    TEST_ASSERT_TRUE(advanced < unwritten - 10.0f);
    TEST_ASSERT_TRUE(advanced > 5.0f);
}

/// SOL-PLANT-FLOW-REPORTED.C1: The plant seam names the rate water is drawn as
/// a reported quantity.
///
/// The enumerator exists, sits inside the vocabulary's own count, and is
/// distinct from every other member -- so a consumer can walk the vocabulary
/// and reach it rather than having to know the name. A quantity added to the
/// enum and left out of the count, or duplicated onto another member's value,
/// would be unreachable that way and is what this refuses.
static void test_the_seam_names_the_drawn_rate_as_a_quantity(void)
{
    TEST_ASSERT_TRUE((int)PLANT_QUANTITY_BREW_FLOW_ML_PER_S >= 0);
    TEST_ASSERT_TRUE((int)PLANT_QUANTITY_BREW_FLOW_ML_PER_S < (int)PLANT_QUANTITY_COUNT);

    const plant_quantity_t others[] = {
        PLANT_QUANTITY_BREW_TEMPERATURE_C,
        PLANT_QUANTITY_STEAM_TEMPERATURE_C,
        PLANT_QUANTITY_BREW_PRESSURE_BAR,
        PLANT_QUANTITY_STEAM_PRESSURE_BAR,
        PLANT_QUANTITY_STEAM_DRAW_ML_PER_S,
    };

    /* Every other quantity is listed, not merely a few. A quantity added to the
     * vocabulary and left out of this array escapes the distinctness check
     * silently, and an array that has stopped covering the vocabulary looks
     * exactly like one that passed. */
    TEST_ASSERT_EQUAL_INT_MESSAGE((int)PLANT_QUANTITY_COUNT - 1,
                                  (int)(sizeof(others) / sizeof(others[0])),
                                  "a quantity exists that this array does not name");

    for (size_t i = 0u; i < sizeof(others) / sizeof(others[0]); i++) {
        TEST_ASSERT_TRUE(others[i] != PLANT_QUANTITY_BREW_FLOW_ML_PER_S);
    }
}

/// SOL-PLANT-FLOW-REPORTED.C2: Every plant structure answers the flow quantity.
///
/// Answered rather than refused, on the reference structure. A quantity is the
/// machine's vocabulary and not a structure's, so unlike a state there is no
/// case in which a structure may decline it -- and a consumer that had to test
/// for it before reading is the negotiation the two vocabularies exist to
/// prevent. Checked from rest as well as under a draw, since a structure that
/// answered only once something was commanded would be refusing it in the case
/// a consumer meets first.
static void test_the_reference_structure_answers_the_drawn_rate(void)
{
    plant_model_t model;
    float drawn = -1.0f;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    TEST_ASSERT_TRUE(plant_model_step(&model, &WORKING, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_TRUE(drawn > 0.0f);
}

/* The nominal value the shared description gives one coefficient, by name.
 * Read from the table the description is generated from, so a test comparing
 * against it cannot drift from what was loaded -- and so that no test has to
 * name a field of the structure to find out what it was given. */
static double nominal_value(const char *name)
{
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        if (strcmp(NOMINAL[i].name, name) == 0) {
            return NOMINAL[i].value;
        }
    }
    TEST_FAIL_MESSAGE("no such coefficient in the nominal description");
    return 0.0;
}

/// SOL-PLANT-FLOW-REPORTED.C3: The reported rate follows the pump's commanded
/// level.
///
/// Linear across the range and zero at zero, read against the record's own full
/// scale and the coefficient naming the rate at that full scale. Every level is
/// checked against the figure arithmetic gives rather than against the
/// neighbouring level, so a relation that was monotonic but not proportional --
/// a curve, a dead band, a saturation short of full scale -- fails here rather
/// than passing as "it goes up".
static void test_the_drawn_rate_follows_the_commanded_pump_level(void)
{
    static const uint16_t LEVELS[] = {0u, 1u, ACTUATION_FULL_SCALE / 4u,
                                      ACTUATION_FULL_SCALE / 2u, ACTUATION_FULL_SCALE};

    for (size_t i = 0u; i < sizeof(LEVELS) / sizeof(LEVELS[0]); i++) {
        plant_model_t model;
        plant_actuation_t actuation = {{0u}};
        float drawn = -1.0f;

        actuation.level_permille[ACTUATION_CHANNEL_PUMP] = LEVELS[i];
        TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));

        const float expected = (float)nominal_value("pump.flow_ml_per_s") *
                               ((float)LEVELS[i] / (float)ACTUATION_FULL_SCALE);
        TEST_ASSERT_EQUAL_FLOAT(expected, drawn);
    }
}

/// SOL-PLANT-FLOW-REPORTED.C3: A commanded level of zero reports zero.
///
/// Called out on its own because it is the case a consumer reasons about
/// hardest -- a pump commanded off must not be reported as moving water, or
/// anything watching for a pump that has failed to prime is watching a figure
/// that never reaches zero. Checked after a draw as well as from rest, so a
/// rate that was latched from the previous step rather than recomputed is
/// caught: nothing here carries over.
static void test_a_pump_commanded_off_reports_no_flow(void)
{
    plant_model_t model;
    float drawn = -1.0f;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(plant_model_step(&model, &WORKING, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_TRUE(drawn > 0.0f);

    TEST_ASSERT_TRUE(plant_model_step(&model, &HEATING, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);
}

/// SOL-PLANT-FLOW-REPORTED.C3: The rate is the pump's alone.
///
/// Commanding both heaters at full scale beside the pump reports the same rate
/// as commanding the pump by itself. The relation reads one channel, and a
/// change that fed it from a temperature, a pressure or a second channel would
/// pass every proportionality check above while being wrong about what the
/// figure means.
static void test_the_drawn_rate_is_unmoved_by_the_heaters(void)
{
    plant_model_t pump_only_model;
    plant_model_t everything_model;
    plant_actuation_t pump_only = {{0u}};
    float alone = -1.0f;
    float alongside = -2.0f;

    pump_only.level_permille[ACTUATION_CHANNEL_PUMP] =
        WORKING.level_permille[ACTUATION_CHANNEL_PUMP];

    TEST_ASSERT_TRUE(plant_model_init(&pump_only_model, &parameters));
    TEST_ASSERT_TRUE(plant_model_init(&everything_model, &parameters));

    /* Many steps, so a dependence on a state that has had time to move is
     * reached rather than being sat out at the value both start from. */
    for (int i = 0; i < SHORT_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&pump_only_model, &pump_only, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&everything_model, &WORKING, 0.0f, STEP_MS));
    }

    TEST_ASSERT_TRUE(
        plant_model_quantity(&pump_only_model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &alone));
    TEST_ASSERT_TRUE(
        plant_model_quantity(&everything_model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &alongside));
    TEST_ASSERT_EQUAL_FLOAT(alone, alongside);
}

/// SOL-PLANT-FLOW-REPORTED.C4: The rate the pump moves water at full scale is a
/// described coefficient.
///
/// The shipped description declares an assumed error for it, as every value
/// there does. A coefficient added to the parameter table and left out of the
/// error budget reads as exact, which is a claim nobody is entitled to make
/// about a figure estimated for a pump type from no stated delivery rate. The
/// figure itself is argued in the statement beside the description and is not
/// pinned here.
static void test_the_shipped_description_declares_an_assumed_error_for_the_drawn_rate(void)
{
    char text[REFERENCE_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;
    float assumed = -1.0f;

    const size_t used = read_named_file(REFERENCE_DESCRIPTION_PATH, text, sizeof(text));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));

    TEST_ASSERT_TRUE_MESSAGE(
        plant_parameter_budget_for(&budget, "pump.flow_ml_per_s", &assumed),
        "the shipped description declares no assumed error for pump.flow_ml_per_s");
    TEST_ASSERT_TRUE(isfinite(assumed));
    TEST_ASSERT_TRUE(assumed > 0.0f);
}

/// SOL-PLANT-FLOW-REPORTED.C6: The reported rate is exercised end to end on the
/// host tier.
///
/// A description is loaded as text, a model is initialised from it, the pump is
/// commanded, and the rate is read back through the seam -- the whole path a
/// consumer takes, with no structure field named anywhere in it. The value that
/// comes back is the one the description's own coefficient gives, so a build
/// reading the coefficient from anywhere but the description fails here.
static void test_the_drawn_rate_is_reached_end_to_end_through_the_seam(void)
{
    static const char DESCRIPTION[] = "ambient_temperature_c = 20\n"
                                      "brew.thermal_mass_j_per_k = 420\n"
                                      "brew.heater_power_w = 1200\n"
                                      "brew.loss_w_per_k = 1.5\n"
                                      "brew.outlet_held_volume_ml = 6\n"
                                      "brew.outlet_conduction_time_constant_s = 15\n"
                                      "steam.thermal_mass_j_per_k = 900\n"
                                      "steam.heater_power_w = 1400\n"
                                      "steam.loss_w_per_k = 2.2\n"
                                      "pump.pressure_bar = 9\n"
                                      "pump.flow_ml_per_s = 8\n"
                                      "brew.pressure_time_constant_s = 0.8\n"
                                      "water.feed_temperature_c = 18\n"
                                      "water.heat_capacity_j_per_ml_k = 4.15\n"
                                      "water.latent_heat_j_per_ml = 2000\n"
                                      "steam.saturation_temperature_c = 100\n"
                                      "steam.pressure_bar_per_k = 0.035\n"
                                      "steam.pressure_fall_bar_per_ml = 0.02\n"
                                      "steam.feed_flow_ml_per_s = 5\n";
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;
    plant_actuation_t half_scale = {{0u}};
    float drawn = -1.0f;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

    half_scale.level_permille[ACTUATION_CHANNEL_PUMP] = ACTUATION_FULL_SCALE / 2u;
    TEST_ASSERT_TRUE(plant_model_step(&model, &half_scale, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));

    /* Eight at full scale, commanded at half: exact in binary, so compared as
     * stored rather than within a tolerance. */
    TEST_ASSERT_EQUAL_FLOAT(4.0f, drawn);
}

/// SOL-PLANT-FLOW-REPORTED.C4: The rate the pump moves water at full scale is a
/// described coefficient.
///
/// The statement puts the two pump coefficients together in one place and says
/// they cannot both hold. `pump.pressure_bar` is what the pump makes against a
/// closed outlet and `pump.flow_ml_per_s` is what it delivers into an open
/// path: opposite ends of one characteristic, so a model at full duty reports a
/// pressure and a rate no machine produces together. Each is individually
/// plausible, which is what makes the pair worth a warning -- a reader checking
/// them one at a time finds nothing wrong, and a margin sized against both at
/// once is sized against a case this machine has not got.
///
/// Checked as one line naming both rather than as a phrase, because the wording
/// is the description's to choose and the placement is not: before the rate
/// existed no line named both, so a statement carrying them in separate places
/// has lost the only thing that relates them. Prose in these statements is not
/// hard-wrapped, so one line is one paragraph -- which is why splitting on the
/// newline is splitting on the paragraph.
static void test_the_statement_warns_that_the_two_pump_coefficients_exclude_each_other(void)
{
    char statement[STATEMENT_MAX];
    (void)read_named_file(REFERENCE_STATEMENT_PATH, statement, sizeof(statement));

    bool paragraph_names_both = false;
    for (char *block = strtok(statement, "\n"); block != NULL; block = strtok(NULL, "\n")) {
        if (strstr(block, "pump.pressure_bar") != NULL &&
            strstr(block, "pump.flow_ml_per_s") != NULL) {
            paragraph_names_both = true;
            break;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(paragraph_names_both,
                             "no paragraph of the statement names both pump coefficients, so "
                             "nothing there says they are ends of one characteristic and cannot "
                             "both be reached");
}

/* --- The energy the drawn water carries out of the casting ---------------- */

/*
 * The nominal coefficients as numbers, so a test can change the ones it is
 * about and leave the rest where the shared table put them.
 */
static void nominal_values(double *values)
{
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        values[i] = NOMINAL[i].value;
    }
}

/* An instance described by exactly these values, reached through the loader the
 * way every other test here reaches one -- no structure field is named. */
static void model_from(plant_model_t *model, const double *values)
{
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    const size_t used = describe_values(values, text, sizeof(text));

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(model, &loaded));
}

/* A command on the brew heater and the pump, in parts per thousand of each. */
static plant_actuation_t commanding(uint16_t heater_permille, uint16_t pump_permille)
{
    plant_actuation_t actuation = {{0u}};

    actuation.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = heater_permille;
    actuation.level_permille[ACTUATION_CHANNEL_PUMP] = pump_permille;
    return actuation;
}

/* Put an instance where a test wants it to start from, through the seam. */
static void place(plant_model_t *model, float casting_c, float outlet_c)
{
    TEST_ASSERT_TRUE(
        plant_model_set_state(model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, casting_c));
    TEST_ASSERT_TRUE(plant_model_set_state(model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, outlet_c));
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C1: The casting loses energy to the water drawn
/// through it -- with a draw open and the heater off, the heated mass falls
/// faster than the same structure falls with no draw.
///
/// Two instances of one description, started at the same temperature well above
/// ambient with the element off, stepped side by side with the pump the only
/// difference between them. The one being drawn through has to fall faster at
/// every step, not merely end up lower: a term that only bit once, or one that
/// acted on the wrong sign of the difference, can produce a lower endpoint
/// without producing a steeper fall throughout.
static void test_a_draw_cools_the_heated_mass_faster_than_no_draw(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t drawn;
    plant_model_t undrawn;

    nominal_values(values);
    model_from(&drawn, values);
    model_from(&undrawn, values);

    place(&drawn, 90.0f, 90.0f);
    place(&undrawn, 90.0f, 90.0f);

    const plant_actuation_t with_draw = commanding(0u, ACTUATION_FULL_SCALE);
    const plant_actuation_t without_draw = commanding(0u, 0u);

    float previous_drawn = 90.0f;
    float previous_undrawn = 90.0f;

    for (int step = 0; step < SHORT_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&drawn, &with_draw, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&undrawn, &without_draw, 0.0f, STEP_MS));

        const float now_drawn = heated_mass(&drawn);
        const float now_undrawn = heated_mass(&undrawn);

        /* Both are cooling -- so what is compared below is two falls rather than
         * a fall against a rise. */
        TEST_ASSERT_TRUE(now_drawn < previous_drawn);
        TEST_ASSERT_TRUE(now_undrawn < previous_undrawn);

        /* And this step took more out of the one being drawn through than out of
         * the one that is not. */
        TEST_ASSERT_TRUE((previous_drawn - now_drawn) > (previous_undrawn - now_undrawn));

        previous_drawn = now_drawn;
        previous_undrawn = now_undrawn;
    }

    /* By a margin nobody could mistake for rounding: the drawn rate here carries
     * far more per kelvin than the loss coefficient does. */
    TEST_ASSERT_TRUE(previous_undrawn - previous_drawn > 10.0f);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C1: The casting loses energy to the water drawn
/// through it -- with the heater holding, the droop under draw is larger than
/// the model produces today.
/// SOL-PLANT-FLOW-ENERGY-BALANCE.C7: The heat a unit of drawn water carries is a
/// described coefficient -- the volumetric heat capacity of water, appearing in
/// the relations rather than folded into another constant.
///
/// Held under a constant element and a constant draw until it stops moving, the
/// casting settles where the energy balance puts it and not merely lower than it
/// used to. The figure compared against is arithmetic a reader can redo from the
/// coefficient table: what the element delivers equals what the loss coefficient
/// carries to ambient plus what the drawn volume carries away, and the second of
/// those is the drawn rate times the volumetric heat capacity times how far the
/// water leaving sits above the water arriving.
///
/// That is the whole of what makes this a check on the coefficient rather than
/// on the direction of an inequality. A term that used a heat capacity per unit
/// mass, or that folded a wrong constant into the drawn rate, lands at a
/// different settling temperature and fails here while passing every ordering
/// test above.
static void test_the_settled_droop_is_the_energy_balance_the_coefficients_state(void)
{
    /* Two heat capacities, so the settling point moves with the coefficient
     * rather than happening to agree at one value. */
    static const double CAPACITIES[] = {4.15, 2.0};

    for (size_t c = 0u; c < sizeof(CAPACITIES) / sizeof(CAPACITIES[0]); c++) {
        double values[COEFFICIENT_COUNT];
        plant_model_t model;

        nominal_values(values);
        values[I_WATER_HEAT_CAPACITY] = CAPACITIES[c];
        model_from(&model, values);

        /* Long enough that the slowest admissible case here is settled rather
         * than still on its way, so what is compared is a balance and not a
         * point on a transient. */
        const plant_actuation_t working = commanding(ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE);
        for (int step = 0; step < SETTLED_STEPS; step++) {
            TEST_ASSERT_TRUE(plant_model_step(&model, &working, 0.0f, STEP_MS));
        }

        const double drawn = values[I_PUMP_FLOW];
        const double carried_w_per_k = drawn * CAPACITIES[c];
        const double settled =
            (values[I_BREW_POWER] + values[I_BREW_LOSS] * values[I_AMBIENT] +
             carried_w_per_k * values[I_WATER_FEED]) /
            (values[I_BREW_LOSS] + carried_w_per_k);

        const double got = (double)heated_mass(&model);
        if (!(fabs(got - settled) < 0.05)) {
            char message[220];
            (void)snprintf(message, sizeof(message),
                           "at %.9g J/(mL K): settled at %.9g, the balance gives %.9g",
                           CAPACITIES[c], got, settled);
            TEST_FAIL_MESSAGE(message);
        }

        /* And far below where the same element holds the same casting with the
         * pump closed, which is the droop this term exists to produce. */
        const double without_draw =
            values[I_AMBIENT] + values[I_BREW_POWER] / values[I_BREW_LOSS];
        TEST_ASSERT_TRUE(got < without_draw - 100.0);
    }
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C1: The steam mass is out of scope and gains no
/// such term.
///
/// The pump is on the brew path. Commanding it must leave the steam mass exactly
/// where the same run leaves it with the pump closed -- byte for byte, because
/// the steam relation shares no arithmetic with the coffee side and a difference
/// of one bit would mean it had started to. A term written from the drawn rate
/// onto the steam mass would be the coffee side's water leaving through the
/// steam wand.
static void test_the_steam_mass_gains_no_term_from_the_draw(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t drawn;
    plant_model_t undrawn;

    nominal_values(values);
    model_from(&drawn, values);
    model_from(&undrawn, values);

    const plant_actuation_t with_draw = {
        {ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE}};
    const plant_actuation_t without_draw = {{ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, 0u}};

    for (int step = 0; step < TRAJECTORY_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&drawn, &with_draw, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&undrawn, &without_draw, 0.0f, STEP_MS));
    }

    float steam_drawn = 0.0f;
    float steam_undrawn = 0.0f;
    TEST_ASSERT_TRUE(plant_model_quantity(&drawn, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &steam_drawn));
    TEST_ASSERT_TRUE(
        plant_model_quantity(&undrawn, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &steam_undrawn));
    TEST_ASSERT_EQUAL_MEMORY(&steam_undrawn, &steam_drawn, sizeof(float));

    /* And the coffee side did move, so the equality above is the steam mass
     * being left alone rather than the draw doing nothing at all. */
    TEST_ASSERT_TRUE(heated_mass(&drawn) < heated_mass(&undrawn) - 100.0f);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C2: The energy removed is written through the
/// temperature of the water leaving -- with the draw open, the outlet state
/// enters the casting's own trajectory, which it cannot do in relations that
/// take the difference at the casting.
///
/// The sharpest form the criterion has: two instances identical in every
/// coefficient and identical in the casting, differing only in where the water
/// leaving has been placed, stepped once. With a draw open the castings come
/// apart, and in the direction the physics requires -- the hotter the water
/// leaving, the more energy it takes with it, so the hotter outlet leaves the
/// colder casting. Relations that took the difference at the casting would leave
/// the two castings identical, which is exactly what the pump-closed half of
/// this test shows they are when nothing is being drawn.
static void test_the_casting_depends_on_where_the_water_leaving_sits(void)
{
    double values[COEFFICIENT_COUNT];

    nominal_values(values);

    for (int drawing = 0; drawing < 2; drawing++) {
        plant_model_t cool_outlet;
        plant_model_t warm_outlet;

        model_from(&cool_outlet, values);
        model_from(&warm_outlet, values);

        /* One casting temperature, two temperatures for the water leaving it. */
        place(&cool_outlet, 80.0f, 30.0f);
        place(&warm_outlet, 80.0f, 75.0f);

        const plant_actuation_t actuation =
            commanding(0u, drawing ? ACTUATION_FULL_SCALE : (uint16_t)0u);
        TEST_ASSERT_TRUE(plant_model_step(&cool_outlet, &actuation, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&warm_outlet, &actuation, 0.0f, STEP_MS));

        const float after_cool = heated_mass(&cool_outlet);
        const float after_warm = heated_mass(&warm_outlet);

        if (drawing) {
            /* The warmer outlet carried more away, so its casting is colder --
             * and by a margin, not by a bit. */
            TEST_ASSERT_TRUE(after_warm < after_cool - 0.1f);
        } else {
            /*
             * Nothing drawn, so the term is multiplied by an exact zero and the
             * casting cannot have seen the outlet at all. Compared byte for byte
             * rather than within a tolerance: a term that leaked in through a
             * near-zero rather than a zero would show here and nowhere else.
             */
            TEST_ASSERT_EQUAL_MEMORY(&after_cool, &after_warm, sizeof(float));
        }
    }
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C2: The energy removed is written through the
/// temperature of the water leaving -- perturbing the outlet time constant alone
/// changes the casting's own trajectory.
///
/// The consequence the criterion asks to be asserted directly, and the one that
/// makes the outlet coefficients reachable from the only sensor this machine
/// has. The lag is perturbed through the no-draw conduction constant, which
/// enters the outlet relation and nothing else; with a draw open it moves the
/// casting by degrees, and with the pump closed it moves it by nothing a reader
/// could distinguish from the rounding of two spellings of one closed form.
static void test_the_outlet_time_constant_reaches_the_casting_only_under_a_draw(void)
{
    static const double CONDUCTION_TAUS[] = {2.0, 60.0};

    for (int drawing = 0; drawing < 2; drawing++) {
        float castings[sizeof(CONDUCTION_TAUS) / sizeof(CONDUCTION_TAUS[0])];

        for (size_t t = 0u; t < sizeof(CONDUCTION_TAUS) / sizeof(CONDUCTION_TAUS[0]); t++) {
            double values[COEFFICIENT_COUNT];
            plant_model_t model;

            nominal_values(values);
            values[I_BREW_CONDUCTION_TAU] = CONDUCTION_TAUS[t];
            model_from(&model, values);

            /*
             * A tenth of full scale rather than all of it. At a full draw the
             * held volume is turned over so fast that the conduction constant
             * barely enters the relation it shares -- which is the relation
             * behaving as it should, and would make a poor place to look for the
             * constant's effect. A modest draw is where the two terms are
             * comparable, and it is also the draw a machine actually pulls a
             * shot at.
             */
            const plant_actuation_t actuation = commanding(
                ACTUATION_FULL_SCALE, drawing ? (uint16_t)(ACTUATION_FULL_SCALE / 10u)
                                              : (uint16_t)0u);
            for (int step = 0; step < TRANSIENT_STEPS; step++) {
                TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, STEP_MS));
            }
            castings[t] = heated_mass(&model);
        }

        const double moved = fabs((double)castings[0] - (double)castings[1]);
        char message[200];
        (void)snprintf(message, sizeof(message),
                       "%s a draw, the casting moved %.9g K when only the outlet constant changed",
                       drawing ? "with" : "without", moved);

        if (drawing) {
            TEST_ASSERT_TRUE_MESSAGE(moved > 1.0, message);
        } else {
            /*
             * Not byte-for-byte here, and the reason is worth being exact about.
             * With nothing drawn the pair separates back into two independent
             * relations and the casting's answer is the same closed form it
             * always was -- but the coupled step reaches that closed form
             * through arithmetic that has the outlet's rate in it, so the last
             * few bits move with a coefficient the mathematics has cancelled
             * out. A thousandth of a kelvin is far below anything a machine
             * means and far above the rounding, so a real dependence hiding in
             * this case fails here.
             */
            TEST_ASSERT_TRUE_MESSAGE(moved < 1.0e-3, message);
        }
    }
}

/*
 * The pair of relations the structure integrates, written out here from the
 * description rather than taken from the structure, and stepped with a
 * fourth-order Runge-Kutta at a step far shorter than anything the seam is
 * driven with. It is an approximation where the structure's own step is not,
 * which is the point: an independent answer, arrived at by a method with
 * nothing in common with a closed form, is what a closed form can be wrong
 * against.
 */
typedef struct {
    double casting_c;
    double outlet_c;
} pair_t;

static pair_t pair_rate(const double *values, double duty, double drawn, pair_t state)
{
    const double carried = drawn * values[I_WATER_HEAT_CAPACITY];
    const double approach =
        drawn / values[I_BREW_HELD_VOLUME] + 1.0 / values[I_BREW_CONDUCTION_TAU];
    pair_t rate;

    rate.casting_c = (values[I_BREW_POWER] * duty -
                      values[I_BREW_LOSS] * (state.casting_c - values[I_AMBIENT]) -
                      carried * (state.outlet_c - values[I_WATER_FEED])) /
                     values[I_BREW_MASS];
    rate.outlet_c = approach * (state.casting_c - state.outlet_c);
    return rate;
}

static pair_t pair_offset(pair_t state, pair_t rate, double by)
{
    pair_t moved;

    moved.casting_c = state.casting_c + rate.casting_c * by;
    moved.outlet_c = state.outlet_c + rate.outlet_c * by;
    return moved;
}

static pair_t integrated(const double *values, double duty, double drawn, pair_t state,
                         double seconds, int substeps)
{
    const double h = seconds / (double)substeps;

    for (int i = 0; i < substeps; i++) {
        const pair_t k1 = pair_rate(values, duty, drawn, state);
        const pair_t k2 = pair_rate(values, duty, drawn, pair_offset(state, k1, h / 2.0));
        const pair_t k3 = pair_rate(values, duty, drawn, pair_offset(state, k2, h / 2.0));
        const pair_t k4 = pair_rate(values, duty, drawn, pair_offset(state, k3, h));

        state.casting_c += (h / 6.0) * (k1.casting_c + 2.0 * k2.casting_c + 2.0 * k3.casting_c +
                                        k4.casting_c);
        state.outlet_c +=
            (h / 6.0) * (k1.outlet_c + 2.0 * k2.outlet_c + 2.0 * k3.outlet_c + k4.outlet_c);
    }
    return state;
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C3: The casting and the outlet advance as a
/// coupled pair, by the exact solution of the coupled system rather than a
/// bounded approximation.
///
/// Compared against the pair integrated independently to a far finer resolution
/// than the structure is asked to work at. Three regimes are driven, because the
/// closed form has three shapes to be wrong in: an ordinary machine where the
/// two modes are well separated, a light casting under a fierce draw where the
/// pair oscillates, and coefficients arranged so the two modes coincide exactly
/// -- the case a form built on the difference between them divides by nothing
/// at.
///
/// The tolerance is on the distance travelled rather than on the temperature, so
/// a step that moved almost nothing cannot pass by being nearly right about
/// where it started.
static void test_the_coupled_step_matches_the_pair_integrated_independently(void)
{
    static const uint32_t INTERVALS_MS[] = {10u, 100u, 1000u};

    for (int regime = 0; regime < 3; regime++) {
        double values[COEFFICIENT_COUNT];

        nominal_values(values);
        if (regime == 1) {
            /* A casting light enough that the water it is chasing pulls it
             * about: the pair's discriminant goes negative here. */
            values[I_BREW_MASS] = 20.0;
        } else if (regime == 2) {
            /*
             * The two modes made to coincide. With the pump closed the pair's
             * modes are the casting's own rate and the outlet's own rate, so
             * setting the second equal to the first is arithmetic rather than a
             * search: a loss of 1.5 W/K on 300 J/K is 0.005 per second, and so
             * is a conduction constant of 200 seconds.
             */
            values[I_BREW_MASS] = 300.0;
            values[I_BREW_LOSS] = 1.5;
            values[I_BREW_CONDUCTION_TAU] = 200.0;
        }

        const uint16_t pump = regime == 2 ? (uint16_t)0u : ACTUATION_FULL_SCALE;
        const double drawn = regime == 2 ? 0.0 : values[I_PUMP_FLOW];
        const double duty = 1.0;
        const plant_actuation_t actuation = commanding(ACTUATION_FULL_SCALE, pump);

        for (size_t i = 0u; i < sizeof(INTERVALS_MS) / sizeof(INTERVALS_MS[0]); i++) {
            plant_model_t model;
            pair_t reference;

            model_from(&model, values);
            place(&model, 35.0f, 25.0f);
            reference.casting_c = 35.0;
            reference.outlet_c = 25.0;

            const double seconds = (double)INTERVALS_MS[i] / 1000.0;
            for (int step = 0; step < 8; step++) {
                TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, INTERVALS_MS[i]));
                reference = integrated(values, duty, drawn, reference, seconds, 4000);
            }

            const double casting_travelled = fabs(reference.casting_c - 35.0);
            const double outlet_travelled = fabs(reference.outlet_c - 25.0);
            const double casting_error = fabs((double)heated_mass(&model) - reference.casting_c);
            const double outlet_error = fabs((double)outlet(&model) - reference.outlet_c);

            if (!(casting_error < 1.0e-4 * (casting_travelled + 1.0)) ||
                !(outlet_error < 1.0e-4 * (outlet_travelled + 1.0))) {
                char message[260];
                (void)snprintf(message, sizeof(message),
                               "regime %d at %u ms: casting %.9g against %.9g, water %.9g against "
                               "%.9g",
                               regime, (unsigned)INTERVALS_MS[i], (double)heated_mass(&model),
                               reference.casting_c, (double)outlet(&model), reference.outlet_c);
                TEST_FAIL_MESSAGE(message);
            }
        }
    }
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C3: The pair is advanced by the exact solution
/// over the interval the seam declares, rather than by subdividing it.
///
/// What being exact over a step means operationally: the same stretch of time
/// gives the same answer however it is cut up. One step of a second, ten of a
/// tenth and a hundred of a hundredth land in the same place to within the
/// rounding of single precision. A method carrying any truncation error at all
/// would separate these three, and would separate them further the longer the
/// step -- which is also what would make somebody reach for a shorter interval
/// to hide it.
static void test_the_pair_lands_in_the_same_place_however_the_step_is_cut(void)
{
    static const uint32_t INTERVALS_MS[] = {1000u, 100u, 10u};
    static const int REPEATS[] = {1, 10, 100};

    double values[COEFFICIENT_COUNT];
    float castings[sizeof(INTERVALS_MS) / sizeof(INTERVALS_MS[0])];
    float outlets[sizeof(INTERVALS_MS) / sizeof(INTERVALS_MS[0])];

    nominal_values(values);

    for (size_t i = 0u; i < sizeof(INTERVALS_MS) / sizeof(INTERVALS_MS[0]); i++) {
        plant_model_t model;
        const plant_actuation_t actuation = commanding(ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE);

        model_from(&model, values);
        place(&model, 30.0f, 22.0f);
        /* Ten seconds, cut three ways. */
        for (int repeat = 0; repeat < REPEATS[i] * 10; repeat++) {
            TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, INTERVALS_MS[i]));
        }
        castings[i] = heated_mass(&model);
        outlets[i] = outlet(&model);
    }

    for (size_t i = 1u; i < sizeof(INTERVALS_MS) / sizeof(INTERVALS_MS[0]); i++) {
        char message[220];
        const double casting_gap = fabs((double)castings[i] - (double)castings[0]);
        const double outlet_gap = fabs((double)outlets[i] - (double)outlets[0]);

        (void)snprintf(message, sizeof(message),
                       "%u ms gave %.9g / %.9g where %u ms gave %.9g / %.9g",
                       (unsigned)INTERVALS_MS[i], (double)castings[i], (double)outlets[i],
                       (unsigned)INTERVALS_MS[0], (double)castings[0], (double)outlets[0]);
        TEST_ASSERT_TRUE_MESSAGE(casting_gap < 1.0e-3, message);
        TEST_ASSERT_TRUE_MESSAGE(outlet_gap < 1.0e-3, message);
    }

    /* And the stretch actually went somewhere, so agreement is agreement about
     * a trajectory rather than about a model that never moved. */
    TEST_ASSERT_TRUE(castings[0] > 35.0f);
}

/*
 * How much of the gap between the casting and the water leaving is closed over
 * `seconds` at a given pump level, with the casting held as still as an
 * admissible description can hold it.
 *
 * The thermal mass is put at the top of its declared range and the element left
 * off, so what the outlet relaxes towards barely moves and the fraction below is
 * the outlet relation's own behaviour rather than a race between two moving
 * states. It is not held exactly still -- nothing admissible would do that --
 * which is why what is compared against the closed form carries a tolerance
 * rather than being compared as stored.
 */
static double gap_closed_at(uint16_t pump_permille, double seconds, double *effective_tau_s)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t model;

    nominal_values(values);
    values[I_BREW_MASS] = 100000.0;
    model_from(&model, values);
    place(&model, 90.0f, 20.0f);

    const plant_actuation_t actuation = commanding(0u, pump_permille);
    const int steps = (int)((seconds * 1000.0) / (double)STEP_MS);
    for (int step = 0; step < steps; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, STEP_MS));
    }

    if (effective_tau_s != NULL) {
        const double drawn =
            values[I_PUMP_FLOW] * ((double)pump_permille / (double)ACTUATION_FULL_SCALE);
        *effective_tau_s = 1.0 / (drawn / values[I_BREW_HELD_VOLUME] +
                                  1.0 / values[I_BREW_CONDUCTION_TAU]);
    }
    return ((double)outlet(&model) - 20.0) / (90.0 - 20.0);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C4: The outlet time constant shortens as the
/// draw increases -- the constant becomes a held volume divided by the drawn
/// rate, verified by comparing settling behaviour at two draw rates.
///
/// Two rates, and the comparison is against the constant each one implies rather
/// than against the other. A relation that merely got faster with flow -- the
/// square of it, the square root of it, a different volume -- would satisfy an
/// ordering test and fail this one, because what is checked is how far the
/// relaxation has travelled after a fixed time against what a held volume
/// divided by that rate says it should have.
static void test_the_outlet_settles_faster_the_harder_the_draw(void)
{
    static const uint16_t LEVELS[] = {ACTUATION_FULL_SCALE / 4u, ACTUATION_FULL_SCALE};
    static const double SECONDS = 3.0;

    double closed[sizeof(LEVELS) / sizeof(LEVELS[0])];

    for (size_t i = 0u; i < sizeof(LEVELS) / sizeof(LEVELS[0]); i++) {
        double tau = 0.0;

        closed[i] = gap_closed_at(LEVELS[i], SECONDS, &tau);

        const double expected = 1.0 - exp(-SECONDS / tau);
        if (!(fabs(closed[i] - expected) < 0.02)) {
            char message[220];
            (void)snprintf(message, sizeof(message),
                           "at level %u the water closed %.9g of the gap; a constant of %.9g s "
                           "gives %.9g",
                           (unsigned)LEVELS[i], closed[i], tau, expected);
            TEST_FAIL_MESSAGE(message);
        }
    }

    /* And the harder draw got further, which is the direction the criterion
     * names and which the two closed-form comparisons above do not state on
     * their own. */
    TEST_ASSERT_TRUE(closed[1] > closed[0] + 0.05);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C5: A closed draw leaves the outlet relation
/// defined at its conduction limit -- stepping with the pump at zero produces
/// the no-draw constant exactly, with no guard and no special-case branch.
///
/// Two things, and they are separate. The first is the value: with the pump
/// closed the relaxation is the one the conduction constant alone gives, checked
/// against the closed form rather than against another run. The second is that
/// there is no seam at zero -- the levels below approach a closed pump from
/// above and what they produce approaches the closed-pump answer smoothly, so a
/// branch taken at or near zero would show up as a step in this sequence rather
/// than having to be read out of the source.
static void test_a_closed_pump_relaxes_at_the_conduction_constant(void)
{
    static const double SECONDS = 3.0;
    /* A closed pump, then levels approaching it from above by decades. */
    static const uint16_t LEVELS[] = {0u, 1u, 10u, 100u};

    double at_rest_tau = 0.0;
    const double at_rest = gap_closed_at(0u, SECONDS, &at_rest_tau);

    /* The conduction constant itself, and nothing else: the drawn term is zero,
     * so the reciprocal sum is the reciprocal of that constant alone. */
    TEST_ASSERT_TRUE(fabs(at_rest_tau - NOMINAL[I_BREW_CONDUCTION_TAU].value) < 1.0e-9);

    const double expected = 1.0 - exp(-SECONDS / at_rest_tau);
    if (!(fabs(at_rest - expected) < 0.005)) {
        char message[200];
        (void)snprintf(message, sizeof(message),
                       "with the pump closed the water closed %.9g of the gap; the conduction "
                       "constant gives %.9g",
                       at_rest, expected);
        TEST_FAIL_MESSAGE(message);
    }

    /*
     * And no step at zero. Each level is a tenth of the next, so what the drawn
     * term contributes falls by a decade each time and the answers have to close
     * on the closed-pump one geometrically. A guard, a floor, or a branch that
     * substituted one relation for another at some small rate would break that
     * ordering.
     */
    double distances[sizeof(LEVELS) / sizeof(LEVELS[0])];
    for (size_t i = 1u; i < sizeof(LEVELS) / sizeof(LEVELS[0]); i++) {
        distances[i] = fabs(gap_closed_at(LEVELS[i], SECONDS, NULL) - at_rest);
    }
    for (size_t i = sizeof(LEVELS) / sizeof(LEVELS[0]) - 1u; i > 1u; i--) {
        char message[240];

        (void)snprintf(message, sizeof(message),
                       "level %u sits %.9g from the closed-pump answer, and level %u -- ten times "
                       "the draw -- sits %.9g",
                       (unsigned)LEVELS[i - 1u], distances[i - 1u], (unsigned)LEVELS[i],
                       distances[i]);
        /* A decade less draw, and several times closer: a floor under the drawn
         * term, or a branch substituting one relation for another below some
         * rate, stops this shrinking. */
        TEST_ASSERT_TRUE_MESSAGE(distances[i - 1u] < distances[i] / 5.0, message);
    }

    /* And the smallest non-zero draw the vocabulary can express has all but
     * arrived, which is what having no discontinuity at zero looks like from
     * outside. */
    TEST_ASSERT_TRUE(distances[1] < 0.01);
}

/*
 * Where the casting settles under a full draw and a full element, for one
 * coefficient moved off the nominal table.
 */
static double settled_casting_with(size_t index, double value)
{
    plant_model_t model;
    double values[COEFFICIENT_COUNT];
    const plant_actuation_t working = commanding(ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE);

    nominal_values(values);
    values[index] = value;
    model_from(&model, values);
    for (int step = 0; step < SETTLED_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &working, 0.0f, STEP_MS));
    }
    return (double)heated_mass(&model);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C6: The temperature the water enters at is a
/// coefficient in its own right -- the relations read it rather than reusing
/// ambient.
///
/// Two descriptions differing in the feed temperature and in nothing else, the
/// ambient identical between them. A structure that reached for ambient where
/// the relation names the feed would produce the same trajectory twice, which is
/// the substitution this exists to refuse -- and it is a substitution that would
/// look right on this machine, whose tank stands in the same room the ambient
/// describes.
///
/// Then the same displacement applied to the other one. Both bite, which is what
/// makes them two coefficients rather than one, and under a draw this size the
/// feed bites far harder: what carries energy away with the water is a volume
/// rate times a heat capacity, and what carries it to the room is a loss
/// coefficient an order smaller. A structure using one figure for both could not
/// produce two different numbers here, let alone these two.
static void test_the_feed_temperature_is_read_rather_than_ambient(void)
{
    static const double DISPLACEMENT = 20.0;

    const double nominal = settled_casting_with(I_WATER_FEED, NOMINAL[I_WATER_FEED].value);
    const double warmer_feed =
        settled_casting_with(I_WATER_FEED, NOMINAL[I_WATER_FEED].value + DISPLACEMENT);
    const double warmer_room =
        settled_casting_with(I_AMBIENT, NOMINAL[I_AMBIENT].value + DISPLACEMENT);

    const double moved_by_feed = warmer_feed - nominal;
    const double moved_by_room = warmer_room - nominal;
    char message[240];

    (void)snprintf(message, sizeof(message),
                   "%.9g K on the feed moved the casting %.9g K; the same on the room moved it "
                   "%.9g K",
                   DISPLACEMENT, moved_by_feed, moved_by_room);

    /* Warmer water arriving means less energy leaving with it, so the casting
     * settles higher -- in that direction and not the other. */
    TEST_ASSERT_TRUE_MESSAGE(moved_by_feed > 1.0, message);
    TEST_ASSERT_TRUE_MESSAGE(moved_by_room > 0.0, message);
    TEST_ASSERT_TRUE_MESSAGE(moved_by_feed > 4.0 * moved_by_room, message);

    /* And the figure the balance gives for the feed's share, so this is the
     * coefficient's magnitude rather than only its presence. The room's share is
     * the loss coefficient's and the feed's is the drawn rate times the heat
     * capacity, over the sum of the two. */
    const double carried_w_per_k =
        NOMINAL[I_PUMP_FLOW].value * NOMINAL[I_WATER_HEAT_CAPACITY].value;
    const double expected =
        DISPLACEMENT * carried_w_per_k / (NOMINAL[I_BREW_LOSS].value + carried_w_per_k);
    TEST_ASSERT_TRUE_MESSAGE(fabs(moved_by_feed - expected) < 0.1, message);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C7: The heat a unit of drawn water carries is a
/// described coefficient -- the volumetric heat capacity of water, converting a
/// volume rate into an energy flux.
///
/// The term's shape read straight off one step. The casting is placed at ambient
/// with the element off, so the loss to the room is exactly nothing and the only
/// thing moving it is the water; the water leaving is placed above the feed by a
/// known amount. What the casting does over that step is then the drawn rate
/// times the volumetric heat capacity times that difference, divided by the
/// thermal mass, and nothing else -- so a coefficient per unit mass, a factor
/// folded into the drawn rate, or a difference taken against ambient instead of
/// the feed all land somewhere this comparison refuses.
static void test_the_drawn_power_is_the_volume_rate_times_the_heat_capacity(void)
{
    static const double CAPACITIES[] = {4.15, 3.0};
    static const double OUTLET_C = 70.0;

    for (size_t c = 0u; c < sizeof(CAPACITIES) / sizeof(CAPACITIES[0]); c++) {
        double values[COEFFICIENT_COUNT];
        plant_model_t model;

        nominal_values(values);
        values[I_WATER_HEAT_CAPACITY] = CAPACITIES[c];
        model_from(&model, values);
        place(&model, (float)values[I_AMBIENT], (float)OUTLET_C);

        const plant_actuation_t drawing_only = commanding(0u, ACTUATION_FULL_SCALE);
        const uint32_t interval_ms = 1u;
        TEST_ASSERT_TRUE(plant_model_step(&model, &drawing_only, 0.0f, interval_ms));

        const double seconds = (double)interval_ms / 1000.0;
        const double removed_w = values[I_PUMP_FLOW] * CAPACITIES[c] *
                                 (OUTLET_C - values[I_WATER_FEED]);
        const double expected = values[I_AMBIENT] - (removed_w * seconds) / values[I_BREW_MASS];
        const double got = (double)heated_mass(&model);

        /*
         * A step of a millisecond, so the difference between the rate at the
         * start of it and the exact traverse across it is far below the
         * tolerance -- what is being compared is the term's magnitude and not
         * the integration, which the coupled-step test covers on its own.
         */
        if (!(fabs(got - expected) < 1.0e-4)) {
            char message[240];
            (void)snprintf(message, sizeof(message),
                           "at %.9g J/(mL K): the casting reached %.9g, the drawn power gives %.9g",
                           CAPACITIES[c], got, expected);
            TEST_FAIL_MESSAGE(message);
        }
    }
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C8: The stepped structure stays admissible with
/// a draw open -- stepping with the pump commanded closed to full scale against
/// a cold casting leaves every state finite and non-diverging across the seam's
/// declared interval.
///
/// Separate from the range validation above, and separate from the check that an
/// interval and an actuation are admissible, neither of which has any notion of
/// where a state is. What is asked here is about the trajectory: a step taken as
/// though the rate held across it does not merely lose accuracy on a long
/// interval -- it alternates sign and grows without bound -- and the coupled
/// pair has two modes to do that in rather than one.
///
/// The pump is driven closed to full scale and back every step, which is the
/// worst thing a caller can do to a relation whose time constant depends on the
/// commanded rate: every step changes what the pair is. The casting starts cold,
/// which is where a machine starts and where the draw's contribution is largest
/// against the element's. Every interval the seam accepts is covered, from a
/// millisecond to a minute.
///
/// Non-diverging is asserted against a band the coefficients fix rather than
/// against a number: the casting cannot end up hotter than the element alone
/// would hold it nor colder than the coldest thing feeding it, and the water
/// cannot end up outside the range the casting travelled. The band is widened by
/// its own width to admit the overshoot these relations genuinely produce, which
/// is a property of the pair rather than of the integration.
static void test_a_toggling_draw_against_a_cold_casting_stays_bounded(void)
{
    static const uint32_t INTERVALS_MS[] = {1u, 10u, 100u, 1000u, 60000u};
    static const int STEPS = 500;

    double values[COEFFICIENT_COUNT];

    nominal_values(values);

    const double coldest = fmin(values[I_AMBIENT], values[I_WATER_FEED]);
    const double hottest = values[I_AMBIENT] + values[I_BREW_POWER] / values[I_BREW_LOSS];
    const double width = hottest - coldest;
    const double floor_c = coldest - width;
    const double ceiling_c = hottest + width;

    for (size_t i = 0u; i < sizeof(INTERVALS_MS) / sizeof(INTERVALS_MS[0]); i++) {
        plant_model_t model;

        model_from(&model, values);

        for (int step = 0; step < STEPS; step++) {
            const plant_actuation_t actuation =
                commanding(ACTUATION_FULL_SCALE, (step % 2 == 0) ? ACTUATION_FULL_SCALE
                                                                 : (uint16_t)0u);
            TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, INTERVALS_MS[i]));

            float states[PLANT_STATE_COUNT];
            read_all_states(&model, states);
            for (int s = 0; s < PLANT_STATE_COUNT; s++) {
                char message[240];

                (void)snprintf(message, sizeof(message),
                               "at %u ms, step %d: state %d reached %.9g, outside [%.9g, %.9g]",
                               (unsigned)INTERVALS_MS[i], step, s, (double)states[s], floor_c,
                               ceiling_c);
                TEST_ASSERT_TRUE_MESSAGE(isfinite(states[s]), message);
                /* The two pressures are in bar and are bounded by their own
                 * relations, which this test is not about; the three
                 * temperatures are what the draw reaches. */
                if (s == (int)PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C ||
                    s == (int)PLANT_STATE_BREW_OUTLET_TEMPERATURE_C) {
                    TEST_ASSERT_TRUE_MESSAGE((double)states[s] > floor_c, message);
                    TEST_ASSERT_TRUE_MESSAGE((double)states[s] < ceiling_c, message);
                }
            }
        }
    }
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C10: The description states the relations flow
/// now enters.
///
/// Which coefficients the statement has to name is already asked by the build
/// check beside it, and asking it again here would be a second implementation of
/// that. What is asked here is the part a name check cannot reach: that the
/// relations themselves are written down, with the drawn rate and the two water
/// properties in them, and that the difference driving the loss is between the
/// water leaving and the water arriving rather than between the casting and
/// anything. A statement listing four new coefficients in a table and leaving
/// the relation they enter unstated would pass the build and leave a reader with
/// four numbers and no equation.
static void test_the_statement_writes_out_the_relation_flow_enters(void)
{
    char statement[STATEMENT_MAX];
    (void)read_named_file(REFERENCE_STATEMENT_PATH, statement, sizeof(statement));

    bool relation_is_written = false;
    bool residence_time_is_written = false;
    bool integration_error_is_stated = false;

    for (char *block = strtok(statement, "\n"); block != NULL; block = strtok(NULL, "\n")) {
        if (strstr(block, "flow") != NULL && strstr(block, "T_outlet") != NULL &&
            strstr(block, "T_feed") != NULL) {
            relation_is_written = true;
        }
        if (strstr(block, "flow") != NULL && strstr(block, "V_held") != NULL) {
            residence_time_is_written = true;
        }
        if (strstr(block, "truncation") != NULL && strstr(block, "single precision") != NULL) {
            integration_error_is_stated = true;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(relation_is_written,
                             "no line of the statement writes the loss the drawn water carries as "
                             "a relation between the water leaving and the water arriving");
    TEST_ASSERT_TRUE_MESSAGE(residence_time_is_written,
                             "no line of the statement writes the outlet's time constant against "
                             "the drawn rate and the held volume");
    TEST_ASSERT_TRUE_MESSAGE(integration_error_is_stated,
                             "the statement says nothing about what the coupled step costs, so a "
                             "reader of the error budget beside it cannot tell whether the "
                             "integration adds to the figures there");
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C11: The description records that the outlet
/// coefficient has become reachable rather than identified.
///
/// Two halves, and the second is what stops the first being overclaimed. The
/// statement has to say that the casting's own reading now depends on the outlet
/// coefficients -- and it has to have stopped saying the opposite, which is why
/// the old sentence is searched for and required to be gone rather than merely
/// outnumbered. And it has to go on saying that what it carries about those
/// coefficients is an assumed error and nothing else, because reachable is not
/// identified and nothing has been on a bench.
static void test_the_statement_records_the_outlet_coefficients_as_reachable(void)
{
    char statement[STATEMENT_MAX];
    (void)read_named_file(REFERENCE_STATEMENT_PATH, statement, sizeof(statement));

    TEST_ASSERT_NULL_MESSAGE(
        strstr(statement, "nothing the sensor reads depends on that coefficient"),
        "the statement still says nothing the machine senses depends on the outlet coefficient, "
        "which the flow term has made untrue");

    char *const copy = statement;
    bool reachability_is_stated = false;
    bool identification_is_disclaimed = false;

    for (char *block = strtok(copy, "\n"); block != NULL; block = strtok(NULL, "\n")) {
        if (strstr(block, "brew sensor") != NULL && strstr(block, "residual") != NULL) {
            reachability_is_stated = true;
        }
        if (strstr(block, "assumed error and nothing else") != NULL) {
            identification_is_disclaimed = true;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(reachability_is_stated,
                             "no line of the statement says the reading the machine takes now "
                             "carries information about the outlet coefficients");
    TEST_ASSERT_TRUE_MESSAGE(identification_is_disclaimed,
                             "the statement no longer says that what it carries about those "
                             "coefficients is an assumed error and nothing else, which is the "
                             "difference between reachable and identified");
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C13: The outlet coefficient's superseded
/// declaration is re-derived rather than carried over.
///
/// Three separate things, and a description can do any two of them and still
/// have carried the old judgement forward.
///
/// The superseded coefficient is gone from both files rather than left beside
/// its replacements. A value nothing reads is a value nobody maintains, and it
/// would go on carrying an account of a residence time the drawn-rate relation
/// now computes -- two statements of one quantity, which is the arrangement
/// these files exist to prevent.
///
/// Each replacement carries its own declared error rather than the old figure
/// split or copied. That is asserted next door, against the shipped budget.
///
/// And the claim about which fraction is the widest is re-judged against the new
/// figures rather than asserted unchanged. The statement makes that claim in
/// prose and the figures are in the description, so the two can disagree without
/// either being obviously wrong on its own -- which is exactly the failure a
/// rationale carried forward past the numbers it was written about produces.
/// Here the figures are asked which coefficient is widest and the statement is
/// required to be making its claim about that one.
static void test_the_superseded_outlet_declaration_was_re_derived(void)
{
    /* The name that went. Written out rather than derived, because what is being
     * asserted is that nothing derives it any more. */
    static const char SUPERSEDED[] = "brew.outlet_time_constant_s";

    char values[REFERENCE_MAX];
    char statement[STATEMENT_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    const size_t used = read_named_file(REFERENCE_DESCRIPTION_PATH, values, sizeof(values));
    (void)read_named_file(REFERENCE_STATEMENT_PATH, statement, sizeof(statement));

    TEST_ASSERT_NULL_MESSAGE(strstr(values, SUPERSEDED),
                             "the description still declares the outlet time constant the drawn "
                             "rate now supplies, so one quantity is written down twice");
    TEST_ASSERT_NULL_MESSAGE(strstr(statement, SUPERSEDED),
                             "the statement still accounts for the outlet time constant, so a "
                             "reader is being given the reasoning behind a value nothing reads");

    /*
     * Which coefficient the figures make the widest. Read from the shipped
     * description rather than assumed, so this asks the two files to agree
     * rather than asking either to match something written here.
     */
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(values, used, &budget, &fault));

    const char *widest = NULL;
    float widest_fraction = -1.0f;
    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        float assumed = -1.0f;

        TEST_ASSERT_TRUE(plant_parameter_budget_for(&budget, NOMINAL[i].name, &assumed));
        if (assumed > widest_fraction) {
            widest_fraction = assumed;
            widest = NOMINAL[i].name;
        }
    }
    TEST_ASSERT_NOT_NULL(widest);

    /*
     * And the prose is making its claim about that one. The bullet names the
     * coefficient in words rather than by its identifier -- the accounting
     * section is written for a reader and not for a parser -- so what is matched
     * is the word that distinguishes it, which is the thing the replacement
     * stands for and the old one did not.
     */
    static const struct {
        const char *name;
        const char *word;
    } NAMED_IN_PROSE[] = {
        {"brew.outlet_conduction_time_constant_s", "conduction constant"},
        {"brew.outlet_held_volume_ml", "held volume"},
    };

    const char *word = NULL;
    for (size_t i = 0u; i < sizeof(NAMED_IN_PROSE) / sizeof(NAMED_IN_PROSE[0]); i++) {
        if (strcmp(widest, NAMED_IN_PROSE[i].name) == 0) {
            word = NAMED_IN_PROSE[i].word;
        }
    }

    char message[260];
    (void)snprintf(message, sizeof(message),
                   "the widest declared fraction in the description belongs to '%s' (%.9g), and "
                   "no paragraph of the statement claims the widest fraction for it",
                   widest, (double)widest_fraction);
    TEST_ASSERT_NOT_NULL_MESSAGE(word, message);

    bool re_judged = false;
    for (char *block = strtok(statement, "\n"); block != NULL; block = strtok(NULL, "\n")) {
        if (strstr(block, "widest fraction") != NULL && strstr(block, word) != NULL) {
            re_judged = true;
        }
    }
    TEST_ASSERT_TRUE_MESSAGE(re_judged, message);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C12: The omissions this slice does not close
/// remain stated.
/// SOL-PLANT-FLOW-ENERGY-BALANCE.C14: The description states how completely the
/// drawn water is assumed to equilibrate.
///
/// The arrival of a flow term is exactly the event that makes a reader stop
/// looking, so what the statement still leaves out has to survive it in the
/// place a reader goes to find out. Each of these is required to appear after
/// the heading the omissions are under, not merely somewhere in the file -- a
/// puck mentioned in a relation is not a puck recorded as absent.
static void test_the_omissions_the_flow_term_does_not_close_are_still_recorded(void)
{
    /* Each entry is a phrase, and a short description of what its absence would
     * mean, so a failure names the omission rather than the string. */
    static const struct {
        const char *phrase;
        const char *what;
    } STILL_OPEN[] = {
        {"puck", "the puck"},
        {"flow-versus-pressure", "the pump's flow-versus-pressure characteristic"},
        {"three-way valve", "the contention between the two destinations one block serves"},
        /*
         * What a steam draw costs the steam mass used to be on this list and is
         * not any more, because it is now a relation the description writes out
         * rather than an absence it records. What is still absent on that side is
         * the steam itself -- how much of it there is and what state it is in --
         * and that is what stands here in its place. The entry was replaced
         * rather than deleted, because a slice that closed an omission and left
         * the list one shorter would look identical to one that lost an entry.
         */
        {"steam quality", "how much steam there is and what state it is in"},
        {"equilibrate", "how completely the drawn water is assumed to equilibrate"},
    };

    char statement[STATEMENT_MAX];
    (void)read_named_file(REFERENCE_STATEMENT_PATH, statement, sizeof(statement));

    const char *const omissions = strstr(statement, "What this description leaves out");
    TEST_ASSERT_NOT_NULL_MESSAGE(omissions,
                                 "the statement has no section recording what it leaves out");

    for (size_t i = 0u; i < sizeof(STILL_OPEN) / sizeof(STILL_OPEN[0]); i++) {
        char message[240];

        (void)snprintf(message, sizeof(message),
                       "%s is not recorded as an omission any more, so a reader who has just seen "
                       "a flow term arrive has nothing telling them it is still absent",
                       STILL_OPEN[i].what);
        TEST_ASSERT_NOT_NULL_MESSAGE(strstr(omissions, STILL_OPEN[i].phrase), message);
    }

    /*
     * And the equilibration omission specifically says which way it is wrong.
     * "Not modelled" would be a weaker statement than the criterion asks for:
     * these relations overstate what the group receives and overstate the droop
     * together, and a reader sizing a margin needs the direction.
     */
    bool direction_is_stated = false;
    char *const copy = statement;
    for (char *block = strtok(copy, "\n"); block != NULL; block = strtok(NULL, "\n")) {
        if (strstr(block, "equilibrate") != NULL && strstr(block, "droop") != NULL) {
            direction_is_stated = true;
        }
    }
    TEST_ASSERT_TRUE_MESSAGE(direction_is_stated,
                             "the equilibration omission does not say which way the relations are "
                             "wrong, so nothing tells a reader whether it is optimistic");
}

/* --- What the steam drawn off the block costs it -------------------------- */

/*
 * The rate the tests below hold the wand open at, and a step to hold it for.
 *
 * Two millilitres a second is a hard draw against this description's steam
 * block -- four kilowatts of latent heat against a fourteen-hundred-watt element
 * -- and it is meant to be. The point of these tests is that the term is there
 * and is the size the coefficients say, so a rate that moved the mass by less
 * than the arithmetic's own resolution would be testing the resolution.
 */
#define STEAM_DRAW_ML_PER_S 2.0f

/* Enough steps under both elements to carry the steam block well past
 * saturation, so the pressure relation is exercised above its floor. */
#define BOIL_STEPS 900

/* The steam block, which this structure keeps as a state of its own. */
static float steam_mass(const plant_model_t *model)
{
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(model, PLANT_STATE_STEAM_TEMPERATURE_C, &value));
    return value;
}

/* The steam path's pressure, read through the seam like everything else. */
static float steam_pressure(const plant_model_t *model)
{
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_model_quantity(model, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &value));
    return value;
}

/* What the saturation relation alone gives at a steam temperature, written the
 * way the description states it rather than the way the source spells it. */
static float saturation_pressure(float steam_temperature_c)
{
    const float above = steam_temperature_c - (float)NOMINAL[I_STEAM_SATURATION].value;
    return above > 0.0f ? (float)NOMINAL[I_STEAM_BAR_PER_K].value * above : 0.0f;
}

/*
 * What a millilitre drawn as steam costs the block, from the coefficients rather
 * than from the structure: the feed carried from where it arrives up to where it
 * turns, and then turned. Written out here so that a term the equations dropped,
 * double-counted, or took against the wrong pair of temperatures disagrees with
 * this rather than with itself.
 */
static double drawn_cost_j_per_ml(const double *values)
{
    return values[I_WATER_LATENT_HEAT] +
           values[I_WATER_HEAT_CAPACITY] *
               (values[I_STEAM_SATURATION] - values[I_WATER_FEED]);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C1: The steam-side state each structure keeps
/// loses energy to drawn steam through its latent heat, independent of any
/// existing loss term.
/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C1: Both structures' steam-side loss term
/// sums latent and sensible heat against the feed.
///
/// The size of the term, against the closed form of the steam block's own
/// balance rather than against the source's spelling of it. With the wand open
/// the block is a mass losing to ambient and paying a constant power out
/// besides, so it relaxes towards a settling temperature the two together fix
/// and the step has a closed form: the loss coefficient sets how fast it gets
/// there and the latent power sets where it is going. A term of the wrong size,
/// of the wrong sign, or one that entered the relaxation instead of the balance
/// lands somewhere this refuses.
static void test_the_steam_block_pays_the_heat_of_what_is_drawn_off_it(void)
{
    static const float STARTS[] = {40.0f, 120.0f, 190.0f};
    double values[COEFFICIENT_COUNT];

    nominal_values(values);

    for (size_t i = 0u; i < sizeof(STARTS) / sizeof(STARTS[0]); i++) {
        plant_model_t model;

        model_from(&model, values);
        TEST_ASSERT_TRUE(
            plant_model_set_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, STARTS[i]));
        TEST_ASSERT_TRUE(plant_model_step(&model, &FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));

        const double seconds = (double)STEP_MS / 1000.0;
        const double loss = values[I_STEAM_LOSS];
        const double mass = values[I_STEAM_MASS];
        const double drawn_w = drawn_cost_j_per_ml(values) * (double)STEAM_DRAW_ML_PER_S;
        /* Where the block is heading with the element off and the wand open, and
         * how far along the way one step carries it. */
        const double settles_at = values[I_AMBIENT] - drawn_w / loss;
        const double expected =
            settles_at + ((double)STARTS[i] - settles_at) * exp(-(loss * seconds) / mass);
        const double got = (double)steam_mass(&model);

        if (!(fabs(got - expected) < 1.0e-3)) {
            char message[240];
            (void)snprintf(message, sizeof(message),
                           "from %.9g: the steam block reached %.9g, the balance with the draw "
                           "gives %.9g",
                           (double)STARTS[i], got, expected);
            TEST_FAIL_MESSAGE(message);
        }
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C1: ...through its latent heat, independent of
/// any existing loss term.
///
/// The shape of the term rather than its size, and the assertion that separates
/// a latent heat from the sensible-heat difference the coffee side uses. What a
/// draw costs the block is a power the rate alone fixes, so the difference
/// between a step taken with the wand open and the same step taken with it shut
/// is the same number wherever the block happens to be sitting. A term written
/// as a difference against the block's own temperature -- taken to ambient, to
/// the feed, or to saturation, each of which is a plausible thing to write and
/// each of which the size test above could be made to pass by re-tuning a
/// coefficient -- gives a different number at each of these temperatures, sixty
/// kelvin apart. The sensible half this term carries is a difference too, and
/// this is what says which difference it is: between two coefficients, not
/// against the state.
/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C1: ...against the feed, which is a pair
/// of coefficients rather than the block's own temperature.
static void test_what_a_draw_costs_the_block_does_not_depend_on_where_it_sits(void)
{
    static const float STARTS[] = {130.0f, 190.0f};
    double values[COEFFICIENT_COUNT];
    float costs[sizeof(STARTS) / sizeof(STARTS[0])];

    nominal_values(values);

    for (size_t i = 0u; i < sizeof(STARTS) / sizeof(STARTS[0]); i++) {
        plant_model_t drawn;
        plant_model_t undrawn;

        model_from(&drawn, values);
        model_from(&undrawn, values);
        TEST_ASSERT_TRUE(plant_model_set_state(&drawn, PLANT_STATE_STEAM_TEMPERATURE_C, STARTS[i]));
        TEST_ASSERT_TRUE(
            plant_model_set_state(&undrawn, PLANT_STATE_STEAM_TEMPERATURE_C, STARTS[i]));

        TEST_ASSERT_TRUE(plant_model_step(&drawn, &FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&undrawn, &FEEDING, 0.0f, STEP_MS));

        costs[i] = steam_mass(&undrawn) - steam_mass(&drawn);
    }

    /* What the draw is worth, from the coefficients and not from a run: a power
     * over a thermal mass over a step, with the relaxation across so short a
     * step within a part in ten thousand of unity. */
    const float seconds = (float)STEP_MS / 1000.0f;
    const float expected =
        ((float)drawn_cost_j_per_ml(values) * STEAM_DRAW_ML_PER_S * seconds) /
        (float)values[I_STEAM_MASS];

    TEST_ASSERT_FLOAT_WITHIN(1.0e-3f, expected, costs[0]);
    /* And the same cost at the other temperature, to far inside what a
     * difference-shaped term would have put between them. */
    TEST_ASSERT_FLOAT_WITHIN(1.0e-4f, costs[0], costs[1]);
    /* The premise: the draw did something, so the equality above is two equal
     * costs rather than two absent ones. */
    TEST_ASSERT_TRUE(costs[0] > 0.4f);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C1: ...independent of any existing loss term --
/// at no demand the term is exactly zero and nothing that was here before moves.
///
/// Two descriptions differing only in what a millilitre costs to boil, one of
/// them at the top of the range the structure declares admissible, run through a
/// long trajectory with the wand shut and compared byte for byte. A term that
/// leaked in through a near-zero rather than an exact zero, or one written from
/// the pump's drawn rate rather than from the demand, would separate them. The
/// same pair with the wand open has to come apart, or the comparison above is
/// two runs of a coefficient nothing reads.
static void test_with_the_wand_shut_the_latent_coefficient_reaches_nothing(void)
{
    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];
    char nominal_text[DESCRIPTION_MAX];
    char extreme_text[DESCRIPTION_MAX];

    all_bounds(low, high);

    const size_t nominal_used = describe_with_one(nominal_text, sizeof(nominal_text),
                                                  I_WATER_LATENT_HEAT,
                                                  NOMINAL[I_WATER_LATENT_HEAT].value);
    const size_t extreme_used = describe_with_one(extreme_text, sizeof(extreme_text),
                                                  I_WATER_LATENT_HEAT, high[I_WATER_LATENT_HEAT]);

    plant_parameters_t as_nominal;
    plant_parameters_t as_extreme;
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameters_load(nominal_text, nominal_used, &as_nominal, &fault));
    TEST_ASSERT_TRUE(plant_parameters_load(extreme_text, extreme_used, &as_extreme, &fault));

    for (int drawing = 0; drawing < 2; drawing++) {
        const float demand = drawing ? STEAM_DRAW_ML_PER_S : 0.0f;
        plant_model_t ordinary;
        plant_model_t extreme;
        float from_ordinary[PLANT_QUANTITY_COUNT];
        float from_extreme[PLANT_QUANTITY_COUNT];

        TEST_ASSERT_TRUE(plant_model_init(&ordinary, &as_nominal));
        TEST_ASSERT_TRUE(plant_model_init(&extreme, &as_extreme));

        for (int step = 0; step < TRANSIENT_STEPS; step++) {
            TEST_ASSERT_TRUE(plant_model_step(&ordinary, &DRAWING, demand, STEP_MS));
            TEST_ASSERT_TRUE(plant_model_step(&extreme, &DRAWING, demand, STEP_MS));
        }
        read_all(&ordinary, from_ordinary);
        read_all(&extreme, from_extreme);

        if (drawing) {
            TEST_ASSERT_TRUE(from_extreme[PLANT_QUANTITY_STEAM_TEMPERATURE_C] <
                             from_ordinary[PLANT_QUANTITY_STEAM_TEMPERATURE_C] - 10.0f);
        } else {
            TEST_ASSERT_EQUAL_MEMORY(from_ordinary, from_extreme, sizeof(from_ordinary));
        }
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C1: ...the steam-side state each structure keeps
/// -- and only that state.
///
/// The converse of the test that keeps the pump's drawn rate off the steam mass.
/// This machine has two separately fed blocks, so the wand reaches one of them
/// and the group reaches the other; a draw that moved the coffee block would be
/// steam leaving through the group. Compared byte for byte, because the two
/// sides share no arithmetic and a difference of one bit would mean they had
/// started to.
static void test_a_steam_draw_leaves_the_coffee_side_alone(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t drawn;
    plant_model_t undrawn;

    nominal_values(values);
    model_from(&drawn, values);
    model_from(&undrawn, values);

    for (int step = 0; step < TRANSIENT_STEPS; step++) {
        TEST_ASSERT_TRUE(
            plant_model_step(&drawn, &WORKING_AND_FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&undrawn, &WORKING_AND_FEEDING, 0.0f, STEP_MS));
    }

    const float casting_drawn = heated_mass(&drawn);
    const float casting_undrawn = heated_mass(&undrawn);
    const float outlet_drawn = outlet(&drawn);
    const float outlet_undrawn = outlet(&undrawn);

    TEST_ASSERT_EQUAL_MEMORY(&casting_undrawn, &casting_drawn, sizeof(float));
    TEST_ASSERT_EQUAL_MEMORY(&outlet_undrawn, &outlet_drawn, sizeof(float));

    /* And the steam side did move, so the equalities above are the coffee side
     * being left alone rather than the draw doing nothing at all. */
    TEST_ASSERT_TRUE(steam_mass(&drawn) < steam_mass(&undrawn) - 10.0f);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C3: Steam pressure is driven by an integrated
/// state once a draw is open, rather than derived fresh from temperature every
/// step.
///
/// The distinction stated as arithmetic. At every step the gap between what the
/// saturation relation gives for the temperature the block has just reached and
/// what the model reports for the pressure is read off, and required to be the
/// whole of what the draw has taken since it opened -- one step's worth after
/// one step, ten steps' worth after ten. A pressure derived fresh from the
/// temperature each step, with the draw's cost applied to that fresh answer,
/// would leave that gap at one step's worth for the whole of the run, which is
/// exactly the relation this criterion replaces.
static void test_the_steam_pressure_accumulates_the_draw_rather_than_recomputing_it(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t model;

    nominal_values(values);
    model_from(&model, values);

    /* Above saturation before the wand opens, so there is a pressure for the
     * draw to take from. */
    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_pressure(&model) > 0.5f);

    const double seconds = (double)STEP_MS / 1000.0;
    const double per_step_bar =
        values[I_STEAM_PRESSURE_FALL] * (double)STEAM_DRAW_ML_PER_S * seconds;
    TEST_ASSERT_TRUE(per_step_bar > 0.0);

    for (int step = 1; step <= 10; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, STEAM_DRAW_ML_PER_S, STEP_MS));

        const double relation = (double)saturation_pressure(steam_mass(&model));
        const double reported = (double)steam_pressure(&model);
        const double gap = relation - reported;
        const double expected = per_step_bar * (double)step;

        if (!(fabs(gap - expected) < 1.0e-5)) {
            char message[240];
            (void)snprintf(message, sizeof(message),
                           "after %d steps of draw the path sits %.9g bar below the relation, and "
                           "the draw has taken %.9g",
                           step, gap, expected);
            TEST_FAIL_MESSAGE(message);
        }
        /* The floor is not what is being measured here, so the run has to stay
         * off it. */
        TEST_ASSERT_TRUE(reported > 0.0);
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C4: Steam pressure reverts to the affine relation
/// the instant demand returns to zero.
///
/// Three things, and a model can do the first two and still be carrying the
/// draw's residue. The pressure has to be below the relation while the wand is
/// held; it has to be the relation exactly on the very next step with nothing
/// drawn -- compared byte for byte, because a reversion that merely started
/// would satisfy any tolerance and is a different claim from this one; and
/// opening the wand again has to start from nothing rather than from where the
/// last draw left off, which is what "no leftover offset" means and what a state
/// that decayed towards the relation instead of being discarded would fail.
static void test_the_steam_pressure_is_the_relation_again_the_step_the_draw_stops(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t model;

    nominal_values(values);
    model_from(&model, values);

    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, 0.0f, STEP_MS));
    }
    for (int step = 0; step < 10; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, STEAM_DRAW_ML_PER_S, STEP_MS));
    }

    /* Held down while the wand is open, and by a margin rather than by a bit. */
    const float under_draw = steam_pressure(&model);
    TEST_ASSERT_TRUE(under_draw < saturation_pressure(steam_mass(&model)) - 0.01f);

    /* And the relation itself on the first step with nothing drawn. */
    TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, 0.0f, STEP_MS));
    const float reverted = steam_pressure(&model);
    const float relation = saturation_pressure(steam_mass(&model));
    TEST_ASSERT_EQUAL_MEMORY(&relation, &reverted, sizeof(float));

    /*
     * And the next draw starts from the relation rather than from where the last
     * one stopped. One step at the same rate has to cost exactly one step's
     * worth; a gap that had been decayed rather than discarded would show here
     * as a deeper one.
     */
    TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, STEAM_DRAW_ML_PER_S, STEP_MS));
    const double seconds = (double)STEP_MS / 1000.0;
    const double one_step_bar =
        values[I_STEAM_PRESSURE_FALL] * (double)STEAM_DRAW_ML_PER_S * seconds;
    const double gap = (double)saturation_pressure(steam_mass(&model)) -
                       (double)steam_pressure(&model);
    TEST_ASSERT_TRUE(fabs(gap - one_step_bar) < 1.0e-5);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C4: ...the affine relation, which is the one the
/// structure already had.
///
/// Reversion stated without restating the formula. An instance that has just had
/// a draw closed and an instance that has never had one, brought to the same
/// steam temperature and stepped identically with nothing drawn, report the same
/// pressure to the bit. Nothing here writes down what that pressure should be,
/// so the assertion cannot be satisfied by a test and an implementation agreeing
/// about a wrong relation.
static void test_a_closed_draw_leaves_no_trace_a_later_step_can_see(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t drawn;
    plant_model_t untouched;

    nominal_values(values);
    model_from(&drawn, values);
    model_from(&untouched, values);

    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&drawn, &DRAWING, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&untouched, &DRAWING, 0.0f, STEP_MS));
    }
    for (int step = 0; step < 20; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&drawn, &DRAWING, STEAM_DRAW_ML_PER_S, STEP_MS));
    }

    /* The draw took the block down as well as the path, so the two are brought
     * back to one temperature before the comparison -- what is being compared is
     * the pressure at a temperature, not two temperatures. */
    const float shared_c = steam_mass(&untouched);
    TEST_ASSERT_TRUE(plant_model_set_state(&drawn, PLANT_STATE_STEAM_TEMPERATURE_C, shared_c));

    const plant_actuation_t idle = {{0u, 0u, 0u}};
    TEST_ASSERT_TRUE(plant_model_step(&drawn, &idle, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_set_state(&untouched, PLANT_STATE_STEAM_TEMPERATURE_C, shared_c));
    TEST_ASSERT_TRUE(plant_model_step(&untouched, &idle, 0.0f, STEP_MS));

    const float after_draw = steam_pressure(&drawn);
    const float never_drawn = steam_pressure(&untouched);
    TEST_ASSERT_EQUAL_MEMORY(&never_drawn, &after_draw, sizeof(float));
    /* And there was a pressure to compare, rather than two floors. */
    TEST_ASSERT_TRUE(never_drawn > 0.5f);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: The stepped structure stays admissible with a
/// draw open.
///
/// The same question the rest of this file asks of the coefficient space, asked
/// again with the wand held open, because that is a case none of those runs
/// reaches: they are all driven at no demand, so the two relations the draw
/// enters are absent from every one of them. Sampled across the declared range
/// and at both corners of it, with a draw far harder than any machine of this
/// description could sustain, every quantity has to stay a number and the steam
/// path's gauge pressure has to stay at or above nothing -- a draw that pulled it
/// negative would be this model claiming a vacuum the wand cannot make.
static void test_the_structure_stays_admissible_with_a_draw_open(void)
{
    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];

    all_bounds(low, high);
    rng_seed(PROPERTY_SEED);

    for (int c = 0; c < PROPERTY_CASES + 2; c++) {
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        plant_model_t model;
        size_t used;

        if (c == 0) {
            used = describe_corner(low, high, false, text, sizeof(text));
        } else if (c == 1) {
            used = describe_corner(low, high, true, text, sizeof(text));
        } else {
            used = describe_sampled(low, high, text, sizeof(text));
        }

        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_TRUE(plant_parameters_load(text, used, &loaded, &fault));
        TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

        for (int step = 0; step < SHORT_STEPS; step++) {
            float quantities[PLANT_QUANTITY_COUNT];

            TEST_ASSERT_TRUE(plant_model_step(&model, &WORKING_AND_FEEDING, 50.0f, STEP_MS));
            read_all(&model, quantities);

            for (int q = 0; q < PLANT_QUANTITY_COUNT; q++) {
                if (!isfinite(quantities[q])) {
                    char message[240];
                    (void)snprintf(message, sizeof(message),
                                   "case %d step %d: quantity %d left the finite range under a "
                                   "draw; description was:\n%s",
                                   c, step, q, text);
                    TEST_FAIL_MESSAGE(message);
                }
            }
            if (quantities[PLANT_QUANTITY_STEAM_PRESSURE_BAR] < 0.0f) {
                char message[240];
                (void)snprintf(message, sizeof(message),
                               "case %d step %d: a draw carried the steam path to %.9g bar gauge; "
                               "description was:\n%s",
                               c, step, (double)quantities[PLANT_QUANTITY_STEAM_PRESSURE_BAR],
                               text);
                TEST_FAIL_MESSAGE(message);
            }
        }
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: ...with a draw open, including one the path
/// cannot supply.
///
/// The floor asserted where it is reached rather than only where it is not. A
/// draw that takes more pressure than the block has to give carries the path to
/// exactly nothing and leaves it there however long it is held, which is a steam
/// path venting to the room; a gap that went on accumulating past the pressure
/// there was to lose would report a negative gauge pressure, and one that
/// stopped short would leave the path holding pressure through a draw nothing
/// could supply.
///
/// A description whose path sags far harder per millilitre than the shipped one,
/// because the floor is otherwise unreachable and the test would be asserting
/// about a case it never produced: at the nominal coefficients the block goes
/// cold long before the path empties, and a floor reached by the block falling
/// below saturation would establish nothing about the gap at all.
static void test_a_draw_the_path_cannot_supply_stops_at_nothing(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t model;

    nominal_values(values);
    /* The top of the declared range, which is far enough that a single step of an
     * ordinary draw asks for more pressure than the block has to give. */
    values[I_STEAM_PRESSURE_FALL] = 10.0;
    model_from(&model, values);

    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_pressure(&model) > 0.5f);

    for (int step = 0; step < 20; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, STEAM_DRAW_ML_PER_S, STEP_MS));
        TEST_ASSERT_EQUAL_FLOAT(0.0f, steam_pressure(&model));
    }

    /* And the floor is the draw's doing rather than the block having gone cold:
     * the relation still has pressure in it at the temperature the block is at,
     * and the path is reporting none of it. */
    TEST_ASSERT_TRUE(saturation_pressure(steam_mass(&model)) > 0.0f);

    /* Closing the wand hands the whole of that back on the next step, which is
     * the reversion holding at the floor as well as away from it. */
    TEST_ASSERT_TRUE(plant_model_step(&model, &DRAWING, 0.0f, STEP_MS));
    const float reverted = steam_pressure(&model);
    const float relation = saturation_pressure(steam_mass(&model));
    TEST_ASSERT_EQUAL_MEMORY(&relation, &reverted, sizeof(float));
    TEST_ASSERT_TRUE(reverted > 0.0f);
}

/* An instance commanded nothing but a steam feed, at the level given. */
static plant_actuation_t feeding_at(uint16_t level_permille)
{
    plant_actuation_t actuation = {{0u, 0u, 0u, 0u}};
    actuation.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = level_permille;
    return actuation;
}

/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C1: Both structures' steam-side loss term
/// sums latent and sensible heat against the feed.
///
/// The half of the term this restores, isolated from the half that was always
/// there. Two descriptions differing in nothing but the temperature the feed
/// arrives at, stepped with the wand open and the brew pump shut so that
/// coefficient reaches the steam side and nothing else, have to cost the block
/// different amounts -- by exactly what carrying each millilitre the extra
/// distance is worth. A term charging the latent heat alone costs the two the
/// same, which is the state this description was in; a term taking its
/// difference from ambient or from the block instead of from the feed does not
/// move with this coefficient at all.
static void test_the_cost_of_a_draw_follows_the_temperature_the_feed_arrives_at(void)
{
    double warm[COEFFICIENT_COUNT];
    double cold[COEFFICIENT_COUNT];
    plant_model_t from_warm;
    plant_model_t from_cold;

    nominal_values(warm);
    nominal_values(cold);
    cold[I_WATER_FEED] = warm[I_WATER_FEED] - 15.0;

    model_from(&from_warm, warm);
    model_from(&from_cold, cold);
    TEST_ASSERT_TRUE(plant_model_set_state(&from_warm, PLANT_STATE_STEAM_TEMPERATURE_C, 150.0f));
    TEST_ASSERT_TRUE(plant_model_set_state(&from_cold, PLANT_STATE_STEAM_TEMPERATURE_C, 150.0f));

    TEST_ASSERT_TRUE(plant_model_step(&from_warm, &FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_step(&from_cold, &FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));

    /* What the extra lift on each millilitre is worth over the step, from the
     * coefficients. Both instances relax at the same rate from the same place,
     * so everything else in the two steps is the same number. */
    const float seconds = (float)STEP_MS / 1000.0f;
    const float expected = ((float)(warm[I_WATER_FEED] - cold[I_WATER_FEED]) *
                            (float)warm[I_WATER_HEAT_CAPACITY] * STEAM_DRAW_ML_PER_S * seconds) /
                           (float)warm[I_STEAM_MASS];

    TEST_ASSERT_TRUE(expected > 0.0f);
    TEST_ASSERT_FLOAT_WITHIN(1.0e-4f, expected, steam_mass(&from_warm) - steam_mass(&from_cold));
}

/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C1: ...sensible heat against the feed,
/// which is a lift to saturation and never a fall from it.
///
/// The feed temperature and the saturation temperature are bounded separately
/// and no relation ties them, so a description whose feed arrives above its own
/// saturation temperature loads. Read literally the sensible half would then be
/// negative and a draw would warm the block, which is the same something out of
/// nothing the demand guard above refuses a negative rate for. Compared against
/// a description whose feed arrives exactly at saturation, byte for byte,
/// because a tolerance would admit a small negative term as agreement.
static void test_a_feed_arriving_past_boiling_costs_a_draw_nothing_extra(void)
{
    double at_saturation[COEFFICIENT_COUNT];
    double past_saturation[COEFFICIENT_COUNT];
    plant_model_t arriving_at;
    plant_model_t arriving_past;
    const float start_c = 150.0f;

    nominal_values(at_saturation);
    at_saturation[I_STEAM_SATURATION] = 40.0;
    at_saturation[I_WATER_FEED] = 40.0;
    nominal_values(past_saturation);
    past_saturation[I_STEAM_SATURATION] = 40.0;
    past_saturation[I_WATER_FEED] = 55.0;

    model_from(&arriving_at, at_saturation);
    model_from(&arriving_past, past_saturation);
    TEST_ASSERT_TRUE(plant_model_set_state(&arriving_at, PLANT_STATE_STEAM_TEMPERATURE_C, start_c));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&arriving_past, PLANT_STATE_STEAM_TEMPERATURE_C, start_c));

    TEST_ASSERT_TRUE(plant_model_step(&arriving_at, &FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_step(&arriving_past, &FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));

    const float costs_nothing_extra = steam_mass(&arriving_at);
    const float arrived_past = steam_mass(&arriving_past);
    TEST_ASSERT_EQUAL_MEMORY(&costs_nothing_extra, &arrived_past, sizeof(float));
    /* And the draw still cost the block the latent heat, so the equality above
     * is two charged steps rather than two absent terms. */
    TEST_ASSERT_TRUE(arrived_past < start_c - 0.1f);
}

/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C1: Thermoblock's steam energy and pressure
/// terms clamp to the commanded feed rate.
///
/// Stated as an identity rather than as an inequality, which is what makes it
/// hard to pass by accident. A wand asked for far more than the feed is being
/// commanded to replace has to leave the block and the path exactly where a wand
/// asked for the feed's own rate leaves them -- same temperature, same pressure,
/// to the bit. A bound written as the wrong comparison, applied to one of the
/// two relations and not the other, or scaled from the wrong channel, separates
/// the pair.
static void test_a_draw_beyond_the_commanded_feed_is_honoured_at_the_feed(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t asked_for_more;
    plant_model_t asked_for_the_feed;
    /* A tenth of full scale against a nominal five millilitres a second. */
    const plant_actuation_t throttled = feeding_at(ACTUATION_FULL_SCALE / 10u);
    const float feed_ml_per_s = 0.5f;
    const float beyond_it = 4.0f;

    nominal_values(values);
    model_from(&asked_for_more, values);
    model_from(&asked_for_the_feed, values);

    /* Above saturation first, so there is a pressure for the draw to take from
     * and the two runs are compared on both relations rather than on one. */
    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&asked_for_more, &DRAWING, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&asked_for_the_feed, &DRAWING, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_pressure(&asked_for_more) > 0.5f);

    for (int step = 0; step < 20; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&asked_for_more, &throttled, beyond_it, STEP_MS));
        TEST_ASSERT_TRUE(
            plant_model_step(&asked_for_the_feed, &throttled, feed_ml_per_s, STEP_MS));
    }

    const float bounded_c = steam_mass(&asked_for_more);
    const float at_the_feed_c = steam_mass(&asked_for_the_feed);
    const float bounded_bar = steam_pressure(&asked_for_more);
    const float at_the_feed_bar = steam_pressure(&asked_for_the_feed);
    TEST_ASSERT_EQUAL_MEMORY(&at_the_feed_c, &bounded_c, sizeof(float));
    TEST_ASSERT_EQUAL_MEMORY(&at_the_feed_bar, &bounded_bar, sizeof(float));

    /*
     * And the bound was doing something: the same demand against a feed that can
     * supply it takes the block and the path a long way further down. Without
     * this the identity above is two runs of a relation that ignores the demand.
     */
    plant_model_t supplied;
    model_from(&supplied, values);
    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&supplied, &DRAWING, 0.0f, STEP_MS));
    }
    for (int step = 0; step < 20; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&supplied, &DRAWING, beyond_it, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_mass(&supplied) < bounded_c - 5.0f);
    TEST_ASSERT_TRUE(steam_pressure(&supplied) < bounded_bar - 0.01f);
}

/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C2: A fully commanded feed channel leaves
/// existing behaviour unchanged.
///
/// The other side of the bound, and the one that says it is a lower-of-two
/// rather than a rate the feed simply imposes. A draw the feed can supply has to
/// be honoured whole, and has to be the same run at a feed commanded well above
/// it as at one commanded barely above it -- so the feed's level is not in the
/// arithmetic at all while the demand is the smaller figure. Compared byte for
/// byte across every quantity the seam exposes.
static void test_a_draw_the_feed_can_supply_is_honoured_whole(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t plenty;
    plant_model_t barely;
    float from_plenty[PLANT_QUANTITY_COUNT];
    float from_barely[PLANT_QUANTITY_COUNT];
    /* Half of a nominal five millilitres a second is still above the draw. */
    const plant_actuation_t half = feeding_at(ACTUATION_FULL_SCALE / 2u);

    nominal_values(values);
    model_from(&plenty, values);
    model_from(&barely, values);

    for (int step = 0; step < TRANSIENT_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&plenty, &FEEDING, STEAM_DRAW_ML_PER_S, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&barely, &half, STEAM_DRAW_ML_PER_S, STEP_MS));
    }

    read_all(&plenty, from_plenty);
    read_all(&barely, from_barely);
    TEST_ASSERT_EQUAL_MEMORY(from_plenty, from_barely, sizeof(from_plenty));

    /* And the draw was honoured rather than lost: the block is well down on
     * where the same run with the wand shut leaves it. */
    plant_model_t shut;
    model_from(&shut, values);
    for (int step = 0; step < TRANSIENT_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&shut, &FEEDING, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_mass(&plenty) < steam_mass(&shut) - 10.0f);
}

/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C1: ...clamp the effective draw the energy
/// and pressure terms see -- to nothing, where nothing is being fed.
///
/// The case the bound exists to represent, and the one a reader is likeliest to
/// doubt: a block holding no reservoir makes no steam out of water it has not
/// been given, so opening the wand on a feed commanded shut has to leave the
/// block and the path exactly where leaving the wand shut leaves them. Compared
/// byte for byte over a long run, because a bound that let a fraction through
/// would show as a drift rather than as a difference in any one step.
static void test_a_draw_with_the_feed_shut_costs_the_block_and_the_path_nothing(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t asked;
    plant_model_t unasked;
    const plant_actuation_t shut_feed = feeding_at(0u);
    float from_asked[PLANT_QUANTITY_COUNT];
    float from_unasked[PLANT_QUANTITY_COUNT];

    nominal_values(values);
    model_from(&asked, values);
    model_from(&unasked, values);

    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&asked, &DRAWING, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&unasked, &DRAWING, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_pressure(&asked) > 0.5f);

    for (int step = 0; step < TRANSIENT_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&asked, &shut_feed, 4.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&unasked, &shut_feed, 0.0f, STEP_MS));
    }

    read_all(&asked, from_asked);
    read_all(&unasked, from_unasked);

    /* Every quantity but the one that answers for the demand itself, which is
     * the demand and is meant to differ -- see the test below. */
    for (int q = 0; q < PLANT_QUANTITY_COUNT; q++) {
        if (q == (int)PLANT_QUANTITY_STEAM_DRAW_ML_PER_S) {
            continue;
        }
        TEST_ASSERT_EQUAL_MEMORY(&from_unasked[q], &from_asked[q], sizeof(float));
    }
    TEST_ASSERT_TRUE(from_asked[PLANT_QUANTITY_STEAM_PRESSURE_BAR] > 0.0f);
}

/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C1: ...the energy and pressure terms, and
/// those alone.
///
/// The bound reaches the two relations and deliberately does not reach the
/// quantity the seam reports for the draw, which stays the rate that was asked
/// for. The two figures come apart exactly here, and this is the test that says
/// the divergence is intended rather than an oversight: with nothing being fed,
/// the reported rate is the whole demand while the block is charged for none of
/// it. A bound applied at the report instead of at the relations passes every
/// other test in this section and fails this one.
static void test_the_reported_draw_is_the_demand_even_where_the_feed_bounds_it(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t model;
    const plant_actuation_t shut_feed = feeding_at(0u);
    const float demanded = 3.0f;
    float reported = 0.0f;

    nominal_values(values);
    model_from(&model, values);
    TEST_ASSERT_TRUE(plant_model_set_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, 150.0f));

    const float before_c = steam_mass(&model);
    TEST_ASSERT_TRUE(plant_model_step(&model, &shut_feed, demanded, STEP_MS));
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &reported));

    TEST_ASSERT_EQUAL_FLOAT(demanded, reported);

    /* And the block paid nothing for it: what it did over the step is what it
     * does with the wand shut, which is lose to the room and no more. */
    plant_model_t undrawn;
    model_from(&undrawn, values);
    TEST_ASSERT_TRUE(plant_model_set_state(&undrawn, PLANT_STATE_STEAM_TEMPERATURE_C, before_c));
    TEST_ASSERT_TRUE(plant_model_step(&undrawn, &shut_feed, 0.0f, STEP_MS));
    const float unpaid = steam_mass(&undrawn);
    const float charged = steam_mass(&model);
    TEST_ASSERT_EQUAL_MEMORY(&unpaid, &charged, sizeof(float));
}

/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C1: ...clamp the effective draw the energy
/// and pressure terms see -- which bounds how fast the path's departure widens
/// and does not decide whether there is one.
/// SOL-PLANT-STEAM-DRAW-ENERGY.C4: Steam pressure reverts to the affine relation
/// the instant demand returns to zero -- demand, and not the feed behind it.
///
/// The two halves of the deficit relation answer to different things, and the
/// cheap way to write the bound gets that wrong. Whether the path is tied to its
/// block's temperature is a fact about the wand being open; how fast it is
/// carried further down is a fact about how much steam is being made. A bound
/// applied to both at once makes shutting the feed mid-draw look like shutting
/// the wand, and the whole accumulated departure is handed back in one step --
/// so the pressure rises because the pump stopped, and the one handle a steam
/// loop has over a draw reads as a way of raising steam pressure. Asserted as
/// three things: the departure stops growing, none of it is returned, and the
/// wand closing still returns all of it.
static void test_shutting_the_feed_mid_draw_holds_the_departure_rather_than_returning_it(void)
{
    double values[COEFFICIENT_COUNT];
    plant_model_t model;
    const plant_actuation_t fed = DRAWING;
    plant_actuation_t starved = DRAWING;

    starved.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = 0u;

    nominal_values(values);
    model_from(&model, values);

    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &fed, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_pressure(&model) > 0.5f);

    /* A draw long enough to put a departure worth losing into the path. */
    for (int step = 0; step < 10; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &fed, STEAM_DRAW_ML_PER_S, STEP_MS));
    }
    const double held_open = (double)saturation_pressure(steam_mass(&model)) -
                             (double)steam_pressure(&model);
    TEST_ASSERT_TRUE(held_open > 0.01);

    /* The feed shut with the wand still open. The departure has to be exactly
     * what it was: not widened, because nothing is being made, and not returned,
     * because the wand is still open. */
    for (int step = 0; step < 10; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &starved, STEAM_DRAW_ML_PER_S, STEP_MS));

        const double still_open = (double)saturation_pressure(steam_mass(&model)) -
                                  (double)steam_pressure(&model);
        char message[240];
        (void)snprintf(message, sizeof(message),
                       "step %d with the feed shut and the wand open: the path sits %.9g bar "
                       "below the relation, and it sat %.9g bar below it when the feed closed",
                       step, still_open, held_open);
        TEST_ASSERT_TRUE_MESSAGE(fabs(still_open - held_open) < 1.0e-5, message);
    }

    /* And the wand closing still hands the whole of it back on the next step,
     * which is the reversion this must not have broken. */
    TEST_ASSERT_TRUE(plant_model_step(&model, &starved, 0.0f, STEP_MS));
    const float reverted = steam_pressure(&model);
    const float relation = saturation_pressure(steam_mass(&model));
    TEST_ASSERT_EQUAL_MEMORY(&relation, &reverted, sizeof(float));
    TEST_ASSERT_TRUE(reverted > 0.0f);
}

/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C1: ...scale it by a described full-scale
/// feed-rate coefficient.
///
/// The feed relation itself, in the same shape the brew path's flow relation is
/// held to: proportional to the level commanded, and nothing else in it. Held
/// against a demand above every rate the sweep commands, so what the block is
/// charged is the feed and the demand is out of the arithmetic -- which makes
/// the cost at each level a direct reading of the relation. A relation that read
/// the wrong channel, that was not proportional, or that carried an offset lands
/// somewhere this refuses.
static void test_the_commanded_feed_is_proportional_to_the_level(void)
{
    static const uint16_t LEVELS[] = {0u, ACTUATION_FULL_SCALE / 4u, ACTUATION_FULL_SCALE / 2u,
                                      ACTUATION_FULL_SCALE};
    double values[COEFFICIENT_COUNT];
    /* Above the feed at every level above, so the bound binds throughout. */
    const float beyond_every_feed = 20.0f;
    const float start_c = 150.0f;
    const float seconds = (float)STEP_MS / 1000.0f;

    nominal_values(values);

    for (size_t i = 0u; i < sizeof(LEVELS) / sizeof(LEVELS[0]); i++) {
        plant_model_t model;
        const plant_actuation_t actuation = feeding_at(LEVELS[i]);

        model_from(&model, values);
        TEST_ASSERT_TRUE(plant_model_set_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, start_c));
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, beyond_every_feed, STEP_MS));

        /* Where a block fed at this level and charged for every millilitre of it
         * lands, from the coefficients: the feed rate the level commands, times
         * what a millilitre costs, over the mass, plus what the room took. */
        const double fed_ml_per_s =
            values[I_STEAM_FEED_FLOW] * ((double)LEVELS[i] / (double)ACTUATION_FULL_SCALE);
        const double drawn_w = drawn_cost_j_per_ml(values) * fed_ml_per_s;
        const double loss = values[I_STEAM_LOSS];
        const double mass = values[I_STEAM_MASS];
        const double settles_at = values[I_AMBIENT] - drawn_w / loss;
        const double expected =
            settles_at + ((double)start_c - settles_at) * exp(-(loss * (double)seconds) / mass);

        char message[240];
        (void)snprintf(message, sizeof(message),
                       "at a feed commanded to %u parts per thousand the block reached %.9g, and "
                       "a feed proportional to that level gives %.9g",
                       (unsigned)LEVELS[i], (double)steam_mass(&model), expected);
        TEST_ASSERT_TRUE_MESSAGE(fabs((double)steam_mass(&model) - expected) < 1.0e-3, message);
    }
}

/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C2: Thermoblock's declared omissions no
/// longer list the sensible-heat gap.
/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C2: ...and the declared omission matches.
///
/// Two gaps this description recorded against itself are now relations it
/// writes, and the record has to move with the arithmetic in both directions:
/// the sentences claiming the gaps are gone, the coefficient the new relation
/// reads is named, and the absences the new relations open in their place are
/// recorded where a reader goes to find them. A statement left behind is worse
/// than one that was never written, because it is read as current.
static void test_the_gaps_the_feed_relations_close_are_no_longer_recorded_as_omissions(void)
{
    /* Each entry is a phrase the description used to carry, and what a reader
     * still finding it would be told that is no longer true. */
    static const struct {
        const char *phrase;
        const char *what;
    } NOW_CLOSED[] = {
        {"no relation reads", "that no relation reads the steam feed channel"},
        {"does not charge it for bringing that water",
         "that the steam side is charged the latent heat alone"},
    };
    /* And the absences the two new relations leave in their place. */
    static const struct {
        const char *phrase;
        const char *what;
    } NOW_OPEN[] = {
        {"What a draw actually delivered",
         "that the rate reported for a draw is the demand and not what was made"},
        {"What leaves a wand nothing is feeding",
         "that a path venting with the feed shut is not represented"},
    };

    char statement[STATEMENT_MAX];
    (void)read_named_file(REFERENCE_STATEMENT_PATH, statement, sizeof(statement));

    for (size_t i = 0u; i < sizeof(NOW_CLOSED) / sizeof(NOW_CLOSED[0]); i++) {
        char message[260];
        (void)snprintf(message, sizeof(message),
                       "the statement still tells a reader %s, which the relations no longer "
                       "leave true",
                       NOW_CLOSED[i].what);
        TEST_ASSERT_NULL_MESSAGE(strstr(statement, NOW_CLOSED[i].phrase), message);
    }

    /* The coefficient the feed relation reads is named where the relations are
     * stated, rather than only appearing in the list of figures. */
    TEST_ASSERT_NOT_NULL_MESSAGE(
        strstr(statement, "steam.feed_flow_ml_per_s"),
        "the statement names no coefficient for the rate the feed replaces steam at");

    const char *const omissions = strstr(statement, "What this description leaves out");
    TEST_ASSERT_NOT_NULL_MESSAGE(omissions,
                                 "the statement has no section recording what it leaves out");

    for (size_t i = 0u; i < sizeof(NOW_OPEN) / sizeof(NOW_OPEN[0]); i++) {
        char message[260];
        (void)snprintf(message, sizeof(message),
                       "nothing after the omissions heading records %s", NOW_OPEN[i].what);
        TEST_ASSERT_NOT_NULL_MESSAGE(strstr(omissions, NOW_OPEN[i].phrase), message);
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: ...with a draw open -- including a demand
/// that is not one.
///
/// The seam accepts the demand as a plain step argument and refuses nothing
/// about it, which is deliberate and settled elsewhere. What this structure does
/// with a figure that is not a draw is its own business, and it reads it as no
/// draw: steam arriving rather than leaving is not a case this machine has, and
/// running the relations backwards would put energy into the block and pressure
/// into the path out of nothing. A figure that is not a finite rate is read the
/// same way, and that one matters more than it looks -- arithmetic on it would
/// make every quantity downstream stop being a number too, and a comparison
/// against one of those is false either way, so nothing else in this file would
/// notice. Both ends of that are offered, because they fail differently: an
/// undefined rate poisons the arithmetic immediately, while an unbounded one
/// takes the block to an infinity it then never returns from. Compared byte for
/// byte against a step at no demand, because "close to unaffected" is not the
/// claim.
static void test_a_demand_that_is_not_a_draw_is_read_as_no_draw(void)
{
    static const float NOT_A_DRAW[] = {-1.0f, -500.0f, NAN, INFINITY, -INFINITY};
    double values[COEFFICIENT_COUNT];

    nominal_values(values);

    for (size_t i = 0u; i < sizeof(NOT_A_DRAW) / sizeof(NOT_A_DRAW[0]); i++) {
        plant_model_t offered;
        plant_model_t shut;
        float from_offered[PLANT_QUANTITY_COUNT];
        float from_shut[PLANT_QUANTITY_COUNT];

        model_from(&offered, values);
        model_from(&shut, values);

        for (int step = 0; step < TRANSIENT_STEPS; step++) {
            TEST_ASSERT_TRUE(plant_model_step(&offered, &HEATING, NOT_A_DRAW[i], STEP_MS));
            TEST_ASSERT_TRUE(plant_model_step(&shut, &HEATING, 0.0f, STEP_MS));
        }

        read_all(&offered, from_offered);
        read_all(&shut, from_shut);
        TEST_ASSERT_EQUAL_MEMORY(from_shut, from_offered, sizeof(from_shut));
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C2: The latent-heat coefficient is a described
/// coefficient...
/// SOL-PLANT-STEAM-DRAW-ENERGY.C7: The pressure-divergence-rate coefficient is a
/// described coefficient...
/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: The stepped structure stays admissible with a
/// draw open -- load-time range validation accepts and refuses each new
/// coefficient at the edge of the range the structure declares for it.
///
/// Each is checked for the shape its own relation needs rather than for a range
/// in general. What a millilitre costs to boil is a property of water and is
/// bounded around water's own figure, with a floor above zero: a millilitre that
/// cost nothing to vaporise is not water and would make a steam draw free again,
/// which is the state this slice exists to leave. What a draw costs the path in
/// pressure is a property of the machine and may be nothing -- a description of a
/// path that sags not at all is odd rather than inadmissible -- but may not be
/// less than nothing, because a draw that raised the pressure is the relation
/// running backwards.
static void test_the_steam_draws_coefficients_carry_enforced_admissible_ranges(void)
{
    static const size_t BOTH[] = {I_WATER_LATENT_HEAT, I_STEAM_PRESSURE_FALL};

    double low[COEFFICIENT_COUNT];
    double high[COEFFICIENT_COUNT];

    all_bounds(low, high);

    /* What a millilitre costs to boil never reaches zero from below. */
    TEST_ASSERT_TRUE_MESSAGE(low[I_WATER_LATENT_HEAT] > 0.0,
                             "water.latent_heat_j_per_ml admits a millilitre that costs nothing "
                             "to boil, which makes a steam draw free again");
    /* And it is bounded around water's own figure rather than merely bounded --
     * a fluid an order of magnitude away from water is refused. */
    TEST_ASSERT_TRUE(low[I_WATER_LATENT_HEAT] > 100.0);
    TEST_ASSERT_TRUE(high[I_WATER_LATENT_HEAT] < 100000.0);

    /* A path that sags not at all is admissible; one that gains pressure under a
     * draw is not. */
    TEST_ASSERT_TRUE_MESSAGE(low[I_STEAM_PRESSURE_FALL] == 0.0,
                             "steam.pressure_fall_bar_per_ml does not admit a path that sags not "
                             "at all, or admits one that gains pressure under a draw");

    for (size_t i = 0u; i < sizeof(BOTH) / sizeof(BOTH[0]); i++) {
        const size_t index = BOTH[i];
        const double minimum = low[index];
        const double maximum = high[index];
        char message[160];

        (void)snprintf(message, sizeof(message), "%s: bounds [%.17g, %.17g]", NOMINAL[index].name,
                       minimum, maximum);
        TEST_ASSERT_TRUE_MESSAGE(maximum > minimum, message);
        TEST_ASSERT_TRUE_MESSAGE(isfinite(maximum), message);

        for (int side = 0; side < 2; side++) {
            char text[DESCRIPTION_MAX];
            plant_parameters_t loaded;
            plant_parameter_error_t fault;
            const double outside =
                side == 0 ? minimum - (maximum - minimum) : maximum + (maximum - minimum);

            const size_t used = describe_with_one(text, sizeof(text), index, outside);
            memset(&fault, 0, sizeof(fault));
            TEST_ASSERT_FALSE_MESSAGE(plant_parameters_load(text, used, &loaded, &fault), message);
            TEST_ASSERT_EQUAL(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault);
            TEST_ASSERT_EQUAL_STRING(NOMINAL[index].name, fault.parameter);
        }
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C2: The latent-heat coefficient is a described
/// coefficient with a declared origin and error.
/// SOL-PLANT-STEAM-DRAW-ENERGY.C7: The pressure-divergence-rate coefficient is a
/// described coefficient with a declared origin and error.
///
/// Both halves, against the description the build hands this suite. The error is
/// kept by the loader, so it is read back through the seam. The origin is not
/// kept -- which values are accounted for is a question about a file -- so that
/// half is read out of the file's own text: the line for each coefficient has to
/// carry the marker, a kind the vocabulary declares, and an account after it. A
/// line carrying a marker and a kind and nothing else would pass a check that
/// only looked for the word, and would leave a reader a provenance with no
/// provenance in it.
static void test_the_steam_draws_coefficients_declare_an_origin_and_an_error(void)
{
    static const char *const REQUIRED[] = {
        "water.latent_heat_j_per_ml",
        "steam.pressure_fall_bar_per_ml",
    };
    /* The words plant_origin.h declares, spelled out here because a suite that
     * read them from that header would name a vocabulary the seam already
     * carries into the description as text. */
    static const char *const KINDS[] = {"@document ", "@estimated ", "@measured "};

    char text[REFERENCE_MAX];
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    const size_t used = read_named_file(REFERENCE_DESCRIPTION_PATH, text, sizeof(text));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameter_budget_load(text, used, &budget, &fault));

    for (size_t i = 0u; i < sizeof(REQUIRED) / sizeof(REQUIRED[0]); i++) {
        char message[200];
        float assumed = -1.0f;

        (void)snprintf(message, sizeof(message),
                       "the shipped description declares no assumed error for %s", REQUIRED[i]);
        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_budget_for(&budget, REQUIRED[i], &assumed),
                                 message);
        TEST_ASSERT_TRUE_MESSAGE(isfinite(assumed), message);
        /* Above zero: a declared error of nothing is a claim that the figure is
         * exact, and neither of these is. Neither figure itself is pinned here --
         * choosing them is a judgement argued in the statement beside the
         * description. */
        TEST_ASSERT_TRUE_MESSAGE(assumed > 0.0f, message);

        /* And the line carries an account of where the figure came from. */
        const char *const line = strstr(text, REQUIRED[i]);
        (void)snprintf(message, sizeof(message), "the shipped description does not name %s",
                       REQUIRED[i]);
        TEST_ASSERT_NOT_NULL_MESSAGE(line, message);

        const char *const end = strchr(line, '\n');
        (void)snprintf(message, sizeof(message),
                       "the line for %s carries no origin of a declared kind with an account "
                       "behind it",
                       REQUIRED[i]);

        bool accounted = false;
        for (size_t k = 0u; k < sizeof(KINDS) / sizeof(KINDS[0]); k++) {
            const char *const marker = strstr(line, KINDS[k]);
            if (marker != NULL && (end == NULL || marker < end) &&
                marker[strlen(KINDS[k])] != '\0' && marker[strlen(KINDS[k])] != '\n') {
                accounted = true;
            }
        }
        TEST_ASSERT_TRUE_MESSAGE(accounted, message);
    }
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C1: The plant seam names the steam-draw rate
/// as a reported quantity.
///
/// The enumerator exists, sits inside the vocabulary's own count, and is
/// distinct from every other member -- the rate above it most of all, which is
/// the one it shares a unit with and the one a hand-written initialiser would
/// most plausibly collide with. A quantity outside the count is unreachable to a
/// consumer walking the vocabulary, and one sharing another member's value is a
/// second name for that member rather than a quantity of its own.
static void test_the_seam_names_the_steam_draw_rate_as_a_quantity(void)
{
    TEST_ASSERT_TRUE((int)PLANT_QUANTITY_STEAM_DRAW_ML_PER_S >= 0);
    TEST_ASSERT_TRUE((int)PLANT_QUANTITY_STEAM_DRAW_ML_PER_S < (int)PLANT_QUANTITY_COUNT);

    const plant_quantity_t others[] = {
        PLANT_QUANTITY_BREW_TEMPERATURE_C,
        PLANT_QUANTITY_STEAM_TEMPERATURE_C,
        PLANT_QUANTITY_BREW_PRESSURE_BAR,
        PLANT_QUANTITY_STEAM_PRESSURE_BAR,
        PLANT_QUANTITY_BREW_FLOW_ML_PER_S,
    };

    /* Every other quantity is listed, not merely a few. A quantity added to the
     * vocabulary and left out of this array escapes the distinctness check
     * silently, and an array that has stopped covering the vocabulary looks
     * exactly like one that passed. */
    TEST_ASSERT_EQUAL_INT_MESSAGE((int)PLANT_QUANTITY_COUNT - 1,
                                  (int)(sizeof(others) / sizeof(others[0])),
                                  "a quantity exists that this array does not name");

    for (size_t i = 0u; i < sizeof(others) / sizeof(others[0]); i++) {
        TEST_ASSERT_TRUE(others[i] != PLANT_QUANTITY_STEAM_DRAW_ML_PER_S);
    }
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C2: Every plant structure answers the
/// steam-draw quantity.
///
/// Answered rather than refused on the reference structure, from rest as well as
/// with a draw open. From rest is the case that matters most for this rate: the
/// demand arrives from outside the machine and nothing inside it commands one,
/// so a structure that began answering only once something had been drawn would
/// be refusing the quantity in exactly the state a consumer meets it in first --
/// and a refusal is indistinguishable to that consumer from a structure that
/// does not answer the quantity at all.
static void test_the_reference_structure_answers_the_steam_draw_rate(void)
{
    plant_model_t model;
    float drawn = -1.0f;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, 1.5f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));
    TEST_ASSERT_TRUE(drawn > 0.0f);
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C1: ...and plant_model_quantity returns the
/// value the step's own input carried, derived from nothing else.
///
/// Swept across the range rather than checked at one value, and compared exactly
/// rather than within a tolerance -- TEST_ASSERT_FLOAT_WITHIN at a delta of
/// nothing, because TEST_ASSERT_EQUAL_FLOAT admits a relative tolerance and a
/// structure scaling the demand by a part in a million would pass it. There is
/// no coefficient between the demand and the report, so any tolerance at all
/// would admit a scaling this quantity is not entitled to. A structure that multiplied the demand by anything, or that
/// reported a volume integrated over the step in place of the rate, fails here at
/// every value but zero.
///
/// Each value is read after its own step, and the sweep ends back at nothing: the
/// rate is replaced whole every step rather than accumulated, so a structure
/// carrying it over would report the largest demand it had ever been given and
/// would pass a sweep that only ever rose.
static void test_the_reported_steam_draw_rate_is_the_demand_the_step_was_given(void)
{
    static const float DEMANDS[] = {0.0f, 0.05f, 0.5f, 2.0f, 7.5f, 0.0f};
    plant_model_t model;

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    for (size_t i = 0u; i < sizeof(DEMANDS) / sizeof(DEMANDS[0]); i++) {
        float drawn = -1.0f;
        char message[96];

        TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, DEMANDS[i], STEP_MS));
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));

        (void)snprintf(message, sizeof(message), "a demand of %f was reported as %f",
                       (double)DEMANDS[i], (double)drawn);
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.0f, DEMANDS[i], drawn, message);
    }
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C1: ...the value the step's own input carries,
/// as this structure's own admissibility guard leaves it.
///
/// A demand below zero, and any demand that is not finite, is no draw in this
/// structure's relations -- the seam deliberately refuses nothing about the
/// demand, which leaves the structure the place it is answered. The quantity has
/// to answer it the same way, and the failure if it does not is the one that
/// hides itself: an unbounded or undefined rate handed back through the seam
/// makes every comparison against it false whichever way it is written, so a
/// consumer asking whether a draw is open is told neither open nor closed, and
/// anything computed from it stops being a number with nothing to say so.
///
/// The steam mass is read either side of the step to show the two agree. It sits
/// at ambient with nothing heating it and nothing drawn from it, so a demand that
/// had been acted on would have moved it; a report of anything but nothing beside
/// a mass that did not move is the quantity contradicting the model it was read
/// from.
static void test_an_inadmissible_steam_demand_is_reported_as_no_draw(void)
{
    static const float REFUSED[] = {-1.0f, -0.0001f, NAN, INFINITY, -INFINITY};

    for (size_t i = 0u; i < sizeof(REFUSED) / sizeof(REFUSED[0]); i++) {
        plant_model_t model;
        float drawn = -1.0f;
        float steam_before = 0.0f;
        float steam_after = 0.0f;
        char message[96];

        TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
        TEST_ASSERT_TRUE(
            plant_model_quantity(&model, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &steam_before));

        TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, REFUSED[i], STEP_MS));
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));

        (void)snprintf(message, sizeof(message), "a demand of %f was reported rather than refused",
                       (double)REFUSED[i]);
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.0f, 0.0f, drawn, message);

        TEST_ASSERT_TRUE(
            plant_model_quantity(&model, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &steam_after));
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.0f, steam_before, steam_after, message);
    }
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C4: The reported steam-draw quantity is
/// exercised end to end on the host tier.
///
/// A description is loaded as text, a model is initialised from it, a draw is
/// commanded through the step, and the rate is read back through the seam -- the
/// whole path a consumer takes, with no structure field named anywhere along it.
///
/// The pump is commanded on the same step and its rate read back beside the
/// draw. The two rates share a unit and a shape, and each is held in its own
/// store recomputed whole every step; a structure answering one of them from the
/// other's store is the mistake that passes both quantities' own tests and is
/// visible only when both are non-zero at once and different.
static void test_the_steam_draw_rate_is_reached_end_to_end_through_the_seam(void)
{
    static const char DESCRIPTION[] = "ambient_temperature_c = 20\n"
                                      "brew.thermal_mass_j_per_k = 420\n"
                                      "brew.heater_power_w = 1200\n"
                                      "brew.loss_w_per_k = 1.5\n"
                                      "brew.outlet_held_volume_ml = 6\n"
                                      "brew.outlet_conduction_time_constant_s = 15\n"
                                      "steam.thermal_mass_j_per_k = 900\n"
                                      "steam.heater_power_w = 1400\n"
                                      "steam.loss_w_per_k = 2.2\n"
                                      "pump.pressure_bar = 9\n"
                                      "pump.flow_ml_per_s = 8\n"
                                      "brew.pressure_time_constant_s = 0.8\n"
                                      "water.feed_temperature_c = 18\n"
                                      "water.heat_capacity_j_per_ml_k = 4.15\n"
                                      "water.latent_heat_j_per_ml = 2000\n"
                                      "steam.saturation_temperature_c = 100\n"
                                      "steam.pressure_bar_per_k = 0.035\n"
                                      "steam.pressure_fall_bar_per_ml = 0.02\n"
                                      "steam.feed_flow_ml_per_s = 5\n";
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;
    plant_actuation_t pumping = {{0u}};
    float drawn_steam = -1.0f;
    float drawn_water = -1.0f;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

    pumping.level_permille[ACTUATION_CHANNEL_PUMP] = ACTUATION_FULL_SCALE / 2u;
    TEST_ASSERT_TRUE(plant_model_step(&model, &pumping, 1.25f, STEP_MS));

    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn_steam));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn_water));

    /* The demand as it was commanded, and the pump's own eight at half scale.
     * Both are exact in binary, so both are compared at a delta of nothing
     * rather than through the relative tolerance TEST_ASSERT_EQUAL_FLOAT
     * applies. */
    TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.25f, drawn_steam);
    TEST_ASSERT_FLOAT_WITHIN(0.0f, 4.0f, drawn_water);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C1, C3: A structure declares the delivery
/// points it serves through the seam vocabulary, and the thermoblock structure
/// declares the group and spout served from its one casting.
static void test_the_thermoblock_declares_both_the_group_and_the_spout(void)
{
    plant_delivery_point_set_t served = plant_structure_delivery_points();

    TEST_ASSERT_TRUE((served & PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_GROUP)) != 0u);
    TEST_ASSERT_TRUE(
        (served & PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT)) != 0u);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C2, C3: A structure names the heated mass
/// backing each delivery point it serves, and the thermoblock names the same
/// one for both -- the one casting a diverter routes between them.
static void test_the_thermoblock_answers_the_same_mass_for_both_points(void)
{
    plant_heated_mass_id_t group_mass = 0xFFu;
    plant_heated_mass_id_t spout_mass = 0xFEu;

    TEST_ASSERT_TRUE(
        plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_GROUP, &group_mass));
    TEST_ASSERT_TRUE(
        plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, &spout_mass));
    TEST_ASSERT_EQUAL_UINT8(group_mass, spout_mass);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C4: A consumer queries whether two delivery
/// points share a mass without knowing the structure, and gets true for a pair
/// that share the thermoblock's one casting.
static void test_the_group_and_the_spout_are_reported_as_sharing_a_mass(void)
{
    bool share = false;

    TEST_ASSERT_TRUE(plant_delivery_points_share_mass(
        PLANT_DELIVERY_POINT_GROUP, PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, &share));
    TEST_ASSERT_TRUE(share);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C1, C2, C4: A point the structure does not
/// serve is refused by both the mass accessor and the contention query, rather
/// than answered as though it shared or did not share a mass.
static void test_a_delivery_point_the_thermoblock_does_not_serve_is_refused(void)
{
    const plant_delivery_point_t unserved = (plant_delivery_point_t)PLANT_DELIVERY_POINT_COUNT;
    plant_heated_mass_id_t mass = 0xFFu;
    bool share = true;

    TEST_ASSERT_FALSE(plant_structure_delivery_point_mass(unserved, &mass));
    TEST_ASSERT_EQUAL_UINT8(0xFFu, mass);
    TEST_ASSERT_FALSE(
        plant_delivery_points_share_mass(PLANT_DELIVERY_POINT_GROUP, unserved, &share));
    TEST_ASSERT_TRUE(share);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C2, C4: The mass accessor and the contention
/// query refuse a null output argument rather than writing through it.
static void test_the_delivery_queries_refuse_null_output_arguments(void)
{
    TEST_ASSERT_FALSE(plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_GROUP, NULL));
    TEST_ASSERT_FALSE(plant_delivery_points_share_mass(
        PLANT_DELIVERY_POINT_GROUP, PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, NULL));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_actuation_channels_are_one_enumerated_set);
    RUN_TEST(test_the_structure_states_which_channels_it_answers);
    RUN_TEST(test_a_steam_demand_and_a_steam_feed_command_are_both_accepted);
    RUN_TEST(test_the_trajectory_is_what_it_was_before_the_vocabulary_was_unified);
    RUN_TEST(test_the_coefficient_indices_name_what_they_claim);
    RUN_TEST(test_the_water_on_its_way_to_the_group_trails_the_heated_mass);
    RUN_TEST(test_the_water_follows_the_casting_by_its_own_time_constant);
    RUN_TEST(test_a_shorter_outlet_time_constant_brings_the_water_closer);
    RUN_TEST(test_the_state_vocabulary_carries_what_the_quantities_cannot);
    RUN_TEST(test_every_state_carries_the_quantity_it_names);
    RUN_TEST(test_a_state_read_that_cannot_be_answered_is_refused_and_writes_nothing);
    RUN_TEST(test_the_unreported_state_is_reachable_through_the_seam_alone);
    RUN_TEST(test_the_flow_terms_coefficients_carry_enforced_admissible_ranges);
    RUN_TEST(test_the_shipped_description_declares_an_assumed_error_for_the_new_coefficient);
    RUN_TEST(test_the_statement_and_the_variant_carry_every_coefficient);
    RUN_TEST(test_the_statement_warns_that_the_two_pump_coefficients_exclude_each_other);
    RUN_TEST(test_the_model_advances_over_a_sequence_of_steps);
    RUN_TEST(test_a_step_at_rest_changes_nothing);
    RUN_TEST(test_many_steps_at_rest_change_nothing);
    RUN_TEST(test_rest_stays_at_rest_at_a_different_ambient);
    RUN_TEST(test_heat_raises_the_temperatures_and_lowers_nothing);
    RUN_TEST(test_the_same_inputs_reproduce_the_same_trajectory);
    RUN_TEST(test_an_actuation_beyond_full_scale_is_refused_and_changes_nothing);
    RUN_TEST(test_an_uninitialised_instance_and_a_zero_step_are_refused);
    RUN_TEST(test_one_changed_coefficient_changes_the_trajectory);
    RUN_TEST(test_every_coefficient_reaches_the_equations);
    RUN_TEST(test_comments_and_blank_lines_do_not_change_what_is_read);
    RUN_TEST(test_omitting_any_single_coefficient_is_refused);
    RUN_TEST(test_a_coefficient_outside_its_range_is_refused_with_the_range);
    RUN_TEST(test_a_not_a_number_is_refused_rather_than_run);
    RUN_TEST(test_a_value_that_collapses_to_zero_is_refused);
    RUN_TEST(test_a_value_below_full_precision_is_still_accepted);
    RUN_TEST(test_an_unparsable_description_is_refused_at_its_line);
    RUN_TEST(test_a_refusal_leaves_the_record_untouched);
    RUN_TEST(test_an_empty_description_is_refused);
    RUN_TEST(test_leading_blanks_do_not_change_what_is_read);
    RUN_TEST(test_a_final_line_without_a_newline_is_read);
    RUN_TEST(test_a_line_with_no_separator_is_refused_quoting_the_line);
    RUN_TEST(test_a_setting_with_no_name_is_refused_quoting_the_line);
    RUN_TEST(test_the_declared_bounds_are_themselves_admissible);
    RUN_TEST(test_the_structure_declares_far_fewer_parameters_than_the_loader_admits);
    RUN_TEST(test_a_value_token_longer_than_the_loader_holds_is_refused);
    RUN_TEST(test_every_declared_bound_is_enforced_at_its_edge);
    RUN_TEST(test_rest_stays_at_rest_across_the_declared_range);
    RUN_TEST(test_determinism_across_the_declared_range);
    RUN_TEST(test_a_step_matches_the_closed_form_across_the_declared_range);
    RUN_TEST(test_a_short_step_against_a_long_time_constant_stays_accurate);
    RUN_TEST(test_the_corners_of_the_declared_range_stay_finite);
    RUN_TEST(test_the_corners_of_the_declared_range_stay_at_rest);
    RUN_TEST(test_an_origin_against_a_value_changes_nothing_that_is_read);
    RUN_TEST(test_two_accounts_of_the_same_value_read_the_same);
    RUN_TEST(test_an_origin_of_an_undeclared_kind_is_refused);
    RUN_TEST(test_an_origin_with_no_kind_or_no_account_is_refused);
    RUN_TEST(test_a_statement_the_description_cannot_make_is_refused);
    RUN_TEST(test_an_origin_separated_from_its_marker_by_blanks_is_read);
    RUN_TEST(test_a_final_annotated_line_without_a_newline_is_read);
    RUN_TEST(test_a_description_claiming_no_machine_is_read_like_any_other);
    RUN_TEST(test_every_refusal_still_fires_on_a_line_carrying_an_origin);
    RUN_TEST(test_an_annotated_refusal_still_reports_the_range_it_was_outside);
    RUN_TEST(test_a_description_mixing_the_kinds_is_read_like_any_other);
    RUN_TEST(test_a_coefficient_omitted_from_an_annotated_description_is_still_refused);
    RUN_TEST(test_the_reference_description_is_admissible_and_advances_a_model);
    RUN_TEST(test_the_carried_description_is_refused_on_the_loaders_own_terms);
    RUN_TEST(test_the_reference_description_claims_a_machine);
    RUN_TEST(test_the_assumed_error_of_every_coefficient_is_readable);
    RUN_TEST(test_a_coefficient_the_structure_does_not_have_is_refused);
    RUN_TEST(test_a_value_with_no_error_is_undeclared_rather_than_zero);
    RUN_TEST(test_a_scale_outside_the_declared_range_is_refused_rather_than_clamped);
    RUN_TEST(test_a_scale_inside_the_declared_range_writes_that_coefficient_alone);
    RUN_TEST(test_scaling_refuses_a_position_this_structure_does_not_have);
    RUN_TEST(test_the_position_of_every_coefficient_is_answered_by_name);
    RUN_TEST(test_whether_a_position_is_supply_driven_is_answered_for_every_one);
    RUN_TEST(test_a_budget_never_loaded_answers_nothing);
    RUN_TEST(test_a_refused_description_yields_no_budget);
    RUN_TEST(test_an_assumed_error_that_cannot_stand_is_refused);
    RUN_TEST(test_the_admissible_extremes_of_an_assumed_error_are_taken);
    RUN_TEST(test_an_assumed_error_changes_nothing_that_is_read);
    RUN_TEST(test_every_refusal_still_fires_on_a_line_carrying_an_assumed_error);
    RUN_TEST(test_a_line_carries_both_annotations_in_the_fixed_order);
    RUN_TEST(test_a_marker_inside_an_account_is_part_of_the_account);
    RUN_TEST(test_an_assumed_error_is_read_however_it_is_spaced);
    RUN_TEST(test_the_robustness_classes_are_one_enumerated_set);
    RUN_TEST(test_the_reference_description_states_how_wrong_every_value_may_be);
    RUN_TEST(test_every_state_this_structure_keeps_takes_a_write);
    RUN_TEST(test_writing_one_state_leaves_the_others_where_they_were);
    RUN_TEST(test_a_state_written_to_an_instance_that_cannot_take_it_is_refused);
    RUN_TEST(test_the_seam_names_the_drawn_rate_as_a_quantity);
    RUN_TEST(test_the_reference_structure_answers_the_drawn_rate);
    RUN_TEST(test_the_drawn_rate_follows_the_commanded_pump_level);
    RUN_TEST(test_a_pump_commanded_off_reports_no_flow);
    RUN_TEST(test_the_drawn_rate_is_unmoved_by_the_heaters);
    RUN_TEST(test_the_shipped_description_declares_an_assumed_error_for_the_drawn_rate);
    RUN_TEST(test_the_drawn_rate_is_reached_end_to_end_through_the_seam);
    RUN_TEST(test_the_seam_names_the_steam_draw_rate_as_a_quantity);
    RUN_TEST(test_the_reference_structure_answers_the_steam_draw_rate);
    RUN_TEST(test_the_reported_steam_draw_rate_is_the_demand_the_step_was_given);
    RUN_TEST(test_an_inadmissible_steam_demand_is_reported_as_no_draw);
    RUN_TEST(test_the_steam_draw_rate_is_reached_end_to_end_through_the_seam);
    RUN_TEST(test_a_draw_cools_the_heated_mass_faster_than_no_draw);
    RUN_TEST(test_the_settled_droop_is_the_energy_balance_the_coefficients_state);
    RUN_TEST(test_the_steam_mass_gains_no_term_from_the_draw);
    RUN_TEST(test_the_casting_depends_on_where_the_water_leaving_sits);
    RUN_TEST(test_the_outlet_time_constant_reaches_the_casting_only_under_a_draw);
    RUN_TEST(test_the_coupled_step_matches_the_pair_integrated_independently);
    RUN_TEST(test_the_pair_lands_in_the_same_place_however_the_step_is_cut);
    RUN_TEST(test_the_outlet_settles_faster_the_harder_the_draw);
    RUN_TEST(test_a_closed_pump_relaxes_at_the_conduction_constant);
    RUN_TEST(test_the_feed_temperature_is_read_rather_than_ambient);
    RUN_TEST(test_the_drawn_power_is_the_volume_rate_times_the_heat_capacity);
    RUN_TEST(test_a_toggling_draw_against_a_cold_casting_stays_bounded);
    RUN_TEST(test_the_statement_writes_out_the_relation_flow_enters);
    RUN_TEST(test_the_statement_records_the_outlet_coefficients_as_reachable);
    RUN_TEST(test_the_superseded_outlet_declaration_was_re_derived);
    RUN_TEST(test_the_omissions_the_flow_term_does_not_close_are_still_recorded);
    RUN_TEST(test_the_steam_block_pays_the_heat_of_what_is_drawn_off_it);
    RUN_TEST(test_what_a_draw_costs_the_block_does_not_depend_on_where_it_sits);
    RUN_TEST(test_with_the_wand_shut_the_latent_coefficient_reaches_nothing);
    RUN_TEST(test_a_steam_draw_leaves_the_coffee_side_alone);
    RUN_TEST(test_the_steam_pressure_accumulates_the_draw_rather_than_recomputing_it);
    RUN_TEST(test_the_steam_pressure_is_the_relation_again_the_step_the_draw_stops);
    RUN_TEST(test_a_closed_draw_leaves_no_trace_a_later_step_can_see);
    RUN_TEST(test_the_structure_stays_admissible_with_a_draw_open);
    RUN_TEST(test_a_draw_the_path_cannot_supply_stops_at_nothing);
    RUN_TEST(test_the_cost_of_a_draw_follows_the_temperature_the_feed_arrives_at);
    RUN_TEST(test_a_feed_arriving_past_boiling_costs_a_draw_nothing_extra);
    RUN_TEST(test_a_draw_beyond_the_commanded_feed_is_honoured_at_the_feed);
    RUN_TEST(test_a_draw_the_feed_can_supply_is_honoured_whole);
    RUN_TEST(test_a_draw_with_the_feed_shut_costs_the_block_and_the_path_nothing);
    RUN_TEST(test_the_reported_draw_is_the_demand_even_where_the_feed_bounds_it);
    RUN_TEST(test_shutting_the_feed_mid_draw_holds_the_departure_rather_than_returning_it);
    RUN_TEST(test_the_commanded_feed_is_proportional_to_the_level);
    RUN_TEST(test_the_gaps_the_feed_relations_close_are_no_longer_recorded_as_omissions);
    RUN_TEST(test_a_demand_that_is_not_a_draw_is_read_as_no_draw);
    RUN_TEST(test_the_steam_draws_coefficients_carry_enforced_admissible_ranges);
    RUN_TEST(test_the_steam_draws_coefficients_declare_an_origin_and_an_error);
    RUN_TEST(test_a_written_state_is_what_the_next_step_advances_from);
    RUN_TEST(test_the_thermoblock_declares_both_the_group_and_the_spout);
    RUN_TEST(test_the_thermoblock_answers_the_same_mass_for_both_points);
    RUN_TEST(test_the_group_and_the_spout_are_reported_as_sharing_a_mass);
    RUN_TEST(test_a_delivery_point_the_thermoblock_does_not_serve_is_refused);
    RUN_TEST(test_the_delivery_queries_refuse_null_output_arguments);
    return UNITY_END();
}
