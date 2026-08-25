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
 * Nine significant digits, which is what round-trips an IEEE-754 single
 * precision value exactly. A narrower format would be this run's printing
 * introducing a disagreement rather than reporting one.
 */
#define QUANTITY_FORMAT "%.9g"

static void report(const char *what, int index, int result, unsigned pump, unsigned heater,
                   unsigned long taken, const float *values)
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

static bool stand_the_readings_up(const plant_model_t *machine, const cross_tier_draw_t *draw)
{
    float values[SENSED_CHANNEL_COUNT];

    if (!sensed(machine, values)) {
        return false;
    }
    for (size_t i = 0u; i < SENSED_CHANNEL_COUNT; i++) {
        hw_sim_set_sensor((hw_sensor_channel_t)i, HW_READING_VALID,
                          reported_milli(values[i], draw));
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

int cross_tier_draw_run(const plant_parameters_t *parameters,
                        const estimator_limits_t *limits,
                        const delivery_tolerance_t *tolerance,
                        const cross_tier_draw_t *draw)
{
    plant_model_t machine;
    control_state_t state;
    float values[SENSED_CHANNEL_COUNT];

    if (!plant_model_init(&machine, parameters)) {
        (void)fprintf(stderr, "cross-tier draw: the machine could not be initialised\n");
        return 1;
    }

    hw_sim_reset();
    if (!stand_the_readings_up(&machine, draw)) {
        (void)fprintf(stderr, "cross-tier draw: the machine reported no quantity to read\n");
        return 1;
    }

    /* The machine as it came up, before anything has driven it. */
    if (!sensed(&machine, values)) {
        return 1;
    }
    report("trajectory-baseline", -1, 0, 0u, 0u, 0uL, values);

    if (!control_init(&state, parameters, limits, tolerance)) {
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

        if (!stand_the_readings_up(&machine, draw) || !sensed(&machine, values)) {
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
               (unsigned)hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER), taken, values);
    }

    (void)printf("HOST plant-step-count %lu\n", taken);
    (void)printf("HOST draw-intervals %u\n", draw->interval_count);
    (void)printf("HOST done\n");
    return 0;
}
