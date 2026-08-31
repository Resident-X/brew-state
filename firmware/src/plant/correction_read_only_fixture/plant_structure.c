/*
 * The correction_read_only_fixture structure's implementation.
 *
 * It satisfies the same interface the machine-describing structure does, so
 * the same consumers link against it unchanged -- on the same terms
 * `fixture`'s implementation does. It models nothing; what it answers is
 * chosen so every read `estimator_init` makes succeeds and the one write it
 * makes does not. See plant_structure.h.
 */
#include "plant_model.h"

#include <stddef.h>
#include <string.h>

#define MILLIS_PER_SECOND 1000.0f
#define PERMILLE_FULL_SCALE 1000.0f

static const plant_parameter_spec_t SPECS[] = {
    {"outlet.value_c", -100.0f, 250.0f, offsetof(plant_parameters_t, outlet_value_c)},
    {"heater.gain", -1000.0f, 1000.0f, offsetof(plant_parameters_t, heater_gain)},
};

const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SPECS) / sizeof(SPECS[0]);
    }
    return SPECS;
}

/*
 * This structure describes no machine, so no supply drives any of it, on the
 * same terms the fixtures beside it state.
 */
const char *const *plant_structure_supply_driven_parameters(size_t *count)
{
    if (count != NULL) {
        *count = 0u;
    }
    return NULL;
}

actuation_channel_set_t plant_structure_actuation_channels(void)
{
    return PLANT_STRUCTURE_ACTUATION_CHANNELS;
}

plant_delivery_point_set_t plant_structure_delivery_points(void)
{
    return PLANT_STRUCTURE_DELIVERY_POINTS;
}

/* This structure serves no delivery point, so every point is refused. */
bool plant_structure_delivery_point_mass(plant_delivery_point_t point,
                                         plant_heated_mass_id_t *mass)
{
    if (mass == NULL) {
        return false;
    }
    (void)point;
    return false;
}

bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters)
{
    if (model == NULL || parameters == NULL) {
        return false;
    }
    memset(model, 0, sizeof(*model));
    model->coefficients = *parameters;
    /*
     * Seeded straight from the one coefficient rather than left at nothing:
     * what this structure exists to answer is admission's probes, and a value
     * of exactly zero would leave a reader unable to tell an answered state
     * carrying its seed from one that was never seeded at all.
     */
    model->accumulated = parameters->outlet_value_c;
    model->initialised = true;
    return true;
}

/* Add what the brew heater commanded over `seconds`, scaled by the gain --
 * on the same terms fixture_accumulate does, so the one channel this
 * structure answers is exercised rather than declared and left inert. */
void correction_read_only_fixture_accumulate(plant_model_t *model,
                                             const plant_actuation_t *actuation, float seconds)
{
    model->accumulated += model->coefficients.heater_gain *
                          (actuation->level_permille[ACTUATION_CHANNEL_BREW_HEATER] /
                           PERMILLE_FULL_SCALE) *
                          seconds;
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

    /* This structure describes no machine and models nothing the drawn rate
     * could act on, so the demand is accepted and not acted on. */
    (void)steam_demand_ml_per_s;

    correction_read_only_fixture_accumulate(model, actuation,
                                            (float)interval_millis / MILLIS_PER_SECOND);
    return true;
}

bool plant_model_quantity(const plant_model_t *model, plant_quantity_t quantity, float *value)
{
    if (model == NULL || value == NULL || !model->initialised) {
        return false;
    }

    /*
     * Every temperature and pressure quantity answers from the one
     * accumulator, on the same terms `fixture`'s does: the interface's
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
    /*
     * Neither rate has a commanded level or a demand behind it here -- this
     * structure answers no pump channel and moves nothing a draw could act
     * on -- so the honest answer for both is none, on the same terms
     * `fixture` answers them.
     */
    case PLANT_QUANTITY_BREW_FLOW_ML_PER_S:
    case PLANT_QUANTITY_STEAM_DRAW_ML_PER_S:
        *value = 0.0f;
        return true;
    /*
     * Not a quantity, so there is nothing to answer with. No default label
     * beside it: -Wall gives -Wswitch and this is built under -Werror, so a
     * quantity added to the machine's vocabulary fails the build here rather
     * than being quietly refused.
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
     * Both names the estimator reaches its one reconstructed value by, answered
     * from the one accumulator -- the state the reconstruction is held as, and
     * the state the correction for that same value is applied through, reached
     * by the two-hop walk `correct_against` takes. Answering both is what lets
     * every read `estimator_init` makes succeed against this structure, which
     * is the whole point of it: what this structure is built to be caught by is
     * the write, not a read.
     *
     * The steam and pressure states are refused because this structure keeps no
     * accumulator that could stand for them and no equation that could populate
     * one. Nothing admission asks reaches them, so refusing them costs this
     * structure nothing and narrows it honestly.
     */
    switch (state) {
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
        *value = model->accumulated;
        return true;
    case PLANT_STATE_STEAM_TEMPERATURE_C:
    case PLANT_STATE_BREW_PRESSURE_BAR:
    case PLANT_STATE_STEAM_PRESSURE_BAR:
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
     * One name fewer than the read above answers, and the missing one is the
     * whole of what this structure is for: the state the estimator's per-step
     * correction writes toward is refused here while a read of it succeeds.
     *
     * Every other structure in the tree answers its reads and its writes for
     * exactly the same set of states, and says so in a comment beside this
     * switch. That parity was convention -- nothing enforced it -- and this
     * structure is the counterexample that makes the enforcement testable.
     * Deliberately broken here, and broken in the one direction that was ever
     * admissible: a structure answering a write it refuses a read for is
     * caught by the reachability probe on the first read it is asked for,
     * while this one satisfies every read that probe makes and is only found
     * out by the write beside them.
     */
    switch (state) {
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
        model->accumulated = value;
        return true;
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
    case PLANT_STATE_STEAM_TEMPERATURE_C:
    case PLANT_STATE_BREW_PRESSURE_BAR:
    case PLANT_STATE_STEAM_PRESSURE_BAR:
    case PLANT_STATE_COUNT:
    default:
        return false;
    }
}
