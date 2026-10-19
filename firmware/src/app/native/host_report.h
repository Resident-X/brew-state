/*
 * One report seam for what a host run states about itself.
 *
 * A host run states some findings that are not a trajectory: a bound it was
 * built under, a quality of the steam it made. Each is stated twice, once as a
 * line a person reads and once as a line a program parses, and two writers for
 * one finding are two statements that can disagree. So there is one writer. A
 * finding is a name and an ordered list of fields, and both lines are produced
 * from that list in a single pass over it: the text line `HOST <what> k=v ...`
 * and the JSON line `HOST-JSON {"what":"<what>","k":v,...}`.
 *
 * The values are rendered once each and the same characters are written to both
 * lines, so a number cannot be rounded one way in one form and another way in
 * the other. A text value is double quoted in the text line and so is read as one
 * token whatever it contains.
 *
 * Nothing is written for a list the seam cannot state in both forms: a key that
 * is not a plain name, a key given twice, a number that is not finite (which JSON
 * has no spelling for), or a text value carrying a quote, a backslash or a
 * control character (which would need an escape the text line has no spelling
 * for). A partial or one-sided statement is not a shorter answer, it is no answer.
 */
#ifndef HOST_REPORT_H
#define HOST_REPORT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>

#include "plant_types.h"

typedef enum {
    HOST_REPORT_NUMBER,
    HOST_REPORT_INTEGER,
    HOST_REPORT_BOOLEAN,
    HOST_REPORT_TEXT
} host_report_kind_t;

typedef struct {
    const char *key;
    host_report_kind_t kind;
    double number;
    long long integer;
    bool boolean;
    const char *text;
} host_report_field_t;

/* The constructors for a field of each kind, so a list reads as a list. */
host_report_field_t host_report_number(const char *key, double value);
host_report_field_t host_report_integer(const char *key, long long value);
host_report_field_t host_report_boolean(const char *key, bool value);
host_report_field_t host_report_text(const char *key, const char *value);

/*
 * Write the text line and the JSON line for `what` and its `count` fields to
 * `out`, text first. Returns true when both lines were written, and false,
 * writing nothing, when the finding cannot be stated in both forms (see above),
 * including a null stream, a null or empty `what`, or a `what` that is not a
 * plain name.
 */
bool host_report_emit(FILE *out, const char *what, const host_report_field_t *fields,
                      size_t count);

/*
 * Write to `out` the line a host run owes its builder when a law refuses the
 * description it was handed: `run` and `what` as the prefix, then the parameter
 * and fault when the refusal names one. A refusal that names none -- declared
 * corners that each build and cannot all be run together -- is stated as that,
 * and not as a parameter with an empty name.
 */
void host_report_refusal(FILE *out, const char *run, const char *what,
                         const plant_parameter_error_t *refusal);

#endif /* HOST_REPORT_H */
