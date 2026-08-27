/*
 * The figures the steam control law is given rather than compiled with.
 *
 * These are statements about the design's own policy rather than about the
 * machine: what a casting's steam block will do when its element is switched
 * on belongs in that structure's own description, and where this design
 * chooses to hold the steam path, how hard it leans on an error, and how long
 * it makes the block earn thermal margin before it starts making steam do not
 * change because a different casting was built around it. So they live here,
 * declared once, rather than compiled into the loop that reads them -- on
 * exactly the terms params/tolerance.declaration already keeps a delivery's
 * own bands out of the control source: a figure the design can only vary by
 * editing and recompiling is one nobody varies to find out what it costs.
 *
 * They carry values rather than living as #defines beside the control law's
 * other coefficients, unlike most of what params/control.declaration accounts
 * for. Those figures are properties of the control law itself and are the same
 * on every build this software is compiled for; these are policy choices about
 * where this design holds the steam side and how it gets there, and the whole
 * point of the suite that exercises the loop is that moving one of them moves
 * which trajectories the suite accepts, with no control law rebuilt.
 *
 * Nothing here names a plant structure or a control law by name. A threshold,
 * a band, an interval and a gain are what the design does about a steam path,
 * and they have to outlive both the model the machine was designed against and
 * whatever loop was eventually built to hold it.
 */
#ifndef STEAM_CONTROL_DECLARATION_H
#define STEAM_CONTROL_DECLARATION_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "plant_origin.h"

/*
 * The name each figure is written as in the declaration. Reached by name
 * rather than by position, so a line added beside these later does not have to
 * sit in any particular order relative to them.
 */

/* The pressure below which the steam feed pump is withheld outright. */
#define STEAM_CONTROL_DECLARATION_READY_PRESSURE_WORD "ready-pressure-bar"

/* The block temperature the loop holds while no draw is under way. */
#define STEAM_CONTROL_DECLARATION_READY_TEMPERATURE_WORD "ready-temperature-c"

/* The two edges of the pressure band a draw is held inside. */
#define STEAM_CONTROL_DECLARATION_DRAW_FLOOR_WORD "draw-pressure-floor-bar"
#define STEAM_CONTROL_DECLARATION_DRAW_CEILING_WORD "draw-pressure-ceiling-bar"

/*
 * How long feed is held back after a draw begins, while the heater alone
 * builds the block the thermal margin the first steam is made out of.
 */
#define STEAM_CONTROL_DECLARATION_MARGIN_INTERVAL_WORD "margin-building-interval-ms"

/* How long engaged feed takes to reach its sustainable rate rather than step to it. */
#define STEAM_CONTROL_DECLARATION_FEED_RISE_WORD "feed-rise-interval-ms"

/* The level engaged, settled feed is commanded at and never driven past. */
#define STEAM_CONTROL_DECLARATION_SUSTAINABLE_FEED_WORD "sustainable-feed-rate"

/* The gains the ready-holding phase tracks its temperature target with. */
#define STEAM_CONTROL_DECLARATION_READY_GAIN_WORD "ready-temperature-gain"
#define STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_WORD "ready-temperature-integral-gain"

/* The gains the draw phase tracks its pressure target with. */
#define STEAM_CONTROL_DECLARATION_DRAW_GAIN_WORD "draw-pressure-gain"
#define STEAM_CONTROL_DECLARATION_DRAW_INTEGRAL_GAIN_WORD "draw-pressure-integral-gain"

/* The duty the heater is fed forward for each permille of feed commanded. */
#define STEAM_CONTROL_DECLARATION_FEED_LOAD_GAIN_WORD "feed-load-gain"

/* The duty fed forward for what the block gives up to the room, whatever else is happening. */
#define STEAM_CONTROL_DECLARATION_STANDING_LOAD_WORD "standing-load"

/*
 * The units a figure may be stated in.
 *
 * Every gain is in thousandths of a permille of heater scale per unit of the
 * error or the load it answers, rather than each gain choosing whichever
 * scaling happens to make its own figure a whole number. One rule across the
 * family is what lets a reader compare two of them without first working out
 * which scaling each was written at, and the price -- a proportional gain
 * spelled with six digits -- is paid once in the declaration rather than every
 * time somebody reads it.
 *
 * A unit the loader does not know is a unit nothing can range-check, and
 * writing the word out on every line is what lets a reader tell 900 milli-bar
 * from 900 of some other quantity without already knowing which field of the
 * record they are looking at.
 */
typedef enum {
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_BAR = 0,
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_C,
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_S,
    STEAM_CONTROL_DECLARATION_UNIT_PERMILLE,
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_K,
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_K_S,
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_BAR,
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_BAR_S,
    STEAM_CONTROL_DECLARATION_UNIT_MILLI_PERMILLE_PER_PERMILLE,
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
        "milli-bar", "milli-c", "milli-s", "permille", "milli-permille-per-k",                     \
            "milli-permille-per-k-s", "milli-permille-per-bar", "milli-permille-per-bar-s",        \
            "milli-permille-per-permille"                                                          \
    }

/* The longest a figure's name may be in a fault report, terminator included. */
#define STEAM_CONTROL_DECLARATION_NAME_MAX 48

/*
 * What the steam control law reads at initialisation.
 *
 * Pressures are gauge pressure in thousandths of a bar and temperatures are in
 * thousandths of a degree Celsius -- the units the hardware seam already
 * reports those channels in, so a reading compared against one of these
 * figures is an integer comparison and nothing is converted to decide where
 * the machine stands. The intervals are milliseconds, which is what the seam's
 * own clock counts in, for the same reason.
 *
 * The gains are in thousandths of a permille of heater scale per unit of what
 * they answer: per kelvin of temperature error, per kelvin-second of it, per
 * bar of pressure error, per bar-second of it, and per permille of commanded
 * feed. Every field is signed and the same width, so the loader can carry one
 * table of figures rather than a branch per field, and every range it admits
 * is a range on the same type.
 */
typedef struct {
    int32_t ready_pressure_milli_bar;
    int32_t ready_temperature_milli_c;
    int32_t draw_pressure_floor_milli_bar;
    int32_t draw_pressure_ceiling_milli_bar;
    int32_t margin_interval_millis;
    int32_t feed_rise_millis;
    int32_t sustainable_feed_permille;
    int32_t ready_gain_milli_permille_per_k;
    int32_t ready_integral_gain_milli_permille_per_k_s;
    int32_t draw_gain_milli_permille_per_bar;
    int32_t draw_integral_gain_milli_permille_per_bar_s;
    int32_t feed_load_gain_milli_permille_per_permille;
    int32_t standing_load_permille;
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
    STEAM_CONTROL_DECLARATION_ORIGIN,
    /*
     * The band's floor sits at or above its own ceiling, so the two figures
     * are individually admissible and jointly describe a band no pressure
     * could ever be inside. It is its own fault rather than an out-of-range
     * one because neither figure is out of range: what is wrong is the pair,
     * and a caller told one of them was out of range would go looking at the
     * wrong line.
     */
    STEAM_CONTROL_DECLARATION_BAND_INVERTED
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
 * Every figure the record carries is required. A declaration that leaves one
 * out is refused rather than defaulted: a gain silently taken as nothing is a
 * loop that does not track, and an interval silently taken as nothing is a
 * loop that starts making steam the instant the wand turns -- both of which
 * read as a machine that came up fine.
 *
 * Returns false, writing the fault into `error`, when the text or the record
 * is null, when a line cannot be read, when a figure is named twice or not at
 * all, when it is stated in the wrong unit, when it is outside the range this
 * build admits, when it is not accounted for, or when the band's two edges
 * describe no band. Returns false and writes nothing when `error` is null,
 * since a caller that cannot be told what was wrong must not be told the
 * declaration was fine.
 */
bool steam_control_declaration_load(const char *text, size_t length,
                                    steam_control_declaration_t *declaration,
                                    steam_control_declaration_error_t *error);

#endif /* STEAM_CONTROL_DECLARATION_H */
