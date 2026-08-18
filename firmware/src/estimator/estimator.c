/*
 * The estimator behind estimator.h.
 *
 * It holds an instance of the plant model rather than equations of its own.
 * A second set of equations written to suit the estimator answers the same
 * question differently as soon as either is corrected, and that divergence
 * arrives disguised: predictions that stop matching observation look exactly
 * like a machine that has drifted, which is the one thing an estimator exists
 * to tell apart.
 *
 * Nothing here includes a structure's header or names a field of one. The model
 * is reached only through the plant seam, which is what lets this file be
 * compiled against whichever structure a build selected.
 */
#include "estimator.h"

#include <math.h>
#include <stddef.h>

/*
 * How much of a channel's disagreement is taken out of the state that channel
 * observes, per step. A fraction of one converges without overshooting: the
 * error in an observed state is multiplied by one minus this on every
 * correction, so anything in (0, 1] settles and a half settles quickly. It is a
 * property of the correction rather than of any machine, which is why it is
 * here and not in a parameter record.
 */
#define ESTIMATOR_CORRECTION_GAIN 0.5f

/* Thousandths of a unit, which is what the hardware seam reads in. */
#define ESTIMATOR_MILLI_PER_UNIT 1000.0f

/*
 * What each sensor channel is a measurement of. The hardware seam and the plant
 * seam enumerate the machine's quantities separately -- one is what can be
 * placed against it, the other is what it has -- and this is the correspondence
 * between them, stated rather than assumed from the order they happen to be
 * declared in.
 */
static const plant_quantity_t QUANTITY_FOR_CHANNEL[HW_SENSOR_CHANNEL_COUNT] = {
    [HW_SENSOR_BREW_TEMPERATURE] = PLANT_QUANTITY_BREW_TEMPERATURE_C,
    [HW_SENSOR_STEAM_TEMPERATURE] = PLANT_QUANTITY_STEAM_TEMPERATURE_C,
    [HW_SENSOR_BREW_PRESSURE] = PLANT_QUANTITY_BREW_PRESSURE_BAR,
    [HW_SENSOR_STEAM_PRESSURE] = PLANT_QUANTITY_STEAM_PRESSURE_BAR,
};

/*
 * Which state a disagreement about a quantity is taken out of. A quantity is
 * produced by the states a structure keeps, and this names the one that most
 * directly produces it -- the only place a correction can be applied without
 * the seam telling the estimator how the equations are wired, which it
 * deliberately does not.
 *
 * A structure whose equations recompute one of these from another on every step
 * will overwrite the correction, and that is the structure's answer rather than
 * an error here: the correction was offered and the equations decided.
 *
 * This pairing carries a demand on any structure that arrives later: the
 * quantity has to be that state, in that state's unit, and not a blend of
 * several. Subtracting a disagreement measured in one unit from a state held in
 * another is dimensionally meaningless and has no symptom -- the estimator goes
 * on running and reports residuals that look ordinary. Every structure in the
 * tree satisfies it today. A structure that did not would need the seam to say
 * how its quantities are produced, which it deliberately does not, so a
 * structure of that shape is a reason to revisit this correspondence rather
 * than something to be absorbed here.
 */
static const plant_state_t STATE_FOR_QUANTITY[PLANT_QUANTITY_COUNT] = {
    [PLANT_QUANTITY_BREW_TEMPERATURE_C] = PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C,
    [PLANT_QUANTITY_STEAM_TEMPERATURE_C] = PLANT_STATE_STEAM_TEMPERATURE_C,
    [PLANT_QUANTITY_BREW_PRESSURE_BAR] = PLANT_STATE_BREW_PRESSURE_BAR,
    [PLANT_QUANTITY_STEAM_PRESSURE_BAR] = PLANT_STATE_STEAM_PRESSURE_BAR,
};

/* Which state of the model each state this seam answers for is held as. */
static const plant_state_t STATE_FOR_RECONSTRUCTION[ESTIMATOR_STATE_COUNT] = {
    [ESTIMATOR_STATE_BREW_TEMPERATURE_C] = PLANT_STATE_BREW_OUTLET_TEMPERATURE_C,
};

/*
 * A reading in the unit the hardware seam reports, saturating rather than
 * wrapping. The seam's readings are bounded by what an int32_t holds, and a
 * model that has been driven somewhere absurd must not turn into a plausible
 * small number on the way to being compared with one.
 */
static int32_t milli_from_unit(float value)
{
    const float scaled = value * ESTIMATOR_MILLI_PER_UNIT;

    if (!(scaled > (float)INT32_MIN)) {
        return INT32_MIN;
    }
    if (!(scaled < (float)INT32_MAX)) {
        return INT32_MAX;
    }
    return (int32_t)lroundf(scaled);
}

/* Predicted minus observed, saturating for the same reason. */
static int32_t difference_milli(int32_t predicted, int32_t observed)
{
    const int64_t delta = (int64_t)predicted - (int64_t)observed;

    if (delta > (int64_t)INT32_MAX) {
        return INT32_MAX;
    }
    if (delta < (int64_t)INT32_MIN) {
        return INT32_MIN;
    }
    return (int32_t)delta;
}

static void forget_residuals(estimator_t *estimator)
{
    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        estimator->residual_fresh[channel] = false;
        estimator->residual_milli[channel] = 0;
    }
}

/*
 * Correct one state toward what one channel observed, recording the difference
 * that was used. Returns false when the comparison could not be made or the
 * correction could not be applied -- in which case nothing is recorded, so that
 * a reported residual always means a correction happened.
 */
static bool correct_against(estimator_t *estimator, hw_sensor_channel_t channel,
                            int32_t observed_milli)
{
    const plant_quantity_t quantity = QUANTITY_FOR_CHANNEL[channel];
    const plant_state_t corrected = STATE_FOR_QUANTITY[quantity];

    float predicted = 0.0f;
    if (!plant_model_quantity(&estimator->model, quantity, &predicted)) {
        return false;
    }

    float held = 0.0f;
    if (!plant_model_state(&estimator->model, corrected, &held)) {
        return false;
    }

    const int32_t residual = difference_milli(milli_from_unit(predicted), observed_milli);
    const float taken_out =
        ESTIMATOR_CORRECTION_GAIN * ((float)residual / ESTIMATOR_MILLI_PER_UNIT);

    if (!plant_model_set_state(&estimator->model, corrected, held - taken_out)) {
        return false;
    }

    estimator->residual_milli[channel] = residual;
    estimator->residual_fresh[channel] = true;
    return true;
}

bool estimator_init(estimator_t *estimator, const plant_parameters_t *parameters)
{
    if (estimator == NULL || parameters == NULL) {
        return false;
    }

    estimator->ready = false;
    forget_residuals(estimator);

    if (!plant_model_init(&estimator->model, parameters)) {
        return false;
    }

    /*
     * Settle here whether this structure can carry what this seam answers for.
     * A structure that does not keep one of these states is one whose
     * architecture has nowhere for it to live, and the caller is better told
     * that now than handed a substitute on every read afterwards.
     */
    for (unsigned state = 0u; state < (unsigned)ESTIMATOR_STATE_COUNT; state++) {
        float reachable = 0.0f;
        if (!plant_model_state(&estimator->model, STATE_FOR_RECONSTRUCTION[state], &reachable)) {
            return false;
        }
    }

    estimator->ready = true;
    return true;
}

bool estimator_step(estimator_t *estimator, const plant_actuation_t *actuation,
                    uint32_t interval_millis)
{
    if (estimator == NULL || !estimator->ready) {
        return false;
    }

    /*
     * Cleared before the step rather than after it, so that a step which is
     * refused leaves no residual behind. A stale residual read as a fresh one
     * would report a disagreement the machine is no longer in.
     */
    forget_residuals(estimator);

    if (!plant_model_step(&estimator->model, actuation, interval_millis)) {
        return false;
    }

    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        const hw_reading_t observed = hw_sensor_read((hw_sensor_channel_t)channel);
        if (!observed.valid) {
            continue;
        }
        (void)correct_against(estimator, (hw_sensor_channel_t)channel, observed.value_milli);
    }

    return true;
}

bool estimator_state(const estimator_t *estimator, estimator_state_t state, float *value)
{
    if (estimator == NULL || value == NULL || !estimator->ready) {
        return false;
    }
    if ((unsigned)state >= (unsigned)ESTIMATOR_STATE_COUNT) {
        return false;
    }

    float reconstructed = 0.0f;
    if (!plant_model_state(&estimator->model, STATE_FOR_RECONSTRUCTION[state], &reconstructed)) {
        return false;
    }

    /*
     * A reconstruction that is not a number is not a temperature, and a caller
     * that acted on it would be acting on nothing. Refusing puts it on the same
     * footing as an instance that never initialised, which is what a consumer
     * already knows how to respond to; handing it back would make every
     * consumer's comparison against it decide the answer by which way round it
     * was written.
     */
    if (!isfinite(reconstructed)) {
        return false;
    }

    *value = reconstructed;
    return true;
}

bool estimator_residual(const estimator_t *estimator, hw_sensor_channel_t channel,
                        int32_t *residual_milli)
{
    if (estimator == NULL || residual_milli == NULL) {
        return false;
    }
    if ((unsigned)channel >= (unsigned)HW_SENSOR_CHANNEL_COUNT) {
        return false;
    }
    if (!estimator->residual_fresh[channel]) {
        return false;
    }

    *residual_milli = estimator->residual_milli[channel];
    return true;
}
