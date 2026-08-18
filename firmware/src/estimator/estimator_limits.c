/*
 * Reading a limits declaration into the record behind estimator_limits.h.
 *
 * It is a separate grammar from the parameter description's, and separate on
 * purpose. A description says what the machine is; this says what a reading off
 * it may plausibly be and how long the estimator may go without one. Folding the
 * second into the first would put sensor-seam facts into a table every plant
 * structure has to declare, and a structure would then be answering for
 * channels its equations have nothing to do with.
 *
 * The walk is one pass, and the record is assembled aside and copied out only
 * once the whole declaration is known to be admissible. A refusal therefore
 * leaves the caller with what it had, which matters here more than it does for
 * a description: a half-filled limits record is one that believes some channels
 * and silently distrusts the rest.
 */
#include "estimator_limits.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>

/*
 * The longest figure a line may carry. Well beyond the digits a 32-bit integer
 * spells, so a token this long is a declaration that needs looking at rather
 * than a number to read; refusing it early keeps the copy that terminates the
 * token bounded.
 */
#define FIGURE_TEXT_MAX 32

static const char *const CHANNEL_WORDS[] = ESTIMATOR_LIMITS_CHANNEL_WORDS;

/*
 * The words and the channels are two halves of one vocabulary and are edited
 * separately, so the build is made to check they still agree. Adding a channel
 * to the hardware seam and forgetting its word here is the likely edit, and it
 * would otherwise read one entry past this array while the machine ran.
 */
_Static_assert(sizeof(CHANNEL_WORDS) / sizeof(CHANNEL_WORDS[0]) == (size_t)HW_SENSOR_CHANNEL_COUNT,
               "every sensor channel declares a word, and no word belongs to no channel");

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

static const char *const ORIGIN_WORDS[] = PLANT_ORIGIN_KIND_WORDS;

_Static_assert(sizeof(ORIGIN_WORDS) / sizeof(ORIGIN_WORDS[0]) == (size_t)PLANT_ORIGIN_KIND_COUNT,
               "every origin kind declares a word, and no word belongs to no kind");

/*
 * Whether the annotation occupying [begin, end) -- which the caller has
 * established starts with the marker -- is a kind from the declared vocabulary
 * followed by an account of where the figure came from. Both are required, for
 * the reason the parameter loader requires both: a kind says how a figure was
 * arrived at and an account says what from, and a figure with the first and not
 * the second can be neither reproduced nor challenged.
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

static void report(estimator_limits_error_t *error, estimator_limits_fault_t fault, uint32_t line,
                   const char *name, size_t name_length)
{
    error->fault = fault;
    error->line = line;

    size_t copied = name_length;
    if (copied > ESTIMATOR_LIMITS_NAME_MAX - 1u) {
        copied = ESTIMATOR_LIMITS_NAME_MAX - 1u;
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
    char text[FIGURE_TEXT_MAX];
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

static bool fits_int32(long value)
{
    return value >= (long)INT32_MIN && value <= (long)INT32_MAX;
}

/* Which channel a name is, or the count when it is none of them. */
static size_t channel_of(const char *begin, const char *end)
{
    size_t channel = 0u;
    while (channel < (size_t)HW_SENSOR_CHANNEL_COUNT &&
           !spans_word(begin, end, CHANNEL_WORDS[channel])) {
        channel++;
    }
    return channel;
}

bool estimator_limits_load(const char *text, size_t length, estimator_limits_t *limits,
                           estimator_limits_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    memset(error, 0, sizeof(*error));

    if (text == NULL || limits == NULL) {
        report(error, ESTIMATOR_LIMITS_MALFORMED, 0u, NULL, 0u);
        return false;
    }

    estimator_limits_t staging;
    memset(&staging, 0, sizeof(staging));

    bool channel_given[HW_SENSOR_CHANNEL_COUNT] = {false};
    bool window_given = false;
    bool excursion_given = false;

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
         * A line that is only a statement the declaration makes about itself.
         * The one such statement is the same one a parameter description may
         * make, and it is admitted here for the same reason: a declaration
         * belonging to a structure that describes no machine has nothing an
         * origin could support. Anything else in that position is refused
         * rather than passed over, so that an unrecognised marker cannot become
         * a second comment syntax.
         */
        if (*line_begin == PLANT_ORIGIN_MARKER) {
            const char *statement_begin = line_begin + 1;
            const char *statement_end = line_end;
            trim(&statement_begin, &statement_end);
            if (!spans_word(statement_begin, statement_end, PLANT_ORIGIN_NO_MACHINE_DECLARATION)) {
                report(error, ESTIMATOR_LIMITS_ORIGIN, line_number, line_begin,
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
            report(error, ESTIMATOR_LIMITS_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        const char *name_begin = line_begin;
        const char *name_end = separator;
        trim(&name_begin, &name_end);
        const size_t name_length = (size_t)(name_end - name_begin);
        if (name_length == 0u) {
            report(error, ESTIMATOR_LIMITS_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        /*
         * The figures run to the origin annotation where there is one, and to
         * the end of the line where there is none. Splitting here rather than
         * after reading them is what keeps a figure token what it would be
         * without the annotation, so the refusal of a token with a second
         * number after it is untouched by the grammar's extension.
         */
        const char *origin_begin = separator + 1;
        while (origin_begin < line_end && *origin_begin != PLANT_ORIGIN_MARKER) {
            origin_begin++;
        }

        const char *figures_begin = separator + 1;
        const char *figures_end = origin_begin;
        trim(&figures_begin, &figures_end);

        if (origin_begin != line_end && !origin_is_admissible(origin_begin, line_end)) {
            report(error, ESTIMATOR_LIMITS_ORIGIN, line_number, name_begin, name_length);
            return false;
        }

        const size_t channel = channel_of(name_begin, name_end);
        if (channel < (size_t)HW_SENSOR_CHANNEL_COUNT) {
            if (channel_given[channel]) {
                report(error, ESTIMATOR_LIMITS_DUPLICATE, line_number, name_begin, name_length);
                return false;
            }

            /*
             * The range marker is looked for after the first figure rather than
             * anywhere in the span, so that a negative low -- which a
             * temperature channel legitimately has -- cannot be mistaken for
             * one. A line carrying no marker is a channel given one figure
             * where the grammar admits two.
             */
            const char *marker = figures_begin;
            const size_t marker_length = strlen(ESTIMATOR_LIMITS_RANGE_MARKER);
            while (marker < figures_end &&
                   !(((size_t)(figures_end - marker) >= marker_length) &&
                     memcmp(marker, ESTIMATOR_LIMITS_RANGE_MARKER, marker_length) == 0)) {
                marker++;
            }
            if (marker == figures_end) {
                report(error, ESTIMATOR_LIMITS_MALFORMED, line_number, name_begin, name_length);
                return false;
            }

            const char *low_begin = figures_begin;
            const char *low_end = marker;
            trim(&low_begin, &low_end);
            const char *high_begin = marker + marker_length;
            const char *high_end = figures_end;
            trim(&high_begin, &high_end);

            long low = 0;
            long high = 0;
            if (!parse_figure(low_begin, low_end, &low) ||
                !parse_figure(high_begin, high_end, &high)) {
                report(error, ESTIMATOR_LIMITS_MALFORMED, line_number, name_begin, name_length);
                return false;
            }
            if (!fits_int32(low) || !fits_int32(high)) {
                report(error, ESTIMATOR_LIMITS_OUT_OF_RANGE, line_number, name_begin, name_length);
                return false;
            }

            /*
             * Stated as low below high rather than not above it. A channel
             * whose bounds are the same value admits exactly one reading, which
             * is a declaration nobody means to make and which would distrust
             * every sample the machine ever took.
             */
            if (!(low < high)) {
                report(error, ESTIMATOR_LIMITS_INVERTED, line_number, name_begin, name_length);
                return false;
            }

            staging.low_milli[channel] = (int32_t)low;
            staging.high_milli[channel] = (int32_t)high;
            channel_given[channel] = true;
            continue;
        }

        const bool is_window =
            spans_word(name_begin, name_end, ESTIMATOR_LIMITS_TOLERANCE_WINDOW_WORD);
        const bool is_excursion =
            spans_word(name_begin, name_end, ESTIMATOR_LIMITS_EXCURSION_BOUND_WORD);
        if (!is_window && !is_excursion) {
            report(error, ESTIMATOR_LIMITS_UNKNOWN, line_number, name_begin, name_length);
            return false;
        }
        if ((is_window && window_given) || (is_excursion && excursion_given)) {
            report(error, ESTIMATOR_LIMITS_DUPLICATE, line_number, name_begin, name_length);
            return false;
        }

        long figure = 0;
        if (!parse_figure(figures_begin, figures_end, &figure)) {
            report(error, ESTIMATOR_LIMITS_MALFORMED, line_number, name_begin, name_length);
            return false;
        }

        if (is_window) {
            /*
             * A negative span of time is not a shorter one, and a window wider
             * than the clock it is compared against could never be reached.
             *
             * The upper bound is compared as an unsigned long rather than by
             * casting the limit down to a long. Where long is 32 bits -- which
             * is every build of this that matters, the target among them --
             * (long)UINT32_MAX is a conversion of a value the type cannot hold,
             * and it lands on -1: the test then reads "figure > -1", the whole
             * condition is true for every figure, and the machine refuses every
             * window ever declared. It compiles without a diagnostic and no host
             * gate can see it, because the host is not 32-bit.
             */
            if (figure < 0 || (unsigned long)figure > UINT32_MAX) {
                report(error, ESTIMATOR_LIMITS_OUT_OF_RANGE, line_number, name_begin, name_length);
                return false;
            }
            staging.tolerance_window_ms = (uint32_t)figure;
            window_given = true;
            continue;
        }

        /*
         * A distance of nothing or less is not a bound the estimate could
         * satisfy while moving at all, so a declaration carrying one is refused
         * rather than left to refuse every reconstruction it is asked about.
         */
        if (figure <= 0 || !fits_int32(figure)) {
            report(error, ESTIMATOR_LIMITS_OUT_OF_RANGE, line_number, name_begin, name_length);
            return false;
        }
        staging.excursion_bound_milli = (int32_t)figure;
        excursion_given = true;
    }

    for (size_t channel = 0u; channel < (size_t)HW_SENSOR_CHANNEL_COUNT; channel++) {
        if (!channel_given[channel]) {
            report(error, ESTIMATOR_LIMITS_MISSING, 0u, CHANNEL_WORDS[channel],
                   strlen(CHANNEL_WORDS[channel]));
            return false;
        }
    }
    if (!window_given) {
        report(error, ESTIMATOR_LIMITS_MISSING, 0u, ESTIMATOR_LIMITS_TOLERANCE_WINDOW_WORD,
               strlen(ESTIMATOR_LIMITS_TOLERANCE_WINDOW_WORD));
        return false;
    }
    if (!excursion_given) {
        report(error, ESTIMATOR_LIMITS_MISSING, 0u, ESTIMATOR_LIMITS_EXCURSION_BOUND_WORD,
               strlen(ESTIMATOR_LIMITS_EXCURSION_BOUND_WORD));
        return false;
    }

    *limits = staging;
    error->fault = ESTIMATOR_LIMITS_OK;
    return true;
}
