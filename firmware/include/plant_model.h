/*
 * The plant-model seam.
 *
 * This header is the only vocabulary a consumer of the plant model has for
 * reaching it. It declares free functions rather than a struct of function
 * pointers or a class with virtual methods, so that every call through the
 * seam resolves to a direct call at link time and no structure is bound while
 * the program runs.
 *
 * Nothing here names a structure. The state and parameter types the signatures
 * below refer to -- plant_model_t and plant_parameters_t -- are supplied by
 * plant_structure.h, which whichever structure the build compiles puts on the
 * include path. A translation unit that includes this header therefore depends
 * on the seam rather than on the equations behind it, and this header carries
 * no equation of its own: there is not one function definition in it.
 *
 * Exactly one structure is linked into any given build, selected by which
 * structure directory under src/plant/ the build compiles. A build naming none,
 * or more than one, stops rather than choosing.
 */
#ifndef PLANT_MODEL_H
#define PLANT_MODEL_H

#include "plant_types.h"

/*
 * Supplied by the structure the build compiles. It defines plant_parameters_t
 * and plant_model_t, and declares the parameter table this seam populates.
 */
#include "plant_structure.h"

/*
 * Populate a parameter record from a parameter description.
 *
 * The description is `length` bytes of text and need not be terminated. Blank
 * lines and lines whose first non-blank character is '#' are ignored; every
 * other line is `name = value`.
 *
 * Returns false and leaves no usable record when a line cannot be parsed, when
 * a name is not one this structure has, when a name is given twice, when a
 * value lies outside the range the structure declares for it, or when a
 * coefficient the structure requires is absent. No value is assumed for a
 * coefficient that is missing or rejected. `error` reports which coefficient
 * was at fault and why; it may not be null.
 */
bool plant_parameters_load(const char *text, size_t length,
                           plant_parameters_t *parameters,
                           plant_parameter_error_t *error);

/*
 * Bring a model instance to its initial state under the given parameters.
 *
 * The instance keeps its own copy of the record, so the caller's may go out of
 * scope afterwards. Returns false and leaves the instance unusable when either
 * argument is null.
 */
bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters);

/*
 * The actuation channels the structure this build compiles answers.
 *
 * The actuation vocabulary is the machine's, so a structure of a given
 * architecture will not answer every channel in it. Which ones it does answer
 * is something the structure states, and this is where a consumer reads that
 * statement -- through the seam, like everything else about the model, rather
 * than by including a structure's own header or reading a comment.
 */
actuation_channel_set_t plant_structure_actuation_channels(void);

/*
 * Advance the instance by `interval_millis` under the given actuation, and
 * report why if it is refused.
 *
 * Returns false and changes nothing when an argument is null, when the instance
 * was never initialised, when the interval is zero, when a channel exceeds
 * ACTUATION_FULL_SCALE, or when a channel the structure does not answer is
 * commanded a non-zero level -- a caller must treat a refusal as "the model did
 * not move", not as "the model advanced with the actuation clamped or the
 * unanswered channel dropped".
 *
 * A zero level on a channel the structure does not answer is not a refusal:
 * commanding nothing of an actuator that is not there is not an error, and
 * treating it as one would leave a caller that zeroes every channel it does not
 * use unable to step at all.
 *
 * `error` reports which fault applied and, where the fault has one, which
 * channel; it may not be null. It is set to PLANT_STEP_OK on a step that ran.
 * Where more than one fault applies, which is reported is fixed -- see
 * plant_step_fault_t.
 *
 * The same instance, advanced over the same intervals under the same
 * actuations from the same initial state, reproduces the same trajectory.
 */
bool plant_model_step_reporting(plant_model_t *model, const plant_actuation_t *actuation,
                                uint32_t interval_millis, plant_step_error_t *error);

/*
 * Advance the instance, for a caller that only needs to know whether it moved.
 *
 * Identical to plant_model_step_reporting in what it accepts, what it refuses
 * and what it leaves behind -- it is that operation with the record discarded,
 * and is written once rather than by each structure. A caller that wants to act
 * on a refusal, or to log which channel had nowhere to land, calls the
 * reporting form.
 */
bool plant_model_step(plant_model_t *model, const plant_actuation_t *actuation,
                      uint32_t interval_millis);

/*
 * Whether an actuation and an interval are ones a structure answering
 * `answered` can be stepped under, and what is wrong with them if not.
 *
 * The admissible ones are the same for every structure, differing only in which
 * channels it answers, so this is written once and each structure applies it
 * rather than restating it. A structure still answers for its own instance --
 * whether it is null, and whether it was initialised -- because nothing here
 * can see it. `error` may not be null.
 */
bool plant_step_admissible(const plant_actuation_t *actuation, uint32_t interval_millis,
                           actuation_channel_set_t answered, plant_step_error_t *error);

/*
 * Read one quantity the model exposes, in the unit that quantity is named in.
 *
 * Returns false and writes nothing when the instance or the destination is
 * null, or when the quantity is not one of the enumerated ones.
 */
bool plant_model_quantity(const plant_model_t *model, plant_quantity_t quantity,
                          float *value);

#endif /* PLANT_MODEL_H */
