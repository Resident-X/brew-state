/*
 * Target entry point.
 *
 * It brings the peripherals up through the implementation's own bring-up call,
 * takes the parameter description the artefact carries and turns it into a
 * parameter record, hands that record to the control-logic entry path so the
 * state estimator behind it reconstructs from the same figures, and then runs
 * the same entry path the host build runs. The control logic it calls is compiled from the same sources,
 * unchanged: the only difference between this build and the host build is
 * which implementation of the seam is linked behind it.
 *
 * The limits declaration the artefact carries travels beside the description
 * and is read the same way. It says what a reading off this machine may
 * plausibly be and how long the reconstruction may run without one, which is a
 * fact about a machine and its sensors rather than about the software, so it
 * belongs to the machine the description names and comes up with it.
 *
 * Both are read through the seam's own loader rather than through a reader
 * written for the target. A second parser accepts a slightly different language
 * sooner or later -- a whitespace rule, an annotation quietly skipped -- and
 * then the machine is running numbers the host tier never saw, out of a file
 * both claim to read. One parser cannot disagree with itself.
 */
#include "control.h"
#include "estimator_limits.h"
#include "hw_stm32.h"
#include "plant_model.h"
#include "reference_description.h"
#include "reference_limits.h"

int main(void)
{
    control_state_t state;
    plant_parameters_t parameters;
    plant_parameter_error_t description_fault;
    estimator_limits_t limits;
    estimator_limits_error_t limits_fault;

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

    if (!estimator_limits_load(reference_limits, reference_limits_length, &limits,
                               &limits_fault)) {
        /*
         * The limits declaration this artefact carries is not one the loader
         * accepts, so nothing says which readings this machine's sensors could
         * plausibly have produced. Stop for the same reason a refused
         * description stops the machine: the estimator would correct against
         * whatever a disconnected or shorted channel reports, which drags the
         * reconstruction toward a state the machine cannot be in, and the
         * result is a prediction that means nothing while looking exactly like
         * a machine that has merely drifted. Continuing on a partly-filled
         * record would be worse still -- bounds nobody supplied, believed as
         * though somebody had. What the machine should do about being left
         * without them, beyond not proceeding, is a fault-response concern
         * answered elsewhere.
         */
        for (;;) {
        }
    }

    /*
     * Both records go in through the control path rather than reaching the
     * estimator by a route of their own, so the machine drives from the same
     * description and the same bounds it was verified against. A refusal here
     * leaves the heater commanded off and the fault latched, and the loop below
     * keeps it there.
     */
    (void)control_init(&state, &parameters, &limits);

    for (;;) {
        (void)control_step(&state);
    }
}
