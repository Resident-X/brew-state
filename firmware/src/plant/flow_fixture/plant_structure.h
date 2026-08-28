/*
 * A third structure, alongside `fixture`, that exists so a criterion needing a
 * real admission can be exercised end to end.
 *
 * `fixture` already proves that this project's two delivery points can be
 * declared on two separate heated masses -- see its own header -- but it
 * proves it structurally, by reading the mass table back through the seam.
 * The contention-serialisation slice claims something stronger: that a
 * demand for a point not sharing a mass with what is running is *admitted*
 * immediately, unaffected by any hold. Admission is asked of
 * `control_command_delivery_reporting`, which will not run at all against a
 * machine `control_init` refused to come up on, and `control_init` refuses
 * unless the structure it is brought up against answers a pump channel -- for
 * probe_full_scale_flow_ml_per_s to find a positive figure at -- and answers
 * the state its reachability check probes before it will reconstruct at all.
 * `fixture` answers neither, on purpose: its whole role in the suite beside
 * this one is to be the structure an unanswered-channel refusal and an
 * unreconstructable-state refusal can be shown to trigger against, and giving
 * it either would take that suite's subject away.
 *
 * So this is a second, separate structure rather than an extension of the
 * first. It describes no machine and carries no claim about one, on the same
 * terms `fixture` does; what it adds is just enough of the seam -- one pump
 * channel, and one accumulator answered under both names the estimator
 * reaches it by: the state `ESTIMATOR_STATE_BREW_TEMPERATURE_C` reconstructs,
 * which `control_init`'s reachability check probes before it will come up at
 * all, and the state its per-step correction writes -- for `control_init` to
 * come up and a real admission to be asked of it. Its two delivery points are
 * declared on two separate masses, on the same terms `fixture`'s are and for
 * the same reason: proving a demand at one is admitted while a delivery is
 * running at the other needs two points that do not share a mass to admit it
 * against.
 */
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H

#include "plant_machine_claim.h"
#include "plant_support.h"
#include "plant_types.h"

/*
 * These equations describe no machine, and neither coefficient they read has
 * physical meaning, so altering their arithmetic changes nothing about
 * anything physical -- on the same terms `fixture`'s do not, and for the same
 * reason. This structure is excluded from the mutation sweep's population by
 * declaring this the same way `fixture` does.
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
 * The brew heater and the pump, and neither steam channel. The pump is what
 * this structure exists to answer -- see the file comment above -- and the
 * brew heater comes with it so this structure has something for its one
 * accumulated state to mean, on the same terms `fixture`'s does. The two
 * steam channels are left unanswered so a build linking this structure could
 * still be a subject the seam's refusal of an unanswered channel is shown to
 * trigger against, though no suite currently asks that of this structure --
 * `fixture` remains the one which does.
 */
#define PLANT_STRUCTURE_ACTUATION_CHANNELS                                        \
    (ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER) |                       \
     ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_PUMP))

/*
 * Both points, backed by two distinct masses -- declared on the same terms
 * `fixture`'s are and for the same reason: proving a demand at one point is
 * admitted immediately while a delivery runs at the other needs two points
 * that do not share a mass to admit it against.
 */
#define PLANT_STRUCTURE_DELIVERY_POINTS                                          \
    (PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_GROUP) |                      \
     PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT))

/*
 * The two coefficients this structure reads. Neither means anything: the gain
 * scales an accumulator that stands for no physical quantity, and the pump
 * figure is read on the same terms the machine-describing structures' own
 * `pump.flow_ml_per_s` is -- what full pump scale yields -- so that
 * probe_full_scale_flow_ml_per_s finds a positive figure and control_init can
 * come up against this structure at all.
 */
typedef struct {
    float fixture_gain;
    float pump_flow_ml_per_s;
} plant_parameters_t;

/*
 * One accumulator, standing in for both temperatures this structure answers;
 * the flow the pump drew over the step just taken; and the record the model
 * was initialised from.
 *
 * The flow is not a state: nothing integrates it and nothing carries over
 * between steps, on the same terms `brew_flow_ml_per_s` is left out of the
 * machine-describing structures' own state vocabularies -- it is recomputed
 * whole every step from the commanded pump level, which is why it is reached
 * through plant_model_quantity rather than plant_model_state.
 */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;
    float accumulated;
    float brew_flow_ml_per_s;
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
 * Add what the brew heater commanded over `seconds`, scaled by the gain. This
 * is the whole of the structure's behaviour.
 */
void flow_fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation,
                             float seconds);

#endif /* PLANT_STRUCTURE_H */
