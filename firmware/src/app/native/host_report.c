#include "host_report.h"

#include <math.h>
#include <string.h>

/* Enough digits that a single-precision value survives the round trip. */
#define NUMBER_FORMAT "%.9g"

/* The longest rendering of one number or integer. */
#define RENDERED_MAX 40

host_report_field_t host_report_number(const char *key, double value)
{
    host_report_field_t field = {key, HOST_REPORT_NUMBER, value, 0, false, NULL};
    return field;
}

host_report_field_t host_report_integer(const char *key, long long value)
{
    host_report_field_t field = {key, HOST_REPORT_INTEGER, 0.0, value, false, NULL};
    return field;
}

host_report_field_t host_report_boolean(const char *key, bool value)
{
    host_report_field_t field = {key, HOST_REPORT_BOOLEAN, 0.0, 0, value, NULL};
    return field;
}

host_report_field_t host_report_text(const char *key, const char *value)
{
    host_report_field_t field = {key, HOST_REPORT_TEXT, 0.0, 0, false, value};
    return field;
}

/* A plain name: lower case letters, digits, underscore and hyphen, not empty. */
static bool is_plain_name(const char *name)
{
    if (name == NULL || name[0] == '\0') {
        return false;
    }
    for (const char *c = name; *c != '\0'; c++) {
        const bool plain = (*c >= 'a' && *c <= 'z') || (*c >= '0' && *c <= '9') || *c == '_' ||
                           *c == '-';
        if (!plain) {
            return false;
        }
    }
    return true;
}

static bool is_statable_text(const char *text)
{
    if (text == NULL) {
        return false;
    }
    for (const unsigned char *c = (const unsigned char *)text; *c != '\0'; c++) {
        if (*c < 0x20u || *c == 0x7fu || *c == '"' || *c == '\\') {
            return false;
        }
    }
    return true;
}

static bool is_statable(const host_report_field_t *field)
{
    switch (field->kind) {
    case HOST_REPORT_NUMBER:
        return isfinite(field->number);
    case HOST_REPORT_INTEGER:
    case HOST_REPORT_BOOLEAN:
        return true;
    case HOST_REPORT_TEXT:
        return is_statable_text(field->text);
    }
    return false;
}

/* The one rendering of a field's value, written to both lines. */
static void render(const host_report_field_t *field, char *rendered, size_t size)
{
    switch (field->kind) {
    case HOST_REPORT_NUMBER:
        (void)snprintf(rendered, size, NUMBER_FORMAT, field->number);
        break;
    case HOST_REPORT_INTEGER:
        (void)snprintf(rendered, size, "%lld", field->integer);
        break;
    case HOST_REPORT_BOOLEAN:
        (void)snprintf(rendered, size, "%s", field->boolean ? "true" : "false");
        break;
    case HOST_REPORT_TEXT:
        rendered[0] = '\0';
        break;
    }
}

bool host_report_emit(FILE *out, const char *what, const host_report_field_t *fields,
                      size_t count)
{
    if (out == NULL || !is_plain_name(what) || (fields == NULL && count > 0u)) {
        return false;
    }

    for (size_t i = 0u; i < count; i++) {
        if (!is_plain_name(fields[i].key) || !is_statable(&fields[i])) {
            return false;
        }
        for (size_t j = 0u; j < i; j++) {
            if (strcmp(fields[i].key, fields[j].key) == 0) {
                return false;
            }
        }
    }

    (void)fprintf(out, "HOST %s", what);
    for (size_t i = 0u; i < count; i++) {
        char rendered[RENDERED_MAX];
        render(&fields[i], rendered, sizeof(rendered));
        if (fields[i].kind == HOST_REPORT_TEXT) {
            (void)fprintf(out, " %s=\"%s\"", fields[i].key, fields[i].text);
        } else {
            (void)fprintf(out, " %s=%s", fields[i].key, rendered);
        }
    }
    (void)fprintf(out, "\n");

    (void)fprintf(out, "HOST-JSON {\"what\":\"%s\"", what);
    for (size_t i = 0u; i < count; i++) {
        char rendered[RENDERED_MAX];
        render(&fields[i], rendered, sizeof(rendered));
        if (fields[i].kind == HOST_REPORT_TEXT) {
            (void)fprintf(out, ",\"%s\":\"%s\"", fields[i].key, fields[i].text);
        } else {
            (void)fprintf(out, ",\"%s\":%s", fields[i].key, rendered);
        }
    }
    (void)fprintf(out, "}\n");
    return true;
}

void host_report_refusal(FILE *out, const char *run, const char *what,
                         const plant_parameter_error_t *refusal)
{
    if (out == NULL || run == NULL || what == NULL || refusal == NULL) {
        return;
    }
    if (refusal->parameter[0] == '\0') {
        (void)fprintf(out,
                      "%s: %s: the declared corners cannot all be run together, and no single "
                      "parameter is at fault (fault %d)\n",
                      run, what, (int)refusal->fault);
        return;
    }
    (void)fprintf(out, "%s: %s: parameter %s is refused (fault %d)\n", run, what,
                  refusal->parameter, (int)refusal->fault);
}
