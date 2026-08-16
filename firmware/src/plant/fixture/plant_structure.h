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

#include "plant_types.h"

/* The one coefficient this structure reads. It means nothing. */
typedef struct {
    double fixture_gain;
} plant_parameters_t;

/* One accumulator, and the record it was initialised from. */
typedef struct {
    bool initialised;
    plant_parameters_t parameters;
    double accumulated;
} plant_model_t;

/* The single coefficient this structure requires, and its admissible range. */
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);

/*
 * Add what the brew heater commanded over `seconds`, scaled by the gain. This
 * is the whole of the structure's behaviour.
 */
void fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation, double seconds);

#endif /* PLANT_STRUCTURE_H */
