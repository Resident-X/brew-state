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
 * rebuilt. It is loaded once and handed to both paths, because the control path
 * now drives from a state reconstructed against that same record.
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
 * Nothing here names a plant structure. Whether the control path comes up at
 * all is therefore something this exercise observes rather than assumes: a
 * structure that keeps no state for the estimator to reconstruct is one the
 * control path refuses to start against, and that refusal is a path worth
 * walking on the artefacts built against such a structure. Both outcomes are
 * exercised, and which one happened is printed.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "control.h"
#include "estimator_limits.h"
#include "hw_sim.h"
#include "plant_model.h"

/* Steps to run in each phase of the exercise. */
#define EXERCISE_STEPS 64

/* The interval each modelled step advances the plant by. */
#define PLANT_STEP_INTERVAL_MS 100u

static int failures;

static void expect(bool condition, const char *what)
{
    if (!condition) {
        (void)fprintf(stderr, "host exercise: %s\n", what);
        failures++;
    }
}

static void exercise_actuating_steps(control_state_t *state)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);

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
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);

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
                                    const estimator_limits_t *limits)
{
    control_state_t state;

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    expect(control_init(&state, parameters, limits), "the control path could not be initialised");
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
        (void)fclose(handle);
        return NULL;
    }

    for (;;) {
        if (used == capacity) {
            capacity *= 2u;
            char *grown = realloc(buffer, capacity);
            if (grown == NULL) {
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
        expect(plant_model_step(&model, &heating, PLANT_STEP_INTERVAL_MS),
               "a plant step was refused");
    }

    /* Steps the seam must refuse, so those paths are executed too. */
    plant_actuation_t over_scale = {{0u}};
    over_scale.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = ACTUATION_FULL_SCALE + 1u;
    plant_step_error_t refusal;
    expect(!plant_model_step_reporting(&model, &over_scale, PLANT_STEP_INTERVAL_MS, &refusal),
           "an out-of-scale actuation was accepted");
    expect(refusal.fault == PLANT_STEP_LEVEL_OVER_SCALE,
           "an out-of-scale actuation was refused for the wrong reason");
    expect(!plant_model_step(&model, &heating, 0u), "a zero-length step was accepted");

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
        expect(!plant_model_step_reporting(&model, &unanswered, PLANT_STEP_INTERVAL_MS, &refusal),
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

int main(int argc, char **argv)
{
    control_state_t state;

    if (argc != 3) {
        (void)fprintf(stderr, "usage: %s <parameter-description> <limits-declaration>\n",
                      argc > 0 ? argv[0] : "program");
        return 2;
    }

    size_t length = 0u;
    char *description = read_file(argv[1], &length);
    if (description == NULL) {
        return 1;
    }

    plant_parameters_t parameters;
    plant_parameter_error_t error;
    const bool loaded = plant_parameters_load(description, length, &parameters, &error);
    free(description);

    if (!loaded) {
        (void)fprintf(stderr,
                      "host exercise: parameter description refused: %s (fault %d, line %u)\n",
                      error.parameter, (int)error.fault, error.line);
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

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);

    if (control_init(&state, &parameters, &limits)) {
        (void)printf("host exercise: control path reconstructs its brew temperature\n");
        exercise_actuating_steps(&state);
        exercise_early_step(&state);
        exercise_invalid_sensor(&state);
        exercise_refused_output(&parameters, &limits);
    } else {
        (void)printf("host exercise: this structure keeps no state to reconstruct\n");
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
