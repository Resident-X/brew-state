/*
 * The single-boiler structure's equations.
 *
 * One heated vessel serves both paths. Both temperature quantities are read off
 * that one state, so a machine of this architecture cannot hold the brew side
 * at one temperature while the steam side sits at another -- which is the
 * behaviour the architecture actually has, and the reason a controller written
 * against it has a different problem to solve than one written against two
 * independent masses.
 *
 * Every coefficient these equations use is read from the parameter record the
 * instance was initialised with. The only numbers written here are the unit
 * conversions the interface's units imply and the constants of the integration
 * itself, neither of which is a property of a machine.
 */
#include "plant_model.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

/* Milliseconds to seconds, and parts per thousand to a fraction of full scale. */
#define MILLIS_PER_SECOND 1000.0f
#define PERMILLE_FULL_SCALE 1000.0f

/*
 * The admissible ranges are the ones outside which these equations stop
 * describing a machine of this architecture rather than describing an unusual
 * one: a mass or a time constant at or below zero divides, a negative loss
 * coefficient makes the vessel run away from ambient, and a negative power or
 * pressure drives the wrong way. The upper bounds are where a value stops being
 * an espresso machine and starts being a data-entry error.
 */
static const plant_parameter_spec_t SPECS[] = {
    {"ambient_temperature_c", -40.0f, 60.0f, offsetof(plant_parameters_t, ambient_temperature_c)},

    {"vessel.thermal_mass_j_per_k", 1.0f, 100000.0f,
     offsetof(plant_parameters_t, vessel_thermal_mass_j_per_k)},
    {"vessel.heater_power_w", 0.0f, 10000.0f,
     offsetof(plant_parameters_t, vessel_heater_power_w)},
    {"vessel.loss_w_per_k", 0.0f, 1000.0f, offsetof(plant_parameters_t, vessel_loss_w_per_k)},

    {"pump.pressure_bar", 0.0f, 30.0f, offsetof(plant_parameters_t, pump_pressure_bar)},
    {"pump.flow_ml_per_s", 0.0f, 100.0f, offsetof(plant_parameters_t, pump_flow_ml_per_s)},
    {"brew.pressure_time_constant_s", 0.001f, 100.0f,
     offsetof(plant_parameters_t, brew_pressure_time_constant_s)},

    {"water.feed_temperature_c", 0.0f, 60.0f,
     offsetof(plant_parameters_t, water_feed_temperature_c)},
    {"water.heat_capacity_j_per_ml_k", 1.0f, 10.0f,
     offsetof(plant_parameters_t, water_heat_capacity_j_per_ml_k)},

    {"steam.saturation_temperature_c", 0.0f, 300.0f,
     offsetof(plant_parameters_t, steam_saturation_temperature_c)},
    {"steam.pressure_bar_per_k", 0.0f, 10.0f,
     offsetof(plant_parameters_t, steam_pressure_bar_per_k)},
};

actuation_channel_set_t plant_structure_actuation_channels(void)
{
    return PLANT_STRUCTURE_ACTUATION_CHANNELS;
}

const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SPECS) / sizeof(SPECS[0]);
    }
    return SPECS;
}

/*
 * Steam pressure at a given vessel temperature.
 *
 * One expression, used both to bring an instance up and to advance it. Writing
 * it twice is what let the two disagree: an instance started with a pressure
 * its own equations would not have produced is not at rest, and a step taken
 * with no actuation then moves it.
 */
static float steam_pressure_at(const plant_parameters_t *parameters, float vessel_temperature_c)
{
    const float above_saturation_k =
        vessel_temperature_c - parameters->steam_saturation_temperature_c;
    return above_saturation_k > 0.0f ? parameters->steam_pressure_bar_per_k * above_saturation_k
                                     : 0.0f;
}

/*
 * How far a first-order relaxation travels towards its settling value in `x`
 * time constants: 1 - exp(-x).
 *
 * Written with the library's expm1 rather than as `1 - exp(-x)`. For a short
 * step the exponential is just under one, and subtracting it from one throws
 * away the leading digits of an answer that is itself small -- the error is
 * absolute in the exponential and so grows without bound relative to the
 * result.
 */
static float settled_fraction(float x)
{
    return -expm1f(-x);
}

/*
 * The same fraction per time constant elapsed, which is one in the limit as the
 * step vanishes. There is no threshold: expm1 is accurate all the way down, and
 * a cut would put a discontinuity in the model where a coefficient crossed it.
 */
static float relaxation_factor(float x)
{
    return x > 0.0f ? settled_fraction(x) / x : 1.0f;
}

/*
 * The rate the pump was commanded to move water at, linear in the commanded
 * level and zero when it is zero. What the water is pushed through does not
 * enter it, so this is the rate commanded rather than the rate delivered.
 */
static float commanded_flow_ml_per_s(const plant_parameters_t *p,
                                     const plant_actuation_t *actuation)
{
    return p->pump_flow_ml_per_s *
           (actuation->level_permille[ACTUATION_CHANNEL_PUMP] / PERMILLE_FULL_SCALE);
}

void boiler_advance_vessel(plant_model_t *model, const plant_actuation_t *actuation, float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }

    const plant_parameters_t *p = &model->coefficients;

    const float duty =
        actuation->level_permille[ACTUATION_CHANNEL_BREW_HEATER] / PERMILLE_FULL_SCALE;
    const float drawn_ml_per_s = commanded_flow_ml_per_s(p, actuation);
    /*
     * What the water drawn out costs the vessel, per kelvin it is carried away
     * above the temperature it arrived at. A volume rate, so the conversion to a
     * power is the volumetric heat capacity of water and nothing else.
     */
    const float drawn_w_per_k = drawn_ml_per_s * p->water_heat_capacity_j_per_ml_k;
    const float delivered_w = p->vessel_heater_power_w * duty;
    /*
     * Two losses, and the second is written at the vessel's own temperature.
     * That is not the shortcut the reference architecture rules out -- there the
     * water leaving is a state of its own and taking the difference at the
     * casting would be claiming a gradient that structure exists to represent.
     * Here there is no such state to take it at: this architecture heats the
     * water in the vessel it delivers from, so the water on its way out is the
     * water in the vessel, and the vessel's temperature is the leaving
     * temperature rather than a stand-in for it. A machine of this kind that
     * cooled at the outlet and not at the vessel would be two bodies of water,
     * which is the other architecture.
     */
    const float lost_w = p->vessel_loss_w_per_k * (model->vessel_temperature_c -
                                                   p->ambient_temperature_c) +
                         drawn_w_per_k * (model->vessel_temperature_c -
                                          p->water_feed_temperature_c);
    /*
     * Both losses pull the vessel towards something, so both set how fast it
     * gets there: the relaxation the step is corrected for is the sum of the two
     * coefficients rather than the ambient one alone. With the pump closed the
     * drawn term is exactly zero and this is the coefficient it always was.
     */
    const float settling_w_per_k = p->vessel_loss_w_per_k + drawn_w_per_k;
    const float steps_of_time_constant =
        (seconds * settling_w_per_k) / p->vessel_thermal_mass_j_per_k;
    const float effective_seconds = seconds * relaxation_factor(steps_of_time_constant);

    model->vessel_temperature_c +=
        ((delivered_w - lost_w) * effective_seconds) / p->vessel_thermal_mass_j_per_k;
}

void boiler_advance_pressures(plant_model_t *model, const plant_actuation_t *actuation,
                              float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }

    const plant_parameters_t *p = &model->coefficients;

    const float commanded_bar =
        p->pump_pressure_bar *
        (actuation->level_permille[ACTUATION_CHANNEL_PUMP] / PERMILLE_FULL_SCALE);
    const float settled = settled_fraction(seconds / p->brew_pressure_time_constant_s);
    model->brew_pressure_bar += (commanded_bar - model->brew_pressure_bar) * settled;

    model->steam_pressure_bar = steam_pressure_at(p, model->vessel_temperature_c);
}

bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters)
{
    if (model == NULL || parameters == NULL) {
        return false;
    }

    memset(model, 0, sizeof(*model));
    model->coefficients = *parameters;

    /*
     * The machine starts where it has been sitting: the vessel at ambient, the
     * pump off, and every quantity at the value this structure's own equations
     * give for that state. A step taken from here with no actuation therefore
     * moves nothing, which is what makes an accidentally hard-coded source or
     * sink visible -- and it holds for any admissible ambient, not only for one
     * that happens to sit below saturation.
     */
    model->vessel_temperature_c = parameters->ambient_temperature_c;
    model->brew_pressure_bar = 0.0f;
    model->brew_flow_ml_per_s = 0.0f;
    model->steam_pressure_bar = steam_pressure_at(parameters, model->vessel_temperature_c);
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

    const float seconds = interval_millis / MILLIS_PER_SECOND;

    /*
     * The vessel first, then the pressures: steam pressure follows the vessel,
     * so within one step it reflects where the vessel has just arrived.
     */
    boiler_advance_vessel(model, actuation, seconds);
    boiler_advance_pressures(model, actuation, seconds);

    /* Recomputed whole rather than advanced, so where in the step it is set
     * does not matter; it is set here rather than inside either advance
     * because it is neither the vessel nor a pressure. */
    model->brew_flow_ml_per_s = commanded_flow_ml_per_s(&model->coefficients, actuation);
    return true;
}

bool plant_model_quantity(const plant_model_t *model, plant_quantity_t quantity, float *value)
{
    if (model == NULL || value == NULL || !model->initialised) {
        return false;
    }

    switch (quantity) {
    /*
     * Both temperature quantities answer from the one vessel, because there is
     * one vessel. This is the architecture rather than an approximation of it:
     * on a machine built this way the brew path and the steam path are the same
     * body of water, and a model reporting two independent temperatures for
     * them would be describing a machine that does not exist.
     */
    case PLANT_QUANTITY_BREW_TEMPERATURE_C:
    case PLANT_QUANTITY_STEAM_TEMPERATURE_C:
        *value = model->vessel_temperature_c;
        return true;
    case PLANT_QUANTITY_BREW_PRESSURE_BAR:
        *value = model->brew_pressure_bar;
        return true;
    case PLANT_QUANTITY_STEAM_PRESSURE_BAR:
        *value = model->steam_pressure_bar;
        return true;
    case PLANT_QUANTITY_BREW_FLOW_ML_PER_S:
        *value = model->brew_flow_ml_per_s;
        return true;
    /*
     * Not a quantity, so there is nothing to answer with. No default label
     * beside it, and that absence is deliberate: -Wall gives -Wswitch and this
     * is built under -Werror, so a quantity added to the machine's vocabulary
     * fails the build here rather than being quietly refused by every
     * structure. A quantity is the machine's and not a structure's -- the seam
     * promises every consumer that every structure answers every one -- so
     * silently refusing a new one would break that promise in the one way no
     * consumer can test for.
     */
    case PLANT_QUANTITY_COUNT:
        return false;
    }

    /* Reached only by a value that is not in the vocabulary at all. */
    return false;
}

bool plant_model_state(const plant_model_t *model, plant_state_t state, float *value)
{
    if (model == NULL || value == NULL || !model->initialised) {
        return false;
    }

    switch (state) {
    /*
     * This architecture heats the water in the vessel it delivers from, so
     * nothing sits between the mass and what leaves it: the water on its way out
     * is the water in the vessel. That is not a state this structure has chosen
     * to leave out and could add -- a single-vessel machine has nothing there to
     * keep. Refusing it is how work that reconstructs such a state finds out it
     * is asking the wrong structure, rather than being handed the vessel and
     * quietly reconstructing something that was already being read.
     */
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
        return false;
    /*
     * The heated mass and the steam mass are the one vessel here, for the same
     * reason both temperature quantities are: on a machine built this way they
     * are the same body of water.
     */
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
    case PLANT_STATE_STEAM_TEMPERATURE_C:
        *value = model->vessel_temperature_c;
        return true;
    case PLANT_STATE_BREW_PRESSURE_BAR:
        *value = model->brew_pressure_bar;
        return true;
    case PLANT_STATE_STEAM_PRESSURE_BAR:
        *value = model->steam_pressure_bar;
        return true;
    case PLANT_STATE_COUNT:
    default:
        return false;
    }
}

bool plant_model_set_state(plant_model_t *model, plant_state_t state, float value)
{
    if (model == NULL || !model->initialised) {
        return false;
    }

    switch (state) {
    /*
     * Refused on writing for the reason it is refused on reading: there is no
     * such body of water on a machine built this way, so there is nothing here
     * for the value to be written to.
     */
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
        return false;
    /*
     * One vessel, so a correction to either temperature is a correction to the
     * same state. A caller writing both in one pass gets the second, which is
     * what it means for them to be one body of water.
     */
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
    case PLANT_STATE_STEAM_TEMPERATURE_C:
        model->vessel_temperature_c = value;
        return true;
    case PLANT_STATE_BREW_PRESSURE_BAR:
        model->brew_pressure_bar = value;
        return true;
    case PLANT_STATE_STEAM_PRESSURE_BAR:
        model->steam_pressure_bar = value;
        return true;
    case PLANT_STATE_COUNT:
    default:
        return false;
    }
}
