# Board design method

This is how a controller board is designed in KiCad so that it passes the pre-order check and works once built. The method works for any machine. A machine's own figures come from its own records, and this document names each record only by the role it plays: the machine's constraints record, its separation basis record, the requirements a board serves, the board manufacturer's stated limits, and the datasheets of the parts on the board. A physical constant or a property of a material is stated in this document, with where it was published, wherever a step uses one, so no standard that must be bought is needed to carry a step out.

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
- **Every conductor that relies on a protective device**: each track, copper pour, via, wire or isolating link that carries the device's fault current, from the device, or from the supply input where the device is off the board, up to the first part that limits the current below that fault current, such as a regulator whose current limit is read from its datasheet, or a series resistance shown by arithmetic to limit it. Beyond such a part the fault current is that part's limit, not the device's, and the conductors there are not in this row. It must survive a fault until that device clears it. Its figures are the device's clearing time and the energy it lets through (its let-through I²t) at the declared fault current, both read from the device's datasheet, with the fault current from the machine's constraints record. Its result is the energy the conductor withstands at the cross-section the board will give it, calculated with the arithmetic shown, by the relation and from the inputs step 3 gives for it; a bought link's row instead takes its result from the rating its datasheet states, as step 2 of "Designing for bring-up and a second spin" states.

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

- a **calculation**, with every step's arithmetic written out, in the record or in a file beside it;
- a **short Python script**, committed in the board's folder, that prints the result;
- a **simulation** with ngspice, as below.

Whichever way it is shown, every input to it is sourced, as the figure is, and the row or the file beside it names where each input was read. Step 2's rule is for the figure a circuit must meet; an input to showing it may come from any of these:

- the schematic, for a part's value and how it is connected;
- a part manufacturer's simulation model, for how the part is built and behaves, never as the source of a limit, since a model gives typical behaviour only;
- a source as step 2 defines it, the machine's constraints record or a part's datasheet;
- the board manufacturer's stated limits, for what the board is made of and to, such as its copper thickness (name the manufacturer and the date of the page the figure was read from), or the datasheet of the board material those limits name;
- for a physical constant or a property of a material, the value this document states, or one read from a published reference any reader can obtain without paying (name it, with its edition and the clause or table the value is read from). A value read only from a standard that must be bought is not a source here, since a builder without it could not check it.

A tool's default is not a source here either. ngspice, for one, simulates at 27 °C unless its input says otherwise: where a result depends on temperature, set it with a `.temp` line, for example `.temp 85`, at the end of the temperature range the machine's constraints record declares for the board that is worse for the figure, and list it under Conditions covered. `.temp` changes only models that carry a temperature behaviour of their own. The resistor and capacitor models KiCad's symbols use carry none: `.temp 125` was measured to leave a resistor and capacitor's settling time unchanged. So a part's drift with temperature, read from its datasheet, is applied with `alter` (simulation step 2 below), as the part's value at that temperature, and listed under Conditions covered.

**A conductor's withstand** is calculated from the adiabatic short-circuit relation, the one IEC 60949 gives for a conductor heated by a fault. It takes all of the fault's heat to stay in the conductor, so it errs safe:

```
k² × S² ≥ I²t        where   k = K × √( ln( (θf + β) / (θi + β) ) )
```

- **I²t** is the row's figure, the protective device's let-through at the declared fault current, in A²s.
- **S** is the conductor's cross-section, in mm². For a track or a copper pour, it is the narrowest width the current passes through times the thinnest finished copper the board manufacturer's stated limits allow for the copper weight the board will be ordered with. Where a pour joins a pad through thermal-relief spokes, the spokes are a narrowest neck: take their combined width, or join the pad to the pour solidly. A via the current passes through is a conductor too: its cross-section is its barrel's plating, the hole's circumference times the manufacturer's stated minimum plating thickness, times the number of vias that share the current. For a wire, it is the cross-section its datasheet states.
- **K** and **β** are constants of the conductor's material. For copper, **K = 226 A·s½/mm²** and **β = 234.5 °C**, the values IEC 60949 (1988) gives in its Table 1; they are stated here so that standard is not needed. K is copper's √(σc × (β + 20) / ρ20), from its volumetric heat capacity σc = 3.45 × 10⁶ J/(K·m³) and its resistivity at 20 °C ρ20 = 1.7241 × 10⁻⁸ Ω·m, the values the same table gives: √(3.45 × 10⁶ × 254.5 / (1.7241 × 10⁻⁸)) = 2.257 × 10⁸ A·s½/m², which is 226 A·s½/mm². As a check on the arithmetic, θi = 90 °C and θf = 250 °C give k = 226 × √(ln(484.5 / 324.5)) = 143 A·s½/mm². Name these constants and this document as their source in the row.
- **θi** is the conductor's temperature when the fault begins: the highest temperature the board material is rated to run at continuously, its maximum operating temperature, from the manufacturer's stated limits or the board material's datasheet. No conductor may run hotter than that in service, so starting from it errs safe.
- **θf** is the highest temperature the conductor may reach before the device clears the fault. It is a temperature the board material's datasheet states the material withstands, without damage, for at least the device's clearing time, such as a thermal stress rating given as a temperature held for a stated time. A rating held for less than the clearing time is not a source for it. Where the conductor ends at a soldered joint, θf is no higher than the solder's melting point, from the solder's datasheet. A wire's θf is its insulation's short-circuit temperature, from its datasheet; for bare wire, which has no insulation, the solder-joint and board-material bounds govern, as for a track.

The **Result** is k² × S² in A²s, with the width, copper, vias and temperatures it assumed, and **Met** is `yes` when it is no less than the figure. Where no source states a θi or a θf, the input is not bounded, and the row fails this step as an unbounded figure does, until a board material whose datasheet or stated limits give one is chosen.

What the calculation assumes, the board is then held to. The width it assumed is written into the table the rules section keeps as a custom track-width rule on the conductor's net class, a copper pour's narrowest neck as a `connection_width` rule on the same class, which KiCad's layout rule check holds a zone's fill to as `track_width` holds a track, and a via's hole into a hole-size rule, each with this record's row as its source (step 1 of the rules section). The vias the row assumes share the current are counted on the routed board before it is ordered, on a rendered view of the conductor's path, and each pad the pour joins is checked there to be joined as the row assumed, solidly or by spokes of the combined width it took; fewer vias, or a narrower or a relieved join where the row assumed otherwise, reopens the row. The copper weight it assumed is the weight the board is ordered with.

**Conditions covered** states the conditions each result holds under. They include:

- **the worst of the declared supply span**: the lowest and the highest voltage the machine's constraints record declares for the supply the circuit runs from, whichever is worse for this figure;
- **the worst of the parts' tolerances**: each part's value at the end of the tolerance its datasheet states that is worse for this figure, all of them at once. Where the circuit is not monotonic in a part's value, so that neither end is plainly worse, run every combination of the parts' tolerance ends, or show in the row why the combination chosen is the worst. A semiconductor's parameters that its datasheet gives only within limits count among these, such as a transistor's threshold voltage or a comparator's propagation delay: for each one the figure depends on, the result moves it to the datasheet limit that is worse for the figure, or the row is shown by calculation with the datasheet limits instead;
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

   Keep each circuit's simulation to that circuit. The netlist holds the whole board, and on a real board a circuit's supply usually comes from a regulator or a connector, which has no model and is excluded from simulation (below), so nothing in the netlist drives it. Give the circuit its supply in its own simulation input instead, after the `.include`, as a source on the supply's net, for example `Vsup +3V3 0 3.3` for a net a power symbol names `+3V3`, and set it to each end of the supply span with `alter Vsup = ...`. The rest of the board stays in the netlist, but a simulation source holds its net at the voltage it is given whatever else draws on it, so another block changes this circuit's result only through a net it shares with the circuit's own signal path, which makes it part of the circuit. Measure only at the circuit's own nets.

   A parameter of a part's model is set with `altermod`, naming the model and the parameter, for example `altermod NM vto=1.4` for a model named `NM`. A model inside a subcircuit is named by the subcircuit's instance in the netlist, a colon and the model's name, for example `altermod x1:nsub vto=1.4`. Both forms were measured with ngspice 47 to change the result of the next `run`. A model that does not expose the parameter the figure depends on cannot be moved this way, and that row is shown by calculation instead.

   Every value a simulation input sets, with `alter`, `altermod`, `.temp` or a source it adds, is one the row's Conditions covered lists, with where it was read. A simulation input sets nothing else: a part's nominal value comes from the netlist, never from a line written after the `.include`.

3. Run it in batch mode, with no window:

   ```
   ngspice -b circuit-proof/<circuit>.cir -o circuit-proof/<circuit>.log
   ```

4. Read the result from the log's line naming the measurement, for example `t_settle = 9.99665e-04` (ngspice pads it with spaces), and quote that line in **Result**.

Three things were measured with ngspice 47 that decide whether the log can be believed:

- **A result is read only from a run that exited with status 0 and whose log holds the measurement's own line**, its name, `=` and a number. Both are needed. ngspice exits with a non-zero status when it refuses its input or cannot solve the circuit, but with 0 when a measurement fails, so a status of 0 alone does not show a result. A measurement that fails prints no value line; it prints lines such as `Error: measure  t_settle  when(WHEN) : out of interval` and one ending `failed!` in its place. A log with any line beginning `Error` holds no result for the row, whatever value it also prints. These messages are examples of what was observed, not a list to match against: judge by the exit status and the measurement's own line.
- **Ground must be named `0` or `GND`.** ngspice takes either as its ground. A circuit whose reference net had another name ran with only a warning and gave a wrong result. If the board's reference net is named otherwise, add `Vgnd <net> 0 0` to the simulation input, after the `.include`, which ties that net to ground.
- **Every part in the netlist needs a model.** KiCad's resistor, capacitor and simulation source symbols carry one. A part with none, such as a connector or a regulator, exports as a line naming only the part, such as `J1 __J1`, which ngspice refuses: the simulation stops and ngspice exits with a non-zero status. The log names the refused line after a line beginning `Error on line`; the message that follows was observed to vary with the letter the part's reference begins with, for example `Unable to find definition of model` for `J1` or `U1` and `model name is not found` for `P1`. Mark such a part excluded from simulation in its symbol's properties, which leaves it out of the exported netlist while it stays on the board. If a part the circuit depends on has no model, show the circuit by calculation instead, or give its symbol the manufacturer's published model through KiCad's simulation model settings and commit the model file beside the input, with its datasheet-limited parameters moved to their limits as the tolerances above require. Giving a symbol a model through KiCad's settings has not been exercised.

The commands were exercised on macOS. On Windows, run `ngspice_con.exe` in place of `ngspice`, with the same arguments; that form has not been exercised.

### 4. Commit the record before placement

Commit `circuit-proof.md`, the exported netlist and every simulation input, script and calculation file it names, in a commit made before the first commit that places a footprint on the board. What this step judges is the record as it stood in that earlier commit, not the record as it stands now, so a record committed empty and filled in after placement does not pass. Judge it on the branch as pushed, fetched afresh and checked out, before it is merged: history rewritten before then can make a record written after placement look as if it came first.

From the board's folder, find the placement commit and check out the commit before it into a folder of its own, outside the repository:

```
git log --follow -S'(footprint ' --format=%h -- <board>.kicad_pcb | tail -1
git worktree add --detach <work folder>/before-placement <placement commit>^
```

The first prints the first commit that added a footprint to the board, under whatever name the board file had then: `--follow` carries the search back across a rename, without which a board placed under another name and renamed afterwards would be found only at its rename. Do not add `--reverse` to it; with `--follow` it was measured to print nothing at all. While no footprint has been placed it prints nothing and still exits with status 0; the record is then judged as it stands, in the board's own folder, by the same checks. The second exits with a non-zero status when there is no commit before the placement commit, and then nothing was committed before placement and the step fails. Otherwise the board's folder inside `<work folder>/before-placement` holds the board as it stood before placement. Judge there; if `circuit-proof.md`, or a file a row names, is not in it, it had not been committed, and the step fails.

In that folder, judge steps 1 to 3, and cross-check the record against the schematic rather than taking its word:

- **Every value-critical circuit has a row.** Go through the schematic block by block, as step 1 does. At the least, every input of a converter that a sensor feeds, every fuse or breaker (each conductor that carries its fault current, as step 1 bounds them), every conductor protected only by a device off the board (such as the copper from an input connector to the board's own fuse), every isolating link whose rating rests on this record (step 2 of the next section), every part that switches a load from a controller output, and every circuit that reports the alternating supply's crossings, has a row.
- **The netlist is the schematic's.** Export it again there and compare it with the committed one:

  ```
  kicad-cli sch export netlist --format spice --output <work folder>/check.cir <board>.kicad_sch
  cmp <work folder>/check.cir circuit-proof/<board>.cir
  ```

  Exports of an unchanged schematic were measured to be identical byte for byte, for parts with models built into KiCad, and such a netlist is compared as it is. A netlist holding an `.include` line for a manufacturer's model may name that file's path as it stood where it was exported, so before comparing, rewrite the path on each `.include` line of both netlists as the path from the board's folder; like the model route in step 3, this has not been exercised. `cmp` exits with status 0 when the two are identical; any other status fails the step. On Windows, `fc.exe /b` takes the place of `cmp`, and that form has not been exercised.
- **Every part and value a row relies on is the schematic's.** Each reference designator a row names is a part in that netlist, and each part value a calculation or script uses is that part's value in it.
- **Every figure and input is where the row says it was read.** Open each source the row names, the constraints record as it stood in that commit or the named datasheet's table or graph, and find the value there.
- **Every result is reproduced.** Run each simulation input again, as step 3 does, with its log written to the work folder. It must exit with status 0 and print the measurement line **Result** quotes. Run each script again; it must print the result quoted.

Remove the checkout once this step and step 4 of the next section have been judged in it, with `git worktree remove <work folder>/before-placement`.

A row that was missing, empty or not met in that commit, or that fails a cross-check, fails this step, however complete it is now.

A later change to a listed circuit's parts or values, or to its figure at the source, reopens its row: export the netlist again, show the circuit again, and commit the record before the board is ordered. A circuit added to the schematic after placement is proven, and its row committed, before any of its parts is placed.

A board entering layout fails this step when, in the record as it stood before placement, a value-critical circuit is missing, or a listed circuit lacks a figure, a source of the kind step 2 allows, or a result that meets its figure under the conditions step 3 requires, or when the record had not been committed by then, or when it fails one of the cross-checks above. The remedy is a change to the circuit, shown again, or an amendment to the figure's source. Never the figure relaxed in this record, and never a shortfall judged unimportant.

Out of scope for this section: measuring the built circuit, which belongs to bring-up; coupling that depends on the layout itself, which a proof made before layout cannot show; and the figures for a particular machine, which come from its constraints record.

## Designing for bring-up and a second spin

Do this before any footprint is placed on the board, alongside the previous section. A first spin of a board is expected to need changes, and it must be diagnosable when it does. So every board carries what bring-up needs to find out what is wrong: a test point on every rail and on each key signal, a link that isolates every rail from its loads, and a way to limit the current first power can draw. These are parts in the schematic, each with its own footprint, left on the board. The pre-order check's schematic parity, which fails a layout that disagrees with its schematic, then fails a board from which one of them is missing.

### 1. Name every rail, every supply input and every key signal

A **rail** is a supply net: a net that something holds at a voltage to power other parts. That includes derived rails, made on the board from another, and reference rails, the voltages a converter or comparator measures against. Ground and return nets are not rails: they are the reference every rail is measured from, and carry no isolating link. A mains-referenced supply net is a rail like any other.

List the rails from the schematic itself, not from memory. Export its netlist in KiCad's own format, from the board's folder:

```
kicad-cli sch export netlist --output <board>.net <board>.kicad_sch
```

Each net in it is a `(net ...)` entry with its `(name ...)`, and a `(node ...)` for each part's pin on it, naming the part by `(ref ...)`, the pin by `(pin ...)` and the pin's electrical type by `(pintype ...)`. Ground and return nets aside, these nets are rails:

- every net a power symbol names, which the netlist gives the symbol's own name, such as `+12V`, with no sheet path before it; a global label's net is named the same way, so confirm in the schematic that a power symbol names it;
- every net with a node whose pintype is `power_out`, such as a regulator's output;
- every net with a node whose pintype is `power_in`, such as a part's supply pin;
- every net a supply input feeds before the board's first regulator or converter, such as the nets between an input connector and the regulator it supplies.

Leave out of them every **producer-only net**: a net whose only connections, its test point aside, are a pin or pins of the part producing it and the capacitors that part's datasheet requires on it, such as a controller's internal-regulator output brought out for its capacitor, or an internal reference brought out for its decoupling. It powers nothing outside its producer, so it is not a rail, even where a pin on it carries a `power_out` or `power_in` pintype.

Then look in the schematic for a rail none of these marks, such as a reference made by a divider, whose pins are passive. Every rail, and every producer-only net, is in a row of the record in step 4.

A **supply input** is any pin through which power can enter the board from any source, a supply, a cable, a programmer, a debugger or a USB host, whatever parts lie between it and the circuit it powers. Account for every pin of every connector, terminal or header, test points aside: in the same netlist each part is a `(comp ...)` entry under `(components ...)`, with its `(ref ...)` and every pin it has under `(pins ...)`, connected or not. Class each pin as one of:

- a **supply input**, by the rule above;
- **power-leaving**, a pin through which the board only supplies power to something off it, and through which nothing could power the board;
- **ground or return**, a pin on a ground or return net;
- a **signal**, any other pin.

A pin that might be a supply input is classed one. A supply-input or power-leaving pin's row says, in a few words, what it powers or what it feeds, so the class can be checked against the schematic.

A **key signal** is a signal bring-up must observe to tell whether a block of the board works. It includes each sensing front end's output, each drive stage's control input, the controller's reset, clock and programming interface, and any safety interlock's signal. The clock may be observed at a buffered clock output rather than at a pad on the crystal's nets, which would load the oscillator. Which signals of a particular board are key is that board's own design work; the test is whether, without probing the signal, bring-up could not tell whether its block works.

### 2. Give every rail and key signal a test point, and every rail an isolating link

A **test point** is a part in the schematic with its own reference designator, a pad or a test-point part, that a multimeter or oscilloscope probe can touch on the built board. It has a pin on the net it tests and no pin on any other net but a ground net.

An **isolating link** is a part fitted in series in a rail, between where the rail is produced and everything it feeds, that a builder can open and close again with hand or soldering tools: a removable jumper on a two-pin header, a zero-ohm resistor, a solder jumper, a wire link in through-hole pads, or a bridge of the board's own copper. It has exactly two pins, one on each side of it, and a resistor serving as a link has the value zero in the schematic.

A link on a path that carries a protective device's fault current (step 1 of the previous section) is a conductor there like any other, and has its conductor row in the circuit-proof record. A bought link, such as a zero-ohm resistor or a header and its jumper, takes that row's withstand from a rating its datasheet states for a time no shorter than the device's clearing time: a short-time or overload current, met when it is no less than the declared fault current, or an I²t, met when it is no less than the device's let-through. Where its datasheet states none, that position takes a copper link instead, whose withstand the relation in step 3 of the previous section shows: a wire link in through-hole pads, from the cross-section the wire's datasheet states, or a bridge of the board's own copper. A solder jumper reopened and closed again with solder counts as its copper only where its row shows the copper path the current takes; otherwise fit a wire link in its place. A link on a mains-referenced rail is also rated for the rail's voltage across it when it is open. A link rated for less does not count.

The link divides the rail into its source side and its load side, and is placed so that opening it separates the rail's source from all of its loads. The net on its source side carries only the part producing the rail, the parts of that part's own circuit that hold the rail, such as its output capacitor and feedback divider, the rail's test point and the link. A supply input's source side runs from the input's pin through its series protective parts, such as a fuse, to the link, and may be more than one net. Put the test point on the source side, so the rail can be measured with its loads disconnected; the link's load-side pad then reaches the loads, for example to measure their resistance to ground before power is applied.

A rail fed from more than one source, such as a regulator's output joined by a debug or USB connector's supply pin, or two inputs joined through diodes, is still one rail, with one load-side net. Each source has its own source side, its own link from that side to the shared load-side net, and its own test point. No link serves two rails or two sources.

A producer-only net (step 1) has a test point too, and no link: it powers nothing outside its producer, so there is nothing to isolate.

A test point or link on a mains-referenced net is mains copper. It goes in the `Mains` net class with every other mains-referenced net, as step 2 of the rules section requires, and is held to the board's separation basis like any other mains copper.

### 3. Give first power a means of current limiting

The first time a board is powered, a short or a part fitted wrongly must not be able to draw enough current to do damage. Every supply input (step 1) has its own **current-limit means**, the way the draw through that input on first power is limited, placed upstream of everything the input feeds: between the input's pin and the means there is nothing but the input's series protective parts, such as a fuse, and its test point. A means at one input does not limit another, and a means in a derived rail's link does not limit what the input feeds before it, so neither counts for that input.

The means is a series resistance, a lamp, or a current-limiting circuit on the board, and its first-power row states the current it lets the input draw on first power, with the arithmetic, for example the input's highest voltage over the series resistance, into a short. A part that only interrupts current, such as a fuse, a breaker or a resettable fuse, lets a short draw full current until it acts: it is protection, not the means, and never counts as it.

The means is carried on the board, for example a current-limiting stage at the supply input, or it needs only what a builder without a laboratory has: a multimeter, hand and soldering tools, and ordinary parts, such as a series resistor or a lamp fitted in place of the supply input's own isolating link. A means that needs other instruments, such as a bench supply with its own current limit, does not count. A link position that a resistor or lamp is fitted in must be able to take one: a two-pin header whose jumper is rated as step 2 requires, or a pair of through-hole pads that take the substitute's leads, and a wire link in service, held to the input's net class like the rest of its copper. A solder jumper or a surface-mount zero-ohm footprint cannot, and does not count.

### 4. Record the provisions, and commit them before placement

Keep a file named `bring-up-provision.md` in the board's own folder, beside its KiCad project. In it, keep a table with one row for every rail, every producer-only net and every key signal, and a first-power row for every supply input:

| Rail, producer-only net, key signal or first power | Net | Test point | Isolating link | What it is for |
|---|---|---|---|---|

- **Net** names every net the row covers. A rail names each source side, then its load side, for example `+5V, +5V_LOAD`, or `+3V3_REG, +3V3_DBG, +3V3` for a rail with two sources; it is still one row. A first-power row names the supply input's pin and its net.
- **Test point** and **Isolating link** name the parts by reference designator, one of each per source for a rail. Isolating link is `—` for a key signal and for a producer-only net. In a first-power row, Test point is `—`, and Isolating link names the link position the means is fitted in, or is `—` for a means carried on the board.
- **What it is for** says, for a rail, the part producing it and the parts of its own circuit on each source side, and any pin of it through which power leaves the board; for a producer-only net, the part producing it and the capacitors on it; for a key signal, the block whose working it shows; and, in a first-power row, the current-limit means and the series protective parts between the input's pin and it, by reference designator, and the current the means limits first power to, with its arithmetic.

Below it, keep a pin table with one row for every pin of every connector, terminal or header, test points aside, giving the pin as its part's reference designator and pin number, for example `J5.1`, its net, its class from step 1, and, for a supply input or a power-leaving pin, why:

| Pin | Net | Class | Why |
|---|---|---|---|

Commit the record before the first commit that places a footprint on the board. It is judged as it stood in the commit before placement, on the branch as pushed and in the checkout step 4 of the previous section makes, with `bring-up-provision.md` in place of `circuit-proof.md`. There, export the schematic's netlist in KiCad's own format, `kicad-cli sch export netlist --output <work folder>/check.net <board>.kicad_sch`, and cross-check the record against it and the schematic rather than taking its word:

- every rail step 1's listing finds is in the Net column of exactly one rail row, every producer-only net in exactly one producer-only row, and every key signal step 1 requires has a row: each sensing front end's output and each drive stage's control input that the circuit-proof record lists, the controller's reset, clock and programming interface, and each safety interlock's signal;
- each test point a row names is a part with a pin on the row's net, one on each source side for a rail, and no pin on any other net but a ground net;
- each isolating link a row names has exactly two pins, one on one of the row's source-side nets and one on its load-side net, is named in no other row, is rated as step 2 requires, by its datasheet or by the circuit-proof record's row for it, and, if it is a resistor, has the value zero;
- each producer-only net connects, in the netlist, only to a pin or pins of the part producing it, the capacitors that part's datasheet requires on it, and its test point;
- each source side of a rail carries only the parts step 2 allows there, each named in the row;
- every pin of every connector, terminal or header in the netlist, test points aside, is in the pin table exactly once, on the net the netlist gives it, and the table names no other pin;
- each pin's class is checked against the schematic by step 1's rule: a pin through which power could enter the board from any source is classed a supply input, a pin classed ground or return is on a ground or return net, and each Why says what the schematic shows the pin powering or feeding;
- each supply input has its own first-power row, whose means is a series resistance, a lamp or a current-limiting circuit, a part in the netlist or a link position step 3 allows, never a part that only interrupts current, whose limited current is stated with its arithmetic, from the netlist's values for a means in it, and the nets between the input's pin and the means carry only the parts step 3 allows there, each named in the row.

A rail, key signal, supply input or connector, terminal or header pin of the schematic as it stood then whose row was missing or empty in that commit, or that fails a cross-check, fails this step, however complete the row is now. A later change to the board's rails, key signals, supply inputs or connector, terminal or header pins is recorded, and cross-checked the same way, before the board is ordered.

A board on which any rail lacks a test point or an isolating link, any producer-only net or key signal lacks a test point, any supply input lacks a current-limit means upstream of everything it feeds, or the record fails a cross-check above, fails this step. The remedy is to add the missing part to the schematic, and its row to the record.

Out of scope for this section: carrying out bring-up on built boards, and choosing which signals of a particular board are key, which is that board's own design work.

## Rules before routing

Do this before any track is routed. Its purpose is that every rule the board is routed and checked against is written down, traceable to where its figure comes from, and that the table says which of them KiCad confirms on the board itself, which KiCad's rule check enforces before the board is ordered, and which, a net class's track width and via sizes, are only the defaults routing starts from.

Close the board in every editor before writing anything in this section, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, and keep it closed until step 4. An editor holding the board keeps its own copy of the project file and writes that copy over the file when it quits: a text variable and a net class pattern written to the project file while the board editor held the board open were measured to be gone after it quit. Konnect's tools that write net classes write the project file, so they are no exception.

### 1. Write every rule and net class down, with its figure and source

Keep a table in a file named `design-rules.md` in the board's own folder, beside its KiCad project. Give it one row for every design rule and every net class the board uses:

| Rule or net class | Figure | Where it is set in KiCad | Source of the figure | Confirmed in effect |
|---|---|---|---|---|

- **Design rules** are the board-wide minimums (clearance, track width, via diameter and drill, hole size, annular ring, hole-to-hole, copper-to-edge, silkscreen), each custom rule in the board's rules file, and every net class's own clearance, track width and via sizes.
- **Source** says where the figure comes from, for example: the machine's constraints record (name the figure in it); a requirement the board serves (name the requirement); the manufacturer's stated limits (name the manufacturer and the date of the capability page the figure was read from); the separation basis record; the circuit-proof record, for a width, a copper pour's connection width or a hole a circuit's proof assumed (name the circuit's row); or a finding from a layout review that became a rule (name the review). "Default", "typical" or "what KiCad had" is not a source.
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

    `hole_size` holds every hole on the class's nets, pad holes as well as vias. Each such rule has its own row, with its figure and source, confirmed by step 3 like any custom rule and enforced by the layout rule check in the pre-order check. A width or a via's hole that a conductor's withstand calculation in the circuit-proof record assumed is written this way, on a net class holding that conductor's nets, with the record's row as its source and a figure no smaller than the row assumed. A copper pour's narrowest neck is written the same way, as a `connection_width` constraint, which KiCad's layout rule check holds a zone's fill to; KiCad 10.0.7 was confirmed by step 3 to load a rule written `(constraint connection_width (min 1.5mm))`.

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
