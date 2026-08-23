/*
 * Reading a tolerance declaration into the record behind delivery_tolerance.h.
 *
 * It is a third grammar beside the parameter description's and the limits
 * declaration's, and it is separate for the reason those two are separate from
 * each other: they answer to different seams. A description says what the
 * machine is, a limits declaration says what a reading off it may plausibly be,
 * and this says what the drink demands of a delivery -- which is a fact about
 * neither the machine nor its instrumentation, and would be answering for
 * something outside its subject in either of the others.
 *
 * It is compiled outside src/control, beside no control logic, for a reason the
 * limits loader shows already: reading a declaration means reaching for the
 * standard library's number conversion, and that reaches errno, which is a
 * different symbol on a host and on the target. The control logic is required
 * to be byte-identical across the two, and it is the check that compares them
 * which would have to be weakened to admit a translation unit that cannot be.
 * Nothing is lost by the separation, because the control path never calls this:
 * a record is loaded by whatever brought the machine up and handed in, exactly
 * as the parameter description and the limits declaration are.
 *
 * The walk is one pass, and the record is assembled aside and copied out only
 * once the whole declaration is known to be admissible. A refusal therefore
 * leaves the caller with what it had, which matters here for the same reason it
 * matters for a limits record: a half-filled tolerance record holds some
 * deliveries to a band somebody declared and the rest to whatever was in the
 * memory, and the second kind passes quietly.
 */
#include "delivery_tolerance.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>

/*
 * The longest figure a line may carry. Well beyond the digits a 32-bit integer
 * spells, so a token this long is a declaration that needs looking at rather
 * than a number to read; refusing it early keeps the copy that terminates the
 * token bounded.
 *
 * It carries this loader's name rather than a bare one. The limits loader
 * bounds its own copy with a figure of the same size, and two files defining
 * one unqualified name would be two homes for what reads as one figure -- so
 * either could be corrected and the other left, with nothing saying which the
 * program ran on. They are separate figures about separate grammars and are
 * spelled that way.
 */
#define DELIVERY_FIGURE_TEXT_MAX 32

static const char *const ORIGIN_WORDS[] = PLANT_ORIGIN_KIND_WORDS;

_Static_assert(sizeof(ORIGIN_WORDS) / sizeof(ORIGIN_WORDS[0]) == (size_t)PLANT_ORIGIN_KIND_COUNT,
               "every origin kind declares a word, and no word belongs to no kind");

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
 * established starts with the marker -- is a kind from the declared vocabulary
 * followed by an account of where the figure came from.
 *
 * What the account says is not judged here. Whether it is truthful is a review
 * question, and a reader that tried to answer it would refuse honest
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

static void report(delivery_tolerance_error_t *error, delivery_tolerance_fault_t fault,
                   uint32_t line, const char *name, size_t name_length)
{
    error->fault = fault;
    error->line = line;

    size_t copied = name_length;
    if (copied > DELIVERY_TOLERANCE_NAME_MAX - 1u) {
        copied = DELIVERY_TOLERANCE_NAME_MAX - 1u;
    }
    if (name != NULL && copied > 0u) {
        memcpy(error->name, name, copied);
    }
    error->name[copied] = '\0';
}

/*
 * Read [begin, end) as a whole number.
 *
 * Refused rather than clamped when it does not fit, and refused when anything
 * follows it: `10 20` is two figures where the grammar admits one, and taking
 * the first would silently accept a line whose author meant something else.
 */
static bool parse_figure(const char *begin, const char *end, long *value)
{
    char text[DELIVERY_FIGURE_TEXT_MAX];
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

bool delivery_tolerance_load(const char *text, size_t length, delivery_tolerance_t *tolerance,
                             delivery_tolerance_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    memset(error, 0, sizeof(*error));

    if (text == NULL || tolerance == NULL) {
        report(error, DELIVERY_TOLERANCE_MALFORMED, 0u, NULL, 0u);
        return false;
    }

    delivery_tolerance_t staging;
    memset(&staging, 0, sizeof(staging));

    bool brew_given = false;

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
            report(error, DELIVERY_TOLERANCE_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        const char *name_begin = line_begin;
        const char *name_end = separator;
        trim(&name_begin, &name_end);
        const size_t name_length = (size_t)(name_end - name_begin);
        if (name_length == 0u) {
            report(error, DELIVERY_TOLERANCE_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        /*
         * The figure runs to the origin annotation where there is one, and to
         * the end of the line where there is none. Splitting here rather than
         * after reading it is what keeps the figure token what it would be
         * without the annotation, so the refusal of a token with a second
         * number after it does not depend on whether an origin was written.
         */
        const char *origin_begin = separator + 1;
        while (origin_begin < line_end && *origin_begin != PLANT_ORIGIN_MARKER) {
            origin_begin++;
        }

        const char *figure_begin = separator + 1;
        const char *figure_end = origin_begin;
        trim(&figure_begin, &figure_end);

        if (!spans_word(name_begin, name_end, DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD)) {
            report(error, DELIVERY_TOLERANCE_UNKNOWN, line_number, name_begin, name_length);
            return false;
        }
        if (brew_given) {
            report(error, DELIVERY_TOLERANCE_DUPLICATE, line_number, name_begin, name_length);
            return false;
        }

        /*
         * Every band is accounted for, with no exemption of the kind a
         * description that claims no machine may take. That exemption exists
         * because such a description asserts nothing an origin could support;
         * a band always asserts something -- what the drink demands -- whatever
         * machine is eventually built to meet it.
         */
        if (origin_begin == line_end || !origin_is_admissible(origin_begin, line_end)) {
            report(error, DELIVERY_TOLERANCE_ORIGIN, line_number, name_begin, name_length);
            return false;
        }

        long figure = 0;
        if (!parse_figure(figure_begin, figure_end, &figure)) {
            report(error, DELIVERY_TOLERANCE_MALFORMED, line_number, name_begin, name_length);
            return false;
        }

        /*
         * A band of nothing or less is not a distance a delivery could be held
         * to: it would refuse every trajectory a real machine ever produced,
         * including the ones the design is working. Refused here rather than
         * left to fail every assertion downstream, where it would read as a
         * broken control law rather than as a band nobody meant to declare.
         */
        if (figure <= 0 || figure > (long)INT32_MAX) {
            report(error, DELIVERY_TOLERANCE_OUT_OF_RANGE, line_number, name_begin, name_length);
            return false;
        }

        staging.brew_temperature_band_milli_c = (int32_t)figure;
        brew_given = true;
    }

    if (!brew_given) {
        report(error, DELIVERY_TOLERANCE_MISSING, 0u, DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD,
               strlen(DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD));
        return false;
    }

    *tolerance = staging;
    error->fault = DELIVERY_TOLERANCE_OK;
    return true;
}
