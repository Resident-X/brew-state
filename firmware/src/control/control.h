/*
 * The control-logic entry path.
 *
 * Every translation unit under src/control reaches hardware only through
 * hw_interface.h, includes no vendor header, and is compiled byte-identically
 * into both the host and the target build. The behaviour here is a minimal
 * path that exercises the seam's three operations end to end -- reading a
 * sensor, consulting the clock, driving an output -- because what this unit of
 * work establishes is separability, not control performance. The control law
 * and the state estimator are separate deliverables and do not live here yet.
 */
#ifndef CONTROL_H
#define CONTROL_H

#include <stdbool.h>
#include <stdint.h>

/* Brew temperature the skeleton drives toward, in millidegrees Celsius. */
#define CONTROL_BREW_SETPOINT_MILLI_C 93000

/* Shortest interval between two accepted steps, in milliseconds. */
#define CONTROL_STEP_INTERVAL_MS 10u

/* Why a step did not produce a fresh actuation. */
typedef enum {
    CONTROL_STEP_ACTUATED = 0,   /* the step ran and drove the heater */
    CONTROL_STEP_TOO_SOON,       /* the step interval had not elapsed */
    CONTROL_STEP_SENSOR_INVALID, /* the sensor could not be trusted */
    CONTROL_STEP_OUTPUT_REFUSED, /* the interface rejected the drive level */
    CONTROL_STEP_FAULT_LATCHED   /* an earlier step faulted and the heater stays off */
} control_step_result_t;

typedef struct {
    uint32_t last_step_millis;
    uint32_t step_count;
    uint16_t brew_heater_permille;
    bool started;
    bool faulted;
} control_state_t;

/*
 * Put the state into its pre-run condition and command the brew heater off, so
 * that a build which initialises but never steps still leaves the heater
 * de-energised. Returns false when the interface refuses that command.
 */
bool control_init(control_state_t *state);

/*
 * Advance the control path by one step. A step that finds an untrustworthy
 * sensor reading, or whose drive command is refused, commands the heater off
 * and latches the fault; a latched fault keeps the heater off on every
 * subsequent step. A null state is treated as a sensor-invalid step rather
 * than dereferenced.
 */
control_step_result_t control_step(control_state_t *state);

#endif /* CONTROL_H */
