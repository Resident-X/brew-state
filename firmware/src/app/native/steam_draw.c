/*
 * The host tier's steam loop, driven across a commanded draw.
 *
 * The arrangement is the one the steam law's own suite already establishes, and
 * it is the arrangement rather than the numbers that matters: the control law
 * reads a plant model it does not hold, through the simulated hardware seam,
 * and that model is then advanced under the levels the law actually got onto
 * the two steam channels. Nothing here can agree with itself by construction --
 * the law never sees the machine except through the seam, and the machine never
 * moves except under what the law drove.
 *
 * What this adds over that suite is that every file the run depends on is named
 * from outside it. The suite opens the description, the limits and the design's
 * steam figures from paths fixed when it was compiled, which is right for a
 * suite asserting about the machine this project is building and useless for a
 * run whose whole question is what a different machine would do. Here the three
 * arrive as arguments, so the same executable puts the same draw to as many
 * descriptions as a caller cares to write, without being rebuilt.
 *
 * No converter is modelled between the machine and the law, and the difference
 * from the brew draw beside it is deliberate rather than an oversight. That
 * draw exists to be put beside a loop closed through a real converter, so it
 * has to report through one or the two are different experiments. This draw is
 * put beside no such loop. A full scale written in here would be a fact about a
 * board nobody has selected -- and a truncation to counts nobody has chosen
 * would sit between every perturbation and its effect, quietly deciding which
 * of them were too small to survive being read.
 *
 * What the readings do pass through is the seam's own thousandths, which is not
 * a modelling choice but the vocabulary hw_interface.h states a reading in.
 */
#include "steam_draw.h"

#include <math.h>
#include <stdio.h>

#include "hw_sim.h"
#include "plant_model.h"
#include "steam_control.h"

/*
 * The quantities reported at every interval, in the hardware seam's own channel
 * order, each under the name it is reported by.
 *
 * All four rather than the steam pair alone. A run that reported only what it
 * expected to move could not tell a brew path standing still -- which is what a
 * steam draw should leave it doing on a machine whose two sides do not contend
 * -- from a brew path nobody looked at. The names are the ones the brew draw
 * beside this file prints and the ones everything downstream looks its figures
 * up by; a check in the emulation tier's tests holds the two lists to each
 * other, so a name that moved in one place and not the other fails there rather
 * than silently reading a quantity into the wrong column.
 */
static const plant_quantity_t sensed_quantity[] = {
    PLANT_QUANTITY_BREW_TEMPERATURE_C,  /* HW_SENSOR_BREW_TEMPERATURE */
    PLANT_QUANTITY_STEAM_TEMPERATURE_C, /* HW_SENSOR_STEAM_TEMPERATURE */
    PLANT_QUANTITY_BREW_PRESSURE_BAR,   /* HW_SENSOR_BREW_PRESSURE */
    PLANT_QUANTITY_STEAM_PRESSURE_BAR   /* HW_SENSOR_STEAM_PRESSURE */
};

#define SENSED_CHANNEL_COUNT (sizeof(sensed_quantity) / sizeof(sensed_quantity[0]))

static const char *const quantity_key[] = {"brew-c", "steam-c", "brew-bar", "steam-bar"};

_Static_assert(sizeof(quantity_key) / sizeof(quantity_key[0]) == SENSED_CHANNEL_COUNT,
               "every sensed quantity reported has to have a name to report it under");

/*
 * What the rate water is being drawn through the brew path at is reported
 * under, on the same terms and under the same name the brew draw beside this
 * file reports it: outside the table above, because the seam's flow channel has
 * nothing wired behind it on the board this project is building and a figure
 * reported through the sensed path would be claiming an instrument the machine
 * does not have.
 *
 * A steam draw should leave that rate at nothing throughout -- the brew pump is
 * never commanded here, and these two blocks are separately fed -- and printing
 * it is what turns that into something a reader can establish rather than
 * assume. It is the same argument the four sensed quantities above are all
 * reported under: a run that printed only the channels it expected to move
 * could not tell a brew path standing still from a brew path nobody looked at,
 * and a coefficient's signature across the channels is exactly a statement
 * about which of them it left alone.
 */
#define FLOW_KEY "brew-mlps"

/*
 * Nine significant digits, which is what round-trips an IEEE-754 single
 * precision value exactly. Every quantity the model carries is single
 * precision, and a narrower format would be this run's printing introducing a
 * difference between two machines rather than reporting one -- which is the one
 * thing a sweep reading these lines must never be handed.
 */
#define QUANTITY_FORMAT "%.9g"

/*
 * How far from nothing a reading is allowed to be before it is pinned there.
 *
 * Well inside what a signed thousandths reading is carried in, so that the
 * rounding below is never handed a figure the conversion cannot hold. It is not
 * a plausible span and is not doing that job: what a reading off a machine may
 * be is declared per channel in that machine's limits declaration, and the
 * control law refuses a reading outside it on its own terms. This exists only
 * so that a model handed an absurd coefficient -- which a sweep across declared
 * errors can produce, and which can carry a state to infinity or to no number
 * at all -- reaches that refusal as a pinned rail rather than through a
 * conversion the language leaves undefined.
 */
#define REPORTED_MILLI_LIMIT 2000000000.0f

/*
 * One quantity in the thousandths the hardware seam reports a reading in.
 *
 * The bounds are tested before the rounding rather than after, because rounding
 * a value the destination cannot hold -- or one that is not a number at all --
 * is undefined, and a reading arrived at by undefined behaviour is worse than
 * no reading. The comparison is written so that a value which is not a number
 * fails it: every comparison against such a value is false, so the negated
 * lower test catches it and pins it to the floor, where the machine's own
 * declared plausible span then refuses it as the absurdity it is.
 */
static int32_t milli_of(float value)
{
    const float milli = value * 1000.0f;

    if (!(milli > -REPORTED_MILLI_LIMIT)) {
        return (int32_t)(-REPORTED_MILLI_LIMIT);
    }
    if (milli > REPORTED_MILLI_LIMIT) {
        return (int32_t)REPORTED_MILLI_LIMIT;
    }
    return (int32_t)lroundf(milli);
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
 * Read on its own rather than through the table above, because that table's
 * entries are the quantities a converter input stands behind and this is not
 * one of them. A refusal is worth stopping the draw on: this is one of the
 * plant seam's quantities rather than one structure's state, and the seam
 * undertakes that every structure answers every quantity -- so a refusal here
 * says the model has stopped honouring that, not that this structure keeps no
 * such thing.
 */
static bool drawn_rate(const plant_model_t *machine, float *value)
{
    return plant_model_quantity(machine, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, value);
}

/*
 * One reported line: what the interval did, and what the machine reads once it
 * has done it.
 *
 * The findings are named rather than left to be read off by position, on the
 * terms the brew draw beside this file states: a reader looking for a name
 * fails where it is looked for when a field stops being printed, rather than
 * silently taking whatever now sits in that column.
 */
static void report(const char *what, int index, int result, unsigned drawing,
                   unsigned demand_milli, unsigned heater, unsigned feed, unsigned long taken,
                   const float *values, float flow)
{
    (void)printf("HOST %s", what);
    if (index >= 0) {
        (void)printf(" interval=%d result=%d drawing=%u demand=%u heater=%u feed=%u steps=%lu",
                     index, result, drawing, demand_milli, heater, feed, taken);
    }
    for (size_t i = 0u; i < SENSED_CHANNEL_COUNT; i++) {
        /* The cast is explicit because a variadic argument is promoted whatever
         * the source says, and the build refuses a silent promotion. */
        (void)printf(" %s=" QUANTITY_FORMAT, quantity_key[i], (double)values[i]);
    }
    (void)printf(" " FLOW_KEY "=" QUANTITY_FORMAT, (double)flow);
    (void)printf("\n");
}

/*
 * Stand up every channel the steam law reads, from the machine's own
 * quantities.
 *
 * The knob is not among them: no plant model answers it, because nothing inside
 * the machine decides whether a wand is turned. It carries what the course is
 * presently asking for, in the seam's own discrete spelling -- an interval
 * asking for a rate is an interval the contact reports made.
 */
static bool stand_the_readings_up(const plant_model_t *machine, bool wand_open)
{
    float pressure_bar = 0.0f;
    float temperature_c = 0.0f;

    if (!plant_model_quantity(machine, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &pressure_bar) ||
        !plant_model_quantity(machine, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &temperature_c)) {
        return false;
    }

    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, milli_of(pressure_bar));
    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID, milli_of(temperature_c));
    hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID,
                      wand_open ? HW_READING_DISCRETE_SET : HW_READING_DISCRETE_CLEAR);
    return true;
}

/*
 * Put the machine into the state the draw begins from.
 *
 * The temperature is written into the state the structure integrates, and then
 * the machine is advanced by one idle interval before anything reads it. The
 * second half is not tidiness: the relation between the steam path's pressure
 * and the block's temperature is evaluated when a model is advanced and not
 * when a state is written, so a run that published before that step would put
 * the pressure of the state the instance came up in onto the seam while
 * reporting the temperature of the state the draw asked for -- two different
 * machines, one interval apart, with nothing to say which the loop was reading.
 *
 * The interval it is advanced by is the draw's own first one, so that a course
 * stating an uneven cadence does not have a figure of this file's choosing
 * quietly inserted at its head.
 */
static bool bring_the_machine_to_where_the_draw_begins(plant_model_t *machine,
                                                       const steam_draw_t *draw)
{
    const plant_actuation_t idle = {{0u}};

    if (!plant_model_set_state(machine, PLANT_STATE_STEAM_TEMPERATURE_C,
                               draw->initial_steam_c)) {
        (void)fprintf(stderr,
                      "steam draw: this structure keeps no steam temperature to start the "
                      "machine at, so there is no steam side here to draw from\n");
        return false;
    }
    if (!plant_model_step(machine, &idle, 0.0f, draw->interval_millis[0])) {
        (void)fprintf(stderr,
                      "steam draw: the machine refused the idle interval that settles the state "
                      "the draw begins from\n");
        return false;
    }
    return true;
}

int steam_draw_run(const plant_parameters_t *parameters,
                   const estimator_limits_t *limits,
                   const steam_control_declaration_t *declaration,
                   const steam_draw_t *draw)
{
    plant_model_t machine;
    steam_control_state_t loop;
    float values[SENSED_CHANNEL_COUNT];
    float drawn_ml_per_s = 0.0f;

    /*
     * A course stating no interval is refused before anything is read off it.
     * Nothing presently reaching this entry point can bring one -- the reader
     * that assembles a course from a file will not return an empty one -- but
     * the first thing this run does is advance the machine by the course's own
     * first interval, so an empty course would be read off the front of an
     * array nobody wrote to and the draw would proceed on whatever was there.
     * This is offered as an entry point rather than as something only its
     * present caller may use, and the difference between the two is exactly
     * whether it establishes what it was handed or trusts the one caller that
     * exists today to have been careful.
     */
    if (draw->interval_count == 0u) {
        (void)fprintf(stderr,
                      "steam draw: the course states no interval, so there is no draw here to "
                      "run and no delivery for anything to be judged on\n");
        return 1;
    }

    if (!plant_model_init(&machine, parameters)) {
        (void)fprintf(stderr, "steam draw: the machine could not be initialised\n");
        return 1;
    }
    if (!bring_the_machine_to_where_the_draw_begins(&machine, draw)) {
        return 1;
    }

    hw_sim_reset();
    if (!stand_the_readings_up(&machine, false)) {
        (void)fprintf(stderr, "steam draw: the machine reported no quantity to read\n");
        return 1;
    }

    /* The machine as the draw found it, before the loop has driven anything. */
    if (!sensed(&machine, values) || !drawn_rate(&machine, &drawn_ml_per_s)) {
        return 1;
    }
    report("steam-trajectory-baseline", -1, 0, 0u, 0u, 0u, 0u, 0uL, values, drawn_ml_per_s);

    /*
     * The one interval spent settling the state the draw begins from, reported
     * rather than left for a reader to know about. A run compared against
     * another has to be able to establish that both began from the same place,
     * and how many times the machine had already been advanced when the first
     * interval was reported is half of that.
     */
    (void)printf("HOST steam-settling-steps 1\n");

    if (!steam_control_init(&loop, limits, declaration)) {
        (void)fprintf(stderr, "steam draw: the steam control path could not be brought up\n");
        return 1;
    }

    unsigned long taken = 1uL;

    for (uint32_t interval = 0u; interval < draw->interval_count; interval++) {
        const uint32_t elapsed = draw->interval_millis[interval];
        const uint32_t demand_milli = draw->demand_milli_ml_per_s[interval];
        const bool wand_open = demand_milli > 0u;

        /*
         * The clock is advanced before the step rather than after it, so that
         * the interval the law measures for itself is the one the course
         * declared for that interval and not the one declared for the interval
         * before. The first step has no predecessor to have elapsed from and
         * accumulates nothing whatever the clock says, which is the law's own
         * statement about itself rather than something this run arranges.
         */
        hw_sim_advance_millis(elapsed);

        if (!stand_the_readings_up(&machine, wand_open)) {
            (void)fprintf(stderr,
                          "steam draw: the machine reported no reading to stand up at interval "
                          "%u\n",
                          interval);
            return 1;
        }

        const steam_control_step_result_t result = steam_control_step(&loop);

        /*
         * The machine is advanced under what reached the channels, read back
         * off the seam rather than recomputed from what the law was asked for.
         * A refused drive command leaves a channel where it was, and a run that
         * assumed the command had landed would advance the model under a level
         * the machine never saw.
         */
        plant_actuation_t driven = {{0u}};
        driven.level_permille[ACTUATION_CHANNEL_STEAM_HEATER] =
            hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER);
        driven.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] =
            hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);

        /*
         * The rate is carried into the step rather than onto a channel, because
         * nothing commands it: the wand is a mechanical valve opened by hand,
         * and what leaves through it arrives at the model from outside the
         * machine. It is divided down from the thousandths the course states it
         * in, which is the resolution a course file can express and not a claim
         * about what any instrument could measure -- nothing on this machine
         * measures it at all.
         */
        const float demand_ml_per_s = (float)demand_milli / 1000.0f;

        if (!plant_model_step(&machine, &driven, demand_ml_per_s, elapsed)) {
            (void)fprintf(stderr,
                          "steam draw: the machine refused the actuation interval %u commanded\n",
                          interval);
            return 1;
        }
        taken++;

        if (!sensed(&machine, values) || !drawn_rate(&machine, &drawn_ml_per_s)) {
            (void)fprintf(stderr, "steam draw: the machine reported no quantity at interval %u\n",
                          interval);
            return 1;
        }

        /*
         * Both driven levels are reported, and the feed's is the one a reader
         * cannot do without: the band this loop is held to states the character
         * of the steam coming out, and before feed engages there is none coming
         * out to have a character. Where a run's judged window begins is
         * therefore something the run itself has to say, not something a reader
         * can work out from the course.
         */
        bool drawing = false;
        (void)steam_control_drawing(&loop, &drawing);
        report("steam-trajectory", (int)interval, (int)result, drawing ? 1u : 0u,
               (unsigned)demand_milli,
               (unsigned)hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
               (unsigned)hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP), taken, values,
               drawn_ml_per_s);
    }

    (void)printf("HOST steam-plant-step-count %lu\n", taken);
    (void)printf("HOST steam-draw-intervals %u\n", draw->interval_count);
    (void)printf("HOST done\n");
    return 0;
}
