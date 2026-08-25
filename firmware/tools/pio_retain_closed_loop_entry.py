"""Keep control_command_temperature reachable in the target artefact.

Nothing under src/app/stm32 commands a delivery -- main() only brings the
control path up and steps it forever, which is everything the machine itself
needs but leaves the one entry point
SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT's closed-loop harness needs
unreached: something with no target hardware present has no other route to
ask the artefact for a delivery at all. The linker discards code nothing
reaches, so without this the harness's one call into the artefact from
outside its own call graph resolves to no symbol.

This is the same precedent tools/pio_retain_plant_model.py already sets for
the plant seam's own operations, applied to the one control-seam entry a
harness with no target hardware needs to reach in from outside.
"""

Import("env")  # noqa: F821

env.Append(LINKFLAGS=["-Wl,--undefined=control_command_temperature"])  # noqa: F821
