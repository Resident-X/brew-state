/*
 * The vocabulary the plant-model seam is expressed in.
 *
 * This header carries the types that are the same whatever structure a build
 * compiles: the quantities a model exposes, the actuation a step is taken
 * under, and the shape of a parameter description and of a refusal to accept
 * one. It names no structure, declares no operation and holds no equation.
 *
 * It is separate from plant_model.h because a structure's own header needs
 * this vocabulary to declare its parameter table, while plant_model.h needs
 * the structure's types to declare its operations. Splitting the two is what
 * keeps that from being a cycle.
 *
 * Quantities and coefficients are single precision. That is the width every
 * controller this machine might reasonably be built on handles natively, so it
 * leaves the choice of part open; double precision would either require a part
 * that has a double-precision unit or be emulated in software on one that does
 * not, and narrowing the field of parts is the opposite of what is wanted this
 * early. It costs nothing that matters: the measurement is a twelve- to
 * fifteen-bit conversion, and a plant model is judged against a first
 * identification that recovers the response shape to within tens of percent.
 * Single precision carries far more significant figures than either.
 *
 * Nothing here fixes the arithmetic of anything built on top. A later
 * estimator whose conditioning needs care answers that with a method chosen for
 * numerical stability, not by widening this interface.
 */
#ifndef PLANT_TYPES_H
#define PLANT_TYPES_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/*
 * The quantities every plant structure exposes, in the units named. These are
 * the quantities the machine has, not the states a structure keeps: what a
 * structure carries internally to produce them is its own business, and two
 * structures of different architectures answer these from different states.
 */
typedef enum {
    PLANT_QUANTITY_BREW_TEMPERATURE_C = 0,
    PLANT_QUANTITY_STEAM_TEMPERATURE_C,
    PLANT_QUANTITY_BREW_PRESSURE_BAR,
    PLANT_QUANTITY_STEAM_PRESSURE_BAR,
    PLANT_QUANTITY_COUNT
} plant_quantity_t;

/* The largest drive level an actuation field expresses, in parts per thousand. */
#define PLANT_ACTUATION_FULL_SCALE 1000u

/*
 * What is applied to the plant over one step, in parts per thousand of full
 * scale on each channel. The channels are the machine's, and correspond to the
 * output channels the hardware seam drives.
 */
typedef struct {
    uint16_t brew_heater_permille;
    uint16_t steam_heater_permille;
    uint16_t pump_permille;
} plant_actuation_t;

/* The longest parameter name a refusal can report, including the terminator. */
#define PLANT_PARAMETER_NAME_MAX 48

/*
 * One coefficient a structure requires, where it lands in that structure's
 * parameter record, and the range outside which the structure declares it
 * inadmissible. A structure supplies one of these per coefficient; nothing
 * else needs to know what any of them mean.
 */
typedef struct {
    const char *name;
    float minimum;
    float maximum;
    size_t offset;
} plant_parameter_spec_t;

/* Why a parameter description was refused. */
typedef enum {
    /* Nothing was wrong; the record is populated. */
    PLANT_PARAMETER_OK = 0,
    /* A line is not a comment, not blank, and not `name = value`. */
    PLANT_PARAMETER_MALFORMED,
    /* A line names a coefficient this structure does not have. */
    PLANT_PARAMETER_UNKNOWN,
    /* A coefficient is given more than once, so which one applies is unclear. */
    PLANT_PARAMETER_DUPLICATE,
    /* A coefficient is outside the range the structure declares admissible. */
    PLANT_PARAMETER_OUT_OF_RANGE,
    /* A coefficient the structure requires is absent, and none is assumed. */
    PLANT_PARAMETER_MISSING
} plant_parameter_fault_t;

/*
 * What was wrong with a refused parameter description. `line` is the
 * one-based line the fault was found on, and is zero for a missing
 * coefficient, which has no line to point at. `minimum` and `maximum` carry
 * the declared range only for an out-of-range fault.
 */
typedef struct {
    plant_parameter_fault_t fault;
    uint32_t line;
    char parameter[PLANT_PARAMETER_NAME_MAX];
    float value;
    float minimum;
    float maximum;
} plant_parameter_error_t;

#endif /* PLANT_TYPES_H */
