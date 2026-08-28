#include "protection_margin.h"

#include <stddef.h>

#include "plant_model.h"

/*
 * How long a corner is allowed to carry the machine before the loop is taken to
 * have answered it, in milliseconds. It accounts for itself in
 * params/control.declaration beside the coefficients the loops rest on, on the
 * same terms every other figure the control logic carries does.
 *
 * It is not a coefficient of either control law -- nothing here is multiplied
 * by an error or added to a duty -- and it is not a property of any casting. It
 * is how long a load the loop was not told about goes unanswered, which is a
 * property of how fast the loop closes rather than of the machine it closes
 * around.
 */
#define PROTECTION_MARGIN_RESPONSE_INTERVAL_MS 17000u

/*
 * Whether a value is a number at all, written out rather than asked of the
 * standard library's isfinite for the reason control.c writes its own: this
 * translation unit is compiled byte-identically for the host and the target,
 * and that macro expands to a different implementation-reserved name on each.
 */
static bool is_a_number(float value)
{
    return (value == value) && ((value - value) == 0.0f);
}

/*
 * Where the protected quantity gets to when a machine holding the target is
 * left under the duty the loop commands for it, for as long as the loop takes
 * to answer a load nobody told it about.
 *
 * The model is stood at the target rather than at wherever a fresh instance
 * begins, because what is being measured is the departure a wrong coefficient
 * produces from where the loop believes it is holding -- not the approach to it.
 * A model left at rest would spend the whole interval climbing, and every
 * corner would come back reporting the climb rather than the error.
 *
 * One step of the whole interval rather than a sequence of short ones: the
 * structures behind this seam integrate an interval exactly, so a single call
 * lands where the machine actually gets to instead of accumulating an interval
 * of approximation.
 *
 * The draw is nothing. A margin is a standing property of a commanded target,
 * and the draw a delivery makes is the loop's own business on the step it makes
 * it; probing under one would size the margin for a delivery that may not be
 * the one commanded.
 */
static bool reached_under_the_holding_duty(const plant_parameters_t *machine,
                                           const protection_margin_probe_t *probe,
                                           float *reached_c)
{
    plant_model_t model;
    plant_actuation_t holding = {{0u}};

    if (!plant_model_init(&model, machine)) {
        return false;
    }

    /*
     * A state this structure does not keep is passed over rather than treated
     * as a failure: an architecture that heats the water where it delivers it
     * keeps nothing between the mass and what leaves it, and there is no such
     * state on it to stand anywhere. A structure that keeps none of the states
     * named at all is a different case and is refused below -- the probe would
     * then be measuring a machine climbing from wherever a fresh model begins,
     * which is not what any corner did.
     */
    size_t stood = 0u;
    for (size_t at = 0u; at < probe->held_count && at < (size_t)PROTECTION_MARGIN_STATE_LIMIT;
         at++) {
        if (plant_model_set_state(&model, probe->held_at_target[at], probe->target_c)) {
            stood++;
        }
    }
    if (stood == 0u) {
        return false;
    }

    holding.level_permille[probe->heater] = probe->holding_permille;
    if (!plant_model_step(&model, &holding, 0.0f, PROTECTION_MARGIN_RESPONSE_INTERVAL_MS)) {
        return false;
    }
    return plant_model_quantity(&model, probe->protects, reached_c);
}

/*
 * Whether the budget belongs to the structure this build compiled, and how many
 * coefficients that structure has.
 *
 * A budget of the wrong length is refused rather than read short. A record that
 * was never loaded is zeroed, and reading one would report the design as
 * assuming no error against anything -- a margin of nothing, sized off a
 * description nobody supplied, which is the most dangerous possible reading of
 * an absent one.
 */
static bool coefficients_of(const plant_parameter_budget_t *budget, size_t *count)
{
    bool driven = false;

    if (budget == NULL || budget->count == 0u || budget->count > PLANT_PARAMETER_LIMIT) {
        return false;
    }

    /*
     * The seam answers about a position the structure has and refuses one past
     * its last, so asking about the budget's own last position and about the
     * one after it establishes that this record was read against the structure
     * this build compiled -- without this file having to be told, or to work
     * out, how many coefficients that structure has.
     */
    if (!plant_parameter_supply_driven(budget->count - 1u, &driven) ||
        plant_parameter_supply_driven(budget->count, &driven)) {
        return false;
    }

    *count = budget->count;
    return true;
}

size_t protection_margin_corner_count(const plant_parameter_budget_t *budget)
{
    size_t count = 0u;

    if (!coefficients_of(budget, &count)) {
        return 0u;
    }
    return (2u * count) + 1u;
}

/*
 * The equal fractional sag every supply-driven coefficient admits, and how many
 * of them there are.
 *
 * A supply that sags moves every element on it by one fraction rather than each
 * to its own corner -- an element's power goes as the square of the voltage
 * across it, and there is one voltage -- so the corner is a single fraction
 * applied to all of them. The largest such fraction the description admits is
 * the smallest error declared against any of them; anything larger would carry
 * the tightest of them outside the range the description claims, which is the
 * one thing a corner drawn from a declared error must not do.
 *
 * A coefficient the description declares no error against is not in the corner
 * at all, and is not counted: a supply moves it, but the description says
 * nothing about how far, and inventing a figure for it would be this file
 * declaring an error the description did not.
 */
static bool joint_sag(const plant_parameter_budget_t *budget, size_t count, float *sag,
                      size_t *moves)
{
    *sag = 0.0f;
    *moves = 0u;

    for (size_t at = 0u; at < count; at++) {
        bool driven = false;

        if (!plant_parameter_supply_driven(at, &driven) || !driven || !budget->declared[at]) {
            continue;
        }
        if (*moves == 0u || budget->assumed_error[at] < *sag) {
            *sag = budget->assumed_error[at];
        }
        (*moves)++;
    }
    return *moves > 0u;
}

/*
 * Build the corner machine for one corner of the enumeration, writing every
 * coefficient it moves. Answers false where the structure refuses the result as
 * a machine, which is a corner that cannot be run rather than a fault.
 */
static bool corner_machine(const plant_parameters_t *believed,
                           const plant_parameter_budget_t *budget, size_t count,
                           const protection_margin_corner_t *corner, plant_parameters_t *machine)
{
    const float factor =
        corner->reaching_downwards ? (1.0f - corner->declared_error) : (1.0f + corner->declared_error);

    *machine = *believed;

    if (!corner->joint) {
        return plant_parameter_scale(machine, corner->at, factor);
    }

    for (size_t at = 0u; at < count; at++) {
        bool driven = false;

        if (!plant_parameter_supply_driven(at, &driven) || !driven || !budget->declared[at]) {
            continue;
        }
        if (!plant_parameter_scale(machine, at, factor)) {
            return false;
        }
    }
    return true;
}

/*
 * Fill a corner's descriptor fields -- everything protection_margin_corner_descriptor
 * answers -- leaving the probe-result fields at zero. `count` is the caller's
 * already-established coefficient count, so this never re-validates the
 * budget: both public entry points that reach it have already done that.
 */
static void corner_descriptor(const plant_parameter_budget_t *budget, size_t count, size_t which,
                              protection_margin_corner_t *corner)
{
    corner->at = count;
    corner->moves = 0u;
    corner->joint = (which == 2u * count);
    corner->reaching_downwards = corner->joint || ((which % 2u) == 0u);
    corner->declared_error = 0.0f;
    corner->ran = false;
    corner->reached_c = 0.0f;
    corner->contribution_c = 0.0f;

    if (corner->joint) {
        if (!joint_sag(budget, count, &corner->declared_error, &corner->moves)) {
            return;
        }
    } else {
        corner->at = which / 2u;
        corner->moves = 1u;
        if (!budget->declared[corner->at]) {
            corner->moves = 0u;
            return;
        }
        corner->declared_error = budget->assumed_error[corner->at];
    }

    if (!is_a_number(corner->declared_error) || !(corner->declared_error > 0.0f)) {
        /*
         * A coefficient the description declares exact has no corner: both ends
         * of an error of nothing are the machine itself, and running it would
         * be reporting the description's own figures as a corner of themselves.
         */
        corner->moves = 0u;
    }
}

bool protection_margin_corner_descriptor(const plant_parameter_budget_t *budget, size_t which,
                                         protection_margin_corner_t *corner)
{
    size_t count = 0u;

    if (corner == NULL || !coefficients_of(budget, &count)) {
        return false;
    }
    if (which >= (2u * count) + 1u) {
        return false;
    }

    corner_descriptor(budget, count, which, corner);
    return true;
}

bool protection_margin_corner_machine(const plant_parameters_t *believed,
                                      const plant_parameter_budget_t *budget,
                                      const protection_margin_corner_t *corner,
                                      plant_parameters_t *machine)
{
    size_t count = 0u;

    if (believed == NULL || corner == NULL || machine == NULL || !coefficients_of(budget, &count)) {
        return false;
    }
    return corner_machine(believed, budget, count, corner, machine);
}

bool protection_margin_corner(const plant_parameters_t *believed,
                              const plant_parameter_budget_t *budget,
                              const protection_margin_probe_t *probe, size_t which,
                              protection_margin_corner_t *corner)
{
    size_t count = 0u;

    if (believed == NULL || probe == NULL || corner == NULL || !coefficients_of(budget, &count)) {
        return false;
    }
    if (which >= (2u * count) + 1u) {
        return false;
    }

    corner_descriptor(budget, count, which, corner);
    if (corner->moves == 0u) {
        return true;
    }

    plant_parameters_t machine;
    if (!corner_machine(believed, budget, count, corner, &machine)) {
        return true;
    }

    float reached_c = 0.0f;
    float believed_c = 0.0f;
    if (!reached_under_the_holding_duty(&machine, probe, &reached_c) ||
        !reached_under_the_holding_duty(believed, probe, &believed_c)) {
        return true;
    }
    if (!is_a_number(reached_c) || !is_a_number(believed_c)) {
        return true;
    }

    corner->ran = true;
    corner->reached_c = reached_c;

    /*
     * Only the degrading direction, and clamped at nothing. A corner that
     * leaves the machine short of where the description says it would have been
     * has moved the gap the safe way, and a margin taking credit for it would be
     * a margin sized by the corner that did not happen.
     */
    const float degradation_c = reached_c - believed_c;
    corner->contribution_c = (degradation_c > 0.0f) ? degradation_c : 0.0f;
    return true;
}

bool protection_margin_widened(const plant_parameters_t *believed,
                               const plant_parameter_budget_t *budget,
                               const protection_margin_probe_t *probe,
                               protection_margin_t *margin)
{
    if (margin == NULL || probe == NULL) {
        return false;
    }

    const size_t corners = protection_margin_corner_count(budget);
    if (corners == 0u) {
        return false;
    }

    margin->unwidened_c = (probe->unwidened_c > 0.0f) ? probe->unwidened_c : 0.0f;
    margin->worst_corner_c = 0.0f;
    margin->margin_c = margin->unwidened_c;
    margin->corners = corners;
    margin->corners_run = 0u;
    margin->contributing = 0u;
    margin->worst_at = corners;
    margin->worst_is_joint = false;

    for (size_t which = 0u; which < corners; which++) {
        protection_margin_corner_t corner;

        if (!protection_margin_corner(believed, budget, probe, which, &corner)) {
            return false;
        }
        if (!corner.ran) {
            continue;
        }
        margin->corners_run++;
        if (!(corner.contribution_c > 0.0f)) {
            continue;
        }
        margin->contributing++;

        /*
         * The largest single corner, never the sum of them. Two coefficients
         * shifted to their own corners at once is a machine nothing states, and
         * a figure sized for it would be sized for a machine the description
         * does not claim; the one case where coefficients are stated to move
         * together is already an enumerated corner of its own, run with them
         * moving together, and it competes here on the same terms as any other.
         */
        if (corner.contribution_c > margin->worst_corner_c) {
            margin->worst_corner_c = corner.contribution_c;
            margin->worst_at = which;
            margin->worst_is_joint = corner.joint;
        }
    }

    margin->margin_c = margin->unwidened_c + margin->worst_corner_c;
    return true;
}
