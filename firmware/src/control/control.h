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
#include "protection_margin.h"
#include "pump_trim_declaration.h"

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
 * ceiling on a rate, then -- where a target is already named and the profile
 * states the drinking point -- the drinking-temperature window, then the
 * machine's authority against the draw asked for. A target is judged as
 * nothing-to-evaluate, then not-a-temperature, then the ceiling water itself
 * imposes, then the margin the protection trip point demands once it has been
 * widened for the declared model error, then -- where a delivery is already
 * running and its profile states the drinking point -- the same window, then
 * that same authority bound where a course is already running to be held
 * against.
 *
 * The protection margin is asked ahead of the window and the authority bound
 * for the reason the window is asked ahead of authority: it is a comparison
 * against figures the machine's own description already supplies, while
 * authority costs a settling probe of the plant model, and a command that fails
 * the cheaper question is refused without paying for the dearer one. It follows
 * saturation rather than preceding it because a target that is not liquid water
 * has failed a question about water, and reporting it as a protection margin
 * would send a reader to argue about a thermostat.
 *
 * The window is checked ahead of authority at both entry points because it
 * costs nothing to ask -- a comparison against two figures already in the
 * tolerance record -- while authority costs a plant model probe, and a
 * command that fails the cheaper question first is refused without paying
 * for the dearer one.
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
     * The least-capable plant the machine's declared error admits has not the
     * heater authority to hold the target against the draw the course asks for
     * at its peak. Established by probing the plant description -- see
     * control.c -- rather than by reading any coefficient of it by name, so the
     * bound follows whichever structure is linked instead of describing one of
     * them. The description's own point belief is not probed alone: every
     * coefficient with a path to this answer is also taken to its own corner by
     * its declared error, one at a time, combined by worst case on the same
     * terms the protection margin below is -- so `available` is the settled
     * figure the worst such corner reaches, not the point belief's.
     */
    CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY,
    /*
     * A delivery served at the drinking point names a target below the
     * declared drinking-temperature floor. Asked only of a delivery whose
     * profile states the drinking point -- an extraction gains nothing from
     * this bound and is judged on the others alone -- and only where both a
     * target and a drinking-point profile are known together, on the same
     * terms CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY already asks its
     * question of whichever of the two commands arrives second.
     */
    CONTROL_ADMISSION_TARGET_BELOW_DRINKING_FLOOR,
    /*
     * A delivery served at the drinking point names a target at or above the
     * declared drinking-temperature ceiling. Its own bound rather than a
     * second report of CONTROL_ADMISSION_TARGET_OVER_SATURATION, because the
     * two answer different questions: saturation is where water stops being
     * liquid on any machine, and the ceiling is the narrower point past which
     * this drink stops being one a person should be handed, on a machine that
     * may be perfectly capable of holding a target above it.
     */
    CONTROL_ADMISSION_TARGET_ABOVE_DRINKING_CEILING,
    /*
     * The target sits inside the margin that stands between a commanded
     * temperature and the hardware protection trip point, once that margin has
     * been widened for the error the machine's own description declares it may
     * be wrong by -- see protection_margin.h, and CONTROL_PROTECTION_TRIP_C in
     * control.c for the trip point itself.
     *
     * Its own bound rather than a second report of
     * CONTROL_ADMISSION_TARGET_OVER_SATURATION, on the same terms the drinking
     * ceiling is its own: saturation is where water stops being liquid on any
     * machine, and this is where a target stops leaving room for the model to
     * be as wrong as the description says it may be before a device that opens
     * on the truth removes the power. The two are unrelated figures and either
     * may be the tighter one on a given machine.
     *
     * `requested` carries the target asked for and `available` the trip point
     * less the margin sized for that target, so a caller is told what it may
     * ask for rather than only that it asked for too much. It is the highest
     * target this refusal leaves room for and not a fixed point of the
     * refusal: the margin follows the target, because a machine held higher
     * carries a larger load for the same declared error to be a fraction of,
     * so a target named at that figure is judged against its own, slightly
     * narrower margin when it arrives.
     */
    CONTROL_ADMISSION_TARGET_INSIDE_PROTECTION_MARGIN
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

/*
 * What a delivery has to say about how closely it followed the course it was
 * commanded.
 *
 * Two answers rather than one, because "no departure was seen" and "the rate
 * was never observed" are different states of knowledge and a single flag
 * cannot tell them apart. A machine with no meter fitted, or one whose meter
 * failed for the whole delivery, has observed nothing and must not report that
 * the delivery agreed with its command -- that would be asserting agreement
 * nobody measured, which is precisely the silence the reporting obligation
 * exists to prevent. So `rate_observed` says whether there was ever anything to
 * compare, and `departed` says what the comparison found.
 *
 * `largest_milli_ml_per_s` is the commanded rate less the measured one, so a
 * shortfall is positive -- the same sign convention the estimator uses for a
 * residual. It is the largest by distance from the command in either direction,
 * carrying its sign, so a delivery that ran under its course and a delivery
 * that ran over it are not reported as the same number. It and `at_millis` are
 * meaningful only when `departed` is set, and are zero otherwise: zero is a
 * legitimate elapsed time, so it is read against `departed` rather than on its
 * own, exactly as the admission bound's own `at_millis` asks to be read.
 *
 * It is latched for the life of the delivery and deliberately unlike the
 * estimator's residuals, which are forgotten at the top of every step so a
 * stale one is never mistaken for fresh. That is right for a correction signal
 * and wrong for an account of a delivery: what a delivery owes is an answer to
 * whether this shot followed what it was asked for, and that answer is not the
 * state of the last step.
 *
 * `driven_pump_permille` and `trim_saturated` are DEC-CORRECTION-KEEPS-THE-ACCOUNT's
 * addition to an account that otherwise stands as the departure slice built
 * it: the pump command is now trimmed closed-loop toward the commanded rate,
 * so knowing that a gap was seen is no longer enough to know what the machine
 * actually did about it. The two do not share one lifetime, though, and reading
 * either against the other's rule is a mistake.
 *
 * `driven_pump_permille` is deliberately not latched to the widest departure
 * the way `largest_milli_ml_per_s` and `at_millis` are: it is refreshed on
 * every valid reading a delivery judges, departed or not, and is meaningful
 * whenever `rate_observed` is set rather than only while `departed` is. That
 * is what a caller needs to tell apart a delivery whose trim closed the gap
 * back inside tolerance by the time it ends -- which reads `departed ==
 * false`, the same answer a delivery the trim never had anything to correct
 * also gives -- from one the trim never touched at all: it is the level the
 * trim had actually driven the pump to as of the most recent judged reading,
 * so the open-loop course alone driving a different level is visible even
 * where `departed` alone cannot show it.
 *
 * `trim_saturated` is latched on the same tolerance comparison `departed`
 * itself is -- meaningful only while `departed` is set, zero (false)
 * otherwise, exactly as `largest_milli_ml_per_s` reads -- because saturation
 * is a property of an actual departure and not of a course that merely
 * happens to peak at the pump's own bound with the seam still agreeing. It
 * says whether the trim was pinned at that bound, with the rate still beyond
 * tolerance, as of the most recent departing reading: a trim reaching the
 * limit and reporting nothing about it would fold "the puck asks more than
 * this machine can give" into an ordinary miss the operator has no way to
 * tell apart from one a little more correction would have closed. It is
 * refreshed on every departing reading rather than pinned to the widest one,
 * so a trim that recovers authority later in the same delivery is not left
 * reporting a saturation that has since ended.
 */
typedef struct {
    bool rate_observed;
    bool departed;
    int32_t largest_milli_ml_per_s;
    uint32_t at_millis;
    uint16_t driven_pump_permille;
    bool trim_saturated;
} control_departure_t;

/*
 * What a delivery has to say about rate it chose to give up, as distinct from
 * rate the world took from it.
 *
 * A yield is a departure from the commanded course made deliberately, by the
 * machine's own decision, and it is not allowed to hide behind having been
 * deliberate: control_departure_t above still judges this delivery against
 * the rate its profile commanded, unreduced, so a yielded delivery reports a
 * shortfall exactly as a choked path would. What this record adds is the
 * other half of the account -- that the shortfall was chosen and not merely
 * suffered -- because a caller told only the total cannot tell a machine that
 * decided from a world that intervened, and folding the two into one number
 * would have a failing pump and a correct yield report the same thing.
 *
 * The shape mirrors control_departure_t and is latched the same way and for
 * the same reason: `yielded` says whether this delivery ever gave anything up,
 * `largest_milli_ml_per_s` is the widest reduction it made from the rate its
 * course was commanding at the moment the reduction was largest, and
 * `at_millis` is the point on the course that was taken at. Both are
 * meaningful only while `yielded` is set and are zero otherwise, read against
 * it rather than on their own -- the same convention control_departure_t's
 * own fields already carry.
 */
typedef struct {
    bool yielded;
    int32_t largest_milli_ml_per_s;
    uint32_t at_millis;
} control_yield_t;

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
    /*
     * Accumulated trim intent, in the same permille the pump's own drive
     * level is expressed in -- mirrors integral_permille above, the same
     * conditional-integration discipline and the same reason it exists: it is
     * what removes the steady rate error the trim's proportional term alone
     * leaves standing. It does not share integral_permille's lifetime, though:
     * that term survives between deliveries because the heater is still
     * holding one temperature across the gap between them, while this one is
     * put back to nothing by forget_departure alongside the departure report
     * it feeds -- see pump_trim_command in control.c. A trim's accumulated
     * intent answers for the puck the delivery just finished pouring through,
     * and that puck is not the one the next delivery will meet; carrying the
     * intent forward would have a fresh shot start already trimmed for
     * somebody else's grounds.
     */
    float pump_trim_permille;
    /*
     * The declaration this instance was brought up against, held by value on
     * the same terms `tolerance` above is: no allocator exists to point at a
     * caller's copy instead, and a caller's copy is not promised to outlive
     * the call that handed it in.
     */
    pump_trim_declaration_t pump_trim;
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
     * What that same description says each of its coefficients may be wrong by,
     * held beside the description itself and for the same reason: the margin a
     * commanded target has to keep from the protection trip point is sized from
     * it, and a loop that had to be handed the figures again at every command
     * would be a loop whose margin could be sized against a different
     * description from the one it is driving.
     *
     * It is a separate record rather than part of the description above because
     * the plant seam keeps the two separate: a description says what the machine
     * is and this says how far out those figures may be, and most consumers of
     * the first want nothing to do with the second.
     */
    plant_parameter_budget_t budget;
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
     * A demand named while a point sharing a mass with `delivery` above was
     * already running, held rather than started -- see
     * control_command_delivery_reporting. Held by value for the reason
     * `delivery` itself is: no allocator exists to point at a caller's copy
     * instead. Meaningful only while `delivery_held` is set; a profile that
     * has since been started, or discarded when everything was commanded
     * off, is left in place rather than cleared, on the same terms `delivery`
     * itself is left in place once it finishes.
     */
    delivery_profile_t held_delivery;
    bool delivery_held;
    /*
     * How long the running delivery has been under way, advanced each step by
     * the same interval the estimator is advanced by -- see control_step --
     * so a step that arrived late advances both by the same honest amount
     * rather than the delivery running ahead of, or behind, the
     * reconstruction it is driving alongside.
     */
    uint32_t delivery_elapsed_millis;
    /*
     * How far ahead of delivery_elapsed_millis the drawn-load term reads this
     * delivery's course, in milliseconds -- established once, when the
     * delivery was admitted, against the machine's own description and the
     * course's own peak, and held fixed for the delivery's life. Meaningful
     * only while delivery_running is set, on the same terms delivery itself
     * is: a value left over from a finished delivery is never read, because
     * nothing reads either field once running has gone false.
     */
    uint32_t delivery_lead_millis;
    /*
     * The rate this delivery was commanding over the interval that has just
     * elapsed, and the point on its course that rate was taken from.
     *
     * A flow reading answers for the interval it was measured over, and the
     * command in force during that interval is the one issued on the step
     * before -- the same convention the estimator beside it already runs on,
     * where the model is advanced under the levels commanded over the interval
     * just gone while what is commanded next answers for the interval coming.
     * Comparing a measurement of one interval against the command for the next
     * would be an off-by-one: it reports a departure at the start of every
     * delivery, where the machine had not yet been asked for anything, and
     * leaves a standing error on any course whose rate is still moving. It
     * would also misalign the input and output records the plant model is to
     * be identified from, which is how a timing artefact becomes a coefficient
     * somebody defends.
     *
     * `delivery_rate_commanded` is false until one interval has elapsed under
     * this delivery's command, which is why the first step of a delivery
     * observes nothing rather than reporting the whole commanded rate as a
     * shortfall.
     */
    float delivery_commanded_rate_ml_per_s;
    uint32_t delivery_commanded_at_millis;
    bool delivery_rate_commanded;
    /*
     * What the running delivery has so far had to say about following its
     * course. Cleared when a delivery is commanded and when everything is
     * commanded off, and otherwise only ever added to -- see
     * control_departure_t for why it is latched rather than recomputed each
     * step, and control_delivery_departure for reading it.
     */
    control_departure_t departure;
    /*
     * The proportion of this step's commanded rate a running drinking-point
     * delivery is presently allowed to keep: one while nothing is being given
     * up, and less than one while the heater has no authority left and the
     * reconstruction sits below the drinking-temperature floor -- see
     * drinking_yield_fraction in control.c. Read back the same step it is
     * set, by drawn_load_pump_permille, so that the lead-ahead term answers
     * for the draw the machine is actually making rather than the one the
     * course asked for and this delivery has already stopped attempting.
     *
     * Meaningful only while delivery_running is set. It is put back to one
     * whenever a delivery is commanded or the machine is commanded off (see
     * forget_departure), but not when a delivery ends on its own end
     * condition -- the same value it last held stands until then. That is
     * harmless rather than stale, because every reader of this field is
     * itself gated on delivery_running: a caller reading it against a
     * machine with nothing running never reaches it at all.
     */
    float delivery_yield_fraction;
    /*
     * What the running delivery has so far had to say about rate it gave up
     * on its own account, as distinct from departure imposed by the world.
     * Cleared alongside departure and for the same reason -- see
     * control_yield_t for why it is latched, and control_delivery_yield for
     * reading it.
     */
    control_yield_t yield;
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
 * budget record travels beside the parameter record because it is the same
 * description read for something else -- how far out each of those figures may
 * be -- and it is required rather than optional: a loop that does not know what
 * its model may be wrong by cannot size the margin that stands between a
 * commanded target and a device that removes the power, and a margin sized
 * against an uncertainty nobody stated is one nobody can check. The
 * tolerance record travels the same way and for a different reason: it is not a
 * property of the machine at all, but of the drink, and the control path is
 * given it rather than compiling it in so that changing what a delivery is held
 * to is a change to a declaration rather than to this file. The pump trim
 * record travels the same way and for the same reason the tolerance does: it
 * is not a property of the machine either but a policy choice about how hard
 * the design leans on a rate gap, per DEC-CORRECTION-KEEPS-THE-ACCOUNT, and it
 * is required on exactly the terms the tolerance is. A trim declared nowhere
 * is not "no trim" -- there is no such thing as a delivery this loop drives
 * without a course to hold, so a null here would leave every delivery's pump
 * command uncorrected against a gap this loop already knows how to measure,
 * silently, which is precisely the absorption DEC-CORRECTION-KEEPS-THE-ACCOUNT
 * forbids.
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
 * record is given -- including no budget record -- or when the estimator
 * refuses the structure this build compiled. Those leave the fault latched as
 * an untrustworthy reading does: a control law that cannot obtain the
 * temperature it acts on must not drive the heater, and it must not start
 * driving it later either.
 */
bool control_init(control_state_t *state, const plant_parameters_t *parameters,
                  const plant_parameter_budget_t *budget, const estimator_limits_t *limits,
                  const delivery_tolerance_t *tolerance,
                  const pump_trim_declaration_t *pump_trim);

/*
 * The margin this instance requires between a commanded target and the
 * protection trip point, for a target it is asked about, and the enumeration
 * that margin came out of.
 *
 * A read rather than a figure a caller works out for itself, on the same terms
 * control_temperature_band is one: the margin the loop enforces is sized from
 * the description this instance was brought up with, and a caller computing its
 * own would be holding a machine to a figure the loop is not using. What comes
 * back is the whole account -- the un-widened gap, the worst corner, how many
 * corners were enumerated, how many ran and how many cost the gap anything --
 * so a record of the mapping is taken off the same computation the refusal is
 * taken off rather than off a second one beside it.
 *
 * It is asked about a target rather than answered once, because the margin
 * genuinely follows the target: what the loop commands to hold a temperature is
 * what a wrong coefficient acts through, and a machine held higher carries a
 * larger load for the same error to be a fraction of.
 *
 * Returns false, writing nothing, for a null state or destination, for a target
 * that is not a finite temperature, or where the description this instance
 * holds will not support an enumeration at all -- which is a structure whose
 * budget record was never loaded, and is not a margin of nothing.
 */
bool control_protection_margin(const control_state_t *state, float celsius,
                               protection_margin_t *margin);

/*
 * One corner of the enumeration that margin came out of, by its position in
 * that enumeration.
 *
 * The corners are what the figure above is the worst of, and a record of the
 * mapping from declared error to margin is a record of them: what each corner
 * moves, at what fraction, which end of it, whether it produced a machine at
 * all, and what it cost the gap. Read through this rather than recomputed by a
 * caller, so a record and the refusal it explains come off one enumeration.
 *
 * How many there are is protection_margin_corner_count of the budget this
 * instance holds, which a caller reaches by walking until this refuses.
 *
 * Returns false, writing nothing, on the same terms the figure above does, and
 * additionally for a position at or past the end of the enumeration.
 */
bool control_protection_margin_corner(const control_state_t *state, float celsius, size_t which,
                                      protection_margin_corner_t *corner);

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
 * to stop would be honouring an intent the caller has already withdrawn. That
 * is not the whole of it, though: a profile naming a different point that
 * shares a heated mass with the delivery already running is held rather than
 * replacing it, and the running delivery's own course is left entirely
 * untouched -- see control_command_delivery_reporting for where that
 * question is asked and control_delivery_held for reading a demand held this
 * way. It starts on its own, with nothing asked of the caller again, the
 * control step the delivery it contended with ends; see control_step. A
 * profile naming the same point already running shares that mass trivially
 * and is not this case: it is replaced immediately, exactly as before.
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
 * through has already spent the coffee and the operator's time. Both bounds
 * are permanent-infeasibility questions and are judged once, here, whether the
 * delivery starts immediately or is held first: a demand held for a mass to
 * free is a demand this machine can do, just not yet, and holding it asks a
 * different, transient question rather than repeating these two.
 *
 * A machine that is merely not there yet is admitted. Both bounds are asked of
 * where the description says the machine settles, not of the reconstruction it
 * is presently at, so a cold machine and one still recovering from the last
 * draw both start when nothing else is running. Until then such a delivery
 * runs and the departure report is the only account it gives.
 */
bool control_command_delivery(control_state_t *state, const delivery_profile_t *profile);

/*
 * Start a delivery, and be told which bound a refusal crossed.
 *
 * The reporting sibling of control_command_delivery on the same terms
 * control_command_temperature_reporting is that call's: the operation is
 * written once here, that one is this with the record discarded, and
 * `admission` may not be null. It is set to CONTROL_ADMISSION_OK on a demand
 * this machine can do, whether it starts now or is held because the mass it
 * names is given to the delivery already running.
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
 * Whether a demand commanded through control_command_delivery is presently
 * held for the mass it names to free, and which point the delivery it is
 * held against is serving.
 *
 * A demand is held rather than started when it names a different point
 * sharing a heated mass with the delivery already running -- see
 * control_command_delivery_reporting -- and it starts on its own, with
 * nothing asked of the caller again, the control step the delivery it
 * contended with ends: see control_step. For as long as it stays held, this
 * is the only account of it -- a demand that never starts still gives an
 * account of why, on the same reasoning control_delivery_departure reports a
 * delivery that ran rather than leaving a caller to infer one from silence.
 *
 * Only one demand is ever held at a time. A second contending demand
 * commanded while one is already held replaces it, on the same terms a
 * running delivery is replaced by a later command, and this reports whichever
 * one is presently waiting.
 *
 * Returns false, writing to neither destination, for a null state, a null
 * profile or point destination, or a machine with no demand presently held --
 * the same answer as "nothing is held" and safe for the same reason
 * control_delivery_running's own null case is: nothing is waiting for a state
 * that does not exist.
 */
bool control_delivery_held(const control_state_t *state, delivery_profile_t *held_profile,
                           plant_delivery_point_t *held_against);

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
 * How far a delivery asked for after a hot water draw may sit from the same
 * delivery asked for from rest, in millidegrees.
 *
 * Read back from the same record the band above is, and for the same reason: a
 * caller holding a pair of runs to a distance is holding them to the distance
 * the loop was given rather than to one it read out of a file for itself. It is
 * a separate figure rather than a reading of the band above, because the two
 * answer different questions -- how far one cup may be from what was ordered,
 * and how far two cups ordered the same way may be from each other -- and a
 * machine can meet either while failing the other.
 *
 * Returns false, writing nothing, for a null state or a null destination.
 */
bool control_post_draw_match_band(const control_state_t *state, int32_t *band_milli_c);

/*
 * Whether a delivery served at the point its profile names draws the same
 * heated mass the group draws.
 *
 * Asked of the plant seam, from the point the profile carries, rather than
 * compiled in from what the reference machine's plumbing does. Two deliveries
 * backed by one mass contend for stored energy, so one of them leaves the other
 * somewhere a rested machine does not describe and there is a recovery to
 * account for between them; two deliveries backed by separate masses do not,
 * and nothing is owed. Which of those a machine is, is a property of the
 * structure a build compiles and not of hot water -- a consumer that inferred
 * it from the channels a structure answers would be guessing from a vocabulary
 * that cannot express it.
 *
 * It takes the profile rather than the control state because the question is
 * about a delivery and about the machine this build compiled, and neither is a
 * property of an instance: the same profile put to the same build gets the same
 * answer whether a loop has been brought up or not.
 *
 * Returns false, writing nothing, for a null profile or destination, and for a
 * profile naming a point the linked structure does not serve -- a caller has to
 * be able to tell "this machine does not serve that point" from "that point does
 * not contend with the group", and answering the second for the first would be a
 * statement about contention on a machine that cannot make the delivery at all.
 */
bool control_delivery_contends_with_the_group(const delivery_profile_t *profile, bool *contends);

/*
 * What the delivery under way -- or the last one to run -- had to say about
 * following the course it was commanded.
 *
 * The report is latched across the whole delivery and survives its end, so a
 * caller asks this once the delivery has finished rather than having to watch
 * every step go by. A departure seen on one step and gone on the next is still
 * reported here, because a delivery that briefly stopped following its course
 * is a delivery that did not follow its course.
 *
 * It is cleared when the next delivery is commanded and when the machine is
 * commanded off, so what comes back always belongs to the delivery the caller
 * last asked for and never to the one before it.
 *
 * Reading it before any delivery has run reports nothing observed and nothing
 * departed, which is the honest answer: a machine that has moved no water has
 * measured no rate to compare.
 *
 * Returns false, writing nothing, for a null state or a null destination.
 */
bool control_delivery_departure(const control_state_t *state, control_departure_t *departure);

/*
 * What the delivery under way -- or the last one to run -- had to say about
 * rate it chose to give up, as distinct from control_delivery_departure's
 * account of rate the world took from it.
 *
 * Latched, cleared and read on exactly the terms control_delivery_departure
 * is: across the whole delivery, on the next delivery commanded or the
 * machine commanded off, and as nothing yielded for a machine that has moved
 * no water. Reading both together is what tells a caller a shortfall it sees
 * apart: the same one control_delivery_departure already reports if it was
 * chosen, or a different one entirely if it was not.
 *
 * Returns false, writing nothing, for a null state or a null destination.
 */
bool control_delivery_yield(const control_state_t *state, control_yield_t *yield);

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
 * because the feedforward it carries reads the delivery's own elapsed clock
 * and commanded rate in this same step -- a lead ahead of the clock while a
 * delivery is running -- and both have to be sitting there before either is
 * read, not after.
 *
 * A delivery ending its own course this way is also the step a demand held
 * for the mass it was drawing is started, if one is waiting: see
 * control_delivery_held. Nothing is asked of the caller to make that happen
 * -- the same step that notices the course has ended is the one that starts
 * what was waiting on it, on exactly the terms any other delivery is started
 * on, so its own elapsed course begins counting from this step and not from
 * whenever it was first commanded.
 *
 * A delivery does not outlive the machine driving it. Whenever this step
 * commands everything off -- nothing targeted, a refused drive command, or a
 * fault an earlier step already latched -- command_everything_off clears
 * delivery_running and its elapsed clock along with the outputs, so a
 * delivery is never left running against a machine that has stopped moving
 * water, and control_delivery_running answers false from that step on. A
 * demand held against the delivery just cleared is discarded there too,
 * rather than started: the mass it was waiting on did not free by that
 * delivery reaching its own end, and starting a new course onto a machine
 * that has just been told to stop would not be honouring the wait.
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
 *
 * A delivery served at the drinking point additionally has this step's
 * yield fraction established here, before the pump level it commands is
 * computed and before the heater command reads it through
 * drawn_load_pump_permille -- see drinking_yield_fraction in control.c for
 * the gate and delivery_yield_fraction's own comment for why it is read back
 * the same step it is set. The comparison judge_the_interval_just_elapsed
 * makes is unaffected: it stays the rate the profile commanded before any
 * reduction, so a yielded delivery reports its shortfall exactly as a choked
 * path would, and what was given up is reported separately -- see
 * control_yield_t.
 */
control_step_result_t control_step(control_state_t *state);

#endif /* CONTROL_H */
