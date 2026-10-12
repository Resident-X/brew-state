# Replacement controller design: state of play

Written 2026-10-12 at the close of staircase discussion session `3CD30AB4-5763-4EE0-8610-FD0C090674AA` (project `brew-state`, branch `worktree-controller-board-selection`). This folder is the current, consolidated record of the hardware design for replacing the Sunbeam EM7000's control system. It is a new set of files that replaced the old working folder `docs/sunbeam-em7000/controller-selection-working/`, which has been removed (its files are in git history at commit `07913f4`), and that supersedes the stale slice files in `docs/sunbeam-em7000/` (`controller-io.md`, `component-specification.md`, `controller-io-bom.csv`, `control-board-electrical-requirements.csv`), which are **kept unchanged and must not simply be deleted**: graph evidence and solution nodes cite them by path (22 spec files cite `controller-io.md`, 6 cite `component-specification.md`, 2 cite `controller-io-bom.csv`, 1 cites `control-board-electrical-requirements.csv`), so removing or rewriting them needs graph work first (`open-items.md` section D).

**These are working documents.** Not baselined, not traced to any criterion, and not evidence for anything. The graph is the only durable record, and nothing in this design has been authored into it yet.

## Where we are

The design is specified to the level of a bill of materials, a pin allocation and a module wiring table, with the plumbing and sensing worked out in detail. The controller is a WeAct MiniSTM32H743; the heaters are zero-cross SSRs; the pumps are Standard phase-control dimmers; the valves are on a mechanical relay module; a calibrated PT1000 in the water at the coffee block outlet is the key temperature sensor, with two XDB401 pressure sensors. The owner intends to reuse the operator panel and gauge harnesses; copying the OEM transistor stages for them is recommended, not decided. Nothing has been built. The remaining unknowns are mostly facts about the machine that need one inspection session (threads, tube sizes, check valves, the steam OPV, valve types), a handful of datasheet and bench checks, and a few owner decisions. The proposed next step is a low-voltage-only prototype PCB, which is the subject of the next discussion.

## Reading order

1. `system-design.md` — the whole design in one place.
2. `decisions.md` — what is decided, what is only an owner statement, what is a recommendation.
3. `hydraulic-lines.md` — every device on each water and steam line in order, with provenance.
4. `open-items.md` — what blocks what: the inspection list, bench tests, owner decisions, graph work.
5. `pcb-plan.md` — the PCB recommendation and what a Staircase solution for it would need.

## Document map and precedence

Where two documents disagree: the graph wins where it speaks; `reference-machine.md` and `connector-pinouts.md` win on facts about the machine as found; this folder wins on the replacement design. This precedence rule is proposed by the assistant, not recorded as a decision.

| File | Role | Replaces |
|---|---|---|
| `system-design.md` | Holistic design | New |
| `decisions.md` | Decision and fact log | New |
| `hydraulic-lines.md` | Tank-to-outlet chains | New (no earlier equivalent) |
| `open-items.md` | Ranked unknowns, inspection list, graph work | The open-items part of the old working README |
| `pcb-plan.md` | PCB position and Staircase solution needs | New |
| `temperature-sensing-front-end.md` | Temperature and pressure sensing, commissioning tests | The old working file of the same name |
| `heater-drive-and-supply-timing.md` | Heater drive, burst scheme, energy metering | The old working file of the same name |
| `mains-inlet-protection.md` | Inlet chain, protection, derating | The old working file of the same name |
| `controller-io.md` | Channel enumeration for the controller | `docs/sunbeam-em7000/controller-io.md` |
| `component-specification.md` | Required property per part and what meets it | `docs/sunbeam-em7000/component-specification.md` |
| `control-system-bom.csv`, `part-numbers.csv`, `passive-and-drive-components.csv`, `module-interconnect.csv`, `wiring-and-connectors.csv` | Parts, orderable numbers, passives, module wiring, wire and connectors | The old working files of the same names |
| `h743-pin-allocation.csv`, `h743-header-pinout.csv` | Pin assignment and the board's header map | The old working files of the same names |
| `controller-io-bom.csv`, `control-board-electrical-requirements.csv` | Derived views | The old files of the same names |
| `_carry-forward/` | Per-file change logs and the review record | New |

Files that stay where they are and are not replaced:

- `docs/sunbeam-em7000/reference-machine.md` — the machine as found; updated this session with owner statements.
- `docs/sunbeam-em7000/connector-pinouts.md` — the reverse-engineering record; updated this session with the sheet 3-3 transcription.

## Status words

Defined in `decisions.md`: chosen, owner decision, agreed, recommended, owner statement, parts list, schematic, published unverified, inferred, unmeasured.

## The next discussion

The owner intends to open a new discussion session (with a different model) to work out what goes into the graph for an AI-assisted PCB manufacture method. That session starts from `pcb-plan.md` and this folder, and should treat the controller design as the case study, not the subject. Things it will need to settle, none of them decided here:

- What the requirements are (outcomes, not mechanism) and where the solution sits in the roadmap.
- How a hardware design is verified automatically (ERC, DRC, netlist against the pin allocation and the firmware's hardware-seam channels, BOM against the BOM file) and where physical build evidence is held, given the graph's known gap for solutions awaiting an operator's build.
- What the method's inputs and outputs are, and which are committed.
- How the method relates to `DEL-COMPONENT-SPECIFICATION.C6` (regenerate the specification and purchase list from the graph), which has not been read.

Before graph work, read every node with `show` before linking it and check existing coverage first (`open-items.md` section D).

## Not committed

All of this work is uncommitted on the worktree branch. A blind review is required before any PR, including graph-only ones.
