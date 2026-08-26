/*
 * How far a delivery may sit from what it was asked for, and from the same
 * delivery asked for at a better moment.
 *
 * This is a statement about the drink and not about the machine. What a
 * particular casting does when its element is switched on belongs in that
 * machine's description; how far the water may be from the temperature the
 * caller named before the cup is no longer the one that was ordered does not
 * change because the machine was built around a different block. So the band
 * lives here, declared once, rather than in a plant description -- three
 * structures each carrying a limits file would otherwise each declare a band,
 * and would be free to disagree about what the same drink demands.
 *
 * It carries a value, unlike the cadence declaration beside it. The distinction
 * is who reads the figure: a cadence figure is compiled into a loop that must
 * run at one rate on every machine, and its account exists so a reader can
 * challenge the number at its single site. A band is a criterion the control
 * suite holds trajectories against, and changing which trajectories are
 * acceptable should not require editing and recompiling a source file -- a
 * requirement expressed as a constant is one nobody can vary to find out what
 * the design actually costs.
 *
 * Nothing here names a plant structure or a control law. A band is what the
 * delivery has to achieve, and it has to outlive both the model the machine was
 * designed against and whatever loop was eventually built to deliver it.
 */
#ifndef DELIVERY_TOLERANCE_H
#define DELIVERY_TOLERANCE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "plant_origin.h"

/*
 * The name each band is written as in the declaration. A band is reached by
 * name rather than by position, so a declaration may state them in any order
 * and a band added later does not move the ones already there.
 *
 * A name does not spell the unit its band is stated in. The unit is written on
 * the line as its own word and checked against the one this build holds that
 * band in, so it has a single home that the loader actually reads. A unit
 * carried in the name would be a second statement of the same fact that no
 * check could enforce: renaming the band to say millilitres would go on being
 * read as whatever the record's field happened to be, and the declaration
 * would claim one unit while the software held deliveries to another.
 */
#define DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD "brew-temperature-band"

/*
 * How far the flow a delivery actually moves may sit from the rate its
 * profile is commanding before that gap is reported as departure rather than
 * absorbed. Declared for the same reason the temperature band is: what a
 * delivery is held to is a criterion the control suite tests trajectories
 * against, and a design that can only be loosened or tightened by editing and
 * recompiling a source file is one nobody varies to find out what it costs.
 */
#define DELIVERY_TOLERANCE_FLOW_DEPARTURE_WORD "flow-departure-band"

/*
 * How far a delivery asked for after a hot water draw may sit from the same
 * delivery asked for from rest.
 *
 * It is a statement about two drinks rather than about one: the band above says
 * how far a cup may be from the temperature that was ordered, and this says how
 * far two cups ordered the same way may be from each other. A machine can meet
 * the first and fail this -- two extractions at opposite edges of the
 * temperature band are each acceptable and are not the same drink -- which is
 * why it is its own figure rather than a reading of that one.
 *
 * Declared here beside the other two for the reason they are declared at all:
 * what a delivery is held to is the criterion trajectories are tested against,
 * and a design whose tolerance can only be varied by recompiling is one nobody
 * varies to find out what it costs.
 */
#define DELIVERY_TOLERANCE_POST_DRAW_MATCH_WORD "post-draw-match-band"

/*
 * The units a band may be stated in.
 *
 * Enumerated rather than free text for the reason the origin kinds are: a unit
 * the loader does not know is a unit nothing can range-check, and a band whose
 * quantity is unknown cannot be told apart from one whose figure is wrong. Each
 * band is held in exactly one of these, and a declaration stating it in another
 * is refused rather than read -- which is the whole point of writing the unit
 * down, since 200 is a reasonable band in thousandths of a millilitre per
 * second and an absurd one in millidegrees.
 */
typedef enum {
    DELIVERY_TOLERANCE_UNIT_MILLI_C = 0,      /* thousandths of a degree Celsius */
    DELIVERY_TOLERANCE_UNIT_MILLI_ML_PER_S,   /* thousandths of a millilitre per second */
    DELIVERY_TOLERANCE_UNIT_COUNT
} delivery_tolerance_unit_t;

/*
 * The word each unit is written as on a declaration line, in the order the
 * enumeration above declares them. Paired with that enumeration by a static
 * assertion in the loader, so a unit added without a word -- or a word left
 * behind by a unit removed -- fails the build rather than the declaration.
 */
#define DELIVERY_TOLERANCE_UNIT_WORDS                                                              \
    {                                                                                              \
        "milli-c", "milli-ml-s"                                                                    \
    }

/* The longest a band's name may be in a fault report, terminator included. */
#define DELIVERY_TOLERANCE_NAME_MAX 48

/*
 * The bands a delivery is held to.
 *
 * Every one of them is a half-width: the delivery is inside a band when the
 * quantity that band is about is no further than this from the figure it is
 * compared against, in either direction. They are symmetric because what the
 * drink is sensitive to is distance -- water above the commanded temperature
 * over-extracts and water below it under-extracts, and neither is the drink
 * that was ordered. An asymmetric band would be a claim that one direction is
 * more acceptable than the other, which is a claim nothing here has
 * established.
 *
 * What each band compares differs, and is stated on the field. The first two
 * hold a delivery against what it was commanded; the third holds one delivery
 * against another.
 */
typedef struct {
    int32_t brew_temperature_band_milli_c;
    /*
     * A half-width in thousandths of a millilitre per second, on the same
     * reasoning the temperature band above is symmetric: what the delivery is
     * held to is distance from the rate that was commanded, in either
     * direction, and nothing here has established that moving faster than
     * asked is more acceptable than moving slower.
     */
    int32_t flow_departure_band_milli_ml_per_s;
    /*
     * A half-width in thousandths of a degree Celsius, and the one band here
     * whose two sides are two deliveries rather than a delivery and a command:
     * a demand following a hot water draw is inside it when the water reaching
     * the coffee is no further than this from what the same demand from rest
     * would have received, in either direction. Symmetric on the same footing
     * the temperature band is -- a post-draw run above the rested one is as
     * much a different drink as one below it, and nothing here has established
     * otherwise.
     */
    int32_t post_draw_match_band_milli_c;
} delivery_tolerance_t;

/* Why a tolerance declaration was refused. */
typedef enum {
    /* Nothing was wrong; the record is populated. */
    DELIVERY_TOLERANCE_OK = 0,
    /* A line is not a comment, not blank, and not `name = value`. */
    DELIVERY_TOLERANCE_MALFORMED,
    /* A line names a band nothing in this build holds a delivery to. */
    DELIVERY_TOLERANCE_UNKNOWN,
    /* A band is given more than once, so which one applies is unclear. */
    DELIVERY_TOLERANCE_DUPLICATE,
    /*
     * A band is not a distance a delivery could be held to. The span that
     * settles this is stated per band rather than once for all of them,
     * because the bands are quantities of different kinds: what counts as an
     * absurdly wide temperature band is an unremarkable flow band written in
     * the same digits. One shared span could only ever be the loosest of them,
     * and would admit every figure the tighter band actually needed refusing.
     */
    DELIVERY_TOLERANCE_OUT_OF_RANGE,
    /*
     * A band this build holds a delivery to is declared nowhere. Its own fault
     * rather than a zero band, because a band of nothing is a band no machine
     * could ever meet, and defaulting to one would turn a file somebody forgot
     * to write into a requirement nothing can satisfy -- which reads as a
     * broken control law rather than as a missing declaration.
     */
    DELIVERY_TOLERANCE_MISSING,
    /*
     * A band carries no unit, a unit that is not one of the declared words, or
     * a unit that is not the one this build holds that band in.
     *
     * Separate from OUT_OF_RANGE because a figure of the wrong unit is not a
     * band that is too wide or too narrow -- it is a band measuring the wrong
     * quantity, and reporting it as a range fault would send a reader to
     * re-argue a value that was never the problem. Separate from MALFORMED for
     * the same reason ORIGIN is: the line reads perfectly well, and what is
     * wrong is what it claims.
     */
    DELIVERY_TOLERANCE_UNIT_MISMATCH,
    /*
     * A band carries no origin, a kind that is not one of the declared words,
     * or a kind with no account behind it.
     *
     * Separate from MALFORMED for the reason the parameter loader separates
     * them: this is the one fault whose subject is what the declaration claims
     * rather than whether it can be read, and the difference between "this file
     * is damaged" and "this figure is not accounted for" is repaired by
     * different people from different sources.
     */
    DELIVERY_TOLERANCE_ORIGIN
} delivery_tolerance_fault_t;

/*
 * What was wrong with a refused declaration. `line` is the one-based line the
 * fault was found on, and is zero for a band that is absent, which has no line
 * to point at.
 */
typedef struct {
    delivery_tolerance_fault_t fault;
    uint32_t line;
    char name[DELIVERY_TOLERANCE_NAME_MAX];
} delivery_tolerance_error_t;

/*
 * Read a tolerance declaration into the record above.
 *
 * The grammar is a band's name, an equals sign, a whole number, the word for
 * the unit that number is in, and the origin annotation every declared figure
 * in this project carries: a kind from the vocabulary in plant_origin.h and an
 * account of what the figure was arrived at from. All are required. A band with
 * a kind and no account can be neither reproduced nor challenged, which is the
 * state a load-bearing number is in just before everybody starts treating it as
 * settled; and a band with no unit is a number whose meaning rests on the
 * reader already knowing which quantity it measures.
 *
 * The unit is checked against the one this build holds that band in, and the
 * figure is range-checked as a quantity of that unit. A declaration whose bands
 * have been given each other's units is refused rather than read, so the file
 * cannot go on claiming one quantity while the record carries another.
 *
 * The record is assembled aside and copied out only once the whole declaration
 * is known to be admissible, so a refusal leaves the caller with what it had
 * rather than with some bands read and the rest left at whatever the memory
 * contained.
 *
 * Returns false, writing the fault into `error`, when the text or the record is
 * null, when a line cannot be read, when a band is named twice or not at all,
 * when a band is stated in the wrong unit, when a band is not a distance a
 * delivery could be held to, or when a band is not accounted for. Returns false
 * and writes nothing when `error` is null, since a caller that cannot be told
 * what was wrong must not be told the declaration was fine.
 */
bool delivery_tolerance_load(const char *text, size_t length, delivery_tolerance_t *tolerance,
                             delivery_tolerance_error_t *error);

#endif /* DELIVERY_TOLERANCE_H */
