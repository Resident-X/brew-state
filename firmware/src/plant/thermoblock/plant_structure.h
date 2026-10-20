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
 * driven by the pump; and steam pressure that is saturation of the casting
 * temperature while the wand is shut over held liquid, and the drop across the
 * restriction the steam made goes through while it is open. Whether
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

    /*
     * The temperature the saturation relation below starts from: gauge pressure
     * is zero at and under it, and the relation is valid from it up to the
     * casting ceiling.
     */
    float steam_saturation_temperature_c;
    /*
     * The saturation relation's three figures, Antoine's form
     * log10(p_bar) = a - b / (c + T). It is a property of water and not of the
     * machine, fitted to the saturation line, and the steam-side gauge pressure
     * is its answer less its own answer at the saturation temperature, so the
     * relation is continuous where it starts.
     */
    float steam_saturation_antoine_a;
    float steam_saturation_antoine_b_k;
    float steam_saturation_antoine_c_c;
    /*
     * The hottest casting the trapped pressure is reported for. A shut block
     * holding liquid reports saturation at the lower of its casting and this, so
     * the reported pressure never exceeds saturation at it. It is a control
     * limit the model applies and not containment of anything.
     */
    float steam_casting_ceiling_c;
    /*
     * The drop across the tube, valve and tip per square of the steam made
     * through them, in bar per (millilitre per second) squared: the pressure
     * with the wand open is this times the square of the rate steam is made at.
     * A property of the path and not of water.
     */
    float steam_restriction_bar_s2_per_ml2;
    /*
     * How far below the casting the steam leaves the block, per millilitre a
     * second of steam made, in kelvin: the casting-to-outlet relation. Steam made
     * faster has less time against the metal on its way out, so it leaves further
     * below the casting. The outlet temperature is the casting less this times the
     * rate, and the superheat reported is that outlet less saturation at the
     * pressure the step reports.
     */
    float steam_outlet_drop_k_s_per_ml;
    /*
     * The liquid the block can hold, and the liquid it holds at the start. The
     * second sits between zero and the first; an instance started with more
     * than the capacity holds the capacity.
     */
    float steam_liquid_capacity_ml;
    float steam_initial_inventory_ml;
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
 * Steam pressure is one of two relations. With the wand shut it is saturation of
 * the casting temperature while the block holds liquid, and zero while it holds
 * none. With the wand open it is the drop across the restriction for the steam
 * being made. Which applies is decided by the held liquid and the draw, so the
 * pressure is a function of the step's inputs and the inventory and carries no
 * state of its own.
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
     * The liquid water the block holds, in millilitres. Commanded feed raises it
     * up to the capacity and the steam made lowers it; with the wand shut nothing
     * is made and nothing leaks, so it is kept. It is what separates a shut block
     * whose pressure is saturation of its casting from a dry one that reads
     * nothing, and it stays within zero and the capacity.
     */
    float steam_liquid_inventory_ml;

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

    /*
     * The superheat of the steam at the modelled outlet over the step just taken,
     * in kelvin: the outlet temperature the casting-to-outlet relation gives, less
     * saturation at the pressure the step reports, and nothing while no steam is
     * made or the outlet sits at or below saturation. Held for the reasons the
     * rates above are, and a quantity rather than a state for the same ones: it is
     * recomputed whole every step from the casting, the pressure and the rate
     * steam is made at, and nothing integrates it.
     */
    float steam_outlet_superheat_k;
} plant_model_t;

/*
 * The coefficients this structure requires and the range it declares each one
 * admissible over. `count` receives the number of entries; the returned table
 * outlives any call.
 */
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);

/*
 * The relations between coefficients a description must satisfy beyond each
 * lying in its own range, refused at load as PLANT_PARAMETER_INCONSISTENT. `count`
 * receives the number of entries, which is zero for a structure with none; the
 * returned table outlives any call.
 */
const plant_parameter_relation_t *plant_structure_parameter_relations(size_t *count);

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
 * The held liquid is advanced first: commanded feed raises it, the steam made
 * lowers it, and it is kept within zero and the capacity. Steam pressure is then
 * the restriction's drop for the rate steam is made at while a draw is open --
 * zero when the feed is shut however far the wand is open -- and otherwise
 * saturation of the casting temperature, bounded at the casting ceiling, while
 * the block holds liquid, and zero while it holds none. The superheat at the
 * modelled outlet is taken last, from the casting the step left, the pressure it
 * reports and the rate steam was made at.
 */
void thermoblock_advance_pressures(plant_model_t *model,
                                   const plant_actuation_t *actuation,
                                   float steam_demand_ml_per_s, float seconds);

#endif /* PLANT_STRUCTURE_H */
