/*
 * The host report seam, and the casting-ceiling statement made through it.
 *
 * The seam writes one finding as a text line and a JSON line from one field
 * list. These tests read both lines back with parsers of their own, written
 * here and sharing nothing with the writer, and compare them field by field: a
 * writer that rendered a value two ways, dropped a field from one form, or
 * reordered either would be caught by the comparison and by nothing the writer
 * says about itself.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <unity.h>

#include "casting_ceiling_report.h"
#include "dryness_report.h"
#include "host_report.h"
#include "plant_model.h"

void setUp(void) {}
void tearDown(void) {}

#define FIELD_MAX 16
#define TEXT_MAX 4096

typedef struct {
    char key[48];
    char value[160];
    bool quoted;
} parsed_field_t;

typedef struct {
    char what[64];
    size_t count;
    parsed_field_t fields[FIELD_MAX];
} parsed_line_t;

/* Everything a stream received, from the start. */
static void drain(FILE *stream, char *out, size_t capacity)
{
    rewind(stream);
    const size_t used = fread(out, 1u, capacity - 1u, stream);
    out[used] = '\0';
}

/* The line beginning with `prefix`, copied without its newline; false when absent. */
static bool line_with_prefix(const char *text, const char *prefix, char *line, size_t capacity)
{
    const size_t prefix_length = strlen(prefix);
    const char *cursor = text;
    while (*cursor != '\0') {
        const char *end = strchr(cursor, '\n');
        const size_t length = end != NULL ? (size_t)(end - cursor) : strlen(cursor);
        if (length >= prefix_length && strncmp(cursor, prefix, prefix_length) == 0) {
            if (length >= capacity) {
                return false;
            }
            memcpy(line, cursor, length);
            line[length] = '\0';
            return true;
        }
        if (end == NULL) {
            break;
        }
        cursor = end + 1;
    }
    return false;
}

/* `HOST <what> k=v k="text v" ...` */
static bool parse_text_line(const char *line, parsed_line_t *out)
{
    memset(out, 0, sizeof(*out));
    if (strncmp(line, "HOST ", 5) != 0) {
        return false;
    }
    const char *c = line + 5;
    size_t n = 0u;
    while (*c != '\0' && *c != ' ') {
        if (n + 1u >= sizeof(out->what)) {
            return false;
        }
        out->what[n++] = *c++;
    }
    while (*c == ' ') {
        c++;
        if (*c == '\0') {
            break;
        }
        if (out->count == FIELD_MAX) {
            return false;
        }
        parsed_field_t *field = &out->fields[out->count];
        size_t k = 0u;
        while (*c != '=' && *c != '\0') {
            if (k + 1u >= sizeof(field->key)) {
                return false;
            }
            field->key[k++] = *c++;
        }
        if (*c != '=') {
            return false;
        }
        c++;
        size_t v = 0u;
        if (*c == '"') {
            field->quoted = true;
            c++;
            while (*c != '"' && *c != '\0') {
                if (v + 1u >= sizeof(field->value)) {
                    return false;
                }
                field->value[v++] = *c++;
            }
            if (*c != '"') {
                return false;
            }
            c++;
        } else {
            while (*c != ' ' && *c != '\0') {
                if (v + 1u >= sizeof(field->value)) {
                    return false;
                }
                field->value[v++] = *c++;
            }
        }
        out->count++;
    }
    return *c == '\0';
}

/* `HOST-JSON {"what":"<what>","k":v,"k":"text"}` */
static bool parse_json_line(const char *line, parsed_line_t *out)
{
    memset(out, 0, sizeof(*out));
    static const char HEAD[] = "HOST-JSON {\"what\":\"";
    if (strncmp(line, HEAD, sizeof(HEAD) - 1u) != 0) {
        return false;
    }
    const char *c = line + sizeof(HEAD) - 1u;
    size_t n = 0u;
    while (*c != '"' && *c != '\0') {
        if (n + 1u >= sizeof(out->what)) {
            return false;
        }
        out->what[n++] = *c++;
    }
    if (*c != '"') {
        return false;
    }
    c++;
    while (*c == ',') {
        c++;
        if (*c != '"' || out->count == FIELD_MAX) {
            return false;
        }
        c++;
        parsed_field_t *field = &out->fields[out->count];
        size_t k = 0u;
        while (*c != '"' && *c != '\0') {
            if (k + 1u >= sizeof(field->key)) {
                return false;
            }
            field->key[k++] = *c++;
        }
        if (c[0] != '"' || c[1] != ':') {
            return false;
        }
        c += 2;
        size_t v = 0u;
        if (*c == '"') {
            field->quoted = true;
            c++;
            while (*c != '"' && *c != '\0') {
                if (v + 1u >= sizeof(field->value)) {
                    return false;
                }
                field->value[v++] = *c++;
            }
            if (*c != '"') {
                return false;
            }
            c++;
        } else {
            while (*c != ',' && *c != '}' && *c != '\0') {
                if (v + 1u >= sizeof(field->value)) {
                    return false;
                }
                field->value[v++] = *c++;
            }
        }
        out->count++;
    }
    return c[0] == '}' && c[1] == '\0';
}

/* Whether the two lines state the same finding, field by field and in order. */
static bool same_finding(const parsed_line_t *text, const parsed_line_t *json)
{
    if (strcmp(text->what, json->what) != 0 || text->count != json->count) {
        return false;
    }
    for (size_t i = 0u; i < text->count; i++) {
        const parsed_field_t *a = &text->fields[i];
        const parsed_field_t *b = &json->fields[i];
        if (strcmp(a->key, b->key) != 0 || a->quoted != b->quoted ||
            strcmp(a->value, b->value) != 0) {
            return false;
        }
    }
    return true;
}

/* Both lines of `output`, parsed; asserts they are present and well formed. */
static void read_both(const char *output, parsed_line_t *text, parsed_line_t *json)
{
    char line[TEXT_MAX];
    TEST_ASSERT_TRUE_MESSAGE(line_with_prefix(output, "HOST ", line, sizeof(line)),
                             "no text line was written");
    TEST_ASSERT_TRUE_MESSAGE(parse_text_line(line, text), "the text line is malformed");
    TEST_ASSERT_TRUE_MESSAGE(line_with_prefix(output, "HOST-JSON ", line, sizeof(line)),
                             "no JSON line was written");
    TEST_ASSERT_TRUE_MESSAGE(parse_json_line(line, json), "the JSON line is malformed");
}

static const parsed_field_t *field_named(const parsed_line_t *line, const char *key)
{
    for (size_t i = 0u; i < line->count; i++) {
        if (strcmp(line->fields[i].key, key) == 0) {
            return &line->fields[i];
        }
    }
    return NULL;
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C3: The two forms are written by one report
/// seam from one field list, shared with the dryness report of C9, and a test
/// parses the JSON line and compares it field by field with the text line.
static void test_the_text_line_and_the_json_line_state_the_same_fields(void)
{
    char output[TEXT_MAX];
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    const host_report_field_t fields[] = {
        host_report_number("ceiling_c", 150.0),
        host_report_number("fraction", 0.1f),
        host_report_number("negative", -3.25),
        host_report_integer("steps", 1234567890123LL),
        host_report_boolean("claimed", true),
        host_report_boolean("excluded", false),
        host_report_text("basis", "saturation at the declared ceiling"),
        host_report_text("empty", ""),
    };
    TEST_ASSERT_TRUE(host_report_emit(stream, "a-finding", fields, 8u));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);

    parsed_line_t text;
    parsed_line_t json;
    read_both(output, &text, &json);

    TEST_ASSERT_EQUAL_STRING("a-finding", text.what);
    TEST_ASSERT_EQUAL_UINT(8u, text.count);
    TEST_ASSERT_TRUE(same_finding(&text, &json));
    TEST_ASSERT_EQUAL_STRING("saturation at the declared ceiling",
                             field_named(&json, "basis")->value);
    TEST_ASSERT_TRUE(field_named(&json, "basis")->quoted);
    TEST_ASSERT_FALSE(field_named(&json, "steps")->quoted);
    TEST_ASSERT_EQUAL_STRING("true", field_named(&json, "claimed")->value);
    TEST_ASSERT_EQUAL_STRING("false", field_named(&text, "excluded")->value);
    TEST_ASSERT_EQUAL_STRING("", field_named(&json, "empty")->value);
    /* The one rendering is exact for a single-precision value: it reads back as it was. */
    TEST_ASSERT_EQUAL_FLOAT(0.1f, (float)strtod(field_named(&json, "fraction")->value, NULL));
    TEST_ASSERT_TRUE(strtod(field_named(&text, "negative")->value, NULL) == -3.25);
    TEST_ASSERT_TRUE(strtoll(field_named(&json, "steps")->value, NULL, 10) == 1234567890123LL);
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C3: The two forms are written by one report
/// seam from one field list, shared with the dryness report of C9, and a test
/// parses the JSON line and compares it field by field with the text line.
static void test_a_finding_with_no_fields_is_still_stated_in_both_forms(void)
{
    char output[TEXT_MAX];
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    TEST_ASSERT_TRUE(host_report_emit(stream, "bare", NULL, 0u));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);

    parsed_line_t text;
    parsed_line_t json;
    read_both(output, &text, &json);
    TEST_ASSERT_EQUAL_UINT(0u, text.count);
    TEST_ASSERT_TRUE(same_finding(&text, &json));
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C3: The two forms are written by one report
/// seam from one field list, shared with the dryness report of C9, and a test
/// parses the JSON line and compares it field by field with the text line.
static void test_the_comparison_catches_a_json_line_that_disagrees_or_is_absent(void)
{
    char output[TEXT_MAX];
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    const host_report_field_t fields[] = {
        host_report_number("a", 1.5),
        host_report_text("b", "words here"),
    };
    TEST_ASSERT_TRUE(host_report_emit(stream, "pair", fields, 2u));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);

    parsed_line_t text;
    parsed_line_t json;
    read_both(output, &text, &json);
    TEST_ASSERT_TRUE(same_finding(&text, &json));

    parsed_line_t changed = json;
    (void)strcpy(changed.fields[0].value, "1.6");
    TEST_ASSERT_FALSE(same_finding(&text, &changed));

    changed = json;
    changed.count = 1u;
    TEST_ASSERT_FALSE(same_finding(&text, &changed));

    changed = json;
    (void)strcpy(changed.fields[1].key, "c");
    TEST_ASSERT_FALSE(same_finding(&text, &changed));

    changed = json;
    changed.fields[1].quoted = false;
    TEST_ASSERT_FALSE(same_finding(&text, &changed));

    /* A text line alone, with the JSON line removed, is not a statement in both forms. */
    char line[TEXT_MAX];
    TEST_ASSERT_FALSE(line_with_prefix("HOST pair a=1.5 b=\"words here\"\n", "HOST-JSON ", line,
                                       sizeof(line)));
    /* And a truncated JSON line does not parse. */
    TEST_ASSERT_FALSE(parse_json_line("HOST-JSON {\"what\":\"pair\",\"a\":1.5", &changed));
    TEST_ASSERT_FALSE(parse_json_line("HOST-JSON {\"what\":\"pair\",\"a\":\"x}", &changed));
}

static void assert_nothing_written(const char *what, const host_report_field_t *fields,
                                   size_t count)
{
    char output[TEXT_MAX];
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    TEST_ASSERT_FALSE(host_report_emit(stream, what, fields, count));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);
    TEST_ASSERT_EQUAL_STRING("", output);
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C3: The two forms are written by one report
/// seam from one field list, shared with the dryness report of C9, and a test
/// parses the JSON line and compares it field by field with the text line.
static void test_a_list_that_cannot_be_stated_in_both_forms_writes_nothing(void)
{
    const host_report_field_t not_finite[] = {host_report_number("ok", 1.0),
                                              host_report_number("bad", INFINITY)};
    assert_nothing_written("finding", not_finite, 2u);

    const host_report_field_t not_a_number[] = {host_report_number("bad", NAN)};
    assert_nothing_written("finding", not_a_number, 1u);

    const host_report_field_t duplicate[] = {host_report_number("same", 1.0),
                                             host_report_integer("same", 2)};
    assert_nothing_written("finding", duplicate, 2u);

    const host_report_field_t spaced_key[] = {host_report_number("two words", 1.0)};
    assert_nothing_written("finding", spaced_key, 1u);

    const host_report_field_t empty_key[] = {host_report_number("", 1.0)};
    assert_nothing_written("finding", empty_key, 1u);

    const host_report_field_t null_key[] = {host_report_number(NULL, 1.0)};
    assert_nothing_written("finding", null_key, 1u);

    const host_report_field_t quote[] = {host_report_text("t", "say \"hi\"")};
    assert_nothing_written("finding", quote, 1u);

    const host_report_field_t backslash[] = {host_report_text("t", "a\\b")};
    assert_nothing_written("finding", backslash, 1u);

    const host_report_field_t newline[] = {host_report_text("t", "line\nbreak")};
    assert_nothing_written("finding", newline, 1u);

    const host_report_field_t null_text[] = {host_report_text("t", NULL)};
    assert_nothing_written("finding", null_text, 1u);

    const host_report_field_t fine[] = {host_report_number("ok", 1.0)};
    assert_nothing_written("", fine, 1u);
    assert_nothing_written(NULL, fine, 1u);
    assert_nothing_written("Not Plain", fine, 1u);
    assert_nothing_written("finding", NULL, 1u);

    TEST_ASSERT_FALSE(host_report_emit(NULL, "finding", fine, 1u));
}

/* The reference description's record. */
static char description_text[65536];

static plant_parameters_t reference_parameters(void)
{
    plant_parameters_t parameters;
    plant_parameter_error_t fault;
    FILE *handle = fopen(REFERENCE_DESCRIPTION_PATH, "rb");
    TEST_ASSERT_NOT_NULL(handle);
    const size_t used = fread(description_text, 1u, sizeof(description_text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u && used < sizeof(description_text) - 1u);
    memset(&fault, 0, sizeof(fault));
    char message[160];
    (void)snprintf(message, sizeof(message), "the reference description was refused at %s (line %u)",
                   fault.parameter, (unsigned)fault.line);
    const bool loaded = plant_parameters_load(description_text, used, &parameters, &fault);
    (void)snprintf(message, sizeof(message), "the reference description was refused at %s (line %u)",
                   fault.parameter, (unsigned)fault.line);
    TEST_ASSERT_TRUE_MESSAGE(loaded, message);
    return parameters;
}

static float coefficient(const plant_parameters_t *parameters, const char *name)
{
    size_t at = 0u;
    float value = 0.0f;
    TEST_ASSERT_TRUE(plant_parameter_position(name, &at));
    TEST_ASSERT_TRUE(plant_parameter_value(parameters, at, &value));
    return value;
}

/* The gauge pressure a shut block holding liquid reports with its casting at `casting_c`. */
static float shut_pressure_at(const plant_parameters_t *parameters, float casting_c)
{
    plant_model_t model;
    plant_actuation_t feed_full = {{0u}};
    feed_full.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = 1000u;
    float pressure = -1.0f;
    TEST_ASSERT_TRUE(plant_model_init(&model, parameters));
    TEST_ASSERT_TRUE(plant_model_set_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, casting_c));
    TEST_ASSERT_TRUE(plant_model_step(&model, &feed_full, 0.0f, 100u));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &pressure));
    return pressure;
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C3: Each host run reports the bound in both
/// text and JSON form, stating the ceiling's value, that it is saturation at the
/// declared ceiling, and that it is a control limit and not containment.
static void test_the_casting_ceiling_is_reported_in_both_forms_with_what_it_is(void)
{
    char output[TEXT_MAX];
    const plant_parameters_t parameters = reference_parameters();
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    TEST_ASSERT_EQUAL_INT(CASTING_CEILING_REPORTED, casting_ceiling_report(stream, &parameters));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);

    parsed_line_t text;
    parsed_line_t json;
    read_both(output, &text, &json);
    TEST_ASSERT_TRUE(same_finding(&text, &json));
    TEST_ASSERT_EQUAL_STRING("steam-casting-ceiling", json.what);

    const float ceiling_c = coefficient(&parameters, "steam.casting_ceiling_c");
    TEST_ASSERT_EQUAL_FLOAT(ceiling_c, (float)strtod(field_named(&json, "ceiling_c")->value, NULL));
    TEST_ASSERT_EQUAL_FLOAT(ceiling_c, (float)strtod(field_named(&text, "ceiling_c")->value, NULL));

    const float bound_bar = (float)strtod(field_named(&json, "ceiling_pressure_bar_gauge")->value, NULL);
    TEST_ASSERT_TRUE(bound_bar > 0.0f);
    /*
     * The stated bound is what the model reports with the casting at the ceiling
     * itself, give or take the little the casting cools over the probe's step.
     */
    const float at_ceiling_bar = shut_pressure_at(&parameters, ceiling_c);
    TEST_ASSERT_TRUE(at_ceiling_bar <= bound_bar * 1.0001f);
    TEST_ASSERT_TRUE(at_ceiling_bar >= bound_bar * 0.99f);
    /* And the model never reports more than it with the casting well beyond. */
    TEST_ASSERT_TRUE(shut_pressure_at(&parameters, ceiling_c + 60.0f) <= bound_bar * 1.0001f);

    TEST_ASSERT_EQUAL_STRING("saturation at the declared ceiling", field_named(&json, "basis")->value);
    TEST_ASSERT_EQUAL_STRING("a control limit and not containment", field_named(&text, "nature")->value);
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C3: Each host run reports the bound in both
/// text and JSON form, stating the ceiling's value, that it is saturation at the
/// declared ceiling, and that it is a control limit and not containment.
static void test_the_reported_bound_follows_the_declared_ceiling_and_not_a_constant(void)
{
    char output[TEXT_MAX];
    plant_parameters_t parameters = reference_parameters();
    size_t at = 0u;
    TEST_ASSERT_TRUE(plant_parameter_position("steam.casting_ceiling_c", &at));
    const float declared_c = coefficient(&parameters, "steam.casting_ceiling_c");
    TEST_ASSERT_TRUE(plant_parameter_scale(&parameters, at, 1.2f));

    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);
    TEST_ASSERT_EQUAL_INT(CASTING_CEILING_REPORTED, casting_ceiling_report(stream, &parameters));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);

    parsed_line_t text;
    parsed_line_t json;
    read_both(output, &text, &json);
    TEST_ASSERT_TRUE(same_finding(&text, &json));
    TEST_ASSERT_FLOAT_WITHIN(0.01f, declared_c * 1.2f,
                             (float)strtod(field_named(&json, "ceiling_c")->value, NULL));
    const float raised_bar = (float)strtod(field_named(&json, "ceiling_pressure_bar_gauge")->value, NULL);
    const plant_parameters_t original = reference_parameters();
    TEST_ASSERT_TRUE(raised_bar > shut_pressure_at(&original, declared_c));
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C3: Each host run reports the bound in both
/// text and JSON form, stating the ceiling's value, that it is saturation at the
/// declared ceiling, and that it is a control limit and not containment.
static void test_a_block_declared_to_start_dry_still_states_the_bound(void)
{
    char output[TEXT_MAX];
    plant_parameters_t parameters = reference_parameters();
    size_t at = 0u;
    TEST_ASSERT_TRUE(plant_parameter_position("steam.initial_inventory_ml", &at));
    TEST_ASSERT_TRUE(plant_parameter_scale(&parameters, at, 0.0f));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, coefficient(&parameters, "steam.initial_inventory_ml"));

    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);
    TEST_ASSERT_EQUAL_INT(CASTING_CEILING_REPORTED, casting_ceiling_report(stream, &parameters));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);

    parsed_line_t text;
    parsed_line_t json;
    read_both(output, &text, &json);
    TEST_ASSERT_TRUE(same_finding(&text, &json));
    TEST_ASSERT_TRUE(strtod(field_named(&json, "ceiling_pressure_bar_gauge")->value, NULL) > 0.0);
}

static void assert_nothing_written_dryness(const dryness_finding_t *finding)
{
    char output[TEXT_MAX];
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    TEST_ASSERT_FALSE(dryness_report(stream, finding));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);
    TEST_ASSERT_EQUAL_STRING("", output);
}

#define CARRY_OVER_CAVEAT "droplet carry-over is not excluded without a calorimetric test"

/* Write a dryness statement and read both forms of it back. */
static void state_dryness(const dryness_finding_t *finding, parsed_line_t *text,
                          parsed_line_t *json)
{
    char output[TEXT_MAX];
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    TEST_ASSERT_TRUE(dryness_report(stream, finding));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);

    read_both(output, text, json);
    TEST_ASSERT_TRUE(same_finding(text, json));
    TEST_ASSERT_EQUAL_STRING("steam-dryness", json->what);
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C9: Every surface that states steam is dry
/// bases the claim on superheat above saturation at the measured pressure alone,
/// names the superheat and pressure it rests on, says the superheat is modelled at
/// the outlet and confirmed by no sensor, and states that droplet carry-over is not
/// excluded without a calorimetric test. The claim and the caveat appear in both
/// the text and the JSON form of each run.
static void test_a_dry_steam_claim_names_its_superheat_and_pressure_and_carries_the_caveat(void)
{
    const dryness_finding_t finding = {true, 6.25f, 0.875f};
    parsed_line_t text;
    parsed_line_t json;

    state_dryness(&finding, &text, &json);

    const parsed_line_t *const forms[2] = {&text, &json};
    for (size_t i = 0u; i < 2u; i++) {
        const parsed_line_t *const form = forms[i];
        TEST_ASSERT_EQUAL_STRING("true", field_named(form, "dry")->value);
        TEST_ASSERT_EQUAL_FLOAT(6.25f, (float)strtod(field_named(form, "superheat_k")->value, NULL));
        TEST_ASSERT_EQUAL_FLOAT(
            0.875f, (float)strtod(field_named(form, "pressure_bar_gauge")->value, NULL));
        TEST_ASSERT_EQUAL_STRING(CARRY_OVER_CAVEAT, field_named(form, "carry_over")->value);
        TEST_ASSERT_EQUAL_STRING("modelled at the outlet and confirmed by no sensor",
                                 field_named(form, "superheat_source")->value);
        TEST_ASSERT_EQUAL_STRING("superheat above saturation at the measured steam pressure",
                                 field_named(form, "basis")->value);
        TEST_ASSERT_NOT_NULL(strstr(field_named(form, "claim")->value, "dry"));
    }
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C9: ... and a test fails when either form omits
/// the caveat or claims dryness at zero superheat.
///
/// At zero superheat the steam is not shown dry, and where no steam was made there
/// is nothing to claim; neither says "dry" true in either form, and both still
/// carry the caveat. A superheat that cannot be stated -- below nothing, or not a
/// number -- writes nothing rather than a claim.
static void test_no_dryness_is_claimed_at_zero_superheat_or_with_no_steam(void)
{
    static const dryness_finding_t CASES[] = {
        {true, 0.0f, 0.4f},
        {false, 0.0f, 0.0f},
        {false, 9.0f, 1.0f},
    };

    for (size_t i = 0u; i < sizeof(CASES) / sizeof(CASES[0]); i++) {
        parsed_line_t text;
        parsed_line_t json;

        state_dryness(&CASES[i], &text, &json);
        const parsed_line_t *const forms[2] = {&text, &json};
        for (size_t form = 0u; form < 2u; form++) {
            TEST_ASSERT_EQUAL_STRING_MESSAGE("false", field_named(forms[form], "dry")->value,
                                             "dryness was claimed without superheat");
            TEST_ASSERT_NULL(strstr(field_named(forms[form], "claim")->value, "left the outlet dry"));
            TEST_ASSERT_EQUAL_STRING(CARRY_OVER_CAVEAT, field_named(forms[form], "carry_over")->value);
        }
    }

    assert_nothing_written_dryness(&(dryness_finding_t){true, -0.5f, 1.0f});
    assert_nothing_written_dryness(&(dryness_finding_t){true, NAN, 1.0f});
    assert_nothing_written_dryness(&(dryness_finding_t){true, 3.0f, INFINITY});
    TEST_ASSERT_FALSE(dryness_report(NULL, &CASES[0]));
    TEST_ASSERT_FALSE(dryness_report(stdout, NULL));
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C9: A reader needs no knowledge of the source
/// or the graph to read it.
///
/// The check a reader's tool would make: the text line, read alone as a person
/// would, states the claim, both figures with their units' names and the caveat in
/// words, and the JSON line alone states the same.
static void test_the_dryness_statement_reads_without_the_source(void)
{
    const dryness_finding_t finding = {true, 4.5f, 1.25f};
    parsed_line_t text;
    parsed_line_t json;
    char output[TEXT_MAX];
    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);

    TEST_ASSERT_TRUE(dryness_report(stream, &finding));
    drain(stream, output, sizeof(output));
    (void)fclose(stream);
    read_both(output, &text, &json);

    char line[TEXT_MAX];
    TEST_ASSERT_TRUE(line_with_prefix(output, "HOST steam-dryness ", line, sizeof(line)));
    TEST_ASSERT_NOT_NULL(strstr(line, "superheat_k=4.5"));
    TEST_ASSERT_NOT_NULL(strstr(line, "pressure_bar_gauge=1.25"));
    TEST_ASSERT_NOT_NULL(strstr(line, "confirmed by no sensor"));
    TEST_ASSERT_NOT_NULL(strstr(line, CARRY_OVER_CAVEAT));
    TEST_ASSERT_TRUE(line_with_prefix(output, "HOST-JSON ", line, sizeof(line)));
    TEST_ASSERT_NOT_NULL(strstr(line, "\"superheat_k\":4.5"));
    TEST_ASSERT_NOT_NULL(strstr(line, CARRY_OVER_CAVEAT));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_text_line_and_the_json_line_state_the_same_fields);
    RUN_TEST(test_a_finding_with_no_fields_is_still_stated_in_both_forms);
    RUN_TEST(test_the_comparison_catches_a_json_line_that_disagrees_or_is_absent);
    RUN_TEST(test_a_list_that_cannot_be_stated_in_both_forms_writes_nothing);
    RUN_TEST(test_the_casting_ceiling_is_reported_in_both_forms_with_what_it_is);
    RUN_TEST(test_the_reported_bound_follows_the_declared_ceiling_and_not_a_constant);
    RUN_TEST(test_a_block_declared_to_start_dry_still_states_the_bound);
    RUN_TEST(test_a_dry_steam_claim_names_its_superheat_and_pressure_and_carries_the_caveat);
    RUN_TEST(test_no_dryness_is_claimed_at_zero_superheat_or_with_no_steam);
    RUN_TEST(test_the_dryness_statement_reads_without_the_source);
    return UNITY_END();
}
