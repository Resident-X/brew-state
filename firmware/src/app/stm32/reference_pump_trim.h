/*
 * The pump trim declaration this artefact carries.
 *
 * The host tier opens the declaration it is exercised against, because it runs
 * on something with a filesystem. The machine has none, so the bytes travel
 * compiled into the artefact and this is how the entry point reaches them.
 *
 * The array is defined by a file the build generates from the declaration
 * itself, so there is no copy of the gains in the source tree to fall out of
 * step with the declaration everything else reads. That matters more here than
 * for the machine-describing files beside it: gains written into the source
 * are exactly the duplicate the declaration exists to prevent, because they
 * would go on reading as declared while the software trimmed the pump against
 * the other pair. Nothing here says what the bytes mean: they are a
 * declaration in the language the pump trim loader accepts, and that loader is
 * what turns them into a record.
 *
 * It travels beside the parameter description, the limits declaration and the
 * tolerance declaration, and is unlike all three of them: those say what this
 * machine is, what its sensors could report, and what the drink demands, and
 * this says how hard DEC-CORRECTION-KEEPS-THE-ACCOUNT's trim leans on a rate
 * gap -- a control-tuning policy, on the same footing the steam side's own
 * declaration already is, and not a fact about this machine or this drink at
 * all. It is carried anyway, because the control path cannot be brought up
 * without it and there is nowhere on the machine to read it from.
 */
#ifndef REFERENCE_PUMP_TRIM_H
#define REFERENCE_PUMP_TRIM_H

#include <stddef.h>

/* Not terminated, and not to be treated as a string: it is the file's bytes. */
extern const char reference_pump_trim[];

extern const size_t reference_pump_trim_length;

#endif /* REFERENCE_PUMP_TRIM_H */
