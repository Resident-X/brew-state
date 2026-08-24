/*
 * Bring-up entry point for the STM32 HAL-backed hardware implementation.
 *
 * The control logic never includes this header. It exists because the target
 * peripherals have to be brought up before the seam's operations mean
 * anything, and that bring-up is the implementation's job rather than the
 * interface's -- hw_interface.h covers the operations the control logic
 * invokes, not the sequence that runs before it.
 */
#ifndef HW_STM32_H
#define HW_STM32_H

#include <stdbool.h>

/*
 * Bring up the clocks, port pins, converter and timer the implementation uses.
 * Returns false if any peripheral refuses initialisation, in which case the
 * seam's operations will report untrustworthy readings and refuse drive commands
 * rather than act on an uninitialised peripheral.
 */
bool hw_stm32_init(void);

#endif /* HW_STM32_H */
