/*
 * The host tier's steam loop, run across a commanded draw, reporting what the
 * plant model underneath it did at every control interval.
 *
 * A draw here is a course of demand: how fast steam is leaving the machine over
 * each interval, which is what an operator's hand on the wand decides and
 * nothing inside the machine does. The wand's microswitch follows from the same
 * course rather than being stated beside it -- see steam_draw_t below for why a
 * course able to state the two separately would be able to state a draw nobody
 * opened the wand for.
 *
 * It is a separate entry point from the brew draw beside it rather than a mode
 * of it, because the two are not the same loop asked a different question. They
 * drive different channels, read different channels, are held to different
 * declarations, and switch controlled variable on different events. What they
 * do share -- the simulated hardware seam, the plant model, and the names the
 * model's quantities are reported under -- they share by both being linked into
 * the same host artefact, which is why neither needs an executable of its own.
 *
 * It is deliberately not called a cross-tier draw. The brew draw carries that
 * name because there is a second tier closing the same loop through modelled
 * peripherals for it to be put beside; nothing closes the steam loop on the
 * emulated artefact today, so a run of this one is a run and not a comparison,
 * and naming it after a comparison it is not half of would be a name that
 * promises a second answer nobody produces. What this exists for is asking the
 * same steam loop the same draw against different machines -- which is what a
 * sensitivity sweep over the description's own declared errors is.
 *
 * Nothing here decides whether what came back is acceptable. What runs the draw
 * and what judges it are deliberately not the same thing, on the same terms the
 * brew draw states for itself.
 */
#ifndef STEAM_DRAW_H
#define STEAM_DRAW_H

#include <stdint.h>

#include "estimator_limits.h"
#include "plant_model.h"
#include "steam_control_declaration.h"

/*
 * How a steam draw is commanded.
 *
 * No converter full scale is carried here, unlike the brew draw's own record,
 * and the absence is deliberate rather than an omission. That draw models a
 * converter because the loop it is compared against reads its sensors through
 * one, and two loops reporting through different instruments would be two
 * experiments; this draw is compared against no other loop, so a full scale
 * written here would be a fact about a board nobody has selected, invented for
 * the sake of symmetry and then quietly relied on. The readings this run stands
 * up are the machine's own quantities in the thousandths the hardware seam
 * reports them in -- which is what the suite that already closes this loop
 * against a truth plant does, for the same reason.
 */
typedef struct {
    /*
     * The temperature the steam block is started at, in degrees Celsius.
     *
     * Commanded rather than left at whatever the model comes up in, because a
     * steam block coming up from a cold room spends some three quarters of a
     * minute of simulated time reaching the state this loop holds, and every
     * interval of that is one where the element sits at its ceiling and what
     * the loop reads changes nothing it commands. A draw run from there would
     * be mostly a warm-up, and a warm-up is not what the steam side's declared
     * band holds anything to: that band judges the steam coming out of a block
     * already at its ready state. So the run starts where the machine is meant
     * to be standing when somebody turns the wand, and the caller says where
     * that is rather than this file assuming it -- the ready state is a figure
     * the design declares, and a second copy of it here would be free to drift
     * from the one the loop is actually holding to.
     */
    float initial_steam_c;

    /*
     * The interval, in milliseconds, the simulated clock advances by before
     * each control interval and the machine is then advanced by, one entry per
     * interval. The steam law measures what has elapsed from its own previous
     * step through the seam's clock rather than assuming a cadence, so a course
     * that means to put the loop through an uneven one can, and a course of one
     * repeated figure is simply the even case of the same statement.
     */
    const uint32_t *interval_millis;

    /*
     * The rate steam is leaving the machine during each interval, in
     * thousandths of a millilitre of water turned to vapour per second, one
     * entry per interval.
     *
     * The wand's microswitch is not carried beside it. It reports that the wand
     * is turned and nothing about how much is being asked for, and the two are
     * halves of one mechanical act: the valve the operator opens is what both
     * closes the contact and lets the steam out. A record able to state them
     * separately would be able to state a draw nobody opened the wand for, and
     * a turned wand passing nothing -- neither of which is a machine, and both
     * of which a loop reading the contact would answer as though they were. So
     * an interval asking for a rate is an interval the contact reports made,
     * and an interval asking for nothing is one it reports open.
     *
     * A course rather than a held rate, for the reason the brew draw's own
     * course is one: a draw is a shape. The block is held at its ready state,
     * the wand is opened for as long as a jug takes, and it is shut again --
     * and what the loop is judged on is what came out during the middle of
     * those three, which cannot be asked of a run that never left it.
     */
    const uint32_t *demand_milli_ml_per_s;

    uint32_t interval_count;
} steam_draw_t;

/*
 * Run the draw and print what the plant model reported, one line per interval.
 *
 * Returns zero when the draw ran to its end, and non-zero when the course
 * states no interval, the loop could not be brought up, the machine could not
 * be put into the state the draw begins from, or a step was refused -- a
 * partial trajectory is not a shorter answer, it is no answer, and a caller
 * must not read one as evidence. That includes a structure which keeps no steam
 * temperature to start the machine at: a draw of a steam side an architecture
 * does not have is refused rather than run against whatever state that
 * structure happened to come up in.
 */
int steam_draw_run(const plant_parameters_t *parameters,
                   const estimator_limits_t *limits,
                   const steam_control_declaration_t *declaration,
                   const steam_draw_t *draw);

#endif /* STEAM_DRAW_H */
