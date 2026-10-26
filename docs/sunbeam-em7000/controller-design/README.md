# Earlier controller design: bought-module history and the parts data the custom board draws on

This folder holds the earlier design of the controller, written 2026-10-12, in which the controller was assembled from bought modules: a controller module, solid-state heater switches, phase-control dimmers, a relay module, pressure sensor modules and energy meters. **Nothing of that design was bought** beyond the base machine; the controller board designed in this project is itself the bench instrument. The module-based design was overtaken, but the folder still holds parts, pin and wiring data that the custom board draws on, and the record documents cite its files by path, so no file here has been moved or removed.

## Where the design now is

- The controller baseline: `DEC-CONTROLLER-BASELINE-STM32H743`, the STM32H743 designed bare onto the controller board. The bought controller module of this folder is not kept; only its chip is. An STM32F4 part named by the firmware's test build is a verification stand-in and is not chosen.
- The channel enumeration: [`../controller-io.md`](../controller-io.md), with its two derived views [`../controller-io-bom.csv`](../controller-io-bom.csv) and [`../control-board-electrical-requirements.csv`](../control-board-electrical-requirements.csv).
- The component specification and the assessment of the controller against the channels: [`../component-specification.md`](../component-specification.md).
- The form chosen for each controller function: [`../controller-board-function-forms.md`](../controller-board-function-forms.md).
- The constraints the boards are designed to, including the module properties carried forward from this folder: [`../controller-board-design-constraints.md`](../controller-board-design-constraints.md).
- The board designs: the hardware tree, laid out in [`../../../hardware/README.md`](../../../hardware/README.md).

## Precedence

Where two documents disagree: the graph wins where it speaks; then `reference-machine.md` and `connector-pinouts.md` for the machine as found; then the record documents listed above, which govern the boards together with the board designs; then this folder, which loses wherever it disagrees with any of them (`DEC-MACHINE-RECORD-FOLDER-PER-MACHINE`). The root documents were kept current and this folder's same-named copies are older forks of them. Each difference between a copy and its root document was classified and either carried into the root document or marked in place as superseded, row by row, in [`_carry-forward/reconciliation.md`](_carry-forward/reconciliation.md).

## What each file is for

A file is one of three things: a **source** the custom board draws on, **history** of the module-based design, or a **change record**. Statements in a file that a decision has overtaken are marked in place.

| File | Role | Notes |
|---|---|---|
| `control-system-bom.csv`, `part-numbers.csv`, `passive-and-drive-components.csv` | Source | Parts, orderable numbers and passives, cited by the constraints record. Module rows are history; single-part rows are inputs |
| `h743-pin-allocation.csv`, `h743-header-pinout.csv` | Source | Pin assignments checked against the STM32H743 datasheet. The chip is the one the board carries; the module's own header and on-board peripherals are not part of the board |
| `module-interconnect.csv`, `wiring-and-connectors.csv` | Source | How the machine's retained devices are wired and their connectors; the module names in them are history |
| `temperature-sensing-front-end.md`, `heater-drive-and-supply-timing.md`, `mains-inlet-protection.md` | Source | Sensing front end, heater drive timing and mains entry protection reasoning (the fixed lead retained, the fuse and varistor on the main board) and figures the custom board draws on |
| `hydraulic-lines.md` | Source | Every device on each water and steam line in order, with provenance |
| `controller-io.md`, `component-specification.md`, `controller-io-bom.csv`, `control-board-electrical-requirements.csv` | History | Earlier forks of the root documents of the same names, written for the module design. Differences from the root documents are classified in the reconciliation record |
| `system-design.md`, `decisions.md`, `open-items.md`, `pcb-plan.md` | History | The module design as a whole, its decision and fact log (its facts and owner statements stay inputs), its open items and its prototype-board proposal |
| `_carry-forward/INDEX.md`, `_carry-forward/controller-io.md`, `_carry-forward/component-specification.md`, `_carry-forward/temperature-sensing-front-end.md`, `_carry-forward/heater-mains-wiring.md`, `_carry-forward/data-files-post-review.md` | Change record | How the 2026-10-12 files were built from the earlier working folder and what the review fixed |
| `_carry-forward/reconciliation.md` | Change record | The comparison of each same-named copy with its root document, and the root derived views corrected to the enumeration |
| `README.md` | Entry document | This file |
