# What the emulator is told to do with the artefact once it has loaded it.
#
# It runs inside Renode's own interpreter, so it can reach the emulated core's
# registers and the peripheral models' state directly. Every line it prints
# beginning "EMU " is a finding; the runner outside reads them and is the thing
# that decides whether they are the right findings. Nothing is asserted here --
# an observer that also judges can quietly stop observing the awkward cases.
#
# The artefact is executed, not interpreted. The core is brought from reset
# through the image's own startup code, and every call below enters the compiled
# artefact at a symbol the target build produced, with the arguments in the
# registers the procedure call standard puts them in, and returns to an address
# in core-coupled memory that the artefact never branches to of its own accord.
# Reaching a channel therefore means the artefact's own instructions reached it.

from Antmicro.Renode.Peripherals.CPU import RegisterValue

machine = monitor.Machine
bus = machine.SystemBus
cpu = machine["sysbus.cpu"]

# Core-coupled memory, which this firmware's linker script leaves empty. The
# trap is where a called function is told to return to; the scratch is where a
# function returning a structure is told to put it.
CALL_TRAP = 0x10000100
CALL_SCRATCH = 0x10000200

# The window of flash whose loaded contents are reported back, so that what ran
# can be compared against the artefact on disk rather than taken on trust.
IMAGE_BASE = 0x08000000
IMAGE_LENGTH = 0x20000

ADC1_BASE = 0x40012000
ADC1_INJECT = ADC1_BASE + 0x3F0
ADC1_CONVERSIONS = ADC1_BASE + 0x3E0

TIM3_BASE = 0x40000400
TIM3_CCR1 = TIM3_BASE + 0x34
TIM3_WRITES = TIM3_BASE + 0x100

# How many channels of each kind the seam declares. This script runs inside the
# emulator's own interpreter and cannot read the headers, so the numbers are
# written here -- and the suite outside asserts them against the enumerations in
# hw_interface.h and machine_actuation.h, so a channel added to either without a
# line here is a failure rather than a channel the run quietly skips.
SENSOR_CHANNEL_COUNT = 5
OUTPUT_CHANNEL_COUNT = 4
CONVERTER_INPUTS = 4

# The channel driven into reporting a failed sample, and the conversion result
# its input is put into to do it. Sensor channel n is read through converter
# input n, so the one number selects both.
#
# A count above the converter's own full scale is a sample that came back and
# cannot be trusted, which is the seam's failed reading rather than its absent
# one -- an input is fitted and did answer; the answer is unusable. It is the
# failure this model can produce: a conversion that never completes would be the
# other, but the seam waits for one against a clock this firmware never advances
# under emulation, so a model withholding completion would hang the run rather
# than be reported by it.
FAILING_SENSOR_CHANNEL = 0
UNUSABLE_COUNTS = 4096

# One step budget for every call. It is far above what any of these functions
# takes and is here so that a call that never returns is reported as such
# rather than hanging the run.
STEP_BUDGET = 2000000


def fnv1a64(data):
    digest = 0xCBF29CE484222325
    for byte in data:
        digest = ((digest ^ (byte & 0xFF)) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return digest


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


def read_sensor(channel):
    """The status and figure the seam reports for one channel."""
    bus.WriteDoubleWord(CALL_SCRATCH, 0)
    bus.WriteDoubleWord(CALL_SCRATCH + 4, 0)
    call("hw_sensor_read", [CALL_SCRATCH, channel])
    status = bus.ReadDoubleWord(CALL_SCRATCH)
    value = bus.ReadDoubleWord(CALL_SCRATCH + 4)
    if value >= 0x80000000:
        value -= 0x100000000
    return status, value


def compare_values():
    return [bus.ReadDoubleWord(TIM3_CCR1 + 4 * i) for i in range(OUTPUT_CHANNEL_COUNT)]


def compare_writes():
    return [bus.ReadDoubleWord(TIM3_WRITES + 4 * i) for i in range(OUTPUT_CHANNEL_COUNT)]


def report_outputs(label, level, accepted):
    print("EMU output %s %d %d %s %s" % (
        label, level, accepted,
        ",".join([str(v) for v in compare_values()]),
        ",".join([str(v) for v in compare_writes()])))


# The image as the emulator holds it, before a single instruction has run.
print("EMU image %d %d %d" % (
    IMAGE_BASE, IMAGE_LENGTH, fnv1a64(bus.ReadBytes(IMAGE_BASE, IMAGE_LENGTH))))

# The conversion result each converter input hands back. Distinct, so that a
# channel reading the wrong input reports another channel's figure rather than
# the same figure by coincidence.
INJECTED = [1234, 2345, 3456, 500]
for index in range(CONVERTER_INPUTS):
    bus.WriteDoubleWord(ADC1_INJECT + 4 * index, INJECTED[index])
    print("EMU injected %d %d" % (index, INJECTED[index]))

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
report_outputs("after-init", 0, 1)

# Every sensor channel the seam declares, including the one this board wires no
# converter input to, and one past the end of the set.
for channel in range(SENSOR_CHANNEL_COUNT + 1):
    status, value = read_sensor(channel)
    print("EMU sensor %d %d %d" % (channel, status, value))

for index in range(CONVERTER_INPUTS):
    print("EMU conversions %d %d" % (index, bus.ReadDoubleWord(ADC1_CONVERSIONS + 4 * index)))

# The third reading status: a channel that is fitted, was sampled, and whose
# sample cannot be trusted. One input is put into handing back a count outside
# the converter's scale, and the channel behind it is read again. It happens
# after the counts above are reported so that the extra conversion it starts is
# not mistaken for a channel sampled twice, and the input is put back afterwards
# -- read once more, so that the failure is shown to have been this model's
# doing rather than something broken about the channel.
bus.WriteDoubleWord(ADC1_INJECT + 4 * FAILING_SENSOR_CHANNEL, UNUSABLE_COUNTS)
status, value = read_sensor(FAILING_SENSOR_CHANNEL)
print("EMU failed %d %d %d" % (FAILING_SENSOR_CHANNEL, status, value))
bus.WriteDoubleWord(ADC1_INJECT + 4 * FAILING_SENSOR_CHANNEL, INJECTED[FAILING_SENSOR_CHANNEL])
status, value = read_sensor(FAILING_SENSOR_CHANNEL)
print("EMU restored %d %d %d" % (FAILING_SENSOR_CHANNEL, status, value))

# Every output channel the seam declares, one at a time, each at a level no
# other channel is given, with the whole modelled compare state reported after
# each command.
LEVELS = [137, 429, 651, 908]
for channel in range(OUTPUT_CHANNEL_COUNT):
    accepted = call("hw_output_set", [channel, LEVELS[channel]])
    report_outputs(str(channel), LEVELS[channel], accepted)

# A channel past the end of the set, and a level past full scale. Both are
# refusals the seam promises, and a refusal that moved an output would be a
# command reaching a channel nobody addressed.
print("EMU refusal channel %d" % call("hw_output_set", [OUTPUT_CHANNEL_COUNT, 500]))
report_outputs("after-refused-channel", 500, 0)
print("EMU refusal level %d" % call("hw_output_set", [0, 1001]))
report_outputs("after-refused-level", 1001, 0)

# SOL-STM32-INTERRUPT-VECTORS-DEFINED. Whether SysTick_Handler calls
# HAL_IncTick, read directly rather than inferred from some other HAL
# timeout's behaviour: the modelled ADC completes every conversion it is
# asked for, so hw_sensor_read's own poll never actually waits on the tick,
# and a check that leaned on it would not be evidence about SysTick at all.
TICK_STEP_BUDGET = 5000000

tick_before = call("HAL_GetTick", [])
taken = 0
while call("HAL_GetTick", []) == tick_before and taken < TICK_STEP_BUDGET:
    cpu.Step(1)
    taken += 1
tick_after = call("HAL_GetTick", [])
print("EMU tick %d %d %d" % (tick_before, tick_after, taken))

# Every vector this build does not otherwise give a purposeful handler is
# wired to a shared trap that records itself before halting, rather than left
# on the vendor startup file's silent Default_Handler. WWDG's is exercised
# here because nothing in this seam ever enables or services it, so pending it
# through the NVIC directly is a command reaching a vector by no route this
# firmware would ever take on its own.
NVIC_BASE = 0xE000E000
NVIC_ISER0 = NVIC_BASE + 0x100
NVIC_ISPR0 = NVIC_BASE + 0x200
WWDG_IRQ_NUMBER = 0
FAULT_STEP_BUDGET = 2000000

marker_address = bus.GetSymbolAddress("hw_stm32_unhandled_vector_marker")
print("EMU fault-marker-before %d" % bus.ReadDoubleWord(marker_address))

bus.WriteDoubleWord(NVIC_ISER0, 1 << WWDG_IRQ_NUMBER)
bus.WriteDoubleWord(NVIC_ISPR0, 1 << WWDG_IRQ_NUMBER)
taken = 0
while bus.ReadDoubleWord(marker_address) == 0 and taken < FAULT_STEP_BUDGET:
    cpu.Step(1)
    taken += 1
print("EMU fault-marker-after %d %d" % (bus.ReadDoubleWord(marker_address), taken))

# The vendor's own silent default -- the loop every vector fell into before
# this solution -- is linked as a strong symbol and cannot be shadowed by
# redefining its name; it can only be left unreferenced by overriding every
# alias that pointed at it. If any vector still pointed there, the linker
# would keep the symbol live. Its absence from the linked image is therefore
# evidence about every vector at once, not just the one exercised above.
try:
    bus.GetSymbolAddress("Default_Handler")
    default_handler_present = 1
except Exception:
    default_handler_present = 0
print("EMU default-handler-present %d" % default_handler_present)

print("EMU done")
