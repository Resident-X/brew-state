# Fabrication notes: Sunbeam EM7000 main controller board

What the board maker is asked to build, as the design records state it at the commit that adds this file, and what is still open before the board is ordered. It carries the production-side statements the graph asks of the main board (laminate, coat) and says plainly where the evidence for them is missing. Nothing here is signed or accepted by this file; the separation basis (`hardware/sunbeam-em7000/separation-basis.yaml`) is signed (2026-11-05, re-signed 2026-11-06, on the owner's written instruction entered by Claude, its 33 accepted exceptions of that day signed with it, one of which, the C606 pad pair, was removed on 2026-11-07; the record holds 42 accepted exceptions today, each with its own acceptance date: 23 of 2026-11-06, 3 of 2026-11-07 and 16 of 2026-11-14) and so are the ten exceptions of the derating policy (`derating-policy.yaml`).

Maker figures are from JLCPCB's published capabilities page (https://jlcpcb.com/capabilities/pcb-capabilities), re-read on 2026-11-05 and held in `manufacturer-limits.yaml` and `docs/board-manufacturer-jlcpcb.md`. Where this file says the maker publishes nothing, that is what the pages read on 2026-11-05 held, not a statement about the maker's practice.

## Board

| Item | Statement | Source |
|---|---|---|
| Outline | 131.0 x 125.6 mm | `manufacturer-limits.yaml` header |
| Thickness | 1.6 mm (offered at six layers; 2.5 mm and over is reserved for 12 layers and more) | `design-rules.md` Stackup row; `manufacturer-limits.yaml` |
| Copper layers | six, in this order from the component side: F.Cu (components, signals); In1.Cu (solid `GND` plane, nothing routed); In2.Cu (`GND` fill, permitted signals, a `+3V3` pour over the low-voltage digital area, and the `Mains`-class routes inside the `mains` region); In3.Cu (signals, and two `Mains`-class runs inside the `mains` region); In4.Cu (`GND` fill, slow nets only, never `Fast`, `Sense`, supply or `Mains`); B.Cu (tracks, `GND` pour, test pads) | `design-rules.md` Stackup row |
| Copper weight | 1 oz finished outer copper (the weight a standard multilayer order carries without a surcharge); inner copper 0.5 oz, the maker's default for a multilayer board, taken as is | `board-rules.yaml` `fabrication.outer_copper_oz: 1`; `manufacturer-limits.yaml` |
| Surface finish | ENIG. The maker does not offer HASL at six layers or more; OSP is the other offered finish and is not chosen | `manufacturer-limits.yaml` header; `design-rules.md` Stackup row |
| Controlled impedance | none asked | `manufacturer-limits.yaml` header |
| Panel, tolerance and delivery options | not chosen in any record; set at the quote | none |

## Vias and drills

| Via | Count in the placed board | Annular width | Use |
|---|---|---|---|
| 0.6 mm pad, 0.3 mm drill | 466 | (0.6 - 0.3) / 2 = 0.15 mm (the maker's absolute minimum, below its 0.20 mm recommendation) | every ordinary via: signal, ground and supply nets |
| 0.7 mm pad, 0.3 mm drill | 6 | (0.7 - 0.3) / 2 = 0.20 mm (the maker's recommended figure) | four on `+5V`, one each on the converter nets `AMC_DCDC_OUT` and `AMC_HLDO_IN` |
| 0.75 mm pad, 0.3 mm drill | 69 | 0.225 mm | mains-class vias (the `Mains` classes' routing default) |

The board has 541 vias, read from the board file on 2026-11-15, after the four ground vias beside the tab of U302 were placed; the counts of `design-rules.md`, "Via sizes in the layout", are the same. Every drill is 0.3 mm, over the maker's 0.15 mm minimum drill, and every via pad is 0.30 mm or more over its hole. No via stands inside a surface-mount pad. The board setup's minimum annular width is 0.15 mm, the ring of the 466 vias of 0.6 mm pad; the deviation from the recommended 0.20 mm is signed, on the owner's behalf under his standing instruction of 2026-11-07, as S-24 of `owner-sign-off.md` (`design-rules.md`, Minimum annular width; `layout-plan.md` MFG-1). No 0.2 mm drill is placed, so the maker's capability charge for it and its four-wire test do not arise (`design-rules.md`, Via sizes in the layout).

## Laminate and comparative tracking index (graph criterion C16)

The requirement: the notes specify a laminate whose published comparative tracking index (CTI) is at least 175 (material group IIIa or better), the figure the basis's material group rests on, and cite the laminate maker's document for that index and the revision read. A family whose maker publishes no index in the documents read is listed as such and is not specified. A family specified with no such document cited is not specified. At pollution degree 2 the material group III column covers IIIa and IIIb alike, so a published index below 175 changes no figure of the basis and is not a precondition; the order stops only for a laminate published below 100 (no material group in IEC 60664-1) or a pollution degree 3 fallback taken without an index of 175 or more recorded. The criterion was reworded once: its first text asked for the maker's current document, which the repository cannot show (the makers' sites could not be reached and the copies read are distributors'); the maker's written laminate identity and certificate, which would settle it, are asked for by a criterion of the order leaf and recorded before payment.

### What the board maker says about its laminate (read 2026-11-05)

- Capabilities page (https://jlcpcb.com/capabilities/pcb-capabilities): material "FR-4 Grade A laminates from suppliers including Nan Ya, KB, Shengyi and etc."; for HDI builds only, "Nan Ya NP-175F TG170 / Shengyi S1000-2M TG170". No laminate is named for a standard six-layer order and no CTI is stated.
- Materials page (https://jlcpcb.com/resources/pcb-material): names Rogers and Nan Ya as suppliers, offers a choice of standard multi-layer stackups and of TG value, and says nothing about choosing a laminate brand or about CTI. Its FAQ on custom material requirements answers, as far as the page reader returned it, that the customer should contact customer support.
- Certifications help page (https://jlcpcb.com/help/article/Certifications): no laminate datasheet link, no supplier name and no CTI statement in the text returned. A web-search summary said the page lists Nan Ya NP-140F and NP-155F, Shengyi S1000-2M and KB-6164 datasheets; the page reader could not confirm that, so it is not relied on.
- Help-centre pages for material datasheets (https://jlcpcb.com/help/article/PCB-Material-Datasheet) are script-rendered; fetched with curl they return only the page shell.
- The quote's default option read on 2026-10-13 (`docs/board-manufacturer-jlcpcb.md`) is "FR-4, TG 135-140", with no laminate maker or product.
- A customer question on the maker's forum (https://jlc3dp.com/help/answers/detail/961-What-material-group-according-to-UL-would-the-FR-4,-Nan-Ya-NP-140F,-PCB-boards-have) asks for the material group of "FR-4, Nan Ya NP-140F" and carries no answer.

### Laminate makers' own datasheets (read 2026-11-05)

Each figure is as printed, from the page shown, at the 1.6 mm specimen thickness the sheet states. The files were fetched with curl and read with pdftotext (and, for S1000-2, as a rendered image, since its text is outlines). These are copies hosted by distributors, not the makers' own sites; the revision is the one on the copy. The makers' sites could not be reached for current revisions, so none of these is shown to be the maker's current document; the order leaf's criterion for the maker's written identity and certificate carries that.

| Family | Document, revision as printed | Copy read | CTI as printed |
|---|---|---|---|
| Shengyi S1000-2M / S1000-2MB | "S1000-2M data sheet (20120321)" (file title), 3 pages | https://a-contract.ru/fileadmin/datasheets/base-material/S1000-2M.pdf; same text in the 2013-05 copy at https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/1023/S1000_2D00_2M-data-sheet.pdf | General Properties table, page 1: CTI, IEC60112 Method, V, Spec "PLC3(175~250)", Typical Value "PLC3(200V)". The sheet says its data are typical values and not specification values. |
| Shengyi S1000-2 / S1000-2B | no revision printed; page "-31-" of a catalogue; file created 2009 | https://a-contract.ru/fileadmin/datasheets/base-material/S1000-2.pdf | General Properties table, page 1: CTI, IEC60112 Method, V, Spec "PLC 3(175V--249V)", Typical "PLC 3". Remark 3: typical values are for reference. |
| Shengyi S1141 | no revision printed; file created 2003 | https://a-contract.ru/fileadmin/datasheets/base-material/S1141.pdf | General Properties table, page 1: CTI, IEC60112 Method, V, Spec "-", Typical Value "175". No specification limit is printed, so 175 is a typical value with no guarantee. |
| Kingboard KB-6165F (lead-free series sheet) | "KB-616XF (Lead Free Series)", Version 2.0 / 2.1 (file dated 2012-04) | https://www.intectiv.si/wp-content/uploads/2023/08/Technical-data-sheet-KB-6165F-min.pdf | Purchasing Information table, page 3: column "CTI Value", "175V", beside the yellow base colour and the thickness and sheet-size rows. No test method is printed with it, and it is not in the General Properties table. |
| Kingboard KB-6165 | "KB-6165 Technical Information", Version 1.0 | https://a-contract.ru/fileadmin/datasheets/base-material/KB-6165.pdf | No CTI, tracking or IEC 60112 entry anywhere in the text. Not found. |
| Kingboard KB-6160 / KB-6164 | combined sheet KB-6160_6165_H140_150 (https://www.rezonit.ru/upload/spetsifikatsii/KB-6160_6165_H140_150.pdf) | the downloaded file was damaged (no readable cross-reference table) | Not read. A search summary said it gives "greater than 175 V"; that is not relied on. |
| Nan Ya NP-140TL (NP-140B on the same file) | Nan Ya data sheet, no revision date printed in the text | https://www.epectec.com/downloads/NAN-YA-NP140TL-Data-Sheet.pdf and https://www.mclpcb.com/wp-content/uploads/2021/05/NP-140TL.pdf | No CTI, tracking or IEC 60112 entry in either copy. Not found. NP-140F and NP-155F (the grades the maker's forum mentions) were not found in any datasheet that could be read. |

Reading of the figures against 175 V:

- Published as a specification, class and range printed with the method named: S1000-2M (class PLC3, range 175 to 250, typical 200) and S1000-2 (PLC 3, range 175 to 249). These two are specified.
- Printed, but not a specification: S1141 (175 typical, no specification limit, and a typical value is not a minimum) and KB-6165F (175 V with no test method printed). These are listed as typical value or no method printed, and are not specified.
- Not published in the documents read: KB-6165, Nan Ya NP-140 family (NP-140TL sheet), KB-6160 and KB-6164 (sheet not readable).
- A published figure of exactly 175 V sits on the group boundary, with no margin: material group IIIa is CTI 175 to 399 (`separation-basis.yaml`). Only the S1000-2M and S1000-2 sheets print a class and a range that states 175 as the lower limit of PLC3, which is why only those two are specified.

### What the order can and cannot require

The maker's pages read give the customer a choice of stackup and TG value and nothing that selects the laminate maker or product. They name the families above as a pool ("Nan Ya, KB, Shengyi and etc."), not as an order option, and say custom material requirements go through customer support. Nothing read shows that a laminate brand can be written into the order form or a notes field and be honoured, or that the shipped brand is reported to the customer.

So: the order cannot be shown to require any laminate. The CTI of the laminate actually shipped is unverified, and could be any family in the pool, including ones whose published CTI was not found above.

Before ordering, the owner asks the maker's customer support, in writing, for: (1) the laminate maker and product that will be used for this six-layer 1.6 mm order, with that maker's datasheet; (2) confirmation that it can be fixed to one of the two specified families (S1000-2M or S1000-2) at order time, and the order-form field or note that does it (the order note to carry is: "laminate: Shengyi S1000-2M or S1000-2, comparative tracking index class PLC 3 (175 V or more) per IEC 60112; report any substitution before production"); (3) a material or conformance certificate for the shipped lot stating the CTI to IEC 60112, or the laminate maker's report. If the maker cannot fix the laminate or supply the certificate, the order is not held for it at pollution degree 2: see the next section.

### CTI research of 2026-11-05 and the order stance

Verified in the standards' text as read (IEC 60664-1:2007 Table F.4 and clauses 4.8.1.3 and 5.2.4; IEC 60335-1 Table 17 only as a test-house report form reproduces it): at pollution degree 2 the "other materials" column is one group III column covering IIIa and IIIb alike (250 V: group I 1.25, II 1.80, III 2.50 mm basic; reinforced is twice basic, 5.0 mm). A laminate CTI under 175 therefore changes none of the basis's pollution degree 2 figures, and the 10.0 mm mains-to-low-voltage creepage is well above the 5.0 mm reinforced figure. The printed-wiring column, which excludes IIIb, is not used. A CTI of 175 or more matters only for a pollution degree 3 fallback (IEC 60335-1 as reproduced allows IIIb at pollution degree 3 only to 50 V) or the printed-wiring column. A CTI under 100 falls in no group and no figure was found for it.

Verified about the maker: JLCPCB names a pool of laminate makers (Nan Ya, KB, Shengyi and others, including lesser-known Chinese laminates in its UL listing) and gives no way found to fix a laminate or to obtain a CTI certificate. Its hosted datasheets print ">175" for KB-6164 and KB-6165F and "PLC 3" as a typical value for S1000-2M TG170, S1000H and S1141; Nan Ya NP-140F, NP-155F and NP-175F print no CTI. Not verified: which laminate a six-layer 1.6 mm lot receives, any order field or note that fixes it, any lot-specific certificate, the 2020 edition of IEC 60664-1 and the 6th edition of IEC 60335-1, and the numeric range of PLC 3 from UL 746A.

The order stance: the order carries a laminate note naming Shengyi S1000-2M or S1000-2 (or Kingboard KB-6165F or KB-6164) as the preferred families, as advice and not as a requirement the maker is shown to honour. A CTI certificate is not a precondition to payment at pollution degree 2. The owner asks JLCPCB support once, in writing, for the laminate maker and product and for a conformance statement, and records the answer as evidence (`SOL-HW-CONTROLLER-BOARDS-ORDERED-AND-RECEIVED.C5`). An IEC 60112 test of a delivered sample is the only real verification of the shipped laminate. The statements under criterion C16 below stay as written: the specified families are those whose maker prints the class and range.

### Status

Criterion C16, as amended, is **met on paper**; the shipped laminate is **not verified**. What the notes state, clause by clause:

- Families specified, with a published CTI class and range of at least 175 (material group IIIa or better): Shengyi S1000-2M / S1000-2MB (class PLC3, specification "175~250", typical "200V") and Shengyi S1000-2 / S1000-2B (PLC 3, "175V--249V").
- Families listed and not specified, typical value or no method printed: Shengyi S1141 (typical "175", no specification limit printed) and Kingboard KB-6165F ("175V", no method printed). A typical value is not a minimum, and a figure with no method is not an IEC 60112 result.
- The maker's document and the revision read, for each specified family: the table above gives them as printed (S1000-2M "data sheet (20120321)"; S1000-2 with no revision printed), and says the copies are hosted by distributors.
- The order note that requires the families: "laminate: Shengyi S1000-2M or S1000-2, comparative tracking index class PLC 3 (175 V or more) per IEC 60112; report any substitution before production".
- The written request the owner makes of the maker's customer support: the laminate maker and product for this order with its datasheet; confirmation that it can be fixed to one of the two families and the field that does it; and a certificate of the shipped lot's CTI to IEC 60112.
- Families whose maker publishes no index in the documents read (KB-6165, Nan Ya NP-140 family, KB-6160 and KB-6164) are listed as such and are not specified.

What remains unverified, and is a pre-order action for the owner: the identity and CTI of the laminate the maker will ship, until the maker answers the request; that the maker's pages let the order fix a laminate at all (nothing read shows it); and that the distributor copies are the makers' current revisions (the makers' sites could not be reached). The maker's written laminate identity and CTI certificate, or the owner's re-declared material-group basis, are recorded before payment as a criterion of the order leaf. Choosing the laminate's supplier and receiving the certificate are out of scope of criterion C16.

## Conformal coat (graph criterion C17)

The requirement: the notes name the coat that supports the basis's pollution degree 2 credit (which rests on the enclosure), with its type and the maker's current datasheet, and state that it is applied after bring-up, once the machine is deemed functional from a hardware perspective, and covers the gaps between the board's mains pads, except keep-outs for contacts listed by reference designator.

Status: criterion C17 is **met on paper** (read 2026-11-17). The coat is a supporting measure and earns no part of the pollution degree 2 credit, which stands on the enclosure (`separation-basis.yaml` conditions 1 and 2). No coating test is planned and none is claimed (`layout-plan.md` ENV-1 row).

### Coat chosen

Type: one-part acrylic conformal coating in an aerosol can. It is chosen for application at home with no equipment beyond a ventilated space: spray, room-temperature cure, no oven, no vacuum, no mixing, and rework by a common solvent or by soldering through it.

- **Product: MG Chemicals 419D Acrylic Conformal Coating, aerosol, part number 419D-340G** (410 mL, 340 g net).
- **Fallback, equivalent type: Techspray Turbo-Coat Acrylic Conformal Coating, aerosol, product 2108-12S** (12 oz).
- **Australian supply (web search 2026-11-17; the retailer's page itself was not opened):** Mektronics (mektronics.com.au) lists the 419D 340 g aerosol as in stock at 82.81 AUD including GST, and lists the Techspray Turbo-Coat 12 oz acrylic at 64.22 AUD including GST. Aerosols are dangerous goods in freight, so a courier may refuse or surcharge them; the owner confirms shipping terms with the seller at purchase. Choosing the supplier is out of scope of the criterion.

### The maker's current datasheet

- **419D-340G:** "419D Aerosol, Acrylic Conformal Coating", technical data sheet, 3 pages, dated 31 July 2025, Ver. 4.0. `https://mgchemicals.com/downloads/tds/tds-419d-a.pdf`, the address the product page on mgchemicals.com links for the aerosol, fetched 2026-11-17. It is the maker's own copy and the revision on the maker's site that day. The copy is kept outside the repository and is not committed.
- **Safety data sheet read for the flammability figures:** MG Chemicals "Premium Acrylic Conformal Coating", SDS code 419D-Aerosol, a distributor-hosted copy (`https://assets.testequity.com/te1/Documents/pdf/MG-Chemicals/mg-sds-419d-a.pdf`, no revision date read); not the maker's current SDS, so the owner reads the SDS packed with the can.
- **Fallback:** "Turbo-Coat Acrylic Conformal Coating, Product# 2108", Techspray, Rev. D (3/21), 4 pages, `https://www.techspray.com/content/msds/TS-2108_ENG_TDS.pdf`, fetched 2026-11-17.

Figures relied on, as printed on the 419D sheet (the fallback's, where read, follow in brackets):

| Need | Printed figure |
|---|---|
| Dielectric strength | "Dielectric Strength 1 000 V/mil"; "Breakdown Voltage >1 500 V" (ASTM D149). [2108: "Dielectric strength 1000 volts", ASTM D-149 / IPC-TM-650 2.5.6.1] |
| Service temperature | "-65-125 C". [2108: "-65 to 125 C"] The enclosure air is assumed at 70 degC until bring-up measures it, and the joint cap in the bring-up record is 110 degC, both under 125 degC. |
| Moisture, fungus | "protects effectively against moisture, corrosion, fungus, dirt, dust, thermal shock, short circuits, high voltage arcing"; "Moisture Insulation Resistance 1 x 10^12 ohm.cm" (IPC-TM-650 2.6.3.4). [2108: IPC-CC-830B fungus resistance, moisture and insulation resistance and dielectric withstand voltage "pass"] |
| Standards | "Certified UL 94 V-0 (File# E203094)"; "Certified IPC-CC-830B". [2108: UL94/746E V-0, IPC-CC-830B qualification] |
| Cure | "Dry Time to Handle 10 min (1 coat), 20 min (2 coats)"; "Minimum Recoat Time 3 min"; "Allow to dry at room temperature for 24 hours". [2108: dry to touch 3 min, ambient cure 15 hours at 23 degC] |
| Thickness | "Recommended Film Thickness 25-75 um"; theoretical coverage 5 700 cm2 per can at that thickness. |
| Rework | "It may be removed with appropriate strippers, or soldered through for repair or rework." [2108: removal "Alkane, Acetone or Acetate, Solder iron burn through"; Techspray removal pen 2510] The sheet names no stripper for 419D; Mektronics' listing names MG 435 Thinner, 8309 and 8310A removers, which the owner confirms on the maker's pages before relying on them. |
| Preparation | "Clean the substrate with MG #824 99.9% Isopropyl Alcohol". |
| Spray | "Shake the can vigorously"; spray a test pattern; "Tilt the board at 45 degrees and spray a thin, even coat from a distance of 20-25 cm"; "Wait 3 min before applying another coat"; "Rotate the board 90 degrees and spray again". |
| Flammability (SDS) | Flammable aerosol category 2; flash point 9 degC; flammable limits 2 % to 11 % (dimethyl ether propellant); "Use only outdoors or in a well-ventilated area"; keep away from sparks and flames. The sheet prints a glass transition of 27 degC, so the film is above it, and soft, at the enclosure's 70 degC; the sheet prints no figure for that state and none is relied on. |

What the sheet does not say: it states no creepage or clearance credit and no pollution degree, so none is taken from it; the coat stays a support, as the basis states. The cured film's chemical resistance is printed "Poor", so the coat is no protection against solvent spills; the enclosure is.

### When it is applied

After bring-up, once the machine is deemed functional from a hardware perspective (owner, 2026-11-06). Until then the board is uncoated: the board's first connection to mains and the bring-up bench tests run on the uncoated board, in a clean room, and the coat is no part of the bound on any fault between mains pads until it is applied. The coat is applied by the owner at home. It covers the gaps between the board's mains pads on both faces, which the layout plan's `mains` region and the mains-referenced test pads on B.Cu define, and in practice the whole board face except the keep-outs below.

### Home application steps

1. Finish every bring-up repair first. The two wire links JP101 and JP303 are fitted as links (JP101's first-power lamp removed), and any part to be fitted later (RT301, never with JP303) is fitted before coating, since a later part is soldered through the film.
2. Clean both faces with 99.9 % isopropyl alcohol and a clean brush, remove flux residue, and let the board dry. Handle by the edges.
3. Mask the keep-outs below with masking tape or a peelable mask, and plug the connector sockets and fuse holders with tape or foam. Do not let the tape lie on a pad it is to leave open without pressing it flat.
4. In a well-ventilated place away from flames, sparks and heaters (outdoors or by an open door, no pilot light or heater running), shake the can, spray a test pattern, then spray the board 20 to 25 cm away at 45 degrees in thin coats, rotating the board 90 degrees between coats, waiting 3 min between coats. Spray the bottom face the same way after the top has handled dry (10 min), propping the board on its edges. Aim for 25 to 75 um: two or three thin coats per face, never a heavy one, which traps solvent. Coverage check: one face of the board is 131.0 x 125.6 mm = 164.5 cm2 (about 330 cm2 for both faces), and the sheet gives 5 700 cm2 per can at the recommended thickness, so one can is enough for the job.
5. Peel the masking and plugs once the coat is touch dry (10 min), cutting along the tape edge with a knife first so no film lifts at the edge. Cure 24 hours at room temperature before powering or closing the enclosure.
6. Inspect under a bright light at a low angle, looking for bare gaps between mains pads, bubbles, pinholes, webs between pins, and film on a keep-out. A coat on a keep-out is removed with a swab and the removal solvent before it dries hard. A gap between mains pads is re-sprayed. The inspection is the owner's check; the sheet's UV-A fluorescence means a UV torch also shows coverage.
7. Record the day, the can's batch, and the inspection result in the bring-up record (`DEL-HW-BRING-UP`).

### Keep-out list (left uncoated, by reference designator)

Each part or area is derived from the board file and `parts-specification.yaml` read on 2026-11-17.

- **J101, J102, J103, J106, J107, J108, J109, J110** (push-on tab blades): the receptacle must grip bare metal. Mask the blade and its first 2 mm above the board; coat the board surface and the pad gaps up to the blade's base.
- **F701, F711, F731** (fuse holders, 5 x 20 mm): the clip contacts and the fuse ends must stay bare so a fuse can be changed. Mask the whole holder; coat the pads at the pins on the bottom face. F101 is a soldered pigtail fuse and is coated.
- **K201, K731, K741** (relays): film must not enter the case or its seams. The sealing type of these three is not read in the records, so treat them as vented: mask the case body above the board, coat the board and the pin bases on both faces so the gaps between their mains pins are covered.
- **J401** (SWD debug header) and **J402** (USB panel cable header): programming and the bench USB power path; mask the pins and the socket.
- **JP301, JP302, JP401, JP402, JP761, JP791, JP821** (jumper headers): the shorting jumper or the open link is moved or read in service; mask the header and its pins. JP101 and JP303 are wire links soldered in, not headers: they are coated.
- **J501, J502, J503, J520, J521, J522, J523, J524, J525, J570, J571, J620, J622, J623, J625, J627, J628, J630, J635, J761, J791, J821, J861** (sensor, probe, load-cell, wall-board, gauge, panel and knob headers and sockets): a plug mates in them; mask the connector body, its pins and the mating cavity. The solder fillets on the other face are coated.
- **SW401** (reset switch): film under the actuator can stick the switch; mask it.
- **H1, H2, H3, H4** (M3 lid screw holes, 3.4 mm, non-plated): mask the hole and a ring 3 mm wide round it, so a screw head or washer seats on the board and not on a film that creeps; H3 stands in the `mains` region, so its gap to the neighbouring mains pad is coated outside that ring.
- **The tank reed element at J862** (hand fitted, glass body): mask the glass body; the pads and solder joints are coated once it is soldered and tested.

Not keep-outs, and coated: the 84 test points on B.Cu (TP101 to TP108, TP603 to TP608, TP702 and TP712 among them stand in mains gaps; the bring-up bench tests that probe them are done before the coat goes on; a later probe is made through the film with a sharp probe tip, or the film is removed from the pad with the removal solvent); the resistor and capacitor pads; the fiducials FID1, FID2 and FID3 (an assembly aid, no function after assembly); the crystals Y401, Y402, Y601; the triacs T701 and T711 (their copper lands are the heat path and the film does not impair them; no heat sink is fitted to the board, and none is listed in the parts specification).

Applying the coat and choosing its supplier are out of scope of the criterion. The bring-up humidity step (`DEL-HW-BRING-UP`) is the only check planned for the pollution degree 2 credit, and it reads the closed machine, coated or not.

## Mask, silkscreen and assembly

No record chooses a solder mask colour or a silkscreen colour. The maker's quote defaults read on 2026-10-13 are green mask and white silkscreen; a colour other than green, red, yellow, blue or purple has a wider minimum mask bridge (black and white, 0.13 mm against 0.10 mm), so any change to a colour is a decision for the quote. The board's designators are on F.SilkS (and B.SilkS for the test pads), 376 of 446 of them after the rebuild of 2026-11-14 (`layout-plan.md`, MFG-7 states the 70 that are not); the mains warning stands on both sides inside the mains area, 2.0 mm text with an 8 mm triangle on the back and 1.5 mm text with a 6 mm triangle on the front, and F101's rating and the name of each tab stand beside the part. Assembly options (side, count, which parts) are in `parts-specification.yaml` and the cost estimate, not here.

### Tank reed J862, fitted by hand

The tank reed element is a glass-bodied switch that stands on the back of the board with its two leads through the holes of J862 and soldered on the front. It is in neither the placement file nor the parts list (its footprint carries `exclude_from_pos_files` and `exclude_from_bom`, its symbol `in_bom no`), so the assembler never sees it, and it has no catalogue number. Before soldering:

1. Measure the lead diameter with calipers. The footprint's holes are 1.0 mm drill with 2.0 mm round pads, 20.0 mm apart along Y (pad centre to pad centre); a lead over 0.8 mm will not leave a soldering gap in a 1.0 mm hole. The records do not give the lead diameter (`open-items.md`, reed element lead diameter); this measurement is what closes that row.
2. Form the leads to the 20.0 mm pitch and check the spacing after forming against the footprint's 20.0 mm: the leads must go in without being sprung.
3. The maker's minimum distance from the glass seal to the first bend is not stated by the records: hold the lead with pliers between the seal and the bend, and bend on the pliers' far side, so no bending force reaches the glass.
4. Do not cut the leads with a shear that shocks the glass: hold the lead with pliers between the seal and the cut, and cut on the far side of the pliers.

### Tab column, west edge

When the tabs and their leads are fitted by hand, support the board under the tab column near (7.0, 94.45) mm, midway between the tabs J103 (7.0, 90.2) and J102 (7.0, 98.7), with an insulating rest post, so that pushing a lead onto a tab does not flex the board at the notch beside the column.

### Wire links JP101 and JP303, fitted by hand

The first-power link JP101 (live, between the fuse F101 and everything it feeds) and the module feed link JP303 (between LINE and LINE_MOD) are two plated holes each, 10.0 mm apart (footprint JP101_WireLink_P10mm), with no catalogue number. They are left out of the position file (the footprint carries `exclude_from_pos_files`) and are listed in the bill of materials without an assembler part number, so the assembler's parts match leaves them unmatched and does not fit them. They are not marked "exclude from bill of materials" on the board because the pre-order check reads a board footprint with that mark as a mounting fixing and holds it to the Mains hole distance, and these two links are mains terminals. They are fitted, not left empty: the holes are not marked do-not-populate, and they are fitted by hand.

1. JP101: for the first power-up, fit a lamp (60 W to 100 W, 230 V) with its two leads in JP101's two holes in place of the wire; once the first-power steps in `bring-up-provision.md` are done, replace the lamp by the 1.5 mm2 wire link. The wire's insulation rating is an open owner item (`owner-sign-off.md` S-66; `open-items.md`).
2. JP303: fit a 1.5 mm2 wire link (or a component-lead off-cut) between the two holes; remove it if the inrush thermistor RT301 is ever fitted, never both (`open-items.md`).

## Unresolved before ordering

Both are unresolved in the records and must be checked at the quote, not assumed:

1. **Finish of vias over 0.55 mm at six layers.** The maker fills and plates over vias of 0.15 to 0.55 mm diameter by default at six layers and above; the page says nothing about a via over 0.55 mm. The board has 541 vias, all with a pad over that range (466 of 0.6 mm, 6 of 0.7 mm, 69 of 0.75 mm) and a 0.3 mm hole, none of 0.55 mm or less; no via stands inside a surface-mount pad.
2. **The six-layer engineering and board fee and the ENIG charge at 131 x 125.6 mm.** Only the quote reads them; the cost estimate carries an estimate, not a quote.

## Deviations carried by this board, all signed

Every one of these is signed. None changes a signed figure of the basis (signed 2026-11-05, re-signed 2026-11-06). They are held, with their measurements, in `owner-sign-off.md`; this file points to them and does not restate them.

- The 0.15 mm annular width of the 0.6 / 0.3 mm via (above): `owner-sign-off.md` S-24, signed on the owner's behalf under his standing instruction of 2026-11-07.
- The detour ratios of routed critical nets: `owner-sign-off.md` S-48 and S-49, signed on the owner's behalf in the workmanship acceptance lines (`workmanship-acceptance.yaml`, sessions of 2026-11-12 and 2026-11-14; the S-49 line of the coffee pump LED anode net, 2026-11-14). The mains-to-mains spacing shortfalls the layout check reports are excused by the basis's signed exceptions (33 on 2026-11-06, of which the C606 pad pair was removed on 2026-11-07; 42 today: 23 dated 2026-11-06, 3 dated 2026-11-07 and 16 dated 2026-11-14).
- The plated-hole pairs at 1.25 mm (J791, J821 and J861) and at 1.15 mm (J630 and J635, drilled 0.85 mm since 2026-11-14): exceptions of `hardware/sunbeam-em7000/separation-basis.yaml`, each entry accepted_on 2026-11-18 (the 1.25 mm entries first accepted on 2026-11-06 and the 1.15 mm entries on 2026-11-14), each by the owner, entered by Claude on the owner's written instruction (`owner-sign-off.md`, S-32, records the hole sizes).

## The board as it stands

- Board file `main-board.kicad_pcb`, sha256 38eb68f21d9cf9577df23d9291782348fceb2bc139937090c323dc511d4f8e02 (the board of 2026-11-17).
- 267 locked mains items in the `Mains` class (242 tracks and vias, 25 zones, read with `locked_copper.py record`), 541 vias, and the silkscreen title "BREW STATE" with the text "v1  2026-11".
- The back silkscreen carries the text "JLCJLCJLCJLC" at about (100, 8) mm on B.SilkS. It is understood to be the placeholder for the maker's order number; no record read for this file says what the maker does with it or what removing it costs. The owner decides at ordering whether to pay to have it removed or to leave it.
