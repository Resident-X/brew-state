/*
 * Building and reading a delivery profile.
 *
 * Nothing here reaches the plant model or the hardware seam. Turning a
 * commanded rate into a drive level is the control path's question, asked
 * through the plant seam at the moment a step is taken, and asking which heated
 * mass stands behind the point a delivery names is the control path's question
 * asked of the same seam. This file only ever answers questions about the
 * course itself, and about whether the point it names is one the machine's
 * vocabulary carries at all.
 *
 * It sits under src/control rather than beside the delivery loaders in
 * src/delivery, because it is not a loader: it reaches nothing from the
 * standard library but memcpy and memset, never errno, and control_step calls
 * into it on every step to interpolate the course and to decide whether the
 * delivery has ended. Both of those decide what the pump is driven at, which
 * makes them the control law rather than something adjacent to it, and the
 * check run as part of the build that holds src/control to being
 * byte-identical between the host and the target build only ever reaches
 * translation units it finds there. Left in src/delivery, this file's own
 * interpolation and its own end-condition evaluator would be exactly the kind
 * of control logic that guarantee exists to cover, and would go on reading as
 * covered by it without actually being reached.
 */
#include "delivery_profile.h"

#include <string.h>

/*
 * Whether a value is a rate a pump could be commanded at: neither a
 * not-a-number, nor infinite, nor negative.
 *
 * Written out on the same terms control.c's is_a_temperature is, and for the
 * same reason: this file is compiled into every build the control logic is,
 * including the target, and a library predicate that expands differently on
 * the host and on the target would make a translation unit required to be
 * byte-identical across both not actually be.
 */
static bool is_a_rate(float rate_ml_per_s)
{
    return (rate_ml_per_s == rate_ml_per_s) && ((rate_ml_per_s - rate_ml_per_s) == 0.0f) &&
          (rate_ml_per_s >= 0.0f);
}

static bool course_is_admissible(const delivery_profile_point_t *points, size_t point_count)
{
    if (points == NULL || point_count < 2u || point_count > DELIVERY_PROFILE_POINT_MAX) {
        return false;
    }
    if (points[0].at_millis != 0u) {
        return false;
    }

    for (size_t index = 0u; index < point_count; index++) {
        if (!is_a_rate(points[index].rate_ml_per_s)) {
            return false;
        }
        if (index > 0u && points[index].at_millis <= points[index - 1u].at_millis) {
            return false;
        }
    }

    return true;
}

static bool end_condition_is_admissible(delivery_end_condition_t end)
{
    /*
     * Elapsed time is the one quantity this build can evaluate while a
     * delivery runs -- see the account in delivery_profile.h -- so it is the
     * only member of the enumeration admitted here. A quantity outside the
     * enumeration entirely is refused by the same comparison: it fails to
     * equal the one value this build accepts.
     */
    return end.quantity == DELIVERY_END_ELAPSED_MILLIS;
}

/*
 * Whether the point named is one the machine's vocabulary carries.
 *
 * Written as a comparison against the count, on the same terms the end
 * condition above is written as a comparison against the one quantity this
 * build evaluates: PLANT_DELIVERY_POINT_COUNT and anything past it are values
 * the vocabulary does not carry, and a caller that named nothing arrives here
 * with exactly that. Whether the linked structure serves the point is not
 * asked -- see the account in delivery_profile.h -- because a profile records
 * what a caller asked for and not what one machine happens to be able to do.
 */
static bool delivery_point_is_admissible(plant_delivery_point_t served_at)
{
    return served_at < PLANT_DELIVERY_POINT_COUNT;
}

bool delivery_profile_init(delivery_profile_t *profile, const delivery_profile_point_t *points,
                           size_t point_count, delivery_end_condition_t end,
                           plant_delivery_point_t served_at)
{
    if (profile == NULL) {
        return false;
    }
    if (!course_is_admissible(points, point_count) || !end_condition_is_admissible(end) ||
        !delivery_point_is_admissible(served_at)) {
        return false;
    }

    /*
     * Assembled aside and copied out only once everything above has been
     * found admissible, so a refusal leaves the caller's profile exactly as
     * it was rather than with a course written in and no end condition to
     * stop it -- the same reasoning the parameter and tolerance loaders
     * beside this one apply to their own records.
     */
    delivery_profile_t staging;
    memset(&staging, 0, sizeof(staging));
    memcpy(staging.points, points, point_count * sizeof(*points));
    staging.point_count = point_count;
    staging.end = end;
    staging.served_at = served_at;

    *profile = staging;
    return true;
}

float delivery_profile_rate_ml_per_s(const delivery_profile_t *profile, uint32_t elapsed_millis)
{
    if (profile == NULL || profile->point_count < 2u) {
        return 0.0f;
    }

    if (elapsed_millis <= profile->points[0].at_millis) {
        return profile->points[0].rate_ml_per_s;
    }

    const delivery_profile_point_t *last = &profile->points[profile->point_count - 1u];
    if (elapsed_millis >= last->at_millis) {
        return last->rate_ml_per_s;
    }

    for (size_t index = 1u; index < profile->point_count; index++) {
        const delivery_profile_point_t *before = &profile->points[index - 1u];
        const delivery_profile_point_t *after = &profile->points[index];

        if (elapsed_millis <= after->at_millis) {
            const float span = (float)(after->at_millis - before->at_millis);
            const float into = (float)(elapsed_millis - before->at_millis);
            const float fraction = into / span;

            return before->rate_ml_per_s +
                  fraction * (after->rate_ml_per_s - before->rate_ml_per_s);
        }
    }

    /*
     * Unreachable given the bracketing checks above: every elapsed time is
     * either before the first point, at or beyond the last, or strictly
     * between two consecutive ones, and the loop returns on the first point
     * it is not beyond. Held here as the honest answer for an instant
     * validation guarantees the loop already accounted for, rather than
     * leaving the function without a return on every path.
     */
    return last->rate_ml_per_s;
}

bool delivery_profile_ended(const delivery_profile_t *profile, uint32_t elapsed_millis)
{
    if (profile == NULL) {
        /*
         * A caller with no profile has nothing running for a condition to end.
         * That is a different question from the unevaluable one below: there
         * is no course to stop here, rather than a course whose stopping
         * point cannot be read -- and the two are answered in opposite
         * directions for exactly that reason.
         */
        return false;
    }

    switch (profile->end.quantity) {
    case DELIVERY_END_ELAPSED_MILLIS:
        return elapsed_millis >= profile->end.elapsed_millis;
    case DELIVERY_END_DELIVERED_VOLUME_ML:
    case DELIVERY_END_QUANTITY_COUNT:
    default:
        /*
         * delivery_profile_init refuses every quantity but elapsed time, so a
         * profile built through it never reaches this branch. It is written
         * rather than omitted because a profile is a plain struct a caller
         * could in principle assemble without the constructor.
         *
         * This is not the same direction of error the rest of the file takes.
         * A rate this file cannot establish defaults to 0.0f, toward
         * stillness, because a rate wrong in that direction commands too
         * little water rather than water nobody asked for. A stop condition
         * is the opposite shape: the failure mode of "not yet ended" is the
         * pump going on being driven from the course indefinitely, which is
         * not stillness at all. Toward stillness here therefore means ended
         * rather than running, and returning true is what sends this default
         * into the branch above that commands the pump to zero.
         */
        return true;
    }
}
