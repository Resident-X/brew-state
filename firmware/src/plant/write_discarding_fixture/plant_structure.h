/*
 * A seventh structure, alongside `thermoblock`, `fixture`, `boiler`,
 * `flow_fixture`, `outlet_only_fixture` and `correction_read_only_fixture`,
 * built to carry exactly one shape: it answers a read of both names the
 * estimator reaches its one reconstructed value by, and answers a write of
 * either with success while keeping something other than the value written.
 *
 * `correction_read_only_fixture` carries the shape one call earlier: it
 * refuses the write, which the admission check turns away because the refusal
 * is visible. A write that reports success and discards its argument is not
 * visible in the call. The correction is computed, the write says it was
 * taken, and the state carries on from where it already was -- the identical
 * externally observable failure, reached by a structure that passes every
 * probe that only asks whether the write was accepted. This structure is the
 * only thing in the tree that can drive that case, which is what it exists
 * for.
 *
 * How many writes it keeps is a coefficient, so the one structure carries each
 * shape the probe has to tell apart: none kept (the write is discarded), the
 * first kept and the rest discarded (the write is taken and the restore after
 * it is not), the first kept and the rest refused (the restore is refused
 * outright), and all kept (a structure that is admitted, to show the probe is
 * not simply refusing everything). A further coefficient seeds the state with
 * not-a-number, which no description can name because a description's values
 * are finite, so a held not-a-number can be restored and recognised as
 * restored.
 *
 * It answers one actuation channel, borrowed from `fixture` rather than chosen
 * to mean anything, only because a structure answering none is refused as a
 * broken architecture before it ever reaches the admission this structure
 * exists to be refused by instead. It serves no delivery point: nothing past
 * admission is exercised against it.
 */
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H

#include "plant_machine_claim.h"
#include "plant_support.h"
#include "plant_types.h"

/*
 * These equations describe no machine, and the coefficients below have no
 * physical meaning, on the same terms `fixture`'s do not. A mutation sweep
 * drawing a conclusion from arithmetic that stands for nothing physical would
 * report a number neither a survivor nor a kill is evidence of, so this
 * structure is excluded from the sweep's population the same way.
 */
#define PLANT_STRUCTURE_MACHINE_CLAIM PLANT_DESCRIBES_NO_MACHINE

/*
 * Unverified, and unverifiable: there is no hardware this structure could be
 * run against, because it describes none. Carried anyway, for the reason
 * every structure carries it: a structure exempted from answering would be a
 * hole an arriving structure fits through.
 */
#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED

/*
 * The brew heater, and nothing else -- the same one channel `fixture` and the
 * fixtures beside it answer, and for the same reason: a structure answering no
 * channel at all responds to no command and has stated a broken architecture
 * rather than a narrow one, which check_actuation_declaration.py refuses.
 */
#define PLANT_STRUCTURE_ACTUATION_CHANNELS ACTUATION_CHANNEL_BIT(ACTUATION_CHANNEL_BREW_HEATER)

/*
 * No delivery point at all, on the same terms `correction_read_only_fixture`
 * declares none: a point declared here would be declared for nothing to ever
 * read.
 */
#define PLANT_STRUCTURE_DELIVERY_POINTS ((plant_delivery_point_set_t)0u)

/*
 * The coefficients this structure reads. `outlet_value_c` seeds the one
 * accumulator this structure keeps, so admission's probes have a value to read
 * back before a single step has run, and `heater_gain` scales what the brew
 * heater commands into that same accumulator so the one channel this structure
 * answers is not declared and then left inert. `writes_kept` is how many
 * writes the accumulator takes before the rest are no longer kept;
 * `later_writes_refused` makes those later writes fail rather than report
 * success; `seed_undefined` seeds the accumulator with not-a-number instead of
 * `outlet_value_c`. The last two are flags, nonzero meaning set.
 */
typedef struct {
    float outlet_value_c;
    float heater_gain;
    float writes_kept;
    float later_writes_refused;
    float seed_undefined;
} plant_parameters_t;

/* One accumulator, standing for both names this structure answers under, the
 * record the model was initialised from, and how many writes it has been
 * given -- the count is what lets a suite tell a structure refused on the
 * first write from one refused on the restore after it. */
typedef struct {
    bool initialised;
    plant_parameters_t coefficients;
    float accumulated;
    unsigned writes_given;
} plant_model_t;

/*
 * The coefficients this structure requires, and the range each is admissible
 * over. `count` receives the number of entries; the returned table outlives
 * any call.
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
 */
const char *const *plant_structure_supply_driven_parameters(size_t *count);

/*
 * Add what the brew heater commanded over `seconds`, scaled by the gain, to
 * the one accumulator this structure keeps. Declared here rather than kept
 * `static` in the translation unit so the symbol is visible to anything
 * checking which structure an artefact carries -- on the same terms
 * `fixture_accumulate` is declared for `fixture`.
 */
void write_discarding_fixture_accumulate(plant_model_t *model, const plant_actuation_t *actuation,
                                         float seconds);

#endif /* PLANT_STRUCTURE_H */
