/*
 * The pressure the steam control law withholds feed below and enables it at.
 *
 * This is a statement about the design's own policy rather than about the
 * machine: what a casting's steam block will do when its element is switched
 * on belongs in that structure's own description, and how far below
 * saturation the design chooses to keep feeding water back does not change
 * because a different casting was built around it. So the threshold lives
 * here, declared once, rather than compiled into the control law it gates --
 * on exactly the terms params/tolerance.declaration already keeps a
 * delivery's own bands out of the control source: a figure the design can
 * only vary by editing and recompiling is one nobody varies to find out what
 * it costs.
 *
 * It carries a value rather than living as a #define beside the control
 * law's other coefficients, unlike most of what params/control.declaration
 * accounts for. Those figures are properties of the control law itself --
 * gains, a saturation ceiling -- and are the same on every build this
 * software is compiled for; this threshold is a policy choice about when
 * this design judges the steam side ready, and the band-holding loop this
 * gate feeds reads the very same declared value for its own ready-holding
 * target, which is what "read by the control law rather than compiled into
 * it" is answering.
 *
 * Nothing here names a plant structure or a control law by name. A threshold
 * is what the design withholds feed against, and it has to outlive both the
 * model the machine was designed against and whatever loop was eventually
 * built to hold it.
 */
#ifndef STEAM_CONTROL_DECLARATION_H
#define STEAM_CONTROL_DECLARATION_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "plant_origin.h"

/*
 * The name the ready-pressure threshold is written as in the declaration.
 * Reached by name rather than by position, so a line added beside it later --
 * the band-holding loop's own ready temperature target, its draw-time
 * pressure band -- does not have to sit in any particular order relative to
 * this one.
 */
#define STEAM_CONTROL_DECLARATION_READY_PRESSURE_WORD "ready-pressure-bar"

/*
 * The unit the threshold may be stated in. One entry today, on the same
 * footing params/tolerance.declaration's own unit vocabulary is: a unit the
 * loader does not know is a unit nothing can range-check, and writing the
 * word out on every line is what lets a reader tell 900 milli-bar from 900 of
 * some other quantity without already knowing which field of the record they
 * are looking at.
 */
typedef enum {
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_BAR = 0,
    STEAM_CONTROL_DECLARATION_UNIT_COUNT
} steam_control_declaration_unit_t;

/*
 * The word each unit is written as, in the order the enumeration above
 * declares them. Paired with that enumeration by a static assertion in the
 * loader, so a unit added without a word -- or a word left behind by a unit
 * removed -- fails the build rather than the declaration.
 */
#define STEAM_CONTROL_DECLARATION_UNIT_WORDS                                                       \
    {                                                                                              \
        "milli-bar"                                                                                \
    }

/* The longest a figure's name may be in a fault report, terminator included. */
#define STEAM_CONTROL_DECLARATION_NAME_MAX 48

/*
 * What the steam control law reads at initialisation. Gauge pressure, in
 * thousandths of a bar -- the unit the hardware seam already reports a
 * pressure channel in, so a reading compared against this figure is an
 * integer comparison and nothing is converted to decide whether the machine
 * has reached it.
 */
typedef struct {
    int32_t ready_pressure_milli_bar;
} steam_control_declaration_t;

/* Why a declaration was refused. */
typedef enum {
    /* Nothing was wrong; the record is populated. */
    STEAM_CONTROL_DECLARATION_OK = 0,
    /* A line is not a comment, not blank, and not `name = value`. */
    STEAM_CONTROL_DECLARATION_MALFORMED,
    /* A line names a figure nothing in this build reads. */
    STEAM_CONTROL_DECLARATION_UNKNOWN,
    /* A figure is given more than once, so which one applies is unclear. */
    STEAM_CONTROL_DECLARATION_DUPLICATE,
    /* A figure is outside the range this build admits for it. */
    STEAM_CONTROL_DECLARATION_OUT_OF_RANGE,
    /* A figure this build reads is declared nowhere. */
    STEAM_CONTROL_DECLARATION_MISSING,
    /*
     * A figure carries no unit, a unit that is not one of the declared
     * words, or a unit that is not the one this build holds it in.
     */
    STEAM_CONTROL_DECLARATION_UNIT_MISMATCH,
    /*
     * A figure carries no origin, a kind that is not one of the declared
     * words, or a kind with no account behind it.
     */
    STEAM_CONTROL_DECLARATION_ORIGIN
} steam_control_declaration_fault_t;

/*
 * What was wrong with a refused declaration. `line` is the one-based line the
 * fault was found on, and is zero for a figure that is absent, which has no
 * line to point at.
 */
typedef struct {
    steam_control_declaration_fault_t fault;
    uint32_t line;
    char name[STEAM_CONTROL_DECLARATION_NAME_MAX];
} steam_control_declaration_error_t;

/*
 * Read a steam control declaration into the record above.
 *
 * The grammar is a figure's name, an equals sign, a whole number, the word
 * for the unit that number is in, and the origin annotation every declared
 * figure in this project carries: a kind from the vocabulary in
 * plant_origin.h and an account of what the figure was arrived at from. All
 * are required, on the same terms params/tolerance.declaration's own loader
 * requires them.
 *
 * Returns false, writing the fault into `error`, when the text or the record
 * is null, when a line cannot be read, when the threshold is named twice or
 * not at all, when it is stated in the wrong unit, when it is outside the
 * range this build admits, or when it is not accounted for. Returns false
 * and writes nothing when `error` is null, since a caller that cannot be told
 * what was wrong must not be told the declaration was fine.
 */
bool steam_control_declaration_load(const char *text, size_t length,
                                    steam_control_declaration_t *declaration,
                                    steam_control_declaration_error_t *error);

#endif /* STEAM_CONTROL_DECLARATION_H */
