/*
 * A deliberately short actuation channel table.
 *
 * hw_stm32.c asserts, at compile time, that its own table's length agrees
 * with the actuation vocabulary. That assertion is only evidence that a
 * shortfall is caught if a shortfall can be shown to trip it, so this file
 * carries the same length assertion over a table one entry short of the
 * vocabulary -- exactly the shape the vocabulary's own growth once produced.
 *
 * This file is compiled in place of hw_stm32.c's table by one environment
 * declared must-not-build, and nothing else. It is never linked into
 * anything that runs: the environment that compiles it is required to fail
 * before it would reach the link step, on this file's own assertion message,
 * so that the refusal is demonstrated rather than assumed.
 */
#include <stddef.h>

#include "machine_actuation.h"

static const int output_timer_channel[] = {
    0, /* ACTUATION_CHANNEL_BREW_HEATER */
    1, /* ACTUATION_CHANNEL_STEAM_HEATER */
    2  /* ACTUATION_CHANNEL_PUMP -- ACTUATION_CHANNEL_STEAM_PUMP has no entry */
};

_Static_assert(sizeof(output_timer_channel) / sizeof(output_timer_channel[0])
                    == (size_t)ACTUATION_CHANNEL_COUNT,
               "actuation_channel_map_incomplete: the actuation channel table has fewer "
               "entries than the vocabulary declares");
