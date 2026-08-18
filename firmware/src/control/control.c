#include "control.h"

#include <stddef.h>

#include "estimator.h"
#include "hw_interface.h"

/*
 * Proportional gain expressed as permille of full scale per degree of error,
 * chosen only so that the skeleton produces a bounded, non-trivial drive level
 * from a temperature reading. Tuning belongs to the control-law deliverable.
 */
#define CONTROL_GAIN_PERMILLE_PER_DEGREE 40

/*
 * The temperature below which the proportional term would ask for more than
 * full scale. Recognising saturation from the temperature itself, rather than
 * from a computed error, is what keeps the arithmetic in range: a
 * reconstruction can be any value a float holds, and a model driven somewhere
 * absurd must not arrive at a plausible drive level on the way through.
 */
#define CONTROL_SATURATION_MILLI_C \
    (CONTROL_BREW_SETPOINT_MILLI_C - \
     ((int32_t)ACTUATION_FULL_SCALE / CONTROL_GAIN_PERMILLE_PER_DEGREE) * 1000)

/* What was commanded over the interval just elapsed, for the estimator to advance under. */
static plant_actuation_t commanded_actuation(const control_state_t *state)
{
    plant_actuation_t commanded = {{0u}};

    commanded.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = state->brew_heater_permille;
    return commanded;
}

static uint16_t drive_level_for_temperature(float celsius)
{
    /*
     * Both bounds are tested before the temperature is converted: outside this
     * span the answer does not depend on how far outside, so nothing outside it
     * is ever converted and no conversion can be asked for a value it cannot
     * represent. The first is written as a negated comparison so that the
     * ordering holds whatever arrives, though a reconstruction that is not a
     * number is refused at the seam and never reaches here.
     */
    if (!(celsius > (float)CONTROL_SATURATION_MILLI_C / 1000.0f)) {
        return (uint16_t)ACTUATION_FULL_SCALE;
    }
    if (celsius >= (float)CONTROL_BREW_SETPOINT_MILLI_C / 1000.0f) {
        return 0u;
    }

    /* In range by construction, and positive, so the rounding needs no branch. */
    const int32_t reading_milli_c = (int32_t)(celsius * 1000.0f + 0.5f);

    /* Bounded by construction: the error is now between one and the saturation span. */
    const int32_t error_degrees = (CONTROL_BREW_SETPOINT_MILLI_C - reading_milli_c) / 1000;
    return (uint16_t)(error_degrees * CONTROL_GAIN_PERMILLE_PER_DEGREE);
}

/*
 * Latch the fault and command the heater off. The recorded level follows what
 * the interface accepted rather than what was asked for: if the off command is
 * itself refused -- which is exactly the condition that produced an
 * output-refused step -- the heater is still at its previous level, and
 * recording zero would state that it is off when nothing established that.
 */
static control_step_result_t shut_down(control_state_t *state, control_step_result_t reason)
{
    state->faulted = true;
    if (hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u)) {
        state->brew_heater_permille = 0u;
    }
    return reason;
}

bool control_init(control_state_t *state, const plant_parameters_t *parameters,
                  const estimator_limits_t *limits)
{
    if (state == NULL) {
        return false;
    }

    state->last_step_millis = hw_monotonic_millis();
    state->step_count = 0u;
    state->brew_heater_permille = 0u;
    state->started = false;
    state->faulted = false;

    const bool off = hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u);

    /*
     * The heater is commanded off before the estimator is brought up, so that a
     * refusal below leaves the machine de-energised rather than leaving the
     * off command unsent. A refusal latches the fault for the same reason an
     * untrustworthy reading does: there is no temperature to act on, and a
     * control law that started driving later would be driving blind.
     */
    if (!estimator_init(&state->estimator, parameters, limits)) {
        state->faulted = true;
        return false;
    }

    return off;
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
     * step: the estimator is still advanced by what elapsed and the heater is
     * still driven. What it changes is what the caller is told.
     */
    const bool late =
        state->started && elapsed > (CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE);

    state->started = true;
    state->last_step_millis = now;
    state->step_count++;

    if (state->faulted) {
        if (hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u)) {
            state->brew_heater_permille = 0u;
        }
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
     * Asking about the residual instead, as this once did, made a single
     * dropped sample indistinguishable from a burnt-out sensor and latched a
     * fault nothing in the tree clears.
     */
    float brew_c = 0.0f;
    if (!estimator_state(&state->estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &brew_c)) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    const uint16_t level = drive_level_for_temperature(brew_c);
    if (!hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, level)) {
        return shut_down(state, CONTROL_STEP_OUTPUT_REFUSED);
    }

    state->brew_heater_permille = level;
    return late ? CONTROL_STEP_LATE : CONTROL_STEP_ACTUATED;
}
