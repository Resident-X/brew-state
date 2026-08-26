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

/*
 * A steam temperature comfortably below the declared ready target, used where
 * a test needs the block left cooler than the loop wants it. Chosen without
 * reaching for any coefficient by name, and above the declared saturation
 * temperature so the path still carries some gauge pressure there.
 */
#define BELOW_READY_C 110.0f

/* The coefficient the plant description names as the loosest figure it carries. */
#define SAG_COEFFICIENT "steam.pressure_fall_bar_per_ml"

static plant_parameters_t parameters;
static plant_parameter_budget_t budget;
static estimator_limits_t limits;
static steam_control_declaration_t declaration;

static char description_text[16384];
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
        "margin-building-interval-ms = %d milli-s @estimated a figure this test chose\n"
        "feed-rise-interval-ms = %d milli-s @estimated a figure this test chose\n"
        "sustainable-feed-rate = %d permille @estimated a figure this test chose\n"
        "ready-temperature-gain = %d milli-permille-per-k @estimated a figure this test chose\n"
        "ready-temperature-integral-gain = %d milli-permille-per-k-s @estimated a figure this test chose\n"
        "draw-pressure-gain = %d milli-permille-per-bar @estimated a figure this test chose\n"
        "draw-pressure-integral-gain = %d milli-permille-per-bar-s @estimated a figure this test chose\n"
        "feed-load-gain = %d milli-permille-per-permille @estimated a figure this test chose\n"
        "standing-load = %d permille @estimated a figure this test chose\n",
        d->ready_pressure_milli_bar, d->ready_temperature_milli_c,
        d->draw_pressure_floor_milli_bar, d->draw_pressure_ceiling_milli_bar,
        d->margin_interval_millis, d->feed_rise_millis, d->sustainable_feed_permille,
        d->ready_gain_milli_permille_per_k, d->ready_integral_gain_milli_permille_per_k_s,
        d->draw_gain_milli_permille_per_bar, d->draw_integral_gain_milli_permille_per_bar_s,
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
static const char *description_with(const char *name, const char *value)
{
    static char rewritten[sizeof(description_text)];
    const size_t name_length = strlen(name);
    size_t written = 0u;
    size_t at = 0u;
    bool replaced = false;

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

        bool names_it = (size_t)(end - cursor) > name_length &&
                        memcmp(&description_text[cursor], name, name_length) == 0;
        if (names_it) {
            size_t after = cursor + name_length;
            while (after < end &&
                   (description_text[after] == ' ' || description_text[after] == '\t')) {
                after++;
            }
            names_it = after < end && description_text[after] == '=';
        }

        if (names_it) {
            written += (size_t)snprintf(&rewritten[written], sizeof(rewritten) - written,
                                        "%s = %s\n", name, value);
            replaced = true;
        } else {
            written += (size_t)snprintf(&rewritten[written], sizeof(rewritten) - written, "%.*s\n",
                                        (int)(end - at), &description_text[at]);
        }
        TEST_ASSERT_TRUE(written < sizeof(rewritten));
        at = (end < description_length) ? end + 1u : description_length;
    }

    TEST_ASSERT_TRUE_MESSAGE(replaced, "the coefficient to be perturbed is not in the description");
    return rewritten;
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

    TEST_ASSERT_TRUE(steam_control_init(&loop, &limits, figures));
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
        TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));
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

/// SOL-SIM-STEAM-BAND-SUSTAINED.C1: The controlled variable is temperature
/// while idle and pressure while a draw is active.
///
/// The switch is asserted on the same step the wand's report changes, in both
/// directions, and against the law's own account of which variable it is
/// driving to rather than against a duty -- because during the margin-building
/// interval the duty is the ceiling whichever variable is in force, which C1's
/// own text says is the same command either way with feed still at nothing.
/// A caller that switched on the step after would spend the first interval of
/// a draw -- the one the operator can least afford it in -- answering the
/// question the wand has already stopped asking.
static void test_the_controlled_variable_switches_on_the_step_the_draw_begins(void)
{
    steam_control_state_t state;
    steam_control_variable_t variable;

    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));

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

/// SOL-SIM-STEAM-BAND-SUSTAINED.C1: The controlled variable is temperature
/// while idle and pressure while a draw is active.
///
/// The behavioural half of the same criterion, which the projection above
/// cannot establish on its own: a projection could be right while the duty was
/// computed from the other channel entirely. Each phase is given a step where
/// one reading moves and the other is held exactly where it was, and the duty
/// is required to answer the one the phase is supposed to be driving to and
/// not the other. The draw phase is sampled past the margin-building interval,
/// where the duty is the tracking law's rather than the ceiling.
static void test_duty_answers_temperature_while_idle_and_pressure_while_drawing(void)
{
    steam_control_state_t state;

    /* Idle: pressure held, temperature moved. */
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));
    const uint16_t idle_at_target = step_with(&state, false, declaration.ready_pressure_milli_bar,
                                              declaration.ready_temperature_milli_c);
    const uint16_t idle_cooler = step_with(&state, false, declaration.ready_pressure_milli_bar,
                                           declaration.ready_temperature_milli_c - 5000);
    TEST_ASSERT_TRUE_MESSAGE(idle_cooler > idle_at_target,
                             "a colder block did not raise duty while idle, so the idle phase is "
                             "not driving to temperature");

    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));
    const uint16_t idle_again = step_with(&state, false, declaration.ready_pressure_milli_bar,
                                          declaration.ready_temperature_milli_c);
    const uint16_t idle_pressure_moved =
        step_with(&state, false, declaration.ready_pressure_milli_bar + 400,
                  declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(idle_again, idle_pressure_moved,
                                     "moving the pressure reading moved the duty while idle, so "
                                     "the idle phase is driving to pressure");

    /*
     * Drawing, sampled past the margin-building interval so the duty is the
     * tracking law's own rather than the ceiling, and past the feed's own rise
     * so that the level being fed forward is identical at both probes. A pair
     * of probes taken while feed was still climbing would differ by the
     * feedforward's answer to that climb whichever variable was in force, and
     * would say nothing about which one.
     */
    const int32_t in_band = (declaration.draw_pressure_floor_milli_bar +
                             declaration.draw_pressure_ceiling_milli_bar) /
                            2;
    const uint32_t settled_at =
        (uint32_t)declaration.margin_interval_millis + (uint32_t)declaration.feed_rise_millis;

    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));
    for (uint32_t elapsed = 0u; elapsed <= settled_at; elapsed += STEP_INTERVAL_MS) {
        (void)step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
    }
    const uint16_t drawing_at_target =
        step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
    const uint16_t drawing_sagged =
        step_with(&state, true, in_band - 200, declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE_MESSAGE(drawing_sagged > drawing_at_target,
                             "a sagging path did not raise duty during a draw, so the draw phase "
                             "is not driving to pressure");

    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));
    for (uint32_t elapsed = 0u; elapsed <= settled_at; elapsed += STEP_INTERVAL_MS) {
        (void)step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
    }
    const uint16_t drawing_again =
        step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
    const uint16_t drawing_temperature_moved =
        step_with(&state, true, in_band, declaration.ready_temperature_milli_c - 20000);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(drawing_again, drawing_temperature_moved,
                                     "moving the temperature reading moved the duty during a "
                                     "draw, so the draw phase is driving to temperature");
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
        TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));

        /* A settled draw: past the margin interval and past the feed's rise. */
        const uint32_t settled_at = (uint32_t)declaration.margin_interval_millis +
                                    (uint32_t)declaration.feed_rise_millis;
        for (uint32_t elapsed = 0u; elapsed <= settled_at + STEP_INTERVAL_MS;
             elapsed += STEP_INTERVAL_MS) {
            (void)step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
        }

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
    static const int32_t TARGETS[] = {120000, 130000};
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
/// is the feedforward, because what it answers is the load the loop was told
/// about: at the shipped figure it asks the element for what the commanded
/// feed will cost and the draw stays in band, and at a figure five times too
/// large it asks for far more than the load, drives the block past what the
/// band admits, and the same run fails.
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
                             "the shipped feedforward gain did not hold the band");

    steam_control_declaration_t altered = declaration;
    altered.feed_load_gain_milli_permille_per_permille =
        declaration.feed_load_gain_milli_permille_per_permille * 5;
    const steam_control_declaration_t overstated = re_declared(&altered);

    bring_the_loop_up(&parameters, &overstated, ready_target_c(&overstated));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(30u, 1.0f);
    TEST_ASSERT_FALSE_MESSAGE(in_band_from_first_delivery(&overstated, &worst),
                              "a feedforward gain five times the load it answers still held the "
                              "band, so the gain is not being read");
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
        {"margin-building-interval-ms = 600000 milli-s @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"sustainable-feed-rate = 0 permille @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"ready-temperature-gain = 0 milli-permille-per-k @estimated an account\n",
         STEAM_CONTROL_DECLARATION_OUT_OF_RANGE},
        {"ready-pressure-bar = 900 milli-c @estimated an account\n",
         STEAM_CONTROL_DECLARATION_UNIT_MISMATCH},
        {"draw-pressure-gain = 3000000 milli-permille-per-k @estimated an account\n",
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
        STEAM_CONTROL_DECLARATION_MARGIN_INTERVAL_WORD,
        STEAM_CONTROL_DECLARATION_FEED_RISE_WORD,
        STEAM_CONTROL_DECLARATION_SUSTAINABLE_FEED_WORD,
        STEAM_CONTROL_DECLARATION_READY_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_READY_INTEGRAL_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_DRAW_GAIN_WORD,
        STEAM_CONTROL_DECLARATION_DRAW_INTEGRAL_GAIN_WORD,
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

/* --- Holding the band, and coming back afterwards -------------------------- */

/// SOL-SIM-STEAM-BAND-SUSTAINED.C5: Measured pressure stays within the
/// declared band for the whole of a draw, within the declared model-error
/// tolerance.
///
/// SOL-SIM-STEAM-BAND-SUSTAINED.C9: The host harness closes the loop through a
/// truth plant the control law does not share.
///
/// Four durations from a brief pull to an extended one, each against three
/// machines: the description's own figure for how far a draw drags the steam
/// path down, and that figure at both ends of the error the description itself
/// declares on it. That coefficient is the loosest figure thermoblock.params
/// carries -- a first-principles guess against a path nobody has instrumented
/// -- so a run at one assumed-exact value would be testing the guess rather
/// than the loop, which is what this criterion's own text refuses.
///
/// The nominal figure is read back out of the model rather than typed here,
/// and the perturbed descriptions go back through the same loader, so a
/// machine this run is closed against is one the structure admits.
static void test_pressure_holds_the_band_for_draws_of_every_duration_across_the_declared_error(void)
{
    static const unsigned DURATIONS[] = {3u, 10u, 30u, 60u};
    float assumed_error = 0.0f;

    TEST_ASSERT_TRUE_MESSAGE(
        plant_parameter_budget_for(&budget, SAG_COEFFICIENT, &assumed_error),
        "the description declares no error on the coefficient this criterion is tested across");
    TEST_ASSERT_TRUE_MESSAGE(assumed_error > 0.0f,
                             "the description declares that coefficient exact, which is not what "
                             "its own account says");

    const float FACTORS[] = {1.0f - assumed_error, 1.0f, 1.0f + assumed_error};

    for (size_t corner = 0u; corner < sizeof(FACTORS) / sizeof(FACTORS[0]); corner++) {
        const plant_parameters_t machine = machine_with_scaled(SAG_COEFFICIENT, FACTORS[corner]);

        for (size_t which = 0u; which < sizeof(DURATIONS) / sizeof(DURATIONS[0]); which++) {
            char message[128];
            int32_t worst = 0;

            bring_the_loop_up(&machine, &declaration, ready_target_c(&declaration));
            hold_ready_for(SETTLE_SECONDS);
            draw_for(DURATIONS[which], 1.0f);

            const bool held = in_band_from_first_delivery(&declaration, &worst);
            (void)snprintf(message, sizeof(message),
                           "a %u second draw at %.2f times the declared sag left the band at %d "
                           "milli-bar",
                           DURATIONS[which], (double)FACTORS[corner], worst);
            TEST_ASSERT_TRUE_MESSAGE(held, message);
        }
    }
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C6: Once engaged, feed is commanded at a
/// declared sustainable rate, not a rate requiring an unobservable demand
/// reading.
///
/// Several different demands are put behind the same open wand and the
/// commanded feed, sampled only after the rise has completed, is required to
/// be the declared rate in every one of them. The demands are all above that
/// rate deliberately: what the criterion is about is that no law here varies
/// feed with how much is being asked for, because the microswitch reports that
/// the wand is turned and nothing else, so there is nothing to vary it with.
static void test_settled_feed_is_the_declared_rate_whatever_demand_is(void)
{
    static const float DEMANDS[] = {0.25f, 1.0f, 5.0f};

    for (size_t at = 0u; at < sizeof(DEMANDS) / sizeof(DEMANDS[0]); at++) {
        char message[96];

        bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
        hold_ready_for(SETTLE_SECONDS);
        draw_for(20u, DEMANDS[at]);

        const uint32_t settled_at = (uint32_t)declaration.margin_interval_millis +
                                    (uint32_t)declaration.feed_rise_millis;
        size_t settled = 0u;
        for (size_t step = 0u; step < sample_count; step++) {
            if (samples[step].at_millis >= settled_at) {
                settled++;
                (void)snprintf(message, sizeof(message),
                               "settled feed followed a demand of %.2f ml/s", (double)DEMANDS[at]);
                TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.sustainable_feed_permille,
                                                 samples[step].feed_permille, message);
            }
        }
        TEST_ASSERT_TRUE_MESSAGE(settled > 0u, "the draw never reached its settled rate");
    }
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C11: Delivered character stays in band because
/// feed is never raised to chase demand beyond the declared sustainable rate.
///
/// A demand far beyond anything the block could sustain is put behind the
/// wand, and two things are required of the run: pressure stays inside the
/// declared band throughout, and the rate actually delivered does not climb to
/// meet the larger demand.
///
/// That second half is asserted by comparing two runs whose demands differ by
/// a factor of twenty and requiring their pressure traces to be identical step
/// for step. The plant charges its pressure relation against the steam it
/// actually made, which is the lower of what was asked for and what feed
/// replaced -- so a delivered rate that had climbed with the demand would have
/// dragged the path down further and the two traces would part. That they do
/// not is the seam-level statement that nothing downstream of the cap ever saw
/// the larger demand, which reading the commanded level alone could not
/// establish.
static void test_feed_is_never_raised_to_chase_demand_beyond_the_sustainable_rate(void)
{
    static const float DEMANDS[] = {0.25f, 5.0f};
    static int32_t trace[2][DRAW_SAMPLE_MAX];
    size_t recorded = 0u;
    int32_t worst = 0;

    for (size_t run = 0u; run < sizeof(DEMANDS) / sizeof(DEMANDS[0]); run++) {
        bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
        hold_ready_for(SETTLE_SECONDS);
        draw_for(30u, DEMANDS[run]);

        TEST_ASSERT_TRUE_MESSAGE(in_band_from_first_delivery(&declaration, &worst),
                                 "a draw beyond what the block can sustain left the band, so "
                                 "quality was given up rather than quantity");

        const uint32_t settled_at = (uint32_t)declaration.margin_interval_millis +
                                    (uint32_t)declaration.feed_rise_millis;
        for (size_t step = 0u; step < sample_count; step++) {
            if (samples[step].at_millis >= settled_at) {
                TEST_ASSERT_TRUE_MESSAGE(
                    samples[step].feed_permille <=
                        (uint16_t)declaration.sustainable_feed_permille,
                    "settled feed was commanded past the declared sustainable rate");
            }
            trace[run][step] = samples[step].pressure_milli_bar;
        }
        recorded = sample_count;
    }

    for (size_t step = 0u; step < recorded; step++) {
        TEST_ASSERT_EQUAL_INT32_MESSAGE(trace[0][step], trace[1][step],
                                        "a demand twenty times larger moved the path, so the rate "
                                        "actually delivered climbed to meet it");
    }

    /*
     * A third arm, below the cap rather than above it, which is what keeps
     * the two identical traces above from being explicable by a plant that
     * ignores demand altogether. Both arms above sit above the declared
     * sustainable rate, so the rate delivered is the cap in each and the
     * traces would also match on a model that never read the demand at all.
     * A demand under the cap is the case where the demand is what binds, and
     * the path is required to differ -- less steam made, so less pressure
     * given up.
     */
    const float under_the_cap = 0.02f;
    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(30u, under_the_cap);

    bool differed = false;
    for (size_t step = 0u; step < recorded && step < sample_count; step++) {
        differed = differed || samples[step].pressure_milli_bar != trace[0][step];
    }
    TEST_ASSERT_TRUE_MESSAGE(differed,
                             "a demand below the declared sustainable rate produced the same path "
                             "as one far above it, so nothing downstream reads the demand and the "
                             "identical traces above establish nothing about the cap");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C8: Heater leads and feed lags by a declared
/// interval on demand starting, so delivered steam starts in character.
///
/// Two arms differing in one declared figure. The feed's own rise duration is
/// held fixed at its shipped, nonzero value in both, so that neither arm can
/// be explained by the rise instead of by the interval under test -- which is
/// what the criterion's own text requires and is the whole reason the two
/// intervals have separate tests.
///
/// The block starts both arms held correctly at the declared ready target,
/// which is where the criterion bites: ready means a draw will not be starved,
/// and it sits below the band the delivered steam has to be inside. With the
/// margin-building interval present the element alone carries the block into
/// the band before any steam is made, and the first steam delivered is in
/// character. With it zeroed, feed begins replacing water immediately and the
/// first steam is made out of a block that had not yet earned the margin --
/// out of band, which is exactly the wet start the sequencing exists to
/// prevent.
///
/// The heater being at its ceiling from the first step of the draw is asserted
/// alongside, because "the heater leads" is a claim about the heater and not
/// only about the feed: an arm that merely delayed the feed without driving
/// the element would take longer to reach the band and would pass a test that
/// looked at the feed alone.
static void test_the_heater_leads_and_the_feed_lags_by_the_declared_interval(void)
{
    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(20u, 1.0f);

    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)ACTUATION_FULL_SCALE, samples[0].heater_permille,
                                     "the element was not at its ceiling on the first step of the "
                                     "draw, so the heater does not lead");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, samples[0].feed_permille,
                                     "feed engaged on the first step of the draw, so it does not "
                                     "lag");

    /*
     * That the element leads is asserted a second time, against a draw
     * beginning with the path already in the middle of its band. The
     * assertion just above cannot tell leading apart from ordinary tracking:
     * a draw beginning from a correctly held ready state starts most of a
     * band-width below the draw target, and the proportional term alone
     * saturates the element there without any sequencing doing it -- so that
     * assertion would go on passing with the sequencing removed. With the
     * error at nothing the tracking law commands little more than the
     * declared standing load, and a ceiling can only have come from the
     * heater being made to lead.
     */
    steam_control_state_t leading_only;
    const int32_t at_draw_target = (declaration.draw_pressure_floor_milli_bar +
                                    declaration.draw_pressure_ceiling_milli_bar) /
                                   2;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&leading_only, &limits, &declaration));
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(
        (uint16_t)ACTUATION_FULL_SCALE,
        step_with(&leading_only, true, at_draw_target, declaration.ready_temperature_milli_c),
        "the element was not driven to its ceiling on a draw beginning already in band, so what "
        "saturates it on an ordinary draw is the tracking error rather than the heater leading");

    const sample_t *const with_margin = first_delivery();
    TEST_ASSERT_NOT_NULL_MESSAGE(with_margin, "the draw never fed anything");
    TEST_ASSERT_TRUE_MESSAGE(
        with_margin->at_millis >= (uint32_t)declaration.margin_interval_millis,
        "feed engaged before the declared margin-building interval had elapsed");
    TEST_ASSERT_TRUE_MESSAGE(
        with_margin->pressure_milli_bar >= declaration.draw_pressure_floor_milli_bar &&
            with_margin->pressure_milli_bar <= declaration.draw_pressure_ceiling_milli_bar,
        "the first steam delivered with the margin-building interval present was out of band");

    steam_control_declaration_t altered = declaration;
    altered.margin_interval_millis = 0;
    const steam_control_declaration_t no_margin = re_declared(&altered);
    TEST_ASSERT_EQUAL_INT32_MESSAGE(declaration.feed_rise_millis, no_margin.feed_rise_millis,
                                    "the arms differ in more than the interval under test");
    TEST_ASSERT_TRUE_MESSAGE(no_margin.feed_rise_millis > 0,
                             "the feed's own rise is not held nonzero in both arms");

    bring_the_loop_up(&parameters, &no_margin, ready_target_c(&no_margin));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(20u, 1.0f);

    const sample_t *const without_margin = first_delivery();
    TEST_ASSERT_NOT_NULL_MESSAGE(without_margin, "the draw never fed anything");
    TEST_ASSERT_TRUE_MESSAGE(
        without_margin->pressure_milli_bar < declaration.draw_pressure_floor_milli_bar,
        "the first steam delivered with the margin-building interval zeroed was still in band, so "
        "the interval is not what carries the block into it");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C12: Once engaged, feed rises to its
/// sustainable rate over a declared interval rather than stepping.
///
/// Two arms differing in one declared figure, with the margin-building
/// interval held fixed at its shipped, nonzero value in both -- so that
/// neither arm can be explained by the delay before feed starts rather than by
/// the shape of what feed does once it has. This is the mirror of the
/// margin-building interval's own test, and the pair is deliberate: each holds
/// the other's interval nonzero so that neither is exercised as if it alone
/// explained a good start.
///
/// What separates the arms is the first control step past engagement. With the
/// rise zeroed, feed is at the full declared rate on that very step. With the
/// rise present it is not, and it goes on climbing afterwards without ever
/// passing the declared rate.
static void test_engaged_feed_rises_over_the_declared_interval_rather_than_stepping(void)
{
    steam_control_declaration_t altered = declaration;
    altered.feed_rise_millis = 0;
    const steam_control_declaration_t no_rise = re_declared(&altered);

    TEST_ASSERT_EQUAL_INT32_MESSAGE(declaration.margin_interval_millis,
                                    no_rise.margin_interval_millis,
                                    "the arms differ in more than the interval under test");
    TEST_ASSERT_TRUE_MESSAGE(no_rise.margin_interval_millis > 0,
                             "the margin-building interval is not held nonzero in both arms");

    /* The step feed is first allowed to engage on, which both arms share. */
    const uint32_t engaged_at = (uint32_t)declaration.margin_interval_millis;

    bring_the_loop_up(&parameters, &no_rise, ready_target_c(&no_rise));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(10u, 1.0f);

    size_t at = 0u;
    while (at < sample_count && samples[at].at_millis < engaged_at) {
        at++;
    }
    TEST_ASSERT_TRUE_MESSAGE(at < sample_count, "the draw ended before feed could engage");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)no_rise.sustainable_feed_permille,
                                     samples[at].feed_permille,
                                     "a rise declared as nothing did not reach the full rate on "
                                     "the first step past engagement");

    bring_the_loop_up(&parameters, &declaration, ready_target_c(&declaration));
    hold_ready_for(SETTLE_SECONDS);
    draw_for(10u, 1.0f);

    at = 0u;
    while (at < sample_count && samples[at].at_millis < engaged_at) {
        at++;
    }
    TEST_ASSERT_TRUE_MESSAGE(at < sample_count, "the draw ended before feed could engage");
    TEST_ASSERT_TRUE_MESSAGE(samples[at].feed_permille <
                                 (uint16_t)declaration.sustainable_feed_permille,
                             "the declared rise reached the full rate on the first step past "
                             "engagement, so feed is stepping rather than rising");

    /*
     * And it is a rise rather than a delay followed by a step: the level is
     * required to be strictly increasing somewhere inside the declared
     * interval and to have arrived by the end of it, without ever exceeding
     * the declared rate.
     */
    bool climbed = false;
    uint16_t previous = samples[at].feed_permille;
    while (at < sample_count &&
           samples[at].at_millis < engaged_at + (uint32_t)declaration.feed_rise_millis) {
        TEST_ASSERT_TRUE_MESSAGE(samples[at].feed_permille >= previous,
                                 "the rise went backwards");
        TEST_ASSERT_TRUE_MESSAGE(samples[at].feed_permille <=
                                     (uint16_t)declaration.sustainable_feed_permille,
                                 "the rise overshot the declared rate");
        climbed = climbed || samples[at].feed_permille > previous;
        previous = samples[at].feed_permille;
        at++;
    }
    TEST_ASSERT_TRUE_MESSAGE(climbed, "feed never climbed during the declared rise interval");
    TEST_ASSERT_TRUE_MESSAGE(at < sample_count, "the draw ended before the rise completed");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.sustainable_feed_permille,
                                     samples[at].feed_permille,
                                     "feed had not reached the declared rate by the end of the "
                                     "declared rise interval");
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

/// SOL-SIM-STEAM-BAND-SUSTAINED.C7: Recovery after a draw is the same
/// ready-holding control continuing, not a separate mechanism.
///
/// One instance of the law, brought up once, is asked to do three things in
/// sequence with nothing reinitialised and no second entry point called
/// between them: reach the ready target from a cold machine, hold a draw, and
/// then reach the ready target again from wherever that draw left the block.
/// That the second arrival happens at all is the criterion; that it happens
/// through the same steps as the first is what makes it the ready-holding
/// behaviour continuing rather than a recovery mechanism of its own. Feed is
/// asserted to be cut on the step the wand shuts rather than trailing off.
///
/// A finding this test records rather than assumes: on this plant model, with
/// feed capped at the declared sustainable rate, a draw leaves the block
/// *above* its ready target rather than below it. Holding the band while the
/// path's deficit accumulates is done by raising the block's temperature, and
/// the readiness policy cuts feed the moment the path falls below the ready
/// threshold, so a draw cannot run the block down. The criterion's own text
/// anticipates a draw that drags the temperature down, so the third arm below
/// puts the block there directly -- a disturbance to the machine and to
/// nothing else -- and requires the same law to carry it back up. Both
/// directions are covered because which one a real machine shows is a bench
/// question this model cannot settle.
static void test_recovery_is_the_ready_holding_law_continuing(void)
{
    /*
     * A genuinely cold machine: the block is stood up at the ambient the
     * description declares the machine sits in, read out of that description
     * rather than assumed, and well below the ready target. Reading the
     * starting temperature off the truth plant instead would take whatever the
     * previous test in this file happened to leave behind -- which is warm, and
     * would make this arm a cool-down that passes without the loop heating
     * anything.
     */
    const float ambient_c = nominal_of("ambient_temperature_c");
    TEST_ASSERT_TRUE_MESSAGE(ambient_c < ready_target_c(&declaration) - 50.0f,
                             "the declared ambient is not a cold start for this target");

    bring_the_loop_up(&parameters, &declaration, ambient_c);

    const uint32_t from_cold = millis_to_reach_ready(&declaration);
    TEST_ASSERT_TRUE_MESSAGE(from_cold < RECOVERY_BOUND_SECONDS * 1000u,
                             "the loop never reached the ready target from a cold start");
    TEST_ASSERT_TRUE_MESSAGE(from_cold > 0u,
                             "the block was already at its target, so nothing was heated");

    hold_ready_for(SETTLE_SECONDS);
    draw_for(60u, 1.0f);

    /*
     * The first step on which the wand reports shut, which is the step the
     * criterion says feed is cut on. It is run here rather than folded into
     * the draw above, because what the draw records is the draw.
     */
    (void)closed_loop_step();
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(
        0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
        "feed was still commanded on the step the wand shut");
    const float after_draw = truth_quantity(PLANT_QUANTITY_STEAM_TEMPERATURE_C);
    TEST_ASSERT_TRUE_MESSAGE(fabsf(after_draw - ready_target_c(&declaration)) > READY_TOLERANCE_C,
                             "the draw left the block already at its target, so there is nothing "
                             "for a recovery to do");

    /* The same instance, continuing, carries it back. */
    const uint32_t after = millis_to_reach_ready(&declaration);
    TEST_ASSERT_TRUE_MESSAGE(after < RECOVERY_BOUND_SECONDS * 1000u,
                             "the loop did not carry the block back to ready after a draw");

    /*
     * And from the other direction, reached by disturbing the machine alone.
     * The law is not reinitialised and no operator does anything: the wand
     * stays shut and the same steps go on running.
     */
    TEST_ASSERT_TRUE(plant_model_set_state(&truth, PLANT_STATE_STEAM_TEMPERATURE_C, BELOW_READY_C));
    TEST_ASSERT_TRUE_MESSAGE(BELOW_READY_C < ready_target_c(&declaration) - READY_TOLERANCE_C,
                             "the disturbance did not put the block below its target");

    const uint32_t from_below = millis_to_reach_ready(&declaration);
    TEST_ASSERT_TRUE_MESSAGE(from_below < RECOVERY_BOUND_SECONDS * 1000u,
                             "the loop did not carry a block left below its target back up");
}

/// SOL-SIM-STEAM-BAND-SUSTAINED.C7: Recovery after a draw is the same
/// ready-holding control continuing, not a separate mechanism.
///
/// The recovery time asserted above is claimed across the error the
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
/// The machine's steam path is made to sag further per millilitre drawn than
/// the declaration was sized against -- past the error the description itself
/// declares, so this is a machine outside what anything here claims to hold --
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
        const plant_parameters_t machine = machine_with_scaled(SAG_COEFFICIENT, FACTORS[run]);

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
                             "a machine sagging four times as hard held the band no worse than "
                             "one the declaration was sized against, so the loop is closed on "
                             "something other than the machine");
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
/// regardless, for long enough that the margin-building interval and the
/// feed's rise have both elapsed several times over: a run shorter than that
/// would be showing the sequencing rather than the threshold.
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
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    const plant_actuation_t idle = {{0u}};
    const uint32_t span = (uint32_t)declaration.margin_interval_millis +
                          (uint32_t)declaration.feed_rise_millis;

    for (uint32_t elapsed = 0u; elapsed < span * 3u; elapsed += STEP_INTERVAL_MS) {
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
/// The boundary itself: with a draw long since under way and everything else
/// that would gate feed already elapsed, a reading one milli-bar below the
/// declared threshold still withholds it. This is the case an off-by-one in
/// the comparison would first show up on, which a test set comfortably below
/// the threshold would never catch.
static void test_feed_withheld_one_milli_bar_below_threshold(void)
{
    steam_control_state_t gate;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    const uint32_t span = (uint32_t)declaration.margin_interval_millis +
                          (uint32_t)declaration.feed_rise_millis;
    for (uint32_t elapsed = 0u; elapsed <= span * 2u; elapsed += STEP_INTERVAL_MS) {
        (void)step_with(&gate, true, declaration.ready_pressure_milli_bar - 1,
                        declaration.ready_temperature_milli_c);
    }

    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
}

/// SOL-SIM-STEAM-READINESS-GATE.C2: Steam feed is enabled once measured
/// pressure reaches the declared ready threshold.
///
/// One instance stepped across the boundary with a draw already under way and
/// its sequencing long since elapsed, so that the threshold is the only thing
/// left deciding: withheld a milli-bar below it, available on the very step
/// the reading reaches it exactly, and still available comfortably above. The
/// middle assertion is the criterion in its own words -- feed becomes
/// available on the same step the threshold is crossed -- and the two either
/// side are the regression protection a boundary checked in isolation would
/// not give.
///
/// What duty the band-holding law then commands is out of that criterion's
/// scope and is asserted by this suite's own sustainable-rate tests instead;
/// what is required here is only that feed goes from nothing to something.
static void test_feed_enabled_the_same_step_pressure_reaches_threshold(void)
{
    steam_control_state_t gate;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

    const uint32_t span = (uint32_t)declaration.margin_interval_millis +
                          (uint32_t)declaration.feed_rise_millis;
    for (uint32_t elapsed = 0u; elapsed <= span * 2u; elapsed += STEP_INTERVAL_MS) {
        (void)step_with(&gate, true, declaration.ready_pressure_milli_bar - 1,
                        declaration.ready_temperature_milli_c);
    }
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

    (void)step_with(&gate, true, declaration.ready_pressure_milli_bar,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP) > 0u,
                             "feed was not available on the step the threshold was reached");

    (void)step_with(&gate, true, declaration.ready_pressure_milli_bar + 500,
                    declaration.ready_temperature_milli_c);
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP) > 0u,
                             "feed was withheld above the threshold");
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

/// SOL-SIM-STEAM-READINESS-GATE.C3: Withholding feed holds the pressure
/// deficit rather than letting an open wand widen it.
///
/// The truth plant is first driven with feed actually enabled and the wand
/// open, so the deficit genuinely grows and measured pressure genuinely sags
/// below the saturation relation -- a test starting from a rested, zero
/// deficit state would prove nothing, since a deficit that cannot grow either
/// way looks the same as one being held. Feed is then withheld while the wand
/// stays open, driven only through the law under test rather than set
/// directly, and pressure is asserted not to fall any further.
///
/// The plant's steam heater is deliberately left undriven throughout, though
/// the law commands it: what this criterion is about is the deficit, which is
/// measured against the saturation relation, and driving the element would
/// move that relation underneath the measurement. What the law does with the
/// element is asserted elsewhere in this file.
static void test_withheld_feed_holds_an_existing_deficit_against_an_open_wand(void)
{
    plant_model_t primed;
    steam_control_state_t gate;

    hw_sim_reset();
    TEST_ASSERT_TRUE(plant_model_init(&primed, &parameters));
    TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));
    TEST_ASSERT_TRUE(plant_model_set_state(&primed, PLANT_STATE_STEAM_TEMPERATURE_C, 115.0f));

    /*
     * Primed by driving the truth plant's feed directly rather than through
     * the law: this phase's whole purpose is to reach a state where the
     * deficit is already nonzero, which the law itself -- withholding feed
     * below the threshold -- would never produce. The temperature is chosen so
     * that the rested pressure it carries, and what a real draw sags it to,
     * both stay below the declared threshold.
     */
    plant_actuation_t feeding = {{0u}};
    feeding.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = (uint16_t)ACTUATION_FULL_SCALE;
    for (int step = 0; step < 5; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&primed, &feeding, 3.0f, STEP_INTERVAL_MS));
    }

    float primed_bar = 0.0f;
    TEST_ASSERT_TRUE(plant_model_quantity(&primed, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &primed_bar));
    TEST_ASSERT_TRUE_MESSAGE(
        (int32_t)lroundf(primed_bar * 1000.0f) < declaration.ready_pressure_milli_bar,
        "priming left the truth plant at or above the ready threshold, which this test did not "
        "intend");

    /*
     * Confirms the priming actually produced a nonzero deficit -- primed_bar
     * below the pressure a rested block at this temperature would carry --
     * which is the state this criterion's own text requires the test to start
     * from. Read through the same seam quantity the law is fed through,
     * against a second instance rested at the same starting temperature.
     */
    plant_model_t rested;
    TEST_ASSERT_TRUE(plant_model_init(&rested, &parameters));
    TEST_ASSERT_TRUE(plant_model_set_state(&rested, PLANT_STATE_STEAM_TEMPERATURE_C, 115.0f));
    const plant_actuation_t idle = {{0u}};
    TEST_ASSERT_TRUE(plant_model_step(&rested, &idle, 0.0f, STEP_INTERVAL_MS));
    float rested_saturation_bar = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_quantity(&rested, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &rested_saturation_bar));
    TEST_ASSERT_TRUE_MESSAGE(primed_bar < rested_saturation_bar - 0.01f,
                             "priming did not produce a nonzero deficit to hold");

    /*
     * Feed is now driven only through the law under test, reading the truth
     * plant's own pressure back at each step, with the wand still reported
     * turned throughout. A tolerance rather than exact equality because the
     * block goes on losing a little to ambient with the element undriven; it
     * is an order of magnitude below the drift a still-growing deficit would
     * show over the same steps at this priming rate, and it is a comparison
     * against the step before rather than against the start, so a long run
     * does not accumulate into it.
     *
     * The run is deliberately longer than the margin-building interval and
     * the feed's rise put together. A shorter one would hold feed at nothing
     * whether the readiness threshold existed or not -- the sequencing alone
     * withholds it for the first few seconds of any draw -- and would go on
     * passing with the withhold deleted, which is the one thing this test is
     * about.
     */
    const uint32_t withheld_steps =
        ((uint32_t)declaration.margin_interval_millis +
         (uint32_t)declaration.feed_rise_millis) / STEP_INTERVAL_MS + 5u;

    for (uint32_t step = 0u; step < withheld_steps; step++) {
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                          (int32_t)lroundf(primed_bar * 1000.0f));
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID, 115000);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);

        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&gate));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));

        plant_actuation_t withheld = {{0u}};
        withheld.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] =
            hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        TEST_ASSERT_TRUE(plant_model_step(&primed, &withheld, 3.0f, STEP_INTERVAL_MS));

        float held_bar = 0.0f;
        TEST_ASSERT_TRUE(plant_model_quantity(&primed, PLANT_QUANTITY_STEAM_PRESSURE_BAR,
                                              &held_bar));
        TEST_ASSERT_FLOAT_WITHIN(0.002f, primed_bar, held_bar);
        primed_bar = held_bar;

        hw_sim_advance_millis(STEP_INTERVAL_MS);
    }
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
    TEST_ASSERT_TRUE(steam_control_init(&gate_low, &limits, &low));
    TEST_ASSERT_TRUE(steam_control_init(&gate_high, &limits, &high));

    const uint32_t span =
        (uint32_t)declaration.margin_interval_millis + (uint32_t)declaration.feed_rise_millis;
    for (uint32_t elapsed = 0u; elapsed <= span * 2u; elapsed += STEP_INTERVAL_MS) {
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID, 1000);
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          declaration.ready_temperature_milli_c);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);
        (void)steam_control_step(&gate_low);
        const uint16_t fed = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        (void)steam_control_step(&gate_high);
        const uint16_t withheld = hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP);
        hw_sim_advance_millis(STEP_INTERVAL_MS);

        if (elapsed == span * 2u) {
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
        TEST_ASSERT_TRUE(steam_control_init(&gate, &limits, &declaration));

        const int32_t value = CASES[at].above_declared_high
                                  ? limits.high_milli[HW_SENSOR_STEAM_PRESSURE] + 1000
                                  : 0;
        hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, CASES[at].status, value);
        hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                          declaration.ready_temperature_milli_c);
        hw_sim_set_sensor(HW_SENSOR_STEAM_KNOB, HW_READING_VALID, HW_READING_DISCRETE_SET);

        TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&gate));
        TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
        TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
                                         "the element was driven with no reading to drive from");
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
    TEST_ASSERT_FALSE(steam_control_init(&state, NULL, &declaration));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER));
    TEST_ASSERT_FALSE(steam_control_variable(&state, &variable));
    TEST_ASSERT_FALSE(steam_control_drawing(&state, &drawing));
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(&state));

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(&state, &limits, NULL));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP));
    TEST_ASSERT_EQUAL_UINT16(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER));

    hw_sim_reset();
    TEST_ASSERT_FALSE(steam_control_init(NULL, &limits, &declaration));
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_SENSOR_INVALID, steam_control_step(NULL));
    TEST_ASSERT_FALSE(steam_control_variable(NULL, &variable));
    TEST_ASSERT_FALSE(steam_control_drawing(NULL, &drawing));
}

/// Regression protection for the accessors' null out-parameters, which a
/// caller cannot be told anything through and which must not be written.
static void test_the_accessors_refuse_nowhere_to_answer(void)
{
    steam_control_state_t state;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));
    TEST_ASSERT_FALSE(steam_control_variable(&state, NULL));
    TEST_ASSERT_FALSE(steam_control_drawing(&state, NULL));
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
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));

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
/// the pump was already running before the step began. Mid-draw the feed is at
/// the declared sustainable rate, and a refused heater command leaves the
/// element at a level nothing established -- so water goes on being pushed
/// into a block whose element may be at nothing, which is precisely the wet
/// start the margin-building sequencing exists to prevent, arriving by the one
/// path that bypasses that sequencing. control_step brings the brew side down
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
    const uint32_t settled_at =
        (uint32_t)declaration.margin_interval_millis + (uint32_t)declaration.feed_rise_millis;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));

    for (uint32_t elapsed = 0u; elapsed <= settled_at; elapsed += STEP_INTERVAL_MS) {
        (void)step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
    }
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)declaration.sustainable_feed_permille,
                                     hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "the draw was not feeding, so a refused heater command has "
                                     "nothing to have left running");

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
    TEST_ASSERT_FALSE(steam_control_init(&state, &limits, &declaration));

    hw_sim_set_output_refused(false);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, HW_READING_VALID,
                      declaration.ready_pressure_milli_bar);
    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, HW_READING_VALID,
                      declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL(STEAM_CONTROL_STEP_ACTUATED, steam_control_step(&state));
}

/// Regression protection for the draw clock: a draw closed and reopened earns
/// its margin-building interval again rather than resuming where the last one
/// left off. A law that carried the clock across would start feeding a block
/// immediately on the second draw of a pair, which is the wet start the
/// sequencing exists to prevent and which no test of a single draw would
/// notice.
static void test_a_reopened_draw_earns_its_margin_again(void)
{
    steam_control_state_t state;

    hw_sim_reset();
    TEST_ASSERT_TRUE(steam_control_init(&state, &limits, &declaration));

    const int32_t in_band = (declaration.draw_pressure_floor_milli_bar +
                             declaration.draw_pressure_ceiling_milli_bar) /
                            2;
    const uint32_t span = (uint32_t)declaration.margin_interval_millis +
                          (uint32_t)declaration.feed_rise_millis;

    for (uint32_t elapsed = 0u; elapsed <= span * 2u; elapsed += STEP_INTERVAL_MS) {
        (void)step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
    }
    TEST_ASSERT_TRUE_MESSAGE(hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP) > 0u,
                             "the first draw never fed anything");

    (void)step_with(&state, false, in_band, declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "feed was not cut on the step the wand shut");

    (void)step_with(&state, true, in_band, declaration.ready_temperature_milli_c);
    TEST_ASSERT_EQUAL_UINT16_MESSAGE(0u, hw_sim_output(ACTUATION_CHANNEL_STEAM_PUMP),
                                     "the second draw fed immediately, so the margin-building "
                                     "interval is carried across draws rather than earned again");
    TEST_ASSERT_EQUAL_UINT16_MESSAGE((uint16_t)ACTUATION_FULL_SCALE,
                                     hw_sim_output(ACTUATION_CHANNEL_STEAM_HEATER),
                                     "the element did not lead on the second draw");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_steam_knob_reaches_the_seam_as_a_discrete_reading);
    RUN_TEST(test_only_a_trustworthy_set_knob_reading_is_taken_for_a_draw);
    RUN_TEST(test_the_controlled_variable_switches_on_the_step_the_draw_begins);
    RUN_TEST(test_duty_answers_temperature_while_idle_and_pressure_while_drawing);
    RUN_TEST(test_an_implausible_pressure_reading_mid_draw_is_rejected_rather_than_acted_on);
    RUN_TEST(test_the_declared_ready_target_is_where_the_loop_settles);
    RUN_TEST(test_the_declared_band_decides_which_draws_the_suite_accepts);
    RUN_TEST(test_a_declared_gain_moves_the_pass_fail_boundary);
    RUN_TEST(test_the_declaration_grammar_refuses_what_it_must);
    RUN_TEST(test_pressure_holds_the_band_for_draws_of_every_duration_across_the_declared_error);
    RUN_TEST(test_settled_feed_is_the_declared_rate_whatever_demand_is);
    RUN_TEST(test_feed_is_never_raised_to_chase_demand_beyond_the_sustainable_rate);
    RUN_TEST(test_the_heater_leads_and_the_feed_lags_by_the_declared_interval);
    RUN_TEST(test_engaged_feed_rises_over_the_declared_interval_rather_than_stepping);
    RUN_TEST(test_recovery_is_the_ready_holding_law_continuing);
    RUN_TEST(test_recovery_holds_its_bound_across_the_declared_model_error);
    RUN_TEST(test_a_disturbance_to_the_truth_plant_alone_reaches_the_law);
    RUN_TEST(test_a_machine_unlike_the_declarations_own_holds_the_band_less_well);
    RUN_TEST(test_feed_withheld_while_pressure_stays_below_threshold_with_the_wand_open);
    RUN_TEST(test_feed_withheld_one_milli_bar_below_threshold);
    RUN_TEST(test_feed_enabled_the_same_step_pressure_reaches_threshold);
    RUN_TEST(test_feed_enabled_against_the_plant_models_own_truth);
    RUN_TEST(test_withheld_feed_holds_an_existing_deficit_against_an_open_wand);
    RUN_TEST(test_declared_threshold_moves_the_feed_boundary);
    RUN_TEST(test_the_law_runs_against_the_simulated_implementation_with_no_target_dependency);
    RUN_TEST(test_feed_withheld_when_no_pressure_reading_has_ever_been_trusted);
    RUN_TEST(test_init_is_refused_and_leaves_both_channels_off_without_either_record);
    RUN_TEST(test_the_accessors_refuse_nowhere_to_answer);
    RUN_TEST(test_output_refused_is_reported_rather_than_folded_into_actuated);
    RUN_TEST(test_a_refused_heater_command_does_not_leave_the_feed_running);
    RUN_TEST(test_init_reports_a_refused_off_command_but_leaves_the_loop_usable);
    RUN_TEST(test_a_reopened_draw_earns_its_margin_again);
    return UNITY_END();
}
