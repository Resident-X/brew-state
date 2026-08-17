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

#include "plant_support.h"
#include "plant_types.h"

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
    float brew_pressure_time_constant_s;

    float steam_saturation_temperature_c;
    float steam_pressure_bar_per_k;
} plant_parameters_t;

/*
 * One model instance: the states this structure integrates, and the record it
 * was initialised from. There is one temperature, because there is one vessel;
 * both temperature quantities are answered from it. Steam pressure is not
 * integrated -- it follows the vessel -- but it is kept here so a read costs no
 * arithmetic.
 */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;

    float vessel_temperature_c;
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
 * Advance the vessel over `seconds` under the given actuation. The vessel takes
 * in what its one heater delivers at the commanded duty and gives up what its
 * loss coefficient carries to ambient.
 */
void boiler_advance_vessel(plant_model_t *model, const plant_actuation_t *actuation, float seconds);

/*
 * Advance both pressures over `seconds` under the given actuation. Brew
 * pressure relaxes towards what the pump commands with the structure's time
 * constant; steam pressure follows the vessel above saturation and is zero
 * below it.
 */
void boiler_advance_pressures(plant_model_t *model, const plant_actuation_t *actuation,
                              float seconds);

#endif /* PLANT_STRUCTURE_H */
