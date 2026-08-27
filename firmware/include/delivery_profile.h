/*
 * A delivery expressed as a course of commanded flow, and the point that flow
 * arrives at.
 *
 * It carries no flow figure of its own and no coefficient of any machine. What
 * a caller states here is a shape -- a rate to move water at, changing over the
 * time since the delivery began, with a stated beginning and end -- and nothing
 * about what that shape draws from any particular machine. Turning a point on
 * the course into a level the pump can be driven at is a question the control
 * path answers through the plant seam, because the figure that answers it
 * belongs to the machine description and this type would otherwise be a second,
 * disagreeing copy of it.
 *
 * It does reach the plant seam for one thing, and this file said it reached it
 * for nothing until a delivery had somewhere to arrive: the vocabulary of
 * points a delivery can be served at. That vocabulary is the machine's rather
 * than any structure's -- the same footing the actuation channels are on -- so
 * naming it here is what stops a second spelling of it growing up beside the
 * seam's. Which heated mass stands behind a named point is still the seam's
 * answer and not this type's: nothing here knows it, and nothing here asks.
 *
 * The course is piecewise-linear points rather than piecewise-constant steps,
 * because piecewise-linear is the more general of the two: a step is a course
 * whose consecutive points repeat a rate, and a ramp -- ramping up to the
 * pressure a puck can take rather than commanding it from a standstill, or
 * tapering a shot's end rather than cutting it -- is not expressible as steps
 * at all without approximating it by very many of them. Nothing about the
 * shape of a real delivery is lost by only supporting the general case.
 *
 * The points live in a fixed-capacity array rather than behind a pointer,
 * because the target this compiles for has no allocator: a profile a caller
 * builds on the stack and hands in by value has to be exactly as large handed
 * in as it is stored, with nothing beyond it reached through a pointer that
 * outlives the caller's frame.
 */
#ifndef DELIVERY_PROFILE_H
#define DELIVERY_PROFILE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/*
 * For plant_delivery_point_t alone -- the machine's vocabulary of places a
 * delivery arrives at. This is the seam's vocabulary header rather than the
 * seam itself: it declares no operation, holds no equation and names no
 * structure, so nothing about which machine a build compiles reaches this file
 * through it.
 */
#include "plant_types.h"

/*
 * The most points a course may carry.
 *
 * Eight is room for a shot with a pre-infusion hold, a ramp up, a hold at
 * pressure and a taper -- four segments, five points -- with a margin left
 * over for a course that needs a second ramp partway through, rather than the
 * bare minimum a straightforward profile would use. It is not sized against
 * any particular recipe on file, because none is: it is sized against the
 * shapes a piecewise-linear course can usefully express before a caller
 * wanting more segments than this is really asking for a different mechanism,
 * such as a course generated at run time, rather than a longer fixed one.
 */
#define DELIVERY_PROFILE_POINT_MAX 8

/*
 * One point on a course: the commanded rate a delivery is to be moving water
 * at, at a stated time since it began.
 */
typedef struct {
    uint32_t at_millis;
    float rate_ml_per_s;
} delivery_profile_point_t;

/*
 * The quantity an end condition is stated in.
 *
 * Enumerated rather than left as a tag on whichever member of the union below
 * is populated, so that a quantity this build cannot evaluate is a value the
 * enumeration carries and construction can name and refuse -- rather than a
 * union interpreted under an assumption nothing states.
 *
 * Delivered volume is named here because it belongs in the vocabulary a
 * delivery can end by -- a cup is finished when it holds enough, not merely
 * when a clock says so -- even though nothing on this machine can evaluate it
 * today. Nothing here integrates a delivered volume: the plant seam reports
 * the rate the pump was commanded to move, not the rate a cup received, and
 * the puck, the pump's flow-versus-pressure characteristic and the mechanical
 * pressure cap all sit between the two unrepresented. Leaving the quantity out
 * of the enumeration until a meter exists would make admitting one later a
 * change to this type and every profile built against it; naming it now and
 * refusing it at construction, in delivery_profile_init below, keeps the
 * later change confined to the evaluator that decides whether a condition
 * naming it can be honoured.
 */
typedef enum {
    DELIVERY_END_ELAPSED_MILLIS = 0,
    DELIVERY_END_DELIVERED_VOLUME_ML,
    DELIVERY_END_QUANTITY_COUNT
} delivery_end_quantity_t;

/*
 * The condition a delivery ends on: the quantity it is stated in, and the
 * value of that quantity at which the delivery is over.
 *
 * The value is a C11 anonymous union rather than a value per quantity carried
 * side by side, because exactly one of them is ever the condition a profile
 * was built with -- the quantity names which -- and a struct carrying both
 * would let a caller populate the one that is not named and have it read back
 * as though it mattered.
 */
typedef struct {
    delivery_end_quantity_t quantity;
    union {
        uint32_t elapsed_millis;
        float delivered_volume_ml;
    };
} delivery_end_condition_t;

/*
 * A delivery: a course of commanded flow, the condition it ends on, and the
 * point it is served at.
 *
 * The end condition is carried inside the profile rather than passed beside
 * it, so that a delivery cannot be commanded without one -- a course with
 * nowhere to stop is not a delivery, and a caller supplying the two
 * separately could supply one and forget the other. The delivery point is
 * carried here for exactly that reason and not a different one: a course with
 * no destination is not a delivery either, and a point passed alongside the
 * profile could be passed to one call and left off the next, with the control
 * path free to decide what the caller meant.
 *
 * `point_count` is how much of `points` is meaningful, on the same reasoning
 * the plant seam's parameter budget carries its own count: the array is sized
 * for the largest course this build admits, not for the one a particular
 * caller built.
 */
typedef struct {
    delivery_profile_point_t points[DELIVERY_PROFILE_POINT_MAX];
    size_t point_count;
    delivery_end_condition_t end;
    plant_delivery_point_t served_at;
} delivery_profile_t;

/*
 * Build a profile from a course and an end condition, validating both.
 *
 * The course is copied in point by point rather than the array being handed
 * in as the profile's own, so that a caller's buffer may be shorter than
 * DELIVERY_PROFILE_POINT_MAX -- which every course but the longest admissible
 * one is -- and so that what ends up in the profile is exactly what
 * validation examined rather than a buffer the caller could go on mutating
 * afterwards.
 *
 * The course is refused unless it has at least two points, the first at zero
 * elapsed, every subsequent point strictly later than the one before, and
 * every rate finite and non-negative. Two points are the fewest that describe
 * a course at all; a first point elsewhere would leave the interval before it
 * with no stated rate; times that do not strictly increase would leave the
 * interpolation below asking which of two points at one instant applies; and
 * a rate that is negative or not a number is not a flow a pump can be
 * commanded at.
 *
 * The end condition is refused unless its quantity is one this build can
 * evaluate while a delivery runs -- see delivery_end_quantity_t -- which
 * today is elapsed time alone. This is checked here, when the profile is
 * built, rather than later when it is run, because a condition naming an
 * unevaluable quantity is not a course that started out fine and then failed:
 * it was never a deliverable profile, and saying so at the moment a caller
 * tried to build one is what stops it reaching a delivery already under way.
 *
 * `served_at` is refused on exactly those terms: a value outside the machine's
 * vocabulary of delivery points is refused here, where the profile is built,
 * rather than being carried into a delivery for something downstream to
 * interpret. PLANT_DELIVERY_POINT_COUNT is the value a caller with nothing to
 * name arrives with, and it is refused like any other value the vocabulary does
 * not carry -- there is no separate spelling for "unset", because a delivery
 * with no destination and a delivery to somewhere this machine has never heard
 * of are the same thing to everybody downstream. No point is chosen for a caller
 * that names none: a course with no destination is not a delivery, and
 * defaulting it to the group would be this file deciding what the caller meant.
 *
 * That is a promise about profiles built through this call rather than about the
 * type. The group is the zero of the vocabulary, so a delivery_profile_t a caller
 * zeroed or aggregate-initialised for itself reads as a group delivery, and
 * nothing downstream examines the point again. The end condition is in exactly
 * that position for exactly that reason -- elapsed time is its enumeration's zero
 * too -- and the answer is the same for both: a profile is built here, or the
 * caller answers for what it assembled.
 *
 * Whether the structure a build compiles actually serves the named point is a
 * different question and is not asked here: it is asked of the plant seam by
 * whoever needs the answer, and a profile is a statement of what was asked for
 * rather than of what one machine can do.
 *
 * Returns false, leaving `profile` unusable, for a null `profile` or `points`,
 * for a `point_count` outside [2, DELIVERY_PROFILE_POINT_MAX], for a course, an
 * end condition or a delivery point that fails the checks above. Nothing is
 * written on a refusal: a caller left with a half-built profile could go on to
 * command a delivery whose end nothing had validated.
 */
bool delivery_profile_init(delivery_profile_t *profile, const delivery_profile_point_t *points,
                           size_t point_count, delivery_end_condition_t end,
                           plant_delivery_point_t served_at);

/*
 * The rate the course commands at a given time since the delivery began.
 *
 * Linear between the two points bracketing `elapsed_millis`, which is what
 * makes a ramp between two commanded rates a course a caller can state as
 * just its endpoints rather than as many close-together steps approximating
 * it. Before the first point's time -- which validation has already fixed at
 * zero -- there is nothing to interpolate from, so the first point's rate
 * applies; at or beyond the course's last point, the course has nothing
 * further to say and the last point's rate is held rather than the rate
 * falling to nothing, so a delivery whose end condition runs slightly past
 * the course's nominal finish does not have the pump cut on the step before
 * the condition is actually met.
 *
 * Returns 0.0f for a null profile or one with fewer than two points, which
 * delivery_profile_init never produces -- so this is a defined answer for a
 * profile nothing built, rather than a promise this function makes about one.
 */
float delivery_profile_rate_ml_per_s(const delivery_profile_t *profile, uint32_t elapsed_millis);

/*
 * Whether the delivery's end condition has been met by the given elapsed time.
 *
 * Evaluated against the quantity the condition names -- today, always elapsed
 * time, since delivery_profile_init refuses every other quantity a profile
 * could otherwise carry -- rather than assuming which quantity applies, so
 * that the evaluator is the one place a later quantity's admission changes
 * once construction is taught to accept it.
 *
 * A quantity the enumeration carries but this build cannot evaluate -- reached
 * only by a caller that assembles a profile directly rather than through
 * delivery_profile_init, which refuses every quantity but elapsed time -- is
 * read as ended rather than as not yet ended. Elsewhere in this file a
 * quantity that cannot be established defaults toward stillness, but stillness
 * for a stop condition is the delivery being over, not the delivery running
 * on: the alternative is a pump driven from the course indefinitely, which is
 * the failure a stated end condition exists to prevent.
 *
 * Returns false for a null profile, which is the same answer as "not yet
 * ended" and is safe for the same reason: a caller with no profile has
 * nothing running for the condition to end. That is a different case from an
 * unevaluable condition above: there is no course to stop rather than a course
 * whose stopping point cannot be read.
 */
bool delivery_profile_ended(const delivery_profile_t *profile, uint32_t elapsed_millis);

/*
 * The rate the drawn-load term reads for the step at elapsed_millis, a lead
 * ahead of it, without reading past the delivery's own end.
 *
 * A single future instant is not what the lead is owed: elapsed_millis plus
 * lead_millis names when the read lands, but everything the course does
 * between elapsed_millis and that landing is water this step's duty answers
 * for, and a rising or falling course says something different at each end
 * of that stretch. Averaging the course across the whole stretch is what a
 * point taken only at its far edge cannot do -- on a course holding one rate
 * the two agree, and only a course that changes across the stretch tells
 * them apart.
 *
 * The stretch is cut short at the delivery's own end rather than read past
 * it: elapsed_millis is always before the end while a delivery is running,
 * so the far edge is the nearer of where the lead would land and where the
 * course stops, never past the end even when the lead would otherwise land
 * there. A quantity this build cannot evaluate -- reached only by a profile
 * assembled without delivery_profile_init -- is read the same direction
 * delivery_profile_ended reads it: as ended already, which cuts the stretch
 * to nothing and answers with the rate the present instant alone states.
 *
 * Returns 0.0f for a null profile, on the same terms delivery_profile_ended
 * does: a caller with no profile has no course to read ahead of.
 */
float delivery_profile_read_ahead_rate_ml_per_s(const delivery_profile_t *profile,
                                                uint32_t elapsed_millis, uint32_t lead_millis);

#endif /* DELIVERY_PROFILE_H */
