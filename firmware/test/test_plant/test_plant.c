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

static const plant_actuation_t AT_REST = {{0u, 0u, 0u}};
static const plant_actuation_t HEATING = {{ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, 0u}};
/* Heat and pump together, so no coefficient is left out of the trajectory. */
static const plant_actuation_t WORKING = {
    {ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE / 2u}};

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
    const plant_actuation_t over_scale = {{ACTUATION_FULL_SCALE + 1u, 0u, 0u}};

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
    const plant_actuation_t brew_only = {{ACTUATION_FULL_SCALE, 0u, 0u}};
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
    TEST_ASSERT_TRUE(plant_model_step(&model, &at_scale, STEP_MS));
    TEST_ASSERT_FALSE(plant_model_step(&model, &beyond_scale, STEP_MS));
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C2: The plant-model seam carries each
/// structure's statement of the channels it answers.
/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C3: Every structure behind the seam
/// declares which actuation channels it answers.
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
        TEST_ASSERT_TRUE(plant_model_step_reporting(&model, &one_channel, STEP_MS, &refusal));
        TEST_ASSERT_EQUAL(PLANT_STEP_OK, refusal.fault);
    }
}

/// SOL-PLANT-ACTUATION-CHANNEL-DECLARATION.C7: The structures and the control
/// logic behave identically after the vocabulary is unified.
static void test_the_trajectory_is_what_it_was_before_the_vocabulary_was_unified(void)
{
    /*
     * Recorded from the build as it stood before the actuation vocabulary was
     * unified, and carried here as values rather than regenerated: regenerating
     * them from this build would compare the change with itself and pass
     * whatever it did to the equations. Written as hexadecimal literals because
     * they are exact -- nothing here touches an equation, so a difference of one
     * bit is a difference this test exists to report.
     */
    static const float EXPECTED[][PLANT_QUANTITY_COUNT] = {
        {0x1.4p+4f, 0x1.4p+4f, 0x0p+0f, 0x0p+0f},
        {0x1.4p+4f, 0x1.4p+4f, 0x0p+0f, 0x0p+0f},
        {0x1.c8693p+4f, 0x1.8a64c2p+4f, 0x0p+0f, 0x0p+0f},
        {0x1.6a718ap+5f, 0x1.0ec6eap+5f, 0x1.1fd73ap+2f, 0x0p+0f},
        {0x1.28fbf8p+8f, 0x1.693cd6p+7f, 0x1.1ffff8p+2f, 0x1.692c1cp+1f},
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
                                      "steam.thermal_mass_j_per_k = 900\n"
                                      "steam.heater_power_w = 1400\n"
                                      "steam.loss_w_per_k = 2.2\n"
                                      "pump.pressure_bar = 9\n"
                                      "brew.pressure_time_constant_s = 0.8\n"
                                      "steam.saturation_temperature_c = 100\n"
                                      "steam.pressure_bar_per_k = 0.035\n";
    plant_parameters_t recorded;
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &recorded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &recorded));

    for (size_t checkpoint = 0u; checkpoint < sizeof(STEPS) / sizeof(STEPS[0]); checkpoint++) {
        for (int i = 0; i < STEPS[checkpoint]; i++) {
            TEST_ASSERT_TRUE(plant_model_step(&model, UNDER[checkpoint], STEP_MS));
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
#define REFERENCE_MAX 8192

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
        TEST_ASSERT_TRUE(plant_model_step(&model, &WORKING, STEP_MS));
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

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_actuation_channels_are_one_enumerated_set);
    RUN_TEST(test_the_structure_states_which_channels_it_answers);
    RUN_TEST(test_the_trajectory_is_what_it_was_before_the_vocabulary_was_unified);
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
    return UNITY_END();
}
