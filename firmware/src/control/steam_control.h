/*
 * The steam control law.
 *
 * It holds the steam side at a ready state while nothing is being drawn,
 * holds the delivered character inside a declared band for the whole of a
 * draw, and carries the machine back to ready afterwards without anybody
 * asking it to.
 *
 * What it drives to changes with what is happening. While no draw is under
 * way the controlled variable is the block's own measured temperature, held
 * at a declared ready target: with the wand shut, the path's pressure is a
 * direct function of that temperature, so holding one holds the other, and
 * the temperature channel is the one whose reading does not depend on an
 * instrument nobody has fitted yet. The instant the wand's microswitch
 * reports a draw, the controlled variable becomes measured pressure, because
 * a draw is precisely what parts the two -- and pressure is what the milk in
 * the jug is sensitive to.
 *
 * The steam wand is a manual, purely mechanical valve. Nothing in this
 * machine's actuation list places a solenoid in that path to block it, so
 * preventing a draw before the steam side can sustain one cannot mean
 * intercepting the valve: it has to mean nothing else feeds a draw that starts
 * too early. Withholding the feed pump below a declared ready pressure is that
 * policy, and it stands in front of everything else here -- feed commanded by
 * the band-holding law below still reaches the machine as nothing while the
 * path sits below that threshold.
 *
 * On a draw beginning, the heater leads and the feed lags. Duty goes to the
 * actuator's ceiling immediately and feed is held at nothing for a declared
 * margin-building interval, because steam made before the block has thermal
 * margin to give is the wet, degrading start this loop exists to avoid. Once
 * feed engages it rises to a declared sustainable rate over a declared
 * interval rather than stepping to it, and once settled it is never commanded
 * past that rate however hard the wand is opened -- which is what makes
 * quantity yield before quality here. Nothing else was available to make yield
 * that way: the microswitch reports that the wand is turned and nothing about
 * how much is being asked for, so no law here could follow demand if it wanted
 * to.
 *
 * On a draw ending, feed is cut on that same step and the ready-holding
 * behaviour resumes from wherever the draw left the machine. Recovery is not a
 * mechanism of its own: once the draw stops costing the block anything, there
 * is nothing recovery needs to do that holding ready does not already do, and
 * a second control path for it would be two mechanisms maintained for one
 * behaviour.
 *
 * Every figure this law rests on -- the ready target, the band, both
 * intervals, the sustainable rate and every gain -- is carried in as a
 * declaration rather than compiled in. See steam_control_declaration.h.
 *
 * Every translation unit under src/control reaches hardware only through
 * hw_interface.h, includes no vendor header, and is compiled byte-identically
 * into both the host and the target build, on the same terms control.h states
 * for itself.
 */
#ifndef STEAM_CONTROL_H
#define STEAM_CONTROL_H

#include <stdbool.h>
#include <stdint.h>

#include "estimator_limits.h"
#include "protection_margin.h"
#include "steam_control_declaration.h"

/* Why a step drove the steam channels the way it did, or did not drive them. */
typedef enum {
    /* The step ran and drove both channels from a trustworthy reading. */
    STEAM_CONTROL_STEP_ACTUATED = 0,
    /*
     * No trustworthy reading was available for the variable this step needed
     * -- nothing is fitted, a sample failed, or the value sat outside the
     * declared plausible span -- so the step acted on what it last trusted,
     * or on nothing where it has never trusted anything. This is not a fault:
     * a machine between readings is not a machine this law has fresh evidence
     * about, and saying so rather than folding it into an ordinary step is
     * what lets a caller tell the two apart.
     */
    STEAM_CONTROL_STEP_SENSOR_INVALID,
    /* The interface rejected a drive command; that channel is at whatever it was. */
    STEAM_CONTROL_STEP_OUTPUT_REFUSED
} steam_control_step_result_t;

/*
 * Which quantity the loop is presently driving to.
 *
 * Projected rather than left implicit because the switch between the two is a
 * property of the law worth being able to observe on the step it happens, and
 * because it is not visible in the duty on that step: the margin-building
 * interval pins the element at its ceiling whichever variable is in force, so
 * a caller watching only what was driven cannot tell a loop that switched from
 * one that did not until that interval has elapsed.
 *
 * That the duty is the same across the switch is a consequence of the pinning
 * and not of the two variables agreeing. They do not agree here: the ready
 * target is a temperature whose rested pressure is the readiness threshold,
 * and the draw-time target is the middle of a band declared deliberately above
 * that threshold -- so at the instant a draw begins the temperature error is
 * nothing while the pressure error is the whole distance from ready up into
 * the band. Climbing that distance before any steam is made out of the block
 * is exactly what the margin-building interval is for.
 */
typedef enum {
    STEAM_CONTROL_VARIABLE_TEMPERATURE = 0,
    STEAM_CONTROL_VARIABLE_PRESSURE
} steam_control_variable_t;

/*
 * An instance of the loop: the records it was brought up with and what it has
 * established since, held by value for the reason control_state_t's own
 * members are -- no allocator exists to point at a caller's copy instead.
 *
 * The last trusted reading of each channel is kept rather than only the
 * present one, because a reading outside physically plausible bounds is to be
 * rejected rather than acted on, and rejecting one means going on from what
 * was last believed rather than from nothing. A channel nothing has ever been
 * trusted on has no such value, which is a different condition from a stale
 * one and is carried separately.
 */
typedef struct {
    bool configured;
    estimator_limits_t limits;
    steam_control_declaration_t declaration;

    /* Where the loop's own clock was when it last ran, and whether it ever has. */
    bool started;
    uint32_t last_step_millis;

    /* Whether a draw was under way at the end of the previous step. */
    bool drawing;
    /* How long the present draw has been under way, in milliseconds. */
    uint32_t draw_elapsed_millis;

    /* Accumulated intent, in permille of heater scale. */
    float integral_permille;

    bool pressure_trusted;
    int32_t trusted_pressure_milli_bar;
    bool temperature_trusted;
    int32_t trusted_temperature_milli_c;

    /* What the previous step actually got onto each channel. */
    uint16_t heater_permille;
    uint16_t feed_permille;

    /*
     * The description this instance was brought up against and what that
     * description says its own figures may be wrong by, held by value on the
     * same terms every other record here is. They are kept rather than read and
     * discarded so that the margin a caller asks about is taken off the same
     * description the loop was admitted against, rather than off whatever the
     * caller happens to be holding when it asks.
     */
    plant_parameters_t parameters;
    plant_parameter_budget_t budget;
} steam_control_state_t;

/*
 * Put the state into its pre-run condition and command both steam channels
 * off, so that a build which initialises but never steps leaves the steam side
 * neither heated nor fed.
 *
 * The limits record is what this loop will believe a reading to be, and the
 * declaration record is every figure it acts on -- carried in rather than
 * reached by a path of their own, on the same terms control_init is handed its
 * own records, so a change to either is a change to a declaration rather than
 * to this file.
 *
 * The description and its budget arrive here for a third reason, and it is not
 * that this loop drives from a model -- it does not, and nothing here steps
 * one. It is that the ready target the declaration names is a commanded
 * temperature, and the steam block carries hardware protection of its own; how
 * far below that protection a target has to sit is sized from what the
 * description says its own figures may be wrong by. A loop handed a target and
 * no statement of how wrong its model may be would be commanding against a
 * margin nobody can check -- see protection_margin.h, and
 * STEAM_CONTROL_PROTECTION_TRIP_C in steam_control.c for the trip point.
 *
 * Returns false, leaving the outputs commanded off but the instance refusing
 * every subsequent step, when the interface refuses either off command, when
 * any record is null, or when the declared ready target does not leave the
 * widened margin between itself and that trip point: a loop that cannot obtain
 * the figures it acts on, or the bounds a reading is judged by, must not drive
 * a heater on a whim it invented for itself -- and one asked to hold a block at
 * a temperature the declared model error could carry into its own protection
 * must not start either.
 */
bool steam_control_init(steam_control_state_t *state, const estimator_limits_t *limits,
                        const steam_control_declaration_t *declaration,
                        const plant_parameters_t *parameters,
                        const plant_parameter_budget_t *budget);

/*
 * The margin this instance requires between the ready target it was brought up
 * with and the steam side's protection trip point, and the enumeration that
 * margin came out of.
 *
 * A read rather than a figure a caller works out for itself, on the same terms
 * control_protection_margin is one: the margin the loop was admitted against is
 * sized from the description it was handed, and a caller computing its own
 * would be holding a machine to a figure this loop never used.
 *
 * Returns false, writing nothing, for a null state or destination, for an
 * instance this loop cannot vouch for, or where the description it holds will
 * not support a corner enumeration at all.
 */
bool steam_control_protection_margin(const steam_control_state_t *state,
                                     protection_margin_t *margin);

/*
 * One corner of the enumeration that margin came out of, by its position in
 * that enumeration, on exactly the terms control_protection_margin_corner
 * reads the coffee side's own: the corners are what the figure above is the
 * worst of, and a record of the mapping from declared error to margin is a
 * record of them. Read through this rather than recomputed by a caller, so a
 * record and the margin it explains come off one enumeration.
 *
 * Returns false, writing nothing, on the same terms the figure above does, and
 * additionally for a position at or past the end of the enumeration.
 */
bool steam_control_protection_margin_corner(const steam_control_state_t *state, size_t which,
                                            protection_margin_corner_t *corner);

/*
 * Advance the loop by one step: read the wand's microswitch and both steam
 * channels, and drive the heater and the feed pump for the interval that has
 * just elapsed.
 *
 * The interval is measured from this instance's own last step through the
 * seam's monotonic clock rather than assumed, on the same terms control_step
 * advances its estimator by what actually elapsed: what an integral
 * accumulates over an interval that did not pass is an answer to a question
 * nobody asked. The first step of an instance has no predecessor to measure
 * from and so accumulates nothing.
 *
 * A null state, or one that failed initialisation, is treated as a
 * sensor-invalid step rather than dereferenced, on the same terms
 * control_step treats a null state: there is no declaration to read and no
 * record of what the channels were last commanded to, so nothing is driven and
 * the caller is told why rather than having a channel touched on a state this
 * function cannot vouch for.
 */
steam_control_step_result_t steam_control_step(steam_control_state_t *state);

/*
 * Which quantity the loop drove to on its last step. False, writing nothing,
 * for a null state or one that failed initialisation -- an instance that never
 * ran is not driving to anything, and answering with the temperature phase
 * would say it was holding ready.
 */
bool steam_control_variable(const steam_control_state_t *state, steam_control_variable_t *variable);

/*
 * Whether the loop presently has a draw to serve, as the wand's microswitch
 * last reported it. False, writing nothing, on a state this loop cannot vouch
 * for, on the same terms as above.
 */
bool steam_control_drawing(const steam_control_state_t *state, bool *drawing);

#endif /* STEAM_CONTROL_H */
