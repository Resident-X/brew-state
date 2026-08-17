/*
 * A second structure that exists so the build's checks have something to fail
 * against.
 *
 * The exclusivity check -- that a linked artefact carries the symbols of one
 * structure and of no other -- and the build's refusal to compile two
 * structures at once both pass unconditionally while only one structure exists
 * in the tree, and a check that cannot fail is not a check. This structure is
 * the second subject that keeps them honest.
 *
 * It describes no machine and carries no claim about one. Its single
 * coefficient has no physical meaning, its one state is an accumulator, and it
 * is never compiled into a machine's artefact. Nothing here should be read as
 * an alternative architecture: the demonstration that a second real structure
 * can be added without disturbing existing structures or their consumers is a
 * separate piece of work.
 */
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H

#include "plant_support.h"
#include "plant_types.h"

/*
 * Unverified, and unverifiable: there is no hardware this structure could be
 * run against, because it describes none. It carries the status anyway, because
 * every structure answers the same question in the same words -- a structure
 * exempted from answering is a hole an arriving structure would fit through,
 * and "this one is different" is what every unverified structure would say.
 */
#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED

/*
 * The brew heater, and nothing else. This structure describes no machine, so it
 * is free to describe one with fewer actuators than the vocabulary carries --
 * and being narrower than the vocabulary is what makes it a subject the seam's
 * refusal of an unanswered channel can be shown to fail against. A structure
 * that answered everything could not trigger it, and a refusal nothing can
 * trigger is indistinguishable from not having one.
 */
#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER)

/* The one coefficient this structure reads. It means nothing. */
typedef struct {
    float fixture_gain;
} plant_parameters_t;

/* One accumulator, and the record it was initialised from. */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;
    float accumulated;
} plant_model_t;

/* The single coefficient this structure requires, and its admissible range. */
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);

/*
 * Add what the brew heater commanded over `seconds`, scaled by the gain. This
 * is the whole of the structure's behaviour.
 */
void fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation, float seconds);

#endif /* PLANT_STRUCTURE_H */
