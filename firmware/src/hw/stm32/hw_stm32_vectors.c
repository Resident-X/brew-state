/*
 * The target build's own response to an interrupt reaching a vector this
 * build gives a purposeful handler, and to one reaching a vector it does not.
 *
 * The vendor startup file (Drivers/CMSIS/Device/ST/STM32F4xx/Source/Templates/
 * gcc/startup_stm32f407xx.s, reached through the stm32cube framework the stm32
 * environment builds against) weak-aliases every exception and external
 * interrupt handler name to its own Default_Handler, an infinite loop with
 * nothing recorded before it. That file links Default_Handler itself as a
 * strong symbol, so it cannot be overridden by redefining that name here --
 * what can be overridden is each of the weak aliases pointing at it, one
 * function per name, which is what this file does.
 *
 * SysTick is one of those aliases and is given the handler the tick counter
 * needs. Every other alias that startup file declares is written out below
 * rather than derived, in the same spirit as the seam's other vocabulary
 * tables (see hw_stm32.c's sensor_adc_channel and output_timer_channel): a
 * vector the vendor's next device revision adds and this list does not name
 * would otherwise fall through to the silent default unnoticed, rather than
 * fail a build that should have named it.
 */
#include "stm32f4xx_hal.h"

#include <stdint.h>

void SysTick_Handler(void)
{
    HAL_IncTick();
}

/*
 * Set once, by whichever trap below runs: the high halfword marks this state
 * as deliberately reached rather than corrupt memory left by something else,
 * and the low halfword is the trapping vector's own exception number (the
 * Cortex-M core's ICSR VECTACTIVE field), so which vector trapped is
 * recoverable from the marker alone rather than needing a debugger attached
 * at the moment it happened.
 */
#define UNHANDLED_VECTOR_MARKER_BASE 0xFA170000u

volatile uint32_t hw_stm32_unhandled_vector_marker;

static void unhandled_vector_trap(void)
{
    __disable_irq();
    hw_stm32_unhandled_vector_marker =
        UNHANDLED_VECTOR_MARKER_BASE | (SCB->ICSR & SCB_ICSR_VECTACTIVE_Msk);
    for (;;) {
    }
}

#define UNHANDLED_VECTORS(X)                  \
    X(NMI_Handler)                            \
    X(HardFault_Handler)                      \
    X(MemManage_Handler)                      \
    X(BusFault_Handler)                       \
    X(UsageFault_Handler)                     \
    X(SVC_Handler)                            \
    X(DebugMon_Handler)                       \
    X(PendSV_Handler)                         \
    X(WWDG_IRQHandler)                        \
    X(PVD_IRQHandler)                         \
    X(TAMP_STAMP_IRQHandler)                  \
    X(RTC_WKUP_IRQHandler)                    \
    X(FLASH_IRQHandler)                       \
    X(RCC_IRQHandler)                         \
    X(EXTI0_IRQHandler)                       \
    X(EXTI1_IRQHandler)                       \
    X(EXTI2_IRQHandler)                       \
    X(EXTI3_IRQHandler)                       \
    X(EXTI4_IRQHandler)                       \
    X(DMA1_Stream0_IRQHandler)                \
    X(DMA1_Stream1_IRQHandler)                \
    X(DMA1_Stream2_IRQHandler)                \
    X(DMA1_Stream3_IRQHandler)                \
    X(DMA1_Stream4_IRQHandler)                \
    X(DMA1_Stream5_IRQHandler)                \
    X(DMA1_Stream6_IRQHandler)                \
    X(ADC_IRQHandler)                         \
    X(CAN1_TX_IRQHandler)                     \
    X(CAN1_RX0_IRQHandler)                    \
    X(CAN1_RX1_IRQHandler)                    \
    X(CAN1_SCE_IRQHandler)                    \
    X(EXTI9_5_IRQHandler)                     \
    X(TIM1_BRK_TIM9_IRQHandler)               \
    X(TIM1_UP_TIM10_IRQHandler)               \
    X(TIM1_TRG_COM_TIM11_IRQHandler)          \
    X(TIM1_CC_IRQHandler)                     \
    X(TIM2_IRQHandler)                        \
    X(TIM3_IRQHandler)                        \
    X(TIM4_IRQHandler)                        \
    X(I2C1_EV_IRQHandler)                     \
    X(I2C1_ER_IRQHandler)                     \
    X(I2C2_EV_IRQHandler)                     \
    X(I2C2_ER_IRQHandler)                     \
    X(SPI1_IRQHandler)                        \
    X(SPI2_IRQHandler)                        \
    X(USART1_IRQHandler)                      \
    X(USART2_IRQHandler)                      \
    X(USART3_IRQHandler)                      \
    X(EXTI15_10_IRQHandler)                   \
    X(RTC_Alarm_IRQHandler)                   \
    X(OTG_FS_WKUP_IRQHandler)                 \
    X(TIM8_BRK_TIM12_IRQHandler)              \
    X(TIM8_UP_TIM13_IRQHandler)               \
    X(TIM8_TRG_COM_TIM14_IRQHandler)          \
    X(TIM8_CC_IRQHandler)                     \
    X(DMA1_Stream7_IRQHandler)                \
    X(FSMC_IRQHandler)                        \
    X(SDIO_IRQHandler)                        \
    X(TIM5_IRQHandler)                        \
    X(SPI3_IRQHandler)                        \
    X(UART4_IRQHandler)                       \
    X(UART5_IRQHandler)                       \
    X(TIM6_DAC_IRQHandler)                    \
    X(TIM7_IRQHandler)                        \
    X(DMA2_Stream0_IRQHandler)                \
    X(DMA2_Stream1_IRQHandler)                \
    X(DMA2_Stream2_IRQHandler)                \
    X(DMA2_Stream3_IRQHandler)                \
    X(DMA2_Stream4_IRQHandler)                \
    X(ETH_IRQHandler)                         \
    X(ETH_WKUP_IRQHandler)                    \
    X(CAN2_TX_IRQHandler)                     \
    X(CAN2_RX0_IRQHandler)                    \
    X(CAN2_RX1_IRQHandler)                    \
    X(CAN2_SCE_IRQHandler)                    \
    X(OTG_FS_IRQHandler)                      \
    X(DMA2_Stream5_IRQHandler)                \
    X(DMA2_Stream6_IRQHandler)                \
    X(DMA2_Stream7_IRQHandler)                \
    X(USART6_IRQHandler)                      \
    X(I2C3_EV_IRQHandler)                     \
    X(I2C3_ER_IRQHandler)                     \
    X(OTG_HS_EP1_OUT_IRQHandler)              \
    X(OTG_HS_EP1_IN_IRQHandler)               \
    X(OTG_HS_WKUP_IRQHandler)                 \
    X(OTG_HS_IRQHandler)                      \
    X(DCMI_IRQHandler)                        \
    X(HASH_RNG_IRQHandler)                    \
    X(FPU_IRQHandler)

#define DEFINE_UNHANDLED_VECTOR(name) \
    void name(void)                  \
    {                                 \
        unhandled_vector_trap();     \
    }

UNHANDLED_VECTORS(DEFINE_UNHANDLED_VECTOR)

#undef DEFINE_UNHANDLED_VECTOR
#undef UNHANDLED_VECTORS
