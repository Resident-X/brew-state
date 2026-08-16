# Firmware

The control logic, the hardware seam that separates it from the target, and the
plant-model seam that separates the equations of the machine from everything
that uses them.

## Why the hardware seam exists

The control logic has to be exercised before any hardware exists, and the
analysis that catches memory errors and undefined behaviour runs on a host
rather than on a microcontroller. Both need the control logic to build and run
with the target absent. So every peripheral operation the control logic uses is
declared once, in vendor-neutral terms, in `include/hw_interface.h`, and two
implementations satisfy it: a simulated one for the host and an STM32 HAL-backed
one for the target.

Which implementation a build gets follows from which environment is built. It is
not a run-time choice, and no source file under `src/control` differs between the
two builds. That is what keeps an indirect call out of the control path.

## Why the plant-model seam exists

Two machines of the same architecture differ only in their numbers. Two machines
of different architectures differ in their equations, and no set of numbers
bridges that. So the split is drawn there: parameters are data the machine
carries, and structure is code behind a named interface. Adopting a machine of
the same architecture is then measurement work rather than development work, and
supporting a different architecture is implementing `include/plant_model.h`
rather than negotiating with everything that consumes the model.

Which structure a build gets follows from which directory under `src/plant/` it
compiles and puts on the include path — again a build-time fact, decided by
`DEC-MODEL-STRUCTURE-AT-BUILD-TIME` rather than by anything read while the
software runs. A build compiling the plant model must name exactly one; naming
none or naming two stops the build rather than letting a default or the linker
choose. Controlling a machine with another architecture's dynamics has no
obvious symptom until the machine is well outside where it should be, so it is
made unreachable rather than merely unlikely.

The `fixture` structure describes no machine. It exists because the checks that
keep one structure out of another's artefact, and that refuse a two-structure
build, both pass unconditionally with only one structure in the tree — and a
check that cannot fail is not a check.

Whether the `thermoblock` structure's equations describe any real machine is a
question that needs a real machine. What is established here is that the numbers
are replaceable, the equations are replaceable, and neither is reachable except
through the seam.

## Layout

| Path | What it holds |
| --- | --- |
| `include/hw_interface.h` | The hardware seam. Free functions, no vendor type, compiles freestanding. |
| `include/plant_model.h` | The plant-model seam. Free functions, no structure named, no equation. |
| `include/plant_types.h` | The vocabulary the plant seam is expressed in: quantities, actuation, parameter faults. |
| `src/control/` | The control logic. Reaches hardware only through the seam. Identical in both builds. |
| `src/hw/sim/` | The simulated implementation, and the controls tests use to stand readings up. |
| `src/hw/stm32/` | The STM32 HAL-backed implementation. Naming vendor symbols is its job. |
| `src/plant/common/` | Reads a parameter record from a description. One parser, every structure. Not a structure itself. |
| `src/plant/thermoblock/` | The machine-describing structure: two heated masses, pump-driven brew pressure, steam pressure above saturation. |
| `src/plant/fixture/` | A structure that models nothing, so the exclusivity and two-structure checks have a second subject. |
| `params/` | Parameter descriptions. Read at run time; the build compiles none of them in. |
| `src/app/native/` | Host entry point: drives the control path and the model, including their error paths, and exits. |
| `src/app/stm32/` | Target entry point: brings the peripherals up, then runs the same control path. |
| `test/test_control/` | The control logic exercised against the simulated implementation. |
| `test/test_plant/` | The plant model exercised through the seam, naming no structure symbol. |
| `tools/` | The checks that make the seam's properties build failures rather than review notes. |

The control logic behind the seam is a minimal path that reads a sensor,
consults the clock and drives an output. What this establishes is separability,
not control performance — the control law, the state estimator and the plant
model are separate units of work.

## Building

PlatformIO is the build system. It installs into its own virtual environment
rather than onto `PATH`:

```sh
curl -fsSL -o get-platformio.py \
  https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py
python3 get-platformio.py
```

The host environment needs only a system C compiler. The target environment
downloads the ARM GCC toolchain and the STM32Cube framework on its first build;
after that both build offline.

Everything runs from the repository root through the task runner:

```sh
task fw:verify     # build every environment, run every check, run the tests, run the host builds
task fw:build      # the environments only
task fw:check      # the build-time checks only
task fw:test       # the control-logic and plant-model tests, and the tests covering the checks
```

Set `PIO=/path/to/pio` if PlatformIO lives somewhere other than
`~/.platformio/penv/bin/pio`.

## What the checks enforce

Each is a standalone script, so the same check runs from the build and from the
task runner. Five of them also run automatically inside every `pio run`.

| Check | What it fails on |
| --- | --- |
| `check_header_neutral.py` | The seam header names a vendor symbol, or does not compile standalone against a freestanding compiler with no vendor include path. Runs inside every build. |
| `check_encapsulation.py` | A file under `src/control` reaches a HAL function, a CMSIS symbol, a peripheral instance, a device header, an include the check cannot resolve, a peripheral address, or assembly. Runs inside every build. |
| `check_sanitizers.py` | A source of this project's own reaches the host artefact without the sanitizers or without the strict warning settings, or the executable links no sanitizer runtime — failures that otherwise pass silently. |
| `check_direct_calls.py` | A seam call in the linked executable is indirect, or a seam operation the control logic references is reached by no direct call at all. |
| `check_control_identical.py` | A control translation unit does not preprocess identically in both environments — which is how an environment-defined macro reaching the control logic is caught. |
| `check_plant_header.py` | A seam header names a structure, reaches into a structure's record, carries a function definition, or fails to compile standalone against *every* structure in turn. Run over `plant_model.h`, and over `plant_types.h` under `--vocabulary-only`, which drops only the requirement to declare an operation. Inspecting one and not the other would let the uninspected one clear itself. Runs inside every build. |
| `check_plant_encapsulation.py` | Anything outside `src/plant/` includes a structure's own header or names a field or function a structure owns. Runs inside every build. |
| `check_structure_selection.py` | A build that compiles the plant model names no structure, or names more than one. Runs inside every build, before anything is compiled. |
| `check_structure_exclusive.py` | A linked artefact is missing the structure it was built for, or carries a symbol belonging to another one. |
| `check_selection_refused.py` | A deliberately misconfigured environment — naming no structure, or naming two — builds anyway, or leaves an artefact behind. |
| `check_parameters_are_data.py` | One unchanged artefact run against two descriptions differing in a single coefficient produces the same trajectory twice, which is what a compiled-in coefficient does. |

Each check fails rather than passes when it cannot find what it is meant to
inspect. A check that inspects nothing must not report success. The
encapsulation checks apply the same rule to file kinds: they inspect every file
under their subject except a listed set they know a build never compiles, so a
C++ or assembly source dropped into a directory the build filter takes
wholesale cannot walk past them.

The plant checks carry that further, because several of them can only fail if
there is something to fail against. `check_plant_header.py` refuses a tree with
fewer than two structures, since compiling against one cannot distinguish a
neutral header from one written for that structure.
`check_structure_exclusive.py` refuses a tree with fewer than two, and refuses
one where two structures declare the same names — in either case there is
nothing to exclude, and it would pass whatever the artefact contained.
`check_structure_selection.py` treats a source filter it could not resolve as an
error rather than as "this build compiles no plant source".

What a structure owns is read out of the structures themselves rather than
listed in the tools: `structure_symbols.py` derives each structure's fields and
declarations from its own header, so a structure that gains a coefficient does
not need a check to be updated to keep covering it.

## The nominated STM32 family

The target environment names an STM32F4 board so that the control logic can be
preprocessed and compiled against a real cross toolchain before any controller
is chosen. That nomination is not the machine's controller selection, which is
answered later against measured parameters. Changing it touches
`src/hw/stm32/` and `platformio.ini` and nothing else — which is the seam's own
property, and the reason the nomination is cheap.
