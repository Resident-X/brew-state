"""Keep the entry points a draw is commanded through reachable in the target
artefact.

Nothing under src/app/stm32 commands a delivery -- main() only brings the
control path up and steps it forever, which is everything the machine itself
needs but leaves the entry points
SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT's closed-loop harness needs
unreached: something with no target hardware present has no other route to
ask the artefact for a delivery at all. The linker discards code nothing
reaches, so without this the harness's calls into the artefact from outside
its own call graph resolve to no symbol.

Two of them, because a draw is two commands. A temperature alone leaves the
pump off for the whole run, which leaves the water on its way to the group
reaching the block by conduction alone -- and a loop that never moves water
holds the heater at its limit for every interval a run of emulable length can
cover, which is a loop whose reading changes nothing it does.

This is the same precedent tools/pio_retain_plant_model.py already sets for
the plant seam's own operations, applied to the control-seam entries a
harness with no target hardware needs to reach in from outside.
"""

Import("env")  # noqa: F821

env.Append(LINKFLAGS=[  # noqa: F821
    "-Wl,--undefined=control_command_temperature",
    "-Wl,--undefined=control_command_flow",
])
