/*
 * The flow_fixture structure's implementation.
 *
 * It satisfies the same interface the machine-describing structures do, so
 * the same consumers link against it unchanged -- on the same terms
 * `fixture`'s implementation does, and for the same reason. It models
 * nothing; what it answers is chosen so control_init can come up against it,
 * which is the whole of what it is for. See plant_structure.h.
 */
#include "plant_model.h"

#include <stddef.h>
#include <string.h>

#define MILLIS_PER_SECOND 1000.0f
#define PERMILLE_FULL_SCALE 1000.0f

static const plant_parameter_spec_t SPECS[] = {
    {"fixture.gain", -1000.0f, 1000.0f, offsetof(plant_parameters_t, fixture_gain)},
    {"pump.flow_ml_per_s", 0.0f, 1000.0f, offsetof(plant_parameters_t, pump_flow_ml_per_s)},
};

const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count)
{
    if (count != NULL) {
        *count = sizeof(SPECS) / sizeof(SPECS[0]);
    }
    return SPECS;
}

void flow_fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation,
                             float seconds)
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

plant_delivery_point_set_t plant_structure_delivery_points(void)
{
    return PLANT_STRUCTURE_DELIVERY_POINTS;
}

/* Each point answers a different identifier: they draw on independent masses. */
bool plant_structure_delivery_point_mass(plant_delivery_point_t point,
                                         plant_heated_mass_id_t *mass)
{
    if (mass == NULL) {
        return false;
    }
    if ((PLANT_STRUCTURE_DELIVERY_POINTS & PLANT_DELIVERY_POINT_BIT(point)) == 0u) {
        return false;
    }

    *mass = (point == PLANT_DELIVERY_POINT_GROUP) ? 0u : 1u;
    return true;
}

bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters)
{
    if (model == NULL || parameters == NULL) {
        return false;
    }
    memset(model, 0, sizeof(*model));
    model->coefficients = *parameters;
    model->accumulated = 0.0f;
    model->brew_flow_ml_per_s = 0.0f;
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

    /* This structure describes no machine and models nothing the drawn rate
     * could act on, so the demand is accepted and not acted on. */
    (void)steam_demand_ml_per_s;

    flow_fixture_accumulate(model, actuation, (float)interval_millis / MILLIS_PER_SECOND);

    /*
     * Recomputed whole from the commanded pump level every step, on the same
     * terms the machine-describing structures' own drawn-rate figure is: it is
     * not integrated and carries nothing over from the step before. It scales
     * linearly with the commanded level because there is no equation here for
     * it to follow instead -- what this structure needs is a positive figure
     * for admission to compare a course's peak against, not an account of how
     * a real pump behaves.
     */
    model->brew_flow_ml_per_s = model->coefficients.pump_flow_ml_per_s *
                                ((float)actuation->level_permille[ACTUATION_CHANNEL_PUMP] /
                                 PERMILLE_FULL_SCALE);
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
     * The drawn rate answers the flow the step just took rather than the
     * accumulator, unlike `fixture`'s: this structure answers a pump channel
     * -- see plant_structure.h for why -- so there is a commanded level for a
     * rate to be derived from, and answering the accumulator here would
     * report a figure with nothing to do with what the pump was actually
     * told.
     */
    case PLANT_QUANTITY_BREW_FLOW_ML_PER_S:
        *value = model->brew_flow_ml_per_s;
        return true;
    /*
     * No steam channel is answered, so no steam is ever made here whatever a
     * caller asks for -- on the same terms `fixture` answers this quantity.
     */
    case PLANT_QUANTITY_STEAM_DRAW_ML_PER_S:
        *value = 0.0f;
        return true;
    /*
     * Not a quantity, so there is nothing to answer with. No default label
     * beside it, and that absence is deliberate: -Wall gives -Wswitch and
     * this is built under -Werror, so a quantity added to the machine's
     * vocabulary fails the build here rather than being quietly refused.
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
     * Narrower than the quantities above, and narrower than the vocabulary --
     * this structure describes no machine, so it is free to keep whatever
     * state it likes. The one it answers is the accumulator, under the name
     * of the water on its way out, because that is the one state
     * ESTIMATOR_STATE_BREW_TEMPERATURE_C reconstructs -- see estimator.c's
     * STATE_FOR_RECONSTRUCTION -- and control_init refuses to come up
     * against a structure that does not keep it. Nothing here claims it is a
     * temperature of anything real. The other four states remain refused:
     * this structure keeps no separate mass state, no steam-side state and no
     * pressure state, because it answers no channel any of them would come
     * from.
     */
    switch (state) {
    case PLANT_STATE_BREW_OUTLET_TEMPERATURE_C:
        *value = model->accumulated;
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

bool plant_model_set_state(plant_model_t *model, plant_state_t state, float value)
{
    if (model == NULL || !model->initialised) {
        return false;
    }

    /*
     * The same one state the read answers, and the same refusals for the
     * rest. A structure that answered a write it would not answer a read for
     * could be written to and then not read back, which is a worse thing to
     * be than narrow.
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
