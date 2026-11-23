# Order record, main board

**Status of this file:** the order-time record of this board for `SOL-HW-CONTROLLER-BOARDS-ORDERED`, written ahead of the order. Every row marked **pending** or **OWNER ACT** has not been done: nothing here is a preview, a quote, a manufacturer's answer or a confirmation, and none was made up. The preview, the quote, the laminate answer, the via-finish answer, the order and the payment are the owner's or the manufacturer's-account acts, and the rows name each. Beside this file: `production-files-check.md`, the per-part and per-layer judgement against the preview.

## Production files and the manufacturer's preview (SOL-HW-CONTROLLER-BOARDS-ORDERED.C1)

Both boards ride in one order and one parcel, so each board's preview is judged on its own and the quote and the running total are weighed once for both. The part-by-part table and the layer table of this board are in `production-files-check.md` beside this file; payment waits until every row of both boards' tables matches.

The files are generated from the committed design with the method's ordering step (`kicad-cli pcb export pos`, then `production_files.py fetch-footprints`, `placement` and `parts-list`, each writing a full set and a surface-mount set, then `kicad-cli pcb export gerbers` and `drill`, and `production_files.py render`) and are never edited by hand.

| Item | State |
|---|---|
| Production files exported from the commit | **pending**: export from the commit the layout review closed on; record it in `production-files-check.md` (Board judged) |
| Assembler's footprints fetched (`fetch-footprints`, outside the repository) | **pending**: run on the order date |
| Order-date availability record, `availability-record.yaml` beside this file (written from the assembler's catalogue search service on the order date; both commands refuse to run without it) | **pending**: not written; the order date is not yet set |
| Placement file, both sets, each part in the assembler's footprint frame | **pending**: run `placement --unavailable availability-record.yaml`; a part it refuses is recorded as an override with its reason |
| Parts list, both sets | **pending**: run `parts-list --catalogue catalogue-extract.yaml --unavailable availability-record.yaml`; each row's comment is the one the catalogue extract holds for its number, and a number with no entry or no comment, or held twice, fails it |
| U401 catalogue number at the order | The files name C114409 (STM32H743VIT6), which showed stock 0 on 2026-11-22. The owner swaps the line on the order to C5271084 (STM32H743VIT6TR), the same device: ST's ordering key (DS12110 Rev 11, section 9) gives `TR` as tape-and-reel packing and no character as tray, so the pinout, package and rating are one device's. The JLCPCB listing price read 2026-11-22 was 12.09 USD each for C5271084 against 10.37 USD last known for C114409. **Owner decision, recorded for a reorder:** the cheaper listing is preferred when it is in stock. The owner makes the swap on the order, so this record and the parts specification keep C114409; the placement override for U401 was fitted to C114409's footprint (residual 0.125 mm) and the footprint of C5271084 was not read. |
| Assembler's preview, each side, and its placement preview | **OWNER ACT, not done**: upload the archive, the placement file and the parts list to the manufacturer's order page and go no further than its preview; save the images with the date |
| Every placed part's row compared with the preview; every layer row | **pending the preview** |
| Rotation direction and origin convention the preview shows | **pending the first real preview**; recorded with that board's check in `production-files-check.md` |
| Quote of the order (both boards) | **OWNER ACT, not done**: the quote shown at upload, with its date; none has been read |
| Declared spend | 250 USD (`docs/sunbeam-em7000/component-specification.md`) |
| Running total before this order | 0 USD bought to date; block-level estimate of the first order 149.68 USD (`docs/sunbeam-em7000/controller-board-cost-estimate.md`) |
| Quote against the running total | **pending the quote**: running total after the order = running total before + the quote; entered in the component specification's running-total table and weighed against 250 USD before payment |

**Who fits each position.** A position with a catalogue number is `assembler` or `owner` in `parts-specification.yaml`; one with no number is `none` where it is not a part (a test point, a hole, a fiducial, a net tie) and `owner` where it is a real part the owner supplies and fits. The board check refuses `none` on a numbered position and `assembler` on an unnumbered one. The wall board's all-owner default is recorded in its own ordering record.

## The order-date catalogue read (SOL-HW-CONTROLLER-BOARDS-ORDERED.C3)

Read the manufacturer's public catalogue on the order date for each part below, which the board design accepted below the rating it needs, and record what is found against each before payment. A part found in stock that meets the rating is brought to the schematic leaf as an amendment before the board is ordered. No read has been made: the criterion asks for the order date, and a read made earlier would not state it.

| Position | Catalogue number | Part as drawn | Rating needed | What to look for | Found at the order date (source, read date) |
|---|---|---|---|---|---|
| K731, K741 | C91370 | HF32FA-G/005-HSL1 valve relay, 250 VAC contacts | contacts rated 253 V rms or higher | a 5 V relay, same footprint and contact current, rated at or above 253 V rms, in stock and assembly-capable | **pending**: not read |
| F701, F711, F731 | C3131 | 5x20 mm slow-blow, 250 VAC | rated 253 V rms or higher | a 5x20 mm fuse of the same current rated at or above 253 V rms, in stock | **pending**: not read |
| F101 | C22447834 | 10 A 250 VAC entry fuse | rated 253 V rms or higher | a fuse of the same size and rating at or above 253 V rms, in stock | **pending**: not read |
| T701, T711 with U701, U711 | C2971290 with C899826 | T835-800B triac (800 V) with MOC3052SVM opto-triac (600 V) | a triac and opto-triac pair rated 800 V | an 800 V opto-triac driver pin-compatible with U701 and U711 that is in stock | **pending**: not read |

The limit this board's records state for each figure a part's maker does not publish, read on 2026-11-22 against `bring-up-provision.md` and the accepted exceptions of `derating-policy.yaml`: the entry fuse F101, the branch fuses F701, F711 and F731 and the valve relays K731 and K741 are each held in an accepted exception that names the figure (357.8 V peak against the 353.553 V peak of their 250 VAC listing, about 1 % over) and what bounds it; R102 and R104 (a half-swing against a 200 V rating) and the clamps D701 and D711 (400 V stand-off against 357.8 V) are held the same way; the retained tabs and the link JP101 (TE publishes no rating) are held in the bring-up row M18, whose limit is a rise of at most 40 K over the surrounding air (the 110 degC cap less the 70 degC air assumed), and the module inrush and entry fuse I2t in row M11, whose limit is an integral of at most 50 A2s, both with their source in `open-items.md`. Each states its limit and carries it to a bring-up measurement. Confirmed on that date: no figure read there lacks a limit. What stays **pending** is only the order-date catalogue read of the table above, which the criterion dates to the order.

## Via finish (SOL-HW-CONTROLLER-BOARDS-ORDERED.C4)

The board has 6 copper layers. The via sizes it uses, counted on 2026-11-22 from the `(via ...)` items of the committed `main-board.kicad_pcb` with the repository's s-expression reader (`hardware/tools/sexpr.py`), the copper layers counted from the file's `layers` list (each count is also asserted by `hardware/tools/tests/test_ordering_records.py`):

| Via diameter / hole (mm) | Count |
|---|---|
| 0.60 / 0.30 | 466 |
| 0.70 / 0.30 | 6 |
| 0.75 / 0.30 | 69 |

The manufacturer's record (`docs/board-manufacturer-jlcpcb.md`, *Via filling by default at 6 layers and over*, read 2026-11-05) states that vias are filled and plated over by default at six layers and over, compatible with via diameters of 0.15 to 0.55 mm, and says nothing of how a via over 0.55 mm is finished at six layers. All three sizes this board uses (0.60, 0.70 and 0.75 mm) are above 0.55 mm, so **no finish is stated by the published page for any of them**: each needs the manufacturer's written answer before payment.

| Via diameter / hole | Finish the manufacturer states | Source | Read on |
|---|---|---|---|
| each size above | **pending**: a page of the manufacturer's capabilities, or its support's written answer, stating the finish | | |

A diameter whose finish is not stated is reported here and the order is not paid for until it is.

## Laminate (SOL-HW-CONTROLLER-BOARDS-ORDERED.C5)

The separation basis reads the material group III column at pollution degree 2, which covers groups IIIa and IIIb alike, so a comparative tracking index certificate is not a precondition to payment. The basis is the signed record `hardware/sunbeam-em7000/separation-basis.yaml` and is not restated here.

**Written request to the manufacturer's support (OWNER ACT: send, then record the date):**

> Please state the laminate maker and product (the core and prepreg family and the TG grade) that will be used for the order the owner names when sending this request and, if you hold one, a certificate or test report of that laminate's comparative tracking index to IEC 60112. We do not need the certificate to proceed.

**Laminate note carried on the order (OWNER ACT: paste into the order's remarks, record the date):** the laminate line of this board's `fabrication-notes.md`.

| Item | Date | State |
|---|---|---|
| Request sent | | **pending, owner** |
| Laminate note on the order | | **pending, owner** |
| Manufacturer's answer, or the absence of one | | **pending**; record the text with its source and date |

An answer naming a laminate whose published comparative tracking index is below 100, which falls in no material group, is reported here and the order is not paid for until the owner re-declares the basis; so is a pollution degree 3 fallback taken without an index of 175 or more recorded.

## Pin functions (SOL-HW-CONTROLLER-BOARDS-ORDERED.C9)

Every output, sensor and serial channel the firmware drives or reads on the main board's controller. Each channel is read at the pin the board gives it in the pin allocation record, against the function the main board's controller pin table lists for that pin (`main-board/controller-pin-table.md`, DS12110 Rev 11 Table 9, LQFP100 column). The reading was made on the commit that holds this file; every channel below carries its function, so none stops the order. Whether the firmware's own tables spell the same pin is the firmware-side check's, after the order. The crystal pins (HSE and LSE) and the serial-wire output are not firmware channels and are not listed.

| Channel | Pin | Function the pin table lists | Function the channel needs | Carries it |
|---|---|---|---|---|
| key1 | PE2 | GPIO (panel key/indicator line, owner D) | plain GPIO line | yes |
| key2 | PE3 | GPIO | plain GPIO line | yes |
| key3 | PE4 | GPIO | plain GPIO line | yes |
| key4 | PE5 | GPIO | plain GPIO line | yes |
| key5 | PE6 | GPIO | plain GPIO line | yes |
| pump_s_gate | PA8 | TIM1_CH1 AF1 (MCO1 is AF0) | timer output | yes |
| pump_c_gate | PA9 | TIM1_CH2 AF1 | timer output | yes |
| anode_gate | PB5 | TIM3_CH2 AF2 | timer output | yes |
| gauge_step1 | PD14 | TIM4_CH3 AF2 | timer output | yes |
| gauge_step2 | PD15 | TIM4_CH4 AF2 | timer output | yes |
| heat_c_drv | PD11 | GPIO output | plain output | yes |
| heat_s_drv | PD12 | GPIO output (I2C4_SCL, LPTIM1_IN1 not used) | plain output | yes |
| valve_2w_drv | PD13 | GPIO output (I2C4_SDA not used) | plain output | yes |
| valve_3w_drv | PB12 | GPIO output (SPI2_NSS AF5 not used) | plain output | yes |
| gauge_dir1 | PD8 | GPIO output | plain output | yes |
| gauge_dir2 | PD9 | GPIO output | plain output | yes |
| gauge_rst | PD10 | GPIO output | plain output | yes |
| buzzer | PB2 | GPIO output | plain output | yes |
| pol_out | PC7 | GPIO output, push-pull (proof of life) | plain output | yes |
| lowwater_k | PE12 | GPIO output (open-drain use, owner D) | plain output | yes |
| pt1_cs | PD0 | GPIO output | plain output | yes |
| pt2_cs | PD1 | GPIO output | plain output | yes |
| amc_cs | PA15 | GPIO output (JTDI AF0 at reset, internal pull-up, until firmware releases it) | plain output | yes |
| amc_reset | PC8 | GPIO output | plain output | yes |
| wt1_clk | PD6 | GPIO output | plain output | yes |
| wt2_clk | PD3 | GPIO output | plain output | yes |
| ntc_cof | PC0 | ADC123_INP10 | converter input | yes |
| ntc_stm | PC1 | ADC123_INP11 | converter input | yes |
| ntc_wand | PC4 | ADC12_INP4 | converter input | yes |
| stmp_an | PC5 | ADC12_INP8 | converter input | yes |
| brew_an | PA6 | ADC12_INP3 | converter input | yes |
| curr1_an | PA2 | ADC12_INP14 | converter input | yes |
| curr2_an | PA3 | ADC12_INP15 | converter input | yes |
| spare_an2 | PA0 | ADC1_INP16 | converter input | yes |
| zc_in | PA10 | TIM1_CH3 AF1 | timer-capture or edge-capable input | yes |
| flow_in | PB10 | TIM2_CH3 AF1 (32-bit timer input capture; also USART3_TX AF7) | timer-capture or edge-capable input | yes |
| amc_drdy | PC6 | GPIO input (EXTI line 6) | timer-capture or edge-capable input | yes |
| wt1_data | PD5 | GPIO input | plain input | yes |
| wt2_data | PD2 | GPIO input | plain input | yes |
| tank_level | PE0 | GPIO input | plain input | yes |
| knob_hot | PE13 | GPIO input | plain input | yes |
| knob_steam | PE14 | GPIO input | plain input | yes |
| mains_pres_c | PE15 | GPIO input (wall-board mains-presence confirm through R764, 27 kohm, with R765, 82 kohm, to GND) | plain input | yes |
| mains_pres_s | PB11 | GPIO input (wall-board mains-presence confirm through R774, 27 kohm, with R775, 82 kohm, to GND) | plain input | yes |
| display_tx | PB6 | USART1_TX AF7 (display link, header J522 pin 3); also I2C4_SCL AF6, I2C1_SCL AF4 | serial bus pins | yes |
| display_rx | PB7 | USART1_RX AF7 (display link, header J522 pin 4); also I2C4_SDA AF6, I2C1_SDA AF4 | serial bus pins | yes |
| spi3_sck | PC10 | SPI3_SCK AF6 | serial bus pins | yes |
| spi3_miso | PC11 | SPI3_MISO AF6 | serial bus pins | yes |
| spi3_mosi | PC12 | SPI3_MOSI AF6 | serial bus pins | yes |
| stm_scl | PB8 | I2C1_SCL AF4 (also UART4_RX AF8) | serial bus pins | yes |
| stm_sda | PB9 | I2C1_SDA AF4 (also UART4_TX AF8) | serial bus pins | yes |
| usb_dm | PA11 | OTG_FS_DM (USB_FS DM), alternate function after firmware configures it | serial bus pins | yes |
| usb_dp | PA12 | OTG_FS_DP (USB_FS DP), alternate function after firmware configures it | serial bus pins | yes |
| swdio | PA13 | JTMS/SWDIO AF0 | serial bus pins | yes |
| swclk | PA14 | JTCK/SWCLK AF0 | serial bus pins | yes |

## The placed order (SOL-HW-CONTROLLER-BOARDS-ORDERED.C8)

Filled in after the owner reports the order placed; placing the order and paying are the owner's acts and receipt is the received-boards leaf's.

| Item | Record |
|---|---|
| Manufacturer's order confirmation (number and date) | **pending, owner** |
| Set of production files uploaded (full or surface-mount, with the placement file's and parts list's names) | **pending, owner** |
| Fitting choice taken (who fits the through-hole parts) | **Working default recorded in `parts-specification.yaml`: the assembler fits the through-hole parts as well as the surface-mount parts** (the owner's statement that the manufacturer will likely fit them, depending on final cost). The final choice is taken after both quotes (full set against surface-mount-only set) are seen. Flipping it is an edit to the `fitted_by` values of the through-hole positions in this board's parts specification record, followed by regenerating both file sets. **Final choice: pending, owner** |
| Cost difference between the two options (full set against surface-mount-only set) | **pending the two quotes.** The cost estimate's basis (`docs/sunbeam-em7000/controller-board-cost-estimate.md`, Economic assembly) prices the surface-mount-only assembly at 26.98 USD, of which 15.35 USD is Extended feeder loading for 5 types at 3.07 USD; each further Extended through-hole type the assembler fits adds 3.07 USD of loading at that rate (14 types: 42.98 USD), plus its joints and parts charges, against the owner's soldering time. That is an estimate, not a quote. The choice is weighed on the difference between the two quotes. **Pending, owner** |
| Cost paid | **pending, owner** |
| Running total after this order (entered in the component specification) | **pending** |
