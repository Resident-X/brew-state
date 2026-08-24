#include "control.h"

#include <stddef.h>

#include "delivery_profile.h"
#include "estimator.h"
#include "hw_interface.h"
#include "plant_model.h"

/*
 * The three coefficients the law rests on. Each accounts for itself in
 * params/control.declaration, and a check run as part of the build refuses a
 * figure here that accounts for itself nowhere -- so a gain added beside these
 * during a tuning session cannot arrive as a bare number nothing asserts, which
 * is the shape a load-bearing figure takes just before everybody treats it as
 * settled.
 *
 * They are coefficients of the loop and not of any machine, which is why they
 * live here rather than in a plant description. A description says what a
 * particular casting is; these say what the design does about it, and they are
 * the same on every machine this software is compiled for.
 */

/*
 * Proportional gain: permille of full heater scale per kelvin of error.
 */
#define CONTROL_PROPORTIONAL_PERMILLE_PER_K 30.0f

/*
 * Integral gain: permille of full heater scale per kelvin of error per second.
 */
#define CONTROL_INTEGRAL_PERMILLE_PER_K_PER_S 0.35f

/*
 * The temperature the machine draws its water and its air from, in degrees
 * Celsius. What the loop has to supply is the cost of lifting the delivery
 * above this, so it is the origin the two load coefficients below are measured
 * from rather than a temperature the loop ever drives toward.
 */
#define CONTROL_COLD_REFERENCE_C 20.0f

/*
 * What the machine loses to the room, in permille of full heater scale per
 * kelvin of rise above the cold reference.
 */
#define CONTROL_STANDING_PERMILLE_PER_K 1.2f

/*
 * What the drawn water carries away, in permille of full heater scale per
 * kelvin of rise above the cold reference, per permille of commanded pump
 * level.
 */
#define CONTROL_DRAWN_PERMILLE_PER_K_PER_PUMP_PERMILLE 0.02905f

/*
 * What was commanded over the interval just elapsed, for the estimator to
 * advance under.
 *
 * The pump level belongs in here as much as the heater's does. Without it the
 * model is advanced as though the machine were still while water was moving
 * through it, and the state no sensor observes -- the temperature of the water
 * on its way to the group -- drifts from the machine exactly when a delivery is
 * under way. That is the failure this loop exists to prevent, arriving through
 * the back door of the model rather than through the control law.
 */
static plant_actuation_t commanded_actuation(const control_state_t *state)
{
    plant_actuation_t commanded = {{0u}};

    commanded.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = state->brew_heater_permille;
    commanded.level_permille[ACTUATION_CHANNEL_PUMP] = state->driven_pump_permille;
    return commanded;
}

/*
 * Whether a value is a temperature at all -- neither a not-a-number nor an
 * unbounded one.
 *
 * Written out rather than asked of the standard library's isfinite, which is a
 * macro that expands to a different implementation-reserved name on a host and
 * on the target. The control logic is required to be byte-identical across the
 * two and a check run as part of the build compares them, so a macro that
 * expands differently is a difference in the control logic however identical
 * the source reads. Everything outside src/control is free to use it, and does.
 *
 * The first comparison refuses a not-a-number, which compares equal to nothing
 * including itself. The second refuses either infinity, whose difference from
 * itself is a not-a-number rather than nothing.
 *
 * It rests on the build not telling the compiler that neither case can arise.
 * Under -ffinite-math-only, or the -Ofast that implies it, both comparisons are
 * licensed to fold to true and the refusal disappears without a diagnostic --
 * which would be a silent hole rather than a loud one. No environment in this
 * project passes either flag, and a build that started to would be asserting
 * something about this machine's arithmetic that nothing has established.
 */
static bool is_a_temperature(float celsius)
{
    return (celsius == celsius) && ((celsius - celsius) == 0.0f);
}

/* Narrow a command in permille to what the actuator can be given. */
static uint16_t as_drive_level(float permille)
{
    /*
     * Written as a negated comparison so that a command that is not a number
     * lands at nothing rather than somewhere in range. A reconstruction that is
     * not finite is refused at the seam and never reaches the arithmetic above,
     * but the guard costs a branch and removes the whole class.
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
 * The heater command for one step, and the accumulated intent it leaves behind.
 *
 * The feedforward term is added before the loop looks at the error rather than
 * after, because it answers a load the machine has been told about: the pump
 * level is what a delivery asked for, and the energy the water it moves will
 * carry away is known at that moment rather than discovered once the
 * temperature has fallen. On a block holding a few millilitres the fall arrives
 * faster than any feedback term could answer it, so a loop without this is a
 * loop that is always apologising.
 *
 * It carries the standing loss as well as the drawn one. The two are separate
 * figures because they answer to different things -- one moves with the flow
 * commanded and the other does not -- and together they are what the machine
 * needs when it is doing what it was asked to do. Leaving either to the error
 * term would make the loop earn the whole steady load through an error large
 * enough to command it, which is a loop that only reaches the temperature it
 * was asked for by first being wrong about it.
 *
 * Both are measured per kelvin of rise above the temperature the machine draws
 * from, and are scaled here by the rise the commanded target actually asks for.
 * That is what keeps this a feedforward rather than a calibration: a pair of
 * figures fixed at one brew temperature would answer the whole load exactly
 * there and be wrong everywhere else, by an amount growing with the distance
 * from it, and the residue would fall to an integral slow enough that a shot
 * would end before it had trimmed half of it. Since the target became something
 * a caller names rather than a constant, "everywhere else" is where the machine
 * now spends its time.
 *
 * Integration is made conditional on the actuator rather than unwound after the
 * fact. Full duty is this machine's ordinary condition and not an exception --
 * a cold start, a long draw, a machine recovering between shots all sit there --
 * so the limit is where the loop spends much of its working life, and intent
 * accumulated across it would arrive as an overshoot once the demand ended,
 * long after the interval that produced it. The test of the arrangement is not
 * that a saturated interval produces no overshoot but that a longer one
 * produces no more of it: an integrator that merely unwinds fast passes the
 * first and fails the second.
 *
 * The condition is asked of the command the loop would issue before this step's
 * accumulation, and of the direction the error would push it: intent is
 * surrendered only while the actuator is already at a limit and the error would
 * drive it further past. An error pointing back into range still integrates, so
 * the loop leaves saturation on the step the machine does rather than some
 * steps later.
 */
static float heater_command(control_state_t *state, float reconstruction_c, float interval_s)
{
    const float error_k = state->target_c - reconstruction_c;
    const float proportional = CONTROL_PROPORTIONAL_PERMILLE_PER_K * error_k;

    /*
     * A target at or below the temperature the machine draws from costs nothing
     * to hold, and a negative rise would have the feedforward asking for less
     * than no heat. Taken at nothing rather than allowed through, so the term
     * answers a load rather than becoming a second, inverted controller.
     */
    const float rise_k = (state->target_c > CONTROL_COLD_REFERENCE_C)
                             ? (state->target_c - CONTROL_COLD_REFERENCE_C)
                             : 0.0f;
    const float feedforward =
        rise_k * (CONTROL_STANDING_PERMILLE_PER_K +
                  (CONTROL_DRAWN_PERMILLE_PER_K_PER_PUMP_PERMILLE *
                   (float)state->commanded_pump_permille));

    const float before = proportional + state->integral_permille + feedforward;
    const bool pushing_past_full = (before >= (float)ACTUATION_FULL_SCALE) && (error_k > 0.0f);
    const bool pushing_past_off = (before <= 0.0f) && (error_k < 0.0f);

    if (!pushing_past_full && !pushing_past_off) {
        state->integral_permille += CONTROL_INTEGRAL_PERMILLE_PER_K_PER_S * error_k * interval_s;
    }

    return proportional + state->integral_permille + feedforward;
}

/*
 * Command every output off.
 *
 * The pump goes off with the heater rather than being left where it was. A
 * control path that has stopped driving the heater and gone on moving water is
 * pushing the feed temperature through the group, which is both the wrong drink
 * and a machine doing something nobody asked it to; and the case this is
 * reached from is one where the temperature the water is at is no longer
 * known.
 *
 * Each recorded level follows what the interface accepted rather than what was
 * asked for: if an off command is itself refused -- which is exactly the
 * condition that produced an output-refused step -- that output is still at its
 * previous level, and recording zero would state it is off when nothing
 * established that.
 */
static void command_everything_off(control_state_t *state)
{
    if (hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u)) {
        state->brew_heater_permille = 0u;
    }
    if (hw_output_set(ACTUATION_CHANNEL_PUMP, 0u)) {
        state->driven_pump_permille = 0u;
    }

    /*
     * What was asked for is forgotten along with what was driven. A machine
     * brought down, or standing between deliveries, has no outstanding request
     * to resume: leaving the last delivery's flow here would have the pump
     * start again at that level the moment a temperature was next commanded,
     * which is water moving because of something the caller asked for minutes
     * ago and has not repeated.
     *
     * A running delivery is exactly such an outstanding request, and is ended
     * here alongside it rather than left to go on counting. Every path that
     * reaches this function -- shutting down, a fault latching, and a step
     * with nothing targeted -- is a machine that has stopped driving water, so
     * a delivery still marked running past this point would burn the rest of
     * its course against the clock while nothing moved, and report itself
     * finished having delivered nothing.
     */
    state->commanded_pump_permille = 0u;
    state->delivery_running = false;
    state->delivery_elapsed_millis = 0u;
}

/* Latch the fault and command the outputs off. */
static control_step_result_t shut_down(control_state_t *state, control_step_result_t reason)
{
    state->faulted = true;
    command_everything_off(state);
    return reason;
}

/*
 * What full pump scale draws on the machine a parameter record describes, in
 * millilitres per second.
 *
 * Asked through the plant seam's own vocabulary -- a model of this machine
 * kept aside, stepped once at full pump, and read back for what it says is
 * moving -- rather than by reaching for the structure's coefficient by name.
 * A coefficient named here would tie this file to the thermoblock's own
 * spelling of it, which is exactly what the plant encapsulation check refuses
 * of every consumer under src/control and src/delivery: the next structure
 * this software is compiled against may not call the same figure the same
 * thing, or may not carry it as a single coefficient at all, and this file
 * has to go on working against it unchanged.
 *
 * Zero is the honest answer for a record that fails to initialise a model, a
 * step that is refused, or a structure that genuinely draws nothing at full
 * pump -- and it is left for the caller to decide what a figure of nothing
 * means, rather than this function treating any of those as its own fault.
 */
static float probe_full_scale_flow_ml_per_s(const plant_parameters_t *parameters)
{
    plant_model_t probe;
    plant_actuation_t everything = {{0u}};
    float flow = 0.0f;

    if (!plant_model_init(&probe, parameters)) {
        return 0.0f;
    }

    everything.level_permille[ACTUATION_CHANNEL_PUMP] = (uint16_t)ACTUATION_FULL_SCALE;
    if (!plant_model_step(&probe, &everything, 0.0f, CONTROL_STEP_INTERVAL_MS)) {
        return 0.0f;
    }
    if (!plant_model_quantity(&probe, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &flow) || !(flow > 0.0f)) {
        return 0.0f;
    }

    return flow;
}

bool control_init(control_state_t *state, const plant_parameters_t *parameters,
                  const estimator_limits_t *limits, const delivery_tolerance_t *tolerance)
{
    if (state == NULL) {
        return false;
    }

    state->last_step_millis = hw_monotonic_millis();
    state->step_count = 0u;
    state->brew_heater_permille = 0u;
    state->commanded_pump_permille = 0u;
    state->driven_pump_permille = 0u;
    state->target_c = 0.0f;
    state->targeted = false;
    state->integral_permille = 0.0f;
    state->started = false;
    state->faulted = false;
    state->full_scale_flow_ml_per_s = 0.0f;
    state->delivery_running = false;
    state->delivery_elapsed_millis = 0u;

    /*
     * The band is put into the state before anything can refuse, so that an
     * instance which failed to come up still answers what it was given rather
     * than whatever the memory it was declared in contained. Given none it
     * answers nothing, which is the honest answer and is why the refusal below
     * follows rather than a band being assumed.
     */
    state->tolerance.brew_temperature_band_milli_c = 0;
    if (tolerance != NULL) {
        state->tolerance = *tolerance;
    }

    const bool off = hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u) &&
                     hw_output_set(ACTUATION_CHANNEL_PUMP, 0u);

    /*
     * A control path with no band is refused after the outputs are commanded
     * off, not before, so that the refusal leaves the machine de-energised the
     * way every other refusal here does. A band left undeclared is not a wide
     * band: it is a criterion nothing holds a delivery to, and a loop that came
     * up anyway would be driving toward a temperature with no statement of what
     * counts as having reached it.
     */
    if (tolerance == NULL) {
        state->faulted = true;
        return false;
    }

    /*
     * The outputs are commanded off before the estimator is brought up, so that
     * a refusal below leaves the machine de-energised rather than leaving the
     * off commands unsent. A refusal latches the fault for the same reason an
     * untrustworthy reading does: there is no temperature to act on, and a
     * control law that started driving later would be driving blind.
     */
    if (!estimator_init(&state->estimator, parameters, limits)) {
        state->faulted = true;
        return false;
    }

    /*
     * Probed once the estimator has accepted the same record, rather than
     * before: a record the estimator refuses is not a machine this instance
     * is going anywhere with, and probing it anyway would be answering a
     * question about a structure this instance is about to report unusable.
     */
    state->full_scale_flow_ml_per_s = probe_full_scale_flow_ml_per_s(parameters);

    return off;
}

bool control_command_temperature(control_state_t *state, float celsius)
{
    if (state == NULL || !is_a_temperature(celsius)) {
        return false;
    }

    if (!state->targeted || state->target_c != celsius) {
        state->integral_permille = 0.0f;
    }
    state->target_c = celsius;
    state->targeted = true;
    return true;
}

bool control_command_flow(control_state_t *state, uint16_t pump_permille)
{
    if (state == NULL || pump_permille > (uint16_t)ACTUATION_FULL_SCALE) {
        return false;
    }

    state->commanded_pump_permille = pump_permille;
    return true;
}

bool control_command_delivery(control_state_t *state, const delivery_profile_t *profile)
{
    if (state == NULL || profile == NULL || !(state->full_scale_flow_ml_per_s > 0.0f)) {
        return false;
    }

    state->delivery = *profile;
    state->delivery_running = true;
    state->delivery_elapsed_millis = 0u;
    return true;
}

bool control_delivery_running(const control_state_t *state)
{
    return state != NULL && state->delivery_running;
}

bool control_temperature_band(const control_state_t *state, int32_t *band_milli_c)
{
    if (state == NULL || band_milli_c == NULL) {
        return false;
    }

    *band_milli_c = state->tolerance.brew_temperature_band_milli_c;
    return true;
}

control_step_result_t control_step(control_state_t *state)
{
    if (state == NULL) {
        return CONTROL_STEP_SENSOR_INVALID;
    }

    const uint32_t now = hw_monotonic_millis();

    /*
     * Compare the elapsed difference rather than the absolute instants, so the
     * step interval survives the monotonic counter wrapping.
     */
    const uint32_t elapsed = now - state->last_step_millis;
    if (state->started && elapsed < CONTROL_STEP_INTERVAL_MS) {
        return CONTROL_STEP_TOO_SOON;
    }

    /*
     * What the estimator will be advanced by: the interval that actually
     * elapsed, not the one the loop is meant to run at. The two coincide on a
     * loop that is not late, and they differ on exactly the steps where the
     * reconstruction matters most. A model integrates over an interval, and
     * handing it one that did not pass makes its output an answer to a question
     * nobody asked -- an instant that never happened, reported as the present.
     *
     * The first accepted step has no predecessor to measure from, so it is
     * advanced by the declared interval rather than by the age of the instance.
     *
     * Reproducibility is not what is given up here. The suites that drive this
     * path own the clock rather than observe it, so the elapsed figure is an
     * input they choose exactly; determinism is kept by governing the clock
     * rather than by misinforming the estimator.
     */
    const uint32_t advance = state->started ? elapsed : CONTROL_STEP_INTERVAL_MS;

    /*
     * Whether this step arrived later than the cadence tolerates. Noted before
     * the step runs and reported after it, because being late does not stop the
     * step: the estimator is still advanced by what elapsed and the outputs are
     * still driven. What it changes is what the caller is told.
     */
    const bool late =
        state->started && elapsed > (CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE);

    state->started = true;
    state->last_step_millis = now;
    state->step_count++;

    if (state->faulted) {
        command_everything_off(state);
        return CONTROL_STEP_FAULT_LATCHED;
    }

    const plant_actuation_t commanded = commanded_actuation(state);
    if (!estimator_step(&state->estimator, &commanded, advance)) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    /*
     * Whether there is a state to drive from is asked of the estimator once,
     * and asked as that question rather than as a question about a channel. A
     * reading that did not arrive, or arrived and was absurd, is an ordinary
     * operating condition: the estimator carries the reconstruction on
     * prediction and goes on answering, and this path drives from it. It stops
     * answering when the loss is no longer brief or the prediction has
     * travelled too far, and that refusal -- not the absence of one reading --
     * is what brings the heater down.
     *
     * The state asked for is the water on its way to the group and not the mass
     * a sensor reports. They are different quantities, and how far apart they
     * are moves with the draw, so a loop closed on the reading would be right
     * about the machine and wrong about the drink.
     */
    float brew_c = 0.0f;
    if (!estimator_state(&state->estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &brew_c)) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    /*
     * A machine that has not been asked for a drink drives nothing. The
     * estimator has already been advanced above, so the reconstruction goes on
     * following the machine while it waits, and the delivery that arrives next
     * starts from a state that has been kept rather than from one that stopped.
     *
     * command_everything_off clears a running delivery as part of commanding
     * everything else off, so a step that reaches this branch ends whatever
     * delivery was running rather than leaving it for the block below to go on
     * advancing against a machine that is not driving water.
     */
    if (!state->targeted) {
        state->integral_permille = 0.0f;
        command_everything_off(state);
        return CONTROL_STEP_NO_TARGET;
    }

    /*
     * A running delivery is advanced here: after the estimator, because what
     * it commands next answers for the interval that is coming rather than
     * correcting the one just gone; below the no-target branch above, because
     * a delivery only ever advances on a step that actually drives the
     * machine -- a step with nothing targeted has already ended it, by way of
     * command_everything_off, and advancing its clock and its commanded rate
     * regardless would have it run against the course while nothing moved;
     * and above the heater command below, because the feedforward it carries
     * reads commanded_pump_permille in this same step, and a delivery's
     * commanded rate has to be sitting there before it is read, not after.
     *
     * `advance` is the interval that actually elapsed, the same one the
     * estimator was just advanced by. Timing the delivery against the nominal
     * cadence instead would have it end early or late by exactly how far a
     * late step had fallen behind -- the same dishonesty the estimator's own
     * advance is written to avoid.
     *
     * control_command_delivery refuses to start a delivery unless
     * full_scale_flow_ml_per_s is usable, so nothing here has to check it
     * again: every delivery reaching this branch has a figure to divide the
     * commanded rate by.
     */
    if (state->delivery_running) {
        state->delivery_elapsed_millis += advance;

        if (delivery_profile_ended(&state->delivery, state->delivery_elapsed_millis)) {
            state->delivery_running = false;
            state->commanded_pump_permille = 0u;
        } else {
            const float rate_ml_per_s =
                delivery_profile_rate_ml_per_s(&state->delivery, state->delivery_elapsed_millis);
            const float permille =
                (rate_ml_per_s / state->full_scale_flow_ml_per_s) * (float)ACTUATION_FULL_SCALE;
            state->commanded_pump_permille = as_drive_level(permille);
        }
    }

    const float interval_s = (float)advance / 1000.0f;
    const uint16_t level = as_drive_level(heater_command(state, brew_c, interval_s));

    /*
     * The pump is driven before the heater command is recorded but after the
     * heater is driven, so that a machine which accepts one command and refuses
     * the other is shut down rather than left half-driven. Both levels reach
     * the machine in the step the flow was commanded in, which is what makes
     * the feedforward above a feedforward rather than a fast reaction.
     */
    if (!hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, level)) {
        return shut_down(state, CONTROL_STEP_OUTPUT_REFUSED);
    }
    state->brew_heater_permille = level;

    if (!hw_output_set(ACTUATION_CHANNEL_PUMP, state->commanded_pump_permille)) {
        return shut_down(state, CONTROL_STEP_OUTPUT_REFUSED);
    }
    state->driven_pump_permille = state->commanded_pump_permille;

    return late ? CONTROL_STEP_LATE : CONTROL_STEP_ACTUATED;
}
