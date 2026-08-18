/*
 * Target entry point.
 *
 * It brings the peripherals up through the implementation's own bring-up call,
 * takes the parameter description the artefact carries and turns it into a
 * parameter record, and then runs the same control-logic entry path the host
 * build runs. The control logic it calls is compiled from the same sources,
 * unchanged: the only difference between this build and the host build is
 * which implementation of the seam is linked behind it.
 *
 * The description is read through the plant seam's own loader rather than
 * through a reader written for the target. A second parser accepts a slightly
 * different language sooner or later -- a whitespace rule, an annotation
 * quietly skipped -- and then the machine is running numbers the host tier
 * never saw, out of a file both claim to read. One parser cannot disagree with
 * itself.
 */
#include "control.h"
#include "hw_stm32.h"
#include "plant_model.h"
#include "reference_description.h"

int main(void)
{
    control_state_t state;
    plant_parameters_t parameters;
    plant_parameter_error_t description_fault;

    if (!hw_stm32_init()) {
        /*
         * Nothing can be driven safely without the peripherals the seam needs,
         * so stop here rather than run the control path against uninitialised
         * hardware.
         */
        for (;;) {
        }
    }

    if (!plant_parameters_load(reference_description, reference_description_length, &parameters,
                               &description_fault)) {
        /*
         * The description this artefact carries is not one the loader accepts,
         * so there is no model of this machine. Stop rather than continue on
         * whatever a partly-filled record happens to hold: a machine running
         * against coefficients nobody supplied is one whose predictions mean
         * nothing, and it has no symptom that distinguishes it from a machine
         * whose model is merely wrong. What the machine should do about being
         * left without a model, beyond not proceeding, is a fault-response
         * concern answered elsewhere.
         */
        for (;;) {
        }
    }

    (void)control_init(&state);

    for (;;) {
        (void)control_step(&state);
    }
}
