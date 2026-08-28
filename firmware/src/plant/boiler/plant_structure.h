/*
 * The single-boiler structure: state, parameters, and the operations that
 * advance them.
 *
 * This is a different architecture from the one the project's own machine is
 * built on, not the same equations with different numbers. One heated vessel
 * serves both the brew path and the steam path, where the reference machine
 * has two masses heated independently. Everything else follows from that: both
 * temperature quantities are answered from the one vessel state, steam
 * pressure follows that same state above saturation, and there is no second
 * heater to command -- so this structure answers fewer of the machine's
 * actuation channels than the vocabulary carries.
 *
 * It exists to establish that the seam admits an architecture rather than a
 * parameter set. A structure of the same architecture with different numbers
 * would exercise the parameter path, which is already covered and is the
 * weaker claim; only a structure whose equations differ tests whether the seam
 * is drawn in the right place. Its equations are accordingly the thinnest set
 * that expresses the architecture, and no more.
 *
 * A consumer of the plant model never includes this header -- it sees only
 * plant_model.h, which reaches these types by including whichever
 * plant_structure.h the build put on the include path. Naming the fields and
 * functions below is exactly this structure's job, and the plant encapsulation
 * check exempts src/plant for that reason while failing the build for anything
 * outside it that names them.
 */
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H

#include "plant_machine_claim.h"
#include "plant_support.h"
#include "plant_types.h"

/*
 * These equations are an account of a real architecture -- single-boiler
 * machines exist in quantity, whether or not anyone here owns one -- so altering
 * their arithmetic changes what the model says such a machine does, and whether
 * a test notices is a question worth asking. Nothing about this claim is
 * weakened by the structure being unverified: describing an architecture and
 * having been checked against one are separate, and the support status below is
 * where the second is answered.
 */
#define PLANT_STRUCTURE_MACHINE_CLAIM PLANT_DESCRIBES_A_MACHINE

/*
 * Unverified, and nobody here can change that. These equations describe an
 * architecture no one on this project owns a machine of, so there is no bench
 * this structure could be taken to -- which makes unverified the correct final
 * state of the claim rather than a gap somebody is expected to close. An
 * adopter who has such a machine is the first person able to say otherwise, and
 * says it by citing what was run.
 */
#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED

/*
 * The brew heater and the pump, and not the steam heater. One vessel serves
 * both paths here, so the machine's second heating channel has nothing behind
 * it on a machine of this architecture -- and a channel with nothing behind it
 * is one this structure states it does not answer rather than one it silently
 * absorbs. The seam refuses a non-zero command on it and names it; that
 * contract is the seam's and predates this structure.
 *
 * The brew heater is the channel the single vessel is driven by. That is a
 * choice about which name the one heating channel takes, and it is the brew
 * channel because a machine of this architecture is a brewing machine that can
 * also make steam, not the other way round.
 */
#define PLANT_STRUCTURE_ACTUATION_CHANNELS                                        \
    (ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER) |                       \
     ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_PUMP))

/*
 * No delivery point is declared for this architecture: nothing establishes how
 * this vessel's outlet is routed, and stating a point here would be asserting
 * an arrangement nothing requires of it.
 */
#define PLANT_STRUCTURE_DELIVERY_POINTS ((plant_delivery_point_set_t)0u)

/*
 * Every coefficient this structure uses. There is no number in the equations
 * that is not read from here, apart from unit conversions and the constants of
 * the integration itself, which are properties of the equations rather than of
 * a machine.
 *
 * There is one thermal mass and one heater, not two of each. That is the
 * architecture stated in the coefficients: a description of a machine of this
 * kind has nowhere to put a second heater's rating, which is what makes the two
 * architectures different rather than differently parameterised.
 */
typedef struct {
    float ambient_temperature_c;

    float vessel_thermal_mass_j_per_k;
    float vessel_heater_power_w;
    float vessel_loss_w_per_k;

    float pump_pressure_bar;
    float pump_flow_ml_per_s;
    float brew_pressure_time_constant_s;

    /*
     * Properties of the water rather than of this machine, which is why they sit
     * apart from the coefficients above. They are the same three names the other
     * architecture's description carries, because what a millilitre of water
     * costs to warm, what it costs to turn into vapour, and what temperature it
     * arrives at do not depend on how the machine around it is built.
     */
    float water_feed_temperature_c;
    float water_heat_capacity_j_per_ml_k;
    float water_latent_heat_j_per_ml;

    float steam_saturation_temperature_c;
    float steam_pressure_bar_per_k;
    /*
     * How far a draw carries the steam path's pressure below what the vessel's
     * temperature alone would give it, per millilitre drawn. A property of the
     * path and not of water, so unlike the three above it is this machine's own
     * figure -- what a draw costs in pressure depends on what there is to draw
     * from, and a vessel is not a thermoblock.
     */
    float steam_pressure_fall_bar_per_ml;
} plant_parameters_t;

/*
 * One model instance: the states this structure integrates, and the record it
 * was initialised from. There is one temperature, because there is one vessel;
 * both temperature quantities are answered from it. Steam pressure follows the
 * vessel whenever nothing is being drawn, and is carried below it while
 * something is -- the gap beside it is what carries that, so a step with no draw
 * reproduces the vessel's own relation exactly rather than approaching it.
 */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;

    float vessel_temperature_c;
    float brew_pressure_bar;
    float steam_pressure_bar;

    /*
     * How far below the saturation relation a draw has carried the steam path,
     * in bar. Kept as the gap rather than as the pressure itself, so that closing
     * the wand restores the relation exactly: the gap goes to nothing and what is
     * left is the relation's answer with no residue of the draw in it.
     *
     * It never exceeds the pressure there was to lose, so the pressure it
     * produces is never negative. This architecture reaches that floor sooner
     * than a two-block machine would for a given draw and would be the one to
     * show it if it were unguarded, since the one vessel serving both paths is
     * also the one the brew draw is cooling.
     */
    float steam_pressure_deficit_bar;

    /*
     * The rate water was drawn at over the step just taken, held so the seam
     * can answer it without being handed the actuation again. It is not a
     * state: nothing integrates it and nothing carries over between steps -- it
     * is recomputed whole from the commanded pump level every step, which is
     * why no state vocabulary names it.
     */
    float brew_flow_ml_per_s;

    /*
     * The rate steam was drawn at over the step just taken, held so the seam can
     * answer it without being handed the demand again, and no more a state than
     * the rate above: each step replaces it whole with the demand that step was
     * given.
     *
     * It is that demand as this structure's admissibility guard leaves it rather
     * than the argument as it arrived, so what a consumer reads is the rate the
     * step's own relations acted on. A rate below zero, and any rate that is not
     * finite -- a number that is not one, and an unbounded one alike -- is no draw
     * here exactly as it is no draw in the vessel and pressure relations; handing the argument back untouched would return a value those
     * relations refused to a consumer that has no way to tell it apart from one
     * they used.
     */
    float steam_draw_ml_per_s;
} plant_model_t;

/*
 * The coefficients this structure requires and the range it declares each one
 * admissible over. `count` receives the number of entries; the returned table
 * outlives any call.
 */
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);

/*
 * The coefficients the supply this machine is fed from drives, by the names the
 * description calls them by. `count` receives the number of entries; the
 * returned table outlives any call.
 *
 * It is the one relationship between two of this structure's coefficients that
 * is stated anywhere, and it is stated here because a description's own grammar
 * has nowhere to put one: every line there accounts for a single number, and a
 * pair that moves together is a fact about two of them.
 */
const char *const *plant_structure_supply_driven_parameters(size_t *count);

/*
 * Advance the vessel over `seconds` under the given actuation and the rate steam
 * is being drawn. The vessel takes in what its one heater delivers at the
 * commanded duty, gives up what its loss coefficient carries to ambient, gives
 * up what the water drawn out of it carries away above the temperature the water
 * arrived at, and gives up what the feed replacing the steam drawn off it costs to
 * carry to saturation and then boil.
 * There is one state to write the third loss at, because on a machine of this
 * architecture the water leaving is the water in the vessel.
 *
 * The last two are separate subtractions and do not meet. One is water leaving
 * as liquid at the vessel's temperature, so it is a difference against the feed
 * and grows as the vessel climbs; the other is water leaving as vapour, so it is
 * a power the rate alone fixes and the vessel's temperature does not enter it.
 * Folding them together would assert that one draw changes what the other costs,
 * which is contention this architecture's equations do not represent.
 */
void boiler_advance_vessel(plant_model_t *model, const plant_actuation_t *actuation,
                           float steam_demand_ml_per_s, float seconds);

/*
 * Advance both pressures over `seconds` under the given actuation and the rate
 * steam is being drawn. Brew pressure relaxes towards what the pump commands
 * with the structure's time constant.
 *
 * Steam pressure follows the vessel above saturation and is zero below it
 * whenever nothing is being drawn. While something is, it is carried below that
 * relation at a rate the demand sets, and never below nothing at all; the
 * departure is discarded rather than unwound the moment the draw stops, so the
 * relation is exact again on the first step with no demand.
 */
void boiler_advance_pressures(plant_model_t *model, const plant_actuation_t *actuation,
                              float steam_demand_ml_per_s, float seconds);

#endif /* PLANT_STRUCTURE_H */
