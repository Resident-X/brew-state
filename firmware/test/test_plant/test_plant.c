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
#include <string.h>

#include <unity.h>

#include "plant_model.h"

/* One coefficient of the structure under test, and an admissible value for it. */
typedef struct {
    const char *name;
    double value;
} coefficient_t;

/*
 * Admissible, plausible, and describing no machine -- the same standing as the
 * descriptions under params/. What matters here is only that they are accepted
 * and that changing any one of them is visible.
 */
static const coefficient_t NOMINAL[] = {
    {"ambient_temperature_c", 20.0},
    {"brew.thermal_mass_j_per_k", 420.0},
    {"brew.heater_power_w", 1200.0},
    {"brew.loss_w_per_k", 1.5},
    {"steam.thermal_mass_j_per_k", 900.0},
    {"steam.heater_power_w", 1400.0},
    {"steam.loss_w_per_k", 2.2},
    {"pump.pressure_bar", 9.0},
    {"brew.pressure_time_constant_s", 0.8},
    {"steam.saturation_temperature_c", 100.0},
    {"steam.pressure_bar_per_k", 0.035},
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

static const plant_actuation_t AT_REST = {0u, 0u, 0u};
static const plant_actuation_t HEATING = {PLANT_ACTUATION_FULL_SCALE, PLANT_ACTUATION_FULL_SCALE,
                                          0u};
/* Heat and pump together, so no coefficient is left out of the trajectory. */
static const plant_actuation_t WORKING = {PLANT_ACTUATION_FULL_SCALE, PLANT_ACTUATION_FULL_SCALE,
                                          PLANT_ACTUATION_FULL_SCALE / 2u};

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

/* Run `steps` steps under one actuation and leave the quantities in `out`. */
static void run(plant_model_t *model, const plant_actuation_t *actuation, int steps,
                float out[PLANT_QUANTITY_COUNT])
{
    for (int i = 0; i < steps; i++) {
        TEST_ASSERT_TRUE(plant_model_step(model, actuation, STEP_MS));
    }
    read_all(model, out);
}

/*
 * A number standing for the whole trajectory rather than its endpoint.
 *
 * Every quantity at every step is folded in, because a coefficient can matter
 * to the path without mattering to where the path ends: a time constant
 * changes how fast a pressure settles and not what it settles at, so comparing
 * final values alone would report it as unused.
 *
 * The accumulator is deliberately wider than the quantities it sums. It is a
 * comparison device rather than part of the model, and summing thousands of
 * single-precision values into a single-precision total would lose the small
 * differences this exists to detect -- which would quietly blind the check that
 * every coefficient reaches the equations.
 */
static double signature(plant_model_t *model, const plant_actuation_t *actuation, int steps)
{
    double total = 0.0;

    for (int i = 0; i < steps; i++) {
        float quantities[PLANT_QUANTITY_COUNT];
        TEST_ASSERT_TRUE(plant_model_step(model, actuation, STEP_MS));
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
 */
static size_t describe_with(size_t index, const char *token, char *out, size_t capacity)
{
    size_t used = 0u;

    for (size_t i = 0u; i < COEFFICIENT_COUNT; i++) {
        const int written = snprintf(out + used, capacity - used, "%s = %s\n", NOMINAL[i].name,
                                     i == index ? token : "1.0");
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
    TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, STEP_MS));
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
    TEST_ASSERT_TRUE(plant_model_step(&model, &HEATING, STEP_MS));
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
    const plant_actuation_t over_scale = {PLANT_ACTUATION_FULL_SCALE + 1u, 0u, 0u};

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    read_all(&model, before);
    TEST_ASSERT_FALSE(plant_model_step(&model, &over_scale, STEP_MS));
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
    TEST_ASSERT_FALSE(plant_model_step(&model, &HEATING, STEP_MS));
    TEST_ASSERT_FALSE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &value));

    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));
    TEST_ASSERT_FALSE(plant_model_step(&model, &HEATING, 0u));
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
            written = snprintf(text + used, sizeof(text) - used, "%s = 1.0\n", NOMINAL[i].name);
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, STEP_MS));
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
    const plant_actuation_t brew_only = {PLANT_ACTUATION_FULL_SCALE, 0u, 0u};

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
                TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 100u));
            }
            read_all(&model, before);
            for (int n = 0; n < ACCUMULATION_STEPS; n++) {
                TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, intervals_ms[k]));
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
    const plant_actuation_t brew_only = {PLANT_ACTUATION_FULL_SCALE, 0u, 0u};
    double values[COEFFICIENT_COUNT];
    char text[DESCRIPTION_MAX];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];

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

    read_all(&model, before);
    for (int n = 0; n < ACCUMULATION_STEPS; n++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &brew_only, 10u));
    }
    read_all(&model, after);

    const double seconds = (10.0 * (double)ACCUMULATION_STEPS) / 1000.0;
    const double settling = values[I_AMBIENT] + values[I_BREW_POWER] / values[I_BREW_LOSS];
    const double from = (double)before[PLANT_QUANTITY_BREW_TEMPERATURE_C];
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &AT_REST, STEP_MS));
        read_all(&model, after);
        TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
    }
}

int main(void)
{
    UNITY_BEGIN();
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
    RUN_TEST(test_every_declared_bound_is_enforced_at_its_edge);
    RUN_TEST(test_rest_stays_at_rest_across_the_declared_range);
    RUN_TEST(test_determinism_across_the_declared_range);
    RUN_TEST(test_a_step_matches_the_closed_form_across_the_declared_range);
    RUN_TEST(test_a_short_step_against_a_long_time_constant_stays_accurate);
    RUN_TEST(test_the_corners_of_the_declared_range_stay_finite);
    RUN_TEST(test_the_corners_of_the_declared_range_stay_at_rest);
    return UNITY_END();
}
