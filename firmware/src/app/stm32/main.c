/*
 * Target entry point.
 *
 * It brings the peripherals up through the implementation's own bring-up call
 * and then runs the same control-logic entry path the host build runs. The
 * control logic it calls is compiled from the same sources, unchanged: the
 * only difference between this build and the host build is which
 * implementation of the seam is linked behind it.
 */
#include "control.h"
#include "hw_stm32.h"

int main(void)
{
    control_state_t state;

    if (!hw_stm32_init()) {
        /*
         * Nothing can be driven safely without the peripherals the seam needs,
         * so stop here rather than run the control path against uninitialised
         * hardware.
         */
        for (;;) {
        }
    }

    (void)control_init(&state);

    for (;;) {
        (void)control_step(&state);
    }
}
