/*
 * The thermoblock structure: state, parameters, and the operations that
 * advance them.
 *
 * A consumer of the plant model never includes this header -- it sees only
 * plant_model.h, which reaches these types by including whichever
 * plant_structure.h the build put on the include path. Naming the fields and
 * functions below is exactly this structure's job, and the plant encapsulation
 * check exempts src/plant for that reason while failing the build for anything
 * outside it that names them.
 *
 * The equations are the thinnest set that expresses this architecture: two
 * independently heated thermal masses, each losing to ambient; the coffee block
 * additionally losing whatever the water drawn through it carries away, because
 * a flow-through casting heats the stream out of its own store; the water on its
 * way to the group following that casting's temperature through a lag whose
 * length is set by how fast the water is being displaced, because a low-mass
 * flow-through system puts real dynamics between the metal and the stream; the
 * steam block additionally losing what the feed replacing whatever steam is
 * drawn off it costs to bring to the boil and then boil, because vapour leaving
 * carries away far more than its temperature suggests and the water standing in
 * its place arrives cold; that draw bounded by the rate the steam side's own
 * feed pump is commanded to supply it at, because a block holding no reservoir
 * makes steam no faster than it is given water to make it from; brew pressure
 * driven by the pump; and steam pressure following the steam mass above
 * saturation except while a draw carries it below that relation. Whether
 * they describe any real machine cannot be settled until
 * there is one to measure against; what they establish here is that the numbers
 * and the equations are separable and replaceable.
 */
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H

#include "plant_machine_claim.h"
#include "plant_support.h"
#include "plant_types.h"

/*
 * These equations are an account of a real architecture -- the one the project's
 * own machine is built on -- so altering their arithmetic changes what the model
 * says a machine does, and whether a test notices is a question worth asking.
 * That is a claim about what the equations are about, and not a claim that they
 * are right about it; the support status below is where that is answered.
 */
#define PLANT_STRUCTURE_MACHINE_CLAIM PLANT_DESCRIBES_A_MACHINE

/*
 * Nothing has been on the bench. These equations describe the architecture the
 * project's own machine is built on, which is a claim about what they are for
 * and not a claim that they have been checked against it -- no instrumented run
 * against that machine, or any other of the architecture, has happened.
 * Whoever makes one is the first.
 */
#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED

/*
 * Every channel the machine has. This architecture heats two masses
 * independently and drives a pump, so there is no channel of the vocabulary it
 * leaves unanswered -- which is a property of this architecture rather than of
 * structures in general, and is why the refusal of an unanswered channel cannot
 * be demonstrated against this one.
 */
#define PLANT_STRUCTURE_ACTUATION_CHANNELS                                        \
    (ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER) |                       \
     ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_STEAM_HEATER) |                      \
     ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_PUMP) |                              \
     ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_STEAM_PUMP))

/*
 * Both the group and the hot water spout, because the reference machine's own
 * arrangement is one coffee casting whose outlet a diverter routes to either.
 * Both points are declared here rather than assumed by a consumer.
 */
#define PLANT_STRUCTURE_DELIVERY_POINTS                                          \
    (PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_GROUP) |                      \
     PLANT_DELIVERY_POINT_BIT(PLANT_DELIVERY_POINT_HOT_WATER_SPOUT))

/*
 * Every coefficient this structure uses. There is no number in the equations
 * that is not read from here, apart from unit conversions and the constants of
 * the integration itself, which are properties of the equations rather than of
 * a machine.
 */
typedef struct {
    float ambient_temperature_c;

    float brew_thermal_mass_j_per_k;
    float brew_heater_power_w;
    float brew_loss_w_per_k;
    float brew_outlet_held_volume_ml;
    float brew_outlet_conduction_time_constant_s;

    float steam_thermal_mass_j_per_k;
    float steam_heater_power_w;
    float steam_loss_w_per_k;

    float pump_pressure_bar;
    float pump_flow_ml_per_s;
    float brew_pressure_time_constant_s;

    /*
     * Properties of the water rather than of the machine, which is why they sit
     * apart from the coefficients above rather than under a path's name. What a
     * millilitre of water costs to raise by a kelvin belongs to water, and the
     * temperature it arrives at belongs to whatever feeds the machine -- a tank
     * standing in the room on this one, and a cold main on the next one.
     *
     * The third is water's too, and is the one the steam side spends. Turning a
     * millilitre of water into vapour costs its enthalpy of vaporisation whether
     * or not the vapour then goes anywhere, and that cost is not a temperature
     * difference: steam leaves as vapour, so there is no outlet temperature to
     * write the loss through the way the coffee side writes its own.
     */
    float water_feed_temperature_c;
    float water_heat_capacity_j_per_ml_k;
    float water_latent_heat_j_per_ml;

    float steam_saturation_temperature_c;
    float steam_pressure_bar_per_k;
    /*
     * How far the steam path's pressure is driven below what its temperature
     * alone would give it, per millilitre drawn out of it. A property of the
     * path rather than of water: what a draw costs in pressure depends on what
     * there is to draw from and how freely it vents, which is the machine's
     * plumbing and not the steam tables.
     */
    float steam_pressure_fall_bar_per_ml;
    /*
     * The rate this side's own feed pump pushes replacement water in at, at full
     * duty. It sits with the steam path's figures rather than beside the brew
     * pump's because what it bounds is how fast this block can make steam, and
     * that is a property of the path it feeds as much as of the pump itself: a
     * block holding no reservoir makes vapour out of what has just been pushed
     * into it and out of nothing else.
     */
    float steam_feed_flow_ml_per_s;
} plant_parameters_t;

/*
 * One model instance: the states this structure integrates, and the record it
 * was initialised from.
 *
 * The coffee side carries two temperatures rather than one. `brew_temperature_c`
 * is the casting the heater acts on, which is where this machine's brew sensor
 * is and so is the one it reports; `brew_outlet_temperature_c` is the water on
 * its way to the group, which is what an extraction is judged by and what
 * nothing on the machine reads. On this architecture the second follows the
 * first rather than being it, and keeping only one would say the metal and the
 * stream are at the same temperature -- the assumption a flow-through machine is
 * least entitled to make.
 *
 * The outlet is the state worth reconstructing precisely because no quantity
 * carries it. It is no longer a state nothing here could be identified from: the
 * energy the drawn water removes from the casting is written at this
 * temperature, so with a draw open the casting the machine does read moves
 * differently depending on where the water leaving it sits. That is reachability
 * and not identification -- see the omissions in params/thermoblock.md.
 *
 * Steam pressure follows the steam mass whenever nothing is being drawn, and
 * departs from it while something is. What carries that departure is the
 * deficit beside it rather than the pressure itself: the pressure is the
 * saturation relation's answer less the deficit, so a step taken with no draw
 * reproduces that relation exactly rather than approaching it.
 */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;

    float brew_temperature_c;
    float brew_outlet_temperature_c;
    float steam_temperature_c;
    float brew_pressure_bar;
    float steam_pressure_bar;

    /*
     * How far below the saturation relation a draw has carried the steam path,
     * in bar. This is the state the divergence is kept in, and it is kept as the
     * gap rather than as the pressure so that closing the wand restores the
     * relation exactly: the gap is set to nothing, and what is left is the
     * relation's own answer with no residue of the draw in it. A pressure
     * integrated in its own right would have had to find its way back, and
     * whatever rate it came back at would have been a second claim about the
     * machine that nothing here is in a position to make.
     *
     * It is never larger than the pressure there was to lose, so the pressure it
     * produces is never negative -- a steam path venting to the room stops at the
     * room, and a gauge pressure below zero would be the model claiming a vacuum
     * the wand cannot draw.
     */
    float steam_pressure_deficit_bar;

    /*
     * The rate water was drawn at over the step just taken. It is held here so
     * that reading it costs no arithmetic and so that the seam can answer it
     * without being handed the actuation again -- not because it is a state.
     * Nothing integrates it and nothing carries over from one step to the next:
     * it is a function of the commanded pump level alone, recomputed whole
     * every step, which is why it appears in no state vocabulary and why a
     * consumer reaches it through plant_model_quantity rather than
     * plant_model_state.
     */
    float brew_flow_ml_per_s;

    /*
     * The rate steam was drawn at over the step just taken, held here for the
     * reasons the rate above is and refused a place in the state vocabulary for
     * the same ones: nothing integrates it, and each step replaces it whole with
     * the demand that step was handed.
     *
     * It is that demand as this structure's admissibility guard leaves it, and
     * not the argument as it arrived. A rate below zero, and any rate that is not
     * finite -- a number that is not one, and an unbounded one alike -- is
     * answered here exactly as it is answered in the relations: as no draw. Handing the argument back untouched would put a value the equations
     * themselves refused into the quantity vocabulary, and an unbounded or
     * undefined one makes every comparison against it false whichever way it is
     * written -- so a consumer inspecting the model afterwards could not see
     * that anything had happened. The guard is where that is answered, which
     * makes the guarded rate the only one this quantity can honestly carry.
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
 * Advance both thermal masses over `seconds` under the given actuation and the
 * rate steam is being drawn, and the water on its way to the group with them.
 * Each mass takes in what its heater delivers at the commanded duty and gives up
 * what its loss coefficient carries to ambient; the coffee block gives up, on
 * top of that, what the water drawn through it carries out, and the water
 * relaxes towards the casting it has just passed through over a residence time
 * that shortens as the draw grows.
 *
 * The steam mass gives up, on top of its own loss to ambient, what the feed
 * replacing the steam leaving it costs to carry to saturation and then boil --
 * and it gives it up for the lower of the rate asked for and the rate this side's
 * own feed pump is commanded to supply, because a block holding no reservoir
 * makes steam out of what has just been pushed into it and out of nothing else.
 * That term is independent of the loss beside it: it is a power set by the rate
 * alone and does not depend on where the mass has got to, so it neither replaces
 * the ambient loss nor changes how fast the mass settles towards it. At no draw,
 * and at no feed, it is exactly zero.
 *
 * The casting and the water are advanced as one pair rather than one after the
 * other: each now appears in the other's equation, so neither has a closed form
 * of its own to be exact against. The steam mass keeps its own single-mass step,
 * because nothing on that side is coupled to a second state.
 */
void thermoblock_advance_temperatures(plant_model_t *model,
                                      const plant_actuation_t *actuation,
                                      float steam_demand_ml_per_s, float seconds);

/*
 * Advance both pressures over `seconds` under the given actuation and the rate
 * steam is being drawn. Brew pressure relaxes towards what the pump commands
 * with the structure's time constant.
 *
 * Steam pressure follows the steam mass above saturation and is zero below it
 * whenever nothing is being drawn. While something is, it is carried below that
 * relation, and never below nothing at all. What holds it there is the demand and
 * what sets how fast it goes further is the steam actually being made, so a feed
 * commanded shut mid-draw stops the departure widening without handing any of it
 * back. The departure is discarded rather than unwound the moment the draw stops,
 * so the relation is exact again on the first step with no demand rather than
 * several steps later.
 */
void thermoblock_advance_pressures(plant_model_t *model,
                                   const plant_actuation_t *actuation,
                                   float steam_demand_ml_per_s, float seconds);

#endif /* PLANT_STRUCTURE_H */
