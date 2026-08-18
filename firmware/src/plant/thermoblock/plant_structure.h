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
 * independently heated thermal masses, each losing to ambient; the water on its
 * way to the group following the coffee block's temperature through a lag,
 * because a low-mass flow-through system puts real dynamics between the metal
 * and the stream; brew pressure driven by the pump; and steam pressure
 * following the steam mass above saturation. Whether they describe any real
 * machine cannot be settled until there is one to measure against; what they
 * establish here is that the numbers and the equations are separable and
 * replaceable.
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
     ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_PUMP))

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
    float brew_outlet_time_constant_s;

    float steam_thermal_mass_j_per_k;
    float steam_heater_power_w;
    float steam_loss_w_per_k;

    float pump_pressure_bar;
    float brew_pressure_time_constant_s;

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
 * carries it. Nothing downstream of the casting feeds back into these equations,
 * so it is also a state nothing here can identify from a reading -- see the
 * omissions in params/thermoblock.md.
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
 * to ambient; the water relaxes towards the casting it has just passed through,
 * with the structure's outlet time constant.
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
