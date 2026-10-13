# Hardware

Board designs and the check every one of them has to pass before it is ordered.

- `hardware/<machine>/` holds one machine's board designs, one KiCad project per board in its own folder, and the `separation-basis.yaml` they are held to.
- `hardware/tools/` holds the pre-order check, the locked-copper check used around routing, and their tests. They work for any machine.
- `hardware/proof/` holds designs committed only to prove the check. They are never ordered.

A **board design** is a KiCad project file (`.kicad_pro`) together with the schematic (`.kicad_sch`) and layout (`.kicad_pcb`) of the same name beside it. The check finds every design git tracks, wherever it sits. The layout above is a convention for readers, not something the check depends on. A design is checked once git tracks it: `git add` is enough for the design's own files. The check reads a design only as the repository holds it. KiCad is given a copy of the tracked files alone, each in its place in the repository: everything in the design's folder, every sheet its schematic reaches, and every library its `sym-lib-table` and `fp-lib-table` name, wherever in the repository they sit. A library, sheet or rules file left uncommitted is therefore not used. A sheet the schematic names, a custom rules file or library table beside the project, or a library a table names, that git does not track fails the design by name. So does a library the repository cannot hold at all: one named by an absolute path, one outside the repository, or one reached through a path variable other than `${KIPRJMOD}` and those naming the libraries KiCad installs with itself (`${KICAD10_SYMBOL_DIR}`, `${KICAD10_FOOTPRINT_DIR}` and the like). Name a library from its table as `${KIPRJMOD}/` followed by its path from the design's folder. The separation basis record has to be committed exactly as it stands (see below).

KiCad is run with a configuration the check makes for the run, not the one on the machine running it. That configuration names only the libraries KiCad installs with itself, and no `KICAD…` variable from the environment reaches KiCad. A symbol or footprint whose library only one machine's own KiCad setup names, in its global library tables or its path variables, is therefore reported by KiCad as a library its configuration does not include, and fails the design under `design_library`. Put such a library in the repository and name it in the design's own table.

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
- `task hw:test` runs the tests of the check itself, and of the locked-copper check, against the real `kicad-cli`.
- `task hw:copper-record` and `task hw:copper-compare` run the locked-copper check (below) on one board, around the routing round trip. They need the same tools as `hw:verify`, and read the paths given after `--` from the folder they are run in.

How a board is designed so that it passes the check, from its rules to its routing, is in [`docs/board-design-method.md`](../docs/board-design-method.md).

## The locked-copper check

A board's critical nets are routed by hand and locked before an external router places the rest. The check makes sure the export, the router and the import changed none of them. It is not part of the pre-order check: it runs on one board, either side of the round trip.

- **Recording**, `task hw:copper-record -- --board <board>.kicad_pcb --project <board>.kicad_pro --class <name> [--class <name> ...] --record <file>`, writes every track, arc, via and zone on a net in the named classes to `<file>`. A track is recorded by its net, layer, end points and width, an arc also by its mid point, a via by its net, position, diameter, drill and layers, and a zone by its net, layers and outline. Each item also records whether it is locked. Which nets are in which class is asked of KiCad, on the board itself with its project file, so assignments, patterns and any class the layout file carries all count as KiCad applies them. Recording refuses, and writes nothing, in these cases: a project file other than the one beside the board with the board's name, which is the one KiCad opens it with; a class the design does not define; a class named twice; any item on those nets that is not locked; a `<file>` inside the board's folder or inside any other folder that holds a project file, at any depth; or a `<file>` that cannot be written. The record is a working file, and is never kept with any design. It names the board it was taken of, its classes and the nets each held.
- **Comparing**, `task hw:copper-compare -- --board <board>.kicad_pcb --project <board>.kicad_pro --record <file>`, reads the imported board against the record. It fails in these cases: a recorded item is missing, is no longer locked, or has changed in any recorded property, or a critical-class net carries an item the record does not hold. Items are matched by their recorded properties and counted, so an added copy of a recorded item is still an addition. The critical nets at comparison are every net the record names as well as every net the critical classes hold then. A class the record names that the design no longer defines fails the comparison. So a change to class membership between recording and comparing, such as a project file the import rewrote, cannot hide added copper. Copper on nets outside both is ignored. The comparison also fails, comparing nothing, when the record was taken of another board or the project file is not the board's own.

Each finding is one line, `<FINDING> | <item> | <detail>`, where the finding is `MISSING`, `UNLOCKED`, `CHANGED` (the detail gives each changed property as old -> new), `ADDED`, `UNDEFINED` (a recorded class the design no longer defines) or `MISMATCH` (another board's record, or a project file not the board's own). A `RESULT` line comes last. A board, project file or record that cannot be read is reported as `UNREADABLE`, and fails rather than passes. So does a KiCad run that does not load the rules asking it which nets are in which class. The exit status is 0 when the record is written or the board matches it, 1 when recording is refused or the board does not match, and 2 when the check cannot run at all, for example because a tool is missing.

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
- state its separation in its own custom rules file (`<design>.kicad_dru`) as **one** rule, with no `(layer ...)` and one condition written exactly `A.hasNetclass('Mains') && !B.hasNetclass('Mains')`. The rule holds both a `clearance` and a `creepage` constraint, each written `(min <n>mm)` and no less than the signed record's figures;
- be held to a signed **separation basis record**. This is the `separation-basis.yaml` in the nearest folder at or above the design. Its keys are `standard`, `supply`, `working_voltage`, `pollution_degree`, `material_group`, `environment`, `barriers`, `mains_to_low_voltage` (a mapping holding `clearance_mm` and `creepage_mm`), `accepted_by`, `accepted_on` and `synthetic`; the check compares `mains_to_low_voltage.clearance_mm` and `.creepage_mm`, in millimetres. `accepted_by` names the acceptor by the identity they record acts under in this project's requirement graph. The record fails the design if it is missing or cannot be parsed, or if a figure is missing or not a positive number. It also fails if it is unsigned: an `accepted_by` that is missing or a placeholder (`unsigned`, `tbd`, `todo`, `none`, `placeholder`, or anything in angle brackets), or an `accepted_on` that is missing, is not a `YYYY-MM-DD` date, or is later than today. A record marked `synthetic` passes only a design whose project text variable `NOT_FOR_MANUFACTURE` is `true`. The commit that adds or changes the record is its audit trail. A record that is untracked, ignored by git, staged but never committed, edited since its last commit, or deleted from the working tree therefore fails the design. A nearer uncommitted record is never passed over for a committed one further up.

The layout check enforces the signed figures, not the design's own. On the temporary copy, the record's clearance and creepage are appended to the design's rules as the last rule, in the same condition form. In KiCad the last matching rule wins, so no later or narrower rule and no net class setting can undercut it. A design that declares a stricter figure is still held only to the record's.

KiCad 10 ranks some settings above every custom rule, and the appended rule cannot outrank them. The check therefore fails them outright:

- **A local clearance override on a pad or a footprint** below the signed clearance fails, whatever net it is on. KiCad 10.0.7 applies the larger of the two items' pad or footprint overrides ahead of any custom rule. A 0.1 mm override on either a mains pad or a low-voltage pad would let low-voltage copper pass at 0.1 mm. A smaller clearance can still be written as a custom rule, which the signed rule outranks.
- **A zone's clearance** does not outrank custom rules: zones are refilled to the signed figure. A zone on a `Mains`-class net may still not declare a clearance below the signed figure.
- **A net tie joining a `Mains`-class net to any net outside the class** fails, naming the footprint and both nets. A net tie joins its nets in copper, so such a tie joins low-voltage copper to mains outright, and KiCad 10.0.7 checks no clearance between the pads it ties. A net tie may join `Mains`-class nets to one another. A pad group naming a pad its footprint does not have fails too, since which nets it joins cannot be told.

## The one form each file is read in

Wherever KiCad can answer a question, the check asks KiCad: which nets are in `Mains`, whether the rules file loaded, what a zone fills to, whether a symbol's or footprint's library is reachable. Where the check has to read a file itself, it reads it only in the one form KiCad writes, and fails any other form by name rather than guessing what KiCad would make of it:

| File | The form read | Anything else fails as |
|---|---|---|
| Custom rules (`.kicad_dru`) | Each rule has its own name, and at most one `(condition ...)`, one `(layer ...)` and one `(severity ...)`. KiCad loads a rule with two conditions and keeps only one of them, and loads two rules of one name. | `custom_rules` |
| The Mains rule in it | Exactly one condition, written exactly `A.hasNetclass('Mains') && !B.hasNetclass('Mains')`, with no other spacing; exactly one `(constraint clearance (min <n>mm))` and one `(constraint creepage (min <n>mm))`, in millimetres with no further limit; no other constraint. | `separation_rule` |
| Project file (`.kicad_pro`) | Every key once in each object; `text_variables` an object of strings; `NOT_FOR_MANUFACTURE` `true` or `false` when present; the exclusion lists lists; `net_settings.netclass_assignments` an object. Its net classes and patterns are resolved by KiCad itself. | `project_file` |
| Separation basis record | Every key once and no YAML merge key (`<<`); only the keys listed below, plus any further pair of distances for readers, a mapping holding exactly `clearance_mm` and `creepage_mm`; `mains_to_low_voltage` holding only those two; `synthetic` `true` or `false` when present. | `separation_basis` |
| Library tables (`sym-lib-table`, `fp-lib-table`) | Headed for their own kind; at most one `(version ...)`; `(lib ...)` entries each holding one `name`, one `type` of `KiCad`, one `uri`, and at most one each of `options`, `descr`, `disabled` and `hidden`; each nickname once. | `design_library` |
| Hierarchical sheets | Each `(sheet ...)` names its file in exactly one `Sheetfile` property. | `design_discovery` |

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
| `project_file` | A setting the check reads from the project file is not in the form KiCad writes, or a key is given twice |
| `ignored_check` | A check is set to ignore, or a custom rule hides what it finds |
| `custom_rules` | KiCad did not load the design's custom rules (the location names the rule it rejects, or the line where the file stops being well-formed), the rules file is not tracked, a rule takes a name reserved for the check, two rules share a name, or a rule holds a clause KiCad takes once more than once |
| `mains_declaration` | `MAINS` is missing or invalid, or disagrees with the layout's `Mains` net class |
| `mains_class` | The layout, the schematic and the project file's net settings do not all put the same nets in `Mains` |
| `design_library` | A library table beside the design, or a library it names, is not tracked, names a library the repository cannot hold, or is not in the form KiCad writes; or a symbol or footprint comes from a library no table the design carries names |
| `separation_rule` | The design's own Mains separation rule is missing, narrowed, incomplete, not in its one form, or below the record |
| `separation_basis` | The separation basis record is missing, unreadable, not in its one form, unsigned, not committed as it stands, or synthetic on an orderable board |
| `local_clearance_override` | A pad, footprint or Mains-class zone sets a clearance below the signed figure |
| `mains_net_tie` | A net tie joins a `Mains`-class net to a net outside the class, or names a pad its footprint does not have |

The exit status is 0 when every design passes, 1 when any fails, and 2 when the check cannot run at all, for example because a tool is missing.

## The proof design

`hardware/proof/gate-proof` is a deliberately tiny board. Two mains nets run through a connector and a resistor, and two low-voltage nets do the same. Its symbol and footprint libraries are carried beside it, so it needs nothing from a local KiCad installation's libraries. It is marked `NOT_FOR_MANUFACTURE=true` and carries its own synthetic `separation-basis.yaml`. It passes the check as committed, and `task hw:prove` shows each failure condition above failing on a copy of it.
