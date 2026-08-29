/*
 * Reading a pump trim declaration into the record behind
 * pump_trim_declaration.h.
 *
 * It is compiled outside src/control, beside no control logic, for the same
 * reason steam_control_declaration.c and delivery_tolerance.c beside it are:
 * reading a declaration means reaching for the standard library's number
 * conversion, and that reaches errno, which is a different symbol on a host and
 * on the target. The control logic is required to be byte-identical across the
 * two, and it is the check that compares them which would have to be weakened
 * to admit a translation unit that cannot be. Nothing is lost by the
 * separation, because the control path never calls this: a record is loaded by
 * whatever brings the control path up and hands it in, exactly as the
 * tolerance and steam declarations are.
 *
 * The figures are read against a table rather than by a branch per name, on
 * exactly the terms steam_control_declaration.c's own table is: the unit
 * check, the range check, the duplicate check and the absence check are each
 * written once per figure, and the one that is forgotten is forgotten
 * silently, because a figure with no range check reads exactly like a figure
 * whose range is wide. There are only two figures here, and the table is kept
 * anyway rather than collapsed into two branches -- a third figure arriving
 * later joins a shape this file already has rather than one somebody has to
 * introduce.
 *
 * The walk is one pass, and the record is assembled aside and copied out only
 * once the whole declaration is known to be admissible, on the same terms
 * delivery_tolerance_load and steam_control_declaration_load already keep: a
 * refusal leaves the caller with what it had rather than with some figures
 * read and the rest of the record left at whatever the memory contained.
 */
#include "pump_trim_declaration.h"

#include <errno.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

/*
 * The longest figure a line may carry. Well beyond the digits a 32-bit
 * integer spells, so a token this long is a declaration that needs looking
 * at rather than a number to read.
 *
 * It carries this loader's own name rather than a bare one, on the same
 * terms steam_control_declaration.c's own figure bound does: two files each
 * defining an unqualified bound of this shape would be two homes for what
 * reads as one figure.
 */
#define PUMP_TRIM_DECLARATION_FIGURE_TEXT_MAX 32

/*
 * The span the proportional gain may be declared inside, in thousandths of a
 * permille of pump scale per millilitre per second of rate error.
 *
 * A gain of nothing is a trim that never answers a gap at all, so the low end
 * is the smallest figure that is not that -- the same reasoning every other
 * gain bound in this project rests on. The high end is a thousand permille
 * per ml/s, the point at which one millilitre a second of error alone would
 * command the whole pump: past it the figure has stopped describing a
 * proportional term and become a switch, which is a different design rather
 * than an aggressive setting of this one.
 */
#define PUMP_TRIM_DECLARATION_GAIN_LOW_MILLI 1
#define PUMP_TRIM_DECLARATION_GAIN_HIGH_MILLI 1000000

/*
 * The span the integral gain may be declared inside, in thousandths of a
 * permille of pump scale per millilitre per second of rate error, per second.
 *
 * The low end is the smallest figure that still accumulates anything, on the
 * same reasoning the proportional gain's own low bound rests on: an integral
 * gain of nothing is a trim with no integral rather than a slow one, and a
 * gap the proportional term does not fully answer would then stand forever.
 * The high end is a thousand permille per ml/s-second, at which one second of
 * one millilitre a second of error alone has accumulated the whole pump on
 * its own -- past that the integral is no longer the slow term it exists to
 * be and has become a second, faster proportional gain wearing an
 * integrator.
 */
#define PUMP_TRIM_DECLARATION_INTEGRAL_GAIN_LOW_MILLI 1
#define PUMP_TRIM_DECLARATION_INTEGRAL_GAIN_HIGH_MILLI 1000000

static const char *const ORIGIN_WORDS[] = PLANT_ORIGIN_KIND_WORDS;

_Static_assert(sizeof(ORIGIN_WORDS) / sizeof(ORIGIN_WORDS[0]) == (size_t)PLANT_ORIGIN_KIND_COUNT,
               "every origin kind declares a word, and no word belongs to no kind");

static const char *const UNIT_WORDS[] = PUMP_TRIM_DECLARATION_UNIT_WORDS;

_Static_assert(sizeof(UNIT_WORDS) / sizeof(UNIT_WORDS[0]) ==
                  (size_t)PUMP_TRIM_DECLARATION_UNIT_COUNT,
               "every unit declares a word, and no word belongs to no unit");

/*
 * One figure this grammar reads: the word it is written as, the unit it is
 * held in, the span it is admissible inside, and where it lands in the record.
 *
 * The offset is how the table reaches the field rather than a pointer per
 * figure, on the same terms steam_control_declaration.c's own figure_spec_t
 * already reaches a figure's home: every field is the same type, so one write
 * serves all of them and a figure added to the record cannot be given a
 * writer of the wrong width.
 */
typedef struct {
    const char *word;
    pump_trim_declaration_unit_t unit;
    int32_t low;
    int32_t high;
    size_t offset;
} figure_spec_t;

static const figure_spec_t FIGURES[] = {
    {PUMP_TRIM_DECLARATION_GAIN_WORD, PUMP_TRIM_DECLARATION_UNIT_MILLI_PERMILLE_PER_ML_PER_S,
     PUMP_TRIM_DECLARATION_GAIN_LOW_MILLI, PUMP_TRIM_DECLARATION_GAIN_HIGH_MILLI,
     offsetof(pump_trim_declaration_t, gain_milli_permille_per_ml_per_s)},
    {PUMP_TRIM_DECLARATION_INTEGRAL_GAIN_WORD,
     PUMP_TRIM_DECLARATION_UNIT_MILLI_PERMILLE_PER_ML_PER_S_S,
     PUMP_TRIM_DECLARATION_INTEGRAL_GAIN_LOW_MILLI, PUMP_TRIM_DECLARATION_INTEGRAL_GAIN_HIGH_MILLI,
     offsetof(pump_trim_declaration_t, integral_gain_milli_permille_per_ml_per_s_s)}
};

#define FIGURE_COUNT (sizeof(FIGURES) / sizeof(*FIGURES))

/*
 * Every field of the record is a figure this grammar reads, and every figure
 * lands in a field of its own. The record carries nothing but these fields and
 * all of them are the same width, so its size divided by one field's is how
 * many there are -- and a field added without a line in the table above, or a
 * line added without a field, fails the build here rather than leaving a
 * figure that reads as declared and is written nowhere.
 */
_Static_assert(sizeof(pump_trim_declaration_t) / sizeof(int32_t) == FIGURE_COUNT,
               "every figure this grammar reads has a field of its own, and no field belongs "
               "to no figure");

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
 * Whether [begin, end) is exactly `word`. The span is not terminated -- it
 * points into the declaration -- so the length is compared as well as the
 * bytes. A name that merely starts with a declared word is not that word.
 */
static bool spans_word(const char *begin, const char *end, const char *word)
{
    const size_t length = (size_t)(end - begin);
    return strlen(word) == length && memcmp(word, begin, length) == 0;
}

/*
 * Whether the annotation occupying [begin, end) -- which the caller has
 * established starts with the marker -- is a kind from the declared
 * vocabulary followed by an account of where the figure came from.
 *
 * What the account says is not judged here. Whether it is truthful is a
 * review question, and a reader that tried to answer it would refuse honest
 * declarations.
 */
static bool origin_is_admissible(const char *begin, const char *end)
{
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
    while (kind < (size_t)PLANT_ORIGIN_KIND_COUNT &&
          !spans_word(cursor, kind_end, ORIGIN_WORDS[kind])) {
        kind++;
    }
    if (kind == (size_t)PLANT_ORIGIN_KIND_COUNT) {
        return false;
    }

    const char *account_begin = kind_end;
    const char *account_end = end;
    trim(&account_begin, &account_end);
    return account_begin != account_end;
}

static void report(pump_trim_declaration_error_t *error, pump_trim_declaration_fault_t fault,
                   uint32_t line, const char *name, size_t name_length)
{
    error->fault = fault;
    error->line = line;

    size_t copied = name_length;
    if (copied > PUMP_TRIM_DECLARATION_NAME_MAX - 1u) {
        copied = PUMP_TRIM_DECLARATION_NAME_MAX - 1u;
    }
    if (name != NULL && copied > 0u) {
        memcpy(error->name, name, copied);
    }
    error->name[copied] = '\0';
}

/*
 * Read [begin, end) as a whole number.
 *
 * Refused rather than clamped when it does not fit, and refused when
 * anything follows it: `900 901` is two figures where the grammar admits
 * one, and taking the first would silently accept a line whose author meant
 * something else.
 */
static bool parse_figure(const char *begin, const char *end, long *value)
{
    char text[PUMP_TRIM_DECLARATION_FIGURE_TEXT_MAX];
    const size_t length = (size_t)(end - begin);

    if (length == 0u || length >= sizeof(text)) {
        return false;
    }
    memcpy(text, begin, length);
    text[length] = '\0';

    errno = 0;
    char *stop = NULL;
    const long read = strtol(text, &stop, 10);
    if (errno != 0 || stop == text) {
        return false;
    }
    while (*stop != '\0' && is_blank(*stop)) {
        stop++;
    }
    if (*stop != '\0') {
        return false;
    }

    *value = read;
    return true;
}

/* Where in a staging record the figure at `spec` lands. */
static int32_t *field_of(pump_trim_declaration_t *staging, const figure_spec_t *spec)
{
    return (int32_t *)(void *)((char *)staging + spec->offset);
}

bool pump_trim_declaration_load(const char *text, size_t length,
                                pump_trim_declaration_t *declaration,
                                pump_trim_declaration_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    memset(error, 0, sizeof(*error));

    if (text == NULL || declaration == NULL) {
        report(error, PUMP_TRIM_DECLARATION_MALFORMED, 0u, NULL, 0u);
        return false;
    }

    pump_trim_declaration_t staging;
    memset(&staging, 0, sizeof(staging));

    bool given[FIGURE_COUNT];
    memset(given, 0, sizeof(given));

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
            report(error, PUMP_TRIM_DECLARATION_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        const char *name_begin = line_begin;
        const char *name_end = separator;
        trim(&name_begin, &name_end);
        const size_t name_length = (size_t)(name_end - name_begin);
        if (name_length == 0u) {
            report(error, PUMP_TRIM_DECLARATION_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        /*
         * The figure runs to the origin annotation where there is one, and
         * to the end of the line where there is none, on the same terms
         * steam_control_declaration.c's own split is: taken before the
         * figure is read, so the refusal of a token with a second number
         * after it does not depend on whether an origin was written.
         */
        const char *origin_begin = separator + 1;
        while (origin_begin < line_end && *origin_begin != PLANT_ORIGIN_MARKER) {
            origin_begin++;
        }

        const char *figure_begin = separator + 1;
        const char *figure_end = origin_begin;
        trim(&figure_begin, &figure_end);

        size_t at = 0u;
        while (at < FIGURE_COUNT && !spans_word(name_begin, name_end, FIGURES[at].word)) {
            at++;
        }
        if (at == FIGURE_COUNT) {
            report(error, PUMP_TRIM_DECLARATION_UNKNOWN, line_number, name_begin, name_length);
            return false;
        }
        if (given[at]) {
            report(error, PUMP_TRIM_DECLARATION_DUPLICATE, line_number, name_begin, name_length);
            return false;
        }

        if (origin_begin == line_end || !origin_is_admissible(origin_begin, line_end)) {
            report(error, PUMP_TRIM_DECLARATION_ORIGIN, line_number, name_begin, name_length);
            return false;
        }

        /*
         * The figure region carries the number and then the word for the
         * unit it is in, split at the last run of blanks rather than the
         * first, on the same terms steam_control_declaration.c's own split
         * is: a region with a second number in it still reaches
         * parse_figure with both, and is still refused as malformed rather
         * than quietly reading the first and taking the second for a unit.
         */
        const char *unit_begin = figure_end;
        while (unit_begin > figure_begin && !is_blank(*(unit_begin - 1))) {
            unit_begin--;
        }
        const char *number_end = unit_begin;
        while (number_end > figure_begin && is_blank(*(number_end - 1))) {
            number_end--;
        }

        if (figure_begin == figure_end) {
            report(error, PUMP_TRIM_DECLARATION_MALFORMED, line_number, name_begin, name_length);
            return false;
        }
        if (unit_begin == figure_begin || number_end == figure_begin) {
            report(error, PUMP_TRIM_DECLARATION_UNIT_MISMATCH, line_number, name_begin,
                   name_length);
            return false;
        }

        long figure = 0;
        if (!parse_figure(figure_begin, number_end, &figure)) {
            report(error, PUMP_TRIM_DECLARATION_MALFORMED, line_number, name_begin, name_length);
            return false;
        }

        if (!spans_word(unit_begin, figure_end, UNIT_WORDS[FIGURES[at].unit])) {
            report(error, PUMP_TRIM_DECLARATION_UNIT_MISMATCH, line_number, name_begin,
                   name_length);
            return false;
        }

        if (figure < (long)FIGURES[at].low || figure > (long)FIGURES[at].high) {
            report(error, PUMP_TRIM_DECLARATION_OUT_OF_RANGE, line_number, name_begin,
                   name_length);
            return false;
        }

        *field_of(&staging, &FIGURES[at]) = (int32_t)figure;
        given[at] = true;
    }

    for (size_t at = 0u; at < FIGURE_COUNT; at++) {
        if (!given[at]) {
            report(error, PUMP_TRIM_DECLARATION_MISSING, 0u, FIGURES[at].word,
                   strlen(FIGURES[at].word));
            return false;
        }
    }

    *declaration = staging;
    error->fault = PUMP_TRIM_DECLARATION_OK;
    return true;
}
