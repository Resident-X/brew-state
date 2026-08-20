/*
 * The state estimator exercised against the structure that describes the
 * reference machine.
 *
 * The estimator reconstructs a state no sensor channel reports, from the
 * channels that do exist, by running the same equations the machine's model
 * runs and correcting them toward what is observed. What can be established
 * here is that a state the machine cannot sense is produced at all, that it
 * moves toward the truth the model holds rather than away from it, and that the
 * difference the correction acted on is the one anything downstream will read.
 *
 * What cannot be established here is whether the reconstruction is close enough
 * to control a real machine with. That waits on measured coefficients, and the
 * structure's own support status records that nothing has been on the bench.
 */
#include <unity.h>

#include <math.h>
#include <stdio.h>
#include <string.h>

#include "estimator.h"
#include "estimator_limits.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"

/* The interval every step in this suite advances by. */
#define STEP_INTERVAL_MS 10u

static plant_parameters_t parameters;
static estimator_limits_t limits;

static void load_the_reference_description(void)
{
    static char text[16384];

    FILE *const handle = fopen(REFERENCE_DESCRIPTION_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "could not open the reference description");

    const size_t used = fread(text, 1u, sizeof(text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < sizeof(text) - 1u);

    plant_parameter_error_t fault;
    TEST_ASSERT_TRUE(plant_parameters_load(text, used, &parameters, &fault));
}

/*
 * The limits declaration beside that description, read from the same place for
 * the same reason: a suite carrying its own bounds would keep passing after the
 * declaration the machine actually ships drifted away from it.
 */
static void load_the_reference_limits(void)
{
    static char text[16384];

    FILE *const handle = fopen(REFERENCE_LIMITS_PATH, "rb");
    TEST_ASSERT_NOT_NULL_MESSAGE(handle, "could not open the reference limits declaration");

    const size_t used = fread(text, 1u, sizeof(text) - 1u, handle);
    (void)fclose(handle);
    TEST_ASSERT_TRUE(used > 0u);
    TEST_ASSERT_TRUE(used < sizeof(text) - 1u);

    estimator_limits_error_t fault;
    TEST_ASSERT_TRUE(estimator_limits_load(text, used, &limits, &fault));
}

/* Stand every channel the hardware seam reports up from a model's quantities. */
static void report_from(const plant_model_t *model)
{
    static const plant_quantity_t QUANTITY_FOR_CHANNEL[HW_SENSOR_CHANNEL_COUNT] = {
        [HW_SENSOR_BREW_TEMPERATURE] = PLANT_QUANTITY_BREW_TEMPERATURE_C,
        [HW_SENSOR_STEAM_TEMPERATURE] = PLANT_QUANTITY_STEAM_TEMPERATURE_C,
        [HW_SENSOR_BREW_PRESSURE] = PLANT_QUANTITY_BREW_PRESSURE_BAR,
        [HW_SENSOR_STEAM_PRESSURE] = PLANT_QUANTITY_STEAM_PRESSURE_BAR,
    };

    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        float value = 0.0f;
        TEST_ASSERT_TRUE(plant_model_quantity(model, QUANTITY_FOR_CHANNEL[channel], &value));
        hw_sim_set_sensor((hw_sensor_channel_t)channel, true, (int32_t)lroundf(value * 1000.0f));
    }
}

/* An actuation this structure answers, at a level that visibly heats. */
static plant_actuation_t heating(void)
{
    plant_actuation_t actuation = {{0u}};

    actuation.level_permille[ACTUATION_CHANNEL_BREW_HEATER] = 600u;
    return actuation;
}

static plant_actuation_t idle(void)
{
    const plant_actuation_t actuation = {{0u}};

    return actuation;
}

void setUp(void)
{
    hw_sim_reset();
    load_the_reference_description();
    load_the_reference_limits();
}

void tearDown(void) {}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C2: The estimator reconstructs a state
/// no sensor channel reports.
///
/// Stepped against readings drawn only from the channels that exist, it answers
/// a state that is none of them. The readings are held at one temperature while
/// the reconstruction starts at another, so a reconstruction that was merely a
/// channel passed through would equal one of the four and is caught.
static void test_a_state_no_channel_reports_is_reconstructed(void)
{
    estimator_t estimator;
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));

    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        hw_sim_set_sensor((hw_sensor_channel_t)channel, true, 80000);
    }

    const plant_actuation_t actuation = heating();
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

    float reconstructed = 0.0f;
    TEST_ASSERT_TRUE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &reconstructed));
    TEST_ASSERT_TRUE(isfinite(reconstructed));

    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        const hw_reading_t reading = hw_sensor_read((hw_sensor_channel_t)channel);
        TEST_ASSERT_TRUE(reading.valid);
        TEST_ASSERT_NOT_EQUAL(reading.value_milli, (int32_t)lroundf(reconstructed * 1000.0f));
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C2: The estimator reconstructs a state
/// no sensor channel reports.
///
/// Read before an instance has been initialised, the answer is a refusal rather
/// than a default. A default is indistinguishable from a machine that happens
/// to be at that temperature, and the caller cannot tell it has reconstructed
/// nothing.
static void test_a_state_read_before_initialisation_is_refused(void)
{
    estimator_t estimator;
    float value = -1.0f;

    estimator.ready = false;
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, value);

    TEST_ASSERT_FALSE(estimator_state(NULL, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, NULL));
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C2: The estimator reconstructs a state
/// no sensor channel reports.
///
/// A state outside the enumerated set is refused rather than answered, so a
/// caller that has drifted out of the vocabulary finds out rather than reading
/// past the end of it.
static void test_a_state_outside_the_enumerated_set_is_refused(void)
{
    estimator_t estimator;
    float value = -1.0f;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_FALSE(estimator_state(&estimator, (estimator_state_t)ESTIMATOR_STATE_COUNT, &value));
    TEST_ASSERT_FALSE(
        estimator_state(&estimator, (estimator_state_t)(ESTIMATOR_STATE_COUNT + 1), &value));
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, value);
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C12: The estimator refuses a structure
/// that lacks the state it reconstructs.
///
/// The half of that criterion this build can show: the structure describing the
/// reference machine keeps the state, so initialisation is accepted. The
/// refusal is shown by the suites built against the structures that do not,
/// because a build compiles one structure and this one compiles this.
static void test_a_structure_that_keeps_the_state_is_accepted(void)
{
    estimator_t estimator;
    float reconstructed = 0.0f;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_TRUE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &reconstructed));
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C12: The estimator refuses a structure
/// that lacks the state it reconstructs.
///
/// A record it cannot initialise a model from is refused on the same terms, and
/// leaves the instance answering nothing rather than half-built.
static void test_an_instance_with_no_record_is_refused_and_answers_nothing(void)
{
    estimator_t estimator;
    float value = -1.0f;

    TEST_ASSERT_FALSE(estimator_init(&estimator, NULL, &limits));
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_FALSE(estimator_init(NULL, &parameters, &limits));

    const plant_actuation_t actuation = idle();
    TEST_ASSERT_FALSE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C3: A reconstructed state converges on
/// the truth the plant model holds.
///
/// A reference instance is run as the truth and reports only what the hardware
/// seam exposes as channels; the estimator is started from a state deliberately
/// displaced from it and is given nothing else. What is asserted is the
/// direction of travel: the error in the state no channel reports falls, and
/// stays fallen rather than growing or ringing. An accuracy figure against a
/// real machine is not asserted, and none could be before coefficients are
/// measured.
static void test_the_reconstruction_converges_on_the_models_own_truth(void)
{
    plant_model_t truth;
    estimator_t estimator;

    TEST_ASSERT_TRUE(plant_model_init(&truth, &parameters));

    /*
     * Displace the truth from where an estimator would start: both settle at
     * the declared ambient, so run the truth away from it first.
     *
     * This stretch is longer than it once was, and the reason is in the plant
     * rather than here. The state being displaced is the water on its way to the
     * group, and with the pump closed the only thing bringing it up is now
     * conduction from the casting -- a far slower path than the residence time
     * the description used to carry a single constant for. Four seconds of
     * heating no longer moves it a degree. Nothing about what this test asserts
     * changed; it just has to wait for the machine it is asserting about.
     */
    const plant_actuation_t actuation = heating();
    for (int i = 0; i < 2000; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&truth, &actuation, STEP_INTERVAL_MS));
    }

    report_from(&truth);
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));

    float truth_outlet = 0.0f;
    float estimated_outlet = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(&truth, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &truth_outlet));
    TEST_ASSERT_TRUE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &estimated_outlet));

    const float displaced = fabsf(truth_outlet - estimated_outlet);
    TEST_ASSERT_TRUE_MESSAGE(displaced > 1.0f, "the estimator did not start away from the truth");

    /*
     * And the run has to be long enough for the slowest path the correction
     * reaches this state through. The sensor is on the casting; the water is
     * brought to the casting by conduction while nothing is drawn, and that is
     * the constant the error decays on once the casting itself is right. A run
     * of a few of those constants is what "converged" can be asserted over, and
     * the settling stretch below is half of it for the same reason.
     */
    static const int STEPS = 12000;
    float worst_after_settling = 0.0f;
    float error = displaced;
    for (int step = 0; step < STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&truth, &actuation, STEP_INTERVAL_MS));
        report_from(&truth);
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

        TEST_ASSERT_TRUE(
            plant_model_state(&truth, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &truth_outlet));
        TEST_ASSERT_TRUE(
            estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &estimated_outlet));
        error = fabsf(truth_outlet - estimated_outlet);
        TEST_ASSERT_TRUE_MESSAGE(isfinite(error), "the reconstruction left the finite numbers");

        /* Once past the settling stretch, the error must stay down rather than
         * dip through the truth and climb out the far side. */
        if (step >= STEPS / 2 && error > worst_after_settling) {
            worst_after_settling = error;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(error < displaced / 10.0f, "the reconstruction did not converge");
    TEST_ASSERT_TRUE_MESSAGE(worst_after_settling < displaced / 10.0f,
                             "the reconstruction did not stay converged");
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C8: The estimator reports the difference
/// between each predicted and observed measurement.
///
/// The sign and the magnitude follow the discrepancy that was imposed rather
/// than sitting at zero. Both directions are driven, so a residual that
/// reported a magnitude without a sign would be caught.
static void test_the_residual_follows_the_imposed_discrepancy(void)
{
    static const int32_t OBSERVED[] = {15000, 25000};
    static const int STANDS[] = {1, -1};

    for (unsigned i = 0u; i < sizeof(OBSERVED) / sizeof(OBSERVED[0]); i++) {
        estimator_t estimator;
        hw_sim_reset();
        TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));

        /* The model settles at the declared ambient of 20 degrees; the reading
         * is stood up either side of it. */
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, OBSERVED[i]);

        const plant_actuation_t actuation = idle();
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

        int32_t residual = 0;
        TEST_ASSERT_TRUE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
        TEST_ASSERT_EQUAL_INT(STANDS[i], (residual > 0) ? 1 : -1);
        TEST_ASSERT_INT32_WITHIN(50, 20000 - OBSERVED[i], residual);
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C8: The estimator reports the difference
/// between each predicted and observed measurement.
///
/// A channel the step did not correct against reports no residual at all, which
/// is a different answer from a residual of zero: the first says the estimator
/// has nothing to say about that channel, the second says the prediction and
/// the observation agreed. A caller acting on drift needs to tell them apart.
static void test_a_channel_not_corrected_against_reports_no_residual(void)
{
    estimator_t estimator;
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));

    /* The brew channel agrees with the model exactly; the rest report nothing. */
    float predicted = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_quantity(&estimator.model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &predicted));
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, (int32_t)lroundf(predicted * 1000.0f));

    const plant_actuation_t actuation = idle();
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

    int32_t residual = -1;
    TEST_ASSERT_TRUE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
    TEST_ASSERT_EQUAL_INT32(0, residual);

    for (unsigned channel = 1u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        int32_t untouched = 12345;
        TEST_ASSERT_FALSE(
            estimator_residual(&estimator, (hw_sensor_channel_t)channel, &untouched));
        TEST_ASSERT_EQUAL_INT32(12345, untouched);
    }

    int32_t beyond = 0;
    TEST_ASSERT_FALSE(estimator_residual(&estimator, (hw_sensor_channel_t)HW_SENSOR_CHANNEL_COUNT,
                                         &beyond));
    TEST_ASSERT_FALSE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, NULL));
    TEST_ASSERT_FALSE(estimator_residual(NULL, HW_SENSOR_BREW_TEMPERATURE, &beyond));
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C9: The reported residual is the one the
/// correction step used.
///
/// A second instance is advanced identically and left uncorrected, which is what
/// the estimator predicted before it corrected anything. The reported residual
/// has to be that prediction minus the observation, and the amount taken out of
/// the state has to be that same residual scaled -- established by driving two
/// different discrepancies and requiring the same proportion of each to have
/// been acted on. A residual recomputed for the report would agree with the one
/// used only by coincidence, and only until either was touched.
static void test_the_reported_residual_is_the_one_the_correction_used(void)
{
    static const int32_t OBSERVED[] = {15000, 25000};
    float acted_on_fraction[2] = {0.0f, 0.0f};

    for (unsigned i = 0u; i < sizeof(OBSERVED) / sizeof(OBSERVED[0]); i++) {
        estimator_t estimator;
        plant_model_t uncorrected;

        hw_sim_reset();
        TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
        TEST_ASSERT_TRUE(plant_model_init(&uncorrected, &parameters));
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, OBSERVED[i]);

        const plant_actuation_t actuation = heating();
        TEST_ASSERT_TRUE(plant_model_step(&uncorrected, &actuation, STEP_INTERVAL_MS));
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

        float predicted = 0.0f;
        TEST_ASSERT_TRUE(
            plant_model_quantity(&uncorrected, PLANT_QUANTITY_BREW_TEMPERATURE_C, &predicted));

        int32_t residual = 0;
        TEST_ASSERT_TRUE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
        TEST_ASSERT_EQUAL_INT32((int32_t)lroundf(predicted * 1000.0f) - OBSERVED[i], residual);
        TEST_ASSERT_NOT_EQUAL(0, residual);

        float corrected = 0.0f;
        TEST_ASSERT_TRUE(plant_model_state(
            &estimator.model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &corrected));

        acted_on_fraction[i] = (predicted - corrected) / ((float)residual / 1000.0f);
    }

    /* Some of the reported difference was taken out, in the direction that
     * closes it, and the same proportion of each. */
    TEST_ASSERT_TRUE(acted_on_fraction[0] > 0.0f);
    TEST_ASSERT_TRUE(acted_on_fraction[0] <= 1.0f);
    TEST_ASSERT_FLOAT_WITHIN(0.001f, acted_on_fraction[0], acted_on_fraction[1]);
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C9: The reported residual is the one the
/// correction step used.
///
/// A step that corrects nothing reports nothing, rather than the difference the
/// step before it acted on. A stale residual read as a fresh one reports a
/// disagreement the machine is no longer in.
static void test_a_step_that_corrects_nothing_reports_no_residual(void)
{
    estimator_t estimator;
    int32_t residual = 0;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 15000);

    const plant_actuation_t actuation = idle();
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    TEST_ASSERT_TRUE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));

    /* The reading is withdrawn: the model still advances, and corrects nothing. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 15000);
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    TEST_ASSERT_FALSE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));

    /* And a step the seam refuses leaves none behind either. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 15000);
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    TEST_ASSERT_TRUE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
    TEST_ASSERT_FALSE(estimator_step(&estimator, &actuation, 0u));
    TEST_ASSERT_FALSE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C2: The estimator reconstructs a state
/// no sensor channel reports.
///
/// The reconstruction keeps running when a reading is withdrawn: the model is
/// what carries it, and the correction is what a reading contributes. This is
/// the regression guard on the estimator being a model that is corrected rather
/// than a reading that is passed through.
static void test_the_reconstruction_survives_a_withdrawn_reading(void)
{
    estimator_t estimator;
    float before = 0.0f;
    float after = 0.0f;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);

    /*
     * Kept inside the declared tolerance window, which is what makes this a
     * statement about the model carrying the reconstruction rather than about
     * how long it may do so. Where the window runs out is a different property
     * with its own tests; running past it here would fail this one for a reason
     * it is not asserting.
     */
    const plant_actuation_t actuation = heating();
    TEST_ASSERT_TRUE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &before));
    for (int i = 0; i < 40; i++) {
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    }
    TEST_ASSERT_TRUE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &after));

    TEST_ASSERT_TRUE(isfinite(after));
    TEST_ASSERT_TRUE_MESSAGE(after > before, "the heated water did not warm without a reading");
}


/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C8: The estimator reports the difference
/// between each predicted and observed measurement.
///
/// Every channel, not the one the control law happens to read. Each is stood
/// away from what the model predicts by a different amount and in a different
/// direction, in that channel's own unit, so a correspondence that had two
/// channels crossed, or that corrected against one and reported the rest as
/// absent, is caught rather than passing on the strength of the brew channel
/// alone.
static void test_every_channel_reports_its_own_difference(void)
{
    /*
     * Each offset is large enough to be unmistakable and small enough that the
     * reading it produces is still one the machine could plausibly report. A
     * discrepancy is what this test imposes; an absurdity is not, and a channel
     * driven outside its declared bounds would be skipped rather than corrected
     * against -- which would make this test fail for the plausibility rule's
     * reason instead of its own.
     */
    static const int32_t OFFSET_MILLI[HW_SENSOR_CHANNEL_COUNT] = {
        [HW_SENSOR_BREW_TEMPERATURE] = -4000,
        [HW_SENSOR_STEAM_TEMPERATURE] = 9000,
        [HW_SENSOR_BREW_PRESSURE] = -2500,
        [HW_SENSOR_STEAM_PRESSURE] = 750,
    };
    static const plant_quantity_t QUANTITY_FOR_CHANNEL[HW_SENSOR_CHANNEL_COUNT] = {
        [HW_SENSOR_BREW_TEMPERATURE] = PLANT_QUANTITY_BREW_TEMPERATURE_C,
        [HW_SENSOR_STEAM_TEMPERATURE] = PLANT_QUANTITY_STEAM_TEMPERATURE_C,
        [HW_SENSOR_BREW_PRESSURE] = PLANT_QUANTITY_BREW_PRESSURE_BAR,
        [HW_SENSOR_STEAM_PRESSURE] = PLANT_QUANTITY_STEAM_PRESSURE_BAR,
    };

    estimator_t estimator;
    plant_model_t uncorrected;
    int32_t predicted_milli[HW_SENSOR_CHANNEL_COUNT];

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_TRUE(plant_model_init(&uncorrected, &parameters));

    /*
     * The reading each channel will be stood up at is the prediction it is about
     * to make, moved by that channel's offset. The prediction comes from a second
     * instance advanced identically and left uncorrected, so the expected
     * difference is known before the estimator is asked for it.
     */
    const plant_actuation_t actuation = heating();
    TEST_ASSERT_TRUE(plant_model_step(&uncorrected, &actuation, STEP_INTERVAL_MS));

    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        float predicted = 0.0f;
        TEST_ASSERT_TRUE(
            plant_model_quantity(&uncorrected, QUANTITY_FOR_CHANNEL[channel], &predicted));
        predicted_milli[channel] = (int32_t)lroundf(predicted * 1000.0f);
        hw_sim_set_sensor((hw_sensor_channel_t)channel, true,
                          predicted_milli[channel] - OFFSET_MILLI[channel]);
    }

    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        char message[96];
        int32_t residual = 0;

        (void)snprintf(message, sizeof(message), "channel %u reported no residual", channel);
        TEST_ASSERT_TRUE_MESSAGE(
            estimator_residual(&estimator, (hw_sensor_channel_t)channel, &residual), message);

        (void)snprintf(message, sizeof(message), "channel %u reported the wrong difference",
                       channel);
        TEST_ASSERT_EQUAL_INT32_MESSAGE(OFFSET_MILLI[channel], residual, message);
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C8: The estimator reports the difference
/// between each predicted and observed measurement.
///
/// A channel's correction lands on the state that channel observes and on no
/// other. A correspondence with two entries crossed would subtract a
/// disagreement measured in one unit from a state held in another, on every
/// step, and go on reporting residuals that look ordinary -- so the states that
/// were not observed are required to be exactly where the uncorrected model
/// left them.
static void test_a_channels_correction_lands_on_its_own_state_and_no_other(void)
{
    static const plant_state_t OBSERVED_BY_A_CHANNEL[] = {
        PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C,
        PLANT_STATE_STEAM_TEMPERATURE_C,
        PLANT_STATE_BREW_PRESSURE_BAR,
        PLANT_STATE_STEAM_PRESSURE_BAR,
    };

    estimator_t estimator;
    plant_model_t uncorrected;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_TRUE(plant_model_init(&uncorrected, &parameters));

    /* Only the brew temperature is observed; every other channel stays silent. */
    float predicted_brew = 0.0f;
    const plant_actuation_t actuation = heating();
    TEST_ASSERT_TRUE(plant_model_step(&uncorrected, &actuation, STEP_INTERVAL_MS));
    TEST_ASSERT_TRUE(
        plant_model_quantity(&uncorrected, PLANT_QUANTITY_BREW_TEMPERATURE_C, &predicted_brew));
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true,
                      (int32_t)lroundf(predicted_brew * 1000.0f) + 6000);

    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

    /* The state that channel observes moved, and moved toward the reading. */
    float corrected = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(&estimator.model,
                                       PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &corrected));
    TEST_ASSERT_TRUE(corrected > predicted_brew);

    /* Every state no channel reported stayed exactly where the equations left it. */
    for (unsigned i = 1u; i < sizeof(OBSERVED_BY_A_CHANNEL) / sizeof(OBSERVED_BY_A_CHANNEL[0]);
         i++) {
        float untouched = 0.0f;
        float advanced = 0.0f;
        char message[96];

        TEST_ASSERT_TRUE(plant_model_state(&estimator.model, OBSERVED_BY_A_CHANNEL[i], &advanced));
        TEST_ASSERT_TRUE(plant_model_state(&uncorrected, OBSERVED_BY_A_CHANNEL[i], &untouched));

        (void)snprintf(message, sizeof(message), "state %d moved with no channel reporting it",
                       (int)OBSERVED_BY_A_CHANNEL[i]);
        TEST_ASSERT_EQUAL_FLOAT_MESSAGE(untouched, advanced, message);
    }

    /* And the state no channel observes at all is the reconstruction itself. */
    float reconstructed = 0.0f;
    float unreconstructed = 0.0f;
    TEST_ASSERT_TRUE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &reconstructed));
    TEST_ASSERT_TRUE(
        plant_model_state(&uncorrected, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &unreconstructed));
    TEST_ASSERT_EQUAL_FLOAT(unreconstructed, reconstructed);
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C2: The estimator reconstructs a state
/// no sensor channel reports.
///
/// A reconstruction that is not a number is refused rather than handed back. It
/// is reached by writing one into the model through the seam, which is the same
/// route the correction takes, so this is the shape a correction driven somewhere
/// absurd would arrive in.
static void test_a_reconstruction_that_is_not_a_number_is_refused(void)
{
    estimator_t estimator;
    float value = -1.0f;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_TRUE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));

    TEST_ASSERT_TRUE(plant_model_set_state(&estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, (float)NAN));
    value = -1.0f;
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_EQUAL_FLOAT(-1.0f, value);

    TEST_ASSERT_TRUE(plant_model_set_state(&estimator.model,
                                           PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, (float)INFINITY));
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));

    /* And it comes back when the model holds a number again. */
    TEST_ASSERT_TRUE(
        plant_model_set_state(&estimator.model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, 42.0f));
    TEST_ASSERT_TRUE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_EQUAL_FLOAT(42.0f, value);
}


/*
 * A limits record built from text the test writes, for the cases that need
 * bounds or a window the shipped declaration does not have. The shipped one is
 * exercised by every other test in this suite through setUp; these are for
 * asking what happens at a boundary, which means choosing where the boundary
 * is.
 */
static estimator_limits_t limits_from(const char *text)
{
    estimator_limits_t built;
    estimator_limits_error_t fault;

    TEST_ASSERT_TRUE_MESSAGE(estimator_limits_load(text, strlen(text), &built, &fault),
                             "the suite's own limits declaration was refused");
    return built;
}

/* Stand every channel up at one reading, so a test varies only the one it means to. */
static void report_everything_at(int32_t milli)
{
    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        hw_sim_set_sensor((hw_sensor_channel_t)channel, true, milli);
    }
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C2: A reading outside its declared bounds is
/// not corrected against.
///
/// The absurd reading and the absent one must land in the same place, which is
/// what "treated exactly as one the seam could not obtain" means. Two instances
/// are advanced identically and differ only in whether the brew channel reports
/// nine hundred degrees or reports nothing; a reconstruction that had been
/// dragged toward the absurd value would end somewhere the other did not.
static void test_a_reading_outside_its_declared_bounds_is_not_corrected_against(void)
{
    estimator_t dragged;
    estimator_t withheld;

    TEST_ASSERT_TRUE(estimator_init(&dragged, &parameters, &limits));
    TEST_ASSERT_TRUE(estimator_init(&withheld, &parameters, &limits));

    const plant_actuation_t actuation = heating();

    for (unsigned step = 0u; step < 8u; step++) {
        report_everything_at(40000);
        /* Far above the declared high for a temperature channel. */
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 900000);
        TEST_ASSERT_TRUE(estimator_step(&dragged, &actuation, STEP_INTERVAL_MS));

        report_everything_at(40000);
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
        TEST_ASSERT_TRUE(estimator_step(&withheld, &actuation, STEP_INTERVAL_MS));
    }

    float from_absurd = 0.0f;
    float from_absent = 0.0f;
    TEST_ASSERT_TRUE(estimator_state(&dragged, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &from_absurd));
    TEST_ASSERT_TRUE(estimator_state(&withheld, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &from_absent));
    TEST_ASSERT_EQUAL_FLOAT(from_absent, from_absurd);

    /* And it reports no residual for the channel it did not correct against. */
    int32_t residual = 0;
    TEST_ASSERT_FALSE(estimator_residual(&dragged, HW_SENSOR_BREW_TEMPERATURE, &residual));
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C2: A reading outside its declared bounds is
/// not corrected against.
///
/// The bounds themselves and the values immediately beyond them, rather than
/// one convenient value well inside the span. A boundary is the cheapest place
/// for the comparison to be written the wrong way round, and the cheapest place
/// to notice that it was: an inclusive bound tested only at the middle passes
/// whether it is inclusive or not.
static void test_each_declared_bound_is_believed_and_the_step_beyond_it_is_not(void)
{
    static const char DECLARATION[] = "@describes-no-machine\n"
                                      "brew-temperature = 20000 .. 60000\n"
                                      "steam-temperature = -10000 .. 250000\n"
                                      "brew-pressure = -1000 .. 20000\n"
                                      "steam-pressure = -1000 .. 20000\n"
                                      "loss-tolerance-window-ms = 500\n"
                                      "excursion-bound-milli-c = 15000\n";
    static const struct {
        int32_t reading;
        bool believed;
        const char *what;
    } CASES[] = {
        {20000, true, "the declared low"},
        {60000, true, "the declared high"},
        {19999, false, "one thousandth below the declared low"},
        {60001, false, "one thousandth above the declared high"},
    };

    const estimator_limits_t narrow = limits_from(DECLARATION);
    const plant_actuation_t actuation = heating();

    for (size_t i = 0u; i < sizeof(CASES) / sizeof(CASES[0]); i++) {
        estimator_t estimator;
        int32_t residual = 0;

        TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &narrow));
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, CASES[i].reading);
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

        const bool corrected =
            estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual);
        TEST_ASSERT_EQUAL_MESSAGE(CASES[i].believed, corrected, CASES[i].what);
    }
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C3: A reconstructed state stays usable across
/// a gap in the observations it depends on.
///
/// Inside the window the reconstruction runs on prediction and is still
/// answered, and it is still the model's own trajectory rather than a held
/// value: a reference instance advanced identically with no correction to apply
/// is where it should be, and an estimator that had frozen instead of predicting
/// would part company with it.
static void test_a_state_stays_usable_across_a_gap_in_what_it_depends_on(void)
{
    estimator_t estimator;
    plant_model_t predicted;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_TRUE(plant_model_init(&predicted, &parameters));

    const plant_actuation_t actuation = heating();

    /* Withdrawn for a run well inside the shipped window of five hundred. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);
    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, false, 0);
    hw_sim_set_sensor(HW_SENSOR_BREW_PRESSURE, false, 0);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, false, 0);

    for (unsigned step = 0u; step < 20u; step++) {
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
        TEST_ASSERT_TRUE(plant_model_step(&predicted, &actuation, STEP_INTERVAL_MS));
    }

    float reconstructed = 0.0f;
    float expected = 0.0f;
    TEST_ASSERT_TRUE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &reconstructed));
    TEST_ASSERT_TRUE(
        plant_model_state(&predicted, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &expected));
    TEST_ASSERT_EQUAL_FLOAT(expected, reconstructed);
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C3: A reconstructed state stays usable across
/// a gap in the observations it depends on.
///
/// A channel this state does not rest on cannot starve it. The steam channels
/// and the brew pressure reach no state the caller asked for, so withdrawing
/// them for far longer than the window leaves the brew temperature answering --
/// a rule keyed on channels rather than on states would have stopped the
/// machine for a sensor that has nothing to do with what it was controlling.
static void test_a_gap_in_a_channel_the_state_does_not_depend_on_leaves_it_answering(void)
{
    estimator_t estimator;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));

    const plant_actuation_t actuation = heating();

    hw_sim_set_sensor(HW_SENSOR_STEAM_TEMPERATURE, false, 0);
    hw_sim_set_sensor(HW_SENSOR_BREW_PRESSURE, false, 0);
    hw_sim_set_sensor(HW_SENSOR_STEAM_PRESSURE, false, 0);

    /* Far beyond the window, so a channel-keyed rule would certainly have fired. */
    for (unsigned step = 0u; step < 200u; step++) {
        hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 40000);
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    }

    float reconstructed = 0.0f;
    TEST_ASSERT_TRUE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &reconstructed));
    TEST_ASSERT_TRUE(isfinite(reconstructed));
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C4: The reconstruction is refused once it has
/// travelled past its declared excursion bound.
///
/// The distance and the window are separate refusals, and this is the one that
/// establishes it: the window is set far wider than the run lasts, so a refusal
/// arriving here is the distance and cannot be the window. The bound is small
/// enough that ordinary heating reaches it, which is what makes the arrival
/// observable at all -- on the shipped declaration the excursion bound is
/// reached by a model that has diverged rather than by one that is merely warm.
static void test_the_reconstruction_is_refused_past_its_declared_excursion_bound(void)
{
    static const char DECLARATION[] = "@describes-no-machine\n"
                                      "brew-temperature = -10000 .. 250000\n"
                                      "steam-temperature = -10000 .. 250000\n"
                                      "brew-pressure = -1000 .. 20000\n"
                                      "steam-pressure = -1000 .. 20000\n"
                                      "loss-tolerance-window-ms = 4000000\n"
                                      "excursion-bound-milli-c = 250\n";
    const estimator_limits_t tight = limits_from(DECLARATION);

    estimator_t estimator;
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &tight));

    /* One observation, to establish where the travel is measured from. */
    report_everything_at(20000);
    const plant_actuation_t actuation = heating();
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

    float anchored_at = 0.0f;
    TEST_ASSERT_TRUE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &anchored_at));

    /* Then the observations stop and the heater stays on. */
    for (unsigned channel = 0u; channel < (unsigned)HW_SENSOR_CHANNEL_COUNT; channel++) {
        hw_sim_set_sensor((hw_sensor_channel_t)channel, false, 0);
    }

    bool refused = false;
    float last_answered = anchored_at;
    float when_refused = anchored_at;
    unsigned elapsed_ms = 0u;
    for (unsigned step = 0u; step < 4000u && !refused; step++) {
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
        elapsed_ms += STEP_INTERVAL_MS;

        float value = 0.0f;
        if (estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value)) {
            last_answered = value;
        } else {
            refused = true;
            /*
             * Read through the plant seam rather than through the estimator,
             * because the estimator is exactly what has just declined to answer.
             * This is where the reconstruction stood on the step that was
             * refused, which is the other side of the bound.
             */
            TEST_ASSERT_TRUE(plant_model_state(&estimator.model,
                                               PLANT_STATE_BREW_OUTLET_TEMPERATURE_C,
                                               &when_refused));
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(refused, "the reconstruction was never refused");

    /* The window had not run out, so the distance is what refused it. */
    TEST_ASSERT_TRUE_MESSAGE(elapsed_ms < tight.tolerance_window_ms,
                             "the window expired first, so this establishes nothing about the "
                             "excursion bound");

    /*
     * Both sides of the declared distance, so the refusal is pinned to it
     * rather than merely shown to arrive eventually. The last answer given was
     * still inside the bound, and the step that was refused had travelled past
     * it: a refusal at half the declared distance fails the first of these, and
     * one arriving late fails the second. Asserting only the first would pass
     * for every threshold at or below the one declared.
     */
    const float bound = (float)tight.excursion_bound_milli / 1000.0f;
    TEST_ASSERT_TRUE_MESSAGE(fabsf(last_answered - anchored_at) <= bound,
                             "a reconstruction inside the declared distance was refused");
    TEST_ASSERT_TRUE_MESSAGE(fabsf(when_refused - anchored_at) > bound,
                             "the refusal arrived before the declared distance was passed");
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C5: A state whose observations stop for longer
/// than the declared window becomes unusable.
///
/// The window is carried to its edge and one interval past it, so the test says
/// where the refusal arrives rather than only that one eventually does. Then the
/// channel is restored, and the elapsed figure clearing is shown by the state
/// answering again on the next accepted observation -- a figure that only ever
/// grew would leave a machine that had recovered permanently refused.
static void test_a_state_becomes_unusable_past_the_window_and_recovers_after_it(void)
{
    static const char DECLARATION[] = "@describes-no-machine\n"
                                      "brew-temperature = -10000 .. 250000\n"
                                      "steam-temperature = -10000 .. 250000\n"
                                      "brew-pressure = -1000 .. 20000\n"
                                      "steam-pressure = -1000 .. 20000\n"
                                      "loss-tolerance-window-ms = 100\n"
                                      "excursion-bound-milli-c = 250000\n";
    const estimator_limits_t brief = limits_from(DECLARATION);

    estimator_t estimator;
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &brief));

    report_everything_at(20000);
    const plant_actuation_t actuation = idle();
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);

    /* Ten steps of ten milliseconds is exactly the window, and still answered. */
    float value = 0.0f;
    for (unsigned step = 0u; step < 10u; step++) {
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
        TEST_ASSERT_TRUE_MESSAGE(
            estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value),
            "the state was refused inside the declared window");
    }

    /* One interval past it, and it is not. */
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));

    /* Restored, and the next accepted observation clears it. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 20000);
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    TEST_ASSERT_TRUE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));

    int32_t residual = 0;
    TEST_ASSERT_TRUE(estimator_residual(&estimator, HW_SENSOR_BREW_TEMPERATURE, &residual));
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C5: A state whose observations stop for longer
/// than the declared window becomes unusable.
///
/// An implausible reading starves the state exactly as an absent one does. It is
/// the same path by construction, and this is what would notice if the two were
/// ever separated -- a channel reading absurdly for a minute must not read as
/// freshly observed.
static void test_a_persistently_implausible_reading_starves_the_state_too(void)
{
    estimator_t estimator;

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));

    const plant_actuation_t actuation = idle();

    report_everything_at(20000);
    TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

    /* Arriving intact every step, and absurd every step. */
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, true, 900000);
    for (unsigned step = 0u; step < 60u; step++) {
        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
    }

    float value = 0.0f;
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
}

/// SOL-USABLE-ESTIMATE-EVERY-STEP.C1: Every plant description declares plausible
/// bounds for the channels it is corrected against.
///
/// The two figures that are not about any one channel, at and either side of
/// what each admits. A window is a span of time, so a negative one is not a
/// shorter one; an excursion bound is a distance the estimate may travel, so a
/// bound of nothing admits no movement at all and would refuse every
/// reconstruction it was asked about rather than bounding one.
///
/// The upper end of the window is here because the arithmetic that judges it is
/// the kind that reads correctly and compiles differently: the figure arrives as
/// a long, the bound it is compared against is unsigned, and a comparison
/// written across that line behaves one way where long is 64 bits and another
/// where it is 32. This suite runs on the host and cannot tell those apart, so
/// what it pins is the meaning; that the target agrees is the emulation tier's
/// to establish against the shipping binary.
static void test_a_window_or_a_distance_outside_what_it_admits_is_refused(void)
{
    static const struct {
        const char *figures;
        bool admitted;
        const char *what;
    } CASES[] = {
        {"loss-tolerance-window-ms = 0\nexcursion-bound-milli-c = 15000\n", true,
         "a window of nothing tolerates no gap and is a declaration somebody may mean"},
        {"loss-tolerance-window-ms = -1\nexcursion-bound-milli-c = 15000\n", false,
         "a negative span of time"},
        {"loss-tolerance-window-ms = 4294967295\nexcursion-bound-milli-c = 15000\n", true,
         "the widest window the figure is held in can carry"},
        {"loss-tolerance-window-ms = 500\nexcursion-bound-milli-c = 0\n", false,
         "a distance of nothing, which no moving estimate could satisfy"},
        {"loss-tolerance-window-ms = 500\nexcursion-bound-milli-c = -1\n", false,
         "a negative distance"},
        {"loss-tolerance-window-ms = 500\nexcursion-bound-milli-c = 1\n", true,
         "the smallest distance that still admits a stationary estimate"},
    };

    for (size_t i = 0u; i < sizeof(CASES) / sizeof(CASES[0]); i++) {
        char text[512];
        (void)snprintf(text, sizeof(text),
                       "@describes-no-machine\n"
                       "brew-temperature = -10000 .. 250000\n"
                       "steam-temperature = -10000 .. 250000\n"
                       "brew-pressure = -1000 .. 20000\n"
                       "steam-pressure = -1000 .. 20000\n"
                       "%s",
                       CASES[i].figures);

        estimator_limits_t built;
        estimator_limits_error_t fault;
        const bool loaded = estimator_limits_load(text, strlen(text), &built, &fault);

        TEST_ASSERT_EQUAL_MESSAGE(CASES[i].admitted, loaded, CASES[i].what);
        if (!loaded) {
            TEST_ASSERT_NOT_EQUAL(ESTIMATOR_LIMITS_OK, fault.fault);
        }
    }
}

/// SOL-PLANT-FLOW-REPORTED.C5: A quantity no state observes cannot read as the
/// first state.
///
/// The failure this guards is not a crash. A quantity paired with a state it is
/// not read from leaves the estimator correcting the wrong state against a
/// reading and going on running: the reported residual looks ordinary, the
/// correction never reaches the prediction it was computed from, and the
/// machine presents as one that has drifted rather than as one that is
/// miswired. Telling those two apart is the whole job of the residual, so it is
/// the one failure the pairing must not have.
///
/// Held by driving one channel at a time with a reading that disagrees with the
/// model, and requiring that channel's own residual to close over successive
/// steps. A correction landing on the state the reading is measured against
/// moves the prediction the next residual is computed from, so the disagreement
/// shrinks; one landing on any other state -- the first among them -- leaves
/// that prediction where it was, and the residual stands still while every step
/// goes on reporting a correction that happened.
///
/// The steam pressure channel is driven and checked for a residual but not for
/// closure, and that is the structure's answer rather than a gap here. This
/// structure does not integrate steam pressure: every step recomputes it from
/// the steam mass through the saturation relation, so a correction written into
/// it is overwritten before the next residual is taken. The correction was
/// offered and the equations decided, which is a different thing from the
/// correction never arriving.
static void test_each_channel_corrects_the_state_its_own_reading_is_measured_against(void)
{
    struct driven {
        hw_sensor_channel_t channel;
        int32_t reading_milli;
        bool correction_sticks;
    };

    /*
     * A reading per channel that disagrees with a model sitting at ambient and
     * is still inside the span the limits declaration admits -- an implausible
     * one is refused before any correction is reached, which would leave this
     * passing for the wrong reason.
     */
    static const struct driven DRIVEN[] = {
        {HW_SENSOR_BREW_TEMPERATURE, 60000, true},
        {HW_SENSOR_STEAM_TEMPERATURE, 60000, true},
        {HW_SENSOR_BREW_PRESSURE, 5000, true},
        {HW_SENSOR_STEAM_PRESSURE, 5000, false},
    };

    for (size_t i = 0u; i < sizeof(DRIVEN) / sizeof(DRIVEN[0]); i++) {
        estimator_t estimator;
        TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters, &limits));

        const plant_actuation_t actuation = idle();

        /* One channel at a time, so no other channel's correction can move the
         * prediction this one is being measured against. */
        hw_sim_reset();
        hw_sim_set_sensor(DRIVEN[i].channel, true, DRIVEN[i].reading_milli);

        TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));

        int32_t first = 0;
        TEST_ASSERT_TRUE_MESSAGE(estimator_residual(&estimator, DRIVEN[i].channel, &first),
                                 "a channel reporting a plausible reading produced no residual");
        TEST_ASSERT_TRUE_MESSAGE(first != 0, "the reading was chosen to disagree and did not");

        for (int step = 0; step < 8; step++) {
            TEST_ASSERT_TRUE(estimator_step(&estimator, &actuation, STEP_INTERVAL_MS));
        }

        int32_t later = 0;
        TEST_ASSERT_TRUE(estimator_residual(&estimator, DRIVEN[i].channel, &later));

        /* Compared as magnitudes, so a residual that closed by overshooting
         * through zero is not read as one that failed to close. */
        const int32_t opened = (first < 0) ? -first : first;
        const int32_t closed = (later < 0) ? -later : later;

        if (DRIVEN[i].correction_sticks) {
            char message[112];
            (void)snprintf(message, sizeof(message),
                           "channel %d: correcting left its own disagreement at %ld of %ld",
                           (int)DRIVEN[i].channel, (long)closed, (long)opened);
            TEST_ASSERT_TRUE_MESSAGE(closed < opened, message);
        }
    }
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_each_channel_corrects_the_state_its_own_reading_is_measured_against);
    RUN_TEST(test_a_state_no_channel_reports_is_reconstructed);
    RUN_TEST(test_a_state_read_before_initialisation_is_refused);
    RUN_TEST(test_a_state_outside_the_enumerated_set_is_refused);
    RUN_TEST(test_a_structure_that_keeps_the_state_is_accepted);
    RUN_TEST(test_an_instance_with_no_record_is_refused_and_answers_nothing);
    RUN_TEST(test_the_reconstruction_converges_on_the_models_own_truth);
    RUN_TEST(test_the_residual_follows_the_imposed_discrepancy);
    RUN_TEST(test_a_channel_not_corrected_against_reports_no_residual);
    RUN_TEST(test_the_reported_residual_is_the_one_the_correction_used);
    RUN_TEST(test_a_step_that_corrects_nothing_reports_no_residual);
    RUN_TEST(test_the_reconstruction_survives_a_withdrawn_reading);
    RUN_TEST(test_every_channel_reports_its_own_difference);
    RUN_TEST(test_a_channels_correction_lands_on_its_own_state_and_no_other);
    RUN_TEST(test_a_reconstruction_that_is_not_a_number_is_refused);
    RUN_TEST(test_a_reading_outside_its_declared_bounds_is_not_corrected_against);
    RUN_TEST(test_each_declared_bound_is_believed_and_the_step_beyond_it_is_not);
    RUN_TEST(test_a_state_stays_usable_across_a_gap_in_what_it_depends_on);
    RUN_TEST(test_a_gap_in_a_channel_the_state_does_not_depend_on_leaves_it_answering);
    RUN_TEST(test_the_reconstruction_is_refused_past_its_declared_excursion_bound);
    RUN_TEST(test_a_state_becomes_unusable_past_the_window_and_recovers_after_it);
    RUN_TEST(test_a_persistently_implausible_reading_starves_the_state_too);
    RUN_TEST(test_a_window_or_a_distance_outside_what_it_admits_is_refused);
    return UNITY_END();
}
