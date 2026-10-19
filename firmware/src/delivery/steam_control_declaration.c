/*
 * Reading a steam control declaration into the record behind
 * steam_control_declaration.h.
 *
 * It is compiled outside src/control, beside no control logic, for the same
 * reason delivery_tolerance.c beside it is: reading a declaration means
 * reaching for the standard library's number conversion, and that reaches
 * errno, which is a different symbol on a host and on the target. The
 * control logic is required to be byte-identical across the two, and it is
 * the check that compares them which would have to be weakened to admit a
 * translation unit that cannot be. Nothing is lost by the separation: the
 * control path never calls the reader, because a record is loaded by whatever
 * brings the steam control law up and hands it in, exactly as the parameter
 * description and the limits declaration are for the brew side; it calls only
 * the validity function the reader ends in, which reaches no number conversion,
 * so a declaration built by hand is held to what a loaded one is. It sits
 * beside delivery_tolerance.c rather than in a directory of its own because
 * the two answer to the same build-time need -- a runtime-loaded declaration
 * outside the control law's byte-identical boundary -- and that need, not
 * the word "delivery", is what this location is compiled for.
 *
 * The figures are read against a table rather than by a branch per name. A
 * branch per name is what the file carried while there was one figure to
 * read, and it is the shape that goes wrong as figures are added: the
 * unit check, the range check, the duplicate check and the absence check are
 * each written once per figure, and the one that is forgotten is forgotten
 * silently, because a figure with no range check reads exactly like a figure
 * whose range is wide. Each figure declares its word, its unit, the span it
 * is admissible inside and where it lands in the record, and every check is
 * written once and taken over the table.
 *
 * The walk is one pass, and the record is assembled aside and copied out
 * only once the whole declaration is known to be admissible, on the same
 * terms delivery_tolerance_load already keeps: a refusal leaves the caller
 * with what it had rather than with some figures read and the rest of the
 * record left at whatever the memory contained.
 */
#include "steam_control_declaration.h"

#include <errno.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#include "machine_actuation.h"

/*
 * The longest figure a line may carry. Well beyond the digits a 32-bit
 * integer spells, so a token this long is a declaration that needs looking
 * at rather than a number to read.
 *
 * It carries this loader's own name rather than a bare one, on the same
 * terms delivery_tolerance.c's own figure bound does: two files each
 * defining an unqualified bound of this shape would be two homes for what
 * reads as one figure.
 */
#define STEAM_CONTROL_DECLARATION_FIGURE_TEXT_MAX 32

/*
 * The span of gauge pressures this grammar will read on the steam path, in
 * thousandths of a bar. It bounds the ready threshold and both edges of the
 * draw-time band, because all three are the same physical quantity read off
 * the same path and a reader could mean any figure inside it by any of them.
 *
 * A tenth of a bar is close to nothing at all -- a machine holding feed back
 * until the path has barely left rest -- and fifteen bar sits at the pump's
 * own nameplate rating in thermoblock.params, well past anything a steam
 * path's saturation relation would put there. Neither end is a claim about
 * where the design should set any of the three; both are chosen to admit any
 * figure a reader could mean and refuse a digit typed in the wrong place.
 */
#define STEAM_CONTROL_DECLARATION_PRESSURE_LOW_MILLI_BAR 100
#define STEAM_CONTROL_DECLARATION_PRESSURE_HIGH_MILLI_BAR 15000

/*
 * The span of block temperatures this grammar will read, in thousandths of a
 * degree Celsius. Below the low end the steam path carries no gauge pressure
 * at all under any saturation relation, so a target there is not a ready
 * state; the high end sits at the temperature thermoblock.params records the
 * steam thermostat as permitting, past which the machine's own protection
 * rather than this design decides what happens.
 */
#define STEAM_CONTROL_DECLARATION_TEMPERATURE_LOW_MILLI_C 100000
#define STEAM_CONTROL_DECLARATION_TEMPERATURE_HIGH_MILLI_C 200000

/*
 * The span either feed level -- the level a draw starts at and the ceiling the
 * pressure loop is never commanded past -- may be declared inside, in permille
 * of the feed pump's full scale. A level of nothing is not a low feed: as a
 * start it is a draw that is never fed, which the readiness gate already
 * expresses, and as a ceiling it leaves the pressure loop with no actuator at
 * all. The highest is the actuator's own full scale, which is where the level
 * stops meaning anything rather than a figure this file chooses -- so it is read
 * from the machine's actuation vocabulary rather than written again here.
 */
#define STEAM_CONTROL_DECLARATION_FEED_LEVEL_LOW_PERMILLE 1
#define STEAM_CONTROL_DECLARATION_FEED_LEVEL_HIGH_PERMILLE ACTUATION_FULL_SCALE

/*
 * The span the feed's rise limit may be declared inside, in permille of the feed
 * pump's scale per second. Nothing is admissible: a design that holds a draw's
 * feed at its start level and lets the pressure loop only take it down has made
 * a choice rather than omitted a figure. The high end is the whole scale in a
 * hundredth of a second, a step of the loop, past which the limit limits nothing.
 */
#define STEAM_CONTROL_DECLARATION_FEED_RISE_LOW_PERMILLE_PER_S 0
#define STEAM_CONTROL_DECLARATION_FEED_RISE_HIGH_PERMILLE_PER_S 100000

/*
 * The span the superheat setpoint may be declared inside, in thousandths of a
 * kelvin. Nothing is admissible -- steam held just at saturation is a setpoint,
 * if a poor one -- and the high end is a hundred kelvin, well past any superheat
 * a domestic steam block makes and where a digit typed in the wrong place would
 * land.
 */
#define STEAM_CONTROL_DECLARATION_SUPERHEAT_LOW_MILLI_K 0
#define STEAM_CONTROL_DECLARATION_SUPERHEAT_HIGH_MILLI_K 100000

/*
 * The span the ready-holding phase's proportional gain may be declared inside,
 * in thousandths of a permille of heater scale per kelvin. A gain of nothing
 * is a loop that does not track, so the low end is the smallest figure that is
 * not that. The high end is a thousand permille per kelvin, at which a single
 * kelvin of error commands the whole element -- past that the gain has stopped
 * describing a proportional band and become a switch, which is a different
 * design rather than an aggressive setting of this one.
 */
#define STEAM_CONTROL_DECLARATION_READY_GAIN_LOW_MILLI 1
#define STEAM_CONTROL_DECLARATION_READY_GAIN_HIGH_MILLI 1000000

/*
 * The span the ready-holding phase's integral gain may be declared inside, in
 * thousandths of a permille of heater scale per kelvin per second. The low end
 * is the smallest figure that still accumulates, for the reason the
 * proportional gain's is; the high end is a thousand permille per kelvin per
 * second, at which one second of a single kelvin of error has accumulated the
 * whole element on its own and the integral has stopped being the slow term it
 * is here to be.
 */
#define STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_LOW_MILLI 1
#define STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_HIGH_MILLI 1000000

/*
 * The span the superheat loop's proportional gain may be declared inside, in
 * thousandths of a permille of heater scale per kelvin of superheat error. It is
 * drawn against the same unit the ready-holding phase's gain is, and is its own
 * figure rather than a reading of that one because the two answer different
 * errors -- one the casting's distance from a target, the other the outlet
 * steam's distance from its setpoint -- and either may be revised without the
 * other silently moving with it. The low end is the smallest gain that is not
 * nothing, and the high end is a thousand permille per kelvin, past which the
 * loop is a switch.
 */
#define STEAM_CONTROL_DECLARATION_SUPERHEAT_GAIN_LOW_MILLI 1
#define STEAM_CONTROL_DECLARATION_SUPERHEAT_GAIN_HIGH_MILLI 1000000

/*
 * The span the superheat loop's integral gain may be declared inside, in
 * thousandths of a permille of heater scale per kelvin-second, on the terms the
 * ready-holding phase's integral bound is drawn on and for the same reasons.
 */
#define STEAM_CONTROL_DECLARATION_SUPERHEAT_INTEGRAL_GAIN_LOW_MILLI 1
#define STEAM_CONTROL_DECLARATION_SUPERHEAT_INTEGRAL_GAIN_HIGH_MILLI 1000000

/*
 * The span the pressure loop's proportional gain may be declared inside, in
 * thousandths of a permille of feed scale per bar of pressure error. The low end
 * is the smallest gain that is not nothing. The high end is a hundred thousand
 * permille per bar, at which a hundredth of a bar commands the whole pump.
 */
#define STEAM_CONTROL_DECLARATION_FEED_GAIN_LOW_MILLI 1
#define STEAM_CONTROL_DECLARATION_FEED_GAIN_HIGH_MILLI 100000000

/*
 * The span the pressure loop's integral gain may be declared inside, in
 * thousandths of a permille of feed scale per bar-second, drawn against the
 * pressure error for the reason the proportional gain above is and its own
 * figure because one bounds how hard a standing error is answered and the other
 * how fast an accumulating one is.
 */
#define STEAM_CONTROL_DECLARATION_FEED_INTEGRAL_GAIN_LOW_MILLI 1
#define STEAM_CONTROL_DECLARATION_FEED_INTEGRAL_GAIN_HIGH_MILLI 100000000

/*
 * The span the feedforward gain may be declared inside, in thousandths of a
 * permille of heater scale per permille of commanded feed. Nothing is
 * admissible here, unlike either tracking gain: a design that has decided to
 * answer the feed's load from feedback alone has made a choice rather than
 * omitted a term, and it is the choice the suite has to be able to declare to
 * show what the feedforward buys. The high end is a thousand, at which one
 * permille of feed asks for the whole element and the machine could not
 * command a millilitre of feed without saturating.
 */
#define STEAM_CONTROL_DECLARATION_FEED_LOAD_GAIN_LOW_MILLI 0
#define STEAM_CONTROL_DECLARATION_FEED_LOAD_GAIN_HIGH_MILLI 1000000

/*
 * The span the standing-load feedforward may be declared inside, in permille
 * of heater scale. Nothing is admissible for the reason it is on the gain
 * above -- a design answering the standing loss out of feedback alone has
 * chosen to, and it is the choice a suite has to be able to declare -- and the
 * high end is the actuator's own full scale, past which a duty has stopped
 * being a duty. It is a level rather than a gain, so it is bounded on the same
 * scale a level is, which is read from the machine's actuation vocabulary
 * rather than written again here.
 */
#define STEAM_CONTROL_DECLARATION_STANDING_LOAD_LOW_PERMILLE 0
#define STEAM_CONTROL_DECLARATION_STANDING_LOAD_HIGH_PERMILLE ACTUATION_FULL_SCALE

static const char *const ORIGIN_WORDS[] = PLANT_ORIGIN_KIND_WORDS;

_Static_assert(sizeof(ORIGIN_WORDS) / sizeof(ORIGIN_WORDS[0]) == (size_t)PLANT_ORIGIN_KIND_COUNT,
               "every origin kind declares a word, and no word belongs to no kind");

static const char *const UNIT_WORDS[] = STEAM_CONTROL_DECLARATION_UNIT_WORDS;

_Static_assert(sizeof(UNIT_WORDS) / sizeof(UNIT_WORDS[0]) ==
                  (size_t)STEAM_CONTROL_DECLARATION_UNIT_COUNT,
               "every unit declares a word, and no word belongs to no unit");

/*
 * One figure this grammar reads: the word it is written as, the unit it is
 * held in, the span it is admissible inside, and where it lands in the record.
 *
 * The offset is how the table reaches the field rather than a pointer per
 * figure, on the same terms plant_parameter_spec_t behind the plant seam
 * already reaches a coefficient's home: every field is the same type, so one
 * write serves all of them and a figure added to the record cannot be given a
 * writer of the wrong width.
 */
typedef struct {
    const char *word;
    steam_control_declaration_unit_t unit;
    int32_t low;
    int32_t high;
    size_t offset;
} figure_spec_t;

static const figure_spec_t FIGURES[] = {
    {STEAM_CONTROL_DECLARATION_READY_PRESSURE_WORD, STEAM_CONTROL_DECLARATION_UNIT_MILLI_BAR,
     STEAM_CONTROL_DECLARATION_PRESSURE_LOW_MILLI_BAR,
     STEAM_CONTROL_DECLARATION_PRESSURE_HIGH_MILLI_BAR,
     offsetof(steam_control_declaration_t, ready_pressure_milli_bar)},
    {STEAM_CONTROL_DECLARATION_READY_TEMPERATURE_WORD, STEAM_CONTROL_DECLARATION_UNIT_MILLI_C,
     STEAM_CONTROL_DECLARATION_TEMPERATURE_LOW_MILLI_C,
     STEAM_CONTROL_DECLARATION_TEMPERATURE_HIGH_MILLI_C,
     offsetof(steam_control_declaration_t, ready_temperature_milli_c)},
    {STEAM_CONTROL_DECLARATION_DRAW_FLOOR_WORD, STEAM_CONTROL_DECLARATION_UNIT_MILLI_BAR,
     STEAM_CONTROL_DECLARATION_PRESSURE_LOW_MILLI_BAR,
     STEAM_CONTROL_DECLARATION_PRESSURE_HIGH_MILLI_BAR,
     offsetof(steam_control_declaration_t, draw_pressure_floor_milli_bar)},
    {STEAM_CONTROL_DECLARATION_DRAW_CEILING_WORD, STEAM_CONTROL_DECLARATION_UNIT_MILLI_BAR,
     STEAM_CONTROL_DECLARATION_PRESSURE_LOW_MILLI_BAR,
     STEAM_CONTROL_DECLARATION_PRESSURE_HIGH_MILLI_BAR,
     offsetof(steam_control_declaration_t, draw_pressure_ceiling_milli_bar)},
    {STEAM_CONTROL_DECLARATION_DRAW_START_FEED_WORD, STEAM_CONTROL_DECLARATION_UNIT_PERMILLE,
     STEAM_CONTROL_DECLARATION_FEED_LEVEL_LOW_PERMILLE,
     STEAM_CONTROL_DECLARATION_FEED_LEVEL_HIGH_PERMILLE,
     offsetof(steam_control_declaration_t, draw_start_feed_permille)},
    {STEAM_CONTROL_DECLARATION_FEED_CEILING_WORD, STEAM_CONTROL_DECLARATION_UNIT_PERMILLE,
     STEAM_CONTROL_DECLARATION_FEED_LEVEL_LOW_PERMILLE,
     STEAM_CONTROL_DECLARATION_FEED_LEVEL_HIGH_PERMILLE,
     offsetof(steam_control_declaration_t, feed_ceiling_permille)},
    {STEAM_CONTROL_DECLARATION_FEED_RISE_LIMIT_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_PERMILLE_PER_S,
     STEAM_CONTROL_DECLARATION_FEED_RISE_LOW_PERMILLE_PER_S,
     STEAM_CONTROL_DECLARATION_FEED_RISE_HIGH_PERMILLE_PER_S,
     offsetof(steam_control_declaration_t, feed_rise_limit_permille_per_s)},
    {STEAM_CONTROL_DECLARATION_SUPERHEAT_SETPOINT_WORD, STEAM_CONTROL_DECLARATION_UNIT_MILLI_K,
     STEAM_CONTROL_DECLARATION_SUPERHEAT_LOW_MILLI_K,
     STEAM_CONTROL_DECLARATION_SUPERHEAT_HIGH_MILLI_K,
     offsetof(steam_control_declaration_t, superheat_setpoint_milli_k)},
    {STEAM_CONTROL_DECLARATION_READY_GAIN_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_K,
     STEAM_CONTROL_DECLARATION_READY_GAIN_LOW_MILLI,
     STEAM_CONTROL_DECLARATION_READY_GAIN_HIGH_MILLI,
     offsetof(steam_control_declaration_t, ready_gain_milli_permille_per_k)},
    {STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_K_S,
     STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_LOW_MILLI,
     STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_HIGH_MILLI,
     offsetof(steam_control_declaration_t, ready_integral_gain_milli_permille_per_k_s)},
    {STEAM_CONTROL_DECLARATION_SUPERHEAT_GAIN_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_K,
     STEAM_CONTROL_DECLARATION_SUPERHEAT_GAIN_LOW_MILLI,
     STEAM_CONTROL_DECLARATION_SUPERHEAT_GAIN_HIGH_MILLI,
     offsetof(steam_control_declaration_t, superheat_gain_milli_permille_per_k)},
    {STEAM_CONTROL_DECLARATION_SUPERHEAT_INTEGRAL_GAIN_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_K_S,
     STEAM_CONTROL_DECLARATION_SUPERHEAT_INTEGRAL_GAIN_LOW_MILLI,
     STEAM_CONTROL_DECLARATION_SUPERHEAT_INTEGRAL_GAIN_HIGH_MILLI,
     offsetof(steam_control_declaration_t, superheat_integral_gain_milli_permille_per_k_s)},
    {STEAM_CONTROL_DECLARATION_FEED_GAIN_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_BAR,
     STEAM_CONTROL_DECLARATION_FEED_GAIN_LOW_MILLI,
     STEAM_CONTROL_DECLARATION_FEED_GAIN_HIGH_MILLI,
     offsetof(steam_control_declaration_t, feed_gain_milli_permille_per_bar)},
    {STEAM_CONTROL_DECLARATION_FEED_INTEGRAL_GAIN_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_BAR_S,
     STEAM_CONTROL_DECLARATION_FEED_INTEGRAL_GAIN_LOW_MILLI,
     STEAM_CONTROL_DECLARATION_FEED_INTEGRAL_GAIN_HIGH_MILLI,
     offsetof(steam_control_declaration_t, feed_integral_gain_milli_permille_per_bar_s)},
    {STEAM_CONTROL_DECLARATION_FEED_LOAD_GAIN_WORD,
     STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_PERMILLE,
     STEAM_CONTROL_DECLARATION_FEED_LOAD_GAIN_LOW_MILLI,
     STEAM_CONTROL_DECLARATION_FEED_LOAD_GAIN_HIGH_MILLI,
     offsetof(steam_control_declaration_t, feed_load_gain_milli_permille_per_permille)},
    {STEAM_CONTROL_DECLARATION_STANDING_LOAD_WORD, STEAM_CONTROL_DECLARATION_UNIT_PERMILLE,
     STEAM_CONTROL_DECLARATION_STANDING_LOAD_LOW_PERMILLE,
     STEAM_CONTROL_DECLARATION_STANDING_LOAD_HIGH_PERMILLE,
     offsetof(steam_control_declaration_t, standing_load_permille)}
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
_Static_assert(sizeof(steam_control_declaration_t) / sizeof(int32_t) == FIGURE_COUNT,
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

static void report(steam_control_declaration_error_t *error, steam_control_declaration_fault_t fault,
                   uint32_t line, const char *name, size_t name_length)
{
    error->fault = fault;
    error->line = line;

    size_t copied = name_length;
    if (copied > STEAM_CONTROL_DECLARATION_NAME_MAX - 1u) {
        copied = STEAM_CONTROL_DECLARATION_NAME_MAX - 1u;
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
    char text[STEAM_CONTROL_DECLARATION_FIGURE_TEXT_MAX];
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
static int32_t *field_of(steam_control_declaration_t *staging, const figure_spec_t *spec)
{
    return (int32_t *)(void *)((char *)staging + spec->offset);
}

/*
 * Whether a declaration is one the law may be configured from: every figure in
 * the range this build admits for it, the floor under the ceiling, and the
 * draw-start feed no higher than the feed ceiling.
 *
 * The loader asks it of the record it has read and the law asks it of the one it
 * is handed, so a record built by hand is held to what a file is.
 *
 * The pairs are reported as their own faults rather than as either figure being
 * out of range: what is wrong with a floor at or above its own ceiling is the
 * pair, and a caller sent to one of the two lines would find a figure that is
 * perfectly reasonable on its own. A band admitting nothing is a criterion no
 * draw could ever meet rather than an unusually tight one.
 */
bool steam_control_declaration_admissible(const steam_control_declaration_t *declaration,
                                          steam_control_declaration_error_t *error)
{
    if (declaration == NULL) {
        return false;
    }

    for (size_t at = 0u; at < FIGURE_COUNT; at++) {
        const int32_t figure =
            *(const int32_t *)(const void *)((const char *)declaration + FIGURES[at].offset);
        if (figure < FIGURES[at].low || figure > FIGURES[at].high) {
            if (error != NULL) {
                report(error, STEAM_CONTROL_DECLARATION_OUT_OF_RANGE, 0u, FIGURES[at].word,
                       strlen(FIGURES[at].word));
            }
            return false;
        }
    }

    if (declaration->draw_pressure_floor_milli_bar >= declaration->draw_pressure_ceiling_milli_bar) {
        if (error != NULL) {
            report(error, STEAM_CONTROL_DECLARATION_BAND_INVERTED, 0u,
                   STEAM_CONTROL_DECLARATION_DRAW_FLOOR_WORD,
                   strlen(STEAM_CONTROL_DECLARATION_DRAW_FLOOR_WORD));
        }
        return false;
    }

    if (declaration->draw_start_feed_permille > declaration->feed_ceiling_permille) {
        if (error != NULL) {
            report(error, STEAM_CONTROL_DECLARATION_FEED_START_ABOVE_CEILING, 0u,
                   STEAM_CONTROL_DECLARATION_DRAW_START_FEED_WORD,
                   strlen(STEAM_CONTROL_DECLARATION_DRAW_START_FEED_WORD));
        }
        return false;
    }
    return true;
}

bool steam_control_declaration_load(const char *text, size_t length,
                                    steam_control_declaration_t *declaration,
                                    steam_control_declaration_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    memset(error, 0, sizeof(*error));

    if (text == NULL || declaration == NULL) {
        report(error, STEAM_CONTROL_DECLARATION_MALFORMED, 0u, NULL, 0u);
        return false;
    }

    steam_control_declaration_t staging;
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
            report(error, STEAM_CONTROL_DECLARATION_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        const char *name_begin = line_begin;
        const char *name_end = separator;
        trim(&name_begin, &name_end);
        const size_t name_length = (size_t)(name_end - name_begin);
        if (name_length == 0u) {
            report(error, STEAM_CONTROL_DECLARATION_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        /*
         * The figure runs to the origin annotation where there is one, and
         * to the end of the line where there is none, on the same terms
         * delivery_tolerance.c's own split is: taken before the figure is
         * read, so the refusal of a token with a second number after it does
         * not depend on whether an origin was written.
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
            report(error, STEAM_CONTROL_DECLARATION_UNKNOWN, line_number, name_begin, name_length);
            return false;
        }
        if (given[at]) {
            report(error, STEAM_CONTROL_DECLARATION_DUPLICATE, line_number, name_begin, name_length);
            return false;
        }

        if (origin_begin == line_end || !origin_is_admissible(origin_begin, line_end)) {
            report(error, STEAM_CONTROL_DECLARATION_ORIGIN, line_number, name_begin, name_length);
            return false;
        }

        /*
         * The figure region carries the number and then the word for the
         * unit it is in, split at the last run of blanks rather than the
         * first, on the same terms delivery_tolerance.c's own split is: a
         * region with a second number in it still reaches parse_figure with
         * both, and is still refused as malformed rather than quietly
         * reading the first and taking the second for a unit.
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
            report(error, STEAM_CONTROL_DECLARATION_MALFORMED, line_number, name_begin, name_length);
            return false;
        }
        if (unit_begin == figure_begin || number_end == figure_begin) {
            report(error, STEAM_CONTROL_DECLARATION_UNIT_MISMATCH, line_number, name_begin,
                   name_length);
            return false;
        }

        long figure = 0;
        if (!parse_figure(figure_begin, number_end, &figure)) {
            report(error, STEAM_CONTROL_DECLARATION_MALFORMED, line_number, name_begin, name_length);
            return false;
        }

        if (!spans_word(unit_begin, figure_end, UNIT_WORDS[FIGURES[at].unit])) {
            report(error, STEAM_CONTROL_DECLARATION_UNIT_MISMATCH, line_number, name_begin,
                   name_length);
            return false;
        }

        if (figure < (long)FIGURES[at].low || figure > (long)FIGURES[at].high) {
            report(error, STEAM_CONTROL_DECLARATION_OUT_OF_RANGE, line_number, name_begin,
                   name_length);
            return false;
        }

        *field_of(&staging, &FIGURES[at]) = (int32_t)figure;
        given[at] = true;
    }

    for (size_t at = 0u; at < FIGURE_COUNT; at++) {
        if (!given[at]) {
            report(error, STEAM_CONTROL_DECLARATION_MISSING, 0u, FIGURES[at].word,
                   strlen(FIGURES[at].word));
            return false;
        }
    }

    /*
     * The record as a whole is asked once every figure has been read, so a line
     * out of range is reported with its line number and a pair that cannot
     * stand is reported as the pair.
     */
    if (!steam_control_declaration_admissible(&staging, error)) {
        return false;
    }

    *declaration = staging;
    error->fault = STEAM_CONTROL_DECLARATION_OK;
    return true;
}
