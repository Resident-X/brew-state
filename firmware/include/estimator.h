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
 * An estimator instance.
 *
 * The members are here because a consumer holds one by value rather than
 * allocating it, which is what keeps the target build free of an allocator.
 * They are not the interface: reach them through the operations below.
 */
typedef struct {
    bool ready;
    plant_model_t model;
    bool residual_fresh[HW_SENSOR_CHANNEL_COUNT];
    int32_t residual_milli[HW_SENSOR_CHANNEL_COUNT];
} estimator_t;

/*
 * Bring an instance to its initial state under a parameter record.
 *
 * Returns false, leaving the instance unusable, when the instance or the record
 * is null, when the record does not initialise a model, or when the structure
 * this build compiled does not keep a state this seam reconstructs. The last is
 * the interesting one: a structure whose architecture has nowhere for such a
 * state to live cannot have it reconstructed, and running on whatever it does
 * keep would hand the caller a substitute under the name of the thing it asked
 * for. Which states a structure keeps is fixed by the structure, so this is
 * settled once here rather than on every read.
 *
 * An instance that refused to initialise answers nothing: every read below
 * returns false until an initialisation succeeds.
 */
bool estimator_init(estimator_t *estimator, const plant_parameters_t *parameters);

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
 * enumerated ones, or when what the model holds is not a number. A refusal is
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
