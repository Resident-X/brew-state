/*
 * The machine's actuation channels, and the words for saying which of them a
 * thing answers.
 *
 * The channels belong to the machine rather than to either seam. The hardware
 * seam drives them and the plant model responds to them, so both need to name
 * the same set -- and a set named twice is a set that eventually disagrees with
 * itself. It is enumerated here, once, in a header neither seam owns, because a
 * shared vocabulary is what lets two seams speak about the same thing without
 * either depending on the other. That is the same reasoning that split
 * plant_types.h out of plant_model.h; this header goes one level further out,
 * because the set it carries is shared across the two seams rather than within
 * one of them.
 *
 * The channels are an enumeration with a terminating count rather than a set of
 * named fields, because everything this vocabulary exists for is addressing:
 * a structure has to state which channels it answers, a refusal has to name the
 * channel it refused, and a check has to name a channel a declaration claimed
 * that the machine does not have. None of those sentences can be written about
 * a struct member. Named fields read more pleasantly at a call site, and that
 * is the convenience being given up.
 *
 * Levels are parts per thousand of full scale. The scale is here rather than in
 * either seam for the same reason the channels are: a level means nothing
 * without it, so a seam holding its own copy would be holding half a
 * vocabulary.
 *
 * This header names no vendor type, declares no operation and holds no
 * equation, so a translation unit including it takes on nothing but the
 * vocabulary. Enlarging the set is a change to what the machine has, not a
 * change of spelling, and belongs with the work that gives the machine the
 * actuator.
 */
#ifndef MACHINE_ACTUATION_H
#define MACHINE_ACTUATION_H

#include <stdint.h>

/*
 * Every actuation channel the machine has. A structure of a given architecture
 * need not answer all of them -- which ones it does answer is something it
 * states, and is not a property of this set.
 */
typedef enum {
    ACTUATION_CHANNEL_BREW_HEATER = 0,
    ACTUATION_CHANNEL_STEAM_HEATER,
    ACTUATION_CHANNEL_PUMP,
    ACTUATION_CHANNEL_COUNT
} actuation_channel_t;

/* The largest level any channel accepts, in parts per thousand of full scale. */
#define ACTUATION_FULL_SCALE 1000u

/*
 * A set of channels, one bit per channel. This is how a structure states what
 * it answers: a set rather than a list, because the question asked of it is
 * always whether one channel is in it, and because a set cannot name the same
 * channel twice.
 */
typedef uint32_t actuation_channel_set_t;

/* The set containing one channel. */
#define ACTUATION_CHANNEL_BIT(channel) ((actuation_channel_set_t)1u << (unsigned)(channel))

#endif /* MACHINE_ACTUATION_H */
