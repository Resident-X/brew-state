#include "steam_control.h"

#include <stddef.h>

#include "hw_interface.h"
#include "plant_model.h"
#include "protection_margin.h"

/*
 * No figure the law rests on is written in this file. Every gain, every
 * interval, the band and the rates all arrive in the declaration record --
 * which is why there is no block of coefficients here of the kind control.c
 * carries at the top of itself, and why nothing here accounts for itself in
 * params/control.declaration. What that file accounts for on this side is the
 * spans the grammar reading those figures will admit, which live beside the
 * grammar in src/delivery.
 *
 * Thousandths are what both the hardware seam and the declaration read in, so
 * every conversion below divides by a thousand, written out at each site
 * rather than named once. That follows control.c, which writes its own the
 * same way: a name defined here would be a second home for the unit the
 * estimator beside it already spells, and the check that keeps a figure to one
 * home would then be asking which of the two the machine ran on.
 *
 * Two figures are the exception and neither is a figure of the law. The steam
 * block carries a protective device, and where that device opens is a property
 * of the machine rather than of any declaration a caller writes; what this
 * channel's own sensor may be wrong by is a property of the same kind, of the
 * sensor rather than of the control policy. Both are declared here, once, and
 * account for themselves in params/control.declaration beside the coffee
 * side's own.
 */

/*
 * The temperature at which the hardware protection fitted to the steam block
 * removes power from its element, in degrees Celsius.
 *
 * Declared on this side of the plant seam for the reason the coffee side's own
 * trip point is: the structures behind that seam model no protective device
 * and will run a block straight past this figure, so nothing can be asked of
 * them about it. It is the earliest the fitted device may open rather than its
 * nominal point, on the same reasoning -- a margin exists to survive a trip
 * that comes early, and sizing against nominal would leave it short by the
 * device's own tolerance.
 */
#define STEAM_CONTROL_PROTECTION_TRIP_C 195.0f

/*
 * How far the steam channel's own reading may be wrong by, in degrees Celsius,
 * carried into the commanded margin per DEC-SENSING-ERROR-ADDS-TO-COMMANDED-MARGIN.
 *
 * On the same footing CONTROL_SENSING_ERROR_C in control.c is: no
 * temperature-sensing part has been selected for this channel, and
 * REQ-MEASUREMENT-001 leaves sensor choice an open, cost-driven decision. The
 * figure is estimated at the accuracy class a domestic thermoblock machine's
 * block-mounted sensor ordinarily carries in the wider span this channel works
 * across -- an NTC thermistor read up toward the steam block's working
 * temperature -- rather than read off a fitted part's datasheet. A bench
 * characterisation of the part actually fitted, or a decision settling which
 * sensor this design specifies, displaces this figure with a measured or
 * documented one.
 */
#define STEAM_CONTROL_SENSING_ERROR_C 2.0f


/*
 * Whether a value is a number at all -- neither a not-a-number nor an
 * unbounded one.
 *
 * Written out rather than asked of the standard library's isfinite, which is a
 * macro that expands to a different implementation-reserved name on a host and
 * on the target. This file is compiled byte-identically across the two and a
 * check run as part of the build compares them, so a macro that expands
 * differently is a difference in the control logic however identical the
 * source reads -- the same reasoning control.c's own is_a_temperature carries,
 * and the same reliance on no environment here passing -ffinite-math-only,
 * under which both comparisons would be licensed to fold to true and the
 * refusal would disappear without a diagnostic.
 *
 * Nothing this loop presently reads can reach it. Every error it judges is
 * built from range-checked declaration fields and from readings the seam
 * carries as whole thousandths, so all of them are finite by construction and
 * no test can drive this branch. It is kept on the same terms control.c keeps
 * the negated comparison in its own as_drive_level: the guard costs a branch
 * and removes the whole class, so a later figure arriving as a float, or a
 * quantity read through the plant seam, cannot reintroduce it quietly.
 */
static bool is_a_figure(float value)
{
    return (value == value) && ((value - value) == 0.0f);
}

/*
 * The lesser and the greater of two figures, written out rather than asked of
 * the standard library for the reason is_a_figure above is: this file is
 * compiled byte-identically across the host and the target, and a library call
 * is a different symbol on each.
 */
static float lesser(float a, float b)
{
    return (b < a) ? b : a;
}

static float greater(float a, float b)
{
    return (b > a) ? b : a;
}

/* Narrow a command in permille to what the actuator can be given. */
static uint16_t as_drive_level(float permille)
{
    /*
     * Written as a negated comparison so that a command that is not a number
     * lands at nothing rather than somewhere in range, on the same terms
     * control.c's own as_drive_level is written.
     */
    if (!(permille > 0.0f)) {
        return 0u;
    }
    if (permille >= (float)ACTUATION_FULL_SCALE) {
        return (uint16_t)ACTUATION_FULL_SCALE;
    }

    /* In range by construction, and positive, so the rounding needs no branch. */
    return (uint16_t)(permille + 0.5f);
}

/*
 * Whether a reading of `channel` can be believed, and what it says.
 *
 * Trustworthy on the same terms judge_the_interval_just_elapsed in control.c
 * already asks of a flow reading: obtained, and inside the span this
 * instance's own declared bounds admit for the channel. A reading outside that
 * span is arithmetically fine and physically absurd, and acting on one would
 * be answering a question about a machine no sensor is actually describing.
 */
static bool trustworthy(const steam_control_state_t *state, hw_sensor_channel_t channel,
                        int32_t *value_milli)
{
    const hw_reading_t reading = hw_sensor_read(channel);

    if (reading.status != HW_READING_VALID ||
        reading.value_milli < state->limits.low_milli[channel] ||
        reading.value_milli > state->limits.high_milli[channel]) {
        return false;
    }

    *value_milli = reading.value_milli;
    return true;
}

/*
 * Take a fresh reading of a channel if there is one to be had, and answer with
 * what the loop presently believes about it.
 *
 * A reading that cannot be believed leaves the remembered value exactly where
 * it was: the criterion this answers is that an implausible reading is
 * rejected rather than acted on, and acting on one includes reacting to it by
 * abandoning what was last established. A channel nothing has ever been
 * trusted on stays untrusted, which is a different condition from a stale
 * value and is the one the caller has to refuse to drive on.
 */
static bool believed(bool *trusted, int32_t *remembered, const steam_control_state_t *state,
                     hw_sensor_channel_t channel, bool *fresh)
{
    int32_t sampled = 0;

    *fresh = trustworthy(state, channel, &sampled);
    if (*fresh) {
        *trusted = true;
        *remembered = sampled;
    }
    return *trusted;
}

/*
 * Whether the wand's microswitch says a draw has begun.
 *
 * Three conditions read as no draw and they are deliberately not distinguished
 * here: nothing fitted to the channel, a sample that could not be trusted, and
 * a reading that is neither of the two answers a discrete channel is entitled
 * to give. In every one of them the loop has no evidence a draw is under way,
 * and holding the machine at ready is the softer failure -- an operator who
 * opens the wand against a loop that was never told gets a draw the block's
 * standing margin supplies and no feed behind it, which is unmistakably weak
 * rather than steam that starts acceptable and degrades.
 *
 * The middle value is refused rather than rounded to whichever answer is
 * nearer. A contact is made or it is not, and an implementation reporting
 * something between the two has not answered the question this channel exists
 * to answer; taking a half-made contact for a turned knob would start feeding
 * a block on the strength of a reading no implementation of this seam is
 * entitled to produce.
 */
static bool a_draw_is_under_way(const steam_control_state_t *state)
{
    int32_t knob_milli = 0;

    if (!trustworthy(state, HW_SENSOR_STEAM_KNOB, &knob_milli)) {
        return false;
    }
    return knob_milli == HW_READING_DISCRETE_SET;
}

/*
 * The level the feed pump is commanded at on one step of a fed draw, and the
 * accumulated intent it leaves behind.
 *
 * On the step the wand opens the level is the declared draw-start feed, bounded
 * by the ceiling, whatever the pressure reads: the reading on that step is the
 * shut block's, which says nothing about the drop the orifice will carry once
 * steam is made, and acting on it would cut the very feed a draw opened at ready
 * needs. From then on the level is the start level plus a proportional and an
 * integral answer to the pressure's distance from the middle of the declared
 * band -- the middle rather than either edge, so the loop has equal room either
 * side of it. The middle is derived here rather than declared beside the edges
 * because it is not a third choice anybody makes.
 *
 * Above the start level the level may rise no faster than the declared limit,
 * taken against the unrounded level last issued, and it is never carried past
 * the ceiling. Below the start level nothing limits how fast it falls or comes
 * back: the limit exists to keep the load the heater has to answer from growing
 * faster than it can, and a level under the start is a load the loop began a
 * draw with.
 *
 * Integration is made conditional on the actuator, on the terms heater_command
 * below states for itself: it is withheld while the level is held at the ceiling
 * or by the rise limit with the error asking for more, and while it is held at
 * nothing with the error asking for less.
 */
static uint16_t feed_command(steam_control_state_t *state, float error, float interval_s,
                             bool opening, bool heat_spent)
{
    const float start_permille = (float)state->declaration.draw_start_feed_permille;
    const float ceiling_permille = (float)state->declaration.feed_ceiling_permille;

    if (opening) {
        state->feed_level_permille = start_permille;
        return as_drive_level(state->feed_level_permille);
    }

    const float gain = (float)state->declaration.feed_gain_milli_permille_per_bar / 1000.0f;
    const float integral_gain =
        (float)state->declaration.feed_integral_gain_milli_permille_per_bar_s / 1000.0f;
    const float rise_bound =
        greater(state->feed_level_permille, start_permille) +
        (float)state->declaration.feed_rise_limit_permille_per_s * interval_s;
    /*
     * An element already at full that is losing the superheat cannot be helped
     * by more water: the feed is let down at the declared rise limit until the
     * heater can hold it again, so quantity yields before quality does.
     */
    const float bound =
        heat_spent ? lesser(lesser(rise_bound, ceiling_permille),
                            state->feed_level_permille -
                                (float)state->declaration.feed_rise_limit_permille_per_s *
                                    interval_s)
                   : lesser(rise_bound, ceiling_permille);

    const float asked = start_permille + (gain * error) + state->feed_integral_permille;
    const bool pushing_past_bound = (asked >= bound) && (error > 0.0f);
    const bool pushing_past_off = (asked <= 0.0f) && (error < 0.0f);

    if (!pushing_past_bound && !pushing_past_off) {
        state->feed_integral_permille += integral_gain * error * interval_s;
    }

    const float issued =
        greater(lesser(start_permille + (gain * error) + state->feed_integral_permille, bound),
              0.0f);
    state->feed_level_permille = issued;
    return as_drive_level(issued);
}

/*
 * The heater command for one step, and the accumulated intent it leaves behind
 * in whichever integral the phase in force owns.
 *
 * The feedforward term is added before the loop looks at the error rather than
 * after, for the reason control.c's own heater_command adds its own first: it
 * answers a load the machine has been told about. The feed level is what this
 * same step just decided to command, and the energy the water it pushes in
 * will take to reach saturation and turn is known at that moment rather than
 * discovered once the outlet has gone wet.
 *
 * The standing loss is fed forward as well, and as a flat duty rather than as
 * a figure per kelvin of rise -- which is where this parts company with the
 * brew loop, whose own standing term follows the target a caller names. This
 * loop's casting moves only a few kelvin either side of its ready target, and
 * over that span the block's standing load barely changes. See standing-load's
 * own account in params/steam_control.declaration.
 *
 * The error is taken against whichever variable the heater holds -- the
 * casting's temperature while idle, the outlet superheat while a draw is fed --
 * each in kelvin and each with gains of its own. Pressure is never an error
 * here: during a draw it is the feed's to hold.
 *
 * Integration is made conditional on the actuator rather than unwound after
 * the fact, on exactly the terms control.c's own loop is and for the same
 * reason: intent accumulated across the limit would arrive as an overshoot once
 * the demand ended, long after the interval that produced it. The condition is
 * asked of the command this step would issue.
 */
static float heater_command(steam_control_state_t *state, float error, float interval_s,
                            uint16_t feed_permille, bool superheat)
{
    const float gain =
        superheat ? (float)state->declaration.superheat_gain_milli_permille_per_k
                  : (float)state->declaration.ready_gain_milli_permille_per_k;
    const float integral_gain =
        superheat ? (float)state->declaration.superheat_integral_gain_milli_permille_per_k_s
                  : (float)state->declaration.ready_integral_gain_milli_permille_per_k_s;
    const float feed_load_gain =
        (float)state->declaration.feed_load_gain_milli_permille_per_permille;
    float *const integral =
        superheat ? &state->superheat_integral_permille : &state->integral_permille;

    const float proportional = (gain / 1000.0f) * error;
    const float feedforward = (float)state->declaration.standing_load_permille +
                              ((feed_load_gain / 1000.0f) * (float)feed_permille);

    const float issued = proportional + *integral + feedforward;
    const bool pushing_past_full = (issued >= (float)ACTUATION_FULL_SCALE) && (error > 0.0f);
    const bool pushing_past_off = (issued <= 0.0f) && (error < 0.0f);

    if (!pushing_past_full && !pushing_past_off) {
        *integral += (integral_gain / 1000.0f) * error * interval_s;
    }

    return proportional + *integral + feedforward;
}

/*
 * Command both steam channels off, recording what the interface accepted
 * rather than what was asked for: if an off command is itself refused, that
 * channel is still at its previous level, and recording nothing would state it
 * is off when nothing established that. The same convention control.c's own
 * command_everything_off keeps.
 */
static bool command_everything_off(steam_control_state_t *state)
{
    const bool heater_off = hw_output_set(ACTUATION_CHANNEL_STEAM_HEATER, 0u);
    if (heater_off) {
        state->heater_permille = 0u;
    }

    const bool feed_off = hw_output_set(ACTUATION_CHANNEL_STEAM_PUMP, 0u);
    if (feed_off) {
        state->feed_permille = 0u;
    }

    return heater_off && feed_off;
}

/*
 * The margin this loop requires between the ready target a declaration names
 * and the steam block's own trip point, and the enumeration it came out of.
 *
 * The duty handed to the probe is the standing load the declaration itself
 * carries: it is what this loop commands to hold the ready target with nothing
 * being drawn, which is the duty a wrong coefficient actually acts through. The
 * feed-load term is left out for the reason the coffee side leaves its own
 * drawn load out -- a margin is a standing property of a commanded target, and
 * what a draw costs is answered on the step the draw is made.
 *
 * The un-widened gap is nothing. This loop's ready phase holds a temperature
 * against no declared temperature band at all -- the band it is held to is a
 * pressure one, held with the wand open by the feed rather than by the casting
 * -- so what the trip point alone implies here is only that the target sit
 * below it. Every kelvin of the model-error half of the margin is therefore
 * earned by declared model error rather than inherited, which is a narrower
 * claim than the coffee side's and an honest one. STEAM_CONTROL_SENSING_ERROR_C
 * is added on top of that per DEC-SENSING-ERROR-ADDS-TO-COMMANDED-MARGIN, on
 * the same terms the coffee side's own sensing error is.
 */
static void steam_margin_probe(const steam_control_declaration_t *declaration,
                               protection_margin_probe_t *probe)
{
    probe->protects = PLANT_QUANTITY_STEAM_TEMPERATURE_C;
    probe->heater = ACTUATION_CHANNEL_STEAM_HEATER;
    probe->held_at_target[0] = PLANT_STATE_STEAM_TEMPERATURE_C;
    probe->held_at_target[1] = PLANT_STATE_STEAM_TEMPERATURE_C;
    probe->held_count = 1u;
    probe->target_c = (float)declaration->ready_temperature_milli_c / 1000.0f;
    probe->holding_permille = as_drive_level((float)declaration->standing_load_permille);
    probe->unwidened_c = 0.0f;
}

static bool steam_widened_margin(const steam_control_declaration_t *declaration,
                                 const plant_parameters_t *parameters,
                                 const plant_parameter_budget_t *budget,
                                 protection_margin_t *margin)
{
    protection_margin_probe_t probe;

    steam_margin_probe(declaration, &probe);
    return protection_margin_widened(parameters, budget, &probe, STEAM_CONTROL_SENSING_ERROR_C,
                                     margin);
}

/*
 * The coefficient whose declared error this loop's superheat estimate reads,
 * which the budget must declare for the estimate to carry the allowance it
 * claims.
 */
#define STEAM_ESTIMATE_PARAMETER "steam.outlet_drop_k_s_per_ml"

bool steam_control_description_established(const steam_control_declaration_t *declaration,
                                           const plant_parameters_t *parameters,
                                           const plant_parameter_budget_t *budget,
                                           plant_parameter_error_t *refusal)
{
    protection_margin_probe_t probe;
    protection_margin_t margin;

    if (declaration == NULL) {
        return false;
    }
    steam_margin_probe(declaration, &probe);
    return protection_margin_established(parameters, budget, &probe, STEAM_CONTROL_SENSING_ERROR_C,
                                         STEAM_ESTIMATE_PARAMETER, refusal, &margin);
}

/*
 * Whether the description and budget this loop is given establish a margin, and
 * a declared ready target leaves it between itself and the steam block's trip
 * point.
 *
 * The margin is established under the one precondition every law holds its
 * inputs to (protection_margin_established): a believed description the plant
 * refuses to build a model from, a budget leaving undeclared the coefficient
 * this loop's superheat estimate reads, and a declared-error corner no machine
 * can be built for each refuse the loop rather than being read as a smaller
 * margin. A target sitting exactly at the edge keeps exactly the margin asked
 * for and is admitted.
 */
static bool ready_target_clears_the_protection_margin(const steam_control_declaration_t *declaration,
                                                      const plant_parameters_t *parameters,
                                                      const plant_parameter_budget_t *budget)
{
    protection_margin_probe_t probe;
    protection_margin_t margin;

    steam_margin_probe(declaration, &probe);
    if (!protection_margin_established(parameters, budget, &probe, STEAM_CONTROL_SENSING_ERROR_C,
                                       STEAM_ESTIMATE_PARAMETER, NULL, &margin)) {
        return false;
    }

    return probe.target_c <= (STEAM_CONTROL_PROTECTION_TRIP_C - margin.margin_c);
}

bool steam_control_protection_margin(const steam_control_state_t *state,
                                     protection_margin_t *margin)
{
    if (state == NULL || margin == NULL || !state->configured) {
        return false;
    }

    return steam_widened_margin(&state->declaration, &state->parameters, &state->budget, margin);
}

bool steam_control_protection_margin_corner(const steam_control_state_t *state, size_t which,
                                            protection_margin_corner_t *corner)
{
    if (state == NULL || corner == NULL || !state->configured) {
        return false;
    }

    protection_margin_probe_t probe;

    /*
     * The same probe steam_widened_margin builds, built here rather than shared
     * through a field on the state, on the terms the coffee side's own corner
     * reader states: it is derived entirely from figures the state already
     * holds, and a copy kept beside them would be a second statement of what
     * this loop commands to hold its ready target with.
     */
    probe.protects = PLANT_QUANTITY_STEAM_TEMPERATURE_C;
    probe.heater = ACTUATION_CHANNEL_STEAM_HEATER;
    probe.held_at_target[0] = PLANT_STATE_STEAM_TEMPERATURE_C;
    probe.held_at_target[1] = PLANT_STATE_STEAM_TEMPERATURE_C;
    probe.held_count = 1u;
    probe.target_c = (float)state->declaration.ready_temperature_milli_c / 1000.0f;
    probe.holding_permille = as_drive_level((float)state->declaration.standing_load_permille);
    probe.unwidened_c = 0.0f;

    return protection_margin_corner(&state->parameters, &state->budget, &probe, which, corner);
}

bool steam_control_init(steam_control_state_t *state, const estimator_limits_t *limits,
                        const steam_control_declaration_t *declaration,
                        const plant_parameters_t *parameters,
                        const plant_parameter_budget_t *budget)
{
    if (state == NULL) {
        return false;
    }

    state->configured = false;
    state->started = false;
    state->last_step_millis = hw_monotonic_millis();
    state->drawing = false;
    state->feeding = false;
    state->integral_permille = 0.0f;
    state->superheat_integral_permille = 0.0f;
    state->feed_integral_permille = 0.0f;
    state->feed_level_permille = 0.0f;
    state->superheat_estimated = false;
    state->superheat_estimate_k = 0.0f;
    state->pressure_trusted = false;
    state->trusted_pressure_milli_bar = 0;
    state->temperature_trusted = false;
    state->trusted_temperature_milli_c = 0;
    state->heater_permille = 0u;
    state->feed_permille = 0u;

    /*
     * The records are put into the state before anything can refuse, on the
     * same terms control_init already keeps its own: an instance that failed
     * to come up answers with a record of nothing rather than with whatever
     * the memory it was declared in contained.
     *
     * Copied from a zeroed instance of each type rather than assigned field
     * by field, for the reason control_init's own copies are: which fields
     * either record carries is that record's own business.
     */
    static const estimator_limits_t NO_LIMITS;
    static const steam_control_declaration_t NO_DECLARATION;

    state->limits = NO_LIMITS;
    if (limits != NULL) {
        state->limits = *limits;
    }

    state->declaration = NO_DECLARATION;
    if (declaration != NULL) {
        state->declaration = *declaration;
    }

    static const plant_parameters_t NO_MACHINE;
    static const plant_parameter_budget_t NOTHING_DECLARED_WRONG;

    state->parameters = NO_MACHINE;
    if (parameters != NULL) {
        state->parameters = *parameters;
    }
    state->budget = NOTHING_DECLARED_WRONG;
    if (budget != NULL) {
        state->budget = *budget;
    }

    const bool off = command_everything_off(state);

    /*
     * A loop with no figures to act on, or no bounds to judge a reading by, is
     * refused after the outputs are commanded off, not before, so the refusal
     * leaves the machine neither heated nor fed the way every other refusal
     * here does.
     */
    if (limits == NULL || declaration == NULL || parameters == NULL || budget == NULL) {
        return false;
    }

    /*
     * A declaration built by hand is held to what one read from a file is: a
     * figure out of range, a band with no inside, or a draw that starts above
     * its own ceiling is refused here, after the outputs are off, and the law
     * stays unconfigured.
     */
    if (!steam_control_declaration_admissible(declaration, NULL)) {
        return false;
    }

    /*
     * The believed description and error budget are held to the precondition
     * every law holds them to, and a declaration asking this loop to hold the
     * block where the declared model error could carry it into its own
     * protection is refused here, at
     * the one point the target is taken on, rather than left to be discovered
     * by the device opening. It is refused after the outputs are off for the
     * reason every other refusal here is.
     */
    if (!ready_target_clears_the_protection_margin(declaration, parameters, budget)) {
        return false;
    }

    state->configured = true;
    return off;
}

steam_control_step_result_t steam_control_step(steam_control_state_t *state)
{
    if (state == NULL || !state->configured) {
        return STEAM_CONTROL_STEP_SENSOR_INVALID;
    }

    /*
     * Compare the elapsed difference rather than the absolute instants, so the
     * interval survives the monotonic counter wrapping. The first step of an
     * instance has no predecessor to measure from and advances nothing: an
     * integral given the age of the instance would accumulate a span during
     * which this loop was not driving the machine.
     */
    const uint32_t now = hw_monotonic_millis();
    const uint32_t advance = state->started ? (now - state->last_step_millis) : 0u;

    state->started = true;
    state->last_step_millis = now;

    const bool drawing = a_draw_is_under_way(state);
    const bool opening = drawing && !state->drawing;
    state->drawing = drawing;

    bool pressure_fresh = false;
    bool temperature_fresh = false;
    const bool have_pressure =
        believed(&state->pressure_trusted, &state->trusted_pressure_milli_bar, state,
                 HW_SENSOR_STEAM_PRESSURE, &pressure_fresh);
    const bool have_temperature =
        believed(&state->temperature_trusted, &state->trusted_temperature_milli_c, state,
                 HW_SENSOR_STEAM_TEMPERATURE, &temperature_fresh);

    /*
     * The gate's verdict, taken on the step the wand opens from the pressure the
     * shut block was last trusted at, and held until the wand shuts. A draw
     * opened against a path below the declared ready threshold, or against one
     * nothing has ever been trusted on, is starved for the whole of it: starved
     * and unmistakably weak is the softer failure than steam that starts
     * acceptable and degrades. A draw reopened is a new draw and is judged again.
     *
     * Each new draw also starts the two loops that serve it from no accumulated
     * intent: what one draw learned about a machine is not evidence about the
     * next, which may be opened against a different block.
     */
    if (opening) {
        state->feeding = have_pressure && state->trusted_pressure_milli_bar >=
                                              state->declaration.ready_pressure_milli_bar;
        state->superheat_integral_permille = 0.0f;
        state->feed_integral_permille = 0.0f;
    }
    if (!drawing) {
        state->feeding = false;
        state->feed_level_permille = 0.0f;
    }

    const float interval_s = (float)advance / 1000.0f;
    const float measured_bar = (float)state->trusted_pressure_milli_bar / 1000.0f;
    const float measured_c = (float)state->trusted_temperature_milli_c / 1000.0f;

    uint16_t feed = 0u;
    if (state->feeding) {
        const float target_bar = ((float)(state->declaration.draw_pressure_floor_milli_bar +
                                          state->declaration.draw_pressure_ceiling_milli_bar) *
                                  0.5f) /
                                 1000.0f;
        const bool heat_spent =
            state->heater_permille >= (uint16_t)ACTUATION_FULL_SCALE && state->superheat_estimated &&
            state->superheat_estimate_k <
                ((float)state->declaration.superheat_setpoint_milli_k / 1000.0f);
        feed = feed_command(state, target_bar - measured_bar, interval_s, opening, heat_spent);
    }

    /*
     * What the heater holds. While a draw is fed it is the outlet superheat the
     * law estimates for the feed this step commands, held at the declared
     * setpoint; otherwise -- idle, recovering, or serving a draw it starved, which
     * makes no steam to have a superheat -- it is the casting's temperature, held
     * at the ready target.
     */
    float error = 0.0f;
    bool drivable = false;

    state->superheat_estimated = false;
    if (state->feeding) {
        float estimate_k = 0.0f;

        if (have_pressure && have_temperature &&
            plant_model_least_outlet_superheat(&state->parameters, &state->budget, measured_c,
                                               measured_bar, feed, &estimate_k)) {
            state->superheat_estimated = true;
            state->superheat_estimate_k = estimate_k;
            /*
             * The superheat setpoint is a floor, not a target to bring the
             * casting down to: while the estimate stands above it the casting
             * is held at the ready target, so the heat stored in it is spent
             * on the draw rather than given up at its start.
             */
            error = greater(
                ((float)state->declaration.superheat_setpoint_milli_k / 1000.0f) - estimate_k,
                ((float)state->declaration.ready_temperature_milli_c / 1000.0f) - measured_c);
            drivable = true;
        }
    } else {
        error = ((float)state->declaration.ready_temperature_milli_c / 1000.0f) - measured_c;
        drivable = have_temperature;
    }

    /*
     * A loop with nothing to drive from commands the heater at nothing rather
     * than at whatever the arithmetic of an absent reading produces, and
     * accumulates nothing while it waits: an integral wound up against a
     * machine nobody is observing arrives as duty the moment a reading
     * returns, on the strength of an interval nothing was known about.
     */
    const uint16_t level =
        (drivable && is_a_figure(error))
            ? as_drive_level(heater_command(state, error, interval_s, feed, state->feeding))
            : 0u;

    /*
     * A machine that accepts one of the two commands and refuses the other is
     * brought down rather than left half-driven, on exactly the terms
     * control_step's own refused-drive path brings the brew side down. The
     * case that makes it necessary is the refused heater: the feed pump is
     * still at whatever the step before commanded, which mid-draw is water
     * being pushed into a block whose element is at a level nothing
     * established -- the wet start this whole sequencing exists to prevent,
     * arriving through the one path that bypasses the sequencing entirely.
     * Ordering the two calls cannot answer that, because the pump was already
     * running before this step began; only commanding it off can.
     *
     * The off commands are issued through the same call that may itself have
     * just refused, so they may refuse too. That is why command_everything_off
     * records what the interface accepted rather than what it was asked for --
     * a channel whose off command was refused is still at its previous level,
     * and this state must not claim otherwise.
     */
    if (!hw_output_set(ACTUATION_CHANNEL_STEAM_HEATER, level)) {
        (void)command_everything_off(state);
        return STEAM_CONTROL_STEP_OUTPUT_REFUSED;
    }
    state->heater_permille = level;

    if (!hw_output_set(ACTUATION_CHANNEL_STEAM_PUMP, feed)) {
        (void)command_everything_off(state);
        return STEAM_CONTROL_STEP_OUTPUT_REFUSED;
    }
    state->feed_permille = feed;

    /*
     * A step reports itself ordinary only when it had a fresh reading of both
     * channels: the pressure, which the gate and the feed read, and the casting's
     * temperature, which the heater reads whatever it holds. A stale figure
     * carried forward is the right thing to act on and still not something to
     * report as an observation.
     */
    const bool observed = pressure_fresh && temperature_fresh;
    return observed ? STEAM_CONTROL_STEP_ACTUATED : STEAM_CONTROL_STEP_SENSOR_INVALID;
}

bool steam_control_variable(const steam_control_state_t *state, steam_control_variable_t *variable)
{
    if (state == NULL || variable == NULL || !state->configured) {
        return false;
    }

    *variable = state->drawing ? STEAM_CONTROL_VARIABLE_PRESSURE
                               : STEAM_CONTROL_VARIABLE_TEMPERATURE;
    return true;
}

bool steam_control_drawing(const steam_control_state_t *state, bool *drawing)
{
    if (state == NULL || drawing == NULL || !state->configured) {
        return false;
    }

    *drawing = state->drawing;
    return true;
}

bool steam_control_outlet_superheat(const steam_control_state_t *state, float *superheat_k)
{
    if (state == NULL || superheat_k == NULL || !state->configured ||
        !state->superheat_estimated) {
        return false;
    }

    *superheat_k = state->superheat_estimate_k;
    return true;
}
