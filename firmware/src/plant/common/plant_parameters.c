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
 *
 * A line carries two annotations against its value as well as the value
 * itself: how far out the design assumes that value may be, and where the
 * figure came from. Both are read by the one walk below, and one of them is
 * kept. Two walks would mean two parsers, and two parsers are one grammar
 * until somebody extends one of them -- at which point a description would
 * load through one operation and be refused by the other, which is a worse
 * answer than either of them alone.
 */
#include "plant_model.h"

#include "plant_budget.h"
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
static const char *const ORIGIN_WORDS[] = PLANT_ORIGIN_KIND_WORDS;

/*
 * The words and the kinds are two halves of one vocabulary and are edited
 * separately, so the build is made to check they still agree. Adding a kind and
 * forgetting its word is the likely edit -- it is the one the header invites --
 * and it would otherwise read one entry past this array at run time rather than
 * failing here.
 */
_Static_assert(sizeof(ORIGIN_WORDS) / sizeof(ORIGIN_WORDS[0]) == PLANT_ORIGIN_KIND_COUNT,
               "every origin kind declares a word, and no word belongs to no kind");

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
    while (kind < PLANT_ORIGIN_KIND_COUNT && !spans_word(cursor, kind_end, ORIGIN_WORDS[kind])) {
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

/*
 * Read the assumed-error annotation occupying [begin, end), which the caller
 * has established starts with the marker, and say whether it can stand.
 *
 * The token is a fraction of the value it stands against, so it is a plain
 * number and is parsed by the same routine the value itself is: a description
 * that spells a coefficient one way and its error another would be two
 * grammars in one line.
 *
 * Three things disqualify what is read. A marker with nothing behind it says
 * the author meant to state an error and did not, which is worse than not
 * having claimed one at all -- it reads as declared to anyone skimming. A
 * negative error is not a smaller error, it is a sentence with no meaning: the
 * figure says how far either side of the value the machine may sit, and there
 * is no distance shorter than none. A not-a-number is what a spreadsheet that
 * divided by zero emits, and every comparison against it is false, so it is
 * caught by the lower bound being written as a question about what the value is
 * rather than about what it is not; an infinity passes that question and is
 * refused separately, because "wrong by an unbounded amount" is a statement
 * about a coefficient nobody should be designing against, not a wide margin.
 *
 * There is no upper bound. An error larger than the value is entirely possible
 * for a coefficient nobody has measured -- a loss estimated from geometry with
 * the conduction path left out can be a factor out rather than a percentage --
 * and a limit here would be this file inventing a judgement that belongs to
 * whoever wrote the description.
 */
static bool assumed_error_is_admissible(const char *begin, const char *end, float *fraction)
{
    const char *token_begin = begin + 1; /* Past the marker. */
    const char *token_end = end;
    trim(&token_begin, &token_end);

    float parsed = 0.0f;
    bool representable = true;
    if (!parse_value(token_begin, token_end, &parsed, &representable)) {
        return false;
    }
    if (!(parsed >= 0.0f)) {
        return false;
    }
    if (!isfinite(parsed)) {
        return false;
    }

    *fraction = parsed;
    return true;
}

/*
 * Where in the structure's table the coefficient called `name` sits, or
 * `spec_count` when it has none.
 *
 * The name is a span rather than a terminated string on one side and a
 * terminated one on the other, so the length is compared as well as the bytes:
 * a description naming `brew.loss` must not reach `brew.loss_w_per_k`.
 */
static size_t index_of(const plant_parameter_spec_t *specs, size_t spec_count, const char *name,
                       size_t name_length)
{
    for (size_t candidate = 0u; candidate < spec_count; candidate++) {
        const char *declared = specs[candidate].name;
        if (strlen(declared) == name_length && memcmp(declared, name, name_length) == 0) {
            return candidate;
        }
    }
    return spec_count;
}

/*
 * The one walk over a description, which both of the seam's loaders are.
 *
 * `parameters` is required and `budget` is not, because the record of what the
 * design assumes each value may be wrong by is wanted by some callers and not
 * by most. Both are assembled here and copied out only once the whole
 * description is known to be admissible, so a refusal leaves the caller with
 * what it had rather than with half of a new record.
 */
static bool read_description(const char *text, size_t length, plant_parameters_t *parameters,
                             plant_parameter_budget_t *budget, plant_parameter_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    memset(error, 0, sizeof(*error));

    size_t spec_count = 0u;
    const plant_parameter_spec_t *specs = plant_structure_parameter_specs(&spec_count);
    if (text == NULL || parameters == NULL || specs == NULL || spec_count == 0u ||
        spec_count > PLANT_PARAMETER_LIMIT) {
        report(error, PLANT_PARAMETER_MALFORMED, 0u, NULL, 0u);
        return false;
    }

    /*
     * Everything is assembled here and copied out only once the description is
     * known to be complete and admissible, so a refused description leaves the
     * caller's record untouched rather than half filled in.
     *
     * The assumed errors are assembled whether or not the caller asked for
     * them. Writing them costs one store on a line that has already been parsed
     * and read, and making the walk itself conditional on who is calling would
     * be two paths through the one parser that this file exists to keep single.
     */
    plant_parameters_t staging;
    memset(&staging, 0, sizeof(staging));
    plant_parameter_budget_t assumed;
    memset(&assumed, 0, sizeof(assumed));
    assumed.count = spec_count;
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
         * The value runs to whichever annotation comes first, and to the end of
         * the line where there is none. Splitting here rather than after
         * parsing is what keeps the value token what it always was: `1.0 ~ 0.2
         * @document p.24` offers the parser `1.0`, so the refusal of a token
         * with a second number after it -- `1.0 2.0` -- is untouched by either
         * extension. That refusal is the one an annotation grammar is most
         * likely to lose, because both extensions work by ending the value
         * somewhere earlier than the line does.
         *
         * The origin is found first and the error is looked for only ahead of
         * it, which is what fixes the order of the two. An origin's account is
         * free text running to the end of the line, so a marker appearing
         * inside it is part of what somebody wrote about a service manual
         * rather than a second annotation.
         */
        const char *origin_begin = separator + 1;
        while (origin_begin < line_end && *origin_begin != PLANT_ORIGIN_MARKER) {
            origin_begin++;
        }
        const char *budget_begin = separator + 1;
        while (budget_begin < origin_begin && *budget_begin != PLANT_BUDGET_MARKER) {
            budget_begin++;
        }
        const char *value_begin = separator + 1;
        const char *value_end = budget_begin;
        trim(&value_begin, &value_end);

        const size_t name_length = (size_t)(name_end - name_begin);
        if (name_length == 0u) {
            report(error, PLANT_PARAMETER_MALFORMED, line_number, line_begin,
                   (size_t)(line_end - line_begin));
            return false;
        }

        const size_t index = index_of(specs, spec_count, name_begin, name_length);
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

        /*
         * The assumed error is read after the origin, so a line with both
         * annotations wrong is reported as the fault declared first in
         * plant_parameter_fault_t -- fixed here rather than left to the order
         * the two happen to be written in, so a description with more than one
         * thing wrong with it reports the same fault every time it is read.
         *
         * This is the annotation that is kept. It is not enough that it be
         * well-formed, because something on this side of the seam sizes a
         * margin from it, and a figure that reached a margin calculation as a
         * negative number or as an infinity would produce a margin nobody could
         * account for rather than a refusal anybody could see.
         *
         * A value carrying no error at all is not refused. A description that
         * claims no real machine has nothing to be wrong about, and which
         * descriptions those are is settled where they live -- the same
         * division the origin annotation draws, drawn again here rather than
         * differently, because a grammar with two answers to "must an
         * annotation be present" is one nobody can hold in their head.
         */
        const bool carries_error = budget_begin != origin_begin;
        float assumed_error = 0.0f;
        if (carries_error &&
            !assumed_error_is_admissible(budget_begin, origin_begin, &assumed_error)) {
            report(error, PLANT_PARAMETER_ASSUMED_ERROR, line_number, name_begin, name_length);
            return false;
        }

        float *field = (float *)(void *)((char *)&staging + specs[index].offset);
        *field = value;
        assumed.assumed_error[index] = assumed_error;
        assumed.declared[index] = carries_error;
        supplied |= bit;
    }

    for (size_t index = 0u; index < spec_count; index++) {
        if ((supplied & ((uint64_t)1u << index)) == 0u) {
            const char *name = specs[index].name;
            report(error, PLANT_PARAMETER_MISSING, 0u, name, strlen(name));
            return false;
        }
    }

    if (budget != NULL) {
        *budget = assumed;
    }
    *parameters = staging;
    error->fault = PLANT_PARAMETER_OK;
    return true;
}

bool plant_parameters_load(const char *text, size_t length, plant_parameters_t *parameters,
                           plant_parameter_error_t *error)
{
    return read_description(text, length, parameters, NULL, error);
}

bool plant_parameter_budget_load(const char *text, size_t length, plant_parameter_budget_t *budget,
                                 plant_parameter_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    if (budget == NULL) {
        memset(error, 0, sizeof(*error));
        report(error, PLANT_PARAMETER_MALFORMED, 0u, NULL, 0u);
        return false;
    }

    /*
     * The coefficients are read and dropped. A caller asking what the design
     * assumes about the values has usually loaded them already, and reading
     * the description on any terms other than the full ones would mean a
     * budget could come back from a description the model itself would refuse
     * -- a set of errors about coefficients that never arrived.
     */
    plant_parameters_t discarded;
    return read_description(text, length, &discarded, budget, error);
}

bool plant_parameter_budget_for(const plant_parameter_budget_t *budget, const char *name,
                                float *assumed_error)
{
    if (budget == NULL || name == NULL || assumed_error == NULL) {
        return false;
    }

    size_t spec_count = 0u;
    const plant_parameter_spec_t *specs = plant_structure_parameter_specs(&spec_count);
    if (specs == NULL || spec_count == 0u || spec_count > PLANT_PARAMETER_LIMIT) {
        return false;
    }

    /*
     * A record whose length does not match the structure's answers nothing.
     * That is what a record never loaded looks like -- zeroed, and therefore
     * claiming no coefficients at all -- and answering from one would report
     * the design as assuming an error of nothing for every coefficient in the
     * model, which is the most dangerous possible reading of a description that
     * was never read.
     */
    if (budget->count != spec_count) {
        return false;
    }

    const size_t index = index_of(specs, spec_count, name, strlen(name));
    if (index == spec_count) {
        return false;
    }
    if (!budget->declared[index]) {
        return false;
    }

    *assumed_error = budget->assumed_error[index];
    return true;
}

bool plant_parameter_scale(plant_parameters_t *parameters, size_t at, float factor)
{
    if (parameters == NULL || !isfinite(factor)) {
        return false;
    }

    size_t spec_count = 0u;
    const plant_parameter_spec_t *specs = plant_structure_parameter_specs(&spec_count);
    if (specs == NULL || spec_count == 0u || spec_count > PLANT_PARAMETER_LIMIT ||
        at >= spec_count) {
        return false;
    }

    /*
     * The same route into the record the loader itself takes -- the offset the
     * structure's own table declares -- so a coefficient written here lands
     * where a description would have put it, rather than through a second
     * arrangement that could disagree with the first about which field a
     * position means.
     */
    float *const field = (float *)(void *)((char *)parameters + specs[at].offset);
    const float scaled = *field * factor;

    /*
     * Refused rather than clamped. A record clamped back to the edge of the
     * declared range would be a machine the caller did not ask for, reported as
     * though it were the corner it did: a caller sizing anything against a
     * corner has to be able to tell "the description does not admit that
     * corner" from "here is the corner", and the two demand opposite responses.
     */
    if (!isfinite(scaled) || scaled < specs[at].minimum || scaled > specs[at].maximum) {
        return false;
    }

    *field = scaled;
    return true;
}

bool plant_parameter_position(const char *name, size_t *at)
{
    if (name == NULL || at == NULL) {
        return false;
    }

    size_t spec_count = 0u;
    const plant_parameter_spec_t *specs = plant_structure_parameter_specs(&spec_count);
    if (specs == NULL || spec_count == 0u || spec_count > PLANT_PARAMETER_LIMIT) {
        return false;
    }

    const size_t found = index_of(specs, spec_count, name, strlen(name));
    if (found == spec_count) {
        return false;
    }

    *at = found;
    return true;
}

bool plant_parameter_supply_driven(size_t at, bool *driven)
{
    if (driven == NULL) {
        return false;
    }

    size_t spec_count = 0u;
    const plant_parameter_spec_t *specs = plant_structure_parameter_specs(&spec_count);
    if (specs == NULL || spec_count == 0u || spec_count > PLANT_PARAMETER_LIMIT ||
        at >= spec_count) {
        return false;
    }

    size_t named_count = 0u;
    const char *const *named = plant_structure_supply_driven_parameters(&named_count);

    *driven = false;
    for (size_t which = 0u; which < named_count && named != NULL; which++) {
        if (named[which] != NULL &&
            index_of(specs, spec_count, named[which], strlen(named[which])) == at) {
            *driven = true;
            break;
        }
    }
    return true;
}
