/*
 * The STM32 HAL-backed implementation of the hardware seam.
 *
 * Naming vendor symbols is exactly this file's job -- it is the translation
 * unit that knows what a HAL handle is, so that no translation unit under
 * src/control ever has to. The encapsulation check exempts src/hw for that
 * reason.
 *
 * The family this compiles against is nominated for the pre-hardware build and
 * is not the machine's controller selection, so this file configures the
 * peripherals the seam uses and leaves the clock tree at the device's reset
 * configuration: which oscillator and PLL settings are right is a property of
 * a board that has not been selected. Whether these peripheral settings drive
 * real hardware correctly cannot be established until that board exists.
 */
#include "hw_stm32.h"

#include "stm32f4xx_hal.h"

#include "hw_interface.h"

/*
 * What a channel this board carries no input for is written as, so that such a
 * channel is stated rather than left to the zeroth entry of the table below --
 * which is a real converter input, and would make an unwired channel report the
 * brew casting's temperature under another name.
 */
#define SENSOR_INPUT_NONE 0xFFFFFFFFu

/* Analogue inputs backing the sensor channels, in hw_sensor_channel_t order. */
static const uint32_t sensor_adc_channel[HW_SENSOR_CHANNEL_COUNT] = {
    ADC_CHANNEL_0,    /* HW_SENSOR_BREW_TEMPERATURE */
    ADC_CHANNEL_1,    /* HW_SENSOR_STEAM_TEMPERATURE */
    ADC_CHANNEL_2,    /* HW_SENSOR_BREW_PRESSURE */
    ADC_CHANNEL_3,    /* HW_SENSOR_STEAM_PRESSURE */
    /*
     * The machine's flow meter is wired to the OEM controller this project
     * replaces, not to this board, so the channel is carried with no input
     * behind it and reports that it is absent. Pointing it at a converter
     * input nothing is wired to would make it report a number -- whatever an
     * unconnected pin floats at -- and a number is exactly what a consumer
     * must not get from an instrument that is not there.
     */
    SENSOR_INPUT_NONE /* HW_SENSOR_FLOW */
};

/* Timer compare channels backing the output channels, in hw_output_channel_t order. */
static const uint32_t output_timer_channel[ACTUATION_CHANNEL_COUNT] = {
    TIM_CHANNEL_1, /* ACTUATION_CHANNEL_BREW_HEATER */
    TIM_CHANNEL_2, /* ACTUATION_CHANNEL_STEAM_HEATER */
    TIM_CHANNEL_3, /* ACTUATION_CHANNEL_PUMP */
    TIM_CHANNEL_4  /* ACTUATION_CHANNEL_STEAM_PUMP */
};

/* Full-scale count of the converter, used to scale a raw sample to milli-units. */
#define ADC_FULL_SCALE_COUNTS 4095

/* Milli-units the converter's full scale corresponds to on every channel. */
#define SENSOR_FULL_SCALE_MILLI 200000

/* How long to wait for a conversion before treating the reading as untrustworthy. */
#define ADC_CONVERSION_TIMEOUT_MS 10u

static ADC_HandleTypeDef adc;
static TIM_HandleTypeDef pwm;
static bool peripherals_ready;

static bool init_analogue_inputs(void)
{
    GPIO_InitTypeDef pins = { 0 };

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_ADC1_CLK_ENABLE();

    pins.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2 | GPIO_PIN_3;
    pins.Mode = GPIO_MODE_ANALOG;
    pins.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOA, &pins);

    adc.Instance = ADC1;
    adc.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV4;
    adc.Init.Resolution = ADC_RESOLUTION_12B;
    adc.Init.ScanConvMode = DISABLE;
    adc.Init.ContinuousConvMode = DISABLE;
    adc.Init.DiscontinuousConvMode = DISABLE;
    adc.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
    adc.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    adc.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    adc.Init.NbrOfConversion = 1;
    adc.Init.DMAContinuousRequests = DISABLE;
    adc.Init.EOCSelection = ADC_EOC_SINGLE_CONV;

    return HAL_ADC_Init(&adc) == HAL_OK;
}

static bool init_outputs(void)
{
    GPIO_InitTypeDef pins = { 0 };
    TIM_OC_InitTypeDef compare = { 0 };

    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_TIM3_CLK_ENABLE();

    pins.Pin = GPIO_PIN_6 | GPIO_PIN_7 | GPIO_PIN_8 | GPIO_PIN_9;
    pins.Mode = GPIO_MODE_AF_PP;
    pins.Pull = GPIO_NOPULL;
    pins.Speed = GPIO_SPEED_FREQ_LOW;
    pins.Alternate = GPIO_AF2_TIM3;
    HAL_GPIO_Init(GPIOC, &pins);

    pwm.Instance = TIM3;
    pwm.Init.Prescaler = 0;
    pwm.Init.CounterMode = TIM_COUNTERMODE_UP;
    pwm.Init.Period = ACTUATION_FULL_SCALE - 1u;
    pwm.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
    pwm.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_ENABLE;

    if (HAL_TIM_PWM_Init(&pwm) != HAL_OK) {
        return false;
    }

    compare.OCMode = TIM_OCMODE_PWM1;
    compare.Pulse = 0;
    compare.OCPolarity = TIM_OCPOLARITY_HIGH;
    compare.OCFastMode = TIM_OCFAST_DISABLE;

    for (int i = 0; i < (int)ACTUATION_CHANNEL_COUNT; i++) {
        if (HAL_TIM_PWM_ConfigChannel(&pwm, &compare, output_timer_channel[i]) != HAL_OK) {
            return false;
        }
        if (HAL_TIM_PWM_Start(&pwm, output_timer_channel[i]) != HAL_OK) {
            return false;
        }
    }

    return true;
}

bool hw_stm32_init(void)
{
    peripherals_ready = false;

    if (HAL_Init() != HAL_OK) {
        return false;
    }
    if (!init_analogue_inputs()) {
        return false;
    }
    if (!init_outputs()) {
        return false;
    }

    peripherals_ready = true;
    return true;
}

hw_reading_t hw_sensor_read(hw_sensor_channel_t channel)
{
    /*
     * Failed rather than absent is what every refusal below reports: the
     * peripherals, the converter and the count are all things that went wrong
     * while sampling a channel this board does have an input for. The one
     * condition that is genuinely absence is the channel with no input behind
     * it, and it is answered before any of them.
     */
    hw_reading_t reading = { HW_READING_FAILED, 0 };
    ADC_ChannelConfTypeDef selection = { 0 };

    if ((unsigned)channel >= (unsigned)HW_SENSOR_CHANNEL_COUNT) {
        reading.status = HW_READING_ABSENT;
        return reading;
    }
    if (sensor_adc_channel[channel] == SENSOR_INPUT_NONE) {
        reading.status = HW_READING_ABSENT;
        return reading;
    }
    if (!peripherals_ready) {
        return reading;
    }

    selection.Channel = sensor_adc_channel[channel];
    selection.Rank = 1;
    selection.SamplingTime = ADC_SAMPLETIME_84CYCLES;
    if (HAL_ADC_ConfigChannel(&adc, &selection) != HAL_OK) {
        return reading;
    }

    if (HAL_ADC_Start(&adc) != HAL_OK) {
        return reading;
    }
    if (HAL_ADC_PollForConversion(&adc, ADC_CONVERSION_TIMEOUT_MS) != HAL_OK) {
        (void)HAL_ADC_Stop(&adc);
        return reading;
    }

    const uint32_t counts = HAL_ADC_GetValue(&adc);
    (void)HAL_ADC_Stop(&adc);

    if (counts > (uint32_t)ADC_FULL_SCALE_COUNTS) {
        return reading;
    }

    reading.status = HW_READING_VALID;
    reading.value_milli =
        (int32_t)((counts * (uint32_t)SENSOR_FULL_SCALE_MILLI) / (uint32_t)ADC_FULL_SCALE_COUNTS);
    return reading;
}

bool hw_output_set(hw_output_channel_t channel, uint16_t level_permille)
{
    if (!peripherals_ready || (unsigned)channel >= (unsigned)ACTUATION_CHANNEL_COUNT) {
        return false;
    }
    if (level_permille > ACTUATION_FULL_SCALE) {
        return false;
    }

    __HAL_TIM_SET_COMPARE(&pwm, output_timer_channel[channel], level_permille);
    return true;
}

uint32_t hw_monotonic_millis(void)
{
    return HAL_GetTick();
}
