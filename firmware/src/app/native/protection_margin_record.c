#include "protection_margin_record.h"

#include <stdbool.h>
#include <stdio.h>
#include <string.h>

#include "control.h"
#include "hw_sim.h"
#include "plant_model.h"
#include "steam_control.h"

/*
 * The longest coefficient name this reads back out of a description.
 *
 * The plant seam declares no such limit -- a name is text a caller is holding,
 * and the seam takes it by pointer and length -- so this is a limit of the
 * reading rather than of the vocabulary. It is generous against the longest
 * name any description in this tree carries and a name past it is refused
 * loudly rather than truncated, because a truncated name is one the position
 * lookup would answer nothing for and the corner would then be reported as
 * naming no coefficient at all.
 */
#define COEFFICIENT_NAME_LIMIT 64u

/*
 * What a reading stands at while the mapping is taken, in thousandths of a
 * degree.
 *
 * The margin is a property of a commanded target and of the description, not of
 * where the machine presently is -- the probe behind it stands its own model at
 * the target it is asked about. What this figure is for is only that the
 * control path comes up at all: an instance brought up with no reading at the
 * seam latches a fault and answers nothing. It is the same ordinary room
 * temperature the exercise in main.c brings the loop up against.
 */
#define STANDING_READING_MILLI_C 20000

/*
 * The span the highest admissible target is narrowed within, in degrees, and
 * how many halvings that narrowing takes.
 *
 * The span is deliberately wider than any bound the control path declares, at
 * both ends: what is being found is which of its ceilings is the tighter one on
 * this description, and a span starting inside one of them would answer with
 * its own end rather than with the machine's. Forty halvings takes a hundred
 * degrees below the resolution of a single-precision figure, so the answer is
 * the loop's bound rather than the search's step.
 */
#define NARROWING_FLOOR_C 20.0f
#define NARROWING_CEILING_C 120.0f
#define NARROWING_STEPS 40u

/*
 * The same narrowing on the steam side, in the thousandths that loop's own
 * declaration is written in, and how finely it stops.
 *
 * A ceiling of its own, because the steam block is held an order hotter than
 * the coffee one and a span borrowed from that side would sit entirely inside
 * the answer. It stops at a tenth of a degree rather than after a count of
 * halvings, because what is narrowed here is a whole number of thousandths the
 * declaration is rewritten with and there is nothing finer for it to reach.
 */
#define STEAM_NARROWING_CEILING_MILLI_C 400000
#define STEAM_NARROWING_RESOLUTION_MILLI_C 100

/*
 * The word each admission bound is reported under.
 *
 * Written out rather than printed as the enumerated value alone, because a
 * committed record naming a bound by its number is a record that goes on
 * reading plausibly after a value is inserted ahead of it in the enumeration.
 * The number is printed as well, so a reader can tell a word this table has
 * gone stale on from one it never had.
 */
static const char *bound_word(control_admission_bound_t bound)
{
    switch (bound) {
    case CONTROL_ADMISSION_OK:
        return "admitted";
    case CONTROL_ADMISSION_NOTHING_GIVEN:
        return "nothing-given";
    case CONTROL_ADMISSION_NO_MACHINE_DESCRIBED:
        return "no-machine-described";
    case CONTROL_ADMISSION_NOT_A_TEMPERATURE:
        return "not-a-temperature";
    case CONTROL_ADMISSION_RATE_OVER_FULL_SCALE:
        return "rate-over-full-scale";
    case CONTROL_ADMISSION_TARGET_OVER_SATURATION:
        return "over-saturation";
    case CONTROL_ADMISSION_TARGET_BEYOND_AUTHORITY:
        return "beyond-authority";
    case CONTROL_ADMISSION_TARGET_BELOW_DRINKING_FLOOR:
        return "below-drinking-floor";
    case CONTROL_ADMISSION_TARGET_ABOVE_DRINKING_CEILING:
        return "above-drinking-ceiling";
    case CONTROL_ADMISSION_TARGET_INSIDE_PROTECTION_MARGIN:
        return "inside-protection-margin";
    default:
        break;
    }
    return "unnamed";
}

/*
 * The coefficient names the description supplies, in the structure's own
 * ordering.
 *
 * The description is read for its names and each one is put to the plant seam's
 * position lookup, which is the one route from text a caller is holding to the
 * position the budget record and the corner enumeration are indexed by. Nothing
 * here assumes the description lists its coefficients in the structure's order,
 * or that a structure's order is anything a file could state: the lookup
 * answers that, and a name the structure does not have is passed over rather
 * than counted, because a description carrying a line no structure claims would
 * already have been refused by the loader before this ran.
 *
 * Returns false where a name is longer than this file reads, which is a
 * description this cannot report on rather than one it reports on partly.
 */
static bool names_by_position(const char *text, size_t length,
                              char names[][COEFFICIENT_NAME_LIMIT], size_t limit)
{
    for (size_t at = 0u; at < limit; at++) {
        names[at][0] = '\0';
    }

    size_t at = 0u;
    while (at < length) {
        size_t end = at;
        while (end < length && text[end] != '\n') {
            end++;
        }

        size_t cursor = at;
        while (cursor < end && (text[cursor] == ' ' || text[cursor] == '\t')) {
            cursor++;
        }
        size_t name_end = cursor;
        while (name_end < end && text[name_end] != ' ' && text[name_end] != '\t' &&
               text[name_end] != '=') {
            name_end++;
        }
        size_t equals = name_end;
        while (equals < end && (text[equals] == ' ' || text[equals] == '\t')) {
            equals++;
        }

        const bool assigns = cursor < end && text[cursor] != '#' && name_end > cursor &&
                             equals < end && text[equals] == '=';
        if (assigns) {
            const size_t spelled = (size_t)(name_end - cursor);
            char name[COEFFICIENT_NAME_LIMIT];
            size_t position = 0u;

            if (spelled >= sizeof(name)) {
                (void)fprintf(stderr,
                              "protection margin record: a coefficient name is longer than this "
                              "reads\n");
                return false;
            }
            memcpy(name, &text[cursor], spelled);
            name[spelled] = '\0';

            if (plant_parameter_position(name, &position) && position < limit) {
                memcpy(names[position], name, spelled + 1u);
            }
        }
        at = (end < length) ? end + 1u : length;
    }
    return true;
}

/* The name at a position, or a placeholder where the description named none. */
static const char *named(const char names[][COEFFICIENT_NAME_LIMIT], size_t limit, size_t at)
{
    if (at >= limit || names[at][0] == '\0') {
        return "-";
    }
    return names[at];
}

/*
 * The highest target this instance will take, narrowed on the admission path
 * rather than worked out from any figure read out of the control source, and
 * the bound that stops the narrowing.
 *
 * Which ceiling is the tighter one is exactly what this is asked, so it is
 * asked of the loop. A record that computed the trip point less the margin for
 * itself would report the protection margin as the binding bound on a machine
 * where it is not, which is the one conclusion a reader would take from it.
 */
static bool highest_target_taken(control_state_t *state, float *taken_c,
                                 control_admission_t *refused_at)
{
    float taken = NARROWING_FLOOR_C;
    float refused = NARROWING_CEILING_C;
    control_admission_t admission;

    if (!control_command_temperature(state, taken)) {
        (void)fprintf(stderr,
                      "protection margin record: this instance takes no target at all, so there "
                      "is no highest one\n");
        return false;
    }
    if (control_command_temperature_reporting(state, refused, &admission)) {
        (void)fprintf(stderr,
                      "protection margin record: this instance takes every target the narrowing "
                      "spans, so its highest is not inside it\n");
        return false;
    }
    *refused_at = admission;

    for (unsigned narrowing = 0u; narrowing < NARROWING_STEPS; narrowing++) {
        const float middle = (taken + refused) / 2.0f;

        if (control_command_temperature_reporting(state, middle, &admission)) {
            taken = middle;
        } else {
            refused = middle;
            *refused_at = admission;
        }
    }
    *taken_c = taken;
    return true;
}

/*
 * Which coefficients one corner writes, by name, written into `writes`.
 *
 * An independent corner writes the one it stands at; the joint corner writes
 * every supply-driven coefficient the description declares an error against,
 * which is the same set the enumeration itself moves and is asked of the seam
 * here rather than assumed to be a pair.
 *
 * Returns false where the names run past what this reports, which is a
 * description this cannot report on rather than one it reports on partly.
 */
static bool writes_of(const protection_margin_corner_t *corner,
                      const plant_parameter_budget_t *budget,
                      const char names[][COEFFICIENT_NAME_LIMIT], char *writes, size_t room)
{
    size_t written = 0u;

    writes[0] = '\0';
    if (!corner->joint) {
        written = (size_t)snprintf(writes, room, "%s",
                                   named(names, (size_t)PLANT_PARAMETER_LIMIT, corner->at));
        return written < room;
    }

    for (size_t at = 0u; at < budget->count && at < (size_t)PLANT_PARAMETER_LIMIT; at++) {
        bool driven = false;

        if (!plant_parameter_supply_driven(at, &driven) || !driven || !budget->declared[at]) {
            continue;
        }
        written += (size_t)snprintf(&writes[written], room - written, "%s%s",
                                    written == 0u ? "" : ",",
                                    named(names, (size_t)PLANT_PARAMETER_LIMIT, at));
        if (written >= room) {
            return false;
        }
    }
    if (written == 0u) {
        (void)snprintf(writes, room, "-");
    }
    return true;
}

/* One corner of an enumeration, under the prefix the side reports beneath. */
static void print_corner(const char *prefix, size_t which,
                         const protection_margin_corner_t *corner, const char *writes)
{
    (void)printf("HOST %s which=%u kind=%s at=%u end=%s declared=%.9g factor=%.9g ran=%d "
                 "contribution-c=%.9g moves=%u writes=%s\n",
                 prefix, (unsigned)which, corner->joint ? "joint" : "independent",
                 (unsigned)corner->at, corner->reaching_downwards ? "low" : "high",
                 (double)corner->declared_error,
                 (double)(corner->reaching_downwards ? 1.0f - corner->declared_error
                                                     : 1.0f + corner->declared_error),
                 corner->ran ? 1 : 0, (double)corner->contribution_c, (unsigned)corner->moves,
                 writes);
}

/* The margin figure itself, under the prefix the side reports beneath. */
static void print_margin(const char *prefix, const protection_margin_t *margin)
{
    (void)printf("HOST %s widened-c=%.9g unwidened-c=%.9g worst-c=%.9g sensing-error-c=%.9g "
                 "corners=%u run=%u contributing=%u worst-at=%u worst-joint=%d\n",
                 prefix, (double)margin->margin_c, (double)margin->unwidened_c,
                 (double)margin->worst_corner_c, (double)margin->sensing_error_c,
                 (unsigned)margin->corners, (unsigned)margin->corners_run,
                 (unsigned)margin->contributing, (unsigned)margin->worst_at,
                 margin->worst_is_joint ? 1 : 0);
}

/*
 * The coffee side: the highest target its loop takes, which of its ceilings
 * stops it there, the margin at that target and every corner behind it.
 */
static int record_the_brew_side(const plant_parameters_t *parameters,
                                const plant_parameter_budget_t *budget,
                                const estimator_limits_t *limits,
                                const delivery_tolerance_t *tolerance,
                                const pump_trim_declaration_t *pump_trim,
                                const char names[][COEFFICIENT_NAME_LIMIT])
{
    control_state_t state;
    control_admission_t refused_at;
    protection_margin_t margin;
    float target_c = 0.0f;

    hw_sim_reset();
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, HW_READING_VALID, STANDING_READING_MILLI_C);

    if (!control_init(&state, parameters, budget, limits, tolerance, pump_trim)) {
        (void)fprintf(stderr, "protection margin record: the control path could not be brought "
                              "up\n");
        return 1;
    }
    if (!highest_target_taken(&state, &target_c, &refused_at)) {
        return 1;
    }
    if (!control_protection_margin(&state, target_c, &margin)) {
        (void)fprintf(stderr,
                      "protection margin record: this description supports no corner "
                      "enumeration, so there is no mapping to take\n");
        return 1;
    }

    (void)printf("HOST margin-target target-c=%.9g capping-bound=%d capping-bound-name=%s "
                 "capping-available-c=%.9g\n",
                 (double)target_c, (int)refused_at.bound, bound_word(refused_at.bound),
                 (double)refused_at.available);

    /*
     * The trip point, where the loop's own refusal reports it: the figure the
     * refusal names as the highest admissible target plus the margin sized for
     * the target that was refused. Read back off the loop rather than copied out
     * of the control source, so a record and the loop cannot come to disagree
     * about it.
     *
     * It is reported as unknown where some other ceiling is the tighter one on
     * this description. That is not a gap in the reading: a machine whose
     * protection margin never binds is one whose trip point the control path is
     * never asked about, and a record naming a figure nothing was measured
     * against would be inventing the one number the whole mapping is anchored
     * to.
     */
    const bool trip_known = refused_at.bound == CONTROL_ADMISSION_TARGET_INSIDE_PROTECTION_MARGIN;
    float trip_c = 0.0f;
    if (trip_known) {
        protection_margin_t at_the_refusal;

        if (!control_protection_margin(&state, refused_at.requested, &at_the_refusal)) {
            (void)fprintf(stderr,
                          "protection margin record: the margin behind the refusal could not be "
                          "read back\n");
            return 1;
        }
        trip_c = refused_at.available + at_the_refusal.margin_c;
    }
    (void)printf("HOST margin-trip known=%d trip-c=%.9g\n", trip_known ? 1 : 0, (double)trip_c);
    print_margin("margin", &margin);

    for (size_t which = 0u; which < margin.corners; which++) {
        protection_margin_corner_t corner;
        char writes[PLANT_PARAMETER_LIMIT * COEFFICIENT_NAME_LIMIT];

        if (!control_protection_margin_corner(&state, target_c, which, &corner)) {
            (void)fprintf(stderr,
                          "protection margin record: corner %u of the enumeration could not be "
                          "read\n",
                          (unsigned)which);
            return 1;
        }
        if (!writes_of(&corner, budget, names, writes, sizeof(writes))) {
            (void)fprintf(stderr,
                          "protection margin record: corner %u names more coefficients than this "
                          "reports\n",
                          (unsigned)which);
            return 1;
        }
        print_corner("margin-corner", which, &corner, writes);
    }
    return 0;
}

/*
 * The steam side: the ready target its declaration names, the highest one its
 * loop would come up against at all, the margin behind that and every corner of
 * it.
 *
 * The highest admissible ready target is narrowed the way the coffee side's is,
 * on the loop's own refusal rather than on any arithmetic here -- the steam loop
 * takes its target at bring-up rather than as a command, so what is narrowed is
 * whether the loop comes up at all. The declared target is reported beside it,
 * because the distance between the two is what says whether this loop's ready
 * temperature is one the margin leaves room for or one the margin is what
 * stops.
 */
static int record_the_steam_side(const plant_parameters_t *parameters,
                                 const plant_parameter_budget_t *budget,
                                 const estimator_limits_t *limits,
                                 const steam_control_declaration_t *declaration,
                                 const char names[][COEFFICIENT_NAME_LIMIT])
{
    steam_control_state_t loop;
    steam_control_declaration_t asking = *declaration;
    protection_margin_t margin;

    hw_sim_reset();
    if (!steam_control_init(&loop, limits, declaration, parameters, budget)) {
        (void)fprintf(stderr,
                      "protection margin record: the steam loop refuses the ready target its own "
                      "declaration names, so there is no margin behind a target it holds\n");
        return 1;
    }
    if (!steam_control_protection_margin(&loop, &margin)) {
        (void)fprintf(stderr,
                      "protection margin record: this description supports no steam corner "
                      "enumeration, so there is no mapping to take\n");
        return 1;
    }

    int32_t taken_milli_c = declaration->ready_temperature_milli_c;
    int32_t refused_milli_c = STEAM_NARROWING_CEILING_MILLI_C;
    steam_control_state_t narrowing;

    while (refused_milli_c - taken_milli_c > STEAM_NARROWING_RESOLUTION_MILLI_C) {
        const int32_t middle_milli_c = (taken_milli_c + refused_milli_c) / 2;

        asking.ready_temperature_milli_c = middle_milli_c;
        hw_sim_reset();
        if (steam_control_init(&narrowing, limits, &asking, parameters, budget)) {
            taken_milli_c = middle_milli_c;
        } else {
            refused_milli_c = middle_milli_c;
        }
    }

    (void)printf("HOST steam-margin-target ready-c=%.9g highest-c=%.9g\n",
                 (double)declaration->ready_temperature_milli_c / 1000.0,
                 (double)taken_milli_c / 1000.0);
    print_margin("steam-margin", &margin);

    for (size_t which = 0u; which < margin.corners; which++) {
        protection_margin_corner_t corner;
        char writes[PLANT_PARAMETER_LIMIT * COEFFICIENT_NAME_LIMIT];

        if (!steam_control_protection_margin_corner(&loop, which, &corner)) {
            (void)fprintf(stderr,
                          "protection margin record: steam corner %u of the enumeration could not "
                          "be read\n",
                          (unsigned)which);
            return 1;
        }
        if (!writes_of(&corner, budget, names, writes, sizeof(writes))) {
            (void)fprintf(stderr,
                          "protection margin record: steam corner %u names more coefficients than "
                          "this reports\n",
                          (unsigned)which);
            return 1;
        }
        print_corner("steam-margin-corner", which, &corner, writes);
    }
    return 0;
}

int protection_margin_record_run(const char *description_text, size_t description_length,
                                 const plant_parameters_t *parameters,
                                 const plant_parameter_budget_t *budget,
                                 const estimator_limits_t *limits,
                                 const delivery_tolerance_t *tolerance,
                                 const pump_trim_declaration_t *pump_trim,
                                 const steam_control_declaration_t *steam)
{
    static char names[PLANT_PARAMETER_LIMIT][COEFFICIENT_NAME_LIMIT];

    if (!names_by_position(description_text, description_length, names,
                           (size_t)PLANT_PARAMETER_LIMIT)) {
        return 1;
    }

    const int brew = record_the_brew_side(parameters, budget, limits, tolerance, pump_trim, names);
    if (brew != 0) {
        return brew;
    }
    const int steamed = record_the_steam_side(parameters, budget, limits, steam, names);
    if (steamed != 0) {
        return steamed;
    }

    (void)printf("HOST done\n");
    return 0;
}
