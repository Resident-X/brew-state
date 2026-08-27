/*
 * Host entry point.
 *
 * This is what the tier-one analysis stage runs. It drives the control-logic
 * entry path against the simulated hardware implementation, and it drives the
 * plant model through the plant-model seam, for a bounded number of steps
 * each, so that the memory and undefined-behaviour analysis has a subject that
 * actually executes both paths rather than merely linking them.
 *
 * It walks the paths the control logic can take -- an ordinary actuating step,
 * a step arriving before the interval has elapsed, a step riding out a brief
 * gap in the reading, a step whose gap has outlasted what the machine declares
 * tolerable, and a step whose drive command is refused -- because a run that
 * only ever takes the happy path leaves the others unanalysed. It walks every
 * way a parameter description and a limits declaration can be refused for the
 * same reason.
 *
 * The parameter description is named on the command line rather than compiled
 * in, so the same executable runs different parameter values without being
 * rebuilt. It is the machine's, and by default it is handed to the control path
 * as well, because the control path drives from a state reconstructed against a
 * record of the machine and the ordinary case is that the record it holds is
 * the right one.
 *
 * The brew draw can be given a second description for that control path, and
 * then the two come apart: the machine is built from the first and the
 * reconstruction the loop drives from is built from the second. That is what a
 * machine which has fouled or aged is -- a casting somewhere its controller's
 * figures no longer describe -- and it is not the same experiment as two
 * machines each built consistently to its own coefficients. Naming it rather
 * than deriving it, on the terms the limits declaration is named rather than
 * substituted for: a run whose two descriptions are the same file has said so,
 * and a run whose control path was quietly given the machine's would be
 * reporting the first experiment under the second's name.
 *
 * The limits declaration is named beside it on the same terms. It says what a
 * reading off this machine may plausibly be and how long the estimator may go
 * without one, which is a fact about a machine and its sensors rather than
 * about the software, so it varies with the description and is supplied with
 * it. Naming it rather than deriving its path from the description's is
 * deliberate: a path arrived at by substitution is a second statement of which
 * files belong together, and it goes on producing a plausible answer after
 * somebody renames one of them.
 *
 * The tolerance declaration is not named on the command line, and the
 * difference is the point. The two files above vary with the machine the
 * exercise is run against -- a different casting has different coefficients and
 * its sensors have different plausible ranges -- so which of them to read is a
 * decision the caller makes per run. How far from the temperature it was asked
 * for a delivery may sit does not vary that way: it is what the drink demands,
 * and it would read the same on a machine of another kind entirely. So the path
 * to it is fixed at build time, and an exercise cannot be run against a band
 * nobody declared by leaving an argument off.
 *
 * Nothing here names a plant structure. Whether the control path comes up at
 * all is therefore something this exercise observes rather than assumes: a
 * structure that cannot carry a reconstruction the estimator can keep
 * corrected -- whether because it keeps no state for the reconstruction
 * itself, or because it keeps that state but not the different one the
 * estimator's correction writes toward -- is one the control path refuses to
 * start against, and that refusal is a path worth walking on the artefacts
 * built against such a structure. Both outcomes are exercised, and which one
 * happened is printed.
 *
 * Given a draw to run instead, this executable runs that and only that. There
 * are two of them -- the brew side's, in cross_tier_draw.c, and the steam
 * side's, in steam_draw.c -- and both are reached from here rather than from
 * executables of their own because each needs exactly what this one is already
 * linked from: the control logic, the simulated hardware seam and the plant
 * model. Further host artefacts carrying the same three would be further builds
 * of the same tier for no question the first cannot answer. No two of the three
 * modes share a run: the exercise deliberately drives the loop into faults and
 * refusals, and a draw begun after that would be a draw of a machine somebody
 * had already broken.
 *
 * The steam draw is named a file the other two are not: the figures the steam
 * control law is given rather than compiled with. It arrives on the command
 * line beside the description and the limits rather than being fixed at build
 * time the way the delivery band is, because it is not the same kind of
 * statement. The band says what the drink demands and would read the same on a
 * machine of another kind entirely; the steam figures are the design's policy
 * about a particular steam path, and every gain in them was chosen against a
 * particular casting's coefficients. Which of them to read is therefore a
 * decision that travels with the description, and is a caller's per run.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "control.h"
#include "cross_tier_draw.h"
#include "delivery_tolerance.h"
#include "estimator_limits.h"
#include "hw_sim.h"
#include "machine_actuation.h"
#include "plant_model.h"
#include "steam_control_declaration.h"
#include "steam_draw.h"

/* What names each draw mode on the command line, and how many arguments follow it. */
#define DRAW_OPTION "--cross-tier-draw"
#define DRAW_ARGUMENTS 4
#define STEAM_DRAW_OPTION "--steam-draw"
#define STEAM_DRAW_ARGUMENTS 3

/*
 * What names the description the brew draw's control path is built from, and
 * how many arguments follow it.
 *
 * It is written after the draw's own arguments rather than beside the
 * description at the front, and the position says what it is: the description
 * at the front is the machine's, which every mode needs, and this one is a
 * statement about one draw's control path that only that draw can act on. A
 * second description at the front would have to mean something to the exercise
 * and to the steam draw as well, and it means nothing to either -- the exercise
 * walks the control logic's paths against the machine it was given, and the
 * steam law is built from its own declaration and no description at all.
 *
 * Leaving it off is not an omission and is the ordinary case: a draw handed one
 * description gives it to the machine and the control path alike, which is what
 * a comparison of two tiers running the same machine needs and what every
 * caller before this option existed was asking for.
 */
#define CONTROL_DESCRIPTION_OPTION "--control-description"
#define CONTROL_DESCRIPTION_ARGUMENTS 1

/* Steps to run in each phase of the exercise. */
#define EXERCISE_STEPS 64

/* The interval each modelled step advances the plant by. */
#define PLANT_STEP_INTERVAL_MS 100u

/*
 * The temperature this exercise asks the machine for, in degrees Celsius.
 *
 * There is no setpoint compiled into the control logic: what a delivery is
 * driven toward is state a caller sets, so an exercise that wants the loop to
 * drive has to ask for something. The figure is this exercise's own choice of
 * an ordinary brew temperature and is not a claim about what any drink wants --
 * a machine asked for nothing correctly drives nothing, which is a path this
 * run also walks below rather than one it works around.
 */
#define EXERCISE_TARGET_C 93.0f

static int failures;

static void expect(bool condition, const char *what)
{
    if (!condition) {
        (void)fprintf(stderr, "host exercise: %s\n", what);
        failures++;
    }
}

/*
 * A machine nobody has asked for a drink drives nothing and says so, and the
 * run walks that before asking for anything. It is the ordinary condition of a
 * machine between deliveries rather than a fault, so what has to hold is that
 * the outputs are off, the path is not latched, and the step is still counted --
 * a control path that latched here would need clearing before the next drink.
 */
static void exercise_untargeted_steps(control_state_t *state)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);

    for (int i = 0; i < EXERCISE_STEPS; i++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        expect(control_step(state) == CONTROL_STEP_NO_TARGET,
               "a machine asked for nothing drove toward something");
    }
    expect(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) == 0u,
           "the heater was driven with no temperature commanded");
    expect(hw_sim_output(ACTUATION_CHANNEL_PUMP) == 0u,
           "the pump was driven with no temperature commanded");
}

static void exercise_actuating_steps(control_state_t *state)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    expect(control_command_temperature(state, EXERCISE_TARGET_C),
           "the exercise's target was refused");

    for (int i = 0; i < EXERCISE_STEPS; i++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        expect(control_step(state) == CONTROL_STEP_ACTUATED, "an actuating step did not actuate");
    }
    expect(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) > 0u, "the heater was never driven");
}

static void exercise_early_step(control_state_t *state)
{
    expect(control_step(state) == CONTROL_STEP_TOO_SOON, "a step inside the interval was accepted");
}

/*
 * Both sides of a lost reading, because they are different paths and a run that
 * walked only one would leave the other unanalysed. A brief gap is an ordinary
 * operating condition the machine drives through; a sustained one is the
 * estimator withdrawing the state, which is what brings the heater down.
 *
 * How many steps the first takes is not asserted here -- where the window falls
 * belongs to the machine's declaration and to the suites that test it. What
 * this establishes is that both paths execute.
 */
static void exercise_invalid_sensor(control_state_t *state)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_FAILED, 0);

    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    expect(control_step(state) == CONTROL_STEP_ACTUATED,
           "a single missing reading brought the machine down");

    bool brought_down = false;
    for (int i = 0; i < EXERCISE_STEPS * 16 && !brought_down; i++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        brought_down = control_step(state) == CONTROL_STEP_SENSOR_INVALID;
    }
    expect(brought_down, "a reading gone for good was ridden indefinitely");
    expect(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) == 0u,
           "the heater stayed on through a fault");
}

static void exercise_refused_output(const plant_parameters_t *parameters,
                                    const estimator_limits_t *limits,
                                    const delivery_tolerance_t *tolerance)
{
    control_state_t state;

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);
    expect(control_init(&state, parameters, limits, tolerance),
           "the control path could not be initialised");
    expect(control_command_temperature(&state, EXERCISE_TARGET_C),
           "the exercise's target was refused");
    hw_sim_set_output_refused(true);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    expect(control_step(&state) == CONTROL_STEP_OUTPUT_REFUSED,
           "a refused drive was reported as success");
}

/*
 * What a control path that refused to start must do, on the artefacts built
 * against a structure the estimator cannot reconstruct from. The refusal is
 * only worth anything if it holds: the heater must be off, and it must stay off
 * however many steps arrive afterwards.
 */
static void exercise_refused_reconstruction(control_state_t *state)
{
    expect(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) == 0u,
           "a refused initialisation left the heater driven");

    for (int i = 0; i < EXERCISE_STEPS; i++) {
        hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
        expect(control_step(state) == CONTROL_STEP_FAULT_LATCHED,
               "a step after a refused initialisation was not latched");
    }
    expect(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) == 0u,
           "the heater was driven after a refused initialisation");
}

/* Read a whole file into a heap buffer. The caller frees it. */
static char *read_file(const char *path, size_t *length)
{
    FILE *handle = fopen(path, "rb");
    if (handle == NULL) {
        (void)fprintf(stderr, "host exercise: cannot open %s\n", path);
        return NULL;
    }

    size_t capacity = 4096u;
    size_t used = 0u;
    char *buffer = malloc(capacity);
    if (buffer == NULL) {
        (void)fprintf(stderr, "host exercise: no room to read %s\n", path);
        (void)fclose(handle);
        return NULL;
    }

    for (;;) {
        if (used == capacity) {
            capacity *= 2u;
            char *grown = realloc(buffer, capacity);
            if (grown == NULL) {
                (void)fprintf(stderr, "host exercise: no room to read the whole of %s\n", path);
                free(buffer);
                (void)fclose(handle);
                return NULL;
            }
            buffer = grown;
        }
        const size_t read = fread(buffer + used, 1u, capacity - used, handle);
        used += read;
        if (read == 0u) {
            break;
        }
    }

    (void)fclose(handle);
    *length = used;
    return buffer;
}

/*
 * The course a draw is run along: one line per control interval, each carrying
 * the milliseconds the clock advances before that interval and the one figure
 * that interval commands. The count of lines decides how many intervals the
 * draw runs for.
 *
 * What the second figure means belongs to the draw being run and not to this
 * reader. The brew draw reads it as the permille the pump is asked for; the
 * steam draw reads it as the thousandths of a millilitre per second the wand is
 * passing. That is why the ceiling a figure is held to and the sentence a
 * refusal is reported in both arrive as arguments -- a reader carrying either
 * of them would be a reader that knew which draw it was serving, and the second
 * draw would then need a second copy of the whole of this.
 *
 * A file of figures rather than a pair of figures repeated, and for two separate
 * reasons. The cadence is a sequence because a loop closed through an emulated
 * machine does not keep a perfectly even one, and the control logic advances its
 * estimator by the interval that actually elapsed rather than the one the loop is
 * meant to run at -- so reproducing another loop's draw means reproducing what
 * that loop's clock did. The commanded figure is a sequence because a draw is a
 * shape: nothing moves while the block is coming up, something is drawn once it
 * is, and a level held at one figure for the whole run would leave what it acts
 * on settled after its first few intervals and asked nothing further.
 *
 * The two travel in one file rather than two, so that a draw cannot be run with a
 * cadence of one length against a course of another -- which is not a run with a
 * mistake in it but two different draws, and neither loop would be able to say
 * which one it had been given.
 *
 * Returns false and reports why on any file that cannot be opened, holds something
 * that is not a whole number of milliseconds, carries a figure beyond the ceiling
 * the caller stated, leaves an interval without a figure, or holds no interval at
 * all -- a draw of no intervals is not a short draw, it is not a draw. The caller
 * frees both arrays it writes.
 */
static bool grow_the_course(uint32_t **intervals, uint32_t **commanded, size_t *capacity)
{
    const size_t wanted = *capacity * 2u;

    /* Each is taken only where it was obtained, so a pair where one grew and the
     * other did not still frees exactly what it holds rather than the address it
     * used to hold. */
    uint32_t *grown_intervals = realloc(*intervals, wanted * sizeof(**intervals));
    if (grown_intervals != NULL) {
        *intervals = grown_intervals;
    }
    uint32_t *grown_commanded = realloc(*commanded, wanted * sizeof(**commanded));
    if (grown_commanded != NULL) {
        *commanded = grown_commanded;
    }
    if (grown_intervals == NULL || grown_commanded == NULL) {
        return false;
    }

    *capacity = wanted;
    return true;
}

static bool read_the_course(const char *path, unsigned long ceiling, const char *what,
                            uint32_t **interval_millis, uint32_t **commanded, uint32_t *count)
{
    FILE *handle = fopen(path, "r");
    if (handle == NULL) {
        (void)fprintf(stderr, "host exercise: cannot open %s\n", path);
        return false;
    }

    size_t capacity = 256u;
    size_t used = 0u;
    uint32_t *intervals = malloc(capacity * sizeof(*intervals));
    uint32_t *levels = malloc(capacity * sizeof(*levels));
    if (intervals == NULL || levels == NULL) {
        (void)fprintf(stderr, "host exercise: no room to read the course in %s\n", path);
        free(intervals);
        free(levels);
        (void)fclose(handle);
        return false;
    }

    bool readable = true;
    bool ended = false;
    while (readable && !ended) {
        unsigned long millis = 0uL;
        unsigned long level = 0uL;
        const int read_millis = fscanf(handle, "%lu", &millis);

        if (read_millis == EOF) {
            ended = true;
        } else if (read_millis != 1 || millis == 0uL || millis > 0xFFFFFFFFuL) {
            (void)fprintf(stderr, "host exercise: %s holds something that is not an interval\n",
                          path);
            readable = false;
        } else if (fscanf(handle, "%lu", &level) != 1 || level > ceiling) {
            (void)fprintf(stderr, "host exercise: the interval on line %lu of %s carries no %s\n",
                          (unsigned long)used + 1uL, path, what);
            readable = false;
        } else if (used == capacity && !grow_the_course(&intervals, &levels, &capacity)) {
            (void)fprintf(stderr, "host exercise: no room to read the whole course in %s\n", path);
            readable = false;
        } else {
            intervals[used] = (uint32_t)millis;
            levels[used] = (uint32_t)level;
            used++;
        }
    }

    (void)fclose(handle);

    if (readable && used == 0u) {
        (void)fprintf(stderr, "host exercise: %s declares no interval to run\n", path);
        readable = false;
    }
    if (!readable) {
        free(intervals);
        free(levels);
        return false;
    }

    *interval_millis = intervals;
    *commanded = levels;
    *count = (uint32_t)used;
    return true;
}

/*
 * Run the draw the command line asked for, and nothing else.
 *
 * Every figure is taken from the arguments rather than compiled in. The target
 * and the course are what the draw is; the converter's full scale is a fact
 * about a board this tier does not have, and a run comparing this loop against
 * one closed through a real converter has to hold both to the same reporting.
 *
 * The two descriptions arrive already loaded, and both are required. Where the
 * caller named no second one it hands this the same record twice, which is a
 * loop that knows the machine it is driving; where it named one they differ,
 * and the loop is driving a machine its own figures no longer describe.
 */
static int run_the_draw(char **arguments, const plant_parameters_t *machine_parameters,
                        const plant_parameters_t *control_parameters,
                        const estimator_limits_t *limits,
                        const delivery_tolerance_t *tolerance)
{
    cross_tier_draw_t draw = {0.0f, NULL, NULL, 0u, 0u, 0u};
    char *end = NULL;

    draw.target_c = strtof(arguments[0], &end);
    if (end == arguments[0] || *end != '\0') {
        (void)fprintf(stderr, "host exercise: '%s' is not a temperature to draw toward\n",
                      arguments[0]);
        return 2;
    }

    const unsigned long counts = strtoul(arguments[1], &end, 10);
    if (end == arguments[1] || *end != '\0' || counts == 0uL || counts > 0xFFFFFFFFuL) {
        (void)fprintf(stderr, "host exercise: '%s' is not a converter full scale\n",
                      arguments[1]);
        return 2;
    }

    /*
     * Bounded by what a reading is carried in and not merely by what the figure
     * is stored in. The hardware seam reports a reading as a signed figure in
     * thousandths, so a full scale beyond what that holds is a scale no reading
     * off it could be reported at -- refused here, where a caller can be told
     * which argument was wrong, rather than folded over silently in the
     * converter arithmetic.
     */
    const unsigned long milli = strtoul(arguments[2], &end, 10);
    if (end == arguments[2] || *end != '\0' || milli == 0uL ||
        milli > (unsigned long)INT32_MAX) {
        (void)fprintf(stderr, "host exercise: '%s' is not a full scale in milli-units\n",
                      arguments[2]);
        return 2;
    }

    draw.converter_full_scale_counts = (uint32_t)counts;
    draw.converter_full_scale_milli = (uint32_t)milli;

    uint32_t intervals = 0u;
    uint32_t *cadence = NULL;
    uint32_t *commanded = NULL;
    if (!read_the_course(arguments[3], (unsigned long)ACTUATION_FULL_SCALE,
                         "level the pump can be asked for", &cadence, &commanded, &intervals)) {
        return 1;
    }

    /*
     * Narrowed into the width the draw's own record carries a pump level in.
     * Nothing is lost by it: the reader refused every figure above full scale,
     * and full scale is three orders of magnitude inside what this holds. It is
     * a copy rather than a cast of the array because the two widths are not the
     * same object, and a record pointed at the wider one would read every level
     * from the wrong half of a figure on the first machine whose endianness
     * disagreed with the author's.
     */
    uint16_t *levels = malloc((size_t)intervals * sizeof(*levels));
    if (levels == NULL) {
        (void)fprintf(stderr, "host exercise: no room to hold the course's pump levels\n");
        free(cadence);
        free(commanded);
        return 1;
    }
    for (uint32_t at = 0u; at < intervals; at++) {
        levels[at] = (uint16_t)commanded[at];
    }
    free(commanded);

    draw.interval_millis = cadence;
    draw.pump_permille = levels;
    draw.interval_count = intervals;

    const int outcome =
        cross_tier_draw_run(machine_parameters, control_parameters, limits, tolerance, &draw);
    free(cadence);
    free(levels);
    return outcome;
}

/*
 * Run the steam draw the command line asked for, and nothing else.
 *
 * The steam control declaration is opened here rather than in the draw itself,
 * on the terms the description and the limits are opened in main: reading a
 * file and running a loop are different jobs, and a draw that opened its own
 * inputs could not be handed one that came from anywhere else.
 *
 * The state the machine starts in is taken from the arguments for the reason
 * the draw's own header gives at length -- it is where the design says the
 * machine stands when somebody turns the wand, and that figure is declared
 * rather than being this file's to remember.
 */
static int run_the_steam_draw(char **arguments, const plant_parameters_t *parameters,
                              const estimator_limits_t *limits)
{
    steam_draw_t draw = {0.0f, NULL, NULL, 0u};
    char *end = NULL;

    size_t length = 0u;
    char *text = read_file(arguments[0], &length);
    if (text == NULL) {
        return 1;
    }

    steam_control_declaration_t declaration;
    steam_control_declaration_error_t declaration_error;
    const bool declared =
        steam_control_declaration_load(text, length, &declaration, &declaration_error);
    free(text);

    if (!declared) {
        (void)fprintf(stderr,
                      "host exercise: steam control declaration refused: %s (fault %d, line %u)\n",
                      declaration_error.name, (int)declaration_error.fault,
                      declaration_error.line);
        return 1;
    }

    draw.initial_steam_c = strtof(arguments[1], &end);
    if (end == arguments[1] || *end != '\0') {
        (void)fprintf(stderr, "host exercise: '%s' is not a temperature to start the block at\n",
                      arguments[1]);
        return 2;
    }

    /*
     * The ceiling on a commanded rate is what the figure is carried in and not
     * a judgement about how fast a wand can pass steam. Nobody has established
     * that rate for this machine or its type, and inventing a bound here would
     * be this file quietly declaring one. What refuses a rate the equations
     * cannot act on is the model's own admissibility guard, which is where the
     * question belongs.
     */
    uint32_t intervals = 0u;
    uint32_t *cadence = NULL;
    uint32_t *demand = NULL;
    if (!read_the_course(arguments[2], 0xFFFFFFFFuL,
                         "rate the wand can be passing, in thousandths of a millilitre per second",
                         &cadence, &demand, &intervals)) {
        return 1;
    }
    draw.interval_millis = cadence;
    draw.demand_milli_ml_per_s = demand;
    draw.interval_count = intervals;

    const int outcome = steam_draw_run(parameters, limits, &declaration, &draw);
    free(cadence);
    free(demand);
    return outcome;
}

/*
 * Every way a parameter description can be refused, so the refusal paths are
 * executed under the analysis rather than only the accepting one. Each of these
 * must be refused whatever structure the build compiled: an empty description
 * is missing whatever that structure requires, and the others are wrong before
 * any structure's table is consulted.
 */
static void exercise_refused_descriptions(void)
{
    static const char *const refused[] = {
        "",
        "this line has no separator\n",
        " = 12.0\n",
        "definitely.not.a.parameter = 1.0\n",
        "definitely.not.a.parameter = not-a-number\n",
        /*
         * A statement no description is entitled to make. This is the one
         * annotation fault reachable without naming a coefficient, and naming
         * one here would tie this exercise to a structure. The rest of the
         * annotation grammar's refusals are driven by the model's own tests,
         * which know what the structure they are built against has.
         */
        "@describes-a-machine\n",
        /*
         * An unknown coefficient carrying a well-formed origin. An annotation
         * is not a way past the checks a line already faced.
         */
        "definitely.not.a.parameter = 1.0 @document a page nobody has\n",
    };

    for (size_t i = 0u; i < sizeof(refused) / sizeof(refused[0]); i++) {
        plant_parameters_t parameters;
        plant_parameter_error_t error;
        const bool accepted =
            plant_parameters_load(refused[i], strlen(refused[i]), &parameters, &error);
        expect(!accepted, "a refusable parameter description was accepted");
        expect(error.fault != PLANT_PARAMETER_OK, "a refusal reported no fault");
    }
}

/*
 * Every way a limits declaration can be refused, so those paths are executed
 * under the analysis rather than only the accepting one. None of these names a
 * plant structure, so each is refusable whatever structure the build compiled.
 */
static void exercise_refused_limits(void)
{
    static const char *const refused[] = {
        "",
        "this line has no separator\n",
        " = 1 .. 2\n",
        "definitely-not-a-channel = 1 .. 2\n",
        "brew-temperature = 1\n",
        "brew-temperature = not-a-number .. 2\n",
        "brew-temperature = 20 .. 10\n",
        "brew-temperature = 10 .. 10\n",
        "@describes-a-machine\n",
        "brew-temperature = 1 .. 2 @document\n",
        "brew-temperature = 1 .. 2 @invented an origin nobody declared\n",
    };

    for (size_t i = 0u; i < sizeof(refused) / sizeof(refused[0]); i++) {
        estimator_limits_t limits;
        estimator_limits_error_t error;
        const bool accepted =
            estimator_limits_load(refused[i], strlen(refused[i]), &limits, &error);
        expect(!accepted, "a refusable limits declaration was accepted");
        expect(error.fault != ESTIMATOR_LIMITS_OK, "a refusal reported no fault");
    }
}

static void exercise_plant(const plant_parameters_t *parameters)
{
    plant_model_t model;
    expect(plant_model_init(&model, parameters), "the plant model could not be initialised");

    /*
     * Drive what the structure this artefact was built against says it answers,
     * read through the seam rather than assumed: the two artefacts this exercise
     * is run as are built against structures that answer different channels, and
     * commanding a channel a structure does not answer is refused rather than
     * absorbed.
     */
    const actuation_channel_set_t answered = plant_structure_actuation_channels();
    plant_actuation_t heating = {{0u}};
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        if ((answered & ACTUATION_CHANNEL_BIT(channel)) == 0u) {
            continue;
        }
        heating.level_permille[channel] =
            (channel == (unsigned)ACTUATION_CHANNEL_PUMP) ? ACTUATION_FULL_SCALE / 2u
                                                          : ACTUATION_FULL_SCALE;
    }
    for (int i = 0; i < EXERCISE_STEPS; i++) {
        expect(plant_model_step(&model, &heating, 0.0f, PLANT_STEP_INTERVAL_MS),
               "a plant step was refused");
    }

    /* Steps the seam must refuse, so those paths are executed too. */
    plant_actuation_t over_scale = {{0u}};
    over_scale.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = ACTUATION_FULL_SCALE + 1u;
    plant_step_error_t refusal;
    expect(!plant_model_step_reporting(&model, &over_scale, 0.0f, PLANT_STEP_INTERVAL_MS,
                                       &refusal),
           "an out-of-scale actuation was accepted");
    expect(refusal.fault == PLANT_STEP_LEVEL_OVER_SCALE,
           "an out-of-scale actuation was refused for the wrong reason");
    expect(!plant_model_step(&model, &heating, 0.0f, 0u), "a zero-length step was accepted");

    /*
     * The unanswered-channel path, on the artefacts whose structure leaves one
     * unanswered. A structure that answers everything cannot exercise it, and
     * pretending otherwise here would report a path as run that was not.
     */
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        if ((answered & ACTUATION_CHANNEL_BIT(channel)) != 0u) {
            continue;
        }
        plant_actuation_t unanswered = {{0u}};
        unanswered.level_permille[channel] = ACTUATION_FULL_SCALE;
        expect(!plant_model_step_reporting(&model, &unanswered, 0.0f, PLANT_STEP_INTERVAL_MS,
                                           &refusal),
               "a command on an unanswered channel was accepted");
        expect(refusal.fault == PLANT_STEP_CHANNEL_UNANSWERED &&
                   (unsigned)refusal.channel == channel,
               "a refused command did not name the channel that had nowhere to land");
    }

    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        float value = 0.0f;
        expect(plant_model_quantity(&model, (plant_quantity_t)quantity, &value),
               "a quantity the model exposes could not be read");
        /* The cast is explicit because a variadic argument is promoted
         * whatever the source says, and the build refuses a silent one. */
        (void)printf("plant quantity %d = %.6f\n", quantity, (double)value);
    }

    float unused = 0.0f;
    expect(!plant_model_quantity(&model, PLANT_QUANTITY_COUNT, &unused),
           "a quantity outside the enumerated ones was answered");

    exercise_refused_descriptions();
    exercise_refused_limits();
}

/*
 * Read one parameter description and stand it up, reporting why if it is
 * refused.
 *
 * One reader for however many descriptions a run names, because a second copy
 * of it would be free to admit a description on terms the first does not -- and
 * the whole of what a run naming two of them means is that the same kind of
 * statement was made twice about two different things. A machine admitted by
 * one set of checks and a controller's record admitted by another would not be
 * comparable at all.
 */
static bool load_a_description(const char *path, plant_parameters_t *into)
{
    size_t length = 0u;
    char *text = read_file(path, &length);
    if (text == NULL) {
        return false;
    }

    plant_parameter_error_t error;
    const bool loaded = plant_parameters_load(text, length, into, &error);
    free(text);

    if (!loaded) {
        (void)fprintf(stderr,
                      "host exercise: parameter description %s refused: %s (fault %d, line %u)\n",
                      path, error.parameter, (int)error.fault, error.line);
    }
    return loaded;
}

int main(int argc, char **argv)
{
    control_state_t state;

    /*
     * Which of the three modes was asked for, settled before anything is
     * opened. A mode is named only when its own option is written and exactly
     * the arguments that option takes follow it; anything else past the limits
     * declaration is an unrecognised ask and is refused with the whole usage
     * rather than being run as the mode it most resembles.
     *
     * The brew draw is the one mode that admits a further option after its own
     * arguments, and it is admitted only in that one position and only under
     * its own name. A trailing argument accepted on its position alone would
     * make a mistyped option a control-path description, which is a run that
     * proceeds and answers the wrong question.
     */
    const bool something_requested = argc > 3;
    const bool draw_named = something_requested && strcmp(argv[3], DRAW_OPTION) == 0;
    const bool drifted_draw_requested =
        draw_named && argc == 4 + DRAW_ARGUMENTS + 1 + CONTROL_DESCRIPTION_ARGUMENTS &&
        strcmp(argv[4 + DRAW_ARGUMENTS], CONTROL_DESCRIPTION_OPTION) == 0;
    const bool draw_requested = draw_named && (argc == 4 + DRAW_ARGUMENTS ||
                                               drifted_draw_requested);
    const bool steam_draw_requested = something_requested &&
                                      strcmp(argv[3], STEAM_DRAW_OPTION) == 0 &&
                                      argc == 4 + STEAM_DRAW_ARGUMENTS;

    if (argc < 3 || (something_requested && !draw_requested && !steam_draw_requested)) {
        (void)fprintf(stderr,
                      "usage: %s <parameter-description> <limits-declaration>\n"
                      "       %s <parameter-description> <limits-declaration> "
                      DRAW_OPTION " <target-c> <converter-full-scale-counts> "
                      "<converter-full-scale-milli> <course-file> "
                      "[" CONTROL_DESCRIPTION_OPTION " <parameter-description>]\n"
                      "       %s <parameter-description> <limits-declaration> "
                      STEAM_DRAW_OPTION " <steam-control-declaration> <initial-steam-c> "
                      "<course-file>\n",
                      argc > 0 ? argv[0] : "program", argc > 0 ? argv[0] : "program",
                      argc > 0 ? argv[0] : "program");
        return 2;
    }

    plant_parameters_t parameters;
    if (!load_a_description(argv[1], &parameters)) {
        return 1;
    }

    /*
     * The record the brew draw's control path drives its reconstruction from.
     * It is the machine's own unless a second description was named, and where
     * one was it is loaded and admitted on exactly the terms the machine's was
     * -- a controller believing a description no structure would accept as a
     * machine is not a drifted machine, it is a broken run.
     */
    plant_parameters_t control_parameters;
    if (drifted_draw_requested &&
        !load_a_description(argv[4 + DRAW_ARGUMENTS + 1], &control_parameters)) {
        return 1;
    }

    size_t limits_length = 0u;
    char *declaration = read_file(argv[2], &limits_length);
    if (declaration == NULL) {
        return 1;
    }

    estimator_limits_t limits;
    estimator_limits_error_t limits_error;
    const bool limits_loaded =
        estimator_limits_load(declaration, limits_length, &limits, &limits_error);
    free(declaration);

    if (!limits_loaded) {
        (void)fprintf(stderr,
                      "host exercise: limits declaration refused: %s (fault %d, line %u)\n",
                      limits_error.name, (int)limits_error.fault, limits_error.line);
        return 1;
    }

    /*
     * The band, from the path this build was compiled with rather than from an
     * argument. It is opened and read through the same reader the two files
     * above go through, so a declaration that cannot be opened stops the
     * exercise here rather than reaching the control path as an absence.
     */
    size_t tolerance_length = 0u;
    char *band = read_file(REFERENCE_TOLERANCE_PATH, &tolerance_length);
    if (band == NULL) {
        return 1;
    }

    delivery_tolerance_t tolerance;
    delivery_tolerance_error_t tolerance_error;
    const bool tolerance_loaded =
        delivery_tolerance_load(band, tolerance_length, &tolerance, &tolerance_error);
    free(band);

    if (!tolerance_loaded) {
        (void)fprintf(stderr,
                      "host exercise: tolerance declaration refused: %s (fault %d, line %u)\n",
                      tolerance_error.name, (int)tolerance_error.fault, tolerance_error.line);
        return 1;
    }

    if (draw_requested) {
        return run_the_draw(&argv[4], &parameters,
                            drifted_draw_requested ? &control_parameters : &parameters, &limits,
                            &tolerance);
    }
    if (steam_draw_requested) {
        return run_the_steam_draw(&argv[4], &parameters, &limits);
    }

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, 20000);

    if (control_init(&state, &parameters, &limits, &tolerance)) {
        (void)printf("host exercise: control path reconstructs its brew temperature\n");
        exercise_untargeted_steps(&state);
        exercise_actuating_steps(&state);
        exercise_early_step(&state);
        exercise_invalid_sensor(&state);
        exercise_refused_output(&parameters, &limits, &tolerance);
    } else {
        (void)printf("host exercise: this structure cannot carry a reconstruction the "
                     "estimator can keep corrected\n");
        exercise_refused_reconstruction(&state);
    }

    exercise_plant(&parameters);

    if (failures != 0) {
        (void)fprintf(stderr, "host exercise: %d expectation(s) unmet\n", failures);
        return 1;
    }

    (void)printf("host exercise: control path completed %u steps\n", state.step_count);
    return 0;
}
