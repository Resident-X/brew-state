#!/usr/bin/env python3
"""Merge the sheet files in ../sheets into ../schematic-spec.yaml (the one file the drawing agent reads).
usage: python3 spec-tools/build_spec.py      (run from the main-board folder; needs PyYAML)
The merged file is generated: change the sheet files and run this again, never edit schematic-spec.yaml by hand."""
import yaml, glob, collections, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kilib

ORDER = ["Mains entry and load feed", "Interlock", "Logic supply", "Controller",
         "Supply voltage and current measurement", "Zero-crossing detector",
         "Thermistor inputs", "Flow, pressure and spare analogue inputs", "Current sensing inputs",
         "In-stream temperature converters", "Load-cell amplifiers",
         "Pump drives", "Valve drives", "Heater LED drive and wall board header",
         "Gauge drive", "Operator panel and indicators", "Knob, tank-level and reed inputs"]
sheets = {}
for f in sorted(glob.glob('sheets/*.yaml')):
    d = yaml.safe_load(open(f)); d['source_file'] = os.path.basename(f); sheets[d['sheet']] = d
assert set(sheets) == set(ORDER), set(sheets) ^ set(ORDER)

MAINS_CLASS = """LINE_IN LINE_F LINE LINE1 NEUTRAL_IN NEUTRAL COFVALVE COFFPUMP STEAMPUMP HOTVALVE VALVE_COM
DISCH_A DISCH_B PUMP_C_MT2 PUMP_S_MT2 PUMP_C_GATE_R PUMP_S_GATE_R PUMP_C_OPTO_MT PUMP_S_OPTO_MT
PUMP_C_TRIAC_G PUMP_S_TRIAC_G VMEAS_N1 VMEAS_N2 VMEAS_DIV AMC_AIN0P AMC_AIN0N AMC_AIN1P AMC_AIN1N
AMC_DCDC_OUT AMC_DCDC_HGND AMC_HLDO_IN AMC_HLDO_OUT ZC_N1 ZC_LED_A SHUNT_SENSE_IN SHUNT_SENSE_NEUTRAL
LINE_MOD PUMP_C_SNUB PUMP_S_SNUB""".split()

out_sheets = []
refmap = {}
for i, name in enumerate(ORDER, 1):
    s = sheets[name]
    for p in s['parts']: refmap[p['ref']] = name
    out_sheets.append({
        'order': i, 'sheet': name, 'function': s.get('function'),
        'parts': s['parts'], 'nets': s['nets'], 'no_connect': s.get('no_connect') or [],
        'custom_symbols': s.get('custom_symbols') or [], 'custom_footprints': s.get('custom_footprints') or [],
        'power_flags': s.get('power_flags') or [], 'drawing_notes': s.get('notes')})

# net index
idx = collections.OrderedDict()
for s in out_sheets:
    for n, d in s['nets'].items():
        e = idx.setdefault(n, {'scope': d.get('scope'), 'sheets': []})
        e['sheets'].append(s['sheet'])
net_index = {n: {'scope': e['scope'], 'sheets': e['sheets'], 'class': 'Mains' if n in MAINS_CLASS else 'low-voltage'} for n, e in idx.items()}
for n in MAINS_CLASS: assert n in net_index, n

# controller pin-by-pin
ctrl = sheets['Controller']
u = [p for p in ctrl['parts'] if p['lib_id'].endswith('STM32H743VITx')][0]
pin_net = {}
for n, d in ctrl['nets'].items():
    for pin in d['pins']:
        if pin.startswith(u['ref'] + '.'): pin_net[pin.split('.')[1]] = n
for nc in ctrl.get('no_connect') or []:
    r, _, pn = nc['pin'].partition('.')
    if r == u['ref']: pin_net[pn] = 'NO_CONNECT: ' + nc['reason']
sym = {p['number']: p for p in kilib.sym_pins(u['lib_id'])}
controller_pins = []
for pn in sorted(sym, key=lambda x: int(x)):
    controller_pins.append({'pin': int(pn), 'port_or_name': sym[pn]['name'], 'net': pin_net[pn]})
assert len(controller_pins) == 100 and all(c['net'] for c in controller_pins)

# derived summaries
parts_total = sum(len(s['parts']) for s in out_sheets)
by_class = collections.Counter(p.get('class') for s in out_sheets for p in s['parts'])
hand = sorted(p['ref'] for s in out_sheets for p in s['parts'] if p.get('hand'))
custom_sym = [dict(c, sheet=s['sheet']) for s in out_sheets for c in s['custom_symbols']]
custom_fp = [dict(c, sheet=s['sheet']) for s in out_sheets for c in s['custom_footprints']]

header = {
 'ref': 'J761', 'part': 'WB_LV10, 1x10 2.54 mm pin header (BOOMELE 2.54-1*10PPin, C57369), to the heater wall board',
 'interface_source': 'docs/sunbeam-em7000/controller-board-division.md: The heater path, the interlock and the wall board (three conductors in use: the two opto-triac LED returns and their 5 V supply; seven ways spare, three of them for the reserved mains-presence confirms); The anticipated channel kinds',
 'pin_order_note': 'The division record fixes the interface (ten ways, three in use, the rest spare, the confirms reserved) and does not number the pins. This pin order is drawn here and is an open item the wall board design must meet (open-items.md).',
 'pins': [
  {'pin': 1, 'net': '+5V_WB', 'direction': 'power-leaving', 'use': 'LED supply to both heater opto-triac LEDs, from +5V through isolating link JP761'},
  {'pin': 2, 'net': 'HEAT_C_LED_K', 'direction': 'return sunk by Q761', 'use': 'coffee opto-triac LED return'},
  {'pin': 3, 'net': 'HEAT_S_LED_K', 'direction': 'return sunk by Q771', 'use': 'steam opto-triac LED return'},
  {'pin': 4, 'net': 'GND', 'direction': 'ground', 'use': 'low-voltage ground, in the cable for the reserved confirm places'},
  {'pin': 5, 'net': 'MAINS_PRES_C', 'direction': 'reserved input', 'use': 'coffee mains-presence confirm, not drawn (no parts); PE15 reserved'},
  {'pin': 6, 'net': 'MAINS_PRES_S', 'direction': 'reserved input', 'use': 'steam mains-presence confirm, not drawn (no parts); PD7 reserved'},
  {'pin': 7, 'net': None, 'direction': 'spare', 'use': 'no-connect, reserved'}, {'pin': 8, 'net': None, 'direction': 'spare', 'use': 'no-connect, reserved'},
  {'pin': 9, 'net': None, 'direction': 'spare', 'use': 'no-connect, reserved'}, {'pin': 10, 'net': None, 'direction': 'spare', 'use': 'no-connect, reserved'}],
 'neutral_return_landing': {'ref': 'J110', 'net': 'NEUTRAL', 'note': 'WB_RET: the eighth board-mounted 6.3 mm blade (C20626104, owner decision D8 drawn at the blade), a pad of the tab section in the NEUTRAL pour above the shunt; no retained lead lands on it, the wall board return wire ends in a female push-on on it'},
 'channels_crossing_header_for_the_pin_allocation_record': ['HEAT_C_DRV -> HEAT_C_LED_K (controller PD2)', 'HEAT_S_DRV -> HEAT_S_LED_K (controller PD3)', '+5V_WB (rail)', 'GND (rail)', 'MAINS_PRES_C (controller PE15, reserved)', 'MAINS_PRES_S (controller PD7, reserved)']}

anticipated = [
 {'kind': 1, 'name': 'Supply voltage measurement', 'placed': True, 'where': 'sheet "Supply voltage and current measurement": AMC131M02 channel 0 through the LINE to NEUTRAL divider; digital over SPI2 (the division record\'s analogue conditioning block VM_C became the converter\'s serial link; PB1 stays free)'},
 {'kind': 2, 'name': 'Weight-based endpoint, two load-cell channels', 'placed': True, 'where': 'sheet "Load-cell amplifiers": WT1_H, WT2_H headers and two HX711 amplifiers; PC8, PC9, PC11, PC12'},
 {'kind': 3, 'name': 'Further temperature and pressure inputs of the kinds in use', 'placed': False, 'reason': 'Removed in the division record\'s removal order (D12 drawn at the default). The criterion reserving it would have weakened is the fit: the header regions (46.5 mm wide, 2 x rectangles) cannot take its two two-way and one four-way headers at the 0.3 mm spacing the drawing keeps (no arrangement of the headers exists). Its pins PA4 and PA5 and the second I2C bus stay free on the controller.'},
 {'kind': 4, 'name': 'Direct group-head instrumentation, two channels', 'placed': False, 'reason': 'Removed in the division record\'s removal order (D12 drawn at the default). The criterion reserving it would have weakened is the fit: its two three-way headers cannot be placed in the header regions at the 0.3 mm spacing (no arrangement exists). Pins PA7 and PB0 stay free on the controller.'},
 {'kind': 5, 'name': 'Second current-sensing channel', 'placed': True, 'where': 'sheet "Current sensing inputs": CURR2_H header with burden position and filter to PA3 (CURR2_AN)'},
 {'kind': 6, 'name': 'A further switched output such as another valve', 'placed': False, 'reason': 'Not reserved by the owner\'s choice (2026-10-24, division record), not for want of room: no criterion is weakened.'},
 {'kind': 7, 'name': 'Spare analogue input', 'placed': True, 'where': 'sheet "Flow, pressure and spare analogue inputs": SPARE_AN2_H and conditioning to PA0 (SPARE_AN2)'},
 {'kind': 8, 'name': 'Current sensing, first channel', 'placed': True, 'where': 'sheet "Current sensing inputs": CURR1_H to PA2 (CURR1_AN)'},
 {'kind': 9, 'name': 'Total supply current measurement', 'placed': True, 'where': 'neutral shunt R105 (sheet "Mains entry and load feed") read as channel 1 of the AMC131M02'},
 {'kind': 10, 'name': 'Real-time clock', 'placed': True, 'where': 'sheet "Controller": LSE crystal Y402 on PC14/PC15 (fitted or left unfitted by the open item on the crystal row)'},
 {'kind': 11, 'name': 'In-stream temperature, two PT1000 probes', 'placed': True, 'where': 'sheet "In-stream temperature converters": PT1_H, PT2_H and two RTD converters on SPI2 (PB13, PB14, PB15), chip selects PB12 and PD8'},
 {'kind': 12, 'name': 'Brew-path pressure transducer', 'placed': True, 'where': 'sheet "Flow, pressure and spare analogue inputs": BREW_D (I2C2 on PB10/PB11) and BREW_A (analogue fallback to PA6)'},
 {'kind': 13, 'name': 'Supply frequency measurement', 'placed': True, 'where': 'shared with the zero-crossing detector, ZC_IN on PA10 (TIM1_CH3), both edges'}]

spec = {
 'board': 'Sunbeam EM7000 main controller board',
 'schema': 'Each sheet is one hierarchical sheet. parts lists every symbol; nets lists every net with every REF.PIN it joins (REF.PIN is the part reference and the symbol pin NUMBER). scope: local = a label on that sheet only; global = a global label carrying the net name across sheets; power = a power symbol / power-flagged net of that name on every sheet it reaches. custom_symbols / custom_footprints list what has no stock KiCad 10 equivalent.',
 'generated_by': 'spec-tools/build_spec.py from sheets/*.yaml; do not edit by hand',
 'drawing': {
   'tool_notes': [
    'Root sheet: one sheet symbol per entry of sheets, in order, named exactly as the sheet name, with no sheet pins; every connection between sheets is a global label (or a power symbol for scope: power).',
    'Every net carries the designer name given here; no tool-named net may remain. A pin in no_connect gets a no-connect flag.',
    'Symbol fields on every part: Reference, Value (value), Footprint (footprint), LCSC (lcsc), Rating (rating), plus Manufacturer and MPN (maker, mpn). A part with sim_exclude: true is excluded from simulation in its symbol properties.',
    'Flow left to right on each sheet: inputs and supply at the left, outputs at the right; positive supply toward the top, ground toward the bottom. Mains-referenced circuits stand at the left of a sheet and are drawn apart from low-voltage circuits (the barrier part between them); text clear of text and symbols; connector symbols show pin numbers and the net name beside every pin.',
    'Place every part named in a sheet: parts with dnp: true are placed and marked Do not populate; parts with hand: true are through-hole parts the owner fits by hand and are placed like any other.',
    'Project text variables: MAINS = present. Net class Mains: the nets listed in mains_class_nets.',
    'ERC: a net with only power_in pins needs a PWR_FLAG (the sheet\'s power_flags list names them); no warning may be waived or excluded.']},
 'project_settings': {'MAINS': 'present'},
 'mains_class_nets': MAINS_CLASS,
 'sheets_order': ORDER,
 'totals': {'sheets': len(out_sheets), 'parts': parts_total, 'nets': len(net_index), 'parts_by_catalogue_class': dict(by_class), 'hand_fitted_refs': hand},
 'header_to_wall_board': header,
 'anticipated_channel_kinds': anticipated,
 'controller_pin_assignment': {'part': u['ref'] + ' STM32H743VIT6, LQFP100, LCSC C114409', 'detail': 'proof-rows/B-pin-table.md carries the alternate functions, 5 V classes and reset states; this list is the connectivity', 'pins': controller_pins},
 'hold_off': {'record': 'circuit-proof.md section Hold-off; proof-rows A and D tables',
   'loads': [
    {'load': 'interlock relay coil K201', 'held_by': 'R201 and R202 (buffer input pulled low, no edge), the 56.5 ms gate decay, R205 and R206', 'states': 'reset, 3V3 absent, 5 V absent, rising, falling, output high or low or floating'},
    {'load': 'coffee heater (wall board opto-triac LED)', 'held_by': 'R762 gate pull-down on Q761; the LED has no supply when +5V_WB or its return conductor is open', 'states': 'reset, 3V3 absent, 5 V absent, cable conductor open, header unplugged'},
    {'load': 'steam heater (wall board opto-triac LED)', 'held_by': 'R772 on Q771', 'states': 'as above'},
    {'load': 'coffee pump', 'held_by': 'R702 on Q701 (opto-triac LED stage); pump live feed through LINE1 behind the interlock contact', 'states': 'reset, 3V3 absent, 5 V absent; no cable between stage and the opto-triac'},
    {'load': 'steam pump', 'held_by': 'R712 on Q711', 'states': 'as above'},
    {'load': 'two-way coffee valve', 'held_by': 'R732 on Q731 (coil driver); relay contact open when the coil is unenergised', 'states': 'as above'},
    {'load': 'three-way valve', 'held_by': 'R742 on Q741', 'states': 'as above'}],
   'not_covered_by_the_stage': 'A heater return conductor shorted to ground, or the two heater return conductors shorted together, lights an LED the stage did not command; the interlock contact and the supply-current check are the cover (open-items.md).'},
 'derating_policy_proposed': {
   'status': 'adopted by the owner on 2026-10-29 ("agree, proceed") and relaxed the same day ("adopt"): integrated circuit voltage share 1, junction cap 110 degC, relay contact current share 1; the record is derating-policy.yaml and the factors below are the starting proposal, not the policy',
   'source': 'NASA Goddard Space Flight Center, EEE Parts Derating, Preferred Reliability Practice PD-ED-1201, Table 1 (https://klabs.org/DEI/References/design_guidelines/design_series/1201.pdf, no date printed, read 2026-10-29)',
   'factors': {'capacitors': 'at most 60 % of rated voltage', 'resistors': 'at most 60 % of rated power', 'semiconductor devices': 'at most 50 % of rated power, 75 % of rated voltage, junction temperature 110 degC', 'microcircuits': 'supply at most 80 % of rated voltage, 75 % of rated power, junction temperature 100 degC', 'inductive devices': 'at most 50 % of rated voltage, 60 % of rated temperature', 'relays and connectors': 'at most 50 % of rated current'},
   'consequence_for_mains_rated_parts': 'Taken literally the table puts mains-rated, safety-listed parts (X2 capacitor, varistor, relay contacts, tabs, fuse clips) out of policy at 358 V peak and 15 A; those rows are findings until the owner either declares a different factor for safety-listed parts with a stated reason or accepts the findings.'},
 'departures_from_the_division_record': [
  'Interlock drive has 21 parts, not 19: R205 and R206 (100 kohm, each coupling node to ground) are added, because the record\'s circuit holds the coil about 1.2 s when the output rests high after a rising edge (circuit-proof/A_removal_gate_high_rec.log); the record\'s sentence that a level cannot cross the coupling capacitor is to be amended.',
  'The supply voltage and supply current are read digitally by the AMC131M02 over SPI2, so the record\'s conversion pins PB1 and PA1 and the conditioning blocks VM_C and I_C are not used; the pins stay free.',
  'Mains divider is three 300 kohm 2512 resistors and the zero-crossing feed two 60.4 kohm 2512 resistors (a single element would see more than the 200 V working voltage the maker rates); the VMEAS and IN_COND blocks of the floorplan are larger than the record drew.',
  'Three Extended machine-placed part types are added to the record\'s five (PESD5V0F1BL C45961, BAT54S C47546, MF-NSMF012-2 C163517), +9.21 USD at Economic assembly.',
  'The debug SWO pin PB3 is wired; the allocation record\'s free list loses PA0, PB3, PC7, PD9, PD10 and PD11.',
  'The 8 MHz converter clock oscillator Y601 is added (the AMC131M02 has no oscillator of its own).',
  'The record\'s controller current budget (480 MHz, 439 mA) has no stable junction temperature at 70 degC air; the rail skeleton is drawn to 200 MHz at the lowest power scale until the firmware clock is declared (open-items.md).'],
 'circuit_verdicts': {'file': 'circuit-verdicts.md', 'covers': 'every part and every net of every sheet, and each sheet against the drawing convention; a FINDING names its closing action or its owner'},
 'sheets': out_sheets,
 'custom_symbols': custom_sym,
 'custom_footprints': custom_fp,
 'net_index': net_index,
}
class D(yaml.SafeDumper):
    def ignore_aliases(self, data): return True
with open('schematic-spec.yaml', 'w') as f:
    f.write('# Schematic specification of the Sunbeam EM7000 main controller board: the one file the schematic is drawn from.\n# Generated by spec-tools/build_spec.py from sheets/*.yaml. Do not edit by hand.\n')
    yaml.dump(spec, f, Dumper=D, sort_keys=False, width=220, allow_unicode=True, default_flow_style=False)
print('wrote schematic-spec.yaml', parts_total, 'parts', len(net_index), 'nets', dict(by_class))
