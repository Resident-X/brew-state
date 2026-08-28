"""What the closed-loop run has to have shown before it counts as evidence.

The run happens once for the whole suite, on the same terms
test_emulation_check.py's does: it is one exercise of one artefact, and every
assertion below reads the findings that run produced rather than reaching for
the emulator itself.
"""

import hashlib
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
FIRMWARE_DIR = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, TOOLS)

import build_plant_library  # noqa: E402
import register_map  # noqa: E402
import run_closed_loop_check as runner  # noqa: E402
import seam_channels  # noqa: E402

FINDINGS = None

# Read out of closed_loop.py's own source rather than duplicated here, on the
# same terms register_map.py already reads tim3.py's and adc1.py's register
# constants without executing either -- closed_loop.py references Renode's
# `bus`/`cpu`/`monitor` at module scope and cannot be imported outside it.
DRAW_STEPS = register_map.source_constants(runner.EXERCISE)["DRAW_STEPS"]

INCLUDE_DIR = os.path.join(FIRMWARE_DIR, "include")
HW_STM32_SOURCE = os.path.join(FIRMWARE_DIR, "src", "hw", "stm32", "hw_stm32.c")

# plant_bridge.py is a plain importable module -- unlike tim3.py, adc1.py and
# closed_loop.py, nothing at its top level touches Renode's request/bus/cpu
# globals -- so its own vocabulary constants are read by importing it, the
# same way any of this bridge's other consumers would.
sys.path.insert(0, runner.PERIPHERALS)
import plant_bridge  # noqa: E402


def _enum_member_order(header_path, enum_name):
    """The member names of one C enum, in declaration order.

    A light regex parse rather than a real C parser -- sufficient for the
    fixed-form enums this vocabulary declares, and this is a check against
    drift, not a compiler. Comments are stripped first so a member mentioned
    only in prose is not read as declared.
    """
    with open(header_path, encoding="utf-8") as handle:
        source = handle.read()
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    source = re.sub(r"//.*", "", source)
    match = re.search(
        r"typedef\s+enum\s*\{(.*?)\}\s*%s\s*;" % re.escape(enum_name), source, re.DOTALL)
    if not match:
        raise AssertionError("%s declares no `typedef enum { ... } %s;`" % (header_path, enum_name))
    members = []
    for entry in match.group(1).split(","):
        name = entry.strip().split("=")[0].strip()
        if name:
            members.append(name)
    return members


CONTROL_STEP_ACTUATED = 0
CONTROL_STEP_TOO_SOON = 1
CONTROL_STEP_SENSOR_INVALID = 2
CONTROL_STEP_OUTPUT_REFUSED = 3
CONTROL_STEP_FAULT_LATCHED = 4
CONTROL_STEP_LATE = 5
CONTROL_STEP_NO_TARGET = 6
CONTROL_STEP_DELIVERY_DEPARTED = 7

# A step whose result says the loop actually ran and did not fault, refuse, or
# find itself with nothing commanded -- the only results a run of this
# harness, which always keeps a target commanded, is entitled to see.
ORDINARY_DRIVEN_RESULTS = (CONTROL_STEP_ACTUATED, CONTROL_STEP_TOO_SOON, CONTROL_STEP_LATE)

# The margin the final brew-temperature reading must clear over the baseline
# for the run to count as evidence the loop moved the model rather than
# leaving it where it started -- generous under what a real run reaches (about
# 9 degrees over three simulated seconds from a 20-degree start), so a run
# that barely moved still fails clearly rather than by a coin's width.
MINIMUM_BREW_RISE_C = 2.0


def setUpModule():
    global FINDINGS
    FINDINGS = runner.run_once()


class PlantModelIsTheHostTiersOwnImplementation(unittest.TestCase):
    """SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C1: The plant model driven
    under emulation is the host tier's own implementation, not a re-expression
    of it.
    """

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C1: driven under emulation
    # is the host tier's own implementation.
    def test_the_bridge_compiles_exactly_the_plant_common_and_thermoblock_sources(self):
        """The shared library's source list matches the tree, not a snapshot.

        A file added to src/plant/common or src/plant/thermoblock without this
        list being updated would leave the bridge quietly calling a stale
        subset of the model -- the exact failure "not a re-expression of it"
        exists to rule out. Comparing against a directory listing taken now,
        rather than a second hard-coded list, is what catches that drift.
        """
        common_dir = os.path.join(FIRMWARE_DIR, "src", "plant", "common")
        structure_dir = os.path.join(FIRMWARE_DIR, "src", "plant", "thermoblock")
        expected = {
            os.path.join(common_dir, name) for name in os.listdir(common_dir)
            if name.endswith(".c")
        } | {
            os.path.join(structure_dir, name) for name in os.listdir(structure_dir)
            if name.endswith(".c")
        }
        actual = {os.path.abspath(path) for path in build_plant_library.SOURCES}
        self.assertEqual(
            expected, actual,
            "the plant bridge's source list has drifted from src/plant/common and "
            "src/plant/thermoblock")

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C1: not a re-expression of
    # it -- the library is compiled fresh from the tree's own bytes, not
    # carried as a prebuilt artefact nothing here re-derives.
    def test_the_bridge_library_is_freshly_compiled_from_the_sources_on_disk(self):
        digest = hashlib.sha256()
        for source in sorted(build_plant_library.SOURCES):
            with open(source, "rb") as handle:
                digest.update(handle.read())
        marker = FINDINGS["plant_library"] + ".sources-sha256"
        with open(marker, encoding="utf-8") as handle:
            recorded = handle.read().strip()
        self.assertEqual(
            digest.hexdigest(), recorded,
            "the compiled bridge library does not match the plant sources on disk")

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C1: driven under emulation
    # is the host tier's own implementation -- its steps must be admissible on
    # the seam's own terms, not merely appear to run.
    def test_every_step_the_bridge_took_was_admissible(self):
        self.assertTrue(
            FINDINGS["plant_last_step_ok"],
            "the plant bridge's last step was refused by the seam's own admissibility check")

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C1: the host tier's own
    # implementation -- which depends on the bridge addressing the same
    # channels and quantities machine_actuation.h and plant_types.h declare,
    # not a second, drift-prone copy of their ordering.
    def test_the_bridges_pump_channel_index_matches_the_shared_vocabularys_order(self):
        members = _enum_member_order(
            os.path.join(INCLUDE_DIR, "machine_actuation.h"), "actuation_channel_t")
        self.assertEqual(
            plant_bridge.ACTUATION_CHANNEL_PUMP, members.index("ACTUATION_CHANNEL_PUMP"),
            "the bridge's pump channel index has drifted from actuation_channel_t's own order")
        self.assertEqual(
            plant_bridge.ACTUATION_CHANNEL_BREW_HEATER,
            members.index("ACTUATION_CHANNEL_BREW_HEATER"),
            "the bridge's brew heater channel index has drifted from actuation_channel_t's "
            "own order, so the level a run reports the heater was driven at is another "
            "channel's")
        self.assertEqual(
            plant_bridge.ACTUATION_CHANNEL_COUNT, members.index("ACTUATION_CHANNEL_COUNT"),
            "the bridge's channel count has drifted from actuation_channel_t's own order")

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C1: the host tier's own
    # implementation -- each converter input's figure must be read as the
    # quantity plant_types.h names at that position, not a re-numbered one.
    def test_the_bridges_quantity_indices_match_plant_types_own_order(self):
        members = _enum_member_order(
            os.path.join(INCLUDE_DIR, "plant_types.h"), "plant_quantity_t")
        expected_by_input = {
            0: "PLANT_QUANTITY_BREW_TEMPERATURE_C",
            1: "PLANT_QUANTITY_STEAM_TEMPERATURE_C",
            2: "PLANT_QUANTITY_BREW_PRESSURE_BAR",
            3: "PLANT_QUANTITY_STEAM_PRESSURE_BAR",
        }
        for converter_input, quantity in plant_bridge.SENSOR_QUANTITY_BY_CONVERTER_INPUT.items():
            with self.subTest(converter_input=converter_input):
                self.assertEqual(
                    members.index(expected_by_input[converter_input]), quantity,
                    "converter input %d reads a quantity plant_types.h does not place there"
                    % converter_input)

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C1: the host tier's own
    # implementation -- the counts-to-quantity conversion must be the exact
    # inverse of hw_stm32.c's own scaling, or a reading the artefact computes
    # from a converter count and a reading this bridge injects as one would
    # disagree about the same channel.
    def test_the_bridges_converter_scale_matches_hw_stm32cs_own(self):
        self.assertEqual(
            plant_bridge.ADC_FULL_SCALE_COUNTS,
            seam_channels.defined_value(HW_STM32_SOURCE, "ADC_FULL_SCALE_COUNTS"))
        self.assertEqual(
            plant_bridge.SENSOR_FULL_SCALE_MILLI,
            seam_channels.defined_value(HW_STM32_SOURCE, "SENSOR_FULL_SCALE_MILLI"))


class ActuationReachesThePlantModelEveryInterval(unittest.TestCase):
    """SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C2: Actuation the firmware
    commands through TIM3 reaches the plant model every control interval.
    """

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C2: reaches the plant model
    # every control interval -- one bridge step per interval the firmware
    # actually drove outputs on, at least.
    def test_every_actuating_interval_produced_at_least_one_plant_step(self):
        self.assertGreater(FINDINGS["draw_actuated_count"], 0,
                           "the draw never reached an actuating control interval")
        self.assertGreaterEqual(
            FINDINGS["plant_step_count"], FINDINGS["draw_actuated_count"],
            "fewer plant steps were taken than the firmware drove actuating intervals for")

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C2: every interval, not
    # merely the first -- a bridge that stepped once and then silently stopped
    # reaching the plant model would still show a nonzero step count above.
    def test_the_plant_was_stepped_across_the_whole_draw_not_only_at_its_start(self):
        checkpoints = FINDINGS["checkpoints"]
        self.assertEqual(len(checkpoints), 2, "the run reported neither checkpoint reading")
        self.assertGreater(
            checkpoints[0], FINDINGS["baseline_brew_c"],
            "the plant model had not moved by the draw's first checkpoint")
        self.assertGreater(
            checkpoints[1], checkpoints[0],
            "the plant model stopped advancing between the two checkpoints")


class SensorReadingsReflectThePostActuationState(unittest.TestCase):
    """SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C3: Sensor readings the
    firmware receives via ADC1 reflect the plant model's state after the
    actuation that produced them.
    """

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C3: reflect the plant
    # model's state after the actuation that produced them -- a sensor window
    # still holding the harness's cold-start figure would leave the estimator
    # reconstructing a temperature that never moves, and the closed loop would
    # never learn it was approaching the target.
    def test_the_final_reading_reflects_the_actuation_the_run_commanded(self):
        rise = FINDINGS["final_brew_c"] - FINDINGS["baseline_brew_c"]
        self.assertGreaterEqual(
            rise, MINIMUM_BREW_RISE_C,
            "the brew temperature ADC1 reported rose by only %.3fC over the draw, which is "
            "not evidence the reading tracked the actuated plant" % rise)

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C3: after the actuation
    # that produced them -- the reading changes because the actuation the
    # control law itself commanded produced it, not because of some other
    # figure the harness happened to inject.
    def test_the_control_law_actually_commanded_the_delivery_this_run_measured(self):
        self.assertTrue(FINDINGS["command"], "control_command_temperature was refused")
        # The control path is brought up against the description's coefficients
        # and against what that description says those coefficients may be
        # wrong by. Both are asserted, because the second is what the margin a
        # commanded target is held to is sized from: a run that loaded only the
        # first brings the loop up faulted, and every interval of the draw
        # below then reports a latched fault with the heater standing at
        # nothing -- a shape a reader can mistake for a loop that simply had
        # little to do.
        self.assertTrue(FINDINGS["parameters_loaded"], "plant_parameters_load was refused")
        self.assertTrue(FINDINGS["budget_loaded"], "plant_parameter_budget_load was refused")
        self.assertTrue(FINDINGS["control_init"], "control_init was refused")
        self.assertEqual(
            FINDINGS["flow_refusals"], 0,
            "%s of the draw's flow commands were refused, so the water this run reports "
            "moving was not the water it asked for" % FINDINGS["flow_refusals"])


class ClosedLoopRunsAFullSimulatedDraw(unittest.TestCase):
    """SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C4: The closed loop runs a
    full simulated draw with no target hardware present.
    """

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C4: runs a full simulated
    # draw -- every interval of it, not a run that stopped short.
    def test_the_draw_ran_every_commanded_interval(self):
        self.assertEqual(FINDINGS["draw_steps"], DRAW_STEPS)
        self.assertEqual(len(FINDINGS["draw_results"]), DRAW_STEPS)

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C4: with no target hardware
    # present -- every interval the artefact reported was one of the ordinary
    # results a fully-commanded, fault-free run produces; a fault, a refusal,
    # or an interval reporting nothing commanded would mean the loop broke
    # down somewhere across the draw rather than ran it.
    def test_every_interval_reported_an_ordinary_result(self):
        for index, result in enumerate(FINDINGS["draw_results"]):
            with self.subTest(interval=index):
                self.assertIn(
                    result, ORDINARY_DRIVEN_RESULTS,
                    "interval %d reported control_step result %d, which is not an ordinary "
                    "driven result" % (index, result))

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C4: a full simulated draw
    # -- almost every interval actually actuated, which is the threshold this
    # criterion is measured against: a harness whose cadence starved most
    # intervals into CONTROL_STEP_TOO_SOON would technically run the draw
    # without ever driving it.
    def test_almost_every_interval_actuated(self):
        self.assertGreaterEqual(
            FINDINGS["draw_actuated_count"], FINDINGS["draw_steps"] - 1,
            "fewer than all but one commanded interval actually drove the outputs")

    # SOL-EMULATED-FIRMWARE-CLOSED-LOOP-WITH-PLANT.C4: the run is evidence
    # about the artefact actually built, on the same terms
    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C1 already establishes for
    # the channel-addressing run.
    def test_the_artefact_emulated_is_the_target_environments_own_output(self):
        self.assertEqual(
            os.path.abspath(FINDINGS["artefact"]["path"]),
            os.path.abspath(runner.base.TARGET_ARTEFACT))
        self.assertEqual(
            FINDINGS["image"]["fnv1a64"], FINDINGS["expected_image_fnv1a64"],
            "flash under emulation does not hold the loadable segments of the artefact")


if __name__ == "__main__":
    unittest.main()
