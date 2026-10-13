# Board design method

This is how a controller board is designed in KiCad so that it passes the pre-order check and works once built. The method works for any machine. A machine's own figures come from its own records, and this document names each record only by the role it plays: the machine's constraints record, its separation basis record, the requirements a board serves, and the manufacturer's stated limits.

Each step can be carried out from its own text, whether you work in KiCad yourself or through an agent session. The pre-order check that later enforces these rules, and how to run it, are described in [`hardware/README.md`](../hardware/README.md).

## Tools

These are needed in addition to the tools the pre-order check needs (KiCad 10, Python, PyYAML, git and Task, listed in `hardware/README.md`). Every one is free.

| Tool | Version the commands below were exercised with | Where to get it |
|---|---|---|
| KiCad, with its command-line tool and the Python it bundles with its `pcbnew` module | KiCad 10.0.7 | https://www.kicad.org/download/ |
| Freerouting, the external router | Freerouting 2.5.0, the file `freerouting-2.5.0.jar` | https://github.com/freerouting/freerouting/releases (the v2.5.0 release, asset `freerouting-2.5.0.jar`) |
| A Java runtime, which Freerouting runs on | Eclipse Temurin OpenJDK 26.0.1 | https://adoptium.net/ or any other Java distribution. Freerouting 2.5.0 is built for Java 25, so it needs Java 25 or newer. |

KiCad's bundled Python is the one that can `import pcbnew`. Its usual location:

| System | KiCad's Python |
|---|---|
| macOS | `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3` |
| Windows | `C:\Program Files\KiCad\10.0\bin\python.exe` |
| Linux (distribution package) | the system `python3`, which the package gives the `pcbnew` module |

To check it, run `<KiCad's Python> -c "import pcbnew; print(pcbnew.Version())"`. It should print the KiCad version. The commands below write this Python as `KICAD_PYTHON` and the router's jar file as `FREEROUTING_JAR`. Replace them with the paths on your machine.

The commands were exercised on macOS.

## Rules before routing

Do this before any track is routed. Its purpose is that every rule the board is routed and checked against is written down, traceable to where its figure comes from, and known to be in effect on the board itself.

### 1. Write every rule and net class down, with its figure and source

Keep a table in a file named `design-rules.md` in the board's own folder, beside its KiCad project. Give it one row for every design rule and every net class the board uses:

| Rule or net class | Figure | Where it is set in KiCad | Source of the figure | Read back from the board |
|---|---|---|---|---|

- **Design rules** are the board-wide minimums (clearance, track width, via diameter and drill, hole size, annular ring, hole-to-hole, copper-to-edge, silkscreen), each custom rule in the board's rules file, and every net class's own clearance, track width and via sizes.
- **Source** says where the figure comes from, for example: the machine's constraints record (name the figure in it); a requirement the board serves (name the requirement); the manufacturer's stated limits (name the manufacturer and the date of the capability page the figure was read from); the separation basis record; or a finding from a layout review that became a rule (name the review). "Default", "typical" or "what KiCad had" is not a source.
- **Read back from the board** is filled in only by step 4 below.

A rule with no stated source fails this step. Give it a source or remove it.

### 2. Declare whether the board carries mains

Every board declares this in its project text variable `MAINS` (in KiCad: **File → Board Setup → Text Variables**), set to exactly `present` or `none`. A board with no mains declaration fails this step, and the pre-order check fails it too.

**A board that declares `none`** puts no net in the `Mains` net class.

**A board that declares `present`**:

- assigns every mains-referenced net to the net class named exactly `Mains`. These are the nets at mains potential and those referenced to it, such as a switched live or the low side of a heater. You can assign a net in the schematic with a net class directive, or in **Board Setup → Net Classes** by assignment or by pattern;
- writes the separation between mains and low-voltage copper as **one** custom rule in the board's rules file, `<board>.kicad_dru` beside the project. In KiCad that file is **Board Setup → Design Rules → Custom Rules**. The rule must be exactly in this form:

  ```
  (version 1)
  (rule "Mains separation"
  	(condition "A.hasNetclass('Mains') && !B.hasNetclass('Mains')")
  	(constraint clearance (min <clearance>mm))
  	(constraint creepage (min <creepage>mm)))
  ```

  The condition is written exactly as shown, with no other spacing. The rule has no `(layer ...)` clause and no other narrowing by layer or area. It holds both a `clearance` and a `creepage` constraint, each in millimetres. `<clearance>` and `<creepage>` are no less than the separation basis record's mains-to-low-voltage clearance and creepage (`mains_to_low_voltage.clearance_mm` and `.creepage_mm` in the `separation-basis.yaml` that holds the board to its signed figures). In the table from step 1, both figures name that record as their source. The pre-order check accepts the rule in this form only, and holds the board to the record's figures whatever the rule states.

**Local clearance overrides can defeat the separation rule.** Pads, footprints and zones can each carry a clearance of their own, set outside the custom rules. KiCad applies an override on a pad or a footprint ahead of every custom rule, taking the larger of the two items' overrides. So a small override on either side of a mains/low-voltage pair would let low-voltage copper sit closer to mains than the separation rule allows. KiCad 10.0.7 does not let a zone's own clearance outrank a custom rule. Treat it the same way all the same. Set none of these overrides below the separation basis record's clearance. The pre-order check fails any pad or footprint override, and any clearance on a `Mains`-class zone, that undercuts the signed figure.

### 3. Save, then close and reopen the project

KiCad's board editor does not see a net class written to the project file until the project is reopened. This holds whether the class was written in the schematic editor, by editing the project file, or by an agent. Save everything, close the project, and open it again before reading anything back.

### 4. Read every rule and net class back from the open board

Confirm each row of the table on the reopened board, from the board editor itself. Never confirm it from the project file or from having written it:

- **Net classes and their figures:** **Board Setup → Net Classes** lists each class with its clearance, track width and via sizes, and the patterns that assign nets to it.
- **Each net's class:** the Net Inspector (**View → Panels → Net Inspector**) shows each net with its net class. Check that every net you meant to put in a class is in it, and that no other net is.
- **Board-wide minimums:** **Board Setup → Design Rules → Constraints**.
- **Custom rules:** **Board Setup → Design Rules → Custom Rules**. Press **Check Rule Syntax** and expect no errors. KiCad discards a whole rules file it cannot parse.
- **The separation rule in effect:** select a `Mains`-class item and a nearby low-voltage item, then use **Inspect → Clearance Resolution**. It should show the separation rule's clearance as the one that applies.
- **The mains declaration:** **Board Setup → Text Variables** shows `MAINS`.

Fill in the table's last column for each row as you confirm it. A net class written to the project but not read back from the board fails this step. So does any other rule not read back.

Out of scope for this step: the figures themselves, which come from the machine's constraints record and its separation basis record, and the automated check that later enforces these rules, the pre-order check.

## Routing: critical nets by hand and locked, then the rest

The nets that decide whether a board works are never left to an automatic router. They are routed deliberately to their stated rules and locked. Automated routing is then run only one way: KiCad's exporter, the external router from its command line, then KiCad's importer (step 5). It places only what is left unrouted, and may not move a locked item. A check in the board tooling, never a comparison by hand and never the router's own report, confirms afterwards that nothing locked was moved and nothing was added to a critical net.

### 1. Put every critical net in a named critical class

The critical classes include at least the board's **power**, **decoupling**, **ground**, **mains** and **sensing** paths. Assign every net in those categories to a named net class in step 1 of the rules section, for example `Power`, `Decoupling`, `Ground`, `Mains` and `Sensing`. The names are the board's own, and the mains class is always `Mains`. Every critical class is named to the record step below, which protects only the classes it is given. A critical net left in the `Default` class therefore fails this step: its copper would not be protected.

Which further nets of a particular board are critical is that board's own design work.

### 2. Route every critical net by hand, to its class's rules, and lock it

Route every net in every critical class yourself, to the rules its class states: every track, arc and via. A copper zone on a critical net, such as a ground or mains pour, is deliberate routing like a track, so draw it yourself too.

Then lock every track, arc, via and zone on a critical-class net. In the board editor, select the items, right-click and choose **Locking → Lock**. A locked item shows as locked in the Properties panel, and KiCad writes `(locked yes)` into the item in the board file. A locked item is changed only by a deliberate re-route: unlock it, route it again, and lock it again. A re-route after recording (step 4) needs a fresh record.

Save the board.

### 3. Close the board in every editor holding it

The export and import below act on the board file outside any editor. Close the board in KiCad's board editor, and in any agent session driving an editor, so that neither side works on a stale copy.

### 4. Record the critical-class copper, immediately before export

From the board's folder, run:

```
task hw:copper-record -- --board <board>.kicad_pcb --project <board>.kicad_pro --class <critical class> [--class <critical class> ...] --record <work folder>/<board>.record.json
```

Name every critical class with its own `--class`. Set `KICAD_CLI` as `hardware/README.md` describes if `kicad-cli` is not on your search path.

The record lists every track, arc, via and zone on a net KiCad places in those classes, each with its properties and whether it is locked. It is a working file. Write it to a folder outside the board's folder, and never commit it. The command refuses a path inside the board's folder.

It also refuses, and writes no record, when:
- a named class is not one the design defines;
- any critical-class item is not locked. It names each one, so you can lock it and record again.

It prints each critical class with the nets KiCad puts in it. Check those against your intent. A critical net missing from the list is in the wrong class.

### 5. Export, route the rest externally, import

Before exporting, keep a copy of the board file as it stands, or commit it, so it can be restored if step 6 fails.

KiCad 10's `kicad-cli` has no Specctra command. The exporter and importer are reached through KiCad's bundled Python, with these commands run from the board's folder. Do not substitute another tool's Specctra export: Konnect's own routing export, for one, refuses boards with rounded-rectangle pads.

Export the board for the router:

```
"$KICAD_PYTHON" -c "import pcbnew; b = pcbnew.LoadBoard('<board>.kicad_pcb'); assert pcbnew.ExportSpecctraDSN(b, '<work folder>/<board>.dsn')"
```

Locked items are exported as fixed (`(type fix)` in the `.dsn` file).

Run the router from its command line, with no window:

```
java -jar "$FREEROUTING_JAR" -de <work folder>/<board>.dsn -do <work folder>/<board>.ses --router.autorouter.max_passes=20 --gui.enabled=false
```

Import the router's session into the board and save it:

```
"$KICAD_PYTHON" -c "import pcbnew; b = pcbnew.LoadBoard('<board>.kicad_pcb'); assert pcbnew.ImportSpecctraSES(b, '<work folder>/<board>.ses'); b.Save('<board>.kicad_pcb')"
```

Saving this way also rewrites the project file, with KiCad's defaults filled in for settings it did not hold before. Review that change as you would any other.

The router's own report, for example `0 unrouted and 0 violations`, is not evidence of anything. Neither the router nor the importer is relied on to leave locked copper alone.

### 6. Compare the imported board with the record

From the board's folder, run:

```
task hw:copper-compare -- --board <board>.kicad_pcb --project <board>.kicad_pro --record <work folder>/<board>.record.json
```

This fails, naming each item, when:
- a recorded item is missing;
- a recorded item is no longer locked;
- a recorded item is changed in any recorded property, with each changed property given as old → new;
- a critical-class net carries a track, arc, via or zone that the record does not hold.

An added item identical to a recorded one is still reported as added. Copper on nets outside the critical classes is the router's, and is ignored. A failure fails this step whatever the router or the importer reported. Restore the board as it was before export, correct the cause, and repeat from step 2.

A board on which any critical-class net was placed by the router fails this step.

### 7. Reopen the board and run the board's own rule checks

Reopen the project in KiCad. Then run the pre-order check, which runs KiCad's own electrical and layout rule checks with zones refilled:

```
task hw:verify
```

It checks only designs git tracks (`git add` is enough), as `hardware/README.md` explains. It must pass. A router's or editor's "no violations" is never accepted in its place.

Out of scope for this step: judging the quality of the layout, which is the layout review step.
