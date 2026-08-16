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
 * independently heated thermal masses, each losing to ambient, with brew
 * pressure driven by the pump and steam pressure following the steam mass
 * above saturation. Whether they describe any real machine cannot be settled
 * until there is one to measure against; what they establish here is that the
 * numbers and the equations are separable and replaceable.
 */
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H

#include "plant_types.h"

/*
 * Every coefficient this structure uses. There is no number in the equations
 * that is not read from here, apart from unit conversions and the constants of
 * the integration itself, which are properties of the equations rather than of
 * a machine.
 */
typedef struct {
    double ambient_temperature_c;

    double brew_thermal_mass_j_per_k;
    double brew_heater_power_w;
    double brew_loss_w_per_k;

    double steam_thermal_mass_j_per_k;
    double steam_heater_power_w;
    double steam_loss_w_per_k;

    double pump_pressure_bar;
    double brew_pressure_time_constant_s;

    double steam_saturation_temperature_c;
    double steam_pressure_bar_per_k;
} plant_parameters_t;

/*
 * One model instance: the states this structure integrates, and the record it
 * was initialised from. Steam pressure is not integrated -- it follows the
 * steam mass -- but it is kept here so a read costs no arithmetic.
 */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;

    double brew_temperature_c;
    double steam_temperature_c;
    double brew_pressure_bar;
    double steam_pressure_bar;
} plant_model_t;

/*
 * The coefficients this structure requires and the range it declares each one
 * admissible over. `count` receives the number of entries; the returned table
 * outlives any call.
 */
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);

/*
 * Advance both thermal masses over `seconds` under the given actuation. Each
 * mass takes in what its heater delivers at the commanded duty and gives up
 * what its loss coefficient carries to ambient.
 */
void thermoblock_advance_temperatures(plant_model_t *model,
                                      const plant_actuation_t *actuation,
                                      double seconds);

/*
 * Advance both pressures over `seconds` under the given actuation. Brew
 * pressure relaxes towards what the pump commands with the structure's time
 * constant; steam pressure follows the steam mass above saturation and is zero
 * below it.
 */
void thermoblock_advance_pressures(plant_model_t *model,
                                   const plant_actuation_t *actuation,
                                   double seconds);

#endif /* PLANT_STRUCTURE_H */
