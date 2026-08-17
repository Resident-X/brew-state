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
 * a step arriving before the interval has elapsed, a step finding an
 * untrustworthy reading, and a step whose drive command is refused -- because a
 * run that only ever takes the happy path leaves the others unanalysed. It
 * walks every way a parameter description can be refused for the same reason.
 *
 * The parameter description is named on the command line rather than compiled
 * in, so the same executable runs different parameter values without being
 * rebuilt. Nothing here names a plant structure: the trajectory printed below
 * is whichever structure the build compiled, reached through the seam.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "control.h"
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

static void exercise_invalid_sensor(control_state_t *state)
{
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    expect(control_step(state) == CONTROL_STEP_SENSOR_INVALID, "an invalid reading was accepted");
    expect(hw_sim_output(ACTUATION_CHANNEL_BREW_HEATER) == 0u, "the heater stayed on through a fault");
}

static void exercise_refused_output(void)
{
    control_state_t state;

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    (void)control_init(&state);
    hw_sim_set_output_refused(true);
    hw_sim_advance_millis(CONTROL_STEP_INTERVAL_MS);
    expect(control_step(&state) == CONTROL_STEP_OUTPUT_REFUSED,
           "a refused drive was reported as success");
}

/* Read a whole file into a heap buffer. The caller frees it. */
static char *read_file(const char *path, size_t *length)
{
    FILE *handle = fopen(path, "rb");
    if (handle == NULL) {
        (void)fprintf(stderr, "host exercise: cannot open parameter description %s\n", path);
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

static void exercise_plant(const char *parameter_path)
{
    size_t length = 0u;
    char *description = read_file(parameter_path, &length);
    if (description == NULL) {
        failures++;
        return;
    }

    plant_parameters_t parameters;
    plant_parameter_error_t error;
    const bool loaded = plant_parameters_load(description, length, &parameters, &error);
    free(description);

    if (!loaded) {
        (void)fprintf(stderr, "host exercise: parameter description refused: %s (fault %d, line %u)\n",
                      error.parameter, (int)error.fault, error.line);
        failures++;
        return;
    }

    plant_model_t model;
    expect(plant_model_init(&model, &parameters), "the plant model could not be initialised");

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
}

int main(int argc, char **argv)
{
    control_state_t state;

    if (argc != 2) {
        (void)fprintf(stderr, "usage: %s <parameter-description>\n",
                      argc > 0 ? argv[0] : "program");
        return 2;
    }

    hw_sim_reset();
    expect(control_init(&state), "the control path could not be initialised");

    exercise_actuating_steps(&state);
    exercise_early_step(&state);
    exercise_invalid_sensor(&state);
    exercise_refused_output();
    exercise_plant(argv[1]);

    if (failures != 0) {
        (void)fprintf(stderr, "host exercise: %d expectation(s) unmet\n", failures);
        return 1;
    }

    (void)printf("host exercise: control path completed %u steps\n", state.step_count);
    return 0;
}
