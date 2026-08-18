/*
 * The limits declaration this artefact carries.
 *
 * The host tier opens the declaration it is exercised against, because it runs
 * on something with a filesystem. The machine has none, so the bytes travel
 * compiled into the artefact and this is how the entry point reaches them.
 *
 * The array is defined by a file the build generates from the declaration
 * itself, so there is no copy of those bounds in the source tree to fall out of
 * step with the declaration everything else reads. Nothing here says what the
 * bytes mean: they are a declaration in the language the estimator's own limits
 * loader accepts, and that loader is what turns them into a record.
 *
 * It travels beside the parameter description rather than instead of it. The
 * description says what the machine is; this says what a reading taken off it
 * could possibly report, and how long the reconstruction may run without one.
 * An artefact carrying one and not the other would either believe every reading
 * or believe none.
 */
#ifndef REFERENCE_LIMITS_H
#define REFERENCE_LIMITS_H

#include <stddef.h>

/* Not terminated, and not to be treated as a string: it is the file's bytes. */
extern const char reference_limits[];

extern const size_t reference_limits_length;

#endif /* REFERENCE_LIMITS_H */
