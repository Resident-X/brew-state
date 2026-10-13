# Board design method

This is how a controller board is designed in KiCad so that it passes the pre-order check and works once built. The method works for any machine. A machine's own figures come from its own records, and this document names each record only by the role it plays: the machine's constraints record, its separation basis record, the requirements a board serves, the board manufacturer's stated limits, and the datasheets of the parts on the board.

A board is designed by an agent, with no person at the editor, and each step can be carried out by an agent session from its own text. The pre-order check that later holds a board to the rules KiCad's layout rule check enforces, and how to run it, are described in [`hardware/README.md`](../hardware/README.md).

The sections after the tools are carried out in the order they appear. The first two, proving value-critical circuits and designing for bring-up, are schematic work, finished and committed before any footprint is placed on the board; the rules and the routing follow. A board that fails any section's step is not ordered. The pre-order check does not read the records the first two sections keep, so passing it does not stand in for them.

## Tools

These are needed in addition to the tools the pre-order check needs (KiCad 10, Python, PyYAML, git and Task, listed in `hardware/README.md`). Every one is free.

| Tool | Version the commands below were exercised with | Where to get it |
|---|---|---|
| KiCad, with its command-line tool and the Python it bundles with its `pcbnew` module | KiCad 10.0.7 | https://www.kicad.org/download/ |
| Freerouting, the external router | Freerouting 2.5.0, the file `freerouting-2.5.0.jar` | https://github.com/freerouting/freerouting/releases (the v2.5.0 release, asset `freerouting-2.5.0.jar`) |
| A Java runtime, which Freerouting runs on | Eclipse Temurin OpenJDK 26.0.1 | https://adoptium.net/ or any other Java distribution. Freerouting 2.5.0 is built for Java 25, so it needs Java 25 or newer. |
| ngspice, the circuit simulator, as a program of its own. KiCad embeds ngspice only as a library, behind its simulator window, so the command-line program the steps below run is installed separately. | ngspice 47, on a netlist exported by KiCad 10.0.7's `kicad-cli` | https://ngspice.sourceforge.io/download.html. On macOS, `brew install ngspice` with Homebrew (https://brew.sh/), which is how the version opposite was installed. On Linux, the distribution's `ngspice` package. On Windows, the release archive from the download page, whose console program is `ngspice_con.exe`. |

KiCad's bundled Python is the one that can `import pcbnew`. Its usual location:

| System | KiCad's Python |
|---|---|
| macOS | `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3` |
| Windows | `C:\Program Files\KiCad\10.0\bin\python.exe` |
| Linux (distribution package) | the system `python3`, which the package gives the `pcbnew` module |

To check it, run `<KiCad's Python> -c "import pcbnew; print(pcbnew.Version())"`. It should print the KiCad version. The commands below write this Python as `KICAD_PYTHON` and the router's jar file as `FREEROUTING_JAR`. Replace them with the paths on your machine.

The commands below are written for a POSIX shell, the terminal on macOS or Linux, and were exercised on macOS. On Windows, run them in PowerShell. The `task` commands are typed as written. In the others, write `$env:KICAD_PYTHON` and `$env:FREEROUTING_JAR` where a command says `"$KICAD_PYTHON"` and `"$FREEROUTING_JAR"`, and start a command that begins with KiCad's Python with `& `, for example `& $env:KICAD_PYTHON -c "import pcbnew; print(pcbnew.Version())"`. Set them with `$env:KICAD_PYTHON = "C:\Program Files\KiCad\10.0\bin\python.exe"`. The Windows forms have not been exercised.

KiCad's bundled Python is used here only for the router's export and import. In KiCad 10.0.7 its `pcbnew` module was found unreliable for anything else: some objects it returns come back unwrapped, without their methods, so a net's class could not be asked for its clearance. Nothing else in this method reads or changes the board through it.

### The board editor, driven by an agent

The agent drives KiCad's editors through the Konnect MCP server, and runs every other command in this document from a shell. Konnect loads its tools in toolsets, mid-session. A toolset is visible only to the session that loaded it, not to a subagent spawned from that session, so routing and locking run in the session that loaded the board toolsets.

Konnect's editing tools act on the board through KiCad's IPC interface, so they need the board open in the board editor of the KiCad that Konnect reaches. Konnect reaches one KiCad only: the one holding KiCad's default IPC endpoint, which the first KiCad started takes. A board editor started while another KiCad is running takes an endpoint of its own, which Konnect does not reach (this was measured with KiCad 10.0.7 on macOS). So run one KiCad at a time while designing a board.

Several steps need the board closed in every editor: the editor does not see rules and classes written to the project until it opens the board again, and the board tooling and the router's export and import act on the board file outside the editor. Konnect has no tool that closes the board or the editor; its toolsets were searched for one. The agent's route is therefore not to hold the board open across those steps: it saves the board and quits the editor from a shell, then starts it again. To close the board:

1. Save it, with Konnect's `save_project`.
2. Quit the editor holding it. On macOS: `osascript -e 'quit app "pcbnew"'` for a board editor started on its own, or `osascript -e 'quit app "KiCad"'` for the board editor opened from KiCad's project window. On Windows: `taskkill /IM kicad.exe` or `taskkill /IM pcbnew.exe`, without `/F`, which asks KiCad to close rather than ending it. On Linux: close its windows through the desktop, for example `wmctrl -c KiCad`. Quitting asks first if the board has unsaved changes, which is why it is saved first.
3. Check that no KiCad editor is left running: `pgrep -lx kicad; pgrep -lx pcbnew` on macOS or Linux, `tasklist /FI "IMAGENAME eq kicad.exe"` and `tasklist /FI "IMAGENAME eq pcbnew.exe"` on Windows. Neither prints a process once KiCad has quit.

Quitting the board editor rewrites the project file, with KiCad's defaults filled in for settings it did not hold before, and writes `<board>.kicad_prl` beside it, which holds only the editor's own view settings. This was measured; the net class assignments and the text variables came through unchanged. Review the project file's change as you would any other.

To reopen the board: load Konnect's `verification` toolset and call its `launch_kicad_ui` naming the project. Then call Konnect's `open_project` naming the board. Carry on only when it reports the board open (`requested_open: true`). If it does not, start the board editor on the board from a shell, `open -a "/Applications/KiCad/PCB Editor.app" <board>.kicad_pcb` on macOS, `pcbnew <board>.kicad_pcb` on Linux, `& "C:\Program Files\KiCad\10.0\bin\pcbnew.exe" <board>.kicad_pcb` on Windows, and call `open_project` again. If it still reports the board not open, another KiCad holds the endpoint: close every KiCad as above and start again.

Of these, saving, quitting the board editor started on its own with `osascript`, the check with `pgrep`, starting the board editor from the shell, and `open_project` were exercised on macOS. `launch_kicad_ui` and the Windows and Linux forms were not.

While an editor holds a board open, KiCad keeps a lock file beside it, `~<board>.kicad_pcb.lck`, and `~<board>.kicad_pro.lck` for its project, and deletes both when the editor quits. The board tooling's lock, record and compare commands refuse to run while the board's lock file is there. The file holds only a user and host name, `{"hostname":"…","username":"…"}`, not a process, so it cannot say by itself whether an editor still holds the board. Ending the editor without quitting it, for example with a plain `kill` or after a crash, leaves both lock files behind: that was measured, as was quitting removing them. Tell a stale lock file from a live one this way:

- It is live while any KiCad editor could hold the board. If the check in step 3 above prints a process, the board may be open: if the only KiCad running is the one Konnect reaches, `open_project` naming the board says whether that KiCad holds it, and if it does, close the board as above.
- It is stale once the check in step 3 prints no process, or when the only KiCad running is the one Konnect reaches and `open_project` reports the board not open in it. Delete both lock files, `~<board>.kicad_pcb.lck` and `~<board>.kicad_pro.lck`.

Delete the project's lock file too, even though the board tooling looks only at the board's: a board editor reopening the board over a stale lock file with its own user and host name was measured to open it without asking and take over the board's lock file, but to leave the stale project lock file in place after it quit.

Where a judgement is visual, the agent looks at a rendered view of the board, never at the editor window: Konnect's export toolset and `kicad-cli pcb export svg` both render the board's layers. What to look for is the layout review step's.

## Proving value-critical circuits before layout

Do this before any footprint is placed on the board. Its purpose is that every circuit whose component values decide whether it works is shown to work while changing it still costs only an edit to the schematic: each has a figure it must meet, the figure comes from a source, and a calculation or a simulation shows the circuit meeting it under the worst conditions it will see.

This section and the next apply to every board that will be made, and to throwaway designs made to demonstrate this method. They do not apply to designs that exist only to prove the pre-order check's own tooling.

### 1. List every value-critical circuit

A circuit is **value-critical** when it works or fails on its component values, not only on its connections: wired exactly as drawn, it can still fail because a part was given the wrong value or rating. Go through the schematic block by block and ask of each: could this be connected correctly and still not do its job because of a value? If it could, it is value-critical. A connector carrying signals straight through to another board is not; most circuits with a resistor, a capacitor or a semiconductor chosen for its figures are.

Every board that has these circuits lists them:

- **A sensing front end**, the circuit between a sensor and the converter that reads it. Its noise and its settling time decide whether a reading is good enough to use.
- **A zero-crossing detector**, the circuit that reports when the alternating supply crosses zero. Its delay, between the true crossing and the edge it reports, decides how accurately anything timed from that edge is timed.
- **A drive stage**, the circuit that switches a load from a controller output. Its margin, the drive it gives against the drive its switching part needs to switch fully, decides whether it still switches at the lowest supply voltage.
- **Every conductor that relies on a protective device**: each track, copper pour or wire that carries current from a supply protected by a fuse or breaker. It must survive a fault until that device clears it. Its figures are the device's clearing time and the energy it lets through (its let-through I²t) at the declared fault current, both read from the device's datasheet, with the fault current from the machine's constraints record. Its result is the energy the conductor withstands at the cross-section the board will give it, calculated with the arithmetic shown.

### 2. State each circuit's figure and where it comes from

Keep a table in a file named `circuit-proof.md` in the board's own folder, beside its KiCad project. Give it one row for every value-critical circuit:

| Circuit | What its values decide | Figure | Source of the figure | How shown | Conditions covered | Result | Met |
|---|---|---|---|---|---|---|---|

- **Circuit** names the circuit and the reference designators of the parts whose values matter, for example `Input filter, R12 C7`.
- **Figure** is the value the circuit must meet for the board to do its job, with its unit and which side of it passes, for example "settles to within one count of its final reading in at most" a stated time, or "withstands at least" a stated energy.
- **Source of the figure** is one of two things: the machine's constraints record (name the figure in it), or the datasheet of the part the figure belongs to (name the part, its manufacturer, the datasheet's revision or date, and the table or graph the figure is read from). A value marked typical, with no minimum or maximum, is not a source, nor is a value a tool fills in by default, nor one estimated for this record.

A figure its source does not yet bound, because the constraints record marks it pending or gives no value, or because the datasheet gives it only as typical, fails this step until the source is amended to give one. Never write into this record a figure the source does not hold: the remedy is to amend the source, and the board waits for it.

### 3. Show that each circuit meets its figure, under the worst conditions it will see

Each result is shown in one of three ways, and **How shown** says which, naming the file where there is one:

- a **calculation**, with every step's arithmetic written out, in the record or in a file beside it, and every input value taken from the schematic or from a source as step 2 defines it;
- a **short Python script**, committed in the board's folder, that prints the result;
- a **simulation** with ngspice, as below.

**Conditions covered** states the conditions each result holds under. They include:

- **the worst of the declared supply span**: the lowest and the highest voltage the machine's constraints record declares for the supply the circuit runs from, whichever is worse for this figure;
- **the worst of the parts' tolerances**: each part's value at the end of the tolerance its datasheet states that is worse for this figure, all of them at once;
- **for a sensing front end, the switched loads operating**, wherever the source bounds the interference the machine's switched loads impose on the circuit, for example as a stated disturbance on its supply, its input or its ground. Where the source does not bound it, the cell says plainly: `Switched loads operating: not covered; left to measurement at bring-up.` This is the one condition a missing bound leaves open without failing the step. A missing figure still fails it.

**Result** gives the value shown, under those conditions. **Met** is `yes` only when the result meets the figure under every condition the row lists.

To simulate, run these from the board's folder, with `kicad-cli` written as the path to KiCad's command-line tool if it is not on your search path, as `hardware/README.md` describes. Keep the files in a folder named `circuit-proof` beside the record.

1. Export the schematic as a SPICE netlist:

   ```
   kicad-cli sch export netlist --format spice --output circuit-proof/<board>.cir <board>.kicad_sch
   ```

   It writes one line per part, such as `R1 /IN /OUT 10k`, naming the nets each part joins.

2. Write a simulation input for the circuit, `circuit-proof/<circuit>.cir`, that brings in the netlist, runs an analysis and measures the figure. For example, the time a resistor and capacitor take to charge to 63 % of a 5 V step:

   ```
   Input filter settling: time for OUT to reach 63 % of a 5 V step
   .include <board>.cir
   .tran 10u 5m uic
   .meas tran t_settle WHEN v(/OUT)=3.16 RISE=1
   .end
   ```

   The first line is a title. `.include` names the netlist, from the input's own folder. `.tran` runs a transient analysis, in time steps of 10 µs for 5 ms, starting from zero (`uic`). `.meas` measures the figure and gives it a name. Nodes are named as the netlist names them.

   To cover the conditions, change values and run again inside a `.control` block, which takes the place of the `.meas` line. Keep the `.tran` line; each `run` repeats it. `alter` sets a part's value, a supply source's voltage included:

   ```
   .control
   alter R1 = 9.9k
   alter C1 = 90n
   run
   meas tran t_settle_low WHEN v(/OUT)=3.16 RISE=1
   alter R1 = 10.1k
   alter C1 = 110n
   run
   meas tran t_settle_high WHEN v(/OUT)=3.16 RISE=1
   .endc
   ```

3. Run it in batch mode, with no window:

   ```
   ngspice -b circuit-proof/<circuit>.cir -o circuit-proof/<circuit>.log
   ```

4. Read the result from the log's line naming the measurement, for example `t_settle = 9.99665e-04` (ngspice pads it with spaces), and quote that line in **Result**.

Three things were measured with ngspice 47 that decide whether the log can be believed:

- **ngspice's exit status is not evidence.** It exits with success when a measurement fails and when it cannot solve the circuit. A log with a line containing `failed!`, `Error` or `singular matrix` holds no result, whatever value it also prints.
- **Ground must be named `0` or `GND`.** ngspice takes either as its ground. A circuit whose reference net had another name ran with only a warning and gave a wrong result. If the board's reference net is named otherwise, add `Vgnd <net> 0 0` to the simulation input, after the `.include`, which ties that net to ground.
- **Every part in the netlist needs a model.** KiCad's resistor, capacitor and simulation source symbols carry one. A part with none, such as a connector, exports as a line ngspice refuses (`Unable to find definition of model`), and the simulation stops. Mark such a part excluded from simulation in its symbol's properties, which leaves it out of the exported netlist while it stays on the board. If a part the circuit depends on has no model, show the circuit by calculation instead, or give its symbol the manufacturer's published model through KiCad's simulation model settings and commit the model file beside the input. That last route has not been exercised.

The commands were exercised on macOS. On Windows, run `ngspice_con.exe` in place of `ngspice`, with the same arguments; that form has not been exercised.

### 4. Commit the record before placement

Commit `circuit-proof.md`, the exported netlist and every simulation input, script and calculation file it names, in a commit made before the first commit that places a footprint on the board. The order is then checkable from git history, from the board's folder:

```
git log --reverse --format=%h -- circuit-proof.md | head -1
git log -S'(footprint ' --reverse --format=%h -- <board>.kicad_pcb | head -1
git merge-base --is-ancestor <record commit> <placement commit>
```

The first prints the commit that added the record, the second the first commit that added a footprint to the board, and the third exits with success when the first is an ancestor of the second or the same commit. The record is in time when the third succeeds and the two commits differ. Before any footprint is placed the second prints nothing, and the record need only be committed.

A later change to a listed circuit's parts or values, or to its figure at the source, reopens its row: export the netlist again, show the circuit again, and commit the record before the board is ordered.

A board entering layout fails this step when a value-critical circuit is missing from the record, or a listed circuit lacks a figure, a source of the kind step 2 allows, or a result that meets its figure under the conditions step 3 requires, or when the record was not committed before placement. The remedy is a change to the circuit, shown again, or an amendment to the figure's source. Never the figure relaxed in this record, and never a shortfall judged unimportant.

Out of scope for this section: measuring the built circuit, which belongs to bring-up; coupling that depends on the layout itself, which a proof made before layout cannot show; and the figures for a particular machine, which come from its constraints record.

## Designing for bring-up and a second spin

Do this before any footprint is placed on the board, alongside the previous section. A first spin of a board is expected to need changes, and it must be diagnosable when it does. So every board carries what bring-up needs to find out what is wrong: a test point on every rail and on each key signal, a link that isolates every rail from its loads, and a way to limit the current first power can draw. These are parts in the schematic, each with its own footprint, left on the board. The pre-order check's schematic parity, which fails a layout that disagrees with its schematic, then fails a board from which one of them is missing.

### 1. Name every rail and every key signal

A **rail** is every supply net on the board: each net that a regulator, converter, reference or supply input holds at a voltage to power other parts. That includes derived rails, made on the board from another, and reference rails, the voltages a converter or comparator measures against. Ground and return nets are not rails: they are the reference every rail is measured from, and carry no isolating link. A mains-referenced supply net is a rail like any other.

A **key signal** is a signal bring-up must observe to tell whether a block of the board works. It includes each sensing front end's output, each drive stage's control input, the controller's reset, clock and programming interface, and any safety interlock's signal. Which signals of a particular board are key is that board's own design work; the test is whether, without probing the signal, bring-up could not tell whether its block works.

### 2. Give every rail and key signal a test point, and every rail an isolating link

A **test point** is a part in the schematic with its own reference designator, a pad or a test-point part on the net, that a multimeter or oscilloscope probe can touch on the built board.

An **isolating link** is a part fitted in series in a rail, between where the rail is produced and everything it feeds, that a builder can open and close again with hand or soldering tools: a removable jumper on a two-pin header, a zero-ohm resistor, or a solder jumper. One link per rail, placed so that opening it separates the rail's source from all of its loads. The link divides the rail into two nets, its source side and its load side. They are still one rail, with one link and one test point. Put the test point on the source side, so the rail can be measured with its loads disconnected; the link's load-side pad then reaches the loads, for example to measure their resistance to ground before power is applied.

A test point or link on a mains-referenced net is mains copper. It goes in the `Mains` net class with every other mains-referenced net, as step 2 of the rules section requires, and is held to the board's separation basis like any other mains copper.

### 3. Give first power a means of current limiting

The first time a board is powered, a short or a part fitted wrongly must not be able to draw enough current to do damage. The **current-limit means** is the way the board's draw on first power is limited. It is carried on the board, for example a current-limiting stage at its supply input, or it needs only what a builder without a laboratory has: a multimeter, hand and soldering tools, and ordinary parts, such as a series resistor or a lamp fitted in a link position, typically in place of the supply input's isolating link. A means that needs other instruments, such as a bench supply with its own current limit, does not count.

### 4. Record the provisions, and commit them before placement

Keep a table in a file named `bring-up-provision.md` in the board's own folder, beside its KiCad project. Give it one row for every rail and every key signal, and one row for first power:

| Rail, key signal or first power | Net | Test point | Isolating link | What it is for |
|---|---|---|---|---|

- **Test point** and **Isolating link** name the parts by reference designator. Isolating link is filled in for rails only, and is `—` for a key signal.
- **What it is for** says, for a rail, where it is produced; for a key signal, the block whose working it shows; and, in the first power row, the current-limit means and where it is fitted, by reference designator.

Commit the record before the first commit that places a footprint on the board, checked from git history as step 4 of the previous section shows, with `bring-up-provision.md` in place of `circuit-proof.md`. A later change to the board's rails or key signals is recorded before the board is ordered.

A board on which any rail lacks a test point or an isolating link, any key signal its record names lacks a test point, or first power cannot be current-limited by a means this section allows, fails this step. The remedy is to add the missing part to the schematic, and its row to the record.

Out of scope for this section: carrying out bring-up on built boards, and choosing which signals of a particular board are key, which is that board's own design work.

## Rules before routing

Do this before any track is routed. Its purpose is that every rule the board is routed and checked against is written down, traceable to where its figure comes from, and that the table says which of them KiCad confirms on the board itself, which KiCad's rule check enforces before the board is ordered, and which, a net class's track width and via sizes, are only the defaults routing starts from.

Close the board in every editor before writing anything in this section, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, and keep it closed until step 4. An editor holding the board keeps its own copy of the project file and writes that copy over the file when it quits: a text variable and a net class pattern written to the project file while the board editor held the board open were measured to be gone after it quit. Konnect's tools that write net classes write the project file, so they are no exception.

### 1. Write every rule and net class down, with its figure and source

Keep a table in a file named `design-rules.md` in the board's own folder, beside its KiCad project. Give it one row for every design rule and every net class the board uses:

| Rule or net class | Figure | Where it is set in KiCad | Source of the figure | Confirmed in effect |
|---|---|---|---|---|

- **Design rules** are the board-wide minimums (clearance, track width, via diameter and drill, hole size, annular ring, hole-to-hole, copper-to-edge, silkscreen), each custom rule in the board's rules file, and every net class's own clearance, track width and via sizes.
- **Source** says where the figure comes from, for example: the machine's constraints record (name the figure in it); a requirement the board serves (name the requirement); the manufacturer's stated limits (name the manufacturer and the date of the capability page the figure was read from); the separation basis record; or a finding from a layout review that became a rule (name the review). "Default", "typical" or "what KiCad had" is not a source.
- **Confirmed in effect** says, for each kind of row, what stands behind it, and nothing else may be written there:
  - a **custom rule** in the board's rules file: that KiCad loaded the rules file, from step 3's output;
  - a **net class**: the nets step 3 lists for it;
  - a **board-wide minimum**, and a **net class's own clearance**, set in Board Setup: `not confirmed by step 3; enforced by the layout rule check in the pre-order check`. Step 3 cannot read these figures, so they are never marked confirmed. They stand on the figure and source written in the row. KiCad's layout rule check reports copper, holes and silkscreen that break any of them, as an error, or as a warning for silkscreen clipped by the board edge, and the pre-order check (step 7 of routing) fails the board on either;
  - a **net class's own track width and via sizes**: `routing default only; not enforced`. KiCad starts a track or via on the class's nets at these sizes, but its layout rule check does not hold copper to them: a narrower track or a smaller via on such a net raises no violation of the class's figure, and the pre-order check passes it. A track width or via size the board relies on, such as a mains or power track's width, is therefore also written as a custom rule in the board's rules file, conditioned on the class, one constraint per rule:

    ```
    (rule "Power track width"
    	(condition "A.hasNetclass('Power')")
    	(constraint track_width (min 1.0mm)))
    (rule "Power via diameter"
    	(condition "A.hasNetclass('Power')")
    	(constraint via_diameter (min 1.2mm)))
    (rule "Power hole size"
    	(condition "A.hasNetclass('Power')")
    	(constraint hole_size (min 0.6mm)))
    ```

    `hole_size` holds every hole on the class's nets, pad holes as well as vias. Each such rule has its own row, with its figure and source, confirmed by step 3 like any custom rule and enforced by the layout rule check in the pre-order check.

A rule with no stated source fails this step. Give it a source or remove it.

### 2. Declare whether the board carries mains

Every board declares this in its project text variable `MAINS`, set to exactly `present` or `none`: in the project file, `"text_variables": {"MAINS": "present"}`. Write it into the project file, with the board closed in every editor. A board with no mains declaration fails this step, and the pre-order check fails it too.

**A board that declares `none`** puts no net in the `Mains` net class.

**A board that declares `present`**:

- assigns every mains-referenced net to the net class named exactly `Mains`. These are the nets at mains potential and those referenced to it, such as a switched live or the low side of a heater. You can assign a net in the schematic with a net class directive, or in the project's net classes by assignment or by pattern (Konnect's `create_netclass` and `assign_net_to_class` write them, and work with the board closed);
- writes the separation between mains and low-voltage copper as **one** custom rule in the board's rules file, `<board>.kicad_dru` beside the project, a text file written with the board closed in every editor. The rule must be exactly in this form:

  ```
  (version 1)
  (rule "Mains separation"
  	(condition "A.hasNetclass('Mains') && !B.hasNetclass('Mains')")
  	(constraint clearance (min <clearance>mm))
  	(constraint creepage (min <creepage>mm)))
  ```

  The condition is written exactly as shown, with no other spacing. The rule has no `(layer ...)` clause and no other narrowing by layer or area. It holds both a `clearance` and a `creepage` constraint, each in millimetres. `<clearance>` and `<creepage>` are no less than the separation basis record's mains-to-low-voltage clearance and creepage (`mains_to_low_voltage.clearance_mm` and `.creepage_mm` in the `separation-basis.yaml` that holds the board to its signed figures). In the table from step 1, both figures name that record as their source. The pre-order check accepts the rule in this form only, and holds the board to the record's figures whatever the rule states.

**Local clearance overrides can defeat the separation rule.** Pads, footprints and zones can each carry a clearance of their own, set outside the custom rules. A local clearance override on a pad or a footprint takes precedence over every custom rule in KiCad, which applies the larger of the two items' overrides. So a small override on either side of a mains/low-voltage pair would let low-voltage copper sit closer to mains than the separation rule allows. Treat a zone's own clearance the same way, although KiCad 10 (10.0.7) was measured not to let it outrank a custom rule. Set none of these below the separation basis record's clearance. The pre-order check fails any pad or footprint override that undercuts the signed figure, and any zone on a `Mains`-class net whose own clearance does. It checks a zone's clearance only on a `Mains`-class net. A zone's own clearance does not outrank the separation rule, so a low-voltage zone's cannot undercut it; a `Mains`-class zone is still held to the signed figure, so the board never states a smaller mains separation than the one it is checked against.

### 3. Confirm that KiCad loads the rules file and places each class's nets, by asking KiCad

With the board still closed, from the board's folder, run:

```
task hw:rules-confirm -- --board <board>.kicad_pcb --project <board>.kicad_pro --class <net class> [--class <net class> ...]
```

Name every net class in the table with its own `--class`, `Mains` among them on a board that declares mains. Give the board's own project file, the one beside it with its name. Set `KICAD_CLI` as `hardware/README.md` describes if `kicad-cli` is not on your search path.

The command never reads the rules or the classes from the files. It runs KiCad's own layout rule check on a copy of the board, with its project file and its own rules file, `<board>.kicad_dru`. A marker rule appended to that file fires only if KiCad loaded all of it, since KiCad drops a whole rules file it cannot parse, without saying so. One probe rule per class lists the nets KiCad places in that class. The command fails:
- when KiCad did not load the rules file, naming the rule KiCad rejects;
- when the board has no rules file. A board with no custom rules still has one, holding `(version 1)` alone;
- when a named class is not one the design defines, or KiCad places no net of the board in it;
- when `MAINS` is not exactly `present` or `none`, or is `present` and `Mains` is not named.

Otherwise it prints each class with the nets KiCad puts in it, and `RESULT | CONFIRMED`. Check each class's list against your intent: every net you meant to put in the class is there, and no other. A critical net missing from its list is in the wrong class.

Fill in the table's last column from this output: for each net class, the nets listed; for each custom rule, including one that holds a class's track width or via size, that KiCad loaded the rules file; for each board-wide minimum and each class clearance set in Board Setup, that step 3 does not confirm it and the pre-order check's layout rule check enforces it; and for each class's track width and via sizes, that they are a routing default only and not enforced, as step 1 says. A custom rule or net class row not filled in from this output fails this step, and so does a figure row marked confirmed, and a class track width or via size row marked enforced. So does a failure of the command.

What this confirms is that the rules file loads and that each class holds the nets intended. It does not show that each figure is the one KiCad applies, since a later rule can shadow an earlier one. The separation figure, the one that matters most, is enforced by the pre-order check's own rule whatever the board writes.

### 4. Close the board, and reopen it before routing

The board editor does not see rules or classes written to the project, or a rules file written beside it, until it opens the board again. This holds whether they were written by editing the files or through Konnect. So after step 3 and before routing anything, the board is closed in every editor, as it has been throughout this section, and then reopened, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes.

If an editor held the board open at any point in this section, close it now, and check that what you wrote is still in the project file and the rules file, since quitting the editor writes its own copy of the project file over the file. Write again whatever was lost, with the board closed, and repeat step 3 before reopening.

Out of scope for this section: the figures themselves, which come from the machine's constraints record and its separation basis record, and the automated check that later holds the board to the rules its layout rule check enforces, the pre-order check.

## Routing: critical nets by hand and locked, then the rest

The nets that decide whether a board works are never left to an automatic router. They are routed deliberately to their stated rules and locked. Automated routing is then run only one way: KiCad's exporter, the external router from its command line, then KiCad's importer (step 5). It places only what is left unrouted, and may not move a locked item. Locking is done by the board tooling's lock command on the closed board file (step 3). A check in the board tooling, never a comparison by hand and never the router's own report, confirms afterwards that nothing locked was moved and nothing was added to a critical net. Only the board's own tracks, arcs, vias and zones are locked and recorded; a copper zone inside a footprint is not covered.

### 1. Put every critical net in a named critical class

The critical classes include at least the board's **power**, **decoupling**, **ground**, **mains** and **sensing** paths. Assign every net in those categories to a named net class in step 1 of the rules section, for example `Power`, `Decoupling`, `Ground`, `Mains` and `Sensing`. The names are the board's own, and the mains class is always `Mains`. Every critical class is named to the lock and record steps below, which protect only the classes they are given. A critical net left in the `Default` class therefore fails this step: its copper would not be protected. The board tooling refuses what it can read: a named class holding no net, and, on a board that declares mains, a set of classes that leaves out `Mains`. Which other nets are critical it cannot read, so that stays your judgement.

Which further nets of a particular board are critical is that board's own design work.

### 2. Route every critical net by hand, to its class's rules

On the reopened board, route every net in every critical class yourself, to the rules its class states: every track, arc and via, with Konnect's routing tools. A copper zone on a critical net, such as a ground or mains pour, is deliberate routing like a track, so draw it yourself too. Do this in the session that loaded Konnect's routing toolset, not in a subagent, which would not see it. Look at a rendered view of the board to judge the result.

Save the board, with Konnect's `save_project`.

### 3. Close the board, and lock every critical item

Close the board in every editor, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes. Then, from the board's folder, run:

```
task hw:copper-lock -- --board <board>.kicad_pcb --project <board>.kicad_pro --class <critical class> [--class <critical class> ...]
```

Name every critical class with its own `--class`. This marks every track, arc, via and zone on a net KiCad places in those classes locked in the board file, writing `(locked yes)` where KiCad writes it and changing nothing else. It prints each item it locked, and each class with its nets. It refuses, and leaves the board unchanged, when:
- KiCad's lock file shows the board open in an editor;
- the project file is not the board's own;
- a named class is not one the design defines, holds no net, or is named twice;
- `MAINS` is not exactly `present` or `none`, or is `present` and `Mains` is not named.

A locked item is changed only by a deliberate re-route: remove it, route it again on the reopened board, then close the board and lock again. A re-route after recording needs a fresh record.

### 4. Record the critical-class copper, immediately before export

With the board still closed, from the board's folder, run:

```
task hw:copper-record -- --board <board>.kicad_pcb --project <board>.kicad_pro --class <critical class> [--class <critical class> ...] --record <work folder>/<board>.record.json
```

Name the same classes as step 3.

The record lists every track, arc, via and zone on a net KiCad places in those classes, each with its properties and whether it is locked, and the nets each class holds. It is a working file. Write it to a folder that is not inside any design's folder, and never commit it.

The command refuses, and writes no record, in each case step 3 refuses, and when:
- the record's path is inside the board's folder, or inside any folder that holds a KiCad project file;
- the record cannot be written where it was asked to go;
- any critical-class item is not locked. It names each one; lock again (step 3) and record again.

### 5. Export, route the rest externally, import

Before exporting, keep copies of the board file and the project file as they stand, so the board can be restored if step 6 fails: in the work folder, under names that do not end in `.kicad_pcb` or `.kicad_pro` (for example `<board>.kicad_pro.before`), since a folder holding a project file is a design's folder, where the record is refused. Or commit both.

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

Saving this way also rewrites the project file, with KiCad's defaults filled in for settings it did not hold before. Review that change against the copy kept before export, as you would any other.

The router's own report, for example `0 unrouted and 0 violations`, is not evidence of anything. Neither the router nor the importer is relied on to leave locked copper alone.

### 6. Compare the imported board with the record

From the board's folder, run:

```
task hw:copper-compare -- --board <board>.kicad_pcb --project <board>.kicad_pro --record <work folder>/<board>.record.json
```

With the board still closed, give the same board, its own project file, and the record taken of that board in step 4. This fails, naming each item, when:
- a recorded item is missing;
- a recorded item is no longer locked;
- a recorded item is changed in any recorded property, with each changed property given as old → new;
- a critical-class net carries a track, arc, via or zone that the record does not hold;
- a critical class the record names is no longer defined by the design;
- `MAINS` is not exactly `present` or `none`, or is `present` and the record's classes leave out `Mains`.

The critical nets at comparison are every net the record names and every net the critical classes hold now, so a net that left its class after recording, for example because the import rewrote the project file, is still checked. An added item identical to a recorded one is still reported as added. Copper on nets outside both is the router's, and is ignored. A record taken of another board, a project file that is not the board's own, or a board KiCad's lock file shows open, fails the comparison without comparing anything. A failure fails this step whatever the router or the importer reported. Restore the board as it was before export, correct the cause, and repeat from step 2.

A board on which any critical-class net was placed by the router fails this step.

### 7. Run the board's own rule checks, then reopen the board

Run the pre-order check, which runs KiCad's own electrical and layout rule checks with zones refilled:

```
task hw:verify
```

It checks only designs git tracks (`git add` is enough), as `hardware/README.md` explains. It must pass. A router's or editor's "no violations" is never accepted in its place. Reopen the board in the editor, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, only after this check and the comparison in step 6 have run, and only to continue work on it.

Out of scope for this step: judging the quality of the layout, which is the layout review step.
