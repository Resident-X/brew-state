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
 * other line is `name = value`, optionally followed by the error the design
 * assumes for that value -- the marker plant_budget.h declares and a fraction
 * of the value -- and then by the origin of that value -- the marker, a kind
 * from the vocabulary plant_origin.h declares, and an account of where the
 * figure came from. The order of the two is fixed, because the account of an
 * origin is free text and runs to the end of the line. A line that is only a
 * statement the description makes about itself carries the origin marker and
 * that statement alone.
 *
 * Returns false and leaves no usable record when a line cannot be parsed, when
 * a name is not one this structure has, when a name is given twice, when a
 * value lies outside the range the structure declares for it, or when a
 * coefficient the structure requires is absent. No value is assumed for a
 * coefficient that is missing or rejected. `error` reports which coefficient
 * was at fault and why; it may not be null.
 *
 * An annotation that is present and inadmissible is refused on those same
 * terms rather than passed over as though it were a comment. Whether a value
 * carries an annotation at all is not asked here: a description that claims
 * nothing about a real machine has nothing to account for, and which
 * descriptions those are is settled where they live rather than by the loader.
 */
bool plant_parameters_load(const char *text, size_t length,
                           plant_parameters_t *parameters,
                           plant_parameter_error_t *error);

/*
 * Read the error the design assumes for each value, from the same description.
 *
 * The same text, read on the same terms and refused on the same terms: a
 * description this accepts is one plant_parameters_load accepts and the other
 * way round, because it is the one parse with something different kept from it.
 * What is kept here is the assumed error against each value -- the annotation
 * plant_budget.h declares -- rather than the coefficients themselves, which the
 * caller has the loader above for.
 *
 * It is a second operation rather than another argument to the loader because
 * the two answer different callers. Everything that runs the model wants the
 * coefficients; only work reasoning about how wrong the model may be wants the
 * budget, and making every consumer supply somewhere to put a record it will
 * never read would put the uncertainty work's vocabulary in front of all of
 * them.
 *
 * Returns false and leaves no usable record when the description is refused,
 * for any of the reasons plant_parameters_load refuses one. `error` reports
 * which coefficient was at fault and why; it may not be null.
 *
 * A description carrying no assumed error for a value is not refused here. It
 * loads, and that value reads back as having no error declared -- which is a
 * different answer from an error of zero. See plant_parameter_budget_for.
 */
bool plant_parameter_budget_load(const char *text, size_t length,
                                 plant_parameter_budget_t *budget,
                                 plant_parameter_error_t *error);

/*
 * The error the design assumes for one coefficient, by the name the description
 * calls it by.
 *
 * By name rather than by index, because the order a structure declares its
 * coefficients in is that structure's own business, and a consumer that had to
 * know it would be reaching around this seam to find it out. The name is text
 * the consumer already has -- it is what the description says -- so asking with
 * it names no structure.
 *
 * Returns false and writes nothing when an argument is null, when the name is
 * not one this structure's parameter table declares, or when the description
 * carried no assumed error for it. The last of those is deliberately not
 * answered with zero: a caller sizing a margin has to be able to tell "the
 * description says this coefficient is exact" from "the description says
 * nothing about this coefficient", and the two demand opposite responses.
 */
bool plant_parameter_budget_for(const plant_parameter_budget_t *budget,
                                const char *name, float *assumed_error);

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
 * Advance the instance by `interval_millis` under the given actuation and
 * steam demand, and report why if it is refused.
 *
 * `steam_demand_ml_per_s` is the rate steam is being drawn from the machine --
 * set by the operator's wand, not by the control law, and carried as a step
 * argument rather than a channel of the actuation record because nothing
 * commands it. It defaults to zero, and a step taken with it at zero changes
 * no existing behaviour: no relation this seam's structures compute yet reads
 * it. A caller with no demand to report passes zero.
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
 * actuations and demand from the same initial state, reproduces the same
 * trajectory.
 */
bool plant_model_step_reporting(plant_model_t *model, const plant_actuation_t *actuation,
                                float steam_demand_ml_per_s, uint32_t interval_millis,
                                plant_step_error_t *error);

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
                      float steam_demand_ml_per_s, uint32_t interval_millis);

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
 * null, when the instance was never initialised, or when the quantity is not
 * one of the enumerated ones. Every structure answers every quantity -- they are
 * the machine's rather than any structure's -- so there is no refusal here for a
 * quantity a structure does not have. plant_model_state below has one, because
 * states are the other way round.
 */
bool plant_model_quantity(const plant_model_t *model, plant_quantity_t quantity,
                          float *value);

/*
 * Read one state the structure this build compiles integrates, in the unit that
 * state is named in.
 *
 * A separate operation from plant_model_quantity because the two ask different
 * things. A quantity is what the machine has, and every structure answers all
 * of them; a state is what a structure carries to produce those quantities, and
 * which states it carries follows its architecture. A consumer that needs the
 * second -- work reconstructing a state no sensor reports, or a test checking
 * such a reconstruction against the truth the model holds -- has no way to ask
 * for it through the quantities, and reaching around this seam into a
 * structure's fields is what the plant encapsulation check refuses.
 *
 * Returns false and writes nothing when the instance or the destination is
 * null, when the instance was never initialised, when the state is not one of
 * the enumerated ones, or when it is enumerated but this structure does not
 * keep it. The last of those is a refusal and not a reading of zero: a caller
 * has to be able to tell "this architecture has no such state" from "this state
 * is currently nothing", and the two demand opposite responses -- the first
 * says the caller is asking the wrong structure, the second is an ordinary
 * value. A refused read leaves the destination as the caller left it.
 *
 * Which states a structure keeps is fixed by the structure and does not vary
 * over an instance's life, so a caller may establish it once at initialisation
 * rather than checking every read.
 */
bool plant_model_state(const plant_model_t *model, plant_state_t state, float *value);

/*
 * Write one state the structure this build compiles integrates, in the unit
 * that state is named in.
 *
 * The counterpart of plant_model_state, and here for the same reason. Work that
 * reconstructs a state no sensor reports has to correct its own instance of the
 * model toward what the machine reports, and correcting means putting a value
 * back. Reaching into a structure's fields to do it is what the plant
 * encapsulation check refuses, so without a write through the seam the
 * correction has no admissible expression at all.
 *
 * Returns false and changes nothing when the instance is null, when it was
 * never initialised, when the state is not one of the enumerated ones, or when
 * it is enumerated but this structure does not keep it -- the same refusals the
 * read answers with, for the same reasons. A structure that does not keep a
 * state has nowhere to put the value, and quietly dropping it would leave a
 * caller believing a correction it made was taken.
 *
 * What is written is not checked for plausibility. The seam has no view on
 * which values a machine could be in, and a structure that rejected the ones it
 * disagreed with would be deciding for the consumer whether its reconstruction
 * is any good, which is the consumer's question.
 */
bool plant_model_set_state(plant_model_t *model, plant_state_t state, float value);

#endif /* PLANT_MODEL_H */
