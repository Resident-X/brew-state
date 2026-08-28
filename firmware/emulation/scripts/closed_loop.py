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
# yet -- so control_command_temperature and control_command_flow are both
# unreached from main()'s own call graph and the linker would ordinarily discard
# them. tools/pio_retain_closed_loop_entry.py keeps them in the artefact for
# exactly this script to call from outside.
#
# Both are commanded here, because a draw is both. A temperature alone leaves
# the pump off, which leaves the brew path's pressure where it came up and
# leaves the water on its way to the group reaching the block by conduction
# alone -- and over a draw short enough to emulate, that leaves the control law
# holding the heater at its limit on every single interval. A loop at its limit
# throughout is one whose converter reading makes no difference to what it
# commands next, so a comparison drawn across such a run is a comparison of two
# open loops however exactly the two agree.
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
# What the same description says its own coefficients may be wrong by. The
# control path is brought up against both records, because the margin it holds
# a commanded target to is sized from what the description admits it may be
# wrong by -- so a harness handing it the coefficients alone is one the loop
# refuses to come up at all, and every step of the draw after it would be a
# latched fault rather than a loop.
#
# Placed past the state region rather than in among the records above it,
# because control_state_t carries both of them by value and is far the largest
# thing this harness writes into core-coupled memory. A slot of its own keeps
# these a list of disjoint 4 KiB regions, which is what makes a collision
# between two of them impossible to introduce by accident.
BUDGET_SCRATCH = 0x10006000

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

# The draw is a shape and not a held level: nothing drawn while the block comes
# up, a ramp onto the puck, a hold, a taper off, and then the machine standing
# with the shot finished. The five phases add to DRAW_STEPS, which a check in
# tests/test_cross_tier.py holds them to -- a course shorter or longer than the
# draw would leave intervals commanding something nobody wrote down.
#
# It is stated as levels the pump is driven at rather than as a rate in
# millilitres per second, because a level is what the control path's flow entry
# point takes and what the heater's own feedforward reads in the same step. A
# course stated as a rate would be turned into a level by dividing by what full
# pump scale draws on this machine, which is probed at bring-up -- so the two
# loops being compared would each be commanding the result of their own probe
# rather than the same figure.
PRE_INFUSION_STEPS = 40
RAMP_STEPS = 30
HOLD_STEPS = 120
TAPER_STEPS = 30
REST_STEPS = 80

# What the hold is drawn at, in permille of full pump scale. Well onto the pump
# rather than a trickle, because what the brew path's pressure relation has to
# be asked is where it settles as well as that it moves, and the settling point
# is proportional to the level.
PEAK_PUMP_PERMILLE = 600

# The temperature the draw asks for, in degrees Celsius.
#
# Below a brew temperature, and deliberately. A cold thermoblock reaches the
# neighbourhood of a brew temperature in something over a minute of simulated
# time, and a minute of this loop is many thousands of intervals single-stepped
# through the core -- so a draw commanding one would spend the whole of any
# affordable run at full heater duty, where the loop is holding the element at
# its limit rather than controlling, and where what the converter reported makes
# no difference to what is commanded next. What this run has to be is a loop
# that is actually closing; what it is not is a claim about a drinkable shot.
TARGET_BREW_C = 50.0

# Nine significant digits, which is what round-trips an IEEE-754 single
# precision value exactly. The quantities are single precision on both sides of
# any comparison drawn against this run, so a narrower format would be the
# printing introducing a disagreement rather than reporting one.
QUANTITY_FORMAT = "%.9g"


def to_bits(value):
    """A Python float's IEEE-754 bit pattern, as an unsigned 32-bit int.

    The target build carries no Tag_ABI_VFP_args attribute -- confirmed by
    reading the linked artefact -- so a float argument crosses the AAPCS
    boundary as this bit pattern in an ordinary core register, on the same
    terms every other argument call() passes does.
    """
    return struct.unpack("<I", struct.pack("<f", value))[0]


# How many arguments AAPCS puts in core registers before the rest go on the
# stack. It is four, and it is written down here rather than left implicit
# because getting it wrong is silent: a fifth argument written into r4 is a
# register the callee is entitled to use for anything it likes, so the callee
# reads whatever its own prologue left there and refuses -- with no fault, no
# unmapped access and nothing in the log to say an argument never arrived.
ARGUMENTS_IN_REGISTERS = 4

# The alignment AAPCS requires of the stack pointer at a public interface, in
# bytes. Eight, so a stacked argument list is padded up to it rather than
# leaving the callee's own doubleword accesses misaligned.
STACK_ALIGNMENT = 8


def call(name, args):
    address = bus.GetSymbolAddress(name)
    for index in range(min(len(args), ARGUMENTS_IN_REGISTERS)):
        cpu.SetRegister(index, RegisterValue.Create(args[index], 32))

    # Everything past the fourth argument is passed on the stack, in order,
    # starting at the stack pointer as the call is made. The frame is taken
    # below wherever the core currently stands and given back afterwards, so a
    # harness that calls repeatedly does not walk the stack down.
    stacked = args[ARGUMENTS_IN_REGISTERS:]
    entry_sp = cpu.SP.RawValue
    frame_sp = entry_sp
    if stacked:
        span = len(stacked) * 4
        span += (-span) % STACK_ALIGNMENT
        frame_sp = (entry_sp - span) & ~(STACK_ALIGNMENT - 1)
        for index in range(len(stacked)):
            bus.WriteDoubleWord(frame_sp + (index * 4), stacked[index])
        cpu.SP = RegisterValue.Create(frame_sp, 32)

    cpu.LR = RegisterValue.Create(CALL_TRAP | 1, 32)
    cpu.PC = RegisterValue.Create(address, 32)
    taken = 0
    while cpu.PC.RawValue != CALL_TRAP and taken < STEP_BUDGET:
        cpu.Step(1)
        taken += 1
    if stacked:
        cpu.SP = RegisterValue.Create(entry_sp, 32)
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

# The quantities this machine's sensor channels read, in the order the sensor
# seam enumerates the channels that have a converter input behind them, each
# under the name it is reported by. The whole set is reported at every interval
# rather than the brew temperature alone, because a run reporting one quantity
# leaves anything drawn from it saying nothing about the other three.
#
# Named rather than left to be read off by position, because this run reports a
# field the loop it is compared against has nothing to say about -- what its
# clock read -- so a reader counting columns has to know that separately for each
# of the two. The names are the ones the host loop's own draw prints, and a check
# in tests/test_cross_tier.py holds the two lists to each other.
TRAJECTORY_QUANTITIES = (
    ("brew-c", plant_bridge.PLANT_QUANTITY_BREW_TEMPERATURE_C),
    ("steam-c", plant_bridge.PLANT_QUANTITY_STEAM_TEMPERATURE_C),
    ("brew-bar", plant_bridge.PLANT_QUANTITY_BREW_PRESSURE_BAR),
    ("steam-bar", plant_bridge.PLANT_QUANTITY_STEAM_PRESSURE_BAR),
)


def quantities():
    return " ".join(
        ("%s=" + QUANTITY_FORMAT) % (key, bridge.quantity(q))
        for key, q in TRAJECTORY_QUANTITIES)


def pump_permille(step_index):
    """The level the pump is asked for on one interval of the draw.

    The course written out as a function of the interval rather than as a table,
    so that the phases above are the single statement of the shape and the two
    loops are handed the levels this produces rather than each evaluating a
    course of its own.
    """
    at = step_index
    if at < PRE_INFUSION_STEPS:
        return 0
    at -= PRE_INFUSION_STEPS
    if at < RAMP_STEPS:
        return int(round(PEAK_PUMP_PERMILLE * float(at + 1) / RAMP_STEPS))
    at -= RAMP_STEPS
    if at < HOLD_STEPS:
        return PEAK_PUMP_PERMILLE
    at -= HOLD_STEPS
    if at < TAPER_STEPS:
        return int(round(PEAK_PUMP_PERMILLE * (1.0 - float(at + 1) / TAPER_STEPS)))
    return 0


# Taken here, before a single instruction of the artefact has run, so that it is
# the state the model came up in rather than a state something during bring-up
# moved it to.
baseline_quantities = quantities()
print("EMU trajectory-baseline %s" % baseline_quantities)

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

# The same text read a second time for what it says those coefficients may be
# wrong by, exactly as the artefact's own main() reads it. The control path
# below will not come up without it.
budget_ok = call("plant_parameter_budget_load",
                 [description_addr, description_length, BUDGET_SCRATCH, ERROR_SCRATCH])
print("EMU budget-loaded %d" % budget_ok)

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
    "control_init",
    [STATE_SCRATCH, PARAMS_SCRATCH, BUDGET_SCRATCH, LIMITS_SCRATCH, TOLERANCE_SCRATCH])
print("EMU control-init %d" % control_init_ok)

command_ok = call("control_command_temperature", [STATE_SCRATCH, to_bits(TARGET_BREW_C)])
print("EMU command %d" % command_ok)

# What this run asked the machine for, reported rather than left to be read out
# of this file by anything that wants to put the same draw somewhere else. A
# second reader of the figure is a second answer waiting to disagree with this
# one.
print(("EMU target-brew-c " + QUANTITY_FORMAT) % TARGET_BREW_C)

# Everything above this line drove the machine before the draw began: bringing
# the peripherals up switches the timer's compare outputs on, and bringing the
# control path up commands every output off. Both are compare writes, and a
# compare write is an interval's actuation as far as the bridge is concerned --
# so the model has already been advanced by intervals nothing asked for.
#
# The draw starts from the model as it came up, because that is a place another
# tier's copy of the same model can also start from and wherever bring-up
# happened to leave it is not. What the model reads at this moment is reported
# first, unrounded, so that whether bring-up moved it at all is a finding rather
# than an assumption: these figures standing where the baseline stands is what
# says the discarded intervals commanded nothing.
print("EMU pre-draw-quantities %s" % quantities())
print("EMU pre-draw-steps %d" % bridge.restart())

uwtick_address = bus.GetSymbolAddress("uwTick")

results = []
checkpoints = []
trajectory = []
flow_refusals = 0
checkpoint_marks = (DRAW_STEPS // 3, 2 * DRAW_STEPS // 3)
for step_index in range(DRAW_STEPS):
    tick = bus.ReadDoubleWord(uwtick_address)
    bus.WriteDoubleWord(uwtick_address, tick + CONTROL_STEP_INTERVAL_MS)
    # What the counter reads at the instant the step is entered, kept because
    # the interval the estimator is advanced by is the one that actually
    # elapsed rather than the one the loop is meant to run at -- so a run whose
    # cadence drifted is a run whose model was integrated over something else,
    # and that is not readable from the step's own result.
    ran_at = bus.ReadDoubleWord(uwtick_address)
    # The flow the course asks for is commanded before the step and not after
    # it: the heater's feedforward reads the commanded level within the same
    # step, so a level arriving afterwards would be one the heater answered for
    # an interval late.
    asked_for = pump_permille(step_index)
    if not call("control_command_flow", [STATE_SCRATCH, asked_for]):
        flow_refusals += 1
    results.append(call("control_step", [STATE_SCRATCH]))
    # The level the heater was actually driven at over this interval, read off
    # the compare register the seam wrote it to rather than worked out here. It
    # is what says whether the loop was controlling or merely holding the
    # element at its limit, and a run pinned at the limit throughout is one
    # whose converter reading changed nothing it did.
    driven = bridge.actuation_levels[plant_bridge.ACTUATION_CHANNEL_BREW_HEATER]
    trajectory.append((ran_at, asked_for, driven, bridge.step_count, quantities()))
    if step_index in checkpoint_marks:
        checkpoints.append(bridge.quantity(plant_bridge.PLANT_QUANTITY_BREW_TEMPERATURE_C))

for index in range(len(trajectory)):
    ran_at, asked_for, driven, taken, values = trajectory[index]
    print("EMU trajectory interval=%d result=%d clock=%d pump=%d heater=%d steps=%d %s"
          % (index, results[index], ran_at, asked_for, driven, taken, values))

print("EMU flow-refusals %d" % flow_refusals)

print("EMU checkpoints %s" % ",".join("%f" % value for value in checkpoints))
print("EMU draw-steps %d" % len(results))
print("EMU draw-results %s" % ",".join(str(result) for result in results))
print("EMU draw-actuated-count %d" % sum(1 for r in results if r == CONTROL_STEP_ACTUATED))
print("EMU plant-step-count %d" % bridge.step_count)
print("EMU plant-last-step-ok %d" % (1 if bridge.last_step_ok else 0))

final_brew_c = bridge.quantity(plant_bridge.PLANT_QUANTITY_BREW_TEMPERATURE_C)
print("EMU final-brew-c %f" % final_brew_c)

print("EMU done")
