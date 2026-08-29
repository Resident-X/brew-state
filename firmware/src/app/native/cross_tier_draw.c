/*
 * The host tier's closed loop, driven across a commanded draw.
 *
 * The loop closed here is the one this tier already has: the control logic
 * linked against the simulated implementation of the hardware seam, driving a
 * plant model the estimator does not own. What is added is that the machine
 * reports through a converter rather than by handing the control logic the
 * model's own figure -- because the loop this run exists to be compared against
 * reads its sensors through one, and a reading that skipped the converter would
 * be a different input, not the same one measured differently.
 *
 * The machine and the control path are stood up from separate descriptions,
 * handed in separately. Where the two are the same record the run is what it
 * always was; where they differ it is a machine its controller is wrong about,
 * which is what a casting that has fouled or aged is. The difference is not
 * cosmetic: the loop drives a reconstruction built from whichever description
 * the control path was given, so a controller holding the old figures holds its
 * own estimate at the target rather than the delivery, and what reaches the
 * channels is smaller than it is when the controller knows.
 *
 * What the converter reports has to be able to reach what is commanded next, or
 * modelling it is decoration. That is why the draw commands a course of flow
 * alongside its temperature: with the pump off, the water on its way to the
 * group reaches the block by conduction alone and stays tens of kelvin behind
 * it, so the control law spends every interval of any short draw asking for more
 * than full scale and being given full scale -- a command a reading cannot
 * change. Water moving both brings that state up to the block and lowers what
 * the law is asking for, and the loop leaves the limit.
 *
 * The converter is modelled here and not in the simulated hardware seam, and
 * the difference matters: the seam is a way of standing a reading up, with no
 * view on where the reading came from, and giving it one would make every other
 * suite that uses it depend on a board's scaling. What the seam offers is the
 * injection point; this file decides what to inject.
 *
 * The scaling itself is done in double precision deliberately, and it is the
 * one place in this tree where that is right. Every quantity the model carries
 * is single precision, and the arithmetic below is not the model's -- it is a
 * converter's, reproduced so that the count this run injects is the count the
 * other loop's converter would have produced from the same quantity. Doing it
 * in single precision would round differently in the last place and inject a
 * neighbouring count, which is the comparison losing to its own instrumentation.
 */
#include "cross_tier_draw.h"

#include <stdio.h>

#include "control.h"
#include "hw_sim.h"
#include "plant_model.h"

/*
 * The quantity each sensor channel with a converter input behind it reads, in
 * the seam's own channel order. HW_SENSOR_FLOW is absent from this table
 * because it is absent from the machine: nothing is wired to it, so it reports
 * that nothing is there, which hw_sim_reset already leaves it doing.
 */
static const plant_quantity_t sensed_quantity[] = {
    PLANT_QUANTITY_BREW_TEMPERATURE_C,  /* HW_SENSOR_BREW_TEMPERATURE */
    PLANT_QUANTITY_STEAM_TEMPERATURE_C, /* HW_SENSOR_STEAM_TEMPERATURE */
    PLANT_QUANTITY_BREW_PRESSURE_BAR,   /* HW_SENSOR_BREW_PRESSURE */
    PLANT_QUANTITY_STEAM_PRESSURE_BAR   /* HW_SENSOR_STEAM_PRESSURE */
};

#define SENSED_CHANNEL_COUNT (sizeof(sensed_quantity) / sizeof(sensed_quantity[0]))

/*
 * What each reported figure is called, in the same order.
 *
 * The findings are named rather than left to be read off by position, because
 * the loop this run is compared against reports a field of its own that this one
 * has nothing to say about -- what its clock read -- and a reader counting
 * columns to find the quantities has to know that, separately, for each of the
 * two. A reader looking for a name does not, and a name that stopped being
 * printed fails where it is looked for rather than silently returning whatever
 * now sits in that column.
 */
static const char *const quantity_key[] = {"brew-c", "steam-c", "brew-bar", "steam-bar"};

_Static_assert(sizeof(quantity_key) / sizeof(quantity_key[0]) == SENSED_CHANNEL_COUNT,
               "every sensed quantity reported has to have a name to report it under");

/*
 * What the converter's own reconstructed reading for each sensed quantity is
 * reported under, in the same order as the table above.
 *
 * Deliberately a name of its own rather than a column counted off the table
 * above: the figure printed here is not the plant model's quantity, which the
 * table above already reports -- it is what that quantity becomes after the
 * same round trip through a count `reported_milli` performs before a reading
 * reaches the control law. A run comparing full-scale settings needs this
 * rather than the plant quantity, because the plant quantity is common to
 * every run of the same course and the converter's reading of it is not; the
 * two came apart in exactly the way a subcase comparing full-scale settings
 * has to be able to tell.
 */
static const char *const converter_key[] = {
    "brew-c-converter-milli", "steam-c-converter-milli",
    "brew-bar-converter-milli", "steam-bar-converter-milli"};

_Static_assert(sizeof(converter_key) / sizeof(converter_key[0]) == SENSED_CHANNEL_COUNT,
               "every converter reading reported has to have a name to report it under");

/*
 * What the temperature an extraction is actually judged by is reported under.
 *
 * It is deliberately not in the table above, and the separation is the point.
 * That table is what two tiers reading the same instruments compare with one
 * another, and this is not an instrument's reading at all: nothing on this
 * machine reports the water on its way to the group, which is exactly why the
 * control path reconstructs it and drives to the reconstruction. Folding it in
 * beside the sensed four would put a quantity no converter carries into a
 * comparison whose whole subject is what a converter carried.
 *
 * It is reported all the same, because a run asking what a coefficient's
 * uncertainty costs the drink has to be able to read the drink. The block's own
 * temperature is not a substitute: how far the two sit apart moves with the
 * draw, and the coefficients that decide the distance are among the loosest the
 * description carries.
 */
#define DELIVERED_KEY "outlet-c"

/*
 * What the rate water is being drawn through the brew path at is reported
 * under.
 *
 * It is beside the delivered temperature above rather than in the sensed table,
 * and for the same reason that one is: the table is what two tiers reading the
 * same converters compare with one another, and no converter carries this. The
 * seam enumerates a flow channel, but the board this project is building has
 * nothing wired to it -- the machine's flow meter answers the controller this
 * project replaces -- so a figure reported through the sensed path would be
 * claiming an instrument the machine does not have.
 *
 * It is reported all the same, because the question of whether a coefficient
 * could be told apart from what the machine observes cannot be asked of a
 * channel nobody printed. What this line carries is what the modelled machine's
 * rate actually is, which is the figure an instrument on that channel would be
 * placed against -- and the difference between a channel that carries a
 * distinguishing signature and one that does not is exactly what says whether
 * fitting such an instrument would buy anything.
 *
 * Unlike the delivered temperature it is never absent. The plant seam
 * enumerates it as a quantity rather than a state, which is the seam's own way
 * of saying every structure answers it whatever it keeps inside -- so a
 * structure with no such state still reports the rate it was commanded to move,
 * and there is no architecture for which the field would have to be left off.
 */
#define FLOW_KEY "brew-mlps"

/*
 * Nine significant digits, which is what round-trips an IEEE-754 single
 * precision value exactly. A narrower format would be this run's printing
 * introducing a disagreement rather than reporting one.
 */
#define QUANTITY_FORMAT "%.9g"

/*
 * One reported line.
 *
 * `delivered` is the temperature of the water on its way to the group, or null
 * on a build whose structure keeps no such state. A null is reported by the
 * field being absent from the line rather than by a figure standing for
 * absence: a structure that heats the water where it delivers it has no such
 * temperature, and any number printed for it -- nothing, the block's own, a
 * sentinel -- would be read by whatever consumes the line as a measurement of
 * something. A field that is simply not there fails where it is looked for,
 * which is the answer a consumer can act on.
 */
static void report(const char *what, int index, int result, unsigned pump, unsigned heater,
                   unsigned long taken, const float *values, const int32_t *converter_milli,
                   const float *delivered, float flow)
{
    (void)printf("HOST %s", what);
    if (index >= 0) {
        (void)printf(" interval=%d result=%d pump=%u heater=%u steps=%lu", index, result, pump,
                     heater, taken);
    }
    for (size_t i = 0u; i < SENSED_CHANNEL_COUNT; i++) {
        /* The cast is explicit because a variadic argument is promoted whatever
         * the source says, and the build refuses a silent promotion. */
        (void)printf(" %s=" QUANTITY_FORMAT, quantity_key[i], (double)values[i]);
    }
    for (size_t i = 0u; i < SENSED_CHANNEL_COUNT; i++) {
        (void)printf(" %s=%ld", converter_key[i], (long)converter_milli[i]);
    }
    if (delivered != NULL) {
        (void)printf(" " DELIVERED_KEY "=" QUANTITY_FORMAT, (double)*delivered);
    }
    (void)printf(" " FLOW_KEY "=" QUANTITY_FORMAT, (double)flow);
    (void)printf("\n");
}

static bool sensed(const plant_model_t *machine, float *values)
{
    for (size_t i = 0u; i < SENSED_CHANNEL_COUNT; i++) {
        if (!plant_model_quantity(machine, sensed_quantity[i], &values[i])) {
            return false;
        }
    }
    return true;
}

/*
 * The rate water is presently being drawn through the brew path at.
 *
 * Read on its own rather than through the table above, because the table's
 * entries are the quantities a converter input stands behind and this is not
 * one of them. A refusal here is worth stopping the draw on: this is a
 * quantity and not a state, which is the plant seam's own way of undertaking
 * that every structure answers it whatever it keeps inside, so a structure
 * refusing it is a structure that has stopped honouring the seam rather than
 * one whose architecture has nowhere to put it.
 */
static bool drawn_rate(const plant_model_t *machine, float *value)
{
    return plant_model_quantity(machine, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, value);
}

/*
 * What the machine's converter reports for one quantity, in thousandths of the
 * channel's unit.
 *
 * The quantity is scaled to a count, the count is clamped rather than wrapped
 * -- which is what a converter with a pinned rail does, and what a count
 * aliasing silently back into range does not -- and the count is turned back
 * into milli-units by integer division, because that is the arithmetic a
 * consumer of a converter does. Both halves are here rather than only the
 * second, since a reading that never passed through a count would carry a
 * precision the instrument does not have.
 */
static int32_t reported_milli(float value, const cross_tier_draw_t *draw)
{
    const double milli = (double)value * 1000.0;
    const double scaled =
        milli * (double)draw->converter_full_scale_counts /
        (double)draw->converter_full_scale_milli;

    uint32_t counts;
    if (scaled < 0.0) {
        counts = 0u;
    } else if (scaled > (double)draw->converter_full_scale_counts) {
        counts = draw->converter_full_scale_counts;
    } else {
        counts = (uint32_t)scaled;
    }

    /*
     * Widened for the multiplication and narrowed again after the division. The
     * product of a count and a full scale is not a figure either of them is
     * bounded to hold -- a converter of a few thousand counts against a full
     * scale of a few hundred thousand milli-units already needs twenty-eight
     * bits, and a harness free to hand in either is free to hand in a pair that
     * needs more than thirty-two. Wrapping there would not be reported as
     * anything: it would return a plausible reading of the wrong quantity. The
     * quotient is back inside the full scale by construction, and the caller
     * refuses a full scale that will not fit a reading, so the narrowing loses
     * nothing.
     */
    return (int32_t)(((uint64_t)counts * (uint64_t)draw->converter_full_scale_milli) /
                     (uint64_t)draw->converter_full_scale_counts);
}

static bool stand_the_readings_up(const plant_model_t *machine, const cross_tier_draw_t *draw,
                                  int32_t *converter_milli)
{
    float values[SENSED_CHANNEL_COUNT];

    if (!sensed(machine, values)) {
        return false;
    }
    for (size_t i = 0u; i < SENSED_CHANNEL_COUNT; i++) {
        converter_milli[i] = reported_milli(values[i], draw);
        hw_sim_set_sensor((hw_sensor_channel_t)i, HW_READING_VALID, converter_milli[i]);
    }
    return true;
}

/*
 * Advance the machine by every actuation the interval just written to it.
 *
 * A write reaching the pump is what marks an interval's actuation as fully
 * held -- the control logic writes the brew heater before the pump on every
 * path it can take -- so the count of writes that reached that channel is what
 * says how many intervals' worth of actuation the machine now owes. Counting
 * rather than assuming one is what keeps a path that drove the outputs twice
 * from being absorbed into a single step.
 */
static bool advance_the_machine(plant_model_t *machine, uint32_t owed, uint32_t interval_millis)
{
    for (uint32_t write = 0u; write < owed; write++) {
        plant_actuation_t driven = {{0u}};

        for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
            driven.level_permille[channel] = hw_sim_output((hw_output_channel_t)channel);
        }
        if (!plant_model_step(machine, &driven, 0.0f, interval_millis)) {
            return false;
        }
    }
    return true;
}

/*
 * The temperature of the water on its way to the group, where the structure
 * this build compiled keeps it.
 *
 * Which states a structure keeps is fixed by the structure and does not change
 * over an instance's life, so whether this answers at all is established once
 * by the caller and the per-interval reads then only fail if the model itself
 * has stopped answering -- which is a refusal worth stopping on rather than
 * printing around.
 */
static const float *delivered_or_not(const plant_model_t *machine, bool kept, float *into)
{
    if (!kept) {
        return NULL;
    }
    if (!plant_model_state(machine, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, into)) {
        return NULL;
    }
    return into;
}

int cross_tier_draw_run(const plant_parameters_t *machine_parameters,
                        const plant_parameters_t *control_parameters,
                        const plant_parameter_budget_t *control_budget,
                        const estimator_limits_t *limits,
                        const delivery_tolerance_t *tolerance,
                        const pump_trim_declaration_t *pump_trim,
                        const cross_tier_draw_t *draw)
{
    plant_model_t machine;
    control_state_t state;
    float values[SENSED_CHANNEL_COUNT];
    int32_t converter_milli[SENSED_CHANNEL_COUNT];
    float outlet_c = 0.0f;
    float drawn_ml_per_s = 0.0f;

    if (!plant_model_init(&machine, machine_parameters)) {
        (void)fprintf(stderr, "cross-tier draw: the machine could not be initialised\n");
        return 1;
    }

    /*
     * Whether this structure keeps the temperature a delivery is judged by,
     * asked once. A structure that heats the water where it delivers it keeps
     * no such state, and a draw run against one reports the sensed quantities
     * and nothing under the delivered name -- rather than refusing to run,
     * which would make a legitimate architecture undrawable for want of a
     * figure it has no business having.
     */
    const bool outlet_kept =
        plant_model_state(&machine, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &outlet_c);

    hw_sim_reset();
    if (!stand_the_readings_up(&machine, draw, converter_milli)) {
        (void)fprintf(stderr, "cross-tier draw: the machine reported no quantity to read\n");
        return 1;
    }

    /* The machine as it came up, before anything has driven it. */
    if (!sensed(&machine, values) || !drawn_rate(&machine, &drawn_ml_per_s)) {
        return 1;
    }
    report("trajectory-baseline", -1, 0, 0u, 0u, 0uL, values, converter_milli,
           delivered_or_not(&machine, outlet_kept, &outlet_c), drawn_ml_per_s);

    if (!control_init(&state, control_parameters, control_budget, limits, tolerance, pump_trim)) {
        (void)fprintf(stderr, "cross-tier draw: the control path could not be brought up\n");
        return 1;
    }
    if (!control_command_temperature(&state, draw->target_c)) {
        (void)fprintf(stderr, "cross-tier draw: the draw's target was refused\n");
        return 1;
    }

    /*
     * Where the draw begins. Bringing the control path up commands every output
     * off, and a write reaching the pump is an interval's actuation wherever
     * this loop is closed -- so those writes are counted out here rather than
     * stepped, and the draw starts from the machine as it was initialised. A
     * loop closed through a machine's own peripherals has a bring-up of its own
     * that drives them too, and it starts from the same place for the same
     * reason: two models compared from wherever their bring-up left them are a
     * comparison of the bring-up.
     */
    uint32_t written = hw_sim_output_write_count(ACTUATION_CHANNEL_PUMP);
    unsigned long taken = 0uL;

    (void)printf("HOST pre-draw-steps %lu\n", (unsigned long)written);

    for (uint32_t interval = 0u; interval < draw->interval_count; interval++) {
        const uint32_t elapsed = draw->interval_millis[interval];
        const uint16_t asked_for = draw->pump_permille[interval];

        hw_sim_advance_millis(elapsed);

        /*
         * The flow the course asks for is commanded before the step rather than
         * held once at the top of the draw. It is what the step's own heater
         * feedforward reads, so a level that arrived after the step would be a
         * level the heater answered for one interval late -- and the loop this
         * run is compared against commands it in exactly this position.
         */
        if (!control_command_flow(&state, asked_for)) {
            (void)fprintf(stderr,
                          "cross-tier draw: the flow commanded at interval %u was refused\n",
                          interval);
            return 1;
        }

        const control_step_result_t result = control_step(&state);

        const uint32_t now_written = hw_sim_output_write_count(ACTUATION_CHANNEL_PUMP);
        const uint32_t owed = now_written - written;
        written = now_written;

        /*
         * The declared interval and not the elapsed one. What the clock did is
         * the control logic's business -- it advances its estimator by what
         * really passed -- but an actuation held over one control interval is
         * one control interval of actuation whatever the loop's own scheduling
         * was late by, and a machine advanced by the scheduling jitter instead
         * would be answering for the harness rather than for the actuation.
         */
        if (!advance_the_machine(&machine, owed, CONTROL_STEP_INTERVAL_MS)) {
            (void)fprintf(stderr,
                          "cross-tier draw: the machine refused the actuation interval %u "
                          "commanded\n",
                          interval);
            return 1;
        }
        taken += owed;

        if (!stand_the_readings_up(&machine, draw, converter_milli) || !sensed(&machine, values) ||
            !drawn_rate(&machine, &drawn_ml_per_s)) {
            (void)fprintf(stderr,
                          "cross-tier draw: the machine reported no quantity at interval %u\n",
                          interval);
            return 1;
        }
        /*
         * The level the heater was actually driven at, read back off the seam
         * rather than recomputed here. It is what says whether the loop was
         * controlling over this interval or merely holding the element at its
         * limit -- and a run pinned at full scale for the whole of a draw is one
         * whose sensed reading changed nothing it did, which is a comparison of
         * two open loops however closely the two agree.
         */
        report("trajectory", (int)interval, (int)result, (unsigned)asked_for,
               (unsigned)hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER), taken, values,
               converter_milli, delivered_or_not(&machine, outlet_kept, &outlet_c),
               drawn_ml_per_s);
    }

    (void)printf("HOST plant-step-count %lu\n", taken);
    (void)printf("HOST draw-intervals %u\n", draw->interval_count);
    (void)printf("HOST done\n");
    return 0;
}
