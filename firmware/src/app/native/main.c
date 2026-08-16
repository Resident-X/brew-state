/*
 * Host entry point.
 *
 * This is what the tier-one analysis stage runs: it drives the control-logic
 * entry path against the simulated hardware implementation for a bounded
 * number of steps and exits, so that the memory and undefined-behaviour
 * analysis has a subject that actually executes the control path rather than
 * merely links it.
 *
 * It walks the paths the control logic can take -- an ordinary actuating step,
 * a step arriving before the interval has elapsed, a step finding an
 * untrustworthy reading, and a step whose drive command is refused -- because
 * a run that only ever takes the happy path leaves the others unanalysed.
 */
#include <stdio.h>

#include "control.h"
#include "hw_sim.h"

/* Steps to run in each phase of the exercise. */
#define EXERCISE_STEPS 64

static int failures;

static void expect(bool condition, const char *what)
{
    if (!condition) {
        (void)fprintf(stderr, "host exercise: %s\n", what);
        failures++;
    }
}

static void exercise_actuating_steps(control_state_t *state)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);

    for (int i = 0; i < EXERCISE_STEPS; i++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        expect(control_step(state) == CONTROL_STEP_ACTUATED, "an actuating step did not actuate");
    }
    expect(hw_sim_output(HW_OUTPUT_BREW_HEATER) > 0u, "the heater was never driven");
}

static void exercise_early_step(control_state_t *state)
{
    expect(control_step(state) == CONTROL_STEP_TOO_SOON, "a step inside the interval was accepted");
}

static void exercise_invalid_sensor(control_state_t *state)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    expect(control_step(state) == CONTROL_STEP_SENSOR_INVALID, "an invalid reading was accepted");
    expect(hw_sim_output(HW_OUTPUT_BREW_HEATER) == 0u, "the heater stayed on through a fault");
}

static void exercise_refused_output(void)
{
    control_state_t state;

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    (void)control_init(&state);
    hw_sim_set_output_refused(true);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    expect(control_step(&state) == CONTROL_STEP_OUTPUT_REFUSED, "a refused drive was reported as success");
}

int main(void)
{
    control_state_t state;

    hw_sim_reset();
    expect(control_init(&state), "the control path could not be initialised");

    exercise_actuating_steps(&state);
    exercise_early_step(&state);
    exercise_invalid_sensor(&state);
    exercise_refused_output();

    if (failures != 0) {
        (void)fprintf(stderr, "host exercise: %d expectation(s) unmet\n", failures);
        return 1;
    }

    (void)printf("host exercise: control path completed %u steps\n", state.step_count);
    return 0;
}
