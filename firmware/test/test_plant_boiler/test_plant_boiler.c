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
#include <stdio.h>
#include <string.h>

#include <unity.h>

#include "estimator.h"
#include "estimator_limits.h"
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
                                  "pump.flow_ml_per_s = 7.0\n"
                                  "brew.pressure_time_constant_s = 0.8\n"
                                  "water.feed_temperature_c = 18.0\n"
                                  "water.heat_capacity_j_per_ml_k = 4.15\n"
                                  "water.latent_heat_j_per_ml = 2200.0\n"
                                  "steam.saturation_temperature_c = 100.0\n"
                                  "steam.pressure_bar_per_k = 0.036\n"
                                  "steam.pressure_fall_bar_per_ml = 0.03\n";

/*
 * The same description with the two temperatures the sensible half of a draw is
 * taken between left to the caller. Written as a format rather than as further
 * copies of the text above: a second copy is a second thing to keep in step, and
 * what a pair built from this is for is that everything but those two figures is
 * identical between its halves.
 */
static const char DESCRIPTION_FORMAT[] = "ambient_temperature_c = 20.0\n"
                                         "vessel.thermal_mass_j_per_k = 900.0\n"
                                         "vessel.heater_power_w = 1400.0\n"
                                         "vessel.loss_w_per_k = 2.0\n"
                                         "pump.pressure_bar = 15.0\n"
                                         "pump.flow_ml_per_s = 7.0\n"
                                         "brew.pressure_time_constant_s = 0.8\n"
                                         "water.feed_temperature_c = %.9g\n"
                                         "water.heat_capacity_j_per_ml_k = 4.15\n"
                                         "water.latent_heat_j_per_ml = 2200.0\n"
                                         "steam.saturation_temperature_c = %.9g\n"
                                         "steam.pressure_bar_per_k = 0.036\n"
                                         "steam.pressure_fall_bar_per_ml = 0.03\n";

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
#define PUMP_FLOW_ML_PER_S 7.0f
/* Below the ambient the vessel starts at, deliberately: a feed at ambient would
 * let a drawn-energy term that read ambient instead of the feed pass unnoticed,
 * and the two are separate quantities in the description for that reason. */
#define FEED_TEMPERATURE_C 18.0f
#define WATER_J_PER_ML_K 4.15f
/* What a millilitre costs to boil, which is the whole of what a steam draw costs
 * this vessel. Far from the figure above it on purpose: the two are separate
 * coefficients and a suite whose numbers were close together would let a
 * structure reading the wrong one pass. */
#define WATER_LATENT_J_PER_ML 2200.0f
#define SATURATION_C 100.0f
#define STEAM_BAR_PER_K 0.036f
/* What a draw costs the steam path in pressure, per millilitre drawn. */
#define STEAM_FALL_BAR_PER_ML 0.03f

/* The rate the tests below hold the wand open at, and one no machine of this
 * description could sustain -- two millilitres a second is four and a half
 * kilowatts of latent heat against a fourteen-hundred-watt element. Chosen so
 * the term moves the vessel by far more than the arithmetic's own resolution. */
#define STEAM_DRAW_ML_PER_S 2.0f

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

/* An instance described exactly as the one above is, but for where the feed
 * arrives and where it turns. Reached through the loader, so no field of the
 * parameter record is named here any more than anywhere else in this suite. */
static void initialise_between(plant_model_t *model, float feed_c, float saturation_c)
{
    char text[sizeof(DESCRIPTION_FORMAT) + 64];
    plant_parameters_t loaded;
    plant_parameter_error_t fault;

    const int written = snprintf(text, sizeof(text), DESCRIPTION_FORMAT, (double)feed_c,
                                 (double)saturation_c);
    TEST_ASSERT_TRUE(written > 0 && (size_t)written < sizeof(text));

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(text, (size_t)written, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(model, &loaded));
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
        TEST_ASSERT_TRUE(plant_model_step_reporting(&model, &actuation, 0.0f, STEP_MS, &record));
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

/// SOL-PLANT-STEAM-DRAW-CHANNELS.C6: Boiler and fixture correctly refuse the
/// new steam-feed channel.
/// SOL-PLANT-STEAM-FEED-PUMP-WIRED.C1: ...boiler is unaffected -- it does not
/// answer the channel and continues refusing it through the existing
/// admissibility check. The relation that reads the channel belongs to the
/// two-pump architecture, so wiring it there must not quietly admit it here.
static void test_the_steam_feed_channel_is_refused_here_too(void)
{
    plant_model_t model;
    plant_step_error_t refusal;
    plant_actuation_t feeding = {{0u}};

    /*
     * This architecture has one pump feeding one vessel; the second, steam-side
     * pump the new channel commands belongs to the two-pump machine only.
     * boiler's answered set is left untouched by the criterion that adds the
     * channel, so the same admissibility mechanism that already refuses
     * ACTUATION_CHANNEL_STEAM_HEATER here refuses this one too.
     */
    TEST_ASSERT_EQUAL_UINT32(0u, answered & ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_STEAM_PUMP));

    feeding.level_permille[ACTUATION_CHANNEL_STEAM_PUMP] = ACTUATION_FULL_SCALE;
    initialise(&model);
    TEST_ASSERT_FALSE(plant_model_step_reporting(&model, &feeding, 0.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_CHANNEL_UNANSWERED, refusal.fault);
    TEST_ASSERT_EQUAL(ACTUATION_CHANNEL_STEAM_PUMP, refusal.channel);
}

/// SOL-PLANT-STEAM-DRAW-CHANNELS.C1: Every plant structure's step accepts a
/// steam-demand rate the control law never sets.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C5: The new interfaces are exercised end to
/// end on the host verification tier.
static void test_a_steam_demand_alone_is_accepted(void)
{
    plant_model_t model;
    plant_step_error_t refusal;
    plant_actuation_t idle = {{0u}};

    /*
     * No channel commanded, so the only thing this step can be refused for is
     * the demand itself -- and nothing refuses it, because it is a step
     * argument rather than a member of the actuation record admissibility
     * checks against.
     */
    initialise(&model);
    TEST_ASSERT_TRUE(plant_model_step_reporting(&model, &idle, 250.0f, STEP_MS, &refusal));
    TEST_ASSERT_EQUAL(PLANT_STEP_OK, refusal.fault);
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...it answers all four
/// quantities the seam enumerates from its own states.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C2: The demand input defaults to zero and
/// changes no existing behaviour when unset. This structure's own precise,
/// formula-checked pressure trajectory is unmoved by the step gaining that
/// argument.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C4: Every existing actuation channel behaves
/// unchanged on every structure. Driven with the demand argument at zero,
/// ACTUATION_CHANNEL_PUMP's numeric behaviour here is exactly what it was
/// before the step gained that argument.
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &pumping, 0.0f, STEP_MS));
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
     * The pump is not a heater, and what it does to the vessel is the opposite
     * of heating it: the water it draws out is replaced by water arriving at the
     * feed temperature, which on this description is below where the vessel is
     * sitting, so the vessel goes down while the pump runs. It goes down, never
     * up -- a term entered with the wrong sign would warm a vessel by pumping
     * cold water through it, and that is the failure worth naming here rather
     * than a bare inequality.
     *
     * Both temperature quantities are the one vessel on this architecture, so
     * they have to have moved together; a pump that cooled one of them would
     * have made two bodies of water out of one.
     */
    float after[PLANT_QUANTITY_COUNT];
    read_all(&model, after);
    TEST_ASSERT_TRUE(after[PLANT_QUANTITY_BREW_TEMPERATURE_C] <
                     before[PLANT_QUANTITY_BREW_TEMPERATURE_C]);
    TEST_ASSERT_EQUAL_FLOAT(after[PLANT_QUANTITY_BREW_TEMPERATURE_C],
                            after[PLANT_QUANTITY_STEAM_TEMPERATURE_C]);
    /* And it does not go below what it is being fed, which is what the vessel
     * is relaxing towards rather than a bound the equations impose. */
    TEST_ASSERT_TRUE(after[PLANT_QUANTITY_BREW_TEMPERATURE_C] > FEED_TEMPERATURE_C);

    /* Steam pressure still follows the vessel and not the pump: the vessel is
     * far below saturation throughout, so it is nothing before and after. */
    TEST_ASSERT_EQUAL_FLOAT(before[PLANT_QUANTITY_STEAM_PRESSURE_BAR],
                            after[PLANT_QUANTITY_STEAM_PRESSURE_BAR]);
    TEST_ASSERT_EQUAL_FLOAT(0.0f, after[PLANT_QUANTITY_STEAM_PRESSURE_BAR]);
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &idle, 0.0f, STEP_MS));
    }

    read_all(&model, after);
    TEST_ASSERT_EQUAL_MEMORY(before, after, sizeof(before));
}

/// SOL-PLANT-STRUCTURE-SEAM-SECOND-STRUCTURE.C1: ...a step with heat applied to
/// a channel it answers raises the temperature quantities and lowers none.
/// SOL-PLANT-STEAM-DRAW-CHANNELS.C4: Every existing actuation channel behaves
/// unchanged on every structure. Driven with the demand argument at zero,
/// HEATING_CHANNEL's numeric behaviour here is exactly what it was before the
/// step gained that argument.
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, STEP_MS));
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &varying, 0.0f, STEP_MS));
        read_all(&model, recorded[i]);
    }

    initialise(&model);
    for (int i = 0; i < SETTLE_STEPS; i++) {
        const plant_actuation_t varying = varying_actuation(i);
        TEST_ASSERT_TRUE(plant_model_step(&model, &varying, 0.0f, STEP_MS));
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, STEP_MS));
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, STEP_MS));
    }

    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_BREW_TEMPERATURE_C, &before));
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, STEP_MS));
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
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, STEP_MS));
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
                                   "pump.flow_ml_per_s = 7.0\n"
                                   "brew.pressure_time_constant_s = 0.8\n"
                                   "water.feed_temperature_c = 18.0\n"
                                   "water.heat_capacity_j_per_ml_k = 4.15\n"
                                   "water.latent_heat_j_per_ml = 2200.0\n"
                                   "steam.saturation_temperature_c = 100.0\n"
                                   "steam.pressure_bar_per_k = 0.036\n"
                                   "steam.pressure_fall_bar_per_ml = 0.03\n";

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
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, STEP_MS));
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
    TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, interval_ms));
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
        TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, STEP_MS));
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
                                "pump.flow_ml_per_s = 7.0 ~ 0.45\n"
                                "brew.pressure_time_constant_s = 0.8 ~ 0.5\n"
                                "water.feed_temperature_c = 18.0 ~ 0.5\n"
                                "water.heat_capacity_j_per_ml_k = 4.15 ~ 0.03\n"
                                "water.latent_heat_j_per_ml = 2200.0 ~ 0.05\n"
                                "steam.saturation_temperature_c = 100.0 ~ 0.02\n"
                                "steam.pressure_bar_per_k = 0.036 ~ 0.3\n"
                                "steam.pressure_fall_bar_per_ml = 0.03 ~ 0.65\n";

static const struct {
    const char *name;
    float assumed;
} ASSUMED[] = {
    {"ambient_temperature_c", 0.25f},
    {"vessel.thermal_mass_j_per_k", 0.4f},
    {"vessel.heater_power_w", 0.2f},
    {"vessel.loss_w_per_k", 0.6f},
    {"pump.pressure_bar", 0.35f},
    {"pump.flow_ml_per_s", 0.45f},
    {"brew.pressure_time_constant_s", 0.5f},
    {"water.feed_temperature_c", 0.5f},
    {"water.heat_capacity_j_per_ml_k", 0.03f},
    {"water.latent_heat_j_per_ml", 0.05f},
    {"steam.saturation_temperature_c", 0.02f},
    {"steam.pressure_bar_per_k", 0.3f},
    {"steam.pressure_fall_bar_per_ml", 0.65f},
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
                                   "pump.flow_ml_per_s = 7.0 ~ 0.45\n"
                                   "brew.pressure_time_constant_s = 0.8 ~ 0.5\n"
                                   "water.feed_temperature_c = 18.0 ~ 0.5\n"
                                   "water.heat_capacity_j_per_ml_k = 4.15 ~ 0.03\n"
                                   "water.latent_heat_j_per_ml = 2200.0 ~ 0.05\n"
                                   "steam.saturation_temperature_c = 100.0 ~ 0.02\n"
                                   "steam.pressure_bar_per_k = 0.036 ~ 0.3\n"
                                   "steam.pressure_fall_bar_per_ml = 0.03 ~ 0.65\n";
    static const char EMPTY[] = "ambient_temperature_c = 20.0 ~\n"
                                "vessel.thermal_mass_j_per_k = 900.0 ~ 0.4\n"
                                "vessel.heater_power_w = 1400.0 ~ 0.2\n"
                                "vessel.loss_w_per_k = 2.0 ~ 0.6\n"
                                "pump.pressure_bar = 15.0 ~ 0.35\n"
                                "pump.flow_ml_per_s = 7.0 ~ 0.45\n"
                                "brew.pressure_time_constant_s = 0.8 ~ 0.5\n"
                                "water.feed_temperature_c = 18.0 ~ 0.5\n"
                                "water.heat_capacity_j_per_ml_k = 4.15 ~ 0.03\n"
                                "water.latent_heat_j_per_ml = 2200.0 ~ 0.05\n"
                                "steam.saturation_temperature_c = 100.0 ~ 0.02\n"
                                "steam.pressure_bar_per_k = 0.036 ~ 0.3\n"
                                "steam.pressure_fall_bar_per_ml = 0.03 ~ 0.65\n";
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


/// SOL-PLANT-RECONSTRUCTABLE-STATE.C3: Every plant structure answers the state
/// accessor.
///
/// This architecture heats the water in the vessel it delivers from, so nothing
/// sits between the mass and what leaves it. Asking it for the water on its way
/// to the group is asking the wrong structure, and it says so rather than
/// handing back the vessel -- which is the whole value of the refusal, because a
/// caller given the vessel under that name would go on to reconstruct a state it
/// was already being told.
static void test_this_structure_refuses_the_state_it_does_not_keep(void)
{
    const float SENTINEL = -777.0f;
    plant_model_t model;
    float value = SENTINEL;
    float vessel = 0.0f;

    const plant_actuation_t applied = heating();

    initialise(&model);
    for (int i = 0; i < SETTLE_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, STEP_MS));
    }

    TEST_ASSERT_FALSE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &value));
    /* Not zeroed, and not quietly the vessel either. */
    TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);

    TEST_ASSERT_TRUE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &vessel));
    TEST_ASSERT_TRUE(vessel != SENTINEL);
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C3: Every plant structure answers the state
/// accessor.
///
/// Every state it does keep carries the quantity it names, so a case wired to
/// the wrong field is caught here -- that is a switch of assignments, which
/// produces no arithmetic for the operator sweep to mutate and passes every
/// property asserted about the trajectory. The two temperatures come back as the
/// one vessel, which is the same answer the quantities of those names give,
/// because on this architecture they are the same body of water.
static void test_every_state_this_structure_keeps_carries_what_it_names(void)
{
    plant_model_t model;
    float mass_state = 0.0f;
    float steam_state = 0.0f;
    float brew_pressure = 0.0f;
    float steam_pressure = 0.0f;
    float quantities[PLANT_QUANTITY_COUNT];

    plant_actuation_t applied = heating();

    /* Heat and pump together, and long enough to carry the vessel past
     * saturation: at rest both pressures are zero, and two states that are both
     * zero cannot show a crossed pair. */
    applied.level_permille[ACTUATION_CHANNEL_PUMP] = ACTUATION_FULL_SCALE / 2u;

    initialise(&model);
    for (int i = 0; i < BOIL_STEPS; i++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &applied, 0.0f, STEP_MS));
    }
    for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
        TEST_ASSERT_TRUE(
            plant_model_quantity(&model, (plant_quantity_t)quantity, &quantities[quantity]));
    }

    TEST_ASSERT_TRUE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &mass_state));
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, &steam_state));
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_BREW_PRESSURE_BAR, &brew_pressure));
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_STEAM_PRESSURE_BAR, &steam_pressure));

    /* The temperatures are one vessel and the pressures are two different
     * numbers, so a crossed pair among them would show. */
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_BREW_TEMPERATURE_C], mass_state);
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_STEAM_TEMPERATURE_C], steam_state);
    TEST_ASSERT_EQUAL_FLOAT(mass_state, steam_state);
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_BREW_PRESSURE_BAR], brew_pressure);
    TEST_ASSERT_EQUAL_FLOAT(quantities[PLANT_QUANTITY_STEAM_PRESSURE_BAR], steam_pressure);
    TEST_ASSERT_TRUE(brew_pressure != steam_pressure);
}

/// SOL-PLANT-RECONSTRUCTABLE-STATE.C3: Every plant structure answers the state
/// accessor.
///
/// A state read from an instance that was never initialised is refused on the
/// terms plant_model_quantity already refuses one, here as in the structure that
/// keeps every state -- so the refusal is the seam's and not one architecture's
/// habit.
static void test_a_state_read_from_an_uninitialised_instance_is_refused_here_too(void)
{
    const float SENTINEL = -888.0f;
    plant_model_t uninitialised;
    float value = SENTINEL;

    memset(&uninitialised, 0, sizeof(uninitialised));
    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        value = SENTINEL;
        TEST_ASSERT_FALSE(plant_model_state(&uninitialised, (plant_state_t)state, &value));
        TEST_ASSERT_EQUAL_FLOAT(SENTINEL, value);
    }
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// This architecture keeps one vessel where the vocabulary names two bodies of
/// water, so it accepts the write everywhere it answers the read and refuses it
/// for the state it does not keep. A structure that took a write it would not
/// answer a read for could be written to and then not read back.
static void test_this_structure_answers_the_writes_it_answers_the_reads_for(void)
{
    plant_parameters_t parameters;
    plant_parameter_error_t fault;
    plant_model_t model;
    unsigned refused = 0u;

    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    for (int state = 0; state < PLANT_STATE_COUNT; state++) {
        float held = 0.0f;
        if (plant_model_state(&model, (plant_state_t)state, &held)) {
            float read_back = 0.0f;
            TEST_ASSERT_TRUE(plant_model_set_state(&model, (plant_state_t)state, held + 3.25f));
            TEST_ASSERT_TRUE(plant_model_state(&model, (plant_state_t)state, &read_back));
            TEST_ASSERT_EQUAL_FLOAT(held + 3.25f, read_back);
        } else {
            TEST_ASSERT_FALSE(plant_model_set_state(&model, (plant_state_t)state, 1.0f));
            refused++;
        }
    }

    TEST_ASSERT_TRUE_MESSAGE(refused > 0u, "this structure refused no write, so nothing was shown");

    /* And the refusals that hold whatever a structure keeps. */
    plant_model_t uninitialised;
    memset(&uninitialised, 0, sizeof(uninitialised));
    TEST_ASSERT_FALSE(
        plant_model_set_state(&uninitialised, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 1.0f));
    TEST_ASSERT_FALSE(plant_model_set_state(NULL, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 1.0f));
    TEST_ASSERT_FALSE(plant_model_set_state(&model, (plant_state_t)PLANT_STATE_COUNT, 1.0f));
}

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C13: Every plant structure answers a
/// state written through the seam.
///
/// One vessel serves both temperatures here, so a write to either is a write to
/// the same state. That is what it means for them to be one body of water, and
/// a structure that let them drift apart under writing would be reporting two
/// bodies it does not have.
static void test_writing_either_temperature_moves_the_one_vessel(void)
{
    plant_parameters_t parameters;
    plant_parameter_error_t fault;
    plant_model_t model;
    float brew = 0.0f;
    float steam = 0.0f;

    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &parameters));

    TEST_ASSERT_TRUE(
        plant_model_set_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 64.0f));
    TEST_ASSERT_TRUE(plant_model_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, &steam));
    TEST_ASSERT_EQUAL_FLOAT(64.0f, steam);

    TEST_ASSERT_TRUE(plant_model_set_state(&model, PLANT_STATE_STEAM_TEMPERATURE_C, 111.0f));
    TEST_ASSERT_TRUE(
        plant_model_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &brew));
    TEST_ASSERT_EQUAL_FLOAT(111.0f, brew);
}

/*
 * A limits declaration for the estimator to be brought up against. It carries
 * the statement that exempts it from accounting for its figures, because this
 * suite describes no machine and the numbers below mean nothing: what is being
 * established here is that the structure is refused, and an estimator refused
 * for want of a limits record would be refused for the wrong reason.
 */
static const char LIMITS_DECLARATION[] = "@describes-no-machine\n"
                                         "brew-temperature = -10000 .. 250000\n"
                                         "steam-temperature = -10000 .. 250000\n"
                                         "brew-pressure = -1000 .. 20000\n"
                                         "steam-pressure = -1000 .. 20000\n"
                                         "flow = -1000 .. 20000\n"
                                         "loss-tolerance-window-ms = 500\n"
                                         "excursion-bound-milli-c = 15000\n";

/// SOL-UNMEASURED-STATE-RECONSTRUCTION.C12: The estimator refuses a structure
/// that lacks the state it reconstructs.
///
/// Nothing sits between this architecture's heated mass and what leaves it, so
/// there is no state here to reconstruct. The estimator says so rather than
/// handing back the vessel under the name of the water on its way to the group,
/// which would be reconstructing something that was already being read.
static void test_the_estimator_refuses_this_architecture(void)
{
    plant_parameters_t parameters;
    plant_parameter_error_t fault;
    estimator_t estimator;
    float value = -999.0f;

    TEST_ASSERT_TRUE(
        plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &parameters, &fault));

    estimator_limits_t limits;
    estimator_limits_error_t limits_fault;
    TEST_ASSERT_TRUE(estimator_limits_load(LIMITS_DECLARATION, sizeof(LIMITS_DECLARATION) - 1u,
                                           &limits, &limits_fault));

    TEST_ASSERT_FALSE(estimator_init(&estimator, &parameters, &limits));
    TEST_ASSERT_FALSE(estimator_state(&estimator, ESTIMATOR_STATE_BREW_TEMPERATURE_C, &value));
    TEST_ASSERT_EQUAL_FLOAT(-999.0f, value);

    const plant_actuation_t idle = {{0u}};
    TEST_ASSERT_FALSE(estimator_step(&estimator, &idle, 100u));
}

/// SOL-PLANT-FLOW-REPORTED.C2: Every plant structure answers the flow quantity.
///
/// The single-vessel structure answers the rate water is drawn, and answers it
/// from rest as well as under a draw. This is the structure that refuses a
/// state -- the water on its way to the group, which it does not model -- so it
/// is the one where the difference between the two vocabularies is visible: a
/// state may be declined and a quantity may not, and a structure that treated
/// the rate like the outlet would be refusing something the seam promises every
/// consumer can read.
static void test_the_single_vessel_structure_answers_the_drawn_rate(void)
{
    plant_model_t model;
    plant_actuation_t drawing = {{0u}};
    float drawn = -1.0f;
    float refused_state = 0.0f;

    initialise(&model);
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    /* The state it declines, for contrast: the refusal is a property of the
     * state vocabulary and reaches no quantity. */
    TEST_ASSERT_FALSE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &refused_state));

    drawing.level_permille[ACTUATION_CHANNEL_PUMP] = ACTUATION_FULL_SCALE;
    TEST_ASSERT_TRUE(plant_model_step(&model, &drawing, 0.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));
    TEST_ASSERT_TRUE(drawn > 0.0f);
}

/// SOL-PLANT-FLOW-REPORTED.C3: The reported rate follows the pump's commanded
/// level.
///
/// Held on this structure as well as on the reference one, against the
/// coefficient this description gives rather than against the other's. Two
/// structures answering the same quantity from the same commanded level is what
/// makes the quantity the machine's rather than a structure's, and a structure
/// that scaled it differently would give a consumer a figure whose meaning
/// depended on which build it was talking to.
static void test_the_drawn_rate_follows_the_commanded_pump_level(void)
{
    static const uint16_t LEVELS[] = {0u, ACTUATION_FULL_SCALE / 4u, ACTUATION_FULL_SCALE / 2u,
                                      ACTUATION_FULL_SCALE};
    /* The figure this suite's own description gives for the rate at full scale. */
    static const float AT_FULL_SCALE = 7.0f;

    for (size_t i = 0u; i < sizeof(LEVELS) / sizeof(LEVELS[0]); i++) {
        plant_model_t model;
        plant_actuation_t actuation = {{0u}};
        float drawn = -1.0f;

        actuation.level_permille[ACTUATION_CHANNEL_PUMP] = LEVELS[i];
        initialise(&model);
        TEST_ASSERT_TRUE(plant_model_step(&model, &actuation, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn));

        TEST_ASSERT_EQUAL_FLOAT(
            AT_FULL_SCALE * ((float)LEVELS[i] / (float)ACTUATION_FULL_SCALE), drawn);
    }
}

/* --- The energy the drawn water carries out of the vessel ----------------- */

/* A command on the vessel's heater and the pump, in parts per thousand of each. */
static plant_actuation_t commanding(uint16_t heater_permille, uint16_t pump_permille)
{
    plant_actuation_t actuation = {{0u}};

    actuation.level_permille[HEATING_CHANNEL] = heater_permille;
    actuation.level_permille[ACTUATION_CHANNEL_PUMP] = pump_permille;
    return actuation;
}

/* The one temperature this architecture keeps, read through the seam. */
static float vessel(const plant_model_t *model)
{
    float value = 0.0f;

    TEST_ASSERT_TRUE(
        plant_model_state(model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, &value));
    return value;
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C1: The casting loses energy to the water drawn
/// through it, and every structure that answers the pump channel carries that
/// term rather than only the reference one.
///
/// This architecture answers the pump channel, so it owes the term. Two
/// instances of one description, started together above ambient with the element
/// off and stepped side by side with the pump the only difference: the one being
/// drawn through falls faster at every step, and ends far lower. A term added to
/// the reference structure and not to this one would leave these two identical,
/// which is the failure this test is written against -- and it is not a
/// hypothetical one, since it is precisely what a change made in one file rather
/// than in both would produce.
static void test_a_draw_cools_the_vessel_faster_than_no_draw(void)
{
    plant_model_t drawn;
    plant_model_t undrawn;

    initialise(&drawn);
    initialise(&undrawn);
    TEST_ASSERT_TRUE(
        plant_model_set_state(&drawn, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 90.0f));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&undrawn, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, 90.0f));

    const plant_actuation_t with_draw = commanding(0u, ACTUATION_FULL_SCALE);
    const plant_actuation_t without_draw = commanding(0u, 0u);

    float previous_drawn = 90.0f;
    float previous_undrawn = 90.0f;

    for (int step = 0; step < SETTLE_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&drawn, &with_draw, 0.0f, STEP_MS));
        TEST_ASSERT_TRUE(plant_model_step(&undrawn, &without_draw, 0.0f, STEP_MS));

        const float now_drawn = vessel(&drawn);
        const float now_undrawn = vessel(&undrawn);

        /* Both cooling, so what is compared is two falls rather than a fall
         * against a rise. */
        TEST_ASSERT_TRUE(now_drawn < previous_drawn);
        TEST_ASSERT_TRUE(now_undrawn < previous_undrawn);
        TEST_ASSERT_TRUE((previous_drawn - now_drawn) > (previous_undrawn - now_undrawn));

        previous_drawn = now_drawn;
        previous_undrawn = now_undrawn;
    }

    TEST_ASSERT_TRUE(previous_undrawn - previous_drawn > 5.0f);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C1: The casting loses energy to the water drawn
/// through it -- with the heater holding, the droop under draw is larger than the
/// model produces with no draw.
/// SOL-PLANT-FLOW-ENERGY-BALANCE.C7: The heat a unit of drawn water carries is a
/// described coefficient -- a volumetric heat capacity, since the rate it
/// multiplies is a volume per unit time.
///
/// Held under a constant element and a constant draw until it stops moving, the
/// vessel settles where the balance puts it: what the element delivers equals
/// what the loss coefficient carries to the room plus what the drawn volume
/// carries away above the temperature the water arrived at. The figure is
/// arithmetic from this suite's own coefficients, so a heat capacity per unit
/// mass, or a difference taken against ambient rather than against the feed,
/// lands somewhere this refuses.
static void test_the_vessel_settles_where_the_drawn_energy_balance_puts_it(void)
{
    plant_model_t model;
    const plant_actuation_t working = commanding(ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE);

    initialise(&model);
    /* Long against this vessel's own time constant under a draw, which is what
     * settling means for a mass this size against a rate this large. */
    for (int step = 0; step < 4000; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &working, 0.0f, STEP_MS));
    }

    const double carried_w_per_k = (double)PUMP_FLOW_ML_PER_S * (double)WATER_J_PER_ML_K;
    const double settled = ((double)VESSEL_HEATER_W + (double)VESSEL_LOSS_W_PER_K * (double)AMBIENT_C +
                            carried_w_per_k * (double)FEED_TEMPERATURE_C) /
                           ((double)VESSEL_LOSS_W_PER_K + carried_w_per_k);
    const double got = (double)vessel(&model);

    if (!(fabs(got - settled) < 0.05)) {
        char message[220];
        (void)snprintf(message, sizeof(message), "settled at %.9g, the balance gives %.9g", got,
                       settled);
        TEST_FAIL_MESSAGE(message);
    }

    /* And far below where the same element holds the same vessel with the pump
     * closed, which is the droop the term exists to produce. */
    TEST_ASSERT_TRUE(got < (double)AMBIENT_C +
                               (double)VESSEL_HEATER_W / (double)VESSEL_LOSS_W_PER_K - 100.0);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C1: The casting loses energy to the water drawn
/// through it, and the term joins the ambient loss the vessel already carries.
///
/// Joining it means more than being added to the power: what the vessel is
/// relaxing towards and how fast it gets there are both set by the two
/// coefficients together, so the correction a long step is made for has to be
/// computed from their sum. Over the short steps the rest of this suite takes,
/// that correction is within a part in ten thousand of unity and an alteration
/// to it moves nothing any tolerance would notice. Here the step is comparable
/// with the vessel's time constant under a draw -- which the draw has shortened
/// from four hundred and fifty seconds to about thirty -- and a correction
/// computed from the ambient coefficient alone, or from a difference of the two,
/// misses by tens of degrees or drives the vessel clean past what it is relaxing
/// towards.
static void test_a_long_step_under_a_draw_is_corrected_for_both_losses(void)
{
    plant_model_t model;
    /* Ten seconds against a time constant of about thirty. */
    const uint32_t interval_ms = 10000u;
    const float start_c = 90.0f;

    initialise(&model);
    TEST_ASSERT_TRUE(
        plant_model_set_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, start_c));

    const plant_actuation_t drawing_only = commanding(0u, ACTUATION_FULL_SCALE);
    TEST_ASSERT_TRUE(plant_model_step(&model, &drawing_only, 0.0f, interval_ms));

    const float seconds = (float)interval_ms / 1000.0f;
    const float drawn_w_per_k = PUMP_FLOW_ML_PER_S * WATER_J_PER_ML_K;
    const float settling_w_per_k = VESSEL_LOSS_W_PER_K + drawn_w_per_k;
    /* Where the two losses together put it, and how fast the two together take
     * it there -- the closed form, in the form the implementation does not
     * use. */
    const float settles_at =
        (VESSEL_LOSS_W_PER_K * AMBIENT_C + drawn_w_per_k * FEED_TEMPERATURE_C) / settling_w_per_k;
    const float time_constant_s = VESSEL_MASS_J_PER_K / settling_w_per_k;
    const float expected = settles_at + (start_c - settles_at) * expf(-seconds / time_constant_s);
    const float got = vessel(&model);

    /*
     * Above what it is relaxing towards and below where it started, asserted
     * outright: a relaxation cannot pass its own settling value however long the
     * step, and a step taken as though the rate held across this one would go
     * straight through it and out the far side.
     */
    TEST_ASSERT_FALSE(isnan(got));
    TEST_ASSERT_TRUE(got > settles_at);
    TEST_ASSERT_TRUE(got < start_c);
    TEST_ASSERT_FLOAT_WITHIN(1e-2f, expected, got);
}

/// SOL-PLANT-FLOW-ENERGY-BALANCE.C1: The energy the drawn water removes is the
/// drawn rate against the temperature difference across the vessel.
///
/// The term's shape read off one short step, at three vessel temperatures. On
/// this architecture the difference is taken at the vessel itself, and that is
/// the architecture rather than a shortcut: there is no state between the mass
/// and what leaves it here, because the water on its way out is the water in the
/// vessel -- which is exactly why this structure refuses the outlet state the
/// other one keeps. The reference structure's rule that the difference must not
/// be taken at the casting is a rule about a machine with two bodies of water,
/// and this one has one.
///
/// The middle of the three temperatures is the feed itself, where the drawn term
/// contributes exactly nothing however hard the pump is driven. A term written
/// against ambient instead of the feed removes energy there and fails; so does
/// one that took a difference the wrong way round, since the coldest of the
/// three sits below the feed and has to gain rather than lose.
static void test_the_drawn_loss_is_taken_between_the_vessel_and_the_feed(void)
{
    static const float STARTS[] = {5.0f, FEED_TEMPERATURE_C, 95.0f};
    static const uint32_t INTERVAL_MS = 1u;

    for (size_t i = 0u; i < sizeof(STARTS) / sizeof(STARTS[0]); i++) {
        plant_model_t model;

        initialise(&model);
        TEST_ASSERT_TRUE(
            plant_model_set_state(&model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, STARTS[i]));

        const plant_actuation_t drawing_only = commanding(0u, ACTUATION_FULL_SCALE);
        TEST_ASSERT_TRUE(plant_model_step(&model, &drawing_only, 0.0f, INTERVAL_MS));

        const double seconds = (double)INTERVAL_MS / 1000.0;
        const double start = (double)STARTS[i];
        const double lost_w =
            (double)VESSEL_LOSS_W_PER_K * (start - (double)AMBIENT_C) +
            (double)PUMP_FLOW_ML_PER_S * (double)WATER_J_PER_ML_K *
                (start - (double)FEED_TEMPERATURE_C);
        const double expected = start - (lost_w * seconds) / (double)VESSEL_MASS_J_PER_K;
        const double got = (double)vessel(&model);

        /*
         * A step of a millisecond against a vessel whose shortest time constant
         * is tens of seconds, so the difference between the rate at the start of
         * the step and the exact traverse across it is far below this tolerance.
         * What is compared is the term's magnitude, not the integration.
         */
        if (!(fabs(got - expected) < 1.0e-5)) {
            char message[240];
            (void)snprintf(message, sizeof(message),
                           "from %.9g: the vessel reached %.9g, the two losses give %.9g", start,
                           got, expected);
            TEST_FAIL_MESSAGE(message);
        }
    }

    /* And at the feed temperature the pump costs the vessel nothing at all: what
     * moved it there is the room, and it moved by what the room alone gives. */
    plant_model_t at_feed;
    initialise(&at_feed);
    TEST_ASSERT_TRUE(plant_model_set_state(&at_feed, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C,
                                           FEED_TEMPERATURE_C));
    const plant_actuation_t drawing_only = commanding(0u, ACTUATION_FULL_SCALE);
    TEST_ASSERT_TRUE(plant_model_step(&at_feed, &drawing_only, 0.0f, INTERVAL_MS));
    /* Ambient is above the feed on this description, so the room is warming it
     * -- upwards, which a drawn term written against ambient could not leave
     * alone. */
    TEST_ASSERT_TRUE(vessel(&at_feed) > FEED_TEMPERATURE_C);
}

/* --- What the steam drawn off the vessel costs it ------------------------- */

/* The steam path's pressure, read through the seam. */
static float steam_pressure(const plant_model_t *model)
{
    float value = 0.0f;

    TEST_ASSERT_TRUE(plant_model_quantity(model, PLANT_QUANTITY_STEAM_PRESSURE_BAR, &value));
    return value;
}

/* What the saturation relation alone gives at a vessel temperature, written the
 * way this architecture states it rather than the way the source spells it. */
static float saturation_pressure(float vessel_temperature_c)
{
    const float above = vessel_temperature_c - SATURATION_C;
    return above > 0.0f ? STEAM_BAR_PER_K * above : 0.0f;
}

/*
 * What a millilitre drawn as steam costs the vessel, from the description's own
 * figures: the feed carried from the temperature it arrives at up to the one it
 * turns at, and then turned. Written out here rather than read from the
 * structure, so a term that dropped either half, or took the difference against
 * the vessel instead of between the two coefficients, disagrees with this.
 */
#define STEAM_COST_J_PER_ML \
    (WATER_LATENT_J_PER_ML + WATER_J_PER_ML_K * (SATURATION_C - FEED_TEMPERATURE_C))

/// SOL-PLANT-STEAM-DRAW-ENERGY.C1: The steam-side state each structure keeps
/// loses energy to drawn steam through its latent heat, independent of any
/// existing loss term.
/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C1: Both structures' steam-side loss term
/// sums latent and sensible heat against the feed.
///
/// This architecture keeps one state for both sides, so the steam-side state it
/// keeps is the vessel -- and the vessel owes the term. Asserted against the
/// closed form of its own balance with the wand open: the loss coefficient sets
/// how fast it relaxes and the latent power sets where it is relaxing to. The
/// pump is shut throughout, so the only two things acting are the room and the
/// wand, and a term of the wrong size, of the wrong sign, or one that entered
/// the relaxation instead of the balance lands somewhere this refuses.
static void test_the_vessel_pays_the_heat_of_what_is_drawn_off_it(void)
{
    static const float STARTS[] = {40.0f, 95.0f, 150.0f};
    static const uint32_t INTERVAL_MS = 100u;

    for (size_t i = 0u; i < sizeof(STARTS) / sizeof(STARTS[0]); i++) {
        plant_model_t model;
        const plant_actuation_t idle = commanding(0u, 0u);

        initialise(&model);
        TEST_ASSERT_TRUE(plant_model_set_state(
            &model, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, STARTS[i]));
        TEST_ASSERT_TRUE(plant_model_step(&model, &idle, STEAM_DRAW_ML_PER_S, INTERVAL_MS));

        const double seconds = (double)INTERVAL_MS / 1000.0;
        const double drawn_w = (double)STEAM_COST_J_PER_ML * (double)STEAM_DRAW_ML_PER_S;
        const double settles_at = (double)AMBIENT_C - drawn_w / (double)VESSEL_LOSS_W_PER_K;
        const double time_constant_s =
            (double)VESSEL_MASS_J_PER_K / (double)VESSEL_LOSS_W_PER_K;
        const double expected =
            settles_at + ((double)STARTS[i] - settles_at) * exp(-seconds / time_constant_s);
        const double got = (double)vessel(&model);

        if (!(fabs(got - expected) < 1.0e-3)) {
            char message[240];
            (void)snprintf(message, sizeof(message),
                           "from %.9g: the vessel reached %.9g, the balance with the wand open "
                           "gives %.9g",
                           (double)STARTS[i], got, expected);
            TEST_FAIL_MESSAGE(message);
        }
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C1: ...through its latent heat, independent of
/// any existing loss term.
///
/// The shape of the term rather than its size, and what separates a latent heat
/// from the sensible-heat difference this structure already writes for the water
/// its pump draws out. What the wand costs is a power the rate alone fixes, so
/// the difference between a step with it open and the same step with it shut is
/// the same number wherever the vessel is sitting -- and stays the same number
/// with the pump open beside it, which is the independence the two terms are
/// required to have. The sensible half the steam term carries is a difference
/// too, and this is what says which difference it is: between the feed and
/// saturation, both coefficients, rather than against the vessel's own state. A
/// steam term written against the vessel, or folded into the drawn-water
/// coefficient, changes with both.
/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C1: ...against the feed, and not against
/// the state the vessel happens to be at.
static void test_what_the_wand_costs_is_the_same_wherever_the_vessel_sits(void)
{
    static const float STARTS[] = {60.0f, 150.0f};
    static const uint16_t PUMPS[] = {0u, ACTUATION_FULL_SCALE};
    static const uint32_t INTERVAL_MS = 100u;

    float costs[sizeof(STARTS) / sizeof(STARTS[0])][sizeof(PUMPS) / sizeof(PUMPS[0])];

    for (size_t i = 0u; i < sizeof(STARTS) / sizeof(STARTS[0]); i++) {
        for (size_t j = 0u; j < sizeof(PUMPS) / sizeof(PUMPS[0]); j++) {
            plant_model_t drawn;
            plant_model_t undrawn;
            const plant_actuation_t actuation = commanding(0u, PUMPS[j]);

            initialise(&drawn);
            initialise(&undrawn);
            TEST_ASSERT_TRUE(plant_model_set_state(
                &drawn, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, STARTS[i]));
            TEST_ASSERT_TRUE(plant_model_set_state(
                &undrawn, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, STARTS[i]));

            TEST_ASSERT_TRUE(plant_model_step(&drawn, &actuation, STEAM_DRAW_ML_PER_S,
                                              INTERVAL_MS));
            TEST_ASSERT_TRUE(plant_model_step(&undrawn, &actuation, 0.0f, INTERVAL_MS));

            costs[i][j] = vessel(&undrawn) - vessel(&drawn);
        }
    }

    /*
     * With the pump shut the cost is a power over a thermal mass over a step,
     * the relaxation across so short a step being within a part in ten thousand
     * of unity. With the pump open the vessel's own relaxation is faster, so the
     * step carries a slightly smaller share of the same power -- which is the
     * relaxation the two losses share and not the two terms interacting. The
     * tolerance below admits that share and nothing like the tens of kelvin a
     * difference-shaped steam term would put between the two temperatures.
     */
    const float seconds = (float)INTERVAL_MS / 1000.0f;
    const float expected =
        (STEAM_COST_J_PER_ML * STEAM_DRAW_ML_PER_S * seconds) / VESSEL_MASS_J_PER_K;

    TEST_ASSERT_FLOAT_WITHIN(1.0e-3f, expected, costs[0][0]);
    TEST_ASSERT_FLOAT_WITHIN(1.0e-4f, costs[0][0], costs[1][0]);
    TEST_ASSERT_FLOAT_WITHIN(1.0e-2f, costs[0][1], costs[1][1]);
    /* The premise: the wand did something. */
    TEST_ASSERT_TRUE(costs[0][0] > 0.4f);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C1: ...independent of any existing loss term --
/// at no demand nothing that was here before moves, the brew-flow loss included.
///
/// The existing drawn-water term is the one this slice was most able to break,
/// because the new term sits in the same balance and the two are one edit apart
/// in the source. A run under a full pump with the wand shut, checked against the
/// two-loss closed form the suite already holds that term to, is what says the
/// arithmetic that was here is untouched -- and the same run with the wand open
/// has to come apart from it, or the comparison is a coefficient nothing reads.
static void test_with_the_wand_shut_the_brew_flow_loss_is_what_it_was(void)
{
    plant_model_t shut;
    plant_model_t open;
    /* Ten seconds against a time constant of about thirty, so the relaxation
     * correction is doing real work rather than sitting at unity. */
    const uint32_t interval_ms = 10000u;
    const float start_c = 90.0f;
    const plant_actuation_t drawing_only = commanding(0u, ACTUATION_FULL_SCALE);

    initialise(&shut);
    initialise(&open);
    TEST_ASSERT_TRUE(
        plant_model_set_state(&shut, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, start_c));
    TEST_ASSERT_TRUE(
        plant_model_set_state(&open, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, start_c));

    TEST_ASSERT_TRUE(plant_model_step(&shut, &drawing_only, 0.0f, interval_ms));
    TEST_ASSERT_TRUE(plant_model_step(&open, &drawing_only, STEAM_DRAW_ML_PER_S, interval_ms));

    const float seconds = (float)interval_ms / 1000.0f;
    const float drawn_w_per_k = PUMP_FLOW_ML_PER_S * WATER_J_PER_ML_K;
    const float settling_w_per_k = VESSEL_LOSS_W_PER_K + drawn_w_per_k;
    const float settles_at =
        (VESSEL_LOSS_W_PER_K * AMBIENT_C + drawn_w_per_k * FEED_TEMPERATURE_C) / settling_w_per_k;
    const float time_constant_s = VESSEL_MASS_J_PER_K / settling_w_per_k;
    const float expected = settles_at + (start_c - settles_at) * expf(-seconds / time_constant_s);

    TEST_ASSERT_FLOAT_WITHIN(1e-2f, expected, vessel(&shut));

    /*
     * And with the wand open the same run lands lower, by the drawn power over
     * the same relaxation. Written out rather than merely asserted to be lower:
     * the two losses sum without interacting, so the steam term shifts where the
     * vessel is heading by exactly its power over the settling coefficient and
     * changes nothing about how fast it gets there.
     */
    const float steam_w = STEAM_COST_J_PER_ML * STEAM_DRAW_ML_PER_S;
    const float settles_lower = settles_at - steam_w / settling_w_per_k;
    const float expected_open =
        settles_lower + (start_c - settles_lower) * expf(-seconds / time_constant_s);
    TEST_ASSERT_FLOAT_WITHIN(1e-2f, expected_open, vessel(&open));
    TEST_ASSERT_TRUE(vessel(&open) < vessel(&shut) - 5.0f);
}

/// SOL-PLANT-STEAM-FEED-SENSIBLE-HEAT.C1: ...sensible heat against the feed,
/// which is a lift to saturation and never a fall from it.
///
/// The same guard the other structure carries, asked of this one, because the
/// two write the term separately and a clamp present in one and absent in the
/// other is exactly the kind of divergence a shared correction invites. This
/// description's feed and its saturation temperature are bounded independently,
/// so a feed arriving above the boil loads here as it does there; read literally
/// the sensible half would be negative and the wand would warm the vessel. The
/// two runs are compared byte for byte against a feed arriving exactly at
/// saturation, because a tolerance would admit a small negative term.
static void test_a_feed_arriving_past_boiling_costs_the_wand_nothing_extra(void)
{
    static const uint32_t INTERVAL_MS = 100u;
    const float start_c = 150.0f;
    plant_model_t arriving_at;
    plant_model_t arriving_past;
    const plant_actuation_t idle = commanding(0u, 0u);

    /*
     * The pair differs in the feed temperature alone, one of them arriving at
     * saturation and one above it. It is the saturation figure that is moved
     * down to meet the feed rather than the feed moved up past it, because the
     * feed's own admissible range stops well below the boil -- a description
     * feeding a machine water at a hundred and fifteen degrees is refused, and
     * the case this is about is reachable only from the other direction.
     */
    initialise_between(&arriving_at, 40.0f, 40.0f);
    initialise_between(&arriving_past, 55.0f, 40.0f);
    TEST_ASSERT_TRUE(plant_model_set_state(
        &arriving_at, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, start_c));
    TEST_ASSERT_TRUE(plant_model_set_state(
        &arriving_past, PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C, start_c));

    TEST_ASSERT_TRUE(plant_model_step(&arriving_at, &idle, STEAM_DRAW_ML_PER_S, INTERVAL_MS));
    TEST_ASSERT_TRUE(plant_model_step(&arriving_past, &idle, STEAM_DRAW_ML_PER_S, INTERVAL_MS));

    const float at_saturation = vessel(&arriving_at);
    const float past_saturation = vessel(&arriving_past);
    TEST_ASSERT_EQUAL_MEMORY(&at_saturation, &past_saturation, sizeof(float));
    /* And the wand still cost the vessel the latent heat, so the equality is two
     * charged steps rather than two absent terms. */
    TEST_ASSERT_TRUE(past_saturation < start_c - 0.1f);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C3: Steam pressure is driven by an integrated
/// state once a draw is open, rather than derived fresh from temperature every
/// step.
///
/// The distinction stated as arithmetic, on this architecture as on the other
/// one. At every step the gap between what the saturation relation gives for the
/// vessel the model has just advanced and what it reports for the pressure is
/// read off, and required to be the whole of what the draw has taken since it
/// opened. A pressure derived fresh from the vessel each step, with the draw's
/// cost applied to that fresh answer, leaves the gap at one step's worth for the
/// whole run.
static void test_the_steam_pressure_accumulates_the_draw_rather_than_recomputing_it(void)
{
    plant_model_t model;
    const plant_actuation_t heating_only = heating();

    initialise(&model);
    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &heating_only, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_pressure(&model) > 0.5f);

    const double seconds = (double)STEP_MS / 1000.0;
    const double per_step_bar =
        (double)STEAM_FALL_BAR_PER_ML * (double)STEAM_DRAW_ML_PER_S * seconds;
    TEST_ASSERT_TRUE(per_step_bar > 0.0);

    for (int step = 1; step <= 10; step++) {
        TEST_ASSERT_TRUE(
            plant_model_step(&model, &heating_only, STEAM_DRAW_ML_PER_S, STEP_MS));

        const double relation = (double)saturation_pressure(vessel(&model));
        const double reported = (double)steam_pressure(&model);
        const double gap = relation - reported;
        const double expected = per_step_bar * (double)step;

        if (!(fabs(gap - expected) < 1.0e-5)) {
            char message[240];
            (void)snprintf(message, sizeof(message),
                           "after %d steps of draw the path sits %.9g bar below the relation, and "
                           "the draw has taken %.9g",
                           step, gap, expected);
            TEST_FAIL_MESSAGE(message);
        }
        TEST_ASSERT_TRUE(reported > 0.0);
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C4: Steam pressure reverts to the affine relation
/// the instant demand returns to zero.
///
/// Held below the relation while the wand is open; the relation itself, byte for
/// byte, on the very next step with nothing drawn -- a tolerance would accept a
/// reversion that had merely started, which is a different claim; and a fresh
/// draw afterwards starting from nothing rather than from where the last one
/// stopped, which is what "no leftover offset" means and what a gap that decayed
/// towards the relation rather than being discarded would fail.
static void test_the_steam_pressure_is_the_relation_again_the_step_the_draw_stops(void)
{
    plant_model_t model;
    const plant_actuation_t heating_only = heating();

    initialise(&model);
    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &heating_only, 0.0f, STEP_MS));
    }
    for (int step = 0; step < 10; step++) {
        TEST_ASSERT_TRUE(
            plant_model_step(&model, &heating_only, STEAM_DRAW_ML_PER_S, STEP_MS));
    }

    const float under_draw = steam_pressure(&model);
    TEST_ASSERT_TRUE(under_draw < saturation_pressure(vessel(&model)) - 0.01f);

    TEST_ASSERT_TRUE(plant_model_step(&model, &heating_only, 0.0f, STEP_MS));
    const float reverted = steam_pressure(&model);
    const float relation = saturation_pressure(vessel(&model));
    TEST_ASSERT_EQUAL_MEMORY(&relation, &reverted, sizeof(float));

    TEST_ASSERT_TRUE(plant_model_step(&model, &heating_only, STEAM_DRAW_ML_PER_S, STEP_MS));
    const double seconds = (double)STEP_MS / 1000.0;
    const double one_step_bar =
        (double)STEAM_FALL_BAR_PER_ML * (double)STEAM_DRAW_ML_PER_S * seconds;
    const double gap =
        (double)saturation_pressure(vessel(&model)) - (double)steam_pressure(&model);
    TEST_ASSERT_TRUE(fabs(gap - one_step_bar) < 1.0e-5);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: The stepped structure stays admissible with a
/// draw open.
///
/// Every quantity stays a number and the steam path's gauge pressure stays at or
/// above nothing, under both draws at once and at a rate no machine of this
/// description could sustain. On this architecture that is a sharper question
/// than on the other one: the pump and the wand are pulling on the same vessel,
/// so a run like this takes it a long way below where anything settles, and the
/// pressure relation is asked for an answer well below saturation while the gap
/// is being driven the other way.
static void test_the_structure_stays_admissible_with_a_draw_open(void)
{
    plant_model_t model;
    const plant_actuation_t working = commanding(ACTUATION_FULL_SCALE, ACTUATION_FULL_SCALE);

    initialise(&model);
    for (int step = 0; step < BOIL_STEPS; step++) {
        float quantities[PLANT_QUANTITY_COUNT];

        TEST_ASSERT_TRUE(plant_model_step(&model, &working, 50.0f, STEP_MS));
        read_all(&model, quantities);

        for (int quantity = 0; quantity < PLANT_QUANTITY_COUNT; quantity++) {
            char message[200];
            (void)snprintf(message, sizeof(message),
                           "step %d: quantity %d left the finite range under a draw", step,
                           quantity);
            TEST_ASSERT_TRUE_MESSAGE(isfinite(quantities[quantity]), message);
        }
        TEST_ASSERT_TRUE(quantities[PLANT_QUANTITY_STEAM_PRESSURE_BAR] >= 0.0f);
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: ...with a draw open, including one the path
/// cannot supply.
///
/// The floor asserted where it is reached rather than only where it is not. A
/// draw asking for more pressure than the vessel has to give takes the path to
/// exactly nothing and leaves it there however long it is held; a gap that went
/// on accumulating past the pressure there was to lose would report a negative
/// gauge pressure, and one that stopped short would leave the path holding
/// pressure through a draw nothing could supply. The floor has to be the gap's
/// doing rather than the vessel having gone cold, so the relation is required to
/// still have pressure in it, and closing the wand has to hand the whole of that
/// back on the next step.
static void test_a_draw_the_path_cannot_supply_stops_at_nothing(void)
{
    /* A path that sags far harder per millilitre than this suite's own
     * description, because the floor is otherwise unreachable: at the ordinary
     * figure the vessel goes cold long before the path empties, and a floor
     * reached that way would establish nothing about the gap. */
    static const char STEEP[] = "ambient_temperature_c = 20.0\n"
                                "vessel.thermal_mass_j_per_k = 900.0\n"
                                "vessel.heater_power_w = 1400.0\n"
                                "vessel.loss_w_per_k = 2.0\n"
                                "pump.pressure_bar = 15.0\n"
                                "pump.flow_ml_per_s = 7.0\n"
                                "brew.pressure_time_constant_s = 0.8\n"
                                "water.feed_temperature_c = 18.0\n"
                                "water.heat_capacity_j_per_ml_k = 4.15\n"
                                "water.latent_heat_j_per_ml = 2200.0\n"
                                "steam.saturation_temperature_c = 100.0\n"
                                "steam.pressure_bar_per_k = 0.036\n"
                                "steam.pressure_fall_bar_per_ml = 10.0\n";

    plant_parameters_t steep;
    plant_parameter_error_t fault;
    plant_model_t model;
    const plant_actuation_t heating_only = heating();

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(STEEP, sizeof(STEEP) - 1u, &steep, &fault));
    TEST_ASSERT_EQUAL(PLANT_PARAMETER_OK, fault.fault);
    TEST_ASSERT_TRUE(plant_model_init(&model, &steep));

    for (int step = 0; step < BOIL_STEPS; step++) {
        TEST_ASSERT_TRUE(plant_model_step(&model, &heating_only, 0.0f, STEP_MS));
    }
    TEST_ASSERT_TRUE(steam_pressure(&model) > 0.5f);

    for (int step = 0; step < 20; step++) {
        TEST_ASSERT_TRUE(
            plant_model_step(&model, &heating_only, STEAM_DRAW_ML_PER_S, STEP_MS));
        TEST_ASSERT_EQUAL_FLOAT(0.0f, steam_pressure(&model));
    }

    TEST_ASSERT_TRUE(saturation_pressure(vessel(&model)) > 0.0f);

    TEST_ASSERT_TRUE(plant_model_step(&model, &heating_only, 0.0f, STEP_MS));
    const float reverted = steam_pressure(&model);
    const float relation = saturation_pressure(vessel(&model));
    TEST_ASSERT_EQUAL_MEMORY(&relation, &reverted, sizeof(float));
    TEST_ASSERT_TRUE(reverted > 0.0f);
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: ...with a draw open -- including a demand
/// that is not one.
///
/// The seam accepts the demand as a plain step argument and refuses nothing
/// about it. What this structure does with a figure that is not a draw is its own
/// business, and it reads it as no draw: steam arriving rather than leaving is
/// not a case a machine of this architecture has either, and a figure that is not
/// a finite rate would make every quantity downstream stop being one -- which no
/// comparison in this suite could see, since a comparison against one of those is
/// false either way. Both an undefined rate and an unbounded one are offered,
/// because they fail differently: the first poisons the arithmetic at once, the
/// second takes the vessel to an infinity it never comes back from.
static void test_a_demand_that_is_not_a_draw_is_read_as_no_draw(void)
{
    static const float NOT_A_DRAW[] = {-1.0f, -500.0f, NAN, INFINITY, -INFINITY};

    for (size_t i = 0u; i < sizeof(NOT_A_DRAW) / sizeof(NOT_A_DRAW[0]); i++) {
        plant_model_t offered;
        plant_model_t shut;
        float from_offered[PLANT_QUANTITY_COUNT];
        float from_shut[PLANT_QUANTITY_COUNT];
        const plant_actuation_t heating_only = heating();

        initialise(&offered);
        initialise(&shut);
        for (int step = 0; step < SETTLE_STEPS; step++) {
            TEST_ASSERT_TRUE(
                plant_model_step(&offered, &heating_only, NOT_A_DRAW[i], STEP_MS));
            TEST_ASSERT_TRUE(plant_model_step(&shut, &heating_only, 0.0f, STEP_MS));
        }

        read_all(&offered, from_offered);
        read_all(&shut, from_shut);
        TEST_ASSERT_EQUAL_MEMORY(from_shut, from_offered, sizeof(from_shut));
    }
}

/// SOL-PLANT-STEAM-DRAW-ENERGY.C2: The latent-heat coefficient is a described
/// coefficient...
/// SOL-PLANT-STEAM-DRAW-ENERGY.C7: The pressure-divergence-rate coefficient is a
/// described coefficient...
/// SOL-PLANT-STEAM-DRAW-ENERGY.C5: The stepped structure stays admissible with a
/// draw open -- this architecture declares its own range for each new
/// coefficient and enforces it at load.
///
/// Neither coefficient is inherited from the other structure: a structure reads
/// its own parameter table, so the ranges are declared here as well and a
/// description offering a value outside one is refused rather than run. What a
/// millilitre costs to boil has a floor above zero, because a millilitre that
/// cost nothing to vaporise is not water and would make a steam draw free again.
/// What a draw costs the path in pressure may be nothing -- a vessel that sags
/// not at all is odd rather than inadmissible -- and may not be less.
static void test_this_structure_declares_and_enforces_the_steam_draws_ranges(void)
{
    static const struct {
        const char *line;
        bool admissible;
    } OFFERED[] = {
        {"water.latent_heat_j_per_ml = 0.0\n", false},
        {"water.latent_heat_j_per_ml = -2200.0\n", false},
        {"water.latent_heat_j_per_ml = 1.0e9\n", false},
        {"water.latent_heat_j_per_ml = 2200.0\n", true},
        {"steam.pressure_fall_bar_per_ml = -0.03\n", false},
        {"steam.pressure_fall_bar_per_ml = 1.0e9\n", false},
        {"steam.pressure_fall_bar_per_ml = 0.0\n", true},
        {"steam.pressure_fall_bar_per_ml = 0.03\n", true},
    };

    for (size_t i = 0u; i < sizeof(OFFERED) / sizeof(OFFERED[0]); i++) {
        char text[sizeof(DESCRIPTION) + 64];
        plant_parameters_t loaded;
        plant_parameter_error_t fault;
        char message[200];

        /*
         * The suite's own description with one line appended, which the loader
         * refuses as a repeated name unless the original is dropped -- so the
         * original is dropped by rebuilding the text without it.
         */
        const char *const name_end = strchr(OFFERED[i].line, ' ');
        TEST_ASSERT_NOT_NULL(name_end);
        const size_t name_length = (size_t)(name_end - OFFERED[i].line);
        char name[64];
        TEST_ASSERT_TRUE(name_length < sizeof(name));
        memcpy(name, OFFERED[i].line, name_length);
        name[name_length] = '\0';

        size_t used = 0u;
        const char *cursor = DESCRIPTION;
        while (*cursor != '\0') {
            const char *const line_end = strchr(cursor, '\n');
            const size_t line_length = (size_t)(line_end - cursor) + 1u;

            if (strncmp(cursor, OFFERED[i].line, name_length) != 0) {
                memcpy(text + used, cursor, line_length);
                used += line_length;
            }
            cursor = line_end + 1;
        }
        const size_t replacement = strlen(OFFERED[i].line);
        memcpy(text + used, OFFERED[i].line, replacement);
        used += replacement;
        TEST_ASSERT_TRUE(used < sizeof(text));

        memset(&fault, 0, sizeof(fault));
        const bool accepted = plant_parameters_load(text, used, &loaded, &fault);
        (void)snprintf(message, sizeof(message), "offering '%.*s'",
                       (int)(replacement - 1u), OFFERED[i].line);
        if (OFFERED[i].admissible) {
            TEST_ASSERT_TRUE_MESSAGE(accepted, message);
        } else {
            TEST_ASSERT_FALSE_MESSAGE(accepted, message);
            TEST_ASSERT_EQUAL_MESSAGE(PLANT_PARAMETER_OUT_OF_RANGE, fault.fault, message);
            /* And the refusal names the coefficient that was out of range rather
             * than a neighbour of it. */
            TEST_ASSERT_EQUAL_STRING_MESSAGE(name, fault.parameter, message);
        }
    }
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C2: Every plant structure answers the
/// steam-draw quantity.
///
/// The single-vessel structure answers it, from rest as well as with a draw
/// open. This is the structure that refuses a state -- the water on its way to
/// the group, which it does not model -- so it is where the difference between
/// the two vocabularies shows: a state may be declined and a quantity may not.
/// A structure treating the draw rate the way it treats that state would be
/// refusing something the seam promises every consumer can read, on the one
/// architecture where refusing anything is already routine.
static void test_the_single_vessel_structure_answers_the_steam_draw_rate(void)
{
    plant_model_t model;
    plant_actuation_t at_rest = {{0u}};
    float drawn = -1.0f;
    float refused_state = 0.0f;

    initialise(&model);
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));
    TEST_ASSERT_EQUAL_FLOAT(0.0f, drawn);

    /* The state it declines, for contrast: the refusal is a property of the
     * state vocabulary and reaches no quantity. */
    TEST_ASSERT_FALSE(
        plant_model_state(&model, PLANT_STATE_BREW_OUTLET_TEMPERATURE_C, &refused_state));

    TEST_ASSERT_TRUE(plant_model_step(&model, &at_rest, 2.0f, STEP_MS));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));
    TEST_ASSERT_TRUE(drawn > 0.0f);
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C1: ...and plant_model_quantity returns the
/// value the step's own input carried, for whichever structure the build
/// selected.
///
/// Held on this structure as well as on the reference one, and compared at a
/// delta of nothing -- TEST_ASSERT_EQUAL_FLOAT admits a relative tolerance, and
/// a structure scaling the demand by a part in a million would pass it, which
/// is exactly the derivation this quantity is not entitled to make.
/// Two structures answering the same demand with the same figure is what makes
/// the quantity the machine's rather than a structure's; one that scaled it, or
/// that reported the vessel's own store in its place, would hand a consumer a
/// number whose meaning depended on which build it was talking to -- and this
/// structure is the one where that is easiest to get wrong, since a single
/// vessel serves both paths and both rates pass through it.
static void test_the_reported_steam_draw_rate_is_the_demand_the_step_was_given(void)
{
    static const float DEMANDS[] = {0.0f, 0.05f, 0.5f, 2.0f, 7.5f, 0.0f};
    plant_model_t model;
    plant_actuation_t at_rest = {{0u}};

    initialise(&model);
    for (size_t i = 0u; i < sizeof(DEMANDS) / sizeof(DEMANDS[0]); i++) {
        float drawn = -1.0f;
        char message[96];

        TEST_ASSERT_TRUE(plant_model_step(&model, &at_rest, DEMANDS[i], STEP_MS));
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));

        (void)snprintf(message, sizeof(message), "a demand of %f was reported as %f",
                       (double)DEMANDS[i], (double)drawn);
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.0f, DEMANDS[i], drawn, message);
    }
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C1: ...the value the step's own input carries,
/// as this structure's own admissibility guard leaves it.
///
/// The same refusal the reference structure makes, made here for the same reason
/// and checked separately because each structure carries its own guard: a rate
/// below zero, and any rate that is not finite, is no draw in the relations, so
/// it cannot be a draw in the quantity read back from them. Reported alongside the vessel
/// temperature, which sits at ambient with nothing heating it and would have
/// moved had the demand been acted on.
static void test_an_inadmissible_steam_demand_is_reported_as_no_draw(void)
{
    static const float REFUSED[] = {-1.0f, -0.0001f, NAN, INFINITY, -INFINITY};

    for (size_t i = 0u; i < sizeof(REFUSED) / sizeof(REFUSED[0]); i++) {
        plant_model_t model;
        plant_actuation_t at_rest = {{0u}};
        float drawn = -1.0f;
        float vessel_before = 0.0f;
        float vessel_after = 0.0f;
        char message[96];

        initialise(&model);
        TEST_ASSERT_TRUE(
            plant_model_quantity(&model, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &vessel_before));

        TEST_ASSERT_TRUE(plant_model_step(&model, &at_rest, REFUSED[i], STEP_MS));
        TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn));

        (void)snprintf(message, sizeof(message), "a demand of %f was reported rather than refused",
                       (double)REFUSED[i]);
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.0f, 0.0f, drawn, message);

        TEST_ASSERT_TRUE(
            plant_model_quantity(&model, PLANT_QUANTITY_STEAM_TEMPERATURE_C, &vessel_after));
        TEST_ASSERT_FLOAT_WITHIN_MESSAGE(0.0f, vessel_before, vessel_after, message);
    }
}

/// SOL-PLANT-STEAM-DRAW-REPORTED.C4: The reported steam-draw quantity is
/// exercised end to end on the host tier, on both structures that describe a
/// machine.
///
/// The whole path a consumer takes, taken against this architecture's own
/// description: loaded as text, initialised from it, a draw commanded through
/// the step and the rate read back through the seam. The pump is commanded on
/// the same step and its rate read beside the draw, so a structure answering one
/// rate from the other's store fails here -- the case that passes each
/// quantity's own test and is visible only when both are non-zero and different.
static void test_the_steam_draw_rate_is_reached_end_to_end_through_the_seam(void)
{
    plant_parameters_t loaded;
    plant_parameter_error_t fault;
    plant_model_t model;
    plant_actuation_t pumping = {{0u}};
    float drawn_steam = -1.0f;
    float drawn_water = -1.0f;

    memset(&fault, 0, sizeof(fault));
    TEST_ASSERT_TRUE(plant_parameters_load(DESCRIPTION, sizeof(DESCRIPTION) - 1u, &loaded, &fault));
    TEST_ASSERT_TRUE(plant_model_init(&model, &loaded));

    pumping.level_permille[ACTUATION_CHANNEL_PUMP] = ACTUATION_FULL_SCALE / 2u;
    TEST_ASSERT_TRUE(plant_model_step(&model, &pumping, 1.25f, STEP_MS));

    TEST_ASSERT_TRUE(
        plant_model_quantity(&model, PLANT_QUANTITY_STEAM_DRAW_ML_PER_S, &drawn_steam));
    TEST_ASSERT_TRUE(plant_model_quantity(&model, PLANT_QUANTITY_BREW_FLOW_ML_PER_S, &drawn_water));

    /* The demand as it was commanded, and this description's own seven at half
     * scale. Both are exact in binary, so both are compared at a delta of
     * nothing rather than through the relative tolerance TEST_ASSERT_EQUAL_FLOAT
     * applies. */
    TEST_ASSERT_FLOAT_WITHIN(0.0f, 1.25f, drawn_steam);
    TEST_ASSERT_FLOAT_WITHIN(0.0f, 3.5f, drawn_water);
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C1: this architecture declares no delivery
/// point, since nothing establishes how its one vessel's outlet is routed and
/// stating one would be asserting an arrangement nothing requires of it.
static void test_the_single_vessel_structure_declares_no_delivery_point(void)
{
    TEST_ASSERT_EQUAL_UINT32(0u, (uint32_t)plant_structure_delivery_points());
}

/// SOL-DELIVERY-TOPOLOGY-DECLARED.C2: with no delivery point declared, the
/// mass accessor refuses both the group and the spout rather than answering a
/// mass for a point this architecture never claimed.
static void test_the_single_vessel_structure_refuses_both_delivery_point_masses(void)
{
    plant_heated_mass_id_t mass = 0xFFu;

    TEST_ASSERT_FALSE(plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_GROUP, &mass));
    TEST_ASSERT_EQUAL_UINT8(0xFFu, mass);
    TEST_ASSERT_FALSE(
        plant_structure_delivery_point_mass(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT, &mass));
    TEST_ASSERT_EQUAL_UINT8(0xFFu, mass);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_the_single_vessel_structure_answers_the_drawn_rate);
    RUN_TEST(test_the_single_vessel_structure_answers_the_steam_draw_rate);
    RUN_TEST(test_the_reported_steam_draw_rate_is_the_demand_the_step_was_given);
    RUN_TEST(test_an_inadmissible_steam_demand_is_reported_as_no_draw);
    RUN_TEST(test_the_steam_draw_rate_is_reached_end_to_end_through_the_seam);
    RUN_TEST(test_the_drawn_rate_follows_the_commanded_pump_level);
    RUN_TEST(test_an_instance_runs_a_whole_sequence_through_the_seam);
    RUN_TEST(test_the_declared_channels_are_the_ones_this_architecture_has);
    RUN_TEST(test_the_steam_feed_channel_is_refused_here_too);
    RUN_TEST(test_a_steam_demand_alone_is_accepted);
    RUN_TEST(test_the_pump_drives_the_brew_pressure_and_leaves_the_vessel_alone);
    RUN_TEST(test_a_step_with_nothing_applied_moves_nothing);
    RUN_TEST(test_heat_raises_the_temperatures_and_lowers_no_quantity);
    RUN_TEST(test_the_same_sequence_twice_reproduces_the_same_trajectory);
    RUN_TEST(test_both_temperature_quantities_follow_the_one_vessel);
    RUN_TEST(test_this_structure_refuses_the_state_it_does_not_keep);
    RUN_TEST(test_every_state_this_structure_keeps_carries_what_it_names);
    RUN_TEST(test_a_state_read_from_an_uninitialised_instance_is_refused_here_too);
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
    RUN_TEST(test_this_structure_answers_the_writes_it_answers_the_reads_for);
    RUN_TEST(test_writing_either_temperature_moves_the_one_vessel);
    RUN_TEST(test_a_draw_cools_the_vessel_faster_than_no_draw);
    RUN_TEST(test_the_vessel_settles_where_the_drawn_energy_balance_puts_it);
    RUN_TEST(test_the_drawn_loss_is_taken_between_the_vessel_and_the_feed);
    RUN_TEST(test_a_long_step_under_a_draw_is_corrected_for_both_losses);
    RUN_TEST(test_the_vessel_pays_the_heat_of_what_is_drawn_off_it);
    RUN_TEST(test_what_the_wand_costs_is_the_same_wherever_the_vessel_sits);
    RUN_TEST(test_a_feed_arriving_past_boiling_costs_the_wand_nothing_extra);
    RUN_TEST(test_with_the_wand_shut_the_brew_flow_loss_is_what_it_was);
    RUN_TEST(test_the_steam_pressure_accumulates_the_draw_rather_than_recomputing_it);
    RUN_TEST(test_the_steam_pressure_is_the_relation_again_the_step_the_draw_stops);
    RUN_TEST(test_the_structure_stays_admissible_with_a_draw_open);
    RUN_TEST(test_a_draw_the_path_cannot_supply_stops_at_nothing);
    RUN_TEST(test_a_demand_that_is_not_a_draw_is_read_as_no_draw);
    RUN_TEST(test_this_structure_declares_and_enforces_the_steam_draws_ranges);
    RUN_TEST(test_the_estimator_refuses_this_architecture);
    RUN_TEST(test_the_single_vessel_structure_declares_no_delivery_point);
    RUN_TEST(test_the_single_vessel_structure_refuses_both_delivery_point_masses);
    return UNITY_END();
}
