# Hardware

Board designs and the check every one of them has to pass before it is ordered.

- `hardware/<machine>/` holds one machine's board designs, one KiCad project per board in its own folder, and the `separation-basis.yaml` they are held to.
- `hardware/tools/` holds the pre-order check and its tests. They work for any machine.
- `hardware/proof/` holds designs committed only to prove the check. They are never ordered.

A **board design** is a KiCad project file (`.kicad_pro`) together with the schematic (`.kicad_sch`) and layout (`.kicad_pcb`) of the same name beside it. The check finds every design git tracks, wherever it sits. The layout above is a convention for readers, not something the check depends on. A design is checked once git tracks it: `git add` is enough for the design's own files. The check reads a design only as the repository holds it. KiCad is given a copy of the tracked files alone, each in its place in the repository: everything in the design's folder, every sheet its schematic reaches, and every library its `sym-lib-table` and `fp-lib-table` name, wherever in the repository they sit. A library, sheet or rules file left uncommitted is therefore not used. A sheet the schematic names, a custom rules file or library table beside the project, or a library a table names, that git does not track fails the design by name. So does a library the repository cannot hold at all: one named by an absolute path, one outside the repository, or one reached through a path variable other than `${KIPRJMOD}` and those naming the libraries KiCad installs with itself (`${KICAD10_SYMBOL_DIR}`, `${KICAD10_FOOTPRINT_DIR}` and the like). Name a library from its table as `${KIPRJMOD}/` followed by its path from the design's folder. The separation basis record has to be committed exactly as it stands (see below).

## What you need

Every tool is free. The check stops with an error naming any tool that is missing or too old, rather than skipping the checks that need it.

| Tool | Minimum | Where to get it |
|---|---|---|
| KiCad (its `kicad-cli`) | KiCad 10.0 | https://www.kicad.org/download/. This repository's board files are in KiCad 10's format, which older versions cannot open. |
| Python | Python 3.9 | https://www.python.org/downloads/ |
| PyYAML | PyYAML 5.1 | `pip install pyyaml`, or your system's `python3-yaml` package |
| git | git 2.11 | https://git-scm.com/downloads |
| Task | 3 | https://taskfile.dev/installation/ |

`kicad-cli` is often installed off the search path. The tasks use the variable `KICAD_CLI`, which defaults to the bare name `kicad-cli`. If it is not on your search path, set the variable to the tool's full path, either on the command line (`task hw:verify KICAD_CLI=/path/to/kicad-cli`) or in the environment. Its usual location:

| System | `kicad-cli` |
|---|---|
| macOS | `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` |
| Windows | `C:\Program Files\KiCad\10.0\bin\kicad-cli.exe` |
| Linux (distribution or PPA package) | `/usr/bin/kicad-cli` |
| Linux (Flatpak) | not a file on the path: write a one-line script that runs `flatpak run --command=kicad-cli org.kicad.KiCad "$@"` and point `KICAD_CLI` at it |

## The commands

- `task hw:verify` runs the pre-order check on every board design in the repository. It exits 0 only when every design passes.
- `task hw:prove` seeds each fault the check guards against into a throwaway copy of `hardware/proof/gate-proof`, in a temporary directory outside the repository. It requires the check to catch each fault. This command is on demand and is not part of the gate.
- `task hw:test` runs the tests of the check itself against the real `kicad-cli`.

## What a design must satisfy

For each design the check runs KiCad's own electrical rule check on the schematic. It also runs KiCad's own layout rule check once, on a temporary copy, with schematic parity on and every zone refilled first. KiCad does the checking itself. A router's or editor's "no violations" is never accepted in its place. A design fails on any of these:

- **Any violation KiCad reports**: electrical, layout, unconnected item, or layout-schematic disagreement. Warnings count.
- **Any check set to ignore**, in the project's severities or in a custom rule's `(severity ignore)`. This applies even when ignore is KiCad's own default for that check, as it is for `missing_courtyard` and `footprint_filters_mismatch`. Set every check to error or warning.
- **Any violation marked as excluded**, whether in the project file's exclusion lists or by a custom rule's `(severity exclusion)`. Fix the violation instead.
- **A custom rules file KiCad declines to load.** KiCad drops a whole rules file it cannot parse, without saying so, and that would leave every custom rule unchecked. The check detects this and fails the design. It then names the first rule KiCad rejects, with its line, or a missing `(version 1)` header. When no one rule can be named it says why: the file is not well-formed at a given line, or every rule loads on its own and what KiCad rejects lies in the comments between them. It finds that rule by re-running KiCad's layout check on the file's rules a few at a time, so the editor is never needed to find it.
- **A custom rule whose name contains `pre-order check`.** Those words are reserved for the rules the check adds to the copy it checks. The rules the check recognises in KiCad's report are named afresh for every run, so no design rule can pass for one of them.
- **No mains declaration.** The project text variable `MAINS` must be `present` or `none`. A design that declares `present` must have a net in the `Mains` net class on its layout, since that is where the separation rule is enforced. A design that declares `none` may have none there.
- **Any disagreement about which nets are in `Mains`.** Three things say which nets are in the class, and each is read as KiCad itself resolves it: the layout (KiCad's layout check on the board), the schematic (KiCad's own netlist of it, which carries its net class directives), and the project file's net settings (its assignments by name and its patterns, which KiCad resolves for every net the layout, the schematic or an assignment names, copper or not). Every net must be in the class in all three or in none. A net in only some of them fails by name, saying which have it and which lack it. The usual fix is to save the schematic, so the project file carries its assignments, and update the layout from the schematic. A class only the layout gives a net comes from a `(net_class ...)` block that older KiCad versions wrote into the layout file, which KiCad 10 still honours.

A design that declares `MAINS` as `present` must also:

- assign every mains-referenced net to the net class `Mains`;
- state its separation in its own custom rules file (`<design>.kicad_dru`) as **one** rule, with no `(layer ...)` and the condition exactly `A.hasNetclass('Mains') && !B.hasNetclass('Mains')`. The rule holds both a `clearance` and a `creepage` constraint, each no less than the signed record's figures;
- be held to a signed **separation basis record**. This is the `separation-basis.yaml` in the nearest folder at or above the design. Its keys are `standard`, `supply`, `working_voltage`, `pollution_degree`, `material_group`, `environment`, `barriers`, `mains_to_low_voltage` (a mapping holding `clearance_mm` and `creepage_mm`), `accepted_by`, `accepted_on` and `synthetic`; the check compares `mains_to_low_voltage.clearance_mm` and `.creepage_mm`, in millimetres. `accepted_by` names the acceptor by the identity they record acts under in this project's requirement graph. The record fails the design if it is missing or cannot be parsed, or if a figure is missing or not a positive number. It also fails if it is unsigned: an `accepted_by` that is missing or a placeholder (`unsigned`, `tbd`, `todo`, `none`, `placeholder`, or anything in angle brackets), or an `accepted_on` that is missing, is not a `YYYY-MM-DD` date, or is later than today. A record marked `synthetic` passes only a design whose project text variable `NOT_FOR_MANUFACTURE` is `true`. The commit that adds or changes the record is its audit trail. A record that is untracked, ignored by git, staged but never committed, edited since its last commit, or deleted from the working tree therefore fails the design. A nearer uncommitted record is never passed over for a committed one further up.

The layout check enforces the signed figures, not the design's own. On the temporary copy, the record's clearance and creepage are appended to the design's rules as the last rule, in the same condition form. In KiCad the last matching rule wins, so no later or narrower rule and no net class setting can undercut it. A design that declares a stricter figure is still held only to the record's.

KiCad 10 ranks some settings above every custom rule, and the appended rule cannot outrank them. The check therefore fails them outright:

- **A local clearance override on a pad or a footprint** below the signed clearance fails, whatever net it is on. KiCad 10.0.7 applies the larger of the two items' pad or footprint overrides ahead of any custom rule. A 0.1 mm override on either a mains pad or a low-voltage pad would let low-voltage copper pass at 0.1 mm. A smaller clearance can still be written as a custom rule, which the signed rule outranks.
- **A zone's clearance** does not outrank custom rules: zones are refilled to the signed figure. A zone on a `Mains`-class net may still not declare a clearance below the signed figure.

## The report

The report has one verdict line per design, one line per violation under it, and a result line last:

```
DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | PASS
DESIGN | hardware/m/board/board.kicad_pro | FAIL | 1 violation
VIOLATION | hardware/m/board/board.kicad_pro | clearance | Track [/LV_A] on F.Cu, length 2.0000 mm @ (28.085, 9) mm; PTH pad 2 [/MAINS_N] of R1 @ (25.16, 10) mm | Clearance violation (rule 'pre-order check: signed separation basis' clearance 3.0000 mm; actual 2.0000 mm)
RESULT | FAIL | 1 of 2 designs failed
```

Each violation line has five fields separated by ` | `: `VIOLATION`, the design, the rule broken, where it is, and the message. The message is KiCad's own for anything KiCad found, and says what to change for anything else. The rule is KiCad's own check name (for example `clearance`, `creepage`, `pin_not_connected`, `footprint_symbol_mismatch`), or one of the check's own:

| Rule | Meaning |
|---|---|
| `design_discovery` | No design was found, a project lacks its schematic or layout, a board file is tracked without a project, or a schematic names a sheet git does not track |
| `design_unreadable` | A design file or library table cannot be opened or parsed, or KiCad cannot resolve the project file's net classes |
| `ignored_check` | A check is set to ignore, or a custom rule hides what it finds |
| `custom_rules` | KiCad did not load the design's custom rules (the location names the rule it rejects, or the line where the file stops being well-formed), the rules file is not tracked, or a rule takes a name reserved for the check |
| `mains_declaration` | `MAINS` is missing or invalid, or disagrees with the layout's `Mains` net class |
| `mains_class` | The layout, the schematic and the project file's net settings do not all put the same nets in `Mains` |
| `design_library` | A library table beside the design, or a library it names, is not tracked, or names a library the repository cannot hold |
| `separation_rule` | The design's own Mains separation rule is missing, narrowed, incomplete, or below the record |
| `separation_basis` | The separation basis record is missing, unreadable, unsigned, not committed as it stands, or synthetic on an orderable board |
| `local_clearance_override` | A pad, footprint or Mains-class zone sets a clearance below the signed figure |

The exit status is 0 when every design passes, 1 when any fails, and 2 when the check cannot run at all, for example because a tool is missing.

## The proof design

`hardware/proof/gate-proof` is a deliberately tiny board. Two mains nets run through a connector and a resistor, and two low-voltage nets do the same. Its symbol and footprint libraries are carried beside it, so it needs nothing from a local KiCad installation's libraries. It is marked `NOT_FOR_MANUFACTURE=true` and carries its own synthetic `separation-basis.yaml`. It passes the check as committed, and `task hw:prove` shows each failure condition above failing on a copy of it.
