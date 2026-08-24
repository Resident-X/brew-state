/*
 * How far a delivery may sit from the temperature it was asked for.
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
 */
#define DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD "brew-temperature-band-milli-c"

/*
 * How far the flow a delivery actually moves may sit from the rate its
 * profile is commanding before that gap is reported as departure rather than
 * absorbed. Declared for the same reason the temperature band is: what a
 * delivery is held to is a criterion the control suite tests trajectories
 * against, and a design that can only be loosened or tightened by editing and
 * recompiling a source file is one nobody varies to find out what it costs.
 */
#define DELIVERY_TOLERANCE_FLOW_DEPARTURE_WORD "flow-departure-band-milli-ml-s"

/* The longest a band's name may be in a fault report, terminator included. */
#define DELIVERY_TOLERANCE_NAME_MAX 48

/*
 * The bands a delivery is held to.
 *
 * A band is a half-width: the delivery is within it when the reconstructed
 * temperature is no further than this from the temperature commanded, in either
 * direction. It is symmetric because what the drink is sensitive to is distance
 * from the temperature that was asked for -- water above it over-extracts and
 * water below it under-extracts, and neither is the drink that was ordered.
 * An asymmetric band would be a claim that one of those is more acceptable than
 * the other, which is a claim nothing here has established.
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
     * A band is not a distance a delivery could be held to: nothing, negative,
     * or wider than the integer that carries it.
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
 * The grammar is a band's name, an equals sign, a whole number of millidegrees,
 * and the origin annotation every declared figure in this project carries: a
 * kind from the vocabulary in plant_origin.h and an account of what the figure
 * was arrived at from. Both are required. A band with a kind and no account can
 * be neither reproduced nor challenged, which is the state a load-bearing
 * number is in just before everybody starts treating it as settled.
 *
 * The record is assembled aside and copied out only once the whole declaration
 * is known to be admissible, so a refusal leaves the caller with what it had
 * rather than with some bands read and the rest left at whatever the memory
 * contained.
 *
 * Returns false, writing the fault into `error`, when the text or the record is
 * null, when a line cannot be read, when a band is named twice or not at all,
 * when a band is not a distance a delivery could be held to, or when a band is
 * not accounted for. Returns false and writes nothing when `error` is null,
 * since a caller that cannot be told what was wrong must not be told the
 * declaration was fine.
 */
bool delivery_tolerance_load(const char *text, size_t length, delivery_tolerance_t *tolerance,
                             delivery_tolerance_error_t *error);

#endif /* DELIVERY_TOLERANCE_H */
