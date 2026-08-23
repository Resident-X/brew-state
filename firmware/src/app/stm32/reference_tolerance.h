/*
 * The tolerance declaration this artefact carries.
 *
 * The host tier opens the declaration it is exercised against, because it runs
 * on something with a filesystem. The machine has none, so the bytes travel
 * compiled into the artefact and this is how the entry point reaches them.
 *
 * The array is defined by a file the build generates from the declaration
 * itself, so there is no copy of the band in the source tree to fall out of
 * step with the declaration everything else reads. That matters more here than
 * for the two files beside it: a band written into the source is exactly the
 * duplicate the declaration exists to prevent, because it would go on reading
 * as declared while the software held deliveries to the other one. Nothing here
 * says what the bytes mean: they are a declaration in the language the delivery
 * tolerance loader accepts, and that loader is what turns them into a record.
 *
 * It travels beside the parameter description and the limits declaration and is
 * unlike both. Those two say what this machine is and what its sensors could
 * report; this says how far from the temperature it was asked for a delivery
 * may sit, which is a property of the drink and reads the same whatever the
 * water was heated in. It is carried anyway, because the control path cannot be
 * brought up without it and there is nowhere on the machine to read it from.
 */
#ifndef REFERENCE_TOLERANCE_H
#define REFERENCE_TOLERANCE_H

#include <stddef.h>

/* Not terminated, and not to be treated as a string: it is the file's bytes. */
extern const char reference_tolerance[];

extern const size_t reference_tolerance_length;

#endif /* REFERENCE_TOLERANCE_H */
