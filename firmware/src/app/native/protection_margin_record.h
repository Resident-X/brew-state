/*
 * Read the loop's own error-to-margin mapping out of it, and report it.
 *
 * The margin a commanded target has to keep from the hardware protection trip
 * point is computed inside the control path, out of the description that path
 * was brought up against and the error that description declares against its
 * own coefficients. That computation is the subject of a committed record --
 * which corners the declared error implies, what each one costs the trip-point
 * gap, and which of them the margin is therefore the worst of -- and a record
 * taken off a second computation standing beside the loop would go on
 * describing an enumeration the loop was not actually using.
 *
 * So nothing is computed here. Every figure this reports is read back through
 * control.h's own reads, against an instance brought up exactly the way a
 * delivery brings one up, and printed. What builds the corner machines, what
 * combines them and what the margin comes to are all the control path's, and
 * the tool outside consumes what the machine says rather than re-deriving it.
 *
 * The target the mapping is taken at is the highest one the loop will actually
 * take, found by narrowing on the admission path rather than by reading a
 * figure out of the control source: a record asserting against its own
 * arithmetic would agree with itself after the loop stopped agreeing with
 * either. Which bound stops the narrowing is reported beside it, because
 * whether it is the protection margin or some other ceiling that is the tighter
 * one on a given machine is a finding about that machine and not a constant.
 *
 * Nothing here runs a delivery. Whether a delivery lands within its band at a
 * corner is a question about a draw, and the draws this project already has are
 * run by cross_tier_draw.c under a course the caller writes -- so the tool
 * outside runs them there, against the corner machines this mapping names,
 * rather than a second draw being grown here.
 */
#ifndef PROTECTION_MARGIN_RECORD_H
#define PROTECTION_MARGIN_RECORD_H

#include <stddef.h>

#include "delivery_tolerance.h"
#include "estimator_limits.h"
#include "plant_model.h"
#include "pump_trim_declaration.h"
#include "steam_control_declaration.h"

/*
 * Print the mapping, one `HOST ` line per finding, and answer the process exit
 * status the caller should use.
 *
 * `description_text` is the text the coefficients and the budget were both read
 * from. It is taken rather than the record alone because the enumeration is
 * indexed by the structure's own ordering and a reader outside has no way to
 * turn a position back into the coefficient it names; the names are in the text
 * the caller is already holding, and each is put to the plant seam's own
 * position lookup, which is what that lookup exists for.
 *
 * Both loops are read, because both size a margin against the same declared
 * error and against trip points of their own. They are read in one run rather
 * than under two options, because the enumeration a margin is taken over
 * belongs to the description rather than to either loop: two runs would be free
 * to be handed two descriptions, and the record would then put two loops'
 * margins side by side under the shipped machine's name.
 *
 * The steam side reports its own margin and enumeration alongside the ready
 * target its declaration names, so a reader can tell a ready target the margin
 * leaves room for from one the margin is what stops.
 *
 * Returns 0 where the whole mapping was read and printed, and 1 where either
 * control path would not come up, where the description supports no enumeration
 * at all, or where a read of it was refused part way through -- each reported on
 * stderr. A partial mapping is never printed as a whole one.
 */
int protection_margin_record_run(const char *description_text, size_t description_length,
                                 const plant_parameters_t *parameters,
                                 const plant_parameter_budget_t *budget,
                                 const estimator_limits_t *limits,
                                 const delivery_tolerance_t *tolerance,
                                 const pump_trim_declaration_t *pump_trim,
                                 const steam_control_declaration_t *steam);

#endif /* PROTECTION_MARGIN_RECORD_H */
