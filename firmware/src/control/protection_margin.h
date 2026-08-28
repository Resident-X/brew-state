/*
 * The gap a commanded target has to keep from a hardware protection trip point,
 * sized against the error the machine's own description declares it may be
 * wrong by.
 *
 * A trip point is not something the software drives to and not something it can
 * negotiate with: it is a device that opens on the truth. What the design gets
 * to decide is how far below it a target is commanded, and that distance is the
 * commanded margin REQ-MEASUREMENT-001 names. Left at whatever gap the trip
 * point alone implies, that margin says only that the target is somewhere
 * below the trip point -- which is a statement about arithmetic and not about a
 * machine, because the machine the loop is driving is not the machine its model
 * describes, and how far the two may be apart is exactly what the description's
 * declared error says.
 *
 * So the margin is widened. Every coefficient the description declares an error
 * against is taken to its own corner, one coefficient at a time, and the
 * machine is asked -- through the plant seam and in the seam's own vocabulary
 * -- how far past where the loop believes it is holding that corner carries it
 * over the interval the loop takes to answer a load it was not told about. That
 * distance is what the corner costs the gap, and the margin has to cover it.
 *
 * The corners combine by worst case and not by summing: the figure is the
 * largest single-corner degradation across the whole enumeration, one corner
 * per coefficient run independently plus one corner per stated joint dependence
 * run together. Summing every coefficient's contribution at once would shift
 * every coefficient to its worst corner simultaneously where nothing states
 * they move together, and combining them in quadrature would give a tighter
 * figure than a simultaneous worst case can actually reach -- which is the one
 * failure a protection bound exists to rule out. Neither is what the corner
 * sweeps this project already runs do, and a second convention answering the
 * same question differently is worse than either.
 *
 * A corner is only ever counted in the degrading direction. A coefficient whose
 * corner carries the machine away from the trip point has made the gap safer,
 * and a margin that shrank on the strength of it would be a margin sized by the
 * good news; such a corner contributes nothing, so the widened margin is never
 * narrower than the un-widened gap it started from.
 *
 * A coefficient with no path to the protected quantity contributes nothing
 * either, and does so without being excluded by name: its corner moves the
 * machine nowhere the probe can see, so it has nothing to contribute through.
 * Nothing here carries a list of which coefficients matter, which is what lets
 * the same computation stand in front of a structure whose coefficients are not
 * these.
 *
 * Nothing here names a plant structure, a coefficient or a control law. The
 * quantity being protected, the channel that heats it, the target and the duty
 * the loop holds it at are all handed in by whichever loop is asking, so the
 * coffee side and the steam side get the same computation rather than two that
 * will eventually disagree.
 *
 * Sensing error is not part of this. What a sensor may be wrong by is the other
 * half of commanded margin and it is not carried here; a margin that folded the
 * two together would leave neither half separately answerable.
 */
#ifndef PROTECTION_MARGIN_H
#define PROTECTION_MARGIN_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "plant_model.h"

/*
 * The most states a probe stands at the temperature the loop is holding before
 * it lets the corner machine run.
 *
 * Two, because the widest case here is a structure that keeps the heated mass
 * and the water on its way out of it apart: both have to start where the loop
 * believes the machine is, or the probe measures the two closing on each other
 * rather than what the corner did. A structure keeping one of them keeps fewer,
 * and one keeping neither cannot be probed at all -- which is answered by the
 * probe refusing rather than by this figure.
 */
#define PROTECTION_MARGIN_STATE_LIMIT 2u

/*
 * What a loop is asking about: the quantity its trip point protects, the
 * machine it is holding, and where it believes it is holding it.
 *
 * `protects` is the quantity the trip point is a limit on, and `heater` the
 * channel that drives it. `held_at_target` names the states a machine holding
 * that target has standing at it, so a corner starts from where the loop
 * believes the machine is rather than from wherever a fresh model happens to
 * begin; a structure that refuses one of them is one this cannot be probed on,
 * and says so rather than being probed from the wrong place.
 *
 * `holding_permille` is the duty the loop commands to hold `target_c` on the
 * machine it believes in. It is handed in rather than worked out here because
 * it is a property of the control law asking -- its own feedforward, its own
 * standing load -- and not of the description.
 *
 * `unwidened_c` is the gap the trip point alone implies: how far below the trip
 * point a target has to sit before any declared error is considered at all.
 * Handed in for the same reason, because what a delivery is allowed to do
 * around its command is a statement each loop makes for itself.
 */
typedef struct {
    plant_quantity_t protects;
    actuation_channel_t heater;
    plant_state_t held_at_target[PROTECTION_MARGIN_STATE_LIMIT];
    size_t held_count;
    float target_c;
    uint16_t holding_permille;
    float unwidened_c;
} protection_margin_probe_t;

/*
 * One enumerated corner, and what it cost the gap.
 *
 * `at` is the coefficient's position in the structure's own ordering -- the
 * ordering the budget record is indexed by -- and is meaningless for the joint
 * corner, which moves more than one. `moves` is how many coefficients the
 * corner writes, so a reader can tell an independent corner from a joint one
 * without reading `joint` and can tell a joint corner that found one
 * supply-driven coefficient from one that found two.
 *
 * `reaching_downwards` says which end of the declared error the corner is: a
 * coefficient written at one less its declared fraction, or at one plus it. The
 * joint corner is always downwards, because a supply sags and nothing states a
 * cause that would raise two elements at once.
 *
 * `ran` is false for a corner there was nothing to run: a coefficient the
 * description declares no error against, a corner the structure refuses as a
 * machine, or a probe the structure could not answer. Such a corner contributes
 * nothing, and that is reported as not having run rather than as a contribution
 * of nothing -- the two are different findings and only one of them is about
 * the machine.
 *
 * `reached_c` is where the protected quantity got to under the corner and is
 * meaningful only while `ran` is set. `contribution_c` is what the corner cost
 * the gap: how much further toward the trip point it carried the machine than
 * the description's own figures did, clamped at nothing.
 */
typedef struct {
    size_t at;
    size_t moves;
    bool joint;
    bool reaching_downwards;
    float declared_error;
    bool ran;
    float reached_c;
    float contribution_c;
} protection_margin_corner_t;

/*
 * The margin a loop is to command within, and the enumeration it came out of.
 *
 * `margin_c` is `unwidened_c` plus `worst_corner_c`, and is the whole of what a
 * loop enforces. The rest is the account: how many corners the enumeration
 * covers, how many of them were runnable, how many actually cost the gap
 * anything, and which one was worst. A margin figure with no account behind it
 * is a number nobody can challenge, which is the state a load-bearing figure is
 * in just before everybody treats it as settled.
 */
typedef struct {
    float unwidened_c;
    float worst_corner_c;
    float margin_c;
    size_t corners;
    size_t corners_run;
    size_t contributing;
    size_t worst_at;
    bool worst_is_joint;
} protection_margin_t;

/*
 * How many corners the enumeration covers for a budget.
 *
 * Two per coefficient the structure declares -- each end of whatever error the
 * description carries against it -- and one more for the joint dependence.
 * Every coefficient is counted whether the description declares an error
 * against it or not, so that a corner's position in the enumeration is fixed by
 * the structure rather than by which lines a particular description happened to
 * annotate: a corner index means the same coefficient and the same end of it
 * whichever description is loaded, and one that had nothing to run says so.
 *
 * Both ends are run even for a coefficient the description's own prose calls
 * one-sided. The description's grammar carries no such statement -- a fraction
 * against a value is symmetric -- so nothing here could read it, and running
 * the end the description does not claim can only widen the margin. That is the
 * safe direction of error for a protection bound, and it is why this does not
 * quietly narrow a margin on a claim it cannot see.
 *
 * Returns 0 for a null budget or one that describes no coefficients, which is a
 * budget nothing can be enumerated over.
 */
size_t protection_margin_corner_count(const plant_parameter_budget_t *budget);

/*
 * The corner descriptor for corner `which` alone: which coefficient it moves
 * (or, for the joint corner, how many), which end of the declared error, and
 * the fraction. Written apart from protection_margin_corner below so a caller
 * that wants the degraded machine a corner describes, but not this file's own
 * probe of it, can ask for one without this file assuming the caller's probe
 * shape -- the authority bound in control.c is such a caller: it has its own
 * question to put to the degraded machine and no standing duty to hold it at.
 *
 * `moves` comes back 0 for a corner with nothing to run: a coefficient the
 * description declares no error against, or declares an error of nothing
 * against. `ran`, `reached_c` and `contribution_c` are left at their zero
 * values -- this call runs no probe, so no probe result exists to fill them
 * with; a caller wanting those runs protection_margin_corner instead.
 *
 * Returns false, writing nothing, for a null argument, for a corner index at
 * or past the count above, or for a budget whose coefficient count does not
 * match the structure this build compiled.
 */
bool protection_margin_corner_descriptor(const plant_parameter_budget_t *budget, size_t which,
                                         protection_margin_corner_t *corner);

/*
 * The degraded plant_parameters_t a described corner builds: the believed
 * parameters with every coefficient the corner moves written at its corner
 * value through the plant seam. A corner with `moves` at 0 comes back as the
 * believed parameters unchanged in the ordinary case -- an undeclared
 * coefficient's corner has nothing to scale -- but not in every case a
 * caller could construct one: a hand-built corner with `moves` left at 0 and
 * a declared_error the plant seam refuses (not-a-number, say) is not
 * distinguished from the ordinary one and still reaches the seam's own
 * range check below, on the same terms an inadmissible corner from
 * protection_margin_corner_descriptor above does.
 *
 * Returns false for a null argument, for a budget whose coefficient count
 * does not match the structure this build compiled, or for a corner the
 * structure will not admit as a machine -- the same range check a
 * description is built against. `machine` is left holding the believed
 * parameters, not untouched, when a scale past the first fails: the corner
 * is written coefficient by coefficient and only the whole result is the
 * caller's to trust, so a false return is the signal to read, not the
 * partial machine.
 */
bool protection_margin_corner_machine(const plant_parameters_t *believed,
                                      const plant_parameter_budget_t *budget,
                                      const protection_margin_corner_t *corner,
                                      plant_parameters_t *machine);

/*
 * Run one corner of that enumeration and report what it cost the gap.
 *
 * The corner is built by writing the description's own coefficients at their
 * corner values through the plant seam and standing a model up from the result,
 * so a corner the structure will not admit as a machine is refused by the same
 * range check a description is, and comes back as a corner that did not run.
 *
 * Returns false, writing nothing, for a null argument, for a corner index at or
 * past the count above, or for a budget whose coefficient count does not match
 * the structure this build compiled. Everything else -- a coefficient carrying
 * no declared error, a corner outside the admissible range, a structure that
 * cannot answer the probe -- is a corner that ran nothing rather than a
 * refusal, because those are findings about the description and the caller has
 * to be able to record them.
 */
bool protection_margin_corner(const plant_parameters_t *believed,
                              const plant_parameter_budget_t *budget,
                              const protection_margin_probe_t *probe, size_t which,
                              protection_margin_corner_t *corner);

/*
 * The widened margin: the un-widened gap plus the largest single-corner
 * degradation across the whole enumeration.
 *
 * Written in terms of protection_margin_corner above rather than beside it, so
 * the figure a loop enforces and the record a reader inspects come out of one
 * enumeration. Two enumerations would eventually disagree, and the disagreement
 * would be invisible: the record would go on describing corners the margin was
 * not actually taken over.
 *
 * Returns false, writing nothing, for a null argument or a budget that does not
 * belong to the structure this build compiled. A budget that declares no error
 * against anything is not a refusal: it produces a margin of exactly the
 * un-widened gap, which is the honest answer for a description that claims to
 * be exact.
 */
bool protection_margin_widened(const plant_parameters_t *believed,
                               const plant_parameter_budget_t *budget,
                               const protection_margin_probe_t *probe,
                               protection_margin_t *margin);

#endif /* PROTECTION_MARGIN_H */
