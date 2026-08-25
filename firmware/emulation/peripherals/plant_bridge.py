# The bridge between the two register models and the plant model they are
# supposed to be closing a loop with.
#
# tim3.py and adc1.py are two separate PythonPeripheral scripts, each with its
# own execution namespace, and neither can call the other's -- so what closes
# the loop between them has to live somewhere both reach. This module is that
# somewhere: a plain Python module, not a peripheral itself, imported by name
# from both. Renode loads every PythonPeripheral into the one process, so the
# singleton this module holds is the same object however many peripherals
# import it, which is what lets a TIM3 write reach ADC1's state without either
# script naming the other.
#
# It calls the plant model through firmware/src/plant/common/plant_step.c and
# the thermoblock structure's own plant_structure.c, compiled to a host-native
# shared library by tools/build_plant_library.py -- not a re-expression of the
# equations in Python, per DEC-EMULATION-TIER-RENODE. Every argument that
# crosses into the library is passed by ctypes.byref(): this Renode build's
# ctypes marshals a bare ctypes.pointer() of a Structure or scalar
# inconsistently -- a call taking one has been observed to report success
# while leaving the pointee unwritten, and even to refuse steps outright with
# no admissibility fault set -- while ctypes.byref() has been verified correct
# for every pattern this bridge uses. A c_void_p parameter backed by a
# ctypes.create_string_buffer is passed as that buffer directly: the two
# opaque records (plant_model_t and plant_parameters_t) are never laid out in
# Python, so they are carried as oversized blank buffers the C side alone
# reads and writes, addressed as plain void*.
#
# Configuration arrives through the OS environment rather than being written
# into this file or into the platform description: the runner that launches
# Renode is the one thing that knows where the library and the reference
# description it must agree with the artefact about were built, and an
# environment variable is a channel that reaches a Python peripheral's process
# without templating a path into source the way the platform description
# templates PERIPHERALS.

import ctypes
import os

LIBRARY_ENV = "BREW_STATE_PLANT_LIBRARY"
PARAMETERS_ENV = "BREW_STATE_PLANT_PARAMETERS"

# Parts per thousand of full scale, the machine's own actuation vocabulary.
# machine_actuation.h is the source of truth; these mirror it on the same
# terms tim3.py and adc1.py already mirror the STM32 register map -- a
# vocabulary the check tooling verifies these peripherals against separately.
ACTUATION_CHANNEL_COUNT = 4
ACTUATION_FULL_SCALE = 1000

# plant_quantity_t, from plant_types.h. Only the four this seam's sensor
# channels read are named; the flow and steam-draw quantities have no sensor
# channel behind them and this bridge never reads them.
PLANT_QUANTITY_BREW_TEMPERATURE_C = 0
PLANT_QUANTITY_STEAM_TEMPERATURE_C = 1
PLANT_QUANTITY_BREW_PRESSURE_BAR = 2
PLANT_QUANTITY_STEAM_PRESSURE_BAR = 3

# hw_stm32.c's own converter scaling: a converter count is a quantity of
# SENSOR_FULL_SCALE_MILLI milli-units at ADC_FULL_SCALE_COUNTS counts. Mirrored
# here for the same reason the peripherals mirror the register map -- there is
# nothing to import it from, since it is a fact of the hardware seam's own
# translation unit, not the vocabulary either seam shares.
ADC_FULL_SCALE_COUNTS = 4095
SENSOR_FULL_SCALE_MILLI = 200000

# hw_sensor_channel_t order, and which converter input each reads. Index -1
# marks the channel this board wires no input to (HW_SENSOR_FLOW): the bridge
# never derives a figure for it, on the same terms hw_stm32.c never samples it.
SENSOR_QUANTITY_BY_CONVERTER_INPUT = {
    0: PLANT_QUANTITY_BREW_TEMPERATURE_C,
    1: PLANT_QUANTITY_STEAM_TEMPERATURE_C,
    2: PLANT_QUANTITY_BREW_PRESSURE_BAR,
    3: PLANT_QUANTITY_STEAM_PRESSURE_BAR,
}

# machine_actuation.h's channel order, which output_timer_channel in
# hw_stm32.c maps to TIM3 compare channels 1..4 in the same order. The pump is
# the last channel this build's control law ever writes in one iteration
# (control.c always writes the brew heater before the pump, on every path),
# which is what makes a write landing here the signal that one control
# interval's actuation is now fully written and ready to be stepped.
ACTUATION_CHANNEL_BREW_HEATER = 0
ACTUATION_CHANNEL_PUMP = 2


class PlantActuation(ctypes.Structure):
    _fields_ = [("level_permille", ctypes.c_uint16 * ACTUATION_CHANNEL_COUNT)]


def _quantity_to_counts(value):
    """A plant quantity, in its own physical unit, as a converter count.

    The inverse of hw_stm32.c's own counts-to-milli-units scaling: milli-units
    are the physical value scaled by 1000, and a count is milli-units scaled by
    ADC_FULL_SCALE_COUNTS / SENSOR_FULL_SCALE_MILLI. A value the scale cannot
    represent is clamped rather than wrapped, matching what a converter with a
    pinned rail would report rather than a count that silently aliases back
    into range.
    """
    milli = value * 1000.0
    counts = milli * ADC_FULL_SCALE_COUNTS / SENSOR_FULL_SCALE_MILLI
    if counts < 0:
        return 0
    if counts > ADC_FULL_SCALE_COUNTS:
        return ADC_FULL_SCALE_COUNTS
    return int(counts)


class PlantBridge(object):
    """One plant model instance, stepped from TIM3 writes and read by ADC1."""

    def __init__(self):
        library_path = os.environ[LIBRARY_ENV]
        parameters_path = os.environ[PARAMETERS_ENV]

        self._lib = ctypes.CDLL(library_path)
        self._bind()

        with open(parameters_path, "rb") as handle:
            description = handle.read()

        self._parameters = ctypes.create_string_buffer(16384)
        error = ctypes.create_string_buffer(2048)
        if not self._lib.plant_parameters_load(
                description, len(description), self._parameters, error):
            raise RuntimeError(
                "plant_bridge: the reference description at %s was refused" % parameters_path)

        self._model = ctypes.create_string_buffer(16384)
        if not self._lib.plant_model_init(self._model, self._parameters):
            raise RuntimeError("plant_bridge: the plant model could not be initialised")

        # Every TIM3 compare register's held level, in machine_actuation.h
        # order. Answers with zero for a channel this structure does not
        # answer, and zero is always admissible -- plant_step_admissible
        # refuses only a non-zero command on an unanswered channel.
        self.actuation_levels = [0] * ACTUATION_CHANNEL_COUNT

        # Converter counts for each converter input, refreshed on every step
        # and read by adc1.py in place of a value the harness injected by
        # hand. Seeded from the model's own initial quantities so the first
        # sample taken before any TIM3 write has occurred reads the model's
        # cold-start state rather than an arbitrary placeholder.
        self.injected_counts = {}
        self.step_count = 0
        self.last_step_ok = True
        self._refresh_injected_counts()

    def restart(self):
        """Return the model to the state it came up in, and report what it lost.

        The seam's own bring-up writes the timer's compare registers before the
        control law has commanded anything -- switching the outputs on at zero
        is still a write -- and this bridge reads a compare write as an
        interval's actuation. So by the time a driving script has brought the
        artefact up, the model has already been advanced by intervals nothing
        asked for.

        That does not matter to a run asking whether the loop closes, which is
        why nothing needed this before. It matters to a run asking whether this
        model and another agree, because the two would then be started from
        different places and the comparison would be reporting the bring-up
        rather than the models. A driving script says here that the draw begins
        with the model as initialised; the count of steps discarded is returned
        so a run that meant to discard nothing can see what it discarded.
        """
        if not self._lib.plant_model_init(self._model, self._parameters):
            raise RuntimeError("plant_bridge: the plant model could not be re-initialised")

        discarded = self.step_count
        self.actuation_levels = [0] * ACTUATION_CHANNEL_COUNT
        self.step_count = 0
        self.last_step_ok = True
        self._refresh_injected_counts()
        return discarded

    def _bind(self):
        lib = self._lib
        lib.plant_parameters_load.argtypes = [
            ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p]
        lib.plant_parameters_load.restype = ctypes.c_bool
        lib.plant_model_init.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.plant_model_init.restype = ctypes.c_bool
        lib.plant_model_step_reporting.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(PlantActuation), ctypes.c_float,
            ctypes.c_uint32, ctypes.c_void_p]
        lib.plant_model_step_reporting.restype = ctypes.c_bool
        lib.plant_model_quantity.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_float)]
        lib.plant_model_quantity.restype = ctypes.c_bool

    def quantity(self, quantity):
        """One quantity the plant model currently exposes, in its own unit.

        Public so a driving script can read the model's state directly --
        the same read the injected-counts refresh below takes, on the same
        terms plant_model_quantity itself does not distinguish its callers.
        """
        value = ctypes.c_float(0.0)
        if not self._lib.plant_model_quantity(self._model, quantity, ctypes.byref(value)):
            raise RuntimeError("plant_bridge: quantity %d could not be read" % quantity)
        return value.value

    def _refresh_injected_counts(self):
        for converter_input, quantity in SENSOR_QUANTITY_BY_CONVERTER_INPUT.items():
            self.injected_counts[converter_input] = _quantity_to_counts(self.quantity(quantity))

    def on_compare_write(self, channel_index, level_permille):
        """A TIM3 compare register was written. Steps the plant on the pump
        channel, which every path through this build's control law writes
        last within one iteration -- so a write reaching it is the signal that
        the whole interval's actuation is now held and ready to act on.
        """
        if 0 <= channel_index < ACTUATION_CHANNEL_COUNT:
            self.actuation_levels[channel_index] = level_permille

        if channel_index != ACTUATION_CHANNEL_PUMP:
            return

        actuation = PlantActuation()
        for index in range(ACTUATION_CHANNEL_COUNT):
            actuation.level_permille[index] = self.actuation_levels[index]

        # CONTROL_STEP_INTERVAL_MS: a write only ever reaches the pump channel
        # once control.c's own cadence gate has accepted the step, so the
        # interval this write represents is always exactly one control tick.
        error = ctypes.create_string_buffer(64)
        ok = self._lib.plant_model_step_reporting(
            self._model, ctypes.byref(actuation), ctypes.c_float(0.0),
            ctypes.c_uint32(10), error)
        self.last_step_ok = bool(ok)
        if ok:
            self.step_count += 1
            self._refresh_injected_counts()


_bridge = None


def get():
    global _bridge
    if _bridge is None:
        _bridge = PlantBridge()
    return _bridge
