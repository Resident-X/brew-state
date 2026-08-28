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
 * The tolerance declaration travels the same way and answers a different kind
 * of question. It is not a statement about this machine at all: it says how far
 * from the temperature it was asked for a delivery may sit before the cup is no
 * longer the one that was ordered, which reads the same whatever the water was
 * heated in. It is carried because the control path is given the band rather
 * than compiling it in, and because there is no filesystem here to open it from.
 *
 * All three are read through their own loaders rather than through readers
 * written for the target. A second parser accepts a slightly different language
 * sooner or later -- a whitespace rule, an annotation quietly skipped -- and
 * then the machine is running numbers the host tier never saw, out of a file
 * both claim to read. One parser cannot disagree with itself.
 */
#include "control.h"
#include "delivery_tolerance.h"
#include "estimator_limits.h"
#include "hw_stm32.h"
#include "plant_model.h"
#include "reference_description.h"
#include "reference_limits.h"
#include "reference_tolerance.h"

int main(void)
{
    control_state_t state;
    plant_parameters_t parameters;
    plant_parameter_budget_t budget;
    plant_parameter_error_t description_fault;
    estimator_limits_t limits;
    estimator_limits_error_t limits_fault;
    delivery_tolerance_t tolerance;
    delivery_tolerance_error_t tolerance_fault;

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
                               &description_fault) ||
        !plant_parameter_budget_load(reference_description, reference_description_length, &budget,
                                     &description_fault)) {
        /*
         * The description this artefact carries is not one the loader accepts,
         * so there is no model of this machine. Stop rather than continue on
         * whatever a partly-filled record happens to hold: a machine running
         * against coefficients nobody supplied is one whose predictions mean
         * nothing, and it has no symptom that distinguishes it from a machine
         * whose model is merely wrong. The same text is read a second time for
         * what it says those coefficients may be wrong by, and a failure of
         * either stops here: a description whose figures load and whose
         * uncertainty does not is one the loop would command a target against a
         * margin sized by nothing. What the machine should do about being left
         * without a model, beyond not proceeding, is a fault-response concern
         * answered elsewhere.
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

    if (!delivery_tolerance_load(reference_tolerance, reference_tolerance_length, &tolerance,
                                 &tolerance_fault)) {
        /*
         * The tolerance declaration this artefact carries is not one the loader
         * accepts, so nothing says how close to the temperature it was asked for
         * a delivery has to be. Stop for the same reason a refused description
         * or refused bounds stop the machine, though what goes wrong is of
         * another kind: a band nothing declared is not a wide band, it is a
         * criterion nothing holds a delivery to. The loop would drive, the
         * machine would make coffee, and every cup would be within tolerance
         * because there is no tolerance to be outside of -- a claim that reads
         * as success from every direction and rests on nothing. Continuing on a
         * partly-filled record would be the same failure wearing a number:
         * a band nobody supplied, held to as though somebody had. What the
         * machine should do about being left without one, beyond not proceeding,
         * is a fault-response concern answered elsewhere.
         */
        for (;;) {
        }
    }

    /*
     * All three records go in through the control path rather than reaching the
     * estimator by a route of their own, so the machine drives from the same
     * description, the same bounds and the same band it was verified against. A
     * refusal here leaves the heater commanded off and the fault latched, and
     * the loop below keeps it there.
     */
    (void)control_init(&state, &parameters, &budget, &limits, &tolerance);

    for (;;) {
        (void)control_step(&state);
    }
}
