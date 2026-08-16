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
    expect(hw_sim_output(HW_OUTPUT_BREW_HEATER) > 0u, "the heater was never driven");
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
    expect(hw_sim_output(HW_OUTPUT_BREW_HEATER) == 0u, "the heater stayed on through a fault");
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

    const plant_actuation_t heating = {
        .brew_heater_permille = PLANT_ACTUATION_FULL_SCALE,
        .steam_heater_permille = PLANT_ACTUATION_FULL_SCALE,
        .pump_permille = PLANT_ACTUATION_FULL_SCALE / 2u,
    };
    for (int i = 0; i < EXERCISE_STEPS; i++) {
        expect(plant_model_step(&model, &heating, PLANT_STEP_INTERVAL_MS),
               "a plant step was refused");
    }

    /* A step the seam must refuse, so that path is executed too. */
    const plant_actuation_t over_scale = {
        .brew_heater_permille = PLANT_ACTUATION_FULL_SCALE + 1u,
        .steam_heater_permille = 0u,
        .pump_permille = 0u,
    };
    expect(!plant_model_step(&model, &over_scale, PLANT_STEP_INTERVAL_MS),
           "an out-of-scale actuation was accepted");
    expect(!plant_model_step(&model, &heating, 0u), "a zero-length step was accepted");

    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        double value = 0.0;
        expect(plant_model_quantity(&model, (plant_quantity_t)quantity, &value),
               "a quantity the model exposes could not be read");
        (void)printf("plant quantity %d = %.6f\n", quantity, value);
    }

    double unused = 0.0;
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
