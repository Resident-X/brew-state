/*
 * The hardware seam.
 *
 * This header is the only vocabulary the control logic has for reaching
 * hardware. It declares free functions rather than a struct of function
 * pointers or a class with virtual methods, so that every call through the
 * seam resolves to a direct call at link time and no implementation is bound
 * while the program runs.
 *
 * Nothing here names a vendor type. There is no HAL handle, no CMSIS register
 * definition and no build-system-injected macro in any signature, so a
 * translation unit that includes this header carries no dependency on the
 * target microcontroller and this header compiles against a freestanding C
 * compiler with no vendor include path present.
 *
 * Exactly one implementation is linked into any given build, selected by which
 * build environment is being built. Peripheral bring-up -- clock configuration,
 * interrupt registration, DMA setup -- is the job of the implementation and of
 * the entry point, not of this interface: these are the operations the control
 * logic itself invokes.
 */
#ifndef HW_INTERFACE_H
#define HW_INTERFACE_H

#include <stdbool.h>
#include <stdint.h>

/*
 * The machine's actuation channels. They are the same channels the plant model
 * responds to, so they are named in one place that neither seam owns rather
 * than enumerated again here.
 */
#include "machine_actuation.h"

/*
 * Sensor channels the control logic can read.
 *
 * The set is what a reading can be taken of, not what a given machine has
 * fitted. A channel no instrument is wired to is still enumerated here and
 * answers -- it answers that nothing is there, which is a different sentence
 * from a sample that was attempted and could not be trusted, and the status
 * below is where that difference is carried. Enumerating only the fitted
 * channels would put that difference in the vocabulary instead, where a
 * consumer could not ask the question at all.
 */
typedef enum {
    HW_SENSOR_BREW_TEMPERATURE = 0,
    HW_SENSOR_STEAM_TEMPERATURE,
    HW_SENSOR_BREW_PRESSURE,
    HW_SENSOR_STEAM_PRESSURE,
    /*
     * The rate water moves through the brew path. It is a channel of this seam
     * rather than a figure taken from the plant model deliberately: the model
     * answers what the pump was commanded to move, and what a meter placed in
     * the path reports is a separate thing that may disagree with it. Reading
     * the commanded figure as though it were the measured one would make that
     * disagreement unobservable, which is the whole reason a meter would be
     * fitted.
     */
    HW_SENSOR_FLOW,
    /*
     * Whether the steam control knob is turned, as the microswitch behind it
     * reports it. It is a channel of this seam beside the analogue ones rather
     * than folded into one of them, because what it answers is a different
     * kind of question -- not how much of a quantity there is, but whether a
     * thing is so -- and a switch smuggled into a continuous channel as two
     * agreed-upon values would be a channel whose consumers each had to know
     * which two.
     *
     * It reports that a draw has been asked for and nothing about its size:
     * the wand is a mechanical valve opened by hand, and the switch closes at
     * some point in the knob's travel that nobody has characterised. A
     * consumer wanting a rate has to get it from somewhere else, and there is
     * nowhere else on this machine.
     */
    HW_SENSOR_STEAM_KNOB,
    HW_SENSOR_CHANNEL_COUNT
} hw_sensor_channel_t;

/*
 * Output channels the control logic can drive: the machine's actuation
 * channels, under the name this seam knows them by. This is another name for
 * the shared set rather than a second copy of it, so a channel added to the
 * machine reaches this seam without anything here being edited.
 */
typedef actuation_channel_t hw_output_channel_t;

/*
 * How far a reading can be trusted.
 *
 * Three answers rather than two, because "no trustworthy sample" covers two
 * conditions a caller can act on differently and a flag cannot tell apart. A
 * channel nothing is fitted to will never report, however long it is waited
 * on, and a channel that sampled and came back untrustworthy may report on the
 * next step. A flag pressed into service for both makes an unfitted instrument
 * indistinguishable from a broken one -- and on a machine where an instrument
 * is optional, that is the difference between a variant built without it and a
 * variant whose wiring has come off.
 *
 * Absent is the zeroth answer so that an implementation which has established
 * nothing about a channel reports the reading it can defend: nothing is there
 * until something says otherwise.
 */
typedef enum {
    HW_READING_ABSENT = 0, /* nothing is fitted to this channel, so none is coming */
    HW_READING_FAILED,     /* a sample was attempted and cannot be trusted */
    HW_READING_VALID       /* a sample was obtained and can be trusted */
} hw_reading_status_t;

/*
 * A sensor reading in thousandths of the channel's unit -- millidegrees Celsius
 * for a temperature channel, millibar for a pressure channel, millilitres per
 * second in thousandths for a flow channel. `value_milli` carries a measurement
 * only when `status` is HW_READING_VALID; under either other status it is
 * meaningless and the control logic must not use it. It is not a reading of
 * zero, and nothing here ever substitutes a commanded figure for a measured
 * one: a channel that reports nothing reports nothing.
 */
typedef struct {
    hw_reading_status_t status;
    int32_t value_milli;
} hw_reading_t;

/*
 * What a channel measuring a thing that is either so or not so reports in
 * `value_milli`.
 *
 * Such a channel carries no continuous quantity, but it is read back through
 * the same reading as every other channel, so it needs a spelling for its two
 * answers rather than a second reading type. Thousandths of the channel's own
 * unit is what this seam already means by `value_milli`, and the unit of a
 * thing that is so is that it is so -- one whole of it, or none.
 *
 * They are the two admissible values and not merely two agreed-upon ones. A
 * discrete channel reporting anything between them has not answered the
 * question it exists to answer: whatever produced it was not the switch, and
 * a consumer reading "mostly so" from a contact that is either made or not has
 * been handed a figure no implementation of this seam is entitled to produce.
 * The distinction is worth keeping separate from HW_READING_VALID, which says
 * a sample was obtained, and from the plausible span a machine declares for
 * the channel, which says what a reading off that machine could be: an
 * implementation can obtain a sample, inside the declared span, that is still
 * not one of the two answers.
 */
#define HW_READING_DISCRETE_CLEAR 0
#define HW_READING_DISCRETE_SET 1000

/*
 * Sample a sensor channel. A channel outside the enumerated set reports
 * HW_READING_ABSENT rather than undefined behaviour: nothing this seam knows of
 * is there to have been sampled.
 */
hw_reading_t hw_sensor_read(hw_sensor_channel_t channel);

/*
 * Drive an output channel at `level_permille` parts per thousand of full scale.
 * Returns false and changes nothing when the channel is out of range, when the
 * level exceeds ACTUATION_FULL_SCALE, or when the implementation cannot drive
 * the channel at all -- a caller must treat a refusal as "the channel is at
 * whatever it was", not as "the channel is off".
 */
bool hw_output_set(hw_output_channel_t channel, uint16_t level_permille);

/*
 * Milliseconds since the implementation started. Monotonic: successive calls
 * never return a smaller value. Wraps at the width of the type, which callers
 * must handle by comparing differences rather than absolute values.
 */
uint32_t hw_monotonic_millis(void);

#endif /* HW_INTERFACE_H */
