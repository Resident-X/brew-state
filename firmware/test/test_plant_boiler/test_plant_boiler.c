/*
 * The seam driven against a structure of a different architecture: one heated
 * vessel serving both the brew path and the steam path.
 *
 * What this suite asserts is fixed independently of what the structure says
 * about itself. A model is free to be wrong about a machine -- whether these
 * equations describe any real single-boiler machine cannot be settled without
 * one to measure, and nobody here has one -- but it is not free to invent
 * energy, to lose the arithmetic between two identical runs, or to report a
 * brew temperature and a steam temperature that drift apart when there is one
 * body of water behind both. Those hold whatever the coefficients are.
 *
 * Nothing here includes a structure's own header or names a structure symbol.
 * The quantities and the answered channels are read through the seam, and the
 * coefficients are carried as text, on the same footing the other structures'
 * suites carry theirs.
 */
#include <math.h>
#include <string.h>

#include <unity.h>

#include "plant_model.h"

#define STEP_MS 100u

/* Enough steps that a quantity has moved well away from where it started. */
#define SETTLE_STEPS 25

/* Long enough to carry the vessel past saturation, so the steam pressure
 * relation is exercised rather than left sitting at its floor. */
#define BOIL_STEPS 900

static plant_parameters_t parameters;
static actuation_channel_set_t answered;

/*
 * An admissible description for the structure this environment builds, as text
 * rather than as symbols. It is not the description under params/: a suite
 * reading that file would be asserting about whichever values happen to be in
 * it, and these properties are meant to hold for any admissible set. The values
 * below are chosen only so that the model moves visibly within the steps taken
 * here -- a heater of zero power would let every assertion below pass by
 * nothing ever happening.
 */
static const char DESCRIPTION[] = "ambient_temperature_c = 20.0\n"
                                  "vessel.thermal_mass_j_per_k = 900.0\n"
                                  "vessel.heater_power_w = 1400.0\n"
                                  "vessel.loss_w_per_k = 2.0\n"
                                  "pump.pressure_bar = 15.0\n"
                                  "brew.pressure_time_constant_s = 0.8\n"
                                  "steam.saturation_temperature_c = 100.0\n"
                                  "steam.pressure_bar_per_k = 0.036\n";

/* The channel the vessel's one heater is driven by. */
#define HEATING_CHANNEL ACTUATION_CHANNEL_BREW_HEATER

/*
 * The coefficients DESCRIPTION carries, as numbers this suite can compute with.
 *
 * Restated here rather than read back out of the parameter record, because
 * naming a field of that record is reaching around the seam -- the
 * encapsulation check refuses it, and it would couple this suite to whichever
 * structure the build selected. The two cannot drift silently: every assertion
 * computed from these is against a trajectory produced from the text above, so
 * a disagreement between them fails the test rather than passing quietly.
 */
#define AMBIENT_C 20.0f
#define VESSEL_MASS_J_PER_K 900.0f
#define VESSEL_HEATER_W 1400.0f
#define VESSEL_LOSS_W_PER_K 2.0f
#define SATURATION_C 100.0f
#define STEAM_BAR_PER_K 0.036f

static void read_all(const plant_model_t *model, float out[PLANT_QUANTITY_COUNT])
{
    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_TRUE(plant_model_quantity(model, (plant_quantity_t)quantity, &out[quantity]));
    }
}

static void initialise(plant_model_t *model)
{
    TEST_ASSERT_TRUE(plant_model_init(model, &parameters));
}

/* An actuation driving the vessel's heater at full duty and nothing else. */
static plant_actuation_t heating(void)
{
    plant_actuation_t actuation = {{0u}};
    actuation.level_permille[HEATING_CHANNEL] = ACTUATION_FULL_SCALE;
    return actuation;
}

/* A heating duty that differs from step to step, so a replayed sequence is a
 * trajectory rather than a constant held for a while. */
static plant_actuation_t varying_actuation(int step)
{
    plant_actuation_t actuation = {{0u}};
    actuation.level_permille[HEATING_CHANNEL] =
        (uint16_t)((unsigned)step * (ACTUATION_FULL_SCALE / (unsigned)SETTLE_STEPS));
    return actuation;
}

void setUp(void)
{
    plant_parameter_error_t fault;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    answered = plant_structure_actuation_channels();
}

void tearDown(void) {}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: A second machine-describing
/// structure of a different architecture runs on the host through the seam --
/// the host build initialises an instance from a description and advances it
/// over a sequence of steps to completion.
static void test_an_instance_runs_a_whole_sequence_through_the_seam(void)
{
    plant_model_t model;
    const plant_actuation_t actuation = heating();
    float initial[PLANT_QUANTITY_COUNT];

    initialise(&model);
    /* Read through the seam, not from the parameter record: what this suite is
     * entitled to know about the structure is what the seam exposes. */
    read_all(&model, initial);

    for (int i = 0; i < SETTLE_STEPS; i++) {
        plant_step_error_t record;
        TEST_ASSERT_TRUE(plant_model_step_reporting(&model, &actuation, STEP_MS, &record));
        TEST_ASSERT_EQUAL(PLANT_STEP_OK, record.fault);
    }

    /* Every quantity the seam enumerates is answered from this structure's own
     * states, and one outside them is not answered at all. */
    float values[PLANT_QUANTITY_COUNT];
    read_all(&model, values);

    /* The sequence went somewhere, so the steps above ran rather than merely
     * being accepted. A model that returned true and did nothing would satisfy
     * every assertion before this one. */
    TEST_ASSERT_TRUE(values[PLANT_QUANTITY_BREW_TEMPERATURE_C] >
                     initial[PLANT_QUANTITY_BREW_TEMPERATURE_C]);

    float outside = 0.0f;
    TEST_ASSERT_FALSE(plant_model_quantity(&model, PLANT_QUANTITY_COUNT, &outside));
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...it declares the narrower set
/// of actuation channels it responds to.
static void test_the_declared_channels_are_the_ones_this_architecture_has(void)
{
    /* The channel the one vessel is heated by, and the pump. */
    TEST_ASSERT_NOT_EQUAL(0u, answered & ACTUATION_CHANNEL_BIT(HEATING_CHANNEL));
    TEST_ASSERT_NOT_EQUAL(0u, answered & ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_PUMP));

    /*
     * And not the machine's second heating channel. There is one vessel here,
     * so there is no second heater for a command to reach -- and this is the
     * assertion that makes the architecture claim falsifiable rather than
     * merely stated. Widening the declaration to include that channel would
     * leave every gate in the tree green: the check that a structure declares
     * its channels asks that the declaration exists and is drawn from the
     * machine's vocabulary, not which channels are in it. It would also remove
     * the only structure with real equations behind it that exercises the
     * seam's refusal of a command with nowhere to land.
     */
    TEST_ASSERT_EQUAL_UINT32(0u, answered & ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_STEAM_HEATER));

    /* Narrower than the vocabulary, and containing nothing outside it. */
    for (unsigned channel = (unsigned)ACTUATION_CHANNEL_COUNT; channel < 32u; channel++) {
        TEST_ASSERT_EQUAL_UINT32(0u, answered & ACTUATION_CHANNEL_BIT(channel));
    }
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...it answers all four
/// quantities the seam enumerates from its own states.
static void test_the_pump_drives_the_brew_pressure_and_leaves_the_vessel_alone(void)
{
    plant_model_t model;
    plant_actuation_t pumping = {{0u}};
    float value = 0.0f;
    float previous = 0.0f;
    float before[PLANT_QUANTITY_COUNT];

    initialise(&model);
    read_all(&model, before);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, before[PLANT_QUANTITY_BREW_PRESSURE_BAR]);

    /*
     * Half duty, so the settling value is a figure the pump's coefficient fixes
     * rather than the coefficient itself -- a structure ignoring the commanded
     * level and jumping to the coefficient would pass a test driven at full
     * scale.
     */
    pumping.level_permille[ACTUATION_CHANNEL_PUMP] = ACTUATION_FULL_SCALE / 2u;

    value = before[PLANT_QUANTITY_BREW_PRESSURE_BAR];
    for (int i = 0; i < SETTLE_STEPS; i++) {
        previous = value;
        TEST_ASSERT_TRUE(plant_model_step(&model, &pumping, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_PRESSURE_BAR, &value));
        /* Rising every step, and never past what was commanded: a relaxation
         * that overshoots has its step length and its time constant confused. */
        TEST_ASSERT_TRUE(value > previous);
        TEST_ASSERT_TRUE(value < 7.5f);
    }

    /* And most of the way there after several time constants, so the value is
     * following the commanded pressure rather than drifting near zero. */
    TEST_ASSERT_TRUE(value > 7.0f);

    /*
     * The pump is not a heater. Driving it moves neither temperature quantity
     * nor the steam pressure that follows the vessel -- the two paths share one
     * vessel in this architecture, but they do not share the pump.
     */
    float after[PLANT_QUANTITY_COUNT];
    read_all(&model, after);
    TEST_ASSERT_EQUAL_FLOAT(before[PLANT_QUANTITY_BREW_TEMPERATURE_C],
                            after[PLANT_QUANTITY_BREW_TEMPERATURE_C]);
    TEST_ASSERT_EQUAL_FLOAT(before[PLANT_QUANTITY_STEAM_TEMPERATURE_C],
                            after[PLANT_QUANTITY_STEAM_TEMPERATURE_C]);
    TEST_ASSERT_EQUAL_FLOAT(before[PLANT_QUANTITY_STEAM_PRESSURE_BAR],
                            after[PLANT_QUANTITY_STEAM_PRESSURE_BAR]);
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...a step with no actuation
/// and no external influence leaves every exposed quantity unchanged.
static void test_a_step_with_nothing_applied_moves_nothing(void)
{
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];
    const plant_actuation_t idle = {{0u}};

    initialise(&model);
    read_all(&model, before);

    /*
     * Many steps rather than one. A single step can hide a small hard-coded
     * source or sink inside the resolution of the comparison; a hundred cannot,
     * because the error accumulates while the correct answer stays put.
     */
    for (int i = 0; i < 100; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &idle, STEP_MS));
    }

    read_all(&model, after);
    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...a step with heat applied to
/// a channel it answers raises the temperature quantities and lowers none.
static void test_heat_raises_the_temperatures_and_lowers_no_quantity(void)
{
    plant_model_t model;
    float before[PLANT_QUANTITY_COUNT];
    float after[PLANT_QUANTITY_COUNT];
    const plant_actuation_t actuation = heating();

    /* The channel being driven is one this structure states it answers, read
     * through the seam rather than assumed. */
    TEST_ASSERT_NOT_EQUAL(0u, answered & ACTUATION_CHANNEL_BIT(HEATING_CHANNEL));

    initialise(&model);
    read_all(&model, before);

    for (int i = 0; i < SETTLE_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, STEP_MS));
    }

    read_all(&model, after);

    /* Both temperature quantities rose... */
    TEST_ASSERT_TRUE(after[PLANT_QUANTITY_BREW_TEMPERATURE_C] >
                     before[PLANT_QUANTITY_BREW_TEMPERATURE_C]);
    TEST_ASSERT_TRUE(after[PLANT_QUANTITY_STEAM_TEMPERATURE_C] >
                     before[PLANT_QUANTITY_STEAM_TEMPERATURE_C]);

    /* ...and nothing the model exposes fell. Heat applied to a machine that is
     * sitting at ambient has nowhere to take a quantity downwards, and a model
     * in which it does has a sign wrong somewhere. */
    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_TRUE(after[quantity] >= before[quantity]);
    }
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...the same sequence run twice
/// from the same initial state reproduces the same trajectory exactly.
static void test_the_same_sequence_twice_reproduces_the_same_trajectory(void)
{
    plant_model_t model;
    float recorded[SETTLE_STEPS][PLANT_QUANTITY_COUNT];
    float replayed[PLANT_QUANTITY_COUNT];

    /*
     * The same instance, brought back to its initial state and driven again --
     * not two instances stepped side by side. Two instances in lockstep can only
     * disagree through global state, whereas re-initialising and replaying also
     * catches an initialisation that leaves something behind from the run
     * before. That is the failure this property is worth having: a model that
     * reproduces its trajectory only when it happens to start from fresh memory
     * is one whose later identification runs are not comparable.
     *
     * A varying sequence rather than a constant, and compared at every step
     * rather than only at the end: a model carrying state it does not report can
     * still arrive at the same place by a different route.
     */
    initialise(&model);
    for (int i = 0; i < SETTLE_STEPS; i++) {
        const plant_actuation_t varying = varying_actuation(i);
        TEST_ASSERT_TRUE(plant_model_step(&model, &varying, STEP_MS));
        read_all(&model, recorded[i]);
    }

    initialise(&model);
    for (int i = 0; i < SETTLE_STEPS; i++) {
        const plant_actuation_t varying = varying_actuation(i);
        TEST_ASSERT_TRUE(plant_model_step(&model, &varying, STEP_MS));
        read_all(&model, replayed);
        TEST_ASSERT_EQUAL_MEMORY(recorded[i], replayed, sizeof(replayed));
    }

    /* The sequence moved the model, so the comparison above is over a
     * trajectory rather than over a row of identical states. */
    TEST_ASSERT_TRUE(recorded[SETTLE_STEPS - 1][PLANT_QUANTITY_BREW_TEMPERATURE_C] >
                     recorded[0][PLANT_QUANTITY_BREW_TEMPERATURE_C]);
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...it answers all four
/// quantities the seam enumerates from its own states, so both temperature
/// quantities follow one heater.
static void test_both_temperature_quantities_follow_the_one_vessel(void)
{
    plant_model_t model;
    const plant_actuation_t actuation = heating();

    initialise(&model);

    /*
     * This is the architecture, not an approximation of it. On a machine with
     * one heated vessel serving both paths there is no arrangement of the
     * actuation that separates the two temperatures, because there is one body
     * of water behind both -- which is precisely what a structure of the
     * reference machine's architecture, with two independently heated masses,
     * would fail here.
     */
    for (int i = 0; i < BOIL_STEPS; i++) {
        float values[PLANT_QUANTITY_COUNT];
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, STEP_MS));
        read_all(&model, values);
        TEST_ASSERT_EQUAL_MEMORY(&values[PLANT_QUANTITY_BREW_TEMPERATURE_C],
                                 &values[PLANT_QUANTITY_STEAM_TEMPERATURE_C], sizeof(float));
    }

    /* And the run went somewhere: the vessel passed saturation, so the steam
     * pressure relation was exercised above its floor rather than left at zero
     * for the whole sequence. */
    float steam_pressure = 0.0f;
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &steam_pressure));
    TEST_ASSERT_TRUE(steam_pressure > 0.0f);
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...a structure directory that
/// defines its own state and parameter types -- so the coefficients it reads are
/// its own, and another structure's are not silently accepted.
static void test_the_structure_reads_its_own_coefficients_and_no_others(void)
{
    plant_parameters_t loaded;
    plant_parameter_error_t fault;

    /*
     * A coefficient belonging to the reference machine's architecture, which
     * this one does not have. It is refused rather than ignored: a structure
     * that quietly accepted another's description would let a machine be run
     * against equations that were never given its numbers.
     */
    static const char FOREIGN[] = "steam.heater_power_w = 1000.0\n";
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(FOREIGN, sizeof(FOREIGN) - 1u, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_UNKNOWN, fault.fault);

    /*
     * And a description missing one of this structure's own coefficients is
     * refused rather than defaulted, so no value is ever assumed for a machine.
     */
    static const char INCOMPLETE[] = "ambient_temperature_c = 20.0\n";
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(INCOMPLETE, sizeof(INCOMPLETE) - 1u, &loaded, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_MISSING, fault.fault);
}

/*
 * What the equations compute, against an independent statement of the same
 * physics.
 *
 * Everything above asserts properties that hold whatever the coefficients are --
 * energy is not invented, a replay reproduces, the two temperatures do not drift
 * apart. Those are the right properties and they are deliberately indifferent to
 * the arithmetic, which is exactly why they leave it unpinned: the mutation sweep
 * altered every operator in these equations in turn and nine of the alterations
 * changed what the model says a machine does without a single test above
 * objecting.
 *
 * The distinction this section rests on is between two questions that are easy to
 * run together. Whether these equations describe a real single-boiler machine is
 * unknowable here and stays out of scope, as the preamble says. Whether they
 * compute what they claim to compute is a different question, and it is
 * answerable: the vessel is a first-order thermal relaxation, so its step has a
 * closed form, and the assertions below come from that closed form rather than
 * from the implementation's own formulation of it.
 *
 * That independence is the point. The implementation advances the state with an
 * effective-interval correction built out of expm1; these tests use the analytic
 * solution written the other way, with a plain exponential towards the settling
 * temperature. Restating the source's own expression would have made a test that
 * agreed with the code however the code was wrong.
 */

/* The temperature the vessel settles at under a constant delivered power. */
static float settling_temperature(float delivered_w)
{
    return AMBIENT_C + delivered_w / VESSEL_LOSS_W_PER_K;
}

/*
 * Where a first-order relaxation from `from` towards `settles_at` has reached
 * after `seconds`: the closed-form solution, in the form the implementation does
 * not use.
 */
static float relaxed(float from, float settles_at, float seconds)
{
    const float time_constant_s = VESSEL_MASS_J_PER_K / VESSEL_LOSS_W_PER_K;
    return settles_at + (from - settles_at) * expf(-seconds / time_constant_s);
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: a test earns its place by being capable of
/// failing on a plausible defect -- the vessel's step is the energy balance it
/// claims, so altering any operator in it is a change some test objects to.
static void test_the_vessel_step_is_the_energy_balance_it_claims(void)
{
    plant_model_t model;
    float before = 0.0f;
    float after = 0.0f;
    const plant_actuation_t applied = heating();

    initialise(&model);

    /*
     * Carried away from ambient first, and this is load-bearing rather than
     * tidiness. At ambient the loss term is zero, so a step taken from there
     * cannot tell a loss that opposes the heater from one that assists it --
     * which is one of the alterations that survived.
     */
    for (int i = 0; i < SETTLE_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &applied, STEP_MS));
    }

    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &before));
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &after));

    const float delivered_w = VESSEL_HEATER_W; /* Full duty. */
    const float seconds = (float)STEP_MS / 1000.0f;
    const float expected = relaxed(before, settling_temperature(delivered_w), seconds);

    TEST_ASSERT_TRUE(before < after);
    TEST_ASSERT_FLOAT_WITHIN(1e-3f, expected, after);
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: the duty a channel is driven at scales the
/// power delivered, so an alteration to that scaling is one a test objects to.
static void test_a_half_duty_delivers_half_the_power(void)
{
    plant_model_t model;
    float before = 0.0f;
    float after = 0.0f;
    plant_actuation_t applied = {{0u}};

    applied.level_permille[HEATING_CHANNEL] = ACTUATION_FULL_SCALE / 2u;

    initialise(&model);
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &before));
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &after));

    const float duty = (float)(ACTUATION_FULL_SCALE / 2u) / (float)ACTUATION_FULL_SCALE;
    const float delivered_w = VESSEL_HEATER_W * duty;
    const float seconds = (float)STEP_MS / 1000.0f;
    const float expected = relaxed(before, settling_temperature(delivered_w), seconds);

    TEST_ASSERT_FLOAT_WITHIN(1e-3f, expected, after);
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: a vessel losing nothing is an admissible
/// description and the one where the relaxation correction is asked for a value at
/// the edge of its domain, so the answer there is asserted rather than assumed.
static void test_a_vessel_that_loses_nothing_heats_at_the_rate_its_power_implies(void)
{
    /*
     * Zero loss is inside the declared range, and it is the description that
     * drives the time constant to nothing -- so the correction the step applies
     * is evaluated where its numerator and denominator both vanish. The limit is
     * one and the temperature rises by the plain energy balance; an alteration
     * that reaches the division anyway produces a value that is not a number,
     * and every quantity downstream of it stops being one. Nothing above would
     * notice, because a comparison against a NaN is false either way.
     */
    static const char LOSSLESS[] = "ambient_temperature_c = 20.0\n"
                                   "vessel.thermal_mass_j_per_k = 900.0\n"
                                   "vessel.heater_power_w = 1400.0\n"
                                   "vessel.loss_w_per_k = 0.0\n"
                                   "pump.pressure_bar = 15.0\n"
                                   "brew.pressure_time_constant_s = 0.8\n"
                                   "steam.saturation_temperature_c = 100.0\n"
                                   "steam.pressure_bar_per_k = 0.036\n";

    plant_parameters_t lossless;
    plant_parameter_error_t fault;
    plant_model_t model;
    float before = 0.0f;
    float after = 0.0f;
    const plant_actuation_t applied = heating();

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameters_load(LOSSLESS, sizeof(LOSSLESS) - 1u, &lossless, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    TEST_ASSERT_TRUE(plant_model_init(&model, &lossless));
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &before));
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &after));

    const float seconds = (float)STEP_MS / 1000.0f;
    const float expected = before + (VESSEL_HEATER_W * seconds) / VESSEL_MASS_J_PER_K;

    /* Stated outright: a NaN fails this where it passes a comparison. */
    TEST_ASSERT_FALSE(isnan(after));
    TEST_ASSERT_FLOAT_WITHIN(1e-3f, expected, after);
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: a step long enough for the relaxation to
/// matter is corrected for it, so altering that correction is a change some test
/// objects to.
static void test_a_long_step_is_corrected_for_the_relaxation_within_it(void)
{
    plant_model_t model;
    float before = 0.0f;
    float after = 0.0f;
    const plant_actuation_t applied = heating();

    /*
     * A step comparable with the vessel's time constant, and that is the whole
     * point of it. Over the short steps every other test takes, the correction
     * for the temperature changing during the step is within a part in ten
     * thousand of unity -- so an alteration to it moves the answer by less than
     * any tolerance worth asserting, and it survived. Here the correction is
     * about three quarters, and getting it wrong in either direction is a
     * difference of tens of degrees.
     *
     * A long step is also the case a caller most plausibly takes: catching up
     * after a pause, or simulating faster than real time.
     */
    const uint32_t interval_ms = 300000u; /* 300 s against a 450 s time constant. */

    initialise(&model);
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &before));
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, interval_ms));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &after));

    const float seconds = (float)interval_ms / 1000.0f;
    const float settles_at = settling_temperature(VESSEL_HEATER_W);
    const float expected = relaxed(before, settles_at, seconds);

    /*
     * Asserted against the closed form, and additionally required not to have
     * overshot: a relaxation cannot pass the temperature it is relaxing towards,
     * however long the step, and an uncorrected step of this length would.
     */
    TEST_ASSERT_TRUE(after < settles_at);
    TEST_ASSERT_FLOAT_WITHIN(1e-2f, expected, after);
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: above saturation the steam pressure is the
/// declared slope on the excess temperature, so altering either the difference or
/// the slope is a change some test objects to.
static void test_the_steam_pressure_is_the_declared_slope_above_saturation(void)
{
    plant_model_t model;
    float temperature = 0.0f;
    float pressure = 0.0f;
    const plant_actuation_t applied = heating();

    initialise(&model);
    for (int i = 0; i < BOIL_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &applied, STEP_MS));
    }

    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &temperature));
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &pressure));

    /* The premise of the assertion, not an assumption of it. */
    TEST_ASSERT_TRUE(temperature > SATURATION_C);

    const float expected = STEAM_BAR_PER_K * (temperature - SATURATION_C);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, expected, pressure);
}

/// OBL-VERIFICATION-DISCIPLINE-001.C2: below saturation the steam pressure is
/// nothing at all, which is the other side of the same comparison.
static void test_the_steam_pressure_is_nothing_below_saturation(void)
{
    plant_model_t model;
    float temperature = 0.0f;
    float pressure = 0.0f;

    initialise(&model);
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &temperature));
    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &pressure));

    TEST_ASSERT_TRUE(temperature < SATURATION_C);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, pressure);
}

/* --- The error the design assumes against a value ------------------------- */

/*
 * The same description with the error the design assumes for each value written
 * against it. It is carried here as text, like every other coefficient this
 * suite uses, so that what is exercised is the grammar and the seam rather than
 * whatever figures happen to be in the file under params/.
 *
 * A different figure against each, so that a record read back cannot be right
 * by accident: an implementation answering from the wrong position, or from the
 * first entry for everything, would pass an assertion made against one repeated
 * number.
 */
static const char ANNOTATED[] = "ambient_temperature_c = 20.0 ~ 0.25\n"
                                "vessel.thermal_mass_j_per_k = 900.0 ~ 0.4\n"
                                "vessel.heater_power_w = 1400.0 ~ 0.2\n"
                                "vessel.loss_w_per_k = 2.0 ~ 0.6\n"
                                "pump.pressure_bar = 15.0 ~ 0.35\n"
                                "brew.pressure_time_constant_s = 0.8 ~ 0.5\n"
                                "steam.saturation_temperature_c = 100.0 ~ 0.02\n"
                                "steam.pressure_bar_per_k = 0.036 ~ 0.3\n";

static const struct {
    const char *name;
    float assumed;
} ASSUMED[] = {
    {"ambient_temperature_c", 0.25f},
    {"vessel.thermal_mass_j_per_k", 0.4f},
    {"vessel.heater_power_w", 0.2f},
    {"vessel.loss_w_per_k", 0.6f},
    {"pump.pressure_bar", 0.35f},
    {"brew.pressure_time_constant_s", 0.5f},
    {"steam.saturation_temperature_c", 0.02f},
    {"steam.pressure_bar_per_k", 0.3f},
};

#define ASSUMED_COUNT (sizeof(ASSUMED) / sizeof(ASSUMED[0]))

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C2: the operation is answered by the shared loader, so a second structure inherits it without reimplementing it
static void test_the_assumed_error_is_read_through_the_seam_here_too(void)
{
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameter_budget_load(ANNOTATED, sizeof(ANNOTATED) - 1u, &budget, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    /*
     * Nothing in this structure's own sources knows what an assumed error is.
     * The coefficients are a different set from the other structures', and the
     * figures come back against the names this description uses.
     */
    for (size_t i = 0u; i < ASSUMED_COUNT; i++) {
        float assumed = -1.0f;
        TEST_ASSERT_TRUE(plant_parameter_budget_for(&budget, ASSUMED[i].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT(ASSUMED[i].assumed, assumed);
    }
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C2: a name this structure's table does not declare is refused rather than answered
static void test_a_name_this_structure_does_not_have_is_refused(void)
{
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;
    float assumed = 5.0f;

    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameter_budget_load(ANNOTATED, sizeof(ANNOTATED) - 1u, &budget, &fault));

    /*
     * A coefficient belonging to a structure of the other architecture. It is a
     * perfectly good name in that tree and means nothing in this one, and an
     * answer for it would mean the budget was being read from something other
     * than the structure this build compiled.
     */
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, "brew.thermal_mass_j_per_k", &assumed));
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, "steam.heater_power_w", &assumed));
    TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, "not.a.coefficient", &assumed));
    TEST_ASSERT_EQUAL_FLOAT(5.0f, assumed);
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: an assumed error that cannot stand is refused whatever structure the description is for
static void test_an_assumed_error_that_cannot_stand_is_refused_here_too(void)
{
    static const char NEGATIVE[] = "ambient_temperature_c = 20.0 ~ -0.25\n"
                                   "vessel.thermal_mass_j_per_k = 900.0 ~ 0.4\n"
                                   "vessel.heater_power_w = 1400.0 ~ 0.2\n"
                                   "vessel.loss_w_per_k = 2.0 ~ 0.6\n"
                                   "pump.pressure_bar = 15.0 ~ 0.35\n"
                                   "brew.pressure_time_constant_s = 0.8 ~ 0.5\n"
                                   "steam.saturation_temperature_c = 100.0 ~ 0.02\n"
                                   "steam.pressure_bar_per_k = 0.036 ~ 0.3\n";
    static const char EMPTY[] = "ambient_temperature_c = 20.0 ~\n"
                                "vessel.thermal_mass_j_per_k = 900.0 ~ 0.4\n"
                                "vessel.heater_power_w = 1400.0 ~ 0.2\n"
                                "vessel.loss_w_per_k = 2.0 ~ 0.6\n"
                                "pump.pressure_bar = 15.0 ~ 0.35\n"
                                "brew.pressure_time_constant_s = 0.8 ~ 0.5\n"
                                "steam.saturation_temperature_c = 100.0 ~ 0.02\n"
                                "steam.pressure_bar_per_k = 0.036 ~ 0.3\n";
    plant_parameters_t untouched;
    plant_parameters_t before;
    plant_parameter_error_t fault;

    memset(&untouched, 0xA5, sizeof(untouched));
    before = untouched;
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(
        plant_parameters_load(NEGATIVE, sizeof(NEGATIVE) - 1u, &untouched, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_ASSUMED_ERROR, fault.fault);
    TEST_ASSERT_EQUAL_STRING("ambient_temperature_c", fault.parameter);
    TEST_ASSERT_EQUAL_UINT32(1u, fault.line);
    TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_FALSE(plant_parameters_load(EMPTY, sizeof(EMPTY) - 1u, &untouched, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_ASSUMED_ERROR, fault.fault);
    TEST_ASSERT_EQUAL_STRING("ambient_temperature_c", fault.parameter);
    TEST_ASSERT_EQUAL_MEMORY(&before, &untouched, sizeof(before));
}

/// SOL-SIM-UNCERTAINTY-BUDGET-DECLARED-MODEL-ERROR.C3: a description carrying no assumed error at all still loads, and reads back as declaring none
static void test_the_suites_own_description_declares_no_assumed_error(void)
{
    plant_parameter_budget_t budget;
    plant_parameter_error_t fault;

    /*
     * The description the rest of this suite runs on carries no annotation of
     * any kind. It is not refused for that -- the loader's contract is
     * unchanged by the extension -- and every coefficient in it reads back as
     * having no error declared rather than as an error of zero.
     */
    memset(&budget, 0, sizeof(budget));
    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(
        plant_parameter_budget_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &budget, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);

    for (size_t i = 0u; i < ASSUMED_COUNT; i++) {
        float assumed = 4.0f;
        TEST_ASSERT_FALSE(plant_parameter_budget_for(&budget, ASSUMED[i].name, &assumed));
        TEST_ASSERT_EQUAL_FLOAT(4.0f, assumed);
    }
}


int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_an_instance_runs_a_whole_sequence_through_the_seam);
    RUN_TEST(test_the_declared_channels_are_the_ones_this_architecture_has);
    RUN_TEST(test_the_pump_drives_the_brew_pressure_and_leaves_the_vessel_alone);
    RUN_TEST(test_a_step_with_nothing_applied_moves_nothing);
    RUN_TEST(test_heat_raises_the_temperatures_and_lowers_no_quantity);
    RUN_TEST(test_the_same_sequence_twice_reproduces_the_same_trajectory);
    RUN_TEST(test_both_temperature_quantities_follow_the_one_vessel);
    RUN_TEST(test_the_structure_reads_its_own_coefficients_and_no_others);
    RUN_TEST(test_the_vessel_step_is_the_energy_balance_it_claims);
    RUN_TEST(test_a_half_duty_delivers_half_the_power);
    RUN_TEST(test_a_vessel_that_loses_nothing_heats_at_the_rate_its_power_implies);
    RUN_TEST(test_a_long_step_is_corrected_for_the_relaxation_within_it);
    RUN_TEST(test_the_steam_pressure_is_the_declared_slope_above_saturation);
    RUN_TEST(test_the_steam_pressure_is_nothing_below_saturation);
    RUN_TEST(test_the_assumed_error_is_read_through_the_seam_here_too);
    RUN_TEST(test_a_name_this_structure_does_not_have_is_refused);
    RUN_TEST(test_an_assumed_error_that_cannot_stand_is_refused_here_too);
    RUN_TEST(test_the_suites_own_description_declares_no_assumed_error);
    return UNITY_END();
}
