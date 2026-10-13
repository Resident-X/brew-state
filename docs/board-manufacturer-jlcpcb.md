# Board manufacturer: JLCPCB

What JLCPCB can make and assemble, what an order costs, and which files it takes, read from its own published pages and dated. JLCPCB is the manufacturer the controller boards are made and assembled by (`DEC-BOARD-MANUFACTURER-JLCPCB`). Nothing here is specific to any machine: a board for any machine of this project is held to the same limits, so this record lives outside every machine's folder (`DEC-MACHINE-RECORD-FOLDER-PER-MACHINE`). A second manufacturer gets a record of its own beside this one rather than a section in it.

**Who reads it, and how.** The session designing a board takes the manufacturer's stated limits from here into the rows of that board's design rules, as the board design method's step 1 asks (`docs/board-design-method.md` § Rules before routing, step 1). Each entry below is written to be copied into such a row as it stands: its figure, its unit, the condition it holds under, and the page it was read from. **The date in an entry's *Read* column is the date a design-rules row cites as the date its figure was read.** The builder reads the order, assembly and parts-library charges here when weighing parts against the declared spend, and the partition and feasibility task reads them when it estimates each board's cost.

**What is not here.** Choosing a board's layer count, outline or assembly side, which the partition and design tasks decide against these limits. Which parts a machine's channels might use, with their stock and price, which is specific to a machine and kept in the design-constraints record in that machine's own folder.

**Prices.** JLCPCB publishes and charges in US dollars: its pages state that another selected currency "is for reference only, payments must be made in US dollars", and its assembly price page that "prices may vary slightly due to exchange rate fluctuations". Every price below is in US dollars as published.

**Reading it again.** Every figure here changes when JLCPCB changes its pages. To refresh an entry, open the address in its *Source* column, read the same figure under the same condition, and replace the value and the *Read* date together. A figure that has moved is replaced, not annotated; the commit that changes it is its history. Most of the pages read carry their own "Last updated" date, given in § Pages read, so a reader can tell whether a page has changed since this record read it.

## Evidence grades

These grades are this record's own, and their meanings here govern it. They are kept distinct, never levelled: an entry derived from others is no stronger than the weakest of them, and says which set its grade.

| Grade | Meaning in this record |
|---|---|
| **published unverified, read at source** | The figure as JLCPCB publishes it on the page cited, read at that page on the date given. It is the manufacturer's own claim about its process or its prices; nothing in this project has made or measured a board to confirm it. |
| **inferred** | Worked out from other entries in this record, with the working shown beside it so it can be checked. |
| **unmeasured** | A figure that bounds the boards for which no published value was found on the pages read. The entry says why, and how the figure would be read. |

Where two of JLCPCB's own pages disagree, both are recorded, and the entry says which one this record takes and why.

## Pages read

All read on 2026-10-13 from a browser session with no JLCPCB account signed in and no destination country chosen.

| Page | Address | The page's own "Last updated" date |
|---|---|---|
| Rigid PCB manufacturing capabilities | https://jlcpcb.com/capabilities/pcb-capabilities | none stated |
| PCB assembly capabilities | https://jlcpcb.com/capabilities/pcb-assembly-capabilities | none stated |
| PCB Assembly Cost: What Does the Price Include? | https://jlcpcb.com/help/article/pcb-assembly-price | 2026-09-09 |
| PCB Assembly FAQs | https://jlcpcb.com/help/article/pcb-assembly-faqs | 2026-09-09 |
| PCB Assembly FAQ (Part 2) | https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2 | 2026-09-09 |
| PCBA Parts Sourcing Instruction | https://jlcpcb.com/help/article/pcba-parts-sourcing-instruction | 2026-09-09 |
| In what cases will there be charged extra? | https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra | 2026-09-09 |
| How to Prepare Gerber Files Before Placing Orders? | https://jlcpcb.com/help/article/gerber-files-preparation | 2026-09-09 |
| Bill of Materials (BOM) File for PCB Assembly | https://jlcpcb.com/help/article/bill-of-materials-for-pcb-assembly | 2026-09-09 |
| Pick & Place File for PCB Assembly | https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly | 2026-09-09 |
| PCB Files Preparation, and PCBA Files Preparation (help catalogues) | https://jlcpcb.com/help/catalog/180-PCB-Files-Preparation; https://jlcpcb.com/help/catalog/190-PCBA-Files-Preparation | none stated |
| Online PCB instant quote | https://cart.jlcpcb.com/quote | none stated |
| Fast PCB Prototypes in 24 Hours | https://jlcpcb.com/ads/pcb-prototype | none stated |
| JLCPCB Unveils JLCONE: $2 PCBs & Exclusive Shipping Rates Now Available Only on JLCONE Desktop | https://jlcpcb.com/news/jlcpcb-jlcone-desktop-app | press release dated 2026-08-22 |
| Home page, *Ordering Instructions* | https://jlcpcb.com | none stated |
| JLCPCB Shipping Methods: Delivery Time & Global Options | https://jlcpcb.com/help/article/Shipping-Methods-and-Delivery-Time | 2026-09-09 |
| Shipping calculator | https://jlcpcb.com/shipping | none stated |
| Parts library | https://jlcpcb.com/parts, and each part's page at https://jlcpcb.com/partdetail/… | none stated |

**How the quote was read.** The fabrication prices and weights below marked as read at the quote were read on 2026-10-13 at about 11:40 UTC by loading the quote page and taking the figures the page's own cost service returned for it (the request the page sends to https://cart.jlcpcb.com/api/overseas-core-platform/shoppingCart/calculationGoodsCostsNew), changing only the options each entry names. The page shows two prices for an order: one labelled *Web*, the price when the order is placed on the website, and one labelled *JLCONE Desktop*, the price when it is placed through JLCPCB's JLCONE desktop application. Both are given where the quote gave both. For a board of four layers or more the quote returned no JLCONE price; that price is graded unmeasured, and is read by quoting the same options in the JLCONE application. The quote page states "Additional charges may apply for special cases", meaning the extra charges listed below, which are added at file review when they apply.

## Fabrication limits

Each is a minimum the manufacturer will make unless the entry says otherwise. A board-wide minimum a design-rules row takes from here takes the entry's condition with it.

### Tracks and spacing

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Minimum track width and spacing | 0.10 mm / 0.10 mm (4 / 4 mil) | 1- and 2-layer boards, 1 oz finished copper | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-capabilities, *Traces*, "Min. track width and spacing (1 oz)" | 2026-10-13 |
| Minimum track width and spacing | 0.09 mm / 0.09 mm (3.5 / 3.5 mil); 3 mil accepted in BGA fan-outs. A board with track or spacing of 3.0–3.5 mil carries an extra charge of 20 % of the order amount at 4–8 layers and 30 % at 10 layers and over (§ Price bands and the fabrication order, *Extra charge for fine track or spacing*) | Multilayer boards, 1 oz | published unverified, read at source | Same page, same row; the charge from https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, item 14 | 2026-10-13 |
| Minimum track width and spacing | 0.16 mm / 0.16 mm (6.5 / 6.5 mil) | 2-layer boards, 2 oz | published unverified, read at source | Same page, *Traces*, "Min. track width and spacing (2 oz)" | 2026-10-13 |
| Minimum track width and spacing | 0.15 mm / 0.15 mm (6 / 6 mil) | Multilayer boards, 2 oz | published unverified, read at source | Same page, same row | 2026-10-13 |
| Minimum track width and spacing | 0.20 mm / 0.20 mm at 2.5 oz; 0.25 mm / 0.25 mm at 3.5 oz; 0.30 mm / 0.30 mm at 4.5 oz | 2-layer boards, at the copper weight named | published unverified, read at source | Same page, *Traces*, the 2.5 oz, 3.5 oz and 4.5 oz rows | 2026-10-13 |
| Track width tolerance | ±20 % | Any board | published unverified, read at source | Same page, *Traces*, "Track width tolerance" | 2026-10-13 |
| Pad to track clearance | 0.10 mm (0.09 mm locally at BGA pads) | 1 oz | published unverified, read at source | Same page, *Traces*, "Pad to track clearance (1oz)" | 2026-10-13 |
| SMD pad to pad clearance, different nets | 0.15 mm; smallest SMD pad 0.25 mm × 0.25 mm | Any board | published unverified, read at source | Same page, *Traces*, "SMD pad to pad clearance (different nets)" | 2026-10-13 |
| Same-net track spacing | 0.25 mm | Any board | published unverified, read at source | Same page, *Traces*, "Same-net track spacing" | 2026-10-13 |
| Hatched copper grid width and spacing | 0.25 mm | Any board | published unverified, read at source | Same page, *Traces*, "Hatched grid width and spacing" | 2026-10-13 |

### Drills, vias and annular rings

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Drill diameter range | 0.15–6.3 mm | 2-layer and multilayer boards; holes of 6.3 mm and over are routed from a smaller drill | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-capabilities, *Drilling*, "Drill Diameter" | 2026-10-13 |
| Drill diameter range | 0.3–6.3 mm | 1-layer boards | published unverified, read at source | Same page, same row | 2026-10-13 |
| Drill diameter, smallest offered | 0.10 mm, at an extra cost. **The extra cost is not established**: the table of small-hole charges (§ Price bands and the fabrication order, *Extra charge for small vias*) prices holes of 0.15 mm and over only. It is read at the quote, https://cart.jlcpcb.com/quote, with the board's options and the matching via option chosen | 2-layer and multilayer boards no thicker than 1 mm, ENIG or OSP finish only | published unverified, read at source (the size, and that it costs more); unmeasured (the extra cost) | Same page, same row | 2026-10-13 |
| Finished hole size tolerance | +0.13 / −0.08 mm | Plated through-holes | published unverified, read at source | Same page, *Drilling*, "Hole size Tolerance" | 2026-10-13 |
| Recommended smallest plated hole | 0.5 mm | Plated through-holes, so that soldermask or tin does not stick in the hole | published unverified, read at source | Same page, same row, description | 2026-10-13 |
| Minimum via hole / via diameter | 0.15 mm / 0.25 mm | 2-layer and multilayer boards | published unverified, read at source | Same page, *Drilling*, "Min. Via hole size/diameter" | 2026-10-13 |
| Minimum via hole / via diameter, smallest offered | 0.10 mm / 0.20 mm | Boards no thicker than 1 mm, ENIG or OSP finish only | published unverified, read at source | Same page, same row | 2026-10-13 |
| Via diameter over via hole | At least 0.10 mm larger, 0.15 mm preferred | Any board | published unverified, read at source | Same page, same row, note ① | 2026-10-13 |
| Preferred minimum via hole | 0.20 mm | Any board | published unverified, read at source | Same page, same row, note ② | 2026-10-13 |
| Via sizes that cost more | A 0.10 or 0.15 mm hole at any diameter; a 0.20 or 0.25 mm hole with a diameter under 0.45 mm. What each costs is § Price bands and the fabrication order, *Extra charge for small vias* | Any board; the matching via option must be chosen when ordering | published unverified, read at source | Same page, same row, note ③ | 2026-10-13 |
| Minimum non-plated hole | 0.50 mm | Drawn on the mechanical or keep-out layer | published unverified, read at source | Same page, *Drilling*, "Min. Non-plated holes" | 2026-10-13 |
| Minimum plated slot width | 0.5 mm (2-layer); 0.35 mm (multilayer); length at least twice the width | Slot drawn with a pad | published unverified, read at source | Same page, *Drilling*, "Min. Plated Slots Width" | 2026-10-13 |
| Minimum non-plated slot width | 1.0 mm | Outline drawn on the mechanical or outline layer | published unverified, read at source | Same page, *Drilling*, "Min. Non-Plated Slots" | 2026-10-13 |
| Rectangular holes or slots without rounded corners | Not made | Any board | published unverified, read at source | Same page, *Drilling*, "Rectangular Holes / Slots" | 2026-10-13 |
| PTH annular ring | 0.25 mm recommended, 0.18 mm absolute minimum | 2-layer boards, 1 oz | published unverified, read at source | Same page, *Traces*, "PTH annular ring" | 2026-10-13 |
| PTH annular ring | 0.20 mm recommended, 0.15 mm absolute minimum | Multilayer boards, 1 oz | published unverified, read at source | Same page, same row | 2026-10-13 |
| PTH annular ring | 0.254 mm or more | 2 oz, any layer count | published unverified, read at source | Same page, same row | 2026-10-13 |
| NPTH pad annular ring | 0.45 mm or more recommended | Pads around non-plated holes | published unverified, read at source | Same page, *Traces*, "NPTH pad annular ring" | 2026-10-13 |

### Hole-to-hole and clearances to holes and edges

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Via hole to via hole | 0.20 mm | Any board | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-capabilities, *Drilling*, "Via Hole-to-Hole Spacing" | 2026-10-13 |
| Pad hole to pad hole | 0.45 mm | Any board | published unverified, read at source | Same page, *Drilling*, "Pad Hole-to-Hole Spacing" | 2026-10-13 |
| Via hole to track | 0.20 mm | Any board | published unverified, read at source | Same page, *Traces*, "Via hole to Track" | 2026-10-13 |
| Plated hole to track | 0.28 mm minimum, 0.35 mm recommended | Any board | published unverified, read at source | Same page, *Traces*, "PTH to Track" | 2026-10-13 |
| Non-plated hole to track | 0.20 mm | Any board | published unverified, read at source | Same page, *Traces*, "NPTH to Track" | 2026-10-13 |
| Via hole to copper, inner layers | 0.20 mm | Multilayer boards | published unverified, read at source | Same page, *Traces*, "Inner layer via hole to copper clearance" | 2026-10-13 |
| Plated pad hole to copper, inner layers | 0.30 mm | Multilayer boards | published unverified, read at source | Same page, *Traces*, "Inner layer PTH pad hole to copper clearance" | 2026-10-13 |
| Copper to a routed board edge or routed slot | 0.20 mm | Board outline routed | published unverified, read at source | Same page, *Outline*, "Routed" | 2026-10-13 |
| Copper to a V-cut edge | 0.40 mm | Panel separated by V-cut | published unverified, read at source | Same page, *Outline*, "V-Cut" | 2026-10-13 |
| Traces and components to board edge, recommended | More than 0.3 mm | Boards assembled under Economic assembly, which are panelised and separated after assembly with about 0.2 mm routing tolerance | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, item 14 | 2026-10-13 |
| Board outline tolerance | ±0.2 mm regular, ±0.1 mm high precision (routed); ±0.4 mm (V-cut) | As named | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-capabilities, *Outline* | 2026-10-13 |

### Soldermask and silkscreen

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Soldermask bridge, minimum pad spacing | 0.10 mm (green, red, yellow, blue, purple); 0.13 mm (black, white) | 1 oz | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-capabilities, *Soldermask*, "Soldermask bridge" | 2026-10-13 |
| Soldermask bridge, minimum pad spacing | 0.20 mm, any colour | 2 oz | published unverified, read at source | Same page, same row | 2026-10-13 |
| Soldermask opening to neighbouring trace | At least 0.09 mm; openings may be 1:1 with the pad | Any board | published unverified, read at source | Same page, *Soldermask*, "Soldermask Expansion" | 2026-10-13 |
| Silkscreen minimum line width | 0.15 mm | Any board; narrower characters are unreadable | published unverified, read at source | Same page, *Legend*, "Minimum Line Width" | 2026-10-13 |
| Silkscreen minimum text height | 1.0 mm (40 mil) | Any board | published unverified, read at source | Same page, *Legend*, "Minimum text height" | 2026-10-13 |
| Silkscreen character width to height | 1:6 preferred | Any board | published unverified, read at source | Same page, *Legend* | 2026-10-13 |
| Pad to silkscreen | 0.15 mm | Any board | published unverified, read at source | Same page, *Legend*, "Pad To Silkscreen" | 2026-10-13 |

### Layers, thickness, copper and board size

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Layer count | 1–32 | FR-4 rigid boards | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-capabilities, *PCB Specifications*, "Layer count" | 2026-10-13 |
| Board thickness options | 0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0 mm (2.5 mm and over for 12 layers and more) | FR-4 | published unverified, read at source | Same page, "Thickness" | 2026-10-13 |
| Board thickness tolerance | ±10 % at 1.0 mm and over; ±0.1 mm under 1.0 mm | FR-4 | published unverified, read at source | Same page, "Thickness Tolerance" | 2026-10-13 |
| Finished outer copper | 1, 2, 2.5, 3.5 or 4.5 oz | 2-layer boards | published unverified, read at source | Same page, "Finished Outer Layer Copper" | 2026-10-13 |
| Finished outer copper | 1 or 2 oz | Multilayer boards | published unverified, read at source | Same page, same row | 2026-10-13 |
| Finished inner copper | 0.5 oz by default; 1 or 2 oz offered | Multilayer boards | published unverified, read at source | Same page, "Finished Inner Layer Copper" | 2026-10-13 |
| Surface finish | HASL (leaded or lead-free), ENIG, OSP | FR-4; HASL not offered at 6 layers and over or at 0.4 mm and under | published unverified, read at source | Same page, "Surface Finish" | 2026-10-13 |
| Largest board | 670 × 600 mm (2-layer); 663 × 593 mm (4-layer) | FR-4 at 0.8 mm thick and over | published unverified, read at source | Same page, "Maximum Dimensions" | 2026-10-13 |
| Smallest board | 3 × 3 mm; panelisation recommended for small boards | FR-4 at 0.6 mm thick and over | published unverified, read at source | Same page, "Minimum Dimensions" | 2026-10-13 |

## Price bands and the fabrication order

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Minimum fabrication quantity | 5 boards (the smallest quantity the quote offers; quantities outside its list, such as 3 or 8, are not taken) | Any board ordered as single boards; for a panel, the quantity counts panels | published unverified, read at source | https://cart.jlcpcb.com/quote, *PCB Qty* and its note | 2026-10-13 |
| Board-size threshold of the lowest price band | A single board within or equal to 102 × 102 mm is charged a special price only. A panelised board (V-cuts or routed lines between boards) is charged the engineering fee plus the board fee instead, whatever its size. The promotional page's "100 × 100 mm" (below) is a size inside this band, not a different threshold: the quote prices a 102 × 102 mm board as it prices a 100 × 100 mm one, and a 103 × 103 mm board as engineering fee plus board fee (*Fabrication price of a minimum order* below) | Single-board delivery | published unverified, read at source | https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, item 7, *Board Fee*; https://cart.jlcpcb.com/quote | 2026-10-13 |
| The quote's default options | FR-4, TG 135–140; 1.6 mm thick; 1 oz finished outer copper, and 0.5 oz inner copper on a multilayer board; green soldermask, white silkscreen; leaded HASL; smallest via 0.3 mm hole with 0.4–0.45 mm diameter; one design; single-board delivery; 2-day build time. Each price below is at these options except the ones its entry names | 5 boards | published unverified, read at source | https://cart.jlcpcb.com/quote, the options it selects on opening | 2026-10-13 |
| Estimated weight of a minimum order | 0.294 kg for the order (the boards 0.17 kg) at 100 × 100 mm, at 2 and at 4 layers; 0.3045 kg (the boards 0.18 kg) at 102 × 102 mm. The quote states the weight is the larger of gross and volume weight, estimated for reference, and that the shipping cost is adjusted if the actual weight differs | 5 boards, 1.6 mm, at the quote's default options | published unverified, read at source | https://cart.jlcpcb.com/quote, *Shipping Estimate*, *Weight* | 2026-10-13 |
| Extra charge for orders with special process | An extra charge, calculated by the quote with a warning, when an order's options are not those commonly chosen; the page's example is 1 layer, 1.6 mm, red, leaded HASL, 1 oz copper. **The amount is not established**: the page gives none, and it is read at the quote for the options chosen | Fabrication | published unverified, read at source (that it applies); unmeasured (the amount) | https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, item 8 | 2026-10-13 |

The fabrication price of a minimum order, 5 boards, single-board delivery, at the quote's default options except as each row names, for 2-, 4- and 6-layer boards. The prices are read at the quote, as § Pages read, *How the quote was read*, states. *Website* is the quote's *Web* price and *JLCONE* its *JLCONE Desktop* price.

| Configuration | Website | JLCONE | Grade | Source | Read |
|---|---|---|---|---|---|
| 2 layers, up to 102 × 102 mm (read at 100 × 100 and at 102 × 102 mm), leaded HASL | 4.00 USD | 2.00 USD | published unverified, read at source | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 2 layers, up to 102 × 102 mm (read at 100 × 100 mm), lead-free HASL | 5.30 USD (4.00 USD plus 1.30 USD for the finish) | 3.30 USD | published unverified, read at source | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 2 layers, up to 102 × 102 mm (read at 100 × 100 mm), ENIG | 21.70 USD (4.00 USD plus 17.70 USD for the finish) | 19.70 USD | published unverified, read at source | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 2 layers, up to 102 × 102 mm (read at 100 × 100 mm), leaded HASL, 2 oz outer copper | 40.40 USD (4.00 USD plus 36.40 USD for the copper) | 38.40 USD | published unverified, read at source | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 4 layers, up to 102 × 102 mm (read at 100 × 100 and at 102 × 102 mm), leaded HASL | 8.00 USD | **Not established**: the quote returned no JLCONE price | published unverified, read at source (website); unmeasured (JLCONE) | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 4 layers, up to 102 × 102 mm (read at 100 × 100 mm), ENIG | 25.70 USD (8.00 USD plus 17.70 USD for the finish) | **Not established**, as above | published unverified, read at source (website); unmeasured (JLCONE) | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 6 layers, 50 × 50 mm, ENIG (HASL is not offered at 6 layers, § Layers, thickness, copper and board size) | 48.90 USD (32.00 USD plus 16.90 USD for the finish) | **Not established**, as above | published unverified, read at source (website); unmeasured (JLCONE) | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 2 layers, 103 × 103 mm, just above the lowest band | 9.20 USD (engineering fee 4.00 USD plus board fee 5.20 USD) | No JLCONE price given | published unverified, read at source | https://cart.jlcpcb.com/quote | 2026-10-13 |
| 4 layers, 103 × 103 mm, just above the lowest band | 31.60 USD (engineering fee 25.00 USD plus board fee 6.60 USD) | No JLCONE price given | published unverified, read at source | https://cart.jlcpcb.com/quote | 2026-10-13 |
| Any board over 102 × 102 mm other than those read above, or any panel | **Not established.** Such a board is priced as engineering fee plus board fee for its own outline, layer count and options, and JLCPCB publishes no table of either. It is read at the quote, at a quantity of 5, once the board's outline is known | **Not established** | unmeasured | https://cart.jlcpcb.com/quote; the band from https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, item 7 | 2026-10-13 |
| The advertised floor, "From $2.00" for "1–4 Layers · 5 pcs · 100 × 100 mm" and for "6-8 Layers • 5 pcs • 50 × 50 mm" | Not a price for any configuration. The page footnotes that pricing varies with board size and specification, its FAQ that the offer applies to "selected standard PCB orders", and it names no layer count, thickness, copper, finish or colour the floor holds for. Since 2026-08-22 the offer is available only through the JLCONE application. The rows above are the prices of stated configurations; this row records only what the advertisement claims | — | published unverified, read at source (the claim); unmeasured (the configurations it holds for) | https://jlcpcb.com/ads/pcb-prototype, *Standard Prototype PCB*, *Advanced Multilayer PCB*; https://jlcpcb.com/news/jlcpcb-jlcone-desktop-app, *Exclusive $2 PCB Special Deal* | 2026-10-13 |

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Extra charge for burr removal and corner rounding | 0.02 USD per board with a side of 15–30 mm; 0.05 USD per board with a side under 15 mm | Any quantity | published unverified, read at source | https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, item 6 | 2026-10-13 |
| Extra charge for small boards delivered singly | 0.0157 USD per board with a side of 1–3 cm, from 500 boards; 0.0471 USD per board with a side of 0.6 cm to under 1 cm, from 150 boards; 0.0785 USD per board with a side of 0.3 cm to under 0.6 cm, from 100 boards. Charged by the smaller side. Below those quantities, so on a minimum order of 5, it does not apply | Delivery format *Single PCB*, a side of 3 cm or less | published unverified, read at source | Same page, item 10, its table | 2026-10-13 |
| Extra charge for small vias | 0.15 mm hole at 0.25 or 0.3 mm diameter: engineering fee 31.43 USD plus 47.14 USD per m². 0.20 mm hole at 0.3 or 0.35 mm diameter: 15.71 USD plus 23.57 USD per m². 0.25 mm hole at 0.35 or 0.4 mm diameter, and a 0.20 mm hole at 0.4 mm diameter, which is charged as this combination: 15.71 USD plus 15.71 USD per m². A 0.20 or 0.25 mm hole at 0.45 mm diameter, and a 0.3 mm hole at 0.4 mm diameter: no charge. Any other hole is charged by its hole size. The table's no-charge row gives its holes as 0.25 and 0.2 mm while its remark says "0.25mm or 0.35mm"; this record takes the table's hole column, which agrees with the capabilities page's note that a 0.20 or 0.25 mm hole costs more only below a 0.45 mm diameter | The smallest via on the board; the charge is added at the quote when the matching via option is chosen, and at file review when it is not | published unverified, read at source | Same page, item 4, its table | 2026-10-13 |
| Extra charge for fine track or spacing | 20 % of the order amount at 4–8 layers; 30 % at 10 layers and over | Multilayer boards with track width or spacing of 3.0–3.5 mil | published unverified, read at source | Same page, item 14 | 2026-10-13 |
| Extra charge for a long board | 31.43 USD per design for a prototype order; 31.43 USD per m² for a batch order | A board 60 cm long or longer | published unverified, read at source | Same page, item 14 | 2026-10-13 |
| Extra charge for a large board | Charged per further 50 cm² over 650 cm² of one board's area. **The amount is not established**: the page gives none. It is read at the quote by entering the board's outline | Fabrication | published unverified, read at source (that it applies); unmeasured (the amount) | Same page, item 15 | 2026-10-13 |
| Extra charge for several designs in one file | 4.06 USD per design beyond the first, on website and JLCONE prices alike (read at 2 and 3 designs: 4.06 and 8.12 USD). The page itself gives no amount and says the charge is calculated at the quote by selecting the number of designs; the charge at other configurations is not established and is read there | One Gerber file holding more than one design; read at 2 layers, 100 × 100 mm, 5 boards, the quote's default options | published unverified, read at source | Same page, item 1; the amount from https://cart.jlcpcb.com/quote, *Different Design* | 2026-10-13 |

## Assembly limits

JLCPCB offers two assembly services, Economic and Standard. Which service an order uses is a condition on every entry below.

| Limit | Economic assembly | Standard assembly | Grade | Source | Read |
|---|---|---|---|---|---|
| Sides placed | One side only, surface-mount or through-hole | One or both sides, surface-mount or through-hole | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-assembly-capabilities, *Assembly Types* | 2026-10-13 |
| Layer counts assembled | 2, 4 or 6 | 1–32 | published unverified, read at source | Same page, *PCB Layer* | 2026-10-13 |
| Board thickness assembled | 0.8–1.6 mm | No limit | published unverified, read at source | Same page, *Thickness* | 2026-10-13 |
| Single board size assembled | 10 × 10 mm to 470 × 500 mm | 70 × 70 mm to 460 × 500 mm | published unverified, read at source | Same page, *Dimension* | 2026-10-13 |
| Panel size assembled | 10 × 10 mm to 250 × 250 mm | 70 × 70 mm to 250 × 250 mm | published unverified, read at source | Same page, *Dimension* | 2026-10-13 |
| Assembled quantity per order | 2–50 boards | 2–80 000 boards | published unverified, read at source | Same page, *Order Volume*. The older assembly FAQ (https://jlcpcb.com/help/article/pcb-assembly-faqs, item 10) gives 30 as Economic's ceiling; the capabilities page is taken, being the service's own specification | 2026-10-13 |
| **Minimum number of assembled boards** | **2** | **2** | published unverified, read at source | Same page, *Order Volume*: the lower bound of both ranges | 2026-10-13 |
| Smallest package placed | 0402 | 0201 | published unverified, read at source | Same page, *Minimum Package* | 2026-10-13 |
| Smallest IC lead pitch placed | 0.40 mm | 0.35 mm | published unverified, read at source | Same page, *Minimum IC Pin Spacing* | 2026-10-13 |
| Smallest BGA pitch placed | 0.5 mm centre to centre | 0.3 mm centre to centre | published unverified, read at source | Same page, *Minimum BGA Spacing* | 2026-10-13 |
| Edge rails and fiducials | Not needed | Needed | published unverified, read at source | Same page, *Edge Rails*, *Fiducials* | 2026-10-13 |
| Board finishes and colours assembled | Limited to the combinations the page lists; at 1.6 mm, green with leaded or lead-free HASL or ENIG, 2–50 boards | No limit | published unverified, read at source | Same page, *PCB Specs for Economic PCB Assembly* | 2026-10-13 |
| Castellated holes, edge plating, gold fingers | Not assembled | Assembled | published unverified, read at source | Same page, *Gold Fingers/Castellated Holes/Edge Plating* | 2026-10-13 |
| Reflow peak | 255 ± 5 °C, not adjustable | 240 ± 5 °C | published unverified, read at source | Same page, *Reflow temperature* | 2026-10-13 |
| Through-hole and mixed assembly | Offered | Offered | published unverified, read at source | Same page, FAQ "Can you assemble THT components?" | 2026-10-13 |
| Boards made elsewhere | Not assembled: JLCPCB assembles only boards it fabricates | Same | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs, item 14 | 2026-10-13 |
| Parts left unassembled | Not shipped with the assembled boards | Same | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, item 15 | 2026-10-13 |

## Assembly charges

From the assembly price page, last updated 2026-09-09. The older assembly FAQ gives earlier figures for some of the same charges (a setup fee of 8.00 USD, a stencil of 1.50 USD, 0.0017 USD per SMT joint, 3.5 USD hand-soldering labour, 0.0173 USD per manually soldered joint, 3 USD per extended part; https://jlcpcb.com/help/article/pcb-assembly-faqs, items 1 and 6). Where they differ, the price page is taken: it is the one that itemises every charge by service, and the FAQ's figures match no current service exactly.

| Charge | Economic assembly | Standard assembly | Grade | Source | Read |
|---|---|---|---|---|---|
| Setup fee | 8.18 USD per order | 25.56 USD single-sided; 51.12 USD double-sided | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-price, *Setup fee* | 2026-10-13 |
| Stencil | 1.53 USD | 8.21 USD single-sided; 16.42 USD double-sided | published unverified, read at source | Same page, *Stencil* | 2026-10-13 |
| Panel charge | 8.21 USD | 8.21 USD | published unverified, read at source | Same page, *Panel*, applicable when more than one design is panelised | 2026-10-13 |
| SMT assembly, per solder joint | 0.0016 USD for 1–100 000 joints | 0.0016 USD for 1–50 000; 0.0013 USD for 50 001–100 000; 0.0012 USD for 100 001–1 000 000 | published unverified, read at source | Same page, *SMT Assembly* | 2026-10-13 |
| Pre-reflow soldering, per joint | 0.016 USD | 0.016 USD | published unverified, read at source | Same page, *Pre-reflow Soldering* | 2026-10-13 |
| Manual assembly, per solder joint | 0.0164 USD for 1–10 000; 0.015 USD for 10 001–30 000; 0.012 USD for 30 001–100 000 | Same | published unverified, read at source | Same page, *Manual Assembly* | 2026-10-13 |
| Hand-soldering labour | 3.58 USD per order | 3.58 USD per order | published unverified, read at source | Same page, *Hand-soldering Labor* | 2026-10-13 |
| Single-board assembly surcharge | — | The shortfall below 0.48 USD per board: where the SMT assembly charge works out below 0.48 USD per board, the difference is charged. The page's table gives only "$0.48"; its explanation says the minimum applies "for bulk orders" and does not say which orders count as bulk, so whether it applies to a minimum order is not established. Panelising boards avoids it | published unverified, read at source (the figure, and how it is charged); unmeasured (which orders it applies to) | Same page, *Single board assembly surcharge*, the table and *Fee Details and Explanations* | 2026-10-13 |
| Handling fee | — | The shortfall below 14.93 USD, so 0 to 14.93 USD: where both services are available for the same order, Standard must cost at least 14.93 USD more than Economic, and any shortfall is charged as this fee. The page contradicts itself: its table cell reads "≥ $14.93", which reads as a fee of at least 14.93 USD, while its explanation says the 14.93 USD is the least price difference and the fee is the shortfall. This record takes the explanation, which says how the fee is worked out where the cell gives only a bound | published unverified, read at source | Same page, *Handling fee*, the table and *Fee Details and Explanations* | 2026-10-13 |
| Fixtures, rigid board | — | 8.21 USD per fixture: 2 fixtures (16.42 USD) for 1–29 boards; 3 (24.63 USD) for 30–99; 5 (41.04 USD) for 100–199; 10 (82.09 USD) for 200–349; 15 (123.13 USD) for 350–499; 20 (164.18 USD) for 500–100 000. The page also gives fixture charges for flexible boards, which this record does not cover | published unverified, read at source | Same page, *Fixture (Standard Rigid PCB)* | 2026-10-13 |
| Stencil storage | — | 4.93 USD. The page lists the fee without saying when it is charged, so when it applies is not established | published unverified, read at source (the figure); unmeasured (when it is charged) | Same page, *Stencil Storage* | 2026-10-13 |
| Fixture storage | — | 4.93 USD. The page lists the fee without saying when it is charged, so when it applies is not established | published unverified, read at source (the figure); unmeasured (when it is charged) | Same page, *Fixture Storage* | 2026-10-13 |
| Packing | Free | 0.50 USD + 0.00003 USD per cm² of board | published unverified, read at source | Same page, *Packing* | 2026-10-13 |
| Large board | 57.46 USD | 57.46 USD | published unverified, read at source | Same page, *Large Size*, when the board area exceeds 650 cm² | 2026-10-13 |
| X-ray inspection, per component inspected | 1.64 USD for 1–10 components; 0.82 USD for 11–50; 0.49 USD for 51–200; 0.33 USD for 201–500; 0.25 USD for 501–1 000; 0.16 USD for 1 001–3 000; 0.082 USD for 3 001–99 999 | Same | published unverified, read at source | Same page, *X-ray Inspection*, required for BGA, QFN and other leadless parts | 2026-10-13 |
| Placement confirmation | 0.45 USD | 0.45 USD | published unverified, read at source | Same page, *Confirm Parts Placement* | 2026-10-13 |
| Components | At each part's catalogue price | Same | published unverified, read at source | Same page, *Components*, "Per system" | 2026-10-13 |

## Parts library classes and their fees

Every part in JLCPCB's catalogue carries a library class, shown on its page in the parts library at https://jlcpcb.com/parts. Each class is a condition on the fees below.

| Class | What it is | Setup fee per unique part, per order | Per-part fee | Grade | Source | Read |
|---|---|---|---|---|---|---|
| **Basic** | Frequently used parts held loaded on the placement machines | Economic: none. Standard: 1.53 USD feeder loading | None beyond the part's catalogue price and the per-joint assembly charge | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs, item 6; https://jlcpcb.com/help/article/pcb-assembly-price, *Feeder Loading* | 2026-10-13 |
| **Preferred** (an extended part so marked) | Parts formerly Basic, loaded by hand, exempt from Economic's feeder loading fee | Economic: none. Standard: 1.53 USD feeder loading. The price page names only Basic and Extended parts in its feeder-loading row; the exemption under Economic is the assembly FAQ's, item 7, which this record takes because it names Preferred parts and the price page is silent on them | As Basic | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs, item 7; https://jlcpcb.com/help/article/pcb-assembly-price, *Feeder Loading* | 2026-10-13 |
| **Extended** | Every other catalogue part, its feeder mounted by hand for the order | Economic: 3.07 USD feeder loading. Standard: 1.53 USD feeder loading | As Basic | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-price, *Feeder Loading* and *Extended Components Fee* | 2026-10-13 |
| Minimum quantity charged per part, any class | A part used in fewer than its minimum quantity is charged at that minimum, the spares being kept for attrition and not returned | — | **Not established for any part**: no page read states the minimum, and a part's page does not display it. JLCPCB's online quote shows the exact components cost once the parts are selected for an assembly order, so it is read there for a given parts list | unmeasured (the minimum); published unverified, read at source (that a minimum applies, and where the cost is shown) | https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, item 4; https://jlcpcb.com/help/article/pcb-assembly-faqs, item 1 | 2026-10-13 |
| Parts outside the public library | Global sourcing (9–15 days), parts pre-ordered into a private library, and parts consigned by the customer, each usable in an assembly order under the restrictions the page states | — | — | published unverified, read at source | https://jlcpcb.com/help/article/pcba-parts-sourcing-instruction, items 1 and 2 | 2026-10-13 |

The price of a part changes between orders and between JLCPCB and its sister distributor LCSC; the price shown at the time of ordering is the one charged (https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, item 11).

## Which parts are fitted by hand

| Rule | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Parts JLCPCB fits by hand | A part whose page in the parts library gives its *Assembly Type* as *Wave Soldering* is a through-hole part, assembled manually and charged at the manual assembly rate per joint plus the hand-soldering labour per order. A part given as *SMT Assembly* is placed by machine | Either service | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs, item 2; the charges from https://jlcpcb.com/help/article/pcb-assembly-price, *Manual Assembly* and *Hand-soldering Labor*; the *Assembly Type* field on each part's page | 2026-10-13 |
| Surface-mount parts JLCPCB places by hand | Parts the placement machine cannot take, such as a rough top surface, a tall body or one the nozzle cannot pick, are placed manually | Either service | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, item 12 | 2026-10-13 |
| Parts the builder fits | Any part not in JLCPCB's library, not sourced or consigned through it, or not selected and confirmed in the order is not fitted, and is not shipped with the boards, so the builder fits it after delivery | Either service | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, items 7 and 15 | 2026-10-13 |

The disagreement in JLCPCB's wording is recorded as found: its assembly capabilities page says through-hole parts are soldered by wave soldering, while its assembly FAQ says parts marked *Wave Soldering* "will be assembled manually". The charge is the same either way, the manual assembly rate per joint, so this record takes the charge and does not settle the process.

## File formats

| File | What JLCPCB accepts | Grade | Source | Read |
|---|---|---|---|---|
| Fabrication | Gerber files with drill data, all required layers (copper, soldermask, silkscreen, outline) compressed into one ZIP file. Recommended layer names: `.GTO` top silkscreen, `.GTS` top soldermask, `.GTL` top copper, `.G2L`, `.G3L`… inner copper, `.GBL` bottom copper, `.GBS` bottom soldermask, `.GBO` bottom silkscreen, `.XLN` drills, `.GKO` or `.GM1` board outline, with only one outline layer in the file. Any other layer is ignored unless its use is remarked when ordering | published unverified, read at source | https://jlcpcb.com/help/article/gerber-files-preparation; the ZIP requirement from https://jlcpcb.com (home page, *Ordering Instructions*) | 2026-10-13 |
| Parts list (BOM) | `.csv`, `.xls` or `.xlsx`, with columns *Comment* (value and specification), *Designator* (letter case is not used to tell parts apart) and *Footprint* (package) | published unverified, read at source | https://jlcpcb.com/help/article/bill-of-materials-for-pcb-assembly | 2026-10-13 |
| Component placement (CPL) | `.csv`, `.xls` or `.xlsx`, with columns *Designator*, *Mid X* and *Mid Y* (the part's centroid, in millimetres), *Layer* (Top or Bottom) and *Rotation* (degrees, counter-clockwise positive). Rotation is corrected by JLCPCB's engineers from the silkscreen polarity mark where it does not match | published unverified, read at source | https://jlcpcb.com/help/article/pick-place-file-for-pcb-assembly; https://jlcpcb.com/help/article/pcb-assembly-faqs-part-2, items 2 and 10 | 2026-10-13 |
| Files from KiCad | JLCPCB publishes step-by-step export guides per KiCad version, linked from its file-preparation help catalogues | published unverified, read at source | https://jlcpcb.com/help/catalog/180-PCB-Files-Preparation; https://jlcpcb.com/help/catalog/190-PCBA-Files-Preparation | 2026-10-13 |

## Shipping

What shipping costs depends on the destination, so the cost of shipping a board order to a builder is kept in that builder's machine record, not here. JLCPCB's shipping calculator, at https://jlcpcb.com/shipping, quotes each method's cost by destination country and chargeable weight, and states that the cost it gives "is for reference only. The final shipping cost will be confirmed at checkout". Since 2026-08-22 JLCPCB's special shipping rates are available only through its JLCONE desktop application (https://jlcpcb.com/news/jlcpcb-jlcone-desktop-app, *Exclusive Shipping Rates & Routes*), so the website calculator's figures need not match what that application charges. Import duties and taxes are the importer's and are not estimated by JLCPCB (https://jlcpcb.com/help/article/Shipping-Methods-and-Delivery-Time). All read 2026-10-13, graded published unverified, read at source.
