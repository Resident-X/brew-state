/*
 * The fixture structure's implementation.
 *
 * It satisfies the same interface the machine-describing structure does, so
 * the same consumers link against it unchanged -- which is what makes it a
 * usable second subject for the exclusivity and two-structure checks. It
 * models nothing.
 */
#include "plant_model.h"

#include <stddef.h>
#include <string.h>

#define MILLIS_PER_SECOND 1000.0f
#define PERMILLE_FULL_SCALE 1000.0f

static const plant_parameter_spec_t SPECS[] = {
    {"fixture.gain", -1000.0f, 1000.0f, offsetof(plant_parameters_t, fixture_gain)},
};

const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SPECS) / sizeof(SPECS[0]);
    }
    return SPECS;
}

void fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation, float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }
    model->accumulated += model->coefficients.fixture_gain *
                          (actuation->level_permille[ACTUATION_CHANNEL_BREW_HEATER] /
                           PERMILLE_FULL_SCALE) *
                          seconds;
}

actuation_channel_set_t plant_structure_actuation_channels(void)
{
    return PLANT_STRUCTURE_ACTUATION_CHANNELS;
}

bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters)
{
    if (model == NULL || parameters == NULL) {
        return false;
    }
    memset(model, 0, sizeof(*model));
    model->coefficients = *parameters;
    model->accumulated = 0.0f;
    model->initialised = true;
    return true;
}

bool plant_model_step_reporting(plant_model_t *model, const plant_actuation_t *actuation,
                                uint32_t interval_millis, plant_step_error_t *error)
{
    if (error == NULL) {
        return false;
    }
    if (model == NULL || !model->initialised) {
        error->fault = PLANT_STEP_NOT_STEPPABLE;
        error->channel = ACTUATION_CHANNEL_COUNT;
        return false;
    }
    if (!plant_step_admissible(actuation, interval_millis, PLANT_STRUCTURE_ACTUATION_CHANNELS,
                               error)) {
        return false;
    }

    fixture_accumulate(model, actuation, interval_millis / MILLIS_PER_SECOND);
    return true;
}

bool plant_model_quantity(const plant_model_t *model, plant_quantity_t quantity, float *value)
{
    if (model == NULL || value == NULL || !model->initialised) {
        return false;
    }

    /*
     * Every quantity answers from the one accumulator. The interface's
     * quantities are the machine's, and this structure has no machine, so
     * there is nothing more meaningful to answer with.
     */
    switch (quantity) {
    case PLANT_QUANTITY_BREW_TEMPERATURE_C:
    case PLANT_QUANTITY_STEAM_TEMPERATURE_C:
    case PLANT_QUANTITY_BREW_PRESSURE_BAR:
    case PLANT_QUANTITY_STEAM_PRESSURE_BAR:
        *value = model->accumulated;
        return true;
    case PLANT_QUANTITY_COUNT:
    default:
        return false;
    }
}

bool plant_model_state(const plant_model_t *model, plant_state_t state, float *value)
{
    if (model == NULL || value == NULL || !model->initialised) {
        return false;
    }

    /*
     * Deliberately narrower than the quantities above, and narrower than the
     * vocabulary. This structure describes no machine, so it is free to keep
     * whatever states it likes, and keeping one is what makes the refusal of
     * the rest something a test can trigger. The structures that do describe a
     * machine answer nearly all of them, so a refusal demonstrated only against
     * those would be demonstrated against almost nothing -- which is the same
     * reason this structure's actuation declaration is narrower than the
     * channel vocabulary.
     *
     * The one it answers is the accumulator, under the name of the mass a
     * heater acts on. Nothing here claims that is a temperature of anything
     * real.
     */
    switch (state) {
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
        *value = model->accumulated;
        return true;
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
    case PLANT_STATE_STEAM_TEMPERATURE_C:
    case PLANT_STATE_BREW_PRESSURE_BAR:
    case PLANT_STATE_STEAM_PRESSURE_BAR:
    case PLANT_STATE_COUNT:
    default:
        return false;
    }
}
