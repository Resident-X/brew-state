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

#include "delivery_profile.h"
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
     *
     * Takes priority over CONTROL_STEP_DELIVERY_DEPARTED when both are true of
     * the same cycle: lateness is the pre-existing, more urgent signal, and a
     * caller must still learn of it even on a cycle whose flow also departed.
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
    CONTROL_STEP_NO_TARGET,
    /*
     * The step ran and drove the outputs, but the flow a running delivery is
     * actually moving sits further from the rate its profile is commanding
     * than the declared flow-departure band tolerates. It is its own result
     * rather than an actuated one for the same reason CONTROL_STEP_LATE is:
     * a delivery that has come apart from its course is a different outcome
     * from one that is tracking it, and a caller should learn that here
     * rather than from the cup. Departure does not stop the delivery -- it
     * keeps running to its own end condition, and this result is reported on
     * every cycle the gap stays outside the band, not only the first.
     *
     * Never returned when the flow reading is HW_READING_ABSENT or
     * HW_READING_FAILED: an unread channel is not evidence of departure, so a
     * cycle with nothing trustworthy to compare against reports whatever it
     * would have reported anyway.
     *
     * Yields to CONTROL_STEP_LATE when both are true of the same cycle: this
     * result is additive scope layered on top of an otherwise-ordinary cycle,
     * not a replacement for the pre-existing, more urgent lateness signal.
     */
    CONTROL_STEP_DELIVERY_DEPARTED
} control_step_result_t;

/*
 * Which bound a command crossed, or that it crossed none.
 *
 * These are bounds on what the machine can *ever* do, not on what it is doing
 * at the moment it is asked. A machine still cold, or still recovering from
 * the last draw, has crossed nothing: it will arrive, and refusing it would be
 * refusing a delivery that is merely early. What is named here is the set of
 * asks no amount of waiting satisfies.
 *
 * The order they are checked in is fixed rather than left to the
 * implementation, on the same terms the plant seam fixes the order of its step
 * faults: a command with more than one thing wrong with it names the same bound
 * every time. Each entry point states its own order, because the two ask
 * different questions. A delivery is judged as nothing-to-evaluate, then the
 * ceiling on a rate, then the machine's authority against the draw asked for. A
 * target is judged as nothing-to-evaluate, then not-a-temperature, then the
 * ceiling water itself imposes, then that same authority bound where a course
 * is already running to be held against.
 */
typedef enum {
    /* Nothing was crossed; the command was taken. */
    CONTROL_ADMISSION_OK = 0,
    /*
     * Nothing was handed in to judge: a null state, or a null profile where a
     * command required one. It is the caller's own mistake rather than anything
     * about the machine, which is why it is separate from the value below --
     * the two are repaired by different people from different sources, on the
     * same reasoning the parameter loader separates a damaged file from an
     * unaccounted figure.
     *
     * It is named for what is missing rather than for which argument was
     * missing. A target names no profile, so a value spelled "no profile given"
     * would be answering a question the temperature command was never asked;
     * and splitting it per argument would multiply values that no caller
     * responds to differently, since every one of them is the same bug in the
     * same calling code.
     */
    CONTROL_ADMISSION_NOTHING_GIVEN,
    /*
     * There is a caller and a course but no machine the pair could be judged
     * against: full pump scale draws nothing on the linked structure, so no
     * level asks for any commanded rate. It is the refusal
     * control_command_delivery has always answered with, given a name rather
     * than given a new meaning.
     */
    CONTROL_ADMISSION_NO_MACHINE_DESCRIBED,
    /* The value named as a target is not a temperature -- see is_a_temperature. */
    CONTROL_ADMISSION_NOT_A_TEMPERATURE,
    /*
     * The course asks, at some point along it, for water faster than full pump
     * scale draws on this machine. Used as a ceiling and only as a ceiling: a
     * rate above it is unreachable however the path downstream behaves, and a
     * rate below it is no promise at all about what a cup receives -- the puck,
     * the pump's flow-versus-pressure characteristic and the mechanical
     * pressure cap all sit between the two and none of them is represented.
     */
    CONTROL_ADMISSION_RATE_OVER_FULL_SCALE,
    /*
     * The target is at or above the temperature water boils at where this
     * machine stands. It is a bound this control path declares rather than one
     * the plant description discovers: the structures behind the seam carry no
     * phase change and will go on reporting liquid water well past boiling, so
     * a probe would call such a target reachable and would be right about the
     * model while being wrong about water.
     */
    CONTROL_ADMISSION_TARGET_OVER_SATURATION,
    /*
     * The machine has not the heater authority to hold the target against the
     * draw the course asks for at its peak. Established by probing the plant
     * description -- see control.c -- rather than by reading any coefficient of
     * it by name, so the bound follows whichever structure is linked instead of
     * describing one of them.
     */
    CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY
} control_admission_bound_t;

/*
 * What a command was refused for, and by how much.
 *
 * Answering only true or false tells an operator to guess. `requested` is the
 * figure the caller asked for and `available` the figure the machine has, both
 * in the unit of the bound named -- millilitres per second for the rate
 * ceiling, degrees Celsius for the two temperature bounds. Both are zero for a
 * bound that compares no pair of figures, and for CONTROL_ADMISSION_OK -- an
 * admitted command populates no figure at all, so a caller cannot read one off
 * a record that refused nothing. A value that is not a temperature is reported
 * as no figure rather than as itself, since a not-a-number written into
 * `requested` would be a figure nobody can compare or print.
 *
 * `at_millis` is the time on the course at which the bound was crossed. It is
 * meaningful only for a bound a course names a point for, and is zero
 * otherwise -- read it against `bound` rather than on its own, exactly as the
 * plant seam's step error asks its channel to be read, since zero is also a
 * legitimate point on a course.
 */
typedef struct {
    control_admission_bound_t bound;
    float requested;
    float available;
    uint32_t at_millis;
} control_admission_t;

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
    /*
     * What full pump scale draws on the machine this instance was brought up
     * against, in millilitres per second -- probed once, at control_init, and
     * kept here rather than asked of the plant seam on every step a delivery
     * is running. It is what turns a course's commanded rate into a permille
     * the pump can be driven at: dividing the rate by this figure and scaling
     * by full scale is the only place that conversion happens, so a delivery
     * profile never carries a flow figure of its own to disagree with it.
     *
     * Zero means the probe found nothing to divide by: a structure that draws
     * no water at full pump. control_command_delivery refuses to start a
     * delivery in that state rather than dividing by it, which is why nothing
     * downstream of this field has to check it again.
     */
    float full_scale_flow_ml_per_s;
    /*
     * The description this instance was brought up against, held by value on
     * the same terms the estimator above is: no allocator exists to point at a
     * caller's copy instead, and a caller's copy is not promised to outlive the
     * call that handed it in.
     *
     * It is kept because admission asks a question of the machine that the
     * flow figure above cannot answer on its own. What full pump scale draws is
     * one number and does not change; whether the heater can hold a given
     * target against a given draw is a different question for every pair a
     * caller names, so it is asked when the pair arrives rather than answered
     * once here. Asking it means standing a model up from this record, which
     * means having the record.
     *
     * The estimator beside it holds a copy of the same description and cannot
     * serve instead. That copy is inside its own model instance, which is
     * carrying the reconstruction the loop is driving from and must not be
     * stepped an hour forward to answer a question; and the seam offers no way
     * to read a description back out of a model, deliberately -- reaching into
     * one for its coefficients is exactly what the plant encapsulation check
     * refuses.
     *
     * What it describes is what the loop believes it is driving rather than the
     * machine on the bench -- the harness deliberately allows the two to
     * differ -- and admission is a judgement against the former, which is the
     * only thing available before anything moves.
     */
    plant_parameters_t parameters;
    /*
     * The delivery currently under way, held by value for the reason the
     * estimator above is: no allocator exists to point at one instead. It is
     * meaningful only while `delivery_running` is set; a profile copied in
     * and then finished is left in place rather than cleared, since nothing
     * reads it once running has gone false.
     */
    delivery_profile_t delivery;
    bool delivery_running;
    /*
     * How long the running delivery has been under way, advanced each step by
     * the same interval the estimator is advanced by -- see control_step --
     * so a step that arrived late advances both by the same honest amount
     * rather than the delivery running ahead of, or behind, the
     * reconstruction it is driving alongside.
     */
    uint32_t delivery_elapsed_millis;
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
 * What full pump scale draws on this machine is also established here, by
 * stepping a model of it -- built from the same parameter record, kept aside
 * for the purpose and discarded once read -- at full pump for one interval and
 * reading back what moved, through the plant seam's own quantity rather than a
 * coefficient reached for by name. It is asked once, here, rather than by
 * every step a delivery runs: the figure is a property of the compiled
 * structure and the record it was brought up with, neither of which changes
 * between steps, and asking the seam again on every one of them would be
 * paying for an answer this file already has. A structure that draws nothing
 * at full pump leaves the figure at zero, which is not treated as a fault of
 * initialisation -- a machine with no pump channel wired is not an
 * untrustworthy reading -- but is read by control_command_delivery as "no
 * delivery can be commanded", rather than divided by later.
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
 * Returns false, changing nothing, for a null state, for a temperature that is
 * not a finite number, and for one at or above the temperature water boils at
 * where this machine stands. That last is a delivery of steam rather than a
 * delivery of water however much authority the element has, and it is the one
 * ceiling here that is declared rather than probed -- see CONTROL_SATURATION_C
 * in control.c and its account in params/control.declaration. Whether the
 * machine can hold a target below it against a particular draw is a different
 * question, asked of the pair when a delivery names one.
 *
 * It is that pair, and not this call, that the machine's own authority is
 * asked about: a target alone names no draw, and the same target is reachable
 * at rest and out of reach under a draw.
 */
bool control_command_temperature(control_state_t *state, float celsius);

/*
 * Name the temperature, and be told which bound a refusal crossed.
 *
 * The same operation as control_command_temperature with the record kept
 * rather than discarded -- it is written once here and that one calls it --
 * on the terms the plant seam's reporting step already set. `admission` may
 * not be null, and is set to CONTROL_ADMISSION_OK on a target that is taken.
 * A caller given only true or false has to guess which ceiling it met; a
 * caller given this can say so.
 */
bool control_command_temperature_reporting(control_state_t *state, float celsius,
                                           control_admission_t *admission);

/*
 * Command the level the pump is to be driven at, in permille of full scale.
 *
 * This is the actuation-level entry point the heater feedforward reads in the
 * same step, and it stays that: what commands it now is ordinarily a running
 * delivery profile rather than a caller setting a held level directly, but the
 * signature, the refusal and the feed-forward reading of it are unchanged, and
 * every caller that held a level this way before goes on being able to.
 *
 * Calling this while a delivery is running is not refused, because refusing it
 * would be a change to what this function has always accepted, and there is a
 * defensible reading of what it does instead: the level it sets here holds
 * only until the delivery's own next step, which recomputes
 * commanded_pump_permille from the course and overwrites it -- so the caller
 * has, at most, borrowed the pump for the step in between. A caller that wants
 * to hold a level for longer than that has to stop the delivery first, which
 * is not a mechanism this file adds, because nothing about it needs one: a
 * later call to control_command_delivery simply replaces what is running.
 *
 * Returns false, changing nothing, for a null state or a level beyond full
 * scale. A level is not applied to the machine here -- it takes effect on the
 * next step, alongside the heater command it is fed forward into, so that the
 * two reach the machine together.
 */
bool control_command_flow(control_state_t *state, uint16_t pump_permille);

/*
 * Start a delivery, given as a profile.
 *
 * The profile is copied into the state by value, on the same reasoning every
 * other by-value member here is: no allocator exists to hold a pointer to a
 * caller's own copy instead. It begins with elapsed time at zero regardless of
 * anything a previous delivery reached, because a course is stated from its
 * own beginning and has no other beginning to resume from.
 *
 * A delivery already running is replaced rather than refused, on the same
 * terms control_command_temperature replaces a target already named: a caller
 * that names a new course meant to say what should be happening now, and a
 * control path that went on running the old one until some other call told it
 * to stop would be honouring an intent the caller has already withdrawn.
 *
 * Returns false, changing nothing, for a null state or profile, or when the
 * figure control_init probed for what full pump scale draws on this machine
 * was nothing -- a structure that draws no water at full pump has no level
 * that could ask for any commanded rate, and starting a delivery in that state
 * would leave every step dividing by a figure that is not there rather than
 * saying plainly that no delivery can be commanded.
 *
 * It also returns false, changing nothing, for a delivery beyond what this
 * machine can ever do: a course asking at any point for water faster than full
 * pump scale draws, or a target the heater has not the authority to hold
 * against the draw the course asks for at its peak. Both are judged before
 * anything is driven, because a delivery admitted and then abandoned part way
 * through has already spent the coffee and the operator's time.
 *
 * A machine that is merely not there yet is admitted. Both bounds are asked of
 * where the description says the machine settles, not of the reconstruction it
 * is presently at, so a cold machine and one still recovering from the last
 * draw both start -- which is deliberate, and is the case a later slice, the
 * one that defers a delivery until the heated mass is free, will own. Until
 * then such a delivery runs and the departure report is the only account it
 * gives.
 */
bool control_command_delivery(control_state_t *state, const delivery_profile_t *profile);

/*
 * Start a delivery, and be told which bound a refusal crossed.
 *
 * The reporting sibling of control_command_delivery on the same terms
 * control_command_temperature_reporting is that call's: the operation is
 * written once here, that one is this with the record discarded, and
 * `admission` may not be null. It is set to CONTROL_ADMISSION_OK on a delivery
 * that starts.
 *
 * The target's own ceiling is not re-asked here. A target at or above
 * saturation is refused where it is named, so no state a delivery is commanded
 * against can be carrying one, and asking again would be a second site of the
 * same judgement.
 */
bool control_command_delivery_reporting(control_state_t *state, const delivery_profile_t *profile,
                                        control_admission_t *admission);

/*
 * Whether a delivery commanded through control_command_delivery is still
 * running.
 *
 * A query rather than a value a caller reaches for on the state directly,
 * for the reason every other read here goes through a function: what counts
 * as running is this file's own bookkeeping -- set on control_command_delivery,
 * cleared by control_step the moment the end condition is met, and cleared the
 * same way whenever the machine is commanded off -- and a caller reading the
 * field itself would be reaching around the one place that bookkeeping is
 * kept honest.
 *
 * A machine that has been shut down, has just faulted, or has nothing
 * targeted has no outstanding delivery to resume, on the same reasoning it has
 * no held pump level to resume: command_everything_off clears this flag
 * alongside the outputs it drives to nothing. Without that, a delivery would
 * survive a latched fault and answer true for ever afterwards, or would go on
 * being timed against a machine that had stopped moving water, ending having
 * delivered nothing.
 *
 * Returns false for a null state, which is the same answer as "no delivery is
 * running" and is safe for the same reason: nothing is running for a state
 * that does not exist.
 */
bool control_delivery_running(const control_state_t *state);

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
 *
 * A running delivery's elapsed time is advanced here too, by the same interval
 * the estimator is advanced by rather than by the cadence the loop is meant to
 * run at, for the reason `advance` is computed that way in control.c: a late
 * step is a step over an interval that genuinely was longer, and a delivery
 * timed against the nominal cadence instead would end early or late by exactly
 * how late the loop had fallen. The end condition is evaluated against that
 * advanced figure, and a delivery whose condition is met on this step ends on
 * this step -- the pump commanded to zero -- rather than running on to see
 * whether some later step notices. This happens after the estimator has been
 * advanced, because what the delivery commands next has to answer for the
 * interval that is coming, not correct the one just gone; below the check for
 * a targeted machine, because a delivery only ever advances on a step that
 * actually drives the machine; and before the heater command is computed,
 * because the feedforward it carries reads commanded_pump_permille in this
 * same step, and a delivery's commanded rate has to be sitting there before
 * it is read, not after.
 *
 * A delivery does not outlive the machine driving it. Whenever this step
 * commands everything off -- nothing targeted, a refused drive command, or a
 * fault an earlier step already latched -- command_everything_off clears
 * delivery_running and its elapsed clock along with the outputs, so a
 * delivery is never left running against a machine that has stopped moving
 * water, and control_delivery_running answers false from that step on.
 *
 * On a step that advances a still-running delivery, the flow channel is read
 * and compared against the rate the course is commanding for that step. A gap
 * wider than the declared flow-departure band is reported through
 * CONTROL_STEP_DELIVERY_DEPARTED in place of the ordinary result; the
 * delivery is not ended or corrected by it, only reported. A reading that is
 * absent or failed is not compared against anything, on the same reasoning
 * the brew-temperature reconstruction is carried on prediction rather than
 * treated as evidence of a fault: no reading is not evidence of a departed
 * one.
 */
control_step_result_t control_step(control_state_t *state);

#endif /* CONTROL_H */
