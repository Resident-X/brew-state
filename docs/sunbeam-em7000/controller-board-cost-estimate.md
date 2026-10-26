# Controller boards: block-level cost estimate

What the four things this machine's retrofit has made, bought or had assembled cost, estimated from the manufacturer's charges and weighed against what remains of the declared spend before any board is designed in detail. The four are the main board, the heater wall board, the mains entry's fuse and varistor parts (carried on the main board, § Mains entry) and the steam-path assembly; the division of `controller-board-division.md` § Every function has one owner has two off-board assemblies, the heater wall board and the steam-path assembly, and the machine keeps its fixed mains lead with no inlet. The mains entry is a set of parts on the main board (§ Mains entry) and the steam-path assembly is sourced by the owner, outside the board orders (§ Steam-path assembly, owner-sourced), so every total is shown without that assembly (*the board orders*, which is what the declared spend counts) and with it (*the board orders and the owner-sourced assembly*, for information). This is for the machine in `docs/sunbeam-em7000/` and its builder's country (Australia), so it lives in the machine's folder; a builder of another machine, or in another country, re-prices it by the steps in § Re-pricing it in another market.

**This is a derived view, and its sources govern.** Every figure is read off a source named beside it with the date it was read, or is marked as an estimate with its basis. The manufacturer's limits and charges are `docs/board-manufacturer-jlcpcb.md`; the parts, their counts and the shipping destination are `controller-board-design-constraints.md` § Manufacturer stock and price, per channel; the boards, their outlines, layer counts and hand-fitted parts are `controller-board-division.md`; the declared figure is `component-specification.md`. Where this file and one of those disagree, the source is right and this file is corrected. A figure that has moved is replaced here, not annotated.

**What this record is not.** It is not the quoted order cost each board's design task records before ordering. That quote prices a finished design from its own files and replaces the estimate's inferred and estimated lines; § Marks ended and re-pointed says which lines wait for it.

## Evidence grades

The grades are those of `controller-board-design-constraints.md` § Evidence grades and `docs/board-manufacturer-jlcpcb.md` § Evidence grades, with two more used here, each as `controller-board-division.md` uses them.

| Grade | Meaning in this record |
|---|---|
| **published unverified, read at source** | The figure as the manufacturer's own service or page gives it, read on the date shown. Nothing in this project has bought or measured the part or order the figure prices. |
| **inferred** | Worked out from other figures with the working shown. |
| **computed** | Arithmetic on named figures, shown. |
| **estimate** | A figure no source read gives. Its basis is stated beside it, so a reader can replace it with a read figure. |
| **unmeasured** | A figure the sources do not give and this record does not estimate; the entry says how it is read. |

## What is settled before pricing

- **Currency.** United States dollars, the manufacturer's billing currency (`docs/board-manufacturer-jlcpcb.md`, *Prices*) and the declared figure's (`component-specification.md` § The component list, *Declared spend: 250 USD*). The only non-dollar prices are the earlier design's Australian-dollar estimates for the owner-sourced steam-path assembly (§ Steam-path assembly), converted at the exchange rate read on 2026-10-24 (§ Sources read).
- **The count the declared spend takes.** What the owner pays for the minimum order: 5 boards fabricated and 2 assembled for each board JLCPCB makes (`docs/board-manufacturer-jlcpcb.md` § Price bands and the fabrication order, *Minimum fabrication quantity*; § Assembly limits, *Minimum number of assembled boards*), the machine-placed parts for those 2, the hand-fitted parts for **one** set (one machine, the owner's statement below), and one steam-path assembly. The cost per machine is shown beside every total: two assembled boards are two machines' worth of boards, so a per-machine figure halves what the manufacturer's order places and adds one hand-fitted set (with its shipping and tax share) and the owner-sourced assembly in full.
- **The configuration priced, and the owner's decision of 2026-10-25.** The owner decided, on 2026-10-25, to hand-solder the through-hole parts that drive the assembly cost and to have the manufacturer assemble only the minimal set of surface-mount parts. So: the main board, one 4-layer board of 131.0 × 125.0 mm, 1 oz copper, leaded HASL, 1.6 mm, as drawn, is fabricated by the manufacturer and assembled by it under Economic assembly **for its surface-mount parts only**, the five Extended types (the microcontroller, the triac C256462, the optocoupler, the shunt and the 120 kΩ mains-sense resistor) and the Basic surface-mount parts. Its 14 through-hole Extended types (the supply module, the pump opto-triac C8965, the interlock relay, the valve relay, the fuse holder, the fuse clip, the 6.3 mm tab and seven header types) are bought separately and soldered by the owner, for one machine's set: the manufacturer charges no loading fee, no hand-soldered joints and no hand-soldering labour for them, and their parts stay priced at the catalogue prices. The heater wall board, a 57.0 × 42.5 mm body with the bracket's two mounting ears (89.0 mm over all, 2 662.5 mm²), 2 layers, is fabricated only, at its band price, in the main board's order, with no assembly order; its parts, one set, are bought and soldered by the owner. The steam-path assembly is sourced by the owner and the mains entry is hand-fitted parts on the main board (the owner's statements below). D10 of the division record is therefore decided; D13 (2 oz copper) is not drawn and is priced as a difference in § Weighed against the declared spend. **The pump opto-triac is priced as the DIP-6 part C8965** (a through-hole package, § What the library class allows), so it is hand-fitted; a surface-mount variant, if the board's design task chooses one, would be machine-placed and add back one Extended type, 3.07 USD, and is not priced. The division record counts the same 19 Extended types, 5 machine-placed and 14 hand-fitted, and records D10 as decided on 2026-10-25.
- **The owner's statements of 2026-10-25, recorded as the owner's.** The owner, David Baker, stated on 2026-10-25:
  1. *One hand-fitted set.* The owner hand-solders **one** board's set of the through-hole parts, and the heater wall board: the hand-fitted parts are bought for one set (one machine), not two. The manufacturer still assembles the surface-mount parts of the minimum 2 boards, so the machine-placed parts, setup, stencil and joints stay as priced. The hand-fitted parts are charged at one set under the per-part rule of § The two per-part numbers.
  2. *Owner-sourced non-board items.* The owner sources the non-board items: the steam-path assembly (pressure transducer, tee, drop-leg tube, thread adaptor). It is not on the manufacturer's order and not in the board orders' total; it stays in the estimate as a labelled line, because the division names it and an assembly the division names may not be left out.
  3. *The mains harness is not changed: the owner's ruling.* The machine keeps its existing fixed mains lead: the supply cord goes straight to the main board's mains tabs 2 and 3 as on the original board, with no appliance inlet and no bought inlet filter. This record prices that arrangement as the declared one (§ Mains entry); the division record's decision list no longer holds it as pending (`controller-board-division.md` § Owner intent carried in, § The fuses).
  4. *The heater wall board stays a self-contained carrier*: the opto-triacs, their gate resistors, the three-way header, the varistors and the blade terminals, with the triacs, by the owner's stated intent, standing on a right-angle heat-spreader bracket that is fixed to the board and bolted to the wall (a cut and bent plate the owner makes or sources: it is not in the catalogue and is not priced here; a few dollars at most, an estimate whose basis is the owner's own fabrication); the triacs past the board's short edge, or wired at a distance, are the other forms, weighed against it in `controller-board-division.md` § The heater wall board, *The bracket*. The heater parts stay off the main board. If the edge form is chosen the board is about 10 mm shorter, in the same price band. Its pricing is unchanged: fabrication 4.00 USD, one set of parts.
- **The owner's answers of 2026-10-26, recorded as the owner's.** The owner, David Baker, answered on 2026-10-26 two questions about what the declared 250 USD counts:
  1. *The declared 250 USD excludes the items the owner sources*, the steam-path assembly (pressure transducer, tee, drop-leg tube, thread adaptor). They are priced here for completeness and are not counted against the declared figure.
  2. *The declared 250 USD does not count a likely second spin.* It covers the first order of the board orders only.
- **Shipping.** To Australia, by the cheapest method the manufacturer's shipping calculator quotes at the order's chargeable weight, with the other methods listed (§ Shipping). One parcel, the hand-fitted parts assumed ordered into it. The owner-sourced assembly is not in the parcel and has no shipping line.
- **Import tax.** An estimated line with its stated basis, counted in the total, because it is spend the build adds (§ Import tax).
- **Parts at the build quantity.** For the machine-placed parts, one machine's count of the part times 2 (`controller-board-design-constraints.md` § Manufacturer stock and price, per channel, *Prices, breaks and the build quantity*); for the hand-fitted parts, one machine's count (one set). Each is raised to the part's minimum quantity where the library service gives one (§ The two per-part numbers, § Parts).

## Sources read

| Source | Address | What was taken | Read |
|---|---|---|---|
| Parts library search service | https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2 (the service the page https://jlcpcb.com/parts calls), one request a part number | Library class, stock, unit price at the smallest break, and the two per-part numbers the service returns, `leastPatchNumber` and `lossNumber` | 2026-10-24, about 20:30 UTC |
| Shipping calculator service | https://jlcpcb.com/api/overseas-core-platform/shoppingCart/queryOrderShippingVo (the service the page https://jlcpcb.com/shipping calls), body `chargeWeight` in kg and `countryCode` AU | Each method's cost and delivery time at nine weights | 2026-10-24, about 20:33 UTC |
| PCB Assembly Cost: What Does the Price Include? | https://jlcpcb.com/help/article/pcb-assembly-price, last updated on the page 2026-10-22 | Every assembly charge of § Assembly charges of the manufacturer record, compared line by line with it; only the panel charge changed, so the other rows are re-dated by comparison, not by a fresh quote | 2026-10-24 |
| Parts library search service, minimum-quantity re-read | the same service, `POST` body `{"keyword":"C3131","currentPage":1,"pageSize":10,"searchSource":"search"}` with the part number as keyword, one request a part | `leastPatchNumber`, `lossNumber`, class, stock and smallest-break price of the 14 hand-fitted parts and the four mains-entry parts (§ The two per-part numbers) | 2026-10-25, 01:25–01:26 UTC |
| Parts library search service, mains-entry and filter catalogue read | the same service, one request a keyword | Fuse clips, fuses, X2 and Y2 capacitors, varistors, common-mode chokes and filter modules, inlets (§ Mains entry) | 2026-10-25, about 00:02–00:06 UTC |
| EasyEDA component service | https://easyeda.com/api/products/<LCSC part number>/components?version=6.4.19.5, the service the vendor's footprint editor calls; the `packageDetail` pad records | Pad shape, size, drill and pitch of the mains-entry parts, in the service's unit of 0.254 mm (10 mil), checked on C22447845, whose pad pitch of 94.488 units × 0.254 = 24.00 mm matches its footprint name `P24.00` | 2026-10-25 |
| Parts library search service, catalogue read | the same service, one request a keyword | Library class, stock and price of the 14 parts priced, the seven header families, the shunt, and the Basic and Preferred alternatives (§ What the library class allows) | 2026-10-25 |
| PCBWay | its public pages, https://www.pcbway.com | Prices could not be read: assembly and fabrication prices need a calculator run; no public parts catalogue or application interface was found | 2026-10-25 |
| Exchange rate | https://open.er-api.com/v6/latest/AUD, the service's own update time 2026-10-24 00:02 UTC | 1 AUD = 0.70296 USD | 2026-10-24 |
| The manufacturer record | `docs/board-manufacturer-jlcpcb.md` | Fabrication price bands and the 103 × 103 mm points, the extra charges, the assembly-service limits | Each entry's own *Read* date, 2026-10-13 |
| The earlier design's bill of materials | `docs/sunbeam-em7000/controller-design/control-system-bom.csv`, columns *Qty* and *Cost_AUD_ea* | The Australian-dollar estimates of the mains-entry and steam-path assemblies' parts. The bill says these prices are estimates not looked up | The bill's own dates |

**What was tried and did not answer.** The fabrication price at the main board's own outline is read at the quote, https://cart.jlcpcb.com/quote. Its cost service (`.../shoppingCart/calculationGoodsCostsNew`, 2026-10-24) answers HTTP 200 and refuses every request body tried with "Parameter exception"; the page's own script builds the request from an uploaded design file and the options chosen on it, and no design file exists yet. The price is therefore inferred from the manufacturer's two published points (§ Main board, *Fabrication*) and re-pointed to the design task's quoted order. The JLCONE application's prices are not readable by a headless request. The pages tried for the rate of the Australian goods and services tax (the tax authority's and the border force's, 2026-10-24) returned HTTP 404.

## The two per-part numbers

The library service returns, for each part, `leastPatchNumber` and `lossNumber`. The pages read do not define them. This record **infers** that the first is the least quantity the manufacturer places for that part and the second the spares it adds for placement loss, which is the rule its assembly FAQ states in words (*Minimum quantity charged per part, any class*, `docs/board-manufacturer-jlcpcb.md` § Parts library classes and their fees). It charges, for each part,

> charged quantity = the larger of (build quantity, `leastPatchNumber`) + `lossNumber`

and prices that quantity at the smallest break's unit price, which every charged quantity below falls inside. A wrong reading moves cents, not dollars: the dearest charged parts here are priced at counts of one to four.

**The numbers for the hand-fitted parts, read from the library service on 2026-10-25 at 01:25–01:26 UTC** (one request a part number; `leastPatchNumber` / `lossNumber`; every part Extended, `componentLibraryType` `expand`; the stock and smallest-break price agreed with the earlier reads), and the charged quantity at one set:

| Part | JLCPCB part | `leastPatchNumber` / `lossNumber` | One set's count | Charged quantity |
|---|---|---|---|---|
| Logic-supply module | C6280121 | 0 / 0 | 1 | 1 |
| Pump opto-triac | C8965 | 2 / 0 | 2 | 2 |
| Interlock relay | C5318991 | 2 / 0 | 1 | 2 |
| Valve relay | C91370 | 0 / 0 | 2 | 2 |
| Fuse holder | C3131 | 2 / 0 | 3 | 3 |

**The numbers for the machine-placed parts, read from the same service on 2026-10-25 at 01:41:29–01:41:37 UTC** (one request a part number; the estimated shunt and unlisted passives have no part and no entry). Each reproduces the charged quantity of § Parts, build quantity being two boards' count:

| Part | JLCPCB part | `leastPatchNumber` / `lossNumber` | Build quantity | Charged quantity |
|---|---|---|---|---|
| Microcontroller | C114409 | 0 / 0 | 2 | 2 |
| Pump triac | C256462 | 0 / 0 | 4 | 4 |
| AC-input optocoupler | C108051 | 2 / 2 | 2 | 4 |
| Mains-sense resistor 120 kΩ | C5126146 | 5 / 2 | 4 | 7 |
| Crystal 8 MHz | C115962 | 5 / 0 | 2 | 5 |
| Crystal 25 MHz | C9006 | 5 / 4 | 2 | 9 |
| Transistor 2N7002 | C8545 | 10 / 5 | 4 | 15 |
| Transistor MMBT3904 | C20526 | 10 / 5 | 2 | 15 |
| Transistor S8050 | C2146 | 10 / 5 | 2 | 15 |
| Diode 1N4148W | C81598 | 15 / 14 | 6 | 29 |
| P-channel switch AO3401A | C15127 | 5 / 4 | 2 | 9 |
| Regulator AMS1117-3.3 | C6186 | 2 / 0 | 2 | 2 |
| Resistor 10 kΩ 0603 | C25804 | 20 / 10 | 18 | 30 |
| Capacitor 100 nF 0603 | C14663 | 20 / 10 | 66 | 76 |
| Fuse clip | C3130 | 2 / 5 | 6 | 11 |
| 6.3 mm tab | C20626104 | 2 / 4 | 8 main, 6 wall | 12 main, 10 wall |
| Wall board triac | C9100 | 0 / 0 | 2 | 2 |
| Wall board opto-triac | C10797 | 2 / 0 | 2 | 2 |
| Wall board varistor | C49072860 | 2 / 1 | 4 | 5 |
| Entry fuse clip (mains entry) | C151075 | 2 / 2 | 2 | 4 |
| Entry fuse (mains entry) | C22447845 | 2 / 0 | 2 | 2 |
| Mains-entry varistor | C8852 | 2 / 1 | 1 | 3 |
| Mains-entry X2 capacitor | C489079 | 2 / 1 | 1 | 3 |

## Main board

One board, 4 layers, 131.0 × 125.0 mm (16 375 mm²), 1 oz, leaded HASL, 1.6 mm, Economic assembly; five fabricated, two assembled.

### Fabrication

The manufacturer publishes a board of this size as an engineering fee plus a board fee and no table of either; its two published points at 103 × 103 mm (10 609 mm²) for 4 layers are an engineering fee of 25.00 USD and a board fee of 6.60 USD (`docs/board-manufacturer-jlcpcb.md` § Price bands and the fabrication order, read 2026-10-13). The division record infers the board fee at another area as proportional to it (`controller-board-division.md` § Candidate divisions); this record takes the same inference.

25.00 + 6.60 × 16 375 / 10 609 = 25.00 + 10.19 = **35.19 USD**. Grade: inferred from published points; unmeasured at the quote. The two-layer fallback of the division (`controller-board-division.md` § Layer counts) is 4.00 + 5.20 × 16 375 / 10 609 = 4.00 + 8.03 = 12.03 USD by the same inference, 23.16 USD less.

No other fabrication charge arises at the drawn configuration, each checked against the manufacturer's page of extra charges:

- The board is far under 650 cm² (it is 163.75 cm²), so neither the large-board fabrication charge nor the assembly large-board charge of 57.46 USD applies.
- The eight slots are 202 mm of slot path, 12.3 m of slot path per m² of board against the 80 m per m² the routing charge starts above (`controller-board-division.md` § Zones and the barrier), and no slot is narrower than the 1.0 mm the manufacturer makes, so no routing charge arises.
- One design in the file, so no several-designs charge; no expedited build time is ordered, so neither the expedited fee nor its order-area multiplier is charged; the options are the quote's defaults, so the special-process charge is not expected, though the quote confirms that.

### Assembly

Economic assembly of the surface-mount parts only, charges as the price page gives them (read 2026-10-24; § Sources read). The count of unique Extended types the manufacturer places is **5**: the microcontroller, the triac C256462, the optocoupler, the shunt and the 120 kΩ mains-sense resistor. The 14 through-hole Extended types (the supply module, the pump opto-triac C8965, the interlock relay, the valve relay, the fuse holder, the fuse clip, the tab and seven header types) are the owner's, hand-soldered, and carry no manufacturer charge (§ What is settled before pricing). With them the main board has 19 unique Extended types, 5 placed by the manufacturer and 14 fitted by the owner, as the division record counts them; the 120 kΩ resistor is an Extended part of the supply-timing front end (§ What the library class allows), and every header is Extended, as the 2026-10-25 read found.

| Charge | Working | USD |
|---|---|---|
| Setup fee, once an order | 8.18 | 8.18 |
| Stencil | 1.53 | 1.53 |
| Extended feeder loading | 5 types × 3.07 | 15.35 |
| Machine-placed joints | about 600 a board × 2 boards × 0.0016 (estimate: the division counts "a few hundred"; 600 is a round figure above the parts listed, not an itemised count, so it does not count the opto-triac's pins and is kept: its 12 hand-soldered pins on two boards would be 0.04 USD at 0.0016, inside the round figure's margin) | 1.92 |
| **Assembly at the manufacturer** | 8.18 + 1.53 + 15.35 + 1.92 | **26.98** |

No X-ray inspection is charged: the microcontroller is a leaded LQFP and nothing on the board is a BGA or leadless part. The 0.45 USD placement-confirmation service is not ordered. The single-board surcharge and the two storage fees are charges of Standard assembly only (`docs/board-manufacturer-jlcpcb.md` § Assembly charges), so none arises under Economic.

### Parts

Prices, classes and the two per-part numbers read 2026-10-24 from the library service (the class re-read 2026-10-25, § What the library class allows; the hand-fitted parts' numbers re-read 2026-10-25, § The two per-part numbers); counts are one board's, from `controller-board-division.md` and `controller-board-design-constraints.md` § Manufacturer stock and price, per channel. The parts the manufacturer places are priced at the build quantity of two boards, below; the hand-fitted parts are priced at one set, after it. The microcontroller's price here is 10.6814 USD, read 2026-10-24 (`controller-board-design-constraints.md` *Controller* row; `component-specification.md`). The interlock relay is priced as the 12 V variant, as the division does, because the 5 V variant's number is not recorded. The channel parts the division names only as "proving candidates" are priced as those candidates; the design task for the board selects the fitted part.

| Part | JLCPCB part | Class | Count a board | Build quantity | Charged quantity | Unit price (USD, smallest break) | Cost (USD) |
|---|---|---|---|---|---|---|---|
| Microcontroller STM32H743VIT6 | C114409 | Extended | 1 | 2 | 2 | 10.6814 | 21.36 |
| Pump triac BTA204S-600B | C256462 | Extended | 2 | 4 | 4 | 0.8543 | 3.42 |
| AC-input optocoupler LTV-814S-TA1-A | C108051 | Extended | 1 | 2 | 4 | 0.1362 | 0.54 |
| Mains-sense resistor 120 kΩ 2512 | C5126146 | Extended | 2 | 4 | 7 | 0.0261 | 0.18 |
| Crystal 8 MHz | C115962 | Basic | 1 | 2 | 5 | 0.2462 | 1.23 |
| Crystal 25 MHz | C9006 | Basic | 1 | 2 | 9 | 0.0951 | 0.86 |
| Transistor 2N7002 | C8545 | Basic | 2 | 4 | 15 | 0.0161 | 0.24 |
| Transistor MMBT3904 | C20526 | Basic | 1 | 2 | 15 | 0.0116 | 0.17 |
| Transistor S8050 | C2146 | Basic | 1 | 2 | 15 | 0.0142 | 0.21 |
| Diode 1N4148W | C81598 | Basic | 3 | 6 | 29 | 0.0124 | 0.36 |
| P-channel switch AO3401A | C15127 | Basic | 1 | 2 | 9 | 0.0959 | 0.86 |
| Regulator AMS1117-3.3 | C6186 | Basic | 1 | 2 | 2 | 0.2048 | 0.41 |
| Resistor 10 kΩ 0603 | C25804 | Basic | 9 | 18 | 30 | 0.0022 | 0.07 |
| Capacitor 100 nF 0603 | C14663 | Basic | 33 | 66 | 76 | 0.0084 | 0.64 |
| Shunt resistor, 2512, 1 mΩ class, not chosen (estimate: 0.50 USD each) | none | Extended | 1 | 2 | 2 | 0.5000 | 1.00 |
| Passives and small semiconductors not listed above (estimate: about 150 parts a board at about 0.007 USD) | none | Basic | — | — | — | — | 2.00 |
| **Parts the manufacturer places** | | | | | | | **33.55** |

**Parts the owner fits by hand, one set** (one machine; charged quantity = the larger of (count, `leastPatchNumber`) + `lossNumber`, § The two per-part numbers):

| Part | JLCPCB part | Class | Count | Charged quantity | Unit price (USD, smallest break) | Cost (USD) |
|---|---|---|---|---|---|---|
| Logic-supply module IRM-20-5 | C6280121 | Extended | 1 | 1 | 6.3840 | 6.38 |
| Pump opto-triac MOC3052M | C8965 | Extended | 2 | 2 | 0.5892 | 1.18 |
| Interlock relay, priced as the 12 V variant HF115F-Q/012-1H | C5318991 | Extended | 1 | 2 | 3.2141 | 6.43 |
| Valve relay HF32FA-G/005-HSL1 | C91370 | Extended | 2 | 2 | 1.6169 | 3.23 |
| Fuse holder 5 × 20 mm | C3131 | Extended | 3 | 3 | 0.0847 | 0.25 |
| Fuse clip | C3130 | Extended | 6 | 11 | 0.0326 | 0.36 |
| 6.3 mm board tab (seven tabs and the return landing) | C20626104 | Extended | 8 | 12 | 0.0374 | 0.45 |
| Headers for the harnesses, seven types, 85 ways (estimate: 85 × 0.0204 USD a way, the dearer of the two rows read) | none | Extended | 85 ways | 85 ways | 0.0204 a way | 1.73 |
| **Hand-fitted parts of the 14 types** | | | | | | **20.01** |

6.38 + 1.18 + 6.43 + 3.23 + 0.25 + 0.36 + 0.45 + 1.73 = **20.01 USD**, bought separately. The mains-entry parts the owner also fits by hand to this board, 1.54 USD (§ Mains entry), are added to it: 20.01 + 1.54 = **21.55 USD**. The parts the manufacturer places and charges are 33.55 USD, the sum of the rows of the first table.

**The 6.3 mm board tab is C20626104, replacing C20626100.** The catalogue titles C20626100 (BZXC BTC-3-PCB485005D) "4.8 × 0.5 mm", a short-leg solder-in blade; "6.3" appears only in EasyEDA's footprint name (`TH-2_L6.3-W0.5`), read 2026-10-25, and in the blade-width attribute the library gives every part of the family. The harness's blade is 6.36 mm wide and 0.81 mm thick (`connector-pinouts.md` § The nine terminals), so that part does not fit it, and the division record replaces it (`controller-board-division.md` § What the owner fits by hand, *The tab that fits the harness*). The replacement is C20626104 (BZXC BTC-3-PCB634908T), whose maker's drawing gives a blade 6.3 ±0.2 mm wide and 0.8 mm thick (+0, −0.03), Extended, stock 14 453, `leastPatchNumber` 2 and `lossNumber` 4 as the part it replaces, read from the library service on 2026-10-26 and from the drawing the part's page links the same day. **What follows from it is recomputed:** the class and the charged quantities are unchanged, and the unit price at one to 99 is 0.0374 USD against 0.0351 USD, so the main board's twelve tabs cost 0.45 USD against 0.42, the wall board's ten 0.37 against 0.35, and each total, shipping share, tax, board order and per-machine figure below that rests on them moves by those cents (the hand-fitted set 20.01 USD against 19.98, the wall board's parts 2.88 against 2.86, the board orders 149.68 against 149.63).

The microcontroller's cost at the build count is 2 × 10.6814 = 21.36 USD plus its feeder loading, 3.07 USD, in the assembly table: 24.43 USD, against the 13.75 USD for one machine's part in `component-specification.md`'s *Controller* row (10.6814 + 3.07). That figure is contained in the main board's lines above and is not counted twice.

### Main board, first order

Fabrication 35.19 + assembly 26.98 + parts the manufacturer places 33.55 = **95.72 USD** at the manufacturer, plus the 21.55 USD of hand-fitted parts of one set with the mains-entry parts: 95.72 + 21.55 = **117.27 USD** before shipping and tax.

## Heater wall board

57.0 × 42.5 mm body with the bracket's two mounting ears along its wall edge, 89.0 mm over all and 2 662.5 mm², 2 layers, 1 oz, leaded HASL, within the lowest price band. All through-hole. By the owner's decision of 2026-10-25 the manufacturer fabricates it only, five boards in the main board's order (a separate design file in the same order, so it is not the charge for several designs in one file, `docs/board-manufacturer-jlcpcb.md` § Price bands and the fabrication order; that record does not say whether a second file in one order is charged, so **this is a quote check**: the order's quote with both files loaded), and the owner buys its parts, one set, and fits them by hand: no assembly order, so none of the setup, stencil, loading, joint or labour charges. It stays a self-contained carrier of the opto-triacs, their gate resistors, the three-way header, the varistors and the blade terminals, with the triacs standing on the right-angle heat-spreader bracket fixed to it and bolted to the wall (the owner's statement 4, § What is settled before pricing); the heater parts stay off the main board. Were the triacs past the board's short edge instead, the board would be about 10 mm shorter, in the same price band, so no price moves.

- **Fabrication.** The band price for 5 boards of 2 layers, leaded HASL, up to 102 × 102 mm: **4.00 USD** (`docs/board-manufacturer-jlcpcb.md` § Price bands and the fabrication order, read at the quote 2026-10-13, published unverified, read at source). Not re-read: the quote page takes no request without a design file. The page's JLCONE price for this band is 2.00 USD (same entry), which the estimate does not take (§ Marks ended and re-pointed).
- **Assembly.** None at the manufacturer. The five Extended types for this board (the triac C9100, the opto-triac C10797, the tab C20626104, the three-way header and the varistor C49072860) are the owner's to fit, with the 39 joints a board of division A11, so no manufacturer fee arises.
- **Parts, one set.** Charged quantity at one set, § The two per-part numbers. Triacs C9100: 2 × 0.8445 = 1.69. Opto-triacs C10797: 2 (minimum 2) × 0.2907 = 0.58. Tabs C20626104: 6 + 4 loss = 10 × 0.0374 = 0.37. Varistors 07D471K, C49072860: 4 + 1 loss = 5 × 0.0310 = 0.16 (read as Extended on 2026-10-25, the class the division now records; the class changes no figure for a hand-fitted part). Gate and other resistors: 8 × 0.0030 = 0.02, estimate. Three-way header: 3 ways × 0.0204 = 0.06, estimate. 1.69 + 0.58 + 0.37 + 0.16 + 0.02 + 0.06 = **2.88 USD**, bought by the owner. Triac and opto-triac prices read 2026-10-24, the per-part numbers 2026-10-25; the C9100 and C10797 counts follow the division, halved from the two-board build quantity.

4.00 + 2.88 = **6.88 USD** before shipping and tax.

## Mains entry

**Priced: the retained supply cord to the main board's mains tabs 2 and 3, as on the original board, with the entry parts on the main board, hand-fitted.** This is the declared arrangement, the owner's ruling that the machine keeps its fixed mains lead and fits no appliance inlet and no bought inlet filter (§ What is settled before pricing, statement 3; `DEC-INLET-CHAIN-RATED-ABOVE-ITS-FUSE`). The entry parts are a 10 A entry fuse in two 5 × 20 mm clips, the varistor that sits hard against it and downstream of it, and an X2 capacitor. The varistor and the X2 capacitor are what the original board carried at its mains entry, a 470 V metal-oxide varistor and a 0.1 µF X2 capacitor across the live and neutral (`reference-machine.md`, *Mains-entry surge and filter parts on the original board*, `RV1` and `C1`). The X2 capacitor is a provision priced pending the main board design's decision on whether the entry needs emission suppression, and the owner checks the original board's varistor before the part is chosen. One set (one machine), charged quantities from § The two per-part numbers, prices read from the library service on 2026-10-25 (all four parts Extended):

| Part | JLCPCB part | Count | Charged quantity | Unit price (USD) | Cost (USD) |
|---|---|---|---|---|---|
| Entry fuse clip, Littelfuse 01110501Z, 10 A 250 V (two a fuse, one fuse fitted) | C151075 | 2 | 4 | 0.1676 | 0.67 |
| 10 A entry fuse, 5 × 20 mm, SCF520PF10A250V (two bought, one spare; the slow-blow type is **unconfirmed** in the catalogue entry, which gives 10 A, 250 V DC and 1.5 kA interrupting capacity and does not name the time-delay type) | C22447845 | 2 | 2 | 0.1621 | 0.32 |
| Varistor 14D471K, 14 mm, 470 V class, 84.6 J | C8852 | 1 | 3 | 0.1477 | 0.44 |
| X2 capacitor 0.1 µF, 275 V, KNSCHA MPX104K31C3KN15600 | C489079 | 1 | 3 | 0.0383 | 0.11 |
| **Mains-entry parts on the main board** | | | | | **1.54** |

0.67 + 0.32 + 0.44 + 0.11 = **1.54 USD**, inside the main board's 21.55 USD of hand-fitted parts (§ Parts). The retained loom's connectors and the mains leads are not priced: the loom is the machine's own.

**Not priced.**
- *A mains common-mode choke, or a filter module.* None was found: no in-stock rated 6–10 A choke or PCB filter module in the library service (the first 25 of 88 rows of the choke keyword in Chinese all had zero stock, and the English keywords returned signal inductors; the in-stock UU9.8 and UU10.5 types show no current rating on the pages read), and the distributor's own parts search (LCSC) was not reachable (HTTP 403). The library's in-stock inlet filters (Schaffner FN9222 rows have zero stock; TE C42547035 8.446 USD, C43205315 7.0451 USD and C44050533 7.9157 USD have stock 10, 7 and 4 and no rating in their titles) are not fitted: the machine has no inlet.
- *Y2 capacitors, as an option*: 2.2 nF, 250 VAC, radial, pitch 7.5 mm, C2761720 (Dersonic CY2222MD1IEF46J2A8), 0.0295 USD, stock 291 123. Not in the totals.
- **Whether the entry needs a choke, a filter or Y2 capacitors is a bring-up and pre-compliance judgement, not one this estimate decides.** `REQ-PRODUCTION-GRADE-VERIFICATION-001.C2` and `.C7` have conducted and radiated emissions measured on the assembled machine; the estimate prices the parts the original board carried and records the cost of the options it found.

**Parts read for the entry, 2026-10-25** (the library service's catalogue, about 00:02–00:06 UTC; stock and smallest-break price in USD; all Extended; no Basic or Preferred part was found for any of them, and whether a Basic 5 × 20 mm holder or X2 exists is not settled by the search):

| Function | Parts read (LCSC, stock, price) |
|---|---|
| 5 × 20 mm clip or holder, 10 A | C151075 Littelfuse 01110501Z clip, 10 A 250 V, 4 051, 0.1676 (chosen); C182320 LS-502 clip, 10 A, 1 780, 0.0297; C58066 two-piece holder, rating not stated, 21 265, 0.2748; C3131 holder, **6.3 A**, 89 099, 0.0847 (the existing holder; its 6.3 A rating is below a 10 A fuse's); C3130 clip, no rating on the page read, 194 084, 0.0326 |
| 10 A 5 × 20 mm fuse | C22447845 SCF520PF10A250V, 3 054, 0.1621 (chosen); C22447834 SCT520PT10A250V, 887, 0.1716; C2997142, mounting unresolved (SMD footprint name, through-hole body), 6 359, 0.1621; C47118149, 2 631, 0.1545. No ceramic-tube 10 A 5 × 20 mm part was found |
| X2 0.1 µF 275 VAC, pitch 10 mm | C489079 (chosen), 418 924, 0.0383; C93370, 4 741, 0.0446; C2888214, 5 152, 0.0657; C105759, 115 294, 0.0431. Pitch 15 mm: C2888213, 11 538, 0.0500. 0.22 µF pitch 10 mm: C22371563, 7 323, 0.0428 (Dongtong); 0.47 µF: C22371566, 37, 0.1243 |
| Varistor 470 V class | 14 mm: C8852 (chosen), 78 738, 0.1477; C693460, 4 295, 0.0974. 10 mm: C2839518, 39 927, 0.0539. 7 mm: C49072860, 358 492, 0.0310 (31 J, the wall board's) |
| Y2 2.2 nF, 250 or 300 VAC | C2761720 250 VAC, 291 123, 0.0295; C2803195 300 VAC, 183 155, 0.0302; C332371 250 VAC, 33 337, 0.0303. 4.7 nF: C48997974 300 VAC, 1 591, 0.0395; C2761721 250 VAC, 88 895, 0.0482 |
| Inrush NTC, 5–10 Ω, 5 A (not needed by the owner's variant) | C51666 5 Ω, 9 542, 0.2578; C105635 10 Ω, 10 350, 0.3185 |

**Footprint facts for the design task** (EasyEDA pad records of 2026-10-25; the service's unit is 0.254 mm and its hole value is a radius, so the drill is twice it; a pad or drill is not a manufacturer's drawing, and the design task takes the part's datasheet over it):

| LCSC | Part | Pads | Pad pitch (mm) | Pad (mm) | Drill (mm) |
|---|---|---|---|---|---|
| C151075 | Fuse clip 01110501Z | 2, ellipse | 5.0 | 2.2 | 1.5 |
| C22447845 | Fuse SCF520PF10A250V | 2, ellipse | 24.0 | 2.2 | 1.4 |
| C8852 | Varistor 14D471K | 2, ellipse | 7.5 along x, staggered 3.0 along y | 2.0 | 1.2 |
| C489079 | X2 capacitor 0.1 µF | 2, ellipse | 10.0 | 1.8 | 1.0 |
| C2761720 | Y2 capacitor 2.2 nF (option) | 2, ellipse | 7.5 along x, staggered 2.0 along y | 1.52 | 0.91 |
| C3131 | Fuse holder (existing, 6.3 A) | 2, oval | 22.0 | 1.0 × 2.2 | not read |
| C3130 | Fuse clip (existing) | 2, oval | 5.15 | 2.4 × 1.0 | not read |
| C20626100 | Board tab (replaced by C20626104) | 2, oval | 5.0 | 1.5 × 2.5 | 0.9 |
| C20626104 | Board tab | not read | not read | not read | not read |
| C49072860 | Varistor 07D471K (wall board) | 2 | 5.0 | not read | not read |

The fuse C22447845's footprint is a leaded body with its pads 24.0 mm apart, whereas a 5 × 20 mm fuse held in clips has no leads; whether this part has leads, and so whether two clips at about 20 mm centres hold it, is for the design task to settle from the datasheet, with the slow-blow type.

## Steam-path assembly, owner-sourced

The steam-path pressure transducer behind a drop leg, its tee and its thread adaptor (`controller-board-function-forms.md` § Steam-path pressure sensing; `docs/sunbeam-em7000/controller-design/control-system-bom.csv`). One a machine. **The owner sources it (statement 2, § What is settled before pricing): it is not on the manufacturer's order and not in the board orders' total.** It is kept here as a separate, labelled line because the division names it, and every total is shown without it and with it. Estimated from the earlier design's bill's prices, in Australian dollars. The bill's XDB401 line is a transducer of the preferred kind; the proving candidate, the Ashcroft S1, has no price or stock found (`controller-board-function-forms.md` § Availability and price) and is not priced.

| Part | AUD |
|---|---|
| Transducer, XDB401-class, 3.3 V I²C | 30.00 |
| Tee fitting for the pressure tap | 6.00 |
| Drop-leg tube | 10.00 |
| Thread adaptor to the transducer | 20.00 |
| **Total** | **66.00** |

66.00 × 0.70296 = **46.40 USD**. The transducer's withstand rating is absent, so it may not be fittable (`controller-board-function-forms.md`); the second-spin line allows for that.

## What the library class allows

Read on 2026-10-25 from the same library search service as § Sources read, one request a keyword, all answered HTTP 200. The reads are tabulated below so a reader can repeat them. The service is `POST https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList/v2`. Class is the service's `componentLibraryType`: `base` is Basic, `expand` is Extended, and an `expand` part flagged `preferredComponentFlag` is Preferred, which the manufacturer record says is exempt from Economic's feeder loading (`docs/board-manufacturer-jlcpcb.md` § Parts library classes and their fees). The decoding was confirmed on two known parts, C25804 (`base`, a Basic resistor, stock 40 764 574) and C114409 (`expand`, an Extended part, stock 623); the Preferred flag was not checked against a known Preferred part, so it is graded unconfirmed. Stock is the service's `stockCount`, the unit price its first price break (`componentPrices[0].productPrice`, USD), the package its `componentSpecificationEn`. The service filters on `componentLibraryType` `base` and `expand`, but a filter of `preferred` returns nothing for every part, so it cannot filter on Preferred; Preferred parts were found only by scanning, 40 to 241 rows a keyword, so **the Preferred scan was partial** and a Preferred part may exist that it did not reach.

- **Every part this estimate prices is Extended.** The 14 parts read (the microcontroller, the supply module, the opto-triac C8965, the triac C256462, the interlock relay, the valve relay, the AC-input optocoupler, the fuse holder, the fuse clip, the tab, the 120 kΩ resistor, the wall board's triac C9100, opto-triac C10797 and varistor C49072860) are Extended. The varistor, priced as assumed Basic in § Heater wall board, is read as Extended; it is hand-fitted, so its class changes no figure.
- **All seven header families and the shunt are Extended.** 2.54 mm 1×2, 1×3, 1×4 and 1×10, JST XH 2-, 3-, 4- and 10-way, and the 2.0 mm PH 5- and 9-way were read as Extended; the 1.95 mm 4-way was not found. No Basic or Preferred header, and no Basic or Preferred 2512 shunt in 241 rows, was found. The division's assumption A13 (`controller-board-division.md`, every header type and the shunt are Extended) is therefore confirmed as a reading, and the division record now carries the class as read, with its date.
- **The main board has 19 unique Extended types, 5 placed by the manufacturer and 14 fitted by the owner,** the 120 kΩ resistor (C5126146, Extended) among the five; the division record counts the same.

**Parts read, all 2026-10-25** (stock and smallest-break unit price in USD; every one Extended, none Basic or Preferred):

| LCSC | Part | Class | Stock | Unit price | Package |
|---|---|---|---|---|---|
| C114409 | STM32H743VIT6 | Extended | 623 | 10.6814 | LQFP-100 |
| C6280121 | IRM-20-5 | Extended | 2 603 | 6.384 | module |
| C8965 | MOC3052M | Extended | 5 309 | 0.5892 | DIP-6 |
| C256462 | BTA204S-600B,118 | Extended | 4 745 | 0.8543 | TO-252 |
| C5318991 | HF115F-Q/012-1H | Extended | 18 | 3.2141 | DIP 12.7 × 41 mm |
| C91370 | HF32FA-G/005-HSL1 | Extended | 4 239 | 1.6169 | plug-in 17.6 × 10.1 mm |
| C108051 | LTV-814S-TA1-A | Extended | 11 589 | 0.1362 | SMD-4P |
| C3131 | 5 × 20 mm fuse holder XC-7 | Extended | 89 099 | 0.0847 | plug-in |
| C3130 | 5 × 20 mm fuse clip | Extended | 194 084 | 0.0326 | plug-in, 4.8 mm |
| C20626100 | BTC-3-PCB485005D, 4.8 × 0.5 mm tab (replaced) | Extended | 4 746 | 0.0351 | plug-in |
| C20626104 | BTC-3-PCB634908T, 6.3 × 0.8 mm tab (read 2026-10-26) | Extended | 14 453 | 0.0374 | plug-in |
| C5126146 | FRC2512F1203TS, 120 kΩ 1 W 200 V | Extended | 19 820 | 0.0261 | 2512 |
| C9100 | BTA16-600BRG | Extended | 10 230 | 0.8445 | TO-220AB |
| C10797 | MOC3083 | Extended | 9 592 | 0.2907 | DIP-6 |
| C49072860 | 07D471K varistor | Extended | 358 492 | 0.0310 | plug-in, 5 mm |

**Header families read, all 2026-10-25** (one example part each; no Basic or Preferred header or JST part was found, and the Basic filter returned nothing for every header and connector keyword tried):

| Family | Class | Example LCSC, stock, unit price | Mounting |
|---|---|---|---|
| 2.54 mm 1×2 | Extended | C32713268, 175 008, 0.0155 | through-hole |
| 2.54 mm 1×3 | Extended | C49257, 196 792, 0.0284 | through-hole |
| 2.54 mm 1×4 | Extended | C32713270, 125 098, 0.0328 | through-hole |
| 2.54 mm 1×10 | Extended | C57369, 14 010, 0.0711 | through-hole |
| 2.54 mm 1×40 break-away | Extended | C2337, 67 429, 0.1593 | through-hole |
| JST XH 2-way | Extended | C2905024, 14 627, 0.0773 | surface-mount right angle; through-hole not found |
| JST XH 3-way | Extended | C5258884, 10 302, 0.0136 | through-hole, 2.5 mm |
| JST XH 4-way | Extended | C5258885, 7 128, 0.0159 | through-hole, 2.5 mm |
| JST XH 10-way | Extended | C5140471, 574, 0.1853 | surface-mount vertical; through-hole not found |
| PH 5-way, 2.0 mm | Extended | C2898948, 1 795, 0.0212 | through-hole |
| PH 9-way, 2.0 mm | Extended | C54618801, 1 000, 0.0768 | surface-mount right angle; through-hole not found |
| 1.95 mm 4-way | not found | the keyword returned only LEDs | none |

The catalogue lists JST XH at 2.5 mm pitch, and this table takes the catalogue's value. The service has no assembly-process field; the nearest are the `Mounting Type` attribute and the package string. Keyword shape matters: "1x3" and "5x20 fuse clip" returned nothing where "1*3P" and "Fuseholders" worked.

**Alternatives searched, all 2026-10-25** (rows scanned are the most the service returned for the keywords; a scan of 40 to 241 rows does not reach every Preferred part):

| Function | Keywords | Rows scanned | Basic or Preferred found (LCSC, class, stock, unit price) |
|---|---|---|---|
| AC-input optocoupler | PC814, EL814, LTV-814, AC input optocoupler | all returned Extended only | none. DC-input 817 type, Basic: C109227 LTV-817S-TA1-C, 230 247, 0.0811 (SMD-4P); C115450 LTV-217-B-G, 355 752, 0.0837 (SOP-4). The keyword PC817 gave 178 hits, the first 100 all Extended |
| Zero-cross opto-triac driver | MOC3063, MOC3052, MOC3083, MOC3023 | 43 | none. Extended: C77950 MOC3063S-TA1, 59 581, 0.2154; C6171201 MOC3083M, 3 252, 0.2517 |
| 600 V triac, DPAK or TO-220 | BTA16, BTA204, triac, triac 600V | 40 | none. Extended: C256464 BTA204S-600D,118, 1 640, 0.8543 |
| 5 × 20 mm fuse holder or clip | fuse holder, clip and holder keywords | 150 (53 matches) | none. Extended: C717030 PTF-77, 2-piece holder, 100 855, 0.1748 |
| 6.3 mm faston PCB tab | faston and tab keywords | 40 | none. The family C20626100 to C20626104, all Extended; C20626104 is the one whose drawing gives a 6.3 mm, 0.8 mm blade, and it is taken (read 2026-10-26) |
| 120 kΩ resistor, 0603 | 120k 1% | not counted | Basic: C25808, 1 166 788, 0.0015 (100 mW, 75 V) |
| 120 kΩ resistor, 0805 | 120k 1% | not counted | Preferred: C17436, `expand` with the flag, 123 353, 0.0035 (125 mW, 150 V) |
| 120 kΩ resistor, 1206 | 120k 1% | 151 | none |
| 120 kΩ resistor, 2512 | 120k 1% | the Basic 2512 pool, 185 rows, holds no 2512 part | none. Extended: C5126146, 19 820, 0.0261 |
| 2512 shunt, 1 to 5 mΩ | 2512 shunt resistor values | 241 | none. Extended: C459678 RLP25FEGR001 (1 mΩ 3 W), 27 189, 0.0892; C489551 YLR12-3-1F-W, 23 914, 0.1153; C312481, 1 120, 0.1326; C346863, 4 148, 0.3362; C469427 ASR-M-3-1F (1 mΩ 5 W), 40 082, 0.2747; C154685 (2 mΩ), 28 037, 0.1896; C154688 (5 mΩ), 22 652, 0.1450 |
| 5 V or 12 V SPST-NO PCB relay | relay keywords | 100, 37 and 12 | none. Extended: C91370 (5 V), 4 239, 1.6169; C183617 HF32FA-G/012-HSL1 (12 V), 1 572, 1.6709. C194246 is single-pole double-throw and C9226 double-pole, so neither fits |
| 5 V 20 W AC-DC module | module keywords | not counted | none. Extended: C6280121, 2 603, 6.384; C465406 HLK-20M05, 615, 5.0093; C19632441 HLK-20M05L, 42, 3.8687 (an "L" variant, equivalence not verified) |

In the decided configuration only the five surface-mount Extended types carry a manufacturer loading fee, since the owner buys the through-hole parts. Options found that could remove an Extended type, **none applied**:

| Option | Source part, price (USD) | Saves, before tax | Design check it needs |
|---|---|---|---|
| One 1×40 break-away header for the four 2.54 mm header types | C2337, 0.1593 | nothing at the manufacturer, since the headers are hand-fitted; removes three purchased part numbers | Each harness header's way count and the break-away strip's pin length and pitch against the connectors' mating parts |
| A DC-input Basic optocoupler with an antiparallel diode in place of the AC-input LTV-814S | C109227 LTV-817S-TA1-C, 0.0811 (also C115450 LTV-217-B-G, 0.0837) | about 3.29: the 3.07 loading fee and 4 × (0.1362 − 0.0811) = 0.22 | The supply-timing front end's LED current in both half-cycles with the diode's drop, the current-transfer ratio and the pulse width the zero-cross edge needs, in that stage's design task |
| The 0805 Preferred 120 kΩ resistor in a series chain in place of the 2512 | C17436, 150 V rating, 0.0035 | about 3.0: the 3.07 loading fee less the added parts and joints | Each resistor's share of the mains peak against 150 V, its power, and the chain's total against the 120 kΩ the sense divider needs. The 2512 is rated 200 V, 1 W |
| A one-piece fuse holder, if C717030 includes the clips | C717030 PTF-77, 0.1748, a 2-piece holder | nothing at the manufacturer (hand-fitted) | Whether its pitch and fuse seat match the footprint; it is Extended |

No Basic or Preferred alternative was found for the opto-triac driver (43 scanned), the triac (40), the 5 × 20 mm holder and clip (150), the 6.3 mm tab (40), the 5 V relay (100+), the 20 W supply module, or the shunt (241).

**PCBWay.** Its prices could not be read from its public pages (its site, https://www.pcbway.com, read 2026-10-25): assembly and fabrication prices need a run of its calculator, and no public parts catalogue or application interface was found. The estimate stays on the manufacturer the decision names.

## Shipping

Both manufacturer orders are taken to ship in one parcel, and the one set of through-hole parts the owner fits by hand is taken to be ordered into the same parcel (an estimate with that basis; § Weighed against the declared spend gives the figure if they ship apart). The owner-sourced steam-path assembly is not in the parcel. Weight, in kg:

| Item | Working | kg |
|---|---|---|
| Five main boards | 0.170 kg for 5 boards at 100 × 100 mm, scaled by area: 0.170 × 16 375 / 10 000 | 0.278 |
| Five wall boards | 0.170 × 2 662.5 / 10 000, the outline with the bracket's ears | 0.045 |
| Packaging | the quote's order estimate 0.294 less its boards 0.170 (`docs/board-manufacturer-jlcpcb.md`, *Estimated weight of a minimum order*) | 0.124 |
| Hand-fitted parts of one main board | estimate: 0.17 kg (the supply module, three relays, holders and headers; no mass read). **The single-parcel shipping figure rests on this assumed mass** | 0.170 |
| Mains-entry parts | estimate: two clips, two fuses, a varistor and a capacitor, about 0.010 kg | 0.010 |
| Hand-fitted parts of one wall board | estimate | 0.010 |
| **Order** | 0.278 + 0.045 + 0.124 + 0.170 + 0.010 + 0.010 | **0.637** |

The basis is 0.637 kg: the through-hole parts are not on the manufacturer's assembled boards, but one set of them is in the parcel. The weight is an estimate; the manufacturer computes the chargeable weight, the larger of gross and volume weight, at checkout and adjusts the cost if the actual weight differs (`docs/board-manufacturer-jlcpcb.md`, *Estimated weight of a minimum order*). The calculator's cost steps with weight, so the estimate takes its next step up, 0.7 kg. **That step is inferred** from the nine weights read, not a step the calculator names. The order's mass is 0.637 kg, one set of hand-fitted parts being shipped, **which takes the 0.7 kg step**: Global Standard Direct Line is 11.93 USD at 0.7 kg, UPS Worldwide Express Saver 12.03 USD, so Global Standard Direct Line is the cheapest by 0.10 USD (10–14 business days against 5–7). If the actual order is heavier than 0.7 kg, Global Standard rises to about 12.7 USD at 0.803 kg and 13.51 at 0.9 kg and UPS stays flat at 12.03 USD to 1.0 kg, a 0.10 USD difference at most from the figure taken. The calculator, read 2026-10-24 at about 20:33 UTC for Australia, gave, in USD, graded published unverified, read at source:

| Method, as the calculator names it | Delivery time, as quoted | 0.1 kg | 0.5 kg | **0.7 kg** | 0.9 kg | 1.0 kg | 1.5 kg |
|---|---|---|---|---|---|---|---|
| Global Standard Direct Line | 10–14 business days | 6.10 | 9.62 | **11.93** | 13.51 | 14.30 | 19.34 |
| UPS Worldwide Express Saver | 5–7 business days | 10.28 | 10.28 | **12.03** | 12.03 | 12.03 | 18.05 |
| DHL Express | 2–4 business days | 21.27 | 21.27 | **24.19** | 24.19 | 24.19 | 24.50 |
| FedEx Express | 5–7 business days | 28.97 | 28.97 | **34.64** | 34.64 | 34.64 | 39.97 |
| FedEx International Connect Plus | 6–8 business days | no price | no price | **no price** | no price | 39.04 | 43.22 |
| Sea shipment | 20–25 business days | no price | no price | **no price** | no price | no price | no price |

The calculator also lists shipping on the builder's own DHL or UPS account at 2.00 USD at every weight. That is a charge for handing the parcel to the builder's carrier account, with the carrier's own charge billed to the builder separately and not quoted, so it is not taken as the cheapest quoted method.

**The cheapest method at the 0.7 kg step is Global Standard Direct Line, 11.93 USD** (UPS Worldwide Express Saver is cheapest from 0.9 kg). Shipping, **11.93 USD**. If the manufacturer ships the two orders apart, the wall board's parcel of about 0.19 kg adds up to 9.62 USD (Global Standard Direct Line at 0.5 kg), which is not counted. The JLCONE application's special shipping rates are unmeasured (`docs/board-manufacturer-jlcpcb.md` § Shipping). Shipping is shared between the two orders in proportion to their goods, 117.27 and 6.88 of 124.15: main board 11.93 × 117.27 / 124.15 = 11.27, wall board 0.66. The owner-sourced assembly has no shipping.

## Import tax

An estimate, counted in the total. **Basis:** the builder is in Australia, whose goods and services tax on imported goods is charged at 10 % (**an estimate**: the rate is stated from the statute, not read from a page, the pages tried returning HTTP 404). It is applied to the goods and the shipping together, the value on which an importer pays it: 0.10 × (124.15 + 11.93) = **13.61 USD**, shared by goods plus shipping (the shares are rounded and add to 13.60): main board 0.10 × (117.27 + 11.27) = 12.85, wall board 0.10 × (6.88 + 0.66) = 0.75. Shipping and tax together are 11.93 + 13.61 = 25.54 USD on 124.15 of goods, 0.2057 of the goods. Customs duty is not counted (estimate: none is assumed on consignments of this kind and size; the builder's national tariff is read at re-pricing). Whether the manufacturer collects the tax at checkout is unmeasured; the line counts it once either way. The owner-sourced steam-path assembly is priced at Australian retail prices and carries no separate tax line.

## Second spin

The owner does not intend a second spin: the project's purpose is to get the boards right in one spin by comprehensive analysis and model review (owner statement, 2026-10-26). The estimate prices one anyway because the cost criterion it answers asks for "a likely second spin" to be covered, and by the owner's answer of 2026-10-26 it sits outside the declared figure. A second spin is the likely cost of correcting a board after bring-up. Estimate; the basis is each board's kind:

- **Main board:** a full reorder of fabrication, the surface-mount assembly and parts at the first order's configuration (the on-board entry parts included), with one set of hand-fitted parts bought again: 95.72 + 21.55 = 117.27 USD. It carries the first controller board of the project, the mains barrier and the interlock; nothing on it is reusable once its copper changes.
- **Wall board:** its fabrication and one set of parts again, fitted by the owner by hand: 4.00 + 2.88 = 6.88 USD. It is simple, all through-hole and has no sensing, so a respin changes copper and not parts (`controller-board-division.md` § The heater wall board).
- **Steam-path assembly, owner-sourced:** the transducer bought again, 21.09 USD (30.00 AUD × 0.70296), because its withstand rating is absent and a first choice may not be fittable.
- **Mains entry:** nothing beyond the main board's reorder, which includes the entry parts.

The two reorders ship in one parcel at the same 0.7 kg step, 11.93 USD, shared 11.27 and 0.66, and are taxed at the same 10 %: 0.10 × (124.15 + 11.93) = 13.61, shared 12.85 and 0.75. If the hand-fitted set is shipped apart, in its own parcel, the second spin adds the same 9.62 USD (Global Standard Direct Line at the 0.5 kg step) plus 10 % tax, 9.62 + 0.96 = 10.58 USD, as the first order's ship-apart case.

## The estimate by board and assembly

| Board or assembly | Fabrication | Assembly at the manufacturer | Parts at the manufacturer | Parts the owner fits (one set) | Shipping share | Import tax | **First order** | **Second spin** |
|---|---|---|---|---|---|---|---|---|
| Main board, with the mains-entry parts | 35.19 | 26.98 | 33.55 | 21.55 | 11.27 | 12.85 | **141.39** | **141.39** |
| Heater wall board | 4.00 | none | none | 2.88 | 0.66 | 0.75 | **8.29** | **8.29** |
| **The board orders** | | | | | | | **149.68** | **149.68** |
| Steam-path assembly, owner-sourced | none | none | none | 46.40 | none | in the price | **46.40** | **21.09** |
| **The board orders and the owner-sourced assembly** | | | | | | | **196.08** | **170.77** |

The hand-fitted set with its shipping and tax share is 24.43 + 2.35 + 2.68 = 29.46 USD (24.43 = 21.55 + 2.88; shipping 11.93 × 24.43 / 124.15 = 2.35; tax 0.10 × (24.43 + 2.35) = 2.68); the rest of the board orders, what the manufacturer's order places, is 149.68 − 29.46 = 120.22 USD, shared by the two machines the two assembled boards serve. **Per machine** is that 120.22 / 2 = 60.11 plus the one set in full, 29.46, plus the owner-sourced assembly in full where it is counted:

| | First order | First order and likely second spin together |
|---|---|---|
| **The board orders** | 149.68; **89.57 a machine** (60.11 + 29.46) | 149.68 + 149.68 = **299.36**; **179.14 a machine** (89.57 + 89.57) |
| **The board orders and the owner-sourced assembly** | 196.08; **135.97 a machine** (89.57 + 46.40) | 196.08 + 170.77 = **366.85**; **246.63 a machine** (135.97 + 89.57 + 21.09) |

Each figure above cites its source in the section that gives it. The figures that are estimates, and not reads, are: the main board's fabrication (inferred), the machine-placed joint count, the shunt, the headers, the unlisted passives, the wall board's resistors and header, the parts' mass, the chargeable weight and its 0.7 kg step, the import tax, the owner-sourced assembly and the second spin.

## Weighed against the declared spend

**The declared figure** is **250 USD**, written in `component-specification.md` § The component list, *Declared spend: 250 USD*, with its running total in § Against the declared figure, which this estimate brings current. The figure is the owner's and is not changed here.

**What the declared figure counts.** The weighing counts the board orders: the manufacturer's orders for the two boards, the one set of hand-fitted parts including the on-board mains-entry parts (the owner's statements of 2026-10-25), shipping and import tax (the settled terms of § What is settled before pricing). By the owner's answers of 2026-10-26 the declared figure excludes the owner-sourced steam-path assembly and does not count a likely second spin. The count the declared spend takes is what the owner pays for the minimum order, 5 fabricated and 2 assembled boards, one hand-fitted set, with the cost per machine beside it.

**Spend to date.** None is bought (`controller-board-design-constraints.md` § Purchases ahead of verification states none), so spend to date is 0. The controller's one-machine figure the specification carried as decided-not-yet-bought is a part of the main board's lines and is replaced by them, not added to them.

**What remains** is 250.00 − 0.00 = **250.00 USD**.

**The weighing.** The board orders, first order, are **149.68 USD** (89.57 a machine), which is **100.32 USD inside** the 250.00 that remains. The total does not exceed what remains, so the weighing is met: nothing is changed to bring it inside, and the owner is not asked to revisit the figure.

**For information, outside the declared figure by the owner's answers.** These are not counted against the 250.00; they show what the total would be if the owner later chose to count them.

| Total | USD (a machine) | Against 250.00, if counted |
|---|---|---|
| The owner-sourced steam-path assembly alone, estimate | 46.40 | not counted |
| The board orders and the owner-sourced assembly, first order | 196.08 (135.97) | 53.92 inside |
| The board orders, first order and likely second spin | 299.36 (179.14) | 49.36 over |
| The board orders and the owner-sourced assembly, first order and likely second spin | 366.85 (246.63) | 116.85 over |

**If the hand-fitted set ships apart.** The parcel is priced by the rule of § Shipping, the cheapest quoted method at the chargeable weight: at the 0.5 kg step that is Global Standard Direct Line, 9.62 USD. Taken as an addition to the 11.93 USD, with 10 % tax on it (an estimate with that basis), the first order rises by 9.62 + 0.96 = 10.58 USD: the board orders to 149.68 + 10.58 = 160.26, still 89.74 inside. The set's mass is about 0.19 kg (0.170 + 0.010 + 0.010), which takes the calculator's 0.5 kg step; the boards' own parcel, 0.443 kg, would be lighter and might price lower, so this is the upper figure.

**Savings available, for information.** Neither is applied in the figures above. Each is the owner's to take if more headroom is ever wanted; savings before tax, with the tax following at 10 %:

| Change | Rests on | Saves before tax, each manufacturer order | Working |
|---|---|---|---|
| The further savings found by the 2026-10-25 catalogue read: the Basic DC-input optocoupler and the 120 kΩ Preferred chain | The design checks of § What the library class allows | 6.29 | 3.29 + 3.0; the header and fuse-holder options save nothing at the manufacturer |
| The main board on 2 layers with a pour, the division's stated fallback | `controller-board-division.md` § Layer counts | 23.16 | 35.19 − 12.03; loses the inner ground plane the owner favours under the sensing |

With both, each order is 1.10 × 29.45 = 32.40 USD less. 2 oz copper (D13) adds 36.40 USD at two layers in the lowest band and is not drawn.


## Marks ended and re-pointed

Every entry `controller-board-design-constraints.md` § Pending marks held against the block-level cost estimate, with what became of each. A mark that only a quoted order can settle is re-pointed to `DEL-HW-PARTITION-AND-FEASIBILITY.C5`, the design task of the board it belongs to, and not deleted.

| Pending item | Outcome | Figure and source, or reason |
|---|---|---|
| Price of a board's own order where not one of the configurations read: the main board | **Re-pointed.** Carried as an estimate | 35.19 USD inferred, § Main board, *Fabrication*. Only the quote, which needs the board's design file, reads it |
| Price of the wall board's own order | **Ended** | 4.00 USD, the band price, 2026-10-13 |
| Extra cost of a 0.10 mm drill | **Re-pointed** | The drill is chosen with the vias at layout; the estimate assumes the quote's default via |
| Special-process charge | **Re-pointed** | The options are the quote's defaults, so none is expected; the quote confirms it |
| Large-board charges (fabrication and assembly) | **Ended** | Neither applies: 163.75 cm² against 650 cm² |
| Several-designs charge | **Ended** | Not incurred: one design in each file |
| Routing rate for slots narrower than 0.8 mm | **Ended** | Not needed: the least slot drawn is 1.0 mm, at 12.3 and 10.7 m per m² against the 80 m per m² where a routing charge starts |
| Expedited fee and the order-area multiplier above 2.0 m² | **Ended** | Not incurred: no expedited build time is ordered; the order is far under 0.5 m² |
| Single-board surcharge, stencil storage, fixture storage | **Ended** | Charges of Standard assembly only; Economic assembly is chosen (`docs/board-manufacturer-jlcpcb.md` § Assembly charges) |
| Fees of parts sourced outside the public library | **Ended** | None: every part on the manufacturer's orders and every hand-fitted part is a public-library part (§ Parts, § Mains entry). The transducer is sourced by the owner |
| JLCONE prices at every configuration but the four read, and where the 2.00 USD floor holds | **Re-pointed** | The application's prices are not readable by a headless request, and the quote needs the board's own options entered in the application. The estimate takes the website prices throughout |
| Minimum quantity charged per part | **Ended** | `leastPatchNumber` and `lossNumber` read for each part, 2026-10-24 (§ The two per-part numbers); the meaning is inferred |
| Whether a class's loading fee also applies to a part fitted by hand | **Ended** | No manufacturer fee applies: the owner decided on 2026-10-25 to fit the through-hole parts by hand (§ What is settled before pricing), so the manufacturer assembles none of them and charges neither a loading fee nor hand-soldering for them. The question whether it would have charged the fee is moot and is not read |
| Chargeable weight of a board order | **Re-pointed** | Estimated at 0.637 kg, taken at the 0.7 kg step (§ Shipping), on the basis that one set of hand-fitted parts is ordered into the same parcel; the manufacturer computes the chargeable weight at checkout |
| Shipping cost | **Ended** | 11.93 USD by the cheapest method at the 0.7 kg step, with the others listed (§ Shipping), read 2026-10-24 |

## Re-pricing it in another market

1. Take the exchange rate of your currency to US dollars and the date read, and replace the Australian-dollar lines of § Steam-path assembly with local prices.
2. Run the shipping calculator at https://jlcpcb.com/shipping for your country at 0.5, 0.7, 0.9 and 1.0 kg, replace the table of § Shipping, and take the cheapest method at the weight your orders reach.
3. Replace the import tax's rate and basis with your country's, and the customs duty if one applies.
4. Read each part's page at the address its row gives in `controller-board-design-constraints.md` § Manufacturer stock and price, per channel, or search the part number at https://jlcpcb.com/parts, and replace the prices and the two per-part numbers.
5. Re-read the assembly price page at https://jlcpcb.com/help/article/pcb-assembly-price and replace the charges of § Assembly.
6. Quote the finished boards when their files exist; the quote replaces every inferred and estimated line above.
