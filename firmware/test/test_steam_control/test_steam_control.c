/*
 * The steam control law exercised against the structure that describes the
 * reference machine.
 *
 * The suite is in two halves and the difference between them matters. The
 * first drives the law against readings the test stands up directly, which is
 * the right shape for asserting what the law does with the seam -- which
 * channel it reads, what it does with a reading it cannot believe, what it
 * commands on the step a report changes -- and the wrong shape entirely for
 * asserting that it holds anything, because the simulated hardware returns
 * whatever a caller last set and a tracking assertion made against it would be
 * comparing the law with itself.
 *
 * The second half closes the loop through a truth plant the law does not
 * share: the model is advanced under the levels the law actually drove, and
 * the pressure and temperature it arrives at are injected through the hardware
 * seam as the readings. Every band, recovery and sequencing assertion below
 * lives there, and has content because of it -- the same arrangement
 * test_control.c already establishes for the brew side.
 *
 * What cannot be established here is whether any of the declared figures is
 * right for a real machine. Nothing has been on a bench, the coefficients the
 * figures were chosen against have not been either, and
 * params/steam_control.declaration says so on every line.
 */
#include <unity.h>

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "dryness_report.h"
#include "estimator_limits.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"
#include "steam_control.h"
#include "steam_control_declaration.h"

/* The interval every step in this suite advances by. */
#define STEP_INTERVAL_MS 10u

/* Steps in a second of simulated time, at the interval above. */
#define STEPS_PER_SECOND (1000u / STEP_INTERVAL_MS)

/*
 * How long a run is given to settle at the ready target before anything is
 * asked of it. The block is started at the declared ready target, so what this
 * span is for is the integral trimming whatever the declared standing-load
 * feedforward does not exactly answer, not for heating a cold machine -- which
 * is a separate test with its own span.
 */
#define SETTLE_SECONDS 30u

/*
 * The longest a run is given to reach the ready target from wherever it has
 * been left, in seconds.
 *
 * It is not a claim about how quickly this machine becomes ready. It is a
 * bound generous enough to hold at every corner of the error
 * thermoblock.params declares on the two coefficients that decide it -- the
 * steam block's thermal mass, which may be four tenths heavier than declared,
 * and its loss to the room, which may be six tenths smaller -- and the runs
 * below that use it are run at those corners rather than at the nominal
 * figures alone. At the slowest corner the model recovers a draw's worth of
 * excess in a little over five minutes; this admits ten.
 */
#define RECOVERY_BOUND_SECONDS 600u

/*
 * How close to the ready target a run has to come to count as having reached
 * it, in degrees. It is the suite's own reading of "back at ready" rather than
 * a declared figure: the design declares where it holds the block, and nothing
 * declares how tightly, because what the drink is sensitive to is the pressure
 * during a draw and that has a declared band of its own.
 */
#define READY_TOLERANCE_C 1.0f

/* The settle the joint corners are given: the weakest of them is slow to reach ready. */
#define JOINT_SETTLE_SECONDS 300u

/*
 * A steam temperature comfortably below the declared ready target, used where
 * a test needs the block left cooler than the loop wants it. Chosen without
 * reaching for any coefficient by name, and above the declared saturation
 * temperature so the path still carries some gauge pressure there.
 */
#define BELOW_READY_C 110.0f

/*
 * How long a test of the feed-withhold gate holds a draw it starves, in
 * milliseconds: long enough that the feed's own rise from its start level to its
 * ceiling would have run several times over, so a withheld feed is the gate's
 * doing and not the sequencing's.
 */
#define WITHHELD_SPAN_MS 20000u

/*
 * The coefficient the orifice law turns the steam made into pressure through,
 * which the plant description names among the loosest figures it carries.
 */
#define RESTRICTION_COEFFICIENT "steam.restriction_bar_s2_per_ml2"

static plant_parameters_t parameters;
static plant_parameter_budget_t budget;
static estimator_limits_t limits;
static steam_control_declaration_t declaration;

static char description_text[32768];
static size_t description_length;

/* --- Loading what the machine and the design actually declare -------------- */

static size_t read_whole_file(const char *path, char *into, size_t capacity, const char *what)
{
    FILE *const handle = fopen(path, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, what);

    const size_t used = fread(into, 1u, capacity - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < capacity - 1u);
    into[used] = '\0';
    return used;
}

static void load_the_reference_description(void)
{
    description_length = read_whole_file(REFERENCE_DESCRIPTION_PATH, description_text,
                                         sizeof(description_text),
                                         "could not open the reference description");

    plant_parameter_error_t fault;
    TEST_ASSERT_TRUE(
        plant_parameters_load(description_text, description_length, &parameters, &fault));
    TEST_ASSERT_TRUE(
        plant_parameter_budget_load(description_text, description_length, &budget, &fault));
}

static void load_the_reference_limits(void)
{
    static char text[16384];
    const size_t used = read_whole_file(REFERENCE_LIMITS_PATH, text, sizeof(text),
                                        "could not open the reference limits declaration");

    estimator_limits_error_t fault;
    TEST_ASSERT_TRUE(estimator_limits_load(text, used, &limits, &fault));
}

static void load_the_reference_steam_control_declaration(void)
{
    static char text[32768];
    const size_t used = read_whole_file(REFERENCE_STEAM_CONTROL_DECLARATION_PATH, text,
                                        sizeof(text),
                                        "could not open the reference steam control declaration");

    steam_control_declaration_error_t fault;
    TEST_ASSERT_TRUE(steam_control_declaration_load(text, used, &declaration, &fault));
}

/*
 * A record written back out as a declaration.
 *
 * Every test that wants a figure other than the shipped one takes a copy of
 * the shipped record, moves the one field it is interested in, and comes back
 * through here and through the loader again. That is deliberate rather than
 * convenient: it is the loader that has to accept the altered figure, so what
 * the test hands the control law is a record the declaration grammar produced
 * and not one the test assembled behind the grammar's back. A figure the
 * grammar would refuse cannot reach the law by this route, which is the
 * property "declared data" is standing for.
 */
static const char *text_for(const steam_control_declaration_t *d)
{
    static char text[4096];
    const int written = snprintf(
        text, sizeof(text),
        "ready-pressure-bar = %d milli-bar @estimated a figure this test chose\n"
        "ready-temperature-c = %d milli-c @estimated a figure this test chose\n"
        "draw-pressure-floor-bar = %d milli-bar @estimated a figure this test chose\n"
        "draw-pressure-ceiling-bar = %d milli-bar @estimated a figure this test chose\n"
        "draw-start-feed = %d permille @estimated a figure this test chose\n"
        "feed-ceiling = %d permille @estimated a figure this test chose\n"
        "feed-rise-limit = %d permille-per-s @estimated a figure this test chose\n"
        "superheat-setpoint = %d milli-k @estimated a figure this test chose\n"
        "ready-temperature-gain = %d milli-permille-per-k @estimated a figure this test chose\n"
        "ready-temperature-integral-gain = %d milli-permille-per-k-s @estimated a figure this test chose\n"
        "superheat-gain = %d milli-permille-per-k @estimated a figure this test chose\n"
        "superheat-integral-gain = %d milli-permille-per-k-s @estimated a figure this test chose\n"
        "feed-pressure-gain = %d milli-permille-per-bar @estimated a figure this test chose\n"
        "feed-pressure-integral-gain = %d milli-permille-per-bar-s @estimated a figure this test chose\n"
        "feed-load-gain = %d milli-permille-per-permille @estimated a figure this test chose\n"
        "standing-load = %d permille @estimated a figure this test chose\n",
        d->ready_pressure_milli_bar, d->ready_temperature_milli_c,
        d->draw_pressure_floor_milli_bar, d->draw_pressure_ceiling_milli_bar,
        d->draw_start_feed_permille, d->feed_ceiling_permille, d->feed_rise_limit_permille_per_s,
        d->superheat_setpoint_milli_k, d->ready_gain_milli_permille_per_k,
        d->ready_integral_gain_milli_permille_per_k_s, d->superheat_gain_milli_permille_per_k,
        d->superheat_integral_gain_milli_permille_per_k_s, d->feed_gain_milli_permille_per_bar,
        d->feed_integral_gain_milli_permille_per_bar_s,
        d->feed_load_gain_milli_permille_per_permille, d->standing_load_permille);

    TEST_ASSERT_TRUE_MESSAGE(written > 0 && (size_t)written < sizeof(text),
                             "the suite's own declaration did not fit");
    return text;
}

static bool declaration_from(const char *text, steam_control_declaration_t *built,
                             steam_control_declaration_error_t *fault)
{
    return steam_control_declaration_load(text, strlen(text), built, fault);
}

/* The shipped record with whatever the caller moved, back through the loader. */
static steam_control_declaration_t re_declared(const steam_control_declaration_t *altered)
{
    steam_control_declaration_t built;
    steam_control_declaration_error_t fault;

    TEST_ASSERT_TRUE_MESSAGE(declaration_from(text_for(altered), &built, &fault),
                             "the suite's own altered declaration was refused");
    return built;
}

/*
 * The reference description with one coefficient written differently.
 *
 * The line is rewritten and handed back to the same loader rather than the
 * record being reached into, so a perturbed description is admitted on exactly
 * the terms a shipped one is -- including the range the structure declares the
 * coefficient admissible within, which is what decides whether a perturbation
 * is still a machine. Written on the same terms test_control.c's own
 * description_with is, and for the same reasons.
 */
static const char *description_with_all(const char *const *names, const char *const *values,
                                        size_t count)
{
    static char rewritten[sizeof(description_text)];
    size_t written = 0u;
    size_t at = 0u;
    size_t replaced = 0u;

    while (at < description_length) {
        size_t end = at;
        while (end < description_length && description_text[end] != '\n') {
            end++;
        }

        size_t cursor = at;
        while (cursor < end &&
               (description_text[cursor] == ' ' || description_text[cursor] == '\t')) {
            cursor++;
        }

        size_t named = count;
        for (size_t which = 0u; which < count && named == count; which++) {
            const size_t name_length = strlen(names[which]);
            bool names_it = (size_t)(end - cursor) > name_length &&
                            memcmp(&description_text[cursor], names[which], name_length) == 0;
            if (names_it) {
                size_t after = cursor + name_length;
                while (after < end &&
                       (description_text[after] == ' ' || description_text[after] == '\t')) {
                    after++;
                }
                names_it = after < end && description_text[after] == '=';
            }
            if (names_it) {
                named = which;
            }
        }

        if (named < count) {
            written += (size_t)snprintf(&rewritten[written], sizeof(rewritten) - written,
                                        "%s = %s\n", names[named], values[named]);
            replaced++;
        } else {
            written += (size_t)snprintf(&rewritten[written], sizeof(rewritten) - written, "%.*s\n",
                                        (int)(end - at), &description_text[at]);
        }
        TEST_ASSERT_TRUE(written < sizeof(rewritten));
        at = (end < description_length) ? end + 1u : description_length;
    }

    TEST_ASSERT_EQUAL_UINT_MESSAGE(count, replaced,
                                   "a coefficient to be perturbed is not in the description");
    return rewritten;
}

static const char *description_with(const char *name, const char *value)
{
    return description_with_all(&name, &value, 1u);
}

static plant_parameters_t parameters_from(const char *text)
{
    plant_parameters_t built;
    plant_parameter_error_t fault;

    TEST_ASSERT_TRUE_MESSAGE(plant_parameters_load(text, strlen(text), &built, &fault),
                             "the suite's own description was refused");
    return built;
}

/*
 * What the reference description says a coefficient is.
 *
 * Read out of the description's own text rather than typed here, so a revised
 * figure moves every run that is scaled from it rather than leaving this suite
 * asserting about a machine the description no longer describes. The
 * coefficient is named by the name the description calls it -- which is text
 * the suite already has, and which names no structure's record or field.
 */
static float nominal_of(const char *coefficient)
{
    const char *const found = strstr(description_text, coefficient);
    float value = 0.0f;

    TEST_ASSERT_NOT_NULL_MESSAGE(found, coefficient);
    TEST_ASSERT_EQUAL_INT_MESSAGE(1, sscanf(strchr(found, '=') + 1, "%f", &value), coefficient);
    return value;
}

/* The reference description with one coefficient scaled by `factor`. */
static plant_parameters_t machine_with_scaled(const char *coefficient, float factor)
{
    char value[32];

    (void)snprintf(value, sizeof(value), "%.6f", (double)(nominal_of(coefficient) * factor));
    return parameters_from(description_with(coefficient, value));
}

/*
 * The reference description with every coefficient named scaled at once, each by
 * its own factor.
 */
static plant_parameters_t machine_with_all_scaled(const char *const *coefficients,
                                                  const float *factors, size_t count)
{
    char text[8][32];
    const char *values[8];

    TEST_ASSERT_TRUE(count <= 8u);
    for (size_t at = 0u; at < count; at++) {
        (void)snprintf(text[at], sizeof(text[at]), "%.6f",
                       (double)(nominal_of(coefficients[at]) * factors[at]));
        values[at] = text[at];
    }
    return parameters_from(description_with_all(coefficients, values, count));
}

/* --- The harness the loop is closed through -------------------------------- */

/* The machine the loop is closed through, which the control law does not hold. */
static plant_model_t truth;
static steam_control_state_t loop;
static bool wand_open;
static float demand_ml_per_s;

static float truth_quantity(plant_quantity_t which)
{
    float value = 0.0f;

    TEST_ASSERT_TRUE(plant_model_quantity(&truth, which, &value));
    return value;
}

static int32_t truth_pressure_milli_bar(void)
{
    return (int32_t)lroundf(truth_quantity(PLANT_QUANTITY_STEAM_PRESSURE_BAR) * 1000.0f);
}

/*
 * Stand every channel the law reads up from the truth plant, as a machine
 * carrying the instruments the reference machine now does would present them.
 * The knob is not the plant's to answer -- the wand is opened by an operator's
 * hand and nothing inside the machine decides it -- so it carries what this
 * suite is presently doing with it, in the seam's own discrete spelling.
 */
static void publish(void)
{
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, truth_pressure_milli_bar());
    hw_sim_set_sensor(
        HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
        (int32_t)lroundf(truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C) * 1000.0f));
    hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID,
                      wand_open ? HW_READING_DISCRETE_SET : HW_READING_DISCRETE_CLEAR);
}

/*
 * One turn of the closed loop: publish what the machine presently reads, run
 * the control step, then advance the machine under the levels that step
 * actually got onto the two channels.
 *
 * The order is the whole arrangement. The plant is stepped under what was
 * driven rather than under what the test wanted driven, and the law never sees
 * the plant except through the seam, so nothing here can agree with itself by
 * construction.
 */
static steam_control_step_result_t closed_loop_step(void)
{
    publish();

    const steam_control_step_result_t result = steam_control_step(&loop);

    plant_actuation_t driven = {{0u}};
    driven.level_permille[ACTUATION_CHANNEL_STEAM_HEATER] =
        hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER);
    driven.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] =
        hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);

    TEST_ASSERT_TRUE(plant_model_step(&truth, &driven, demand_ml_per_s, STEP_INTERVAL_MS));
    hw_sim_advance_millis(STEP_INTERVAL_MS);
    return result;
}

static void bring_the_loop_up(const plant_parameters_t *machine,
                              const steam_control_declaration_t *figures, float steam_temperature_c)
{
    hw_sim_reset();
    wand_open = false;
    demand_ml_per_s = 0.0f;

    TEST_ASSERT_TRUE(plant_model_init(&truth, machine));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, steam_temperature_c));

    /*
     * One idle step so the pressure the structure reports follows the
     * temperature just written into it: the relation is evaluated when a model
     * is advanced, not when a state is set, and publishing before it would put
     * the pressure of the state the instance came up in on the seam.
     */
    const plant_actuation_t idle = {{0u}};
    TEST_ASSERT_TRUE(plant_model_step(&truth, &idle, 0.0f, STEP_INTERVAL_MS));

    TEST_ASSERT_TRUE(steam_control_init(&loop, &limits, figures, &parameters, &budget));
}

static float ready_target_c(const steam_control_declaration_t *figures)
{
    return (float)figures->ready_temperature_milli_c / 1000.0f;
}

/* Run the loop with the wand shut for a span of simulated seconds. */
static void hold_ready_for(unsigned seconds)
{
    wand_open = false;
    demand_ml_per_s = 0.0f;
    for (unsigned step = 0u; step < seconds * STEPS_PER_SECOND; step++) {
        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, closed_loop_step());
    }
}

/* What one step of a draw showed. */
typedef struct {
    uint32_t at_millis;
    int32_t pressure_milli_bar;
    uint16_t heater_permille;
    uint16_t feed_permille;
    /* The truth plant's superheat at its modelled outlet, after the step. */
    float superheat_k;
    /* The law's own estimate of it on the step, and whether it formed one. */
    bool estimated;
    float estimate_k;
    float steam_c;
} sample_t;

#define DRAW_SAMPLE_MAX 12000

static sample_t samples[DRAW_SAMPLE_MAX];
static size_t sample_count;

/* Run a draw of `seconds` at `demand`, recording every step. */
static void draw_for(unsigned seconds, float demand)
{
    const size_t steps = (size_t)seconds * STEPS_PER_SECOND;

    TEST_ASSERT_TRUE_MESSAGE(steps <= DRAW_SAMPLE_MAX, "a draw longer than the suite records");
    sample_count = 0u;
    wand_open = true;
    demand_ml_per_s = demand;

    for (size_t step = 0u; step < steps; step++) {
        (void)closed_loop_step();
        samples[sample_count].at_millis = (uint32_t)(step * STEP_INTERVAL_MS);
        samples[sample_count].pressure_milli_bar = truth_pressure_milli_bar();
        samples[sample_count].heater_permille = hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER);
        samples[sample_count].feed_permille = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        samples[sample_count].superheat_k = truth_quantity(PLANT_QUANTITY_STEAM_OUTLET_SUPERHEAT_K);
        samples[sample_count].estimated =
            steam_control_outlet_superheat(&loop, &samples[sample_count].estimate_k);
        samples[sample_count].steam_c = truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C);
        sample_count++;
    }

    wand_open = false;
    demand_ml_per_s = 0.0f;
}

/* The first step of the recorded draw on which any steam was actually fed. */
static const sample_t *first_delivery(void)
{
    for (size_t at = 0u; at < sample_count; at++) {
        if (samples[at].feed_permille > 0u) {
            return &samples[at];
        }
    }
    return NULL;
}

/*
 * Whether every step from the first one that fed steam to the end of the draw
 * kept measured pressure inside the declared band, and the worst offender if
 * not.
 *
 * The window starts where steam is first actually delivered rather than at the
 * instant the wand turned, and the distinction is the band's own: what the
 * band states is the character of the steam coming out, and before feed
 * engages there is none coming out to have a character. The interval before
 * that point is not unexamined -- it is exactly what the margin-building
 * criterion's own test asserts about, and what it asserts is that the block
 * spends it climbing into this band rather than delivering from below it.
 */
static bool in_band_from_first_delivery(const steam_control_declaration_t *figures,
                                        int32_t *worst)
{
    bool held = true;

    *worst = 0;
    bool delivering = false;
    for (size_t at = 0u; at < sample_count; at++) {
        delivering = delivering || samples[at].feed_permille > 0u;
        if (!delivering) {
            continue;
        }
        const int32_t pressure = samples[at].pressure_milli_bar;
        if (pressure < figures->draw_pressure_floor_milli_bar ||
            pressure > figures->draw_pressure_ceiling_milli_bar) {
            if (held) {
                *worst = pressure;
            }
            held = false;
        }
    }
    return held && delivering;
}

void setUp(void)
{
    hw_sim_reset();
    load_the_reference_description();
    load_the_reference_limits();
    load_the_reference_steam_control_declaration();
}

void tearDown(void) {}

/* --- The hardware seam the wand reaches the control unit through ----------- */

/// SOL-SIM-STEAM-BAND-SUSTAINED.C10: The steam knob's microswitch reaches the
/// control unit as a discrete reading.
///
/// The channel is asserted to carry the same present-or-absent and
/// valid-or-failed reporting discipline every other channel on this seam
/// already does, one condition at a time: nothing stood up reports absent
/// rather than a knob that is not turned, a sample that failed reports failed
/// and carries no value, and a trustworthy sample reports each of the two
/// discrete answers the seam spells. It is a channel of its own alongside the
/// analogue ones rather than folded into any of them, which is what the last
/// assertion establishes -- standing the knob up moves no other channel.
static void test_the_steam_knob_reaches_the_seam_as_a_discrete_reading(void)
{
    hw_sim_reset();

    hw_reading_t reading = hw_sensor_read(HW_SENSOR_STEAM_KNOB);
    TEST_ASSERT_EQUAL_MESSAGE(HW_READING_ABSENT, reading.status,
                              "a channel nobody stood up reported a knob that is not turned, "
                              "which is a different sentence");

    hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_FAILED, HW_READING_DISCRETE_SET);
    reading = hw_sensor_read(HW_SENSOR_STEAM_KNOB);
    TEST_ASSERT_EQUAL(HW_READING_FAILED, reading.status);
    TEST_ASSERT_EQUAL_INT32_MESSAGE(0, reading.value_milli,
                                    "a failed sample carried a value a consumer could act on");

    hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_CLEAR);
    reading = hw_sensor_read(HW_SENSOR_STEAM_KNOB);
    TEST_ASSERT_EQUAL(HW_READING_VALID, reading.status);
    TEST_ASSERT_EQUAL_INT32(HW_READING_DISCRETE_CLEAR, reading.value_milli);

    hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);
    reading = hw_sensor_read(HW_SENSOR_STEAM_KNOB);
    TEST_ASSERT_EQUAL(HW_READING_VALID, reading.status);
    TEST_ASSERT_EQUAL_INT32(HW_READING_DISCRETE_SET, reading.value_milli);

    /* And nothing else on the seam moved with it. */
    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        if (channel == (unsigned)HW_SENSOR_STEAM_KNOB) {
            continue;
        }
        TEST_ASSERT_EQUAL_MESSAGE(
            HW_READING_ABSENT, hw_sensor_read((hw_sensor_channel_t)channel).status,
            "standing the knob up moved another channel, so the knob is folded into one");
    }
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C10: The steam knob's microswitch reaches the
/// control unit as a discrete reading.
///
/// The bit reaching the control unit is asserted through the law rather than
/// only at the seam, because a channel nothing reads is a channel that could
/// be miswired without symptom. Each condition the seam can present the knob
/// in is put to the law and the law's own report of whether it has a draw to
/// serve is read back: only a trustworthy, set reading is a draw. A reading
/// between the two discrete answers is refused rather than rounded -- an
/// implementation reporting a half-made contact has not answered the question
/// this channel exists to answer, and taking it for a turned knob would start
/// feeding a block on the strength of it.
static void test_only_a_trustworthy_set_knob_reading_is_taken_for_a_draw(void)
{
    static const struct {
        hw_reading_status_t status;
        int32_t value_milli;
        bool drawing;
        const char *what;
    } CASES[] = {
        {HW_READING_ABSENT, 0, false, "nothing fitted read as a draw"},
        {HW_READING_FAILED, HW_READING_DISCRETE_SET, false, "a failed sample read as a draw"},
        {HW_READING_VALID, HW_READING_DISCRETE_CLEAR, false, "a shut wand read as a draw"},
        {HW_READING_VALID, HW_READING_DISCRETE_SET, true, "a turned wand did not read as a draw"},
        {HW_READING_VALID, HW_READING_DISCRETE_SET / 2, false,
         "a contact reported half made read as a draw"},
        {HW_READING_VALID, HW_READING_DISCRETE_SET * 2, false,
         "a reading outside the declared span read as a draw"},
    };

    for (size_t at = 0u; at < sizeof(CASES) / sizeof(CASES[0]); at++) {
        steam_control_state_t state;

        hw_sim_reset();
        TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                          declaration.ready_pressure_milli_bar);
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          declaration.ready_temperature_milli_c);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, CASES[at].status, CASES[at].value_milli);

        (void)steam_control_step(&state);

        bool drawing = true;
        TEST_ASSERT_TRUE(steam_control_drawing(&state, &drawing));
        TEST_ASSERT_EQUAL_MESSAGE(CASES[at].drawing, drawing, CASES[at].what);
    }
}

/* --- Which variable governs, and what an unbelievable reading does --------- */

/*
 * Stand the two analogue channels up directly and run one step, so a test can
 * move one reading at a time without a plant deciding what the other does.
 */
static uint16_t step_with(steam_control_state_t *state, bool knob, int32_t pressure_milli_bar,
                          int32_t temperature_milli_c)
{
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, pressure_milli_bar);
    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID, temperature_milli_c);
    hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID,
                      knob ? HW_READING_DISCRETE_SET : HW_READING_DISCRETE_CLEAR);
    (void)steam_control_step(state);
    hw_sim_advance_millis(STEP_INTERVAL_MS);
    return hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER);
}

/*
 * Open a draw the gate feeds -- the wand turned with the shut block at the
 * declared ready pressure and target -- and then run it for `steps` more steps
 * at the readings given, so a test can stand a fed draw up without a plant.
 */
static void open_a_fed_draw(steam_control_state_t *state, int32_t pressure_milli_bar,
                            int32_t temperature_milli_c, unsigned steps)
{
    (void)step_with(state, true, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP) > 0u,
                             "a draw opened at the ready pressure was not fed");
    for (unsigned step = 0u; step < steps; step++) {
        (void)step_with(state, true, pressure_milli_bar, temperature_milli_c);
    }
}

/* The middle of the declared band, which the pressure loop holds. */
static int32_t band_middle(const steam_control_declaration_t *figures)
{
    return (figures->draw_pressure_floor_milli_bar + figures->draw_pressure_ceiling_milli_bar) / 2;
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: The feed holds pressure and heater power
/// holds a declared superheat setpoint, and no pressure loop drives the heater.
///
/// The controlled variable is temperature while idle and pressure while a draw
/// is open. The switch is asserted on the same step the wand's report changes,
/// in both directions, against the law's own account of which variable it is
/// driving to. A caller that switched on the step after would spend the first
/// step of a draw -- the one the operator can least afford it in -- answering
/// the question the wand has already stopped asking.
static void test_the_controlled_variable_switches_on_the_step_the_draw_begins(void)
{
    steam_control_state_t state;
    steam_control_variable_t variable;

    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));

    (void)step_with(&state, false, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE(steam_control_variable(&state, &variable));
    TEST_ASSERT_EQUAL(STEAM_CONTROL_VARIABLE_TEMPERATURE, variable);

    (void)step_with(&state, true, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE(steam_control_variable(&state, &variable));
    TEST_ASSERT_EQUAL_MESSAGE(STEAM_CONTROL_VARIABLE_PRESSURE, variable,
                              "the loop was still driving to temperature on the step the draw "
                              "began");

    (void)step_with(&state, false, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE(steam_control_variable(&state, &variable));
    TEST_ASSERT_EQUAL_MESSAGE(STEAM_CONTROL_VARIABLE_TEMPERATURE, variable,
                              "the loop was still driving to pressure on the step the draw ended");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: The feed holds pressure and heater power
/// holds a declared superheat setpoint, and no pressure loop drives the heater.
///
/// Three instances share one history -- a draw opened at ready and run at the
/// middle of the band -- with the feedforward declared at nothing so the heater
/// answers its error alone. At the probe step one is handed the pressure moved
/// alone, and a second the same moved pressure with the casting moved by
/// exactly what keeps the law's own superheat estimate where the unmoved
/// instance's is. If the heater answers superheat and nothing else, the second's
/// duty is the unmoved instance's, though its pressure error is a fifth of a bar
/// different; a pressure term anywhere in the heater command would part them.
/// The first is the control that the probe is sensitive at all: the same
/// pressure move with the casting held changes the estimate and so the duty.
///
/// The feed, on the other hand, answers pressure and not the casting: the moved
/// pressure moves it, and the moved casting beside it leaves it where the
/// pressure alone put it.
///
/// The ready target is declared low here and the casting held above it, so the
/// superheat term is the one that binds the heater in the probe: with the
/// casting at or under ready the setpoint's floor would leave the ready term in
/// charge and the probe would say nothing about the superheat.
static void test_the_heater_answers_superheat_and_never_pressure_error(void)
{
    steam_control_declaration_t altered = declaration;
    altered.feed_load_gain_milli_permille_per_permille = 0;
    altered.ready_temperature_milli_c = 120000;
    const steam_control_declaration_t figures = re_declared(&altered);
    const int32_t middle = band_middle(&figures);
    const int32_t moved = middle + 200;
    const int32_t casting = 131500;

    steam_control_state_t unmoved;
    steam_control_state_t pressure_only;
    steam_control_state_t both_moved;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&unmoved, &limits, &figures, &parameters, &budget));
    open_a_fed_draw(&unmoved, middle, casting, 300u);
    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&pressure_only, &limits, &figures, &parameters, &budget));
    open_a_fed_draw(&pressure_only, middle, casting, 300u);
    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&both_moved, &limits, &figures, &parameters, &budget));
    open_a_fed_draw(&both_moved, middle, casting, 300u);

    float unmoved_estimate = 0.0f;
    const uint16_t unmoved_duty = step_with(&unmoved, true, middle, casting);
    const uint16_t unmoved_feed = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
    TEST_ASSERT_TRUE(steam_control_outlet_superheat(&unmoved, &unmoved_estimate));

    float pressure_only_estimate = 0.0f;
    const uint16_t pressure_only_duty = step_with(&pressure_only, true, moved, casting);
    const uint16_t moved_feed = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
    TEST_ASSERT_TRUE(steam_control_outlet_superheat(&pressure_only, &pressure_only_estimate));
    TEST_ASSERT_TRUE_MESSAGE(moved_feed < unmoved_feed,
                             "a higher pressure did not take the feed down, so the feed is not "
                             "holding pressure");
    TEST_ASSERT_TRUE_MESSAGE(pressure_only_duty != unmoved_duty,
                             "moving the pressure moved neither the estimate nor the duty, so the "
                             "probe below is not sensitive to anything");

    /*
     * The casting that gives the moved instance the unmoved one's estimate, at
     * the feed the moved pressure commands, found by narrowing on the relation
     * the law itself reads.
     */
    float low_c = (float)casting / 1000.0f;
    float high_c = low_c + 40.0f;
    for (int narrowing = 0; narrowing < 60; narrowing++) {
        const float middle_c = 0.5f * (low_c + high_c);
        float estimate = 0.0f;
        TEST_ASSERT_TRUE(plant_model_least_outlet_superheat(&parameters, &budget, middle_c,
                                                            (float)moved / 1000.0f, moved_feed,
                                                            &estimate));
        if (estimate < unmoved_estimate) {
            low_c = middle_c;
        } else {
            high_c = middle_c;
        }
    }
    const int32_t compensating = (int32_t)lroundf(high_c * 1000.0f);

    float both_moved_estimate = 0.0f;
    const uint16_t both_moved_duty = step_with(&both_moved, true, moved, compensating);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(moved_feed, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "moving the casting moved the feed, so the feed answers "
                                     "something besides pressure");
    TEST_ASSERT_TRUE(steam_control_outlet_superheat(&both_moved, &both_moved_estimate));
    TEST_ASSERT_FLOAT_WITHIN(0.01f, unmoved_estimate, both_moved_estimate);
    TEST_ASSERT_UINT16_WITHIN_MESSAGE(1u, unmoved_duty, both_moved_duty,
                                      "a fifth of a bar of pressure error moved the heater with the "
                                      "superheat estimate held, so a pressure loop drives it");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C2: A steam pressure reading outside
/// physically plausible bounds is rejected rather than acted on.
///
/// A draw is brought to a settled duty and each implausible reading in turn is
/// injected mid-draw: one below zero absolute, one above the block's declared
/// mechanical rating, and the two conditions the seam reports when it has no
/// figure at all. What is asserted is that nothing moves -- neither the duty
/// nor the feed -- rather than merely that the machine survives: a law that
/// abandoned its last trusted value would drive toward whatever the absurd
/// figure implied, and one that cut feed on a single bad sample would chop the
/// operator's draw off and back on again. The step still reports itself
/// sensor-invalid, because acting on what was last believed is not the same as
/// having observed anything.
static void test_an_implausible_pressure_reading_mid_draw_is_rejected_rather_than_acted_on(void)
{
    static const struct {
        hw_reading_status_t status;
        bool below_declared_low;
        const char *what;
    } CASES[] = {
        {HW_READING_VALID, true, "a reading below zero absolute"},
        {HW_READING_VALID, false, "a reading above the declared mechanical rating"},
        {HW_READING_FAILED, false, "a sample that failed"},
        {HW_READING_ABSENT, false, "a channel reporting nothing is fitted"},
    };

    for (size_t at = 0u; at < sizeof(CASES) / sizeof(CASES[0]); at++) {
        steam_control_state_t state;
        const int32_t in_band = (declaration.draw_pressure_floor_milli_bar +
                                 declaration.draw_pressure_ceiling_milli_bar) /
                                2;

        hw_sim_reset();
        TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));

        /* A settled draw, opened at ready and held at the middle of the band. */
        open_a_fed_draw(&state, in_band, declaration.ready_temperature_milli_c, 4000u);

        const uint16_t duty_before = hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER);
        const uint16_t feed_before = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        TEST_ASSERT_TRUE_MESSAGE(feed_before > 0u,
                                 "the draw was not feeding, so there is nothing for an absurd "
                                 "reading to have disturbed");

        const int32_t absurd = CASES[at].below_declared_low
                                   ? limits.low_milli[HW_SENSOR_STEAM_PRESSURE] - 1
                                   : limits.high_milli[HW_SENSOR_STEAM_PRESSURE] + 1;
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, CASES[at].status, absurd);
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          declaration.ready_temperature_milli_c);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);

        TEST_ASSERT_EQUAL_MESSAGE(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&state),
                                  CASES[at].what);
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(duty_before,
                                         hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
                                         CASES[at].what);
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(feed_before, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                         CASES[at].what);
    }
}

/* --- Everything the declaration decides ------------------------------------ */

/// SOL-SIM-STEAM-BAND-SUSTAINED.C3: The ready temperature target and the
/// draw-time pressure band are declared data with recorded origins.
///
/// Two runs of the same control law against the same machine, differing in
/// nothing but a declared ready temperature read at run time, settle at the
/// two different temperatures they were told to. Nothing is rebuilt between
/// them. A target compiled into the source would put both runs at the same
/// place.
static void test_the_declared_ready_target_is_where_the_loop_settles(void)
{
    static const int32_t TARGETS[] = {127000, 137000};
    float settled[2] = {0.0f, 0.0f};

    for (size_t run = 0u; run < sizeof(TARGETS) / sizeof(TARGETS[0]); run++) {
        steam_control_declaration_t altered = declaration;
        altered.ready_temperature_milli_c = TARGETS[run];
        const steam_control_declaration_t figures = re_declared(&altered);

        bring_the_loop_up(&parameters, &figures, ready_target_c(&figures));
        hold_ready_for(SETTLE_SECONDS);
        settled[run] = truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C);

        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(READY_TOLERANCE_C, ready_target_c(&figures), settled[run],
                                         "the loop did not hold the declared ready target");
    }

    TEST_ASSERT_TRUE_MESSAGE(settled[1] > settled[0] + 5.0f,
                             "two declared targets ten degrees apart held the block at the same "
                             "temperature, so the target is not being read");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C3: The ready temperature target and the
/// draw-time pressure band are declared data with recorded origins.
///
/// The band's half of the same criterion. The same draw against the same
/// machine is judged against two declared bands, and the suite's own verdict
/// moves with the declaration: the shipped band accepts the run and a band
/// declared elsewhere -- narrow, and placed where this machine does not go --
/// refuses it. Nothing about the machine or the law changed between them,
/// which is what makes the verdict the declaration's and not the source's.
static void test_the_declared_band_decides_which_draws_the_suite_accepts(void)
{
    int32_t worst = 0;

    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(20u, 1.0f);

    TEST_ASSERT_TRUE_MESSAGE(in_band_from_first_delivery(&declaration, &worst),
                             "the shipped band did not accept a draw the loop is meant to hold");

    steam_control_declaration_t elsewhere = declaration;
    elsewhere.draw_pressure_floor_milli_bar = 3000;
    elsewhere.draw_pressure_ceiling_milli_bar = 3200;
    const steam_control_declaration_t narrow = re_declared(&elsewhere);

    TEST_ASSERT_FALSE_MESSAGE(in_band_from_first_delivery(&narrow, &worst),
                              "a band this machine never reaches accepted the same run, so the "
                              "verdict does not follow the declaration");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C4: The control law's band and gains are
/// inputs it reads rather than constants compiled into it.
///
/// One declared gain is moved and the suite's own pass-fail boundary moves
/// with it, with no control law rebuilt between the two arms. The gain chosen
/// is the pressure loop's proportional gain, because the orifice law gives the
/// pressure no lag to hide behind: at the shipped figure a step of the loop
/// answers a little over half an error and the draw stays in band, and at a
/// thousand times that the first hundredth of a bar past the middle of the band
/// takes the feed to nothing at once -- the fall is not rise-limited -- which
/// drops the pressure through the floor, and the same run fails.
///
/// Everything else is held identical -- the same machine, the same draw, the
/// same duration, the same band -- so the only thing that could have moved the
/// verdict is the figure that was declared differently.
static void test_a_declared_gain_moves_the_pass_fail_boundary(void)
{
    int32_t worst = 0;

    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(30u, 1.0f);
    TEST_ASSERT_TRUE_MESSAGE(in_band_from_first_delivery(&declaration, &worst),
                             "the shipped pressure gain did not hold the band");

    steam_control_declaration_t altered = declaration;
    altered.feed_gain_milli_permille_per_bar = declaration.feed_gain_milli_permille_per_bar * 1000;
    const steam_control_declaration_t overstated = re_declared(&altered);

    bring_the_loop_up(&parameters, &overstated, ready_target_c(&overstated));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(30u, 1.0f);
    TEST_ASSERT_FALSE_MESSAGE(in_band_from_first_delivery(&overstated, &worst),
                              "a pressure gain a thousand times the shipped one still held the band, so "
                              "the gain is not being read");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C3: The ready temperature target and the
/// draw-time pressure band are declared data with recorded origins.
///
/// SOL-SIM-STEAM-BAND-SUSTAINED.C4: The control law's band and gains are
/// inputs it reads rather than constants compiled into it.
///
/// The grammar's own refusals, table-driven across every fault it can report:
/// a line with no separator, one naming nothing this build reads, a figure
/// given twice, one outside the range this build admits, one in the wrong
/// unit, one with no account of where it came from, a band whose floor sits at
/// or above its own ceiling, and -- one case per figure -- a declaration that
/// simply leaves that figure out. The last of those is the point of the table
/// being generated rather than written: a figure added to the record and
/// forgotten here would be one nothing establishes is required, and an
/// undeclared load-bearing figure silently taken as nothing is exactly what
/// "declared data" exists to prevent.
static void test_the_declaration_grammar_refuses_what_it_must(void)
{
    static const struct {
        const char *text;
        steam_control_declaration_fault_t fault;
    } CASES[] = {
        {"ready-pressure-bar 900 milli-bar @estimated an account\n",
         STEAM_CONTROL_DECLARATION_MALFORMED},
        {"ready-pressure-bar = @estimated an account\n", STEAM_CONTROL_DECLARATION_MALFORMED},
        {"boiler-pressure-bar = 900 milli-bar @estimated an account\n",
         STEAM_CONTROL_DECLARATION_UNKNOWN},
        {"ready-pressure-bar = 900 milli-bar @estimated an account\n"
         "ready-pressure-bar = 950 milli-bar @estimated a second account\n",
         STEAM_CONTROL_DECLARATION_DUPLICATE},
        {"ready-pressure-bar = 20000 milli-bar @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"feed-rise-limit = 100001 permille-per-s @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"draw-start-feed = 0 permille @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"feed-ceiling = 1001 permille @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"superheat-setpoint = -1 milli-k @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"ready-temperature-gain = 0 milli-permille-per-k @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"ready-pressure-bar = 900 milli-c @estimated an account\n",
         STEAM_CONTROL_DECLARATION_UNIT_MISMATCH},
        {"feed-pressure-gain = 20000 milli-permille-per-k @estimated an account\n",
         STEAM_CONTROL_DECLARATION_UNIT_MISMATCH},
        {"superheat-setpoint = 5000 milli-c @estimated an account\n",
         STEAM_CONTROL_DECLARATION_UNIT_MISMATCH},
        {"ready-pressure-bar = 900 milli-bar\n", STEAM_CONTROL_DECLARATION_ORIGIN},
        {"ready-pressure-bar = 900 milli-bar @invented an account\n",
         STEAM_CONTROL_DECLARATION_ORIGIN},
        {"ready-pressure-bar = 900 milli-bar @estimated\n", STEAM_CONTROL_DECLARATION_ORIGIN},
        {"", STEAM_CONTROL_DECLARATION_MISSING},
    };

    for (size_t at = 0u; at < sizeof(CASES) / sizeof(CASES[0]); at++) {
        steam_control_declaration_t built;
        steam_control_declaration_error_t fault;
        TEST_ASSERT_FALSE_MESSAGE(declaration_from(CASES[at].text, &built, &fault),
                                  CASES[at].text);
        TEST_ASSERT_EQUAL_MESSAGE(CASES[at].fault, fault.fault, CASES[at].text);
    }

    /* A band that admits nothing, with both edges individually admissible. */
    steam_control_declaration_t inverted = declaration;
    inverted.draw_pressure_floor_milli_bar = declaration.draw_pressure_ceiling_milli_bar;
    steam_control_declaration_t built;
    steam_control_declaration_error_t fault;
    TEST_ASSERT_FALSE_MESSAGE(declaration_from(text_for(&inverted), &built, &fault),
                              "a floor at its own ceiling was accepted");
    TEST_ASSERT_EQUAL(STEAM_CONTROL_DECLARATION_BAND_INVERTED, fault.fault);

    /*
     * One arm per figure: the shipped declaration with that figure's line
     * removed. The lines are dropped by name from the rendered text, so a
     * figure added to the record and to text_for is covered here without
     * anything else being edited -- and one added to the record alone would
     * fail the loader's own static assertion before reaching this.
     */
    static const char *const WORDS[] = {
        STEAM_CONTROL_DECLARATION_READY_PRESSURE_WORD,
        STEAM_CONTROL_DECLARATION_READY_TEMPERATURE_WORD,
        STEAM_CONTROL_DECLARATION_DRAW_FLOOR_WORD,
        STEAM_CONTROL_DECLARATION_DRAW_CEILING_WORD,
        STEAM_CONTROL_DECLARATION_DRAW_START_FEED_WORD,
        STEAM_CONTROL_DECLARATION_FEED_CEILING_WORD,
        STEAM_CONTROL_DECLARATION_FEED_RISE_LIMIT_WORD,
        STEAM_CONTROL_DECLARATION_SUPERHEAT_SETPOINT_WORD,
        STEAM_CONTROL_DECLARATION_READY_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_SUPERHEAT_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_SUPERHEAT_INTEGRAL_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_FEED_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_FEED_INTEGRAL_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_FEED_LOAD_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_STANDING_LOAD_WORD,
    };

    for (size_t at = 0u; at < sizeof(WORDS) / sizeof(WORDS[0]); at++) {
        static char without[4096];
        const char *whole = text_for(&declaration);
        size_t written = 0u;

        while (*whole != '\0') {
            const char *line_end = strchr(whole, '\n');
            const size_t line_length = (size_t)(line_end - whole) + 1u;

            if (strncmp(whole, WORDS[at], strlen(WORDS[at])) != 0) {
                TEST_ASSERT_TRUE(written + line_length < sizeof(without));
                memcpy(&without[written], whole, line_length);
                written += line_length;
            }
            whole = line_end + 1;
        }
        without[written] = '\0';

        TEST_ASSERT_FALSE_MESSAGE(declaration_from(without, &built, &fault), WORDS[at]);
        TEST_ASSERT_EQUAL_MESSAGE(STEAM_CONTROL_DECLARATION_MISSING, fault.fault, WORDS[at]);
        TEST_ASSERT_EQUAL_STRING(WORDS[at], fault.name);
    }
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: A declaration whose draw-start level
/// exceeds its feed ceiling is refused as its own fault, not reduced to the
/// ceiling.
///
/// Each figure is inside its own range, so what is wrong is the pair. A start at
/// the ceiling is accepted and a start one permille above it is refused naming
/// the start, and the law opened on the accepted declaration starts the feed at
/// exactly the start level, which is the ceiling here.
static void test_a_draw_start_above_the_feed_ceiling_is_refused_as_its_own_fault(void)
{
    steam_control_declaration_t figures = declaration;
    steam_control_declaration_t built;
    steam_control_declaration_error_t fault;

    figures.draw_start_feed_permille = figures.feed_ceiling_permille;
    TEST_ASSERT_TRUE_MESSAGE(declaration_from(text_for(&figures), &built, &fault),
                             "a start at its ceiling was refused");
    TEST_ASSERT_EQUAL_INT32(figures.feed_ceiling_permille, built.draw_start_feed_permille);

    figures.draw_start_feed_permille = figures.feed_ceiling_permille + 1;
    TEST_ASSERT_FALSE_MESSAGE(declaration_from(text_for(&figures), &built, &fault),
                              "a start above its ceiling was accepted");
    TEST_ASSERT_EQUAL(STEAM_CONTROL_DECLARATION_FEED_START_ABOVE_CEILING, fault.fault);
    TEST_ASSERT_EQUAL_STRING(STEAM_CONTROL_DECLARATION_DRAW_START_FEED_WORD, fault.name);

    /* A start inside its range and a ceiling inside its range, however far apart. */
    figures.draw_start_feed_permille = figures.feed_ceiling_permille + 400;
    TEST_ASSERT_FALSE(declaration_from(text_for(&figures), &built, &fault));
    TEST_ASSERT_EQUAL(STEAM_CONTROL_DECLARATION_FEED_START_ABOVE_CEILING, fault.fault);
}

/*
 * A law brought up on a working declaration and run until the element is
 * driven, so that the commands a refused initialisation must leave off are
 * seen to have been on. Returns whether the element was on.
 */
static bool heating_state_on(steam_control_state_t *state)
{
    hw_sim_reset();
    if (!steam_control_init(state, &limits, &declaration, &parameters, &budget)) {
        return false;
    }
    for (unsigned step = 0u; step < 20u; step++) {
        (void)step_with(state, false, 0, 20000);
    }
    return hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER) > 0u;
}

/*
 * Handed to steam_control_init, the declaration is refused with every command
 * left off and the law unconfigured: the element that was driven is not, and a
 * step answers an invalid sensor rather than running a law no one admitted.
 */
static void assert_init_refuses(const steam_control_declaration_t *figures, const char *what)
{
    steam_control_state_t working;
    steam_control_state_t refused;

    TEST_ASSERT_TRUE_MESSAGE(heating_state_on(&working), "no command was on to be left off");
    TEST_ASSERT_FALSE_MESSAGE(steam_control_init(&refused, &limits, figures, &parameters, &budget),
                              what);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER), what);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP), what);
    TEST_ASSERT_EQUAL_MESSAGE(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&refused), what);
    TEST_ASSERT_FALSE_MESSAGE(steam_control_declaration_admissible(figures, NULL), what);
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: A declaration whose draw-start level
/// exceeds its feed ceiling is refused as its own fault, at load and again when
/// the law is initialised, which refuses it and commands nothing, and is not
/// reduced to the ceiling.
///
/// A declaration built by hand and never read from a file is held to what a file
/// is. A start above the ceiling, by one permille and by a long way, is refused
/// by the law's own initialisation; a start at the ceiling is accepted and the
/// law opened on it starts the feed at exactly that level.
static void test_a_hand_built_declaration_with_the_start_above_the_ceiling_is_refused_by_the_law(void)
{
    steam_control_declaration_t figures = declaration;
    steam_control_state_t state;
    steam_control_declaration_error_t fault;

    figures.draw_start_feed_permille = figures.feed_ceiling_permille;
    hw_sim_reset();
    TEST_ASSERT_TRUE_MESSAGE(steam_control_init(&state, &limits, &figures, &parameters, &budget),
                             "a start at its ceiling was refused");
    TEST_ASSERT_TRUE(steam_control_declaration_admissible(&figures, NULL));

    const int32_t above[] = {figures.feed_ceiling_permille + 1, figures.feed_ceiling_permille + 400,
                             ACTUATION_FULL_SCALE};
    for (size_t at = 0u; at < sizeof(above) / sizeof(above[0]); at++) {
        if (above[at] <= declaration.feed_ceiling_permille) {
            continue;
        }
        figures.draw_start_feed_permille = above[at];
        assert_init_refuses(&figures, "a start above its ceiling");
        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_FALSE(steam_control_declaration_admissible(&figures, &fault));
        TEST_ASSERT_EQUAL(STEAM_CONTROL_DECLARATION_FEED_START_ABOVE_CEILING, fault.fault);
        TEST_ASSERT_EQUAL_STRING(STEAM_CONTROL_DECLARATION_DRAW_START_FEED_WORD, fault.name);
        TEST_ASSERT_EQUAL_UINT32(0u, fault.line);
    }
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: A declaration whose draw-start level
/// exceeds its feed ceiling is refused as its own fault, at load and again when
/// the law is initialised, which refuses it and commands nothing, and is not
/// reduced to the ceiling.
///
/// The band's floor at or above its ceiling describes a band no pressure is ever
/// inside, so it is refused by the law's initialisation as it is by the loader:
/// at equality, one milli-bar above and by a long way, each naming the floor.
static void test_a_hand_built_declaration_with_the_floor_at_or_above_the_ceiling_is_refused_by_the_law(void)
{
    steam_control_declaration_t figures = declaration;
    steam_control_declaration_error_t fault;

    const int32_t floors[] = {declaration.draw_pressure_ceiling_milli_bar,
                              declaration.draw_pressure_ceiling_milli_bar + 1,
                              declaration.draw_pressure_ceiling_milli_bar + 500};
    for (size_t at = 0u; at < sizeof(floors) / sizeof(floors[0]); at++) {
        figures.draw_pressure_floor_milli_bar = floors[at];
        assert_init_refuses(&figures, "a floor at or above its ceiling");
        memset(&fault, 0, sizeof(fault));
        TEST_ASSERT_FALSE(steam_control_declaration_admissible(&figures, &fault));
        TEST_ASSERT_EQUAL(STEAM_CONTROL_DECLARATION_BAND_INVERTED, fault.fault);
        TEST_ASSERT_EQUAL_STRING(STEAM_CONTROL_DECLARATION_DRAW_FLOOR_WORD, fault.name);
    }

    /* One milli-bar under the ceiling is a band, and is accepted. */
    figures.draw_pressure_floor_milli_bar = declaration.draw_pressure_ceiling_milli_bar - 1;
    TEST_ASSERT_TRUE(steam_control_declaration_admissible(&figures, NULL));
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: A declaration whose draw-start level
/// exceeds its feed ceiling is refused as its own fault, at load and again when
/// the law is initialised, which refuses it and commands nothing, and is not
/// reduced to the ceiling.
///
/// A figure outside the range this build admits for it is as little a
/// declaration as a pair that cannot stand, and is refused by the law's
/// initialisation wherever the record came from: every figure in turn, written
/// as the largest and the smallest number the record holds and as below zero.
/// The refusal names the figure, and a null declaration is refused.
static void test_a_hand_built_declaration_with_a_figure_out_of_range_is_refused_by_the_law(void)
{
    const size_t figure_count = sizeof(declaration) / sizeof(int32_t);
    const int32_t hostile[] = {INT32_MAX, INT32_MIN, -1};
    steam_control_declaration_error_t fault;

    TEST_ASSERT_EQUAL_UINT(0u, sizeof(declaration) % sizeof(int32_t));
    for (size_t at = 0u; at < figure_count; at++) {
        for (size_t v = 0u; v < sizeof(hostile) / sizeof(hostile[0]); v++) {
            steam_control_declaration_t figures = declaration;
            char message[64];

            ((int32_t *)(void *)&figures)[at] = hostile[v];
            (void)snprintf(message, sizeof(message), "figure %u written as %ld", (unsigned)at,
                           (long)hostile[v]);
            assert_init_refuses(&figures, message);
            memset(&fault, 0, sizeof(fault));
            TEST_ASSERT_FALSE_MESSAGE(steam_control_declaration_admissible(&figures, &fault),
                                      message);
            TEST_ASSERT_EQUAL_MESSAGE(STEAM_CONTROL_DECLARATION_OUT_OF_RANGE, fault.fault, message);
            TEST_ASSERT_TRUE_MESSAGE(fault.name[0] != '\0', message);
        }
    }

    TEST_ASSERT_FALSE(steam_control_declaration_admissible(NULL, NULL));
    TEST_ASSERT_TRUE(steam_control_declaration_admissible(&declaration, NULL));
}

/* --- Holding the band, and coming back afterwards -------------------------- */

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: The feed holds pressure and heater power
/// holds a declared superheat setpoint, and no pressure loop drives the heater.
///
/// Four durations from a brief pull to an extended one, each against three
/// machines: the description's own restriction coefficient and that figure at
/// both ends of the error the description declares on it. That coefficient is
/// what the orifice law turns the steam made into pressure through, and it is
/// among the loosest figures thermoblock.params carries, so a run at one
/// assumed-exact value would be testing the guess rather than the loop. On
/// every one the pressure is in the declared band from the first steam actually
/// delivered to the end of the draw.
///
/// On the description's own machine the superheat at the modelled outlet is at
/// or above the declared setpoint on every step that made steam, and the law's
/// own estimate of it, which it reads nothing from the truth plant to form, is
/// the least the declared error admits: never above the plant's figure, and
/// within that error of it.
static void test_pressure_and_superheat_hold_for_draws_of_every_duration(void)
{
    static const unsigned DURATIONS[] = {3u, 10u, 30u, 60u};
    float assumed_error = 0.0f;

    TEST_ASSERT_TRUE_MESSAGE(
        plant_parameter_budget_for(&budget, RESTRICTION_COEFFICIENT, &assumed_error),
        "the description declares no error on the coefficient this criterion is tested across");
    TEST_ASSERT_TRUE_MESSAGE(assumed_error > 0.0f,
                             "the description declares that coefficient exact, which is not what "
                             "its own account says");

    const float FACTORS[] = {1.0f - assumed_error, 1.0f, 1.0f + assumed_error};
    const float setpoint_k = (float)declaration.superheat_setpoint_milli_k / 1000.0f;
    float outlet_error = 0.0f;
    TEST_ASSERT_TRUE(
        plant_parameter_budget_for(&budget, "steam.outlet_drop_k_s_per_ml", &outlet_error));

    for (size_t corner = 0u; corner < sizeof(FACTORS) / sizeof(FACTORS[0]); corner++) {
        const plant_parameters_t machine =
            machine_with_scaled(RESTRICTION_COEFFICIENT, FACTORS[corner]);

        for (size_t which = 0u; which < sizeof(DURATIONS) / sizeof(DURATIONS[0]); which++) {
            char message[160];
            int32_t worst = 0;

            bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
            hold_ready_for(SETTLE_SECONDS);
            draw_for(DURATIONS[which], 1.0f);

            const bool held = in_band_from_first_delivery(&declaration, &worst);
            (void)snprintf(message, sizeof(message),
                           "a %u second draw at %.2f times the declared restriction left the "
                           "band at %d milli-bar",
                           DURATIONS[which], (double)FACTORS[corner], worst);
            TEST_ASSERT_TRUE_MESSAGE(held, message);

            if (FACTORS[corner] != 1.0f) {
                continue;
            }
            for (size_t at = 0u; at < sample_count; at++) {
                if (samples[at].feed_permille == 0u) {
                    continue;
                }
                (void)snprintf(message, sizeof(message),
                               "a %u second draw left the outlet at %.3f K of superheat at %u ms, "
                               "below the %.3f K setpoint",
                               DURATIONS[which], (double)samples[at].superheat_k,
                               (unsigned)samples[at].at_millis, (double)setpoint_k);
                TEST_ASSERT_TRUE_MESSAGE(samples[at].superheat_k >= setpoint_k, message);
                TEST_ASSERT_TRUE_MESSAGE(samples[at].estimated,
                                         "a fed step formed no estimate of the superheat");
                /*
                 * The estimate is read against the pressure the law was handed,
                 * which is the step before's, and the plant's after the step; so
                 * it is judged from the second fed step on, once the feed is
                 * steady enough that the two pressures agree to within the
                 * actuator's resolution.
                 */
                if (at > 0u && samples[at - 1u].feed_permille == samples[at].feed_permille) {
                    const float made_ml_per_s = nominal_of("steam.feed_flow_ml_per_s") *
                                                (float)samples[at].feed_permille / 1000.0f;
                    const float admitted_k =
                        outlet_error * nominal_of("steam.outlet_drop_k_s_per_ml") * made_ml_per_s;

                    TEST_ASSERT_TRUE_MESSAGE(samples[at].estimate_k <= samples[at].superheat_k + 0.01f,
                                             "the law's estimate claimed more superheat than the "
                                             "plant's outlet carries");
                    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.05f, samples[at].superheat_k - admitted_k,
                                                     samples[at].estimate_k,
                                                     "the law's estimate is not the plant's "
                                                     "outlet superheat taken at the cool end of "
                                                     "the declared outlet error");
                }
            }
        }
    }
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: Superheat stays at or above its setpoint
/// for the whole draw -- of any duration within the declared model-error
/// tolerance.
///
/// The coefficients that decide the superheat are the element's power, the
/// block's thermal mass and loss, the drop from casting to outlet, and the
/// restriction the pressure is made through. Each is taken to both ends of the
/// error the description declares for it, by the same corner mechanism the
/// restriction sweep above uses -- a factor on the described coefficient, the
/// others where the description puts them -- and each machine is drawn on for a
/// brief, a long and an extended duration. On every step that fed the block, the
/// plant's superheat at the modelled outlet is at or above the declared setpoint.
static void test_superheat_holds_the_setpoint_across_the_error_ends_of_every_coefficient_that_decides_it(void)
{
    static const char *const DECIDING[] = {"steam.heater_power_w", "steam.thermal_mass_j_per_k",
                                           "steam.loss_w_per_k", "steam.outlet_drop_k_s_per_ml",
                                           RESTRICTION_COEFFICIENT};
    static const unsigned DURATIONS[] = {3u, 30u, 60u};
    const float setpoint_k = (float)declaration.superheat_setpoint_milli_k / 1000.0f;
    static char report[2048];
    size_t shortfalls = 0u;

    report[0] = '\0';
    for (size_t k = 0u; k < sizeof(DECIDING) / sizeof(DECIDING[0]); k++) {
        float assumed = 0.0f;

        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_budget_for(&budget, DECIDING[k], &assumed),
                                 DECIDING[k]);
        TEST_ASSERT_TRUE_MESSAGE(assumed > 0.0f, DECIDING[k]);

        for (size_t end = 0u; end < 2u; end++) {
            const float factor = end == 0u ? 1.0f - assumed : 1.0f + assumed;
            const plant_parameters_t machine = machine_with_scaled(DECIDING[k], factor);

            for (size_t which = 0u; which < sizeof(DURATIONS) / sizeof(DURATIONS[0]); which++) {
                float least_k = INFINITY;
                unsigned least_at_ms = 0u;

                bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
                hold_ready_for(SETTLE_SECONDS);
                draw_for(DURATIONS[which], 1.0f);

                for (size_t at = 0u; at < sample_count; at++) {
                    if (samples[at].feed_permille != 0u && samples[at].superheat_k < least_k) {
                        least_k = samples[at].superheat_k;
                        least_at_ms = (unsigned)samples[at].at_millis;
                    }
                }
                if (least_k < setpoint_k) {
                    /* Every machine that leaves the setpoint is listed, not only the first. */
                    shortfalls += (size_t)snprintf(
                        &report[shortfalls], sizeof(report) - shortfalls,
                        "%s at %.3f times its description: %.3f K at %u ms in a %u second draw; ",
                        DECIDING[k], (double)factor, (double)least_k, least_at_ms, DURATIONS[which]);
                    if (shortfalls >= sizeof(report)) {
                        shortfalls = sizeof(report) - 1u;
                    }
                }
            }
        }
    }
    TEST_ASSERT_EQUAL_STRING_MESSAGE("", report,
                                     "the outlet superheat fell below the declared setpoint on the "
                                     "machines listed");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: During a draw the steam control law
/// drives the feed pump to hold measured pressure inside the declared band and
/// drives heater power to hold the modelled outlet superheat at a declared
/// setpoint carrying its origin; superheat stays at or above its setpoint for
/// the whole draw, with each coefficient that decides superheat taken alone to
/// each end of its declared error and the joint dependences the description
/// states taken together as the worst-case margin convention sets out, and
/// stays above zero at every corner the description's error admits, the joint
/// ends included.
///
/// Every one of the thirty-two combinations of the five deciding coefficients'
/// ends, drawn on for a brief and a long draw: sixty-four closed-loop runs,
/// each after a settle long enough for the weakest corner to reach the ready
/// pressure, which every run is asserted to have been fed after. On every step that fed the block the
/// plant's superheat at the modelled outlet is above zero, the dryness floor.
static void test_superheat_stays_above_zero_at_every_joint_corner_of_the_deciding_coefficients(void)
{
    static const char *const DECIDING[] = {"steam.heater_power_w", "steam.thermal_mass_j_per_k",
                                           "steam.loss_w_per_k", "steam.outlet_drop_k_s_per_ml",
                                           RESTRICTION_COEFFICIENT};
    enum { COEFFICIENTS = sizeof(DECIDING) / sizeof(DECIDING[0]) };
    static const unsigned DURATIONS[] = {3u, 30u};
    float assumed[COEFFICIENTS];
    static char report[2048];
    size_t shortfalls = 0u;

    for (size_t k = 0u; k < COEFFICIENTS; k++) {
        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_budget_for(&budget, DECIDING[k], &assumed[k]),
                                 DECIDING[k]);
        TEST_ASSERT_TRUE_MESSAGE(assumed[k] > 0.0f, DECIDING[k]);
    }

    report[0] = '\0';
    for (unsigned corner = 0u; corner < (1u << COEFFICIENTS); corner++) {
        float factors[COEFFICIENTS];

        for (size_t k = 0u; k < COEFFICIENTS; k++) {
            factors[k] = ((corner >> k) & 1u) != 0u ? 1.0f + assumed[k] : 1.0f - assumed[k];
        }
        const plant_parameters_t machine = machine_with_all_scaled(DECIDING, factors, COEFFICIENTS);

        for (size_t which = 0u; which < sizeof(DURATIONS) / sizeof(DURATIONS[0]); which++) {
            float least_k = INFINITY;
            unsigned least_at_ms = 0u;

            bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
            hold_ready_for(JOINT_SETTLE_SECONDS);
            draw_for(DURATIONS[which], 1.0f);
            TEST_ASSERT_NOT_NULL_MESSAGE(first_delivery(),
                                         "a corner was starved for the whole draw, so it was "
                                         "passed without being tested");

            for (size_t at = 0u; at < sample_count; at++) {
                if (samples[at].feed_permille != 0u && samples[at].superheat_k < least_k) {
                    least_k = samples[at].superheat_k;
                    least_at_ms = (unsigned)samples[at].at_millis;
                }
            }
            if (!(least_k > 0.0f)) {
                shortfalls += (size_t)snprintf(
                    &report[shortfalls], sizeof(report) - shortfalls,
                    "corner %u: %.3f K at %u ms in a %u second draw; ", corner, (double)least_k,
                    least_at_ms, DURATIONS[which]);
                if (shortfalls >= sizeof(report)) {
                    shortfalls = sizeof(report) - 1u;
                }
            }
        }
    }
    TEST_ASSERT_EQUAL_STRING_MESSAGE("", report,
                                     "the outlet superheat reached zero at the joint corners "
                                     "listed");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: During a draw the steam control law
/// drives the feed pump to hold measured pressure inside the declared band and
/// drives heater power to hold the modelled outlet superheat at or above a
/// declared setpoint carrying its origin, the setpoint being a floor: while the
/// superheat stands above it the heater holds the casting at the declared ready
/// temperature.
///
/// A nominal machine is drawn on for sixty seconds at the middle of what it can
/// make. The superheat has margin throughout, so the setpoint is not what the
/// heater answers, and the casting stays within the ready tolerance of the ready
/// target to the end of the draw. A law that brought the casting down to the
/// setpoint's own target would let it fall several kelvin below ready.
static void test_the_casting_is_held_at_ready_while_the_superheat_stands_above_its_floor(void)
{
    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(60u, 1.0f);

    TEST_ASSERT_NOT_NULL_MESSAGE(first_delivery(), "the draw was starved");
    for (size_t at = 0u; at < sample_count; at++) {
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(READY_TOLERANCE_C, ready_target_c(&declaration),
                                         samples[at].steam_c,
                                         "the casting left the ready target while the superheat "
                                         "stood above its floor");
    }
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: Feed is bounded by a declared ceiling
/// and a declared rise limit, both re-derived from the orifice law, and quantity
/// yields before quality. When the heater is at full and the law's superheat
/// estimate is below its setpoint, the feed does not rise and is let down at the
/// declared rise limit until the heater holds the setpoint again, so quantity
/// yields before quality.
///
/// A machine whose element is weak, whose block loses heat fast and whose
/// restriction is open asks the ceiling for more steam than the element can
/// boil. The feed rises on the pressure it wants and the heater goes to full;
/// from then on the feed is let down, ending below both the ceiling and the
/// level it peaked at, and the outlet superheat stays above zero on every step
/// that fed. Without the yield the same machine is driven to zero superheat.
static void test_the_feed_yields_to_dryness_when_the_element_cannot_boil_what_the_ceiling_admits(void)
{
    static const char *const SPENT[] = {"steam.heater_power_w", "steam.loss_w_per_k",
                                        RESTRICTION_COEFFICIENT};
    const float factors[] = {0.79f, 1.6f, 0.3f};
    const plant_parameters_t machine = machine_with_all_scaled(SPENT, factors, 3u);

    bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
    hold_ready_for(JOINT_SETTLE_SECONDS);
    draw_for(60u, 1.0f);
    TEST_ASSERT_NOT_NULL_MESSAGE(first_delivery(), "the draw was starved");

    size_t full_at = sample_count;
    uint16_t peak_feed = 0u;
    for (size_t at = 0u; at < sample_count; at++) {
        if (full_at == sample_count && samples[at].heater_permille >= (uint16_t)ACTUATION_FULL_SCALE) {
            full_at = at;
        }
        if (full_at != sample_count && samples[at].feed_permille > peak_feed) {
            peak_feed = samples[at].feed_permille;
        }
        if (samples[at].feed_permille != 0u) {
            TEST_ASSERT_TRUE_MESSAGE(samples[at].superheat_k > 0.0f,
                                     "the outlet reached saturation, so quality was given up "
                                     "before quantity");
        }
    }
    TEST_ASSERT_TRUE_MESSAGE(full_at != sample_count, "the heater never went to full, so the "
                                                      "machine does not test the yield");
    const uint16_t last_feed = samples[sample_count - 1u].feed_permille;
    TEST_ASSERT_TRUE_MESSAGE(last_feed < (uint16_t)declaration.feed_ceiling_permille,
                             "the feed stayed at the ceiling with the heater spent");
    TEST_ASSERT_TRUE_MESSAGE(last_feed + 10u < peak_feed,
                             "the feed was not let down once the heater was full");
}

/*
 * Whether every step of the recorded draw kept the feed at or under `ceiling`
 * and, above the draw-start level, rising no faster than `rise` permille a
 * second; the first offending step's position, or the sample count when none.
 *
 * A level is the rise-limited figure rounded to the actuator's resolution, so a
 * step may show one permille more than the limit alone admits.
 */
static size_t first_feed_out_of_bounds(const steam_control_declaration_t *figures)
{
    const float per_step = (float)figures->feed_rise_limit_permille_per_s *
                           ((float)STEP_INTERVAL_MS / 1000.0f);

    for (size_t at = 0u; at < sample_count; at++) {
        const uint16_t level = samples[at].feed_permille;
        if (level > (uint16_t)figures->feed_ceiling_permille) {
            return at;
        }
        if (at == 0u || level <= (uint16_t)figures->draw_start_feed_permille) {
            continue;
        }
        const uint16_t previous = samples[at - 1u].feed_permille;
        const float from = (float)(previous > (uint16_t)figures->draw_start_feed_permille
                                       ? previous
                                       : (uint16_t)figures->draw_start_feed_permille);
        if ((float)level > from + per_step + 1.0f) {
            return at;
        }
    }
    return sample_count;
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: Feed is bounded by a declared ceiling
/// and a declared rise limit, both re-derived from the orifice law, and quantity
/// yields before quality.
///
/// Demand is raised across several values behind the same open wand: one well
/// under what the start level feeds, which leaves the path short of pressure for
/// the whole draw and drives the loop to its ceiling; one near it; one well above
/// it; and one far above anything the block could boil. On every one the feed is
/// never above the declared ceiling and never rises faster than the declared
/// limit above the start level, and the draw that leaves the loop wanting more
/// reaches the ceiling and stays there rather than stopping short of it.
static void test_feed_never_exceeds_its_ceiling_or_rises_faster_than_its_limit(void)
{
    static const float DEMANDS[] = {0.05f, 0.2f, 1.0f, 5.0f};

    for (size_t at = 0u; at < sizeof(DEMANDS) / sizeof(DEMANDS[0]); at++) {
        char message[160];

        bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
        hold_ready_for(SETTLE_SECONDS);
        draw_for(20u, DEMANDS[at]);

        TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.draw_start_feed_permille,
                                         samples[0].feed_permille,
                                         "a draw opened at ready was not fed at the start level on "
                                         "its first step");
        const size_t offending = first_feed_out_of_bounds(&declaration);
        (void)snprintf(message, sizeof(message),
                       "at a demand of %.2f ml/s the feed reached %u permille at %u ms, outside "
                       "its ceiling or its rise limit",
                       (double)DEMANDS[at],
                       offending < sample_count ? samples[offending].feed_permille : 0u,
                       offending < sample_count ? (unsigned)samples[offending].at_millis : 0u);
        TEST_ASSERT_TRUE_MESSAGE(offending == sample_count, message);
    }

    /* The starved-of-pressure draw is the one that drives the loop to its limit. */
    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(20u, DEMANDS[0]);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.feed_ceiling_permille,
                                     samples[sample_count - 1u].feed_permille,
                                     "a draw that never reached the band did not take the feed to "
                                     "its ceiling");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: Feed is bounded by a declared ceiling
/// and a declared rise limit, both re-derived from the orifice law, and quantity
/// yields before quality.
///
/// The ceiling, the rise limit and the start level are read as data. The same
/// pressure-starved draw is run under the shipped declaration and under one
/// whose ceiling is lower, whose rise limit is slower and whose start level is
/// different, with nothing rebuilt: each run's first feed is its own declared
/// start level, it settles at its own declared ceiling, and the slower limit
/// takes longer to get there.
static void test_the_feed_ceiling_rise_limit_and_start_level_are_read_as_data(void)
{
    steam_control_declaration_t altered = declaration;
    altered.feed_ceiling_permille = declaration.feed_ceiling_permille - 30;
    altered.feed_rise_limit_permille_per_s = declaration.feed_rise_limit_permille_per_s / 2;
    altered.draw_start_feed_permille = declaration.draw_start_feed_permille - 10;
    const steam_control_declaration_t figures[2] = {declaration, re_declared(&altered)};
    uint32_t reached_at[2] = {0u, 0u};

    for (size_t run = 0u; run < 2u; run++) {
        bring_the_loop_up(&parameters, &figures[run], ready_target_c(&figures[run]));
        hold_ready_for(SETTLE_SECONDS);
        draw_for(30u, 0.05f);

        TEST_ASSERT_EQUAL_UINT16((uint16_t)figures[run].draw_start_feed_permille,
                                 samples[0].feed_permille);
        TEST_ASSERT_EQUAL_UINT16((uint16_t)figures[run].feed_ceiling_permille,
                                 samples[sample_count - 1u].feed_permille);
        TEST_ASSERT_EQUAL_size_t(sample_count, first_feed_out_of_bounds(&figures[run]));

        reached_at[run] = samples[sample_count - 1u].at_millis;
        for (size_t at = 0u; at < sample_count; at++) {
            if (samples[at].feed_permille == (uint16_t)figures[run].feed_ceiling_permille) {
                reached_at[run] = samples[at].at_millis;
                break;
            }
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(reached_at[1] > reached_at[0],
                             "half the rise limit reached its ceiling no later, so the limit is not "
                             "being read");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C10: Feed is bounded by a declared ceiling
/// and a declared rise limit, both re-derived from the orifice law, and quantity
/// yields before quality.
///
/// A machine whose restriction is far more open than the description admits
/// needs more feed than the ceiling allows to hold the middle of the band, so
/// the ceiling binds. The loop gives up pressure before it gives up quantity:
/// the feed is held at the ceiling, so the steam made does not fall back, while
/// the pressure settles below the middle of the band it was asked to hold. And
/// quantity is what yielded, not quality: the steam is still made dry, with the
/// outlet above saturation on every step.
static void test_when_the_ceiling_binds_pressure_yields_before_quantity_or_quality(void)
{
    const plant_parameters_t machine = machine_with_scaled(RESTRICTION_COEFFICIENT, 0.15f);

    bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(30u, 5.0f);

    const size_t settled_from = sample_count / 2u;
    for (size_t at = settled_from; at < sample_count; at++) {
        TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.feed_ceiling_permille,
                                         samples[at].feed_permille,
                                         "the feed fell back from the ceiling, so quantity was "
                                         "given up while pressure was still short");
        TEST_ASSERT_TRUE_MESSAGE(samples[at].pressure_milli_bar < band_middle(&declaration),
                                 "the ceiling did not bind, so this run says nothing about what "
                                 "the loop gives up when it does");
        TEST_ASSERT_TRUE_MESSAGE(samples[at].superheat_k > 0.0f,
                                 "the steam made at the ceiling left the outlet wet, so quality "
                                 "was given up");
    }
}



/*
 * Bring the loop up against `machine` with the shut block's casting where its
 * trusted pressure reads `pressure_milli_bar`, found by narrowing on the plant
 * itself, so a draw can be opened at exactly a chosen pressure.
 */
static void bring_the_loop_up_holding(const plant_parameters_t *machine, int32_t pressure_milli_bar)
{
    float low_c = 100.0f;
    float high_c = 150.0f;

    for (int narrowing = 0; narrowing < 40; narrowing++) {
        const float middle_c = 0.5f * (low_c + high_c);
        bring_the_loop_up(machine, &declaration, middle_c);
        if (truth_pressure_milli_bar() < pressure_milli_bar) {
            low_c = middle_c;
        } else {
            high_c = middle_c;
        }
    }
    bring_the_loop_up(machine, &declaration, high_c);
    if (truth_pressure_milli_bar() != pressure_milli_bar) {
        bring_the_loop_up(machine, &declaration, low_c);
    }
    TEST_ASSERT_EQUAL_INT32_MESSAGE(pressure_milli_bar, truth_pressure_milli_bar(),
                                    "the shut block could not be put at the pressure asked for");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C12: A wand opened at the ready pressure is
/// not starved by the feed-withhold gate under the orifice law.
///
/// The truth plant's shut block is put exactly at the declared ready pressure
/// and the wand is opened on the very next step. The draw is fed from its first
/// step at the declared draw-start level, and holds the band from the first
/// steam actually delivered to the end -- rather than collapsing to nothing
/// because, under the orifice law, the pressure the draw itself makes sits
/// below the ready threshold on every one of its steps.
///
/// The same is then asked one milli-bar below the threshold, and that draw is
/// starved for the whole of it: no feed on any step, so no steam and no
/// pressure, however long the wand is held and however hot the block becomes.
static void test_a_wand_opened_at_ready_is_fed_and_one_just_below_is_starved(void)
{
    int32_t worst = 0;

    bring_the_loop_up_holding(&parameters, declaration.ready_pressure_milli_bar);
    draw_for(20u, 1.0f);

    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.draw_start_feed_permille,
                                     samples[0].feed_permille,
                                     "a wand opened at the ready pressure was not fed at the "
                                     "draw-start level on its first step");
    TEST_ASSERT_TRUE_MESSAGE(in_band_from_first_delivery(&declaration, &worst),
                             "a draw opened at the ready pressure did not hold the band from "
                             "its first steam");
    bool below_threshold_while_fed = false;
    for (size_t at = 0u; at < sample_count; at++) {
        TEST_ASSERT_TRUE_MESSAGE(samples[at].feed_permille > 0u,
                                 "a draw opened at the ready pressure was starved part way through");
        below_threshold_while_fed =
            below_threshold_while_fed ||
            samples[at].pressure_milli_bar < declaration.ready_pressure_milli_bar;
    }
    TEST_ASSERT_TRUE_MESSAGE(below_threshold_while_fed,
                             "the draw's own pressure never sat below the ready threshold, so "
                             "this run says nothing about a gate judging it instantaneously");

    bring_the_loop_up_holding(&parameters, declaration.ready_pressure_milli_bar - 1);
    draw_for(20u, 1.0f);
    for (size_t at = 0u; at < sample_count; at++) {
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, samples[at].feed_permille,
                                         "a wand opened a milli-bar below the ready pressure was "
                                         "fed");
        TEST_ASSERT_EQUAL_INT32(0, samples[at].pressure_milli_bar);
    }
}



/*
 * Run the loop with the wand shut until the block is within the suite's
 * tolerance of the declared ready target, and answer how long that took in
 * milliseconds -- or the bound itself if it never got there.
 */
static uint32_t millis_to_reach_ready(const steam_control_declaration_t *figures)
{
    const uint32_t bound = RECOVERY_BOUND_SECONDS * 1000u;

    wand_open = false;
    demand_ml_per_s = 0.0f;
    for (uint32_t elapsed = 0u; elapsed < bound; elapsed += STEP_INTERVAL_MS) {
        (void)closed_loop_step();
        if (fabsf(truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C) - ready_target_c(figures)) <=
            READY_TOLERANCE_C) {
            return elapsed;
        }
    }
    return bound;
}

/*
 * How long the block stays within the suite's tolerance of the ready target
 * from now, in seconds, up to `seconds`: the loop runs with the wand shut and
 * the first step outside the tolerance ends the count.
 */
static unsigned seconds_held_at_ready(const steam_control_declaration_t *figures, unsigned seconds)
{
    wand_open = false;
    demand_ml_per_s = 0.0f;
    for (unsigned step = 0u; step < seconds * STEPS_PER_SECOND; step++) {
        (void)closed_loop_step();
        if (fabsf(truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C) - ready_target_c(figures)) >
            READY_TOLERANCE_C) {
            return step / STEPS_PER_SECOND;
        }
    }
    return seconds;
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C11: After a draw ends the casting returns to
/// the ready state unattended by the same heater control.
///
/// One instance of the law, brought up once, is asked to reach the ready target
/// from a cold machine, and then, for each of several draw durations in turn,
/// to hold a draw, have the wand shut on it, and carry the casting back into the
/// ready band and keep it there for a minute -- with nothing reinitialised, no
/// second entry point called and nothing done by an operator but shutting the
/// wand. That the arrival happens through the same steps that brought the block
/// up from cold is what makes it the idle control continuing rather than a
/// recovery mechanism of its own. Feed is cut on the step the wand shuts.
///
/// A law whose idle control were disabled would leave the block to cool past the
/// ready band after any draw: it would never arrive, or would not stay.
static void test_the_casting_returns_to_ready_after_draws_of_every_duration(void)
{
    static const unsigned DURATIONS[] = {3u, 10u, 30u, 60u};
    const float ambient_c = nominal_of("ambient_temperature_c");

    TEST_ASSERT_TRUE_MESSAGE(ambient_c < ready_target_c(&declaration) - 50.0f,
                             "the declared ambient is not a cold start for this target");
    bring_the_loop_up(&parameters, &declaration, ambient_c);

    const uint32_t from_cold = millis_to_reach_ready(&declaration);
    TEST_ASSERT_TRUE_MESSAGE(from_cold > 0u && from_cold < RECOVERY_BOUND_SECONDS * 1000u,
                             "the loop never brought a cold block to the ready target");

    for (size_t which = 0u; which < sizeof(DURATIONS) / sizeof(DURATIONS[0]); which++) {
        char message[128];

        hold_ready_for(SETTLE_SECONDS);
        draw_for(DURATIONS[which], 1.0f);
        TEST_ASSERT_NOT_NULL_MESSAGE(first_delivery(), "the draw was never fed");

        (void)closed_loop_step();
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                         "feed was still commanded on the step the wand shut");

        const uint32_t back = millis_to_reach_ready(&declaration);
        (void)snprintf(message, sizeof(message),
                       "the casting did not return to the ready band after a %u second draw",
                       DURATIONS[which]);
        TEST_ASSERT_TRUE_MESSAGE(back < RECOVERY_BOUND_SECONDS * 1000u, message);

        (void)snprintf(message, sizeof(message),
                       "the casting did not stay in the ready band after a %u second draw",
                       DURATIONS[which]);
        TEST_ASSERT_EQUAL_UINT_MESSAGE(60u, seconds_held_at_ready(&declaration, 60u), message);
    }

    /*
     * And from below, reached by disturbing the machine alone: the wand stays
     * shut and the same steps go on running.
     */
    TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, BELOW_READY_C));
    TEST_ASSERT_TRUE(BELOW_READY_C < ready_target_c(&declaration) - READY_TOLERANCE_C);
    TEST_ASSERT_TRUE_MESSAGE(millis_to_reach_ready(&declaration) < RECOVERY_BOUND_SECONDS * 1000u,
                             "the loop did not carry a block left below its target back up");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C11: After a draw ends the casting returns to
/// the ready state unattended by the same heater control.
///
/// The recovery asserted above is claimed across the error the
/// description declares on the two coefficients that decide it -- the steam
/// block's thermal mass and its loss to the room -- rather than at the nominal
/// figures alone, because a bound established at nominal is a bound
/// established about a machine nobody has measured. Each coefficient is taken
/// to both ends of its declared error, the same draw is run, and the same
/// bound is required to hold.
static void test_recovery_holds_its_bound_across_the_declared_model_error(void)
{
    static const char *const COEFFICIENTS[] = {"steam.thermal_mass_j_per_k", "steam.loss_w_per_k"};
    static const float ENDS[] = {-1.0f, 1.0f};

    for (size_t which = 0u; which < sizeof(COEFFICIENTS) / sizeof(COEFFICIENTS[0]); which++) {
        float assumed_error = 0.0f;
        TEST_ASSERT_TRUE_MESSAGE(
            plant_parameter_budget_for(&budget, COEFFICIENTS[which], &assumed_error),
            "the description declares no error on a coefficient recovery rests on");

        for (size_t end = 0u; end < sizeof(ENDS) / sizeof(ENDS[0]); end++) {
            char message[160];
            const plant_parameters_t machine =
                machine_with_scaled(COEFFICIENTS[which], 1.0f + ENDS[end] * assumed_error);

            bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
            hold_ready_for(SETTLE_SECONDS);
            draw_for(60u, 1.0f);

            const uint32_t recovered = millis_to_reach_ready(&declaration);
            (void)snprintf(message, sizeof(message),
                           "%s at %s its declared error did not recover inside the bound",
                           COEFFICIENTS[which], ENDS[end] < 0.0f ? "the low end of" : "the high end of");
            TEST_ASSERT_TRUE_MESSAGE(recovered < RECOVERY_BOUND_SECONDS * 1000u, message);
        }
    }
}

/* --- Accumulated intent does not outlive the limit ------------------------- */

/*
 * Hold the block at a fixed, well-below-target temperature for a controlled
 * span -- pinning the heater against its ceiling for exactly that long -- then
 * let it go and report how far the temperature climbs past the ready target.
 *
 * The steam law offers nothing comparable to control_command_flow's own
 * external knob, which is what lets the brew side's version of this test pin
 * duty at the ceiling independent of the plant's own physics. The same effect
 * is had here instead by holding the variable the law is actually driving to
 * fixed by hand for the span under test: writing the truth plant's
 * temperature back to the same cold figure on every step of it overrides
 * whatever the block would otherwise have done under that duty, so the error
 * the law sees -- and therefore whether it is pushing past the ceiling -- is
 * the same on every one of those steps regardless of how many there are. Once
 * the span ends the plant is left alone, so what happens next is the law's own
 * continuation and nothing the test is still forcing.
 */
static float overshoot_after_saturating_for(unsigned steps, float *released_at)
{
    const float cold_c = nominal_of("ambient_temperature_c");
    float highest = -1000.0f;

    bring_the_loop_up(&parameters, &declaration, cold_c);

    for (unsigned step = 0u; step < steps; step++) {
        TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, cold_c));
        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, closed_loop_step());
        TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)ACTUATION_FULL_SCALE,
                                         hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
                                         "the loop was not held against its limit at all");
    }

    *released_at = truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C);

    for (unsigned step = 0u; step < 12000u; step++) {
        (void)closed_loop_step();
        const float temperature = truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C);
        if (temperature > highest) {
            highest = temperature;
        }
    }

    return highest - ready_target_c(&declaration);
}

/// SOL-SIM-ROBUSTNESS-ACTUATOR-LIMIT-BEHAVIOUR-DESIGNED.C1: Accumulated intent
/// does not outlive the actuator limit on the steam loop, to the same
/// structural standard already proven for the brew loop.
///
/// The discriminating check is the second one, on the same terms
/// test_control.c's own version of this test states it: a loop that merely
/// unwinds quickly passes the first assertion by having accumulated little,
/// and fails this one, because what it accumulated grew with the time spent
/// against the limit. Conditional integration does not accumulate there at
/// all, so a longer interval leaves the same overshoot as a shorter one.
static void test_a_longer_saturated_interval_does_not_deepen_the_overshoot(void)
{
    float released_from_short = 0.0f;
    float released_from_long = 0.0f;

    const float shorter = overshoot_after_saturating_for(3000u, &released_from_short);
    const float longer = overshoot_after_saturating_for(6000u, &released_from_long);

    /*
     * Both runs are released from the same held-cold state by construction,
     * which is what makes the comparison below about the length of the
     * saturated interval rather than about two different machines being let
     * go at two different temperatures.
     */
    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.1f, released_from_short, released_from_long,
                                     "the two runs were released from different states, so the "
                                     "comparison is not about the saturated interval");

    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.05f, shorter, longer,
                                     "twice as long against the limit left a different overshoot, "
                                     "so intent accumulated while the actuator could take no more");
}

/// SOL-SIM-ROBUSTNESS-ACTUATOR-LIMIT-BEHAVIOUR-DESIGNED.C1: Accumulated intent
/// does not outlive the actuator limit on the steam loop, to the same
/// structural standard already proven for the brew loop.
///
/// Nothing accumulates while the actuator is at its limit and the error would
/// drive it further past, and what had accumulated before is still there when
/// the loop comes back into range. The second half is what keeps this from
/// being satisfied by an integrator that is simply switched off: an error
/// pointing back into range integrates on the step the machine does, so the
/// loop leaves saturation when the machine does rather than some steps later.
static void test_intent_is_surrendered_at_the_limit_and_not_afterwards(void)
{
    const float cold_c = nominal_of("ambient_temperature_c");

    bring_the_loop_up(&parameters, &declaration, cold_c);

    for (unsigned step = 0u; step < 100u; step++) {
        TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, cold_c));
        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, closed_loop_step());
    }
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)ACTUATION_FULL_SCALE,
                                     hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
                                     "the loop was not held against its limit at all");
    const float held = loop.integral_permille;

    for (unsigned step = 0u; step < 2000u; step++) {
        TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, cold_c));
        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, closed_loop_step());
    }
    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(held, loop.integral_permille,
                                    "intent accumulated while the actuator could take no more");

    /* Let the machine back into range, and it accumulates again. */
    for (unsigned step = 0u; step < 6000u; step++) {
        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, closed_loop_step());
    }
    TEST_ASSERT_TRUE_MESSAGE(loop.integral_permille != held,
                             "the integral never resumed, so it is switched off rather than "
                             "conditional");
}

/*
 * Hold a fed draw against the feed ceiling for `steps` steps -- a demand far
 * under what the start level feeds, so the path never reaches the band and the
 * pressure loop asks for more on every step -- then open the draw wide and
 * report the trace of pressure that follows, from the step it is opened.
 */
static void pressure_after_holding_the_feed_at_its_ceiling(unsigned steps, int32_t *trace,
                                                           size_t length, float *held_integral)
{
    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);

    wand_open = true;
    demand_ml_per_s = 0.05f;
    for (unsigned step = 0u; step < steps; step++) {
        (void)closed_loop_step();
    }
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.feed_ceiling_permille,
                                     hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "the feed was not held at its ceiling at all");
    *held_integral = loop.feed_integral_permille;

    demand_ml_per_s = 5.0f;
    for (size_t at = 0u; at < length; at++) {
        (void)closed_loop_step();
        trace[at] = truth_pressure_milli_bar();
    }
    wand_open = false;
    demand_ml_per_s = 0.0f;
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: The feed holds pressure and heater power
/// holds a declared superheat setpoint, and no pressure loop drives the heater.
///
/// The pressure loop withholds integration while its actuator is pushed past its
/// limit. Held against the ceiling for one length of time and then for twice
/// that, and then released into a draw it can hold, the pressure that follows
/// the release is the same step for step: conditional integration accumulated
/// nothing while the feed could rise no further, so the longer interval leaves
/// no more behind it than the shorter. The integral is also read directly: what
/// it held when the feed reached the ceiling is what it holds after.
static void test_the_pressure_loop_accumulates_nothing_while_held_at_its_ceiling(void)
{
    static int32_t shorter[1000];
    static int32_t longer[1000];
    float held_short = 0.0f;
    float held_long = 0.0f;

    pressure_after_holding_the_feed_at_its_ceiling(1500u, shorter, 1000u, &held_short);
    pressure_after_holding_the_feed_at_its_ceiling(3000u, longer, 1000u, &held_long);

    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(held_short, held_long,
                                    "twice as long against the ceiling left more intent behind");
    for (size_t at = 0u; at < 1000u; at++) {
        TEST_ASSERT_EQUAL_INT32_MESSAGE(shorter[at], longer[at],
                                        "twice as long against the ceiling changed what followed "
                                        "the release, so intent accumulated at the limit");
    }

    /* And once released it integrates again rather than staying switched off. */
    bool resumed = false;
    for (size_t at = 1u; at < 1000u; at++) {
        resumed = resumed || longer[at] != longer[at - 1u];
    }
    TEST_ASSERT_TRUE_MESSAGE(resumed, "the pressure never moved after the release");
}

/*
 * Hold a fed draw's casting thirty kelvin under the ready target for `steps`
 * steps, writing it back on every one so the outlet cannot reach its setpoint
 * and the heater is pushed against its ceiling, then let it go and report the
 * highest superheat the outlet reaches in the next minute, in kelvin over the
 * setpoint.
 */
static float superheat_overshoot_after_holding_the_heater_full(unsigned steps, float *held)
{
    const float held_c = ready_target_c(&declaration) - 30.0f;
    float highest = -1000.0f;

    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);

    /*
     * A draw the wand passes little of, so the pressure loop takes the feed to
     * its ceiling and the load fed forward with it puts the element at its own,
     * with the casting held cold so the superheat it asks for never arrives.
     * The first ten seconds bring the feed up and are not the interval under test.
     */
    wand_open = true;
    demand_ml_per_s = 0.05f;
    for (unsigned step = 0u; step < 10u * STEPS_PER_SECOND; step++) {
        TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, held_c));
        (void)closed_loop_step();
    }
    for (unsigned step = 0u; step < steps; step++) {
        TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, held_c));
        (void)closed_loop_step();
        TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)ACTUATION_FULL_SCALE,
                                         hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
                                         "the heater was not held against its ceiling");
    }
    *held = loop.superheat_integral_permille;

    for (unsigned step = 0u; step < 60u * STEPS_PER_SECOND; step++) {
        (void)closed_loop_step();
        const float superheat = truth_quantity(PLANT_QUANTITY_STEAM_OUTLET_SUPERHEAT_K);
        if (superheat > highest) {
            highest = superheat;
        }
    }
    wand_open = false;
    demand_ml_per_s = 0.0f;
    return highest - (float)declaration.superheat_setpoint_milli_k / 1000.0f;
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: The feed holds pressure and heater power
/// holds a declared superheat setpoint, and no pressure loop drives the heater.
///
/// The superheat loop withholds integration while the heater is pushed past its
/// ceiling, on the terms the pressure loop's test above holds that loop to: a
/// casting held cold for one length of time and for twice that leaves the same
/// integral and the same overshoot once released.
static void test_the_superheat_loop_accumulates_nothing_while_the_heater_is_full(void)
{
    float held_short = 0.0f;
    float held_long = 0.0f;

    const float shorter = superheat_overshoot_after_holding_the_heater_full(1000u, &held_short);
    const float longer = superheat_overshoot_after_holding_the_heater_full(2000u, &held_long);

    TEST_ASSERT_EQUAL_FLOAT_MESSAGE(held_short, held_long,
                                    "twice as long against the ceiling left more intent behind");
    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.05f, shorter, longer,
                                     "twice as long against the ceiling left a different "
                                     "overshoot, so intent accumulated at the limit");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C9: Every claim that steam is dry names its
/// superheat and measured pressure and states carry-over is not excluded.
///
/// A closed-loop draw is run and the dryness statement is made from what the
/// truth plant reports at its outlet, as the host run does: the least superheat
/// over the steps steam was made on, with the pressure that step carried. The
/// loop holds the declared setpoint, so the claim is dry, its figures are those
/// the draw produced, and both forms carry the caveat. A draw the gate starved
/// made no steam, and the statement then claims nothing.
static void test_a_closed_loop_draw_is_stated_dry_with_its_figures_and_the_caveat(void)
{
    char out[4096];
    dryness_finding_t finding = {false, 0.0f, 0.0f};

    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(20u, 1.0f);
    for (size_t at = 0u; at < sample_count; at++) {
        if (samples[at].feed_permille == 0u) {
            continue;
        }
        if (!finding.steam_made || samples[at].superheat_k < finding.superheat_k) {
            finding.steam_made = true;
            finding.superheat_k = samples[at].superheat_k;
            finding.pressure_bar = (float)samples[at].pressure_milli_bar / 1000.0f;
        }
    }
    TEST_ASSERT_TRUE(finding.steam_made);
    TEST_ASSERT_TRUE(finding.superheat_k >= (float)declaration.superheat_setpoint_milli_k / 1000.0f);

    FILE *stream = tmpfile();
    TEST_ASSERT_NOT_NULL(stream);
    TEST_ASSERT_TRUE(dryness_report(stream, &finding));
    rewind(stream);
    out[fread(out, 1u, sizeof(out) - 1u, stream)] = '\0';
    (void)fclose(stream);

    TEST_ASSERT_NOT_NULL(strstr(out, "HOST steam-dryness dry=true"));
    TEST_ASSERT_NOT_NULL(strstr(out, "HOST-JSON {\"what\":\"steam-dryness\",\"dry\":true"));
    char figure[64];
    (void)snprintf(figure, sizeof(figure), "superheat_k=%.9g", (double)finding.superheat_k);
    TEST_ASSERT_NOT_NULL(strstr(out, figure));
    (void)snprintf(figure, sizeof(figure), "\"pressure_bar_gauge\":%.9g", (double)finding.pressure_bar);
    TEST_ASSERT_NOT_NULL(strstr(out, figure));
    const char *first = strstr(out, "droplet carry-over is not excluded");
    TEST_ASSERT_NOT_NULL(first);
    TEST_ASSERT_NOT_NULL_MESSAGE(strstr(first + 1, "droplet carry-over is not excluded"),
                                 "the caveat appeared in one form only");

    /* A starved draw makes no steam, and claims none dry. */
    bring_the_loop_up_holding(&parameters, declaration.ready_pressure_milli_bar - 1);
    draw_for(5u, 1.0f);
    for (size_t at = 0u; at < sample_count; at++) {
        TEST_ASSERT_EQUAL_UINT16(0u, samples[at].feed_permille);
        TEST_ASSERT_EQUAL_FLOAT(0.0f, samples[at].superheat_k);
    }
}

/* --- The truth plant is not the law's own view of the machine -------------- */

/// SOL-SIM-STEAM-BAND-SUSTAINED.C9: The host harness closes the loop through a
/// truth plant the control law does not share.
///
/// A disturbance applied to the machine and to nothing else reaches the law,
/// which can only happen if what it drives from is produced by a model it does
/// not own. Against an arrangement where the reading is whatever a caller last
/// set, there would be no machine to disturb and the duty would not move.
///
/// The block is cooled, and only the block. That the duty rises afterwards is
/// the whole property: nothing told the law about it except the seam.
static void test_a_disturbance_to_the_truth_plant_alone_reaches_the_law(void)
{
    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);

    const uint16_t holding = hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER);
    TEST_ASSERT_TRUE_MESSAGE(holding > 0u && holding < (uint16_t)ACTUATION_FULL_SCALE,
                             "the loop was not holding at a duty a disturbance could move");

    TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, BELOW_READY_C));
    (void)closed_loop_step();

    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER) > holding,
                             "cooling the machine and nothing else did not move the duty, so the "
                             "loop is not closed through the machine at all");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C9: The host harness closes the loop through a
/// truth plant the control law does not share.
///
/// A machine unlike the one the declared figures were chosen against holds the
/// band less well than one like it, which is the check that the two are
/// genuinely distinct. Against an arrangement where the only model in the loop
/// is the law's own view of the machine, both runs would track identically and
/// every band assertion in this file would pass for free.
///
/// The machine's steam path is made four times as tight as the declaration was
/// sized against -- past the error the description itself declares on its
/// restriction, so this is a machine outside what anything here claims to hold --
/// and the furthest the path departs from the middle of the band is required
/// to be worse for it.
static void test_a_machine_unlike_the_declarations_own_holds_the_band_less_well(void)
{
    static const float FACTORS[] = {1.0f, 4.0f};
    int32_t furthest[2] = {0, 0};

    const int32_t middle = (declaration.draw_pressure_floor_milli_bar +
                            declaration.draw_pressure_ceiling_milli_bar) /
                           2;

    for (size_t run = 0u; run < sizeof(FACTORS) / sizeof(FACTORS[0]); run++) {
        const plant_parameters_t machine =
            machine_with_scaled(RESTRICTION_COEFFICIENT, FACTORS[run]);

        bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
        hold_ready_for(SETTLE_SECONDS);
        draw_for(30u, 1.0f);

        for (size_t step = 0u; step < sample_count; step++) {
            if (samples[step].feed_permille == 0u) {
                continue;
            }
            const int32_t gap = samples[step].pressure_milli_bar - middle;
            const int32_t magnitude = gap < 0 ? -gap : gap;
            if (magnitude > furthest[run]) {
                furthest[run] = magnitude;
            }
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(furthest[1] > furthest[0],
                             "a restriction four times as tight held the band no worse than "
                             "one the declaration was sized against, so the loop is closed on "
                             "something other than the machine");
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C7: The feed holds pressure and heater power
/// holds a declared superheat setpoint, and no pressure loop drives the heater.
///
/// The truth machine's element is made a fifth weaker and then a fifth stronger
/// than the description the law holds, and nothing else about it changes. The
/// superheat at the outlet moves with it -- the heater is what sets dryness --
/// while the pressure and the feed are the same on every step of the three
/// draws: the feed is the only thing that moves the pressure, and nothing the
/// heater does reaches the feed.
static void test_perturbing_heater_power_moves_superheat_and_leaves_pressure_to_the_feed(void)
{
    static const float FACTORS[] = {0.8f, 1.0f, 1.2f};
    static int32_t pressure[3][DRAW_SAMPLE_MAX];
    static uint16_t feed[3][DRAW_SAMPLE_MAX];
    float superheat_mean[3] = {0.0f, 0.0f, 0.0f};
    size_t recorded = 0u;

    for (size_t run = 0u; run < 3u; run++) {
        const plant_parameters_t machine =
            machine_with_scaled("steam.heater_power_w", FACTORS[run]);

        bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
        draw_for(20u, 1.0f);
        for (size_t at = 0u; at < sample_count; at++) {
            pressure[run][at] = samples[at].pressure_milli_bar;
            feed[run][at] = samples[at].feed_permille;
            superheat_mean[run] += samples[at].superheat_k / (float)sample_count;
        }
        recorded = sample_count;
    }

    for (size_t at = 0u; at < recorded; at++) {
        for (size_t run = 1u; run < 3u; run++) {
            TEST_ASSERT_EQUAL_UINT16_MESSAGE(feed[0][at], feed[run][at],
                                             "the element's power moved the feed");
            TEST_ASSERT_EQUAL_INT32_MESSAGE(pressure[0][at], pressure[run][at],
                                            "the element's power moved the pressure, so the feed "
                                            "is not its sole actuator");
        }
    }
    TEST_ASSERT_TRUE_MESSAGE(superheat_mean[0] < superheat_mean[1] &&
                                 superheat_mean[1] < superheat_mean[2],
                             "a weaker element did not leave the outlet less superheated, nor a "
                             "stronger one more, so the heater is not what sets dryness");
}

/* --- The readiness policy the band-holding law carries in front of it ------ */

/// SOL-SIM-STEAM-READINESS-GATE.C1: Steam feed is withheld while measured
/// pressure sits below the declared ready threshold.
///
/// SOL-SIM-STEAM-READINESS-GATE.C5: The feed-withhold policy is exercised in
/// host simulation against the plant model before any hardware exists.
///
/// A truth instance of the reference structure is held well below the declared
/// threshold and a real draw is opened against it -- the wand reported turned
/// through the seam, and a nonzero steam demand handed to the plant on every
/// step. The law reads the truth's own pressure back through the simulated
/// hardware implementation and is required to withhold feed on every step
/// regardless, for long enough that the feed's rise from its start level to its
/// ceiling would have run several times over.
///
/// The heater is deliberately left undriven in the plant here, so the block
/// does not climb out of the condition the test is about. The law still
/// commands it; what this test asserts about is the feed.
static void test_feed_withheld_while_pressure_stays_below_threshold_with_the_wand_open(void)
{
    plant_model_t below;
    steam_control_state_t gate;

    hw_sim_reset();
    TEST_ASSERT_TRUE(plant_model_init(&below, &parameters));
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration, &parameters, &budget));

    const plant_actuation_t idle = {{0u}};
    for (uint32_t elapsed = 0u; elapsed < WITHHELD_SPAN_MS; elapsed += STEP_INTERVAL_MS) {
        TEST_ASSERT_TRUE(plant_model_step(&below, &idle, 3.0f, STEP_INTERVAL_MS));

        float pressure_bar = 0.0f;
        float temperature_c = 0.0f;
        TEST_ASSERT_TRUE(plant_model_quantity(&below, PLANT_QUANTITY_STEAM_PRESSURE_BAR,
                                              &pressure_bar));
        TEST_ASSERT_TRUE(plant_model_quantity(&below, PLANT_QUANTITY_STEAM_TEMPERATURE_C,
                                              &temperature_c));
        TEST_ASSERT_TRUE_MESSAGE(
            (int32_t)lroundf(pressure_bar * 1000.0f) < declaration.ready_pressure_milli_bar,
            "the truth plant reached the ready threshold, which this test did not intend");

        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                          (int32_t)lroundf(pressure_bar * 1000.0f));
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          (int32_t)lroundf(temperature_c * 1000.0f));
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);

        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

        hw_sim_advance_millis(STEP_INTERVAL_MS);
    }
}

/// SOL-SIM-STEAM-READINESS-GATE.C1: Steam feed is withheld while measured
/// pressure sits below the declared ready threshold.
///
/// The boundary itself: a draw opened on a reading one milli-bar below the
/// declared threshold is withheld, and stays withheld however long it runs. This is the case an off-by-one in
/// the comparison would first show up on, which a test set comfortably below
/// the threshold would never catch.
static void test_feed_withheld_one_milli_bar_below_threshold(void)
{
    steam_control_state_t gate;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration, &parameters, &budget));

    for (uint32_t elapsed = 0u; elapsed <= WITHHELD_SPAN_MS; elapsed += STEP_INTERVAL_MS) {
        (void)step_with(&gate, true, declaration.ready_pressure_milli_bar - 1,
                        declaration.ready_temperature_milli_c);
    }

    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
}

/// SOL-SIM-STEAM-READINESS-GATE.C2: Steam feed is enabled once measured
/// pressure reaches the declared ready threshold.
///
/// The threshold is judged when the wand opens, so "the same step it is
/// crossed" is asked as the gate now asks it: three instances share a history
/// of a shut block held a milli-bar below the threshold, and each opens the wand
/// on the step the shut block's reading is, respectively, still a milli-bar
/// below it, exactly at it, and comfortably above it. The first is withheld; the
/// second is fed on that very step, which is the criterion in its own words; and
/// the third is fed too. The two either side are the regression protection a
/// boundary checked in isolation would not give.
///
/// What feed the pressure loop then commands is out of that criterion's scope;
/// what is required here is only that feed goes from nothing to something.
///
/// The threshold is judged at the wand opening. A draw opened below it cannot
/// cross it later: with the wand open the plant's pressure is the orifice drop
/// across the steam made, and the steam made is the lesser of the demand and
/// the feed, which is nothing while the gate withholds feed. The only crossing
/// is on a shut block, and the next opening judges it; the test beside this one
/// holds a draw open below the threshold and asserts exactly that.
static void test_feed_enabled_the_same_step_pressure_reaches_threshold(void)
{
    static const struct {
        int32_t offset_milli_bar;
        bool fed;
        const char *what;
    } CASES[] = {
        {-1, false, "feed was available a milli-bar below the threshold"},
        {0, true, "feed was not available on the step the threshold was reached"},
        {500, true, "feed was withheld above the threshold"},
    };

    for (size_t at = 0u; at < sizeof(CASES) / sizeof(CASES[0]); at++) {
        steam_control_state_t gate;

        hw_sim_reset();
        TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration, &parameters, &budget));
        for (unsigned step = 0u; step < 200u; step++) {
            (void)step_with(&gate, false, declaration.ready_pressure_milli_bar - 1,
                            declaration.ready_temperature_milli_c);
        }
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

        (void)step_with(&gate, true,
                        declaration.ready_pressure_milli_bar + CASES[at].offset_milli_bar,
                        declaration.ready_temperature_milli_c);
        TEST_ASSERT_EQUAL_MESSAGE(CASES[at].fed, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP) > 0u,
                                  CASES[at].what);
    }
}

/// SOL-SIM-STEAM-READINESS-GATE.C2: Steam feed is enabled once measured
/// pressure reaches the declared ready threshold.
///
/// The threshold is judged when the wand opens, and a draw opened below it
/// cannot cross it later. The loop is closed through the truth plant under
/// everything the law itself commands, heater included, with the wand opened on
/// a block well under the threshold: the element heats the block for the whole
/// draw, yet with the wand open the pressure is the drop across the steam made,
/// and none is made while feed is withheld, so the pressure stays at nothing and
/// the feed at nothing on every step. That the crossing was on offer is asserted
/// rather than assumed: the same block shut afterwards reads at or above the
/// threshold, and the next opening is fed.
static void test_a_draw_opened_below_ready_cannot_cross_it_while_the_wand_stays_open(void)
{
    const float start_c = ready_target_c(&declaration) - 30.0f;

    bring_the_loop_up(&parameters, &declaration, start_c);
    TEST_ASSERT_TRUE_MESSAGE(truth_pressure_milli_bar() < declaration.ready_pressure_milli_bar,
                             "the block started at or above the ready threshold");

    draw_for(WITHHELD_SPAN_MS / 1000u, 1.0f);

    float hottest_c = start_c;
    uint16_t most_heater = 0u;
    for (size_t at = 0u; at < sample_count; at++) {
        char message[96];

        (void)snprintf(message, sizeof(message), "at %u ms of a draw opened below ready",
                       (unsigned)samples[at].at_millis);
        TEST_ASSERT_EQUAL_INT32_MESSAGE(0, samples[at].pressure_milli_bar, message);
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, samples[at].feed_permille, message);
        TEST_ASSERT_EQUAL_FLOAT_MESSAGE(0.0f, samples[at].superheat_k, message);
        hottest_c = fmaxf(hottest_c, samples[at].steam_c);
        most_heater = (samples[at].heater_permille > most_heater) ? samples[at].heater_permille
                                                                  : most_heater;
    }
    TEST_ASSERT_TRUE_MESSAGE(most_heater > 0u, "the law never drove the element, so nothing was heating");
    TEST_ASSERT_TRUE_MESSAGE(hottest_c > start_c + 10.0f,
                             "the block did not heat through the draw, so no crossing was on offer");

    /* The same block with the wand shut now reads at or above the threshold. */
    hold_ready_for(1u);
    TEST_ASSERT_TRUE_MESSAGE(truth_pressure_milli_bar() >= declaration.ready_pressure_milli_bar,
                             "the block the draw heated is still under the threshold shut");

    /* And the next opening judges it and feeds. */
    draw_for(2u, 1.0f);
    bool fed = false;
    for (size_t at = 0u; at < sample_count; at++) {
        fed = fed || samples[at].feed_permille > 0u;
    }
    TEST_ASSERT_TRUE_MESSAGE(fed, "the opening that found the block ready was not fed");
}

/// SOL-SIM-STEAM-READINESS-GATE.C2: Steam feed is enabled once measured
/// pressure reaches the declared ready threshold.
///
/// Exercised against the truth plant rather than an injected reading, on the
/// same terms C1's own plant-backed test is: the block is held at the declared
/// ready target, whose rested pressure the plant seam alone establishes clears
/// the threshold, and feed is read back from what the simulated hardware
/// implementation reports once a draw has been under way long enough for
/// nothing else to be withholding it.
static void test_feed_enabled_against_the_plant_models_own_truth(void)
{
    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);

    TEST_ASSERT_TRUE_MESSAGE(truth_pressure_milli_bar() >= declaration.ready_pressure_milli_bar,
                             "the declared ready target does not clear the declared threshold on "
                             "this machine");

    draw_for(10u, 1.0f);
    TEST_ASSERT_TRUE_MESSAGE(first_delivery() != NULL,
                             "feed was never enabled against a machine above the threshold");
}



/// SOL-SIM-STEAM-READINESS-GATE.C4: The ready threshold is declared data with
/// a recorded origin, read by the control law rather than compiled into it.
///
/// Two instances, brought up from two declarations differing in nothing but
/// the threshold, are handed the same pressure reading -- one sitting between
/// the two thresholds -- with a draw under way and its sequencing elapsed in
/// both, and are required to disagree about whether feed is withheld. Nothing
/// is rebuilt: both declarations are read at run time by the same loader,
/// which is what "read by the control law rather than compiled into it" is
/// standing for.
static void test_declared_threshold_moves_the_feed_boundary(void)
{
    steam_control_declaration_t lower = declaration;
    steam_control_declaration_t higher = declaration;

    lower.ready_pressure_milli_bar = 500;
    higher.ready_pressure_milli_bar = 1500;
    const steam_control_declaration_t low = re_declared(&lower);
    const steam_control_declaration_t high = re_declared(&higher);

    steam_control_state_t gate_low;
    steam_control_state_t gate_high;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&gate_low, &limits, &low, &parameters, &budget));
    TEST_ASSERT_TRUE(steam_control_init(&gate_high, &limits, &high, &parameters, &budget));

    for (uint32_t elapsed = 0u; elapsed <= WITHHELD_SPAN_MS; elapsed += STEP_INTERVAL_MS) {
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, 1000);
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          declaration.ready_temperature_milli_c);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);
        (void)steam_control_step(&gate_low);
        const uint16_t fed = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        (void)steam_control_step(&gate_high);
        const uint16_t withheld = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        hw_sim_advance_millis(STEP_INTERVAL_MS);

        if (elapsed == WITHHELD_SPAN_MS) {
            TEST_ASSERT_TRUE_MESSAGE(fed > 0u,
                                     "the instance whose declared threshold sits below the "
                                     "reading withheld feed");
            TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, withheld,
                                             "the instance whose declared threshold sits above "
                                             "the reading fed anyway, so the threshold is not "
                                             "being read");
        }
    }
}

/// SOL-SIM-STEAM-READINESS-GATE.C5: The feed-withhold policy is exercised in
/// host simulation against the plant model before any hardware exists.
///
/// The law builds into a host executable with no target dependency present,
/// initialises and steps against the simulated implementation alone, and
/// drives both channels from what the plant model reports. Every other test in
/// this file is closed through the plant model on the same terms; this is the
/// one that says so directly.
///
/// Both channels are asserted at figures only a machine could have produced. A
/// block held below the ready target is one the loop has to answer with more
/// duty than the declared standing-load feedforward alone -- which is what it
/// would command if the error were nothing -- and with no draw reported there
/// is nothing for it to feed. The pair is asserted rather than either alone,
/// because a pump at rest is the correct answer here and would also be the
/// answer of a law that never ran at all.
static void test_the_law_runs_against_the_simulated_implementation_with_no_target_dependency(void)
{
    bring_the_loop_up(&parameters, &declaration, BELOW_READY_C);

    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, closed_loop_step());
    TEST_ASSERT_TRUE_MESSAGE(
        hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER) >
            (uint16_t)declaration.standing_load_permille,
        "a block below the ready target was not answered with more duty than the standing load "
        "alone, so nothing was driven from what the plant model reported");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "feed was commanded with no draw reported");
}

/// SOL-SIM-STEAM-READINESS-GATE.C1: Steam feed is withheld while measured
/// pressure sits below the declared ready threshold.
///
/// An absent, failed, or implausible reading on the pressure channel is not
/// evidence the steam side has reached the threshold, so an instance that has
/// never had a trustworthy one withholds feed on every one of them rather than
/// acting on a figure it has no reason to believe. This is deliberately the
/// case where nothing has ever been trusted: an instance that has a last
/// trusted value goes on from that instead, which is the neighbouring
/// criterion's own subject and is asserted separately.
static void test_feed_withheld_when_no_pressure_reading_has_ever_been_trusted(void)
{
    static const struct {
        hw_reading_status_t status;
        bool above_declared_high;
    } CASES[] = {
        {HW_READING_ABSENT, false},
        {HW_READING_FAILED, true},
        {HW_READING_VALID, true},
    };

    for (size_t at = 0u; at < sizeof(CASES) / sizeof(CASES[0]); at++) {
        steam_control_state_t gate;

        hw_sim_reset();
        TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration, &parameters, &budget));

        const int32_t value = CASES[at].above_declared_high
                                  ? limits.high_milli[HW_SENSOR_STEAM_PRESSURE] + 1000
                                  : 0;
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, CASES[at].status, value);
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          declaration.ready_temperature_milli_c);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);

        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&gate));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
        const uint16_t starved_duty = hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER);

        /*
         * A starved draw makes no steam, so its heater holds the ready target
         * from the temperature it does have, exactly as an idle step with the
         * same readings does -- and never from the pressure it has no figure for.
         */
        steam_control_state_t idle;
        hw_sim_reset();
        TEST_ASSERT_TRUE(steam_control_init(&idle, &limits, &declaration, &parameters, &budget));
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, CASES[at].status, value);
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          declaration.ready_temperature_milli_c);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_CLEAR);
        (void)steam_control_step(&idle);
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER), starved_duty,
                                         "the element of a starved draw was not driven as the "
                                         "idle control drives it");
    }
}

/* --- Regression protection for the paths no criterion names --------------- */

/// Regression protection for steam_control_init's own refusals: a caller
/// handed no limits record or no declaration is refused with both channels
/// left commanded off rather than left at whatever they were, on the same
/// terms control_init already refuses a null tolerance record. A refused
/// instance also answers nothing about what it is driving to, rather than
/// answering that it is holding ready.
static void test_init_is_refused_and_leaves_both_channels_off_without_either_record(void)
{
    steam_control_state_t state;
    steam_control_variable_t variable;
    bool drawing = false;

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(&state, NULL, &declaration, &parameters, &budget));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER));
    TEST_ASSERT_FALSE(steam_control_variable(&state, &variable));
    TEST_ASSERT_FALSE(steam_control_drawing(&state, &drawing));
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&state));

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(&state, &limits, NULL, &parameters, &budget));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER));

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(NULL, &limits, &declaration, &parameters, &budget));
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(NULL));
    TEST_ASSERT_FALSE(steam_control_variable(NULL, &variable));
    TEST_ASSERT_FALSE(steam_control_drawing(NULL, &drawing));
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: a loop handed no
/// description of the machine, or no statement of how far out that
/// description's figures may be, is refused with both channels left commanded
/// off -- on exactly the terms one handed no limits record or no declaration
/// is.
///
/// This loop drives from no model, so a reader could reasonably expect it to
/// take a declaration and nothing else. It takes both because the ready target
/// that declaration names is a commanded temperature and the steam block
/// carries protection of its own: how far below that protection the target has
/// to sit is sized from what the description says its figures may be wrong by,
/// and a loop asked to hold a block against a margin nobody stated would be
/// holding it against nothing.
///
/// The margin reads answer nothing on a refused instance, which is what says
/// the refusal is not merely at the door: an instance that would not come up
/// and then reported a margin would be reporting one nothing is enforcing.
static void test_init_is_refused_without_a_description_or_a_budget(void)
{
    steam_control_state_t state;
    protection_margin_t margin;
    protection_margin_corner_t corner;

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(&state, &limits, &declaration, NULL, &budget));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER));
    TEST_ASSERT_FALSE(steam_control_protection_margin(&state, &margin));
    TEST_ASSERT_FALSE(steam_control_protection_margin_corner(&state, 0u, &corner));

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(&state, &limits, &declaration, &parameters, NULL));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER));
    TEST_ASSERT_FALSE_MESSAGE(steam_control_protection_margin(&state, &margin),
                              "an instance brought up without a budget reported a margin");
    TEST_ASSERT_FALSE(steam_control_protection_margin_corner(&state, 0u, &corner));

    /* And the reads refuse a null state and a null destination on the same terms. */
    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));
    TEST_ASSERT_FALSE(steam_control_protection_margin(NULL, &margin));
    TEST_ASSERT_FALSE(steam_control_protection_margin(&state, NULL));
    TEST_ASSERT_FALSE(steam_control_protection_margin_corner(NULL, 0u, &corner));
    TEST_ASSERT_FALSE(steam_control_protection_margin_corner(&state, 0u, NULL));

    /* A position past the end of the enumeration is refused rather than answered. */
    TEST_ASSERT_TRUE(steam_control_protection_margin(&state, &margin));
    TEST_ASSERT_FALSE(steam_control_protection_margin_corner(&state, margin.corners, &corner));
}

/// Regression protection for the accessors' null out-parameters, which a
/// caller cannot be told anything through and which must not be written.
static void test_the_accessors_refuse_nowhere_to_answer(void)
{
    steam_control_state_t state;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));
    TEST_ASSERT_FALSE(steam_control_variable(&state, NULL));
    TEST_ASSERT_FALSE(steam_control_drawing(&state, NULL));

    /*
     * The superheat estimate answers only on a step that fed a draw: idle, and
     * on a draw the gate starved, no steam was made to have a superheat.
     */
    float superheat_k = 0.0f;
    TEST_ASSERT_FALSE(steam_control_outlet_superheat(NULL, &superheat_k));
    (void)step_with(&state, false, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_FALSE(steam_control_outlet_superheat(&state, &superheat_k));
    (void)step_with(&state, true, declaration.ready_pressure_milli_bar - 1,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_FALSE(steam_control_outlet_superheat(&state, &superheat_k));
    (void)step_with(&state, false, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    (void)step_with(&state, true, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE(steam_control_outlet_superheat(&state, &superheat_k));
    TEST_ASSERT_FALSE(steam_control_outlet_superheat(&state, NULL));
}

/// Regression protection for steam_control_step's own error path: a refused
/// drive command is reported as STEAM_CONTROL_STEP_OUTPUT_REFUSED rather than
/// folded into an ordinary step, on the same terms test_control.c's own
/// test_refused_drive_command_is_reported_and_latches covers control_step's
/// identical case. A caller has to be able to tell it apart from an ordinary
/// cycle or it cannot tell the machine is not doing what it was just told.
static void test_output_refused_is_reported_rather_than_folded_into_actuated(void)
{
    steam_control_state_t state;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));

    hw_sim_set_output_refused(true);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                      declaration.ready_pressure_milli_bar);
    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                      declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_OUTPUT_REFUSED, steam_control_step(&state));
}

/// Regression protection for the half-driven machine: a step whose heater
/// command is refused does not leave the feed pump running.
///
/// This is the case the ordering of the two drive calls cannot answer, because
/// the pump was already running before the step began. Mid-draw the feed is
/// running, and a refused heater command leaves the element at a level nothing
/// established -- so water goes on being pushed into a block whose element may
/// be at nothing, which is precisely the wet steam the heater exists to prevent. control_step brings the brew side down
/// in the same situation and for the same reason.
///
/// Only the heater channel is refused, not both: under a blanket refusal the
/// off command would be refused too, and a pump that stayed where it was could
/// not be told from one nothing tried to move.
static void test_a_refused_heater_command_does_not_leave_the_feed_running(void)
{
    steam_control_state_t state;
    const int32_t in_band = (declaration.draw_pressure_floor_milli_bar +
                             declaration.draw_pressure_ceiling_milli_bar) /
                            2;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));

    open_a_fed_draw(&state, in_band, declaration.ready_temperature_milli_c, 300u);
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP) > 0u,
                             "the draw was not feeding, so a refused heater command has nothing "
                             "to have left running");

    hw_sim_set_output_channel_refused(ACTUATION_CHANNEL_STEAM_HEATER, true);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, in_band);
    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                      declaration.ready_temperature_milli_c);
    hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);

    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_OUTPUT_REFUSED, steam_control_step(&state));
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "a refused heater command left the feed pump running into a "
                                     "block whose element is at a level nothing established");
}

/// Regression protection for steam_control_init's own refusal of the initial
/// off commands: the instance is still handed back usable -- a subsequent step
/// is not treated as uninitialised -- but the return value itself is false, on
/// the same terms control_init returns false from a refused off command while
/// leaving the rest of the state usable. A caller reading only the boolean and
/// assuming the channels are therefore off would be wrong; steam_control.h's
/// own account of this is what this test holds the implementation to.
static void test_init_reports_a_refused_off_command_but_leaves_the_loop_usable(void)
{
    steam_control_state_t state;

    hw_sim_reset();
    hw_sim_set_output_refused(true);
    TEST_ASSERT_FALSE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));

    hw_sim_set_output_refused(false);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                      declaration.ready_pressure_milli_bar);
    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                      declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&state));
}

/// SOL-PLANT-STEAM-FLASH-GENERATOR.C12: A wand opened at the ready pressure is
/// not starved by the feed-withhold gate under the orifice law.
///
/// The gate's verdict is held for one draw and no longer. A draw opened at ready
/// and fed keeps being fed while its own pressure sits well below the threshold;
/// once the wand shuts the feed is cut on that step; and a draw reopened below
/// the threshold is judged afresh and starved, rather than inheriting the verdict
/// the last one earned. The reverse holds too: a starved draw shut and reopened
/// at ready is fed. A law that carried the verdict across would feed a block it
/// never judged, or starve one that had become ready.
static void test_a_reopened_draw_is_judged_afresh(void)
{
    steam_control_state_t state;
    const int32_t below = declaration.ready_pressure_milli_bar - 1;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));

    open_a_fed_draw(&state, declaration.draw_pressure_floor_milli_bar,
                    declaration.ready_temperature_milli_c, 300u);
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP) > 0u,
                             "a draw opened at ready stopped being fed when its own pressure sat "
                             "below the threshold");

    (void)step_with(&state, false, below, declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "feed was not cut on the step the wand shut");

    for (unsigned step = 0u; step < 300u; step++) {
        (void)step_with(&state, true, below, declaration.ready_temperature_milli_c);
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                         "a draw reopened below the threshold was fed on the "
                                         "verdict the last draw earned");
    }

    (void)step_with(&state, false, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    (void)step_with(&state, true, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.draw_start_feed_permille,
                                     hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "a draw reopened at ready after a starved one was not fed at "
                                     "the start level");
}

/* --- The margin the ready target keeps from the steam block's trip point --- */


/*
 * The coefficients the reference description declares one-sided, and the one
 * end of each the description actually claims.
 *
 * One-sidedness is a sentence in params/thermoblock.md and not a field of the
 * description's grammar -- the line beside the value carries a symmetric
 * fraction and nothing that could say otherwise -- so it cannot be read out of
 * the budget and is written here instead, exactly as the sibling stability
 * analysis writes it beside its own corner logic. All three are one-sided the
 * same way and for the same kind of reason: each is a figure standing in for
 * something it is not, and a real machine sits below it rather than either side
 * of it.
 *
 * A corner at the end the description does not claim is a machine nobody has
 * claimed, and a verdict taken against one would be a verdict about a machine
 * this description does not describe. The margin computation itself still runs
 * both ends -- nothing on that side of the seam can read this sentence, and
 * running the unclaimed end can only widen a margin, which is the safe
 * direction for a protection bound -- but a delivery verdict is a different
 * kind of claim and is taken only where the description stands behind the
 * machine.
 *
 * Nothing structural ties this table to the prose it was read out of, so a
 * name that has gone stale would leave this quietly skipping a corner the
 * description now claims. The tripwire is the assertion below that every name
 * here is one this structure has: a coefficient renamed or removed fails
 * loudly rather than being carried silently.
 */
static const char *const ONE_SIDED_REACHING_DOWNWARDS[] = {
    "pump.pressure_bar",
    "pump.flow_ml_per_s",
    "steam.feed_flow_ml_per_s",
};

static bool the_end_the_description_does_not_claim(const protection_margin_corner_t *corner)
{
    if (corner->joint || corner->reaching_downwards) {
        return false;
    }

    for (size_t which = 0u; which < sizeof(ONE_SIDED_REACHING_DOWNWARDS) /
                                        sizeof(ONE_SIDED_REACHING_DOWNWARDS[0]);
         which++) {
        size_t at = 0u;

        if (plant_parameter_position(ONE_SIDED_REACHING_DOWNWARDS[which], &at) &&
            at == corner->at) {
            return true;
        }
    }
    return false;
}

/* Every name in that table is one this structure has, or the table has gone stale. */
static void the_one_sided_table_still_names_this_machine(void)
{
    for (size_t which = 0u; which < sizeof(ONE_SIDED_REACHING_DOWNWARDS) /
                                        sizeof(ONE_SIDED_REACHING_DOWNWARDS[0]);
         which++) {
        size_t at = 0u;

        TEST_ASSERT_TRUE_MESSAGE(plant_parameter_position(ONE_SIDED_REACHING_DOWNWARDS[which], &at),
                                 ONE_SIDED_REACHING_DOWNWARDS[which]);
    }
}

/*
 * The machine one enumerated corner names, built through the plant seam from
 * the position that corner moves rather than from any coefficient's name --
 * the same route the margin computation itself takes to build it, so a draw's
 * verdict is taken against the machine the contribution was taken against.
 */
static bool the_machine_at_the_corner(const protection_margin_corner_t *corner,
                                      plant_parameters_t *machine)
{
    const float factor = corner->reaching_downwards ? (1.0f - corner->declared_error)
                                                    : (1.0f + corner->declared_error);

    *machine = parameters;
    if (!corner->joint) {
        return plant_parameter_scale(machine, corner->at, factor);
    }

    for (size_t at = 0u; at < budget.count; at++) {
        bool driven = false;

        if (!plant_parameter_supply_driven(at, &driven) || !driven || !budget.declared[at]) {
            continue;
        }
        if (!plant_parameter_scale(machine, at, factor)) {
            return false;
        }
    }
    return true;
}

/*
 * Whether the draw came to rest inside the band, judged over its trailing
 * third.
 *
 * Where a draw *lands* rather than everything it did on the way, which is what
 * this criterion asks and is a different question from the one
 * in_band_from_first_delivery above answers. Holding the delivered character
 * inside the band for the whole of a draw is what the steam law's own criterion
 * claims at the description's own figures; how tightly it is held as the model
 * moves is declared a degrading behaviour in params/robustness.declaration and
 * is permitted to get worse. A corner that shifts the relation between the
 * block's temperature and the path's pressure gives the loop a longer climb
 * before the band is reached at all, and judging that climb would be judging
 * the horizon rather than the machine.
 */
static bool lands_in_band(const steam_control_declaration_t *figures, int32_t *worst)
{
    bool held = false;
    const size_t judged_from = (sample_count * 2u) / 3u;

    *worst = 0;
    for (size_t at = judged_from; at < sample_count; at++) {
        const int32_t pressure = samples[at].pressure_milli_bar;

        held = true;
        if (pressure < figures->draw_pressure_floor_milli_bar ||
            pressure > figures->draw_pressure_ceiling_milli_bar) {
            *worst = pressure;
            return false;
        }
    }
    return held;
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: A draw lands inside
/// the band the design holds it to at every independent declared-error corner
/// and at the one joint corner the description's own construction implies,
/// with the loop admitted at the widened margin.
///
/// Every coefficient the shipped description carries a declared error against
/// is taken to its corner and the same draw is run against it, with the machine
/// built from that corner's coefficients while the loop stays where it was:
/// this loop drives from no model at all, so what a corner moves is the machine
/// and never the belief, and the split the coffee side has to arrange
/// deliberately is structural here. Both ends of a two-sided coefficient are
/// run, and a coefficient whose other end the structure will not admit as a
/// machine is run at the one end it does.
///
/// The committed record of this side's mapping is docs/protection-margin.md,
/// written by firmware/emulation/tools/run_protection_margin.py off the same
/// reads this case uses and kept in step with the method by
/// firmware/emulation/tests/test_protection_margin.py. It is a checked-in file
/// rather than a table this case prints because a table printed by a Unity test
/// is swallowed by the runner: nothing downstream of any gate ever sees it.
///
/// The joint corner is run to the same standard rather than left with the
/// settling check the sibling stability solution gives it: it is the one corner
/// where two declared errors move together, and leaving band adequacy unchecked
/// there would leave it unchecked at the only corner an independent sweep
/// cannot reach.
static void test_a_draw_lands_within_its_band_at_every_declared_error_corner(void)
{
    protection_margin_t margin;
    unsigned drawn = 0u;
    unsigned joint_drawn = 0u;
    unsigned contributing = 0u;
    float widest_contribution_c = 0.0f;
    float summed_contributions_c = 0.0f;
    float squared_contributions = 0.0f;

    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    TEST_ASSERT_TRUE(steam_control_protection_margin(&loop, &margin));
    TEST_ASSERT_TRUE_MESSAGE(margin.corners > 0u,
                             "the shipped description supports no corner enumeration at all");

    /*
     * The whole enumeration is read off the loop before any corner is drawn
     * against, because the margin follows whatever description the instance is
     * holding: a corner read from a loop since brought up against another
     * corner's machine would belong to a different enumeration.
     */
    static protection_margin_corner_t corners[(2u * PLANT_PARAMETER_LIMIT) + 1u];

    for (size_t which = 0u; which < margin.corners; which++) {
        TEST_ASSERT_TRUE(steam_control_protection_margin_corner(&loop, which, &corners[which]));
    }
    the_one_sided_table_still_names_this_machine();

    for (size_t which = 0u; which < margin.corners; which++) {
        const protection_margin_corner_t *const corner = &corners[which];
        plant_parameters_t machine;
        int32_t worst = 0;
        char coefficient[16];

        if (corner->joint) {
            (void)snprintf(coefficient, sizeof(coefficient), "pair");
        } else {
            (void)snprintf(coefficient, sizeof(coefficient), "%u", (unsigned)corner->at);
        }

        if (!the_end_the_description_does_not_claim(corner) && corner->ran &&
            the_machine_at_the_corner(corner, &machine)) {
            char message[224];

            bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
            hold_ready_for(SETTLE_SECONDS);
            draw_for(30u, 1.0f);

            const bool held = lands_in_band(&declaration, &worst);
            drawn++;
            if (corner->joint) {
                joint_drawn++;
            }

            (void)snprintf(message, sizeof(message),
                           "corner %u -- %s, coefficient %s %s at %.4f of nominal -- left the "
                           "delivered pressure at %d milli-bar, outside the declared band of %d "
                           "to %d",
                           (unsigned)which, corner->joint ? "joint mains droop" : "independent",
                           coefficient, corner->reaching_downwards ? "low" : "high",
                           (double)corner->declared_error, worst,
                           declaration.draw_pressure_floor_milli_bar,
                           declaration.draw_pressure_ceiling_milli_bar);
            TEST_ASSERT_TRUE_MESSAGE(held, message);
        }

        if (!corner->ran) {
            continue;
        }
        if (corner->contribution_c > widest_contribution_c) {
            widest_contribution_c = corner->contribution_c;
        }
        if (corner->contribution_c > 0.0f) {
            contributing++;
            summed_contributions_c += corner->contribution_c;
            squared_contributions += corner->contribution_c * corner->contribution_c;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(drawn >= 2u,
                             "no corner of the declared error was drawn against at all, so "
                             "nothing here was established");
    TEST_ASSERT_EQUAL_UINT_MESSAGE(1u, joint_drawn,
                                   "the joint corner was not drawn against to the same standard "
                                   "the independent corners were");
    TEST_ASSERT_EQUAL_UINT_MESSAGE(contributing, margin.contributing,
                                   "the record and the margin disagree about how many corners "
                                   "cost the trip-point gap anything");
    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(1e-5f, widest_contribution_c, margin.worst_corner_c,
                                     "the margin's worst corner is not the widest contribution in "
                                     "the record");
    TEST_ASSERT_FLOAT_WITHIN_MESSAGE(
        1e-5f, margin.unwidened_c + widest_contribution_c + margin.sensing_error_c,
        margin.margin_c,
        "the widened margin is not the un-widened gap plus the worst corner plus the declared "
        "sensing error");
    if (contributing >= 2u) {
        TEST_ASSERT_TRUE_MESSAGE(margin.worst_corner_c < summed_contributions_c - 1e-5f,
                                 "the margin is the sum of every corner's contribution rather "
                                 "than the worst single corner");
        TEST_ASSERT_TRUE_MESSAGE(margin.worst_corner_c < sqrtf(squared_contributions) - 1e-5f,
                                 "the margin is the root-sum-square of the corners' "
                                 "contributions rather than the worst single corner");
    }
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C2: The corner sweep above
/// is drawn at the ready target the declaration names, and how far that sits
/// from the widened margin's own edge is a finding rather than a silence.
///
/// "Commanded at the widened margin" is a claim about which bound actually
/// stops this loop's target, and on this machine it is not the margin: the
/// declaration names a ready temperature well below the highest one the margin
/// leaves room for, so the sweep above draws at a target the margin refuses
/// nothing about. The headroom is narrowed on the loop's own refusal rather
/// than computed here, and asserted to be real, so a description or a
/// declaration that closed that gap fails this case instead of quietly turning
/// the sweep into a different experiment.
///
/// Drawing the sweep at that edge instead is not the fix and is worth saying
/// why: the band a draw is held to is declared for the block held at the ready
/// temperature, and a draw taken with the block some sixty degrees hotter would
/// leave the band by construction rather than because any declared error moved
/// it. What is exercised at the edge is the refusal itself, which is the case
/// below.
static void test_the_sweep_draws_at_the_declared_ready_target_and_not_at_the_margins_edge(void)
{
    steam_control_declaration_t asking = declaration;
    steam_control_state_t narrowing;
    protection_margin_t margin;
    char message[224];

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&narrowing, &limits, &declaration, &parameters, &budget));
    TEST_ASSERT_TRUE(steam_control_protection_margin(&narrowing, &margin));

    int32_t taken_milli_c = declaration.ready_temperature_milli_c;
    int32_t refused_milli_c = 400000;

    while (refused_milli_c - taken_milli_c > 100) {
        const int32_t middle_milli_c = (taken_milli_c + refused_milli_c) / 2;

        asking.ready_temperature_milli_c = middle_milli_c;
        hw_sim_reset();
        if (steam_control_init(&narrowing, &limits, &asking, &parameters, &budget)) {
            taken_milli_c = middle_milli_c;
        } else {
            refused_milli_c = middle_milli_c;
        }
    }

    (void)snprintf(message, sizeof(message),
                   "the declaration names %.3f C and the highest the margin leaves room for is "
                   "%.3f C, against a widened margin of %.4f C",
                   (double)declaration.ready_temperature_milli_c / 1000.0,
                   (double)taken_milli_c / 1000.0, (double)margin.margin_c);

    TEST_ASSERT_TRUE_MESSAGE(taken_milli_c > declaration.ready_temperature_milli_c, message);
    TEST_ASSERT_TRUE_MESSAGE(margin.margin_c > 0.0f,
                             "the declared error widened this loop's margin by nothing, so the "
                             "headroom above is not a statement about model error");

    /* And one step past the edge is refused, so the edge is the loop's and not this case's. */
    asking.ready_temperature_milli_c = refused_milli_c;
    hw_sim_reset();
    TEST_ASSERT_FALSE_MESSAGE(
        steam_control_init(&narrowing, &limits, &asking, &parameters, &budget),
        "the loop came up at a ready target above the highest the narrowing found, so the "
        "headroom reported is not the margin's own edge");
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-SENSING-ERROR.C1: the steam loop's own
/// margin reader carries a nonzero declared sensing error, on the same terms
/// the coffee loop's does -- carried explicitly rather than silently absent on
/// this side of the machine, which is the half of the criterion's "on each
/// loop" claim nothing else in this file pins down: every other margin
/// assertion in this suite reads `sensing_error_c` back out of the same figure
/// it is folded into, so a steam-side regression that zeroed it would still
/// pass every other case here.
static void test_the_steam_margin_reader_carries_the_declared_sensing_error(void)
{
    steam_control_state_t state;
    protection_margin_t margin;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration, &parameters, &budget));
    TEST_ASSERT_TRUE(steam_control_protection_margin(&state, &margin));
    TEST_ASSERT_TRUE_MESSAGE(margin.sensing_error_c > 0.0f,
                             "the steam loop's margin reader carries no declared sensing error at "
                             "all");
}

/// SOL-SIM-ROBUSTNESS-MARGIN-WIDENS-WITH-MODEL-ERROR.C1: The widened margin is
/// what this loop actually enforces against the ready target it is handed,
/// rather than a figure computed and left unused.
///
/// The same declaration is put to the loop twice against two descriptions
/// differing in nothing but how far out they say the steam element may be.
/// Against the shipped figures the ready target is taken; against a description
/// declaring the element far looser -- widening the margin past the gap the
/// ready target leaves to the block's own protection -- the loop refuses to
/// come up at all. A margin computed and discarded would accept both.
static void test_a_ready_target_inside_the_widened_margin_is_refused(void)
{
    steam_control_declaration_t ambitious = declaration;
    steam_control_state_t refused_loop;
    protection_margin_t margin;

    /*
     * The highest ready target the shipped description leaves room for, asked
     * of the loop by narrowing on it rather than worked out from a trip point
     * read out of the control source: a suite computing that figure for itself
     * would be asserting against its own arithmetic. The case is then run a
     * degree under it, which the shipped description takes.
     */
    int32_t taken_milli_c = declaration.ready_temperature_milli_c;
    int32_t refused_milli_c = 200000;

    while (refused_milli_c - taken_milli_c > 100) {
        const int32_t middle_milli_c = (taken_milli_c + refused_milli_c) / 2;

        ambitious.ready_temperature_milli_c = middle_milli_c;
        hw_sim_reset();
        if (steam_control_init(&refused_loop, &limits, &ambitious, &parameters, &budget)) {
            taken_milli_c = middle_milli_c;
        } else {
            refused_milli_c = middle_milli_c;
        }
    }

    ambitious.ready_temperature_milli_c = taken_milli_c - 1000;
    TEST_ASSERT_TRUE_MESSAGE(ambitious.ready_temperature_milli_c >
                                 declaration.ready_temperature_milli_c,
                             "the shipped description's own margin already refuses every target "
                             "above the one it ships with, so this case tests nothing");

    hw_sim_reset();
    TEST_ASSERT_TRUE_MESSAGE(
        steam_control_init(&refused_loop, &limits, &ambitious, &parameters, &budget),
        "the ready target this case turns on is already refused against the shipped description, "
        "so a refusal below would establish nothing about the declared error");
    TEST_ASSERT_TRUE(steam_control_protection_margin(&refused_loop, &margin));

    const plant_parameters_t loose = machine_with_scaled("steam.loss_w_per_k", 1.0f);
    plant_parameter_budget_t widened = budget;

    /*
     * The declared error on every coefficient of the description is widened
     * together rather than one being singled out: what this case is about is
     * the loop refusing a target the margin no longer leaves room for, and
     * which coefficient earned the margin is C1's own sweep on the coffee side
     * rather than this one's.
     */
    for (size_t at = 0u; at < widened.count; at++) {
        if (widened.declared[at]) {
            widened.assumed_error[at] = 0.95f;
        }
    }

    protection_margin_t wider;
    steam_control_state_t probing;
    steam_control_declaration_t modest = declaration;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&probing, &limits, &modest, &loose, &widened));
    TEST_ASSERT_TRUE(steam_control_protection_margin(&probing, &wider));
    TEST_ASSERT_TRUE_MESSAGE(wider.margin_c > margin.margin_c,
                             "widening every declared error did not widen the margin, so the "
                             "refusal below would not be about the declared error");

    hw_sim_reset();
    TEST_ASSERT_FALSE_MESSAGE(
        steam_control_init(&refused_loop, &limits, &ambitious, &loose, &widened),
        "a ready target inside the widened protection margin was taken");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(
        0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
        "the refusal left the steam element commanded on");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_steam_knob_reaches_the_seam_as_a_discrete_reading);
    RUN_TEST(test_only_a_trustworthy_set_knob_reading_is_taken_for_a_draw);
    RUN_TEST(test_the_controlled_variable_switches_on_the_step_the_draw_begins);
    RUN_TEST(test_the_heater_answers_superheat_and_never_pressure_error);
    RUN_TEST(test_an_implausible_pressure_reading_mid_draw_is_rejected_rather_than_acted_on);
    RUN_TEST(test_the_declared_ready_target_is_where_the_loop_settles);
    RUN_TEST(test_the_declared_band_decides_which_draws_the_suite_accepts);
    RUN_TEST(test_a_declared_gain_moves_the_pass_fail_boundary);
    RUN_TEST(test_the_declaration_grammar_refuses_what_it_must);
    RUN_TEST(test_a_draw_start_above_the_feed_ceiling_is_refused_as_its_own_fault);
    RUN_TEST(test_a_hand_built_declaration_with_the_start_above_the_ceiling_is_refused_by_the_law);
    RUN_TEST(test_a_hand_built_declaration_with_the_floor_at_or_above_the_ceiling_is_refused_by_the_law);
    RUN_TEST(test_a_hand_built_declaration_with_a_figure_out_of_range_is_refused_by_the_law);
    RUN_TEST(test_pressure_and_superheat_hold_for_draws_of_every_duration);
    RUN_TEST(test_superheat_holds_the_setpoint_across_the_error_ends_of_every_coefficient_that_decides_it);
    RUN_TEST(test_superheat_stays_above_zero_at_every_joint_corner_of_the_deciding_coefficients);
    RUN_TEST(test_the_casting_is_held_at_ready_while_the_superheat_stands_above_its_floor);
    RUN_TEST(test_the_feed_yields_to_dryness_when_the_element_cannot_boil_what_the_ceiling_admits);
    RUN_TEST(test_feed_never_exceeds_its_ceiling_or_rises_faster_than_its_limit);
    RUN_TEST(test_the_feed_ceiling_rise_limit_and_start_level_are_read_as_data);
    RUN_TEST(test_when_the_ceiling_binds_pressure_yields_before_quantity_or_quality);
    RUN_TEST(test_a_wand_opened_at_ready_is_fed_and_one_just_below_is_starved);
    RUN_TEST(test_the_casting_returns_to_ready_after_draws_of_every_duration);
    RUN_TEST(test_recovery_holds_its_bound_across_the_declared_model_error);
    RUN_TEST(test_a_longer_saturated_interval_does_not_deepen_the_overshoot);
    RUN_TEST(test_intent_is_surrendered_at_the_limit_and_not_afterwards);
    RUN_TEST(test_the_pressure_loop_accumulates_nothing_while_held_at_its_ceiling);
    RUN_TEST(test_the_superheat_loop_accumulates_nothing_while_the_heater_is_full);
    RUN_TEST(test_a_disturbance_to_the_truth_plant_alone_reaches_the_law);
    RUN_TEST(test_a_machine_unlike_the_declarations_own_holds_the_band_less_well);
    RUN_TEST(test_perturbing_heater_power_moves_superheat_and_leaves_pressure_to_the_feed);
    RUN_TEST(test_feed_withheld_while_pressure_stays_below_threshold_with_the_wand_open);
    RUN_TEST(test_feed_withheld_one_milli_bar_below_threshold);
    RUN_TEST(test_feed_enabled_the_same_step_pressure_reaches_threshold);
    RUN_TEST(test_a_draw_opened_below_ready_cannot_cross_it_while_the_wand_stays_open);
    RUN_TEST(test_feed_enabled_against_the_plant_models_own_truth);
    RUN_TEST(test_declared_threshold_moves_the_feed_boundary);
    RUN_TEST(test_the_law_runs_against_the_simulated_implementation_with_no_target_dependency);
    RUN_TEST(test_feed_withheld_when_no_pressure_reading_has_ever_been_trusted);
    RUN_TEST(test_init_is_refused_and_leaves_both_channels_off_without_either_record);
    RUN_TEST(test_init_is_refused_without_a_description_or_a_budget);
    RUN_TEST(test_the_accessors_refuse_nowhere_to_answer);
    RUN_TEST(test_output_refused_is_reported_rather_than_folded_into_actuated);
    RUN_TEST(test_a_refused_heater_command_does_not_leave_the_feed_running);
    RUN_TEST(test_init_reports_a_refused_off_command_but_leaves_the_loop_usable);
    RUN_TEST(test_a_reopened_draw_is_judged_afresh);
    RUN_TEST(test_a_draw_lands_within_its_band_at_every_declared_error_corner);
    RUN_TEST(test_the_sweep_draws_at_the_declared_ready_target_and_not_at_the_margins_edge);
    RUN_TEST(test_the_steam_margin_reader_carries_the_declared_sensing_error);
    RUN_TEST(test_a_ready_target_inside_the_widened_margin_is_refused);
    RUN_TEST(test_a_closed_loop_draw_is_stated_dry_with_its_figures_and_the_caveat);
    return UNITY_END();
}
