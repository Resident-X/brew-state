"""What the emulation run has to have shown before it counts as evidence.

The run happens once for the whole suite, because it is one exercise of one
artefact and splitting it would mean asserting about several different runs as
though they were one. Every assertion below reads the findings that run
produced; none of them reaches for the emulator itself.
"""

import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, "..", "tools"))
sys.path.insert(0, TOOLS)

import register_map  # noqa: E402
import run_emulation_check as runner  # noqa: E402
import seam_channels  # noqa: E402

FINDINGS = None

EXERCISE = os.path.join(TOOLS, "..", "scripts", "exercise.py")

# The hardware seam's own vocabulary, as the header declares it. Named here
# because the assertions are about coverage of that set, and a suite that
# discovered the set from the run could never notice a channel the run missed.
# Written down rather than read, and then asserted against the headers by
# ChannelSetsAreTheSeamsOwn below: a list read from the headers would follow
# them wherever they went, including into the state this tier exists to catch.
SENSOR_CHANNELS = {
    0: "HW_SENSOR_BREW_TEMPERATURE",
    1: "HW_SENSOR_STEAM_TEMPERATURE",
    2: "HW_SENSOR_BREW_PRESSURE",
    3: "HW_SENSOR_STEAM_PRESSURE",
    4: "HW_SENSOR_FLOW",
}
OUTPUT_CHANNELS = {
    0: "ACTUATION_CHANNEL_BREW_HEATER",
    1: "ACTUATION_CHANNEL_STEAM_HEATER",
    2: "ACTUATION_CHANNEL_PUMP",
    3: "ACTUATION_CHANNEL_STEAM_PUMP",
}

# The channel this board wires no converter input to. It is in the set above
# and answers by saying nothing is there, which is a different answer from a
# reading of zero.
UNWIRED_SENSOR_CHANNEL = 4

HW_READING_ABSENT = 0
HW_READING_FAILED = 1
HW_READING_VALID = 2

# The seam implementation's declared mapping from converter counts to
# milli-units. Asserted rather than derived from the run, so that a change to
# either end of it has to be a deliberate change to this line too.
ADC_FULL_SCALE_COUNTS = 4095
SENSOR_FULL_SCALE_MILLI = 200000


def setUpModule():
    global FINDINGS
    FINDINGS = runner.run()


def command_steps():
    """Just the per-channel commands, in the order they were issued."""
    return [entry for entry in FINDINGS["compare"] if entry["label"].isdigit()]


def labelled(label):
    for entry in FINDINGS["compare"]:
        if entry["label"] == label:
            return entry
    raise AssertionError("the run reported no compare state labelled %r" % label)


class TargetBinaryIdentity(unittest.TestCase):
    """SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C1: The emulation harness
    loads the same compiled image the target environment produces for the
    microcontroller, rather than compiling the control logic, the hardware-seam
    implementation, or any other firmware source separately for the emulator.
    Provenance is established by comparing the artefact loaded into the harness
    against the target build's own output for the same commit, not by
    re-deriving equivalent behaviour from source. Out of scope: whether the
    artefact's timing matches the real microcontroller's electrical behaviour,
    which is a property the on-target tier establishes rather than a property of
    what is loaded here.

    Each test below names the clause of that criterion it carries.
    """

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C1: Provenance is established
    # by comparing the artefact loaded into the harness against the target
    # build's own output for the same commit.
    def test_the_instructions_in_emulated_flash_are_the_artefacts_own_bytes(self):
        reported = FINDINGS["image"]["fnv1a64"]
        expected = FINDINGS["expected_image_fnv1a64"]
        self.assertEqual(
            reported, expected,
            "flash under emulation does not hold the loadable segments of %s"
            % FINDINGS["artefact"]["path"])

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C1: Provenance is established
    # by comparing the artefact loaded into the harness against the target
    # build's own output for the same commit, not by re-deriving equivalent
    # behaviour from source.
    def test_a_single_altered_instruction_would_be_noticed(self):
        """The comparison above is only evidence if it can fail.

        Both sides of it are derived from the same file, so a comparison that
        agreed whatever the file held would agree just as readily about a
        re-expression. One byte of the artefact is altered here and the host
        side recomputed: the digest has to move.
        """
        base = FINDINGS["image"]["base"]
        length = FINDINGS["image"]["length"]
        image = bytearray(runner.image_of(FINDINGS["artefact"]["path"], base, length))
        self.assertEqual(runner.fnv1a64(bytes(image)), FINDINGS["image"]["fnv1a64"])
        image[0x200] ^= 0x01
        self.assertNotEqual(
            runner.fnv1a64(bytes(image)), FINDINGS["image"]["fnv1a64"],
            "the comparison cannot tell the artefact from an altered copy of it")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C1: The emulation harness
    # loads the same compiled image the target environment produces for the
    # microcontroller, rather than compiling the control logic, the
    # hardware-seam implementation, or any other firmware source separately for
    # the emulator.
    def test_the_artefact_emulated_is_the_target_environments_own_output(self):
        self.assertEqual(
            os.path.abspath(FINDINGS["artefact"]["path"]),
            os.path.abspath(runner.TARGET_ARTEFACT),
            "the run emulated something other than the target build's output file")
        with open(FINDINGS["script"], encoding="utf-8") as handle:
            script = handle.read()
        self.assertIn(
            "LoadELF @%s" % runner.TARGET_ARTEFACT, script,
            "the emulator was not told to load the target build's own artefact")
        self.assertNotIn(
            "LoadBinary", script,
            "the artefact reached the emulator by some route other than being loaded as built")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C1: Provenance is established
    # by comparing the artefact loaded into the harness against the target
    # build's own output for the same commit.
    def test_the_artefact_was_not_replaced_while_the_run_was_under_way(self):
        self.assertEqual(
            FINDINGS["artefact"]["sha256"], FINDINGS["artefact"]["sha256_after_run"],
            "the artefact on disk changed between the build and the end of the run")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C1: The emulation harness
    # loads the same compiled image the target environment produces for the
    # microcontroller.
    def test_the_artefacts_own_startup_code_brought_the_core_to_the_entry_point(self):
        self.assertIsNotNone(
            FINDINGS["startup"],
            "the run never reported reaching the artefact's entry point")
        self.assertGreater(
            FINDINGS["startup"], 0,
            "no instruction of the artefact was executed before the entry point was reached")


class SensorChannelsAreModelled(unittest.TestCase):
    """SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: For each sensor channel
    the hardware interface enumerates, the emulation harness backs the
    corresponding peripheral with a model that can be driven into every reading
    status the interface defines -- a channel with nothing fitted, a sample that
    failed, and a trustworthy value -- and the firmware under emulation reads
    back exactly the status and figure the model was put into. Out of scope:
    whether the modelled figures correspond to any particular machine's real
    sensor readings, which is a plant-model concern carried by the criterion
    governing what drives the emulated firmware and what it drives in turn.

    Each test below names the clause of that criterion it carries.
    """

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: For each sensor channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model.
    def test_the_peripherals_the_seam_needs_came_up_under_the_models(self):
        self.assertEqual(
            FINDINGS["init"], 1,
            "the seam's bring-up refused, so no channel below was reached through a real peripheral")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... a model that can be
    # driven into every reading status the interface defines -- ... a
    # trustworthy value -- and the firmware under emulation reads back exactly
    # the status and figure the model was put into.
    def test_every_wired_sensor_channel_reports_the_figure_its_own_input_was_given(self):
        for channel, name in SENSOR_CHANNELS.items():
            if channel == UNWIRED_SENSOR_CHANNEL:
                continue
            with self.subTest(channel=name):
                counts = FINDINGS["injected"][channel]
                expected = counts * SENSOR_FULL_SCALE_MILLI // ADC_FULL_SCALE_COUNTS
                reading = FINDINGS["sensor"][channel]
                self.assertEqual(
                    reading["status"], HW_READING_VALID,
                    "%s did not obtain a reading from its model" % name)
                self.assertEqual(
                    reading["value_milli"], expected,
                    "%s reported a figure its own converter input was not given" % name)

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... the firmware under
    # emulation reads back exactly the status and figure the model was put into.
    def test_no_two_sensor_channels_reported_the_same_figure(self):
        reported = [FINDINGS["sensor"][channel]["value_milli"]
                    for channel in SENSOR_CHANNELS
                    if channel != UNWIRED_SENSOR_CHANNEL]
        self.assertEqual(
            len(set(reported)), len(reported),
            "two sensor channels reached the same modelled converter input")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: For each sensor channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model ... the firmware under emulation
    # reads back exactly the status and figure the model was put into.
    def test_each_wired_channel_caused_exactly_one_conversion_on_its_own_input(self):
        for channel, name in SENSOR_CHANNELS.items():
            if channel == UNWIRED_SENSOR_CHANNEL:
                continue
            with self.subTest(channel=name):
                self.assertEqual(
                    FINDINGS["conversions"][channel], 1,
                    "%s did not sample its converter input exactly once" % name)

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... a model that can be
    # driven into every reading status the interface defines -- a channel with
    # nothing fitted ...
    def test_the_channel_this_board_wires_nothing_to_answers_by_saying_so(self):
        reading = FINDINGS["sensor"][UNWIRED_SENSOR_CHANNEL]
        self.assertEqual(
            reading["status"], HW_READING_ABSENT,
            "%s reported something other than absence, though no converter input backs it"
            % SENSOR_CHANNELS[UNWIRED_SENSOR_CHANNEL])
        self.assertEqual(
            sum(FINDINGS["conversions"].values()), len(SENSOR_CHANNELS) - 1,
            "a conversion was started that no wired channel accounts for")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... a model that can be
    # driven into every reading status the interface defines -- a channel with
    # nothing fitted ...
    def test_a_channel_outside_the_declared_set_answers_absence_rather_than_a_neighbours_reading(self):
        beyond = max(SENSOR_CHANNELS) + 1
        self.assertIn(beyond, FINDINGS["sensor"], "the run never asked past the declared set")
        self.assertEqual(
            FINDINGS["sensor"][beyond]["status"], HW_READING_ABSENT,
            "a channel outside the declared set was answered by a model")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... a model that can be
    # driven into every reading status the interface defines -- ... a sample
    # that failed ... -- and the firmware under emulation reads back exactly the
    # status and figure the model was put into.
    def test_a_fitted_channel_whose_sample_came_back_unusable_reports_a_failed_reading(self):
        """The third status, and the only one the run has to provoke.

        Absence comes from the board's own wiring and a trustworthy value from
        an input handing one back, so both arise on their own. A failed sample
        does not: one input is put into handing back a count outside the
        converter's scale, and the seam has to answer that the channel is fitted
        and its sample cannot be trusted. Without this the seam could report
        absence, or scale the unusable count into a figure and call it
        trustworthy, on a channel that failed, and nothing here would differ.
        """
        channel = min(FINDINGS["failed"]) if FINDINGS["failed"] else None
        self.assertIsNotNone(
            channel, "the run never drove a channel into a failed reading")
        self.assertIn(
            channel, SENSOR_CHANNELS,
            "the channel driven into failure is not one the seam declares")
        self.assertNotEqual(
            channel, UNWIRED_SENSOR_CHANNEL,
            "failure was provoked on the channel with nothing fitted, where it "
            "cannot be told from absence")

        reading = FINDINGS["failed"][channel]
        self.assertEqual(
            reading["status"], HW_READING_FAILED,
            "%s reported %d rather than a failed reading, though its converter "
            "input handed back a count outside the converter's scale"
            % (SENSOR_CHANNELS[channel], reading["status"]))
        self.assertEqual(
            reading["value_milli"], 0,
            "%s carried a figure alongside a reading it says cannot be trusted"
            % SENSOR_CHANNELS[channel])

        # The three statuses are distinct answers, not one answer under three
        # names: the same channel reports a trustworthy value when its input is
        # left alone, and a different channel reports absence throughout.
        self.assertEqual(
            FINDINGS["sensor"][channel]["status"], HW_READING_VALID)
        self.assertEqual(
            FINDINGS["sensor"][UNWIRED_SENSOR_CHANNEL]["status"], HW_READING_ABSENT)
        self.assertEqual(
            len({HW_READING_ABSENT, HW_READING_FAILED, HW_READING_VALID}), 3)

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... a model that can be
    # driven into every reading status the interface defines ... and the
    # firmware under emulation reads back exactly the status and figure the
    # model was put into.
    def test_the_channel_driven_into_failure_reports_its_own_figure_again_afterwards(self):
        """Failure has to be the model's doing, not the channel's.

        A channel that failed because something about it had broken would fail
        whatever the model did, and reporting that as a driven failure would be
        reporting the harness's own defect as evidence. So the input is put back
        to a count within scale and the same channel read again: it has to come
        back with the trustworthy figure its own input holds.
        """
        channel = min(FINDINGS["failed"])
        self.assertIn(
            channel, FINDINGS["restored"],
            "the run never read the channel again with its input put back")
        reading = FINDINGS["restored"][channel]
        counts = FINDINGS["injected"][channel]
        self.assertEqual(
            reading["status"], HW_READING_VALID,
            "%s did not recover once its input was put back, so its failure was "
            "not the model's doing" % SENSOR_CHANNELS[channel])
        self.assertEqual(
            reading["value_milli"],
            counts * SENSOR_FULL_SCALE_MILLI // ADC_FULL_SCALE_COUNTS,
            "%s recovered with a figure its own converter input was not given"
            % SENSOR_CHANNELS[channel])


class OutputChannelsAreSeparatelyAddressable(unittest.TestCase):
    """SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: For each output channel
    the hardware interface enumerates, the emulation harness backs the
    corresponding peripheral with a model that records only the level last
    commanded on that channel. Commanding one output channel while observing
    every modelled channel shows that only the addressed channel's recorded
    state changes: no two channels share a model and no command is silently
    absorbed by none. This demonstrates, for the emulation tier, that every
    output the control logic can command is shown separately addressable before
    anything is energised. Out of scope: whether the channel a command reaches
    on emulated hardware corresponds to the device a real machine's wiring
    intends, which is a property of the finished machine rather than of the
    emulation harness.

    Each test below names the clause of that criterion it carries.
    """

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: For each output channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model that records only the level last
    # commanded on that channel.
    def test_every_declared_output_channel_was_commanded(self):
        commanded = [int(entry["label"]) for entry in command_steps()]
        self.assertEqual(
            commanded, sorted(OUTPUT_CHANNELS),
            "the run did not command every output channel the seam declares, once each")
        for entry in command_steps():
            with self.subTest(channel=OUTPUT_CHANNELS[int(entry["label"])]):
                self.assertTrue(
                    entry["accepted"],
                    "the seam refused a command on a channel it declares")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: Commanding one output channel while observing every modelled channel shows
    # that only the addressed channel's recorded state changes: no two channels
    # share a model and no command is silently absorbed by none.
    def test_commanding_one_channel_moved_only_that_channels_modelled_state(self):
        previous = labelled("after-init")
        for entry in command_steps():
            channel = int(entry["label"])
            with self.subTest(channel=OUTPUT_CHANNELS[channel]):
                self.assertEqual(
                    entry["values"][channel], entry["level"],
                    "%s did not take the level it was commanded" % OUTPUT_CHANNELS[channel])
                self.assertEqual(
                    entry["writes"][channel], previous["writes"][channel] + 1,
                    "%s was not written exactly once by its own command"
                    % OUTPUT_CHANNELS[channel])
                for other in OUTPUT_CHANNELS:
                    if other == channel:
                        continue
                    self.assertEqual(
                        entry["values"][other], previous["values"][other],
                        "commanding %s moved %s as well"
                        % (OUTPUT_CHANNELS[channel], OUTPUT_CHANNELS[other]))
                    self.assertEqual(
                        entry["writes"][other], previous["writes"][other],
                        "commanding %s reached %s as well"
                        % (OUTPUT_CHANNELS[channel], OUTPUT_CHANNELS[other]))
            previous = entry

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: ... no two channels share
    # a model and no command is silently absorbed by none.
    def test_no_two_channels_ended_on_the_same_modelled_state(self):
        final = command_steps()[-1]
        levels = [entry["level"] for entry in command_steps()]
        self.assertEqual(len(set(levels)), len(levels),
                         "the run commanded two channels the same level, so it could not tell them apart")
        self.assertEqual(
            final["values"], levels,
            "the modelled compare state does not hold one commanded level per channel")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: ... only the addressed
    # channel's recorded state changes: no two channels share a model ...
    def test_every_channel_was_reached_the_same_number_of_times(self):
        final = command_steps()[-1]
        self.assertEqual(
            len(set(final["writes"])), 1,
            "one channel's compare register was written more often than another's, "
            "which is what two channels sharing an output looks like")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: ... a model that records
    # only the level last commanded on that channel ... no command is silently
    # absorbed by none.
    def test_a_refused_command_reached_no_output_at_all(self):
        settled = command_steps()[-1]
        self.assertFalse(FINDINGS["refusals"]["channel"],
                         "the seam accepted a command on a channel it does not declare")
        self.assertFalse(FINDINGS["refusals"]["level"],
                         "the seam accepted a level above full scale")
        for label in ("after-refused-channel", "after-refused-level"):
            with self.subTest(refusal=label):
                after = labelled(label)
                self.assertEqual(after["values"], settled["values"],
                                 "a refused command moved a modelled output")
                self.assertEqual(after["writes"], settled["writes"],
                                 "a refused command reached a compare register")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: ... no command is
    # silently absorbed by none. This demonstrates, for the emulation tier, that
    # every output the control logic can command is shown separately addressable
    # before anything is energised.
    def test_nothing_the_run_commanded_landed_where_no_peripheral_answers(self):
        self.assertEqual(
            FINDINGS["unanswered_writes"], [],
            "the artefact wrote to an address this machine maps no peripheral to, "
            "so a command reached nothing")


class ModelledRegistersAreThePartsOwn(unittest.TestCase):
    """SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2, .C3: the harness backs
    each peripheral "with a model" -- of the part, which a model answering the
    wrong offsets is not, and no run against one can be evidence about the part.
    Both models are checked against the vendor's register description, which the
    provisioning step pins.

    Each test below names the clause of the criterion it carries.
    """

    @classmethod
    def setUpClass(cls):
        cls.svd = FINDINGS["svd"]

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: For each sensor channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model ...
    def test_the_converter_model_answers_the_parts_own_register_offsets(self):
        _, registers, fields = register_map.peripheral_map(self.svd, "ADC1")
        constants = register_map.model_constants("adc1")
        for name in ("SR", "CR1", "CR2", "SQR3", "DR"):
            with self.subTest(register=name):
                self.assertEqual(
                    constants[name], registers[name],
                    "the converter model answers %s at an offset the part does not use" % name)
        self.assertEqual(constants["SR_EOC"], 1 << fields["SR"]["EOC"])
        self.assertEqual(constants["SR_STRT"], 1 << fields["SR"]["STRT"])
        self.assertEqual(constants["CR2_ADON"], 1 << fields["CR2"]["ADON"])
        self.assertEqual(constants["CR2_SWSTART"], 1 << fields["CR2"]["SWSTART"])

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: For each output channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model ...
    def test_the_timer_model_answers_the_parts_own_compare_register_offsets(self):
        _, registers, _ = register_map.peripheral_map(self.svd, "TIM3")
        constants = register_map.model_constants("tim3")
        self.assertEqual(
            constants["CCR1"], registers["CCR1"],
            "the timer model answers the first compare register at an offset the part does not use")
        for index in range(constants["COMPARE_CHANNELS"]):
            name = "CCR%d" % (index + 1)
            with self.subTest(register=name):
                self.assertIn(name, registers,
                              "the part declares no %s, so this model has a channel the part has not" % name)
                self.assertEqual(
                    constants["CCR1"] + 4 * index, registers[name],
                    "the model places %s where the part does not" % name)

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... a model that can be
    # driven into every reading status the interface defines ... and the
    # firmware under emulation reads back exactly the status and figure the
    # model was put into.
    def test_the_converters_harness_windows_shadow_no_register_the_part_declares(self):
        """Including the window every reading status is driven from.

        A window the harness writes to drive the model is only harness-side
        while it lands nowhere the part has a register. One that shadowed a real
        register would be a peripheral the firmware could reach, and a status
        driven through it would be the firmware's doing rather than the
        harness's.
        """
        occupied = register_map.declared_offsets(self.svd, "ADC1")
        constants = register_map.model_constants("adc1")
        for base_name in ("INJECT_BASE", "COUNT_BASE"):
            base = constants[base_name]
            for offset in range(base, base + 4 * constants["PORT_INPUTS"]):
                with self.subTest(window=base_name, offset=hex(offset)):
                    self.assertNotIn(
                        offset, occupied,
                        "the harness window at %s covers a register the part really has" % hex(offset))

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: For each output channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model that records only the level last
    # commanded on that channel.
    def test_the_timers_harness_window_shadows_no_register_the_part_declares(self):
        occupied = register_map.declared_offsets(self.svd, "TIM3")
        constants = register_map.model_constants("tim3")
        base = constants["COUNT_BASE"]
        for offset in range(base, base + 4 * constants["COMPARE_CHANNELS"]):
            with self.subTest(offset=hex(offset)):
                self.assertNotIn(
                    offset, occupied,
                    "the harness window at %s covers a register the part really has" % hex(offset))


class FindingsAreReadHonestly(unittest.TestCase):
    """The suite's own reading of the run, checked against a run it makes up.

    Every assertion above is only as good as the parsing between the emulator's
    output and the record they read. These drive that parsing with output
    describing failures the real run did not produce, so a parser that quietly
    dropped an awkward line would be caught here rather than by everything
    passing.
    """

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: Commanding one output
    # channel while observing every modelled channel shows that only the
    # addressed channel's recorded state changes: no two channels share a model
    # ...
    def test_a_run_where_two_channels_shared_an_output_is_read_as_such(self):
        # What the seam did before its fourth channel was given a compare
        # register of its own: the fourth command lands on the first channel's
        # register, so that register is written twice and the fourth never.
        parsed = runner.parse_findings("\n".join([
            "EMU output after-init 0 1 0,0,0,0 1,1,1,1",
            "EMU output 0 137 1 137,0,0,0 2,1,1,1",
            "EMU output 3 908 1 908,0,0,0 3,1,1,1",
            "EMU done",
        ]))
        self.assertTrue(parsed["completed"])
        steps = [entry for entry in parsed["compare"] if entry["label"].isdigit()]
        self.assertEqual(steps[-1]["writes"], [3, 1, 1, 1])
        self.assertEqual(steps[-1]["values"][0], 908,
                         "a command reaching another channel's register was not read as reaching it")
        self.assertNotEqual(
            len(set(steps[-1]["writes"])), 1,
            "a run in which one register absorbed two channels was read as if every channel had its own")

    # Untraced: this is about the harness's own honesty, not about a channel or
    # an artefact. No criterion of the solution says a run must report whether
    # it finished -- the runner refuses to hand over findings from a run that
    # did not, which is a property of the runner, and every criterion above is
    # only reached once it has.
    def test_a_run_that_stopped_early_is_not_read_as_a_complete_one(self):
        parsed = runner.parse_findings("EMU init 1\nEMU sensor 0 2 60268")
        self.assertFalse(
            parsed["completed"],
            "a run that never reported finishing was read as though it had")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: ... the firmware under
    # emulation reads back exactly the status and figure the model was put into.
    def test_a_negative_reading_is_not_read_as_a_large_positive_one(self):
        """Kept traced: the reading is only "exactly" what it is once read.

        The seam's figure is signed and this run's models never hand back a
        negative one, so the only thing standing between a firmware reporting
        minus one and a half units and the suite seeing sixty-odd thousand is
        this parse. A criterion about reading back exactly what was put in is
        not carried by the run alone.
        """
        parsed = runner.parse_findings("EMU sensor 2 2 -1500")
        self.assertEqual(parsed["sensor"][2]["value_milli"], -1500)

    # Untraced: this is about telling the harness's findings from the
    # emulator's own chatter around them. No criterion asks for it; every
    # criterion above depends on it, which is why it is asserted here rather
    # than claimed by one of them.
    def test_output_from_the_emulator_that_is_not_a_finding_is_ignored(self):
        noisy = "\n".join([
            "Renode, version 1.16.1",
            "  EMU init 1  ",
            "warning: EMU init 0",
            "EMU done",
        ])
        parsed = runner.parse_findings(noisy)
        self.assertEqual(parsed["init"], 1,
                         "a line that merely mentions a finding was read as one")
        self.assertTrue(parsed["completed"])

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: ... no command is
    # silently absorbed by none.
    def test_a_write_that_reached_no_peripheral_is_read_out_of_the_emulators_log(self):
        """The one finding whose absence is the evidence.

        Every assertion about a write landing nowhere reads an empty list, and
        an empty list is what a reading that never matches anything also
        produces. The wording is the emulator's, not ours, so a release that
        phrased it differently would leave that list empty for good and the
        check vacuous. This drives the same reading with the message the
        emulator really emits, so the day the wording moves is the day this
        fails rather than the day nobody notices.
        """
        log = "\n".join([
            "12:00:00.0000 [WARNING] sysbus: WriteDoubleWord to non existing "
            "peripheral at 0x0, value 0x147",
            "12:00:00.0001 [WARNING] sysbus: WriteByte to non existing "
            "peripheral at 0x4000FFFC, value 0x1",
            "12:00:00.0002 [INFO] sysbus: peripheral at 0xDEADBEEF answered",
        ])
        self.assertEqual(
            runner.unanswered_writes(log), ["0", "4000fffc"],
            "the emulator's own report of a write reaching nothing was not read as one")
        self.assertEqual(
            runner.unanswered_writes(""), [],
            "a run whose log says nothing was read as reporting a write")


class ChannelSetsAreTheSeamsOwn(unittest.TestCase):
    """SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2, .C3: "for each sensor
    channel the hardware interface enumerates" and "for each output channel the
    hardware interface enumerates" -- which is a claim about the interface's
    enumeration, not about the list this suite happens to hold.

    The run and the suite both work from channel sets written down by hand, and
    a written-down set is a copy of an enumeration. The defect this whole tier
    exists to net is a channel reaching the seam with no peripheral behind it,
    and that arrives by a channel being added to an enumeration. If the copies
    did not have to follow, such a channel would be one the run never commands
    and the suite never misses: every assertion above would keep passing over
    the smaller, older set, and the tier would be quietly answering a question
    nobody asked any more.

    So both copies are held to the headers here. Read rather than asserted, they
    would follow the enumeration wherever it went, including into exactly that
    state -- which is why the sets stay written down and this is where they are
    made to agree.
    """

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2: For each sensor channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model ...
    def test_the_sensor_channels_asserted_are_the_ones_the_interface_enumerates(self):
        self.assertEqual(
            SENSOR_CHANNELS, seam_channels.sensor_channels(),
            "the sensor channels this suite asserts about are not the ones "
            "hw_interface.h enumerates, so a channel has been added or renamed "
            "without the run reaching it")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C3: For each output channel
    # the hardware interface enumerates, the emulation harness backs the
    # corresponding peripheral with a model ...
    def test_the_output_channels_asserted_are_the_ones_the_interface_enumerates(self):
        self.assertEqual(
            OUTPUT_CHANNELS, seam_channels.output_channels(),
            "the output channels this suite asserts about are not the ones "
            "machine_actuation.h enumerates, so a channel has been added or "
            "renamed without the run commanding it")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2, .C3: For each sensor
    # channel the hardware interface enumerates ... For each output channel the
    # hardware interface enumerates ...
    def test_the_run_reached_as_many_channels_as_the_interface_enumerates(self):
        """The script that exercises the artefact holds its own copy.

        It runs inside the emulator's interpreter and cannot read a header, so
        the counts it walks are written into it. Held to the enumerations here,
        because a run that walked four of five channels would report about four
        and every assertion above would be about the four it reported.
        """
        constants = register_map.source_constants(EXERCISE)
        self.assertEqual(
            constants["SENSOR_CHANNEL_COUNT"], len(seam_channels.sensor_channels()),
            "the run walks a different number of sensor channels than "
            "hw_interface.h enumerates")
        self.assertEqual(
            constants["OUTPUT_CHANNEL_COUNT"], len(seam_channels.output_channels()),
            "the run commands a different number of output channels than "
            "machine_actuation.h enumerates")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2, .C3: ... every reading
    # status the interface defines ... no command is silently absorbed by none.
    def test_a_channel_added_to_the_interface_is_reported_rather_than_passed_over(self):
        """The check above is only evidence if it can fail.

        Both an added channel and a renamed one have to be caught, and a
        comparison of two lists nobody varies would agree just as readily if it
        compared nothing. The enumeration is read from a header written here
        with a channel the suite's set does not hold: the reading has to return
        it, so the comparison above would have something to disagree with.
        """
        declared = seam_channels.declared(
            seam_channels.OUTPUT_HEADER,
            seam_channels.OUTPUT_TYPE,
            seam_channels.OUTPUT_COUNT)
        with open(seam_channels.OUTPUT_HEADER, encoding="utf-8") as handle:
            header = handle.read()
        widened = header.replace(
            "    ACTUATION_CHANNEL_COUNT",
            "    ACTUATION_CHANNEL_GRINDER,\n    ACTUATION_CHANNEL_COUNT")
        self.assertNotEqual(widened, header, "the header could not be widened")

        with tempfile.NamedTemporaryFile(
                "w", suffix=".h", encoding="utf-8", delete=False) as handle:
            handle.write(widened)
            path = handle.name
        self.addCleanup(os.unlink, path)

        read_back = seam_channels.declared(
            path, seam_channels.OUTPUT_TYPE, seam_channels.OUTPUT_COUNT)
        self.assertEqual(
            read_back, declared + ["ACTUATION_CHANNEL_GRINDER"],
            "a channel added to the enumeration was not read back, so the "
            "comparison above would pass over one added for real")
        self.assertNotEqual(
            dict(enumerate(read_back)), OUTPUT_CHANNELS,
            "a widened enumeration still matched the set this suite asserts about")

    # SOL-EMULATED-BINARY-AND-MODELLED-PERIPHERALS.C2, .C3: For each sensor
    # channel the hardware interface enumerates ... For each output channel the
    # hardware interface enumerates ...
    def test_an_enumeration_that_cannot_be_read_is_refused_rather_than_read_as_empty(self):
        """A check that inspects nothing must not report success."""
        with self.assertRaises(seam_channels.Unreadable):
            seam_channels.declared(
                os.path.join(TOOLS, "no-such-header.h"),
                seam_channels.OUTPUT_TYPE, seam_channels.OUTPUT_COUNT)
        with self.assertRaises(seam_channels.Unreadable):
            seam_channels.declared(
                seam_channels.OUTPUT_HEADER,
                "no_such_type_t", seam_channels.OUTPUT_COUNT)


class SysTickAdvancesTheTickCounter(unittest.TestCase):
    """SOL-STM32-INTERRUPT-VECTORS-DEFINED.C1: The SysTick interrupt runs a
    real handler that advances the tick counter.

    Verification and regression protection are the same assertion here: a
    SysTick_Handler that does not call HAL_IncTick() -- reverted, or replaced
    by a future change that forgets it -- makes tick_after equal tick_before
    regardless of how many instructions run in between, which is exactly what
    the single test below checks and what this criterion requires. A
    forgotten call was confirmed to fail this test before it was written back
    in, so no second test is needed to cover the same regression a different
    way.
    """

    # SOL-STM32-INTERRUPT-VECTORS-DEFINED.C1: The SysTick interrupt runs a
    # real handler that advances the tick counter.
    def test_the_tick_counter_advances_while_the_core_runs(self):
        tick = FINDINGS["tick"]
        self.assertGreater(
            tick["after"], tick["before"],
            "HAL_GetTick() did not advance across %d single-stepped "
            "instructions; SysTick_Handler is not calling HAL_IncTick()"
            % tick["steps_taken"])


class UnhandledVectorTrapsToADefinedFaultState(unittest.TestCase):
    """SOL-STM32-INTERRUPT-VECTORS-DEFINED.C2: An interrupt reaching any other
    unhandled vector traps to a defined fault state, not a silent lockup.
    """

    #: The high halfword the trap writes, chosen to be recognisable rather
    #: than a value uninitialised memory could plausibly hold.
    FAULT_MARKER_TAG = 0xFA170000

    #: WWDG's own exception number under the Cortex-M core's ICSR.VECTACTIVE
    #: numbering: external IRQ0 is exception 16.
    WWDG_EXCEPTION_NUMBER = 16

    # SOL-STM32-INTERRUPT-VECTORS-DEFINED.C2: An interrupt reaching any other
    # unhandled vector traps to a defined fault state.
    def test_pending_an_unused_vector_reaches_the_fault_marker(self):
        """WWDG is pended directly through the NVIC.

        Nothing in this seam enables or services the watchdog, so this is a
        vector reached by no route the firmware would ever take on its own --
        which is exactly the situation an unhandled vector is: an interrupt
        this build gave no purposeful handler, arriving anyway.
        """
        self.assertEqual(
            FINDINGS["fault_marker_before"], 0,
            "the fault marker was non-zero before any vector was pended, so "
            "the value after pending one is not evidence about this test's "
            "own pend")
        after = FINDINGS["fault_marker_after"]
        self.assertNotEqual(
            after["value"], 0,
            "pending WWDG's interrupt through the NVIC did not reach the "
            "fault marker within %d instructions" % after["steps_taken"])

    # SOL-STM32-INTERRUPT-VECTORS-DEFINED.C2: ... not a silent lockup -- the
    # trap records which vector reached it rather than merely halting.
    def test_the_marker_names_the_vector_that_trapped(self):
        after = FINDINGS["fault_marker_after"]["value"]
        self.assertEqual(
            after & 0xFFFF0000, self.FAULT_MARKER_TAG,
            "the fault marker's tag does not match the value the trap "
            "deliberately writes, so this may be leftover memory rather than "
            "the trap having run")
        self.assertEqual(
            after & 0x1FF, self.WWDG_EXCEPTION_NUMBER,
            "the fault marker does not name WWDG's own exception number, so "
            "whatever produced it was not this test's pend")

    # SOL-STM32-INTERRUPT-VECTORS-DEFINED.C2: An interrupt reaching any other
    # unhandled vector traps to a defined fault state, not a silent lockup.
    def test_the_vendor_default_handler_is_absent_from_the_linked_image(self):
        """Evidence about every vector at once, not just the one pended above.

        The vendor startup file links Default_Handler as a strong symbol and
        weak-aliases every otherwise-unhandled vector to it; that strong
        symbol cannot be redefined; overriding a vector means overriding that
        vector's own alias instead. A vector this build forgot would leave
        its alias pointing at Default_Handler, which would keep that symbol
        reachable and so present in the linked image. Its absence is only
        possible if every alias was overridden -- this is what makes the
        claim "any other unhandled vector", not just WWDG's.
        """
        self.assertFalse(
            FINDINGS["default_handler_present"],
            "Default_Handler is still present in the linked artefact, so at "
            "least one vector still falls through to the vendor's silent "
            "loop")


if __name__ == "__main__":
    unittest.main()
