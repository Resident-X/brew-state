# Controller pin table, STM32H743VIT6 in LQFP100

Part: STMicroelectronics STM32H743VIT6, JLCPCB C114409, LQFP100 14 x 14 mm. Pin numbers, port names, I/O structures and notes are DS12110 Rev 11 (January 2026) Table 9, LQFP100 column and Figure 5 (read 2026-10-29 from the Internet Archive's copy of https://www.st.com/resource/en/datasheet/stm32h743vi.pdf); alternate-function numbers are Table 10; the stock KiCad symbol `MCU_ST_STM32H7:STM32H743VITx` carries the same pin numbers (checked pin by pin). Reset states are DS12110 Table 8 (all I/Os are floating inputs during and after reset unless a note says otherwise), RM0433 Rev 8 (January 2023) 11.3.1 and GPIOx_MODER/PUPDR reset values, and AN4938 Rev 7 (October 2024) 6.3.3. The sheet is `sheets/31-controller.yaml`; every pin is in exactly one net or in its `no_connect` list.

Bootloader and USB notes: AN2606 Rev 70 (February 2026), section 60 (STM32H74xxx/75xxx), Tables 135 and 136; AN4879 Rev 10 (January 2025), 2.6 and 3.1; both STMicroelectronics, Internet Archive copies of the st.com PDFs, read 2026-10-29.

Counts: 100 pins = 5 VDD + 5 VSS + VBAT + VDDA + VSSA + VREF+ + 2 VCAP + NRST + BOOT0 + 82 GPIO (80 port pins and the analogue-only pads PC2_C and PC3_C). The LQFP100 package has no PDR_ON, VDDLDO, BYPASS_REG, VDD33USB or VREF- pin: Table 9 note 5 (PDR_ON tied internally to VDD, so the internal power supervisor is always on), note 6 (VDDLDO tied to VDD) and note 7 (the *_u* pins run from VDD when no USB is used). Of the 82 GPIO, 60 are used and 22 are not connected.

| Pin | Port / name | Net | Function / AF | 5 V class (Table 9) | State in reset | Note |
|---|---|---|---|---|---|---|
| 1 | PE2 | KEY1 | GPIO (panel key/indicator line, owner D) | FT_h | floating input (analog mode per RM0433) |  |
| 2 | PE3 | KEY2 | GPIO | FT_h | floating input (analog mode per RM0433) |  |
| 3 | PE4 | KEY3 | GPIO | FT_h | floating input (analog mode per RM0433) |  |
| 4 | PE5 | KEY4 | GPIO | FT_h | floating input (analog mode per RM0433) |  |
| 5 | PE6 | KEY5 | GPIO | FT_h | floating input (analog mode per RM0433) |  |
| 6 | VBAT | +3V3 | supply: backup domain (no battery; tied to VDD through 100 nF) | S | - |  |
| 7 | PC13 | no connect | unused | FT | floating input (analog mode per RM0433) | output limited to 3 mA (Table 52); backup-domain pin |
| 8 | PC14 | LSE_IN | OSC32_IN (LSE crystal Y402) | FT | oscillator pin, off until LSEON |  |
| 9 | PC15 | LSE_OUT | OSC32_OUT (LSE crystal Y402) | FT | oscillator pin, off until LSEON |  |
| 10 | VSS | GND | supply | S | - |  |
| 11 | VDD | +3V3 | supply | S | - |  |
| 12 | PH0 | HSE_IN | OSC_IN (HSE crystal Y401) | FT | oscillator pin, off until HSEON (HSI selected at reset) |  |
| 13 | PH1 | HSE_OUT | OSC_OUT (HSE crystal Y401) | FT | oscillator pin |  |
| 14 | NRST | NRST | reset, bidirectional, internal pull-up 30-50 kohm | RST | low while reset is asserted |  |
| 15 | PC0 | NTC_COF | ADC123_INP10 | FT_a | floating input (analog mode per RM0433) |  |
| 16 | PC1 | NTC_STM | ADC123_INP11 | FT_ha | floating input (analog mode per RM0433) |  |
| 17 | PC2_C | no connect | unused (analogue-only pad, ADC3_INP0/INN1) | ANA TT_a | floating input (analog mode per RM0433) |  |
| 18 | PC3_C | no connect | unused (analogue-only pad, ADC3_INP1) | ANA TT_a | floating input (analog mode per RM0433) |  |
| 19 | VSSA | GND | supply (analogue ground) | S | - |  |
| 20 | VREF+ | VREF+ | reference voltage input/output | S | - |  |
| 21 | VDDA | +3V3A | supply (analogue) | S | - |  |
| 22 | PA0 | SPARE_AN2 | ADC1_INP16 | FT_a | floating input (analog mode per RM0433) |  |
| 23 | PA1 | no connect | unused (ADC1_INP17) | FT_ha | floating input (analog mode per RM0433) |  |
| 24 | PA2 | CURR1_AN | ADC12_INP14 | FT_a | floating input (analog mode per RM0433) |  |
| 25 | PA3 | CURR2_AN | ADC12_INP15 | FT_ha | floating input (analog mode per RM0433) |  |
| 26 | VSS | GND | supply | S | - |  |
| 27 | VDD | +3V3 | supply | S | - |  |
| 28 | PA4 | no connect | unused (ADC12_INP18, DAC1_OUT1) | TT_a | floating input (analog mode per RM0433) |  |
| 29 | PA5 | no connect | unused (ADC12_INP19, DAC1_OUT2) | TT_ha | floating input (analog mode per RM0433) |  |
| 30 | PA6 | BREW_AN | ADC12_INP3 | FT_a | floating input (analog mode per RM0433) |  |
| 31 | PA7 | no connect | unused (ADC12_INP7) | TT_a | floating input (analog mode per RM0433) |  |
| 32 | PC4 | NTC_WAND | ADC12_INP4 | TT_a | floating input (analog mode per RM0433) |  |
| 33 | PC5 | STMP_AN | ADC12_INP8 | TT_a | floating input (analog mode per RM0433) |  |
| 34 | PB0 | no connect | unused (ADC12_INP9) | FT_a | floating input (analog mode per RM0433) |  |
| 35 | PB1 | no connect | unused (ADC12_INP5) | TT_a | floating input (analog mode per RM0433) |  |
| 36 | PB2 | no connect | unused | FT_ha | floating input (analog mode per RM0433) |  |
| 37 | PE7 | no connect | unused | TT_ha | floating input (analog mode per RM0433) | 3.3 V-tolerant only (TT): never a 5 V user |
| 38 | PE8 | no connect | unused | TT_ha | floating input (analog mode per RM0433) | 3.3 V-tolerant only (TT): never a 5 V user |
| 39 | PE9 | no connect | unused | TT_ha | floating input (analog mode per RM0433) | 3.3 V-tolerant only (TT): never a 5 V user |
| 40 | PE10 | no connect | unused | TT_ha | floating input (analog mode per RM0433) | 3.3 V-tolerant only (TT): never a 5 V user |
| 41 | PE11 | no connect | unused | TT_ha | floating input (analog mode per RM0433) | 3.3 V-tolerant only (TT): never a 5 V user |
| 42 | PE12 | TANK_LEVEL | GPIO input | FT_h | floating input (analog mode per RM0433) |  |
| 43 | PE13 | KNOB_HOT | GPIO input | FT_h | floating input (analog mode per RM0433) |  |
| 44 | PE14 | KNOB_STEAM | GPIO input | FT_h | floating input (analog mode per RM0433) |  |
| 45 | PE15 | MAINS_PRES_C | GPIO input (wall-board mains-presence confirm through R764, 27 kohm, with R765, 82 kohm, to GND) | FT_h | analog mode at reset (RM0433); firmware sets a plain floating input, no pull (DS12110 Table 109 note 4) |  |
| 46 | PB10 | BREW_SCL | I2C2_SCL AF4 (also USART3_TX AF7) | FT_f | floating input (analog mode per RM0433) |  |
| 47 | PB11 | BREW_SDA | I2C2_SDA AF4 (also USART3_RX AF7) | FT_f | floating input (analog mode per RM0433) |  |
| 48 | VCAP | VCAP | core regulator output (VCAP1) | S | - |  |
| 49 | VSS | GND | supply | S | - |  |
| 50 | VDD | +3V3 | supply | S | - |  |
| 51 | PB12 | PT1_CS | GPIO output (SPI2_NSS AF5 not used) | FT_u | floating input (analog mode per RM0433) | supplied by VDD33USB, tied to VDD in this package; Table 9 note 7 |
| 52 | PB13 | SPI2_SCK | SPI2_SCK AF5 | FT_u | floating input (analog mode per RM0433) | as PB12 |
| 53 | PB14 | SPI2_MISO | SPI2_MISO AF5 | FT_u | floating input (analog mode per RM0433) | as PB12 |
| 54 | PB15 | SPI2_MOSI | SPI2_MOSI AF5 | FT_u | floating input (analog mode per RM0433) | as PB12 |
| 55 | PD8 | PT2_CS | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 56 | PD9 | AMC_CS | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 57 | PD10 | AMC_DRDY | GPIO input (EXTI) | FT_h | floating input (analog mode per RM0433) |  |
| 58 | PD11 | AMC_RESET | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 59 | PD12 | no connect | unused (I2C4_SCL, LPTIM1_IN1) | FT_fh | floating input (analog mode per RM0433) |  |
| 60 | PD13 | no connect | unused (I2C4_SDA) | FT_fh | floating input (analog mode per RM0433) |  |
| 61 | PD14 | GAUGE_STEP1 | TIM4_CH3 AF2 | FT_h | floating input (analog mode per RM0433) |  |
| 62 | PD15 | GAUGE_STEP2 | TIM4_CH4 AF2 | FT_h | floating input (analog mode per RM0433) |  |
| 63 | PC6 | FLOW_IN | TIM8_CH1 AF3 | FT_h | floating input (analog mode per RM0433) |  |
| 64 | PC7 | POL_OUT | GPIO output, push-pull (proof of life) | FT_h | floating input (analog mode per RM0433) |  |
| 65 | PC8 | WT1_DATA | GPIO input | FT_h | floating input (analog mode per RM0433) |  |
| 66 | PC9 | WT1_CLK | GPIO output (MCO2 AF0 not used) | FT_fh | floating input (analog mode per RM0433) |  |
| 67 | PA8 | PUMP_S_GATE | TIM1_CH1 AF1 (MCO1 is AF0) | FT_fha | floating input (analog mode per RM0433) | I2C3_SCL in the ST bootloader: open-drain, no pull (AN2606 Rev 70, Table 135); never driven high |
| 68 | PA9 | PUMP_C_GATE | TIM1_CH2 AF1 | FT_u | floating input (analog mode per RM0433) | USART1_TX in the ST bootloader: alternate push-pull with pull-up, an input until USART1 is detected in bootloader 0x91 (AN2606 Rev 70, Table 135). Its OTG_FS_VBUS function is not used: USB runs with VBUS detection off (`circuit-proof.md`, USB rows) |
| 69 | PA10 | ZC_IN | TIM1_CH3 AF1 | FT_u | floating input (analog mode per RM0433) | USART1_RX in the ST bootloader |
| 70 | PA11 | USB_DM | OTG_FS_DM (USB_FS DM), alternate function after firmware configures it | FT_u | floating input (analog mode per RM0433) | bootloader USB (DFU) pin: alternate push-pull, no pull (AN2606 Rev 70, Table 135); to J402.2 through D401 |
| 71 | PA12 | USB_DP | OTG_FS_DP (USB_FS DP), alternate function after firmware configures it | FT_u | floating input (analog mode per RM0433) | bootloader USB (DFU) pin: alternate push-pull, no pull (AN2606 Rev 70, Table 135); to J402.1 through D401 |
| 72 | PA13 | SWDIO | JTMS/SWDIO AF0 | FT | AF0 debug, internal pull-up (AN4938 6.3.3; GPIOA_PUPDR reset 0x6400 0000) |  |
| 73 | VCAP | VCAP | core regulator output (VCAP2, joined to pin 48) | S | - |  |
| 74 | VSS | GND | supply | S | - |  |
| 75 | VDD | +3V3 | supply | S | - |  |
| 76 | PA14 | SWCLK | JTCK/SWCLK AF0 | FT | AF0 debug, internal pull-down |  |
| 77 | PA15 | no connect | unused (JTDI) | FT | AF0 JTDI, internal pull-up, until firmware releases it |  |
| 78 | PC10 | no connect | unused | FT_ha | floating input (analog mode per RM0433) |  |
| 79 | PC11 | WT2_DATA | GPIO input | FT_h | floating input (analog mode per RM0433) |  |
| 80 | PC12 | WT2_CLK | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 81 | PD0 | GAUGE_DIR1 | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 82 | PD1 | GAUGE_DIR2 | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 83 | PD2 | HEAT_C_DRV | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 84 | PD3 | HEAT_S_DRV | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 85 | PD4 | VALVE_2W_DRV | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 86 | PD5 | VALVE_3W_DRV | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 87 | PD6 | GAUGE_RST | GPIO output | FT_h | floating input (analog mode per RM0433) |  |
| 88 | PD7 | MAINS_PRES_S | GPIO input (wall-board mains-presence confirm through R774, 27 kohm, with R775, 82 kohm, to GND) | FT_h | analog mode at reset (RM0433); firmware sets a plain floating input, no pull (DS12110 Table 109 note 4) |  |
| 89 | PB3 | SWO | JTDO/TRACESWO AF0 (serial-wire output, optional) | FT | AF0 debug, floating (no pull) per RM0433 11.3.1 |  |
| 90 | PB4 | no connect | unused (NJTRST) | FT | AF0 NJTRST, internal pull-up, until firmware releases it |  |
| 91 | PB5 | ANODE_GATE | TIM3_CH2 AF2 | FT | floating input (analog mode per RM0433) |  |
| 92 | PB6 | no connect | unused (I2C1/I2C4 SCL, USART1_TX) | FT_f | floating input (analog mode per RM0433) |  |
| 93 | PB7 | no connect | unused (I2C1/I2C4 SDA, USART1_RX) | FT_fa | floating input (analog mode per RM0433) |  |
| 94 | BOOT0 | BOOT0 | boot mode select | B | sampled 4th SYSCLK rising edge after reset release |  |
| 95 | PB8 | STM_SCL | I2C1_SCL AF4 (also UART4_RX AF8) | FT_fh | floating input (analog mode per RM0433) |  |
| 96 | PB9 | STM_SDA | I2C1_SDA AF4 (also UART4_TX AF8) | FT_fh | floating input (analog mode per RM0433) |  |
| 97 | PE0 | LOWWATER_K | GPIO output (open-drain use, owner D) | FT_h | floating input (analog mode per RM0433) |  |
| 98 | PE1 | BUZZER | GPIO output (open-drain use, owner D) | FT_h | floating input (analog mode per RM0433) |  |
| 99 | VSS | GND | supply | S | - |  |
| 100 | VDD | +3V3 | supply | S | - |  |

Class key (Table 8): FT is 5 V tolerant, TT is 3.3 V tolerant only, B is the dedicated BOOT0 pin, RST is the bidirectional reset pin with a weak pull-up, S is a supply pin, ANA is analogue-only; the suffixes are _a analogue option (supplied by VDDA), _h high-speed low-voltage I/O, _f fast-mode-plus I2C, _u USB option (supplied by VDD33USB, which is VDD in this package). The operating limit for an FT pin is Min(VDD, VDDA, VDD33USB) + 3.6 V and below 5.5 V (Table 112), a TT pin VDD + 0.3 V; both while VDD is present. With VDD absent see `B-holdoff-facts.md`.

## Differences from the record's allocation

- Every function the allocation table (`component-specification.md`, Where each function lands) and the net dictionary place is on the pin they give. The dictionary adds POL_OUT on PC7, the AMC131M02's AMC_CS, AMC_DRDY and AMC_RESET on PD9, PD10 and PD11, SPARE_AN2 on PA0, CURR1_AN and CURR2_AN on PA2 and PA3, BREW_AN on PA6, and the two reserved mains-presence inputs on PE15 and PD7; each of those pins is FT_h or FT_a in Table 9.
- PB3 is wired to the debug header's SWO pin (JTDO/TRACESWO, AF0). The allocation record lists PB3 among the 20 free 5 V-rated pins; it is no longer free. PB3 has no pull in reset (RM0433 11.3.1).
- The pins the dictionary does not use stay unconnected: PA1, PA4, PA5, PA7, PB0, PB1, PB2 (conversion or general), PB4, PB6, PB7, PA15, PC10, PC13, PD12, PD13, PE7 to PE11, PC2_C, PC3_C. Of the record's 20 free pins rated for 5 V (PA0, PA1, PA11, PA12, PA15, PB2, PB3, PB4, PB6, PB7, PC7, PC10, PC13, PD9, PD10, PD11, PD12, PD13, PE10, PE11), PA0, PA11, PA12, PB3, PC7, PD9, PD10 and PD11 are now placed, which leaves 12. The lead restates the free list.
- The PB12 to PB15 pins are *_u* pins: no USB is used, so they run from VDD (Table 9 note 7; AN4938 2.1.2). Their FT_u leakage limit is 5 000 nA above Max(VDDXXX) (Table 147) and they take no 5 V.
- No MCO pin is free for a clock observation point: MCO1 is PA8 (the steam pump gate) and MCO2 is PC9 (a load-cell clock).

## Converter-input map

Three 16-bit ADCs (DS12110 section 3.17; Table 2). ADC1 and ADC2 share one common block and one kernel clock; ADC3 is separate. All three take their kernel clock from the same selector (RM0433 Rev 8, RCC_D3CCIPR ADCSEL: pll2_p_ck by default, pll3_r_ck or per_ck), which feeds adc_ker_ck_input to each; the clock reaching the analogue block is that clock divided by two after the programmable prescaler (RM0433 Rev 8, ADC clock scheme). ADC1 and ADC2 reach every pin below marked ADC12 and can sample at the same time; ADC3 reaches PC0, PC1 and the analogue-only pads.

| Net | Pin | ADC channel (Table 9) | Converters | Class |
|---|---|---|---|---|
| NTC_COF | PC0 (15) | ADC123_INP10 | ADC1, ADC2, ADC3 | FT_a |
| NTC_STM | PC1 (16) | ADC123_INP11 | ADC1, ADC2, ADC3 | FT_ha |
| NTC_WAND | PC4 (32) | ADC12_INP4 | ADC1, ADC2 | TT_a |
| STMP_AN | PC5 (33) | ADC12_INP8 | ADC1, ADC2 | TT_a |
| SPARE_AN2 | PA0 (22) | ADC1_INP16 | ADC1 | FT_a |
| CURR1_AN | PA2 (24) | ADC12_INP14 | ADC1, ADC2 | FT_a |
| CURR2_AN | PA3 (25) | ADC12_INP15 | ADC1, ADC2 | FT_ha |
| BREW_AN | PA6 (30) | ADC12_INP3 | ADC1, ADC2 | FT_a |

Eight conversion pins are placed. Eight remain free: PA1 (ADC1_INP17), PA4 (ADC12_INP18, also DAC1_OUT1), PA5 (ADC12_INP19, also DAC1_OUT2), PA7 (ADC12_INP7), PB0 (ADC12_INP9), PB1 (ADC12_INP5), and the analogue-only pads PC2_C (ADC3_INP0, INN1) and PC3_C (ADC3_INP1), which reach ADC3 only. PB1 and PA1 stay free as the dictionary says (the voltage and supply-current measurement became the AMC131M02's digital link); PA7 and PB0 are the allocation record's direct group-head instrumentation inputs. The converters' supply is `+3V3A` (VDDA) and their reference is `VREF+`, tied to `+3V3A` through the 0 ohm link R302, so a ratiometric thermistor divider referenced to `+3V3A` reads against the same rail the converter uses; the owner of those dividers decides whether to use it.
