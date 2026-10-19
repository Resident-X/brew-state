#include "dryness_report.h"

#include <math.h>

#include "host_report.h"

#define BASIS_TEXT "superheat above saturation at the measured steam pressure"
#define PRESSURE_SOURCE_TEXT \
    "the plant model's steam pressure on that step, which the simulated sensor is set to read in whole millibar"
#define OVER_TEXT "the least over the draw"
#define SOURCE_TEXT "modelled at the outlet and confirmed by no sensor"
#define CARRY_OVER_TEXT "droplet carry-over is not excluded without a calorimetric test"

#define DRY_CLAIM "the steam left the outlet dry"
#define SATURATED_CLAIM "the steam is not shown dry: it left the outlet with no superheat"
#define NO_STEAM_CLAIM "no steam was made, so no dryness is claimed"

bool dryness_report(FILE *out, const dryness_finding_t *finding)
{
    if (out == NULL || finding == NULL || !isfinite(finding->superheat_k) ||
        !isfinite(finding->pressure_bar) || finding->superheat_k < 0.0f) {
        return false;
    }

    const bool dry = finding->steam_made && finding->superheat_k > 0.0f;
    const char *claim = dry ? DRY_CLAIM : (finding->steam_made ? SATURATED_CLAIM : NO_STEAM_CLAIM);

    const host_report_field_t fields[] = {
        host_report_boolean("dry", dry),
        host_report_text("claim", claim),
        host_report_number("superheat_k", (double)finding->superheat_k),
        host_report_number("pressure_bar_gauge", (double)finding->pressure_bar),
        host_report_text("pressure_source", PRESSURE_SOURCE_TEXT),
        host_report_text("basis", BASIS_TEXT),
        host_report_text("superheat_over", OVER_TEXT),
        host_report_text("superheat_source", SOURCE_TEXT),
        host_report_text("carry_over", CARRY_OVER_TEXT),
    };
    return host_report_emit(out, "steam-dryness", fields, sizeof(fields) / sizeof(fields[0]));
}
