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

static const char *const UNIT_WORDS[] = DELIVERY_TOLERANCE_UNIT_WORDS;

_Static_assert(sizeof(UNIT_WORDS) / sizeof(UNIT_WORDS[0]) == (size_t)DELIVERY_TOLERANCE_UNIT_COUNT,
               "every unit declares a word, and no word belongs to no unit");

/*
 * The widest half-width each band may be declared at.
 *
 * These bound what the grammar will admit; they are not the bands, and nothing
 * holds a delivery to them. The band itself has one home and it is the
 * declaration -- what is written here is only the point past which a figure has
 * stopped being a statement about the drink at all, which is a property of the
 * quantity rather than of the design and so cannot live in the file whose
 * figures it is checking.
 *
 * They are stated per band rather than once for all of them. Two of these bands
 * measure different quantities outright, and the third measures the same
 * quantity as the first while being about something else entirely -- the
 * distance between two deliveries rather than between a delivery and its
 * command -- so sharing a unit is not sharing a bound. A single shared bound
 * could only ever be the loosest of the three, and would then admit for the
 * tighter ones every figure they most needed refusing: which is how a
 * declaration in the wrong unit reads as merely a generous one, and how a band
 * that has stopped being a criterion reads as a relaxed one.
 *
 * Twenty degrees, as a half-width, is a forty-degree span: water anywhere in it
 * is not the drink that was ordered under any account of extraction, and an
 * unregulated machine of this kind swings by considerably less. Seven
 * millilitres a second is what the reference description declares the pump
 * draws at full scale, so a half-width there or beyond accepts every rate the
 * machine can physically produce -- a band that reports nothing, which is the
 * failure the flow band exists to prevent rather than a loose setting of it.
 *
 * Two degrees is where two extractions have stopped being the same drink: it is
 * the span the extraction literature treats as the point a difference in the
 * cup becomes tasteable rather than merely measurable, and a post-draw run that
 * far from a rested one is a different cup by the same account the brew band
 * itself rests on. It sits an order of magnitude below the temperature bound
 * above even though both are in thousandths of a degree, which is the whole
 * reason the two are separate figures: one shared bound could only be the
 * looser, and would then admit for this band every figure it most needs to
 * refuse.
 */
#define BREW_TEMPERATURE_WIDEST_ADMISSIBLE_MILLI_C 20000
#define FLOW_DEPARTURE_WIDEST_ADMISSIBLE_MILLI_ML_PER_S 7000
#define POST_DRAW_MATCH_WIDEST_ADMISSIBLE_MILLI_C 2000

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
    bool flow_given = false;
    bool post_draw_given = false;

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

        int32_t *slot = NULL;
        bool *given = NULL;
        delivery_tolerance_unit_t stated_in = DELIVERY_TOLERANCE_UNIT_COUNT;
        long widest = 0;
        if (spans_word(name_begin, name_end, DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD)) {
            slot = &staging.brew_temperature_band_milli_c;
            given = &brew_given;
            stated_in = DELIVERY_TOLERANCE_UNIT_MILLI_C;
            widest = (long)BREW_TEMPERATURE_WIDEST_ADMISSIBLE_MILLI_C;
        } else if (spans_word(name_begin, name_end, DELIVERY_TOLERANCE_FLOW_DEPARTURE_WORD)) {
            slot = &staging.flow_departure_band_milli_ml_per_s;
            given = &flow_given;
            stated_in = DELIVERY_TOLERANCE_UNIT_MILLI_ML_PER_S;
            widest = (long)FLOW_DEPARTURE_WIDEST_ADMISSIBLE_MILLI_ML_PER_S;
        } else if (spans_word(name_begin, name_end, DELIVERY_TOLERANCE_POST_DRAW_MATCH_WORD)) {
            slot = &staging.post_draw_match_band_milli_c;
            given = &post_draw_given;
            stated_in = DELIVERY_TOLERANCE_UNIT_MILLI_C;
            widest = (long)POST_DRAW_MATCH_WIDEST_ADMISSIBLE_MILLI_C;
        } else {
            report(error, DELIVERY_TOLERANCE_UNKNOWN, line_number, name_begin, name_length);
            return false;
        }
        if (*given) {
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

        /*
         * The figure region carries the number and then the word for the unit
         * it is in. They are split at the last run of blanks rather than the
         * first, so that the number token is exactly what parse_figure would
         * have been handed before the unit existed: a region with a second
         * number in it still reaches parse_figure with both, and is still
         * refused as malformed rather than quietly reading the first and
         * taking the second for a unit.
         */
        const char *unit_begin = figure_end;
        while (unit_begin > figure_begin && !is_blank(*(unit_begin - 1))) {
            unit_begin--;
        }
        const char *number_end = unit_begin;
        while (number_end > figure_begin && is_blank(*(number_end - 1))) {
            number_end--;
        }

        /*
         * Nothing at all between the separator and the origin is a line that
         * states no quantity to have a unit for, and is malformed on the same
         * terms it was before units existed -- reporting it as a unit fault
         * would send a reader looking for a word that was never the point.
         */
        if (figure_begin == figure_end) {
            report(error, DELIVERY_TOLERANCE_MALFORMED, line_number, name_begin, name_length);
            return false;
        }

        /*
         * One token where two were wanted is a band declared with a number and
         * no unit, or with a unit and no number. Either way the quantity is
         * not stated, and what is missing from it is the unit.
         */
        if (unit_begin == figure_begin || number_end == figure_begin) {
            report(error, DELIVERY_TOLERANCE_UNIT_MISMATCH, line_number, name_begin, name_length);
            return false;
        }

        /*
         * The number is read before the unit word is judged, so that a region
         * carrying two figures is still refused as malformed rather than as a
         * unit fault: what is wrong with `2000 milli-c 3000` is the second
         * number, and reporting the unit would send a reader to check a word
         * that is spelled correctly and sitting in the wrong place.
         */
        long figure = 0;
        if (!parse_figure(figure_begin, number_end, &figure)) {
            report(error, DELIVERY_TOLERANCE_MALFORMED, line_number, name_begin, name_length);
            return false;
        }

        if (!spans_word(unit_begin, figure_end, UNIT_WORDS[stated_in])) {
            report(error, DELIVERY_TOLERANCE_UNIT_MISMATCH, line_number, name_begin, name_length);
            return false;
        }

        /*
         * A band of nothing or less is not a distance a delivery could be held
         * to: it would refuse every trajectory a real machine ever produced,
         * including the ones the design is working. Refused here rather than
         * left to fail every assertion downstream, where it would read as a
         * broken control law rather than as a band nobody meant to declare.
         *
         * The upper bound is this band's own, not one distance shared by all of
         * them: a figure is judged as a quantity of the unit it was just
         * checked to be stated in. A band wider than its own bound has stopped
         * being a criterion -- it accepts everything the machine can do -- and
         * that point sits at a different number for each quantity.
         */
        if (figure <= 0 || figure > widest) {
            report(error, DELIVERY_TOLERANCE_OUT_OF_RANGE, line_number, name_begin, name_length);
            return false;
        }

        *slot = (int32_t)figure;
        *given = true;
    }

    if (!brew_given) {
        report(error, DELIVERY_TOLERANCE_MISSING, 0u, DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD,
               strlen(DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD));
        return false;
    }
    if (!flow_given) {
        report(error, DELIVERY_TOLERANCE_MISSING, 0u, DELIVERY_TOLERANCE_FLOW_DEPARTURE_WORD,
               strlen(DELIVERY_TOLERANCE_FLOW_DEPARTURE_WORD));
        return false;
    }
    /*
     * Its own fault rather than a zero band or the temperature band standing in
     * for it. Zero would hold two runs to agreeing exactly, which no pair of
     * trajectories from a real machine ever does; the temperature band would be
     * twice as loose as the design intends and would go on reading as declared
     * here while nothing had declared it. Both turn a file somebody forgot to
     * write into a criterion nobody chose.
     */
    if (!post_draw_given) {
        report(error, DELIVERY_TOLERANCE_MISSING, 0u, DELIVERY_TOLERANCE_POST_DRAW_MATCH_WORD,
               strlen(DELIVERY_TOLERANCE_POST_DRAW_MATCH_WORD));
        return false;
    }

    *tolerance = staging;
    error->fault = DELIVERY_TOLERANCE_OK;
    return true;
}
