#include "hw_sim.h"

typedef struct {
    hw_reading_status_t status;
    int32_t value_milli;
} sim_channel_t;

static sim_channel_t sim_sensors[HW_SENSOR_CHANNEL_COUNT];
static uint16_t sim_outputs[ACTUATION_CHANNEL_COUNT];
static uint32_t sim_output_writes[ACTUATION_CHANNEL_COUNT];
static uint32_t sim_millis;
static bool sim_output_refused;
static bool sim_output_channel_refused[ACTUATION_CHANNEL_COUNT];

/*
 * The enumerations have no negative enumerator, so a compiler is free to give
 * them an unsigned underlying type. Comparing as unsigned is therefore the
 * range check that holds either way: a negative value converted to the
 * enumeration lands above the count rather than below zero.
 */
static bool sensor_channel_in_range(hw_sensor_channel_t channel)
{
    return (unsigned)channel < (unsigned)HW_SENSOR_CHANNEL_COUNT;
}

static bool output_channel_in_range(hw_output_channel_t channel)
{
    return (unsigned)channel < (unsigned)ACTUATION_CHANNEL_COUNT;
}

void hw_sim_reset(void)
{
    /*
     * Every channel comes up with nothing fitted to it rather than with a
     * failed sample, because that is what a harness that has said nothing about
     * a channel is entitled to claim: a sample cannot have failed on an
     * instrument nobody stood up. A suite wanting a channel that samples and
     * cannot be trusted asks for it.
     */
    for (int i = 0; i < (int)HW_SENSOR_CHANNEL_COUNT; i++) {
        sim_sensors[i].status = HW_READING_ABSENT;
        sim_sensors[i].value_milli = 0;
    }
    for (int i = 0; i < (int)ACTUATION_CHANNEL_COUNT; i++) {
        sim_outputs[i] = 0u;
        sim_output_writes[i] = 0u;
        sim_output_channel_refused[i] = false;
    }
    sim_millis = 0u;
    sim_output_refused = false;
}

void hw_sim_set_sensor(hw_sensor_channel_t channel, hw_reading_status_t status,
                       int32_t value_milli)
{
    if (!sensor_channel_in_range(channel)) {
        return;
    }
    sim_sensors[channel].status = status;
    sim_sensors[channel].value_milli = value_milli;
}

uint16_t hw_sim_output(hw_output_channel_t channel)
{
    if (!output_channel_in_range(channel)) {
        return 0u;
    }
    return sim_outputs[channel];
}

uint32_t hw_sim_output_write_count(hw_output_channel_t channel)
{
    if (!output_channel_in_range(channel)) {
        return 0u;
    }
    return sim_output_writes[channel];
}

void hw_sim_advance_millis(uint32_t delta_millis)
{
    sim_millis += delta_millis;
}

void hw_sim_set_output_refused(bool refused)
{
    sim_output_refused = refused;
}

void hw_sim_set_output_channel_refused(hw_output_channel_t channel, bool refused)
{
    if (!output_channel_in_range(channel)) {
        return;
    }
    sim_output_channel_refused[channel] = refused;
}

hw_reading_t hw_sensor_read(hw_sensor_channel_t channel)
{
    hw_reading_t reading = { HW_READING_ABSENT, 0 };

    if (!sensor_channel_in_range(channel)) {
        return reading;
    }

    /*
     * The value is carried only by a reading that has one. A channel standing
     * absent or failed reports zero rather than whatever was last injected, so
     * that no consumer can read a stale figure out of a reading that is not
     * offering one.
     */
    reading.status = sim_sensors[channel].status;
    reading.value_milli =
        (sim_sensors[channel].status == HW_READING_VALID) ? sim_sensors[channel].value_milli : 0;
    return reading;
}

bool hw_output_set(hw_output_channel_t channel, uint16_t level_permille)
{
    if (!output_channel_in_range(channel) || level_permille > ACTUATION_FULL_SCALE) {
        return false;
    }
    if (sim_output_refused || sim_output_channel_refused[channel]) {
        return false;
    }

    sim_outputs[channel] = level_permille;
    sim_output_writes[channel]++;
    return true;
}

uint32_t hw_monotonic_millis(void)
{
    return sim_millis;
}
