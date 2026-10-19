/*
 * The bound a host run's steam side holds trapped pressure to, stated by the run.
 *
 * The thermoblock reports saturation of its casting temperature while the wand
 * is shut over held liquid, and never more than saturation at a declared casting
 * ceiling. This states that ceiling, and the gauge pressure the model reports
 * with the casting beyond it, through the host report seam in text and JSON.
 * The pressure is read off the model by driving it rather than computed here, so
 * what the run states is what the structure it was built against does.
 *
 * The statement says what the figure is: saturation at the declared ceiling, a
 * control limit the model applies and not containment of anything.
 */
#ifndef CASTING_CEILING_REPORT_H
#define CASTING_CEILING_REPORT_H

#include <stdio.h>

#include "plant_model.h"

typedef enum {
    /* Both lines were written. */
    CASTING_CEILING_REPORTED,
    /* The structure declares no casting ceiling, as a boiler's steam side does not. Nothing written. */
    CASTING_CEILING_NOT_DECLARED,
    /* The structure declares one and the run could not state it. Nothing written. */
    CASTING_CEILING_REFUSED
} casting_ceiling_outcome_t;

casting_ceiling_outcome_t casting_ceiling_report(FILE *out, const plant_parameters_t *parameters);

#endif /* CASTING_CEILING_REPORT_H */
