/*
 * The thermoblock structure's equations.
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
    {"brew.outlet_time_constant_s", 0.001f, 100.0f,
     offsetof(plant_parameters_t, brew_outlet_time_constant_s)},

    {"steam.thermal_mass_j_per_k", 1.0f, 100000.0f,
     offsetof(plant_parameters_t, steam_thermal_mass_j_per_k)},
    {"steam.heater_power_w", 0.0f, 10000.0f, offsetof(plant_parameters_t, steam_heater_power_w)},
    {"steam.loss_w_per_k", 0.0f, 1000.0f, offsetof(plant_parameters_t, steam_loss_w_per_k)},

    {"pump.pressure_bar", 0.0f, 30.0f, offsetof(plant_parameters_t, pump_pressure_bar)},
    {"pump.flow_ml_per_s", 0.0f, 100.0f, offsetof(plant_parameters_t, pump_flow_ml_per_s)},
    {"brew.pressure_time_constant_s", 0.001f, 100.0f,
     offsetof(plant_parameters_t, brew_pressure_time_constant_s)},

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
 * Steam pressure at a given steam temperature.
 *
 * One expression, used both to bring an instance up and to advance it. Writing
 * it twice is what let the two disagree: an instance started with a pressure
 * its own equations would not have produced is not at rest, and a step taken
 * with no actuation then moves it.
 */
static float steam_pressure_at(const plant_parameters_t *parameters, float steam_temperature_c)
{
    const float above_saturation_k =
        steam_temperature_c - parameters->steam_saturation_temperature_c;
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
 * result. At a step a thousandth of the time constant that spelling is wrong in
 * the third significant figure, which is worse than assuming the rate held
 * constant across the step, the very thing this exists to improve on.
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
 * One mass's temperature after `seconds` of heating at `duty` and losing to
 * ambient. Exact for a constant actuation over the step, and stable for any
 * step length at any admissible coefficients.
 */
static float advanced_temperature(float temperature_c, float ambient_c, float heater_power_w,
                                   float duty, float loss_w_per_k, float thermal_mass_j_per_k,
                                   float seconds)
{
    const float delivered_w = heater_power_w * duty;
    const float lost_w = loss_w_per_k * (temperature_c - ambient_c);
    const float steps_of_time_constant = (seconds * loss_w_per_k) / thermal_mass_j_per_k;
    const float effective_seconds = seconds * relaxation_factor(steps_of_time_constant);
    return temperature_c + ((delivered_w - lost_w) * effective_seconds) / thermal_mass_j_per_k;
}

/*
 * The water on its way to the group after `seconds`, having entered the step at
 * `outlet_c` while the casting travelled from `block_from_c` to `block_to_c`.
 *
 * The heater does not appear here. It acts on the casting, and the only way it
 * reaches the water is through this relaxation -- which is the whole of what
 * distinguishes these two states from one state read twice.
 *
 * Exact for a block that traverses the step linearly, rather than for one held
 * at either end of it. Relaxing towards a fixed value is what the pressure path
 * does, and it is exact there because the pump's command really is constant
 * across a step; the block's temperature is not, and taking either end of its
 * traverse as though it were leaves an error first order in the step length --
 * every other integration in this structure is exact for its own step, and one
 * that is not would be the one a shorter step was needed to hide.
 *
 * The two library expressions are the ones already used above: how far a
 * relaxation travels in the step, and the same per time constant elapsed. That
 * second one is what carries the block's traverse, and it is why the result
 * reduces to the ordinary relaxation when the block does not move.
 */
static float advanced_outlet(float outlet_c, float block_from_c, float block_to_c,
                             float time_constant_s, float seconds)
{
    const float steps_of_time_constant = seconds / time_constant_s;
    const float settled = settled_fraction(steps_of_time_constant);
    const float carried = relaxation_factor(steps_of_time_constant);
    return block_to_c - (block_to_c - block_from_c) * carried +
           (outlet_c - block_from_c) * (1.0f - settled);
}

void thermoblock_advance_temperatures(plant_model_t *model, const plant_actuation_t *actuation,
                                      float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }

    const plant_parameters_t *p = &model->coefficients;

    const float casting_before_c = model->brew_temperature_c;

    model->brew_temperature_c = advanced_temperature(
        casting_before_c, p->ambient_temperature_c, p->brew_heater_power_w,
        actuation->level_permille[ACTUATION_CHANNEL_BREW_HEATER] / PERMILLE_FULL_SCALE,
        p->brew_loss_w_per_k,
        p->brew_thermal_mass_j_per_k, seconds);

    model->brew_outlet_temperature_c =
        advanced_outlet(model->brew_outlet_temperature_c, casting_before_c,
                        model->brew_temperature_c, p->brew_outlet_time_constant_s, seconds);

    model->steam_temperature_c = advanced_temperature(
        model->steam_temperature_c, p->ambient_temperature_c, p->steam_heater_power_w,
        actuation->level_permille[ACTUATION_CHANNEL_STEAM_HEATER] / PERMILLE_FULL_SCALE,
        p->steam_loss_w_per_k,
        p->steam_thermal_mass_j_per_k, seconds);
}

/*
 * The rate the pump was commanded to move water at, from the level it was
 * commanded with. Linear in that level and zero when it is zero, which is the
 * whole of the relation: what the water is being pushed through does not enter
 * it, so a puck, the pump's own flow-versus-pressure characteristic and the
 * mechanical cap are all absent. This is the rate commanded, not the rate a cup
 * received, and params/thermoblock.md carries that gap as a stated omission.
 */
static float commanded_flow_ml_per_s(const plant_parameters_t *p,
                                     const plant_actuation_t *actuation)
{
    return p->pump_flow_ml_per_s *
           (actuation->level_permille[ACTUATION_CHANNEL_PUMP] / PERMILLE_FULL_SCALE);
}

void thermoblock_advance_pressures(plant_model_t *model, const plant_actuation_t *actuation,
                                   float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }

    const plant_parameters_t *p = &model->coefficients;

    const float commanded_bar =
        p->pump_pressure_bar *
        (actuation->level_permille[ACTUATION_CHANNEL_PUMP] / PERMILLE_FULL_SCALE);
    /* The same relaxation the thermal masses use, through the same expression:
     * the shortest admissible time constant is far below the step lengths a
     * caller may use, and taking the rate as constant across the step would
     * oscillate rather than settle. */
    const float settled = settled_fraction(seconds / p->brew_pressure_time_constant_s);
    model->brew_pressure_bar += (commanded_bar - model->brew_pressure_bar) * settled;

    model->steam_pressure_bar = steam_pressure_at(p, model->steam_temperature_c);
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
     * the water on its way to the group at ambient with them -- a casting and an
     * outlet at the same temperature is what having stood still means, and any
     * other pairing would have the two moving before anything was commanded --
     * the pump off, and every quantity at the value this structure's own
     * equations give for that state. A step taken from here with no actuation
     * therefore moves nothing, which is what makes an accidentally hard-coded
     * source or sink visible -- and it holds for any admissible ambient, not
     * only for one that happens to sit below saturation.
     */
    model->brew_temperature_c = parameters->ambient_temperature_c;
    model->brew_outlet_temperature_c = parameters->ambient_temperature_c;
    model->steam_temperature_c = parameters->ambient_temperature_c;
    model->brew_pressure_bar = 0.0f;
    model->brew_flow_ml_per_s = 0.0f;
    model->steam_pressure_bar = steam_pressure_at(parameters, model->steam_temperature_c);
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
     * Temperatures first, then pressures: steam pressure follows the steam
     * mass, so within one step it reflects where that mass has just arrived.
     */
    thermoblock_advance_temperatures(model, actuation, seconds);
    thermoblock_advance_pressures(model, actuation, seconds);

    /*
     * The rate drawn over the step just taken. It is recomputed whole rather
     * than advanced, so where it is set within the step does not matter; it is
     * set here rather than inside either advance because it is neither a
     * temperature nor a pressure, and folding it into one of those would make
     * that function's name a smaller truth than its body.
     */
    model->brew_flow_ml_per_s = commanded_flow_ml_per_s(&model->coefficients, actuation);
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

    /*
     * This architecture keeps every state the vocabulary names. The casting and
     * the water that has left it are separate states here, and only the first
     * is exposed as a quantity -- which is what gives work reconstructing the
     * second from a reading of the first something to reconstruct.
     */
    switch (state) {
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
        *value = model->brew_temperature_c;
        return true;
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
        *value = model->brew_outlet_temperature_c;
        return true;
    case PLANT_STATE_STEAM_TEMPERATURE_C:
        *value = model->steam_temperature_c;
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

    /* Every state the vocabulary names is kept here, so every one can be written. */
    switch (state) {
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
        model->brew_temperature_c = value;
        return true;
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
        model->brew_outlet_temperature_c = value;
        return true;
    case PLANT_STATE_STEAM_TEMPERATURE_C:
        model->steam_temperature_c = value;
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
