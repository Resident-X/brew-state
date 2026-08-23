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
 * The channels a step is taken under, and the scale their levels are expressed
 * on. They are the machine's rather than this seam's, so they are included
 * from the vocabulary both seams share rather than enumerated again here.
 */
#include "machine_actuation.h"

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
    /*
     * The rate water is drawn through the brew path, as a volume per unit
     * time. It is here rather than in the state vocabulary below because a
     * consumer has to be able to read it without knowing which structure it
     * was built against: a loop commanding a rate of water closes against
     * this, and a quantity some structures answered and others refused would
     * be one every such consumer had to test for first. No structure keeps it
     * as a state -- it is produced from what the pump was commanded, not
     * integrated -- which is exactly the case the two vocabularies are
     * separate to allow.
     *
     * What it reports is the rate the pump was commanded to move, not the rate
     * a cup received. The puck, the pump's flow-versus-pressure characteristic
     * and the mechanical pressure cap all sit between the two and are none of
     * them represented; each structure's description says so.
     */
    PLANT_QUANTITY_BREW_FLOW_ML_PER_S,
    /*
     * The rate steam is being drawn off the machine, as the volume of water
     * turned to vapour per unit time -- the same unit the rate above is in, so
     * that one figure per millilitre stands against both and neither has to be
     * read against how much room the vapour then takes up.
     *
     * It is a quantity for the same reason the drawn water rate is: a consumer
     * has to reach it without knowing which structure it was built against. A
     * loop that must hold its targets through a draw reads this to know one is
     * open, and a later bench measurement of a real draw has a modelled figure
     * to be set against. What such a comparison would establish is how far this
     * model's account of a draw sits from the machine's; no comparability with
     * any instrument is claimed in advance, and the rate above claims none
     * either. No structure keeps it as a state, and it is not merely un-integrated
     * the way the rate above is -- it does not originate inside the machine at
     * all. The wand is opened by hand, so the rate arrives at the step from
     * outside and nothing the control law writes sets it.
     *
     * What it reports is the rate the step was told steam is leaving at, as the
     * structure's own admissibility guard leaves it: the rate that structure's
     * relations acted on over the step just taken. A rate below zero, and any
     * rate that is not finite, is reported as no draw, which is what those
     * relations spent. It is not a measurement of
     * what a wand passed, and no structure claims the two agree.
     */
    PLANT_QUANTITY_STEAM_DRAW_ML_PER_S,
    PLANT_QUANTITY_COUNT
} plant_quantity_t;

/*
 * The states a structure may integrate, in the units named. This is a separate
 * vocabulary from the quantities above and not a widening of them, because the
 * two answer different questions: a quantity is something the machine has and
 * every structure exposes, while a state is something a structure carries to
 * produce those quantities and is a property of its architecture. Collapsing
 * them into one list would oblige a structure to expose states it does not keep
 * and would destroy the distinction plant_types.h has drawn in prose since it
 * was written.
 *
 * The vocabulary is the machine's rather than any one structure's, on the same
 * reasoning the actuation channels are: a name a refusal can report has to
 * exist independently of whether the structure in the build happens to keep the
 * state it names. A structure of a given architecture will therefore not answer
 * every state in it -- a machine that heats the water in the vessel it delivers
 * from keeps nothing between the two -- and plant_model_state is where a
 * consumer finds out which it does.
 *
 * That the same names appear here and above for four of these is a property of
 * the two architectures behind the seam today rather than of the split. Where a
 * structure answers both, it is because the quantity it exposes is read from
 * the state it keeps; where it answers a state and no quantity of that name, or
 * the other way round, nothing here objects.
 */
typedef enum {
    /*
     * The temperature of the mass the brew heater acts on directly. On this
     * machine's architecture it is also the one a sensor can reach, which is
     * why it is exposed as a quantity as well.
     */
    PLANT_STATE_BREW_HEATED_MASS_TEMPERATURE_C = 0,
    /*
     * The temperature of the water on its way to the group, after it has left
     * that mass. It is the temperature an extraction is judged by and the one
     * nothing on the machine reports, which is what makes it the state worth
     * reconstructing. A structure that heats the water where it delivers it
     * keeps no such state and refuses this one.
     */
    PLANT_STATE_BREW_OUTLET_TEMPERATURE_C,
    PLANT_STATE_STEAM_TEMPERATURE_C,
    PLANT_STATE_BREW_PRESSURE_BAR,
    PLANT_STATE_STEAM_PRESSURE_BAR,
    PLANT_STATE_COUNT
} plant_state_t;

/*
 * What is applied to the plant over one step, in parts per thousand of full
 * scale on each channel. The levels are indexed by the machine's actuation
 * channels, so a level and the channel it is for are one thing rather than a
 * field and a convention about which channel it corresponds to.
 */
typedef struct {
    uint16_t level_permille[ACTUATION_CHANNEL_COUNT];
} plant_actuation_t;

/*
 * Why a step was refused.
 *
 * The order these are checked in is fixed rather than left to the
 * implementation, so a command with more than one thing wrong with it reports
 * the same fault every time: the faults below are reported in the order they
 * are declared, and within a fault the lowest-numbered offending channel is the
 * one reported.
 */
typedef enum {
    /* Nothing was wrong; the model advanced. */
    PLANT_STEP_OK = 0,
    /* The model or the actuation was null, or the model was never initialised. */
    PLANT_STEP_NOT_STEPPABLE,
    /* The interval was zero, so there is no span to advance over. */
    PLANT_STEP_ZERO_INTERVAL,
    /* A channel was commanded beyond ACTUATION_FULL_SCALE. */
    PLANT_STEP_LEVEL_OVER_SCALE,
    /* A channel this structure does not answer was commanded a non-zero level. */
    PLANT_STEP_CHANNEL_UNANSWERED
} plant_step_fault_t;

/*
 * What was wrong with a refused step. `channel` names the offending channel and
 * is meaningful only for a fault that has one -- an over-scale level or an
 * unanswered channel; it is ACTUATION_CHANNEL_COUNT for the others, which name
 * no channel and must not be read as naming the first one.
 */
typedef struct {
    plant_step_fault_t fault;
    actuation_channel_t channel;
} plant_step_error_t;

/* The longest parameter name a refusal can report, including the terminator. */
#define PLANT_PARAMETER_NAME_MAX 48

/*
 * The most coefficients a structure may declare.
 *
 * The loader records which coefficients a description has supplied in a bitmap
 * one word wide, and a structure with more coefficients than that is refused
 * outright rather than silently having the surplus go unchecked for absence.
 *
 * It sits in the vocabulary rather than in the loader because the record of
 * what the design assumes each coefficient may be wrong by is indexed by the
 * same positions and has to be the same length. Two limits that must agree are
 * two limits that eventually do not, and the failure would be silent: a
 * structure past the shorter of them would have its last coefficients' assumed
 * errors written nowhere and read back as undeclared.
 */
#define PLANT_PARAMETER_LIMIT 64

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
    PLANT_PARAMETER_MISSING,
    /*
     * An origin against a value, or a statement the description makes about
     * itself, is not one this vocabulary declares -- no kind after the marker,
     * a kind that is not one of the declared words, an account that is empty,
     * or a statement the description is not entitled to make.
     *
     * Separate from MALFORMED because it is the one fault whose subject is what
     * the description claims rather than whether it can be read, and a caller
     * distinguishing the two is the difference between "this file is damaged"
     * and "this value is not accounted for".
     */
    PLANT_PARAMETER_ORIGIN,
    /*
     * The assumed error against a value is not one that can stand -- the marker
     * with no token behind it, a token that is not a number, an error below
     * zero, or one that is not finite.
     *
     * Separate from ORIGIN because the two annotations answer different
     * questions about the same value: where the figure came from, and how far
     * out it may be. A caller told only that "an annotation is wrong" would
     * have to read the file to find out which, and the two are repaired by
     * different people from different sources.
     *
     * A value carrying no assumed error at all is not this fault, and is not a
     * fault here at all. Whether a description owes an error for every value it
     * carries follows what that description claims about a real machine, which
     * is settled where the description lives rather than by the loader -- the
     * same division the origin annotation already draws.
     */
    PLANT_PARAMETER_ASSUMED_ERROR
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

/*
 * What the design assumes each of a structure's coefficients may be wrong by,
 * as a fraction of the value the description gave for it.
 *
 * This is the one thing a description carries that is kept after it has been
 * read. The origin of a value is not: which values are accounted for, and
 * whether the account is adequate, is a question about a file and is settled
 * where that file lives. The assumed error is different because it has a
 * consumer on this side of the seam -- a margin is sized from it, a sweep is
 * run across it -- and a figure the running program cannot reach is a figure
 * that has to be typed a second time into whatever consumes it.
 *
 * `assumed_error` and `declared` are indexed by the structure's own order of
 * coefficients, which is the order its parameter table declares them in. That
 * is an ordering nothing outside the structure knows, so a caller reaches an
 * entry by the coefficient's name rather than by an index it would have to
 * have obtained from somewhere.
 *
 * `declared` is separate from the figure rather than being a reserved value of
 * it, because zero is a perfectly ordinary thing for a description to say: a
 * coefficient believed exact -- a defined saturation point, a ratio fixed by
 * construction -- has an assumed error of nothing at all, and reading that back
 * as "no error was declared" would silently turn the strongest claim a
 * description can make into the weakest.
 *
 * `count` is how many coefficients the structure has, and therefore how much of
 * the two arrays means anything. It is not how many errors were declared.
 */
typedef struct {
    float assumed_error[PLANT_PARAMETER_LIMIT];
    bool declared[PLANT_PARAMETER_LIMIT];
    size_t count;
} plant_parameter_budget_t;

#endif /* PLANT_TYPES_H */
