/*
 * Where the carried description's bytes and their length come from.
 *
 * This translation unit exists so that the generated definition is compiled
 * exactly once, under the same settings as every other source this project
 * wrote, rather than being included wherever somebody wants the bytes. The
 * length is taken with sizeof here for the same reason the array is generated:
 * a length written down separately is a second statement of how long the
 * description is, and it is wrong the first time the description changes.
 */
#include "reference_description.h"

/*
 * Generated into the build directory from the description the environment
 * declares, and put on the include path by the script that generates it. It
 * defines reference_description; there is deliberately no copy of it in the
 * source tree.
 */
#include "reference_description_bytes.h"

const size_t reference_description_length = sizeof(reference_description);
