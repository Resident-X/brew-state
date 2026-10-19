/*
 * The steam control law.
 *
 * It holds the steam side at a ready state while nothing is being drawn,
 * holds the delivered character inside a declared band for the whole of a
 * draw, and carries the machine back to ready afterwards without anybody
 * asking it to.
 *
 * The steam block is a flash generator: it holds a little liquid and no vapour
 * reservoir, and with the wand open the pressure in the path is set by how fast
 * steam is being made through the tube, valve and tip rather than by how hot
 * the casting is. So the two actuators split the two things a draw is judged
 * by. The feed pump holds pressure, because the steam made is what is fed. The
 * heater holds dryness -- a declared superheat of the steam at the block's
 * modelled outlet -- because whether the water fed is turned wholly to steam,
 * and how far past saturation it leaves, is the balance of heater power against
 * what that water costs to heat and boil. No loop takes pressure error into the
 * heater: a casting driven to raise pressure would be driving the one variable
 * the heater no longer sets.
 *
 * While no draw is under way the controlled variable is the block's own
 * measured temperature, held at a declared ready target: with the wand shut and
 * liquid held, the path's pressure is saturation of that temperature, so holding
 * one holds the other. The instant the wand's microswitch reports a draw, the
 * controlled variable becomes measured pressure, held by the feed.
 *
 * The heater's superheat is not measured -- no outlet or tip sensor is fitted --
 * so the law forms its own estimate of it from the casting temperature, the
 * measured pressure and the feed it commands, through the relations the plant
 * description it was brought up against declares: the saturation relation and
 * the casting-to-outlet relation, the latter taken at the end of its declared
 * error that leaves the least superheat. It reads nothing from any model
 * instance; the description is the law's own view of the machine.
 *
 * The steam wand is a manual, purely mechanical valve. Nothing in this
 * machine's actuation list places a solenoid in that path to block it, so
 * preventing a draw before the steam side can sustain one cannot mean
 * intercepting the valve: it has to mean nothing else feeds a draw that starts
 * too early. The verdict is taken once, from the pressure the shut block holds
 * at the moment the wand opens, and held until it shuts: a draw opened at or
 * above the declared ready pressure is fed from its first step, and one opened
 * below it is starved for the whole draw. It cannot be judged on the
 * instantaneous pressure once the wand is open, because that pressure is made by
 * the feed: a draw fed nothing reads nothing, and a gate asking it would starve
 * every draw.
 *
 * A fed draw starts at a declared draw-start feed, whose steam puts the pressure
 * at the band through the orifice law from the first step. Above that level the
 * feed may rise no faster than a declared limit, and it is never commanded past
 * a declared ceiling however the pressure stands -- which is what makes quantity
 * yield before quality. There is no reading of how much steam is being asked
 * for, so when the ceiling binds the loop gives up pressure rather than feed.
 *
 * On a draw ending, feed is cut on that same step and the ready-holding
 * behaviour resumes from wherever the draw left the machine, with the intent it
 * held before the draw. Recovery is not a mechanism of its own.
 *
 * Every figure this law rests on -- the ready target, the band, the feed
 * levels and rise limit, the superheat setpoint and every gain -- is carried in
 * as a declaration rather than compiled in. See steam_control_declaration.h.
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
 * Which quantity the loop is presently driving to: the block's temperature while
 * idle, and the path's pressure, through the feed, while a draw is open.
 *
 * Projected rather than left implicit because the switch between the two is a
 * property of the law worth being able to observe on the step it happens.
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
    /*
     * The gate's verdict for the present draw: whether the shut block's trusted
     * pressure was at or above the ready threshold on the step the wand opened.
     * Taken once per draw and held until the wand shuts.
     */
    bool feeding;

    /*
     * Accumulated intent of each loop, kept apart so that one loop's intent is
     * never spent by another: the ready-holding heater loop's, in permille of
     * heater scale, which is frozen while a draw is fed and resumes afterwards;
     * the superheat loop's, in the same unit, which a new draw starts from
     * nothing; and the pressure loop's, in permille of feed scale, likewise.
     */
    float integral_permille;
    float superheat_integral_permille;
    float feed_integral_permille;

    /*
     * The feed level the pressure loop last issued, before it was rounded to the
     * actuator's resolution: the rise limit is applied to this, so a limit
     * smaller than one permille a step still rises rather than rounding away.
     */
    float feed_level_permille;

    /* The law's own estimate of the outlet superheat on its last fed step. */
    bool superheat_estimated;
    float superheat_estimate_k;

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
 * Whether the description and error budget are ones this loop's initialisation
 * takes on: the believed description is one the plant admits, the budget
 * declares an error against the coefficient the loop's superheat estimate
 * reads, and the protection margin is established over every declared corner.
 * Initialisation refuses what this refuses; a caller that has been refused asks
 * it which parameter to tell its builder about. `refusal`, when not null, is
 * written and on a refusal names the parameter and the fault.
 */
bool steam_control_description_established(const steam_control_declaration_t *declaration,
                                           const plant_parameters_t *parameters,
                                           const plant_parameter_budget_t *budget,
                                           plant_parameter_error_t *refusal);

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

/*
 * The law's own estimate of the superheat at the block's modelled outlet, in
 * kelvin, on its last step: the figure the heater held to the declared setpoint.
 * It is a modelled figure that no sensor confirms, and it is the least the
 * description's declared error on the casting-to-outlet relation admits.
 *
 * False, writing nothing, for a null argument, for a state this loop cannot
 * vouch for, and on any step that fed no draw -- no steam was made, so there is
 * no outlet steam to have a superheat.
 */
bool steam_control_outlet_superheat(const steam_control_state_t *state, float *superheat_k);

#endif /* STEAM_CONTROL_H */
