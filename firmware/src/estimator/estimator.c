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
 *
 * A switch with no default label rather than a table indexed by the channel,
 * for the reason the pairing below is one: a channel added to the hardware seam
 * without being answered for here would have taken the zeroth entry of such a
 * table, which is a real quantity, so a new channel would have read as the brew
 * casting's temperature and been corrected against the state that produces it.
 * That is the same silent wrong answer the pairing below exists to refuse, one
 * lookup earlier in the same two-hop walk, and refusing it in one place and not
 * the other would leave the walk exactly as reachable as before.
 */
static bool quantity_measured_by(hw_sensor_channel_t channel, plant_quantity_t *quantity)
{
    switch (channel) {
    case HW_SENSOR_BREW_TEMPERATURE:
        *quantity = PLANT_QUANTITY_BREW_TEMPERATURE_C;
        return true;
    case HW_SENSOR_STEAM_TEMPERATURE:
        *quantity = PLANT_QUANTITY_STEAM_TEMPERATURE_C;
        return true;
    case HW_SENSOR_BREW_PRESSURE:
        *quantity = PLANT_QUANTITY_BREW_PRESSURE_BAR;
        return true;
    case HW_SENSOR_STEAM_PRESSURE:
        *quantity = PLANT_QUANTITY_STEAM_PRESSURE_BAR;
        return true;
    /* Not a channel, and so a measurement of nothing. */
    case HW_SENSOR_CHANNEL_COUNT:
        return false;
    }

    /* Reached only by a value that is not in the vocabulary at all. */
    return false;
}

/*
 * The state each quantity is observed from, or a refusal. Written as a switch
 * over the vocabulary with no default label rather than as a table indexed by
 * the quantity, and that shape is the whole mechanism: -Wall gives -Wswitch,
 * the shipping target compiles this under -Werror, and so a quantity added to
 * the vocabulary without being answered for here fails the build. It replaced a
 * table filled by designated initialiser, which was the same statement made in
 * a form that could not fail -- an unlisted quantity took the zeroth entry, and
 * the zeroth entry is a real state, so the omission read as an observation of
 * the brew casting rather than as an omission. Sizing an assertion against the
 * quantity count would not have caught it either: such a table is sized by that
 * count and so stays exactly the right size at the moment an entry goes
 * missing.
 *
 * This is also the only path from a quantity to a state. There is no table left
 * for a caller to subscript instead, so a quantity that observes nothing cannot
 * reach a state by any route rather than merely by convention.
 *
 * The failure being closed is not a crash. It is the estimator correcting the
 * wrong state against a reading and going on running, reporting residuals that
 * look ordinary -- which presents as a machine that has drifted rather than as
 * a miswiring, and telling those two apart is what the residual exists for.
 *
 * The pairing this expresses carries a demand on any structure that arrives
 * later: where a quantity is observed, it has to be that state, in that state's
 * unit, and not a blend of several. Subtracting a disagreement measured in one
 * unit from a state held in another is dimensionally meaningless and has no
 * symptom. Every structure in the tree satisfies it today; one that did not
 * would need the seam to say how its quantities are produced, which it
 * deliberately does not, so such a structure is a reason to revisit this
 * correspondence rather than something to absorb here.
 *
 * A structure whose equations recompute one of these from another on every step
 * will overwrite the correction, and that is the structure's answer rather than
 * an error here: the correction was offered and the equations decided.
 */
static bool state_observed_by(plant_quantity_t quantity, plant_state_t *state)
{
    switch (quantity) {
    case PLANT_QUANTITY_BREW_TEMPERATURE_C:
        *state = PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C;
        return true;
    case PLANT_QUANTITY_STEAM_TEMPERATURE_C:
        *state = PLANT_STATE_STEAM_TEMPERATURE_C;
        return true;
    case PLANT_QUANTITY_BREW_PRESSURE_BAR:
        *state = PLANT_STATE_BREW_PRESSURE_BAR;
        return true;
    case PLANT_QUANTITY_STEAM_PRESSURE_BAR:
        *state = PLANT_STATE_STEAM_PRESSURE_BAR;
        return true;
    /*
     * The rate water is drawn is refused deliberately rather than by omission.
     * No structure keeps it as a state -- it is produced from what the pump was
     * commanded rather than integrated -- so there is no state a reading of it
     * could correct, and a reader can see that was decided here.
     */
    case PLANT_QUANTITY_BREW_FLOW_ML_PER_S:
        return false;
    /* Not a quantity, and so observed by nothing. */
    case PLANT_QUANTITY_COUNT:
        return false;
    }

    /* Reached only by a value that is not in the vocabulary at all. */
    return false;
}

/* Which state of the model each state this seam answers for is held as. */
static const plant_state_t STATE_FOR_RECONSTRUCTION[ESTIMATOR_STATE_COUNT] = {
    [ESTIMATOR_STATE_BREW_TEMPERATURE_C] = PLANT_STATE_BREW_OUTLET_TEMPERATURE_C,
};

/*
 * Which observations each reconstructed state rests on, read from the seam's
 * own declaration rather than restated here. A second statement of it would be
 * the one that disagreed after a state was added.
 */
static const estimator_observation_set_t OBSERVATIONS_FOR_RECONSTRUCTION[ESTIMATOR_STATE_COUNT] =
    ESTIMATOR_STATE_OBSERVATIONS;

/*
 * A state added to the vocabulary without its dependencies stated would default
 * to depending on nothing, and a state depending on nothing is one no gap can
 * ever starve -- it would go on being reported usable through a total loss of
 * observation, which is the failure this table exists to prevent. Designated
 * initialisers make that omission silent, so the build is made to notice it.
 */
_Static_assert(sizeof(OBSERVATIONS_FOR_RECONSTRUCTION) /
                       sizeof(OBSERVATIONS_FOR_RECONSTRUCTION[0]) ==
                   (size_t)ESTIMATOR_STATE_COUNT,
               "every reconstructed state names the observations it depends on");

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

/*
 * Whether a reading that arrived is one the machine could actually have
 * produced. Compared in the unit the seam reports, so nothing is converted on
 * the way to being judged: a reading is either inside the span the description
 * declared for its channel or it is not.
 *
 * This is a different question from the one the seam's own flag answers. That
 * flag says whether a sample could be obtained; this says whether the sample
 * obtained is possible. A disconnected or shorted channel produces values that
 * are arithmetically fine and physically absurd, and correcting against one
 * drags the reconstruction toward a state the machine cannot be in.
 */
static bool reading_is_plausible(const estimator_t *estimator, hw_sensor_channel_t channel,
                                 int32_t value_milli)
{
    return value_milli >= estimator->limits.low_milli[channel] &&
           value_milli <= estimator->limits.high_milli[channel];
}

/*
 * Add an elapsed interval to a figure that must not wrap. A gap that overflowed
 * back to nothing would report a state starved of observation for weeks as
 * freshly observed, which is the one answer worse than either bound.
 */
static uint32_t saturating_add(uint32_t accumulated, uint32_t interval_millis)
{
    if (UINT32_MAX - accumulated < interval_millis) {
        return UINT32_MAX;
    }
    return accumulated + interval_millis;
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
    plant_quantity_t quantity = PLANT_QUANTITY_COUNT;
    if (!quantity_measured_by(channel, &quantity)) {
        return false;
    }

    plant_state_t corrected = PLANT_STATE_COUNT;
    if (!state_observed_by(quantity, &corrected)) {
        return false;
    }

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

bool estimator_init(estimator_t *estimator, const plant_parameters_t *parameters,
                    const estimator_limits_t *limits)
{
    if (estimator == NULL) {
        return false;
    }

    /*
     * Put the instance into its refusing state before anything else is looked
     * at, including the arguments. What this seam promises is that an instance
     * which refused to initialise answers nothing, and that promise has to hold
     * for an instance whose initialisation was refused on its first line -- a
     * caller that passed no record still holds the instance afterwards, and
     * every read of it must refuse rather than report whatever the memory it
     * was declared in happened to contain.
     *
     * No state has been observed yet, and none has an anchor. Starting the
     * elapsed figures at nothing rather than at the window is deliberate: an
     * instance that has just come up has not yet failed to observe anything,
     * and refusing on that basis would make every machine unusable at start-up
     * until a first reading happened to arrive.
     */
    estimator->ready = false;
    forget_residuals(estimator);
    for (unsigned state = 0u; state < (unsigned)ESTIMATOR_STATE_COUNT; state++) {
        estimator->unobserved_millis[state] = 0u;
        estimator->observed_at[state] = 0.0f;
        estimator->anchored[state] = false;
    }

    if (parameters == NULL || limits == NULL) {
        return false;
    }

    estimator->limits = *limits;

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

    /*
     * Which channels actually fed the estimate this step. A reading the seam
     * could not obtain and a reading it obtained that is absurd take the same
     * path -- the prediction advances, the correction is skipped, no residual
     * is reported -- because in both cases there is nothing here worth
     * correcting toward.
     */
    estimator_observation_set_t usable = 0u;
    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        const hw_reading_t observed = hw_sensor_read((hw_sensor_channel_t)channel);
        if (!observed.valid) {
            continue;
        }
        if (!reading_is_plausible(estimator, (hw_sensor_channel_t)channel, observed.value_milli)) {
            continue;
        }
        if (correct_against(estimator, (hw_sensor_channel_t)channel, observed.value_milli)) {
            usable |= ESTIMATOR_OBSERVATION_BIT(channel);
        }
    }

    /*
     * Then the bookkeeping each reconstructed state needs to say whether it is
     * still supported. It is judged against that state's own dependencies: a
     * channel reaching no state the caller asked for has no business making one
     * unusable, and this is where that is enforced rather than at the call
     * site.
     *
     * The anchor is taken after the corrections rather than before, so the
     * distance a later step measures is travel away from where the last
     * observation actually left the state.
     */
    for (unsigned state = 0u; state < (unsigned)ESTIMATOR_STATE_COUNT; state++) {
        if ((OBSERVATIONS_FOR_RECONSTRUCTION[state] & usable) == 0u) {
            estimator->unobserved_millis[state] =
                saturating_add(estimator->unobserved_millis[state], interval_millis);
            continue;
        }

        estimator->unobserved_millis[state] = 0u;

        float held = 0.0f;
        if (plant_model_state(&estimator->model, STATE_FOR_RECONSTRUCTION[state], &held)) {
            estimator->observed_at[state] = held;
            estimator->anchored[state] = true;
        }
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

    /*
     * How far the reconstruction has travelled from where its observations left
     * it. Refused past the declared distance however much of the window
     * remains, because a prediction that has run away is not made trustworthy
     * by being early. Measured only once an observation has established
     * somewhere to measure from: before that there is no travel to speak of,
     * only a starting value.
     */
    if (estimator->anchored[state]) {
        const float travelled = fabsf(reconstructed - estimator->observed_at[state]);
        if (milli_from_unit(travelled) > estimator->limits.excursion_bound_milli) {
            return false;
        }
    }

    /*
     * And how long ago they stopped. Inside the window the reconstruction runs
     * on prediction and is still answered; past it the loss is no longer brief,
     * and answering would be reporting a state nothing has supported for longer
     * than this machine's description says is safe.
     */
    if (estimator->unobserved_millis[state] > estimator->limits.tolerance_window_ms) {
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
