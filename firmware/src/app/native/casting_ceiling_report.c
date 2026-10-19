#include "casting_ceiling_report.h"

#include "host_report.h"

#include <math.h>

#define CEILING_COEFFICIENT "steam.casting_ceiling_c"

/* How far past the ceiling the casting is put to read the bound. */
#define BEYOND_CEILING_C 25.0f

/* One step with the feed full, long enough to fill a block and short enough to leave the casting hot. */
#define PROBE_STEP_MS 100u

#define BASIS_TEXT "saturation at the declared ceiling"
#define NATURE_TEXT "a control limit and not containment"

casting_ceiling_outcome_t casting_ceiling_report(FILE *out, const plant_parameters_t *parameters)
{
    size_t at = 0u;
    if (parameters == NULL || out == NULL) {
        return CASTING_CEILING_REFUSED;
    }
    if (!plant_parameter_position(CEILING_COEFFICIENT, &at)) {
        return CASTING_CEILING_NOT_DECLARED;
    }

    float ceiling_c = 0.0f;
    if (!plant_parameter_value(parameters, at, &ceiling_c)) {
        return CASTING_CEILING_REFUSED;
    }

    plant_model_t probe;
    plant_actuation_t feed_full = {{0u}};
    feed_full.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = ACTUATION_FULL_SCALE;
    float bound_bar = 0.0f;
    if (!plant_model_init(&probe, parameters) ||
        !plant_model_set_state(&probe, PLANT_STATE_STEAM_TEMPERATURE_C,
                               ceiling_c + BEYOND_CEILING_C) ||
        !plant_model_step(&probe, &feed_full, 0.0f, PROBE_STEP_MS) ||
        !plant_model_quantity(&probe, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &bound_bar) ||
        !isfinite(bound_bar)) {
        return CASTING_CEILING_REFUSED;
    }

    const host_report_field_t fields[] = {
        host_report_number("ceiling_c", (double)ceiling_c),
        host_report_number("ceiling_pressure_bar_gauge", (double)bound_bar),
        host_report_text("basis", BASIS_TEXT),
        host_report_text("nature", NATURE_TEXT),
    };
    return host_report_emit(out, "steam-casting-ceiling", fields,
                            sizeof(fields) / sizeof(fields[0]))
               ? CASTING_CEILING_REPORTED
               : CASTING_CEILING_REFUSED;
}
