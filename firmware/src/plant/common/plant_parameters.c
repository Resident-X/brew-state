/*
 * Populating a structure's parameter record from a parameter description.
 *
 * This is the one implementation, shared by every structure: a structure says
 * which coefficients it has, where each lands in its own record and what range
 * it declares admissible, and nothing beyond that table is needed to read a
 * description for it. Adding a structure is therefore supplying equations and
 * a table, not writing another parser.
 *
 * The description is read as bytes rather than as a file, so the same code
 * serves a host reading from disk and a target reading from wherever a record
 * is stored. Where a record lives on the target belongs to the stored-data
 * work and is not decided here.
 */
#include "plant_model.h"

#include <errno.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

/*
 * The longest value token a line may carry. It is well beyond the digits a
 * float distinguishes, so a token this long is a description that needs
 * looking at rather than a value to round; refusing it early keeps the copy
 * that terminates the token bounded.
 */
#define VALUE_TEXT_MAX 64

/*
 * Coefficients a structure may declare. The bitmap that records which ones a
 * description supplied is one word wide, and a structure with more
 * coefficients than that is refused outright rather than silently having the
 * surplus go unchecked for absence.
 */
#define SPEC_LIMIT 64

static bool is_blank(char c)
{
    return c == ' ' || c == '\t' || c == '\r' || c == '\v' || c == '\f';
}

/* Narrow the span [begin, end) to its first and last non-blank characters. */
static void trim(const char **begin, const char **end)
{
    while (*begin < *end && is_blank(**begin)) {
        (*begin)++;
    }
    while (*end > *begin && is_blank(*(*end - 1))) {
        (*end)--;
    }
}

static void report(plant_parameter_error_t *error, plant_parameter_fault_t fault, uint32_t line,
                   const char *name, size_t name_length)
{
    error->fault = fault;
    error->line = line;
    error->value = 0.0f;
    error->minimum = 0.0f;
    error->maximum = 0.0f;

    size_t copied = name_length;
    if (copied > PLANT_PARAMETER_NAME_MAX - 1u) {
        copied = PLANT_PARAMETER_NAME_MAX - 1u;
    }
    if (name != NULL && copied > 0u) {
        memcpy(error->parameter, name, copied);
    }
    error->parameter[copied] = '\0';
}

/*
 * Parse a value token that is not terminated in place. The whole token must be
 * consumed: `1.0x` and `1.0 2.0` are refusals, not the number they start with.
 *
 * strtof rather than strtod, so that reading a description costs the target no
 * double-precision arithmetic and drags in none of the library that emulates
 * it. The model's quantities are single precision throughout, and a wider parse
 * would only produce a value the record cannot hold.
 *
 * `representable` is false when the token names a real number this type cannot
 * carry at all -- one that arrives as zero, or as infinity. Either is refused
 * rather than delivered: a coefficient silently turned into zero, or into
 * infinity, is not the coefficient the description asked for.
 *
 * The test is on what arrived, not on ERANGE alone. A result too small to be
 * held with full precision but still perfectly usable -- anything below the
 * smallest normal value -- also raises ERANGE, and refusing on the flag by
 * itself would reject values sitting well inside the range their own structure
 * declares admissible.
 */
static bool parse_value(const char *begin, const char *end, float *value, bool *representable)
{
    *representable = true;

    const size_t length = (size_t)(end - begin);
    if (length == 0u || length >= VALUE_TEXT_MAX) {
        return false;
    }

    char text[VALUE_TEXT_MAX];
    memcpy(text, begin, length);
    text[length] = '\0';

    char *stopped = NULL;
    errno = 0;
    const float parsed = strtof(text, &stopped);
    if (stopped != text + length) {
        return false;
    }
    if (errno == ERANGE && (parsed == 0.0f || isinf(parsed))) {
        /* Written out even though this is a refusal, so the caller can report
         * what arrived rather than a value it never saw. */
        *value = parsed;
        *representable = false;
        return false;
    }

    *value = parsed;
    return true;
}

bool plant_parameters_load(const char *text, size_t length, plant_parameters_t *parameters,
                           plant_parameter_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    memset(error, 0, sizeof(*error));

    size_t spec_count = 0u;
    const plant_parameter_spec_t *specs = plant_structure_parameter_specs(&spec_count);
    if (text == NULL || parameters == NULL || specs == NULL || spec_count == 0u ||
        spec_count > SPEC_LIMIT) {
        report(error, PLANT_PARAMETER_MALFORMED, 0u, NULL, 0u);
        return false;
    }

    /*
     * Everything is assembled here and copied out only once the description is
     * known to be complete and admissible, so a refused description leaves the
     * caller's record untouched rather than half filled in.
     */
    plant_parameters_t staging;
    memset(&staging, 0, sizeof(staging));
    uint64_t supplied = 0u;

    const char *cursor = text;
    const char *limit = text + length;
    uint32_t line_number = 0u;

    while (cursor < limit) {
        const char *line_begin = cursor;
        const char *line_end = line_begin;
        while (line_end < limit && *line_end != '\n') {
            line_end++;
        }
        cursor = (line_end < limit) ? line_end + 1 : limit;
        line_number++;

        trim(&line_begin, &line_end);
        if (line_begin == line_end || *line_begin == '#') {
            continue;
        }

        const char *separator = line_begin;
        while (separator < line_end && *separator != '=') {
            separator++;
        }
        if (separator == line_end) {
            report(error, PLANT_PARAMETER_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        const char *name_begin = line_begin;
        const char *name_end = separator;
        trim(&name_begin, &name_end);
        const char *value_begin = separator + 1;
        const char *value_end = line_end;
        trim(&value_begin, &value_end);

        const size_t name_length = (size_t)(name_end - name_begin);
        if (name_length == 0u) {
            report(error, PLANT_PARAMETER_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        size_t index = spec_count;
        for (size_t candidate = 0u; candidate < spec_count; candidate++) {
            const char *name = specs[candidate].name;
            if (strlen(name) == name_length && memcmp(name, name_begin, name_length) == 0) {
                index = candidate;
                break;
            }
        }
        if (index == spec_count) {
            report(error, PLANT_PARAMETER_UNKNOWN, line_number, name_begin, name_length);
            return false;
        }

        const uint64_t bit = (uint64_t)1u << index;
        if ((supplied & bit) != 0u) {
            report(error, PLANT_PARAMETER_DUPLICATE, line_number, name_begin, name_length);
            return false;
        }

        float value = 0.0f;
        bool representable = true;
        if (!parse_value(value_begin, value_end, &value, &representable)) {
            /*
             * A token that is a number the type cannot hold is out of range
             * rather than unreadable -- the description is legible, the value
             * is not one this model can carry.
             */
            report(error,
                   representable ? PLANT_PARAMETER_MALFORMED : PLANT_PARAMETER_OUT_OF_RANGE,
                   line_number, name_begin, name_length);
            if (!representable) {
                /*
                 * The value is reported as it arrived, which is the zero or the
                 * infinity that makes it unusable, rather than as the number
                 * the description spelled -- that number is precisely what this
                 * type cannot hold.
                 */
                error->value = value;
                error->minimum = specs[index].minimum;
                error->maximum = specs[index].maximum;
            }
            return false;
        }

        /*
         * Stated as "is it inside the range" rather than "is it outside", so
         * that a value which compares false to both bounds is refused. A
         * not-a-number reaching here is what a calibration tool that divided
         * by zero emits, and every comparison against it is false: written the
         * other way round it would pass the guard, initialise a model, and
         * turn every quantity the model exposes into a quiet NaN.
         */
        if (!(value >= specs[index].minimum && value <= specs[index].maximum)) {
            report(error, PLANT_PARAMETER_OUT_OF_RANGE, line_number, name_begin, name_length);
            error->value = value;
            error->minimum = specs[index].minimum;
            error->maximum = specs[index].maximum;
            return false;
        }

        float *field = (float *)(void *)((char *)&staging + specs[index].offset);
        *field = value;
        supplied |= bit;
    }

    for (size_t index = 0u; index < spec_count; index++) {
        if ((supplied & ((uint64_t)1u << index)) == 0u) {
            const char *name = specs[index].name;
            report(error, PLANT_PARAMETER_MISSING, 0u, name, strlen(name));
            return false;
        }
    }

    *parameters = staging;
    error->fault = PLANT_PARAMETER_OK;
    return true;
}
