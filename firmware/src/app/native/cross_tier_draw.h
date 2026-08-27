/*
 * The host tier's closed loop, run across a commanded draw, reporting the plant
 * model's sensed quantities at every control interval.
 *
 * A draw here is a temperature to drive toward and a course of pump levels to
 * draw it at, run at a stated cadence. Both halves are commanded, because a
 * machine asked only for a temperature never moves water: the pump stays off,
 * the brew path's pressure stays where it came up, and the water on its way to
 * the group reaches the block only by conduction -- which leaves the loop
 * driving at full duty for the whole of any draw short enough to emulate, and a
 * loop pinned at full duty is one whose sensed reading changes nothing it does.
 * A comparison drawn across such a run compares two open loops.
 *
 * Declared separately from the exercise beside it because the two ask different
 * things of the same artefact. The exercise walks every path the control logic
 * can take, so the analysis stage has a subject that executes them; this runs
 * one path -- an ordinary draw -- and reports what the machine underneath it
 * did, so the same draw can be put to another tier and the two answers
 * compared.
 *
 * Nothing here decides whether the answers agree. What runs the draw and what
 * judges it are deliberately not the same thing.
 *
 * Beside the sensed quantities each interval carries the temperature of the
 * water on its way to the group, where the structure the build compiled keeps
 * it. That is the temperature an extraction is judged by and the one nothing on
 * the machine reports, so it takes no part in a comparison of two tiers reading
 * the same instruments -- but a run asking what a coefficient's uncertainty
 * costs the drink has to be able to read the drink, and the block's own
 * temperature is not a stand-in for it: how far the two sit apart moves with
 * the draw. On a structure that keeps no such state the field is absent from
 * the line rather than reported as a figure standing for absence.
 */
#ifndef CROSS_TIER_DRAW_H
#define CROSS_TIER_DRAW_H

#include <stdint.h>

#include "delivery_tolerance.h"
#include "estimator_limits.h"
#include "plant_model.h"

/*
 * How a draw is commanded, and how the machine underneath it reports.
 *
 * The converter's full scale is carried here rather than written into the
 * implementation because it is a fact about a board, and this tier has no
 * board. A run comparing this loop against one closed through a real converter
 * has to hold both loops to the same reporting or it is comparing two different
 * experiments -- so the figures come from wherever that converter's own scaling
 * is declared, and are handed in.
 */
typedef struct {
    /* The temperature the draw asks the machine for, in degrees Celsius. */
    float target_c;

    /*
     * The interval, in milliseconds, the simulated clock is advanced by before
     * each control interval, one entry per interval. The control logic advances
     * its estimator by the interval that actually elapsed rather than by the
     * one the loop is meant to run at, so a run that means to reproduce another
     * loop's draw has to reproduce that loop's cadence and not merely its
     * nominal one.
     */
    const uint32_t *interval_millis;

    /*
     * The level the pump is asked for before each control interval, in permille
     * of full scale, one entry per interval.
     *
     * A course rather than a single held level, because what a draw does to the
     * machine is not one thing: water moving is what carries the block's heat to
     * the group and what puts pressure in the brew path, and a level that never
     * changed would leave the pressure relation settled after its first few
     * intervals and never asked another question. It is carried here beside the
     * cadence for the same reason the cadence is carried at all -- the two loops
     * being compared have to be asked for exactly the same thing, and a course
     * either of them worked out for itself is a second answer waiting to
     * disagree.
     */
    const uint16_t *pump_permille;

    uint32_t interval_count;

    /* The count the converter reports at its full scale. */
    uint32_t converter_full_scale_counts;

    /* What that full scale is, in thousandths of the channel's own unit. */
    uint32_t converter_full_scale_milli;
} cross_tier_draw_t;

/*
 * Run the draw and print what the plant model reported, one line per interval.
 *
 * Returns zero when the draw ran to its end, and non-zero when the loop could
 * not be brought up or a step was refused -- a partial trajectory is not a
 * shorter answer, it is no answer, and a caller must not read one as evidence.
 */
int cross_tier_draw_run(const plant_parameters_t *parameters,
                        const estimator_limits_t *limits,
                        const delivery_tolerance_t *tolerance,
                        const cross_tier_draw_t *draw);

#endif /* CROSS_TIER_DRAW_H */
