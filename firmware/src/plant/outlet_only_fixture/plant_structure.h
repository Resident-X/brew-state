/*
 * A fifth structure, alongside `fixture`, `boiler` and `flow_fixture`, built
 * to carry exactly one shape: it keeps the state
 * `ESTIMATOR_STATE_BREW_TEMPERATURE_C` reconstructs -- the water on its way to
 * the group, which `estimator_init`'s reachability check probes before it will
 * admit a structure at all -- and refuses the state the estimator's per-step
 * correction writes toward for the same reconstructed value -- the mass being
 * heated, reached by the second hop of the same walk `correct_against` takes.
 *
 * `flow_fixture` answered both names from one accumulator specifically so
 * `control_init` could come up and a real admission be asked of the delivery
 * path; that shape is spoken for and this is not a second copy of it. This
 * structure's whole role is to be the one case the admission check itself
 * could not previously catch -- a structure control_init would have accepted
 * before its reachability check learned to ask the second name, and refuses
 * once it does. It answers one actuation channel, borrowed from `fixture`
 * rather than chosen to mean anything, only because a structure answering
 * none is refused as a broken architecture before it ever reaches the
 * admission this structure exists to be refused by instead. It serves no
 * delivery point: nothing past admission is exercised against it, so proving
 * the pairing check is what this structure is for, and everything else the
 * seam offers belongs to a structure built to demonstrate it.
 */
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H

#include "plant_machine_claim.h"
#include "plant_support.h"
#include "plant_types.h"

/*
 * These equations describe no machine, and the one coefficient below has no
 * physical meaning, on the same terms `fixture`'s do not. A mutation sweep
 * drawing a conclusion from arithmetic that stands for nothing physical would
 * report a number neither a survivor nor a kill is evidence of, so this
 * structure is excluded from the sweep's population the same way.
 */
#define PLANT_STRUCTURE_MACHINE_CLAIM PLANT_DESCRIBES_NO_MACHINE

/*
 * Unverified, and unverifiable: there is no hardware this structure could be
 * run against, because it describes none. Carried anyway, for the reason
 * every structure carries it: a structure exempted from answering would be a
 * hole an arriving structure fits through.
 */
#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED

/*
 * The brew heater, and nothing else -- the same one channel `fixture`
 * answers, and for the same reason: a structure answering no channel at all
 * responds to no command and has stated a broken architecture rather than a
 * narrow one, which is what check_actuation_declaration.py refuses. Which
 * channel is answered is not what this structure exists to demonstrate, so it
 * borrows `fixture`'s rather than choosing a second one.
 */
#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER)

/*
 * No delivery point at all. `control_init` never reaches delivery-point
 * declarations for a structure its own reconstruction check has already
 * refused, which is what this structure is built to be refused by, so a
 * point declared here would be declared for nothing to ever read.
 */
#define PLANT_STRUCTURE_DELIVERY_POINTS ((plant_delivery_point_set_t)0u)

/*
 * The two coefficients this structure reads. The first seeds the one state
 * this structure keeps, so admission's reachability probe has a value to read
 * back before a single step has run; the second scales what the brew heater
 * commands into that same accumulator, on the same terms `fixture.gain` does,
 * so the one channel this structure answers is not declared and then left
 * inert.
 */
typedef struct {
    float outlet_value_c;
    float heater_gain;
} plant_parameters_t;

/* One accumulator, standing for the one state this structure keeps, and the
 * record the model was initialised from. */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;
    float accumulated;
} plant_model_t;

/*
 * The two coefficients this structure requires, and the range each is
 * admissible over. `count` receives the number of entries; the returned table
 * outlives any call.
 */
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);

/*
 * The coefficients the supply this machine is fed from drives, by the names the
 * description calls them by. `count` receives the number of entries; the
 * returned table outlives any call.
 *
 * It is the one relationship between two of this structure's coefficients that
 * is stated anywhere, and it is stated here because a description's own grammar
 * has nowhere to put one: every line there accounts for a single number, and a
 * pair that moves together is a fact about two of them.
 */
const char *const *plant_structure_supply_driven_parameters(size_t *count);

/*
 * Add what the brew heater commanded over `seconds`, scaled by the gain, to
 * the one state this structure keeps. This is the whole of the structure's
 * behaviour, declared here rather than kept `static` in the translation unit
 * so the symbol is visible to anything checking which structure an artefact
 * carries -- on the same terms `fixture_accumulate` is declared for `fixture`.
 */
void outlet_only_fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation,
                                    float seconds);

#endif /* PLANT_STRUCTURE_H */
