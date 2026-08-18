/*
 * The control-logic entry path.
 *
 * Every translation unit under src/control reaches hardware only through
 * hw_interface.h, includes no vendor header, and is compiled byte-identically
 * into both the host and the target build. The behaviour here is a minimal
 * path that exercises the seam's three operations end to end -- reading a
 * sensor, consulting the clock, driving an output -- because what this unit of
 * work establishes is separability, not control performance. Tuning the control
 * law is a separate deliverable and does not live here yet.
 *
 * What it acts on is a reconstructed state rather than a reading. The sensor
 * that can be placed on this machine reports the mass being heated, and the
 * temperature that matters is the water leaving it; the estimator is what
 * stands between the two, so the control path reaches the hardware seam for its
 * output and reaches estimator.h for the temperature it drives toward.
 */
#ifndef CONTROL_H
#define CONTROL_H

#include <stdbool.h>
#include <stdint.h>

#include "estimator.h"

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
    /*
     * Held by value rather than pointed at, so that a caller brings the control
     * path up without an allocator -- which the target build does not have.
     */
    estimator_t estimator;
} control_state_t;

/*
 * Put the state into its pre-run condition and command the brew heater off, so
 * that a build which initialises but never steps still leaves the heater
 * de-energised.
 *
 * The parameter record is the one the estimator reconstructs from, carried in
 * through here rather than reached by a path of its own, so that the control
 * path and the state it acts on are brought up from the same description.
 *
 * Returns false when the interface refuses the off command, when no usable
 * record is given, or when the estimator refuses the structure this build
 * compiled. The last two leave the fault latched as an untrustworthy reading
 * does: a control law that cannot obtain the temperature it acts on must not
 * drive the heater, and it must not start driving it later either.
 */
bool control_init(control_state_t *state, const plant_parameters_t *parameters);

/*
 * Advance the control path by one step: the estimator is advanced under the
 * level commanded over the interval just elapsed and corrected toward what the
 * machine reports, and the drive level follows the temperature it reconstructs.
 *
 * A step that cannot obtain a trustworthy reconstruction, or whose drive
 * command is refused, commands the heater off and latches the fault; a latched
 * fault keeps the heater off on every subsequent step. A null state is treated
 * as a sensor-invalid step rather than dereferenced.
 */
control_step_result_t control_step(control_state_t *state);

#endif /* CONTROL_H */
