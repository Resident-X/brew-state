# Board design method

This is how a controller board is designed in KiCad so that it passes the pre-order check and works once built. The method works for any machine. A machine's own figures come from its own records, and this document names each record only by the role it plays: the machine's constraints record, its separation basis record, the requirements a board serves, the board manufacturer's stated limits, and the datasheets of the parts on the board. A physical constant or a property of a material is stated in this document, with where it was published, wherever a step uses one, so no standard that must be bought is needed to carry a step out.

A board is designed by an agent, with no person at the editor, and each step can be carried out by an agent session from its own text. The pre-order check that later holds a board to the rules KiCad's layout rule check enforces, and how to run it, are described in [`hardware/README.md`](../hardware/README.md).

The sections after the tools, up to and including the layout review, are carried out in the order they appear. The first three, proving value-critical circuits, designing for bring-up and planning the layout, are finished and committed before any footprint is placed on the board; the rules and the routing follow, and the layout review judges the finished layout before the board is ordered. A board that fails any section's step is not ordered. The pre-order check does not read the records the first three sections keep, or the layout review's, so passing it does not stand in for them. The last two sections, [Layout review views](#layout-review-views) and [Layout practice catalogue](#layout-practice-catalogue), are not steps carried out in order: they are reference lists the steps use. The catalogue cites only documents any reader can obtain without charge.

## Tools

These are needed in addition to the tools the pre-order check needs (KiCad 10, Python, PyYAML, git and Task, listed in `hardware/README.md`). Every one is free.

| Tool | Version the commands below were exercised with | Where to get it |
|---|---|---|
| KiCad, with its command-line tool and the Python it bundles with its `pcbnew` module | KiCad 10.0.7 | https://www.kicad.org/download/ |
| Freerouting, the external router | Freerouting 2.5.0, the file `freerouting-2.5.0.jar` | https://github.com/freerouting/freerouting/releases (the v2.5.0 release, asset `freerouting-2.5.0.jar`) |
| A Java runtime, which Freerouting runs on | Eclipse Temurin OpenJDK 26.0.1 | https://adoptium.net/ or any other Java distribution. Freerouting 2.5.0 is built for Java 25, so it needs Java 25 or newer. |
| resvg, the SVG rasteriser that turns the [layout review views](#layout-review-views) into images | resvg 0.48.1 and resvg 0.47.0; the command refuses one older than 0.47 | A prebuilt program from https://github.com/linebender/resvg/releases: the v0.47.0 release carries one for each of Windows (`resvg-win64.zip`), macOS and Linux (x86_64), and later releases carry them for macOS and Linux only. Or `brew install resvg` with Homebrew, on macOS or Linux. Or `cargo install resvg` with a Rust toolchain from https://rustup.rs/, on any operating system. Set `RESVG=/path/to/resvg` when it is not on the search path. |
| A monospaced font for the captions of the layout review views: DejaVu Sans Mono, or Menlo, Consolas, Liberation Mono or Courier New, the captions being drawn in the first of these that resvg finds among the system's fonts | Menlo, as macOS carries it | macOS carries Menlo and Windows carries Consolas. Elsewhere, install DejaVu Sans Mono from https://dejavu-fonts.github.io/ or your system's package of it (for example `fonts-dejavu`). Without one the command stops with `CANNOT RUN`. |
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

Where a judgement is visual, the agent looks at a rendered view of the board, never at the editor window: Konnect's export toolset and `kicad-cli pcb export svg` both render the board's layers, and `task hw:views` renders every view the layout review judges a board on ([Layout review views](#layout-review-views)). What to look for is the [layout review](#layout-review) step's.

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

Remove the checkout once this step, step 4 of the next section and step 3 of [Planning the layout](#planning-the-layout) have been judged in it, with `git worktree remove <work folder>/before-placement`.

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

## Planning the layout

Do this before any footprint is placed on the board, once the schematic the two previous sections prove and provide for is finished. Its purpose is that the first layout is designed to the [Layout practice catalogue](#layout-practice-catalogue) rather than brought up to it by review: the board has a written floorplan, and a plan of how its layout meets every catalogue item that applies to it, before any part is placed. The rules section then writes every rule-kind item that applies into the board's rules before routing, and the [layout review](#layout-review) confirms a board drawn to this plan.

Keep the floorplan and the plan in a file named `layout-plan.md` in the board's own folder, beside its KiCad project.

### 1. Draw the floorplan

The floorplan divides the board into regions and places its connectors. Give it a region table with exactly these four rows:

| Region | Bounds | What it holds |
|---|---|---|

- **Region** is one of `mains`, `low voltage`, `analog sensing` and `digital`. The mains region holds every mains-referenced part and its copper; low voltage holds the low-voltage supplies, their regulators and the load drive stages; analog sensing holds every sensing front end, and any converter of its own part that the front ends feed; digital holds the controller and the logic it drives.
- **Bounds** gives the region's extent in board coordinates, in millimetres, as the rectangles `(x1, y1)–(x2, y2)` that make it up, corner to opposite corner. Board coordinates are those KiCad's board editor shows and the layout review views state in their captions. Regions do not overlap.
- **What it holds** names the blocks of the schematic placed in the region, for example `load drive stages, Q3–Q6, R20–R27`.

A board that carries no mains records its mains region as `none`: a board whose schematic carries no mains-referenced net, which the rules section therefore declares `MAINS` `none` (step 2 there), writes `none: the board carries no mains` in Bounds. A board whose schematic carries no circuit of one of the other three kinds writes `none` in Bounds with what the schematic lacks, for example `none: the schematic carries no sensing front end`.

Below it, keep a connector table with one row for every connector, terminal or header of the schematic, test points aside:

| Connector | Edge | Position |
|---|---|---|

- **Connector** is its reference designator.
- **Edge** is the board edge it sits at, `top`, `bottom`, `left` or `right` as seen from the board's front in board coordinates, or `none` for one that sits away from every edge, with the reason, such as a programming header reached only at bring-up.
- **Position** is the board coordinates, in millimetres, of the connector's pin 1.

### 2. Plan every catalogue item

Below the floorplan, keep a plan table with one row for every item of the [Layout practice catalogue](#layout-practice-catalogue), in the catalogue's order:

| Item | Applies | How the layout meets it, or why it does not apply |
|---|---|---|

- **Item** is the item's identifier, for example `GROUND-1`.
- **Applies** is `yes` or `no`, read from the item's *Applies when* against the schematic. An item whose condition the schematic meets is `yes`; it cannot be marked `no`.
- For an item that applies, the last column says how the layout will meet it, naming the regions of the floorplan, the parts by reference designator and the nets by name that it binds, closely enough that a failure the layout review finds against the item can be traced either to this row, as a plan the layout did not follow or a plan that was not enough, or to the item itself. For example, for `DECOUPLE-1`: `C12 and C13 at U4 pins 7 and 20, each within its own crop, C13 (100 nF) nearest pin 20, supply entering through each capacitor's pad; no via between capacitor and pin`. For a rule-kind item, it names the rules it puts in the board's rules table, with the board's own class names and the record each figure will be read from.
- For an item that does not apply, the last column gives the reason against the item's condition, stating what the schematic lacks, for example `no crystal or ceramic resonator in the schematic` for `CLOCK-1`.

Below the plan table, keep a table of the board's own items: practice this board must meet that no catalogue item states, such as a keep-out a part's datasheet asks for around it. Write each in the catalogue's item form ([How an item is read](#how-an-item-is-read)), one row per item, with how the layout will meet it:

| Item | Applies when | Asks | Passes | Fails, as the views show it | Judged on | Kind | Severity | Source | How the layout meets it |
|---|---|---|---|---|---|---|---|---|---|

- **Item** is `BOARD-<n>`, numbered from 1 in the order the items are written. Like a catalogue identifier, it is never renumbered and never reused.
- The columns from **Applies when** to **Source** are filled as the catalogue's fields are. Where the item comes from what this board must do rather than from published practice, its **Source** may name the requirement the board serves or the machine's record it comes from, by its role, in place of a published document. A rule-kind item's rules are carried into the board's rules table as a catalogue item's are ([Rules before routing](#rules-before-routing), step 1).
- **How the layout meets it** is written as a `yes` row of the plan table is, naming the regions, parts and nets it binds.

A board with no items of its own writes `none` in the Item column of the table's one row. The catalogue and these items together are the checklist the [layout review](#layout-review) judges the board against, and the table as committed before placement is that checklist's baseline. After that commit the table is only added to: no baseline row is removed, and none of its fields from Applies when to Source is changed. An item a review of the board adds later is appended below the others, its Source naming that review; it is judged from the review's next round on and is not part of the baseline. An item that is withdrawn keeps its row, marked withdrawn, as a catalogue item does.

### 3. Commit the floorplan and plan before placement

Commit `layout-plan.md` before the first commit that places a footprint on the board. It is judged as it stood in the commit before placement, on the branch as pushed and in the checkout step 4 of [Proving value-critical circuits before layout](#proving-value-critical-circuits-before-layout) makes, found the same way, with `layout-plan.md` in place of `circuit-proof.md`. There, export the schematic's netlist in KiCad's own format, `kicad-cli sch export netlist --output <work folder>/check.net <board>.kicad_sch`, and cross-check the plan against it, the schematic and the catalogue in the checkout's own copy of this document, `docs/board-design-method.md`, rather than taking its word:

- the region table has its four rows, each with bounds or a `none` the schematic bears out: the mains region is `none` exactly when the schematic carries no mains-referenced net, and no two regions' rectangles overlap;
- every connector, terminal or header in the netlist, test points aside, has exactly one row in the connector table, with an edge and a position, and the table names no other part;
- the plan table has exactly one row for every item of the catalogue as it stood in that commit, and names no other;
- each row marked `no` gives a reason against the item's *Applies when* that the schematic bears out, so no item whose condition the schematic meets is marked `no`;
- each row marked `yes` says how the layout meets the item, names at least one region, part or net it binds, and each region, part and net it names is one the floorplan or the netlist holds;
- the board's own items table is there, either with its one `none` row or with a row for each item, each identifier `BOARD-<n>` used once, every column filled as step 2 says, each *Applies when* one the schematic meets, and each How the layout meets it naming at least one region, part or net, each one the floorplan or the netlist holds.

A plan that is missing, incomplete or uncommitted in that checkout, or that fails a cross-check above, fails this step, however complete it is now. A part added to the schematic after placement is planned for, by amending the floorplan and every row whose item it bears on, and that change is committed before the part is placed.

A plan item the finished layout does not meet is a finding at the [layout review](#layout-review).

Out of scope for this section: the layout review itself, which [Layout review](#layout-review) describes, and producing the views it judges a board on, which [Layout review views](#layout-review-views) describes.

## Rules before routing

Do this before any track is routed. Its purpose is that every rule the board is routed and checked against is written down, traceable to where its figure comes from, and that the table says which of them KiCad confirms on the board itself, which KiCad's rule check enforces before the board is ordered, which the pre-order check measures itself, and which, a net class's track width and via sizes, are only the defaults routing starts from.

Close the board in every editor before writing anything in this section, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, and keep it closed until step 4. An editor holding the board keeps its own copy of the project file and writes that copy over the file when it quits: a text variable and a net class pattern written to the project file while the board editor held the board open were measured to be gone after it quit. Konnect's tools that write net classes write the project file, so they are no exception.

### 1. Write every rule and net class down, with its figure and source

Keep a table in a file named `design-rules.md` in the board's own folder, beside its KiCad project. Give it one row for every design rule and every net class the board uses:

| Rule or net class | Figure | Where it is set in KiCad | Source of the figure | Confirmed in effect |
|---|---|---|---|---|

- **Design rules** are the board-wide minimums (clearance, track width, via diameter and drill, hole size, annular ring, hole-to-hole, copper-to-edge, silkscreen), each custom rule in the board's rules file, every measured rule's figure, every check of KiCad's own that a rule-kind item names in place of a rule, and every net class's own clearance, track width and via sizes.
- **Source** says where the figure comes from, for example: the machine's constraints record (name the figure in it); a requirement the board serves (name the requirement); the manufacturer's stated limits (name the manufacturer and the date of the capability page the figure was read from); the separation basis record; the circuit-proof record, for a width, a copper pour's connection width or a hole a circuit's proof assumed (name the circuit's row); a rule-kind item of the [Layout practice catalogue](#layout-practice-catalogue) (name the item by its identifier, and, where the item names its figure by its role, also the record the board's figure was read from, as in `POWER-1; the machine's constraints record, the load supply's continuous current`); or a finding from a layout review that became a rule (name the review). "Default", "typical" or "what KiCad had" is not a source.
- **Carried rules.** Every rule-kind item of the catalogue that applies to the board, by its *Applies when* and as the plan in `layout-plan.md` records it, and every rule-kind item among the board's own items there, puts each rule it gives into this table, one row per rule, with the item as its source. Write each rule in the form the item gives it: a board-wide minimum, a net class's figure, a custom rule, KiCad's own check where the item names one in place of a rule, or a measured rule's figure. Where the item names a net class by its role, such as `<power class>`, write the board's own name for that class in its place; the `Mains` class is named as it is. Where the item names a figure by its role, read the figure from the record the role names. A board that has more than one class in a role carries the rule once for each. An applicable rule-kind item whose rules are missing from this table, or from the board, fails this step.
- **Where it is set in KiCad** names, for a measured rule, the project text variable that holds its figure, for example `WORK_DETOUR_RATIO`, written into the project file with the board closed as `MAINS` is (step 2). Write the figure as a plain decimal number, in the unit the item gives, with no unit after it: a missing figure, or one written any other way, fails the pre-order check, naming it. For KiCad's own check that an item names in place of a rule, it names that check, for example `KiCad's via_dangling check, reported unaided`.
- **Confirmed in effect** says, for each kind of row, what stands behind it, and nothing else may be written there:
  - a **custom rule** in the board's rules file: that KiCad loaded the rules file, from step 3's output. A rule's figure written with a unit KiCad does not take for its constraint, such as `deg` after a `track_angle` minimum, makes KiCad drop the whole rules file without a word, every rule in it with it; step 3 and the pre-order check both catch that, by a marker rule that fires only when KiCad loaded the file;
  - a **measured rule**: the pre-order check's `FIGURE` line for it, which states the figure the check read from the project file, quoted from the check's report;
  - **KiCad's own check**, named in place of a rule: `reported unaided by the layout rule check in the pre-order check`;
  - a **net class**: the nets step 3 lists for it;
  - a **board-wide minimum**, and a **net class's own clearance**, set in Board Setup: `not confirmed by step 3; enforced by the layout rule check in the pre-order check`. Step 3 cannot read these figures, so they are never marked confirmed. They stand on the figure and source written in the row. KiCad's layout rule check reports copper, holes and silkscreen that break any of them, as an error, or as a warning for silkscreen clipped by the board edge, and the pre-order check (step 7 of routing) fails the board on either;
  - a **net class's own track width and via sizes**: `routing default only; not enforced`. KiCad starts a track or via on the class's nets at these sizes, but its layout rule check does not hold copper to them: a narrower track or a smaller via on such a net raises no violation of the class's figure. The class's track width is also the width the measured rule of `WORK-8` holds every track of the class to away from its pads, which the row of that rule's figure records; it is not a minimum KiCad enforces. A track width or via size the board relies on, such as a mains or power track's width, is therefore also written as a custom rule in the board's rules file, conditioned on the class, one constraint per rule:

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

  The condition is written exactly as shown, with no other spacing. The rule has no `(layer ...)` clause and no other narrowing by layer or area. It holds both a `clearance` and a `creepage` constraint, each in millimetres. `<clearance>` and `<creepage>` are no less than the separation basis record's mains-to-low-voltage clearance and creepage (`mains_to_low_voltage.clearance_mm` and `.creepage_mm` in the `separation-basis.yaml` that holds the board to its signed figures). In the table from step 1, both figures name catalogue item `MAINS-1` and that record as their source; this rule is the one `MAINS-1` carries. The pre-order check accepts the rule in this form only, and holds the board to the record's figures whatever the rule states.

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

Out of scope for this section: the figures themselves, which come from the machine's constraints record and its separation basis record, the catalogue naming each such figure only by its role, and the automated check that later holds the board to the rules its layout rule check enforces, the pre-order check.

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

Out of scope for this step: judging the quality of the layout, which is the [layout review](#layout-review) that follows.

## Layout review

Do this once routing is finished and the pre-order check passes the board, and before the board is ordered. Its purpose is to confirm that the finished layout is the one the board was planned to have. The board was designed to the [Layout practice catalogue](#layout-practice-catalogue) when its layout was planned; the review is how that is shown, not how the board gets good. Every item of the checklist gets a recorded verdict, every finding stays open until something stated here closes it, every finding that can be written as a rule becomes one so later boards are checked for it without anyone remembering it, and a failure the plan should have prevented is corrected at the planning that let it through.

The **checklist** is every item of the catalogue together with the board's own items in `layout-plan.md` (step 2 of [Planning the layout](#planning-the-layout)). Its baseline is that file as committed before placement, which step 3 there judges.

The **reviewer** is an agent session, or a person, that did not design the board. It works from these alone: the board's design files, the checklist, the [layout review views](#layout-review-views) rendered from the board, the pre-order check's report, and the board's committed `layout-plan.md`. It never works from the designer's reasoning, session or notes.

Keep the review in one file named `layout-review.md` in the board's own folder, beside its KiCad project. It holds every round of the review, the first and every repeat, each under its own heading, `Round <n>`, numbered from 1, with its full set of verdicts, its findings and their closures. Commit the record at the end of each round, once its verdicts and findings are written and before any change to the board they call for, never part-way through a round, and again with every change that closes a finding. What a round recorded at its end, its opening lines, its verdict table and each finding's number, Raised by, Severity and What and where, is never changed afterwards; only Rule, Added as, Planning shortfall and Closed by are filled in later, as steps 5 to 7 complete them. So round 1 stays the board's first full review. A review is cited, wherever an item, a rule or a commit names it, by the record's path from the repository's root and the round, and a finding by its number as well, for example `<board folder>/layout-review.md, round 1, finding 1.3`.

### 1. Start a round: commit the board, render its views, run the pre-order check

Commit the board's design files as they are to be judged. With the board closed in every editor, render its views as [Layout review views](#layout-review-views) describes, naming every critical class, the classes step 3 of routing locked, and run the pre-order check, `task hw:verify`, as step 7 of routing does. Begin the round with:

- **Board judged**: the commit holding the design files the round judges;
- **Views**: the `task hw:views` command as it was run, and any further view rendered in the round (step 2), with the command that rendered it;
- **Pre-order check**: the board's `DESIGN` line from the report, and every `FIGURE` and `VIOLATION` line under it.

A round judges the board only as that commit holds it, and only on those views.

### 2. Judge every checklist item

Go through the checklist in order, the catalogue's items as the round's commit holds them and then the board's own items, and give every item one verdict in the round's verdict table:

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|

- **Item**, **Kind** and **Severity** are the item's identifier, kind and severity.
- **Verdict** is one of `pass`, `fail`, `not applicable` or `cannot judge`.
- **Rests on** cites each view the verdict rests on, by the name the views' index gives it, a tile's included, and the place on the board, in the board coordinates the view's caption states, or `whole board` for an item judged over all of it. Judge each item on every view its *Judged on* names.
- **Why**: for `not applicable`, the reason against the item's *Applies when*, stating what the schematic lacks, which the schematic must bear out: an item whose condition the schematic meets applies, and cannot be judged not applicable. For `fail`, the number of the finding it raises (step 4), or of the finding an earlier round raised against it and closed by a reason (step 7). For `cannot judge`, the view the item needs and why the views rendered do not show it.

A **rule-kind item**'s verdict rests on two things, and Rests on cites both: the pre-order check's report, the board's `DESIGN` line with no `VIOLATION` line under it of a rule the item gives, and for a measured rule its `FIGURE` line, giving the figure the check read; and the board's rules table, `design-rules.md`, by the row of every rule the item gives, each rule present there with a figure the item's own figure and source bear out, read from the record its role names where the item names its figure by its role. Both are needed because the check holds the board only to the figure its rules state, the figure in its rules file, its Board Setup or its project text variable: a figure looser than the item requires passes the check, and only the rules table, read against the item, shows it. Either one falling short is a `fail`.

A `cannot judge` verdict is resolved within the round, before the review can close: render the views again, or render the view the item needs that the views command does not make, for example with `kicad-cli pcb export svg`, and judge the item again on it. Write the verdict reached in the same row, after the `cannot judge` and the view rendered to resolve it.

A score or figure a tool reports while some of its inputs were not resolved, such as a placement score that could not match decoupling capacitors to their device, is unresolved, never a pass. No verdict rests on it: an item that would rest on it is `cannot judge` until it is judged on the views.

### 3. Compare the layout with the plan, then make a free pass

Read the layout against `layout-plan.md`: each region's bounds and what it holds, each connector's edge and position, each `yes` row of the plan table and each of the board's own items' How the layout meets it. A plan item the layout does not meet is a finding, even where the item it serves passes.

Then make a **free pass**: look over every view for anything else wrong with the board that no item and no plan row asks about, and record each thing seen as a finding.

### 4. Record every finding

Give every finding a row in the round's findings table, numbered `<round>.<n>`, so `1.1` is the first finding of round 1:

| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |
|---|---|---|---|---|---|---|---|

- **Raised by** is the item whose `fail` verdict raised it; `plan` with the plan row or the floorplan's row the layout departs from; or `free pass`.
- **Severity** is the item's, for a finding raised by an item or by its plan row. For a departure from the floorplan's region or connector table, and for a free-pass finding, it is one of the catalogue's four severities ([How an item is read](#how-an-item-is-read)), chosen by their definitions. A finding that bears on separation between mains and anything a person or a low-voltage circuit can reach, on fusing, on protective earthing or on insulation is of safety severity, whatever raised it.
- **What and where** says what is wrong, with the view and the board coordinates that show it.
- **Rule** and **Added as** are step 5's, **Planning shortfall** step 6's and **Closed by** step 7's.

### 5. Turn every finding that can be a rule into one

For every finding, write in Rule whether it can be expressed as a design rule. It can exactly when the pre-order check can enforce it through the board's rules, in one of the four forms step 1 of [Rules before routing](#rules-before-routing) uses: a board-wide minimum, a net class's figure or a custom rule, which KiCad's layout rule check enforces, or a measured rule, for a quality a measurement from the board's files can state that KiCad does not measure, which the pre-order check then measures. A finding a measurement can state is a rule in whichever of those forms can enforce it, preferring KiCad's own. Write `yes` with the rule and its form, or `no` with why none of the four forms can state it, so that it needs judgement on the views. A measured rule that is new is added to the pre-order check, with a seeded fault proving it, before the review closes. Then, before the review closes:

- A finding that can be a rule is added to the catalogue as a rule-kind item, with its rule, its figure and its source like any other rule-kind item, its Source naming the review it came from. From then on step 1 of the rules section carries it into the rules of every later board it applies to, and the pre-order check checks it, without anyone remembering it.
- A finding that needs judgement on the views is added to the catalogue as a judgement-kind item when it holds for any board, or to the board's own items in `layout-plan.md` when it holds for this board only, its Source naming the review.
- A finding that an item of the catalogue, or of the board's own, already states, in the same kind, needs no new item.

**Added as** names the item: the new item's identifier, or the item that already states it. A new catalogue item is written in the catalogue's item form, in the area it belongs to, and takes the next number that area has not used. A figure that depends on one machine is written in the item by its role, as the catalogue's other items write theirs, its number living in that machine's board rules, so the catalogue holds no machine's data.

### 6. Trace a first-review failure against a planned item to its planning cause

A finding of safety or function severity in round 1, raised by or through the plan row of an item the board's plan said it would meet, a catalogue item whose plan row is `yes` or one of the board's own items in the baseline, is also a planning shortfall. In Planning shortfall, name the catalogue item, or the step of this document's [Planning the layout](#planning-the-layout), that let it through, and amend that item or step in this document before the review closes, so that a later board planned the same way would not repeat it. An amended catalogue item names the review and the finding in its Source; an amended planning step carries, at the end of the step's text, a note naming them, written `Amended after <review>, finding <n>.`, for example `Amended after <board folder>/layout-review.md, round 1, finding 1.3.`, so a reader holding only a copy of this document can see where the step came from, and is amended in a commit whose message names them too. Planning shortfall gives the commit that made the amendment. Every other finding writes `—` there. The board itself is changed as for any other finding (step 7).

A shortfall recorded without an amendment, or an amendment that names no shortfall, fails this step.

### 7. Close every finding

A finding stays open until one of these closes it, written in Closed by:

- a change to the board, naming the commit that makes it, which the next round judges;
- a recorded reason showing that the item is in fact met, written `met:`; that it does not apply to this board, written `does not apply:`; or that it is overridden by a requirement the board serves or an item of the catalogue or of the board's own that the board must also meet, written `overridden by:` with that requirement or item named.

Never a judgement that the finding is unimportant.

A finding of safety severity closes only by a change to the board, or by a named person's acceptance of one of those reasons, and never by the agent that designed or reviewed the board. The acceptance is recorded beside the board, in the review record, in the same form as the signature on the board's separation basis record: after the reason, Closed by gives `accepted_by:` with the person's name and `accepted_on:` with the date they accepted it, written `YYYY-MM-DD`, and the record is committed with them. The name is a person's, never an agent session's, and never a placeholder such as `unsigned`, `tbd`, `todo`, `none`, `placeholder` or anything in angle brackets; the date is no later than the day of the commit that adds it. That commit is the acceptance's audit trail; no cryptographic signature is involved.

### 8. After any change, review the whole board again

After any change to the board, begin a new round at step 1: render the views again, pass the pre-order check again, and judge the whole checklist again, not only the items the change addressed, then compare the layout with the plan and make the free pass again. An item added to the checklist since the last round is judged in it.

The review **closes** on a round that judges the board's design files as they stand, in which the pre-order check passes the board, every item has a verdict and none is left `cannot judge`, every `fail` verdict raises a finding or cites one an earlier round closed by a reason, and every finding of every round is closed. A finding closed in that round by a change needs a further round. A board whose review has not closed is not ordered.

Before the first order of any board that carries mains, a review by an experienced electrical engineer is recommended, besides this one. It is not required.

Judge the record against the board and the repository rather than taking its word:

- **Every round judged the whole checklist.** Each round's verdict table has exactly one row for every item of the catalogue in the round's commit and every row of the board's own items table in that commit, and names no other. Every verdict is one of the four, and no `cannot judge` is left without a verdict after it.
- **Every view was rendered.** Render the views again from the round's commit with the round's command: its classes are the critical classes routing locked; the index holds a `layer-` view of every copper, mask, paste, silkscreen and edge layer the board carries and a `net-` view of every net the critical classes hold; and every view a verdict cites is in it, or is a further view the round names with its command.
- **Every verdict rests where it says.** Each `not applicable` gives a reason the schematic bears out. Each rule-kind verdict cites the report's line and the rules table's rows, and a `pass` has no `VIOLATION` line of a rule the item gives under the board's `DESIGN` line, a measured rule's `FIGURE` line giving the figure its row gives, and every rule the item gives in the table with a figure its source bears out.
- **Every finding was judged as a rule, and added.** Each finding has a Rule entry. Each `no` gives why none of the four forms can state the finding, and a `no` whose finding one of them can state, as step 1 of [Rules before routing](#rules-before-routing) defines them, fails, as a `not applicable` the schematic does not bear out does. One judged `yes` names in Added as a rule-kind item of the catalogue, as committed, that states it: a new one whose Source names the review, or one that already stated it. One judged `no` names a judgement-kind item of the catalogue or one of the board's own items that states it, new with its Source naming the review, or already there.
- **The baseline came first.** Every row of the board's own items table in the commit before placement is in each round's commit, with the same fields from Applies when to Source, so no baseline item is removed, narrowed, loosened or lowered after the layout began. Every row of the board's own items table that the commit before placement lacks names, in its Source, the review that added it. That commit is the one step 3 of [Planning the layout](#planning-the-layout) finds.
- **Each round stands as it was first recorded.** For each round, the first commit that `git log --reverse --format=%H -G '^#+ Round <n>$' -- <board folder>/layout-review.md` lists is that round's end-of-round commit. In it, the round's opening lines and verdict table are as the record now gives them, and so are its findings, none removed or added, each with the same number, Raised by, Severity and What and where. That commit comes before every commit after the round's Board judged commit that changes the board's design files: it is an ancestor of each, `git merge-base --is-ancestor <record commit> <change commit>` exiting with status 0, and is none of them. The planning shortfall check below therefore reads round 1 as it was first recorded.
- **Every severity is the one this step gives.** Each row of each verdict table gives the item's own kind and severity, as the round's commit holds the item. Each finding's Severity is the severity of the item that raised it, or of the item whose plan row it departs from, read from the catalogue or the board's own items table in the round's commit; for a departure from the floorplan's region or connector table, and for a free-pass finding, it is the severity the catalogue's definitions give what its What and where says is wrong. And whatever raised it, a finding whose What and where bears on separation between mains and anything a person or a low-voltage circuit can reach, on fusing, on protective earthing or on insulation has safety severity. The two checks below key on the severity a finding records, so a finding recorded below its severity fails here rather than closing by a reason with no acceptance or escaping its planning shortfall.
- **Every planning shortfall has its amendment.** Each finding of safety or function severity in round 1 raised against a catalogue item whose plan row was `yes`, or one of the board's own items in the baseline, names an item or a step and a commit. That commit changes this document at that item or step. An amended item's Source names the review and the finding; an amended step's text ends with the note step 6 gives naming them, and the commit's message names them too.
- **Every closure is one the method allows.** Each Closed by is a change naming a commit that changes the board's design files, or a reason of one of the three kinds. A safety finding's is a change, or a reason carrying an `accepted_by` and `accepted_on` as step 7 states.
- **The closing round judged the board as it stands.** None of the board's design files has changed since the closing round's commit: `git diff --quiet <commit> -- <file> ...`, naming the board's project, schematic and its sheets, layout and rules file, exits with status 0.

A review with an item left without a verdict, a `cannot judge` verdict unresolved, a view not rendered, or a baseline checklist committed after the layout began fails this step, and so does a record that fails a cross-check above. A baseline is committed after the layout began when step 3 of [Planning the layout](#planning-the-layout) fails it.

**This step is shown to find what it checks for** on `hardware/proof/review-proof`, a clean proof design carrying at least one part for every area of the [Layout practice catalogue](#layout-practice-catalogue), never ordered. `task hw:review-seed -- --seeds <file> --out <folder>` copies it outside the repository, places one or more known layout defects in the copy for every catalogue area, refuses the copy unless the pre-order check passes it, and writes a review folder holding only what this step gives a reviewer: the copy's design files with its floorplan, plan and rules records, this document, `hardware/README.md`, every view of the copy and the pre-order check's report on it. The seed list goes to `<file>`, apart from the folder. A session that did not design the board and has no record of the seeds then follows this step on the folder alone, started with the command's fixed prompt (`task hw:review-seed -- --print-prompt`), and its findings are compared with the seed list afterwards. Every seed must be reported as a finding against the catalogue item that covers it. A seed not reported is a gap in the catalogue, the views or this step and what it gives a reviewer, closed where it lies, and the blind review is repeated in a new session before this step is relied on. Repeat the proof after changing the catalogue, the views or this step. `hardware/README.md` describes the proof design and the command.

Out of scope for this section: the pre-order check itself, which [`hardware/README.md`](../hardware/README.md) describes; the content of the catalogue; producing the views, which [Layout review views](#layout-review-views) describes; the content of any particular board's findings; and who the electrical engineer is.

## Layout review views

An image of one layer shows no net names, so a ground drawn as a thin trace looks like any other track. The layout review therefore judges a board on an image of each layer (`layer-<layer>`) and on views that show each critical net against the board (`net-<net>`), the critical classes against each other (`classes`), each integrated circuit framed with its own decoupling parts (`crop-<reference>`), each side as it is assembled (`assembly-top`, `assembly-bottom`), and the assembled board in three dimensions (`3d-top`, `3d-bottom`, `3d-angled`). It also uses a table of the facts a picture cannot carry. With the board closed in every editor, render them from the board's folder:

```
task hw:views -- --board <board>.kicad_pcb --project <board>.kicad_pro --class <critical class> [--class <critical class> ...] --out <work folder>/<board>-views
```

Name every critical class, as in routing step 3. The output folder is a working folder: it must be new or empty, and outside every design's folder. Never commit it. The views, their names, the index and the per-net fact table, and what the command refuses, are listed in [`hardware/README.md`](../hardware/README.md#the-layout-review-views). The command needs KiCad's command-line tool, resvg and a monospaced font for the captions (see [Tools](#tools)).

**Resolution.** The views are drawn at

    pixels per millimetre = 3 / (the smaller of the board's minimum track width and minimum clearance, in millimetres)

so the smallest track and the smallest gap each span at least three pixels. Both minimums are read from the board's design rules, Board Setup's minimum track width and minimum clearance, whose figures and sources the board's rules table already carries (step 1 of [Rules before routing](#rules-before-routing)). The method itself therefore carries no manufacturer's figure. A board whose rules state either minimum as none, zero or less fails the command, naming the missing figure.

**Image size limit.** Every image is kept within a long edge of 1568 pixels, and within 1568 visual patches of 28 by 28 pixels. An image costs ⌈width / 28⌉ × ⌈height / 28⌉ patches. This is the standard tier of the model vendor's published limits, the tier for all models other than its high-resolution ones. An image over either limit is downscaled to the largest size that fits, keeping its aspect ratio, so an image within both is read at the resolution it was drawn at. The source is the "Resolution and token cost" section of https://platform.claude.com/docs/en/build-with-claude/vision, read on 2026-10-13. That section also gives a high-resolution tier, a long edge of 2576 pixels and 4784 patches, for the vendor's newer models. The views keep to the standard tier, so every reviewing model reads them whole. Every two-dimensional view larger than the limit, a crop included, is cut into tiles. Each three-dimensional view is one image within it.

**Captions.** Every image carries a caption drawn into it. A two-dimensional view's caption states its layers, the colour of each layer or, on the class map, of each class, its net or class, its scale in pixels per millimetre and the board coordinates in millimetres it covers. A three-dimensional view's caption states its view direction and image size. The index repeats every caption, as text and as JSON, so a reviewer working from the files alone has every fact without the author's context.

**Nothing left out quietly.** The views are drawn from a temporary copy that reads as the design does in place: it keeps the design's own file names, and every model path the design's folder anchors is written out in full. Every two-dimensional view, and every tile of one, is composed in one place, which alone frames it, puts it on the dark background, draws its rule areas, names the layers it lacks and the fonts KiCad substituted, and writes its caption fields. So these hold for every two-dimensional view alike:

- A whole-board view frames everything KiCad draws on the board's plotted layers, united with the outline and the rule areas, with a millimetre to spare, so a part or a text reaching past the outline is drawn whole rather than cut off. A crop is framed on, and names, only its own circuit and that circuit's decoupling parts, and it shows only what lies within the board coordinates its caption states. A crop is at least 640 pixels wide, so a crop of a small circuit is widened about its centre and can take in a neighbouring circuit's parts: everything within its coordinates is drawn, and another circuit's parts that fall there are drawn but not named, so a part that neither the crop's caption nor the index names as that circuit's decoupling is not its decoupling. A decoupling part is a two-pad part, not itself an integrated circuit, with its two pads on two different nets that are both a circuit's supply nets. It belongs to the one circuit sharing those nets whose nearest pad is closest to it, so a crop never names another circuit's decoupling on a shared rail as its own. A circuit to which none belongs is marked in its caption and the index as having no decoupling parts.
- KiCad does not plot a rule area, so the command draws each one as a dashed, hatched outline on every two-dimensional view that shows one of its layers, the faint board beneath a net overlay or the class map included, wherever the view's region reaches the area, and that view's caption names it. The three-dimensional views do not draw rule areas.
- A fabrication or courtyard layer the board does not carry is named as not carried in the caption of every view that would show it. The board must carry every other layer a view shows.
- A font KiCad cannot find, whose text it draws in another, is named in every caption, the three-dimensional views' included.

The three-dimensional views say what they leave out in their own captions and in the index:

- A part drawn without a model is named: one whose model KiCad cannot find, one declaring no model, one whose model the design hides, and one marked do not populate. Which parts KiCad drew a model for is judged from KiCad's three-dimensional export of the same copy (`kicad-cli pcb export glb`), not from the rendered images, so a model the renderer loads but the export does not would be named as not found although it is drawn.
- A three-dimensional view is zoomed out until no part reaches its frame, and its caption states the zoom.

The command reports each part the three-dimensional views draw without its model, whatever the reason, a font KiCad substitutes and a layer the board does not carry as lines of their own as well. A board with any of them still gets its views: whether what they leave out matters is the review's judgement.

Out of scope for this section: judging the images, which is the [layout review](#layout-review) step.

## Layout practice catalogue

This is the one statement of what a well laid-out board looks like. It is used three times on every board: the board is planned against it before placement ([Planning the layout](#planning-the-layout)), every rule-kind item that applies to it is written into its rules before routing ([Rules before routing](#rules-before-routing), step 1), and the [layout review](#layout-review) uses it as the baseline checklist a finished layout is judged item by item against, adding to it every finding that can be written as a rule or that holds for any board. It holds no figure, part or board shape of any one machine. A figure that depends on the machine is named here by its role, such as the highest continuous current a class carries, and its number lives in that machine's records and its board's rules.

### How an item is read

Every item carries the same fields:

- **Identifier**, its area and a number, such as `GROUND-1`. An identifier is never renumbered and never reused: a plan, a rule and a review cite items by it. A new item takes the next number its area has not used, and an item withdrawn keeps its identifier, marked withdrawn, so a citation of it still finds it.
- **Applies when** states, in terms of what the board's schematic carries, the condition under which the item applies to a board. An item whose condition the schematic meets applies; it cannot be marked as not applying.
- **Asks** is the question the item asks of a board.
- **Passes** is the pattern that passes.
- **Fails, as the views show it** is what a failing board looks like in the [layout review views](#layout-review-views).
- **Judged on** names the views it is judged on: an image of one layer, `layer-<layer>`, such as `layer-F.Cu`; a critical net against the board, `net-<net>`; the critical classes against each other, `classes`; an integrated circuit with its decoupling, `crop-<reference>`; a side as assembled, `assembly-top` or `assembly-bottom`; the assembled board in three dimensions, `3d-top`, `3d-bottom` or `3d-angled`; or the fact table, `facts.txt`, which gives every net's track width range, via count, zones and classes. A rule-kind item is judged on the pre-order check's report and on the board's rules table, `design-rules.md`: the check holds the board to whatever figure its rules state, so a figure smaller than the item's source requires passes the check, and only the rules table, its figure read against the item, shows it. Its *Fails* names what such an undersized figure looks like in that table.
- **Kind** is one of two. A **rule-kind** item is enforced by the automated pre-order check, through the board's rules: it gives its rule in one of the four forms the rules step uses, with its figure and source. Three of them KiCad's own layout rule check enforces: a board-wide minimum, a net class's figure, and a custom rule in the board's rules file (an item whose quality KiCad reports unaided, such as a via left unconnected, gives no rule and names KiCad's check). The fourth is a **measured rule**, a quality KiCad does not measure, such as how much longer a route is than its pads' places need: the pre-order check measures it itself from the board's files, against a figure the board sets as a project text variable, and the check's report states the figure it read. A net class it names by its role, such as `<power class>`, is replaced by the board's own name for that class; only the `Mains` class is named literally, since its name is fixed. A **judgement-kind** item is judged on the rendered views. A practice only partly expressible as a rule is two items, one of each kind, so every item has a single kind.
- **Severity** is one of four:
  - **safety**: the item bears on separation between mains and anything a person or a low-voltage circuit can reach, on fusing, on protective earthing, or on insulation;
  - **function**: a board failing it may not do its job, or may not meet a figure it is held to, such as a sensing accuracy;
  - **quality**: a board failing it works, but with less margin, reliability or ease of manufacture or bring-up than it should have;
  - **cosmetic**: a board failing it works as well, and only its appearance or legibility suffers.
- **Source** is a published document any reader can obtain without charge, such as a part or tool manufacturer's application note, design guide or datasheet, cited by its title, publisher, section, address and the date it was read, and checked against the document itself, never cited from memory. A standard that must be bought, or a book that could not be opened and read, is not a source. An item added from a layout review names that review, beside its published source where it has one and in place of one where it has none. Each item is stated fully enough to apply without reading its source.

The areas, in order: [floorplan and partitioning](#floorplan-and-partitioning-floor), [power paths and heat](#power-paths-and-heat-power), [grounding and return paths](#grounding-and-return-paths-ground), [decoupling and switching loops](#decoupling-and-switching-loops-decouple), [sensing front ends](#sensing-front-ends-sense), [clocks](#clocks-clock), [separation of mains from low voltage](#separation-of-mains-from-low-voltage-mains), [connectors and mechanical fit](#connectors-and-mechanical-fit-conn), [test access and bring-up](#test-access-and-bring-up-test), [manufacture and assembly](#manufacture-and-assembly-mfg), [emissions](#emissions-emi) and [workmanship](#workmanship-work).

### Floorplan and partitioning (FLOOR)

#### FLOOR-1. Parts are grouped by function into their floorplan regions

- **Applies when:** always.
- **Asks:** Does every part sit in the region of the floorplan that holds its function, with like functions together rather than mixed?
- **Passes:** Each part lies within the bounds `layout-plan.md` gives the region holding its block: mains, low voltage, analog sensing or digital. Fast logic, the controller among it, sits close to the low-voltage supply that feeds it; analog sensing sits farthest from fast logic and from switching stages.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, read against the board coordinates in the caption, a sensing front end's parts scattered among the controller's or a switching stage's parts, or any part outside its region's bounds.
- **Judged on:** `assembly-top`, `assembly-bottom`, `classes`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning*, https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### FLOOR-2. Analog and digital signals stay in their own regions on every layer

- **Applies when:** the schematic carries a sensing front end feeding a converter, on its own part or inside the controller.
- **Asks:** Is every analog signal routed only within the analog sensing region, and every digital signal only within the digital region, on every copper layer?
- **Passes:** No digital track crosses the analog sensing region, and no analog track crosses the digital region, on any layer. The two meet only at the converter, where the analog signal enters it.
- **Fails, as the views show it:** on a `layer-<copper layer>` view, a digital track, such as a communication line or a drive output, running through the analog sensing region's bounds, or a sensing net on `net-<net>` running across the digital region.
- **Judged on:** every `layer-<copper layer>`, `net-<net>` for each sensing net, `classes`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Grounding in mixed-signal systems demystified, Part 2*, Analog Applications Journal 2Q 2013, SLYT512, the opening passage on split and partitioned planes ("Analog signals must be routed only in the board's analog section, and digital signals must be routed only in the board's digital section, with both on all layers", Figures 4 and 5), https://www.ti.com/lit/pdf/slyt512, read 2026-10-14; and Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("Avoid crossing digital lines with the analog signal path"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14.

#### FLOOR-3. Supply entry, regulator and controller sit together, and the analog supply is taken from them

- **Applies when:** the schematic carries a supply input feeding a regulator that powers a controller.
- **Asks:** Do the supply input, the regulator it feeds and the controller sit next to one another, joined by a wide ground, with any analog supply filtered or regulated from the digital one rather than taken from the far side of the board?
- **Passes:** The supply input's connector, the regulator and the controller are adjacent, with a solid or gridded ground spanning all three. Power reaches the digital circuits first and is filtered or regulated before it feeds the analog sensing region.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, the regulator far from the supply input or from the controller, so that the supply crosses the board; on a ground `net-<net>`, the three joined only by thin tracks; on `classes`, the analog supply's copper running direct from the supply input past the digital region.
- **Judged on:** `assembly-top`, `assembly-bottom`, `net-<net>` for the ground and supply nets, `classes`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning* ("Locate the microcomputer next to the voltage regulator, and the voltage regulator next to where VBatt enters the board"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Grounding in mixed-signal systems demystified, Part 2*, Analog Applications Journal 2Q 2013, SLYT512, section *Grounding when multiple data converters are used on a single board* ("The power should enter the board in the digital partition and be fed directly to the digital circuitry, then filtered or regulated to feed the analog circuitry"), https://www.ti.com/lit/pdf/slyt512, read 2026-10-14.

### Power paths and heat (POWER)

#### POWER-1. Every class carrying supply or load current has a minimum track width for its current

- **Applies when:** the schematic carries a supply input or a part that switches a load, which puts nets carrying their current in a power class (step 1 of routing). The `Mains` class is such a class where its nets carry a load's current.
- **Asks:** Is every track on a class carrying supply or load current at least 0.381 mm wide for each ampere of the highest continuous current any net of that class carries?
- **Passes:** The board's rules hold, for each such class, this custom rule, and the pre-order check reports no `track_width` violation:

  ```
  (rule "<power class> track width"
  	(condition "A.hasNetclass('<power class>')")
  	(constraint track_width (min <width>mm)))
  ```

  `<width>` is 0.381 mm times the highest continuous current, in amperes, that any net of the class carries, read from the machine's constraints record or a requirement the board serves. The source gives 0.381 mm (15 mils) per ampere as the absolute minimum for a standard board. Where the circuit-proof record also holds a track width on the class, write one rule with the larger of the two figures and name both sources in its row: KiCad applies only the last of two rules whose conditions match the same track (KiCad, *PCB Editor* manual, version 10.0, *Custom rule syntax*).
- **Fails, as the views show it:** the pre-order check reports a `track_width` violation on a track of the class; or, in `design-rules.md`, a class the plan says the item applies to has no row for this rule, or the row's figure is less than 0.381 mm times the highest continuous current the record it names gives for the class's nets, or the row names no record the current was read from.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 5 *Traces and Ground Plane* ("make the traces an absolute minimum of 15 mils (0.381mm) per Ampere"), https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### POWER-2. Power paths are short, direct and wide, with their parts close together

- **Applies when:** the schematic carries a supply input or a part that switches a load.
- **Asks:** Is every path carrying supply or load current as short, direct and wide as the board allows, between parts placed close together?
- **Passes:** Each power net runs the shortest practical way between the parts it joins, at a width well above the minimum `POWER-1` sets wherever there is room, with no detour and no neck narrower than the rest of the path. The parts a high current flows through in turn sit next to one another.
- **Fails, as the views show it:** on `net-<net>` for a power net, a track wandering around the board, or a wide track narrowing to a thin one partway along; in `facts.txt`, a power net whose track width range reaches down to the board's minimum.
- **Judged on:** `net-<net>` for each power-class net, `facts.txt`, `classes`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 5 *Traces and Ground Plane* ("Make all of the power (high current) traces as short, direct, and thick as possible"), https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### POWER-3. A current that changes layer passes through one via for every 200 mA

- **Applies when:** the schematic carries a supply input or a part that switches a load.
- **Asks:** Where a path carrying supply or load current changes copper layer, does it pass through at least one via of the board's standard size for every 200 mA of the current it carries?
- **Passes:** At each place a power path changes layer, the vias sharing its current number at least the path's continuous current divided by 200 mA, rounded up, each of the board's standard via size, the via size its rules give as the board's default. A board of one copper layer, or one whose power paths never change layer, meets it with no such via; its plan row says which, and for a path that will change layer, the number of vias its current needs.
- **Fails, as the views show it:** on `net-<net>` for a power net, a single via carrying the whole of a path's current from one layer to another; in `facts.txt`, a power net whose via count is lower than its layer changes need.
- **Judged on:** `net-<net>` for each power-class net, `facts.txt`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 5 *Traces and Ground Plane* ("use one standard via per 200 mA of current if the trace will need to conduct a significant amount of current from one plane to the other"), https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### POWER-4. An exposed thermal pad is soldered to a thermal land with solidly connected vias

- **Applies when:** the schematic carries a part whose package has an exposed pad on its underside meant to carry heat into the board, as its datasheet states.
- **Asks:** Does each such part sit on a copper thermal land it is soldered to, sized from its datasheet, with thermal vias carrying heat into an inner plane or the far side, each joined to that copper all the way round rather than through relief spokes?
- **Passes:** A copper land under the exposed pad, its solderable area defined by the solder mask to the datasheet's maximum exposed-pad size, with as much copper beyond it as heat needs. On a board of more than one layer, thermal vias in the land join it to a plane, each connected with a continuous ring of copper on every layer it joins, never by relief spokes.
- **Fails, as the views show it:** on `crop-<reference>` or `layer-F.Cu`, an exposed pad with no land or a land no bigger than the pad and no copper beyond; on a plane's `layer-<copper layer>`, the thermal vias joined to the plane by spokes, seen as a ring of gaps round each via.
- **Judged on:** `crop-<reference>`, `layer-<copper layer>` for each layer the vias join, `layer-F.Mask` or `layer-B.Mask`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PowerPAD Thermally Enhanced Package*, SLMA002H, revised July 2018, § 2.3 *Thermal Lands* and § 2.4 *Thermal Vias* ("it is recommended that all vias used under the package make internal connections to the planes using a continuous connection completely around the hole diameter"), https://www.ti.com/lit/pdf/slma002, read 2026-10-14.

#### POWER-5. A leaded switching part that sheds heat through its leads has copper area on them

- **Applies when:** the schematic carries a part that switches a load, such as a phototriac, a triac or a transistor, whose datasheet states that its heat leaves mainly through its leads or pads into the board.
- **Asks:** Do that part's pads carry as much copper area, on both sides of the board, as there is room for, while keeping the separation its input and output sides need?
- **Passes:** The part's load-side pads are joined to copper areas on both outer layers, as large as the space allows, with thermal vias between them where the layer count allows. Every pin the datasheet says is soldered is soldered, none left open or socketed. The copper stops short of the separation its isolated sides need, which `MAINS-1` holds where those sides are mains and low voltage.
- **Fails, as the views show it:** on `layer-F.Cu` and `layer-B.Cu`, the part's load-side pads joined by bare tracks with no copper area round them.
- **Judged on:** `layer-F.Cu`, `layer-B.Cu`, `assembly-top` or `assembly-bottom`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Vishay Semiconductors, *VO3526 Power Phototriac Design Considerations*, Application Note 33, document 81937, Rev. 1.1, 19 October 2011, section *PCB Design Considerations* ("The size of the pads and copper area on both top and bottom sides should be as big as possible while keeping a minimum safe distance between input and output pins"), https://www.vishay.com/docs/81937/appnote.pdf, read 2026-10-14.

### Grounding and return paths (GROUND)

The ground and return-path items, `GROUND-1` to `GROUND-4` and `EMI-1`, bind the board's low-voltage copper only: the ground they ask for, and the signal and supply tracks they hold over it, stop at the mains region's bounds, which `MAINS-2` keeps clear of low-voltage copper.

#### GROUND-1. Ground is a plane, not a set of tracks

- **Applies when:** always.
- **Asks:** Is the board's ground a continuous plane, or on a board whose layers cannot give it one, a grid of copper joined at both ends of every run, rather than tracks?
- **Passes:** The ground net is a copper zone covering as much of at least one layer as the other copper leaves free, unbroken across the regions it serves. On a two-layer board, the remaining space on both layers is filled with ground and the fills are joined to each other through as many vias as fit, every fill joined at two or more points rather than left as a dead end.
- **Fails, as the views show it:** on `net-<net>` for a ground net, ground drawn as thin tracks threading between parts; a ground zone broken into islands joined only by narrow tracks; in `facts.txt`, a ground net with no zone.
- **Judged on:** `net-<net>` for each ground net, every `layer-<copper layer>`, `facts.txt`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.1.2 *Two-Layer vs Four-Layer Boards* and § 2.2.3 *Gridding to Create Planes* ("A ground-fill-pattern geometry connected at only one point is just a ground shield, but if connected at two or more points, it becomes a conductor"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Grounding in mixed-signal systems demystified, Part 1*, Analog Applications Journal 1Q 2013, SLYT499, section *Analog or digital ground plane, or both?*, https://www.ti.com/lit/pdf/slyt499, read 2026-10-14.

#### GROUND-2. No track runs over a gap in the plane beneath it

- **Applies when:** always.
- **Asks:** Does every signal track have unbroken ground copper under it along its whole length, so its return current can flow directly beneath it?
- **Passes:** Under every track, on the adjacent layer, the ground plane is solid. Nothing cuts the plane under a track: no track buried in the ground layer, no slot, and no row of via or hole clearances merging into a slot; where a row of through-hole pins crosses the plane, copper runs between the pins.
- **Fails, as the views show it:** on a plane's `layer-<copper layer>` read against `net-<net>` for a signal, a track crossing a cut, a slot or a merged row of clearances in the plane beneath it, or a track routed on the ground layer itself dividing the plane in two.
- **Judged on:** every `layer-<copper layer>` holding ground, `net-<net>` for each critical signal net.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.1.4 *Signal Return Grounds* and § 2.1.7 *Power Plane Do's and Don'ts for Four-Layer Boards* (Figure 5), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.5 *Reference Planes* and § 4.6 *Routing*, item 4, https://www.ti.com/lit/pdf/slla284, read 2026-10-14.

#### GROUND-3. One ground plane is partitioned, not split

- **Applies when:** the schematic carries a sensing front end feeding a converter, alongside digital logic.
- **Asks:** Is the ground one plane, partitioned by where parts and tracks sit, rather than split into separate analog and digital planes; and where the board does carry a split, does every track crossing it cross at a single bridge joining the two?
- **Passes:** One ground plane under both the analog sensing and the digital regions, with the regions kept apart by placement and routing (`FLOOR-2`). Where a design reason forces separate planes, they are joined at one place, and every track passing between them crosses at that bridge, over copper.
- **Fails, as the views show it:** on a ground `layer-<copper layer>` or `net-<net>`, a gap separating an analog ground area from a digital one with a track crossing the gap away from any bridge, or two planes joined only at the supply input.
- **Judged on:** every `layer-<copper layer>` holding ground, `net-<net>` for each ground net and each net crossing between regions.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Grounding in mixed-signal systems demystified, Part 2*, Analog Applications Journal 2Q 2013, SLYT512, the opening passage and Figures 1 to 5 ("It is always preferable to use only one ground plane, partitioning the PCB into analog and digital sections"; "the planes should first be connected at one location to form a bridge for the return current"), https://www.ti.com/lit/pdf/slyt512, read 2026-10-14.

#### GROUND-4. A part's analog and digital ground pins join the same plane at the part

- **Applies when:** the schematic carries a part with separate analog and digital ground pins, such as a converter.
- **Asks:** Are that part's analog and digital ground pins joined, at the part, to the same low-impedance ground plane by the shortest connections?
- **Passes:** Each ground pin goes straight to the plane under the part by the shortest connection, the analog and digital ground pins to the same plane.
- **Fails, as the views show it:** on `crop-<reference>`, the digital ground pin routed away by a track to a distant ground, or the two ground pins joined to different copper areas.
- **Judged on:** `crop-<reference>`, `net-<net>` for the ground nets.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Grounding in mixed-signal systems demystified, Part 1*, Analog Applications Journal 1Q 2013, SLYT499, the section on interpreting AGND and DGND pins ("the AGND and DGND pins should be joined together externally to the same low-impedance ground plane with minimum lead lengths"), https://www.ti.com/lit/pdf/slyt499, read 2026-10-14.

### Decoupling and switching loops (DECOUPLE)

#### DECOUPLE-1. Each decoupling capacitor sits at its supply pin, with nothing between them

- **Applies when:** the schematic carries an integrated circuit with a decoupling capacitor on a supply pin.
- **Asks:** Is each decoupling capacitor next to the supply pin it decouples, the smallest nearest, with the supply reaching the pin through the capacitor's pad and no via between capacitor and pin?
- **Passes:** Each capacitor sits beside its pin, joined to it by a short, wide track. Where a pin has more than one, the smallest value is closest. The supply arrives at the capacitor first and then goes on to the pin; any via to the supply plane is on the far side of the capacitor from the pin.
- **Fails, as the views show it:** on `crop-<reference>`, a decoupling capacitor across the part or on the far side of the board from its pin, a via between capacitor and pin, or a supply track reaching the pin before the capacitor; a crop captioned as having no decoupling parts for a part whose schematic gives it some.
- **Judged on:** `crop-<reference>` for each integrated circuit.
- **Kind:** judgement. **Severity:** function.
- **Source:** Tim Claycomb, *The basics: How to layout a PCB for an op amp*, Texas Instruments, Precision Hub blog, 8 January 2016, closing list of layout practices ("Place decoupling capacitors as close to the supply pins as possible"; "If using multiple decoupling capacitors, place the smallest decoupling capacitor closest to the supply pin"; "Do not place vias between decoupling capacitors and supply pins"), https://e2e.ti.com/blogs_/archives/b/precisionhub/posts/the-basics-how-to-layout-a-pcb-for-an-op-amp, read 2026-10-14; and Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("Avoid placing vias between the supply pin and its decoupling capacitor"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14.

#### DECOUPLE-2. The decoupling loop is small, its ground side straight into the plane

- **Applies when:** the schematic carries an integrated circuit with a decoupling capacitor on a supply pin.
- **Asks:** Is the loop from the supply pin through the capacitor and back to the part's ground pin as small in area and length as it can be, with the capacitor's ground side going straight into the ground plane?
- **Passes:** The capacitor's ground pad joins the plane at once, through two vias where it changes layer, or through ground copper extended from under the part rather than a track. The supply and ground sides run over or beside each other, so the loop encloses little area seen from above.
- **Fails, as the views show it:** on `crop-<reference>`, the capacitor's ground pad reaching ground by a long track, or the loop through capacitor and part enclosing a wide area.
- **Judged on:** `crop-<reference>`, `net-<net>` for the ground net.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.2.4 *Bypassing and Ferrite Beads* ("Make the bypassing loops as small as possible in area and length"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.6 *Routing*, item 10 (the capacitor's ground side "through two vias to the ground plane"), https://www.ti.com/lit/pdf/slla284, read 2026-10-14.

#### DECOUPLE-3. A switching converter's power parts form tight loops that curl the same way

- **Applies when:** the schematic carries a switching converter, a circuit that switches current through an inductor or a transformer.
- **Asks:** Are the converter's input capacitor at its input pin, its inductor, output capacitors and switch or diode close together, their grounds joined close together straight into the ground plane, and placed so that the current loop in each switching state turns the same way?
- **Passes:** The input capacitor sits at the converter's input pin. The inductor, the output capacitors and the diode, where there is one, sit together, so the loops the switching current takes in its on and off states are small. The grounds of the converter, its input capacitors, its output capacitors and its diode join close together, directly to a ground plane. The loop in the on state and the loop in the off state run in the same direction round the parts.
- **Fails, as the views show it:** on `crop-<reference>` of the converter and on `layer-<copper layer>`, the input capacitor away from the input pin, the inductor separated from the output capacitors by other parts, or the converter's ground and the capacitors' grounds joined only by long tracks.
- **Judged on:** `crop-<reference>` of the converter, every `layer-<copper layer>`, `assembly-top` or `assembly-bottom`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 3 *Filter Capacitors* and § 5 *Traces and Ground Plane* ("Arrange the components so that the switching current loops curl in the same direction"), https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### DECOUPLE-4. A switching converter's feedback is kept away from its inductor

- **Applies when:** the schematic carries a switching converter with a feedback connection, or with external feedback or compensation parts.
- **Asks:** Does the feedback trace run as far from the inductor and the noisy power traces as the board allows, with its feedback and compensation parts close to the converter and away from the inductor?
- **Passes:** The feedback trace runs direct to the feedback pin, away from the inductor, on the side of the board opposite the inductor with a ground plane between them where the layers allow. The feedback and compensation parts sit at the converter's pins, not beside the inductor.
- **Fails, as the views show it:** on `layer-<copper layer>` and `crop-<reference>`, the feedback trace passing under or beside the inductor, or the compensation parts placed next to it.
- **Judged on:** `crop-<reference>` of the converter, every `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 2 *Feedback* and § 4 *Compensation*, https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### DECOUPLE-5. A snubber sits at the switch it protects

- **Applies when:** the schematic carries a snubber, a resistor and capacitor in series across a switching part such as a triac or phototriac.
- **Asks:** Is the snubber placed as close to the switching part as it can be?
- **Passes:** The snubber's resistor and capacitor sit beside the switch, joined to its terminals by short connections.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, the snubber's parts placed away from the switch, reached by long tracks.
- **Judged on:** `assembly-top`, `assembly-bottom`, `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Vishay Semiconductors, *VO3526 Power Phototriac Design Considerations*, Application Note 33, document 81937, Rev. 1.1, 19 October 2011, section *Snubber Circuit* and Figure 5 ("Locate the snubber circuit as close to the VO3526 as possible"), https://www.vishay.com/docs/81937/appnote.pdf, read 2026-10-14.

### Sensing front ends (SENSE)

#### SENSE-1. A current-sense resistor is read through Kelvin connections

- **Applies when:** the schematic carries a resistor used to measure current, a shunt whose voltage an amplifier or a converter reads.
- **Asks:** Are the amplifier's inputs joined to the shunt's own pads by their own tracks, separate from the tracks carrying the load current, and for a low-side shunt, does the amplifier's gain resistor return to ground at the shunt's ground pad?
- **Passes:** Two sense tracks leave the shunt at its own pads and run to the amplifier, separate from the tracks carrying the load current, so no load current flows in them. For a low-side shunt, the gain-setting resistor's ground end is placed as close as it can be to the shunt's ground connection.
- **Fails, as the views show it:** on `net-<net>` for the sense nets, a sense track leaving the load-current track partway along rather than at the shunt's pad, or the gain resistor's ground joining the plane far from the shunt.
- **Judged on:** `net-<net>` for the shunt's nets, `layer-<copper layer>`, `crop-<reference>` of the amplifier.
- **Kind:** judgement. **Severity:** function.
- **Source:** Tim Claycomb, *How to Lay Out a PCB for High-performance, Low-side Current-sensing Designs*, Texas Instruments technical article, SSZT805, February 2018, its two design requirements and closing list ("Use Kelvin connections on the shunt resistor"; "Place RG as close to the shunt resistor ground as possible"), https://www.ti.com/lit/pdf/sszt805, read 2026-10-14.

#### SENSE-2. A converter's input filter and reference capacitor sit at its pins

- **Applies when:** the schematic carries a filter at a converter's analog input, such as a resistor and capacitor, or a capacitor on a converter's reference pin.
- **Asks:** Are the input filter's parts, and the reference capacitor, placed immediately next to the converter pins they serve, joined by short, wide tracks?
- **Passes:** The filter capacitor and its resistor sit at the converter's input pin; the reference capacitor sits at the reference pin with its ground going straight into the plane.
- **Fails, as the views show it:** on `crop-<reference>` of the converter, or on `assembly-top` for a converter inside the controller, the filter or reference capacitor placed some way from its pin with a long track between.
- **Judged on:** `crop-<reference>` of the converter or controller, `assembly-top`, `assembly-bottom`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("The fly-wheel RC filters are placed immediately next to the input pins"; the reference capacitor "within 0.1-inches from the pin"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14.

#### SENSE-3. An amplifier's high-impedance input connections are as short as possible

- **Applies when:** the schematic carries an operational or instrumentation amplifier.
- **Asks:** Are the connections to the amplifier's inverting input, a high-impedance node, as short as they can be, with its feedback and gain resistors placed at that pin?
- **Passes:** The feedback and gain resistors sit next to the inverting pin, joined to it by the shortest tracks, with no track on that node wandering across the board.
- **Fails, as the views show it:** on `crop-<reference>` of the amplifier, a feedback or gain resistor placed away from the inverting pin, reached by a long track.
- **Judged on:** `crop-<reference>` of the amplifier.
- **Kind:** judgement. **Severity:** function.
- **Source:** Tim Claycomb, *The basics: How to layout a PCB for an op amp*, Texas Instruments, Precision Hub blog, 8 January 2016 ("Make the connections to the inverting pin as short as possible"), https://e2e.ti.com/blogs_/archives/b/precisionhub/posts/the-basics-how-to-layout-a-pcb-for-an-op-amp, read 2026-10-14.

#### SENSE-4. Sensing signals keep away from noise sources

- **Applies when:** the schematic carries a sensing front end.
- **Asks:** Do the sensing inputs and the converter's reference run away from noise sources: switching nodes, power tracks, relays and their drivers, the oscillator, and connectors carrying other signals?
- **Passes:** Each sensing net runs within the analog sensing region, kept apart from switching converters, load switches, relay coils and their drivers, the crystal and other connectors' signal tracks, and runs as far from supply lines as the board allows.
- **Fails, as the views show it:** on `net-<net>` for a sensing net, or on `classes`, a sensing track running alongside a power or switching track or past a relay, its driver or the crystal.
- **Judged on:** `net-<net>` for each sensing net, `classes`, every `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("keep the analog input signals and the reference input signals away from noise sources"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14; and Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.4.1 *Capacitive and Inductive Crosstalk* ("Keep non-noisy traces away from areas on the board were they could pick up noise, such as connectors, oscillator circuits, relays, and relay drivers"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *TLV333, TLV2333, TLV4333* data sheet, SBOS751, December 2015, § 11.2 *Layout Example* ("Run the input traces as far away from the supply lines as possible"), https://www.ti.com/lit/ds/symlink/tlv333.pdf, read 2026-10-14.

#### SENSE-5. Precision sensing parts are kept away from heat sources

- **Applies when:** the schematic carries a sensing front end.
- **Asks:** Are the sensing front end's amplifier, its input parts and the converter's reference placed away from the board's heat sources, with the two sides of each differential input at the same temperature?
- **Passes:** Regulators, power resistors, load switches and other parts that dissipate heat sit outside and away from the analog sensing region. The parts on the two sides of a differential input sit together, symmetrically, so no heat source warms one side more than the other.
- **Fails, as the views show it:** on `assembly-top`, `assembly-bottom` or `3d-angled`, a regulator or power part placed beside a sensing amplifier or its input parts, or a heat source nearer one input's parts than the other's.
- **Judged on:** `assembly-top`, `assembly-bottom`, `3d-angled`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *TLV333, TLV2333, TLV4333* data sheet, SBOS751, December 2015, § 11.1.1 *General Layout Guidelines* ("Avoid temperature gradients that create thermoelectric (Seebeck) effects"; "Thermally isolate components from power supplies or other heat sources"), https://www.ti.com/lit/ds/symlink/tlv333.pdf, read 2026-10-14.

### Clocks (CLOCK)

#### CLOCK-1. The crystal and its load capacitors sit at the oscillator pins

- **Applies when:** the schematic carries a crystal or a ceramic resonator.
- **Asks:** Are the crystal and its load capacitors close to the oscillator pins, the input pin's capacitor placed first and closest, the two load capacitors close to each other, and the input and output tracks short and kept apart from each other?
- **Passes:** The crystal sits at the controller's oscillator pins, its tracks short and direct. The load capacitor on the oscillator input sits closest to that pin and to ground; the two capacitors sit side by side. The input and output tracks are routed apart rather than side by side.
- **Fails, as the views show it:** on `crop-<reference>` of the controller, the crystal placed away from its pins with long tracks, the load capacitors apart from each other, or the input and output tracks running in parallel.
- **Judged on:** `crop-<reference>` of the controller, `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Microchip Technology (Atmel), *AVR186: Best Practices for the PCB Layout of Oscillators*, Atmel-8128B, September 2016, § 2 *Design Guides*, https://ww1.microchip.com/downloads/en/AppNotes/Atmel-8128-Best-Practices-for-the-PCB-layout-of-Oscillators_ApplicationNote_AVR186.pdf, read 2026-10-14.

#### CLOCK-2. The oscillator has its own ground area, kept clear of other return currents

- **Applies when:** the schematic carries a crystal or a ceramic resonator.
- **Asks:** Is there a ground area under the oscillator parts joined to the oscillator's ground, with the load capacitors and the crystal's case grounded to it by short connections that no other circuit's return current runs through?
- **Passes:** Ground copper under the crystal and its capacitors, joined to the controller's oscillator ground and to the plane. The capacitors' ground connections are short. No return current of a communication line, a load drive, a pulse-width output or a power path runs through that ground area. On a board with one copper layer, a guard ring round the oscillator parts joined to the oscillator ground pin.
- **Fails, as the views show it:** on a `layer-<copper layer>` under the oscillator, no ground copper under the crystal, or a power or drive track's return crossing the oscillator's ground area; on `net-<net>` for ground, the load capacitors reaching ground by long tracks.
- **Judged on:** `crop-<reference>` of the controller, every `layer-<copper layer>`, `net-<net>` for ground.
- **Kind:** judgement. **Severity:** function.
- **Source:** Microchip Technology (Atmel), *AVR186: Best Practices for the PCB Layout of Oscillators*, Atmel-8128B, September 2016, § 2 *Design Guides* ("A ground area should be placed under the crystal oscillator area. This ground land should be connected to the oscillator ground"; "The ground connection for the load capacitors should be short and avoid the return currents from USB, RS232, LIN, PWM,… and power lines"), https://ww1.microchip.com/downloads/en/AppNotes/Atmel-8128-Best-Practices-for-the-PCB-layout-of-Oscillators_ApplicationNote_AVR186.pdf, read 2026-10-14.

#### CLOCK-3. Other parts and signals keep away from the oscillator

- **Applies when:** the schematic carries a crystal or a ceramic resonator.
- **Asks:** Is the oscillator kept away from unrelated parts, from digital and clock lines, and from analog circuits, low-speed signals and connectors?
- **Passes:** No part unrelated to the oscillator sits within 25 mm (one inch) of the crystal. No digital or clock line runs near the crystal's tracks. The oscillator is away from the analog sensing region and from every connector.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, read against the caption's board coordinates, an unrelated part within 25 mm of the crystal, or the crystal beside a connector or the analog sensing region; on `layer-<copper layer>`, a digital track running beside the crystal's tracks.
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning* ("It is especially important that oscillator tank loops be located away from analog circuits, low-speed signals, and connectors") and § 2.4.1 *Capacitive and Inductive Crosstalk* ("No unrelated components should be closer than 1 inch to the crystal"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Microchip Technology (Atmel), *AVR186: Best Practices for the PCB Layout of Oscillators*, Atmel-8128B, September 2016, § 2 *Design Guides* ("Keep other digital signal lines, especially clock lines and frequently switching signal lines, as far away from the crystal connections as possible"), https://ww1.microchip.com/downloads/en/AppNotes/Atmel-8128-Best-Practices-for-the-PCB-layout-of-Oscillators_ApplicationNote_AVR186.pdf, read 2026-10-14.

### Separation of mains from low voltage (MAINS)

#### MAINS-1. Mains is separated from low voltage by the signed figures

- **Applies when:** the schematic carries a mains-referenced net, so the board declares `MAINS` `present`.
- **Asks:** Do the board's rules hold the separation between mains and low-voltage copper to the clearance and creepage its signed separation basis record states, in the single form the rules step fixes?
- **Passes:** The board's rules file holds the one `Mains separation` rule exactly as step 2 of [Rules before routing](#rules-before-routing) writes it, its condition `A.hasNetclass('Mains') && !B.hasNetclass('Mains')`, with a `clearance` and a `creepage` constraint no less than the separation basis record's mains-to-low-voltage figures, and the pre-order check passes the board. This item adds no rule of its own: it is that rule, and those figures are the signed ones the record holds.
- **Fails, as the views show it:** the pre-order check reports a `clearance` or `creepage` violation, or a `mains_declaration`, `separation_rule`, `separation_basis`, `local_clearance_override` or `mains_net_tie` failure; or, in `design-rules.md`, the `Mains separation` rule's clearance or creepage has no row, or its row gives a figure less than the separation basis record's `mains_to_low_voltage` figure, or names a source other than `MAINS-1` and that record.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** safety.
- **Source:** Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.3 *Creepage Distance* ("An adequate creepage distance protects against tracking"), https://www.ti.com/lit/pdf/slla284, read 2026-10-14.

#### MAINS-2. Mains copper stays in the mains region, and low-voltage copper stays out of it

- **Applies when:** the schematic carries a mains-referenced net.
- **Asks:** Does all `Mains`-class copper lie within the floorplan's mains region, on every layer, with no low-voltage track, via, pad or zone inside that region?
- **Passes:** On every layer, the `Mains` class's copper lies within the mains region's bounds in `layout-plan.md`, and nothing outside the class lies there. The only parts with pins on both sides of the region's boundary are the parts that bridge the barrier, such as an optocoupler, an isolator, a relay or a transformer.
- **Fails, as the views show it:** on `classes`, `Mains`-class copper outside the mains region, or another class's copper inside it; on a `layer-<copper layer>`, a low-voltage track or zone running into the mains region.
- **Judged on:** `classes`, every `layer-<copper layer>`, `assembly-top`, `assembly-bottom`.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning* (like functions placed in the same area, not mixed together), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.2 *Layer Stack*, Figure 4-1 (the space between the two sides kept "free from planes, traces, pads, and vias"), https://www.ti.com/lit/pdf/slla284, read 2026-10-14.

#### MAINS-3. Nothing crosses under a part that bridges the barrier

- **Applies when:** the schematic carries a part with pins on both a mains-referenced net and a net outside the `Mains` class, such as an optocoupler, an isolator, a relay or a transformer.
- **Asks:** Is the space under each such part, between its mains side and its low-voltage side, kept free of tracks, vias, pads and zones on every layer?
- **Passes:** Under each barrier-bridging part, on every copper layer, no copper lies between the row of pins on its mains side and the row on its low-voltage side.
- **Fails, as the views show it:** on any `layer-<copper layer>`, a track, via or zone passing under the part between its two sides, inner layers included.
- **Judged on:** every `layer-<copper layer>`, `classes`, `crop-<reference>` where the part is an integrated circuit.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.3 *Creepage Distance* ("on all layers keep the space under the isolator free from traces, vias, and pads to maintain maximum creepage distance"), https://www.ti.com/lit/pdf/slla284, read 2026-10-14.

#### MAINS-4. A slot cut to lengthen creepage is wide enough to count

- **Applies when:** the schematic carries a part with pins on both a mains-referenced net and a net outside the `Mains` class, such as an optocoupler, an isolator, a relay or a transformer.
- **Asks:** Where such a part's own spacing between its two sides, read from its datasheet, is less than the creepage the separation basis record states, so the layout makes up the difference with a slot or groove, is each slot or groove that the creepage relies on wider than 1 mm, does the creepage counted across it rely only on its width and twice its depth, and does it leave the board strong enough?
- **Passes:** A part whose own spacing is no less than the record's creepage needs no slot and meets it; its plan row gives the part's spacing from its datasheet and the record's figure. Where a part's spacing is less, the slot is drawn on the board outline layer, wider than 1 mm along its whole length, and spans the full distance between the part's two sides. The creepage across a groove, the surface distance plus the groove's width plus twice its depth, is no less than the separation basis record's creepage. A slot cut through the board leaves no surface path across it, so its creepage is the shortest path along the surface round its ends, which is no less than that figure. It leaves enough board on either side that the board does not flex at it.
- **Fails, as the views show it:** on `layer-Edge.Cuts` and on `crop-<reference>` or `assembly-top`, no slot where the part's spacing needs one, a slot 1 mm wide or narrower, or a slot that stops short of the part's ends so a surface path runs round it.
- **Judged on:** `layer-Edge.Cuts`, `assembly-top`, `assembly-bottom`, `crop-<reference>`.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.3 *Creepage Distance*, Figure 4-2 ("For a groove (>1 mm wide), the only depth requirement is that the existing creepage distance plus the width of the groove and twice the depth of the groove must equal or exceed the required creepage distance. The groove must not weaken the substrate"), https://www.ti.com/lit/pdf/slla284, read 2026-10-14.

### Connectors and mechanical fit (CONN)

#### CONN-1. A transient suppressor sits at its connector, on the line's path

- **Applies when:** the schematic carries a transient-voltage or electrostatic-discharge suppressor on a line that leaves the board at a connector.
- **Asks:** Is the suppressor as close to the connector as the rules allow, with the line running straight from the connector pin to the suppressor's pin, with no via and no stub, then on to what it protects, and with no unprotected track alongside it between the connector and the suppressor?
- **Passes:** The suppressor sits at the connector, and the protected circuit sits much further from it. The line runs from the connector pin to the suppressor's pin in a straight track, curved or at 45° where it must turn, then on. The suppressor's ground goes straight into the plane by the shortest path. No unprotected track runs in the area between connector and suppressor.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, the suppressor placed by the part it protects rather than by the connector; on `layer-<copper layer>`, the line reaching the suppressor through a stub or a via, a right-angled turn, or another track running beside it between connector and suppressor.
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ESD Protection Layout Guide*, SLVA680A, revised April 2022, § 2.1 *Optimizing Impedance for Dissipating ESD*, § 2.2 *Limiting EMI from ESD* and § 2.3 *Routing with VIAs*, https://www.ti.com/lit/pdf/slva680, read 2026-10-14.

#### CONN-2. Thin leadless packages keep away from where the board bends

- **Applies when:** the schematic carries a leadless package, such as a QFN or SON.
- **Asks:** Is each leadless package placed away from the regions of the board that bend most in manufacture and use, such as beside connectors that take mating force, mounting holes and the board's edges where it is handled?
- **Passes:** Each leadless package sits away from connectors, mounting holes and board edges, in a part of the board held flat.
- **Fails, as the views show it:** on `assembly-top`, `assembly-bottom` or `3d-angled`, a QFN or SON beside a connector, at a mounting hole or at the board's edge.
- **Judged on:** `assembly-top`, `assembly-bottom`, `3d-angled`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *QFN and SON PCB Attachment*, SLUA271C, revised December 2023, § 3.7 *Board Layout Considerations* ("Location of the thinner format QFN packages should be carefully considered when laying out the board design to avoid regions of extreme deflection"), https://www.ti.com/lit/pdf/slua271, read 2026-10-14.

#### CONN-3. No cable folds over the oscillator or the controller

- **Applies when:** the schematic carries a connector for a cable, and a controller or a crystal.
- **Asks:** Is each cable connector placed so that its cable, once fitted, cannot lie over the oscillator or the controller?
- **Passes:** Each cable connector sits at the board edge `layout-plan.md` gives it, facing off the board, so its cable leaves without crossing the controller or the crystal.
- **Fails, as the views show it:** on `3d-angled`, `3d-top` or `assembly-top`, a cable connector facing inward across the controller or the crystal, or placed so its cable must pass over them.
- **Judged on:** `3d-angled`, `3d-top`, `3d-bottom`, `assembly-top`, `assembly-bottom`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning* ("Do not design in cable assemblies that fold over the oscillator or the microcomputer after final assembly"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

### Test access and bring-up (TEST)

#### TEST-1. Every test point can be reached by a probe

- **Applies when:** the schematic carries a test point, which every board does ([Designing for bring-up and a second spin](#designing-for-bring-up-and-a-second-spin)).
- **Asks:** Is every test point a pad a probe can land on and stay on: a dedicated pad, a through-hole lead or a small via, never a surface-mount part's land, of a usable size, spaced from its neighbours and from part bodies?
- **Passes:** Each test point is a dedicated pad, a through-hole lead or a via with a hole of 0.36 mm or less, never a surface-mount land. Its pad is 1.0 mm across, or 0.9 mm at least. Test points are at least 2.5 mm apart centre to centre, at least 1.0 mm from any part's body edge to edge, and at least 2.0 mm from a part taller than 2.6 mm.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, a test point crowded against a part, under a part's outline, or closer than 2.5 mm to another; on `layer-F.Cu` or `layer-B.Cu`, a test point that is a surface-mount part's land or a pad smaller than 0.9 mm.
- **Judged on:** `assembly-top`, `assembly-bottom`, `layer-F.Cu`, `layer-B.Cu`, `3d-angled`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Jack Olson, *Circuit Board Design for In-Circuit Testers*, Altium Resources, updated 27 December 2020, section *Testability Checklist at the PCB Layout Level*, https://resources.altium.com/p/circuit-board-design-circuit-testability, read 2026-10-14.

#### TEST-2. Test points are on one side, with tall parts on the other

- **Applies when:** the schematic carries a test point.
- **Asks:** Are the test points on one side of the board, the side with the fewest parts, with the tall parts on the other side?
- **Passes:** Every test point sits on the same side of the board, and parts taller than 6.4 mm sit on the other side or at least 5.0 mm from any test point.
- **Fails, as the views show it:** on `assembly-top` and `assembly-bottom`, test points on both sides, or among tall parts.
- **Judged on:** `assembly-top`, `assembly-bottom`, `3d-angled`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Jack Olson, *Circuit Board Design for In-Circuit Testers*, Altium Resources, updated 27 December 2020, section *Testability Checklist at the PCB Layout Level* ("try to put all test points on one side of the board, usually the bottom or the side with the least circuit complexity"; "Keep tall components on the side that is not probed"), https://resources.altium.com/p/circuit-board-design-circuit-testability, read 2026-10-14.

#### TEST-3. A low-resistance part has two test pads on each side for four-wire measurement

- **Applies when:** the schematic carries a resistor used to measure current, or another part whose resistance is too low to read with two probes.
- **Asks:** Does each such part have two test pads on each of its nets, so its resistance can be measured four-wire?
- **Passes:** Each of the part's two nets carries two test pads, one for the current and one for the voltage, near the part.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, a shunt with one test pad, or none, on a side.
- **Judged on:** `assembly-top`, `assembly-bottom`, `net-<net>` for the part's nets.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Jack Olson, *Circuit Board Design for In-Circuit Testers*, Altium Resources, updated 27 December 2020, section *Testability Checklist at the PCB Layout Level* ("Provide two pads on nets tied to critical low impedance devices (four-wire Kelvin testing)"), https://resources.altium.com/p/circuit-board-design-circuit-testability, read 2026-10-14.

### Manufacture and assembly (MFG)

#### MFG-1. The board-wide minimums are the manufacturer's stated limits

- **Applies when:** always.
- **Asks:** Is every board-wide minimum in Board Setup's constraints set to the value the board manufacturer's stated limits give for the board's layer count and copper weight?
- **Passes:** Each board-wide minimum the rules step lists, minimum clearance, track width, via diameter and drill, hole size, annular ring, hole-to-hole, copper-to-edge and the silkscreen minimums, is set in Board Setup's constraints to the value the manufacturer recommends where it states one, and otherwise to its stated minimum, never smaller, each with its row in the board's rules table naming this item and the manufacturer's stated limits as its source, and the pre-order check reports none of them broken.
- **Fails, as the views show it:** the pre-order check reports a violation of a board-wide minimum; or, in `design-rules.md`, a board-wide minimum has no row, or its row's figure is smaller than the value the manufacturer's capability page it names gives for the board's layer count and copper weight, the recommended value where the page states one, or the row names no manufacturer and dated capability page.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** function.
- **Source:** KiCad, *PCB Editor* manual, version 10.0, section *Board setup*, *Configuring design rules*, *Constraints* ("Constraints in this section apply to the entire board and should be set to the values recommended by your board manufacturer"), https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html, read 2026-10-14.

#### MFG-2. An exposed pad's paste covers half to seven tenths of it

- **Applies when:** the schematic carries a part with an exposed pad on its underside.
- **Asks:** Is the solder paste on each exposed pad divided into openings covering about 50 % to 70 % of the pad, rather than one opening the size of the pad?
- **Passes:** On the paste layer, each exposed pad's paste is a set of smaller openings, together about 50 % to 70 % of the pad's area, or the part's datasheet's own stencil pattern where it gives one.
- **Fails, as the views show it:** on `layer-F.Paste` or `layer-B.Paste`, an exposed pad's paste as one opening the full size of the pad.
- **Judged on:** `layer-F.Paste`, `layer-B.Paste`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *QFN and SON PCB Attachment*, SLUA271C, revised December 2023, § 4.4 *Exposed-Pad Stencil Design* ("Typically, the solder-paste coverage is approximately 50% to 70% of the pad area"; a 1:1 aperture "results in excessive metal volume that can "float" the part"), https://www.ti.com/lit/pdf/slua271, read 2026-10-14.

#### MFG-3. Vias in a soldered pad do not draw the solder away

- **Applies when:** the schematic carries a part with an exposed pad on its underside.
- **Asks:** Is each via in the exposed pad's land small enough, or capped on the part's side, that it does not draw solder away from the joint?
- **Passes:** Each via in the land has a drill of 0.33 mm or smaller, or is capped with solder mask on the part's side, the cap at least 0.1 mm larger than the via's diameter. A land holding no via meets it; its plan row says whether the land will hold vias and, where it will, their drill or their cap.
- **Fails, as the views show it:** on `layer-F.Mask` (or `layer-B.Mask` for a part on the bottom), large open vias in an exposed pad's land; on `crop-<reference>`, vias in the land larger than the rest of the board's.
- **Judged on:** `layer-F.Mask`, `layer-B.Mask`, `crop-<reference>`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PowerPAD Thermally Enhanced Package*, SLMA002H, revised July 2018, § 2.4 *Thermal Vias* ("a via drill diameter of 0.33 mm (13 mils) or smaller works well"; "a solder mask material should be used to cap the vias on the component side with a dimension equal to the via diameter + 0.1 mm minimum"), https://www.ti.com/lit/pdf/slma002, read 2026-10-14.

### Emissions (EMI)

#### EMI-1. Power and its ground run over each other

- **Applies when:** always.
- **Asks:** Does each supply path to a part run directly over or beside its ground return, so the loop between them encloses little area?
- **Passes:** Each supply track or pour has ground running directly beneath it on the next layer, or beside it, all the way from its source to the part. On a two-layer board, ground is routed under power wherever it can be.
- **Fails, as the views show it:** on `classes`, a supply path and its ground taking different routes across the board, enclosing an area between them.
- **Judged on:** `classes`, `net-<net>` for each supply and ground net.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.1.1 *Inductance* ("Power and ground should be run directly over each other, which reduces impedance and minimizes loop area") and § 2.1.2 *Two-Layer vs Four-Layer Boards*, https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### EMI-2. No noisy track runs along the board edge

- **Applies when:** the schematic carries a crystal or a ceramic resonator, a switching converter, or a controller, each a source of tracks that can switch faster than 50 kHz.
- **Asks:** Are noisy tracks, clocks, switching nodes and outputs switching faster than 50 kHz, kept away from the outside edge of the board?
- **Passes:** No noisy track runs along the board's outside edge; where several noisy tracks run together, ground tracks surround the group. The plan row names the board's nets that switch faster than 50 kHz, so the review knows which tracks are noisy.
- **Fails, as the views show it:** on a `layer-<copper layer>` or `net-<net>`, a clock or switching track running along the board edge.
- **Judged on:** every `layer-<copper layer>`, `net-<net>` for each critical net.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 1.3 *Static Pins vs Active Pins vs Inputs* (signals switching faster than 50 kHz) and § 2.4.1 *Capacitive and Inductive Crosstalk* ("Never run noisy traces on the outside edge of the board"; "If possible, group a number of noisy traces together surrounded by ground traces"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### EMI-3. Lines leaving the board are filtered at the connector into a wide ground

- **Applies when:** the schematic carries a capacitor from a line that leaves the board at a connector to ground.
- **Asks:** Does each such capacitor sit at the connector, with its ground joined to a large ground area by a short, wide connection?
- **Passes:** The filter capacitors sit at the connector's pins. Their ground side joins a large ground area on both sides of the board, by connections no longer than three times their width.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, the filter capacitors away from the connector; on `layer-<copper layer>`, their ground reached by a narrow track.
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.5.4 *I/O Recommendations for Off-PCB Signals* and § 3.3 *Cables and Bypassing to the Shield*, Figure 13 ("The connection to the chassis is an RF path requiring 3:1 length to width"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### EMI-4. A supply ferrite bead sits nearest the noise source, with its capacitor inside it

- **Applies when:** the schematic carries a ferrite bead in a supply to an integrated circuit.
- **Asks:** Is the bead placed at the part it isolates, in the supply only and not the ground, with the part's bypass capacitor between the bead and the part?
- **Passes:** The bead sits next to the part it serves, in the supply line; the bypass capacitor sits between bead and part, so the part's switching current flows in the small loop inside the bead.
- **Fails, as the views show it:** on `crop-<reference>` or `assembly-top`, the bead at the far end of the supply, or the bypass capacitor on the supply side of the bead.
- **Judged on:** `crop-<reference>`, `assembly-top`, `assembly-bottom`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.2.4 *Bypassing and Ferrite Beads*, Figure 9 ("placing the capacitors inside the ferrite bead"; "The ferrite bead is used only on +V, not on ground"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### EMI-5. Series resistors on the controller's outputs sit at the controller

- **Applies when:** the schematic carries a resistor in series with a controller's output or input pin.
- **Asks:** Is each series resistor placed as close to the controller's pin as it can be?
- **Passes:** Each series resistor sits at its controller pin, over the controller's ground area where it can.
- **Fails, as the views show it:** on `crop-<reference>` of the controller or on `assembly-top`, a series resistor placed at the far end of its line.
- **Judged on:** `crop-<reference>` of the controller, `assembly-top`, `assembly-bottom`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.2.5 *Keeping Noise Close to the Chip* ("Place the resistor as close as possible to the microcomputer, overlapping the microcomputer ground if possible"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

### Workmanship (WORK)

These items ask what an experienced electrical engineer expects of any board before they look at what it does: parts placed by what they connect to, and copper that runs neat, tidy and direct. A board can pass every other item and still be laid out like a first attempt. The qualities a board's files hold exactly, an angle, a length, a width, are rule items the pre-order check measures, because a few pixels on an image are easily missed. The qualities of overall form are judgement items, each stated as what good looks like and what a failing board looks like in the views.

KiCad's layout rule check compares every two tracks that meet on one copper layer anywhere but at a pad, at a via as much as in open copper, and does not compare tracks that meet at a pad or that meet at a via on different layers (KiCad 10.0.7, measured on a throwaway board). So a track that branches off the middle of another, or off a via on its own layer, makes an angle with each side of it, and `WORK-4` fails the branch however it leaves. A route therefore branches only at a pad: the track runs to the pad and leaves it again. That is also the shape `WORK-2` measures a route against, the shortest tree joining a net's pads.

#### WORK-1. Connected parts sit together, so their connections run short and uncrossed

- **Applies when:** always.
- **Asks:** Is each part placed next to the parts it connects to, in the order its connections run, so that every connection is short and none crosses another on the way?
- **Passes:** Parts joined by a connection sit close together, in the order the circuit runs from part to part, each turned so that its pads face the pads they join. The tracks between them are short and run side by side rather than across one another, and a track crosses to another layer only to pass a track it cannot go round. A part that serves one pin, such as a resistor or a capacitor on it, sits beside that pin.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, a part set well apart from every part it connects to, or turned so that its pads face away from them; on a `layer-<copper layer>` or `net-<net>`, a track running across the board, or looping round other parts, to reach a partner that could have been placed beside it, or tracks crossing one another between layers where turning or swapping two parts would have kept them apart.
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`, `net-<net>` for each critical net.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 4 *Summary* ("a careful positioning of the integrated circuits is essential to achieve short interconnect lines") and § 1.4.1 *Proportionality of Loops and Dipoles* ("Loops and dipoles are antennas"; "the larger the laid-out area of the loop, the stronger the radiation"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and `hardware/proof/review-proof/layout-review.md`, round 1, which records parts placed loosely enough that a signal loops across that board to reach its partner.

#### WORK-2. Every net routed in tracks runs no longer than its pads' places need

- **Applies when:** always.
- **Asks:** Is every net routed in tracks no longer, in all its tracks together, than 1.2 times the shortest straight-line tree joining the centres of its pads?
- **Passes:** The board's project text variable `WORK_DETOUR_RATIO` is set to 1.2, or less, with its row in the board's rules table, and the pre-order check reports no `workmanship_detour` violation. The check measures each net that has tracks and at least two pads: the length of all its tracks and arcs on every layer, against the minimum spanning tree of its pad centres in straight lines. A net that carries a copper zone is not measured, since the zone carries its connection. A route drawn the direct way, turning at 45 degrees and branching at its pads, runs at most 1.08 times the straight line between each two pads it joins, the most a run along and at 45 degrees to the board's edges adds to a straight line: between two pads in a direction θ off the nearest of those directions it runs cos θ + (√2 − 1) sin θ times the line, at worst 1.08 at 22.5 degrees. So 1.2 leaves room for leaving and entering pads; one that wanders or loops round the board does not.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_detour` violation; or, in `design-rules.md`, no row for `WORK_DETOUR_RATIO`, a figure above 1.2, or no source named.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.1.1 *Inductance* ("Inductance increases with increasing length"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and, for the figure of 1.2, `hardware/proof/review-proof/layout-review.md`, round 1, which records the routes of that board that wander and loop, measured against this tree.

#### WORK-3. Routing reads cleanly: nothing wanders, doubles back or changes layer that does not need to

- **Applies when:** always.
- **Asks:** Seen whole, does every route take the path an experienced engineer would draw, with no loop, wander or double-back the placement does not force, no needless change of layer, and the tracks of related nets running together in orderly lines?
- **Passes:** Each route leaves its pad, turns as few times as it needs and arrives, running beside its neighbours at an even spacing where they share a path. A route changes layer only to pass something it cannot go round. A net that a copper zone carries, which `WORK-2` does not measure, reaches its pads as directly as one in tracks.
- **Fails, as the views show it:** on a `layer-<copper layer>` or `net-<net>`, a route that turns back on itself, makes a loop or a wide detour round a part it could have passed, or drops to another layer and comes straight back; on `classes`, a supply and its return taking different ways round the board; tracks sharing a path at uneven spacings or crossing one another without need.
- **Judged on:** every `layer-<copper layer>`, `net-<net>` for each critical net, `classes`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 1.4.1 *Proportionality of Loops and Dipoles* ("Loops and dipoles are antennas"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *High-Speed Layout Guidelines*, SCAA082A, November 2006, revised August 2017, § 2.5 *Traces, Vias, and Other PCB Components* ("Vias also increase the trace length"), https://www.ti.com/lit/pdf/scaa082, read 2026-10-14.

#### WORK-4. Corners are turned at 45 degrees or as arcs, never square or acute

- **Applies when:** always.
- **Asks:** Does every corner a track turns meet at 135 degrees or more between its two straight runs, or as an arc, with no right-angled and no acute corner?
- **Passes:** The board's rules file holds this custom rule, and the pre-order check reports no `track_angle` violation:

  ```
  (rule "Corners"
  	(constraint track_angle (min 135)))
  ```

  KiCad states the angle at a joint as the angle between its two tracks, so a straight run is 180, a 45-degree bend 135 and a square corner 90; the figure is a bare number, since a unit KiCad does not take drops the whole rules file. The rule has no condition, or the one condition `A.Type == 'Track'`, and no layer, so it holds on every track. A branch is made at a pad (see the opening of this area).
- **Fails, as the views show it:** the pre-order check reports a `track_angle` violation, or a `workmanship_rule` violation naming `WORK-4`; or, in `design-rules.md`, no row for the rule or a figure below 135.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *High-Speed Layout Guidelines*, SCAA082A, November 2006, revised August 2017, § 2.5 *Traces, Vias, and Other PCB Components* ("Avoid right-angle bends in a trace and try to route them at least with two 45° corners. To minimize any impedance change, the best routing would be a round bend"), https://www.ti.com/lit/pdf/scaa082, read 2026-10-14; and Texas Instruments, *High-Speed Interface Layout Guidelines*, SPRAAR7J, November 2018, revised February 2023, § 3.11 *Signal Bending* ("When bending is required, maintain a bend angle greater than 135°"), https://www.ti.com/lit/pdf/spraar7, read 2026-10-14.

#### WORK-5. No jog: no straight run is shorter than 1 mm

- **Applies when:** always.
- **Asks:** Is every straight run of track, between two bends or between a bend and a pad, at least 1 mm long, so that no small kink or offset is left in a route?
- **Passes:** The board's rules file holds this custom rule, and the pre-order check reports no `track_segment_length` violation:

  ```
  (rule "Jogs"
  	(constraint track_segment_length (min 1mm)))
  ```

  The rule has no condition, or the one condition `A.Type == 'Track'`, and no layer. KiCad measures the run into a pad as much as one between two bends, so a track leaves a pad, or a via, straight for at least 1 mm before it turns.
- **Fails, as the views show it:** the pre-order check reports a `track_segment_length` violation, or a `workmanship_rule` violation naming `WORK-5`; or, in `design-rules.md`, no row for the rule, or a figure below 1 mm.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** cosmetic.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, which records the jogs left in that board's routes beside two parts, each shorter than 1 mm.

#### WORK-6. No stub: no track ends free

- **Applies when:** always.
- **Asks:** Does every track end on a pad, a via, a copper zone or another track of its own net, with no length of track left ending in free space?
- **Passes:** The board's project text variable `WORK_STUB_MM` is set to 0, with its row in the board's rules table, and the pre-order check reports no `workmanship_stub` violation and no `track_dangling` violation. The check finds each track end that touches no pad, via, zone outline or other copper of its net on its layer, and measures the stub as the run of track from that end back to where it first joins anything else; KiCad's own layout rule check also reports a track end left unconnected, as `track_dangling`.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_stub` or `track_dangling` violation; or, in `design-rules.md`, no row for `WORK_STUB_MM`, or a figure above 0.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, which records the stubs left in that board's routes beside two parts.

#### WORK-7. No via a route does not need

- **Applies when:** always.
- **Asks:** Does every via join copper on two or more layers, so that none is left joining nothing or copper on one layer only?
- **Passes:** The pre-order check reports no `via_dangling` violation. KiCad's own layout rule check reports a via that is unconnected or connected on only one layer, unaided, so this item needs no rule written in the board's rules file. Its row in the board's rules table names KiCad's check.
- **Fails, as the views show it:** the pre-order check reports a `via_dangling` violation; or, in `design-rules.md`, no row for the check.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *High-Speed Layout Guidelines*, SCAA082A, November 2006, revised August 2017, § 2.5 *Traces, Vias, and Other PCB Components* ("Do not use vias on traces with sensitive signals, if unnecessary"), https://www.ti.com/lit/pdf/scaa082, read 2026-10-14.

#### WORK-8. One track width for each net class along a route, narrower only where it enters a pad

- **Applies when:** always.
- **Asks:** Is every track at least its net class's track width, except where it necks down within 1 mm of a pad to enter it?
- **Passes:** The board's project text variable `WORK_NECK_MM` is set to 1, or less, with its row in the board's rules table, and the pre-order check reports no `workmanship_width` violation. The check reads each net class's track width from the project file and the nets KiCad places in each class, a net in several classes taking the width of the one ranked first; a track narrower than that width passes only as part of a run of such tracks that reaches a pad of its net and is no longer than `WORK_NECK_MM` in all. A track wider than its class's width never fails, so a power path widened where there is room, as `POWER-2` asks, passes. A rule that requires a different width on some tracks writes it as the class's own figure.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_width` violation; or, in `design-rules.md`, no row for `WORK_NECK_MM`, or a figure above 1 mm.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *High-Speed Interface Layout Guidelines*, SPRAAR7J, November 2018, revised February 2023, § 3.2 *High-Speed Differential Signal Rules* ("Maintain constant trace width after the SoC BGA escape to avoid impedance mismatches in the transmission lines"), https://www.ti.com/lit/pdf/spraar7, read 2026-10-14; and, for the figure of 1 mm, `hardware/proof/review-proof/layout-review.md`, round 1, which records that board's tracks narrowed partway along.

#### WORK-9. Tracks run parallel to the board's edges or at 45 degrees to them

- **Applies when:** always.
- **Asks:** Does every straight track run parallel to the board's edges, or at 45 degrees to them, within 0.1 degree?
- **Passes:** The board's project text variable `WORK_ANGLE_TOLERANCE_DEG` is set to 0.1, or less, with its row in the board's rules table, and the pre-order check reports no `workmanship_direction` violation. The check takes the direction of the board's edges from the longest straight side of its outline, and holds every straight track to a multiple of 45 degrees from it; an arc is a corner, which `WORK-4` judges.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_direction` violation; or, in `design-rules.md`, no row for `WORK_ANGLE_TOLERANCE_DEG`, or a figure above 0.1.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** cosmetic.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, which records that board's tracks drawn at odd angles.

#### WORK-10. A track enters a long pad along its long axis, from its end

- **Applies when:** the schematic carries a part with a pad at least twice as long as it is wide, such as an integrated circuit's lead or a crystal's pad.
- **Asks:** Does every track entering a pad at least twice as long as it is wide run in along the pad's long axis, through one of its short ends, within 0.1 degree?
- **Passes:** The board's project text variable `WORK_PAD_ENTRY_RATIO` is set to 2, or less, with its row in the board's rules table, `WORK_ANGLE_TOLERANCE_DEG` is set as `WORK-9` asks, and the pre-order check reports no `workmanship_pad_entry` violation. The check finds each track that has one end on such a pad's copper and the other off it, and holds its direction there to the pad's long axis. A pad less than twice as long as it is wide, such as a chip resistor's, may be entered from any side, square to that side.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_pad_entry` violation; or, in `design-rules.md`, no row for `WORK_PAD_ENTRY_RATIO`, or a figure above 2.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, which records that board's tracks entering long pads from their sides and at a slant; and, for the figure of 2, Altium, *Altium Designer* documentation, *SMT Rule Types*, *SMD Entry* ("The longer edge of the pad is considered the side"; "the ends are the shorter edges"; "the side option is only applied if the Side length > 2x End length"), https://www.altium.com/documentation/altium-designer/pcb/design-rule-types/smt, read 2026-10-14.

Out of scope for this section: applying the catalogue to a finished layout, which the [layout review](#layout-review) does, and producing the views it is judged on, which [Layout review views](#layout-review-views) describes.
