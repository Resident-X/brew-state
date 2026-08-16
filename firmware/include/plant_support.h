/*
 * How far a plant structure has been verified, and the words for saying so.
 *
 * Cheap to add is not the same as supported. A structure can be written,
 * compiled, linked and run against the seam's own tests without ever having met
 * the machine whose dynamics it claims, and nothing in that sequence tells an
 * adopter which structures have. This header is the one place the distinction
 * is named, so that every structure answers it in the same words and an adopter
 * comparing two of them is comparing like with like.
 *
 * The line is drawn at verification against real hardware and nowhere else. In
 * particular it is not drawn at whose machine a structure describes -- that is
 * a different question, answered by the structure's own documentation, and a
 * status read as answering it would tell an adopter that the author's own
 * structure was checked when it was not. Both questions are worth asking; only
 * one of them is this.
 *
 * The vocabulary is as small as that distinction. Richer gradations -- verified
 * on one machine of the architecture, verified in part, verified against a
 * variant -- describe evidence nobody here has, and a vocabulary carrying terms
 * nothing can populate is an invitation to populate them anyway.
 *
 * Every structure under src/plant/ defines PLANT_STRUCTURE_SUPPORT_STATUS in
 * its own header as one of the values below. A structure claiming
 * PLANT_SUPPORT_HARDWARE_VERIFIED also defines PLANT_STRUCTURE_SUPPORT_EVIDENCE
 * as text identifying what was run and against what, in enough detail to be
 * challenged. check_support_status.py fails the build on a structure that
 * carries no status, on a status outside this vocabulary, and on a verified
 * claim with nothing cited behind it -- the case that would otherwise be set
 * from confidence rather than from a bench.
 */
#ifndef PLANT_SUPPORT_H
#define PLANT_SUPPORT_H

/* How far a structure has been verified against the machine it describes. */
typedef enum {
    /*
     * Nobody has run this structure against hardware of the architecture it
     * describes. Its equations may be right; nothing has established that, and
     * whoever runs it first is the one establishing it.
     */
    PLANT_SUPPORT_UNVERIFIED = 0,
    /*
     * This structure has been run against hardware of its architecture, and the
     * structure cites what was run. Claimable only with that citation.
     */
    PLANT_SUPPORT_HARDWARE_VERIFIED
} plant_support_status_t;

#endif /* PLANT_SUPPORT_H */
