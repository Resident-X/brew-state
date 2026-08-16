#include "control.h"

#include <stddef.h>

#include "hw_interface.h"

/*
 * Proportional gain expressed as permille of full scale per degree of error,
 * chosen only so that the skeleton produces a bounded, non-trivial drive level
 * from a temperature reading. Tuning belongs to the control-law deliverable.
 */
#define CONTROL_GAIN_PERMILLE_PER_DEGREE 40

/*
 * The reading below which the proportional term would ask for more than full
 * scale. Recognising saturation from the reading itself, rather than from a
 * computed error, is what keeps the arithmetic in range: the seam can return
 * any value an int32_t holds, and subtracting the setpoint from the most
 * negative of them would overflow.
 */
#define CONTROL_SATURATION_MILLI_C \
    (CONTROL_BREW_SETPOINT_MILLI_C - \
     ((int32_t)HW_OUTPUT_FULL_SCALE / CONTROL_GAIN_PERMILLE_PER_DEGREE) * 1000)

static uint16_t drive_level_for_reading(int32_t reading_milli_c)
{
    if (reading_milli_c <= CONTROL_SATURATION_MILLI_C) {
        return (uint16_t)HW_OUTPUT_FULL_SCALE;
    }
    if (reading_milli_c >= CONTROL_BREW_SETPOINT_MILLI_C) {
        return 0u;
    }

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
    if (hw_output_set(HW_OUTPUT_BREW_HEATER, 0u)) {
        state->brew_heater_permille = 0u;
    }
    return reason;
}

bool control_init(control_state_t *state)
{
    if (state == NULL) {
        return false;
    }

    state->last_step_millis = hw_monotonic_millis();
    state->step_count = 0u;
    state->brew_heater_permille = 0u;
    state->started = false;
    state->faulted = false;

    return hw_output_set(HW_OUTPUT_BREW_HEATER, 0u);
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
        if (hw_output_set(HW_OUTPUT_BREW_HEATER, 0u)) {
            state->brew_heater_permille = 0u;
        }
        return CONTROL_STEP_FAULT_LATCHED;
    }

    const hw_reading_t brew = hw_sensor_read(HW_SENSOR_BREW_TEMPERATURE);
    if (!brew.valid) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    const uint16_t level = drive_level_for_reading(brew.value_milli);
    if (!hw_output_set(HW_OUTPUT_BREW_HEATER, level)) {
        return shut_down(state, CONTROL_STEP_OUTPUT_REFUSED);
    }

    state->brew_heater_permille = level;
    return CONTROL_STEP_ACTUATED;
}
