/*
 * A sixth structure, alongside `thermoblock`, `fixture`, `boiler`,
 * `flow_fixture` and `outlet_only_fixture`, built to carry exactly one shape: it answers a read
 * of both names the estimator reaches its one reconstructed value by -- the
 * state the reconstruction is held as, `PLANT_STATE_BREW_OUTLET_TEMPERATURE_C`,
 * and the state that value's correction is applied through,
 * `PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C` -- and refuses a *write* of the
 * second.
 *
 * `outlet_only_fixture` carries the shape one step earlier in the same path:
 * it refuses the correction-target state outright, on read as well as write,
 * which the admission check turns away on the first read it makes. That shape
 * is spoken for and this is not a second copy of it. A structure answering the
 * read and refusing the write passed that check cleanly for as long as it only
 * ever read, and then had every
 * correction against it dropped by `plant_model_set_state`'s own refusal one
 * call further down `correct_against` -- the identical externally observable
 * failure, reached one step later. This structure is the only thing in the
 * tree that can drive that case, which is what it exists for.
 *
 * The asymmetry runs the opposite way to the one every other structure's
 * `plant_model_set_state` warns against in comments beside its switch. Those
 * warn against answering a write under a name a read is refused for, which
 * would take a value and never give it back. This answers the read and
 * refuses the write, which takes nothing and reports success to nobody: the
 * correction is computed against a state that will not receive it. Both are
 * broken; only this one was ever admissible.
 *
 * It answers one actuation channel, borrowed from `fixture` rather than chosen
 * to mean anything, only because a structure answering none is refused as a
 * broken architecture before it ever reaches the admission this structure
 * exists to be refused by instead. It serves no delivery point: nothing past
 * admission is exercised against it, so proving the write is proved is what
 * this structure is for, and everything else the seam offers belongs to a
 * structure built to demonstrate it.
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
 * The brew heater, and nothing else -- the same one channel `fixture` and
 * `outlet_only_fixture` answer, and for the same reason: a structure
 * answering no channel at all responds to no command and has stated a broken
 * architecture rather than a narrow one, which is what
 * check_actuation_declaration.py refuses. Which channel is answered is not
 * what this structure exists to demonstrate, so it borrows theirs rather than
 * choosing a third.
 */
#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER)

/*
 * No delivery point at all. `control_init` never reaches delivery-point
 * declarations for a structure whose admission has already been refused, which
 * is what this structure is built to be refused by, so a point declared here
 * would be declared for nothing to ever read.
 */
#define PLANT_STRUCTURE_DELIVERY_POINTS ((plant_delivery_point_set_t)0u)

/*
 * The two coefficients this structure reads. The first seeds the one
 * accumulator this structure keeps, so admission's probes have a value to read
 * back before a single step has run; the second scales what the brew heater
 * commands into that same accumulator, on the same terms `fixture.gain` does,
 * so the one channel this structure answers is not declared and then left
 * inert.
 */
typedef struct {
    float outlet_value_c;
    float heater_gain;
} plant_parameters_t;

/* One accumulator, standing for both names this structure answers a read
 * under, and the record the model was initialised from. */
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
 */
const char *const *plant_structure_supply_driven_parameters(size_t *count);

/*
 * Add what the brew heater commanded over `seconds`, scaled by the gain, to
 * the one accumulator this structure keeps. This is the whole of the
 * structure's behaviour, declared here rather than kept `static` in the
 * translation unit so the symbol is visible to anything checking which
 * structure an artefact carries -- on the same terms `fixture_accumulate` is
 * declared for `fixture`.
 */
void correction_read_only_fixture_accumulate(plant_model_t *model,
                                             const plant_actuation_t *actuation, float seconds);

#endif /* PLANT_STRUCTURE_H */
