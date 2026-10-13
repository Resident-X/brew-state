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

## Fabrication limits

Each is a minimum the manufacturer will make unless the entry says otherwise. A board-wide minimum a design-rules row takes from here takes the entry's condition with it.

### Tracks and spacing

| Limit | Value | Condition | Grade | Source | Read |
|---|---|---|---|---|---|
| Minimum track width and spacing | 0.10 mm / 0.10 mm (4 / 4 mil) | 1- and 2-layer boards, 1 oz finished copper | published unverified, read at source | https://jlcpcb.com/capabilities/pcb-capabilities, *Traces*, "Min. track width and spacing (1 oz)" | 2026-10-13 |
| Minimum track width and spacing | 0.09 mm / 0.09 mm (3.5 / 3.5 mil); 3 mil accepted in BGA fan-outs | Multilayer boards, 1 oz | published unverified, read at source | Same page, same row | 2026-10-13 |
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
| Drill diameter, smallest offered | 0.10 mm, at extra cost | 2-layer and multilayer boards no thicker than 1 mm, ENIG or OSP finish only | published unverified, read at source | Same page, same row | 2026-10-13 |
| Finished hole size tolerance | +0.13 / −0.08 mm | Plated through-holes | published unverified, read at source | Same page, *Drilling*, "Hole size Tolerance" | 2026-10-13 |
| Recommended smallest plated hole | 0.5 mm | Plated through-holes, so that soldermask or tin does not stick in the hole | published unverified, read at source | Same page, same row, description | 2026-10-13 |
| Minimum via hole / via diameter | 0.15 mm / 0.25 mm | 2-layer and multilayer boards | published unverified, read at source | Same page, *Drilling*, "Min. Via hole size/diameter" | 2026-10-13 |
| Minimum via hole / via diameter, smallest offered | 0.10 mm / 0.20 mm | Boards no thicker than 1 mm, ENIG or OSP finish only | published unverified, read at source | Same page, same row | 2026-10-13 |
| Via diameter over via hole | At least 0.10 mm larger, 0.15 mm preferred | Any board | published unverified, read at source | Same page, same row, note ① | 2026-10-13 |
| Preferred minimum via hole | 0.20 mm | Any board | published unverified, read at source | Same page, same row, note ② | 2026-10-13 |
| Via sizes that cost more | A 0.10 or 0.15 mm hole at any diameter; a 0.20 or 0.25 mm hole with a diameter under 0.45 mm | Any board; the matching via option must be chosen when ordering | published unverified, read at source | Same page, same row, note ③ | 2026-10-13 |
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
| Board-size threshold of the lowest price band | A single board within or equal to 102 × 102 mm is charged a special price only. A panelised board (V-cuts or routed lines between boards) is charged the engineering fee plus the board fee instead, whatever its size | Single-board delivery | published unverified, read at source | https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, item 7, *Board Fee* | 2026-10-13 |
| Fabrication price of a minimum order, lowest band | From 2.00 USD for 5 boards | 1–4 layers, 100 × 100 mm; "from" means the lowest options; ordered through the JLCONE desktop application only, since 2026-08-22, when the deal was withdrawn from the website | published unverified, read at source | https://jlcpcb.com/ads/pcb-prototype, *Standard Prototype PCB*; https://jlcpcb.com/news/jlcpcb-jlcone-desktop-app, *Exclusive $2 PCB Special Deal* | 2026-10-13 |
| Fabrication price of a minimum order, lowest band, multilayer promotion | From 2.00 USD for 5 boards | 6–8 layers, 50 × 50 mm, same desktop-application condition | published unverified, read at source | https://jlcpcb.com/ads/pcb-prototype, *Advanced Multilayer PCB* | 2026-10-13 |
| Fabrication price of a minimum order, above the lowest band | **Not established.** JLCPCB publishes no figure for a board over 102 × 102 mm or panelised: such a board is priced as engineering fee plus board fee by the instant quote for its outline, layer count and options. It is read by entering the board's outline and options at the quote page, at the quantity of 5, once a board's outline is known | Single board over 102 × 102 mm, or any panel | unmeasured | https://cart.jlcpcb.com/quote; the band's existence from https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, item 7 | 2026-10-13 |
| Extra charge for a small board | 0.02 USD per board with a side of 15–30 mm; 0.05 USD per board with a side under 15 mm | Burr removal and corner rounding; a further charge applies to boards with a side of 30 mm or less delivered as single boards | published unverified, read at source | https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, items 6 and 10 | 2026-10-13 |
| Extra charge for a large board | Charged per further 50 cm² over 650 cm² of one board's area | Fabrication | published unverified, read at source | Same page, item 15 | 2026-10-13 |
| Extra charge for several designs in one file | Charged per extra design | One Gerber file holding more than one design | published unverified, read at source | Same page, item 1 | 2026-10-13 |

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
| Single-board assembly surcharge | — | Makes up the SMT charge to at least 0.48 USD per board | published unverified, read at source | Same page, *Single board assembly surcharge* | 2026-10-13 |
| Handling fee | — | At least 14.93 USD, charged when Standard costs less than 14.93 USD more than Economic for the same order | published unverified, read at source | Same page, *Handling fee* | 2026-10-13 |
| Fixtures, rigid board | — | 8.21 USD each; 2 fixtures (16.42 USD) for 1–29 boards | published unverified, read at source | Same page, *Fixture (Standard Rigid PCB)* | 2026-10-13 |
| Packing | Free | 0.50 USD + 0.00003 USD per cm² of board | published unverified, read at source | Same page, *Packing* | 2026-10-13 |
| Large board | 57.46 USD | 57.46 USD | published unverified, read at source | Same page, *Large Size*, when the board area exceeds 650 cm² | 2026-10-13 |
| X-ray inspection | 1.64 USD per component for 1–10 components, falling with count | Same | published unverified, read at source | Same page, *X-ray Inspection*, applied automatically to BGA, QFN and other leadless parts | 2026-10-13 |
| Placement confirmation | 0.45 USD | 0.45 USD | published unverified, read at source | Same page, *Confirm Parts Placement* | 2026-10-13 |
| Components | At each part's catalogue price | Same | published unverified, read at source | Same page, *Components*, "Per system" | 2026-10-13 |

## Parts library classes and their fees

Every part in JLCPCB's catalogue carries a library class, shown on its page in the parts library at https://jlcpcb.com/parts. Each class is a condition on the fees below.

| Class | What it is | Setup fee per unique part, per order | Per-part fee | Grade | Source | Read |
|---|---|---|---|---|---|---|
| **Basic** | Frequently used parts held loaded on the placement machines | Economic: none. Standard: 1.53 USD feeder loading | None beyond the part's catalogue price and the per-joint assembly charge | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs, item 6; https://jlcpcb.com/help/article/pcb-assembly-price, *Feeder Loading* | 2026-10-13 |
| **Preferred** (an extended part so marked) | Parts formerly Basic, loaded by hand, exempt from Economic's feeder loading fee | Economic: none. Standard: 1.53 USD feeder loading | As Basic | published unverified, read at source | https://jlcpcb.com/help/article/pcb-assembly-faqs, item 7; https://jlcpcb.com/help/article/pcb-assembly-price, *Feeder Loading* | 2026-10-13 |
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
