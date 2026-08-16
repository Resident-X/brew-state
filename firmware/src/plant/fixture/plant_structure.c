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

#define MILLIS_PER_SECOND 1000.0
#define PERMILLE_FULL_SCALE 1000.0

static const plant_parameter_spec_t SPECS[] = {
    {"fixture.gain", -1000.0, 1000.0, offsetof(plant_parameters_t, fixture_gain)},
};

const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SPECS) / sizeof(SPECS[0]);
    }
    return SPECS;
}

void fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation, double seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }
    model->accumulated +=
        model->coefficients.fixture_gain * (actuation->brew_heater_permille / PERMILLE_FULL_SCALE) *
        seconds;
}

bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters)
{
    if (model == NULL || parameters == NULL) {
        return false;
    }
    memset(model, 0, sizeof(*model));
    model->coefficients = *parameters;
    model->accumulated = 0.0;
    model->initialised = true;
    return true;
}

bool plant_model_step(plant_model_t *model, const plant_actuation_t *actuation,
                      uint32_t interval_millis)
{
    if (model == NULL || actuation == NULL || !model->initialised || interval_millis == 0u) {
        return false;
    }
    if (actuation->brew_heater_permille > PLANT_ACTUATION_FULL_SCALE ||
        actuation->steam_heater_permille > PLANT_ACTUATION_FULL_SCALE ||
        actuation->pump_permille > PLANT_ACTUATION_FULL_SCALE) {
        return false;
    }

    fixture_accumulate(model, actuation, interval_millis / MILLIS_PER_SECOND);
    return true;
}

bool plant_model_quantity(const plant_model_t *model, plant_quantity_t quantity, double *value)
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
