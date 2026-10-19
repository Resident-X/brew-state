/*
 * The thermoblock structure's equations.
 *
 * Every coefficient these equations use is read from the parameter record the
 * instance was initialised with. The only numbers written here are the unit
 * conversions the interface's units imply and the constants of the integration
 * itself, neither of which is a property of a machine.
 */
#include "plant_maths.h"
#include "plant_model.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

/* Milliseconds to seconds, and parts per thousand to a fraction of full scale. */
#define MILLIS_PER_SECOND 1000.0f
#define PERMILLE_FULL_SCALE 1000.0f

/* The conversion from a base-ten exponent to the natural one the exponential takes. */
#define NATURAL_LOG_OF_TEN 2.30258509f

/* The natural logarithm of two, by which a halving moves a logarithm. */
#define NATURAL_LOG_OF_TWO 0.693147181f

/*
 * Newton steps taken on a logarithm whose argument has been brought into [1, 2).
 * The starting guess is within about two hundredths there, and each step squares
 * the relative error, so three leave it below what single precision carries.
 */
#define LOGARITHM_REFINEMENTS 3

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
 * look like a plausible machine. Its latent heat is bounded on exactly those
 * terms and for exactly that reason, around the enthalpy of vaporisation of
 * water; a floor above zero because a millilitre of steam that cost nothing to
 * make is not water and not any other fluid either.
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
    {"water.latent_heat_j_per_ml", 500.0f, 5000.0f,
     offsetof(plant_parameters_t, water_latent_heat_j_per_ml)},

    {"steam.saturation_temperature_c", 0.0f, 300.0f,
     offsetof(plant_parameters_t, steam_saturation_temperature_c)},
    {"steam.saturation_antoine_a", 1.0f, 10.0f,
     offsetof(plant_parameters_t, steam_saturation_antoine_a)},
    {"steam.saturation_antoine_b_k", 100.0f, 10000.0f,
     offsetof(plant_parameters_t, steam_saturation_antoine_b_k)},
    {"steam.saturation_antoine_c_c", 10.0f, 1000.0f,
     offsetof(plant_parameters_t, steam_saturation_antoine_c_c)},
    {"steam.casting_ceiling_c", 0.0f, 300.0f, offsetof(plant_parameters_t, steam_casting_ceiling_c)},
    {"steam.restriction_bar_s2_per_ml2", 0.0f, 1000.0f,
     offsetof(plant_parameters_t, steam_restriction_bar_s2_per_ml2)},
    {"steam.outlet_drop_k_s_per_ml", 0.0f, 1000.0f,
     offsetof(plant_parameters_t, steam_outlet_drop_k_s_per_ml)},
    {"steam.liquid_capacity_ml", 0.1f, 100.0f,
     offsetof(plant_parameters_t, steam_liquid_capacity_ml)},
    {"steam.initial_inventory_ml", 0.0f, 100.0f,
     offsetof(plant_parameters_t, steam_initial_inventory_ml)},
    {"steam.feed_flow_ml_per_s", 0.0f, 100.0f,
     offsetof(plant_parameters_t, steam_feed_flow_ml_per_s)},
};

actuation_channel_set_t plant_structure_actuation_channels(void)
{
    return PLANT_STRUCTURE_ACTUATION_CHANNELS;
}

plant_delivery_point_set_t plant_structure_delivery_points(void)
{
    return PLANT_STRUCTURE_DELIVERY_POINTS;
}

/*
 * Both delivery points answer the same identifier: they are the same casting,
 * routed by a diverter this structure does not itself model.
 */
bool plant_structure_delivery_point_mass(plant_delivery_point_t point,
                                         plant_heated_mass_id_t *mass)
{
    if (mass == NULL) {
        return false;
    }
    if ((PLANT_STRUCTURE_DELIVERY_POINTS & PLANT_DELIVERY_POINT_BIT(point)) == 0u) {
        return false;
    }

    *mass = 0u;
    return true;
}

const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SPECS) / sizeof(SPECS[0]);
    }
    return SPECS;
}

/*
 * The two element ratings, which are not independent of one another. Both
 * elements are fed from the one mains supply, and an element's power goes as
 * the square of the voltage across it, so a supply that sags makes both of
 * them low at once and never one of them alone. Nothing else this structure
 * carries is driven that way: a thermal mass, a loss coefficient and a
 * saturation slope are properties of a casting and of water, and no supply
 * moves them.
 */
static const char *const SUPPLY_DRIVEN[] = {
    "brew.heater_power_w",
    "steam.heater_power_w",
};

const char *const *plant_structure_supply_driven_parameters(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SUPPLY_DRIVEN) / sizeof(SUPPLY_DRIVEN[0]);
    }
    return SUPPLY_DRIVEN;
}

/*
 * Absolute saturation pressure of water at a temperature, in bar, from the
 * declared relation.
 */
static float saturation_absolute_bar(const plant_parameters_t *parameters, float temperature_c)
{
    const float log10_bar = parameters->steam_saturation_antoine_a -
                            parameters->steam_saturation_antoine_b_k /
                                (parameters->steam_saturation_antoine_c_c + temperature_c);
    return plant_expf(log10_bar * NATURAL_LOG_OF_TEN);
}

static bool inventory_fits_the_capacity(const void *parameters)
{
    const plant_parameters_t *p = parameters;
    return p->steam_initial_inventory_ml <= p->steam_liquid_capacity_ml;
}

/* A ceiling at or below the saturation temperature leaves no span the pressure relation is valid over. */
static bool ceiling_is_above_saturation(const void *parameters)
{
    const plant_parameters_t *p = parameters;
    return p->steam_casting_ceiling_c > p->steam_saturation_temperature_c;
}

/*
 * The saturation inversion divides by a less log10 of the absolute pressure, so
 * the highest pressure the block can carry -- the restriction's drop at the full
 * feed rate, over the saturation figure the gauge is read from -- must stay under
 * 10^a, where the divisor reaches zero.
 */
static bool open_draw_pressure_is_invertible(const void *parameters)
{
    const plant_parameters_t *p = parameters;
    const float feed = p->steam_feed_flow_ml_per_s;
    const float highest_bar =
        p->steam_restriction_bar_s2_per_ml2 * feed * feed +
        saturation_absolute_bar(p, p->steam_saturation_temperature_c);
    return highest_bar < plant_expf(p->steam_saturation_antoine_a * NATURAL_LOG_OF_TEN);
}

static const plant_parameter_relation_t RELATIONS[] = {
    {"steam.initial_inventory_ml", inventory_fits_the_capacity},
    {"steam.casting_ceiling_c", ceiling_is_above_saturation},
    {"steam.restriction_bar_s2_per_ml2", open_draw_pressure_is_invertible},
};

const plant_parameter_relation_t *plant_structure_parameter_relations(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(RELATIONS) / sizeof(RELATIONS[0]);
    }
    return RELATIONS;
}

/*
 * Gauge pressure of the trapped steam over liquid at a casting temperature.
 *
 * The relation is valid from the declared saturation temperature up to the
 * casting ceiling, and the gauge figure is its answer less its own answer at the
 * saturation temperature, so it starts from nothing there rather than from a
 * step. Below that temperature there is no gauge pressure to report. Above the
 * ceiling the casting is read as the ceiling, so the figure never exceeds
 * saturation at it.
 *
 * One expression, used both to bring an instance up and to advance it. Writing
 * it twice is what let the two disagree: an instance started with a pressure
 * its own equations would not have produced is not at rest, and a step taken
 * with no actuation then moves it.
 */
static float trapped_pressure_bar(const plant_parameters_t *parameters, float casting_c)
{
    if (!(casting_c > parameters->steam_saturation_temperature_c)) {
        return 0.0f;
    }

    const float bounded_c = fminf(casting_c, parameters->steam_casting_ceiling_c);
    return fmaxf(saturation_absolute_bar(parameters, bounded_c) -
                     saturation_absolute_bar(parameters, parameters->steam_saturation_temperature_c),
                 0.0f);
}

/*
 * The natural logarithm of a positive number, built from the exponential the
 * model already carries: the argument is halved or doubled into [1, 2), where a
 * fixed number of Newton steps on e^y = x converges, and the halvings are added
 * back. Nothing that is not a positive finite number reaches it here; one that
 * did is answered as nothing rather than looped on.
 */
static float natural_log(float x)
{
    if (!(x > 0.0f) || !isfinite(x)) {
        return 0.0f;
    }

    float halvings = 0.0f;
    while (x >= 2.0f) {
        x *= 0.5f;
        halvings += 1.0f;
    }
    while (x < 1.0f) {
        x *= 2.0f;
        halvings -= 1.0f;
    }

    float y = (x - 1.0f) / sqrtf(x);
    for (int step = 0; step < LOGARITHM_REFINEMENTS; step++) {
        y = y - 1.0f + x * plant_expf(-y);
    }
    return halvings * NATURAL_LOG_OF_TWO + y;
}

/*
 * The temperature at which water saturates at a gauge pressure, by the same
 * declared relation the trapped case reads forwards, read backwards: the gauge
 * figure is put back on the relation's own answer at the saturation temperature
 * to make it absolute, and Antoine's form is solved for the temperature. A gauge
 * pressure below nothing is read as nothing.
 */
static float saturation_temperature_c(const plant_parameters_t *parameters, float gauge_bar)
{
    const float absolute_bar =
        fmaxf(gauge_bar, 0.0f) +
        saturation_absolute_bar(parameters, parameters->steam_saturation_temperature_c);
    return parameters->steam_saturation_antoine_b_k /
               (parameters->steam_saturation_antoine_a -
                natural_log(absolute_bar) / NATURAL_LOG_OF_TEN) -
           parameters->steam_saturation_antoine_c_c;
}

/*
 * The superheat of steam at the modelled outlet: the casting less the drop the
 * casting-to-outlet relation gives for the rate steam is made at, less
 * saturation at the pressure the path carries, and nothing below that.
 *
 * Superheat appears only once the steam is dry, and the steam is dry only once
 * the casting it passes is hotter than the water boils at: a block whose heater
 * cannot pay for the sensible and latent heat of what it is fed falls towards
 * and below saturation, and its outlet carries none. Nothing is made, nothing
 * leaves and there is no outlet to speak of, so no steam has no superheat.
 *
 * The energy the superheat itself carries away is not charged to the casting: at
 * the rates and the few kelvin this block works at it is under a hundredth of
 * the latent heat charged for the same steam, and params/thermoblock.md carries
 * the omission.
 */
static float outlet_superheat_k(const plant_parameters_t *parameters, float drop_k_s_per_ml,
                                float casting_c, float pressure_bar, float made_ml_per_s)
{
    if (!(made_ml_per_s > 0.0f)) {
        return 0.0f;
    }

    const float outlet_c = casting_c - drop_k_s_per_ml * made_ml_per_s;
    return fmaxf(outlet_c - saturation_temperature_c(parameters, pressure_bar), 0.0f);
}

/*
 * The pressure a shut wand leaves: saturation of the casting while the block
 * holds liquid, and nothing while it holds none.
 */
static float shut_pressure_bar(const plant_model_t *model)
{
    return model->steam_liquid_inventory_ml > 0.0f
               ? trapped_pressure_bar(&model->coefficients, model->steam_temperature_c)
               : 0.0f;
}

/*
 * How far a first-order relaxation travels towards its settling value in `x`
 * time constants: 1 - exp(-x).
 *
 * Written with the exponential-less-one rather than as `1 - exp(-x)`. For a short
 * step the exponential is just under one, and subtracting it from one throws
 * away the leading digits of an answer that is itself small -- the error is
 * absolute in the exponential and so grows without bound relative to the
 * result. At a step a thousandth of the time constant that spelling is wrong in
 * the third significant figure, which is worse than assuming the rate held
 * constant across the step, the very thing this exists to improve on.
 */
static float settled_fraction(float x)
{
    return -plant_expm1f(-x);
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
 * The rate steam is actually leaving the machine, from the rate the step was
 * handed.
 *
 * A demand below zero is steam arriving rather than leaving, which is not a case
 * this machine has and not one these relations carry a term for. It is read as
 * no draw rather than run backwards through them, which would put energy into
 * the steam mass and pressure into the steam path out of nothing at all.
 *
 * A demand that is not a finite rate is read the same way, and that guard earns
 * its place separately from the one above. An unbounded or undefined rate does
 * not merely give a wrong answer here: every relation it enters stops producing
 * a number, and so does every quantity downstream of them, and a comparison
 * against one of those is false whichever way it is written -- so nothing that
 * inspects the model afterwards can see what happened. The seam refuses nothing
 * about the demand, deliberately, which leaves this the place it is answered.
 */
static float drawn_steam_ml_per_s(float steam_demand_ml_per_s)
{
    return isfinite(steam_demand_ml_per_s) ? fmaxf(steam_demand_ml_per_s, 0.0f) : 0.0f;
}

/*
 * What the steam being drawn costs the mass it is drawn from, as a power.
 *
 * Two costs against the one rate, and the block owes both. A millilitre leaving
 * as vapour is made good by a millilitre of feed arriving in its place, and that
 * replacement has to be carried from the temperature it arrives at up to the
 * temperature it turns at before any of the latent cost is owed on it. Charging
 * the second alone charges the block for the boiling and not for the heating
 * that has to happen first.
 *
 * Neither part is taken against this mass's own temperature, which is what keeps
 * the whole term a power the rate alone fixes. The sensible part is a difference
 * between two coefficients -- where the feed starts and where it turns -- and
 * both belong to the water and to whatever supplies it rather than to the block.
 * So it stays out of the relaxation the step is corrected by exactly as the
 * latent part does, and unlike the coffee side's drawn term, which is a
 * difference across two temperatures this structure itself keeps.
 *
 * That difference stops at nothing rather than going below it. A description
 * whose feed arrives above its own saturation temperature is admissible -- the
 * two coefficients are bounded separately and no relation ties them -- and read
 * literally it would have a draw warm the block, which is the same something out
 * of nothing the guard above refuses a negative demand for. Water arriving past
 * boiling costs nothing to bring to it, and that is the reading taken.
 *
 * What is still absent is any temperature for where the vapour goes: it leaves
 * as vapour and this structure keeps no state for the wand, so nothing here is
 * taken against one, and a hot block gives up the same per millilitre as a cool
 * one.
 *
 * The rate is the volume of water turned to steam rather than the volume the
 * vapour occupies, which is what puts it in the same unit as the coffee side's
 * drawn rate and lets one coefficient per millilitre stand against both.
 */
static float drawn_steam_power_w(const plant_parameters_t *p, float drawn_ml_per_s)
{
    const float to_saturation_k =
        fmaxf(p->steam_saturation_temperature_c - p->water_feed_temperature_c, 0.0f);
    const float per_ml_j =
        p->water_latent_heat_j_per_ml + p->water_heat_capacity_j_per_ml_k * to_saturation_k;
    return per_ml_j * drawn_ml_per_s;
}

/*
 * One mass's temperature after `seconds` of heating at `duty`, losing to ambient
 * and giving up `drawn_w` to whatever is being taken out of it. Exact for a
 * constant actuation over the step, and stable for any step length at any
 * admissible coefficients.
 *
 * `drawn_w` is a power and not a coefficient per kelvin, so it moves where the
 * mass is heading without changing how fast it gets there -- which is why it
 * enters the balance beside the delivered power and stays out of the relaxation
 * the step is corrected by. A loss that did depend on the mass's own temperature
 * would have to enter both, the way the coffee side's drawn term does.
 */
static float advanced_temperature(float temperature_c, float ambient_c, float heater_power_w,
                                   float duty, float drawn_w, float loss_w_per_k,
                                   float thermal_mass_j_per_k, float seconds)
{
    const float delivered_w = heater_power_w * duty;
    const float lost_w = loss_w_per_k * (temperature_c - ambient_c);
    const float steps_of_time_constant = (seconds * loss_w_per_k) / thermal_mass_j_per_k;
    const float effective_seconds = seconds * relaxation_factor(steps_of_time_constant);
    return temperature_c +
           ((delivered_w - lost_w - drawn_w) * effective_seconds) / thermal_mass_j_per_k;
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
 * The rate the steam side's feed pump was commanded to push replacement water in
 * at, from the level it was commanded with. The same shape as the brew path's
 * flow relation above and for the same reasons: linear in the level, zero when
 * it is zero, and carrying no resistance term, so what the water is being pushed
 * into makes no difference to the figure. It is a second pump on a second path
 * and not the brew pump under another name, which is why it reads a channel of
 * its own.
 */
static float commanded_steam_feed_ml_per_s(const plant_parameters_t *p,
                                           const plant_actuation_t *actuation)
{
    return p->steam_feed_flow_ml_per_s *
           (actuation->level_permille[ACTUATION_CHANNEL_STEAM_PUMP] / PERMILLE_FULL_SCALE);
}

/*
 * The rate steam is actually made at, which is the lower of what is being asked
 * for and what the feed is being commanded to replace.
 *
 * This block holds a little liquid but no reservoir a draw could lean on. Every
 * millilitre that leaves as vapour is a millilitre the feed pump has just pushed
 * in, so the feed is not a supply the
 * draw happens to lean on but the whole of what there is to draw from -- and a
 * demand beyond it is a demand for steam out of water the machine has not been
 * given. Taking the lower of the two is that fact and nothing more: it is a
 * bound on the rate, not a characteristic of the pump, and the pump's own
 * pressure-versus-flow behaviour is as absent here as it is on the brew side.
 *
 * With the feed commanded shut this is zero however hard the wand is opened,
 * which is the case worth being explicit about, because it is the one that reads
 * oddest and is the one this architecture actually has: opening a wand on a block
 * nothing is feeding makes no steam, and so reads no pressure through the
 * restriction, because the pressure with the wand open is set by this rate and
 * by nothing else.
 */
static float honoured_steam_ml_per_s(const plant_parameters_t *p,
                                     const plant_actuation_t *actuation,
                                     float steam_demand_ml_per_s)
{
    return fminf(drawn_steam_ml_per_s(steam_demand_ml_per_s),
                 commanded_steam_feed_ml_per_s(p, actuation));
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
        carried = plant_expf(-slow) * relaxation_factor(separation + separation);
        second_order = (relaxation_factor(slow) - carried) / fast;
    } else {
        /*
         * One decay with a turn on it. The turn is what the pair does when the
         * casting is chasing water that is behind it, and the step is exact
         * across however many turns it contains.
         */
        const float turn = sqrtf(-separation_squared);
        const float half_turn = plant_sinf(turn * 0.5f);
        const float decayed = plant_expf(-decay);
        carried = decayed * (plant_sinf(turn) / turn);
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
                                      float steam_demand_ml_per_s, float seconds)
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
     * The steam mass keeps the single-mass step, and keeps it under a draw as
     * well as without one: what the steam takes away is a power fixed by the
     * rate, so the mass has one temperature and one relaxation whether or not the
     * wand is open.
     *
     * The rate is the step's own argument bounded by this side's own feed, and
     * not anything of the brew path's. Giving this mass a term from the pump's
     * drawn rate would be the coffee side's water leaving through the steam wand,
     * and giving the coffee side a term from this one would be the reverse; the
     * two draws reach the two masses and neither reaches both, which is what this
     * machine's two separately fed blocks mean.
     */
    model->steam_temperature_c = advanced_temperature(
        model->steam_temperature_c, p->ambient_temperature_c, p->steam_heater_power_w,
        actuation->level_permille[ACTUATION_CHANNEL_STEAM_HEATER] / PERMILLE_FULL_SCALE,
        drawn_steam_power_w(p, honoured_steam_ml_per_s(p, actuation, steam_demand_ml_per_s)),
        p->steam_loss_w_per_k, p->steam_thermal_mass_j_per_k, seconds);
}

void thermoblock_advance_pressures(plant_model_t *model, const plant_actuation_t *actuation,
                                   float steam_demand_ml_per_s, float seconds)
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

    /*
     * The liquid held. Feed raises it and the steam made lowers it, and the made
     * rate is never above the feed, so the inventory never falls below zero by
     * this arithmetic; the bounds are written all the same because the capacity
     * is the declared limit and not a consequence of the rates.
     */
    const float demanded_ml_per_s = drawn_steam_ml_per_s(steam_demand_ml_per_s);
    const float made_ml_per_s = honoured_steam_ml_per_s(p, actuation, steam_demand_ml_per_s);
    const float fed_ml_per_s = commanded_steam_feed_ml_per_s(p, actuation);

    model->steam_liquid_inventory_ml =
        fminf(fmaxf(model->steam_liquid_inventory_ml + (fed_ml_per_s - made_ml_per_s) * seconds,
                    0.0f),
              p->steam_liquid_capacity_ml);

    if (demanded_ml_per_s > 0.0f) {
        /*
         * A draw is open: the pressure is the drop across the restriction the
         * steam being made goes through, and the casting temperature does not
         * enter. With the feed shut nothing is made, so the drop is nothing.
         */
        model->steam_pressure_bar =
            p->steam_restriction_bar_s2_per_ml2 * made_ml_per_s * made_ml_per_s;
    } else {
        model->steam_pressure_bar = shut_pressure_bar(model);
    }

    model->steam_outlet_superheat_k =
        demanded_ml_per_s > 0.0f
            ? outlet_superheat_k(p, p->steam_outlet_drop_k_s_per_ml, model->steam_temperature_c,
                                 model->steam_pressure_bar, made_ml_per_s)
            : 0.0f;
}

bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters)
{
    if (model == NULL || parameters == NULL) {
        return false;
    }
    /* A record this structure's own ranges and relations refuse is not run. */
    if (!plant_parameters_admissible(parameters, NULL)) {
        model->initialised = false;
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
    model->steam_draw_ml_per_s = 0.0f;
    model->steam_outlet_superheat_k = 0.0f;
    /* The block starts holding the declared liquid, which the admissibility check has held to
     * the capacity, and the wand shut, so the pressure is the one its own
     * equations give for that state. */
    model->steam_liquid_inventory_ml = parameters->steam_initial_inventory_ml;
    model->steam_pressure_bar = shut_pressure_bar(model);
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

    const float seconds = (float)interval_millis / MILLIS_PER_SECOND;

    /*
     * Temperatures first, then pressures: the trapped pressure follows the casting
     * temperature, so within one step it reflects where that mass has just
     * arrived.
     *
     * The drawn rate and the actuation are handed to both of them. The steam
     * feed channel sets the rate steam is made at and so the pressure with the
     * wand open, and it fills the held liquid.
     */
    thermoblock_advance_temperatures(model, actuation, steam_demand_ml_per_s, seconds);
    thermoblock_advance_pressures(model, actuation, steam_demand_ml_per_s, seconds);

    /*
     * The rate drawn over the step just taken. It is recomputed whole rather
     * than advanced, so where it is set within the step does not matter; it is
     * set here rather than inside either advance because it is neither a
     * temperature nor a pressure, and folding it into one of those would make
     * that function's name a smaller truth than its body.
     */
    model->brew_flow_ml_per_s = commanded_flow_ml_per_s(&model->coefficients, actuation);
    /*
     * The rate steam was asked for over the same step, taken through the same
     * guard the two advances read the demand through rather than from the
     * argument directly, so that a demand the structure refuses reads as no draw
     * here as well as there.
     *
     * It is the demand as that guard leaves it and nothing else: this quantity
     * passes the step's own input through, and deriving it from anything besides
     * that input is outside what the quantity was named to do. The feed bound is
     * such a derivation -- it reads the actuation record -- so it stays out of
     * this line even though it is in both relations above.
     *
     * The consequence is that the figure reported and the figure the relations
     * spent energy against are the same number whenever the feed can keep up and
     * come apart when it cannot. That is a real gap in what a consumer can see
     * and it is recorded as one in params/thermoblock.md, rather than closed here
     * by reporting one of the two under the other's name.
     */
    model->steam_draw_ml_per_s = drawn_steam_ml_per_s(steam_demand_ml_per_s);
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
    case PLANT_QUANTITY_STEAM_DRAW_ML_PER_S:
        *value = model->steam_draw_ml_per_s;
        return true;
    case PLANT_QUANTITY_STEAM_OUTLET_SUPERHEAT_K:
        *value = model->steam_outlet_superheat_k;
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
    case PLANT_STATE_STEAM_LIQUID_INVENTORY_ML:
        *value = model->steam_liquid_inventory_ml;
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

    /*
     * The held liquid is the one state with a physical limit the model itself
     * states, so a value outside it is refused rather than held until the first
     * step clamps it. The temperatures stay free: the ceiling probe sets one
     * above the ceiling on purpose.
     */
    if (state == PLANT_STATE_STEAM_LIQUID_INVENTORY_ML &&
        !(value >= 0.0f && value <= model->coefficients.steam_liquid_capacity_ml)) {
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
    case PLANT_STATE_STEAM_LIQUID_INVENTORY_ML:
        model->steam_liquid_inventory_ml = value;
        return true;
    case PLANT_STATE_COUNT:
    default:
        return false;
    }
}

/*
 * The least superheat the casting-to-outlet relation admits for these readings:
 * its coefficient is taken at the end of its declared error that leaves the
 * outlet coolest, which is the one that makes the steam faster to lose its
 * superheat, and everything else at the description's figure. The steam made is
 * taken to be the feed, which is what a draw that takes all it is fed makes.
 */
bool plant_model_least_outlet_superheat(const plant_parameters_t *parameters,
                                        const plant_parameter_budget_t *budget, float casting_c,
                                        float pressure_bar, uint16_t feed_permille,
                                        float *superheat_k)
{
    if (parameters == NULL || budget == NULL || superheat_k == NULL || !isfinite(casting_c) ||
        !isfinite(pressure_bar)) {
        return false;
    }

    float drop_error = 0.0f;
    for (size_t at = 0u; at < sizeof(SPECS) / sizeof(SPECS[0]) && at < budget->count; at++) {
        if (SPECS[at].offset == offsetof(plant_parameters_t, steam_outlet_drop_k_s_per_ml) &&
            budget->declared[at]) {
            drop_error = fmaxf(budget->assumed_error[at], 0.0f);
        }
    }

    const float made_ml_per_s =
        parameters->steam_feed_flow_ml_per_s * ((float)feed_permille / PERMILLE_FULL_SCALE);
    *superheat_k = outlet_superheat_k(parameters,
                                      parameters->steam_outlet_drop_k_s_per_ml * (1.0f + drop_error),
                                      casting_c, pressure_bar, made_ml_per_s);
    return true;
}
