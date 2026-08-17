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

#include "plant_origin.h"

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

/*
 * Whether [begin, end) is exactly `word`.
 *
 * The span is not terminated -- it points into the description -- so the length
 * is compared as well as the bytes. A kind that merely starts with a declared
 * word is not that kind.
 */
static bool spans_word(const char *begin, const char *end, const char *word)
{
    const size_t length = (size_t)(end - begin);
    return strlen(word) == length && memcmp(word, begin, length) == 0;
}

/*
 * Read the origin annotation occupying [begin, end), which the caller has
 * established starts with the marker.
 *
 * An annotation is the marker, a kind from the declared vocabulary, and an
 * account of where the figure came from -- and all three are required. An
 * annotation carrying a kind and nothing else is refused rather than accepted
 * as a bare label: the kind says how a figure was arrived at and the account
 * says what it was arrived at from, and a value with the first and not the
 * second cannot be reproduced or challenged, which is the whole point of
 * recording it.
 *
 * What the account says is not judged here. Whether a citation is truthful, or
 * the document it names exists, is a review question, and a parser that tried
 * to answer it would refuse honest descriptions.
 */
static bool origin_is_admissible(const char *begin, const char *end)
{
    static const char *const words[] = PLANT_ORIGIN_KIND_WORDS;

    const char *cursor = begin + 1; /* Past the marker. */
    while (cursor < end && is_blank(*cursor)) {
        cursor++;
    }

    const char *kind_end = cursor;
    while (kind_end < end && !is_blank(*kind_end)) {
        kind_end++;
    }
    if (kind_end == cursor) {
        return false;
    }

    size_t kind = 0u;
    while (kind < PLANT_ORIGIN_KIND_COUNT && !spans_word(cursor, kind_end, words[kind])) {
        kind++;
    }
    if (kind == PLANT_ORIGIN_KIND_COUNT) {
        return false;
    }

    const char *account_begin = kind_end;
    const char *account_end = end;
    trim(&account_begin, &account_end);
    return account_begin != account_end;
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

        /*
         * A line that is nothing but a statement the description makes about
         * itself. Only one such statement exists, and anything else in that
         * position is refused rather than passed over: a marker that could be
         * ignored when unrecognised would turn the whole annotation grammar
         * into a second comment syntax, and a description exempting itself
         * with a word this loader has never heard of would read as exempt to
         * its author and as unaccounted-for to everything else.
         */
        if (*line_begin == PLANT_ORIGIN_MARKER) {
            const char *statement_begin = line_begin + 1;
            const char *statement_end = line_end;
            trim(&statement_begin, &statement_end);
            if (!spans_word(statement_begin, statement_end,
                            PLANT_ORIGIN_NO_MACHINE_DECLARATION)) {
                report(error, PLANT_PARAMETER_ORIGIN, line_number, line_begin,
                       (size_t)(line_end - line_begin));
                return false;
            }
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
        /*
         * The value runs to the marker where one is present, and to the end of
         * the line where it is not. Splitting here rather than after parsing is
         * what keeps the value token what it always was: `1.0 @document p.24`
         * offers the parser `1.0`, so the refusal of a token with a second
         * number after it -- `1.0 2.0` -- is untouched by the extension.
         */
        const char *origin_begin = separator + 1;
        while (origin_begin < line_end && *origin_begin != PLANT_ORIGIN_MARKER) {
            origin_begin++;
        }
        const char *value_begin = separator + 1;
        const char *value_end = origin_begin;
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

        /*
         * The account is read after the value it belongs to, so a line whose
         * value is wrong is reported as that rather than as an accounting
         * fault: the substance of a line is refused before its provenance.
         *
         * Nothing is retained from it. Which values are accounted for, and
         * whether the account is adequate, is settled where the description
         * lives -- by the check that reads the file -- rather than by carrying
         * strings into a record the target holds in memory. What this loader
         * owes the property is that an account cannot be malformed and pass,
         * because a description whose annotations are quietly skipped is a
         * description with no annotations at all.
         */
        if (origin_begin != line_end && !origin_is_admissible(origin_begin, line_end)) {
            report(error, PLANT_PARAMETER_ORIGIN, line_number, name_begin, name_length);
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
