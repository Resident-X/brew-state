/*
 * The control-logic entry path.
 *
 * Every translation unit under src/control reaches hardware only through
 * hw_interface.h, includes no vendor header, and is compiled byte-identically
 * into both the host and the target build.
 *
 * What it acts on is a reconstructed state rather than a reading. The sensor
 * that can be placed on this machine reports the mass being heated, and the
 * temperature that matters is the water leaving it; the estimator is what
 * stands between the two, so the control path reaches the hardware seam for its
 * outputs and reaches estimator.h for the temperature it drives toward. The two
 * are not a fixed offset apart -- how fast the water leaving the block follows
 * the block depends on how much water is being drawn through it -- which is why
 * closing the loop on the reading and trusting the water to follow would leave
 * an error the controller could not see, largest at exactly the moment a
 * delivery is under way.
 *
 * The loop is not reactive. On a block holding a few millilitres, the dip that
 * incoming water causes arrives faster than feedback can answer it, so the
 * level the pump is commanded at raises the heater command in the same step it
 * is commanded in rather than after the reconstruction has fallen. What the
 * loop is asked to deliver, and how far from it a delivery may sit, are inputs
 * rather than constants: a caller names the temperature it wants, and the band
 * it is held to is declared in params/tolerance.declaration.
 */
#ifndef CONTROL_H
#define CONTROL_H

#include <stdbool.h>
#include <stdint.h>

#include "delivery_tolerance.h"
#include "estimator.h"

/*
 * Shortest interval between two accepted steps, in milliseconds.
 *
 * This is the single site of the figure. Where it came from is accounted for in
 * params/cadence.declaration, and a check run as part of the build refuses a
 * second definition of it anywhere in the tree -- because a cadence figure
 * spelled in two places is one that stops agreeing with itself the first time
 * either is touched, silently, on exactly the timing question nobody re-reads.
 *
 * Whether ten milliseconds is short enough for the disturbances this machine
 * sees is a sufficiency question, and nothing here claims it is.
 */
#define CONTROL_STEP_INTERVAL_MS 10u

/*
 * How many step intervals may elapse before an arriving step is reported late
 * rather than treated as ordinary. Its single site, and accounted for beside
 * the interval it multiplies.
 */
#define CONTROL_STEP_LATE_MULTIPLE 3u

/* Why a step did not produce a fresh actuation. */
typedef enum {
    CONTROL_STEP_ACTUATED = 0,   /* the step ran and drove the outputs */
    CONTROL_STEP_TOO_SOON,       /* the step interval had not elapsed */
    CONTROL_STEP_SENSOR_INVALID, /* the estimator would not support the state acted on */
    CONTROL_STEP_OUTPUT_REFUSED, /* the interface rejected a drive level */
    CONTROL_STEP_FAULT_LATCHED,  /* an earlier step faulted and the outputs stay off */
    /*
     * The step ran and drove the outputs, having arrived later than the cadence
     * tolerates. It is its own result rather than an actuated one because an
     * estimate that arrives late is a different quantity from the one the
     * control law asked for, and a caller that has fallen behind should learn
     * it here rather than from the coffee. Being late is not a reason to stop
     * controlling, so the step is not refused.
     */
    CONTROL_STEP_LATE,
    /*
     * No temperature has been commanded, so there is nothing to drive toward.
     * The outputs are commanded off and the step is otherwise ordinary: the
     * estimator is still advanced, so a machine that is later given a target
     * starts from a reconstruction that has been following it all along rather
     * than from one that stopped when the last delivery ended.
     *
     * Its own result rather than a fault, because a machine between deliveries
     * is in an ordinary condition and a latched fault is not something a
     * caller can clear. Refusing a target the machine cannot reach is a
     * different answer to a different question and is not this one.
     */
    CONTROL_STEP_NO_TARGET
} control_step_result_t;

typedef struct {
    uint32_t last_step_millis;
    uint32_t step_count;
    uint16_t brew_heater_permille;
    /*
     * The level the pump is commanded at, and the level it was last actually
     * driven at. They are separate because the estimator is advanced over an
     * interval that has already passed, and what moved the machine over that
     * interval is what was driven during it -- not what a caller asked for
     * afterwards. Advancing the model under the newer figure would have it
     * reconstruct a draw that had not started.
     */
    uint16_t commanded_pump_permille;
    uint16_t driven_pump_permille;
    /*
     * The temperature the water reaching the coffee is being driven toward, and
     * whether one has been named. The flag is carried rather than a sentinel
     * temperature, because every value a float holds is either a temperature
     * somebody could mean or one the seam refuses, and neither is "nobody has
     * said yet".
     */
    float target_c;
    bool targeted;
    /*
     * Accumulated intent, in the same permille the drive level is expressed in.
     * It is what removes the steady error the proportional term alone leaves,
     * and it is the term the actuator limit is allowed to take away: see the
     * conditional integration in control.c.
     */
    float integral_permille;
    /* How far from the commanded temperature a delivery may sit. */
    delivery_tolerance_t tolerance;
    bool started;
    bool faulted;
    /*
     * Held by value rather than pointed at, so that a caller brings the control
     * path up without an allocator -- which the target build does not have.
     */
    estimator_t estimator;
} control_state_t;

/*
 * Put the state into its pre-run condition and command the outputs off, so that
 * a build which initialises but never steps still leaves the machine
 * de-energised.
 *
 * The parameter record is the one the estimator reconstructs from, and the
 * limits record is what that estimator will believe a reading to be, carried in
 * through here rather than reached by a path of their own, so that the control
 * path and the state it acts on are brought up from the same description. The
 * tolerance record travels the same way and for a different reason: it is not a
 * property of the machine at all, but of the drink, and the control path is
 * given it rather than compiling it in so that changing what a delivery is held
 * to is a change to a declaration rather than to this file.
 *
 * No temperature is commanded here. A machine that has just been brought up has
 * not been asked for a drink, and starting to drive toward a temperature nobody
 * named would be the control path deciding what the caller wanted.
 *
 * Returns false when the interface refuses an off command, when no usable
 * record is given, or when the estimator refuses the structure this build
 * compiled. The last two leave the fault latched as an untrustworthy reading
 * does: a control law that cannot obtain the temperature it acts on must not
 * drive the heater, and it must not start driving it later either.
 */
bool control_init(control_state_t *state, const plant_parameters_t *parameters,
                  const estimator_limits_t *limits, const delivery_tolerance_t *tolerance);

/*
 * Name the temperature the water reaching the coffee is to be driven toward.
 *
 * The target is state the caller sets rather than a constant this file carries,
 * so that a delivery says what it wants and two deliveries in one build can
 * want different things.
 *
 * Accumulated intent is not carried across a change of target: what it
 * accumulated was the error against the temperature that was asked for before,
 * and applying it to a new one would be the loop acting on a demand nobody is
 * making any more. The proportional and feedforward terms answer the new target
 * immediately, so nothing is lost but the wind-up.
 *
 * Returns false, changing nothing, for a null state or a temperature that is
 * not a finite number. Whether the machine can actually reach a finite target
 * is a different question, asked by work that does not exist yet; this refuses
 * only what is not a temperature at all.
 */
bool control_command_temperature(control_state_t *state, float celsius);

/*
 * Command the level the pump is to be driven at, in permille of full scale.
 *
 * This is what a delivery asks for, and the control path both drives it and
 * feeds it forward into the heater command. The second is the point: the water
 * a delivery draws is known at the moment it is commanded rather than
 * discovered as it arrives, and a loop that waited to see the temperature fall
 * would be answering a disturbance it had been told about in advance.
 *
 * Returns false, changing nothing, for a null state or a level beyond full
 * scale. A level is not applied to the machine here -- it takes effect on the
 * next step, alongside the heater command it is fed forward into, so that the
 * two reach the machine together.
 */
bool control_command_flow(control_state_t *state, uint16_t pump_permille);

/*
 * How far from the commanded temperature a delivery may sit, in millidegrees.
 *
 * Read back from the record the control path was brought up with rather than
 * from the file, so a caller holding a trajectory to a band is holding it to
 * the same band the loop was given. Two readers of one declaration can disagree
 * about it; a reader and the thing it is asking about cannot.
 *
 * Returns false, writing nothing, for a null state or a null destination.
 */
bool control_temperature_band(const control_state_t *state, int32_t *band_milli_c);

/*
 * Advance the control path by one step: the estimator is advanced under the
 * levels commanded over the interval just elapsed and corrected toward what the
 * machine reports, and the drive levels follow the temperature it reconstructs
 * and the flow that has been asked for.
 *
 * A step that cannot obtain a trustworthy reconstruction, or whose drive
 * command is refused, commands the outputs off and latches the fault; a latched
 * fault keeps them off on every subsequent step. A null state is treated as a
 * sensor-invalid step rather than dereferenced.
 *
 * A reading that is briefly absent or implausible is not on its own such a
 * step. The estimator carries the reconstruction on prediction for as long as
 * this machine's description says it may, and only its refusal to support the
 * state any longer brings the heater down -- so a single dropped sample is no
 * longer made indistinguishable from a burnt-out sensor.
 */
control_step_result_t control_step(control_state_t *state);

#endif /* CONTROL_H */
