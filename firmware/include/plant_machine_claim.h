/*
 * Whether a plant structure's equations describe a machine, and the words for
 * saying so.
 *
 * A structure behind this seam is a set of equations and a parameter table. Some
 * of them are an account of how a real espresso machine of some architecture
 * behaves; others exist to give the seam's own checks a second subject to be
 * exercised against, and their arithmetic is arithmetic about nothing. Both
 * kinds compile, link, and pass tests, and nothing in that sequence separates
 * them.
 *
 * The separation matters to anything that draws a conclusion from the model's
 * arithmetic. The mutation sweep is the case that forced this header: it alters
 * every operator and comparison in the swept sources in turn and asks whether a
 * test notices, and the answer is only worth having about equations that mean
 * something. A surviving mutant in a structure describing no machine says
 * nothing about the tests -- there was no behaviour to change -- and a killed
 * one says nothing either, so including such a structure would pad the sweep's
 * denominator with a subject no conclusion can be drawn from.
 *
 * This is deliberately not the same question as how far a structure has been
 * verified, which plant_support.h answers. A structure can describe a real
 * architecture and have met no hardware; that is the ordinary state of a new
 * structure, and it is the state every structure in this tree is in. Conflating
 * the two would mean either that an unverified structure describes no machine --
 * which is false and would drop real equations out of the sweep -- or that a
 * structure describing no machine could be marked verified, which is a claim
 * about hardware that does not exist.
 *
 * The vocabulary is as small as the distinction it draws. A term for "describes
 * a machine in part", or for how closely, would describe a judgement nobody can
 * make at build time and would give an arriving structure somewhere vague to
 * sit.
 *
 * Every structure under src/plant/ defines PLANT_STRUCTURE_MACHINE_CLAIM in its
 * own header as one of the values below. check_machine_claim.py fails the build on
 * a structure that carries no claim and on a claim outside this vocabulary, for
 * the same reason the support status is required: a property that decides what
 * the sweep draws mutants from cannot be one a reader infers from a comment.
 *
 * What no check reaches is whether a structure's claim about itself is true. For
 * the machine-describing case that is the same question as whether its equations
 * are right, which is what verification against hardware settles and what
 * plant_support.h records the answer to.
 */
#ifndef PLANT_MACHINE_CLAIM_H
#define PLANT_MACHINE_CLAIM_H

/* Whether a structure's equations are an account of some real machine. */
typedef enum {
    /*
     * These equations describe no machine. Their arithmetic carries no claim
     * about anything physical, so no conclusion about a machine follows from
     * altering it.
     */
    PLANT_DESCRIBES_NO_MACHINE = 0,
    /*
     * These equations are an account of how a machine of some architecture
     * behaves. Whether they are a correct account is a separate question, asked
     * of hardware and recorded in the structure's support status.
     */
    PLANT_DESCRIBES_A_MACHINE
} plant_machine_claim_t;

#endif /* PLANT_MACHINE_CLAIM_H */
