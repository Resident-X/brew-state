/*
 * The state-estimation seam.
 *
 * A control law acts on the state of the machine, and the machine does not
 * report its state -- it reports what a sensor can be placed against. The two
 * sets overlap without coinciding, and this header is the vocabulary for the
 * difference: what a consumer asks the estimator for is a state, named in the
 * estimator's own words rather than the plant seam's, because which states a
 * control law works from is a claim about the control law and not about any
 * structure.
 *
 * Nothing here names a plant structure or a coefficient of one. The parameter
 * record and the actuation below are the plant seam's neutral types, so a
 * translation unit including this header depends on this seam and that one
 * rather than on the equations behind either. It declares free functions for
 * the same reason plant_model.h does: every call resolves at link time and
 * nothing is bound while the program runs.
 */
#ifndef ESTIMATOR_H
#define ESTIMATOR_H

#include <stdbool.h>
#include <stdint.h>

#include "estimator_limits.h"
#include "hw_interface.h"
#include "plant_model.h"

/*
 * The states a consumer of this seam can ask for.
 *
 * Deliberately not the plant seam's state vocabulary. That one enumerates what
 * a structure keeps, which is an answer about the model; this one enumerates
 * what a control law works from, which is an answer about the machine's
 * behaviour. Reusing the first for the second would make the control law's
 * vocabulary shift whenever a structure changed what it integrates.
 */
typedef enum {
    /*
     * The temperature of the water on its way to the group. No sensor channel
     * reports it -- a sensor can be placed on the mass being heated far more
     * readily than in the stream leaving it -- and it is what the extraction
     * actually happens at.
     */
    ESTIMATOR_STATE_BREW_TEMPERATURE_C = 0,
    ESTIMATOR_STATE_COUNT
} estimator_state_t;

/*
 * A set of the seam's sensor channels, as bits.
 *
 * One machine word rather than an array of flags because the sets below are
 * compared and combined a step at a time, and because a set that fits in a
 * register costs the target nothing to carry.
 */
typedef uint32_t estimator_observation_set_t;

#define ESTIMATOR_OBSERVATION_BIT(channel)                                                         \
    ((estimator_observation_set_t)1u << (unsigned)(channel))

/*
 * Which observations each reconstructed state rests on.
 *
 * Declared here rather than worked out at the call site, and declared per state
 * rather than per channel, because that is where the consequence lands. This
 * seam corrects four plant states from four channels and answers one state to
 * its caller, so a rule keyed on channels would let a dead steam-pressure
 * sensor refuse a brew temperature that never depended on it -- and stop the
 * machine for a reason that has nothing to do with what it was asked to
 * control.
 *
 * The state this seam answers is the water on its way to the group, and no
 * channel observes it. What reaches it is the temperature of the mass being
 * heated, which the brew temperature channel corrects and which the water
 * follows; nothing downstream of that mass feeds back into it. So the set below
 * names the one channel a gap in which actually starves this state, and a gap
 * in any other leaves it answering.
 *
 * A state added here without its dependencies stated would default to depending
 * on nothing, and would then go on being reported usable through a total loss
 * of observation. The build is made to check the table is as wide as the
 * vocabulary for that reason.
 */
#define ESTIMATOR_STATE_OBSERVATIONS                                                               \
    {                                                                                              \
        [ESTIMATOR_STATE_BREW_TEMPERATURE_C] =                                                     \
            ESTIMATOR_OBSERVATION_BIT(HW_SENSOR_BREW_TEMPERATURE),                                 \
    }

/*
 * An estimator instance.
 *
 * The members are here because a consumer holds one by value rather than
 * allocating it, which is what keeps the target build free of an allocator.
 * They are not the interface: reach them through the operations below.
 */
typedef struct {
    bool ready;
    plant_model_t model;
    estimator_limits_t limits;
    bool residual_fresh[HW_SENSOR_CHANNEL_COUNT];
    int32_t residual_milli[HW_SENSOR_CHANNEL_COUNT];
    /*
     * Per reconstructed state: how long since a usable observation among the
     * ones it depends on, and where it stood when they stopped arriving. The
     * anchor is what the excursion bound is measured from, and it is only
     * meaningful once an observation has established it -- which is what the
     * flag beside it records, rather than a sentinel value a real temperature
     * could take.
     */
    uint32_t unobserved_millis[ESTIMATOR_STATE_COUNT];
    float observed_at[ESTIMATOR_STATE_COUNT];
    bool anchored[ESTIMATOR_STATE_COUNT];
} estimator_t;

/*
 * Bring an instance to its initial state under a parameter record.
 *
 * The limits record travels alongside the parameter record because the two are
 * one description of one machine seen from two sides -- what it is, and what a
 * reading off it may plausibly be. An instance brought up from one without the
 * other would either believe every reading or believe none.
 *
 * Returns false, leaving the instance unusable, when the instance or either
 * record is null, when the record does not initialise a model, or when the
 * structure this build compiled does not keep a state this seam reconstructs.
 * The last is the interesting one: a structure whose architecture has nowhere
 * for such a state to live cannot have it reconstructed, and running on what
 * it does keep would hand the caller a substitute under the name of what it
 * asked for. Which states a structure keeps is fixed by the structure, so this is
 * settled once here rather than on every read.
 *
 * An instance that refused to initialise answers nothing: every read below
 * returns false until an initialisation succeeds. That holds however early the
 * refusal came, including for an instance handed no record at all -- the caller
 * still holds the instance afterwards, and it is put into its refusing state
 * before its arguments are looked at rather than left as whatever the memory it
 * was declared in contained.
 */
bool estimator_init(estimator_t *estimator, const plant_parameters_t *parameters,
                    const estimator_limits_t *limits);

/*
 * Advance the instance by one interval under the actuation that was commanded,
 * then correct it toward what the machine reports.
 *
 * The actuation is what the caller commanded over the interval just elapsed,
 * not what it is about to command: the model is being advanced over time that
 * has already passed. Readings are taken through hw_interface.h for every
 * channel it exposes, and each one that can be trusted is corrected against;
 * one that cannot is left out of the correction rather than treated as zero,
 * and reports no residual for that step.
 *
 * Returns false, having corrected nothing and cleared every residual, when the
 * instance is null or was never initialised, or when the seam refuses the step.
 */
bool estimator_step(estimator_t *estimator, const plant_actuation_t *actuation,
                    uint32_t interval_millis);

/*
 * Read one reconstructed state, in the unit that state is named in.
 *
 * Returns false and writes nothing when the instance or the destination is
 * null, when the instance is not initialised, when the state is not one of the
 * enumerated ones, when what the model holds is not a number, when the state
 * has travelled further from where its observations left it than the declared
 * excursion bound admits, or when those observations stopped longer ago than
 * the declared tolerance window.
 *
 * The last two are the estimator declining to answer for a reconstruction it
 * can no longer support, and they are separate refusals rather than one. The
 * distance bounds the estimate: a prediction that has run away is not made
 * trustworthy by being early, so it is refused however much of the window
 * remains. The window bounds the machine's exposure, because a well-behaved
 * model sitting still while the real mass runs away travels no distance at all
 * and would otherwise be believed indefinitely. A refusal is
 * not a reading of zero: an uninitialised estimator has reconstructed nothing,
 * and answering with a default would be indistinguishable from a machine that
 * happens to be cold. The last refusal is there for the same reason -- a value
 * that is not a number is not a temperature, and a consumer comparing against
 * it would have the answer decided by which way round the comparison was
 * written rather than by the machine.
 */
bool estimator_state(const estimator_t *estimator, estimator_state_t state, float *value);

/*
 * Read the difference between what the model predicted for one channel and what
 * that channel observed on the most recent step, in the unit the channel is
 * read in.
 *
 * This is the same difference the correction consumed, kept from that step
 * rather than computed again for the report. A residual computed twice is two
 * answers to one question, and the two stop agreeing the first time either is
 * touched.
 *
 * Returns false and writes nothing when the instance or the destination is
 * null, when the channel is not one of the enumerated ones, or when the most
 * recent step did not correct against that channel -- because its reading could
 * not be trusted, because the step was refused, or because no step has run yet.
 * That refusal is distinct from a residual of zero, which says the prediction
 * and the observation agreed.
 */
bool estimator_residual(const estimator_t *estimator, hw_sensor_channel_t channel,
                        int32_t *residual_milli);

#endif /* ESTIMATOR_H */
