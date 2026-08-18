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

#include "estimator.h"
#include "hw_interface.h"
#include "hw_sim.h"
#include "plant_model.h"

/* The interval every step in this suite advances by. */
#define STEP_INTERVAL_MS 10u

static plant_parameters_t parameters;

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
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));

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
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

    TEST_ASSERT_FALSE(estimator_init(&estimator, NULL));
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_FALSE(estimator_init(NULL, &parameters));

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

    /* Displace the truth from where an estimator would start: both settle at
     * the declared ambient, so run the truth away from it first. */
    const plant_actuation_t actuation = heating();
    for (int i = 0; i < 400; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&truth, &actuation, STEP_INTERVAL_MS));
    }

    report_from(&truth);
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));

    float truth_outlet = 0.0f;
    float estimated_outlet = 0.0f;
    TEST_ASSERT_TRUE(plant_model_state(&truth, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &truth_outlet));
    TEST_ASSERT_TRUE(
        estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &estimated_outlet));

    const float displaced = fabsf(truth_outlet - estimated_outlet);
    TEST_ASSERT_TRUE_MESSAGE(displaced > 1.0f, "the estimator did not start away from the truth");

    float worst_after_settling = 0.0f;
    float error = displaced;
    for (int step = 0; step < 4000; step++) {
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
        if (step >= 2000 && error > worst_after_settling) {
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
        TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));

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
    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));

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
        TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
    hw_sim_set_sensor(HW_SENSOR_BREW_TEMPERATURE, false, 0);

    const plant_actuation_t actuation = heating();
    TEST_ASSERT_TRUE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &before));
    for (int i = 0; i < 200; i++) {
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
    static const int32_t OFFSET_MILLI[HW_SENSOR_CHANNEL_COUNT] = {
        [HW_SENSOR_BREW_TEMPERATURE] = -4000,
        [HW_SENSOR_STEAM_TEMPERATURE] = 9000,
        [HW_SENSOR_BREW_PRESSURE] = -2500,
        [HW_SENSOR_STEAM_PRESSURE] = 1750,
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

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

    TEST_ASSERT_TRUE(estimator_init(&estimator, &parameters));
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

int main(void)
{
    UNITY_BEGIN();
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
    return UNITY_END();
}
