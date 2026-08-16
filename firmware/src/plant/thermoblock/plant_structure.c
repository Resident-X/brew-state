/*
 * The thermoblock structure's equations.
 *
 * Every coefficient these equations use is read from the parameter record the
 * instance was initialised with. The only numbers written here are the unit
 * conversions the interface's units imply and the constants of the integration
 * itself, neither of which is a property of a machine.
 */
#include "plant_model.h"

#include <stddef.h>
#include <string.h>

/* Milliseconds to seconds, and parts per thousand to a fraction of full scale. */
#define MILLIS_PER_SECOND 1000.0f
#define PERMILLE_FULL_SCALE 1000.0f

/*
 * The admissible ranges are the ones outside which these equations stop
 * describing a machine of this architecture rather than describing an unusual
 * one: a mass or a time constant at or below zero divides, a negative loss
 * coefficient makes a mass run away from ambient, and a negative power or
 * pressure drives the wrong way. The upper bounds are where a value stops
 * being an espresso machine and starts being a data-entry error.
 */
static const plant_parameter_spec_t SPECS[] = {
    {"ambient_temperature_c", -40.0f, 60.0f, offsetof(plant_parameters_t, ambient_temperature_c)},

    {"brew.thermal_mass_j_per_k", 1.0f, 100000.0f,
     offsetof(plant_parameters_t, brew_thermal_mass_j_per_k)},
    {"brew.heater_power_w", 0.0f, 10000.0f, offsetof(plant_parameters_t, brew_heater_power_w)},
    {"brew.loss_w_per_k", 0.0f, 1000.0f, offsetof(plant_parameters_t, brew_loss_w_per_k)},

    {"steam.thermal_mass_j_per_k", 1.0f, 100000.0f,
     offsetof(plant_parameters_t, steam_thermal_mass_j_per_k)},
    {"steam.heater_power_w", 0.0f, 10000.0f, offsetof(plant_parameters_t, steam_heater_power_w)},
    {"steam.loss_w_per_k", 0.0f, 1000.0f, offsetof(plant_parameters_t, steam_loss_w_per_k)},

    {"pump.pressure_bar", 0.0f, 30.0f, offsetof(plant_parameters_t, pump_pressure_bar)},
    {"brew.pressure_time_constant_s", 0.001f, 100.0f,
     offsetof(plant_parameters_t, brew_pressure_time_constant_s)},

    {"steam.saturation_temperature_c", 0.0f, 300.0f,
     offsetof(plant_parameters_t, steam_saturation_temperature_c)},
    {"steam.pressure_bar_per_k", 0.0f, 10.0f,
     offsetof(plant_parameters_t, steam_pressure_bar_per_k)},
};

const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SPECS) / sizeof(SPECS[0]);
    }
    return SPECS;
}

/* One mass's temperature after `seconds` of heating at `duty` and losing to ambient. */
static float advanced_temperature(float temperature_c, float ambient_c, float heater_power_w,
                                   float duty, float loss_w_per_k, float thermal_mass_j_per_k,
                                   float seconds)
{
    const float delivered_w = heater_power_w * duty;
    const float lost_w = loss_w_per_k * (temperature_c - ambient_c);
    return temperature_c + ((delivered_w - lost_w) * seconds) / thermal_mass_j_per_k;
}

void thermoblock_advance_temperatures(plant_model_t *model, const plant_actuation_t *actuation,
                                      float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }

    const plant_parameters_t *p = &model->coefficients;

    model->brew_temperature_c = advanced_temperature(
        model->brew_temperature_c, p->ambient_temperature_c, p->brew_heater_power_w,
        actuation->brew_heater_permille / PERMILLE_FULL_SCALE, p->brew_loss_w_per_k,
        p->brew_thermal_mass_j_per_k, seconds);

    model->steam_temperature_c = advanced_temperature(
        model->steam_temperature_c, p->ambient_temperature_c, p->steam_heater_power_w,
        actuation->steam_heater_permille / PERMILLE_FULL_SCALE, p->steam_loss_w_per_k,
        p->steam_thermal_mass_j_per_k, seconds);
}

void thermoblock_advance_pressures(plant_model_t *model, const plant_actuation_t *actuation,
                                   float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }

    const plant_parameters_t *p = &model->coefficients;

    const float commanded_bar =
        p->pump_pressure_bar * (actuation->pump_permille / PERMILLE_FULL_SCALE);
    model->brew_pressure_bar += ((commanded_bar - model->brew_pressure_bar) * seconds) /
                                p->brew_pressure_time_constant_s;

    const float above_saturation_k = model->steam_temperature_c - p->steam_saturation_temperature_c;
    model->steam_pressure_bar =
        above_saturation_k > 0.0f ? p->steam_pressure_bar_per_k * above_saturation_k : 0.0f;
}

bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters)
{
    if (model == NULL || parameters == NULL) {
        return false;
    }

    memset(model, 0, sizeof(*model));
    model->coefficients = *parameters;

    /*
     * The machine starts where it has been sitting: both masses at ambient,
     * the pump off and nothing above saturation. A step taken from here with
     * no actuation therefore moves nothing, which is what makes an
     * accidentally hard-coded source or sink visible.
     */
    model->brew_temperature_c = parameters->ambient_temperature_c;
    model->steam_temperature_c = parameters->ambient_temperature_c;
    model->brew_pressure_bar = 0.0f;
    model->steam_pressure_bar = 0.0f;
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

    const float seconds = interval_millis / MILLIS_PER_SECOND;

    /*
     * Temperatures first, then pressures: steam pressure follows the steam
     * mass, so within one step it reflects where that mass has just arrived.
     */
    thermoblock_advance_temperatures(model, actuation, seconds);
    thermoblock_advance_pressures(model, actuation, seconds);
    return true;
}

bool plant_model_quantity(const plant_model_t *model, plant_quantity_t quantity, float *value)
{
    if (model == NULL || value == NULL || !model->initialised) {
        return false;
    }

    switch (quantity) {
    case PLANT_QUANTITY_BREW_TEMPERATURE_C:
        *value = model->brew_temperature_c;
        return true;
    case PLANT_QUANTITY_STEAM_TEMPERATURE_C:
        *value = model->steam_temperature_c;
        return true;
    case PLANT_QUANTITY_BREW_PRESSURE_BAR:
        *value = model->brew_pressure_bar;
        return true;
    case PLANT_QUANTITY_STEAM_PRESSURE_BAR:
        *value = model->steam_pressure_bar;
        return true;
    case PLANT_QUANTITY_COUNT:
    default:
        return false;
    }
}
