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
 * one: a mass, a held volume or a time constant at or below zero divides, a
 * negative loss coefficient makes a mass run away from ambient, and a negative
 * power or pressure drives the wrong way. The upper bounds are where a value
 * stops being an espresso machine and starts being a data-entry error.
 *
 * The two water properties are bounded on a different footing from the rest,
 * because they are not this machine's figures. Feed water is admitted from
 * freezing to a warm tank and no further: below zero it is not water, and above
 * that band a machine is being fed from something this description has no
 * account of. Its heat capacity is bounded around water's, close enough that a
 * figure for some other fluid is refused here rather than quietly changing what
 * a millilitre costs -- these equations convert a volume rate into an energy
 * flux with it, and that conversion is the one place a wrong substance would
 * look like a plausible machine.
 */
static const plant_parameter_spec_t SPECS[] = {
    {"ambient_temperature_c", -40.0f, 60.0f, offsetof(plant_parameters_t, ambient_temperature_c)},

    {"brew.thermal_mass_j_per_k", 1.0f, 100000.0f,
     offsetof(plant_parameters_t, brew_thermal_mass_j_per_k)},
    {"brew.heater_power_w", 0.0f, 10000.0f, offsetof(plant_parameters_t, brew_heater_power_w)},
    {"brew.loss_w_per_k", 0.0f, 1000.0f, offsetof(plant_parameters_t, brew_loss_w_per_k)},
    {"brew.outlet_held_volume_ml", 0.1f, 1000.0f,
     offsetof(plant_parameters_t, brew_outlet_held_volume_ml)},
    {"brew.outlet_conduction_time_constant_s", 0.001f, 1000.0f,
     offsetof(plant_parameters_t, brew_outlet_conduction_time_constant_s)},

    {"steam.thermal_mass_j_per_k", 1.0f, 100000.0f,
     offsetof(plant_parameters_t, steam_thermal_mass_j_per_k)},
    {"steam.heater_power_w", 0.0f, 10000.0f, offsetof(plant_parameters_t, steam_heater_power_w)},
    {"steam.loss_w_per_k", 0.0f, 1000.0f, offsetof(plant_parameters_t, steam_loss_w_per_k)},

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

/*
 * How fast the water on its way to the group approaches the casting, as a rate
 * rather than as a time constant.
 *
 * Two paths reach the same water and they add as rates because they act at the
 * same time: displacement, which replaces the held volume once every time the
 * drawn rate has moved that volume through, and conduction, which acts on
 * whatever is sitting there whether or not anything is moving. Adding the rates
 * is combining the time constants as reciprocals, and it is why nothing here
 * needs a guard at a closed pump: at no draw the first term is exactly zero and
 * what is left is the conduction rate, which is a coefficient with a positive
 * range and so never zero. A relation written in time constants would have had
 * to divide by the drawn rate and then say what to do at zero, and whatever it
 * said would have been a discontinuity where a coefficient crossed it.
 */
static float outlet_approach_per_s(const plant_parameters_t *p, float drawn_ml_per_s)
{
    return drawn_ml_per_s / p->brew_outlet_held_volume_ml +
           1.0f / p->brew_outlet_conduction_time_constant_s;
}

/*
 * The two weights the coupled step is built from, for a pair whose two modes sit
 * either side of `mean_rate` by a separation the `discriminant` sets, and whose
 * rates multiply to `product_rate`.
 *
 * The casting and the water now appear in each other's equations, so neither
 * has a closed form of its own any more. What the pair does have is linearity
 * and, across one step of constant actuation, constant coefficients -- so the
 * exact answer is the matrix exponential of the pair, and for a two-state pair
 * that exponential is a pair of scalars: the state after the step is where it
 * started, plus `kappa` times the rate it was leaving at, plus `sigma` times the
 * rate that rate was itself changing at. Both reduce to the familiar figures as
 * the step vanishes -- kappa to the step and sigma to half its square, which is
 * the first two terms of the traverse anything would write down -- and both are
 * exact for the whole of it however long it is.
 *
 * The discriminant decides which of two shapes the pair's own dynamics has, and
 * the split below is that fact rather than a numerical threshold. Above zero the
 * two modes decay at separate rates and the answer is built from them; below it
 * they are one decay carrying an oscillation, which is what writing the loss at
 * the water's temperature makes possible -- the casting gives up heat according
 * to where the water is, and the water is behind, so a fast enough draw against
 * a light enough casting overshoots and comes back. The two expressions agree
 * where they meet, at the repeated eigenvalue, which is the case that would
 * divide by nothing if it were reached from the oscillating side.
 *
 * Everything is written so that no expression here subtracts two nearly equal
 * numbers. The decay of the slower mode is recovered from the product of the two
 * rather than by subtracting the separation from the mean, so it is never a
 * cancelled zero; the exponential over the separation is taken through the same
 * settled fraction the single-mass step uses, so a step far shorter than either
 * mode keeps its leading digits. That is the same care `settled_fraction` exists
 * for, applied to a pair.
 */
static void coupled_step_weights(float mean_rate, float discriminant, float product_rate,
                                 float seconds, float *kappa, float *sigma)
{
    /*
     * The decay of the pair's mean mode over the step, and how far the two modes
     * separate over it. Both are dimensionless; both are non-negative, the first
     * because the pair always loses energy and the second by construction.
     */
    const float decay = mean_rate * seconds;
    const float separation_squared = discriminant * seconds * seconds;

    float carried;
    float second_order;

    if (separation_squared >= 0.0f) {
        const float separation = sqrtf(separation_squared);
        /*
         * The two modes, as the decay each carries over the step. The faster one
         * is the sum, which cannot cancel. The slower one is the product of the
         * two divided by it, and the product is handed in already multiplied out
         * rather than recovered from the mean and the separation, because taking
         * the difference directly is what would leave nothing but rounding when
         * the pair is nearly one mode.
         */
        const float fast = decay + separation;
        const float slow = (product_rate * seconds * seconds) / fast;
        /*
         * How much of the step the pair's average mode carries. Written through
         * the slower mode and the separation rather than through the mean and a
         * hyperbolic sine, because the slower mode's decay is bounded and the
         * separation's sine is not: on a stiff pair the two would overflow and
         * cancel back to a number well inside the range.
         */
        carried = expf(-slow) * relaxation_factor(separation + separation);
        second_order = (relaxation_factor(slow) - carried) / fast;
    } else {
        /*
         * One decay with a turn on it. The turn is what the pair does when the
         * casting is chasing water that is behind it, and the step is exact
         * across however many turns it contains.
         */
        const float turn = sqrtf(-separation_squared);
        const float half_turn = sinf(turn * 0.5f);
        const float decayed = expf(-decay);
        carried = decayed * (sinf(turn) / turn);
        second_order = (settled_fraction(decay) + (decayed + decayed) * half_turn * half_turn -
                        decay * carried) /
                       (decay * decay + turn * turn);
    }

    *kappa = seconds * (carried + (decay + decay) * second_order);
    *sigma = seconds * seconds * second_order;
}

/*
 * The casting and the water on its way to the group, advanced together over
 * `seconds` at a constant duty and a constant drawn rate.
 *
 * The casting takes in what the element delivers, gives up what its loss
 * coefficient carries to ambient, and gives up what the water carries out of it:
 * a volume rate times what a volume of water costs per kelvin, times how much
 * hotter that water is than the water arriving to replace it. The difference is
 * taken at the water leaving rather than at the casting, because that is where
 * the energy actually goes -- and it is what makes the casting the machine reads
 * depend on a state nothing on the machine reads.
 *
 * The water relaxes towards the casting at the rate above. The heater still does
 * not appear in that second relation: it acts on the casting, and the only way
 * it reaches the water is through this relaxation.
 *
 * The two are advanced as one pair. Each is in the other's equation now, so
 * advancing one and then the other would be exact for neither -- and this
 * structure's standard is that every integration in it is exact for its own
 * step, not that it is close enough if the step is kept short.
 */
static void advanced_casting_and_outlet(const plant_parameters_t *p, float duty,
                                        float drawn_ml_per_s, float seconds, float *casting_c,
                                        float *outlet_c)
{
    const float carried_w_per_k = drawn_ml_per_s * p->water_heat_capacity_j_per_ml_k;
    const float casting_before_c = *casting_c;
    const float outlet_before_c = *outlet_c;

    /*
     * The three rates the pair is made of, each per second: how fast the casting
     * relaxes towards ambient, how fast the water leaving pulls on the casting,
     * and how fast the water approaches the casting.
     */
    const float to_ambient_per_s = p->brew_loss_w_per_k / p->brew_thermal_mass_j_per_k;
    const float to_water_per_s = carried_w_per_k / p->brew_thermal_mass_j_per_k;
    const float approach_per_s = outlet_approach_per_s(p, drawn_ml_per_s);

    /* Where each state is heading as the step opens. */
    const float casting_rate =
        (p->brew_heater_power_w * duty -
         p->brew_loss_w_per_k * (casting_before_c - p->ambient_temperature_c) -
         carried_w_per_k * (outlet_before_c - p->water_feed_temperature_c)) /
        p->brew_thermal_mass_j_per_k;
    const float outlet_rate = approach_per_s * (casting_before_c - outlet_before_c);

    /* And how fast each of those is itself changing, which is the same pair of
     * equations read again with the rates in place of the temperatures. */
    const float casting_curvature = -to_ambient_per_s * casting_rate - to_water_per_s * outlet_rate;
    const float outlet_curvature = approach_per_s * (casting_rate - outlet_rate);

    /*
     * The pair's mean decay rate, and the discriminant that says whether its two
     * modes are separate decays or one decay with a turn on it. The discriminant
     * is written as the difference of the two rates rather than as the mean
     * squared less the product, so that a pair with no draw -- where the two are
     * simply the casting's own rate and the water's own rate -- comes out
     * exactly non-negative rather than as the rounding of a cancellation.
     */
    const float mean_rate = (to_ambient_per_s + approach_per_s) * 0.5f;
    const float difference = to_ambient_per_s - approach_per_s;
    const float discriminant =
        (difference * difference - 4.0f * approach_per_s * to_water_per_s) * 0.25f;
    /* The product of the two modes, multiplied out here rather than recovered
     * from the two above, for the same reason: it is a sum of positive terms in
     * this form and the difference of two nearly equal ones in the other. */
    const float product_rate = approach_per_s * (to_ambient_per_s + to_water_per_s);

    float kappa;
    float sigma;
    coupled_step_weights(mean_rate, discriminant, product_rate, seconds, &kappa, &sigma);

    *casting_c = casting_before_c + kappa * casting_rate + sigma * casting_curvature;
    *outlet_c = outlet_before_c + kappa * outlet_rate + sigma * outlet_curvature;
}

void thermoblock_advance_temperatures(plant_model_t *model, const plant_actuation_t *actuation,
                                      float seconds)
{
    if (model == NULL || actuation == NULL) {
        return;
    }

    const plant_parameters_t *p = &model->coefficients;

    advanced_casting_and_outlet(
        p, actuation->level_permille[ACTUATION_CHANNEL_BREW_HEATER] / PERMILLE_FULL_SCALE,
        commanded_flow_ml_per_s(p, actuation), seconds, &model->brew_temperature_c,
        &model->brew_outlet_temperature_c);

    /*
     * The steam mass keeps the single-mass step, and keeps it because nothing is
     * drawn through it in these equations. What a steam draw costs that mass is
     * among the omissions in params/thermoblock.md, and giving it a term here
     * from the brew path's drawn rate would be the coffee side's water leaving
     * through the steam wand.
     */
    model->steam_temperature_c = advanced_temperature(
        model->steam_temperature_c, p->ambient_temperature_c, p->steam_heater_power_w,
        actuation->level_permille[ACTUATION_CHANNEL_STEAM_HEATER] / PERMILLE_FULL_SCALE,
        p->steam_loss_w_per_k,
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
                                float steam_demand_ml_per_s, uint32_t interval_millis,
                                plant_step_error_t *error)
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

    /*
     * No relation these equations compute yet reads the drawn rate or the
     * steam-side feed channel's commanded level: what either costs or drives
     * is a later relation's term, not this one's. Accepting them here, ahead
     * of that term existing, is what lets it be added without every caller of
     * this seam changing again.
     */
    (void)steam_demand_ml_per_s;

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
