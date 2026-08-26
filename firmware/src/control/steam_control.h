/*
 * The steam feed-withhold gate.
 *
 * The steam wand is a manual, purely mechanical valve -- nothing in this
 * machine's actuation list places a solenoid in that path to block it, so
 * preventing a draw before the steam side can sustain it cannot mean
 * intercepting the valve. It has to mean nothing else feeds a draw that
 * starts too early. This is that policy: it withholds the steam feed pump,
 * the only thing standing between a draw and getting more steam made for it,
 * for as long as measured steam pressure sits below the declared ready
 * threshold, and hands feed to whatever holds it in band once that threshold
 * is reached. No control law drives either steam channel today; this is the
 * first one to.
 *
 * Every translation unit under src/control reaches hardware only through
 * hw_interface.h, includes no vendor header, and is compiled byte-identically
 * into both the host and the target build, on the same terms control.h
 * states for itself.
 *
 * What this file does not do: it does not drive the steam heater, does not
 * track pressure once feed is enabled, and does not recover the block after
 * a draw. Those belong to the band-holding loop this gate feeds, which reads
 * the same declared threshold as its own ready-holding target.
 */
#ifndef STEAM_CONTROL_H
#define STEAM_CONTROL_H

#include <stdbool.h>

#include "estimator_limits.h"
#include "steam_control_declaration.h"

/* Why a step drove the feed pump channel the way it did, or did not drive it. */
typedef enum {
    /* The step ran and drove the feed pump channel from a trustworthy reading. */
    STEAM_CONTROL_STEP_ACTUATED = 0,
    /*
     * No trustworthy pressure reading was available -- nothing is fitted, a
     * sample failed, or the value sat outside the declared plausible span --
     * so feed was withheld rather than acted on. This is not a fault: a
     * machine between readings is not a machine this gate has evidence is
     * ready, and withholding is the same softer failure the criterion this
     * gate exists for is named after.
     */
    STEAM_CONTROL_STEP_SENSOR_INVALID,
    /* The interface rejected the drive command; the channel is at whatever it was. */
    STEAM_CONTROL_STEP_OUTPUT_REFUSED
} steam_control_step_result_t;

/*
 * An instance of the gate: the record it was brought up with, held by value
 * for the reason control_state_t's own members are -- no allocator exists to
 * point at a caller's copy instead.
 */
typedef struct {
    bool configured;
    estimator_limits_t limits;
    steam_control_declaration_t declaration;
} steam_control_state_t;

/*
 * Put the state into its pre-run condition and command the feed pump channel
 * off, so that a build which initialises but never steps still leaves the
 * steam side unfed.
 *
 * The limits record is what this gate will believe a pressure reading to be,
 * and the declaration record is the threshold it withholds feed below --
 * carried in rather than reached by a path of their own, on the same terms
 * control_init is handed its own records, so a change to either is a change
 * to a declaration rather than to this file.
 *
 * Returns false, leaving the outputs commanded off but the instance refusing
 * every subsequent step, when the interface refuses the off command or when
 * either record is null: a gate that cannot obtain the threshold it acts
 * against, or the bounds a reading is judged by, must not withhold feed on a
 * whim it invented for itself.
 */
bool steam_control_init(steam_control_state_t *state, const estimator_limits_t *limits,
                        const steam_control_declaration_t *declaration);

/*
 * Advance the gate by one step: read measured steam pressure, and drive the
 * feed pump channel at nothing while that reading sits below the declared
 * ready threshold, at the actuator's full scale once it has reached it.
 *
 * The specific rate fed once the threshold is reached is not this gate's
 * question -- it hands sustained tracking to the band-holding loop, which is
 * free to command anything from there. What this file answers is only
 * whether feed is withheld or not.
 *
 * The decision is taken fresh from the current reading on every call rather
 * than carried across steps, because withholding is a function of where the
 * pressure presently sits and not of anything this gate remembers: a step
 * that finds the threshold newly crossed enables feed on that same step, and
 * one that finds the reading has become untrustworthy withholds it on that
 * same step, whatever the step before did.
 *
 * A null state, or one that failed initialisation, is treated as a
 * sensor-invalid step rather than dereferenced, on the same terms
 * control_step treats a null state: there is no declared threshold to read
 * and no record of what the channel was last commanded to, so nothing is
 * driven and the caller is told why rather than having a channel touched on
 * a state this function cannot vouch for.
 */
steam_control_step_result_t steam_control_step(steam_control_state_t *state);

#endif /* STEAM_CONTROL_H */
