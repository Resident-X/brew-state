/*
 * The parameter description this artefact carries.
 *
 * The host tier opens the description it is exercised against, because it runs
 * on something with a filesystem. The machine has none, so the bytes travel
 * compiled into the artefact and this is how the entry point reaches them.
 *
 * The array is defined by a file the build generates from the description
 * itself, so there is no copy of those numbers in the source tree to fall out
 * of step with the description everything else reads. Nothing here says what
 * the bytes mean: they are a description in the language the plant seam's
 * loader accepts, and that loader is what turns them into coefficients.
 */
#ifndef REFERENCE_DESCRIPTION_H
#define REFERENCE_DESCRIPTION_H

#include <stddef.h>

/* Not terminated, and not to be treated as a string: it is the file's bytes. */
extern const char reference_description[];

extern const size_t reference_description_length;

#endif /* REFERENCE_DESCRIPTION_H */
