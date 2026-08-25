# Runs the closed loop this solution builds: commands a delivery on the
# target artefact, then drives its own control_step entry point -- the same
# one main()'s infinite loop calls -- across a simulated draw, with TIM3's
# compare writes and ADC1's converter reads answered by the models tim3.py and
# adc1.py wire to plant_bridge.py rather than by fixed figures the harness
# injects. Every line beginning "EMU " is a finding; the runner outside reads
# them and decides whether they are the right ones, on the same terms
# exercise.py's findings are read.
#
# What this asks that exercise.py cannot: exercise.py calls hw_output_set and
# hw_sensor_read directly, one channel at a time, against whatever the harness
# put in the injected window -- it never runs a step of the control law and
# never lets what one channel did affect what another later reads. This script
# runs the artefact's own control_step repeatedly, against a plant model that
# is actually stepped by what control_step commands, and reads back what the
# same model reports afterwards -- the closed loop
# SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT builds, and the reason it is a
# distinct piece of work from SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.
#
# main() never commands a delivery -- nothing on the machine has been asked to
# yet -- so control_command_temperature is unreached from main()'s own call
# graph and the linker would ordinarily discard it. tools/pio_retain_closed_loop_entry.py
# keeps it in the artefact for exactly this script to call from outside.
#
# Advancing simulated time between control_step calls is done by writing the
# HAL's own millisecond counter (uwTick) directly rather than by letting the
# core free-run for the interval: free-running is what exercise.py's own tick
# check does to prove SysTick works at all, but doing that here, thousands of
# times over, costs minutes of wall-clock time for no finding this script
# needs -- it already knows SysTick works. Advancing the counter the interval
# gate itself reads is a direct statement of simulated time passing, on the
# same terms plant_model_step_reporting's own interval_millis argument already
# is: neither this script nor the plant model claims anything about how long a
# real interval would take to run on real silicon.

import struct

from Antmicro.Renode.Peripherals.CPU import RegisterValue

machine = monitor.Machine
bus = machine.SystemBus
cpu = machine["sysbus.cpu"]

# Core-coupled memory, exactly as exercise.py uses it: empty of anything the
# linker placed, so it is free for this harness's own bookkeeping. The traps
# and scratch regions here are a disjoint range from exercise.py's, though the
# two scripts never run against the same core at once.
CALL_TRAP = 0x10000100
PARAMS_SCRATCH = 0x10001000
LIMITS_SCRATCH = 0x10002000
TOLERANCE_SCRATCH = 0x10003000
ERROR_SCRATCH = 0x10004000
STATE_SCRATCH = 0x10005000

# One step budget for every call, as exercise.py's is: far above what any of
# these functions takes, so a call that never returns is reported as such
# rather than hanging the run.
STEP_BUDGET = 2000000

# Thumb `b .` -- branches to itself. Written once into CALL_TRAP so that
# stepping the core while it sits there, which this script does to let a
# handler or a wait loop's own instructions run, cannot walk off core-coupled
# memory's end into an address nothing backs and fault. A call() leaves the
# core parked here, at an address the artefact never branches to on its own.
CALL_TRAP_INSTRUCTION = 0xE7FE

CONTROL_STEP_INTERVAL_MS = 10

# CONTROL_STEP_ACTUATED and CONTROL_STEP_LATE both mean the step drove the
# outputs; CONTROL_STEP_TOO_SOON means the interval gate held it back, which
# this harness's own uwTick advance is sized to avoid but does not guarantee
# against on every single cycle. None of the three is a fault.
CONTROL_STEP_ACTUATED = 0
CONTROL_STEP_TOO_SOON = 1
CONTROL_STEP_LATE = 5
ORDINARY_STEP_RESULTS = (CONTROL_STEP_ACTUATED, CONTROL_STEP_TOO_SOON, CONTROL_STEP_LATE)

# A full simulated draw: three seconds of the control law's own cadence, which
# is long enough for a thermoblock's brew mass to move substantially toward a
# commanded temperature from a cold start without costing minutes of wall
# time to run under Renode's functional core model.
DRAW_STEPS = 300

TARGET_BREW_C = 93.0


def to_bits(value):
    """A Python float's IEEE-754 bit pattern, as an unsigned 32-bit int.

    The target build carries no Tag_ABI_VFP_args attribute -- confirmed by
    reading the linked artefact -- so a float argument crosses the AAPCS
    boundary as this bit pattern in an ordinary core register, on the same
    terms every other argument call() passes does.
    """
    return struct.unpack("<I", struct.pack("<f", value))[0]


def call(name, args):
    address = bus.GetSymbolAddress(name)
    for index in range(len(args)):
        cpu.SetRegister(index, RegisterValue.Create(args[index], 32))
    cpu.LR = RegisterValue.Create(CALL_TRAP | 1, 32)
    cpu.PC = RegisterValue.Create(address, 32)
    taken = 0
    while cpu.PC.RawValue != CALL_TRAP and taken < STEP_BUDGET:
        cpu.Step(1)
        taken += 1
    if cpu.PC.RawValue != CALL_TRAP:
        raise Exception("%s did not return within %d instructions" % (name, STEP_BUDGET))
    return cpu.GetRegister(0).RawValue


def read_symbol_u32(name):
    return bus.ReadDoubleWord(bus.GetSymbolAddress(name))


bus.WriteWord(CALL_TRAP, CALL_TRAP_INSTRUCTION)

# The plant bridge, read directly for the baseline and the final quantity this
# script's own findings report. tim3.py and adc1.py reach the same singleton
# through the identical environment variable and import path; constructing it
# here first only decides which of the three scripts happens to pay for the
# model's own initialisation.
import os
import sys

sys.path.insert(0, os.environ["BREW_STATE_EMULATION_PERIPHERALS_DIR"])
import plant_bridge  # noqa: E402

bridge = plant_bridge.get()
baseline_brew_c = bridge.quantity(plant_bridge.PLANT_QUANTITY_BREW_TEMPERATURE_C)
print("EMU baseline-brew-c %f" % baseline_brew_c)

# The image as the emulator holds it, before a single instruction has run --
# the same check exercise.py opens with, so a run of this script is also
# evidence the artefact it loaded is the one on disk.
IMAGE_BASE = 0x08000000
IMAGE_LENGTH = 0x20000


def fnv1a64(data):
    digest = 0xCBF29CE484222325
    for byte in data:
        digest = ((digest ^ (byte & 0xFF)) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return digest


print("EMU image %d %d %d" % (
    IMAGE_BASE, IMAGE_LENGTH, fnv1a64(bus.ReadBytes(IMAGE_BASE, IMAGE_LENGTH))))

main_address = bus.GetSymbolAddress("main")
machine.Start()
machine.Pause()
startup_steps = 0
while cpu.PC.RawValue != main_address and startup_steps < STEP_BUDGET:
    cpu.Step(1)
    startup_steps += 1
if cpu.PC.RawValue != main_address:
    raise Exception("the artefact's startup code did not reach main")
print("EMU startup %d" % startup_steps)

print("EMU init %d" % call("hw_stm32_init", []))

description_addr = bus.GetSymbolAddress("reference_description")
description_length = read_symbol_u32("reference_description_length")
parameters_ok = call("plant_parameters_load",
                      [description_addr, description_length, PARAMS_SCRATCH, ERROR_SCRATCH])
print("EMU parameters-loaded %d" % parameters_ok)

limits_addr = bus.GetSymbolAddress("reference_limits")
limits_length = read_symbol_u32("reference_limits_length")
limits_ok = call("estimator_limits_load",
                  [limits_addr, limits_length, LIMITS_SCRATCH, ERROR_SCRATCH])
print("EMU limits-loaded %d" % limits_ok)

tolerance_addr = bus.GetSymbolAddress("reference_tolerance")
tolerance_length = read_symbol_u32("reference_tolerance_length")
tolerance_ok = call("delivery_tolerance_load",
                     [tolerance_addr, tolerance_length, TOLERANCE_SCRATCH, ERROR_SCRATCH])
print("EMU tolerance-loaded %d" % tolerance_ok)

control_init_ok = call(
    "control_init", [STATE_SCRATCH, PARAMS_SCRATCH, LIMITS_SCRATCH, TOLERANCE_SCRATCH])
print("EMU control-init %d" % control_init_ok)

command_ok = call("control_command_temperature", [STATE_SCRATCH, to_bits(TARGET_BREW_C)])
print("EMU command %d" % command_ok)

uwtick_address = bus.GetSymbolAddress("uwTick")

results = []
checkpoints = []
checkpoint_marks = (DRAW_STEPS // 3, 2 * DRAW_STEPS // 3)
for step_index in range(DRAW_STEPS):
    tick = bus.ReadDoubleWord(uwtick_address)
    bus.WriteDoubleWord(uwtick_address, tick + CONTROL_STEP_INTERVAL_MS)
    results.append(call("control_step", [STATE_SCRATCH]))
    if step_index in checkpoint_marks:
        checkpoints.append(bridge.quantity(plant_bridge.PLANT_QUANTITY_BREW_TEMPERATURE_C))

print("EMU checkpoints %s" % ",".join("%f" % value for value in checkpoints))
print("EMU draw-steps %d" % len(results))
print("EMU draw-results %s" % ",".join(str(result) for result in results))
print("EMU draw-actuated-count %d" % sum(1 for r in results if r == CONTROL_STEP_ACTUATED))
print("EMU plant-step-count %d" % bridge.step_count)
print("EMU plant-last-step-ok %d" % (1 if bridge.last_step_ok else 0))

final_brew_c = bridge.quantity(plant_bridge.PLANT_QUANTITY_BREW_TEMPERATURE_C)
print("EMU final-brew-c %f" % final_brew_c)

print("EMU done")
