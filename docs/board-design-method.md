# Board design method

This is how a controller board is designed in KiCad so that it passes the pre-order check and works once built. The method works for any machine. A machine's own figures come from its own records, and this document names each record only by the role it plays: the machine's constraints record, its separation basis record, the requirements a board serves, the board manufacturer's stated limits, and the datasheets of the parts on the board. A physical constant or a property of a material is stated in this document, with where it was published, wherever a step uses one, so no standard that must be bought is needed to carry a step out.

A board is designed by an agent, with no person at the editor, and each step can be carried out by an agent session from its own text. The pre-order check that later holds a board to the rules KiCad's layout rule check enforces, and how to run it, are described in [`hardware/README.md`](../hardware/README.md). This method designs controller boards and the boards that ride with them: the pre-order check requires a pin allocation record listing at least one channel from a controller pin, named as a port letter then a number, unless the record declares `controller: none`, which only a board placing no controller, and no part carrying the machine's controller catalogue number, can pass; such a record lists the channels crossing the board's header, each a far channel that another board in the machine folder lists with a controller pin, or a rail, and a board that places a controller may list a connector's supply and return pins by rail entries. The form is in `hardware/README.md`, which also states the residual the declaration leaves. Besides the board, the check holds every design, mains or not, to three records, each read from the nearest folder at or above the board: the pin allocation record (`pin-allocation.yaml`), the parts specification (`parts-specification.yaml`) and the catalogue extract (`catalogue-extract.yaml`). A design that declares mains is held to a fourth, the separation basis record (`separation-basis.yaml`), found the same way and signed by a named person. The forms of all four are in `hardware/README.md`. A throwaway board made to demonstrate this method carries synthetic records, each marked `synthetic: true`, and has its project text variable `NOT_FOR_MANUFACTURE` set to `true`; a synthetic record passes only a board so marked. A throwaway design under `hardware/proof/` carries a separation basis record marked synthetic even when it declares no mains, because the repository's listing of what the check reads expects a separation basis record for every tracked design (`test_every_file_the_check_reads_of_the_designs_in_this_repository_is_listed` in `hardware/tools/tests/test_board_check.py` fails without one).

The sections after the tools, up to and including the ordering step, are carried out in the order they appear. The first four, proving value-critical circuits, designing for bring-up, reviewing the schematic and planning the layout, are finished and committed before any footprint is placed on the board; the placement, chosen from more than one and recorded before any track, arc, via or pour is drawn, follows, then the rules and the routing, the layout review judges the finished layout before the board is ordered, and the ordering step then checks the board's production files against the assembler's preview and on rendered layers before the board is paid for. A board that fails any section's step is not ordered. The pre-order check does not read the records the first four sections keep, including the schematic review's, or the layout review's, so passing it does not stand in for them. The last four sections, [Layout review views](#layout-review-views), [Layout practice catalogue](#layout-practice-catalogue), [Schematic drawing convention](#schematic-drawing-convention) and [Circuit practice catalogue](#circuit-practice-catalogue), are not steps carried out in order: they are reference lists the steps use. The catalogues and the convention cite only documents any reader can obtain without charge.

## Tools

These are needed in addition to the tools the pre-order check needs (KiCad 10, Python, PyYAML, git and Task, listed in `hardware/README.md`). The tools in the table other than the agent client and the model it runs are free; the agent client's row says what those two cost.

| Tool | Version the commands below were exercised with | Where to get it |
|---|---|---|
| The agent client that runs the session: a program that speaks MCP (the Model Context Protocol), launches Konnect and calls its tools, loads the Konnect skills and the repository's `repo-board-design` skill, and runs the shell commands of the steps below. Every step is carried out through it. The model it runs, and any account or subscription the client needs, are a cost the reader bears. | Claude Code 2.1.300, the version the fresh session that followed this method used. Another client that does the same may be used. | https://claude.com/claude-code. Claude Code needs an Anthropic account, a subscription or an API key, and the model it runs is billed to that account. |
| KiCad, with its command-line tool and the Python it bundles with its `pcbnew` module. A reader who only wants to see a board's schematic drawn needs this tool and no other: `task hw:sheets` writes an image of every sheet of every design with it alone. | KiCad 10.0.7 | https://www.kicad.org/download/ |
| Freerouting, the external router | Freerouting 2.5.0, the file `freerouting-2.5.0.jar` | https://github.com/freerouting/freerouting/releases (the v2.5.0 release, asset `freerouting-2.5.0.jar`) |
| A Java runtime, which Freerouting runs on | Eclipse Temurin OpenJDK 26.0.1 | https://adoptium.net/ or any other Java distribution. Freerouting 2.5.0 is built for Java 25, so it needs Java 25 or newer. |
| resvg, the SVG rasteriser that turns the [layout review views](#layout-review-views) into images | resvg 0.48.1 and resvg 0.47.0; the command refuses one older than 0.47 | A prebuilt program from https://github.com/linebender/resvg/releases: the v0.47.0 release carries one for each of Windows (`resvg-win64.zip`), macOS and Linux (x86_64), and later releases carry them for macOS and Linux only. Or `brew install resvg` with Homebrew, on macOS or Linux. Or `cargo install resvg` with a Rust toolchain from https://rustup.rs/, on any operating system. Set `RESVG=/path/to/resvg` when it is not on the search path. |
| A monospaced font for the captions of the layout review views: DejaVu Sans Mono, or Menlo, Consolas, Liberation Mono or Courier New, the captions being drawn in the first of these that resvg finds among the system's fonts | Menlo, as macOS carries it | macOS carries Menlo and Windows carries Consolas. Elsewhere, install DejaVu Sans Mono from https://dejavu-fonts.github.io/ or your system's package of it (for example `fonts-dejavu`). Without one the command stops with `CANNOT RUN`. |
| gerbonara, a Python library under the Apache licence that reads Gerber and drill files, which KiCad's command-line tool does not. The [ordering step](#ordering) uses it to turn each exported fabrication layer and the drill file into a vector image, which resvg turns into an image. It is installed into a virtual environment of its own, at this exact version. | gerbonara 1.6.3 | `python3 -m venv <folder>`, then `<folder>/bin/python -m pip install gerbonara==1.6.3` (on Windows `<folder>\Scripts\python.exe`). https://pypi.org/project/gerbonara/. The commands that draw layers take the environment's Python as `GERBONARA_PYTHON` (`hardware/README.md`). A tool that needs it and does not find it at that version stops with `CANNOT RUN` naming it. |
| Konnect, the MCP server through which the agent drives KiCad's editors. It is launched and its tools are called by the agent client in the first row; a session without one cannot carry out the steps that name Konnect. It ships skills of its own (`konnect`, `kicad-schematic`, `kicad-pcb`, `kicad-library`, `kicad-review`, `kicad-manufacture`), which are used as they ship. | Konnect 0.13.0, with KiCad 10.0.7 | Install it through KiCad's Plugin and Content Manager, or from https://github.com/mixelpixx/Konnect/releases (the v0.13.0 release). Its licence is AGPL-3.0. Then register it with your MCP client as that client describes. |
| ngspice, the circuit simulator, as a program of its own. KiCad embeds ngspice only as a library, behind its simulator window, so the command-line program the steps below run is installed separately. | ngspice 47, on a netlist exported by KiCad 10.0.7's `kicad-cli` | https://ngspice.sourceforge.io/download.html. On macOS, `brew install ngspice` with Homebrew (https://brew.sh/), which is how the version opposite was installed. On Linux, the distribution's `ngspice` package. On Windows, the release archive from the download page, whose console program is `ngspice_con.exe`. |

KiCad's bundled Python is the one that can `import pcbnew`. Its usual location:

| System | KiCad's Python |
|---|---|
| macOS | `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3` |
| Windows | `C:\Program Files\KiCad\10.0\bin\python.exe` |
| Linux (distribution package) | the system `python3`, which the package gives the `pcbnew` module |

To check it, run `<KiCad's Python> -c "import pcbnew; print(pcbnew.Version())"`. It should print the KiCad version. The commands below write this Python as `KICAD_PYTHON` and the router's jar file as `FREEROUTING_JAR`. Replace them with the paths on your machine. Every `task hw:` command runs `kicad-cli`. If it is not on the search path, set `KICAD_CLI` to its full path, as `hardware/README.md` describes, before the first of them.

The commands below are written for a POSIX shell, the terminal on macOS or Linux, and were exercised on macOS. On Windows, run them in PowerShell. The `task` commands are typed as written. In the others, write `$env:KICAD_PYTHON` and `$env:FREEROUTING_JAR` where a command says `"$KICAD_PYTHON"` and `"$FREEROUTING_JAR"`, and start a command that begins with KiCad's Python with `& `, for example `& $env:KICAD_PYTHON -c "import pcbnew; print(pcbnew.Version())"`. Set them with `$env:KICAD_PYTHON = "C:\Program Files\KiCad\10.0\bin\python.exe"`. The Windows forms have not been exercised.

KiCad's bundled Python is used here for the router's export and import, and for the edits Konnect cannot make ([What Konnect cannot do, and the workaround](#what-konnect-cannot-do-and-the-workaround)). In KiCad 10.0.7 its `pcbnew` module was found unreliable for reading the board back: some objects it returns come back unwrapped, without their methods, so a net's class could not be asked for its clearance. Nothing else in this method reads the board through it.

### The board editor, driven by an agent

The agent drives KiCad's editors through the Konnect MCP server, and runs every other command in this document from a shell. Konnect loads its tools in toolsets, mid-session. A toolset is visible only to the session that loaded it, not to a subagent spawned from that session, so all board work, routing and locking included, runs in the session that loaded the board toolsets.

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

Where a judgement is visual, the agent looks at a rendered view of the board, never at the editor window: Konnect's export toolset and `kicad-cli pcb export svg` both render the board's layers, `task hw:views` renders every view the layout review judges a board on ([Layout review views](#layout-review-views)), and `task hw:placement` renders a placed board's parts with their unrouted connections and measures them ([Placement](#placement)). What to look for is the [layout review](#layout-review) step's.

#### Konnect's skills, and where they conflict with this method

Load Konnect's bundled skills as they ship and do not edit them. Where one of them conflicts with this method, this method governs. The case that matters most is routing: Konnect's own routing export refuses the rounded pads that standard surface-mount footprints use, so whatever a bundled skill says about autorouting, routing here goes through KiCad's exporter, Freerouting from its command line and KiCad's importer ([Routing](#routing-critical-nets-by-hand-and-locked-then-the-rest), steps 6 and 7), and the result is judged by KiCad's own rule checks, never by the router's report.

The same holds for Konnect's manufacture skill (`kicad-manufacture`). Its tools that export a manufacturing package, convert the position file into the assembler's placement file with a correction policy of Konnect's own, and report a `READY`, `NOT READY` or `INCOMPLETE` verdict are not used for the [ordering step](#ordering): that step names the export commands and the conversion, which the tooling tests run against a proof design, and its own check record, not the skill's verdict or its report that a package is complete, decides whether a board is paid for. Where the skill's ordering steps differ from the ordering step, the ordering step governs. What the skill asks that the step also asks, a direct rule check before export, a fresh destination for the files, opening the Gerber and drill files in a viewer and inspecting every component in the assembler's preview before an order is approved, is done as the step says it.

#### What Konnect cannot do, and the workaround

In Konnect 0.13.0, with KiCad 10.0.7, these were found to be beyond its tools:

- deleting a via;
- creating or editing a rule area (a zone carrying a keepout);
- moving a footprint's text fields, such as its reference or value;
- swapping a placed footprint for another while keeping its link to its schematic symbol;
- setting a placed footprint's library description, attributes, 3D model and schematic fields, which footprints Konnect places lack, and clearing the `in_bom` attribute Konnect writes on a mounting-hole footprint (a footprint's attribute is set in the same way);
- setting each placed pad's pin type and pin function from the schematic's netlist, which Konnect's update from the schematic did not write in the demonstration run (Konnect 0.13.0, KiCad 10.0.7). The layout review views and the pre-order check name a circuit's supply nets, and its decoupling parts, only from pads typed power input or power output (`hardware/README.md`, the crop view), so a board whose pads carry no type shows none. Give each pad the type of its node in `kicad-cli sch export netlist`, whose `(pintype …)` the netlist's nodes carry, with `pad.SetPinType` and `pad.SetPinFunction` of the `pcbnew` module, before the views are first rendered and the pre-order check first run.

Each is done with KiCad's scripting, on the board closed in every editor (the closing steps above), run with `KICAD_PYTHON`: load the board with `pcbnew.LoadBoard`, make the change, refill the zones, and save. Refill every time, whether or not the edit touches a zone, so the saved board always carries current fills and the comparison below is made between two refilled saves. To show the save is stable, refill and save a second time and compare the two files byte for byte, with `cmp` or on Windows `fc /b`; they must be identical. An edit that touches a critical-class item repeats the locking and the record of [Routing](#routing-critical-nets-by-hand-and-locked-then-the-rest), steps 3 and 5, before the board is exported. KiCad leaves a `.history/` folder and a `<board>.kicad_prl` file beside the board: delete both before committing. This is the one use of `pcbnew` besides the router's export and import; the reason for keeping it narrow is given above, so use it to make those edits only, and read the result back with KiCad's own checks.

Konnect also has no tool for the project file's text variables, its ERC and DRC severities or its board minimums. Konnect's skill forbids editing the project file directly, and this method governs: with the board closed in every editor, read the project file as JSON, change the entry and write the whole object back, keeping every other key, and read the result back with the checks the step names.

Two further limits of Konnect bear on the steps. Net classes written to the project file are not seen by a board that is open until it is reopened, so confirm them by asking KiCad, as [Rules before routing](#rules-before-routing) step 3 does, and reopen the board before routing, as its step 4 says. Konnect's placement score reports full marks when it cannot match decoupling capacitors to their integrated circuit, so a full score with any unmatched capacitor is unresolved, never a pass.

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

Obtain a datasheet from the part manufacturer's own site, and cite it by that address and the date it was read. A distributor's copy is allowed only when it is the manufacturer's own document, and is cited as such.

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

`<work folder>`, here and in every later step, is a new, empty folder made for this design, for example with `mktemp -d`, and not a shared temporary directory, which may hold other work's KiCad project files. The record is refused inside the board's folder or inside any folder that holds a KiCad project file, and the views are refused under the same rule and, as well, in a folder that already holds files.

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

The two pins of an isolating link (step 2) are classed signal: power reaches them only through the supply input upstream of the link, and none enters the board by them.

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

## Schematic review

Do this once the schematic is drawn and the two previous sections' records are committed, and before any footprint is placed on the board. The layout catalogue judges how a board is drawn and leaves outside its scope whether its circuit is right; the first section proves only the circuits whose values decide whether they work. This section closes the gap between them: every net and every part of the schematic receives a recorded verdict against the [Circuit practice catalogue](#circuit-practice-catalogue) while a change still costs only an edit to the schematic. A pin driven beyond its rating, a missing pull-up, a floating strap pin or a cable mirrored against its harness is found here, since the layout review cannot see any of them.

The **checklist** is every item of the circuit practice catalogue as the commit under review holds it. The **reviewer** is an agent session, or a person, that did not draw the schematic. It works from these alone: the schematic and the netlist exported from it, the datasheet of every part, the board's circuit-proof and bring-up records, the board's constraints record, its separation basis record and its pin allocation, parts specification and catalogue extract records. The drawing of each sheet that `task hw:sheets` writes from the commit under review is opened for `DRAW-1`. A datasheet is opened at its address, never recalled; the reviewer records its document number and revision. It never works from the designer's reasoning, session or notes.

Keep the review in one file named `schematic-review.md` in the board's own folder, beside its KiCad project, its `circuit-proof.md` and its `bring-up-provision.md`, and beside the `layout-review.md` it precedes. It holds every round of the review, each under its own heading, `## Round <n>`, numbered from 1. A round holds its opening fields (step 1), then `### Verdicts` with the verdict table (step 3), then `### Findings` with the findings table (step 4), or the line `This round raises no finding.` in its place. What a round recorded at its end is never changed afterwards; only a finding's Closed by is filled in later, as step 5 completes it. Commit the record at the end of each round, before any change to the schematic it calls for, and again with every change that closes a finding.

**A round may be judged by unit instead of by one reviewer.** That is a way of carrying out steps 2 to 4, and it changes none of them. `task hw:review-run -- --caller schematic` ([`hardware/README.md`](../hardware/README.md#the-schematic-review-by-unit)) judges a round with one reviewer for each area of the circuit practice catalogue and one for the free pass; an item that selects every net, every part or every sheet stays in its area's unit and is not split. Each reviewer is a fork of one shared context that holds this section, the drawing convention, the whole catalogue, the schematic, the netlist, the records, the round's fields and the check's report and judges nothing, with two reviewers of each so that a fail either raises stands, and a reviewer opens every datasheet at its address as step 3 requires. The command merges what they return, with no model, into one round of the one record: the verdict table has a row for each item together with each net, part or sheet it selects (the replicas' rows are merged pair by pair, a fail standing), and the findings are numbered at the merge in the checklist's order with the free pass's last. The round's own fields in step 1, its number, the commit judged, the command the netlist was exported with and the records read, come from whoever starts the round: they are given to the command in the review folder it reads, which `task hw:schematic-review-folder` writes from the committed schematic, the exported netlist, the drawing of each sheet that `task hw:sheets` wrote and the check's report, since the merge has no model to write them. For a round after the first the folder holds the earlier rounds of `schematic-review.md` as recorded, because a fail's Why may cite an earlier finding closed by a reason, and for a first round it holds no review record. The folder command refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, a sheet with no drawing, a missing check report, a record that is not a Markdown or YAML file of the design at the commit, a record that is the schematic review record, a designer's notes or a session record (the name is matched without regard to case and against every folder and file name in the record's path), a record given twice or none, a number that is not a whole number of one or more, a netlist command that is not one line and a method lacking a section the review needs, and writes nothing. The merge refuses a folder whose round fields are missing or malformed, or whose netlist names parts or sheets other than the schematic's, before any reviewer starts, as it does a method whose circuit practice catalogue gives one area code to two areas or holds an item before any area heading. It fails a round in which an item has no verdict row, in which a row is for something that is not an item of the checklist, in which any net or part of the netlist or any sheet of the schematic appears in no item's rows (the merge checks the coverage of every net, part and sheet, so the items that select every net, every part and every sheet must each name all of theirs), in which a row names something that does not exist, in which there is an item that selects nothing and also selects something (a `none` row beside another row raised by one and the same reviewer; where reviewers disagree whether an item selects anything, the rows of those that judged what it selects stand and the `none` row gives way), in which there is a pass or fail with nothing under Rests on, in which there is a not applicable or fail with nothing under Why (the free pass's row too, for this and the check before it), in which a fail cites no finding of its own item or of an earlier round, in which a finding is of an item that does not fail, a finding not raised by its item, a severity outside the catalogue's four or a Closed by the reviewer wrote, or in which a `cannot judge` is left, and it names the item and the net, part or sheet. It does not judge which nets an item selects or whether a verdict is right. A `cannot judge` (step 3) is resolved by whoever started the round, since a reviewer cannot draw a sheet: they add the sheet drawing or view, or a text file holding the figure when the Why asks for a document the schematic gives no address to fetch it from, to the review folder with the folder command's `--add-view` or `--add-document` mode, which records the item, the Why, the file and, given `--cannot-judge-target`, the net, part or sheet it was about, and run that unit again, and the merged row is written `cannot judge, then <verdict>` with the added file in Rests on. The merged round is written as one file that whoever started the round appends below the record's earlier rounds, which stay as they are, and commits at the end of the round, as step 1 requires. Judging a round with one reviewer, a person or an agent session that does not use the command, stays valid, and every round already recorded stands. The fanned-out form is relied on only once its proof is recorded, and until then this section is carried out with one reviewer.

### 1. Start a round: commit the schematic, export its netlist

Commit the schematic as it is to be judged. From the board's folder, export its netlist in KiCad's own format:

```
kicad-cli sch export netlist --output <work folder>/review.net <board>.kicad_sch
```

Begin the round with:

- **Schematic judged**: the commit holding the schematic the round judges;
- **Netlist**: the command as it was run;
- **Records read**: each record the round reads, by path, with the separation basis record's `accepted_on` where the board declares mains.

A round judges the schematic only as that commit holds it.

### 2. Select the nets and parts each item applies to

For each item of the checklist, read its *Applies when* against the netlist and the schematic, and list the nets and parts it selects. An item whose condition the schematic meets applies, and cannot be marked as not applying. `PINV-1` selects every net, `DERATE-2` selects every part and `DRAW-1` selects every sheet, so every net, every part and every sheet of the schematic is selected by at least one item. A sheet is named as the schematic names it, the root sheet by the design's name. A net or part the netlist holds, or a sheet the schematic holds, that no row of the next step names fails the round.

### 3. Give every item a verdict for every net, part and sheet it selects

Give one row of the round's verdict table to each item together with each net, part or sheet the item selects, and one row to each item that selects none, so a round with no row for an applicable pair fails:

| Item | Net or part | Verdict | Rests on | Why |
|---|---|---|---|---|

- **Item** is the item's identifier. **Net or part** is one net name, one reference designator or one sheet name, as step 2 names a sheet, or `none` for an item that applies to nothing on this board.
- **Verdict** is one of `pass`, `fail`, `not applicable` or `cannot judge`.
- **Rests on** cites what the verdict was reached from: the schematic sheet and the net or reference designator, each datasheet by document number, revision and section or page, each calculation by the file and row that holds its arithmetic, and each record by path and key. A verdict that rests on a rating, a figure or a requirement it does not cite is not a `pass`.
- **Why**: for `not applicable`, the reason against the item's *Applies when*, stating what the schematic lacks. For `fail`, the number of the finding it raises (step 4), or of an earlier finding closed by a reason (step 5). For `cannot judge`, what is missing and where it will be found; a `cannot judge` is resolved within the round, and the verdict reached is written in the same row after it.

A rating a reviewer cannot source at review counts as absent and fails the item: a datasheet that cannot be opened, a rating the datasheet does not state, and a figure a purchased standard sets that neither the board's separation basis record nor a cited, freely available derivation of that standard's tables gives, are each absent. A figure of such a standard is never taken from the reviewer's memory, and the item that needs one names where it comes from.

### 4. Record every finding

Give every finding a row in the round's findings table, numbered `<round>.<n>`, so `1.1` is the first finding of round 1:

| Finding | Raised by | Severity | What and where | Closed by |
|---|---|---|---|---|

- **Raised by** is the item whose `fail` verdict raised it, or `free pass` for something the reviewer saw that no item asks about. After the verdicts, look over the whole schematic once for anything else wrong with it and record each thing seen.
- **Severity** is the item's, on the catalogue's four-level scale ([How a circuit item is read](#how-a-circuit-item-is-read)), or for a free-pass finding chosen by those definitions. A finding that bears on separation between mains and anything a person or a low-voltage circuit can reach, on fusing, on protective earthing or on insulation is of safety severity, whatever raised it.
- **What and where** says what is wrong, with the sheet and the net or reference designator that show it.

### 5. Close every finding

A finding stays open until one of these closes it, written in Closed by:

- a change to the schematic, naming the commit that makes it, which the next round judges. Before that round, sweep the schematic for every instance of the finding's class, not only the one the reviewer named, and fix them together; the commit names what was searched for and how many instances were found;
- a recorded reason showing that the item is in fact met, written `met:`; that it does not apply to this board, written `does not apply:`; or that it is overridden by a requirement the board serves or an item of the catalogue that the board must also meet, written `overridden by:` with that requirement or item named.

Never a judgement that the finding is unimportant. The designer writes Closed by and the change that closes a finding, and nothing else in a round the reviewer has recorded.

A finding of safety severity closes only by a change to the schematic, or by a named person's acceptance of one of those reasons, and never by the agent that drew or reviewed the board. The acceptance is recorded beside the board, in the review record, in the same form as the signature on the board's separation basis record: after the reason, Closed by gives `accepted_by:` with the person's name and `accepted_on:` with the date they accepted it, written `YYYY-MM-DD`, and the record is committed with them. The name is a person's, never an agent session's, and never a placeholder such as `unsigned`, `tbd`, `todo`, `none`, `placeholder` or anything in angle brackets; the date is no later than the day of the commit that adds it.

### 6. After a change, begin the next round; the review closes on a clean full round

After any change to the schematic, begin a new round at step 1 and export the netlist again. Every round judges the whole checklist, so a change cannot leave an item unjudged against the schematic as it now stands. The review **closes** on a round that judges the schematic as committed, in which every item has a verdict for every net, part and sheet it selects and none is left `cannot judge`, every `fail` verdict raises a finding or cites one an earlier round closed by a reason, and every finding of every round is closed. A finding closed in that round by a change needs a further round.

Commit the closed record before the first commit that places a footprint on the board. It is judged as it stood in the commit before placement, on the branch as pushed, in the checkout step 4 of the first section makes, with `schematic-review.md` in place of `circuit-proof.md`. Judge the record against the schematic rather than taking its word:

- every net and every part of the netlist exported from the schematic in that commit, and every sheet of that schematic, has a row, and the record names no other;
- every item of the catalogue in that commit has a row for every net, part and sheet its *Applies when* selects on that netlist and schematic, and each `not applicable` gives a reason the schematic bears out;
- every `Rests on` cites what step 3 requires, and each datasheet it cites states the rating the verdict rests on;
- every finding's Severity is the one step 4 gives, and every Closed by is one step 5 allows, a safety finding's carrying an `accepted_by` and `accepted_on` where it closes by a reason.

A board whose schematic review has not closed is not placed, and so is not ordered.

**This review is shown to find what it checks for** on `hardware/proof/circuit-review-proof`, a clean proof design, marked not for manufacture, that declares mains and holds at least one part or net for every catalogue item a condition selects. A session that has never read the catalogue seeds defects of its own choosing, the mistakes a designer makes, into a copy of the design's folder in a temporary work tree outside the repository, keeps the copy's records consistent so that no tool reports a seed, exports the copy's netlist and writes the seed list apart from both the copy and the review folder. A fresh session with no record of the seeds then follows this section on a review folder holding only what the step gives a reviewer: the seeded copy at its repository-relative path with no history, its netlist, every record the step reads, the drawing of each sheet that `task hw:sheets` writes from the copy, this method as written, the hardware readme and the pre-order check's report on the copy. It is granted read tools and read-only retrieval of a datasheet at its address, and returns its schematic review record. Each seed is then looked for among that record's findings, and a seed the review does not report is closed where the gap lies, in the catalogue with a published source or in this section, and the blind review repeated in a new session. [`hardware/README.md`](../hardware/README.md#the-proof-designs) describes the proof design. Repeat the proof after changing the catalogue, the drawing convention or this section, in the form that changed: a change to the section as one reviewer follows it repeats the single-reviewer proof above, and a change to how a round is judged by unit, to the schematic caller or to the review folder it reads repeats the fanned-out proof, `task hw:schematic-review-proof -- --work <folder> --seeded-repo <work tree> --seeds <seed list>`, which checks the seeded copy, exports its netlist, draws its sheets, writes the review folder from the copy's commit, runs the single form once through the review kit on the mid-tier model and records it as the baseline file `schematic_single_runs.json` when none is recorded for the seed list, design and model (none is recorded in a form the kit loads, so the first proof records it), runs the fanned-out form with two small-tier reviewers of each unit, and judges it against the recorded single run by the review kit's pooled criterion: the fanned-out form must report no fewer seeds than the fewest any recorded single run reported and every seed every recorded single run reported, in at most half the single mean time and at most 1.25 times the single mean cost. A change to the catalogue or the drawing convention repeats both, the single-reviewer proof being followed in a new session. The recorded proof of one form stands for that form alone.

Out of scope for this section: the content of the catalogue; judging the layout, which the [layout review](#layout-review) does; and the content of any particular board's findings.

## Planning the layout

Do this before any footprint is placed on the board, once the schematic the three previous sections prove, provide for and review is finished. Its purpose is that the first layout is designed to the [Layout practice catalogue](#layout-practice-catalogue) rather than brought up to it by review: the board has a written floorplan, and a plan of how its layout meets every catalogue item that applies to it, before any part is placed. The rules section then writes every rule-kind item that applies into the board's rules before routing, and the [layout review](#layout-review) confirms a board drawn to this plan.

Keep the floorplan and the plan in a file named `layout-plan.md` in the board's own folder, beside its KiCad project.

### 1. Draw the floorplan

The floorplan divides the board into regions and places its connectors. Give it a region table with exactly these four rows:

| Region | Bounds | What it holds | Parts |
|---|---|---|---|

- **Region** is one of `mains`, `low voltage`, `analog sensing` and `digital`. The mains region holds every mains-referenced part and its copper; low voltage holds the low-voltage supplies, their regulators and the load drive stages; analog sensing holds every sensing front end, and any converter of its own part that the front ends feed; digital holds the controller and the logic it drives.
- **Bounds** gives the region's extent in board coordinates, in millimetres, as the rectangles `(x1, y1)–(x2, y2)` that make it up, corner to opposite corner, separated by commas. Board coordinates are those KiCad's board editor shows and the layout review views state in their captions. Regions do not overlap.
- **What it holds** names the blocks of the schematic placed in the region, for example `load drive stages, Q3–Q6, R20–R27`.
- **Parts** lists the reference designator of every part the region holds, comma-separated and without ranges, for example `Q3, Q4, Q5, Q6, R20, R21`. A part that spans two regions, such as an isolator whose pins lie either side of the mains boundary, is listed in both. Every part in the schematic's netlist is listed in at least one region, its connectors, test points and mounting holes among them, and every footprint on the board, mounting holes, fiducials and logos among them, is a part drawn on the schematic, as the pre-order check's schematic parity already requires of a board ([Designing for bring-up and a second spin](#designing-for-bring-up-and-a-second-spin)). KiCad's parity check passes over a footprint marked board-only, so the placement command's report is what catches one: a footprint the schematic does not carry is listed in no region, and the command reports it outside, which no chosen placement may hold. A symbol marked excluded from the board is absent from the netlist in the schematic tool's native format, which the planning cross-checks below read, as it is shown to be on a copy of a repository schematic exported with `kicad-cli sch export netlist`; it is not a part for the floorplan and is listed in no region, and listing it fails the second cross-check below. The [placement](#placement) command reads each region's bounds and parts from this column, and measures every part against the regions that list it.

A board that carries no mains records its mains region as `none`: a board whose schematic carries no mains-referenced net, which the rules section therefore declares `MAINS` `none` (step 2 there), writes `none: the board carries no mains` in Bounds. A board whose schematic carries no circuit of one of the other three kinds writes `none` in Bounds with what the schematic lacks, for example `none: the schematic carries no sensing front end`. A region recorded as `none` holds no part, and writes `none` in Parts.

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
- For an item that applies, the last column says how the layout will meet it, naming the regions of the floorplan, the parts by reference designator and the nets by name that it binds, closely enough that a failure the layout review finds against the item can be traced either to this row, as a plan the layout did not follow or a plan that was not enough, or to the item itself. A `yes` row meets each clause of the item's *Passes* for every part it binds, not for the first part alone: where the item states how a part is joined or placed, such as where a supply enters a capacitor's pad or that two capacitors sit side by side, the row states it for each part it names, because step 3 checks only that the parts a row names exist. For example, for `DECOUPLE-1`: `C12 and C13 at U4 pins 7 and 20, each within its own crop, C13 (100 nF) nearest pin 20, supply entering through each capacitor's pad; no via between capacitor and pin`. For a rule-kind item, it names the rules it puts in the board's rules table, with the board's own class names and the record each figure will be read from. A row that names a supply path names every branch that leaves the path for another part, and the layer and the place each branch leaves it at, so that a branch such as the feed to a status LED's resistor is planned against the items that bear on the path it taps, `DECOUPLE-1` and `DECOUPLE-6` among them. Where a path or branch has to cross another net's pour or track, the row names the layer it crosses on and the vias it takes there, rather than stating that it stays on the layer it starts on.
- For an item that does not apply, the last column gives the reason against the item's condition, stating what the schematic lacks, for example `no crystal or ceramic resonator in the schematic` for `CLOCK-1`.

Below the plan table, keep a table of the board's own items: practice this board must meet that no catalogue item states, such as a keep-out a part's datasheet asks for around it. Write each in the catalogue's item form ([How an item is read](#how-an-item-is-read)), one row per item, with how the layout will meet it:

| Item | Applies when | Asks | Passes | Fails, as the views show it | Judged on | Kind | Severity | Source | How the layout meets it |
|---|---|---|---|---|---|---|---|---|---|

- **Item** is `BOARD-<n>`, numbered from 1 in the order the items are written. Like a catalogue identifier, it is never renumbered and never reused.
- The columns from **Applies when** to **Source** are filled as the catalogue's fields are. Where the item comes from what this board must do rather than from published practice, its **Source** may name the requirement the board serves or the machine's record it comes from, by its role, in place of a published document. A rule-kind item's rules are carried into the board's rules table as a catalogue item's are ([Rules before routing](#rules-before-routing), step 1).
- **How the layout meets it** is written as a `yes` row of the plan table is, naming the regions, parts and nets it binds.

A board with no items of its own writes `none` in the Item column of the table's one row. The catalogue and these items together are the checklist the [layout review](#layout-review) judges the board against, and the table as committed before placement is that checklist's baseline. After that commit the table is only added to: no baseline row is removed, and none of its fields from Applies when to Source is changed. An item a review of the board adds later is appended below the others, its Source naming that review; it is judged from the review's next round on and is not part of the baseline. An item that is withdrawn keeps its row, marked withdrawn, as a catalogue item does.

Amended after hardware/proof/review-proof/layout-review.md, round 1, finding 1.3.
Amended after hardware/proof/method-proof/layout-review.md, round 1, finding 1.2.
Amended after hardware/proof/method-proof/layout-review.md, round 1, finding 1.5.

### 3. Commit the floorplan and plan before placement

Commit `layout-plan.md` before the first commit that places a footprint on the board. It is judged as it stood in the commit before placement, on the branch as pushed and in the checkout step 4 of [Proving value-critical circuits before layout](#proving-value-critical-circuits-before-layout) makes, found the same way, with `layout-plan.md` in place of `circuit-proof.md`. There, export the schematic's netlist in KiCad's own format, `kicad-cli sch export netlist --output <work folder>/check.net <board>.kicad_sch`, and cross-check the plan against it, the schematic and the catalogue in the checkout's own copy of this document, `docs/board-design-method.md`, rather than taking its word:

- the region table has its four rows, each with bounds or a `none` the schematic bears out: the mains region is `none` exactly when the schematic carries no mains-referenced net, and no two regions' rectangles overlap;
- every part in the netlist is listed in the Parts column of at least one region, and every reference that column lists is a part in the netlist, written once in its region, comma-separated, with no range; a region recorded as `none` lists none; a symbol marked excluded from the board is not in the netlist, so a region that lists one fails this cross-check, and the placement command's stop on a listed part that is not on the board never meets one;
- every connector, terminal or header in the netlist, test points aside, has exactly one row in the connector table, with an edge and a position, and the table names no other part;
- the plan table has exactly one row for every item of the catalogue as it stood in that commit, and names no other;
- each row marked `no` gives a reason against the item's *Applies when* that the schematic bears out, so no item whose condition the schematic meets is marked `no`;
- each row marked `yes` says how the layout meets the item, names at least one region, part or net it binds, and each region, part and net it names is one the floorplan or the netlist holds;
- each `yes` row whose clause binds every pad or part of a kind, such as a via at each ground pad of an integrated circuit or two vias beside each decoupling capacitor, names every pad or part of that kind the netlist holds, since a promise made for each and kept for some is the shortfall a review finds;
- the board's own items table is there, either with its one `none` row or with a row for each item, each identifier `BOARD-<n>` used once, every column filled as step 2 says, each *Applies when* one the schematic meets, and each How the layout meets it naming at least one region, part or net, each one the floorplan or the netlist holds.

Until the first commit that places a footprint, a plan row may be amended in a commit of its own. The floorplan changes only by appending a part, as below.

A plan that is missing, incomplete or uncommitted in that checkout, or that fails a cross-check above, fails this step, however complete it is now. A part added to the schematic after placement is planned for, by amending the floorplan, which appends the part to its region's Parts and changes no bound, no other part and no other region, and every row whose item it bears on, and that change is committed before the part is placed. The history command that step 6 of [Placement](#placement) runs holds the floorplan the placement section is judged against to the floorplan in the commit before the first commit whose board holds a footprint, comparing the set of region names, each region's bounds and each region's parts; no other text in the table is compared, and allows no other difference than such an appended part, committed before its footprint first appears on the board and kept in the plan until then. Between the first footprint on the board and the first track, pour, arc or via committed, the floorplan can only gain appended parts, so a floorplan error found during placement, a bound that is wrong, a part in the wrong region or a region missing, has no in-place fix: the work restarts from a fresh branch, with the floorplan corrected and committed before any footprint is placed. A part added after the choice and before the first track, pour, arc or via is committed means recording a new candidate that includes it and recording the placement section again. After the first track, pour, arc or via is committed the recorded section is frozen, and the floorplan is held to the commit before the first placement only as it stood in the commit before that first copper, so a part appended to it after that copper is not compared: it is only planned, by amending the floorplan as above, and placed, and the recorded section is left as it is. A part appended before that first copper and placed after it is compared still: the plan in the commit before the one that places it must list it.

A plan item the finished layout does not meet is a finding at the [layout review](#layout-review).

Amended after hardware/proof/method-proof/layout-review.md, round 1, finding 1.4.

Out of scope for this section: the layout review itself, which [Layout review](#layout-review) describes, and producing the views it judges a board on, which [Layout review views](#layout-review-views) describes.

## Placement

Do this once the floorplan and plan are committed, and before any track, arc, via or pour is drawn. Its purpose is that the board's placement is chosen rather than arrived at. Neat routing follows from good placement: parts placed together leave connections that run short, side by side and seldom crossing, and a placement that leaves them long or crossing makes routing long and crossing however carefully it is drawn. So the board is placed more than one way, each placement is seen with its unrouted connections drawn and measured, each is judged against the catalogue items placement decides, and one is chosen on the record, while moving a part still costs only the move.

The **placement items** are the catalogue items whose *Judged on* names `placement`, and those of the board's own items in `layout-plan.md` whose *Judged on* names it: the items whose question is where a part sits, and `MAINS-2`, whose mains copper includes the pads placement puts down.

The **placement view** is what `task hw:placement` renders from the board's files: an image of the board's parts with each net's connections drawn straight between the pads they join, the shortest straight-line tree over the net's pad centres, and the floorplan's regions drawn and named over them, with the placement's measures written beside it as text and JSON: the connections' total length and each net's, the crossings between different nets' connections, and every part outside its regions. Its file names, its measures and what it refuses are in [`hardware/README.md`](../hardware/README.md#the-placement-view). It needs the same tools as the [layout review views](#layout-review-views).

### 1. Set the board-wide minimum track width and clearance

The placement view takes its resolution from the board's minimum track width and minimum clearance, as the layout review views do, so these two are set before placement; the rest of the rules wait for [Rules before routing](#rules-before-routing). With the board closed in every editor, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, write both into the project file, as `board.design_settings.rules.min_track_width` and `.min_clearance` in millimetres, each at the board manufacturer's stated limit, as catalogue item `MFG-1` asks. Write their two rows into the board's rules table, `design-rules.md`, laid out as step 1 of [Rules before routing](#rules-before-routing) gives it: each a board-wide minimum, set in Board Setup, its source the manufacturer's stated limits with the date of the capability page it was read from and `MFG-1`, and its Confirmed in effect the words step 1 gives a board-wide minimum. Commit the project file and the table.

### 2. Place the parts

Reopen the board, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, and place every footprint with Konnect's tools, in this order:

1. the parts that cannot move: each connector, terminal and header at the edge and position the connector table gives, each mounting hole, and the mains region's parts;
2. then the rest, within the floorplan, by the way signals flow from part to part and around each current loop: each part inside a region whose Parts lists it, the main integrated circuit of each block before the parts that serve it, and a part that serves one pin, such as a decoupling capacitor or a pull-up, beside that pin;
3. each part turned so its pins face the pins they join.

Save the board, with Konnect's `save_project`, and close it in every editor.

### 3. Make at least two candidate placements, each in its own commit

A **candidate** is one placement of every part, committed in a commit of its own before it is rendered. Commit the placement from step 2 as candidate 1, naming it in the commit message, for example `<board>: placement candidate 1`. Then reopen the board, place it another way, close it and commit it as candidate 2: another arrangement of a block, a part moved or turned to shorten or uncross its connections, or two blocks' places swapped within the floorplan. Make as many more as the judgement in step 5 calls for. No two candidates' layouts are the same. A candidate may start from an earlier one: with the board closed, restore that one's layout with `git checkout <commit> -- <board folder>/<board>.kicad_pcb`.

### 4. Render and measure each candidate from its commit

Render each candidate from its own commit, in a checkout of that commit outside the repository's working tree, so its view and measures are the commit's and nothing uncommitted reaches them. From the repository's root, with `<n>` the candidate's number:

```
git worktree add --detach <work folder>/<board>-candidate-<n> <commit>
(cd <work folder>/<board>-candidate-<n>/<board folder> && task hw:placement -- --board <board>.kicad_pcb --project <board>.kicad_pro --out <work folder>/<board>-placement-<n>)
git worktree remove <work folder>/<board>-candidate-<n>
```

The output folder is a working folder: it must be new or empty, and outside every design's folder. Never commit it: the images and measures are not committed, as the review views are not, since these commands render them again from the candidate's commit. Open every image the folder's `index.txt` lists, and read its `measures.txt`.

### 5. Judge each candidate against the placement items

For each candidate, give every placement item one verdict in a verdict table:

| Item | Verdict | Rests on | Why |
|---|---|---|---|

- **Item** is the item's identifier.
- **Verdict** is one of `pass`, `fail` or `not applicable`. An item is `not applicable` exactly when the plan table marks it `no`.
- **Rests on** cites each image of the placement view the verdict rests on, by the name the candidate's `index.txt` gives it, a tile's included, with the place on the board in the board coordinates its caption states, or `whole board`; and each line of `measures.txt` it cites.
- **Why**: for `fail`, what the view or the measures show wrong, and where; for `not applicable`, the plan row's reason.

At placement an item is judged on what placement decides: where each part sits, on which side, and which way it is turned. Where an item's Passes or Fails speaks of a track or a route, judge the connection the placement view draws in its place, the straight line between the pads the track will join. So a decoupling capacitor whose connection to its pin runs long, or crosses another net's, fails `DECOUPLE-1`, and `WORK-1` fails where connections run across the board, or cross, where moving, turning or swapping parts would keep them short and apart. A part the measures list as outside its regions fails `FLOOR-1`. `TEST-1` is judged here for its spacing from part bodies only, and at the layout review in full.

### 6. Choose one, and record the placement before any track, arc, via or pour

A candidate that leaves a part outside its floorplan regions, an `OUTSIDE` line naming a part in its `measures.txt`, is not chosen: make another that does not. Among the rest, the choice is a judgement on the item verdicts, with the measures cited as its grounds, and never a fixed weighting of the measures: a candidate that passes an item another fails is the better on that item, and its measures say by how much, for example a capacitor's connection to its pin 3 mm shorter, or two crossings fewer.

Record the placement in `layout-plan.md`, below the board's own items, in a section headed `## Placement`. Give each candidate a heading of its own, `### Candidate <n>`, and under it, in this order:

- **Commit**: the commit that holds it;
- **Renders**: the commands of step 4 that render its view from that commit, as they were run, so naming that commit;
- **Measures**: the `LENGTH`, `CROSSINGS` and `OUTSIDE` lines of its `measures.txt` that give the totals, and every `OUTSIDE` line naming a part, each on a line of its own exactly as `measures.txt` gives it, in a fenced code block below the field;
- its verdict table from step 5.

End the section with **Chosen**: the chosen candidate's number, and why it was chosen over each other candidate, citing the verdicts and the measures that decided it.

If the chosen candidate is not the last committed, restore its layout with the board closed, `git checkout <commit> -- <board folder>/<board>.kicad_pcb`. Commit the section, whole, with the board's design files as the chosen candidate holds them, before any track, arc, via or copper pour is drawn. What this step judges is the section as it stood in the commit before the first commit carrying a track, an arc, a via or a pour, as step 4 of [Proving value-critical circuits before layout](#proving-value-critical-circuits-before-layout) judges its record in the commit before placement, and the section is not changed after it: a section committed empty, or in part, and filled in after the first track does not pass.

Judge the record against the board and the repository rather than taking its word, with the history command. Once the section is committed, and before any track, arc, via or pour is drawn, run it from the board's folder, on the branch as pushed, fetched afresh with its whole history and checked out:

```
task hw:history -- --board <board>.kicad_pcb
```

It needs git and Python only, and refuses a board or `layout-plan.md` that differs from the checked-out commit, and a shallow clone, which lacks the commits the records cite. It reads every version of the board file the checked-out commit's history holds, finds the first commit carrying a track, an arc, a via or a copper pour, `<T>`, and judges the section as it stood in the commit before it, `<T>^`. A pour is a zone on a copper layer, one whose name ends in `.Cu`, that is not a rule area, an unfilled outline included; a rule area, a zone carrying a keepout, carries no net and is no copper, and a zone on a layer that is no copper is no pour. It also finds the first commit whose board holds a footprint, `<P>`, from the history alone and never from the section, and reads the plan in the commit before it, `<P>^`, the commit step 3 of [Planning the layout](#planning-the-layout) judges the plan in; it holds the floorplan in `<T>^` to the one in `<P>^`, comparing the set of region names, each region's bounds and each region's parts; no other text in the table is compared. While no commit carries copper, as at this step, it judges the section as the checked-out commit holds it, and its result line says `before first track`. Its report is described in [`hardware/README.md`](../hardware/README.md#the-placement-and-critical-routing-history). It must end with `RESULT | PASS`. Each `CHECK` line that says `FAIL` names what failed, and means:

- `first track`: a track, arc, via or pour in the repository's first commit, so nothing was committed before it; or copper first appearing on two separate lines of history, neither before the other, or in a merge commit none of whose parents carries any, so no one commit is the first; or a version of the board that cannot be read.
- `first placement`: a footprint in the repository's first commit, so no plan was committed before it; or footprints first appearing on two separate lines of history, or in a merge commit none of whose parents holds one, so no one commit is `<P>`; `<P>^` is not an ancestor of `<T>^`, so the plan was not committed before the section was judged; or no commit's board holds a footprint at all.
- `plan before placement`: `<P>^` holds no readable `layout-plan.md` floorplan, so the plan was not committed before placement, however complete it is now; or the floorplan in `<T>^` differs from the one in `<P>^` in what the command compares: the set of region names, each region's bounds and each region's parts; no other text in the table is compared. The one difference allowed is a reference appended to a region's parts, with no bound changed and no reference removed or moved between regions, and that fails too unless the plan in each commit just before the appended reference's footprint first appears lists it, in a commit after `<P>^`: a reference listed once, dropped, placed and listed again fails, and so does one listed in the commit that places it or after. A part added after placement began and before the first track, pour, arc or via is committed is amended into the plan before it is placed; a part appended in the commit that places it, or after, fails. A part appended to the plan only after that first copper is not compared: it is planned and placed, and the section is left as it is. A part appended before that first copper and placed after it is compared still, by the same rule: the plan in the commit before the one that places it must list it.
- `placement section`: the section is not in `<T>^`, holds no `### Candidate` heading there, or differs from the section now in a line that is not blank: it was committed empty or in part, or changed after the first track.
- `placement items`: `<T>^` names no placement item, in its copy of this document, `docs/board-design-method.md`, or its `layout-plan.md`, so there is nothing to judge the verdicts against.
- `candidates`: fewer than two candidates, or one number given to two.
- `candidate <n> commit`: the candidate names no commit; its commit is not in the repository, or not in the checked-out commit's history, which is what a squash, rebase or force-push leaves of a commit a record cites; it is `<T>` or not an ancestor of it, so it does not come before the first track; it does not hold the board; or its Renders does not name it.
- `candidate <n> measures`: a recorded line the candidate's commit does not measure, or a line it measures that is not recorded. The command measures each candidate's commit again with the placement command's own arithmetic, from that commit's board against the floorplan as `<T>^` holds it, or the checked-out commit before the first track, with the references the plan appended left out where that commit's board does not hold them, without KiCad, so a candidate measured against another floorplan, as one whose commit widens a region is, fails.
- `candidate <n> verdicts`: the verdict table has no row for a placement item, as `<T>^` holds the catalogue and the board's own items, or two, or a row for an item that is not one; a verdict other than `pass`, `fail` or `not applicable`; or a `not applicable` for an item the plan table does not mark `no`.
- `distinct candidates`: two candidates' commits place every part alike, each part's reference, position, angle and side the same and the same set of references on the board, so they are one placement, however their board files differ in a text label or an identifier; a differing set of references, or one part moved, turned or put on the other side, makes them distinct.
- `chosen`: no Chosen, or one naming a candidate the section does not record; or the chosen candidate leaves a part outside its regions, measured from its commit's board against the floorplan in `<T>^`, as `candidate <n> measures` measures it.
- `parts at first track`, or `parts at HEAD` before the first track: a footprint whose reference, position, angle or side in `<T>`, or in the checked-out commit before the first track, is not the chosen candidate's, so a part was moved after the choice or in the commit drawing the first track.

Step 4 and step 8 of [Routing](#routing-critical-nets-by-hand-and-locked-then-the-rest) run the command again, once tracks are drawn, and there it judges this section against `<T>`.

The command reads the branch's own history, and the records cite its commits, so a board's branch merges into the main line without rewriting that history: by a merge commit, never squashed, rebased or force-pushed. The command run on the main line after the merge then judges the same commits. A commit a rewrite left out of the history fails as not in it, rather than being taken on the record's word.

The command judges the record's shape and order, not its judgement: whether each verdict is right and whether the candidates are genuinely different arrangements stay with the designer and the reviewer, and a part moved after the first track is judged by the [layout review](#layout-review).

A placement the command fails, or that cannot be judged because it refuses the checkout, fails this step: among them a placement with fewer than two candidates, a placement item left without a verdict, a chosen candidate with a part outside its regions or a footprint the first track's commit does not hold where it placed it, and a section that, in the commit before the first track, is missing, or differs from the section now.

Out of scope for this section: the placement command itself, which [`hardware/README.md`](../hardware/README.md#the-placement-view) describes, and routing.

## Rules before routing

Do this before any track is routed. Its purpose is that every rule the board is routed and checked against is written down, traceable to where its figure comes from, and that the table says which of them KiCad confirms on the board itself, which KiCad's rule check enforces before the board is ordered, which the pre-order check measures itself, and which, a net class's track width and via sizes, are only the defaults routing starts from.

Close the board in every editor before writing anything in this section, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, and keep it closed until step 4. An editor holding the board keeps its own copy of the project file and writes that copy over the file when it quits: a text variable and a net class pattern written to the project file while the board editor held the board open were measured to be gone after it quit. Konnect's tools that write net classes write the project file, so they are no exception.

### 1. Write every rule and net class down, with its figure and source

Keep a table in a file named `design-rules.md` in the board's own folder, beside its KiCad project. Give it one row for every design rule and every net class the board uses. The board-wide minimum track width and minimum clearance, and their two rows, were written before placement ([Placement](#placement), step 1), because the placement view takes its resolution from them; every other row is written here:

| Rule or net class | Figure | Where it is set in KiCad | Source of the figure | Confirmed in effect |
|---|---|---|---|---|

- **Design rules** are the board-wide minimums (clearance, track width, via diameter and drill, hole size, annular ring, hole-to-hole, copper-to-edge, silkscreen), each custom rule in the board's rules file, every measured rule's figure, every check of KiCad's own that a rule-kind item names in place of a rule, and every net class's own clearance, track width and via sizes.
- **Source** says where the figure comes from, for example: the machine's constraints record (name the figure in it); a requirement the board serves (name the requirement); the manufacturer's stated limits (name the manufacturer and the date of the capability page the figure was read from); the separation basis record; the circuit-proof record, for a width, a copper pour's connection width or a hole a circuit's proof assumed (name the circuit's row); a rule-kind item of the [Layout practice catalogue](#layout-practice-catalogue) (name the item by its identifier, and, where the item names its figure by its role, also the record the board's figure was read from, as in `POWER-1; the machine's constraints record, the load supply's continuous current`); or a finding from a layout review that became a rule (name the review). "Default", "typical" or "what KiCad had" is not a source.
- **Carried rules.** Every rule-kind item of the catalogue that applies to the board, by its *Applies when* and as the plan in `layout-plan.md` records it, and every rule-kind item among the board's own items there, puts each rule it gives into this table, one row per rule, with the item as its source. Write each rule in the form the item gives it: a board-wide minimum, a net class's figure, a custom rule, KiCad's own check where the item names one in place of a rule, a measured rule's figure, or a record figure. Where the item names a net class by its role, such as `<power class>`, write the board's own name for that class in its place; the `Mains` class is named as it is. Where the item names a figure by its role, read the figure from the record the role names. A board that has more than one class in a role carries the rule once for each. An applicable rule-kind item whose rules are missing from this table, or from the board, fails this step.
- **Where it is set in KiCad** names, for a measured rule, the project text variable that holds its figure, for example `WORK_DETOUR_RATIO`, written into the project file with the board closed as `MAINS` is (step 2). Write the figure as a plain decimal number, in the unit the item gives, with no unit after it: a missing figure, or one written any other way, fails the pre-order check, naming it. For a measured rule whose figure is an inherent zero, with no project text variable (`DECOUPLE-6`, `MFG-7` and `MFG-9`; `MFG-10`'s figure is its own count of three), it names the pre-order check's rule by the violation name the item gives and says it reads no project text variable, for example `The pre-order check's decoupling_via rule, which reads no project text variable`. For KiCad's own check that an item names in place of a rule, it names that check, for example `KiCad's via_dangling check, reported unaided`. For a record figure (`SENSE-6`) it names the key of the board rules record that holds the figure, here `sensing.clearance_mm` of `board-rules.yaml`, and the net classes the record names.
- **Confirmed in effect** says, for each kind of row, what stands behind it, and nothing else may be written there:
  - a **custom rule** in the board's rules file: that KiCad loaded the rules file, from step 3's output. A rule's figure written with a unit KiCad does not take for its constraint, such as `deg` after a `track_angle` minimum, makes KiCad drop the whole rules file without a word, every rule in it with it; step 3 and the pre-order check both catch that, by a marker rule that fires only when KiCad loaded the file;
  - a **measured rule**: the pre-order check's `FIGURE` line for it, which states the figure the check read from the project file, quoted from the check's report. An inherent-zero rule's row has the rule's name in the first column, the Figure `none`, the Source of the figure the item and that its figure is the item's own, and the `FIGURE` line quoted here, whose source field reads `none, inherent zero`. The item's *Judged on* names this row, and the review reads it against the report's line;
  - a **record figure**: the pre-order check's `FIGURE` line for it, which states the figure the check read from the board rules record, quoted from the check's report; the record is committed with the board, so the row and the record state the one figure. The item's *Judged on* names this row, and the review reads it against the report's line;
  - **KiCad's own check**, named in place of a rule: `reported unaided by the layout rule check in the pre-order check`;
  - a **net class**: the nets step 3 lists for it;
  - a **board-wide minimum**, and a **net class's own clearance**, set in Board Setup: `not confirmed by step 3; enforced by the layout rule check in the pre-order check`. Step 3 cannot read these figures, so they are never marked confirmed. They stand on the figure and source written in the row. KiCad's layout rule check reports copper, holes and silkscreen that break any of them, as an error, or as a warning for silkscreen clipped by the board edge, and the pre-order check (step 8 of routing) fails the board on either;
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

The pre-order check requires the figure of every measured rule on every board, whether or not that rule's catalogue item applies to it, so `BARRIER_COPPER_MM2` is set on a board that declares no mains. Where `MAINS-5` does not apply, set it to `0`, which the check accepts, and say in the row's source that `MAINS-5` does not apply to the board.

Set every ERC and DRC check in the project file's severities to `error` or `warning`: the pre-order check fails a check set to `ignore`, even where `ignore` is KiCad's own default for it ([`hardware/README.md`](../hardware/README.md), *What a design must satisfy*).

A rule with no stated source fails this step. Give it a source or remove it.

### 2. Declare whether the board carries mains

Every board declares this in its project text variable `MAINS`, set to exactly `present` or `none`: in the project file, `"text_variables": {"MAINS": "present"}`. Write it into the project file, with the board closed in every editor. A board with no mains declaration fails this step, and the pre-order check fails it too.

**A board that declares `none`** puts no net in the `Mains` net class.

**A board that declares `present`**:

- assigns every mains-referenced net to the net class named exactly `Mains`. These are the nets at mains potential and those referenced to it, such as a switched live or the low side of a heater. You can assign a net in the schematic with a net class directive, or in the project's net classes by assignment or by pattern (Konnect's `create_netclass` and `assign_net_to_class` write them, and work with the board closed);
- declares, in the project text variable `MAINS_ENTRY` set to exactly `present` or `none`, whether it carries nets ahead of the entry fuse, and assigns each such net to the net class `Mains_Entry` as well as `Mains` when it declares `present`; a board that declares `none` puts no net in `Mains_Entry`. The pre-order check holds those nets to the larger creepage the separation basis record signs for ahead of the fuse, and holds every pair of `Mains`-class items on different nets to the record's `mains_to_mains` figures, whatever the board's own rules say;
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

The nets that decide whether a board works are never left to an automatic router. They are routed deliberately to their stated rules and locked. Automated routing is then run only one way: KiCad's exporter, the external router from its command line, then KiCad's importer (step 6). It places only what is left unrouted, and may not move a locked item. Locking is done by the board tooling's lock command on the closed board file (step 3). A check in the board tooling, never a comparison by hand and never the router's own report, confirms afterwards that nothing locked was moved and nothing was added to a critical net. Only the board's own tracks, arcs, vias and zones are locked and recorded; a copper zone inside a footprint is not covered.

### 1. Put every critical net in a named critical class

The critical classes include at least the board's **power**, **decoupling**, **ground**, **mains** and **sensing** paths. Assign every net in those categories to a named net class in step 1 of the rules section, for example `Power`, `Decoupling`, `Ground`, `Mains` and `Sensing`. The names are the board's own, and the mains class is always `Mains`. Every critical class is named to the lock and record steps below, which protect only the classes they are given. A critical net left in the `Default` class therefore fails this step: its copper would not be protected. The board tooling refuses what it can read: a named class holding no net, and, on a board that declares mains, a set of classes that leaves out `Mains`. Which other nets are critical it cannot read, so that stays your judgement.

Which further nets of a particular board are critical is that board's own design work.

### 2. Route every critical net by hand, to its class's rules

On the reopened board, route every net in every critical class yourself, to the rules its class states: every track, arc and via, with Konnect's routing tools. A copper zone on a critical net, such as a ground or mains pour, is deliberate routing like a track, so draw it yourself too. Draw each net's pour as one zone on each layer it covers, and extend it over the centre of every pad it joins. Observed with Freerouting 2.5.0 on one board and not reproduced: the router read overlapping zones of one net as separate planes, and added a stub to a pad whose centre no zone covered. Do this in the session that loaded Konnect's routing toolset, not in a subagent, which would not see it. Look at a rendered view of the board to judge the result.

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

### 4. Check the critical routing against the catalogue, before the router runs

The router routes everything else around the critical nets, so their routes are judged now, while changing one costs only that net's re-route. With the board still closed, render the review views with `task hw:views`, as [Layout review views](#layout-review-views) describes, naming the classes step 3 locked, into a working folder of their own, never committed, which both tasks refuse inside the board's folder or inside any folder that holds a KiCad project file, as the record command in step 5 does, and refuse too when it already holds files. The placement view is not rendered here, since this checkpoint judges routing, not where the parts sit: render it too, with `task hw:placement` into a folder of its own beside them as that section describes, only when an item that bears on the critical nets names `placement` in its *Judged on*.

Then judge every item of the [layout review](#layout-review)'s checklist that bears on the critical nets, workmanship items included. An item bears on them when what its *Asks* asks of the board is decided, wholly or in part, by copper a net in a critical class carries: its tracks, arcs, vias or zones, or the way its routes run. Judge each over the critical nets' copper only, since the rest is not yet routed:

- a **judgement-kind** item on the views its *Judged on* names, as step 2 of the layout review judges one;
- a **rule-kind** item on its rows in the rules table alone, `design-rules.md`: the row of every rule the item gives, each present with a figure the item's own figure and source bear out. The pre-order check fails a board that is not fully routed, so it is not run here, and the verdict's Why says that the item's measured half is judged by the pre-order check that step 8 runs after the router.

Record the verdicts in `layout-plan.md`, below the placement section, in a section headed `## Critical routing`, as its first pass, under the heading `### Pass 1`. The section holds nothing but its passes, numbered from 1 and only ever appended, as the layout review's rounds are: a re-route the layout review calls for once the router has run appends the next pass ([Layout review](#layout-review), step 7), and a pass the router has run after is never changed. A pass the router has not run after is not appended to either: step 7 of this section sends the work back to step 2 when a comparison fails, and the pass that has no router commit is then rewritten in place. Each pass is written in the form the layout review records its verdicts (step 1 and step 2 of [Layout review](#layout-review)):

- **Board judged**: for pass 1, the commit holding the board with its critical nets routed and locked, whose layout holds at least one track, arc or via and every one of them locked; for a later pass, the commit holding the re-routed board, made after the previous pass's router commit;
- **Views**: the `task hw:views` command as it was run, and the `task hw:placement` command as it was run when an item that bears on the critical nets names `placement` and so the placement view was rendered, or else that the placement view was not rendered;
- the verdict table, `| Item | Kind | Severity | Verdict | Rests on | Why |`, with one row for every item that bears on the critical nets;
- below the table, every other item of the checklist, each on a line of its own, `` - `<item>`: `` and the reason it bears on no critical net.

A `fail` is put right before the router runs: re-route the net as step 3 says, lock it again and only then commit, render the views again and judge the item again, writing the verdict reached in the same row after the `fail`, with the commit that put it right, as `fail, then pass at <commit>`. A `cannot judge` is resolved the same way the layout review resolves one, written `cannot judge, then <verdict>`, and a verdict reached that is a `fail` is put right in turn. Commit the section before the router runs (step 6).

**This check may be judged by unit instead of by one reviewer.** That is a way of carrying out this step, and it changes none of it. `task hw:review-run -- --caller critical_routing` ([`hardware/README.md`](../hardware/README.md#the-critical-routing-check-by-unit)) judges the pass with one reviewer for each area of the [Layout practice catalogue](#layout-practice-catalogue) and one for the board's own items (areas whose verdicts depend on one another's findings are judged together), each reviewer a fork of one shared context that holds this section, the layout review sections, the whole catalogue, the plan, the records, the pass's fields, the views and a layout-facts extract and judges nothing, with two reviewers of each so that a fail either raises stands. Each reviewer decides which of the items of its unit bear on the critical nets, judges those, and gives every other item `bears on no critical net` with the reason, and the command merges what they return, with no model, into one pass in which every item of the checklist has one verdict row in the table or one line in the list below it; an item one reviewer judged as bearing is judged. The pass's own fields, its number, the commit judged and the views, come from whoever runs the check: they are given to the command in the review folder it reads, which `task hw:review-folder -- --review critical-routing` writes, since the merge has no model to write them. The merge fails a pass in which any of those fields is missing or malformed, in which an item has no verdict row or has two, in which a verdict row is for an item that is not on the checklist, in which a `cannot judge` is left, in which a finding is of an item that does not fail, in which a `fail` cites another item's finding, in which a finding's what and where is empty, in which an item that bears on no critical net has no reason, or in which no item bears on a critical net, and it names the item. It renders a `fail` as a plain `fail`, with the reviewer's finding written into its Why, for the designer to put right in the row before the router runs as above. A `cannot judge` is resolved as the layout review resolves one (step 2 of [Layout review](#layout-review)): whoever runs the check renders the view its Why asks for, or writes the figure into a text file, adds it to the review folder with the folder command's add-view or add-document mode and runs that unit again, and the row is written `cannot judge, then <verdict>`; a `cannot judge` resolved to `bears on no critical net` is written as its list line, which has no verdict cell, with the prefix `Cannot judge: <why>` at the start of its reason. The merged pass is written as a file that whoever runs the check appends below the section's earlier passes, never in place of one the router has run after, and commits before the router runs. Judging an item again after its re-route is this check of one item, which a single reviewer may do, and judging the whole pass with one reviewer, a person or an agent session that does not use the command, stays valid; every pass already recorded stands. The fanned-out form is relied on only once its proof is recorded, and until then this step is carried out with one reviewer. Repeat the proof after changing this step, in the form that changed: a change to the step as one reviewer follows it repeats the single-reviewer form, and a change to how the pass is judged by unit, to the critical-routing caller or to the review folder it reads repeats the fanned-out form, each form's recorded proof standing for that form alone.

Judge the record against the repository rather than taking its word, with the history command [Placement](#placement) step 6 runs. Once the section is committed, run it from the board's folder, on the branch as pushed, fetched afresh with its whole history and checked out:

```
task hw:history -- --board <board>.kicad_pcb
```

It judges the placement section again, now against the first track, and every pass of this section. For each pass it finds the router's commit, `<R>`: the first commit on the line of history from the pass's Board judged commit, `<B>`, that adds or changes a track, arc or via that is not locked, compared with `<B>`. It judges the pass as it stood in `<R>^`, the commit before the router's. Before the router has run after the last pass, that pass has no `<R>`: it is judged as the checked-out commit holds it, and the result line says `router not yet run`, as it does at this step. Step 8 runs the command again once the router's commit is made, with `--routed`, and that run is the one that decides this step.

Finding `<R>` this way rests on two things this method does, which the command cannot see: every critical item is locked before the commit that holds it is a Board judged commit or follows one (step 3, and the re-route of a `fail` above), and the router leaves its copper unlocked, since step 6 runs it on the exported board and step 7 compares only the recorded critical copper. A router, or any step, that locked its own copper would read as the router not having run. A net routed by hand and committed before it was locked comes before `<B>`, so it is never taken for the router's.

The command must end with `RESULT | PASS`. Each `CHECK` line that says `FAIL` names what failed, and means:

- `critical routing section`: the board carries copper, a track, an arc, a via or a pour, or `--routed` is given, and the section is missing; or it holds anything before its first pass, a heading that is not `### Pass <n>`, or passes not numbered from 1 in order, as removing or renumbering a pass leaves them.
- `pass <k> board judged`: the pass names no Board judged or no Views; its Board judged commit is not in the repository, or not in the checked-out commit's history, as a commit on another branch, or one a squash, rebase or force-push left behind, is not; for pass 1, the commit's layout holds no track, arc or via, or one not locked, as a commit named after the router ran does; for a later pass, the commit does not follow the previous pass's router commit, or a commit between the two adds or changes a track, arc or via that is not locked, as running the router again before the pass was judged does, or as a merge bringing such copper in from another line of history does. Removing the router's copper between them passes.
- `pass <k> before router`: the pass is not in `<R>^`, or differs from it in a line that is not blank, so it was written or changed after the router ran; the router's copper first appears on two separate lines of history, or in a merge commit, so no one commit is `<R>`; a pass other than the last has no router commit; or, with `--routed`, the last pass has none, so the router's copper is not committed, or is locked.
- `pass <k> verdicts`: the pass has no verdict table; an item of the checklist, as `<R>^` holds the catalogue and the board's own items, or the checked-out commit for a pass with no `<R>`, is neither in the table nor in the list below it, or is in them twice; the pass names an item that is not on the checklist; a verdict is not one of `pass`, `fail`, `not applicable` and `cannot judge`, or a later verdict is not written `, then <verdict> at <commit>`; a `fail` has no later verdict with the commit that put it right, or a `cannot judge` no later verdict; or a commit a row cites is not after the Board judged commit, or is not before the router's.

The command judges the record's shape and order, not its judgement: whether each verdict is right, whether an item bears on the critical nets or not, and whether each rule-kind row rests on the rules table's rows and says its measured half is judged after the router, stay with the designer and the reviewer. It reads the branch's own history, so the branch merges without rewriting it, as [Placement](#placement) step 6 says.

A section the command fails, or that cannot be judged because it refuses the checkout, fails this step: among them a section that, in the commit before the router's, is missing, or differs from the section now, a Board judged commit whose layout holds no track, arc or via, or one not locked, an item that bears on the critical nets left without a verdict, and a `fail` not put right before the router runs.

### 5. Record the critical-class copper, immediately before export

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

### 6. Export, route the rest externally, import

Before exporting, keep copies of the board file and the project file as they stand, so the board can be restored if step 7 fails: in the work folder, under names that do not end in `.kicad_pcb` or `.kicad_pro` (for example `<board>.kicad_pro.before`), since a folder holding a project file is a design's folder, where the record is refused. Or commit both.

KiCad 10's `kicad-cli` has no Specctra command. The exporter and importer are reached through KiCad's bundled Python, with these commands run from the board's folder. Do not substitute another tool's Specctra export: Konnect's own routing export, for one, refuses boards with rounded-rectangle pads.

The exporter writes every rule area, whatever its keepout flags, as a keepout on each of its layers, and a router cannot route inside one. `FLOOR-4` requires a rule area at the bounds of each floorplan region, so on a board of one region a rule area covers the whole board, and the router has nowhere to route (measured with Freerouting 2.5.0: with that rule area exported it added no track). So export the board with its rule areas removed in memory, saving nothing:

```
"$KICAD_PYTHON" -c "import pcbnew; b = pcbnew.LoadBoard('<board>.kicad_pcb'); [b.Remove(z) for z in [z for z in b.Zones() if z.GetIsRuleArea()]]; assert pcbnew.ExportSpecctraDSN(b, '<work folder>/<board>.dsn')"
```

Only the exported copy lacks the rule areas: the import below loads the board file itself, with them, and the router's session adds tracks only, so the pre-order check still holds the routed board to every rule area.

Locked items are exported as fixed (`(type fix)` in the `.dsn` file). A copper zone is exported as a `(plane …)`, which the router connects to and does not treat as an obstacle.

Run the router from its command line, with no window:

```
java -jar "$FREEROUTING_JAR" -de <work folder>/<board>.dsn -do <work folder>/<board>.ses --router.autorouter.max_passes=20 --gui.enabled=false
```

Import the router's session into the board and save it:

```
"$KICAD_PYTHON" -c "import pcbnew; b = pcbnew.LoadBoard('<board>.kicad_pcb'); assert pcbnew.ImportSpecctraSES(b, '<work folder>/<board>.ses'); b.Save('<board>.kicad_pcb')"
```

Saving this way also rewrites the project file, with KiCad's defaults filled in for settings it did not hold before. Review that change against the copy kept before export, as you would any other.

If nets stay unrouted, read the `.dsn` before changing the board: a `(keepout …)` block is an area the router cannot enter, while `(type fix)` items and `(plane …)` conductors are not. Count them with `grep -c '(keepout' <work folder>/<board>.dsn`; a keepout shaped as a circle, inside a part's `(image …)`, is the part's own hole, and a polygon keepout in the `(structure …)` section is a rule area. Judge the result by KiCad's own unconnected-item check on the imported board, not by the router's report: the router can report an unrouted connection that a locked track already joins.

The router's own report, for example `0 unrouted and 0 violations`, is not evidence of anything. Neither the router nor the importer is relied on to leave locked copper alone.

Observed with Freerouting 2.5.0 on one board and not reproduced: the session file it writes rounded pad centres to its own grid, so a pad whose centre lay off that grid got a router track shorter than 1 mm at its end, which `WORK-5` reports as a `track_segment_length` violation, even where a locked track ends exactly on the pad's centre. Read each `track_segment_length` line that `task hw:verify` reports after the import against this before changing anything. A pad's position is moved only by a placement change, made as step 7 of the [layout review](#layout-review) makes one.

### 7. Compare the imported board with the record

From the board's folder, run:

```
task hw:copper-compare -- --board <board>.kicad_pcb --project <board>.kicad_pro --record <work folder>/<board>.record.json
```

With the board still closed, give the same board, its own project file, and the record taken of that board in step 5. This fails, naming each item, when:
- a recorded item is missing;
- a recorded item is no longer locked;
- a recorded item is changed in any recorded property, with each changed property given as old → new;
- a critical-class net carries a track, arc, via or zone that the record does not hold;
- a critical class the record names is no longer defined by the design;
- `MAINS` is not exactly `present` or `none`, or is `present` and the record's classes leave out `Mains`.

The critical nets at comparison are every net the record names and every net the critical classes hold now, so a net that left its class after recording, for example because the import rewrote the project file, is still checked. An added item identical to a recorded one is still reported as added. Copper on nets outside both is the router's, and is ignored. A record taken of another board, a project file that is not the board's own, or a board KiCad's lock file shows open, fails the comparison without comparing anything. A failure fails this step whatever the router or the importer reported. Restore the board as it was before export, correct the cause, and repeat from step 2. The repeat rewrites in place the pass that has no router commit, the last, and appends no further pass: only the last pass may have no router commit, so a pass appended after one that has no router commit fails `pass <k> before router`, where <k> is that earlier pass, the one with no router commit, and a pass the router has run after is never changed.

A board on which any critical-class net was placed by the router fails this step.

### 8. Run the board's own rule checks, then reopen the board

Run the pre-order check, which runs KiCad's own electrical and layout rule checks with zones refilled:

```
task hw:verify
```

It checks only designs git tracks (`git add` is enough), as `hardware/README.md` explains. It must pass. A router's or editor's "no violations" is never accepted in its place.

When it reports a violation on copper the router placed, on a net outside every critical class, remove that net's router copper and draw the net by hand with Konnect's routing tools, leaving it unlocked, then run this step's check again. If the violation comes from where the parts sit, such as a net made long or looping by the distance between its pads, change the placement as step 7 of the [layout review](#layout-review) says and repeat from step 2. A violation on the copper of a critical-class net is not repaired here: restore the board as it was before export, as step 7 says, correct that net by a re-route (step 3), and repeat from step 2.

Then commit the board's design files as the import left them: this is the router's commit. Push the branch, fetch it afresh with its whole history and check it out, and run the history command from the board's folder, as step 4 does:

```
task hw:history -- --board <board>.kicad_pcb --routed
```

This is its run that decides both the placement section ([Placement](#placement), step 6) and the critical routing section (step 4). It must end with `RESULT | PASS`. With `--routed`, a last pass with no router commit fails `pass <k> before router` rather than passing as `router not yet run`: the router's copper is not committed, or is locked, and no pass has been shown to come before the router. A `FAIL` means what step 6 of [Placement](#placement) and step 4 here say it means. Reopen the board in the editor, as [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes, only after these checks and the comparison in step 7 have run, and only to continue work on it.

Out of scope for this step: judging the quality of the layout, which is the [layout review](#layout-review) that follows.

## Layout review

Do this once routing is finished and the pre-order check passes the board, and before the board is ordered. Its purpose is to confirm that the finished layout is the one the board was planned to have. The board was designed to the [Layout practice catalogue](#layout-practice-catalogue) when its layout was planned; the review is how that is shown, not how the board gets good. Every item of the checklist gets a recorded verdict in every full round, only a full round closes the review, every finding stays open until something stated here closes it, every finding that can be written as a rule becomes one so later boards are checked for it without anyone remembering it, and a failure the plan should have prevented is corrected at the planning that let it through.

The **checklist** is every item of the catalogue together with the board's own items in `layout-plan.md` (step 2 of [Planning the layout](#planning-the-layout)). Its baseline is that file as committed before placement, which step 3 there judges.

The **reviewer** is an agent session, or a person, that did not design the board. It works from these alone: the board's design files, the checklist, the [layout review views](#layout-review-views) rendered from the board, the placement view among them, the pre-order check's report, and the board's committed `layout-plan.md`. For a rule-kind item whose figure rests on a published document, such as `MFG-1`'s manufacturer's capability page, it also works from that document as the board's rules table names it, fetched at the address the row gives, or found from the manufacturer or publisher the row names where it gives none, and judges the figure against it. A document it cannot fetch makes the item `cannot judge`. It never works from the designer's reasoning, session or notes.

Keep the review in one file named `layout-review.md` in the board's own folder, beside its KiCad project. It holds every round of the review, the first and every repeat, each under its own heading, `## Round <n>`, numbered from 1, with its verdicts, its findings and their closures. A round holds its opening fields (step 1), then `### Verdicts` with the verdict table (step 2), then `### Plan and free pass` in prose where it records the comparison with the plan and the free pass (step 3), then `### Findings` with the findings table (step 4), or the line `This round raises no finding.` in its place, and nothing else: the completion checks below read exactly these parts. Commit the record at the end of each round, once its verdicts and findings are written and before any change to the board they call for, never part-way through a round, and again with every change that closes a finding. What a round recorded at its end, its opening lines, its verdict table and each finding's number, Raised by, Severity and What and where, is never changed afterwards; only Rule, Added as, Planning shortfall and Closed by are filled in later, as steps 5 to 7 complete them. So round 1 stays the board's first review. A review is cited, wherever an item, a rule or a commit names it, by the record's path from the repository's root and the round, and a finding by its number as well, for example `<board folder>/layout-review.md, round 1, finding 1.3`.

A round may be judged by unit instead of by one reviewer. That is a way of carrying out the steps below, and it changes none of them. `task hw:review-run -- --caller layout` ([`hardware/README.md`](../hardware/README.md#the-layout-review-by-unit)) judges a round with one reviewer for each area of the catalogue, one for the board's own items and one for the comparison with the plan and the free pass (areas whose verdicts depend on one another's findings are judged together), each reviewer a fork of one shared context that holds the method's layout review sections, the whole catalogue, the plan, the records, the round's fields, the views and a layout-facts extract and judges nothing, with two reviewers of each so that a fail either raises stands, and merges what they return, with no model, into one round of the one record. The round's own fields in step 1, its number, its kind, the commit judged, the views and the pre-order check's lines, and for a narrow round its listed items with the reason for each, its changed regions and the line saying why every other item is not judged, come from whoever starts the round: they are given to the command in the review folder it reads, since the merge has no model to write them. The merge fails a round in which any of those fields is missing or malformed, in which an item the round judges has no verdict row or has two, in which a verdict row is for an item the round does not judge, or in which a `cannot judge` is left, and it names the item. It numbers this round's findings in the checklist's order with the comparison and the free pass last, never by the reviewer that raised them, leaves a citation of an earlier round's finding as written, and reports two findings that cite the same view and board place for the designer to resolve, dropping neither. The unit that raised a finding writes its Planning shortfall entry from the plan row, as step 6 has the round's reviewer do, and after the merge the designer names the item or step to amend, amends it and adds the commit. A `cannot judge` (step 2) is resolved by whoever started the round, since a reviewer cannot render: they render the view its Why asks for, add it to the review folder with the folder command's add-view mode, which records the item, its Why and the view, or, when the Why asks for a document the plan gives no address to fetch it from, write the figure into a text file and add it with the add-document mode, which records the item, its Why, the document and its source, and run that unit again, and the merged row records the `cannot judge`, the view and the verdict reached, in that order, with the document in the view's place when a document was added. The merged round is appended below the record's earlier rounds, which stay as they are, and whoever started the round commits it at the end of the round, once its verdicts and findings are written and before any change to the board, as the record requires of every round. Judging a round with one reviewer, a person or an agent session that does not use the command, stays valid, and every round already recorded stands.

### 1. Start a round: commit the board, render its views, run the pre-order check

Commit the board's design files as they are to be judged. With the board closed in every editor, render its views as [Layout review views](#layout-review-views) describes, naming every critical class, the classes step 3 of routing locked, render its placement view into a folder of its own beside them, as that section describes, and run the pre-order check, `task hw:verify`, as step 8 of routing does. Begin the round with:

- **Board judged**: the commit holding the design files the round judges;
- **Views**: the `task hw:views` command and the `task hw:placement` command as they were run, and any further view rendered in the round (step 2), with the command that rendered it;
- **Pre-order check**: the board's `DESIGN` line from the report, and every `FIGURE` and `VIOLATION` line under it;
- **Round kind**: `full` or `narrow` (step 8), written as a bullet of exactly that form, `- **Round kind**: full` or `- **Round kind**: narrow`, in lowercase, among these opening lines and before the round's first subheading. Round 1 is full, and so is every round that is to close the review. A fix to the board lets the next round be narrow: a fresh reviewer then judges only the catalogue items the changed regions and nets touch. A narrow round also begins with **Changed regions**, the floorplan regions and nets the fix commits change, each named from those commits, and **Items judged**, each item the round judges with the reason the changed regions or nets touch it, and a line saying why every other item is not judged. The views are rendered again and the pre-order check is run again in full in either kind.

A round judges the board only as that commit holds it, and only on those views.

### 2. Judge every checklist item

In a full round, go through the checklist in order, the catalogue's items as the round's commit holds them and then the board's own items, and give every item one verdict in the round's verdict table:

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|

- **Item**, **Kind** and **Severity** are the item's identifier, kind and severity.
- **Verdict** is one of `pass`, `fail`, `not applicable` or `cannot judge`.
- **Rests on** cites each view the verdict rests on, by the name the views' index gives it, or for the placement view the name the placement command's index gives it, a tile's included, and the place on the board, in the board coordinates the view's caption states, or `whole board` for an item judged over all of it. Judge each item on every view its *Judged on* names. Where a view is cut into tiles, judge it on every tile whose board coordinates reach the place judged, and cite each: an item judged over a floorplan region on every tile the region's bounds in `layout-plan.md` reach, and an item judged over the whole board on every tile. A tile not looked at is a part of the board the verdict does not rest on.
- **Why**: for `not applicable`, the reason against the item's *Applies when*, stating what the schematic lacks, which the schematic must bear out: an item whose condition the schematic meets applies, and cannot be judged not applicable. For `fail`, the number of the finding it raises (step 4), or of the finding an earlier round raised against it and closed by a reason (step 7). For `cannot judge`, the view the item needs and why the views rendered do not show it.

A narrow round gives a verdict, in the same table, to each item its **Items judged** lists and to no other, each by the rules of this step, a rule-kind item included. An item it does not judge has no row, and the opening lines say why. A narrow round's verdicts are never taken as a judgement of the items it leaves out, so that only a full round, which judges every item, can close the review (step 8).

A **rule-kind item**'s verdict rests on two things, and Rests on cites both: the pre-order check's report, the board's `DESIGN` line with no `VIOLATION` line under it of a rule the item gives, and for a measured rule its `FIGURE` line, giving the figure the check read; and the board's rules table, `design-rules.md`, by the row of every rule the item gives, each rule present there with a figure the item's own figure and source bear out, read from the record its role names where the item names its figure by its role. Both are needed because the check holds the board only to the figure its rules state, the figure in its rules file, its Board Setup or its project text variable: a figure looser than the item requires passes the check, and only the rules table, read against the item, shows it. Either one falling short is a `fail`. For `DECOUPLE-6`, Rests on also cites the report's `DECOUPLE-6 decoupling paths measured` line, read against the integrated circuits and the decoupling capacitors the schematic holds: a count that falls short of the schematic's decoupling capacitors on integrated circuits' supply pins, zero included, is a `fail`, not a `pass`, since the check did not measure them all; and since a count cannot tell one capacitor from another, each of the schematic's decoupling capacitors is seen in its integrated circuit's `crop-<reference>` with no via in its box.

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

For every finding, write in Rule whether it can be expressed as a design rule. It can exactly when the pre-order check can enforce it through the board's rules, apart from the case below, in one of the five forms step 1 of [Rules before routing](#rules-before-routing) uses: a board-wide minimum, a net class's figure or a custom rule, which KiCad's layout rule check enforces, a measured rule, for a quality a measurement from the board's files can state that KiCad does not measure, which the pre-order check then measures, or a record figure, a clearance between net classes that the board declares in its board rules record and the pre-order check writes into KiCad's own layout rule check. A finding a measurement can state is a rule in whichever of those forms can enforce it, preferring KiCad's own. Write `yes` with the rule and its form, or `no` with why none of the five forms can state it, so that it needs judgement on the views. One case writes `no` although a measurement could state the finding, and says so in the reason: when the only figure available for the measurement has no source outside the check itself, since a rule's figure needs a source (step 1 of [Rules before routing](#rules-before-routing)). The reason says what source is missing, for example which published document or record would have to give the figure. The case does not apply to a finding of safety severity: the figure of a safety rule comes from the board's separation basis record or the standard it cites, so a safety finding that a measurement could state is always added as a rule. A measured rule that is new is added to the pre-order check, with a seeded fault proving it, before the review closes. The check holds every design in the repository to the new rule, the proof designs among them, so first run it on each. A proof design whose review has closed can be changed to meet the rule, but a change to its design files after its closing round fails `closing round` in step 8 until a further full round closes the review again, so the check fails the proof once the rule is added, and the answer is to amend the proof and judge it in one more full round, not to add a judgement-kind item for a quality the rule could state. A rule in the form of a custom rule in a board's rules file holds only the boards whose rules files carry it, so a quality KiCad can measure is written in that form, as `GROUND-5` is, and a closed design that breaks it is not held to it. The check reads a measured rule's figure from every design, so a figure kept in a project text variable would have to be added to every design, the closed proofs included. A figure that is an inherent zero, such as a count of vias that must be none, needs no variable, and the report states it in a `FIGURE` line whose source field reads `none, inherent zero`, as `DECOUPLE-6`, `MFG-7` and `MFG-9` do. The case likewise does not apply to a finding whose figure is an inherent zero, such as a designator inside a part's courtyard or off its own part: its figure is none and needs no source outside the check, so it is added as a rule. A cosmetic finding that recurs, in a later round or on a later board, and that a measurement from the board's files can state, is likewise added as a rule-kind item that the pre-order check enforces, so that a reviewer never sees it again, and is not left to judgement on the views. Then, before the review closes:

- A finding that can be a rule is added to the catalogue as a rule-kind item, with its rule, its figure and its source like any other rule-kind item, its Source naming the review it came from. From then on step 1 of the rules section carries it into the rules of every later board it applies to, and the pre-order check checks it, without anyone remembering it.
- A finding that needs judgement on the views, or whose Rule is `no` for the case above, is added to the catalogue as a judgement-kind item when it holds for any board, or to the board's own items in `layout-plan.md` when it holds for this board only, its Source naming the review.
- A finding that an item of the catalogue, or of the board's own, already states, in the same kind, needs no new item.

**Added as** names the item: the new item's identifier, or the item that already states it. A new catalogue item is written in the catalogue's item form, in the area it belongs to, and takes the next number that area has not used. A figure that depends on one machine is written in the item by its role, as the catalogue's other items write theirs, its number living in that machine's board rules, so the catalogue holds no machine's data.

### 6. Trace a first-review failure against a planned item to its planning cause

A finding of safety or function severity in round 1, raised by or through the plan row of an item the board's plan said it would meet, a catalogue item whose plan row is `yes` or one of the board's own items in the baseline, is also a planning shortfall. Not every such finding is one. When the plan row, followed as written, would have met the item and the layout did not follow it, the cause is the layout and not the plan: write `—` in Planning shortfall, name the row the layout departed from in What and where, and say there why the row, followed as written, meets the item. The round's reviewer writes that Planning shortfall entry, from the row's text and the layout, and never from the designer's reasoning: a `—` is written only when the reviewer can read the row, followed as written, as meeting the item, and a row that on that reading would not have met the item makes the finding a planning shortfall. Otherwise, in Planning shortfall, name the catalogue item, or the step of this document's [Planning the layout](#planning-the-layout), that let it through, and amend that item or step in this document before the review closes, so that a later board planned the same way would not repeat it. An amended catalogue item names the review and the finding in its Source; an amended planning step carries, at the end of the step's text, a note naming them, written `Amended after <review>, finding <n>.`, for example `Amended after <board folder>/layout-review.md, round 1, finding 1.3.`, so a reader holding only a copy of this document can see where the step came from, and is amended in a commit whose message names them too. Planning shortfall gives the commit that made the amendment. Every other finding writes `—` there. The board itself is changed as for any other finding (step 7).

A shortfall recorded without an amendment, or an amendment that names no shortfall, fails this step.

### 7. Close every finding

A finding stays open until one of these closes it, written in Closed by:

- a change to the board, naming the commit that makes it, which the next round judges. Before that round, sweep the board for every instance of the finding's class, not only the one the reviewer named, and fix them together; the commit that fixes the finding names the sweep, what was searched for and how many instances were found;
- a recorded reason showing that the item is in fact met, written `met:`; that it does not apply to this board, written `does not apply:`; or that it is overridden by a requirement the board serves or an item of the catalogue or of the board's own that the board must also meet, written `overridden by:` with that requirement or item named.

Never a judgement that the finding is unimportant.

The designer never writes what the reviewer owns: the verdicts, the Rule answer, the Added as entry and, as step 6 says, the Planning shortfall entry's reading of the row. The designer writes Closed by, and the change that closes a finding, and nothing in a round the reviewer has recorded.

A reason closes a finding for the board as it stood when the reason was written. A later round tests it again against the board as that round's commit holds it: its `fail` cites the closed finding (step 2, Why) only if the reason still applies, and otherwise raises a new finding.

**A workmanship finding caused by placement is closed at the placement.** A finding against a workmanship item (`WORK-`) whose cause is where parts sit, such as a route made long or looping by the distance between the parts it joins, is closed by a change to the placement, never by reshaping the route around the parts as they stand. Judge the cause on the placement view of the round's commit: the cause is where parts sit when the connection the view draws for the finding's net shows the fault the route shows, running long because the pads it joins are far apart, crossing another net's because of where the parts sit, or reaching a partner placed beyond another part; the cause is the route alone when that connection runs short and direct where the route does not. Move or turn the parts the finding names, re-route what the change affects, the critical nets as steps 2 to 4 of routing route, lock and judge them and the rest through the router (steps 5 to 8), and render the placement view and its measures again from the change's commit. Remove the router's copper the change affects rather than editing it, and commit a critical re-route only once it is locked. Step 4 of routing judges the re-routed critical nets as the next pass of the `## Critical routing` section, `### Pass <n>`, appended below the earlier passes, which stay as they are, its Board judged commit made after the earlier router's commit. Once the router's commit is made, run `task hw:history -- --board <board>.kicad_pcb --routed` as step 8 of routing does. It must end with `RESULT | PASS`: a `FAIL` on `pass <n> board judged` means the re-route committed copper that is not locked, or the router ran, before the new pass's Board judged commit; on `pass <n> before router`, that an earlier pass was changed, the new pass was written after the router ran, or the router's copper is not committed, or is locked; and the other `FAIL`s mean what step 4 of routing says. Closed by names the change's commit, each part moved or turned and how, and the placement's measures before and after it: the `LENGTH` and `CROSSINGS` totals of each `measures.txt`, and the `NET` line of each net the finding names, from the round's commit and from the change's. A finding whose cause is the route alone is corrected in the copper.

A finding of safety severity closes only by a change to the board, or by a named person's acceptance of one of those reasons, and never by the agent that designed or reviewed the board. The acceptance is recorded beside the board, in the review record, in the same form as the signature on the board's separation basis record: after the reason, Closed by gives `accepted_by:` with the person's name and `accepted_on:` with the date they accepted it, written `YYYY-MM-DD`, and the record is committed with them. The name is a person's, never an agent session's, and never a placeholder such as `unsigned`, `tbd`, `todo`, `none`, `placeholder` or anything in angle brackets; the date is no later than the day of the commit that adds it. That commit is the acceptance's audit trail; no cryptographic signature is involved.

### 8. After a change, begin the next round; only a full round closes the review

After any change to the board, begin a new round at step 1: render the views again and pass the pre-order check again, in full whatever the round's kind. The next round after a fix may be narrow, judging only the items the changed regions and nets touch (step 1), and then compare the layout with the plan and make the free pass over what the change touches. A round that is to close the review is full: it judges the whole checklist, not only the items a change addressed, then compare the layout with the plan and make the free pass again. A narrow round never closes the review. An item added to the checklist since the last full round is judged in the next full round.

The review **closes** on a full round that judges the board's design files as they stand, in which the pre-order check passes the board, every item has a verdict and none is left `cannot judge`, every `fail` verdict raises a finding or cites one an earlier round closed by a reason, and every finding of every round is closed. A finding closed in that round by a change needs a further round. A board whose review has not closed, which only a full round with no finding open does, is not ordered.

Before the first order of any board that carries mains, a review by an experienced electrical engineer is recommended, besides this one. It is not required.

Judge the record against the board and the repository rather than taking its word:

- **Every full round judged the whole checklist, and every narrow round what it lists.** Each full round's verdict table has exactly one row for every item of the catalogue in the round's commit and every row of the board's own items table in that commit, and names no other. Each narrow round's verdict table has exactly one row for each item its **Items judged** lists, as the round's commit holds the item, and names no other. Every verdict is one of the four, and no `cannot judge` is left without a verdict after it.
- **The closing round is full.** The highest-numbered round states `- **Round kind**: full`; a narrow round that is the last recorded leaves the review open, however clean it is.
- **Every view was rendered.** Render the views again from the round's commit with the round's command: its classes are the critical classes routing locked; the index holds a `layer-` view of every copper, mask, paste, silkscreen and edge layer the board carries and a `net-` view of every net the critical classes hold; and every view a verdict cites is in it, or is a further view the round names with its command. Render the placement view again from the round's commit with the round's `task hw:placement` command, into its own folder: every placement view a verdict cites is in its index.
- **Every verdict rests where it says.** Each `not applicable` gives a reason the schematic bears out. Each rule-kind verdict cites the report's line and the rules table's rows, and a `pass` has no `VIOLATION` line of a rule the item gives under the board's `DESIGN` line, a measured rule's `FIGURE` line giving the figure its row gives, and every rule the item gives in the table with a figure its source bears out. For `DECOUPLE-6` the verdict also cites the `DECOUPLE-6 decoupling paths measured` line, and a pass over a count that falls short of the schematic's decoupling capacitors on integrated circuits' supply pins, zero included, fails here.
- **Every finding was judged as a rule, and added.** Each finding has a Rule entry. Each `no` gives why none of the five forms can state the finding, or for the case step 5 allows, says what source is missing; a `no` whose finding one of them can state, as step 1 of [Rules before routing](#rules-before-routing) defines them, and that gives not that reason, fails, as a `not applicable` the schematic does not bear out does. One judged `yes` names in Added as a rule-kind item of the catalogue, as committed, that states it: a new one whose Source names the review, or one that already stated it. One judged `no` names a judgement-kind item of the catalogue or one of the board's own items that states it, new with its Source naming the review, or already there.
- **The baseline came first.** Every row of the board's own items table in the commit before placement is in each round's commit, with the same fields from Applies when to Source, so no baseline item is removed, narrowed, loosened or lowered after the layout began. Every row of the board's own items table that the commit before placement lacks names, in its Source, the review that added it. That commit is the one step 3 of [Planning the layout](#planning-the-layout) finds.
- **Each round stands as it was first recorded, and the closing round judged the board as it stands.** Run the history command from the board's folder, on the branch as pushed, fetched afresh with its whole history and checked out, and read its verdict:

  ```
  task hw:review-history -- --folder <board folder>
  ```

  It needs git and Python only. It exits 0 and ends `RESULT | PASS` when every check passes, 1 and `RESULT | FAIL` when any fails, and 2 and `RESULT | REFUSED` when it refuses, judging nothing: a shallow clone, a folder that does not track exactly one KiCad project, a record or design file that git does not track or that differs from the checked-out commit, or a closing round whose opening lines state no round kind, state it more than once, or state one that is neither `full` nor `narrow`. Each failing `CHECK` line names the board, the round and what differs, and any failure fails this step:
  - `round structure`: a round, in the record or any earlier version of it, is not fully accounted for by the parts the check reads. A line outside a code fence mentions a round heading in any way but exactly `## Round <n>` (n with no leading zero), a round is given twice, or a code fence is left open. A round holds, outside a code fence, a heading line other than `### Verdicts`, `### Findings` and `### Plan and free pass`, a part twice, no `### Verdicts` part, or a Verdicts or Findings part that is anything but its one table (the verdict table's six columns; the findings table's Finding, Raised by, Severity and What and where columns, each finding numbered once), whether that part is unreadable or holds text, a second table or a code fence beside it. A round with no finding either leaves the Findings part out or gives it only the line `This round raises no finding.`. The Plan and free pass part is prose that is not compared. Each failing line names the round and the offending line, so no part of a round goes unguarded.
  - `rounds kept`: a round recorded in any earlier version of the record is missing from it now, or it holds no round. A record that drops rounds is restored from the history, never rewritten.
  - `round <n> as first recorded`: the round's opening lines, its verdict table or its findings differ from the round's end-of-round commit, the first commit whose record holds its heading. A finding removed, added, renumbered or reworded, or its Raised by or Severity changed, fails. The Closed by column is the one field that legitimately changes after a round is recorded, so it is never compared. The planning shortfall check below therefore reads round 1 as it was first recorded.
  - `round <n> order`: the round's Board judged commit is not in the history, or the round's end-of-round commit is not an ancestor of, or is, a commit after its Board judged commit that changes the board's design files, so a design change was committed before the round that judged it was recorded.
  - `round kind`: the closing round, the highest-numbered, states `- **Round kind**: full`, in its opening lines before its first subheading. A closing round that states `narrow` fails: a narrow round cannot close the review. A closing round that states no kind, states it more than once, states it in any other form than that bullet, or states any other word, is refused rather than failed, since the check cannot tell what the round judged. An earlier round needs no kind and none is read from it, so a record's earlier rounds are never edited to add one.
  - `round completeness`: a closing round of kind full has a verdict row for every item that round 1's verdict table holds and for every item of each earlier full round, so a narrow round labelled full does not close the review. The check names the first missing items and the round each came from. A narrow closing round is held to no item, and a record of one round passes.
  - `closing round`: a design file of the board has changed since the closing round's commit, the highest-numbered round's end-of-round commit, so the round did not judge the board as it stands.

  The board's design files are the files KiCad reads for it: everything tracked in the board's folder, the sheets its schematic reaches and the libraries its library tables name, less the folder's own records, its markdown and YAML files, the review record among them. A record's own commits and a finding's closure are therefore never a design change.
- **Every severity is the one this step gives.** Each row of each verdict table gives the item's own kind and severity, as the round's commit holds the item. Each finding's Severity is the severity of the item that raised it, or of the item whose plan row it departs from, read from the catalogue or the board's own items table in the round's commit; for a departure from the floorplan's region or connector table, and for a free-pass finding, it is the severity the catalogue's definitions give what its What and where says is wrong. And whatever raised it, a finding whose What and where bears on separation between mains and anything a person or a low-voltage circuit can reach, on fusing, on protective earthing or on insulation has safety severity. The two checks below key on the severity a finding records, so a finding recorded below its severity fails here rather than closing by a reason with no acceptance or escaping its planning shortfall.
- **Every planning shortfall has its amendment.** Each finding of safety or function severity in round 1 raised against a catalogue item whose plan row was `yes`, or one of the board's own items in the baseline, names an item or a step and a commit, unless it writes `—` as step 6 allows, naming the row the layout departed from and why that row, followed as written, meets the item, which the round's reviewer wrote from the row's text; a `—` that cannot be read against the row fails. That commit changes this document at that item or step. An amended item's Source names the review and the finding; an amended step's text ends with the note step 6 gives naming them, and the commit's message names them too.
- **Every closure is one the method allows.** Each Closed by is a change naming a commit that changes the board's design files, or a reason of one of the three kinds. A safety finding's is a change, or a reason carrying an `accepted_by` and `accepted_on` as step 7 states. A workmanship finding whose cause the placement view shows to be where parts sit is closed by a change to the placement, naming each part moved or turned and the measures before and after it, as step 7 states, and never by a change to its route alone.

A review whose closing round is narrow, with an item left without a verdict in a full round, a `cannot judge` verdict unresolved, a view not rendered, or a baseline checklist committed after the layout began fails this step, and so does a record that fails a cross-check above. A baseline is committed after the layout began when step 3 of [Planning the layout](#planning-the-layout) fails it.

**This step is shown to find what it checks for** on `hardware/proof/review-proof`, a clean proof design carrying at least one part for every area of the [Layout practice catalogue](#layout-practice-catalogue), never ordered. `task hw:review-seed -- --seeds <file> --out <folder>` copies it outside the repository, places one or more known layout defects in the copy for every catalogue area, refuses the copy unless the pre-order check passes it, and writes a review folder holding only what this step gives a reviewer: the copy's design files with its floorplan, plan and rules records but never its own review record, this document, `hardware/README.md`, every view of the copy, its placement view and measures in a folder of their own, and the pre-order check's report on it. The seed list goes to `<file>`, apart from the folder. A session that did not design the board and has no record of the seeds then follows this step on the folder alone, started with the command's fixed prompt (`task hw:review-seed -- --print-prompt`), and its findings are compared with the seed list afterwards. Every seed must be reported as a finding against the catalogue item that covers it. A seed not reported is a gap in the catalogue, the views or this step and what it gives a reviewer, closed where it lies, and the blind review is repeated in a new session before this step is relied on. Repeat the proof after changing the catalogue, the views or this step, in the form that changed: a change to the step as one reviewer follows it repeats the single-reviewer proof above, and a change to how a round is judged by unit, to the layout caller or to the review folder it reads repeats the fanned-out proof, `task hw:review-proof -- --work <folder>`, which runs the fanned-out form on one seeded copy, from a review folder the folder command writes from the copy's kept work tree and commit, with two reviewers of each set of areas and again with three, and judges it against the recorded single-reviewer runs of the same seed list, design and model by the review kit's pooled criterion, without running the single reviewer again: the fanned-out form must report no fewer seeds than the fewest any recorded single run reported and every seed every recorded single run reported, in at most half the single mean time and at most 1.25 times the single mean cost, and the three-reviewer round's figures are recorded and not bounded. A change to the catalogue or the views repeats both, the single-reviewer proof being followed in a new session and its runs recorded as the baselines the fanned-out proof is judged against. The recorded proof of one form stands for that form alone. `hardware/README.md` describes the proof design and the commands.

Out of scope for this section: the pre-order check itself, which [`hardware/README.md`](../hardware/README.md) describes; the content of the catalogue; producing the views, which [Layout review views](#layout-review-views) describes; the content of any particular board's findings; and who the electrical engineer is.

## Ordering

Do this once the layout review has closed and before the board is paid for. Its purpose is to confirm that the files the manufacturer and the assembler will work from are the design's files. An assembled board most often goes wrong in its production files while its design is right: a footprint's rotation that differs from the assembler's convention, a diode or capacitor placed reversed, a layer exported mirrored, shifted or empty. None of this is visible to the pre-order check or the layout review, which judge the design; all of it is visible in the assembler's own preview and in the exported files rendered, before payment. Every board's design task orders its board, and carries out this step first, so the check is the same each time.

The step compares, for every placed part, the position, the rotation and the polarity or first-pin orientation in the assembly files with the assembler's rendered preview of the assembled board, and the catalogue part each position's row of the parts list names with the board's parts specification record. It then renders the fabrication files from the exported files themselves, every copper, mask, legend and drill layer and the board outline, and has each looked at for missing, shifted or mirrored content. Each finding is corrected and the files exported again before payment.

The step's evidence is a **production-files check record**, `production-files-check.md`, in the board's own folder beside its KiCad project, committed with the board, as the layout review's record is. It is read by whoever approves payment; no command reads it. A board whose files were exported but whose record is absent, or holds a row or layer not judged, is not ready to pay for.

The manufacturer's own facts are in its record, `docs/board-manufacturer-jlcpcb.md`, and this step cites them by role and does not restate them: the file formats it accepts, section *File formats*, give the fabrication archive, the parts list's columns and the placement file's columns, and say that the assembler's engineers correct a rotation from the silkscreen polarity mark where it does not match. Read that section, at its date, before the first export.

### 1. Export the production files from the committed design

Commit the design's files as the layout review closed them. With the board closed in every editor, make a new folder, `<work>`, outside every design's folder and outside the repository's tracked files, since its files are regenerated and never committed, and export into it. Direct DRC and the pre-order check have already passed the board. `<board>` is the layout, `<schematic>` its root schematic, and the copper layers are `F.Cu`, `B.Cu` and each `In<n>.Cu` the board carries:

```
kicad-cli pcb export pos --format csv --units mm --side both --exclude-dnp --output <work>/positions.csv <board>.kicad_pcb
python3 hardware/tools/production_files.py placement --positions <work>/positions.csv --out <work>/placement.csv
kicad-cli sch export bom --fields Reference,Value,Footprint,LCSC --labels Designator,Comment,Footprint,LCSC --group-by LCSC --exclude-dnp --output <work>/parts-list.csv <schematic>.kicad_sch
kicad-cli pcb export gerbers --layers "<each copper layer>,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts" --output <work>/gerbers/ <board>.kicad_pcb
kicad-cli pcb export drill --output <work>/gerbers/ <board>.kicad_pcb
```

These commands were exercised with KiCad 10.0.7 on `hardware/proof/review-proof`, and the tooling tests run them there. What each gives:

- The position export's columns are `Ref,Val,Package,PosX,PosY,Rot,Side`, not the assembler's, and it gives each footprint's origin, which is not always the centre of the part's body. Its Y runs up, as the Gerber files' does, which is the reverse in sign of the editor's Y, so a point read off the design's own views, whose captions are in editor coordinates, has the opposite sign of Y in the export. The conversion, `production_files.py placement`, writes the columns the manufacturer's record gives for the placement file, `Designator,Mid X,Mid Y,Layer,Rotation`, with the side written `Top` or `Bottom` and the rotation in 0 to 360 degrees counter-clockwise, and keeps the export's two coordinates, which agree with the Gerber files exported with them: on the proof design the pad of `TP1`, at editor coordinates (37, 30), is flashed in the bottom copper file at (37, -30), and the converted file gives (37, -30). The manufacturer's record gives no frame for the placement file's coordinates or for a bottom-side part, so how the assembler reads the file is what its own preview shows in step 3 and step 4 checks. It refuses an export with other columns, a part twice or on no side, and an empty one.
- The parts list has one row for each catalogue number, `--group-by LCSC`, with the manufacturer record's columns *Comment*, *Designator* and *Footprint* and the catalogue number in a fourth, `LCSC`; where several positions carry one number the row lists them all in *Designator*. A position that carries no `LCSC` field has an empty cell and is a finding in step 4.
- The fabrication commands write one file for each layer named, a job file, and one drill file holding the plated and the unplated holes, all in `<work>/gerbers/`, with the Gerber files named as KiCad names them. The manufacturer's record lists the extensions it recommends; the archive uploaded in step 3 is those files, in one ZIP.

Do not use Konnect's export tools for this step ([Konnect's skills, and where they conflict with this method](#konnects-skills-and-where-they-conflict-with-this-method)).

### 2. Render every fabrication layer and the drill file from the exported files, and every footprint at rotation 0

Render from the files just exported, never plot the layers again from the board, because a layer exported mirrored, shifted or empty shows only in a render of the exported file. `GERBONARA_PYTHON` is the Python of the virtual environment gerbonara 1.6.3 is installed in ([Tools](#tools)), and `RESVG` is resvg:

```
"$GERBONARA_PYTHON" hardware/tools/production_files.py render --gerbers <work>/gerbers --out <work>/layers --resvg "$RESVG"
```

The command refuses a gerbonara of another version, naming it, with `CANNOT RUN`. It draws every Gerber layer and the drill file into a PNG named `layer-<layer>.png`, all in one common frame at 16 pixels to the millimetre, with an `index.txt` and an `index.json` that list every image, the file it was read from and the frame. The frame is the Gerber files' own, with Y up: a point at editor coordinates (x, y) is at (x, -y). The Gerber library reports a drill file's header as `G90 header statement found after end of header`, which the command lists as a `NOTE` and does not treat as a failure. An exported layer the command lists no image for is a layer not rendered, and blocks the order.

The rotation and the first-pin or polarity orientation of step 4 are judged against the footprint as its library draws it, at rotation 0, which neither the placement file nor the layout's own views show. `<board>` is the layout of step 1:

```
python3 hardware/tools/production_files.py footprints --board <board>.kicad_pcb --out <work>/footprints --kicad-cli "$KICAD_CLI" --resvg "$RESVG"
```

It draws every distinct footprint the board carries, with `kicad-cli fp export svg` and resvg, into a PNG named `footprint-<library>_<name>.png` showing the footprint's copper with its pad numbers, its legend, its fabrication outline and its courtyard, with an `index.txt` and an `index.json` that list every image and the designators that carry it. A footprint the board holds turned or on the bottom side is turned or flipped back to rotation 0 on the top side first. Each image is drawn with the footprint's first pin, a polarity mark or a key as the library draws it, so the mark is read where it lies in the drawing at rotation 0. A part of the placement file at Rotation R on the `Top` side is that drawing turned R degrees counter-clockwise on the page, about the footprint's origin, as the manufacturer's record gives the file's rotation: at 90 what stands at the top of the drawing is at the left, at 180 it is at the bottom and at 270 it is at the right, and the first-pin or polarity mark moves with it. The index repeats this rule. A `Bottom` part is the drawing flipped to the back, whose frame the manufacturer's record does not give, so its marking is read from the preview. A footprint of a placed part with no image is a part whose first pin or polarity cannot be judged, and blocks the order.

Render the design's own views from the same commit, as step 1 of the [layout review](#layout-review) does, with `task hw:views` and `task hw:placement` into folders of their own, outside every design's folder, so each layer has its view to be compared with.

### 3. Obtain the assembler's preview

Upload the fabrication archive, the placement file and the parts list to the assembler's order page, in the formats its record gives, and go no further than its preview: nothing is paid for in this step. Save the assembler's own rendered preview of the assembled board, each side, and its placement preview of every part, as images, noting the date and the assembler's name for each. The preview is the assembler's own drawing of the files as it reads them, so it shows each part where, turned as and with the polarity or first-pin mark it will be assembled with, including any correction the assembler's engineers make to a rotation. An assembler's preview that needs an account or an upload that the session cannot make is the reason the proof below has a stand-in.

### 4. Compare every placed part with the preview

Give every row of the placement file a row in the record's parts table; none is skipped because it looks trivial. For the part in the row, judge:

- **Position**: the preview shows the part named at the file's point. Read the file's Mid X and Mid Y in the Gerber frame, and the part's place on the design's placement view, whose captions are in editor coordinates, by the sign of Y above. A position matches when the file's point lies on the part's own body or its pads as the design draws them, and the preview shows the part there. A part shifted so that the point falls outside its body, or shown by the preview elsewhere, differs.
- **Rotation**: the preview turns the part as the design's own assembly view of its side does, the file's angle being the counter-clockwise turn from the footprint as the library draws it, which the footprint's drawing at rotation 0 from step 2 shows. Turn that drawing by the file's angle by the rule of step 2 and the part's first pin, key or longer side lies where the design's assembly view has it. A part turned differently from the design differs.
- **Polarity or first-pin orientation**: for every polarised part and every part with a first-pin mark, a diode's cathode bar, a capacitor's polarity mark, an integrated circuit's pin-one dot, notch or bevel, a keyed connector, the mark in the preview lies where the design's assembly view and its silkscreen put it, and the mark of the footprint's drawing at rotation 0, turned by the file's angle by the rule of step 2, lies there too. A part reversed or with its first pin turned differs. Where the assembler's engineers would correct a rotation from the silkscreen polarity mark, the preview shows the corrected part; a difference between the file and the design that the preview, drawn as built, shows corrected is not a finding on the preview, and is recorded in the row's Why with the manufacturer record's statement of the correction. A part with no polarity states `none`.
- **Catalogue part**: the parts list's row for the position carries the catalogue number, value and footprint that the board's parts specification record maps the position to. Every position of the placement file is in the parts list and in the record, and the parts list names no position the placement file lacks. A number that differs, is absent, or belongs to another position differs.

### 5. Look at every rendered fabrication layer

Open every image the render wrote, each copper layer, the front and back mask, the front and back legend, the outline and the drill file, and the design's own view of the same layer (the `layer-<layer>` views of step 2, tile by tile where it is tiled, and for the drill file the holes of the copper views). State what was compared in the record's layer table, and look for three things:

- **Missing content**: no content on the exported layer where the design has copper, mask openings, legend or holes;
- **Shifted content**: content that stands in the exported layer at another place than in the design's view, read by the frame's coordinates against the view's captions, with the sign of Y above;
- **Mirrored content**: content that is the design's reflected, legend text that reads backward or a pattern turned over.

An exported layer matches only when none of the three is found.

### 6. Record every verdict, and block the order on anything that does not match

Write `production-files-check.md` in the board's folder, beginning with these lines: **Board judged**, the commit holding the design files the files were exported from; **Tools**, `kicad-cli version`, the gerbonara and resvg versions; **Commands**, each command of steps 1 and 2 as it was run; **Preview**, the assembler's preview as saved, with its date, or, where the preview was not obtained, what stands in for it and why. Then:

`### Parts` holds a table with one row for every placed part:

| Part | Position (file / preview) | Rotation (file / preview) | Polarity or first pin (file / preview) | Catalogue part (record / parts list) | Verdict | Why |
|---|---|---|---|---|---|---|

`### Layers` holds a table with a row for every fabrication layer, the drill file and the outline:

| Layer | File | Compared with | Verdict | Why |
|---|---|---|---|---|

The verdict is `matches`, `differs` or `cannot judge`. A row that is not `matches` blocks the order, as does a layer not `matches`, until the design is corrected and the files exported again. `Why` of a `differs` row says what is wrong and where, as the placement file's designator or the layer's board coordinates, and a `cannot judge` row says what the judgement needs. Count the record's part rows against the placement file's rows: a record with fewer rows than the file has parts is not complete and blocks the order. Under `### Findings` list each difference, and what closed it.

A finding is corrected in the design, or in the commands where the export is wrong, and the files exported again from step 1, since a file edited by hand would no longer be the design's. A correction to the design's files makes it a design the layout review did not judge, so it begins a new round of that review ([Layout review](#layout-review), step 8) and closes it before the files are exported again. Then the record is written again whole for the new commit, and the earlier record stays in the repository's history. Commit the record with the board, and pay only when every row and every layer is `matches`.

**This check may be judged by unit instead of by one reviewer.** That is a way of carrying out steps 4 and 5, and it changes none of them. `task hw:review-run -- --caller production_files` ([`hardware/README.md`](../hardware/README.md#the-production-files-check-by-unit)) judges the check with one reviewer for each group of at most ten placed parts that share a footprint drawing and one for every fabrication layer, the drill file and the outline, each reviewer a fork of one shared context that holds the placement file, the parts list, the parts specification record, the footprint drawings, the layer images, the design's views, the assembler's preview and the check's fields, with three reviewers of each, so that a row any of them finds not to match stands. A placed part whose footprint has no drawing is judged by a reviewer of its own, which gives it `cannot judge`, as step 2 makes it, and the merge refuses any other verdict for it. The command merges what the reviewers return, with no model, into one production-files check record in which every row of the placement file has one row in the parts table and every fabrication layer, the drill file and the outline has one row in the layers table. The record's opening fields, the commit judged, the tools, the commands and the line saying what the preview is, come from whoever runs the check: they are given to the command in the review folder it reads, which `task hw:production-review-folder` writes from the exported files, the design's views and the preview, since the merge has no model to write them. The merge refuses a folder whose fields are missing or malformed before any reviewer starts, as it does a round file that is not a production one; a placement file with a designator twice (compared without case), a blank designator, a row of the wrong width or text that is not UTF-8; a footprint drawings index that is unreadable, malformed, names a missing file or carries one designator in two drawings; a layer images index that lists a layer twice, lacks the drill file or the outline, names a missing file or leaves a Gerber or drill file that no entry names as its source; a parts list lacking the Designator or Footprint column; more than one parts specification record; a placement designator equal to a layer name; and a folder lacking a preview image, a layer view image, a placement, assembly or 3D view image, the placement file, the parts list, the record, the round file or one of the four index text files. `task hw:production-review-folder` refuses, reporting every cause at once and writing nothing, a symbolic link or an earlier check record in any folder given, an output folder inside the repository or an input, a folder that is not new or empty, a missing preview, an input lacking what the check reads, a tools line, command or preview line that is blank, spans lines or holds a code fence, a check with no command, and a Gerber or drill file the layer images index does not list, and removes the folder if a write fails; the layout folder command refuses round-file fields naming tools, commands or preview. The merge fails a check in which a placement-file row has no parts row or has two, in which a row is for a part or a layer the check does not judge, in which a part with no drawing has a verdict other than `cannot judge`, in which a row lacks the cells its kind of row has or is not `matches` and says nothing, and in which a `differs` has no finding or a finding is of a row that matches, and it names the row. A cell is lacking when it is empty or a placeholder such as `—` or `n/a`: a part's four comparisons (`none` for a part with no polarity) and a layer's file and what it was compared with are always judged, and the dash belongs only to the cells of the other kind of row. It writes the record with every row that is not `matches` named and said to block the order. A `cannot judge` is not resolved within the check: it stands and blocks the order, as step 6 says of every row that is not `matches`. The step that obtains the assembler's preview, step 3, stays outside every reviewer, since the preview needs an account and an upload that a read-only reviewer cannot hold; the review folder holds the preview as it was saved. Judging the check with one reviewer, a person or an agent session that does not use the command, stays valid. The fanned-out form is relied on only once its proof is recorded, and until then this step is carried out with one reviewer.

**This step is shown to find what it checks for** on `hardware/proof/review-proof`, the layout review's clean proof design, reused as it stands and never ordered: a throwaway design marked not for manufacture, carrying synthetic records, that passes the pre-order check and carries parts of the kinds this step compares. `task hw:production-seed -- --seeds <file> --out <folder>` exports its production files from the committed design with the commands of step 1, seeds them with known defects, and writes a production-files folder holding only what this step gives the session that follows it: the seeded placement file, the seeded parts list, the Gerber and drill files exported from an edited copy of the board, the image of every layer drawn from those files by step 2, the drawing of every footprint the board carries at rotation 0 with the index that gives the rule for reading a rotation against it (`production/footprints/`), the board's parts specification record, this document, `hardware/README.md` and the manufacturer's record. The assembler's preview needs an account and an upload that a read-only session cannot hold, so the folder holds the design's own rendered placement view and its assembly and three-dimensional views of the unseeded design in its place, each of which shows every part at its intended position, rotation and polarity, with the design's views of every layer. The stand-in tests whether the step finds a difference between the files and the design; it does not test the assembler's own reading of the placement file's coordinates, rotation or bottom-side parts, which only its preview shows. The seed list is written to `<file>`, apart from the folder, and the session is told nothing in it. A fresh session with read tools only, working in the folder, is started with the command's fixed prompt (`task hw:production-seed -- --print-prompt`) and returns its production-files check record, which is compared with the seed list afterwards. Every seed must be reported by a part's row or a layer's verdict that is not `matches`. A finding that matches no seed and shows a real defect in the clean proof design is corrected there and the proof repeated; a false positive is recorded and does not fail the proof. A seed not reported is a gap in this step or in what it gives a session, closed where it lies, and the follow is repeated in a new session before this step is relied on. Repeat the proof after changing this step, in the form that changed: a change to the step as one reviewer follows it repeats the single-reviewer form, and a change to how the check is judged by unit, to the production-files caller or to the review folder it reads repeats the fanned-out form, each form's recorded proof standing for that form alone. `hardware/README.md` describes the proof design and the command.

Out of scope for this section: checking the design itself, which the pre-order check and the [layout review](#layout-review) do; the layout review's views, which are rendered from the design and not from the files sent to the manufacturer; and placing the order.

## Layout review views

An image of one layer shows no net names, so a ground drawn as a thin trace looks like any other track. The layout review therefore judges a board on an image of each layer (`layer-<layer>`) and on views that show each critical net against the board (`net-<net>`), the critical classes against each other (`classes`), each integrated circuit framed with its own decoupling parts (`crop-<reference>`), each side as it is assembled (`assembly-top`, `assembly-bottom`), the assembled board in three dimensions (`3d-top`, `3d-bottom`, `3d-angled`), and the board's parts with their unrouted connections and floorplan regions (`placement`), the [placement](#placement) view. It also uses a table of the facts a picture cannot carry, and the placement's measures. With the board closed in every editor, render them from the board's folder:

```
task hw:views -- --board <board>.kicad_pcb --project <board>.kicad_pro --class <critical class> [--class <critical class> ...] --out <work folder>/<board>-views
task hw:placement -- --board <board>.kicad_pcb --project <board>.kicad_pro --out <work folder>/<board>-placement
```

Name every critical class, as in routing step 3. Each output folder is a working folder: it must be new or empty, and outside every design's folder, and the placement view's is its own, beside the views' and never the same. Never commit either. The placement view's images are named `placement`, as its own index names them, and its measures are in that folder's `measures.txt`, as [`hardware/README.md`](../hardware/README.md#the-placement-view) describes. The views, their names, the index and the per-net fact table, and what the command refuses, are listed in [`hardware/README.md`](../hardware/README.md#the-layout-review-views). The command needs KiCad's command-line tool, resvg and a monospaced font for the captions (see [Tools](#tools)).

**Resolution.** The views are drawn at

    pixels per millimetre = 3 / (the smaller of the board's minimum track width and minimum clearance, in millimetres)

so the smallest track and the smallest gap each span at least three pixels. Both minimums are read from the board's design rules, Board Setup's minimum track width and minimum clearance, whose figures and sources the board's rules table already carries, from step 1 of [Placement](#placement), where they are set before the first candidate is rendered. The method itself therefore carries no manufacturer's figure. A board whose rules state either minimum as none, zero or less fails the command, naming the missing figure.

**Image size limit.** Every image is kept within a long edge of 1568 pixels, and within 1568 visual patches of 28 by 28 pixels. An image costs ⌈width / 28⌉ × ⌈height / 28⌉ patches. This is the standard tier of the model vendor's published limits, the tier for all models other than its high-resolution ones. An image over either limit is downscaled to the largest size that fits, keeping its aspect ratio, so an image within both is read at the resolution it was drawn at. The source is the "Resolution and token cost" section of https://platform.claude.com/docs/en/build-with-claude/vision, read on 2026-10-13. That section also gives a high-resolution tier, a long edge of 2576 pixels and 4784 patches, for the vendor's newer models. The views keep to the standard tier, so every reviewing model reads them whole. Every two-dimensional view larger than the limit, a crop included, is cut into tiles. Each three-dimensional view is one image within it.

**Captions.** Every image carries a caption drawn into it. A two-dimensional view's caption states its layers, the colour of each layer or, on the class map, of each class, its net or class, its scale in pixels per millimetre and the board coordinates in millimetres it covers. A three-dimensional view's caption states its view direction and image size. The index repeats every caption, as text and as JSON, so a reviewer working from the files alone has every fact without the author's context.

**Nothing left out quietly.** The views are drawn from a temporary copy that reads as the design does in place: it keeps the design's own file names, and every model path the design's folder anchors is written out in full. Every two-dimensional view, and every tile of one, is composed in one place, which alone frames it, puts it on the dark background, draws its rule areas, names the layers it lacks and the fonts KiCad substituted, and writes its caption fields. So these hold for every two-dimensional view alike:

- A whole-board view frames everything KiCad draws on the board's plotted layers, united with the outline and the rule areas, with a millimetre to spare, so a part or a text reaching past the outline is drawn whole rather than cut off. A crop is framed on, and names, only its own circuit and that circuit's decoupling parts, and it shows only what lies within the board coordinates its caption states. A crop is at least 640 pixels wide, so a crop of a small circuit is widened about its centre and can take in a neighbouring circuit's parts: everything within its coordinates is drawn, and another circuit's parts that fall there are drawn but not named, so a part that neither the crop's caption nor the index names as that circuit's decoupling is not its decoupling. A decoupling part is a two-pad part, not itself an integrated circuit, with its two pads on two different nets that are both a circuit's supply nets. It belongs to the one circuit sharing those nets whose nearest pad is closest to it, so a crop never names another circuit's decoupling on a shared rail as its own. A circuit to which none belongs is marked in its caption and the index as having no decoupling parts. The caption names a part by its two pads' nets and its nearest circuit alone, not by the role the schematic gives it: a filter capacitor on a connector's line, with its pads across a circuit's supply nets, is named as that circuit's decoupling. A part is judged under the item its schematic role names, `EMI-3` for such a filter, whatever the caption calls it.
- KiCad does not plot a rule area, so the command draws each one as a dashed, hatched outline on every two-dimensional view that shows one of its layers, the faint board beneath a net overlay or the class map included, wherever the view's region reaches the area, and that view's caption names it. The three-dimensional views do not draw rule areas.
- A fabrication or courtyard layer the board does not carry is named as not carried in the caption of every view that would show it. The board must carry every other layer a view shows.
- A font KiCad cannot find, whose text it draws in another, is named in every caption, the three-dimensional views' included.

The three-dimensional views say what they leave out in their own captions and in the index:

- A part drawn without a model is named: one whose model KiCad cannot find, one declaring no model, one whose model the design hides, and one marked do not populate. Which parts KiCad drew a model for is judged from KiCad's three-dimensional export of the same copy (`kicad-cli pcb export glb`), not from the rendered images, so a model the renderer loads but the export does not would be named as not found although it is drawn.
- A three-dimensional view is zoomed out until no part reaches its frame, and its caption states the zoom.

The command reports each part the three-dimensional views draw without its model, whatever the reason, a font KiCad substitutes and a layer the board does not carry as lines of their own as well. A board with any of them still gets its views: whether what they leave out matters is the review's judgement.

Out of scope for this section: judging the images, which is the [layout review](#layout-review) step.

## Layout practice catalogue

This is the one statement of what a well laid-out board looks like. It is used five times on every board: the board is planned against it before placement ([Planning the layout](#planning-the-layout)), each candidate placement is judged against the items whose *Judged on* names `placement` ([Placement](#placement), step 5), every rule-kind item that applies to it is written into its rules before routing ([Rules before routing](#rules-before-routing), step 1), the critical nets' routes are judged against every item that bears on them before the router runs ([Routing](#routing-critical-nets-by-hand-and-locked-then-the-rest), step 4), and the [layout review](#layout-review) uses it as the baseline checklist a finished layout is judged item by item against, adding to it every finding that can be written as a rule or that holds for any board. It holds no figure, part or board shape of any one machine. A figure that depends on the machine is named here by its role, such as the highest continuous current a class carries, and its number lives in that machine's records and its board's rules.

### How an item is read

Every item carries the same fields:

- **Identifier**, its area and a number, such as `GROUND-1`. An identifier is never renumbered and never reused: a plan, a rule and a review cite items by it. A new item takes the next number its area has not used, and an item withdrawn keeps its identifier, marked withdrawn, so a citation of it still finds it.
- **Applies when** states, in terms of what the board's schematic carries, the condition under which the item applies to a board. An item whose condition the schematic meets applies; it cannot be marked as not applying.
- **Asks** is the question the item asks of a board.
- **Passes** is the pattern that passes.
- **Fails, as the views show it** is what a failing board looks like in the [layout review views](#layout-review-views).
- **Judged on** names the views it is judged on: an image of one layer, `layer-<layer>`, such as `layer-F.Cu`; a critical net against the board, `net-<net>`; the critical classes against each other, `classes`; an integrated circuit with its decoupling, `crop-<reference>`; a side as assembled, `assembly-top` or `assembly-bottom`; the assembled board in three dimensions, `3d-top`, `3d-bottom` or `3d-angled`; the fact table, `facts.txt`, which gives every net's track width range, via count, zones and classes; or the placement view, `placement`, the board's parts with their unrouted connections and floorplan regions, with its measures. An item whose *Judged on* names `placement` is judged at [placement](#placement) too, on each candidate before any track is drawn, as well as at the layout review. A rule-kind item is judged on the pre-order check's report and on the board's rules table, `design-rules.md`: the check holds the board to whatever figure its rules state, so a figure smaller than the item's source requires passes the check, and only the rules table, its figure read against the item, shows it. Its *Fails* names what such an undersized figure looks like in that table.
- **Kind** is one of two. A **rule-kind** item is enforced by the automated pre-order check, through the board's rules: it gives its rule in one of the five forms the rules step uses, with its figure and source. Three of them KiCad's own layout rule check enforces: a board-wide minimum, a net class's figure, and a custom rule in the board's rules file (an item whose quality KiCad reports unaided, such as a via left unconnected, gives no rule and names KiCad's check). The fourth is a **measured rule**, a quality KiCad does not measure, such as how much longer a route is than its pads' places need: the pre-order check measures it itself from the board's files, against a figure the board sets as a project text variable, and the check's report states the figure it read. The fifth is a **record figure**, a clearance between two kinds of net class that the board declares in its board rules record (`board-rules.yaml`) rather than in its rules file: the pre-order check writes it into KiCad's own layout rule check on a copy of the board, so KiCad measures it, and the check's report states the figure it read from the record. A net class it names by its role, such as `<power class>`, is replaced by the board's own name for that class; only the `Mains` class is named literally, since its name is fixed. A **judgement-kind** item is judged on the rendered views. A practice only partly expressible as a rule is two items, one of each kind, so every item has a single kind.
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
- **Judged on:** `assembly-top`, `assembly-bottom`, `classes`, `placement`.
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
- **Judged on:** `assembly-top`, `assembly-bottom`, `net-<net>` for the ground and supply nets, `classes`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning* ("Locate the microcomputer next to the voltage regulator, and the voltage regulator next to where VBatt enters the board"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Grounding in mixed-signal systems demystified, Part 2*, Analog Applications Journal 2Q 2013, SLYT512, section *Grounding when multiple data converters are used on a single board* ("The power should enter the board in the digital partition and be fed directly to the digital circuitry, then filtered or regulated to feed the analog circuitry"), https://www.ti.com/lit/pdf/slyt512, read 2026-10-14.

#### FLOOR-4. A part that its floorplan region does not list stays out of that region, by the board's rules

- **Applies when:** always.
- **Asks:** Does the board's rules file keep every footprint out of each floorplan region that does not list it, so that a part moved across a region's bound fails the pre-order check?
- **Passes:** For each region that the floorplan of `layout-plan.md` gives, the board carries a rule area named for the region, drawn at the region's bounds on every copper layer, and its rules file holds one custom rule for the region, in this form, with one `A.Reference != '<part>'` for each part the floorplan lists in the region:

  ```
  (rule "<region> region parts"
  	(condition "A.Type == 'Footprint' && A.intersectsArea('<region>') && A.Reference != '<part>'")
  	(constraint disallow footprint))
  ```

  A part the floorplan lists in two regions, such as one that bridges the barrier, is named in both. The pre-order check reports no `items_not_allowed` violation, and each rule's row in the board's rules table names the region, its bounds and the parts the rule lets in, which are the floorplan's. The regions are the board's own, taken from its plan, so the pre-order check cannot tell a region with no rule, or a rule listing a part its region does not, from a rule that is right; that each region has its rule, listing the floorplan's parts and no others, is judged from `layout-plan.md`, `design-rules.md` and the layout review.
- **Fails, as the views show it:** the pre-order check reports an `items_not_allowed` violation naming a footprint; or, in `design-rules.md`, a region has no row, or a row's bounds or parts differ from the floorplan's.
- **Judged on:** the pre-order check's report, `design-rules.md`, `layout-plan.md`.
- **Kind:** rule. **Severity:** function.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 2, finding 2.1, which records a connector whose body crossed out of its region, and for the practice Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning*, https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### FLOOR-5. Each connector stands where the connector table puts it

- **Applies when:** the schematic carries a connector, terminal or header.
- **Asks:** Does the pin 1 of every connector lie within 2.54 mm of the position the floorplan's connector table gives it, on the edge the table names?
- **Passes:** Each connector's pin 1 is on the edge its row names and within 2.54 mm of its row's position.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, read against the board coordinates in the caption, a connector's pin 1 more than 2.54 mm from its table position.
- **Judged on:** `assembly-top`, `assembly-bottom`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** `hardware/proof/method-proof/layout-review.md`, round 1, finding 1.7.

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
- **Judged on:** `net-<net>` for each power-class net, `facts.txt`, `classes`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 5 *Traces and Ground Plane* ("Make all of the power (high current) traces as short, direct, and thick as possible"), https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### POWER-3. A current that changes layer passes through one via for every 200 mA

- **Applies when:** the schematic carries a supply input or a part that switches a load.
- **Asks:** Where a path carrying supply or load current changes copper layer, does it pass through at least one via of the board's standard size for every 200 mA of the current it carries, the path out and the path that returns the current alike?
- **Passes:** At each place a path carrying supply or load current changes layer, the vias sharing its current number at least the path's continuous current divided by 200 mA, rounded up, each of the board's standard via size, the via size its rules give as the board's default. The path is the supply or load current's whole loop, so a return that reaches a ground plane through vias is held to it as much as the supply that left, whatever net class carries it: the figure of such a return is the current its class's `POWER-1` row reads from the constraints record. A board of one copper layer, or one whose power paths never change layer, meets it with no such via; its plan row says which, and for a path that will change layer, the number of vias its current needs. The count is made for each path at each place it changes layer, against that path's own current: the vias of another path of the same class, or of the same net elsewhere, are not counted toward it.
- **Fails, as the views show it:** on `net-<net>` for a power net or for the net that returns its current, a single via carrying the whole of a path's current from one layer to another; in `facts.txt`, a power net or a return net whose via count is lower than its layer changes need.
- **Judged on:** `net-<net>` for each power-class net and for each net that returns a supply or load current, `facts.txt`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 5 *Traces and Ground Plane* ("use one standard via per 200 mA of current if the trace will need to conduct a significant amount of current from one plane to the other"), https://www.ti.com/lit/pdf/snva021, read 2026-10-14; amended after `hardware/proof/review-proof/layout-review.md`, round 1, finding 1.2, which records a load's 1.0 A return reaching the ground planes through one via because the item spoke only of power-class nets; and after `hardware/proof/method-proof/layout-review.md`, round 1, whose verdict on this item counts the vias at each place a path changes layer against that path's own current.

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
- **Passes:** Under every track, on the adjacent layer, the ground plane is solid. Nothing cuts the plane under a track: no track buried in the ground layer, no slot, and no row of via or hole clearances merging into a slot; where a row of through-hole pins crosses the plane, copper runs between the pins. A pin's thermal-relief gap and its clearance ring are openings in the plane like any other: copper runs between one pin's ring and the next pin's, not only between their pads, so no two pins' rings merge into one opening.
- **Fails, as the views show it:** on a plane's `layer-<copper layer>` read against `net-<net>` for a signal, a track crossing a cut, a slot or a merged row of clearances in the plane beneath it, or a track routed on the ground layer itself dividing the plane in two.
- **Judged on:** every `layer-<copper layer>` holding ground, `net-<net>` for each critical signal net.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.1.4 *Signal Return Grounds* and § 2.1.7 *Power Plane Do's and Don'ts for Four-Layer Boards* (Figure 5), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.5 *Reference Planes* and § 4.6 *Routing*, item 4, https://www.ti.com/lit/pdf/slla284, read 2026-10-14; amended after `hardware/proof/method-proof/layout-review.md`, round 1, finding 1.1, which records the thermal-relief ring of one connector pin merging with the clearance ring of the next on both inner planes while the plan row said no ring merges.

#### GROUND-3. One ground plane is partitioned, not split

- **Applies when:** the schematic carries a sensing front end feeding a converter, alongside digital logic.
- **Asks:** Is the ground one plane, partitioned by where parts and tracks sit, rather than split into separate analog and digital planes; and where the board does carry a split, does every track crossing it cross at a single bridge joining the two?
- **Passes:** One ground plane under both the analog sensing and the digital regions, with the regions kept apart by placement and routing (`FLOOR-2`). Where a design reason forces separate planes, they are joined at one place, and every track passing between them crosses at that bridge, over copper.
- **Fails, as the views show it:** on a ground `layer-<copper layer>` or `net-<net>`, a gap separating an analog ground area from a digital one with a track crossing the gap away from any bridge, or two planes joined only at the supply input.
- **Judged on:** every `layer-<copper layer>` holding ground, `net-<net>` for each ground net and each net crossing between regions.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Grounding in mixed-signal systems demystified, Part 2*, Analog Applications Journal 2Q 2013, SLYT512, the opening passage and Figures 1 to 5 ("It is always preferable to use only one ground plane, partitioning the PCB into analog and digital sections"; "the planes should first be connected at one location to form a bridge for the return current"), https://www.ti.com/lit/pdf/slyt512, read 2026-10-14.

#### GROUND-4. A part's analog and digital ground pins join the same plane at the part

- **Applies when:** the schematic carries an integrated circuit with a ground pin, a part with separate analog and digital ground pins, such as a converter, among them.
- **Asks:** Are that part's ground pins, the analog and digital ones where it has both, joined, at the part, to the same low-impedance ground plane by the shortest connections?
- **Passes:** Each ground pin goes straight to the plane under the part by the shortest connection, a via of its own beside the pad or ground copper under the part rather than a neck of pour or a track, the analog and digital ground pins to the same plane.
- **Fails, as the views show it:** on `crop-<reference>`, the digital ground pin routed away by a track to a distant ground, or the two ground pins joined to different copper areas.
- **Judged on:** `crop-<reference>`, `net-<net>` for the ground nets.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Grounding in mixed-signal systems demystified, Part 1*, Analog Applications Journal 1Q 2013, SLYT499, the section on interpreting AGND and DGND pins ("the AGND and DGND pins should be joined together externally to the same low-impedance ground plane with minimum lead lengths"), https://www.ti.com/lit/pdf/slyt499, read 2026-10-14; amended after `hardware/proof/method-proof/layout-review.md`, round 1, finding 1.4, which records a regulator's only ground pin reaching the planes through a 2 mm neck of pour with the nearest ground via 3.9 mm away, where the plan row promised each ground pad its own vias.

#### GROUND-5. No two plated holes stand so close that their rings merge in a plane

- **Applies when:** always.
- **Asks:** Are every two plated holes of the board far enough apart that, on a layer holding a ground plane or pour, their clearance rings and thermal-relief rings leave copper between them?
- **Passes:** The board's rules file holds this custom rule, with `<figure>` the least distance between the edges of two plated holes at which their rings leave plane copper between them, and KiCad's layout rule check reports no `hole_to_hole` violation of it; or, for a board with no plated pin in a ground plane, which has no figure, `design-rules.md` states the item as none with that reason and the rules file holds no such rule:

  ```
  (rule "Plated hole spacing"
  	(condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole' && B.Type == 'Pad' && B.Pad_Type == 'Through-hole'")
  	(constraint hole_to_hole (min <figure>mm)))
  ```

  `<figure>` is taken over the board's plated pins that open a gap in a ground plane, a pin being in a plane when its pad lies within the outline of a ground-net zone on a layer where that zone is filled: twice the widest annulus width among those pins (half a pad's diameter less half its drill), plus twice the larger of the gaps those pins open in the plane, plus the zone's minimum thickness, each read from the board's own zones, net classes and rules and written in the rule's row. The gap a pin opens in the plane is the thermal-relief gap of the ground zones for a ground pin; for any other pin it is the greatest of the ground zone's clearance, the clearance of the net class of the pin's net, and the clearance any rule of the board's rules file states for that pin in that plane, since KiCad applies the greatest of them. A pin outside the outline of every ground plane enters neither the annulus term nor the gap terms, and a zone, class or rule that does not govern a pin in the plane enters neither, so a mains pour, or a mains connector in a mains region outside the ground planes, does not enlarge the figure; a mains pin's clearance enters only when that pin itself lies in a ground plane. A board with no plated pin in a ground plane has no figure and needs no rule; its row in `design-rules.md` states the item as none, for that reason. The rule keeps its condition on every pair of plated pads: the figure is the least spacing at which rings in a plane cannot merge, and a pair outside every plane that stands closer is held to it as a margin. The derivation: each plated pin in a plane opens a gap around its pad, a thermal-relief gap for a ground pin and a clearance for any other, so between two pins the plane keeps copper only where the distance between the hole edges exceeds the two pads' annulus widths, plus the two gaps the pins open, plus the zone's minimum thickness. Two ground pins open two relief gaps, a ground pin and another pin open a relief gap and a clearance, and two other pins open two clearances. The pair that opens the widest gaps is the one whose gaps are both the larger value, so twice the larger value covers every pair. KiCad does not report a gap between two rings that leaves no copper to measure, so the figure is made large enough that none can form. A pad that is not round is read by its width along the line to the nearest other plated hole, such as across the pin pitch of a row, which is the dimension that enters the gap between the two, not by its longer side; the row states the pad and the dimension it took.

  Worked for the review-proof design, from its board files. Four plated pins lie in a ground plane: pads 1 and 2 of `J2` and of `J4`. Each pad is 1.7 mm across the pin pitch with a 1.0 mm drill, so the widest annulus among them is (1.7 − 1.0) / 2 = 0.35 mm and twice it is 0.70 mm. The ground zones' thermal-relief gap is 0.25 mm, opened by the ground pin (`J2` pad 2), and the ground zone's clearance is 0.2 mm, opened by the others; the larger is 0.25 mm and twice it is 0.50 mm. The ground zones' minimum thickness is 0.25 mm. The figure is 0.70 + 0.50 + 0.25 = 1.45 mm, against 1.50 mm between the hole edges of the closest pairs of those pins. The board's mains pours state a clearance of 3 mm and its mains connector has a wider annulus, but neither lies in a ground plane, so neither enters.
- **Fails, as the views show it:** on a plane's `layer-<copper layer>`, the rings of two pins merged into one keyhole opening with no copper between them; KiCad reports a `hole_to_hole` violation; or, in `design-rules.md`, no row stating the figure or stating none with its reason.
- **Judged on:** the pre-order check's report, `design-rules.md`, every `layer-<copper layer>` holding a ground plane or pour.
- **Kind:** rule. **Severity:** function.
- **Source:** `hardware/proof/method-proof/layout-review.md`, round 1, finding 1.1; for the practice, `GROUND-2`; the reading of a pad that is not round is that review's, round 4, verdict on this item.

### Decoupling and switching loops (DECOUPLE)

#### DECOUPLE-1. Each decoupling capacitor sits at its supply pin, with nothing between them

- **Applies when:** the schematic carries an integrated circuit with a decoupling capacitor on a supply pin.
- **Asks:** Is each decoupling capacitor next to the supply pin it decouples, the smallest nearest, with the supply reaching the pin through the capacitor's pad and no via between capacitor and pin?
- **Passes:** Each capacitor sits beside its pin, joined to it by a short, wide track. Where a pin has more than one, the smallest value is closest. The supply arrives at the capacitor first and then goes on to the pin; any via to the supply plane is on the far side of the capacitor from the pin.
- **Fails, as the views show it:** on `crop-<reference>`, a decoupling capacitor across the part or on the far side of the board from its pin, a via between capacitor and pin, or a supply track reaching the pin before the capacitor; a crop captioned as having no decoupling parts for a part whose schematic gives it some.
- **Judged on:** `crop-<reference>` for each integrated circuit, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Tim Claycomb, *The basics: How to layout a PCB for an op amp*, Texas Instruments, Precision Hub blog, 8 January 2016, closing list of layout practices ("Place decoupling capacitors as close to the supply pins as possible"; "If using multiple decoupling capacitors, place the smallest decoupling capacitor closest to the supply pin"; "Do not place vias between decoupling capacitors and supply pins"), https://e2e.ti.com/blogs_/archives/b/precisionhub/posts/the-basics-how-to-layout-a-pcb-for-an-op-amp, read 2026-10-14; and Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("Avoid placing vias between the supply pin and its decoupling capacitor"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14.

#### DECOUPLE-2. The decoupling loop is small, its ground side straight into the plane

- **Applies when:** the schematic carries an integrated circuit with a decoupling capacitor on a supply pin.
- **Asks:** Is the loop from the supply pin through the capacitor and back to the part's ground pin as small in area and length as it can be, with the capacitor's ground side going straight into the ground plane?
- **Passes:** The capacitor's ground pad joins the plane at once, through two vias of its own beside the pad where it changes layer, or through ground copper extended from under the part rather than a track. A pad joined to a pour only through thermal reliefs, with at most one via near it, is neither: it needs its two vias. The supply and ground sides run over or beside each other, so the loop encloses little area seen from above.
- **Fails, as the views show it:** on `crop-<reference>`, the capacitor's ground pad reaching ground by a long track, or the loop through capacitor and part enclosing a wide area.
- **Judged on:** `crop-<reference>`, `net-<net>` for the ground net.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.2.4 *Bypassing and Ferrite Beads* ("Make the bypassing loops as small as possible in area and length"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.6 *Routing*, item 10 (the capacitor's ground side "through two vias to the ground plane"), https://www.ti.com/lit/pdf/slla284, read 2026-10-14; amended after `hardware/proof/method-proof/layout-review.md`, round 1, finding 1.3, which records capacitors' ground pads joined to a pour through reliefs with one via each, where the plan row promised two vias beside each.

#### DECOUPLE-3. A switching converter's power parts form tight loops that curl the same way

- **Applies when:** the schematic carries a switching converter, a circuit that switches current through an inductor or a transformer.
- **Asks:** Are the converter's input capacitor at its input pin, its inductor, output capacitors and switch or diode close together, their grounds joined close together straight into the ground plane, and placed so that the current loop in each switching state turns the same way?
- **Passes:** The input capacitor sits at the converter's input pin. The inductor, the output capacitors and the diode, where there is one, sit together, so the loops the switching current takes in its on and off states are small. The grounds of the converter, its input capacitors, its output capacitors and its diode join close together, directly to a ground plane. The loop in the on state and the loop in the off state run in the same direction round the parts.
- **Fails, as the views show it:** on `crop-<reference>` of the converter and on `layer-<copper layer>`, the input capacitor away from the input pin, the inductor separated from the output capacitors by other parts, or the converter's ground and the capacitors' grounds joined only by long tracks.
- **Judged on:** `crop-<reference>` of the converter, every `layer-<copper layer>`, `assembly-top` or `assembly-bottom`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 3 *Filter Capacitors* and § 5 *Traces and Ground Plane* ("Arrange the components so that the switching current loops curl in the same direction"), https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### DECOUPLE-4. A switching converter's feedback is kept away from its inductor

- **Applies when:** the schematic carries a switching converter with a feedback connection, or with external feedback or compensation parts.
- **Asks:** Does the feedback trace run as far from the inductor and the noisy power traces as the board allows, with its feedback and compensation parts close to the converter and away from the inductor?
- **Passes:** The feedback trace runs direct to the feedback pin, away from the inductor, on the side of the board opposite the inductor with a ground plane between them where the layers allow. The feedback and compensation parts sit at the converter's pins, not beside the inductor.
- **Fails, as the views show it:** on `layer-<copper layer>` and `crop-<reference>`, the feedback trace passing under or beside the inductor, or the compensation parts placed next to it.
- **Judged on:** `crop-<reference>` of the converter, every `layer-<copper layer>`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *AN-1149 Layout Guidelines for Switching Power Supplies*, SNVA021C, revised April 2013, § 2 *Feedback* and § 4 *Compensation*, https://www.ti.com/lit/pdf/snva021, read 2026-10-14.

#### DECOUPLE-5. A snubber sits at the switch it protects

- **Applies when:** the schematic carries a snubber, a resistor and capacitor in series across a switching part such as a triac or phototriac.
- **Asks:** Is the snubber placed as close to the switching part as it can be?
- **Passes:** The snubber's resistor and capacitor sit beside the switch, joined to its terminals by short connections.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, the snubber's parts placed away from the switch, reached by long tracks.
- **Judged on:** `assembly-top`, `assembly-bottom`, `layer-<copper layer>`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Vishay Semiconductors, *VO3526 Power Phototriac Design Considerations*, Application Note 33, document 81937, Rev. 1.1, 19 October 2011, section *Snubber Circuit* and Figure 5 ("Locate the snubber circuit as close to the VO3526 as possible"), https://www.vishay.com/docs/81937/appnote.pdf, read 2026-10-14.

#### DECOUPLE-6. No via of a decoupling capacitor's supply net lies between the capacitor and the pin it decouples

- **Applies when:** the schematic carries an integrated circuit with a decoupling capacitor on a supply pin.
- **Asks:** Is there no via of the capacitor's supply net inside the box that the capacitor's supply pad and the supply pin it decouples span between them?
- **Passes:** The pre-order check reports no `decoupling_via` violation. The check takes each integrated circuit's supply nets from the pads typed as power input or power output that the board file holds, a decoupling part as `DECOUPLE-1` describes it (a two-pad part across two of a circuit's supply nets, belonging to the nearest circuit), and, for each, the box that bounds the capacitor's pad on the supply net that is not a ground-class net and the nearest pad of the circuit on that net. A via on that net whose centre lies in the box, or whose copper reaches into it, is a violation. Its figure is none, no via, so it is no project text variable; the check's report states it in a `FIGURE` line for the item, and its row in `design-rules.md` is the inherent-zero row that step 1 of [Rules before routing](#rules-before-routing) describes. An integrated circuit here is a footprint whose reference begins with `U`, as the layout review views' circuits are and `hardware/README.md` says, and a part's pads must carry a pin type, set from the schematic's netlist as the list of what Konnect's tools lack in [The board editor, driven by an agent](#the-board-editor-driven-by-an-agent) describes. The report's `DECOUPLE-6 decoupling paths measured` line gives how many paths of how many circuits the check measured. A board not marked `NOT_FOR_MANUFACTURE` whose integrated circuit has netted pads and none typed power input or power output is refused by the pre-order check, as a `decoupling_pintype` violation, so such a board is not ordered. An integrated circuit that has no supply pin, an optocoupler or opto-triac, is skipped only when its position's catalogue extract entry carries the optional `category` key, the first category name of the part's parts-library record, and that category is one of the closed list of two no-supply strings in `hardware/README.md` (The no-supply categories); a skipped part with a pad typed power input or power output still fails, and every other case, an extract that cannot be read or is unusable, a catalogue number that is `none` or absent from the extract, an entry without a category and a category outside the list, is refused. What the check does not measure, which the reviewer judges on the views: a decoupling part is attributed to its nearest circuit only, so a capacitor on a rail shared by several circuits is measured against one; a part with more than two pads is not a decoupling part; a circuit whose ground pin is not typed as a power pin takes no ground-class supply net, so a capacitor across its supply and ground is never attributed to it; and a part referenced otherwise than with `U` is not a circuit.
- **Fails, as the views show it:** the pre-order check reports a `decoupling_via` violation; or, on `crop-<reference>`, a via of the supply net between the capacitor's pad and the pin, such as the tap that takes a branch of the supply to another part.
- **Judged on:** the pre-order check's report, the `design-rules.md` row for the rule `decoupling_via`, and `crop-<reference>` for each integrated circuit.
- **Kind:** rule. **Severity:** function.
- **Source:** `hardware/proof/method-proof/layout-review.md`, round 1, finding 1.2; for the practice, `DECOUPLE-1`.

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
- **Judged on:** `crop-<reference>` of the converter or controller, `assembly-top`, `assembly-bottom`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("The fly-wheel RC filters are placed immediately next to the input pins"; the reference capacitor "within 0.1-inches from the pin"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14.

#### SENSE-3. An amplifier's high-impedance input connections are as short as possible

- **Applies when:** the schematic carries an operational or instrumentation amplifier.
- **Asks:** Are the connections to the amplifier's inverting input, a high-impedance node, as short as they can be, with its feedback and gain resistors placed at that pin?
- **Passes:** The feedback and gain resistors sit next to the inverting pin, joined to it by the shortest tracks, with no track on that node wandering across the board.
- **Fails, as the views show it:** on `crop-<reference>` of the amplifier, a feedback or gain resistor placed away from the inverting pin, reached by a long track.
- **Judged on:** `crop-<reference>` of the amplifier, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Tim Claycomb, *The basics: How to layout a PCB for an op amp*, Texas Instruments, Precision Hub blog, 8 January 2016 ("Make the connections to the inverting pin as short as possible"), https://e2e.ti.com/blogs_/archives/b/precisionhub/posts/the-basics-how-to-layout-a-pcb-for-an-op-amp, read 2026-10-14.

#### SENSE-4. Sensing signals keep away from noise sources

- **Applies when:** the schematic carries a sensing front end.
- **Asks:** Do the sensing inputs and the converter's reference run away from noise sources: switching nodes, power tracks, relays and their drivers, the oscillator, and connectors carrying other signals?
- **Passes:** Each sensing net runs within the analog sensing region, kept apart from switching converters, load switches, relay coils and their drivers, the crystal and other connectors' signal tracks, and runs as far from supply lines as the board allows. The clearance from the net classes the board rules record names as noisy is held by `SENSE-6`; this item keeps what a rule cannot decide: a noise source no net class names, the region the sensing runs in, and a sensing track running alongside a noisy one over a length.
- **Fails, as the views show it:** on `net-<net>` for a sensing net, or on `classes`, a sensing track running alongside a power or switching track or past a relay, its driver or the crystal.
- **Judged on:** `net-<net>` for each sensing net, `classes`, every `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("keep the analog input signals and the reference input signals away from noise sources"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14; and Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.4.1 *Capacitive and Inductive Crosstalk* ("Keep non-noisy traces away from areas on the board were they could pick up noise, such as connectors, oscillator circuits, relays, and relay drivers"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *TLV333, TLV2333, TLV4333* data sheet, SBOS751, December 2015, § 11.2 *Layout Example* ("Run the input traces as far away from the supply lines as possible"), https://www.ti.com/lit/ds/symlink/tlv333.pdf, read 2026-10-14.

#### SENSE-5. Precision sensing parts are kept away from heat sources

- **Applies when:** the schematic carries a sensing front end.
- **Asks:** Are the sensing front end's amplifier, its input parts and the converter's reference placed away from the board's heat sources, with the two sides of each differential input at the same temperature?
- **Passes:** Regulators, power resistors, load switches and other parts that dissipate heat sit outside and away from the analog sensing region. The parts on the two sides of a differential input sit together, symmetrically, so no heat source warms one side more than the other.
- **Fails, as the views show it:** on `assembly-top`, `assembly-bottom` or `3d-angled`, a regulator or power part placed beside a sensing amplifier or its input parts, or a heat source nearer one input's parts than the other's.
- **Judged on:** `assembly-top`, `assembly-bottom`, `3d-angled`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *TLV333, TLV2333, TLV4333* data sheet, SBOS751, December 2015, § 11.1.1 *General Layout Guidelines* ("Avoid temperature gradients that create thermoelectric (Seebeck) effects"; "Thermally isolate components from power supplies or other heat sources"), https://www.ti.com/lit/ds/symlink/tlv333.pdf, read 2026-10-14.

#### SENSE-6. Sensing nets keep the declared clearance from switching and drive nets

- **Applies when:** the schematic carries a sensing front end.
- **Asks:** Does every sensing net keep at least the clearance the board rules record declares from the nets that switch or drive loads, and does no pad or footprint on one of those nets carry a local clearance override below it?
- **Passes:** The pre-order check reports no `sensing_clearance` and no `sensing_override` violation. The board rules record's `sensing` mapping names the net classes that carry precision sensing, the net classes that switch or drive loads, the clearance in millimetres and the figure's source; the check holds each sensing and noisy class pair to that clearance, and a pair with the `Mains` class to the larger of it and the signed clearance. Its figure is a record figure, so it is no project text variable; the report states it in a `FIGURE` line for the item, whose source field reads `board-rules.yaml sensing.clearance_mm`, and its row in `design-rules.md` states the same figure, the classes the record names and the key. A design with no sensing net class states `none` for the mapping, which the check accepts and which the plan row for this item records with its reason. What the check does not measure is judged under `SENSE-4`.
- **Fails, as the views show it:** the pre-order check reports a `sensing_clearance` or `sensing_override` violation; or, on `net-<net>` for a sensing net or on `classes`, a sensing track closer to a track, pad or via of a noisy class than the figure in the row.
- **Judged on:** the pre-order check's report, the `design-rules.md` row for the rules `sensing_clearance` and `sensing_override`, `net-<net>` for each sensing net, `classes`.
- **Kind:** rule. **Severity:** function.
- **Source:** the figure is the board's own, read from `sensing.source` of its board rules record, since no published practice states one; the practice is `SENSE-4`'s, Texas Instruments, *ADS8866* data sheet, SBAS614C, March 2019, § 12.1 *Layout Guidelines* ("keep the analog input signals and the reference input signals away from noise sources"), https://www.ti.com/lit/ds/symlink/ads8866.pdf, read 2026-10-14.

### Clocks (CLOCK)

#### CLOCK-1. The crystal and its load capacitors sit at the oscillator pins

- **Applies when:** the schematic carries a crystal or a ceramic resonator.
- **Asks:** Are the crystal and its load capacitors close to the oscillator pins, the input pin's capacitor placed first and closest, the two load capacitors close to each other, and the input and output tracks short and kept apart from each other?
- **Passes:** The crystal sits at the controller's oscillator pins, its tracks short and direct. The load capacitor on the oscillator input sits closest to that pin and to ground; the two capacitors sit side by side. The input and output tracks are routed apart rather than side by side.
- **Fails, as the views show it:** on `crop-<reference>` of the controller, the crystal placed away from its pins with long tracks, the load capacitors apart from each other, or the input and output tracks running in parallel.
- **Judged on:** `crop-<reference>` of the controller, `layer-<copper layer>`, `placement`.
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
- **Passes:** No part unrelated to the oscillator sits within 10 mm of the crystal, measured from the crystal's body to the part's body. A part is related to the oscillator when it is the crystal or ceramic resonator, one of its load capacitors, the controller whose oscillator pins it joins, or a part `FLOOR-3` and `DECOUPLE-1` place beside that controller: its decoupling capacitors, and the regulator that feeds it with the regulator's own capacitors; or one of the controller's own pin-side parts, a closed list: the series resistors on its pins; the pull-up, pull-down and filter parts on its pins; its reset network (the supervisor driving the reset pin, that pin's resistor, capacitor and button); its boot-mode network (the resistor, button or link on the boot pin); its debug header and the test points on its debug and reset pins; and any other crystal or resonator on its oscillator pins with that one's load capacitors. A test point on a supply net is not pin-side. Every other part keeps the 10 mm. No digital or clock line runs near the crystal's tracks. The oscillator is away from the analog sensing region and from every connector.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, read against the caption's board coordinates, an unrelated part within 10 mm of the crystal, measured body to body, or the crystal beside a connector or the analog sensing region; on `layer-<copper layer>`, a digital track running beside the crystal's tracks.
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning* ("It is especially important that oscillator tank loops be located away from analog circuits, low-speed signals, and connectors") and § 2.4.1 *Capacitive and Inductive Crosstalk* ("No unrelated components should be closer than 1 inch to the crystal"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Microchip Technology (Atmel), *AVR186: Best Practices for the PCB Layout of Oscillators*, Atmel-8128B, September 2016, § 2 *Design Guides* ("Keep other digital signal lines, especially clock lines and frequently switching signal lines, as far away from the crystal connections as possible"), https://ww1.microchip.com/downloads/en/AppNotes/Atmel-8128-Best-Practices-for-the-PCB-layout-of-Oscillators_ApplicationNote_AVR186.pdf, read 2026-10-14; amended after `hardware/proof/review-proof/layout-review.md`, round 1, finding 1.5, which records the 25 mm measured from the crystal's centre by the plan where its source's "closer than 1 inch to the crystal" reads from the crystal itself, and the regulator that the keep-clear and `FLOOR-3` put in conflict; and after `docs/sunbeam-em7000/controller-board-division.md`, the `MCU` block, whose crystal stands beside a 100-pin controller that has its own pin-side parts within 25 mm unavoidably; and lowered from 25 mm to 10 mm by the owner, because the one-inch figure of its source is conservative for the 8 MHz and 32.768 kHz crystals the boards use, and what protects such a crystal is close load capacitors, short tracks, ground beneath it and no digital track beside it, each of which has its own item.

#### CLOCK-4. Parts unrelated to the oscillator keep 10 mm from the crystal's courtyard, by the board's rules

- **Applies when:** the schematic carries a crystal or a ceramic resonator.
- **Asks:** Does the board's rules file hold every part unrelated to the oscillator at least 10 mm from the crystal?
- **Passes:** The board's rules file holds this custom rule, with the crystal's reference designator for `<crystal>` and one `B.Reference != '<part>'` for each part related to the oscillator as `CLOCK-3` defines it, and the pre-order check reports no `courtyards_overlap` violation of it and no `crystal_keepclear` violation, which it reports for a board with a crystal whose rules file lacks the rule in this form, or whose rule exempts every other part:

  ```
  (rule "Crystal keep-clear"
  	(condition "A.Reference == '<crystal>' && B.Reference != '<part>'")
  	(constraint courtyard_clearance (min 10mm)))
  ```

  The figure is `CLOCK-3`'s 10 mm, and the rule's row in the board's rules table names that item as its source. KiCad measures between courtyards, which lie outside the parts' bodies, so a part clear of the crystal by its courtyard is clear of it by its body; it compares the courtyards of one side of the board only, so a part on the other side is judged by `CLOCK-3` on the views.
- **Fails, as the views show it:** the pre-order check reports a `courtyards_overlap` or `crystal_keepclear` violation; or, in `design-rules.md`, no row for the rule, a figure below 10 mm, or a part exempt from it that `CLOCK-3` counts unrelated.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** function.
- **Source:** the source of `CLOCK-3`, and `hardware/proof/review-proof/layout-review.md`, round 1, finding 1.5, which records the parts found within 25 mm of the crystal and the rule that states it.

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
- **Judged on:** `classes`, every `layer-<copper layer>`, `assembly-top`, `assembly-bottom`, `placement`.
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

#### MAINS-5. No copper lies between the pad rows of a part that bridges the barrier

- **Applies when:** the schematic carries a part with pins on both a mains-referenced net and a net outside the `Mains` class, such as an optocoupler, an isolator, a relay or a transformer.
- **Asks:** Is there no copper of any net, on any copper layer, in the strip between the pads on the part's mains side and the pads on its other side?
- **Passes:** The board's project text variable `BARRIER_COPPER_MM2` is set to 0, with its row in the board's rules table, and the pre-order check reports no `mains_barrier` violation. For each part with pads on a `Mains`-class net and on another net, the check takes the box of the copper of each group of pads, and where the two boxes lie apart along one axis, the strip between their inner edges over the extent of both. It adds up the area of every track, via, pad and filled pour of the board that lies in the strip, on each copper layer, and fails any part whose area exceeds the figure. The check refills the board's pours before it measures, so a pour left unfilled or filled before an edit cannot hide copper. A part whose two groups' boxes overlap along both axes has no strip to measure, and a part whose numbered, coppered pads off the `Mains` class have no net is not known to bridge the barrier; the check fails each by name as not measurable, since the barrier rule does not support such a part, and the board uses a part whose `Mains`-class pads lie apart from its other pads along one axis, with every numbered, coppered pad that is not `Mains`-class on a net, a pin meant to be open being flagged no-connect in the schematic. A pad on a `Mains`-class net is a `Mains`-class pad whatever its number, copper layer or net name, even one named `unconnected-(...)`. A pad with no net is in neither group when it has no number or no copper layer, and when it is on a net named `unconnected-(...)` that no other pad carries; a net of that name carried by two or more pads is a real net. A part whose pads off the `Mains` class are all such pads is not judged, which includes, as an accepted limit, a netless pad with no number but with copper, such as a floating tab. The copper of those pads is still added up in the strip.
- **Fails, as the views show it:** the pre-order check reports a `mains_barrier` violation; or, in `design-rules.md`, no row for `BARRIER_COPPER_MM2`, or a figure above 0.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** safety.
- **Source:** Texas Instruments, *Digital Isolator Design Guide*, SLLA284G, revised September 2023, § 4.3 *Creepage Distance* ("on all layers keep the space under the isolator free from traces, vias, and pads to maintain maximum creepage distance"), https://www.ti.com/lit/pdf/slla284, read 2026-10-14; and `hardware/proof/review-proof/layout-review.md`, round 2, finding 2.4, which records mains copper reaching 1.31 mm under an isolator toward its low-voltage pads.

### Connectors and mechanical fit (CONN)

#### CONN-1. A transient suppressor sits at its connector, on the line's path

- **Applies when:** the schematic carries a transient-voltage or electrostatic-discharge suppressor on a line that leaves the board at a connector.
- **Asks:** Is the suppressor as close to the connector as the rules allow, with the line running straight from the connector pin to the suppressor's pin, with no via and no stub, then on to what it protects, and with no unprotected track alongside it between the connector and the suppressor?
- **Passes:** The suppressor sits at the connector, and the protected circuit sits much further from it. The line runs from the connector pin to the suppressor's pin in a straight track, curved or at 45° where it must turn, then on. The suppressor's ground goes straight into the plane by the shortest path. No unprotected track runs in the area between connector and suppressor.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, the suppressor placed by the part it protects rather than by the connector; on `layer-<copper layer>`, the line reaching the suppressor through a stub or a via, a right-angled turn, or another track running beside it between connector and suppressor.
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`, `placement`.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ESD Protection Layout Guide*, SLVA680A, revised April 2022, § 2.1 *Optimizing Impedance for Dissipating ESD*, § 2.2 *Limiting EMI from ESD* and § 2.3 *Routing with VIAs*, https://www.ti.com/lit/pdf/slva680, read 2026-10-14.

#### CONN-2. Thin leadless packages keep away from where the board bends

- **Applies when:** the schematic carries a leadless package, such as a QFN or SON.
- **Asks:** Is each leadless package placed away from the regions of the board that bend most in manufacture and use, such as beside connectors that take mating force, mounting holes and the board's edges where it is handled?
- **Passes:** Each leadless package sits away from connectors, mounting holes and board edges, in a part of the board held flat. The distance that counts as away from a connector or a mounting hole, courtyard to courtyard, is a figure of the board, not of this item: the plan row for this item states it, taken from the machine's constraints record, and the review judges the package against it.
- **Fails, as the views show it:** on `assembly-top`, `assembly-bottom` or `3d-angled`, a QFN or SON beside a connector, at a mounting hole or at the board's edge.
- **Judged on:** `assembly-top`, `assembly-bottom`, `3d-angled`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *QFN and SON PCB Attachment*, SLUA271C, revised December 2023, § 3.7 *Board Layout Considerations* ("Location of the thinner format QFN packages should be carefully considered when laying out the board design to avoid regions of extreme deflection"), https://www.ti.com/lit/pdf/slua271, read 2026-10-14.

#### CONN-3. No cable folds over the oscillator or the controller

- **Applies when:** the schematic carries a connector for a cable, and a controller or a crystal.
- **Asks:** Is each cable connector placed so that its cable, once fitted, cannot lie over the oscillator or the controller?
- **Passes:** Each cable connector sits at the board edge `layout-plan.md` gives it, facing off the board, so its cable leaves without crossing the controller or the crystal. A connector whose mating direction is perpendicular to the board has no facing, and is taken to leave its cable toward the board edge its row in the connector table names; it meets this item when the straight line from its courtyard to that edge crosses neither the controller's nor the crystal's courtyard.
- **Fails, as the views show it:** on `3d-angled`, `3d-top` or `assembly-top`, a cable connector facing inward across the controller or the crystal, or placed so its cable must pass over them.
- **Judged on:** `3d-angled`, `3d-top`, `3d-bottom`, `assembly-top`, `assembly-bottom`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.3 *Board Zoning* ("Do not design in cable assemblies that fold over the oscillator or the microcomputer after final assembly"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; amended after `hardware/proof/method-proof/layout-review.md`, round 1, whose verdict on this item reads the item's facing off the board as the cable leaving away from the controller for a top-entry connector, which has no facing.

#### CONN-4. A board is held at mounting holes that keep a cable's force off its parts

- **Applies when:** the schematic carries a connector or a screw terminal for a cable.
- **Asks:** Does the board have mounting holes that hold it where its connectors take their cables' forces, clear of copper and of every part, and away from leadless packages?
- **Passes:** At least three mounting holes stand in a spread that holds the board without rocking, each beside a board edge that carries a connector or between connectors, each with copper cleared from it by the board's copper-to-hole minimum, none within a part's courtyard, and none beside a leadless package or a crystal, as `CONN-2` asks. Each hole is a part drawn on the schematic, as every footprint on the board is, and listed in its floorplan region.
- **Fails, as the views show it:** on `layer-Edge.Cuts` and `assembly-top`, no mounting hole, holes all on one side of the board, or a hole beside a leadless package; on `3d-angled`, a connector that its cable pulls on and no hole near.
- **Judged on:** `layer-Edge.Cuts`, `assembly-top`, `3d-angled`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, finding 1.51, which records a board whose screw terminal and two cable connectors took their cables' forces with nothing to hold the board. No free published document states the item.

### Test access and bring-up (TEST)

#### TEST-1. Every test point can be reached by a probe

- **Applies when:** the schematic carries a test point, which every board does ([Designing for bring-up and a second spin](#designing-for-bring-up-and-a-second-spin)).
- **Asks:** Is every test point a pad a probe can land on and stay on: a dedicated pad, a through-hole lead or a small via, never a surface-mount part's land, of a usable size, spaced from its neighbours and from tall parts?
- **Passes:** Each test point is a dedicated pad, a through-hole lead or a via with a hole of 0.36 mm or less, never a surface-mount land. Its pad is 1.0 mm across, or 0.9 mm at least. Test points are at least 2.5 mm apart centre to centre and at least 2.0 mm from a part taller than 2.6 mm. Their spacing from part outlines is `TEST-5`'s.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, a test point closer than 2.5 mm to another or crowded against a tall part; on `layer-F.Cu` or `layer-B.Cu`, a test point that is a surface-mount part's land or a pad smaller than 0.9 mm.
- **Judged on:** `assembly-top`, `assembly-bottom`, `layer-F.Cu`, `layer-B.Cu`, `3d-angled`, `placement`, for its spacing from tall parts.
- **Kind:** judgement. **Severity:** function.
- **Source:** Jack Olson, *Circuit Board Design for In-Circuit Testers*, Altium Resources, updated 27 December 2020, section *Testability Checklist at the PCB Layout Level*, https://resources.altium.com/p/circuit-board-design-circuit-testability, read 2026-10-14.

#### TEST-2. Test points are on one side, with tall parts on the other

- **Applies when:** the schematic carries a test point.
- **Asks:** Are the test points on one side of the board, the side with the fewest parts, with the tall parts on the other side?
- **Passes:** Every test point sits on the same side of the board, and parts taller than 6.4 mm sit on the other side or at least 5.0 mm from any test point.
- **Fails, as the views show it:** on `assembly-top` and `assembly-bottom`, test points on both sides, or among tall parts.
- **Judged on:** `assembly-top`, `assembly-bottom`, `3d-angled`, `placement`.
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

#### TEST-4. A voltage test pad joins the part's own pad by a track of its own

- **Applies when:** the schematic carries a resistor used to measure current, or another part whose resistance is too low to read with two probes.
- **Asks:** Does the test pad for the voltage across each such part reach the part's own pad by a track that carries no load current, rather than through a plane or from a point on the current's path?
- **Passes:** The pad for a net's voltage is joined to the part's pad by a track of its own, leaving the pad apart from the track that carries the current, with a via, where it has one, that touches no plane; a ground net's voltage pad therefore reaches the shunt's ground pad through that track alone. The pad for the current may stand anywhere on the current's path.
- **Fails, as the views show it:** on `net-<net>` for the part's nets, a voltage pad whose via branches from the current track partway along it, or from a plane, so that a reading includes the copper between the pad's point and the part.
- **Judged on:** `assembly-top`, `assembly-bottom`, `net-<net>` for the part's nets, every `layer-<copper layer>`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Jack Olson, *Circuit Board Design for In-Circuit Testers*, Altium Resources, updated 27 December 2020, section *Testability Checklist at the PCB Layout Level* ("Provide two pads on nets tied to critical low impedance devices (four-wire Kelvin testing)"), https://resources.altium.com/p/circuit-board-design-circuit-testability, read 2026-10-14, for the two pads; and `hardware/proof/review-proof/layout-review.md`, round 1, finding 1.49, which records a shunt's test pads reaching it only through the planes and a shared via. No free published document states how the voltage pad joins the part.

#### TEST-5. A test pad stands clear of every part's courtyard

- **Applies when:** the schematic carries a test point.
- **Asks:** Does every test point's pad stand far enough from the courtyard of every part, on either side of the board, that a probe can land on it with no part's outline in the way?
- **Passes:** The board's project text variable `TEST_COURTYARD_MM` is set to 1, with its row in the board's rules table, and the pre-order check reports no `test_point_courtyard` violation. A test point is a part whose reference designator begins `TP`. The check measures from the copper of its pad to the courtyard of every other footprint, on the front and on the back, taking a part's courtyard as the box about its drawing on that side's courtyard layer; the test point's own footprint is left out, and a part that draws no courtyard on a side is skipped for it. A board with no test point passes, and a board that omits the variable fails.
- **Fails, as the views show it:** the pre-order check reports a `test_point_courtyard` violation, naming the test point, the part, and the measured and required distances; or, in `design-rules.md`, no row for `TEST_COURTYARD_MM`, or a figure below 1.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** function.
- **Source:** Jack Olson, *Circuit Board Design for In-Circuit Testers*, Altium Resources, updated 27 December 2020, section *Testability Checklist at the PCB Layout Level*, https://resources.altium.com/p/circuit-board-design-circuit-testability, read 2026-10-14, for the 1.0 mm clearance of a test pad from part outlines; and `hardware/proof/review-proof/layout-review.md`, round 14, finding 14.3, which records test pads crowded by part courtyards, made a measured rule after the same finding recurred by eye.

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

#### MFG-4. Solder paste is not printed over a via's hole

- **Applies when:** always.
- **Asks:** Is no paste opening over the hole of a via, so that paste is not printed straight into a hole and lost through it?
- **Passes:** The board's project text variable `PASTE_OVER_VIA_MM2` is set to 0, with its row in the board's rules table, and the pre-order check reports no `paste_via` violation. The check takes each paste opening as its pad's shape grown by the pad's paste margin and ratio, the footprint's or the board's where the pad sets none, and measures the area of each via's hole that lies under it, on either side, failing any larger than the figure. A footprint whose paste openings fall over the vias its pad takes is drawn with openings between them, for example one opening each side of a strip that holds the vias.
- **Fails, as the views show it:** the pre-order check reports a `paste_via` violation; on `layer-F.Paste` or `layer-B.Paste` and `crop-<reference>`, an opening centred on an open via; or, in `design-rules.md`, no row for `PASTE_OVER_VIA_MM2`, or a figure above 0.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *QFN and SON PCB Attachment*, SLUA271C, revised December 2023, § 3.4.1 *Thermal Pad Via Design* ("a smaller via offers less risk of solder volume loss"; "On applications where solder volume loss through the vias is of concern, plugging or tenting can be used to achieve a repeatable process"), https://www.ti.com/lit/pdf/slua271, read 2026-10-16; and `hardware/proof/review-proof/layout-review.md`, round 1, finding 1.50, which records an exposed pad's four paste openings each centred on an open via.

#### MFG-5. A ground pad joins a pour through thermal reliefs

- **Applies when:** always.
- **Asks:** Is every pad on a ground-class net, bar an exposed thermal pad, joined to the copper pours and planes it meets through relief spokes rather than in full, so that its joint can reach soldering temperature and a chip part's two ends heat alike?
- **Passes:** The board's rules file holds this custom rule, with `<ground class>` replaced by the board's name for the class, and one `A.Reference == '<part>' && A.Pad_Number == '<n>'` for each exposed thermal pad that `POWER-4` joins in full, and the pre-order check reports no `starved_thermal` violation and no `ground_relief` violation, which it reports for a board with pads on a net class named for ground whose rules file lacks the rule in this form, or whose rule exempts a pad that is not an exposed pad:

  ```
  (rule "Ground pad reliefs"
  	(condition "A.Type == 'Pad' && A.hasNetclass('<ground class>') && !(A.Reference == '<part>' && A.Pad_Number == '<n>')")
  	(constraint zone_connection thermal_reliefs))
  ```

  KiCad applies the rule when it fills the zones, whatever connection the zone itself sets, and its layout rule check reports a relief left with fewer spokes than Board Setup's minimum resolved spokes as starved. The reliefs' gap and spoke width are the zones' own.
- **Fails, as the views show it:** on a `layer-<copper layer>` holding a pour or plane, a ground pad joined in full, with no gap or spoke round it; the pre-order check reports a `starved_thermal` or `ground_relief` violation; or, in `design-rules.md`, no row for the rule.
- **Judged on:** the pre-order check's report, `design-rules.md`, every `layer-<copper layer>` holding a pour or plane.
- **Kind:** rule. **Severity:** quality.
- **Source:** KiCad, *PCB Editor* manual, version 10.0, zone properties, *Pad connection* ("Thermal reliefs will result in small copper spokes connecting the pad to the rest of the copper zone, increasing the thermal resistance between the pad and the rest of the zone. This can be useful for hand soldering."), https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html, read 2026-10-16; and `hardware/proof/review-proof/layout-review.md`, round 1, finding 2.8, which records pads joined in full to 2 oz ground copper, one end of each chip part heating faster than the other.

#### MFG-6. A pour leaves no sliver gap between its fill and copper of its own net

- **Applies when:** always.
- **Asks:** Does every pour's fill that stops short of a track, via or pad of its own net leave a gap at least the board's minimum clearance, so that no slot can close in etching or leave a sliver?
- **Passes:** The pre-order check reports no `pour_gap` violation, and its report's `FIGURE` line for `MFG-6` gives the board's minimum clearance, which `MFG-1` holds to the manufacturer's limit. KiCad's layout rule check does not compare copper of one net, and its `physical_clearance` constraint also reports every two pieces that touch (KiCad 10.0.7, measured on a copy of the proof design), so it cannot state this. The check refills the board's pours, then measures, on each copper layer, the gap from each zone's fill to every track, via and pad of the zone's net that the fill does not touch, and fails any narrower than the minimum.
- **Fails, as the views show it:** the pre-order check reports a `pour_gap` violation; or, on a `layer-<copper layer>` or `net-<net>`, a hair-thin slot parting a pour from a track, via or pad of its own net, such as beside a keep-out's edge.
- **Judged on:** the pre-order check's report.
- **Kind:** rule. **Severity:** quality.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 4, finding 4.2 and round 5, finding 5.1, which record a pour stopping 0.077 mm and 0.125 mm short of copper of its own net, below the 0.15 mm minimum clearance; for the minimum, `MFG-1`. No free published document states the item.

#### MFG-7. Every part's reference designator is on a silkscreen layer

- **Applies when:** always.
- **Asks:** Does every footprint carry its reference designator on the silkscreen layer of its own side, visible, so a built board names each part and test point?
- **Passes:** The pre-order check reports no `reference_off_silkscreen` violation: every footprint's reference text is on `F.SilkS` for a part on the front and `B.SilkS` for a part on the back, and is not hidden. A footprint excluded from the bill of materials, such as a mounting hole, may hide its reference on its silkscreen layer. Its figure is none, so it is no project text variable; the check's report states it in a `FIGURE` line for the item, and its row in `design-rules.md` is the inherent-zero row that step 1 of [Rules before routing](#rules-before-routing) describes. Where a designator stands against courtyards and other parts is `MFG-9`, which is measured; overlap between two designators' text is not measured and is judged on the views.
- **Fails, as the views show it:** the pre-order check reports a `reference_off_silkscreen` violation; or `layer-F.SilkS` and `layer-B.SilkS` show no designators beside their parts.
- **Judged on:** the pre-order check's report, the `design-rules.md` row for the rule `reference_off_silkscreen`, and `layer-F.SilkS` and `layer-B.SilkS`.
- **Kind:** rule. **Severity:** quality.
- **Source:** `hardware/proof/method-proof/layout-review.md`, round 1, finding 1.8.

#### MFG-8. Silkscreen text reads left to right or bottom to top

- **Applies when:** always.
- **Asks:** Does every reference designator and other legend text read from the left, or from the bottom, as the board is turned to read it from its own side?
- **Passes:** Each text on `F.SilkS` has an angle of 0 or 90 degrees as the front shows it, and each text on `B.SilkS` reads, with the board turned side to side to show its back, from the left or from the bottom: no text reads upside down or from the top down.
- **Fails, as the views show it:** on `layer-F.SilkS`, a designator upside down or reading top to bottom; on `3d-bottom`, a back-side name upside down.
- **Judged on:** `layer-F.SilkS`, `layer-B.SilkS`, `3d-top`, `3d-bottom`.
- **Kind:** judgement. **Severity:** cosmetic.
- **Source:** `hardware/proof/method-proof/layout-review.md`, round 2, finding 2.4.

#### MFG-9. Each designator stands outside every part's body, beside its own part

- **Applies when:** always.
- **Asks:** Does every reference designator on the silkscreen stand clear of the bodies of the parts, its own included, and nearer its own part than any other, so that a person reading the built board can tell which part it names?
- **Passes:** The pre-order check reports no `designator_astray` violation: no designator's text lies inside any part's courtyard, its own included, and none stands nearer another part's courtyard than its own part's. The check estimates each designator's text box from the footprint's text size and thickness and the character count of the name (0.6 of the width size per character, widened by the thickness), places it as the footprint is placed, and takes a part's courtyard as the box about its drawing on the courtyard layer of the text's side. A box reaching 0.05 mm or less into a courtyard is not inside it, and another part is nearer only by more than 0.1 mm. Its figure is none, so it is no project text variable; the report states it in a `FIGURE` line for the item, and its row in `design-rules.md` is the inherent-zero row that step 1 of [Rules before routing](#rules-before-routing) describes. The 0.6, 0.05 mm and 0.1 mm are the estimate's tolerances, not figures the rule enforces, so the rule's figure stays none. A part that draws no courtyard of its own is not held to the nearer test, since a missing courtyard is a different defect, and is still held to the inside test against every other part's courtyard.
- **Fails, as the views show it:** the pre-order check reports a `designator_astray` violation.
- **Judged on:** the pre-order check's report, the `design-rules.md` row for the rule `designator_astray`, and `layer-F.SilkS` and `layer-B.SilkS`.
- **Kind:** rule. **Severity:** cosmetic.
- **Source:** `hardware/proof/method-proof/layout-review.md`, round 3, findings 3.1 and 3.2; amended after the same record, round 4, free pass, which reads strokes on a courtyard line as not inside; made a measured rule after the same findings recurred by eye.

#### MFG-10. Each side with assembled surface-mount parts carries three fiducials

- **Applies when:** the board carries a surface-mount part that the assembler places.
- **Asks:** Does every side that carries assembled surface-mount parts hold at least three fiducials, so the placement machine can find the board's position, turn and stretch on that side?
- **Passes:** The pre-order check reports no `side_fiducials` violation: each side of the board holding a footprint with the surface-mount attribute that is neither a fiducial nor excluded from the position file holds at least three fiducials, a fiducial being a pad with KiCad's global fiducial pad property, counted on the side its footprint sits on. A test point left out of the position file does not make a side count. Its count is three, the item's own, so it is no project text variable; the report states it in a `FIGURE` line for the item, whose source field reads `none, the item's own count`, and its row in `design-rules.md` states three fiducials. A fiducial's size and keep-out clearance are not measured and are judged on the views.
- **Fails, as the views show it:** the pre-order check reports a `side_fiducials` violation; or `layer-F.Cu` or `layer-B.Cu` shows fewer than three round bare-copper pads with their own mask openings on a side with assembled parts.
- **Judged on:** the pre-order check's report, the `design-rules.md` row for the rule `side_fiducials`, `layer-F.Cu` and `layer-B.Cu`.
- **Kind:** rule. **Severity:** quality.
- **Source:** *PCB Panelization, Breakaway Rails, Fiducial Marks, Tooling Holes*, PCBWay, section *Fiducial Marks*, items 8 and 9 ("at least three fiducial marks arranged in an L shape"; "if components are populated on both sides, each side should have fiducial marks"), last updated 17/05/2024, https://www.pcbway.com/helpcenter/design_instruction/PCB_Panelization__Breakaway_Rails__Fiducial_Marks__Tooling_Holes.html, read 2026-10-19; corroborated by *Fiducial Marks in PCB and SMT Assembly: A Complete Guide to Accuracy and Design Rules*, JLCPCB, updated 9 September 2026, section on global fiducials ("A minimum of two, but three fiducial marks are strongly recommended", a set on both sides of a double-sided board), https://jlcpcb.com/blog/fiducial-marks, read 2026-10-19.

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
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.5.4 *I/O Recommendations for Off-PCB Signals* and § 3.3 *Cables and Bypassing to the Shield*, Figure 13 ("The connection to the chassis is an RF path requiring 3:1 length to width"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### EMI-4. A supply ferrite bead sits nearest the noise source, with its capacitor inside it

- **Applies when:** the schematic carries a ferrite bead in a supply to an integrated circuit.
- **Asks:** Is the bead placed at the part it isolates, in the supply only and not the ground, with the part's bypass capacitor between the bead and the part?
- **Passes:** The bead sits next to the part it serves, in the supply line; the bypass capacitor sits between bead and part, so the part's switching current flows in the small loop inside the bead.
- **Fails, as the views show it:** on `crop-<reference>` or `assembly-top`, the bead at the far end of the supply, or the bypass capacitor on the supply side of the bead.
- **Judged on:** `crop-<reference>`, `assembly-top`, `assembly-bottom`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.2.4 *Bypassing and Ferrite Beads*, Figure 9 ("placing the capacitors inside the ferrite bead"; "The ferrite bead is used only on +V, not on ground"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

#### EMI-5. Series resistors on the controller's outputs sit at the controller

- **Applies when:** the schematic carries a resistor in series with a controller's output or input pin.
- **Asks:** Is each series resistor placed as close to the controller's pin as it can be?
- **Passes:** Each series resistor sits at its controller pin, over the controller's ground area where it can.
- **Fails, as the views show it:** on `crop-<reference>` of the controller or on `assembly-top`, a series resistor placed at the far end of its line.
- **Judged on:** `crop-<reference>` of the controller, `assembly-top`, `assembly-bottom`, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.2.5 *Keeping Noise Close to the Chip* ("Place the resistor as close as possible to the microcomputer, overlapping the microcomputer ground if possible"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14.

### Workmanship (WORK)

These items ask what an experienced electrical engineer expects of any board before they look at what it does: parts placed by what they connect to, and copper that runs neat, tidy and direct. A board can pass every other item and still be laid out like a first attempt. The qualities a board's files hold exactly, an angle, a length, a width, are rule items the pre-order check measures, because a few pixels on an image are easily missed. The qualities of overall form are judgement items, each stated as what good looks like and what a failing board looks like in the views.

KiCad's layout rule check compares every two tracks that meet on one copper layer anywhere but at a pad, at a via as much as in open copper, and does not compare tracks that meet at a pad or that meet at a via on different layers (KiCad 10.0.7, measured on a throwaway board). So a track that branches off the middle of another, or off a via on its own layer, makes an angle with each side of it, and `WORK-4` fails the branch however it leaves. A route therefore branches at a pad, the track running to the pad and leaving it again, or at a via where it changes layer, with no more than two of its tracks on any one layer there, running on straight or turning at 45 degrees. That is also the shape `WORK-2` measures a route against, the shortest tree joining a net's pads. Two tracks meeting at a pad are one route passing through it, held to the same corner as anywhere else; only where three or more of a net's tracks leave a pad on one layer does the route branch there.

Wherever a rule item asks whether a track meets a pad, the pre-order check judges it from the copper, as KiCad's connectivity joins a track to a pad, and never from the track's centre line alone. A track's copper is its centre line swept by half its width, so each end is a round cap about its end point. KiCad joins a track to a pad wherever the track's copper reaches the pad's copper. A track meets a pad at an end where that end's cap reaches the pad's copper, so a track ending just short of a pad whose copper still touches it meets the pad. A track whose copper runs over a pad with neither end reaching it, through the pad's centre or off it, crosses the pad, and KiCad joins it to the pad all the same. The check sizes a pad's copper from the shape and size the layout file gives it when it is a circle, an oval, a rectangle or a rounded rectangle. A pad of any other copper, a custom shape, chamfered corners, a trapezoid or a shape set layer by layer, on a layer where tracks of its net run, cannot be measured, and the check fails the board as `workmanship_pad_copper`, naming the pad, rather than guessing where its copper reaches; draw such a pad in one of those four shapes.

#### WORK-1. Connected parts sit together, so their connections run short and uncrossed

- **Applies when:** always.
- **Asks:** Is each part placed next to the parts it connects to, in the order its connections run, so that every connection is short and none crosses another on the way?
- **Passes:** Parts joined by a connection sit close together, in the order the circuit runs from part to part, each turned so that its pads face the pads they join. The tracks between them are short and run side by side rather than across one another, and a track crosses to another layer only to pass a track it cannot go round. A part that serves one pin, such as a resistor or a capacitor on it, sits beside that pin.
- **Fails, as the views show it:** on `assembly-top` or `assembly-bottom`, a part set well apart from every part it connects to, or turned so that its pads face away from them; on a `layer-<copper layer>` or `net-<net>`, a track running across the board, or looping round other parts, to reach a partner that could have been placed beside it, or tracks crossing one another between layers where turning or swapping two parts would have kept them apart.
- **Judged on:** `assembly-top`, `assembly-bottom`, every `layer-<copper layer>`, `net-<net>` for each critical net, `placement`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 4 *Summary* ("a careful positioning of the integrated circuits is essential to achieve short interconnect lines") and § 1.4.1 *Proportionality of Loops and Dipoles* ("Loops and dipoles are antennas"; "the larger the laid-out area of the loop, the stronger the radiation"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and `hardware/proof/review-proof/layout-review.md`, round 1, findings 1.8 and 1.9, which record parts placed loosely enough that a signal loops round its amplifier to reach its partner and the load return runs 22 mm across that board to its shunt.

#### WORK-2. Every net routed in tracks runs no longer than its pads' places need

- **Applies when:** always.
- **Asks:** Is every net routed in tracks no longer, in all its tracks together, than 1.3 times the shortest straight-line tree joining the centres of its pads?
- **Passes:** The board's project text variable `WORK_DETOUR_RATIO` is set to 1.3, or less, with its row in the board's rules table, and the pre-order check reports no `workmanship_detour` violation. The check measures each net that has tracks and two or more pads: the length of all its tracks and arcs on every layer, against the minimum spanning tree, in straight lines, of the centres of all its pads. Zones never enter the measure. A zone cannot shorten the tree, so it can neither take a net out of the measure nor a pad out of the tree, and a net whose connection a zone carries in part only gains room against it. A route drawn the direct way, turning at 45 degrees and branching at its pads, runs at most 1.08 times the straight line between each two pads it joins, the most a run along and at 45 degrees to the board's edges adds to a straight line: between two pads in a direction θ off the nearest of those directions it runs cos θ + (√2 − 1) sin θ times the line, at worst 1.08 at 22.5 degrees. So 1.3 leaves room for leaving and entering pads along their axes and for going round a part's end to reach a pin on its far side; one that wanders or loops round the board does not. The figure catches a route that wanders far, not every loop: a net looping round a part can stay under 1.3 times its tree, as `AMP_OUT` did at 1.249 on the proof design's first reviewed layout, so a loop the figure admits is judged by `WORK-1` and `WORK-3`.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_detour` violation; or, in `design-rules.md`, no row for `WORK_DETOUR_RATIO`, a figure above 1.3, or no source named.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 2.1.1 *Inductance* ("Inductance increases with increasing length"), https://www.ti.com/lit/pdf/szza009, read 2026-10-15. The figure of 1.3 rests on the arithmetic in Passes, the 1.08 a direct route at 45 degrees can add, with room for pad entries; no free published document states a figure. `hardware/proof/review-proof/layout-review.md`, round 1, findings 1.10 and 1.11, applies it to that board, measuring each net against this tree: `LED_DRV`, the one route that wanders, at 1.308.

#### WORK-3. Routing reads cleanly: nothing wanders, doubles back or changes layer that does not need to

- **Applies when:** always.
- **Asks:** Seen whole, does every route take the path an experienced engineer would draw, with no loop, wander or double-back the placement does not force, no needless change of layer, and the tracks of related nets running together in orderly lines?
- **Passes:** Each route leaves its pad, turns as few times as it needs and arrives, running beside its neighbours at an even spacing where they share a path. A route changes layer only to pass something it cannot go round. A net that a copper zone carries reaches the pads the zone joins as directly as one in tracks; `WORK-2` measures only its tracks, against the tree joining all its pads.
- **Fails, as the views show it:** on a `layer-<copper layer>` or `net-<net>`, a route that turns back on itself, makes a loop or a wide detour round a part it could have passed, or drops to another layer and comes straight back; on `classes`, a supply and its return taking different ways round the board; tracks sharing a path at uneven spacings or crossing one another without need.
- **Judged on:** every `layer-<copper layer>`, `net-<net>` for each critical net, `classes`.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *PCB Design Guidelines For Reduced EMI*, SZZA009, November 1999, § 1.4.1 *Proportionality of Loops and Dipoles* ("Loops and dipoles are antennas"), https://www.ti.com/lit/pdf/szza009, read 2026-10-14; and Texas Instruments, *High-Speed Layout Guidelines*, SCAA082A, November 2006, revised August 2017, § 2.5 *Traces, Vias, and Other PCB Components* ("Vias also increase the trace length"), https://www.ti.com/lit/pdf/scaa082, read 2026-10-14.

#### WORK-4. Corners are turned at 45 degrees or as arcs, never square or acute

- **Applies when:** always.
- **Asks:** Does every corner a track turns meet at 135 degrees or more between its two straight runs, or as an arc, with no right-angled and no acute corner, whether it turns in open copper, at a via or through a pad, and do three or more tracks branching at a pad leave it square to one another or wider?
- **Passes:** The board's rules file holds this custom rule, and the pre-order check reports no `track_angle` violation:

  ```
  (rule "Corners"
  	(constraint track_angle (min 135)))
  ```

  KiCad states the angle at a joint as the angle between its two tracks, so a straight run is 180, a 45-degree bend 135 and a square corner 90; the figure is a bare number, since a unit KiCad does not take drops the whole rules file. The rule has no condition, or the one condition `A.Type == 'Track'`, and no layer, so it holds on every track. Any other rule in the file holding `track_angle`, before it or after it, with a condition or without, writes a minimum no lower than this one's, or the check fails it as a `workmanship_rule` violation naming the rule, its line and both figures: KiCad applies the last rule that matches, so a later rule at 90 for one net class would let that class turn square while KiCad's check passes. A branch is made at a pad (see the opening of this area). KiCad does not compare tracks that meet at a pad, so the pre-order check measures them, a track meeting a pad as the opening of this area says, by the angle between the ways they leave it, and reports a `workmanship_pad_corner` violation. Two tracks of a net that meet on one layer at a pad are a route turning through it, held to the `Corners` rule's own figure, which the check reads from the rules file and states in its report. Three or more are a branch, held to the board's project text variable `WORK_PAD_ANGLE_DEG`, set to 90 with its row in the board's rules table: a branch leaves square to the route or wider, and never at the acute angle that leaves a sliver of bare board between two tracks, while a route that merely passes through a pad turns there no more sharply than anywhere else.
- **Fails, as the views show it:** the pre-order check reports a `track_angle` or `workmanship_pad_corner` violation, or a `workmanship_rule` violation naming `WORK-4`; or, in `design-rules.md`, no row for the rule or a figure below 135, or no row for `WORK_PAD_ANGLE_DEG` or a figure below 90.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *High-Speed Layout Guidelines*, SCAA082A, November 2006, revised August 2017, § 2.5 *Traces, Vias, and Other PCB Components* ("Avoid right-angle bends in a trace and try to route them at least with two 45° corners. To minimize any impedance change, the best routing would be a round bend"), https://www.ti.com/lit/pdf/scaa082, read 2026-10-15, which gives the figure of 135: a 45-degree corner leaves 135 degrees between its two runs; Texas Instruments, *High-Speed Interface Layout Guidelines*, SPRAAR7J, November 2018, revised February 2023, § 3.11 *Signal Bending* ("Avoid the introduction of bends into high-speed differential signals"), https://www.ti.com/lit/pdf/spraar7, read 2026-10-15, for keeping bends loose; and, for the figure of 90 at a branch, `hardware/proof/review-proof/layout-review.md`, round 2, finding 2.7, which records the slivers of bare board left between tracks meeting at a pad at 45 degrees.

#### WORK-5. No jog: no straight run is shorter than 1 mm

- **Applies when:** always.
- **Asks:** Is every straight run of track, between two bends or between a bend and a pad, at least 1 mm long, so that no small kink or offset is left in a route?
- **Passes:** The board's rules file holds this custom rule, and the pre-order check reports no `track_segment_length` violation:

  ```
  (rule "Jogs"
  	(constraint track_segment_length (min 1mm)))
  ```

  The rule has no condition, or the one condition `A.Type == 'Track'`, and no layer. Any other rule in the file holding `track_segment_length`, before it or after it, writes a minimum no shorter than this one's, or the check fails it as a `workmanship_rule` violation naming the rule, its line and both figures. KiCad measures the run into a pad as much as one between two bends, so a track leaves a pad, or a via, straight for at least 1 mm before it turns.
- **Fails, as the views show it:** the pre-order check reports a `track_segment_length` violation, or a `workmanship_rule` violation naming `WORK-5`; or, in `design-rules.md`, no row for the rule, or a figure below 1 mm.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** cosmetic.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, findings 1.25 to 1.30, which record the jogs left in that board's routes: straight runs of 0.63 to 0.88 mm beside FB1, R2, R3 and U4, and an offset of 0.05 mm at U2's tab. No free published document states the item or a figure; the figure of 1 mm is set above every run that round records.

#### WORK-6. No stub: no track ends free

- **Applies when:** always.
- **Asks:** Does every track end on a pad, a via, a copper zone or another track of its own net, with no length of track left ending in free space?
- **Passes:** The pre-order check reports no `track_dangling` violation. KiCad's own layout rule check reports a track end connected to no other copper, unaided, wherever the stub leaves the route, so this item needs no rule written in the board's rules file and no figure. Its row in the board's rules table names KiCad's check.
- **Fails, as the views show it:** the pre-order check reports a `track_dangling` violation; or, in `design-rules.md`, no row for the check.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *High-Speed Interface Layout Guidelines*, SPRAAR7J, November 2018, revised February 2023, Appendix A *Device Layout Parameters*, Table A-1 ("Number of stubs allowed on any USB differential pair trace (total)", maximum 0), https://www.ti.com/lit/pdf/spraar7, read 2026-10-15, which states the practice for that board's fastest signals; and KiCad, *PCB Editor* manual, version 10.0, *List of DRC checks* ("Track has unconnected end: This violation occurs when the end of a track segment is not connected to another copper object, such as another track segment, a via or pad, or a zone or copper graphical shape"), https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html, read 2026-10-15, for the check that enforces it.

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
- **Asks:** Is every track at least its net class's track width, except where it necks down to enter a pad, running no more than 1 mm off the pad's copper?
- **Passes:** The board's project text variable `WORK_NECK_MM` is set to 1, or less, with its row in the board's rules table, and the pre-order check reports no `workmanship_width` violation. The check reads each net class's track width from the project file and the nets KiCad places in each class, a net in several classes taking the width of the one ranked first; a track narrower than that width passes only as part of a run of such tracks that meets a pad of its net, as the opening of this area says, and runs no more than `WORK_NECK_MM` in all off the copper of its net's pads, so a narrow track joining two pads close together passes however long it is across them. A track wider than its class's width never fails, so a power path widened where there is room, as `POWER-2` asks, passes. A rule that requires a different width on some tracks writes it as the class's own figure.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_width` violation; or, in `design-rules.md`, no row for `WORK_NECK_MM`, or a figure above 1 mm.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** Texas Instruments, *High-Speed Interface Layout Guidelines*, SPRAAR7J, November 2018, revised February 2023, § 3.2 *High-Speed Differential Signal Rules* ("Maintain constant trace width after the SoC BGA escape to avoid impedance mismatches in the transmission lines"), https://www.ti.com/lit/pdf/spraar7, read 2026-10-14; and, for the figure of 1 mm, `hardware/proof/review-proof/layout-review.md`, round 1, findings 1.33 to 1.37, which measure that board's narrow runs: those necking into a pad lie 0.20 to 0.95 mm off pad copper, those narrowed partway along 1.04 mm or more, so 1 mm lies between them. No free published document states the figure.

#### WORK-9. Tracks run parallel to the board's edges or at 45 degrees to them

- **Applies when:** always.
- **Asks:** Does every track run parallel to the board's edges, or at 45 degrees to them, within 0.1 degree, an arc at each of its two ends?
- **Passes:** The board's project text variable `WORK_ANGLE_TOLERANCE_DEG` is set to 0.1, or less, with its row in the board's rules table, and the pre-order check reports no `workmanship_direction` violation. The check takes the direction of the board's edges from the longest straight side of the outline as drawn on the edge layer: a line, each of a rectangle's four sides less any rounding at its corners, each straight run of a polygon, and the same shapes in a footprint, where the footprint places them. An arc, a circle or a curve turns all along it and gives no direction, and an outline with no straight side is held to the board's own axes. The check holds every straight track to a multiple of 45 degrees from that direction, and an arc by the way it runs at each of its two ends, where it leaves and meets the route: a fillet between two tracks that each run one of those ways passes, and a flat arc drawn at an odd angle fails.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_direction` violation; or, in `design-rules.md`, no row for `WORK_ANGLE_TOLERANCE_DEG`, or a figure above 0.1.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** cosmetic.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, findings 1.38 to 1.43, which record that board's tracks drawn at odd angles, from 0.14 to 16.04 degrees off the nearest of those directions. No free published document states the item or a figure; the figure of 0.1 degree is set below the smallest of them.

#### WORK-10. A track enters a long pad along its long axis, from its end

- **Applies when:** the schematic carries a part with a pad more than twice as long as it is wide, such as an integrated circuit's lead or a crystal's pad.
- **Asks:** Does every track entering a pad more than twice as long as it is wide run in along the pad's long axis, through one of its short ends, within 0.1 degree?
- **Passes:** The board's project text variable `WORK_PAD_ENTRY_RATIO` is set to 2, or less, with its row in the board's rules table, `WORK_ANGLE_TOLERANCE_DEG` is set as `WORK-9` asks, and the pre-order check reports no `workmanship_pad_entry` violation. The check finds each track that meets such a pad at one end and not at the other, or whose copper runs over the pad with neither end meeting it, a track meeting a pad as the opening of this area says, and holds its direction there to the pad's long axis. A pad no more than twice as long as it is wide, such as a chip resistor's, may be entered from any side, square to that side.
- **Fails, as the views show it:** the pre-order check reports a `workmanship_pad_entry` violation; or, in `design-rules.md`, no row for `WORK_PAD_ENTRY_RATIO`, or a figure above 2.
- **Judged on:** the pre-order check's report, `design-rules.md`.
- **Kind:** rule. **Severity:** quality.
- **Source:** `hardware/proof/review-proof/layout-review.md`, round 1, findings 1.44 to 1.48, which record that board's tracks entering long pads from their sides and at a slant; and, for the figure of 2, Altium, *Altium Designer* documentation, *SMT Rule Types*, *SMD Entry* ("Pads can always be entered from either end (the shorter edge)"; "The longer edge of the pad is considered the side. Note that the side option is only applied if the Side length > 2x End length"; "if the pad is 2mm x 1mm then the side option is ignored (all sides are treated as ends)"), https://www.altium.com/documentation/altium-designer/pcb/design-rule-types/smt, read 2026-10-15, so a pad exactly twice as long as it is wide has only ends.

Out of scope for this section: applying the catalogue to a finished layout, which the [layout review](#layout-review) does, and producing the views it is judged on, which [Layout review views](#layout-review-views) describes.

## Schematic drawing convention

This is the one statement of how a schematic is drawn so that someone who did not draw it can follow it, the counterpart of the [Circuit practice catalogue](#circuit-practice-catalogue), which judges whether the circuit is right. The convention is applied while the schematic is drawn, before the [schematic review](#schematic-review) begins, and the review judges every sheet against it with the catalogue's item `DRAW-1`, so a board is not redrawn afterwards. A reader who traces a signal on a printout at a bench, with no one to ask, is the reader it is written for. It holds nothing specific to any one machine or board. Its sources are documents any reader can obtain without charge, each cited by title, publisher, section, address and the date it was read, and checked against the document itself, never from memory. Where a source states a convention as common practice rather than as a rule, the item says so.

The convention is about how a schematic is drawn, and so about nothing the schematic's file or netlist hold differently: the arrangement inside a sheet changes what a reader sees and does not change what a check reads. A reader who wants the drawings draws them from the repository with `task hw:sheets -- --out <folder>`, which needs KiCad, the design tool this repository names, and nothing else ([`hardware/README.md`](../hardware/README.md#the-schematic-sheets)). The drawings are not committed.

### How an item is read

Each item below is a short statement, followed by its **Source**: the published document and the passage it rests on. An item states only what its sources support.

### Items

#### 1. One function to a sheet

A sheet holds the circuit of one function (a power supply, a sensing front end, a connector's interface circuit, the controller and its support parts), and a function too large for one sheet is divided between sheets at a boundary a reader can name.

- **Source:** Flux, Gabriel Hacohen, *PCB Schematic Best Practices for Clean Circuit Design*, June 2026, https://www.flux.ai/p/blog/pcb-schematic-best-practices, § *Grouping Circuits* ("Break the design into logical functional blocks"; "each block lives on its own schematic page"), read 2026-10-18; and Zuken USA, Bob Potock, *How to Draw a Circuit Diagram: 4 Rules for Better PCB Schematics*, Zuken Americas Blog (no date stated on the page), https://www.zuken.com/us/blog/how-to-draw-a-circuit-diagram-4-rules-for-better-pcb-schematics/, § *Rule 2: Keep the Layout Logical and Consistent* ("For PCB designs, group the schematics by functional blocks"), read 2026-10-18.

#### 2. Each sheet is named for its function

A sheet's name says what its function is, in words a reader would use, such as `Power input` or `Temperature sensing`, and the name is unique among the design's sheets. A name that numbers the sheet or repeats the design's name says nothing, and a sheet with no name of its own is judged as unnamed.

- **Source:** Schemalyzer, *Schematic Design Best Practices: 30 Rules for Clear, Professional Circuits (2025)*, 3 December 2025, https://www.schemalyzer.com/en/blog/schematic-review/best-practices/schematic-design-best-practices, rule 29, *Use Title Blocks* (a sheet's title carries its place and its function, such as "3/5: Power Supply"), read 2026-10-18; and KiCad project, *KiCad 10.0 Schematic Editor* manual (the *Schematic Editor* chapter), https://docs.kicad.org/10.0/en/eeschema/eeschema.html, § *Adding hierarchical subsheets to a design* ("The sheet name must be unique, as it is used in the full net name for any nets in the subsheet"), read 2026-10-18.

#### 3. Every net is named by its designer, never by the tool

Every net carries a name its designer gave it, which says what the net carries (`+5V_SENSE`, `HEATER_DRIVE`), and no net is left with the name the design tool generates from the pins it joins.

- **Source:** Flux, Gabriel Hacohen, *PCB Schematic Best Practices for Clean Circuit Design*, June 2026, https://www.flux.ai/p/blog/pcb-schematic-best-practices, § *Clean Schematic Checklist* ("Rename default nets (like Net0012) to descriptive names (like 5V_MAIN or UART_TX)"), read 2026-10-18; Schemalyzer, *Schematic Design Best Practices: 30 Rules for Clear, Professional Circuits (2025)*, 3 December 2025, https://www.schemalyzer.com/en/blog/schematic-review/best-practices/schematic-design-best-practices, rule 13, *Use Descriptive Net Names* (avoid meaningless names, and names that describe the connection and not the function), read 2026-10-18; and KiCad project, *KiCad 10.0 Schematic Editor* manual (the *Schematic Editor* chapter), https://docs.kicad.org/10.0/en/eeschema/eeschema.html, § *Net name assignment rules* ("If none of the label types above are attached to a net, the net's name is automatically generated based on the connected symbol pins"), read 2026-10-18.

#### 4. Wires within a function's circuit, labels between circuits

Inside one function's circuit the pins are joined by wires drawn short and straight, with as few crossings as the circuit allows. A connection between two circuits, and a connection that would run across a sheet, is made by a label carrying the net's name, so the same name stands at both ends.

- **Source:** Flux, Gabriel Hacohen, *PCB Schematic Best Practices for Clean Circuit Design*, June 2026, https://www.flux.ai/p/blog/pcb-schematic-best-practices, § *Labeling Conventions* ("Instead of drawing a continuous wire from a microcontroller pin all the way across the page to a sensor, use net labels"), read 2026-10-18; Zuken USA, Bob Potock, *How to Draw a Circuit Diagram: 4 Rules for Better PCB Schematics*, Zuken Americas Blog (no date stated on the page), https://www.zuken.com/us/blog/how-to-draw-a-circuit-diagram-4-rules-for-better-pcb-schematics/, § *Rule 2: Keep the Layout Logical and Consistent* ("Avoid unnecessary wire crossings"), read 2026-10-18; and KiCad project, *KiCad 10.0 Schematic Editor* manual (the *Schematic Editor* chapter), https://docs.kicad.org/10.0/en/eeschema/eeschema.html, §§ *Wires* and *Labels* (wires establish direct connections; labels assign net names, and wires with the same net name are connected), read 2026-10-18.

#### 5. Signal flow runs one way across each sheet

Within a sheet the signal flows in one direction, from left to right: inputs and supply entering at the left side, processing in the middle and outputs leaving at the right side. Positive supply is drawn toward the top and ground and return paths toward the bottom. A feedback path is drawn against the flow so that it reads as feedback. The direction is common practice, not a law, so the item asks for one direction held through a sheet and a departure from it only where the circuit needs one.

- **Source:** Flux, Gabriel Hacohen, *PCB Schematic Best Practices for Clean Circuit Design*, June 2026, https://www.flux.ai/p/blog/pcb-schematic-best-practices, § *Signal Flow Direction* ("Always design your signal flow to move from left to right"; "For power circuits, use a top-to-bottom flow"), read 2026-10-18; Schemalyzer, *Schematic Design Best Practices: 30 Rules for Clear, Professional Circuits (2025)*, 3 December 2025, https://www.schemalyzer.com/en/blog/schematic-review/best-practices/schematic-design-best-practices, rules 1 to 3 ("Arrange circuits so signals flow from left to right"; "Higher voltages at the top, lower voltages (ground) at the bottom"; feedback routed right-to-left), read 2026-10-18; Zuken USA, Bob Potock, *How to Draw a Circuit Diagram: 4 Rules for Better PCB Schematics*, Zuken Americas Blog (no date stated on the page), https://www.zuken.com/us/blog/how-to-draw-a-circuit-diagram-4-rules-for-better-pcb-schematics/, § *Rule 2: Keep the Layout Logical and Consistent* (signals flow from left to right in many schematics, power often at the top and return paths near the bottom, "is not a strict rule for every design, but consistency matters"), read 2026-10-18; and Wikimedia Foundation, *Circuit diagram*, Wikipedia (page last edited 21 July 2026), § *Organization*, https://en.wikipedia.org/wiki/Circuit_diagram ("organized on the page from left to right and top to bottom", "a usual (although not universal) convention"), read 2026-10-18.

#### 6. Supply rails are joined across sheets by name

A supply rail is drawn with a power symbol or label that carries the rail's name, and the same rail carries the same name on every sheet it reaches, spelt one way. A rail is never carried between sheets by a wire, and two names for one rail are not mixed.

- **Source:** KiCad project, *KiCad 10.0 Schematic Editor* manual (the *Schematic Editor* chapter), https://docs.kicad.org/10.0/en/eeschema/eeschema.html, § *Power symbols* ("two power symbols with the Value connect to each other anywhere in the schematic, regardless of sheet"), read 2026-10-18; and Schemalyzer, *Schematic Design Best Practices: 30 Rules for Clear, Professional Circuits (2025)*, 3 December 2025, https://www.schemalyzer.com/en/blog/schematic-review/best-practices/schematic-design-best-practices, rules 14 and 19 (one style of name, with "avoid having both VDD and 3V3"; "Use Power Symbols, Not Wires"), read 2026-10-18.

#### 7. Each connector is labelled with its pins and what each carries

Each connector's symbol shows its reference designator, the number of every pin, and beside each pin the name of the net it carries, which for a connector to a harness or another board is the signal or channel's name as that harness's record names it, so a reader can follow a signal from the drawing to the pin of a mating connector.

- **Source:** Zuken USA, Bob Potock, *How to Draw a Circuit Diagram: 4 Rules for Better PCB Schematics*, Zuken Americas Blog (no date stated on the page), https://www.zuken.com/us/blog/how-to-draw-a-circuit-diagram-4-rules-for-better-pcb-schematics/, § *Rule 4: Label Components, Values, and Signals Clearly* ("include part numbers, tolerances, ratings, and connector pin information where needed") and step 5, § *Label Everything Clearly* ("Add reference designators, values, wire names, voltage labels, and connector pin numbers"), read 2026-10-18; and Schemalyzer, *Schematic Design Best Practices: 30 Rules for Clear, Professional Circuits (2025)*, 3 December 2025, https://www.schemalyzer.com/en/blog/schematic-review/best-practices/schematic-design-best-practices, rules 12 and 18 (connectors take the reference prefix J or P; "Display pin numbers on all IC symbols"), read 2026-10-18. The sources state that a connector's pin numbers and wire names are drawn; that the name is the harness record's channel name is this convention's own rule, so a rebuilder's harness can be followed from the drawing.

#### 8. Text stands clear of other text and of symbols

No reference designator, value, net name, label or note overlaps another text, a symbol's body or a wire, and parts are spaced so that each text can be read. Text is horizontal, or turned only to read from the bottom or right of the sheet.

- **Source:** Schemalyzer, *Schematic Design Best Practices: 30 Rules for Clear, Professional Circuits (2025)*, 3 December 2025, https://www.schemalyzer.com/en/blog/schematic-review/best-practices/schematic-design-best-practices, § *Visual Inspection* ("No overlapping text") and rule 15, *No Vertical Text* (keep text "horizontal and readable"), read 2026-10-18; and Flux, Gabriel Hacohen, *PCB Schematic Best Practices for Clean Circuit Design*, June 2026, https://www.flux.ai/p/blog/pcb-schematic-best-practices, § *Clean Schematic Checklist* (the article states no rule on overlapping text, and the item takes only its advice on spacing: "Leave adequate breathing room around components. Do not cram symbols together just to save page space"), read 2026-10-18.

Out of scope for this section: judging a schematic against the convention, which the [schematic review](#schematic-review) does with `DRAW-1`; refusing a net named by the tool or a sheet with no name, which the pre-order check does; and the circuit practice, which the [Circuit practice catalogue](#circuit-practice-catalogue) holds.

## Circuit practice catalogue

This is the one statement of what a sound schematic looks like, the counterpart of the [Layout practice catalogue](#layout-practice-catalogue). The layout catalogue judges how a board is drawn and leaves whether its circuit is right outside its scope; this one judges the circuit. It is used once on every board, by the [schematic review](#schematic-review), which gives every net, every part and every sheet of the schematic a verdict against it before any footprint is placed. It holds no figure, part or board shape of any one machine. A figure that depends on the machine or on the installation is named here by its role, such as the working voltage a barrier carries, and its number lives in that machine's records. A figure that a purchased standard sets is never stated here: the item requires it from the governing standard the board's separation basis record names, or from a cited, freely available derivation of that standard's tables.

### How a circuit item is read

Every item carries the fields of a layout item, less the two that belong to the layout review's views:

- **Identifier**, its area and a number, such as `PINV-1`. The areas use codes that no layout item uses. An identifier is never renumbered and never reused: a record and a finding cite items by it. A new item takes the next number its area has not used, and an item withdrawn keeps its identifier, marked withdrawn, so a citation of it still finds it.
- **Applies when** states, in terms of what the board's schematic carries, the condition under which the item applies. An item whose condition the schematic meets applies; it cannot be marked as not applying.
- **Asks** is the question the item asks of a schematic.
- **Passes** is the pattern that passes.
- **Fails, as the schematic shows it** is what a failing schematic looks like in the schematic, the netlist exported from it or the records the item names. Where the layout catalogue's items state how a failure shows on the views, these state how it shows on the schematic, and no item names a view to judge on.
- **Kind** is one of two. A **rule-kind** item is one a check reads the board's files to decide. A **judgement-kind** item is judged by the reviewer on the schematic, its netlist and the documents the item cites. A practice only partly expressible as a check is two items, one of each kind, so every item has a single kind.
- **Severity** is one of the layout catalogue's four ([How an item is read](#how-an-item-is-read)): **safety**, an item that bears on separation between mains and anything a person or a low-voltage circuit can reach, on fusing, on protective earthing, or on insulation; **function**, where a board failing it may not do its job, or may not meet a figure it is held to; **quality**, where a board failing it works with less margin, reliability or ease of bring-up than it should have; and **cosmetic**, where only appearance or legibility suffers.
- **Source** is a published document any reader can obtain without charge, such as a part maker's datasheet, application note or design guide, cited by its title, publisher, section, address and the date it was read, and checked against the document itself, never cited from memory. A standard that must be bought, or a document that could not be opened and read, is not a source. Each item is stated fully enough to apply without reading its source. A rating a reviewer cannot source at review counts as absent and fails the item.

The areas, in order: [pin voltages](#pin-voltages-pinv), [required external parts](#required-external-parts-parts), [capacitor derating](#capacitor-derating-capd), [bus lines](#bus-lines-busl), [boot, strap and debug](#boot-strap-and-debug-strap), [RC filters at converter inputs](#rc-filters-at-converter-inputs-rcfl), [power-up and brown-out](#power-up-and-brown-out-supply), [polarity](#polarity-polar), [cables and harnesses](#cables-and-harnesses-cable), [single-fault analysis](#single-fault-analysis-fault), [independence of the power cut-off](#independence-of-the-power-cut-off-indep), [mains-to-low-voltage barriers](#mains-to-low-voltage-barriers-barrier), [mains transients](#mains-transients-surge), [static discharge](#static-discharge-esd), [touch current](#touch-current-touch), [emissions at their sources](#emissions-at-their-sources-emsrc) and [derating](#derating-derate) and [drawing](#drawing-draw).

### Pin voltages (PINV)

#### PINV-1. Every pin's voltage stays within its absolute maximum in every operating state

- **Applies when:** always; it selects every net, and each pin on the net is judged.
- **Asks:** For every pin on the net, does the voltage the net can reach, the highest and the lowest, steady and transient, in each operating state (power-up, normal, power-down, a fault, a connector unplugged or plugged live, and each supply absent in turn) stay within the absolute maximum and the input tolerance the pin's datasheet states?
- **Passes:** For each pin the review record gives the datasheet's absolute maximum, lowest and highest, its recommended input range and any stated input tolerance (such as a pin said to tolerate a voltage above its own supply), each cited by document number, revision and section. The worst-case voltage the net can reach lies inside all of them. Where a net can leave a pin's rating, the schematic holds a part that stops it: a clamp, a divider, a level translator, or a series resistor sized so that the current the pin's protection diodes then carry stays below the datasheet's stated diode or injection current, the resistor's value and arithmetic shown. A pin whose datasheet states no rating, or whose datasheet was not opened, has no rating, and fails.
- **Fails, as the schematic shows it:** a net reaching a pin from a connector, a higher-voltage rail or another part's output with nothing between and a worst-case voltage above the pin's rating; a series resistor with no arithmetic against the datasheet's diode current; a review row citing no datasheet.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Use Conditions for 5-V Tolerant GPIOs on Tiva C Series TM4C123x Microcontrollers*, SPMA053, July 2013, § 2 *Use Conditions*, note 6 ("If there is a possibility that VIN can be outside the absolute maximum ratings in the end-applications, I/Os must be protected with an external current-limiting series resistor"), https://www.ti.com/lit/an/spma053/spma053.pdf, read 2026-10-18; and Texas Instruments, *ESD Diode Current Specification*, SLAA689B, December 2015, revised August 2021, § 2 *Introduction and Clarification of the Specification* ("the application must protect the device pin externally so that a signal does not exceed the ±2-mA specification", of the part it treats; the figure is that part's, and the item reads the figure from each pin's own datasheet), https://www.ti.com/lit/an/slaa689b/slaa689b.pdf, read 2026-10-18.

#### PINV-2. A pin driven while its own part is unpowered cannot power the part or exceed its rating

- **Applies when:** a net reaches a pin of a part from another part, a sensor, a connector or a cable that has a supply of its own, and the part's own supply can be absent or lower than the net, while the net is driven.
- **Asks:** With the part's own supply at zero, or still rising at power-up, or already falling at power-down, and the net driven, does the pin's voltage stay within its rating, and does no current flow through the pin's protection structures into the part's supply?
- **Passes:** The pin's datasheet states that the pin tolerates a voltage while the part is unpowered, and gives the leakage it then draws, and the net's worst-case voltage lies inside that statement; or the schematic holds a part that removes the drive while the supply is absent (a buffer or switch whose own datasheet states the same tolerance, a series resistor that holds the current below the datasheet's diode current with the supply at zero, or a sequence that keeps the driver's supply behind the part's). A pin whose datasheet is silent is taken to conduct through its protection diodes into the supply rail, and is held to the first pattern's resistor or isolator. Delays in the part's supply, such as inline capacitance or a regulator's soft start, are included in the arithmetic.
- **Fails, as the schematic shows it:** a signal from a separately supplied part wired directly to a pin of a part on another rail with no isolating part and no datasheet statement of unpowered tolerance; a supply that is fed only through that signal's protection diodes when the main supply is off.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ESD Diode Current Specification*, SLAA689B, December 2015, revised August 2021, § 1 *Important Side Effects of the ESD Diodes During Power Cycling* (a voltage applied to a pin while the main supply is unpowered "can cause unintended power sourcing to the MCU through the ESD structures on the GPIOs", a concern at power-up and power-down), https://www.ti.com/lit/an/slaa689b/slaa689b.pdf, read 2026-10-18; and Texas Instruments, *Use Conditions for 5-V Tolerant GPIOs on Tiva C Series TM4C123x Microcontrollers*, SPMA053, July 2013, § 3.2 *Leakage Current When Device is Unpowered* (the leakage a pin so designed draws with its supply absent, which its datasheet states), https://www.ti.com/lit/an/spma053/spma053.pdf, read 2026-10-18.

### Required external parts (PARTS)

#### PARTS-1. Every integrated circuit carries the external parts its datasheet requires, at their values and ratings

- **Applies when:** the schematic carries an integrated circuit or a module.
- **Asks:** Does the schematic hold, for each integrated circuit, every external part its datasheet requires for the part to operate, at the value the datasheet gives and rated for what it sees there?
- **Passes:** The review record names, for each integrated circuit, the datasheet's section that lists its required external parts (its typical application, recommended components or layout-and-implementation section, and any table of component values), and the schematic holds each: input and output capacitors, a bootstrap or compensation network, a feedback divider, a reset or crystal's load network, a reference's bypass, a pull-up or pull-down on a configuration pin. Each is at the datasheet's value or inside its stated range, and rated, in voltage, dielectric, power and temperature, for the worst case at its position (`CAPD-1` and `DERATE-2` set how). Where the datasheet recommends an external part, such as a supply decoupling capacitor on each supply pin, and gives no value, the record takes the value from the part maker's own published hardware design guide for the part's family, citing its section, and the schematic holds the part at that value or inside its range. A part the datasheet requires and the schematic lacks, or a value outside the datasheet's range, fails; so does a recommended part whose value is outside the maker's guide, and a datasheet that was not opened.
- **Fails, as the schematic shows it:** a regulator with no output capacitor, or one below the datasheet's minimum; a controller whose supply pin carries a decoupling capacitor of a value far below the one its maker's hardware design guide gives (a 100 pF capacitor where the guide gives 100 nF); a converter with no bootstrap capacitor or a feedback divider differing from the datasheet's table for the output voltage; an integrated circuit whose review row cites no datasheet section.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *LDO Basics: Capacitor vs. Capacitance*, SSZT654, August 2018, introduction ("for an LDO to operate normally, you need an output capacitor"), https://www.ti.com/lit/pdf/sszt654, read 2026-10-18; and Texas Instruments, *Hardware Design Considerations for Custom Board Design Using AM62A7, AM62A7-Q1, AM62A3, AM62A3-Q1, AM62A1-Q1 and AM62D-Q1 Processor Families*, SPRAD85D, December 2024, revised October 2025, § 5 *JTAG*, note (a custom board design follows the processor's schematic design guidelines and schematic review checklist as well as the hardware design considerations), https://www.ti.com/lit/ug/sprad85d/sprad85d.pdf, read 2026-10-18; and Texas Instruments, *MSPM0 C-Series MCU Hardware Development Guide*, SLAAEG4C, October 2023, revised March 2026, § 2.4 *Recommended Decoupling Circuit for Power Supply* ("A combination of a 10μF plus a 100nF low-ESR ceramic decoupling capacitor is recommended to connect to the DVCC pin", the datasheet of the same family saying only "a combination of low-ESR ceramic decoupling capacitor"), https://www.ti.com/lit/pdf/slaaeg4, read 2026-10-18.

### Capacitor derating (CAPD)

#### CAPD-1. A ceramic capacitor that sets a filter, a regulator's stability or a hold-up time is judged on the capacitance it keeps under bias

- **Applies when:** the schematic carries a ceramic capacitor that sets a filter's corner, a regulator's or converter's stability (a minimum output or input capacitance), a hold-up time or a timing.
- **Asks:** After the loss of capacitance under the DC bias it sees, the loss over temperature and its tolerance, does the capacitor still give at least the capacitance its role needs?
- **Passes:** The review record gives, for each such capacitor, the capacitance its role needs and where that comes from (a datasheet's minimum, a corner frequency, a hold-up arithmetic), then the capacitor's capacitance in the worst case: the nominal value multiplied by the fraction the maker's DC-bias curve for that part number and package gives at the working voltage, by the fraction the maker's temperature characteristic gives at the extreme temperature, and by the lowest tolerance. The result is at least the needed capacitance, and the arithmetic is shown. A bias curve that cannot be found for the part counts as absent and fails; so does a capacitor chosen on its nominal value alone.
- **Fails, as the schematic shows it:** a regulator output capacitor whose nominal value only just meets the datasheet's minimum with a high working voltage across a small package; a filter or timing capacitor with no derating arithmetic in its row.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *LDO Basics: Capacitor vs. Capacitance*, SSZT654, August 2018, sections *DC Voltage Derating*, *Temperature Derating* and *A Real Application* (a 10 µF X7R capacitor in a small package falls to 7 µF under DC bias, to 5.5 µF with temperature and to 3.5 µF with a ±20 % tolerance), https://www.ti.com/lit/pdf/sszt654, read 2026-10-18.

### Bus lines (BUSL)

#### BUSL-1. Every open-drain, open-collector and two-wire bus line has a pull-up sized for the bus speed and capacitance

- **Applies when:** the schematic carries a net driven by an open-drain or open-collector output, or a two-wire bus line (a clock or data line of an I2C-type bus), or a wired-OR line such as a shared interrupt.
- **Asks:** Does the line have a pull-up to the rail that sets its high level, with a value between the largest the rise time allows and the smallest the low-level drive allows?
- **Passes:** One pull-up per bus line, to the rail that defines the bus's high level, not one per device. Its value lies between two limits, both shown in the review record. The smallest is (supply minus the lowest-level output voltage the weakest driver guarantees) divided by the sink current that voltage is guaranteed at, from the datasheets. The largest is the maximum rise time of the bus's speed mode divided by 0.8473 times the bus capacitance, the capacitance totalled over every pin, connector and run of wire on the line, and not above the capacitance limit the bus specification gives for that speed. The rise time and the capacitance limit are the speed mode's, from the bus specification; the 0.8473 is the time the line takes to rise between 30 % and 70 % of the supply in units of the time constant. A line with no pull-up, a pull-up outside the two limits, or two pull-ups to different rails, fails.
- **Fails, as the schematic shows it:** a data or clock net with an open-drain pin on it and no resistor to a rail; a resistor whose value the record's arithmetic puts above the largest the bus capacitance allows.
- **Kind:** judgement. **Severity:** function.
- **Source:** NXP Semiconductors, *I2C-bus specification and user manual*, UM10204, Rev. 7.0, 1 October 2021, § 7.1 *Pull-up resistor sizing*, https://www.nxp.com/docs/en/user-guide/UM10204.pdf, read 2026-10-18; and Texas Instruments, *I2C Bus Pullup Resistor Calculation*, SLVA689A, February 2015, revised October 2026, § 2 *Pullup Resistor Calculation* (equations for the smallest and largest value, and the speed modes' table), https://www.ti.com/lit/an/slva689/slva689.pdf, read 2026-10-18.

### Boot, strap and debug (STRAP)

#### STRAP-1. Every boot, strap and mode-select pin is held to a defined level

- **Applies when:** the schematic carries an integrated circuit with a pin sampled at reset or power-up to choose a boot source, a mode or an option, or any input that the datasheet says must not float.
- **Asks:** Is every such pin held at the level the intended mode needs, with no pin left to float, and is the level true at the moment the part samples it?
- **Passes:** Every boot, strap and mode-select pin is tied or pulled, through a resistor of the datasheet's range, to the level the intended boot mode or option needs; the review record gives the level and the datasheet's table row that sets it. A pin the datasheet calls reserved is terminated as the datasheet says and never left unconnected. A pin that has another function after reset has its pull chosen so the other function does not disturb the level at the moment of sampling, and any part that drives the pin returns to the strap level whenever the part is reset. The board holds a means, such as a jumper, a switch or a series link to the other function, to select the debug-friendly boot mode used during development. An unused input of any logic part is held to a valid level, and never left floating.
- **Fails, as the schematic shows it:** a mode pin with no pull and no connection; a reserved boot pin unconnected; a strap pin shared with an output that drives it to the wrong level at reset; a board with no way to choose the development boot mode.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Hardware Design Guide for AM65x Devices*, SPRACJ6A, October 2018, revised December 2022, § 2.2 *Selecting the Boot Mode*, key considerations (boot pins have other functions after reset; reserved pins "should not be left floating and must be terminated"; provision for a development boot mode), https://www.ti.com/lit/an/spracj6a/spracj6a.pdf, read 2026-10-18; and Texas Instruments, *Implications of Slow or Floating CMOS Inputs*, SCBA004E, July 1994, revised July 2021, § 2 *Slow Input Edge Rate* ("Holding the inputs or I/O pins at a valid logic level when they are not being used or when the part driving them is in the high-impedance state is recommended"), https://www.ti.com/lit/an/scba004e/scba004e.pdf, read 2026-10-18.

#### STRAP-2. A debug connector reaches the controller

- **Applies when:** the schematic carries a controller.
- **Asks:** Does a connector, or a set of pads, carry every signal the controller's debug and programming interface needs from the board's edge to the controller?
- **Passes:** A debug connector or footprint of pads is on the board and wired to each pin of the controller's debug interface that the interface and its probe need (data, clock, and reset where the interface uses it), together with a ground and the target's reference voltage for the probe's level shifters, as the controller's datasheet or reference manual and the probe's connection guide list them. The pulls the controller's datasheet asks for on those pins are present. The review record names the connector, the interface and the document that gives the pin assignment. A controller whose debug pins are used for the application as well shows, in the record, that the application's use leaves the interface reachable.
- **Fails, as the schematic shows it:** a controller with no connector, pad set or test points carrying its debug interface; a connector missing the reset or the reference voltage the probe needs; debug pins shared with an output that cannot be released.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Hardware Design Considerations for Custom Board Design Using AM62A7, AM62A7-Q1, AM62A3, AM62A3-Q1, AM62A1-Q1 and AM62D-Q1 Processor Families*, SPRAD85D, December 2024, revised October 2025, § 5 *JTAG* ("the recommendation is to include JTAG connections on the custom board design", with provision for the recommended pulls and for external ESD protection), https://www.ti.com/lit/ug/sprad85d/sprad85d.pdf, read 2026-10-18.

### RC filters at converter inputs (RCFL)

#### RCFL-1. An RC filter at a converter input settles within the converter's acquisition time and passes the signal band

- **Applies when:** the schematic carries a resistor and capacitor between a signal and an analog-to-digital converter input, on a converter part or inside a controller.
- **Asks:** At the converter's sample rate, does the converter's sampling capacitor settle through the filter to within half a least-significant bit in the acquisition time, and does the filter's corner pass the highest frequency of the signal to be measured?
- **Passes:** The review record gives the converter's resolution (n bits), sample rate and conversion time from its datasheet, and the sampling capacitor and the source resistance the datasheet states. The acquisition time is the sample period less the conversion time. The filter's capacitor is at least 20 times the sampling capacitor, so it holds the charge the sampling draws. The settling time constant, the acquisition time divided by the natural logarithm of 2 to the power n, is at least the product of the filter's resistance and that capacitor. A converter whose input stage the datasheet says needs a driving amplifier is driven by one. The filter's corner, one over 2π times the product of resistance and capacitance, lies above the highest frequency of interest, and the record states that frequency and where it comes from. A filter for which any of these figures cannot be sourced fails.
- **Fails, as the schematic shows it:** a series resistor and shunt capacitor at an input whose product the record's arithmetic puts above the acquisition time over the logarithm; no filter capacitor where the datasheet asks for one; no stated signal band.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Driving SAR and Delta-Sigma ADC Inputs*, TI Precision Labs seminar, SPRPEO2, last updated October 2025, the slides *Charging the CSH Capacitor Within tacq* (the sampling capacitor settles to half a least-significant bit within the acquisition time, the sample period less the maximum conversion time) and *Is RC Circuit Sufficient?* (the external capacitor is 20 times the sampling capacitor; the largest source resistance is the acquisition time divided by the natural logarithm of 2 to the power n, divided by that capacitor) and the slides on the driver's bandwidth requirements (the signal chain's bandwidth is calculated first), https://www.ti.com/lit/ml/sprpeo2/sprpeo2.pdf, read 2026-10-18.

### Power-up and brown-out (SUPPLY)

#### SUPPLY-1. Inrush at power-up stays within what the source, the connector and the protective devices carry

- **Applies when:** the schematic carries a supply input or a rail with capacitance on it, or a switch that connects a capacitive load to a live rail.
- **Asks:** When power is first applied, or a capacitive load is switched on, is the peak current into the uncharged capacitance within the source's output limit and the ratings of every connector, conductor and protective device it passes?
- **Passes:** The review record gives, for each supply input and each switched capacitive load, the capacitance charged (every capacitor on the rail, the datasheets' tolerances included) and the supply's rise time at the pin, and from them the inrush current, the capacitance multiplied by the voltage change and divided by the time it takes. That current is at or below the source's current limit, the rating of each connector and terminal on the path, the conductor ratings the circuit-proof record gives, and what the protective device carrying it passes without acting. Where it is not, the schematic limits it: a soft-start or slew-controlled switch, a series resistance or a thermistor, and the record shows the limited current by the same arithmetic. A rail with no stated rise time or capacitance fails.
- **Fails, as the schematic shows it:** bulk capacitance behind a connector with no soft-start, switch with a controlled slew or series limit and no inrush figure in the record; a record whose inrush figure exceeds a rating it names.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Managing Inrush Current*, SLVA670A, August 2014, revised May 2015, § 1 *What is Inrush Current?* (inrush current is the load capacitance times the voltage change over the rise time), § 2 *Problems Caused by Inrush Current* (connector, terminal and trace current ratings; a supply that cannot supply the current is pulled down) and § 3 *Methods of Reducing Inrush Current*, https://www.ti.com/lit/an/slva670/slva670.pdf, read 2026-10-18.

#### SUPPLY-2. Every supply that powers a part with undefined behaviour below a minimum voltage has undervoltage lockout

- **Applies when:** the schematic carries a rail that powers a controller, a drive stage, a sensor front end or any part whose datasheet gives a minimum operating voltage below which its outputs are not defined.
- **Asks:** Does the rail's source, or a supervisor on the rail, hold the loads in reset or off until the rail is high enough for all of them to behave predictably, with a margin against the supply dipping when the load turns on?
- **Passes:** Each such rail has an undervoltage lockout: in the regulator, or in a supervisor whose threshold is set on that rail. Its turn-on threshold, with the datasheet's tolerance applied at its low end, is at or above the highest minimum operating voltage of any load on the rail. Its hysteresis is greater than the worst-case dip the supply suffers when the loads turn on, computed from the supply's source impedance and the loads' turn-on current, plus a margin. A controller on the rail is held in reset until the rail is above its own threshold. The review record shows the thresholds, the hysteresis, the dip and where each figure comes from. A rail with none, or with a threshold below a load's minimum, fails.
- **Fails, as the schematic shows it:** a regulator whose enable is tied on, feeding a controller with no supervisor or reset hold; a supervisor threshold set below the controller's minimum operating voltage.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *Understanding Undervoltage Lockout in Power Devices*, SLVA769A, April 2016, revised September 2018, § 1 *The Need for an Undervoltage Lockout Function* (below the minimum voltage "the bandgap reference may generate the wrong voltage", "logic functions may generate the wrong control signals"), § 3 *Hysteresis and UVLO "Bouncing"* (the worst-case drop caused by the device turning on is less than the hysteresis, with margin) and § 5 *Data Sheet Parameters*, https://www.ti.com/lit/pdf/slva769, read 2026-10-18.

### Polarity (POLAR)

#### POLAR-1. Every polarised part's orientation is marked on the schematic and no state reverse-biases it beyond its rating

- **Applies when:** the schematic carries a polarised capacitor (aluminium electrolytic or tantalum), a diode, a light-emitting diode, or any other part whose datasheet distinguishes its terminals by polarity.
- **Asks:** Does the schematic show which terminal of each such part is which, matching its datasheet, and does no operating state put a reverse voltage across it that its datasheet does not allow?
- **Passes:** Each polarised part's symbol marks its positive terminal or its cathode, and the symbol's pin numbers map to the terminals of the datasheet's pin table, so the same marking is carried onto the footprint without a second reading. The review record gives each part's reverse-voltage rating from its datasheet, or notes that the datasheet allows none, and no state, including start-up, hot-plugging of a supply and a fault, puts more than that across it. An aluminium electrolytic capacitor on a rail whose polarity can reverse is a bipolar type, or is replaced. A part whose datasheet distinguishes no polarity is marked as unpolarised. A datasheet that cannot be opened fails the part.
- **Fails, as the schematic shows it:** a polarised capacitor drawn as an unpolarised symbol, or a symbol whose pin numbers differ from the datasheet's; a rail that can be driven below the capacitor's negative terminal by another supply; a light-emitting diode with a reverse path above its rating.
- **Kind:** judgement. **Severity:** function.
- **Source:** Nippon Chemi-Con, *Precautions and Guidelines (Aluminum Electrolytic Capacitors)*, CAT. No. E1001A 2026, § 2 *Polarity* ("Never apply a reverse voltage or AC voltage. Connecting with wrong polarity will short-circuit or damage the capacitor"; polarity is marked on the body, and a bipolar type serves circuits where polarity is occasionally reversed), https://www.chemi-con.co.jp/products/relatedfiles/capacitor/catalog/al-precaution-e.pdf, read 2026-10-18; Teverovsky, A., NASA Goddard Space Flight Center, *Reverse Bias Behavior of Surface Mount Solid Tantalum Capacitors*, CARTS 2002, § 1.1 *Background* (solid tantalum capacitors are polarised and "designed to operate only under forward voltage bias conditions"; incorrect installation is the more serious consequence), https://nepp.nasa.gov/npsl/capacitors/55365/reverse_bias_solid_tantalum_caps.pdf, read 2026-10-18; and Vishay Semiconductors, *VLMPG31L1M2* data sheet, Rev. 1.5, 27 September 2021, absolute maximum ratings (a reverse voltage rating, with the note that driving the LED in the reverse direction suits short-term application only), https://www.vishay.com/docs/81653/vlmpg31l1m2.pdf, read 2026-10-18.

### Cables and harnesses (CABLE)

#### CABLE-1. A cable's pinning is checked against the retained harness it mates with

- **Applies when:** the schematic carries a connector that mates a cable or harness the board does not define, one that is kept from an existing machine or bought as an assembly.
- **Asks:** Is each signal on the schematic's connector delivered to the contact at the far end of the harness that the far end's device expects, with the harness's wiring, straight-through or mirrored, taken from the harness itself?
- **Passes:** For each such harness the review record gives its wiring from a source about that harness (its drawing, its datasheet, or continuity measured on the harness itself), saying for each contact at one end which contact at the other end it reaches, so whether the assembly is wired straight through or mirrored is stated and never assumed from a picture or from the connector's numbering. It names the view each connector's numbering is drawn from (the mating face or the cable-entry side) and an asymmetrical reference, such as a key or a polarisation notch, that the numbering is read against. Each signal of the schematic's connector, traced through the harness, reaches the pin of the far device that expects it, and the record shows the trace row by row. A harness whose wiring cannot be sourced counts as absent and fails.
- **Fails, as the schematic shows it:** a connector whose pin numbers are assigned on the assumption that pin 1 meets pin 1 where the harness is mirrored; a record that states no view for the numbering; a harness row with no source.
- **Kind:** judgement. **Severity:** function.
- **Source:** DigiKey Technical Forum, thread *Cable pinout*, 2–3 May 2024 (a reply in the thread says that a ribbon cable assembly is wired mirrored, "contrary to the image representation" of it), https://forum.digikey.com/t/cable-pinout/40883, read 2026-10-18; and Bespokecable, *Why IDC-to-D-Sub Ribbon Cables Are Not Automatically Interchangeable*, 4 October 2026 ("Turning a connector over can mirror the apparent contact order"; drawings should carry an asymmetrical reference and state their view), https://www.bespokecable.com/idc-to-d-sub-ribbon-cable-compatibility/, read 2026-10-18.

### Single-fault analysis (FAULT)

#### FAULT-1. Every component fault in a protective chain leaves the protected output safe or is detected

- **Applies when:** the schematic carries a chain of parts whose purpose is to hold an output in a safe state, such as one that removes power from a load, including every part in the path from the decision to the switching device that acts on it.
- **Asks:** For each part of the chain, in each way it can fail alone, is the protected output left safe, or is the fault detected before it can matter?
- **Passes:** The review record lists every part in the chain, with the failure modes of each: open, short, drift out of tolerance, and for an integrated circuit an output stuck high, stuck low or undefined. For each mode it gives the effect on the protected output and one of two outcomes. The output is safe, with the reason shown from the schematic. Or the fault is detected, naming the diagnostic that detects it, the time within which it does, and the safe state the board then enters. No single fault leaves the output unsafe and undetected. Detection is by the chain's own means, such as a test the chain imposes before power can be made available to the load, and never by the controller or its firmware noticing, since the chain owes nothing to either. A detected fault is shown to be found before a second fault can combine with it, the stated test interval being shorter than the time a second fault takes to arise, and the board is then held from powering the load until a person attends. A fault that leaves the chain looking healthy while it no longer protects is the case this item exists to exclude: the record names, for each part, the test that would show it. A part of the chain missing from the list, or a mode with neither outcome, fails.
- **Fails, as the schematic shows it:** a switching device with no failed-short mode in the record; a detection that depends on the part that has failed; a protected output that stays energised after a failed-short mode whose only diagnostic is the controller that commands it.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Texas Instruments, *Understanding Functional Safety for Gate Drivers and Traction Inverter Systems*, SSZT066, August 2022, the section on random hardware faults ("Single-point faults violate safety goals without the presence of a safety mechanism"; a fault in a safety mechanism is latent unless another mechanism detects it), https://www.ti.com/lit/pdf/sszt066, read 2026-10-18.

### Independence of the power cut-off (INDEP)

#### INDEP-1. The element that removes power on loss of proof of life takes nothing from the controller's clock, reset or supply

- **Applies when:** the schematic carries an element, such as a watchdog-held switch, a timer or a latch, that removes power from a hazardous load when the controller stops showing that it is running.
- **Asks:** Does the schematic show that the element's timing, its reset and its supply do not come from the controller's, so the failure of any of those leaves the load unpowered?
- **Passes:** Tracing every net of the element in the netlist, none reaches the controller's clock, oscillator or timer output, the controller's reset net or reset output, or the supply rail that powers the controller, except the one signal by which the controller shows that it is running. The element's time base is its own (an oscillator or a passive timing network that no part of the controller feeds). Its reset and its supply either come from a source that is not shared with the controller, or are shown to fail in the direction that removes power, and the review record shows that trace for the clock, the reset and the supply separately. With the controller's clock stopped, its reset held, or its supply sagged below its operating range, the element's default state, shown on the schematic, is the one that removes power, and the record shows that state for each of the three. The element is therefore independent in the schematic itself, and not first discovered so at bring-up.
- **Fails, as the schematic shows it:** an element clocked from a controller output; one reset by the controller's own reset net; one powered from the controller's regulator with its output held on when that supply collapses; a trace in the record that stops at a shared net.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Texas Instruments, *Industrial Functional Safety PLC Architecture Implementation based on TI MCU/MPU*, SDAA393, June 2026, the key requirement *Independence* ("Failure of one sub-goal should not cause failure of another"; "using different hardware, different power supplies, different clocks") and the limitation of a single-chip arrangement ("Cannot detect common-cause failures (e.g., shared clock fault)"), https://www.ti.com/lit/an/sdaa393/sdaa393.pdf, read 2026-10-18; and Texas Instruments, *Obtain UL/IEC 60730-1/60335-1 Class B Certification Based on C2000 MCU Diagnostic Library in Appliances*, SPRADI6, May 2024, the clock-diagnostic section ("Common cause failures can be reduced by using different clock sources and different prescale values"), https://www.ti.com/lit/an/spradi6/spradi6.pdf, read 2026-10-18.

### Mains-to-low-voltage barriers (BARRIER)

#### BARRIER-1. Every part that forms a mains-to-low-voltage barrier carries a sourced isolation rating at or above the barrier's declared insulation

- **Applies when:** the schematic carries a part that forms a barrier between a mains-referenced net and a low-voltage net: an isolator, an optocoupler, a transformer, a relay, a safety capacitor, or a separation by spacing.
- **Asks:** Does the part carry, from its own datasheet or certificate, an isolation rating at or above what the barrier it forms is declared to provide, for its insulation type, working voltage, transient withstand and creepage and clearance?
- **Passes:** For each such part the review record gives the barrier's declared insulation type, basic or reinforced, with its working voltage, overvoltage category, pollution degree and material group, read from the board's separation basis record, and the part's own ratings from its datasheet or certificate: the insulation type it is certified for, its maximum working isolation voltage, repetitive peak and transient isolation voltages, surge isolation voltage, the creepage and clearance its package gives, and the material group of its body. Each is at or above what the barrier needs. A barrier declared reinforced is formed by a part certified for reinforced insulation, or by two independent basic barriers in series, shown as such; a part certified for basic insulation only does not form it. What the barrier needs is read from the governing standard the separation basis record names, through the rows of its tables that record keeps, or from a cited, freely available derivation of those tables, and never from memory. A rating that cannot be sourced counts as absent and fails. The barrier is declared in the separation basis record, and a barrier the record does not list fails.
- **Fails, as the schematic shows it:** a barrier part whose review row cites no datasheet rating; a part certified for basic insulation forming a barrier the record declares reinforced; a working voltage in the record above the part's rated working isolation voltage; a barrier absent from the separation basis record.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Texas Instruments, *Isolation Glossary*, SLLA353A, October 2014, revised September 2017, § 1 *Isolation Glossary* (the rated isolation voltages as the manufacturer assigns them), § 1.1 *Insulation* (basic, supplementary, double and reinforced insulation defined), § 1.2 *Pollution Degree* and § 1.3 *Overvoltage Categories and Installation Classification*, https://www.ti.com/lit/an/slla353/slla353.pdf, read 2026-10-18; and Texas Instruments, *High-voltage reinforced isolation: definitions and test methodologies*, SLYY063A, May 2026, the passage on isolation types ("An isolator can be called reinforced at the component level, only if it passes the surge test", at a level the standard sets, and its isolation voltages are tested during certification), https://www.ti.com/lit/slyy063, read 2026-10-18.

### Mains transients (SURGE)

#### SURGE-1. Mains-side transient protection is rated for the surge of the declared overvoltage category, from its makers' ratings

- **Applies when:** the schematic carries a mains input, or a net referenced to the mains.
- **Asks:** Does a surge-limiting part sit at the mains input, with a continuous rating above the highest mains voltage and a surge-current and energy rating, taken from its maker's curves for the surge's waveform, above the surge the declared overvoltage category brings, and does it clamp low enough for what is behind it?
- **Passes:** The mains input carries a surge-limiting part: a varistor, a transient voltage suppressor or a gas discharge tube, with the series impedance or fuse the maker's note calls for. The review record gives the surge its place sees: the test voltage and waveform the governing standard sets for the overvoltage category in the separation basis record, taken from that standard's rows the record keeps or from a cited, freely available derivation, and never from memory, and the source impedance used to turn the voltage into a current, stated. Against that it gives the part's maker's ratings: the continuous (working) voltage, at or above the highest mains voltage with the supply tolerance and a margin the maker's note names; the peak surge current at that waveform, derated for a longer pulse from the maker's pulse-rating curve; the energy rating; and the maximum clamping voltage at the surge current. The clamping voltage is at or below what everything behind the part withstands, including the transient withstand of the barrier parts (`BARRIER-1`). The part's failure mode is a short, so an overcurrent device in series with it is shown. A rating that cannot be sourced counts as absent and fails.
- **Fails, as the schematic shows it:** a mains input with no surge-limiting part; a part whose surge rating comes from no datasheet curve; a clamping voltage above the withstand of the first part behind it; a surge-limiting part with no fuse or other overcurrent protection in series.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Littelfuse, *Considerations for Selecting Littelfuse MOVs and Fuses for Industrial Motor Applications*, application note EC608, April 2001, sections *Surge Current, Energy and MOV Size* (the peak surge current rating depends on the disc area and the energy rating on its volume; a pulse longer than 20 microseconds needs the current rating derated; "exceeding the surge current or energy dissipation ratings of an MOV can result in damage to it. Since the failure mode is a short circuit", the maker recommends overcurrent protection) and the clamping-voltage and V-I characteristics, https://docs.rs-online.com/cc3c/0900766b800a9c37.pdf, read 2026-10-18.

### Static discharge (ESD)

#### ESD-1. Every connector or control a person can reach is protected against static discharge at the declared level

- **Applies when:** the schematic carries a connector, terminal, header, switch, button or other conductor that a person can touch, or reach with a cable, in normal use or service.
- **Asks:** Does each such conductor reach the circuit only through a part that holds a discharge at the declared level below what the circuit behind it withstands?
- **Passes:** At the entry of each reachable conductor the schematic holds a clamping part, such as a transient voltage suppressor sized for the discharge, with a series element where the circuit needs one, or the conductor is separated from the circuit by a barrier whose rating covers the discharge (`BARRIER-1`). The discharge level the board must withstand, its voltage, its current and its waveform, comes from the governing standard the board's records name, through its rows or a cited, freely available derivation, and never from memory. The review record shows, for each entry, the voltage the line sees: the clamp's breakdown voltage plus its dynamic resistance times the discharge current plus the inductance in the clamp's path times the current's rate of change, and that it is at or below the absolute maximum of every pin behind it (`PINV-1`). The clamp's own ratings are the maker's, from its datasheet at the discharge's waveform. A reachable conductor with none, or a clamping voltage above a pin's rating, fails. How the clamp is placed on the board is the layout catalogue's.
- **Fails, as the schematic shows it:** a connector whose signals go straight to controller pins; a clamp whose datasheet rating is below the declared level; a record with no clamping arithmetic.
- **Kind:** judgement. **Severity:** function.
- **Source:** Texas Instruments, *ESD Protection Layout Guide*, SLVA680A, February 2015, revised April 2022, § 1 *Introduction* (the transient voltage suppressor as the foundation of an ESD protection strategy, the standard's waveform) and § 2.1 *Optimizing Impedance for Dissipating ESD* (the voltage the line sees is the breakdown voltage plus the dynamic resistance times the discharge current plus the inductance times the current's rate of change), https://www.ti.com/lit/an/slva680/slva680.pdf, read 2026-10-18.

### Touch current (TOUCH)

#### TOUCH-1. Touch current, estimated from the leakage of the filter and supply parts to protective earth, is within the limit for the protection class

- **Applies when:** the schematic carries a mains input with a filter or supply whose capacitors connect a mains conductor to protective earth or to an accessible conductive part.
- **Asks:** Does the sum of the currents the filter's and the supply's parts leak to protective earth, or to an accessible part, at the worst-case mains voltage and frequency, stay within the limit set for the appliance's protection class?
- **Passes:** The review record lists every capacitor, and every other part, that connects a mains conductor to protective earth or to an accessible conductive part: the filter's line-to-earth capacitors, the supply's rated leakage from its datasheet, and any other. For each capacitor the current, at the top of the declared supply span and the highest mains frequency, with the protective earth connection open where the protection class relies on it, is 2π times the frequency times the capacitance times the voltage, taken at the capacitor's highest tolerance, and the lines' imbalance as the filter maker's note states it; the sum is the estimate. The record states that ceramic capacitors' capacitance rises with frequency and varies with voltage, and a margin for it. The limit is the one the governing standard sets for the appliance's protection class and type of connection, which the board's records name, taken from that standard's rows the record keeps or a cited, freely available derivation, and never from memory. The record keeps touch current (through a person) apart from protective-conductor current (through the earth conductor in normal operation), and says which the limit applies to. An estimate above the limit, or one with a part's leakage missing, fails. A supply or filter whose leakage the datasheet does not state counts as absent and fails.
- **Fails, as the schematic shows it:** line-to-earth capacitors with no leakage arithmetic in the record; a limit stated without naming the standard and the protection class; a filter datasheet's leakage figure taken without the tolerance and frequency conditions it was quoted under.
- **Kind:** judgement. **Severity:** safety.
- **Source:** Schaffner EMV AG, *Leakage Currents in Power Line Filters: Basics about leakage currents including calculation and measurements*, July 2008, § 2 *Requirements in the standards* (touch current is the current through a person; protective earth current flows in normal operation) and § 3 *Calculation of leakage currents* (filter makers quote a calculation at nominal voltage with a stated imbalance and a ±20 % capacitor tolerance; the frequency and voltage dependence of ceramic capacitors is not taken into account, so their leakage can be higher than calculated), https://emcfastpass.com/wp-content/uploads/2017/04/Powerline_leakage.pdf, read 2026-10-18; and EPCOS (TDK), *Application note for Y2 EMI capacitors*, June 2018 (leakage at mains frequency flows through a line-to-frame-ground capacitor and grows with its capacitance, so safety standards limit the capacitance), https://de.tdk-electronics.tdk.com/download/2287190/98201b967d8093a28484585afb216956/pdf-emiapplicationnote-y2.pdf, read 2026-10-18.

### Emissions at their sources (EMSRC)

#### EMSRC-1. A filter sits at the supply inlet, ahead of the first switching stage

- **Applies when:** the schematic carries a mains input feeding a switching stage, a switched load or a supply.
- **Asks:** Does a filter stand between the mains input and the first switching stage, sized to bring the conducted disturbance within the governing standard's limits for household appliances?
- **Passes:** A filter of line-to-line capacitors, line-to-earth capacitors and, where the attenuation needed requires it, a common-mode choke, sits between the inlet and the first switching part. The review record names the standard's emission limit for household appliances that the board's EMC record cites, taken from the standard's rows the record keeps or a cited, freely available derivation, and never from memory, and the attenuation the filter must give against the board's switching spectrum, with the filter maker's ratings. The line-to-earth capacitance is the one `TOUCH-1` accepts. Where the filter is a bought part, its datasheet's attenuation, rated voltage and leakage are cited. An inlet with no filter, or a filter whose attenuation cannot be sourced, fails. How the filter is laid out is the layout catalogue's emissions area (`EMI`).
- **Fails, as the schematic shows it:** a mains inlet wired straight to a switching converter or a phase-controlled load; a record naming no limit; line-to-earth capacitance chosen without `TOUCH-1`'s arithmetic.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Schaffner EMV AG, *Leakage Currents in Power Line Filters*, July 2008, § 1 *Abstract* (noise suppression filters are "almost mandatory") and § 3 *Calculation of leakage currents* (X-capacitors between phases suppress differential-mode interference and Y-capacitors between phase and earth suppress common-mode interference), https://emcfastpass.com/wp-content/uploads/2017/04/Powerline_leakage.pdf, read 2026-10-18; and EPCOS (TDK), *Application note for Y2 EMI capacitors*, June 2018 (capacitors across the AC lines reduce differential-mode noise, effective at high frequency), https://de.tdk-electronics.tdk.com/download/2287190/98201b967d8093a28484585afb216956/pdf-emiapplicationnote-y2.pdf, read 2026-10-18.

#### EMSRC-2. Each switched mains load has a network that limits the slope of the voltage at its switching device

- **Applies when:** the schematic carries a semiconductor switch, such as a triac, that connects a mains load, particularly an inductive one.
- **Asks:** Does a snubber or an equivalent network at the switch limit the rate of rise of the voltage re-applied across it at turn-off and the overvoltage that rate produces, to within the device's datasheet limits?
- **Passes:** The load's switching device carries a resistor-capacitor network across it, or the device is of a type whose datasheet states that none is needed at this load and supply, shown from the datasheet's commutation figures. The review record gives the device's critical rate of rise of voltage and its repetitive peak off-state voltage from the datasheet, the load's inductance and the supply's range, and shows that the network holds the re-applied slope below the first, and the overvoltage the network's resonance produces below the second, with the network's resistor and capacitor rated for the mains voltage across them. The slope this limits is the one the governing standard's emission limits for household appliances, named in the board's EMC record, constrain; the figure comes from that standard through its rows the record keeps, or a cited, freely available derivation, never from memory. A switched mains load with neither fails.
- **Fails, as the schematic shows it:** a switching device across an inductive mains load with no network and no datasheet statement that none is needed; a network sized without the device's critical slope.
- **Kind:** judgement. **Severity:** quality.
- **Source:** STMicroelectronics, *New triacs: is the snubber circuit necessary?*, application note AN437, T. Castagnet, 1999 (AN437/0899), sections *Aim of the snubber circuit* (limiting the reapplied dV/dt below the specified critical value is the snubber's main function) and *Choice of the snubber circuit* (the circuit resonates with the load, and its choice is a compromise between the critical dV/dt and the device's repetitive peak off-state voltage), https://www.thierry-lequeu.fr/data/AN437.pdf, read 2026-10-18.

#### EMSRC-3. The edge rates of switching parts are bounded

- **Applies when:** the schematic carries a switching power stage, such as a switched-mode converter or a bridge of transistors, or a driver of a line that leaves the board.
- **Asks:** Is the edge rate of each switching part set, by a gate resistor, a slew-rate setting or a limited drive, to a value that meets the emission limit at the cost of losses the design can bear?
- **Passes:** Each such part's switching edge is bounded by a part on the schematic: a series resistor in the gate path, a driver's slew-rate setting, a snubber from the switching node to ground, or a driver output of limited slew. The review record states the edge rate chosen, the emission limit for household appliances it serves, named by the standard the board's EMC record cites and read from its rows the record keeps or a cited, freely available derivation, never from memory, and the switching loss at that edge rate against the part's thermal limit (`DERATE-2`). An edge rate left at the part's default without a statement that it was judged fails. How the switching loop is laid out is the layout catalogue's decoupling and emissions areas.
- **Fails, as the schematic shows it:** a gate driven directly with no resistor and no slew setting, with no statement in the record; a slew setting with no loss figure.
- **Kind:** judgement. **Severity:** quality.
- **Source:** Texas Instruments, *Understanding Gate Driver Slew Rate Control, MOSFET Switching Optimization and Protection Features*, SBAA698A, August 2025, revised September 2025, section *Slew Rate Control* ("Determining the desired MOSFET slew rate is a tradeoff between EMI performance and efficiency"), https://www.ti.com/lit/pdf/sbaa698, read 2026-10-18; and Texas Instruments, *How to Use Slew Rate for EMI Control*, SSZTBI0, March 2016 (slowing the turn-on and turn-off with series gate resistors, and a snubber from the switch node to ground, reduce switch-node ringing and the conducted emissions it causes, at a cost in switching loss), https://www.ti.com/lit/pdf/ssztbi0, read 2026-10-18.

### Derating (DERATE)

#### DERATE-1. The board declares a derating policy

- **Applies when:** always.
- **Asks:** Does the board's records state a derating policy, giving for each class of part the share of its rating it may be used at, in voltage, power and temperature, each factor with its source?
- **Passes:** A derating policy is kept in the board's records, naming each class of part the board uses (capacitors, resistors, semiconductors, integrated circuits, inductive parts, relays and connectors, or the board's own classes) and, for each, the factor on rated voltage, on rated power or current, and the highest junction or body temperature, each with a published source or a stated reason from a reliability requirement. A factor taken from an organisation's practice names that practice. A board with no policy, a class of part the policy omits, or a factor with no source, fails.
- **Fails, as the schematic shows it:** parts of a class with no factor in any record; a factor stated without a source.
- **Kind:** judgement. **Severity:** quality.
- **Source:** NASA Goddard Space Flight Center, *EEE Parts Derating*, Preferred Reliability Practice PD-ED-1201 (derating policies stated as maximum shares of rated voltage, power and junction temperature by part class, set as design policy or from a reliability requirement), https://klabs.org/DEI/References/design_guidelines/design_series/1201.pdf, read 2026-10-18; no date is printed on the document.

#### DERATE-2. Every part works within its derated rating at its worst-case operating point

- **Applies when:** always; it selects every part.
- **Asks:** At the highest voltage, current, power and temperature the part sees in any operating state, is each stress within the rating the board's derating policy allows, taken from the part's datasheet at that temperature?
- **Passes:** For each part the review record gives its worst-case voltage across it, current through it, power dissipated and temperature (the hottest enclosure condition the board's records declare, plus the part's own rise from its dissipation and thermal resistance), at the top of the declared supply span and the heaviest load; the rating of each from the part's datasheet at that temperature, including any derating curve; and the policy's factor for its class (`DERATE-1`). Each stress is at or below its rating multiplied by the factor, and the arithmetic is shown. Where a part is selected by another item's arithmetic (`CAPD-1`, `SURGE-1`) its row cites that arithmetic. A part with no datasheet rating at the temperature counts as absent and fails; so does a part with no row.
- **Fails, as the schematic shows it:** a resistor dissipating its full rating at the hottest ambient; a capacitor at its rated voltage; a part with no row in the record.
- **Kind:** judgement. **Severity:** quality.
- **Source:** NASA Goddard Space Flight Center, *EEE Parts Derating*, Preferred Reliability Practice PD-ED-1201 ("Derate applied stress levels ... with respect to the maximum stress level ratings of the part. The allowed stress levels are established as the maximum levels in circuit applications"; "Maximum junction temperature levels should not be exceeded at any time"), https://klabs.org/DEI/References/design_guidelines/design_series/1201.pdf, read 2026-10-18.

### Drawing (DRAW)

#### DRAW-1. Every sheet is drawn to the schematic drawing convention

- **Applies when:** always; it selects every sheet of the schematic, the root sheet included, and a sheet is named in the review's verdict table as the review's step 2 names it.
- **Asks:** Does the sheet meet each item of the [Schematic drawing convention](#schematic-drawing-convention): one function, a name for that function, every net named by its designer, wires within a circuit and labels between circuits, one direction of signal flow, supply rails named alike across sheets, each connector labelled with its pins and what each carries, and text clear of other text and of symbols?
- **Passes:** The review record cites the sheet's drawing and, for each item of the convention, what in the sheet shows it met, or why the item does not arise on the sheet (a sheet with no connector has nothing for the seventh). The sheet holds one function, has a name of its own that says what it is, carries no net the tool named, joins circuits by labels, reads in one direction, carries each rail under its one name, labels each connector pin, and has no overlapping text.
- **Fails, as the schematic shows it:** a sheet holding two unrelated circuits; a sheet whose name is `Sheet2` or the design's own; a net the netlist names `Net-(R4-Pad1)`, or a signal-carrying pin left unconnected (`unconnected-` followed by the pin); a wire run across a sheet where a label would do; a rail spelt two ways on two sheets; a connector whose pins carry no names; a reference designator drawn over a wire.
- **Kind:** judgement. **Severity:** cosmetic.
- **Source:** Flux, Gabriel Hacohen, *PCB Schematic Best Practices for Clean Circuit Design*, June 2026, § *Grouping Circuits*, § *Clean Schematic Checklist* and § *Labeling Conventions*, https://www.flux.ai/p/blog/pcb-schematic-best-practices, read 2026-10-18; and KiCad project, *KiCad 10.0 Schematic Editor* manual (the *Schematic Editor* chapter), §§ *Net name assignment rules* and *Power symbols*, https://docs.kicad.org/10.0/en/eeschema/eeschema.html, read 2026-10-18. The convention's own items each cite their sources in full.

Out of scope for this section: applying the catalogue to a board, which the [schematic review](#schematic-review) does; the layout items, which the [Layout practice catalogue](#layout-practice-catalogue) holds; and any figure specific to one machine.
