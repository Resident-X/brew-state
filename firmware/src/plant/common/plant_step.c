/*
 * The part of taking a step that is the same behind every structure.
 *
 * What makes an actuation admissible is a property of the machine's vocabulary
 * rather than of any structure's equations: a level beyond full scale is beyond
 * full scale whatever responds to it, and a non-zero command on a channel a
 * structure does not answer has nowhere to land whatever the structure is. Only
 * which channels are answered varies, and a structure states that.
 *
 * Written once here rather than restated behind each structure, so that a
 * structure added later inherits the refusals rather than reimplementing them,
 * and so that the fault order the seam promises cannot drift between two
 * structures that both claim to honour it.
 */
#include "plant_model.h"

#include <stddef.h>

bool plant_step_admissible(const plant_actuation_t *actuation, uint32_t interval_millis,
                           actuation_channel_set_t answered, plant_step_error_t *error)
{
    if (error == NULL) {
        return false;
    }

    error->fault = PLANT_STEP_OK;
    error->channel = ACTUATION_CHANNEL_COUNT;

    if (actuation == NULL) {
        error->fault = PLANT_STEP_NOT_STEPPABLE;
        return false;
    }
    if (interval_millis == 0u) {
        error->fault = PLANT_STEP_ZERO_INTERVAL;
        return false;
    }

    /*
     * Both channel faults are looked for over the whole set before either is
     * reported, so that which one a command carrying both is refused for is
     * fixed rather than decided by which channel it happens to be on. An
     * over-scale level is reported ahead of an unanswered channel because it is
     * wrong against the vocabulary itself: the level is one no channel of any
     * machine accepts, whereas an unanswered channel is only wrong against this
     * structure.
     */
    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        if (actuation->level_permille[channel] > ACTUATION_FULL_SCALE) {
            error->fault = PLANT_STEP_LEVEL_OVER_SCALE;
            error->channel = (actuation_channel_t)channel;
            return false;
        }
    }

    for (unsigned channel = 0u; channel < (unsigned)ACTUATION_CHANNEL_COUNT; channel++) {
        const bool commanded = actuation->level_permille[channel] != 0u;
        const bool answers = (answered & ACTUATION_CHANNEL_BIT(channel)) != 0u;
        if (commanded && !answers) {
            error->fault = PLANT_STEP_CHANNEL_UNANSWERED;
            error->channel = (actuation_channel_t)channel;
            return false;
        }
    }

    return true;
}

bool plant_model_step(plant_model_t *model, const plant_actuation_t *actuation,
                      uint32_t interval_millis)
{
    plant_step_error_t discarded;

    return plant_model_step_reporting(model, actuation, interval_millis, &discarded);
}
