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

/* Sensor channels the control logic can read. */
typedef enum {
    HW_SENSOR_BREW_TEMPERATURE = 0,
    HW_SENSOR_STEAM_TEMPERATURE,
    HW_SENSOR_BREW_PRESSURE,
    HW_SENSOR_STEAM_PRESSURE,
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
 * A sensor reading in thousandths of the channel's unit -- millidegrees Celsius
 * for a temperature channel, millibar for a pressure channel. `valid` is false
 * when the implementation could not obtain a trustworthy sample; `value_milli`
 * is then meaningless and the control logic must not use it.
 */
typedef struct {
    bool valid;
    int32_t value_milli;
} hw_reading_t;

/*
 * Sample a sensor channel. An out-of-range channel yields an invalid reading
 * rather than undefined behaviour.
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
