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
 * flow-through system puts real dynamics between the metal and the stream; brew
 * pressure driven by the pump; and steam pressure following the steam mass above
 * saturation. Whether they describe any real machine cannot be settled until
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
     */
    float water_feed_temperature_c;
    float water_heat_capacity_j_per_ml_k;

    float steam_saturation_temperature_c;
    float steam_pressure_bar_per_k;
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
 * Steam pressure is not integrated -- it follows the steam mass -- but it is
 * kept here so a read costs no arithmetic.
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
} plant_model_t;

/*
 * The coefficients this structure requires and the range it declares each one
 * admissible over. `count` receives the number of entries; the returned table
 * outlives any call.
 */
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);

/*
 * Advance both thermal masses over `seconds` under the given actuation, and the
 * water on its way to the group with them. Each mass takes in what its heater
 * delivers at the commanded duty and gives up what its loss coefficient carries
 * to ambient; the coffee block gives up, on top of that, what the water drawn
 * through it carries out, and the water relaxes towards the casting it has just
 * passed through over a residence time that shortens as the draw grows.
 *
 * The casting and the water are advanced as one pair rather than one after the
 * other: each now appears in the other's equation, so neither has a closed form
 * of its own to be exact against.
 */
void thermoblock_advance_temperatures(plant_model_t *model,
                                      const plant_actuation_t *actuation,
                                      float seconds);

/*
 * Advance both pressures over `seconds` under the given actuation. Brew
 * pressure relaxes towards what the pump commands with the structure's time
 * constant; steam pressure follows the steam mass above saturation and is zero
 * below it.
 */
void thermoblock_advance_pressures(plant_model_t *model,
                                   const plant_actuation_t *actuation,
                                   float seconds);

#endif /* PLANT_STRUCTURE_H */
