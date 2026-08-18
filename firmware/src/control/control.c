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

bool control_init(control_state_t *state, const plant_parameters_t *parameters)
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
    if (!estimator_init(&state->estimator, parameters)) {
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
    if (state->started && (now - state->last_step_millis) < CONTROL_STEP_INTERVAL_MS) {
        return CONTROL_STEP_TOO_SOON;
    }

    state->started = true;
    state->last_step_millis = now;
    state->step_count++;

    if (state->faulted) {
        if (hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u)) {
            state->brew_heater_permille = 0u;
        }
        return CONTROL_STEP_FAULT_LATCHED;
    }

    /*
     * Advanced by the interval the control path runs at rather than by the
     * elapsed difference computed above. The two coincide on a loop that is not
     * late, and which of them the estimator ought to be advanced by is part of
     * the rate question this slice defers: an estimator told the truth about a
     * late step is more accurate, and one told the nominal interval is
     * reproducible step for step. Nothing here should decide that quietly.
     */
    const plant_actuation_t commanded = commanded_actuation(state);
    if (!estimator_step(&state->estimator, &commanded, CONTROL_STEP_INTERVAL_MS)) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    /*
     * Whether the brew reading could be trusted is asked of the estimator
     * rather than of the seam a second time. The estimator corrects against a
     * channel exactly when that channel's reading was usable, so the absence of
     * a residual for it is the same fact a repeated read would establish -- and
     * asking twice would let the two answers disagree across the step.
     */
    int32_t brew_residual = 0;
    if (!estimator_residual(&state->estimator, HW_SENSOR_BREW_TEMPERATURE, &brew_residual)) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    float brew_c = 0.0f;
    if (!estimator_state(&state->estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &brew_c)) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    const uint16_t level = drive_level_for_temperature(brew_c);
    if (!hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, level)) {
        return shut_down(state, CONTROL_STEP_OUTPUT_REFUSED);
    }

    state->brew_heater_permille = level;
    return CONTROL_STEP_ACTUATED;
}
