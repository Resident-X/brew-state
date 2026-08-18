/*
 * The vocabulary the design classifies its own behaviours in, against a model
 * that is wrong by an amount nobody has measured.
 *
 * The plant model will be wrong. The useful question is not by how much but
 * what still holds when it is, and that question has two answers rather than
 * one. Some behaviours must hold however wrong the model turns out to be:
 * refusing what the machine cannot deliver, reaching a state that is safe when
 * something has gone wrong, staying inside the supply the machine is fed from.
 * Others are permitted to get worse as the model gets worse -- how tightly a
 * temperature is held, how quickly it is reached -- because they are quality of
 * service rather than the conditions under which service is offered at all.
 *
 * Without the split, a failed identification threatens every property at once
 * and nobody can say which ones still stand. With it, a fit that lands badly
 * has a known blast radius: the second class degrades and is expected to, and
 * the first class is where a failure is a defect rather than a disappointment.
 *
 * The classification is declared as data rather than written as prose because
 * its consumer is a later verification and not a reader. A paragraph saying
 * which properties must survive cannot be checked for exhaustiveness, cannot be
 * diffed when a behaviour is added, and cannot fail a build when a behaviour
 * arrives carrying no class at all -- and an unclassified behaviour is exactly
 * the failure this exists to prevent, because it is the one that reads as
 * covered to everybody who looks at it.
 *
 * The kinds are declared here, once, and the artefact that names the behaviours
 * and the check that inspects it both read them from this file. A kind is then
 * added by a deliberate edit here rather than by someone typing a new word into
 * the declaration and having it accepted. Two is the whole vocabulary on
 * purpose: a third term -- for a behaviour that mostly holds, or that holds in
 * the cases anyone has thought about -- is a place for an unexamined property
 * to sit, and every property put there would be one nobody has to decide about.
 *
 * The line the vocabulary draws is between what a wrong model is allowed to
 * take away and what it is not, and nothing else. It says nothing about how
 * important a behaviour is, how likely it is to fail, or who is responsible for
 * it: a term for any of those would let two behaviours of different kinds carry
 * the same word, which is the distinction this exists to keep sharp.
 *
 * Nothing here names a plant structure, and nothing here names a control law.
 * The classification is a statement about the machine's behaviour, and it has
 * to outlive both the structure the model is written as and whatever loop is
 * eventually built against it.
 */
#ifndef PLANT_ROBUSTNESS_H
#define PLANT_ROBUSTNESS_H

/*
 * What a wrong model is permitted to do to a declared behaviour.
 *
 * The classes are three rather than two because the machine's guarantees fail
 * in three different ways, and a split that offered only two would have to put
 * two of them in one box. A property that holds whatever the model says, and a
 * property that holds provided the model is within the error the description
 * declares, are not the same promise -- and the difference is exactly what a
 * later verification has to know, because the first is checked by making the
 * model arbitrarily wrong and the second by sweeping the declared range.
 *
 * PLANT_ROBUSTNESS_INVARIANT is the class whose members do not depend on
 * identification having succeeded at all. They hold however wrong the model
 * turns out to be, including wrong by more than the description assumed, and
 * their failure is a machine that is unsafe, damages itself, or quietly does
 * something other than what it was asked for. Nothing is admitted here that
 * needs the error budget to be right, because the budget is itself an estimate
 * and this class is what stands when estimates do not.
 *
 * PLANT_ROBUSTNESS_BOUNDED is the class whose members hold across the whole
 * declared range of model error, and at the far end of it -- which is the end a
 * fit will not warn about, because a fit reports how well it matched the data
 * it was given and not how far the machine sits from it. They are real
 * guarantees rather than aspirations, and they are conditional: a machine that
 * turns out to sit outside the range the description declared has invalidated
 * the condition they were established under, and the honest response is to
 * re-establish them against the measured figures rather than to assume they
 * survived.
 *
 * PLANT_ROBUSTNESS_DEGRADING is the class whose members are allowed to get
 * worse as the model does, with no floor claimed. Declaring one here is not an
 * excuse for it: it is a statement that its failure is a worse cup of coffee
 * rather than an unsafe machine, and that the design is entitled to trade it
 * away to keep the other two classes intact.
 */
typedef enum {
    PLANT_ROBUSTNESS_INVARIANT = 0,
    PLANT_ROBUSTNESS_BOUNDED,
    PLANT_ROBUSTNESS_DEGRADING,
    PLANT_ROBUSTNESS_KIND_COUNT
} plant_robustness_kind_t;

/* The word each class is written as in the declaration. */
#define PLANT_ROBUSTNESS_INVARIANT_WORD "invariant"
#define PLANT_ROBUSTNESS_BOUNDED_WORD "bounded"
#define PLANT_ROBUSTNESS_DEGRADING_WORD "degrading"

/*
 * Every word, in the order the classes are enumerated in, so that a reader of
 * the declaration and a reader of this file cannot disagree about which words
 * are admissible. Anything else against a behaviour is refused rather than
 * ignored: a behaviour classified with a word nobody declared has been
 * classified by its author and by nothing else.
 */
#define PLANT_ROBUSTNESS_KIND_WORDS                                                                \
    {                                                                                              \
        PLANT_ROBUSTNESS_INVARIANT_WORD, PLANT_ROBUSTNESS_BOUNDED_WORD,                            \
            PLANT_ROBUSTNESS_DEGRADING_WORD                                                        \
    }

#endif /* PLANT_ROBUSTNESS_H */
