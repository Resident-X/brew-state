/*
 * Test and entry-point control surface for the simulated hardware
 * implementation.
 *
 * The control logic never includes this header -- it sees only hw_interface.h.
 * This is what lets a host build stand a sensor reading up, advance the clock
 * and read back what was driven, without the control logic knowing that its
 * hardware is simulated.
 *
 * This is not a plant model. Readings are whatever a caller last set; nothing
 * here relates a drive level to a future temperature. The plant model and its
 * physics are a separate deliverable.
 */
#ifndef HW_SIM_H
#define HW_SIM_H

#include <stdbool.h>
#include <stdint.h>

#include "hw_interface.h"

/* Return every channel to its power-on condition: no valid readings, no drive, clock at zero. */
void hw_sim_reset(void);

/* Stand a reading up on a channel. An out-of-range channel is ignored. */
void hw_sim_set_sensor(hw_sensor_channel_t channel, bool valid, int32_t value_milli);

/* The level last accepted on a channel, or zero for an out-of-range channel. */
uint16_t hw_sim_output(hw_output_channel_t channel);

/* How many times a channel has been driven, including redundant writes of the same level. */
uint32_t hw_sim_output_write_count(hw_output_channel_t channel);

/* Move the simulated monotonic clock forward. It cannot be moved backward. */
void hw_sim_advance_millis(uint32_t delta_millis);

/*
 * Make every subsequent hw_output_set refuse, so a caller can exercise the
 * path where the interface rejects a drive command.
 */
void hw_sim_set_output_refused(bool refused);

#endif /* HW_SIM_H */
