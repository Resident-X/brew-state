#include "control.h"

#include <stddef.h>

#include "delivery_profile.h"
#include "estimator.h"
#include "hw_interface.h"
#include "plant_model.h"

/*
 * The three coefficients the law rests on. Each accounts for itself in
 * params/control.declaration, and a check run as part of the build refuses a
 * figure here that accounts for itself nowhere -- so a gain added beside these
 * during a tuning session cannot arrive as a bare number nothing asserts, which
 * is the shape a load-bearing figure takes just before everybody treats it as
 * settled.
 *
 * They are coefficients of the loop and not of any machine, which is why they
 * live here rather than in a plant description. A description says what a
 * particular casting is; these say what the design does about it, and they are
 * the same on every machine this software is compiled for.
 */

/*
 * Proportional gain: permille of full heater scale per kelvin of error.
 */
#define CONTROL_PROPORTIONAL_PERMILLE_PER_K 30.0f

/*
 * Integral gain: permille of full heater scale per kelvin of error per second.
 */
#define CONTROL_INTEGRAL_PERMILLE_PER_K_PER_S 0.35f

/*
 * The temperature the machine draws its water and its air from, in degrees
 * Celsius. What the loop has to supply is the cost of lifting the delivery
 * above this, so it is the origin the two load coefficients below are measured
 * from rather than a temperature the loop ever drives toward.
 */
#define CONTROL_COLD_REFERENCE_C 20.0f

/*
 * What the machine loses to the room, in permille of full heater scale per
 * kelvin of rise above the cold reference.
 */
#define CONTROL_STANDING_PERMILLE_PER_K 1.2f

/*
 * What the drawn water carries away, in permille of full heater scale per
 * kelvin of rise above the cold reference, per permille of commanded pump
 * level.
 */
#define CONTROL_DRAWN_PERMILLE_PER_K_PER_PUMP_PERMILLE 0.02905f

/*
 * The two figures admission rests on. They account for themselves beside the
 * coefficients above and are separated from them because they are not
 * coefficients of the control law: neither is multiplied by an error or added
 * to a duty. One is a statement about what a delivery of water means and the
 * other is how a question is put to the plant seam, and a reader challenging
 * either is challenging something different from a gain.
 */

/*
 * The temperature water boils at where this machine stands, in degrees Celsius.
 * It is declared here rather than read through the plant seam because the
 * structures carry no phase change and the figure they do carry sits on the
 * steam side of a record this file may not read by name.
 */
#define CONTROL_SATURATION_C 100.0f

/*
 * How far forward a model is stepped to arrive at where it settles, in
 * milliseconds. One step and not a sequence of them: the structures integrate
 * an interval exactly rather than by small forward steps.
 */
#define CONTROL_SETTLING_INTERVAL_MS 3600000u

/*
 * The three figures the read-ahead lead probe rests on. Like the two above,
 * neither is a coefficient of the control law: none is multiplied by an error
 * or added to a duty, and all three answer a question about how the probe puts
 * its question to the plant seam rather than about what the loop does with the
 * answer.
 */

/*
 * The artificial gap the probe parts the heated mass and the water on its way
 * to the group by, in degrees Celsius, before reading how fast it closes.
 */
#define CONTROL_LEAD_PROBE_OFFSET_C 10.0f

/*
 * The fraction of that gap still outstanding once the probe calls it closed --
 * the ordinary definition of a first-order system's own time constant, and not
 * one this file declares for itself.
 */
#define CONTROL_LEAD_PROBE_CLOSED_FRACTION 0.367879441f

/*
 * How long the probe is willing to go on stepping before it gives up and
 * answers with no lead, in milliseconds.
 */
#define CONTROL_LEAD_PROBE_MAX_MS 60000u

/*
 * The one figure the drinking-point yield rests on: how far the commanded
 * rate backs off, in permille of itself, per kelvin the reconstructed
 * temperature sits below the drinking-temperature floor. It accounts for
 * itself beside the coefficients above rather than in a plant description,
 * on the same footing they do: it states what the design does about a
 * machine that has run out of heater authority, not what any casting is, and
 * it is the same figure on every structure this software is compiled
 * against.
 *
 * It is not a coefficient of heater_command's own law: nothing here is added
 * to a duty or multiplied by an error. It answers a different question --
 * how much of the commanded rate a delivery still gets to keep -- which is
 * why it is separated from the loop's coefficients on the same terms
 * CONTROL_SATURATION_C and CONTROL_SETTLING_INTERVAL_MS already are.
 *
 * At this figure the rate reaches nothing four degrees below the floor --
 * see drinking_yield_fraction's own clamp. That is read here rather than
 * discovered there: a machine that far outside what it can sustain has
 * nothing left to trade the cup for, and a stopped delivery is the safer
 * failure than one that goes on moving water further from what was asked
 * for. See the account in params/control.declaration for where the figure
 * itself came from.
 */
#define CONTROL_YIELD_PERMILLE_PER_K_BELOW_FLOOR 250.0f

/*
 * What was commanded over the interval just elapsed, for the estimator to
 * advance under.
 *
 * The pump level belongs in here as much as the heater's does. Without it the
 * model is advanced as though the machine were still while water was moving
 * through it, and the state no sensor observes -- the temperature of the water
 * on its way to the group -- drifts from the machine exactly when a delivery is
 * under way. That is the failure this loop exists to prevent, arriving through
 * the back door of the model rather than through the control law.
 */
static plant_actuation_t commanded_actuation(const control_state_t *state)
{
    plant_actuation_t commanded = {{0u}};

    commanded.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = state->brew_heater_permille;
    commanded.level_permille[ACTUATION_CHANNEL_PUMP] = state->driven_pump_permille;
    return commanded;
}

/*
 * Whether a value is a temperature at all -- neither a not-a-number nor an
 * unbounded one.
 *
 * Written out rather than asked of the standard library's isfinite, which is a
 * macro that expands to a different implementation-reserved name on a host and
 * on the target. The control logic is required to be byte-identical across the
 * two and a check run as part of the build compares them, so a macro that
 * expands differently is a difference in the control logic however identical
 * the source reads. Everything outside src/control is free to use it, and does.
 *
 * The first comparison refuses a not-a-number, which compares equal to nothing
 * including itself. The second refuses either infinity, whose difference from
 * itself is a not-a-number rather than nothing.
 *
 * It rests on the build not telling the compiler that neither case can arise.
 * Under -ffinite-math-only, or the -Ofast that implies it, both comparisons are
 * licensed to fold to true and the refusal disappears without a diagnostic --
 * which would be a silent hole rather than a loud one. No environment in this
 * project passes either flag, and a build that started to would be asserting
 * something about this machine's arithmetic that nothing has established.
 */
static bool is_a_temperature(float celsius)
{
    return (celsius == celsius) && ((celsius - celsius) == 0.0f);
}

/* Narrow a command in permille to what the actuator can be given. */
static uint16_t as_drive_level(float permille)
{
    /*
     * Written as a negated comparison so that a command that is not a number
     * lands at nothing rather than somewhere in range. A reconstruction that is
     * not finite is refused at the seam and never reaches the arithmetic above,
     * but the guard costs a branch and removes the whole class.
     */
    if (!(permille > 0.0f)) {
        return 0u;
    }
    if (permille >= (float)ACTUATION_FULL_SCALE) {
        return (uint16_t)ACTUATION_FULL_SCALE;
    }

    /* In range by construction, and positive, so the rounding needs no branch. */
    return (uint16_t)(permille + 0.5f);
}

/*
 * The pump level the drawn-load term is scaled by for this step.
 *
 * A running delivery's course is read a lead ahead of where the delivery
 * actually is, rather than at the elapsed time the pump is actually being
 * driven at this step -- and averaged across the stretch the lead spans
 * rather than sampled only at its far edge, because everything the course
 * does between here and there is water this step's duty answers for. A
 * course that is flat across that stretch reads the same either way; a
 * course still rising or falling across it does not, and a point taken only
 * at the far edge answers for a rate the course has not carried for most of
 * the stretch. See delivery_profile_read_ahead_rate_ml_per_s, which also
 * carries why the stretch is cut short at the delivery's own end rather than
 * read past it. The lead itself is the one probe_read_ahead_lead_millis
 * established when the delivery was admitted and does not move as the course
 * runs, so it is read from the state rather than probed again here.
 *
 * A machine with no delivery running has no course to read ahead of: what
 * commands the pump is a level a caller set directly, which carries no future
 * for a lead to be taken against, so the level fed to the term is the one
 * presently commanded -- the same read this file always made before this
 * term existed.
 *
 * The rate read ahead is scaled by delivery_yield_fraction, established for
 * this same step before heater_command is called -- see control_step. A
 * delivery giving nothing up reads back a fraction of one and this is the
 * read it has always been; a delivery presently yielding has the same
 * reduction in force applied here as at the pump, so the term answers the
 * draw the machine will actually be making rather than the one the course
 * asked for and the delivery has already stopped attempting. It is a
 * proportion of the rate read ahead rather than the absolute reduction
 * subtracted from it, because the two agree only where the course is flat
 * and part on every ramp: carrying a proportion forward is what keeps the
 * scaling honest on a course that is still rising or falling across the
 * lead.
 */
static uint16_t drawn_load_pump_permille(const control_state_t *state)
{
    if (!state->delivery_running) {
        return state->commanded_pump_permille;
    }

    const float rate_ml_per_s = delivery_profile_read_ahead_rate_ml_per_s(
        &state->delivery, state->delivery_elapsed_millis, state->delivery_lead_millis);
    const float yielded_rate_ml_per_s = rate_ml_per_s * state->delivery_yield_fraction;
    const float permille =
        (yielded_rate_ml_per_s / state->full_scale_flow_ml_per_s) * (float)ACTUATION_FULL_SCALE;
    return as_drive_level(permille);
}

/*
 * The proportion of a running delivery's commanded rate this step still gets
 * to keep.
 *
 * One while nothing is being given up, which is every extraction and every
 * hot water delivery that has not run out of authority. Less than one only
 * where two conditions are both true, neither sufficient alone: the heater
 * driven on the step just gone was at full scale, and the reconstruction is
 * below the drinking-temperature floor. A delivery merely on its way up, with
 * duty still short of the limit, keeps the rate its course states -- giving
 * up the operator's time there would buy nothing, since both can still be
 * met.
 *
 * The heater level read is the one this file actually drove on the previous
 * step (state->brew_heater_permille), not a level computed fresh here. The
 * level this step is about to drive depends on the pump command this
 * function itself feeds into by way of drawn_load_pump_permille, so asking
 * "is the heater at full scale" of a figure not yet computed would be
 * circular; reading the step before is the same convention control_step
 * already reads a delivery's departure against the command issued the step
 * before, and one control step of latency is not a meaningfully different
 * gate than an instantaneous one at this loop's cadence.
 *
 * The reduction follows the distance below the floor rather than switching
 * between two rates, through the one coefficient CONTROL_YIELD_PERMILLE_PER_K_BELOW_FLOOR
 * accounts for itself with, and it is recomputed fresh every step rather than
 * latched: a delivery that dipped once and came back is not slowed for the
 * rest of its course, because nothing here remembers the dip once the
 * reconstruction is back inside the window.
 *
 * Applies only to a delivery served at the drinking point. An extraction's
 * course is its recipe, held to its commanded rate by the brew criterion
 * rather than this one, and reading this of a machine with no delivery
 * running at all is meaningless -- the caller only ever asks while
 * delivery_running is set.
 */
static float drinking_yield_fraction(const control_state_t *state, float reconstruction_c)
{
    if (state->delivery.served_at != PLANT_DELIVERY_POINT_HOT_WATER_SPOUT) {
        return 1.0f;
    }
    if (state->brew_heater_permille < (uint16_t)ACTUATION_FULL_SCALE) {
        return 1.0f;
    }

    const float floor_c = (float)state->tolerance.drinking_floor_milli_c / 1000.0f;
    if (!(reconstruction_c < floor_c)) {
        return 1.0f;
    }

    const float shortfall_k = floor_c - reconstruction_c;
    const float reduction = (CONTROL_YIELD_PERMILLE_PER_K_BELOW_FLOOR * shortfall_k) / 1000.0f;
    const float fraction = 1.0f - reduction;

    /*
     * A shortfall past the point this coefficient reduces to nothing at is
     * not clamped to some smallest trickle: the commanded rate reaches zero
     * and stays there for as long as the shortfall does. That is a
     * deliberate reading of "has nothing left to trade" rather than an
     * unconsidered edge -- a machine this far outside what it can sustain
     * gains nothing from continuing to move water further from the window
     * than it already is, and a delivery held at zero still reports what it
     * gave up through control_yield_t exactly as a smaller reduction would.
     */
    if (!(fraction > 0.0f)) {
        return 0.0f;
    }
    return fraction;
}

/*
 * The heater command for one step, and the accumulated intent it leaves behind.
 *
 * The feedforward term is added before the loop looks at the error rather than
 * after, because it answers a load the machine has been told about: the pump
 * level is what a delivery asked for, and the energy the water it moves will
 * carry away is known at that moment rather than discovered once the
 * temperature has fallen. On a block holding a few millilitres the fall arrives
 * faster than any feedback term could answer it, so a loop without this is a
 * loop that is always apologising.
 *
 * It carries the standing loss as well as the drawn one. The two are separate
 * figures because they answer to different things -- one moves with the flow
 * commanded and the other does not -- and together they are what the machine
 * needs when it is doing what it was asked to do. Leaving either to the error
 * term would make the loop earn the whole steady load through an error large
 * enough to command it, which is a loop that only reaches the temperature it
 * was asked for by first being wrong about it.
 *
 * Both are measured per kelvin of rise above the temperature the machine draws
 * from, and are scaled here by the rise the commanded target actually asks for.
 * That is what keeps this a feedforward rather than a calibration: a pair of
 * figures fixed at one brew temperature would answer the whole load exactly
 * there and be wrong everywhere else, by an amount growing with the distance
 * from it, and the residue would fall to an integral slow enough that a shot
 * would end before it had trimmed half of it. Since the target became something
 * a caller names rather than a constant, "everywhere else" is where the machine
 * now spends its time.
 *
 * Integration is made conditional on the actuator rather than unwound after the
 * fact. Full duty is this machine's ordinary condition and not an exception --
 * a cold start, a long draw, a machine recovering between shots all sit there --
 * so the limit is where the loop spends much of its working life, and intent
 * accumulated across it would arrive as an overshoot once the demand ended,
 * long after the interval that produced it. The test of the arrangement is not
 * that a saturated interval produces no overshoot but that a longer one
 * produces no more of it: an integrator that merely unwinds fast passes the
 * first and fails the second.
 *
 * The condition is asked of the command the loop would issue before this step's
 * accumulation, and of the direction the error would push it: intent is
 * surrendered only while the actuator is already at a limit and the error would
 * drive it further past. An error pointing back into range still integrates, so
 * the loop leaves saturation on the step the machine does rather than some
 * steps later.
 */
static float heater_command(control_state_t *state, float reconstruction_c, float interval_s)
{
    const float error_k = state->target_c - reconstruction_c;
    const float proportional = CONTROL_PROPORTIONAL_PERMILLE_PER_K * error_k;

    /*
     * A target at or below the temperature the machine draws from costs nothing
     * to hold, and a negative rise would have the feedforward asking for less
     * than no heat. Taken at nothing rather than allowed through, so the term
     * answers a load rather than becoming a second, inverted controller.
     */
    const float rise_k = (state->target_c > CONTROL_COLD_REFERENCE_C)
                             ? (state->target_c - CONTROL_COLD_REFERENCE_C)
                             : 0.0f;
    const float feedforward =
        rise_k * (CONTROL_STANDING_PERMILLE_PER_K +
                  (CONTROL_DRAWN_PERMILLE_PER_K_PER_PUMP_PERMILLE *
                   (float)drawn_load_pump_permille(state)));

    const float before = proportional + state->integral_permille + feedforward;
    const bool pushing_past_full = (before >= (float)ACTUATION_FULL_SCALE) && (error_k > 0.0f);
    const bool pushing_past_off = (before <= 0.0f) && (error_k < 0.0f);

    if (!pushing_past_full && !pushing_past_off) {
        state->integral_permille += CONTROL_INTEGRAL_PERMILLE_PER_K_PER_S * error_k * interval_s;
    }

    return proportional + state->integral_permille + feedforward;
}

/*
 * Command every output off.
 *
 * The pump goes off with the heater rather than being left where it was. A
 * control path that has stopped driving the heater and gone on moving water is
 * pushing the feed temperature through the group, which is both the wrong drink
 * and a machine doing something nobody asked it to; and the case this is
 * reached from is one where the temperature the water is at is no longer
 * known.
 *
 * Each recorded level follows what the interface accepted rather than what was
 * asked for: if an off command is itself refused -- which is exactly the
 * condition that produced an output-refused step -- that output is still at its
 * previous level, and recording zero would state it is off when nothing
 * established that.
 */
/*
 * Round a signed figure in thousandths to the whole thousandth, away from zero.
 *
 * Written without the standard library's rounding for the reason as_drive_level
 * above is: this translation unit is compiled byte-identically for the host and
 * the target, and reaching for math.h reaches a different implementation on
 * each. Away from zero rather than toward it, so a gap is never reported as
 * smaller than it was -- rounding a departure down toward the band is the one
 * direction that could quietly bring a reportable gap inside it.
 */
static int32_t as_milli(float value)
{
    return (int32_t)(value >= 0.0f ? value + 0.5f : value - 0.5f);
}

/*
 * Forget what the last delivery had to say about following its course, and
 * about rate it gave up on its own account.
 *
 * A report belongs to one delivery. Carrying it into the next would have a
 * machine answer for a shot that has already been poured, and the caller has no
 * way to tell that from the shot it is actually asking about. The yield
 * fraction is put back at one alongside the reports it feeds -- see
 * delivery_yield_fraction's own comment -- so a machine with nothing running
 * reads no yield in force rather than a value left over from the last one.
 */
static void forget_departure(control_state_t *state)
{
    state->delivery_commanded_rate_ml_per_s = 0.0f;
    state->delivery_commanded_at_millis = 0u;
    state->delivery_rate_commanded = false;
    state->departure.rate_observed = false;
    state->departure.departed = false;
    state->departure.largest_milli_ml_per_s = 0;
    state->departure.at_millis = 0u;
    state->delivery_yield_fraction = 1.0f;
    state->yield.yielded = false;
    state->yield.largest_milli_ml_per_s = 0;
    state->yield.at_millis = 0u;
}

/*
 * Compare what the meter says moved over the interval just elapsed against the
 * rate this delivery was commanding during it, and fold any departure into the
 * delivery's report. Answers whether this step departed.
 *
 * The reading is taken on every step a delivery runs, which is what makes the
 * control unit a reader of the seam rather than of its own commands. It is used
 * only when the seam marks it trustworthy and its value lies inside the
 * plausible span the description declares for the channel: a disconnected or
 * shorted meter produces figures that are arithmetically fine and physically
 * absurd, and reporting one as departure would have the machine give an account
 * of a rate it never plausibly saw -- a very large one at that, which would
 * then stand as the worst departure the delivery ever showed.
 *
 * Nothing is judged until one interval has elapsed under this delivery's
 * command. On the first step there is no such interval: the meter is reporting
 * what moved before the delivery was asked for anything, and comparing the new
 * command against it would report the whole commanded rate as a shortfall on
 * every delivery ever run.
 */
static bool judge_the_interval_just_elapsed(control_state_t *state)
{
    const hw_reading_t flow = hw_sensor_read(HW_SENSOR_FLOW);

    if (!state->delivery_rate_commanded) {
        return false;
    }
    if (flow.status != HW_READING_VALID ||
        flow.value_milli < state->estimator.limits.low_milli[HW_SENSOR_FLOW] ||
        flow.value_milli > state->estimator.limits.high_milli[HW_SENSOR_FLOW]) {
        return false;
    }

    /*
     * That the rate was observed at all is recorded separately from what the
     * observation found. A delivery nobody measured must not come back
     * reporting that it followed its course: it would be asserting agreement
     * never observed, which reads exactly like a delivery that went perfectly.
     */
    state->departure.rate_observed = true;

    /*
     * Commanded less measured, so a shortfall is positive -- the sign
     * convention the estimator already uses for a residual. The subtraction is
     * the whole mechanism: departure is observed by measuring what moved rather
     * than reproduced by modelling what resisted it, so there is no filter
     * here, no term for the puck, and nothing for anybody to tune.
     */
    const float commanded_milli_ml_per_s = state->delivery_commanded_rate_ml_per_s * 1000.0f;
    const int32_t gap = as_milli(commanded_milli_ml_per_s - (float)flow.value_milli);
    const int32_t gap_magnitude = gap < 0 ? -gap : gap;

    if (gap_magnitude <= state->tolerance.flow_departure_band_milli_ml_per_s) {
        return false;
    }

    /*
     * The widest gap this delivery has shown is what it is reported by, kept
     * with its sign so a delivery that ran under its course is not reported as
     * one that ran over it. Compared by distance from the command because the
     * band is a half-width and either direction is a departure. The time
     * reported is the point on the course the departed command was taken from,
     * not the step the reading arrived on -- the reading answers for that
     * earlier interval.
     */
    const int32_t largest = state->departure.largest_milli_ml_per_s;
    const int32_t largest_magnitude = largest < 0 ? -largest : largest;
    if (!state->departure.departed || gap_magnitude > largest_magnitude) {
        state->departure.largest_milli_ml_per_s = gap;
        state->departure.at_millis = state->delivery_commanded_at_millis;
    }
    state->departure.departed = true;
    return true;
}

static void command_everything_off(control_state_t *state)
{
    if (hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u)) {
        state->brew_heater_permille = 0u;
    }
    if (hw_output_set(ACTUATION_CHANNEL_PUMP, 0u)) {
        state->driven_pump_permille = 0u;
    }

    /*
     * What was asked for is forgotten along with what was driven. A machine
     * brought down, or standing between deliveries, has no outstanding request
     * to resume: leaving the last delivery's flow here would have the pump
     * start again at that level the moment a temperature was next commanded,
     * which is water moving because of something the caller asked for minutes
     * ago and has not repeated.
     *
     * A running delivery is exactly such an outstanding request, and is ended
     * here alongside it rather than left to go on counting. Every path that
     * reaches this function -- shutting down, a fault latching, and a step
     * with nothing targeted -- is a machine that has stopped driving water, so
     * a delivery still marked running past this point would burn the rest of
     * its course against the clock while nothing moved, and report itself
     * finished having delivered nothing.
     */
    state->commanded_pump_permille = 0u;
    state->delivery_running = false;
    state->delivery_elapsed_millis = 0u;
    state->delivery_lead_millis = 0u;
    forget_departure(state);

    /*
     * A demand held against the delivery just cleared has nothing left to
     * wait for. The mass it was waiting on did not free by the delivery it
     * contended with reaching its own end -- it was taken away from under it
     * by whatever commanded everything off -- and starting a new course onto
     * a machine that has just been told to stop would be exactly the
     * outstanding request this function exists to clear, on the same
     * reasoning the running delivery above is cleared rather than left to
     * count on. The resume such a demand is owed happens only where a
     * delivery reaches its own end, in control_step, and not here.
     */
    state->delivery_held = false;
}

/* Latch the fault and command the outputs off. */
static control_step_result_t shut_down(control_state_t *state, control_step_result_t reason)
{
    state->faulted = true;
    command_everything_off(state);
    return reason;
}

/*
 * What full pump scale draws on the machine a parameter record describes, in
 * millilitres per second.
 *
 * Asked through the plant seam's own vocabulary -- a model of this machine
 * kept aside, stepped once at full pump, and read back for what it says is
 * moving -- rather than by reaching for the structure's coefficient by name.
 * A coefficient named here would tie this file to the thermoblock's own
 * spelling of it, which is exactly what the plant encapsulation check refuses
 * of every consumer under src/control and src/delivery: the next structure
 * this software is compiled against may not call the same figure the same
 * thing, or may not carry it as a single coefficient at all, and this file
 * has to go on working against it unchanged.
 *
 * Zero is the honest answer for a record that fails to initialise a model, a
 * step that is refused, or a structure that genuinely draws nothing at full
 * pump -- and it is left for the caller to decide what a figure of nothing
 * means, rather than this function treating any of those as its own fault.
 */
static float probe_full_scale_flow_ml_per_s(const plant_parameters_t *parameters)
{
    plant_model_t probe;
    plant_actuation_t everything = {{0u}};
    float flow = 0.0f;

    if (!plant_model_init(&probe, parameters)) {
        return 0.0f;
    }

    everything.level_permille[ACTUATION_CHANNEL_PUMP] = (uint16_t)ACTUATION_FULL_SCALE;
    if (!plant_model_step(&probe, &everything, 0.0f, CONTROL_STEP_INTERVAL_MS)) {
        return 0.0f;
    }
    if (!plant_model_quantity(&probe, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &flow) || !(flow > 0.0f)) {
        return 0.0f;
    }

    return flow;
}

/*
 * Where the water leaves a machine this record describes, once it has stopped
 * moving, with the heater held at full scale and the pump held at a level.
 *
 * This is the question admission is really asking: not what the machine is at
 * now, but what it arrives at and stays at if given everything the element has
 * against a stated draw. A target above that figure is one no amount of
 * waiting reaches, which is the only kind of unreachable this file refuses.
 *
 * Asked of a model stood up for the purpose and discarded, in the plant seam's
 * own vocabulary, on the same terms probe_full_scale_flow_ml_per_s asks its
 * question and for the same reason: a heater rating and a standing loss reached
 * for by name would tie this file to one structure's spelling of them, and
 * would compile against that structure and fail to build against the next.
 * Probing puts the same physical question in terms every structure answers.
 *
 * The temperature asked for is the water on its way to the group. A structure
 * that heats the water in the vessel it delivers from keeps no such state --
 * there is nothing between the mass and what leaves it -- and refuses that
 * read; on such a machine the temperature the water leaves at is the brew
 * temperature the machine has, which every structure answers as a quantity. So
 * the state is asked for first and the quantity stands in where the
 * architecture has no state to give, rather than either being assumed.
 *
 * Returns false, writing nothing, when the record will not stand a model up,
 * when the step is refused -- which a structure answering no pump channel does
 * the moment one is commanded -- or when neither read is answered. A caller
 * that cannot be told where the machine settles has established no bound, and
 * this file admits what it cannot refuse on evidence.
 */
static bool probe_settled_brew_c(const plant_parameters_t *parameters, uint16_t pump_permille,
                                 float *settled_c)
{
    plant_model_t probe;
    plant_actuation_t held = {{0u}};

    if (!plant_model_init(&probe, parameters)) {
        return false;
    }

    held.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = (uint16_t)ACTUATION_FULL_SCALE;
    held.level_permille[ACTUATION_CHANNEL_PUMP] = pump_permille;
    if (!plant_model_step(&probe, &held, 0.0f, CONTROL_SETTLING_INTERVAL_MS)) {
        return false;
    }

    if (plant_model_state(&probe, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, settled_c)) {
        return true;
    }
    return plant_model_quantity(&probe, PLANT_QUANTITY_BREW_TEMPERATURE_C, settled_c);
}

/*
 * How long the water on its way to the group takes to close on what the
 * heated mass is doing, under a stated draw -- the lead the drawn-load term
 * is to be read ahead by.
 *
 * Asked of a model stood up for the purpose and discarded, in the plant
 * seam's own vocabulary, on the same terms probe_full_scale_flow_ml_per_s and
 * probe_settled_brew_c ask theirs: a held volume and a conduction figure
 * reached for by name would tie this file to the thermoblock's own spelling
 * of them, and the next structure may keep no such state at all.
 * `full_scale_ml_per_s` is the figure control_init already probed for this
 * same record rather than a second one asked here, on the same reasoning the
 * peak this is called with is admission's own scan and not a second one of
 * that either.
 *
 * The model is left exactly where plant_model_init puts it -- at rest, the
 * heater off -- rather than driven toward the target first. What is measured
 * is the free response of the transport lag alone: two states pulled apart by
 * CONTROL_LEAD_PROBE_OFFSET_C and let close on each other under the draw,
 * with nothing else acting on either. Bringing the heater up first would put
 * most of the initial gap in the mass's own slow approach to a driven
 * setpoint -- a mode an order of magnitude slower than the transport lag this
 * probe exists to measure -- and have the close-enough threshold reached, if
 * ever, by that unrelated mode rather than by the one under test. At rest the
 * gap sits almost entirely in the fast, transport mode, so what closes it is
 * what the lead is meant to answer for.
 *
 * The probe advances the model under the peak draw in the loop's own step
 * interval, and reads back how long the gap takes to close to
 * CONTROL_LEAD_PROBE_CLOSED_FRACTION of what it started at -- the ordinary
 * definition of a first-order lag's own time constant, asked by watching the
 * gap close rather than by assuming the relation is linear and solving for
 * it. A structure that keeps no such state -- PLANT_STATE_BREW_OUTLET_TEMPERATURE_C
 * refused -- has no distance for an effect to travel and is given a lead of
 * nothing, which is the honest lead for it.
 *
 * Returns 0u -- no lead -- for a peak draw of nothing, for a record that will
 * not stand a model up, for a structure with no separated outlet state, or
 * for a probe that has not closed within CONTROL_LEAD_PROBE_MAX_MS: the same
 * honesty the other probes answer an unreachable question with, and the same
 * direction of error the design already prefers -- see the rationale beside
 * heater_command.
 */
static uint32_t probe_read_ahead_lead_millis(const plant_parameters_t *parameters,
                                             float full_scale_ml_per_s, float peak_ml_per_s)
{
    plant_model_t probe;
    plant_actuation_t drawing = {{0u}};
    float mass_c = 0.0f;

    if (!(peak_ml_per_s > 0.0f) || !(full_scale_ml_per_s > 0.0f)) {
        return 0u;
    }

    if (!plant_model_init(&probe, parameters) ||
       !plant_model_state(&probe, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &mass_c)) {
        return 0u;
    }

    /*
     * A structure with no separated outlet state refuses this write on the
     * same terms it refuses the read, which is exactly the case that is to be
     * given no lead -- probed rather than inferred from which structure is
     * linked.
     */
    if (!plant_model_set_state(&probe, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C,
                               mass_c - CONTROL_LEAD_PROBE_OFFSET_C)) {
        return 0u;
    }

    drawing.level_permille[ACTUATION_CHANNEL_PUMP] =
        as_drive_level((peak_ml_per_s / full_scale_ml_per_s) * (float)ACTUATION_FULL_SCALE);

    for (uint32_t elapsed = 0u; elapsed < CONTROL_LEAD_PROBE_MAX_MS;
        elapsed += CONTROL_STEP_INTERVAL_MS) {
        if (!plant_model_step(&probe, &drawing, 0.0f, CONTROL_STEP_INTERVAL_MS)) {
            return 0u;
        }

        float outlet_c = 0.0f;
        if (!plant_model_state(&probe, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &mass_c) ||
           !plant_model_state(&probe, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &outlet_c)) {
            return 0u;
        }

        const float gap_c = mass_c - outlet_c;
        const float gap_magnitude = gap_c < 0.0f ? -gap_c : gap_c;
        if (gap_magnitude <= (CONTROL_LEAD_PROBE_OFFSET_C * CONTROL_LEAD_PROBE_CLOSED_FRACTION)) {
            return elapsed + CONTROL_STEP_INTERVAL_MS;
        }
    }
    return 0u;
}

/*
 * The fastest a course ever asks for water, and when it asks.
 *
 * The points are what is examined rather than the course sampled at some
 * cadence, because a piecewise-linear course takes its extremes at its own
 * bends: nothing between two points is faster than the faster of the two, and
 * nothing past the last point is faster than the last, since the last rate is
 * held rather than extended. Sampling would be slower and would still miss a
 * peak that fell between two samples.
 */
static float peak_rate_ml_per_s(const delivery_profile_t *profile, uint32_t *at_millis)
{
    const size_t counted = (profile->point_count < (size_t)DELIVERY_PROFILE_POINT_MAX)
                               ? profile->point_count
                               : (size_t)DELIVERY_PROFILE_POINT_MAX;
    float peak = 0.0f;

    *at_millis = 0u;
    for (size_t at = 0u; at < counted; at++) {
        if (profile->points[at].rate_ml_per_s > peak) {
            peak = profile->points[at].rate_ml_per_s;
            *at_millis = profile->points[at].at_millis;
        }
    }
    return peak;
}

/*
 * Refuse a target that is beyond what the machine can hold against a draw,
 * writing the bound and both figures into the record. A record already
 * carrying a crossed bound is never reached with this: each caller asks only
 * where nothing has been crossed yet.
 *
 * The peak and the point it occurs at are passed in rather than scanned here,
 * so that a caller which has already found them -- the delivery admission
 * below has, to compare the same peak against the pump's own ceiling -- does
 * not scan the course twice and cannot end up with the two scans disagreeing.
 *
 * The pair is what is judged, never either half alone: the same target is
 * comfortably held at rest and out of reach under a draw, so a bound on the
 * target that did not name a draw would be a bound on nothing. The draw taken
 * is the course's peak rather than its mean, because a delivery that falls out
 * of band for the seconds it is drawing hardest is a delivery that failed --
 * an average that stayed in band would be a statement about arithmetic rather
 * than about the cup.
 *
 * Nothing here reads the machine's present condition. Where the water settles
 * is a property of the description and the draw, so a cold machine and a
 * machine at temperature receive the same answer, which is what keeps this a
 * refusal of the impossible rather than a refusal of the early.
 */
static void refuse_if_beyond_the_authority(const control_state_t *state, float peak_ml_per_s,
                                           uint32_t at_millis, float target_c,
                                           control_admission_t *admission)
{
    const uint16_t peak_level = as_drive_level((peak_ml_per_s / state->full_scale_flow_ml_per_s) *
                                               (float)ACTUATION_FULL_SCALE);
    float settled_c = 0.0f;

    /*
     * A probe that could not be taken establishes no bound, and this file
     * admits what it cannot refuse on evidence. A machine settling exactly at
     * the target is held to reach it, so the comparison is strict.
     */
    if (!probe_settled_brew_c(&state->parameters, peak_level, &settled_c) ||
        !(settled_c < target_c)) {
        return;
    }

    admission->bound = CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY;
    admission->requested = target_c;
    admission->available = settled_c;
    admission->at_millis = at_millis;
}

/*
 * Refuse a target outside the drinking-temperature window, for a delivery
 * served at the drinking point, writing the bound and both figures into the
 * record. A record already carrying a crossed bound is never reached with
 * this, on the same terms refuse_if_beyond_the_authority above isn't.
 *
 * Asked only of a delivery whose profile states the drinking point: an
 * extraction's course is its recipe, held to it by the brew-temperature band
 * rather than this window, and gains nothing from a check that names no
 * drinking point at all. Checked ahead of the authority bound at both call
 * sites because it costs nothing to ask -- a comparison against two figures
 * already in the tolerance record -- while authority costs a plant model
 * probe, and a target that fails the cheaper question first is refused
 * without paying for the dearer one.
 *
 * The floor is inclusive and the ceiling is not, on the same convention
 * admit_target's own saturation check already reads CONTROL_SATURATION_C by:
 * a target sitting exactly at the floor is the coldest the drink may still be
 * and is admitted, while one sitting at the ceiling has reached the point
 * past which nothing may be handed to a person.
 */
static void refuse_if_outside_the_drinking_window(const delivery_tolerance_t *tolerance,
                                                  plant_delivery_point_t served_at, float target_c,
                                                  control_admission_t *admission)
{
    if (served_at != PLANT_DELIVERY_POINT_HOT_WATER_SPOUT) {
        return;
    }

    const float floor_c = (float)tolerance->drinking_floor_milli_c / 1000.0f;
    const float ceiling_c = (float)tolerance->drinking_ceiling_milli_c / 1000.0f;

    if (target_c < floor_c) {
        admission->bound = CONTROL_ADMISSION_TARGET_BELOW_DRINKING_FLOOR;
        admission->requested = target_c;
        admission->available = floor_c;
        return;
    }
    if (!(target_c < ceiling_c)) {
        admission->bound = CONTROL_ADMISSION_TARGET_ABOVE_DRINKING_CEILING;
        admission->requested = target_c;
        admission->available = ceiling_c;
    }
}

/*
 * Whether this machine can ever do what a delivery asks of it, and what it
 * crossed if not -- and the course's own peak, so a caller admitting a
 * delivery is not left to scan the course a second time for a figure this
 * call has already found.
 */
static control_admission_t admit_delivery(const control_state_t *state,
                                          const delivery_profile_t *profile,
                                          float *peak_ml_per_s)
{
    control_admission_t admission = {CONTROL_ADMISSION_OK, 0.0f, 0.0f, 0u};

    *peak_ml_per_s = 0.0f;

    if (state == NULL || profile == NULL) {
        admission.bound = CONTROL_ADMISSION_NOTHING_GIVEN;
        return admission;
    }
    if (!(state->full_scale_flow_ml_per_s > 0.0f)) {
        admission.bound = CONTROL_ADMISSION_NO_MACHINE_DESCRIBED;
        return admission;
    }

    uint32_t at_millis = 0u;
    const float peak = peak_rate_ml_per_s(profile, &at_millis);
    *peak_ml_per_s = peak;

    if (peak > state->full_scale_flow_ml_per_s) {
        admission.bound = CONTROL_ADMISSION_RATE_OVER_FULL_SCALE;
        admission.requested = peak;
        admission.available = state->full_scale_flow_ml_per_s;
        admission.at_millis = at_millis;
        return admission;
    }

    /*
     * A machine with no target named has been asked for a rate and nothing
     * else, so there is no pair for the authority bound to be a bound on. The
     * target it is given afterwards is judged where it is named, against the
     * course running by then -- which is why that call asks this same question
     * of a delivery already under way rather than leaving the ordering of the
     * two commands to decide whether the pair is ever examined.
     */
    if (state->targeted) {
        refuse_if_outside_the_drinking_window(&state->tolerance, profile->served_at,
                                              state->target_c, &admission);
        if (admission.bound == CONTROL_ADMISSION_OK) {
            refuse_if_beyond_the_authority(state, peak, at_millis, state->target_c, &admission);
        }
    }
    return admission;
}

/*
 * Whether this machine can ever be driven to a target, and what it crossed if
 * not.
 *
 * A target names no draw of its own, so the only ceiling it always meets is
 * the one water itself imposes. Where a delivery is already running, the
 * course it is running is the draw this target will have to be held against,
 * and the pair is judged here on exactly the terms it would have been judged
 * on had the two commands arrived the other way round.
 */
static control_admission_t admit_target(const control_state_t *state, float celsius)
{
    control_admission_t admission = {CONTROL_ADMISSION_OK, 0.0f, 0.0f, 0u};

    if (state == NULL) {
        admission.bound = CONTROL_ADMISSION_NOTHING_GIVEN;
        return admission;
    }
    /*
     * The value is not carried into the record. What was asked for here is a
     * not-a-number or an infinity, and writing one into a field a caller will
     * compare or print would be handing on the very thing that was refused.
     */
    if (!is_a_temperature(celsius)) {
        admission.bound = CONTROL_ADMISSION_NOT_A_TEMPERATURE;
        return admission;
    }

    /*
     * Written as a negated comparison, so a target that is somehow not a number
     * lands on the refusal rather than sailing past it. is_a_temperature has
     * already refused that above; the guard costs a branch and removes the
     * class.
     */
    if (!(celsius < CONTROL_SATURATION_C)) {
        admission.bound = CONTROL_ADMISSION_TARGET_OVER_SATURATION;
        admission.requested = celsius;
        admission.available = CONTROL_SATURATION_C;
        return admission;
    }

    if (state->delivery_running) {
        refuse_if_outside_the_drinking_window(&state->tolerance, state->delivery.served_at, celsius,
                                              &admission);
        if (admission.bound == CONTROL_ADMISSION_OK && (state->full_scale_flow_ml_per_s > 0.0f)) {
            uint32_t at_millis = 0u;
            const float peak = peak_rate_ml_per_s(&state->delivery, &at_millis);

            refuse_if_beyond_the_authority(state, peak, at_millis, celsius, &admission);
        }
    }
    return admission;
}

bool control_init(control_state_t *state, const plant_parameters_t *parameters,
                  const estimator_limits_t *limits, const delivery_tolerance_t *tolerance)
{
    if (state == NULL) {
        return false;
    }

    state->last_step_millis = hw_monotonic_millis();
    state->step_count = 0u;
    state->brew_heater_permille = 0u;
    state->commanded_pump_permille = 0u;
    state->driven_pump_permille = 0u;
    state->target_c = 0.0f;
    state->targeted = false;
    state->integral_permille = 0.0f;
    state->started = false;
    state->faulted = false;
    state->full_scale_flow_ml_per_s = 0.0f;
    state->delivery_running = false;
    state->delivery_elapsed_millis = 0u;
    state->delivery_lead_millis = 0u;
    /*
     * A demand cannot be held before anything has ever run to contend with,
     * so this starts false on the same terms `delivery_running` above does.
     * `held_delivery` itself is left uninitialised rather than cleared here:
     * it is meaningful only while `delivery_held` is set (see the field
     * comment on `held_delivery` in control.h), on the same terms `delivery`
     * is left in place once `delivery_running` goes false rather than
     * cleared, so there is nothing this function is entitled to assume about
     * its shape that clearing it would express.
     */
    state->delivery_held = false;
    forget_departure(state);

    /*
     * The description is put into the state before anything can refuse, on the
     * same terms the band below is: an instance that failed to come up answers
     * with a record of nothing rather than with whatever the memory it was
     * declared in contained. A record of nothing describes no machine any
     * probe could learn anything from, which is the honest state for an
     * instance that never accepted one -- and every path that would reach for
     * it has already been refused by then.
     *
     * Copied from a zeroed instance of the type rather than assigned field by
     * field: which fields a description carries is the linked structure's own
     * business, and this file is not entitled to know their names.
     */
    static const plant_parameters_t NOTHING;

    state->parameters = NOTHING;
    if (parameters != NULL) {
        state->parameters = *parameters;
    }

    /*
     * The bands are put into the state before anything can refuse, so that an
     * instance which failed to come up still answers what it was given rather
     * than whatever the memory it was declared in contained. Given none it
     * answers nothing, which is the honest answer and is why the refusal below
     * follows rather than a band being assumed.
     *
     * Copied from a zeroed instance of the type rather than field by field, on
     * the same terms the description above is: which bands the record carries
     * grows as the deliveries this software serves are held to more things, and
     * a list of assignments here is the one that goes on compiling while a band
     * added later answers with whatever the memory contained.
     */
    static const delivery_tolerance_t NOTHING_DECLARED;

    state->tolerance = NOTHING_DECLARED;
    if (tolerance != NULL) {
        state->tolerance = *tolerance;
    }

    const bool off = hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, 0u) &&
                     hw_output_set(ACTUATION_CHANNEL_PUMP, 0u);

    /*
     * A control path with no band is refused after the outputs are commanded
     * off, not before, so that the refusal leaves the machine de-energised the
     * way every other refusal here does. A band left undeclared is not a wide
     * band: it is a criterion nothing holds a delivery to, and a loop that came
     * up anyway would be driving toward a temperature with no statement of what
     * counts as having reached it.
     */
    if (tolerance == NULL) {
        state->faulted = true;
        return false;
    }

    /*
     * The outputs are commanded off before the estimator is brought up, so that
     * a refusal below leaves the machine de-energised rather than leaving the
     * off commands unsent. A refusal latches the fault for the same reason an
     * untrustworthy reading does: there is no temperature to act on, and a
     * control law that started driving later would be driving blind.
     */
    if (!estimator_init(&state->estimator, parameters, limits)) {
        state->faulted = true;
        return false;
    }

    /*
     * Probed once the estimator has accepted the same record, rather than
     * before: a record the estimator refuses is not a machine this instance
     * is going anywhere with, and probing it anyway would be answering a
     * question about a structure this instance is about to report unusable.
     */
    state->full_scale_flow_ml_per_s = probe_full_scale_flow_ml_per_s(parameters);

    return off;
}

bool control_command_temperature_reporting(control_state_t *state, float celsius,
                                           control_admission_t *admission)
{
    if (admission == NULL) {
        return false;
    }

    *admission = admit_target(state, celsius);
    if (admission->bound != CONTROL_ADMISSION_OK) {
        return false;
    }

    if (!state->targeted || state->target_c != celsius) {
        state->integral_permille = 0.0f;
    }
    state->target_c = celsius;
    state->targeted = true;
    return true;
}

bool control_command_temperature(control_state_t *state, float celsius)
{
    control_admission_t discarded;

    return control_command_temperature_reporting(state, celsius, &discarded);
}

bool control_command_flow(control_state_t *state, uint16_t pump_permille)
{
    if (state == NULL || pump_permille > (uint16_t)ACTUATION_FULL_SCALE) {
        return false;
    }

    state->commanded_pump_permille = pump_permille;
    return true;
}

/*
 * Copy a profile into the state as the delivery now running, against the
 * peak rate it draws at.
 *
 * Written once so that a delivery commanded directly and a demand that was
 * held and is now being admitted start on identical terms: elapsed time at
 * zero regardless of anything that ran, or waited, before it; the read-ahead
 * lead probed fresh against this course's own peak rather than carried over
 * from whatever last held the field; and the last delivery's departure and
 * yield forgotten, so neither reports on a course that is not its own.
 */
static void start_delivery(control_state_t *state, const delivery_profile_t *profile,
                           float peak_ml_per_s)
{
    state->delivery = *profile;
    state->delivery_running = true;
    state->delivery_elapsed_millis = 0u;
    state->delivery_lead_millis = probe_read_ahead_lead_millis(
        &state->parameters, state->full_scale_flow_ml_per_s, peak_ml_per_s);
    forget_departure(state);
}

/*
 * Start the demand held against the delivery that has just reached its own
 * end, if one is waiting.
 *
 * Called only from the one place in control_step a delivery ends on its own
 * account -- reaching its end condition -- rather than being cut off by
 * everything being commanded off: see command_everything_off for why a
 * demand held against a delivery that ends that way is discarded rather than
 * started. What full pump scale this machine draws and what description it
 * was brought up against have not changed since the demand was held, so
 * nothing about it is re-admitted here; only the peak this course draws at is
 * asked again, on the same terms start_delivery asks it of any other
 * delivery, because it is what the lead-ahead term is probed against and
 * this call does not have admission's own answer lying around to reuse.
 *
 * Started on exactly the terms start_delivery starts any other delivery on,
 * so a demand that waited many control steps for the mass it named begins
 * counting its own elapsed time from this admission and not from however long
 * it waited.
 */
static void start_the_held_delivery(control_state_t *state)
{
    if (!state->delivery_held) {
        return;
    }

    uint32_t at_millis = 0u;
    const float peak_ml_per_s = peak_rate_ml_per_s(&state->held_delivery, &at_millis);

    start_delivery(state, &state->held_delivery, peak_ml_per_s);
    state->delivery_held = false;
}

bool control_command_delivery_reporting(control_state_t *state, const delivery_profile_t *profile,
                                        control_admission_t *admission)
{
    if (admission == NULL) {
        return false;
    }

    float peak_ml_per_s = 0.0f;
    *admission = admit_delivery(state, profile, &peak_ml_per_s);
    if (admission->bound != CONTROL_ADMISSION_OK) {
        return false;
    }

    /*
     * Contention is a transient condition -- whether the mass this profile
     * would draw is given to the delivery already running -- and not a
     * permanent one, so it is asked here rather than folded into
     * admit_delivery's own bound vocabulary above. Asked of whatever is
     * actually running, through the same two-argument seam call the recovery
     * accounting between deliveries already reads, rather than of a fixed
     * reference point: control_delivery_contends_with_the_group answers a
     * narrower question than this one needs.
     *
     * The point named is compared against the one already running first, and
     * the mass is only asked about when the two differ. A profile naming the
     * same point a running delivery already does shares a mass with it
     * trivially -- it is the same mass by definition -- and that is not the
     * contention this question is about: a caller repeating the point it
     * already named is restating the same demand, on the same terms a new
     * target replaces one already commanded, and is replaced exactly as
     * before rather than held against itself. What this asks about is two
     * distinct points that answer for one casting between them.
     *
     * A demand found to contend is held rather than started, and the
     * delivery already running is left completely alone -- nothing here
     * touches `state->delivery` or its bookkeeping. A second contending
     * demand commanded while one is already held simply overwrites
     * `held_delivery`, on the same terms a running delivery is replaced by a
     * later command: one waiting slot, not a queue.
     */
    bool contends = false;
    if (state->delivery_running && profile->served_at != state->delivery.served_at &&
        plant_delivery_points_share_mass(profile->served_at, state->delivery.served_at,
                                         &contends) &&
        contends) {
        state->held_delivery = *profile;
        state->delivery_held = true;
        return true;
    }

    start_delivery(state, profile, peak_ml_per_s);
    return true;
}

bool control_command_delivery(control_state_t *state, const delivery_profile_t *profile)
{
    control_admission_t discarded;

    return control_command_delivery_reporting(state, profile, &discarded);
}

bool control_delivery_running(const control_state_t *state)
{
    return state != NULL && state->delivery_running;
}

bool control_delivery_held(const control_state_t *state, delivery_profile_t *held_profile,
                           plant_delivery_point_t *held_against)
{
    if (state == NULL || held_profile == NULL || held_against == NULL || !state->delivery_held) {
        return false;
    }

    *held_profile = state->held_delivery;
    *held_against = state->delivery.served_at;
    return true;
}

bool control_temperature_band(const control_state_t *state, int32_t *band_milli_c)
{
    if (state == NULL || band_milli_c == NULL) {
        return false;
    }

    *band_milli_c = state->tolerance.brew_temperature_band_milli_c;
    return true;
}

bool control_post_draw_match_band(const control_state_t *state, int32_t *band_milli_c)
{
    if (state == NULL || band_milli_c == NULL) {
        return false;
    }

    *band_milli_c = state->tolerance.post_draw_match_band_milli_c;
    return true;
}

bool control_delivery_contends_with_the_group(const delivery_profile_t *profile, bool *contends)
{
    if (profile == NULL || contends == NULL) {
        return false;
    }

    /*
     * Put to the seam rather than answered here. This machine routes both its
     * deliveries out of one casting through a diverter, so an answer written
     * into this file would be right about this machine and would go on being
     * given on a machine with two heated masses, where the two deliveries do
     * not contend at all and no recovery is owed between them.
     */
    return plant_delivery_points_share_mass(profile->served_at, PLANT_DELIVERY_POINT_GROUP,
                                            contends);
}

bool control_delivery_departure(const control_state_t *state, control_departure_t *departure)
{
    if (state == NULL || departure == NULL) {
        return false;
    }

    *departure = state->departure;
    return true;
}

bool control_delivery_yield(const control_state_t *state, control_yield_t *yield)
{
    if (state == NULL || yield == NULL) {
        return false;
    }

    *yield = state->yield;
    return true;
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
     * step: the estimator is still advanced by what elapsed and the outputs are
     * still driven. What it changes is what the caller is told.
     */
    const bool late =
        state->started && elapsed > (CONTROL_STEP_INTERVAL_MS * CONTROL_STEP_LATE_MULTIPLE);

    state->started = true;
    state->last_step_millis = now;
    state->step_count++;

    if (state->faulted) {
        command_everything_off(state);
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
     * The state asked for is the water on its way to the group and not the mass
     * a sensor reports. They are different quantities, and how far apart they
     * are moves with the draw, so a loop closed on the reading would be right
     * about the machine and wrong about the drink.
     */
    float brew_c = 0.0f;
    if (!estimator_state(&state->estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &brew_c)) {
        return shut_down(state, CONTROL_STEP_SENSOR_INVALID);
    }

    /*
     * A machine that has not been asked for a drink drives nothing. The
     * estimator has already been advanced above, so the reconstruction goes on
     * following the machine while it waits, and the delivery that arrives next
     * starts from a state that has been kept rather than from one that stopped.
     *
     * command_everything_off clears a running delivery as part of commanding
     * everything else off, so a step that reaches this branch ends whatever
     * delivery was running rather than leaving it for the block below to go on
     * advancing against a machine that is not driving water.
     */
    if (!state->targeted) {
        state->integral_permille = 0.0f;
        command_everything_off(state);
        return CONTROL_STEP_NO_TARGET;
    }

    /*
     * A running delivery is advanced here: after the estimator, because what
     * it commands next answers for the interval that is coming rather than
     * correcting the one just gone; below the no-target branch above, because
     * a delivery only ever advances on a step that actually drives the
     * machine -- a step with nothing targeted has already ended it, by way of
     * command_everything_off, and advancing its clock and its commanded rate
     * regardless would have it run against the course while nothing moved;
     * and above the heater command below, because the feedforward it carries
     * reads the delivery's own elapsed clock and its commanded rate in this
     * same step -- a lead ahead of the clock while a delivery is running,
     * commanded_pump_permille directly otherwise -- and both have to be
     * sitting there before either is read, not after.
     *
     * `advance` is the interval that actually elapsed, the same one the
     * estimator was just advanced by. Timing the delivery against the nominal
     * cadence instead would have it end early or late by exactly how far a
     * late step had fallen behind -- the same dishonesty the estimator's own
     * advance is written to avoid.
     *
     * control_command_delivery refuses to start a delivery unless
     * full_scale_flow_ml_per_s is usable, so nothing here has to check it
     * again: every delivery reaching this branch has a figure to divide the
     * commanded rate by.
     */
    bool departed = false;

    if (state->delivery_running) {
        state->delivery_elapsed_millis += advance;

        if (delivery_profile_ended(&state->delivery, state->delivery_elapsed_millis)) {
            /*
             * The interval that has just elapsed ran under this delivery's
             * command and is judged like any other, so the last stretch of a
             * delivery is not the one stretch nothing accounts for. Only the
             * report is written: the step's own result stays the ordinary one,
             * because what this step is reporting is that the delivery ended.
             */
            (void)judge_the_interval_just_elapsed(state);
            state->delivery_running = false;
            state->commanded_pump_permille = 0u;

            /*
             * A demand held for the mass this delivery was drawing has
             * nothing left to wait for: start it now, on the same control
             * cadence that noticed the mass was free, with nothing asked of
             * the caller again. See start_the_held_delivery.
             */
            start_the_held_delivery(state);
        } else {
            const float rate_ml_per_s =
                delivery_profile_rate_ml_per_s(&state->delivery, state->delivery_elapsed_millis);
            /*
             * Established here, before the pump level below is computed and
             * before heater_command reads it back through
             * drawn_load_pump_permille -- see drinking_yield_fraction and
             * delivery_yield_fraction's own comment in control.h. A delivery
             * giving nothing up reads a fraction of one and nothing here
             * changes; this is the gate the loop has always had, extended
             * rather than replaced.
             */
            const float yield_fraction = drinking_yield_fraction(state, brew_c);
            const float yielded_rate_ml_per_s = rate_ml_per_s * yield_fraction;
            const float permille = (yielded_rate_ml_per_s / state->full_scale_flow_ml_per_s) *
                                   (float)ACTUATION_FULL_SCALE;
            state->commanded_pump_permille = as_drive_level(permille);
            state->delivery_yield_fraction = yield_fraction;

            /*
             * What was given up this step, latched the same way departure is
             * and for the same reason -- see control_yield_t. Tracked by
             * magnitude across the delivery's life rather than only by
             * having happened at all, on the same footing
             * control_departure_t's own largest figure already is, so a
             * caller can tell how hard the machine had to trade and not only
             * that it did.
             */
            if (yield_fraction < 1.0f) {
                const int32_t given_up_milli_ml_per_s =
                    as_milli((rate_ml_per_s - yielded_rate_ml_per_s) * 1000.0f);

                if (!state->yield.yielded ||
                    given_up_milli_ml_per_s > state->yield.largest_milli_ml_per_s) {
                    state->yield.largest_milli_ml_per_s = given_up_milli_ml_per_s;
                    state->yield.at_millis = state->delivery_elapsed_millis;
                }
                state->yield.yielded = true;
            }

            /*
             * The delivered flow is compared against the same commanded rate
             * that just drove the pump, on the same cadence the profile is
             * evaluated -- not a figure read back from the plant model, which
             * would compare the command against itself. Per
             * DEC-DEPARTURE-OBSERVED-NOT-MODELLED, departure is observed by
             * measuring what moved rather than reproduced by modelling what
             * resisted it, so an absent or failed reading is not compared
             * against anything: nothing arrived to have moved differently
             * from what was asked.
             */
            departed = judge_the_interval_just_elapsed(state);

            /*
             * What was commanded on this step is what the next step's reading
             * will answer for, so it is kept here after the judgement above has
             * used the one before it. It is the rate the profile commanded and
             * not the one the pump was actually driven at, unreduced by any
             * yield in force: a yielded delivery is judged against what it was
             * asked for, so its shortfall reports exactly as a choked path's
             * would, and what the machine chose to give up is control_yield_t's
             * account rather than this one's.
             */
            state->delivery_commanded_rate_ml_per_s = rate_ml_per_s;
            state->delivery_commanded_at_millis = state->delivery_elapsed_millis;
            state->delivery_rate_commanded = true;
        }
    }

    const float interval_s = (float)advance / 1000.0f;
    const uint16_t level = as_drive_level(heater_command(state, brew_c, interval_s));

    /*
     * The pump is driven before the heater command is recorded but after the
     * heater is driven, so that a machine which accepts one command and refuses
     * the other is shut down rather than left half-driven. Both levels reach
     * the machine in the step the flow was commanded in, which is what makes
     * the feedforward above a feedforward rather than a fast reaction.
     */
    if (!hw_output_set(ACTUATION_CHANNEL_BREW_HEATER, level)) {
        return shut_down(state, CONTROL_STEP_OUTPUT_REFUSED);
    }
    state->brew_heater_permille = level;

    if (!hw_output_set(ACTUATION_CHANNEL_PUMP, state->commanded_pump_permille)) {
        return shut_down(state, CONTROL_STEP_OUTPUT_REFUSED);
    }
    state->driven_pump_permille = state->commanded_pump_permille;

    /*
     * Lateness is reported ahead of departure where both are true of the same
     * cycle: CONTROL_STEP_LATE is the pre-existing, more urgent signal -- a
     * caller that has fallen behind on cadence needs to learn that before
     * anything else -- and CONTROL_STEP_DELIVERY_DEPARTED is additive scope
     * layered on top of an otherwise-ordinary cycle, not a replacement for it.
     * A cycle that is both late and departed is still, first and foremost,
     * late.
     */
    if (late) {
        return CONTROL_STEP_LATE;
    }
    return departed ? CONTROL_STEP_DELIVERY_DEPARTED : CONTROL_STEP_ACTUATED;
}
