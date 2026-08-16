# Firmware

The control logic and the hardware seam that separates it from the target.

## Why the seam exists

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

## Layout

| Path | What it holds |
| --- | --- |
| `include/hw_interface.h` | The seam. Free functions, no vendor type, compiles freestanding. |
| `src/control/` | The control logic. Reaches hardware only through the seam. Identical in both builds. |
| `src/hw/sim/` | The simulated implementation, and the controls tests use to stand readings up. |
| `src/hw/stm32/` | The STM32 HAL-backed implementation. Naming vendor symbols is its job. |
| `src/app/native/` | Host entry point: drives the control path, including its error paths, and exits. |
| `src/app/stm32/` | Target entry point: brings the peripherals up, then runs the same control path. |
| `test/test_control/` | The control logic exercised against the simulated implementation. |
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
task fw:verify     # build both environments, run every check, run the tests, run the host build
task fw:build      # both environments only
task fw:check      # the build-time checks only
task fw:test       # the control-logic tests and the tests covering the checks
```

Set `PIO=/path/to/pio` if PlatformIO lives somewhere other than
`~/.platformio/penv/bin/pio`.

## What the checks enforce

Each is a standalone script, so the same check runs from the build and from the
task runner. Two of them also run automatically inside every `pio run`.

| Check | What it fails on |
| --- | --- |
| `check_header_neutral.py` | The seam header names a vendor symbol, or does not compile standalone against a freestanding compiler with no vendor include path. Runs inside every build. |
| `check_encapsulation.py` | A file under `src/control` reaches a HAL function, a CMSIS symbol, a peripheral instance, a device header, an include the check cannot resolve, a peripheral address, or assembly. Runs inside every build. |
| `check_sanitizers.py` | The host build links the sanitizer runtime while the control logic is not actually compiled under it — a failure that otherwise passes silently. |
| `check_direct_calls.py` | A seam call in the linked executable is indirect, or a seam operation the control logic references is reached by no direct call at all. |
| `check_control_identical.py` | A control translation unit does not preprocess identically in both environments — which is how an environment-defined macro reaching the control logic is caught. |

Each check fails rather than passes when it cannot find what it is meant to
inspect. A check that inspects nothing must not report success. The
encapsulation check applies the same rule to file kinds: it inspects every file
under `src/control` except a listed set it knows a build never compiles, so a
C++ or assembly source dropped into a directory the build filter takes
wholesale cannot walk past it.

## The nominated STM32 family

The target environment names an STM32F4 board so that the control logic can be
preprocessed and compiled against a real cross toolchain before any controller
is chosen. That nomination is not the machine's controller selection, which is
answered later against measured parameters. Changing it touches
`src/hw/stm32/` and `platformio.ini` and nothing else — which is the seam's own
property, and the reason the nomination is cheap.
