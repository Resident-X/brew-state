/*
 * The part of asking about delivery-point contention that is the same behind
 * every structure.
 *
 * Whether two points share a mass is answered entirely from what a structure
 * declares -- its served points and the mass identifier behind each -- so it
 * is written once here rather than restated behind each structure, exactly as
 * plant_step_admissible is for actuation.
 */
#include "plant_model.h"

#include <stddef.h>

bool plant_delivery_points_share_mass(plant_delivery_point_t a, plant_delivery_point_t b,
                                      bool *share)
{
    plant_heated_mass_id_t mass_a;
    plant_heated_mass_id_t mass_b;

    if (share == NULL) {
        return false;
    }

    if (!plant_structure_delivery_point_mass(a, &mass_a) ||
        !plant_structure_delivery_point_mass(b, &mass_b)) {
        return false;
    }

    *share = (mass_a == mass_b);
    return true;
}
