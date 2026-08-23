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

    fixture_accumulate(model, actuation, (float)interval_millis / MILLIS_PER_SECOND);
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
    /*
     * The drawn rate answers zero rather than the accumulator, and is the one
     * quantity here that does. The others stand for nothing in particular, so
     * the accumulator is as good an answer as any; a rate is different, because
     * this structure answers no pump channel at all. There is no commanded
     * level for a rate to be derived from, and reporting the accumulator would
     * claim water was moving on a structure that cannot be told to move any.
     * Refusing it is not open either -- a quantity is the machine's vocabulary
     * and every structure answers every one -- so the answer is the honest
     * quantity, which is none.
     */
    case PLANT_QUANTITY_BREW_FLOW_ML_PER_S:
        *value = 0.0f;
        return true;
    /*
     * The rate steam is drawn answers zero as well, and arrives there from the
     * opposite direction to the rate above. That one has no commanded level to be
     * derived from; this one is handed a demand on every step, because the demand
     * is a step argument every structure takes whatever it models. What this
     * structure does with it is nothing -- it has no mass for a draw to cool and
     * no path for one to vent, so no steam leaves it however hard a caller asks.
     *
     * Echoing the demand back would therefore report a draw that did not happen,
     * on the one structure whose whole purpose is to have no machine behind it.
     * The two rates answer zero for one reason underneath: the honest rate for a
     * structure that moves nothing is none.
     */
    case PLANT_QUANTITY_STEAM_DRAW_ML_PER_S:
        *value = 0.0f;
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

bool plant_model_set_state(plant_model_t *model, plant_state_t state, float value)
{
    if (model == NULL || !model->initialised) {
        return false;
    }

    /*
     * The same one state the read answers, and the same refusals for the rest.
     * A structure that answered a write it would not answer a read for could be
     * written to and then not read back, which is a worse thing to be than
     * narrow.
     */
    switch (state) {
    case PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C:
        model->accumulated = value;
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
