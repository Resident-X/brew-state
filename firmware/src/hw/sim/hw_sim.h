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

/*
 * Return every channel to its power-on condition: every sensor channel absent,
 * no drive, clock at zero. Absent rather than failed, because a harness that
 * has stood nothing up has established that nothing is there rather than that
 * a sample was tried.
 */
void hw_sim_reset(void);

/*
 * Stand a reading up on a channel, under the status a caller reading it should
 * see. Every status the seam declares can be injected, so a suite can put a
 * channel into each of the conditions a machine can present it in -- nothing
 * fitted, a sample that failed, or a trustworthy figure -- rather than only the
 * last of them and a single catch-all for the rest. The value is kept whatever
 * the status, and reaches a reader only under HW_READING_VALID. An out-of-range
 * channel is ignored.
 */
void hw_sim_set_sensor(hw_sensor_channel_t channel, hw_reading_status_t status,
                       int32_t value_milli);

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
