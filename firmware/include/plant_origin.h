/*
 * The vocabulary a parameter description records the origin of a value in.
 *
 * A description carries values, and those values are not all the same kind of
 * fact. Some are read off a document, some are estimated because nothing states
 * them, and later some will be measured on the machine itself. An estimate that
 * cannot be told apart from a measurement is the more dangerous of the two,
 * because it is trusted like the measurement it resembles -- and a description
 * is a mixture from the outset and stays one throughout commissioning, with
 * measured values displacing estimates one at a time while the rest stand.
 *
 * So the kinds are declared here, once, and both the loader that parses a
 * description and the check that inspects one read them from this file. A kind
 * is then added by a deliberate edit here rather than by someone typing a new
 * word into a description and having it accepted.
 *
 * The line the vocabulary draws is between how a figure was arrived at, and
 * nothing else. It says nothing about how good the figure is, how much it is
 * trusted, or who established it: a term for any of those would let two values
 * of different kinds carry the same word, which is the distinction this exists
 * to keep sharp.
 *
 * Nothing here names a plant structure. Every structure's descriptions are read
 * through the same loader, so a structure name reaching this file would reach
 * every one of them.
 */
#ifndef PLANT_ORIGIN_H
#define PLANT_ORIGIN_H

/*
 * How a value in a description was arrived at.
 *
 * PLANT_ORIGIN_DOCUMENT covers a figure read at source and a figure derived
 * from one -- a rating off a circuit diagram, a slope taken from steam tables.
 * What makes it a document origin is that the account names something a reader
 * can go and look at.
 *
 * PLANT_ORIGIN_ESTIMATED covers everything arrived at by judgement: a figure
 * estimated from a comparable machine, from geometry, or from first principles.
 * The three are one kind because the consequence is the same -- nobody has
 * established it for this machine -- and the account is required to say which
 * of them it was.
 *
 * PLANT_ORIGIN_MEASURED is the only kind that claims this machine. It costs a
 * bench measurement, and until the machine has been on the bench no value in
 * any description here carries it.
 */
typedef enum {
    PLANT_ORIGIN_DOCUMENT = 0,
    PLANT_ORIGIN_ESTIMATED,
    PLANT_ORIGIN_MEASURED,
    PLANT_ORIGIN_KIND_COUNT
} plant_origin_kind_t;

/* The word each kind is written as in a description. */
#define PLANT_ORIGIN_DOCUMENT_WORD "document"
#define PLANT_ORIGIN_ESTIMATED_WORD "estimated"
#define PLANT_ORIGIN_MEASURED_WORD "measured"

/*
 * Every word, in the order the kinds are enumerated in, so that a reader of a
 * description and a reader of this file cannot disagree about which words are
 * admissible. Anything else after the marker is refused rather than ignored.
 */
#define PLANT_ORIGIN_KIND_WORDS                                                                    \
    {                                                                                              \
        PLANT_ORIGIN_DOCUMENT_WORD, PLANT_ORIGIN_ESTIMATED_WORD, PLANT_ORIGIN_MEASURED_WORD        \
    }

/*
 * What introduces an origin against a value, and what introduces a statement
 * the description makes about itself. One character serves both because they
 * are the same thing at two scopes: something the description asserts rather
 * than a coefficient it supplies.
 */
#define PLANT_ORIGIN_MARKER '@'

/*
 * The statement that exempts a description from carrying origins at all.
 *
 * A description that asserts nothing about a real machine has nothing an origin
 * could support, and requiring one would only produce a form of words. The
 * exemption follows what a description claims rather than which structure it
 * belongs to: a structure that does describe a machine may still ship
 * descriptions that claim nothing about one, for showing that a linked artefact
 * runs different numbers or for exercising a refusal.
 *
 * It is claimed rather than assumed. A description says this about itself, in
 * the file, or it is required to account for every value it carries.
 */
#define PLANT_ORIGIN_NO_MACHINE_DECLARATION "describes-no-machine"

#endif /* PLANT_ORIGIN_H */
