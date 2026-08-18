/*
 * Where the carried limits declaration's bytes and their length come from.
 *
 * This translation unit exists so that the generated definition is compiled
 * exactly once, under the same settings as every other source this project
 * wrote, rather than being included wherever somebody wants the bytes. The
 * length is taken with sizeof here for the same reason the array is generated:
 * a length written down separately is a second statement of how long the
 * declaration is, and it is wrong the first time the declaration changes.
 */
#include "reference_limits.h"

/*
 * Generated into the build directory from the limits declaration the
 * environment declares, and put on the include path by the script that
 * generates it. It defines reference_limits; there is deliberately no copy of
 * it in the source tree.
 */
#include "reference_limits_bytes.h"

const size_t reference_limits_length = sizeof(reference_limits);
