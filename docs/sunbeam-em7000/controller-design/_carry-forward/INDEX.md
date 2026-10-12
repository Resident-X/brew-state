# Carry-forward index

How the old files map to the new set, written 2026-10-12. Each per-file log in this folder records, section by section, what was carried unchanged, updated, dropped or newly added. The old files are untouched and remain the reference for the review; nothing is to be deleted until the review is accepted.

**The old working folder `controller-selection-working/` was deleted after the review; the paths below are historical. Recover any file with `git show 07913f4:docs/sunbeam-em7000/controller-selection-working/<file>`.**

| Old file | New file | Log |
|---|---|---|
| `controller-selection-working/README.md` | `README.md` (state of play, document map), `decisions.md` (settled items, rejected options, corrections), `open-items.md` (open items) | this index |
| `controller-selection-working/temperature-sensing-front-end.md` | `temperature-sensing-front-end.md` | `temperature-sensing-front-end.md` |
| `controller-selection-working/heater-drive-and-supply-timing.md` | `heater-drive-and-supply-timing.md` | `heater-mains-wiring.md` |
| `controller-selection-working/mains-inlet-protection.md` | `mains-inlet-protection.md` | `heater-mains-wiring.md` |
| `controller-selection-working/wiring-and-connectors.csv` | `wiring-and-connectors.csv` | `heater-mains-wiring.md` |
| `docs/sunbeam-em7000/controller-io.md` | `controller-io.md` | `controller-io.md` |
| `docs/sunbeam-em7000/controller-io-bom.csv` | `controller-io-bom.csv` | `controller-io.md` |
| `docs/sunbeam-em7000/control-board-electrical-requirements.csv` | `control-board-electrical-requirements.csv` | `controller-io.md` |
| `docs/sunbeam-em7000/component-specification.md` | `component-specification.md` | `component-specification.md` |
| `controller-selection-working/control-system-bom.csv`, `part-numbers.csv`, `passive-and-drive-components.csv`, `module-interconnect.csv`, `h743-pin-allocation.csv`, `h743-header-pinout.csv` | same names | copied from the working folder after this session's edits (see below); no per-file log |

## Data files copied rather than rewritten

These six were revised in place during the session (deleted Robin Nano file and old rows removed, OPV and damper rows, retained chain rows, header and mounting-hole corrections, panel and gauge stages and pin rows, snubber count), then copied. The only edit made in this folder is the steam OPV row and a new brew OPV row in `module-interconnect.csv`, which the controller-I/O agent found stale.

## New files with no old equivalent

`system-design.md`, `decisions.md` (apart from the settled list and rejected options carried from the old README), `hydraulic-lines.md`, `pcb-plan.md`.

## Files deliberately not replaced

`docs/sunbeam-em7000/reference-machine.md` and `docs/sunbeam-em7000/connector-pinouts.md` stay where they are; both were updated in place this session (owner statements on valve roles, steam path, OPVs, dampers and check valves; the sheet 3-3 transcription).

## Removed content (not carried)

`robin-nano-v3.1-pin-allocation.csv` was deleted at the owner's instruction. The controller-board history narrative (Robin Nano to F407 to H743) was replaced by a short controller section and a one-line rejected-options list. Rows for the MAX31865 boards, the I2C multiplexer, HLK supplies, the Crydom upgrade, the Fotek, DimmerLink, the 2-channel relay module, the zero-cross detector and the salvaged BES920 driver were removed from the data files.

## Where the old README went

- 'What is settled' went to `decisions.md` (D1 to D22) and `system-design.md`; 'Options rejected, and why' to `decisions.md`.
- 'What is open' went to `open-items.md` (pump drive to D4; the supply-frequency evidence, surge suppression, mains switch, proof-of-life interlock, accuracy-versus-speed and recalibration items, and the heights, to `open-items.md` sections D and E); the temperature and pressure tap bullet and the valve bullet went to `decisions.md`, `hydraulic-lines.md` and `temperature-sensing-front-end.md`.
- The line 'the CI-enforced hardware seam holds 97.5% of firmware source and 100% of tests away from the target layer' was dropped: it is a firmware coverage metric, not hardware design, and appears nowhere in the new set.

## Review status

Two blind reviews were run on 2026-10-12: carry-across completeness (old set against new set) and internal consistency of the new set against `reference-machine.md` and `connector-pinouts.md`. Their findings were presented to the owner and the mechanical fixes applied by four agents plus the orchestrator; each log's 'Post-review fixes' section and `data-files-post-review.md` list them. Four judgment items were deliberately not decided and are recorded as open decisions in `open-items.md` section C: the mains chain rating margin, the heater switching cadence, the steam heater with the knob shut, and the SSR mounting. A final diff-based verification of the fixes is the last step.
