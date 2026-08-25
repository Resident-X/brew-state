# The emulation tier

The target build writes an artefact. This directory runs that artefact — the
file itself, not a rebuild of it and not a re-expression of what it does — on an
emulated STM32F407, against models of the peripherals the hardware seam drives,
and asks two questions of it that no test above the seam can reach:

- does every sensor channel the seam declares have a peripheral behind it, and
  does each one read its own converter input rather than a neighbour's?
- does every output channel the seam declares reach a compare register of its
  own, so that no two commands land on the same output and none lands on
  nothing?

The second question is the reason the tier exists. A comparison between a
control law and a plant model is taken above the addressing, so both sides of it
agree about a channel that was commanded and a channel that was written — even
when those are two different channels. Only something that watches the registers
can tell them apart.

A third, distinct question is answered by the closed-loop run described below:
does the artefact's own control law, actuating and sensing through those same
two models, actually close the loop with the plant model those channels are
addressed against — not merely address it correctly, but move it, and read back
what moving it produced.

## Running it

```
task fw:emulate:provision    # once, and again when the pins change
task fw:emulate
```

`fw:emulate` builds the target environment, hands the emulator the artefact that
build wrote, exercises every channel, runs the closed-loop check, and asserts
both. It is also part of `task fw:verify`.

To re-run a single exercise by hand without the suite, each run leaves a
complete emulator script beside the artefact:

```
.tooling/renode-*/…/renode --console --disable-xwt \
    firmware/.pio/build/stm32/emulation/emulation_check.resc
.tooling/renode-*/…/renode --console --disable-xwt \
    firmware/.pio/build/stm32/emulation/closed_loop.resc
```

Both scripts name absolute paths and depend on nothing else, so each reproduces
its run exactly. The emulator's own log of a run is beside its script, in
`emulation_check.log` or `closed_loop.log`. The closed-loop run additionally
needs `BREW_STATE_PLANT_LIBRARY`, `BREW_STATE_PLANT_PARAMETERS` and
`BREW_STATE_EMULATION_PERIPHERALS_DIR` set in its environment — see
`tools/run_closed_loop_check.py`, which sets all three before launching it.

## What is here

| path | what it is |
| --- | --- |
| `platform/brew_state_stm32f407.repl.in` | the emulated machine, with the location of the two peripheral models left to the runner to fill in |
| `peripherals/adc1.py` | the converter behind the seam's sensor channels, as a register model |
| `peripherals/tim3.py` | the timer behind the seam's output channels, as a register model |
| `peripherals/plant_bridge.py` | closes the loop between the two register models and the plant model, over the closed-loop run's own environment variables |
| `scripts/emulation_check.resc.in` | the channel-addressing run, as the emulator is given it |
| `scripts/exercise.py` | what is done to the artefact once loaded, for the channel-addressing run; it observes and reports, and asserts nothing |
| `scripts/closed_loop.resc.in` | the closed-loop run, as the emulator is given it |
| `scripts/closed_loop.py` | drives the artefact's own control path through a simulated draw, against the plant bridge |
| `tools/provision.py` | fetches the emulator and the register description, each pinned by digest |
| `tools/run_emulation_check.py` | builds the target, renders the two templates, runs the channel-addressing check, gathers findings |
| `tools/run_closed_loop_check.py` | the same, for the closed-loop check, plus building the plant model's shared library |
| `tools/build_plant_library.py` | compiles the plant model — `src/plant/common` and the thermoblock structure `env:stm32` links — to a host-native shared library the bridge calls through ctypes |
| `tools/register_map.py` | reads the models' own register offsets, and the part's, so the two can be compared |
| `tools/pins.json` | the exact bytes of everything fetched |
| `tests/test_emulation_check.py` | what the channel-addressing findings have to say before they count as evidence |
| `tests/test_closed_loop.py` | what the closed-loop findings have to say before they count as evidence |

The models observe and record; the exercise observes and reports; only the suite
judges. Keeping those apart is deliberate — a component that both produces
evidence and decides whether it is good enough can stop producing the awkward
parts without anybody noticing.

## Why nothing here is committed except source

Two things the tier needs are fetched rather than carried, and `.tooling/` is
ignored by git:

**The emulator.** Renode, which `DEC-EMULATION-TIER-RENODE` commits this tier to.
MIT licensed, free, and distributed as a per-platform portable build of a couple
of hundred megabytes. Pinned by SHA-256 per platform in `tools/pins.json`, so a
fetch that produces different bytes fails at the fetch rather than showing up
later as a difference in a result.

**The register description.** ST's CMSIS-SVD file for the STM32F407,
redistributed by the cmsis-svd project and pinned to a commit and a digest. It
is fetched rather than committed because ST licenses it under its own end-user
terms — free of charge, but not the MIT terms this repository is under, and
requiring every copy to carry ST's notice. `provision.py` fetches that notice
alongside the file and puts it in the same directory. Carrying the file in the
tree would mean this repository redistributing it under terms it does not hold;
fetching it by digest gives the same reproducibility without that.

## The two windows in the models that are not the part's

Each model answers a few addresses the real part does not use, and only the host
side of the emulator ever touches them — never the firmware:

- **ADC1 `+0x3F0`…** the conversion result to hand back for each converter
  input. Written before the artefact runs, so each channel gets a figure no
  other channel gets and a channel reading the wrong input is caught reporting
  somebody else's number. It is also how a channel is driven into each reading
  status the seam defines: a figure within the converter's scale is a
  trustworthy value, one above it is a sample that came back unusable, which the
  seam answers as a failure. Absence needs no driving — it is the channel this
  board wires no input to.
- **ADC1 `+0x3E0`…** how many conversions each input has completed. A channel
  that sampled nothing is otherwise indistinguishable from one that sampled and
  got zero.
- **TIM3 `+0x100`…** how many writes have reached each compare register. A
  channel written the value it already held is otherwise indistinguishable from
  one that was never written — which is exactly what a mis-addressed channel
  looks like.

The suite checks against the vendor's description that none of these windows
covers a register the part actually declares, so a model can never shadow real
hardware.

## The closed loop

`closed_loop.py` calls the artefact's own `control_init`, `control_command_temperature`
and `control_step` directly by symbol, entering the compiled image exactly as
`exercise.py` enters `hw_sensor_read` and `hw_output_set` — the artefact is
executed, not interpreted, and every call reaches a symbol the target build
produced. `control_command_temperature` is unreached from `main()`'s own call
graph — nothing on the machine has been asked for a delivery yet — so
`tools/pio_retain_closed_loop_entry.py` keeps it in the linked artefact for
this one caller from outside it.

Each control interval, `tim3.py` reports a compare-register write to
`plant_bridge.py`, which steps the plant model — `src/plant/common` and the
thermoblock structure, called through `ctypes` against the shared library
`tools/build_plant_library.py` compiles, not re-derived in Python — and
refreshes the converter counts `adc1.py` reads back. Simulated time between
steps is advanced by writing the HAL's own millisecond counter directly rather
than by free-running the core for the interval, which is also possible but
costs minutes rather than seconds for a run this tier's gate can afford.

Both harnesses are opt-in on the same two environment variables: the
channel-addressing run configures neither, so `tim3.py` and `adc1.py` are the
same pure register models on that run they always were.

## What this tier does not answer

Whether the emulated peripherals behave in time as the real parts would is a
different question, carried by a different criterion — nothing here claims it.
The closed-loop run advances simulated time by writing the tick counter
directly rather than by executing real cycles, so nothing about the closed
loop's timing, either, claims anything about a real microcontroller's
electrical behaviour. The models answer which input was selected and which
register was written; they say nothing about how long a conversion takes or
what a converter would really have read.
