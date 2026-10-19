/*
 * Whether the steam a host run made was dry, stated by the run.
 *
 * A claim that steam is dry rests on one thing here: the superheat of the steam
 * at the plant's modelled outlet, above saturation at the measured steam
 * pressure. The statement names that superheat and that pressure, says the
 * superheat is modelled and confirmed by no sensor, and says that droplet
 * carry-over is not excluded without a calorimetric test -- in the text line and
 * the JSON line alike, through the host report seam, so the caveat cannot be
 * dropped from one form and kept in the other. Steam is claimed dry only above
 * zero superheat; at saturation it is not, and where no steam was made nothing
 * is claimed.
 */
#ifndef DRYNESS_REPORT_H
#define DRYNESS_REPORT_H

#include <stdbool.h>
#include <stdio.h>

typedef struct {
    /* Whether any steam was made over the run, so that there was outlet steam at all. */
    bool steam_made;
    /* The least modelled outlet superheat over the steps steam was made on, in kelvin. */
    float superheat_k;
    /* The measured steam pressure on that step, in bar gauge. */
    float pressure_bar;
} dryness_finding_t;

/*
 * Write the run's dryness statement to `out` in both forms. Returns false,
 * writing nothing, for a null argument, and for a superheat or pressure that is
 * not a finite number or a superheat below nothing, which no outlet relation
 * gives.
 */
bool dryness_report(FILE *out, const dryness_finding_t *finding);

#endif /* DRYNESS_REPORT_H */
