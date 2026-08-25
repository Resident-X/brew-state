# Peripheral model for ADC1, the converter the STM32 hardware-seam
# implementation samples every sensor channel through.
#
# It is a register model, not a re-expression of the seam: it answers the
# memory-mapped accesses the compiled firmware really makes -- the ones the
# vendor library issues on its behalf -- and knows nothing about the seam's
# vocabulary. What makes it a model of four channels rather than of one is that
# the value it returns from the data register is selected by the regular-sequence
# register the firmware wrote first. A model returning one figure whatever was
# selected would let a firmware that addressed the wrong converter input pass.
#
# Register offsets are the STM32F4 ADC map: the vendored SVD is applied to the
# same window so that every access below is named in the emulator's log by the
# register it lands on, and a write drifting onto a neighbouring register shows
# up as such rather than as a number.
#
# Two windows here are not the part's. They are addressed only from the host
# side of the emulator and never by the firmware, which is what keeps them from
# being a peripheral the firmware could accidentally depend on:
#
#   0x3F0 + 4*n   the conversion result to hand back when converter input n is
#                 selected. The harness writes these before the firmware runs.
#   0x3E0 + 4*n   how many conversions have been completed on input n. Read by
#                 the harness afterwards, so that a channel nothing sampled is
#                 distinguishable from one that sampled and returned zero.
#
# The first of them is also how a channel is driven into reporting a failed
# reading rather than an absent or a trustworthy one: a count written there
# above the converter's own full scale is a sample that came back unusable, and
# the seam answers it as a failure. Nothing else this model can do produces that
# status -- a conversion left never completing would be the part's other way of
# failing, but the seam waits for one against a clock this firmware never
# advances under emulation, so a model that withheld completion would hang the
# run instead of being reported by it.

SR = 0x00
CR1 = 0x04
CR2 = 0x08
SQR3 = 0x34
DR = 0x4C

SR_EOC = 1 << 1
SR_STRT = 1 << 4
CR2_ADON = 1 << 0
CR2_SWSTART = 1 << 30

INJECT_BASE = 0x3F0
COUNT_BASE = 0x3E0
PORT_INPUTS = 4

if request.IsInit:
    registers = {}
    injected = [0] * PORT_INPUTS
    conversions = [0] * PORT_INPUTS
    selected = 0

elif request.IsWrite:
    offset = request.Offset
    if INJECT_BASE <= offset < INJECT_BASE + 4 * PORT_INPUTS:
        injected[(offset - INJECT_BASE) // 4] = request.Value
    elif COUNT_BASE <= offset < COUNT_BASE + 4 * PORT_INPUTS:
        conversions[(offset - COUNT_BASE) // 4] = request.Value
    else:
        registers[offset] = request.Value
        if offset == SQR3:
            # SQ1 is the first conversion in the regular sequence, and the
            # sequence this firmware configures is one conversion long.
            selected = request.Value & 0x1F
        elif offset == CR2:
            if (request.Value & CR2_ADON) and (request.Value & CR2_SWSTART):
                # A software-triggered conversion on a one-deep sequence
                # completes at once: this model says nothing about how long a
                # conversion takes, only which input it read.
                registers[SR] = registers.get(SR, 0) | SR_EOC | SR_STRT
                if selected < PORT_INPUTS:
                    conversions[selected] = conversions[selected] + 1
            # The start bit is cleared by the part once the conversion has
            # begun. Leaving it standing would make the next read-modify-write
            # of this register -- switching the converter on for the following
            # channel -- start a second conversion nobody asked for, and a
            # conversion nobody asked for is indistinguishable from a channel
            # sampled twice.
            registers[CR2] = request.Value & ~CR2_SWSTART

elif request.IsRead:
    offset = request.Offset
    if INJECT_BASE <= offset < INJECT_BASE + 4 * PORT_INPUTS:
        request.Value = injected[(offset - INJECT_BASE) // 4]
    elif COUNT_BASE <= offset < COUNT_BASE + 4 * PORT_INPUTS:
        request.Value = conversions[(offset - COUNT_BASE) // 4]
    elif offset == DR:
        # Reading the data register is what clears the end-of-conversion flag on
        # the part, so it is what clears it here. An input outside the four this
        # board wires reads as nothing rather than as another input's figure.
        registers[SR] = registers.get(SR, 0) & ~SR_EOC
        request.Value = injected[selected] if selected < PORT_INPUTS else 0
    else:
        request.Value = registers.get(offset, 0)
