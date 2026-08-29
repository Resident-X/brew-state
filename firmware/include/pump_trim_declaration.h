/*
 * The figures the pump trim is given rather than compiled with.
 *
 * DEC-CORRECTION-KEEPS-THE-ACCOUNT trims the commanded pump level closed-loop
 * toward the rate a delivery's course commands, driven by the gap the flow seam
 * reports against it. How hard that trim leans on a standing gap and how fast it
 * leans on one that persists are not properties of any machine this software is
 * compiled for -- a puck's resistance, a pump's own flow-versus-pressure
 * characteristic and the mechanical pressure cap all sit between the command and
 * what the seam reports, and none of them is represented here or anywhere else
 * this trim reads. They are choices this design makes about how hard to correct,
 * on exactly the terms params/steam_control.declaration already keeps the steam
 * loop's own gains out of its source: a figure the design can only vary by
 * editing and recompiling the control law is one nobody varies to find out what
 * it costs, and the whole point of the suite that exercises the trim is that
 * moving one of these figures moves which courses converge and which saturate,
 * with no control law rebuilt.
 *
 * They carry values rather than living as #defines beside control.c's own
 * coefficients, unlike CONTROL_PROPORTIONAL_PERMILLE_PER_K and its neighbours,
 * for the same reason steam's own gains do not: those figures answer for the
 * loop that reconstructs a temperature no sensor reports, and this one answers
 * for a loop closed directly on a seam reading, which is the same shape of
 * question params/tolerance.declaration's own band already keeps as data rather
 * than as source.
 *
 * Nothing here names a plant structure, a puck, or a pump's flow-versus-pressure
 * relation. A gain is what the design does about a rate gap, and it has to
 * outlive both whichever plant model the machine happens to be compiled against
 * and whatever loop was eventually built to drive it.
 */
#ifndef PUMP_TRIM_DECLARATION_H
#define PUMP_TRIM_DECLARATION_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "plant_origin.h"

/*
 * The name each figure is written as in the declaration. Reached by name
 * rather than by position, so a line added beside these later does not have to
 * sit in any particular order relative to them.
 */

/* The trim's proportional gain against the rate gap. */
#define PUMP_TRIM_DECLARATION_GAIN_WORD "pump-trim-gain"

/* The trim's integral gain against the same gap. */
#define PUMP_TRIM_DECLARATION_INTEGRAL_GAIN_WORD "pump-trim-integral-gain"

/*
 * The units a figure may be stated in.
 *
 * Both gains are in thousandths of a permille of pump scale per unit of the
 * rate error they answer, on the same terms steam_control_declaration_unit_t's
 * own gains are: one rule across the family is what lets a reader compare a
 * proportional figure against an integral one without first working out which
 * scaling each was written at, and the price -- a gain spelled with several
 * digits -- is paid once here rather than every time somebody reads it.
 */
typedef enum {
    PUMP_TRIM_DECLARATION_UNIT_MILLI_PERMILLE_PER_ML_PER_S = 0,
    PUMP_TRIM_DECLARATION_UNIT_MILLI_PERMILLE_PER_ML_PER_S_S,
    PUMP_TRIM_DECLARATION_UNIT_COUNT
} pump_trim_declaration_unit_t;

/*
 * The word each unit is written as, in the order the enumeration above
 * declares them. Paired with that enumeration by a static assertion in the
 * loader, so a unit added without a word -- or a word left behind by a unit
 * removed -- fails the build rather than the declaration.
 */
#define PUMP_TRIM_DECLARATION_UNIT_WORDS                                                          \
    {                                                                                             \
        "milli-permille-per-ml-per-s", "milli-permille-per-ml-per-s-s"                            \
    }

/* The longest a figure's name may be in a fault report, terminator included. */
#define PUMP_TRIM_DECLARATION_NAME_MAX 48

/*
 * What the pump trim reads at initialisation.
 *
 * Both fields are thousandths of a permille of pump scale per unit of the
 * commanded-minus-measured rate error the trim answers -- ml/s for the
 * proportional term and ml/s-second for the integral one -- on the same
 * footing every gain behind the plant seam is signed and the same width, so a
 * range check written once over the table serves both.
 */
typedef struct {
    int32_t gain_milli_permille_per_ml_per_s;
    int32_t integral_gain_milli_permille_per_ml_per_s_s;
} pump_trim_declaration_t;

/* Why a declaration was refused. */
typedef enum {
    /* Nothing was wrong; the record is populated. */
    PUMP_TRIM_DECLARATION_OK = 0,
    /* A line is not a comment, not blank, and not `name = value`. */
    PUMP_TRIM_DECLARATION_MALFORMED,
    /* A line names a figure nothing in this build reads. */
    PUMP_TRIM_DECLARATION_UNKNOWN,
    /* A figure is given more than once, so which one applies is unclear. */
    PUMP_TRIM_DECLARATION_DUPLICATE,
    /* A figure is outside the range this build admits for it. */
    PUMP_TRIM_DECLARATION_OUT_OF_RANGE,
    /* A figure this build reads is declared nowhere. */
    PUMP_TRIM_DECLARATION_MISSING,
    /*
     * A figure carries no unit, a unit that is not one of the declared
     * words, or a unit that is not the one this build holds it in.
     */
    PUMP_TRIM_DECLARATION_UNIT_MISMATCH,
    /*
     * A figure carries no origin, a kind that is not one of the declared
     * words, or a kind with no account behind it.
     */
    PUMP_TRIM_DECLARATION_ORIGIN
} pump_trim_declaration_fault_t;

/*
 * What was wrong with a refused declaration. `line` is the one-based line the
 * fault was found on, and is zero for a figure that is absent, which has no
 * line to point at.
 */
typedef struct {
    pump_trim_declaration_fault_t fault;
    uint32_t line;
    char name[PUMP_TRIM_DECLARATION_NAME_MAX];
} pump_trim_declaration_error_t;

/*
 * Read a pump trim declaration into the record above.
 *
 * The grammar is a figure's name, an equals sign, a whole number, the word
 * for the unit that number is in, and the origin annotation every declared
 * figure in this project carries: a kind from the vocabulary in
 * plant_origin.h and an account of what the figure was arrived at from. All
 * are required, on the same terms steam_control_declaration_load's own loader
 * requires them.
 *
 * Both figures the record carries are required. A declaration that leaves one
 * out is refused rather than defaulted: a proportional gain silently taken as
 * nothing is a trim that never answers a gap at all, and an integral gain
 * silently taken as nothing is one that never closes a gap that persists --
 * both of which read as a machine that came up fine and quietly never
 * corrects anything.
 *
 * Returns false, writing the fault into `error`, when the text or the record
 * is null, when a line cannot be read, when a figure is named twice or not at
 * all, when it is stated in the wrong unit, when it is outside the range this
 * build admits, or when it is not accounted for. Returns false and writes
 * nothing when `error` is null, since a caller that cannot be told what was
 * wrong must not be told the declaration was fine.
 */
bool pump_trim_declaration_load(const char *text, size_t length,
                                pump_trim_declaration_t *declaration,
                                pump_trim_declaration_error_t *error);

#endif /* PUMP_TRIM_DECLARATION_H */
