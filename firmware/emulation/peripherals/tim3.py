# Peripheral model for TIM3, the timer whose compare channels the STM32
# hardware-seam implementation drives every output channel through.
#
# One modelled state per compare channel, and each is moved only by a write to
# its own compare register. That separation is the whole point of modelling the
# timer at register level rather than recording what the seam was asked for: a
# seam that sends two channels to the same compare register, or one channel to
# no register at all, is invisible from above the seam and unmistakable from
# here.
#
# Alongside the value, each channel carries a count of the writes that reached
# it. A count distinguishes a channel that was never written from one that was
# written the value it already held, which a value on its own cannot -- and the
# second of those is exactly what a mis-addressed channel looks like.
#
# Register offsets are the STM32F4 general-purpose timer map; the vendored SVD
# is applied over the same window so every access is named in the emulator's log
# by the register it lands on.
#
# The two windows below are not the part's. They are addressed only from the
# host side of the emulator, never by the firmware:
#
#   0x100 + 4*n   how many writes have reached compare register n+1.
#
# The compare registers themselves are read back through their own offsets,
# which are the part's, so the modelled level of a channel is read where the
# firmware wrote it.

CCR1 = 0x34
COUNT_BASE = 0x100
COMPARE_CHANNELS = 4

if request.IsInit:
    registers = {}
    writes = [0] * COMPARE_CHANNELS

elif request.IsWrite:
    offset = request.Offset
    if COUNT_BASE <= offset < COUNT_BASE + 4 * COMPARE_CHANNELS:
        writes[(offset - COUNT_BASE) // 4] = request.Value
    else:
        registers[offset] = request.Value
        if CCR1 <= offset < CCR1 + 4 * COMPARE_CHANNELS and (offset - CCR1) % 4 == 0:
            index = (offset - CCR1) // 4
            writes[index] = writes[index] + 1

elif request.IsRead:
    offset = request.Offset
    if COUNT_BASE <= offset < COUNT_BASE + 4 * COMPARE_CHANNELS:
        request.Value = writes[(offset - COUNT_BASE) // 4]
    else:
        request.Value = registers.get(offset, 0)
