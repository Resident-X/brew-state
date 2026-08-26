#include "steam_control.h"

#include <stddef.h>

#include "hw_interface.h"

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
 */

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
 * The level the feed pump is commanded at this step, before the readiness
 * threshold is asked about.
 *
 * Nothing while no draw is under way: a block nothing is being taken out of
 * needs no water pushed into it, and a pump left running against a shut wand
 * is filling a vessel with nowhere for the contents to go.
 *
 * Nothing, too, for the declared margin-building interval after a draw begins.
 * That is the whole of the heater-leads-feed sequencing: the element is at its
 * ceiling from the first step of the draw (see heater_command) while the feed
 * is held back, so that the first steam actually made comes out of a block
 * that has thermal margin to give rather than out of one that is only just
 * ready.
 *
 * Once engaged, the level rises to the declared sustainable rate over the
 * declared rise interval rather than stepping to it, and is never carried past
 * that rate however long the draw runs or however wide the wand is opened.
 * There is no reading of how much steam is being asked for -- the microswitch
 * reports that the wand is turned and nothing else -- so this cap is not a
 * refusal to follow demand but the only rate any law here could command. It is
 * what makes a draw beyond the block's capacity give up quantity rather than
 * character.
 *
 * A rise interval declared as nothing reaches the full rate on the first step
 * past engagement, which is a design saying it wants no rise rather than an
 * edge this arithmetic stumbles into: the division is guarded because it would
 * otherwise be by zero, and the answer on that branch is the one the
 * declaration asked for.
 */
static uint16_t feed_command(const steam_control_state_t *state)
{
    if (!state->drawing) {
        return 0u;
    }

    const uint32_t margin_millis = (uint32_t)state->declaration.margin_interval_millis;
    if (state->draw_elapsed_millis < margin_millis) {
        return 0u;
    }

    const float sustainable_permille = (float)state->declaration.sustainable_feed_permille;
    const uint32_t rise_millis = (uint32_t)state->declaration.feed_rise_millis;
    const uint32_t since_engaged = state->draw_elapsed_millis - margin_millis;

    if (rise_millis == 0u || since_engaged >= rise_millis) {
        return as_drive_level(sustainable_permille);
    }

    return as_drive_level((sustainable_permille * (float)since_engaged) / (float)rise_millis);
}

/*
 * The heater command for one step, and the accumulated intent it leaves
 * behind.
 *
 * The feedforward term is added before the loop looks at the error rather than
 * after, for the reason control.c's own heater_command adds its own first: it
 * answers a load the machine has been told about. The feed level is what this
 * same step just decided to command, and the energy the water it pushes in
 * will take to reach saturation and turn is known at that moment rather than
 * discovered once the pressure has fallen. On a block holding no reservoir of
 * vapour at all, that fall arrives faster than any feedback term could answer
 * it.
 *
 * The standing loss is fed forward as well, and as a flat duty rather than as
 * a figure per kelvin of rise -- which is where this parts company with the
 * brew loop, whose own standing term follows the target a caller names. The
 * reason is that this loop's target does not move: it holds one declared ready
 * state and one declared band, some tens of kelvin apart, and over that span
 * the block's standing load barely changes. What is given up is exactness at
 * the top of the band, which the integral trims; what is bought is one figure
 * rather than a coefficient plus the temperature it would have to be measured
 * from, which this file has no honest source for -- the ambient a block loses
 * to is not a channel the seam reports. See standing-load's own account in
 * params/steam_control.declaration.
 *
 * The error is taken against whichever variable is in force, in that
 * variable's own unit, and each has a gain declared against that unit -- so
 * nothing here converts a pressure into the temperature that would imply it,
 * which is a relation belonging to a plant structure that this file may not
 * read and that a draw makes untrue anyway.
 *
 * Integration is made conditional on the actuator rather than unwound after
 * the fact, on exactly the terms control.c's own loop is and for the same
 * reason: full duty is this machine's ordinary condition rather than an
 * exception -- every draw begins there by construction -- so intent
 * accumulated across the limit would arrive as an overshoot once the demand
 * ended, long after the interval that produced it.
 *
 * The condition is asked of the command this step will actually issue, which
 * during the margin-building interval is the ceiling regardless of what the
 * tracking terms come to. Asking it of the tracking terms instead would let
 * the integral unwind against a duty that was never issued, which is the same
 * error as letting it wind up against one.
 */
static float heater_command(steam_control_state_t *state, float error, float interval_s,
                            uint16_t feed_permille, bool leading)
{
    const float gain =
        state->drawing ? (float)state->declaration.draw_gain_milli_permille_per_bar
                       : (float)state->declaration.ready_gain_milli_permille_per_k;
    const float integral_gain =
        state->drawing ? (float)state->declaration.draw_integral_gain_milli_permille_per_bar_s
                       : (float)state->declaration.ready_integral_gain_milli_permille_per_k_s;
    const float feed_load_gain =
        (float)state->declaration.feed_load_gain_milli_permille_per_permille;

    const float proportional = (gain / 1000.0f) * error;
    const float feedforward = (float)state->declaration.standing_load_permille +
                              ((feed_load_gain / 1000.0f) * (float)feed_permille);

    const float before = proportional + state->integral_permille + feedforward;
    const float issued = leading ? (float)ACTUATION_FULL_SCALE : before;
    const bool pushing_past_full = (issued >= (float)ACTUATION_FULL_SCALE) && (error > 0.0f);
    const bool pushing_past_off = (issued <= 0.0f) && (error < 0.0f);

    if (!pushing_past_full && !pushing_past_off) {
        state->integral_permille +=
            (integral_gain / 1000.0f) * error * interval_s;
    }

    if (leading) {
        return (float)ACTUATION_FULL_SCALE;
    }
    return proportional + state->integral_permille + feedforward;
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

bool steam_control_init(steam_control_state_t *state, const estimator_limits_t *limits,
                        const steam_control_declaration_t *declaration)
{
    if (state == NULL) {
        return false;
    }

    state->configured = false;
    state->started = false;
    state->last_step_millis = hw_monotonic_millis();
    state->drawing = false;
    state->draw_elapsed_millis = 0u;
    state->integral_permille = 0.0f;
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

    const bool off = command_everything_off(state);

    /*
     * A loop with no figures to act on, or no bounds to judge a reading by, is
     * refused after the outputs are commanded off, not before, so the refusal
     * leaves the machine neither heated nor fed the way every other refusal
     * here does.
     */
    if (limits == NULL || declaration == NULL) {
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

    /*
     * The draw's own clock is advanced before anything reads it, and is put
     * back to nothing on the step the wand turns rather than on the step after
     * -- so the margin-building interval is measured from the moment the
     * operator asked for steam, and a draw closed and reopened is a new draw
     * that earns its margin again rather than one resuming where the last left
     * off.
     */
    const bool drawing = a_draw_is_under_way(state);

    if (!drawing) {
        state->draw_elapsed_millis = 0u;
    } else if (!state->drawing) {
        state->draw_elapsed_millis = 0u;
    } else {
        state->draw_elapsed_millis += advance;
    }
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
     * Feed is withheld outright while the pressure this loop believes sits
     * below the declared ready threshold, and while it believes nothing at
     * all. That is the readiness policy standing in front of the band-holding
     * law rather than beside it: a draw beginning against a path that has not
     * reached the threshold is starved and unmistakably weak, which is the
     * softer failure than steam that starts acceptable and degrades. It is
     * asked of the same believed figure the tracking law reads, so a single
     * absurd sample mid-draw does not chop the feed off and back on -- see
     * `believed`.
     */
    const bool ready = have_pressure &&
                       state->trusted_pressure_milli_bar >=
                           state->declaration.ready_pressure_milli_bar;
    const uint16_t feed = ready ? feed_command(state) : 0u;

    /*
     * Which variable governs, and the error against it. The switch happens on
     * the same step the wand's report changes, and not a step later: the
     * draw's whole first second is the part of it the operator can least
     * afford the loop to spend answering the wrong question.
     */
    const bool leading =
        drawing && state->draw_elapsed_millis < (uint32_t)state->declaration.margin_interval_millis;

    float error = 0.0f;
    bool drivable = false;

    if (drawing) {
        /*
         * The middle of the declared band rather than either edge: a loop
         * driven at an edge holds against one side of the band and has the
         * whole of the other to give away before anything notices, which is
         * the arrangement that spends the band rather than keeping it. The
         * target is derived here rather than declared beside the edges because
         * it is not a third choice anybody makes -- it follows from the two,
         * and a declared middle that disagreed with them would be a third
         * figure to keep in step with two others.
         */
        const float target_milli_bar =
            (float)(state->declaration.draw_pressure_floor_milli_bar +
                    state->declaration.draw_pressure_ceiling_milli_bar) *
            0.5f;
        const float target_bar = target_milli_bar / 1000.0f;
        const float measured_bar =
            (float)state->trusted_pressure_milli_bar / 1000.0f;

        error = target_bar - measured_bar;
        drivable = have_pressure;
    } else {
        const float target_c =
            (float)state->declaration.ready_temperature_milli_c / 1000.0f;
        const float measured_c =
            (float)state->trusted_temperature_milli_c / 1000.0f;

        error = target_c - measured_c;
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
            ? as_drive_level(heater_command(state, error, (float)advance / 1000.0f,
                                            feed, leading))
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
     * A step reports itself ordinary only when it had a fresh reading of every
     * channel it acted on: the pressure, which the readiness policy reads on
     * every step whatever is happening, and the variable in force. A stale
     * figure carried forward is the right thing to act on and still not
     * something to report as an observation.
     */
    const bool observed = pressure_fresh && (drawing || temperature_fresh);
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
