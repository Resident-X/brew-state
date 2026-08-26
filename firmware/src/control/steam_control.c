#include "steam_control.h"

#include <stddef.h>

#include "hw_interface.h"

bool steam_control_init(steam_control_state_t *state, const estimator_limits_t *limits,
                        const steam_control_declaration_t *declaration)
{
    if (state == NULL) {
        return false;
    }

    state->configured = false;

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

    const bool off = hw_output_set(ACTUATION_CHANNEL_STEAM_PUMP, 0u);

    /*
     * A gate with no threshold to withhold feed against, or no bounds to
     * judge a reading by, is refused after the outputs are commanded off,
     * not before, so the refusal leaves the machine unfed the way every
     * other refusal here does.
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

    const hw_reading_t reading = hw_sensor_read(HW_SENSOR_STEAM_PRESSURE);

    /*
     * Trustworthy on the same terms judge_the_interval_just_elapsed in
     * control.c already asks of a flow reading: obtained, and inside the
     * span this instance's own declared bounds admit for the channel. A
     * reading outside that span is arithmetically fine and physically
     * absurd, and withholding feed against one would be answering a
     * question about a machine no sensor is actually describing.
     */
    const bool trustworthy = reading.status == HW_READING_VALID &&
                             reading.value_milli >= state->limits.low_milli[HW_SENSOR_STEAM_PRESSURE] &&
                             reading.value_milli <= state->limits.high_milli[HW_SENSOR_STEAM_PRESSURE];

    /*
     * Feed is enabled only once a trustworthy reading has actually reached
     * the declared threshold. An untrustworthy reading reads as not ready
     * rather than as ready or as whatever the last trustworthy reading said:
     * this gate has no evidence the steam side has recovered, and starving a
     * draw is the softer failure the criterion this gate exists for is named
     * after.
     */
    const bool ready = trustworthy && reading.value_milli >= state->declaration.ready_pressure_milli_bar;

    /*
     * The specific rate fed once ready is not this gate's question -- it is
     * handed to the band-holding loop from here, which is free to command
     * anything from this point. Driven at the actuator's own full scale
     * rather than some intermediate figure, so a caller reading the channel
     * back sees feed plainly enabled rather than a duty that could be
     * mistaken for a tracking loop already running.
     */
    const uint16_t level = ready ? (uint16_t)ACTUATION_FULL_SCALE : 0u;

    if (!hw_output_set(ACTUATION_CHANNEL_STEAM_PUMP, level)) {
        return STEAM_CONTROL_STEP_OUTPUT_REFUSED;
    }

    return trustworthy ? STEAM_CONTROL_STEP_ACTUATED : STEAM_CONTROL_STEP_SENSOR_INVALID;
}
