/*
 * What a description declares about readings the estimator can believe, and
 * about how long it may go without one.
 *
 * A reading arrives through hw_interface.h carrying a flag that answers one
 * question: whether the implementation could obtain a sample. That is not the
 * same question as whether the sample is possible. A thermocouple reading nine
 * hundred degrees is obtainable and absurd, and an estimator that corrects
 * against it is dragged toward a temperature the machine cannot be at. The two
 * failures are opposite -- one is no reading, the other is a confident wrong
 * one -- and a single flag pressed into service for both has to choose which of
 * them to get wrong.
 *
 * So the admissible span of each channel is declared per description, here in
 * shape and in a file beside the description in value. Per description because
 * the span is a fact about a machine and its sensors rather than about the
 * seam: a channel's plausible range is not something the software is entitled
 * to assume on every machine's behalf, and a default would be exactly the
 * assumption nobody would ever look at again.
 *
 * The window and the excursion bound are here for the same reason and are the
 * other half of the same question. Losing a reading briefly is an ordinary
 * operating condition rather than a fault: the reconstruction runs on
 * prediction and stays usable, up to a declared span of time and a declared
 * distance travelled. Which of the two refuses first is deliberate and not
 * interchangeable -- the distance bounds the estimate, and the window bounds
 * how long the machine is driven without feedback, because a well-behaved model
 * sitting still while the real mass runs away travels no distance at all.
 *
 * Nothing here names a plant structure or a coefficient of one. The channels
 * are the hardware seam's, and the origins are the vocabulary every description
 * in this project accounts for its values in.
 */
#ifndef ESTIMATOR_LIMITS_H
#define ESTIMATOR_LIMITS_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "hw_interface.h"
#include "plant_origin.h"

/*
 * The word each sensor channel is written as in a limits declaration.
 *
 * Deliberately not the enumerator's spelling. A declaration is written and read
 * by people, and a file naming HW_SENSOR_BREW_TEMPERATURE would be quoting the
 * software's internals back at whoever is recording what a sensor on this
 * machine can plausibly report.
 */
#define ESTIMATOR_LIMITS_BREW_TEMPERATURE_WORD "brew-temperature"
#define ESTIMATOR_LIMITS_STEAM_TEMPERATURE_WORD "steam-temperature"
#define ESTIMATOR_LIMITS_BREW_PRESSURE_WORD "brew-pressure"
#define ESTIMATOR_LIMITS_STEAM_PRESSURE_WORD "steam-pressure"

/*
 * Every channel word, in the order the channels are enumerated in, so that a
 * reader of a declaration and a reader of hw_interface.h cannot disagree about
 * which channels a description is required to account for. A channel added to
 * the seam and not named here is caught where the two are compared rather than
 * read one entry past this array while the machine runs.
 */
#define ESTIMATOR_LIMITS_CHANNEL_WORDS                                                             \
    {                                                                                              \
        ESTIMATOR_LIMITS_BREW_TEMPERATURE_WORD, ESTIMATOR_LIMITS_STEAM_TEMPERATURE_WORD,           \
            ESTIMATOR_LIMITS_BREW_PRESSURE_WORD, ESTIMATOR_LIMITS_STEAM_PRESSURE_WORD              \
    }

/*
 * The two figures that are not about any one channel: how long a reconstructed
 * state may go without a usable observation among the ones it depends on, and
 * how far it may travel from where it stood when they stopped.
 *
 * The window is a span of time rather than a count of steps. A step's duration
 * is whatever elapsed, so a window counted in steps would stretch without limit
 * on exactly the loop that has stalled -- the case it exists to bound.
 */
#define ESTIMATOR_LIMITS_TOLERANCE_WINDOW_WORD "loss-tolerance-window-ms"
#define ESTIMATOR_LIMITS_EXCURSION_BOUND_WORD "excursion-bound-milli-c"

/*
 * What separates a channel's low from its high. Two characters rather than one
 * so that it cannot be confused with a minus sign introducing a negative
 * bound, which a temperature channel's low legitimately is.
 */
#define ESTIMATOR_LIMITS_RANGE_MARKER ".."

/*
 * What one description declares. Readings are compared in the unit the hardware
 * seam reports them in -- thousandths -- so that a comparison against a bound
 * is an integer one and no reading is converted to decide whether it is
 * believable.
 */
typedef struct {
    int32_t low_milli[HW_SENSOR_CHANNEL_COUNT];
    int32_t high_milli[HW_SENSOR_CHANNEL_COUNT];
    uint32_t tolerance_window_ms;
    int32_t excursion_bound_milli;
} estimator_limits_t;

/* Why a declaration was refused. */
typedef enum {
    ESTIMATOR_LIMITS_OK = 0,
    ESTIMATOR_LIMITS_MALFORMED,     /* the line is not name = low .. high or name = value */
    ESTIMATOR_LIMITS_UNKNOWN,       /* it names nothing this seam declares */
    ESTIMATOR_LIMITS_DUPLICATE,     /* it names something a previous line already gave */
    ESTIMATOR_LIMITS_MISSING,       /* something this seam declares was never given */
    ESTIMATOR_LIMITS_INVERTED,      /* a channel's low is not below its high */
    ESTIMATOR_LIMITS_OUT_OF_RANGE,  /* a figure is not one the type can carry */
    ESTIMATOR_LIMITS_ORIGIN         /* the account of where the figure came from is malformed */
} estimator_limits_fault_t;

/* Long enough for every word this seam declares, with room for a longer one. */
#define ESTIMATOR_LIMITS_NAME_MAX 48

/*
 * What was wrong and where. The name is the one the declaration used, so a
 * reader is pointed at the line they wrote rather than at an enumerator.
 */
typedef struct {
    estimator_limits_fault_t fault;
    uint32_t line;
    char name[ESTIMATOR_LIMITS_NAME_MAX];
} estimator_limits_error_t;

/*
 * Read a declaration into a record.
 *
 * Read as bytes rather than as a file, for the reason the parameter loader is:
 * the same code then serves a host opening one from disk and a target carrying
 * one compiled in, and one reader cannot disagree with itself about what the
 * grammar admits.
 *
 * Every channel the hardware seam reports, and both figures above, are
 * required. A declaration that leaves one out is refused rather than defaulted:
 * an unbounded channel that reads as covered to everybody who looks at the file
 * is the failure this whole arrangement exists to prevent, and it has no
 * symptom -- the estimator would go on correcting against it exactly as it did
 * before anybody thought to declare bounds at all.
 *
 * Returns false and leaves `limits` untouched on any refusal, so a caller keeps
 * what it had rather than half of a new record.
 */
bool estimator_limits_load(const char *text, size_t length, estimator_limits_t *limits,
                           estimator_limits_error_t *error);

#endif /* ESTIMATOR_LIMITS_H */
