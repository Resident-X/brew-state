#!/usr/bin/env python3
"""Find the hottest each thermoblock's casting gets while the shipped control path
is holding its heater, across every operating phase the controller commands and
every corner of the declared error.

The proof-of-life removal interval is the time a heater left fully on takes to
reach its retained protection's trip point, and it starts from the casting's
temperature at that moment. The commanded figure does not bound that: the coffee
loop controls the water leaving the block and the steam loop controls pressure
during a draw, and in both the casting runs hotter than the commanded figure by
an amount no declared figure fixes. The plant model represents the casting, so
the peak is read out of it rather than assumed.

Nothing is added to the control path or to the host artefact. The closed-loop
coffee and steam draws already report the casting temperature once per control
interval, with the machine built from one corner's coefficients and the control
path held at the description that shipped; the protection-margin tool already
reads the control path's own corner enumeration and builds each corner's
machine. This tool consumes both. A second enumeration of corners standing
beside the loop's would eventually describe corners the loop was not taking its
margin over, and the record would go on reading plausibly while it did.

What is run, per thermoblock, is a course of phases, each found by what the run
did and not by a clock this file chose:

  * warm-up, from a cold machine to the commanded figure, and the hold at it
    with no draw until the casting has settled -- the point it settled at is
    read off the run, so the two phases are the same run split where it came to
    rest;
  * each delivery that heater serves, at each of the pump levels the flow entry
    point accepts that this tool exercises;
  * recovery after each delivery, continued until the casting has passed its
    post-delivery maximum and settled back to its holding value, and refused
    rather than reported when it had not;
  * each delivery started again on the interval after the last one ended, so
    the block is still recovering from the first.

The target each delivery is commanded at is the highest the control path
admits, and it is read rather than chosen. For the coffee thermoblock that is
what the protection-margin reading narrows to on the loop's own admission path.
For hot water, which the same casting serves at the drinking point, it is the
highest target below the drinking-temperature ceiling the tolerance declaration
states and the control path refuses a target at or above; the ceiling is read
out of that declaration through the sweep's own readers. For the steam
thermoblock it is the highest ready temperature the steam loop comes up at, as
the same reading reports it, and the draw is then held on pressure as the loop
shipped holds it.

The corners are the control path's own: each end of each coefficient carrying a
declared error, on its own, and each stated joint corner. The machine at the
declared coefficients is run too and reported beside them, because a figure
meant to bound a casting must not be lower than the machine the description
actually names. The figure is the worst single corner, never a sum, and each
loop's declared sensing error is then added to the casting temperature the runs
report. The runs feed the controller the plant's true values, so a sensor
reading low -- which holds the casting hotter than the control path believes --
is not otherwise in the peak.

A steam draw has no end of its own: the wand is a hand valve, and the model's
casting keeps rising under a draw held longer than the feed can replace. The
figure is therefore for the draw the course opens the wand for, and the record
carries a table of how the peak moves as the draw is lengthened rather than
leaving the length as an unstated choice.

Nothing here is a measurement of the casting. It is the model's answer, graded
inferred, and measuring the casting on the machine is out of scope.
"""

from __future__ import annotations

import argparse
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))
REPOSITORY_DIR = os.path.abspath(os.path.join(FIRMWARE_DIR, ".."))

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FIRMWARE_DIR, "tools"))

import run_cross_tier_check as cross_tier  # noqa: E402
import run_emulation_check as base  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402
import run_protection_margin as margin  # noqa: E402

#: Where the peaks are kept.
REPORT_PATH = os.path.join(REPOSITORY_DIR, "docs", "casting-peak.md")

#: What regenerates the record, as the record states it.
REGENERATE_COMMAND = "python3 firmware/emulation/tools/run_casting_peak.py"

#: Where this tool's own working files go. A directory of its own, so that this
#: and the protection-margin analysis cannot leave each other's corner
#: descriptions standing under the same names.
BUILD_DIR = os.path.join(FIRMWARE_DIR, ".pio", "build", cross_tier.HOST_ENVIRONMENT,
                         "casting-peak")

#: The two ways a casting is served, and the word each is reported under.
COFFEE = "coffee"
HOT_WATER = "hot water"
STEAM = "steam"

#: The channel of a draw's findings each side's casting temperature is read
#: from, so that a call site names a side and not a free string.
CASTING_CHANNEL = {COFFEE: "brew-c", STEAM: "steam-c"}

#: How a temperature is written into the record. One decimal, because the
#: figure is subtracted from a trip point a few kelvin above it on the coffee
#: side and a whole-degree figure would move the interval by a quarter of a
#: second.
TEMPERATURE_FORMAT = "%.1f"

#: What a table cell holds where there is nothing to say.
NOTHING = "—"

#: The phases a run is divided into, as the words the record reports them
#: under.
WARM_UP = "warm-up"
HOLD = "hold"
DELIVERY = "delivery"
RECOVERY = "recovery"
BACK_TO_BACK = "back-to-back delivery"
RECOVERY_AFTER_BACK_TO_BACK = "recovery after back-to-back delivery"
PHASES = (WARM_UP, HOLD, DELIVERY, RECOVERY, BACK_TO_BACK, RECOVERY_AFTER_BACK_TO_BACK)

#: What "settled" means for a casting, and over how long it has to stay so.
#:
#: A quarter of a kelvin held for ten simulated seconds: finer than the
#: declared band a delivery is held to, and coarser than the slow creep a loop
#: with a long integral time keeps making towards its target for minutes after
#: it has stopped mattering. A window that is not settled by its end is
#: lengthened and run again rather than reported, because a peak taken over a
#: recovery that had not finished is a peak taken over part of the recovery.
SETTLED_BAND_C = 0.25
SETTLED_TAIL_STEPS = 1000

#: How long each phase of the coffee course is, in control intervals, before it
#: is lengthened.
#:
#: The hold is the warm-up and the hold together: the machine begins cold and
#: nothing stands it at its target first. A delivery is long enough to draw a
#: cup of hot water at the faster of the two levels and to drive the heater to
#: its limit while it does. The recovery is long enough, at the declared
#: coefficients, for the casting to come back through its post-delivery
#: maximum.
HOLD_STEPS = 40000
DELIVERY_STEPS = 6000
RECOVERY_STEPS = 40000

#: How long the same phases are on the steam side. A draw is the twenty seconds
#: the sweep's steam course opens the wand for, which is about what a jug of
#: milk takes, and is not lengthened with the coffee side's.
STEAM_HOLD_STEPS = 40000
STEAM_DELIVERY_STEPS = sweep.STEAM_DRAW_STEPS
STEAM_RECOVERY_STEPS = 40000

#: The factors a window is lengthened by while its end has not settled, in
#: order. A window that has not settled at the last is refused.
LENGTHENINGS = (1, 2, 4)

#: The pump levels the coffee thermoblock's deliveries are run at, in permille
#: of full pump scale: the level a shot is drawn at, which is the sweep's, and
#: full pump scale.
#:
#: The flow entry point accepts any level up to full scale, and the recovery
#: after a delivery gets hotter with the level once the heater has been at its
#: limit while the water was drawn. The faster is therefore the worse of the two
#: on that phase, and the shot is here because it is the delivery the machine
#: is built to make. A level between them cannot be hotter than the faster.
SHOT_PERMILLE = sweep.BREW_PEAK_PERMILLE
FULL_SCALE_PERMILLE = 1000
COFFEE_LEVELS = (SHOT_PERMILLE, FULL_SCALE_PERMILLE)

#: The rate the steam wand is opened at: the rate the steam law's own band tests
#: draw at, which the sweep's steam course is built from.
STEAM_LEVELS = (sweep.STEAM_DEMAND_MILLI_ML_PER_S,)

#: How long the wand is held open, in seconds, in the runs that ask how the
#: steam peak depends on that. The first is the draw every corner is run with.
#: The others are longer: a draw held past what the feed can replace does not
#: settle in the model, and what the peak does as the draw lengthens is a
#: finding to be reported rather than a length to be chosen once and left.
STEAM_DRAW_SECONDS = (STEAM_DELIVERY_STEPS * sweep.INTERVAL_MS // 1000, 60, 120, 300)

#: The word the tolerance declaration spells the drinking-temperature ceiling
#: under, and the macro the header names it by.
DRINKING_CEILING_MACRO = "DELIVERY_TOLERANCE_DRINKING_CEILING_WORD"

#: The word the steam declaration spells its ready temperature under.
STEAM_READY_MACRO = "STEAM_CONTROL_DECLARATION_READY_TEMPERATURE_WORD"

#: The section of the controller boards' figures record that quotes the peaks
#: and keeps the interval pending against them, as the heading it is written under.
FIGURES_RECORD_SECTION = "### Proof-of-life removal interval"

#: The files a run is generated from, as the words the record's table names them
#: under and the key of the findings each is held at, in the order the record
#: lists them. The run, the record and the staleness check all read this one list.
INPUTS = (("The machine's coefficients", "description"),
          ("What a reading off it may be", "limits"),
          ("The bands a delivery is held to", "tolerance"),
          ("The steam side's design figures", "declaration"))

#: The headings the record carries, as constants so the readers below and the
#: tests that keep the record honest find the sections this writes.
FIGURES_HEADING = "## The peak under control"
PHASES_HEADING = "## The hottest each phase reached"
CORNERS_HEADING = "## What each corner reached"
RUNS_HEADING = "## What was run"
STEAM_LENGTH_HEADING = "## How the steam peak depends on how long the wand is held open"


class CastingError(RuntimeError):
    """The peak could not be found, or could not be found over everything it
    covers."""


# --- Reading what the control path admits ----------------------------------


def float32_below(value):
    """The largest single-precision number strictly below `value`.

    The control path compares in single precision and refuses a target at or
    above the drinking ceiling, so the highest target it admits is the number
    just under the ceiling in that precision. A decimal figure written a hair
    under the ceiling would round to the ceiling on the way in and be refused.
    """
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    return struct.unpack("<f", struct.pack("<I", bits - 1))[0]


def drinking_ceiling_c(tolerance=sweep.TOLERANCE_DECLARATION):
    """The temperature a drink served at the drinking point may not reach, in
    degrees, read out of the declaration the control path is brought up against
    through the sweep's own readers."""
    word = sweep._declared_word(sweep.TOLERANCE_HEADER, DRINKING_CEILING_MACRO)
    return sweep._declared_figure(tolerance, word) / 1000.0


def targets_admitted(shipped, tolerance):
    """The highest target each way the coffee thermoblock is served is run at.

    The brew target is what the reading narrowed the control path's admission to.
    Hot water is served at the drinking point, whose window the control path
    applies on top of that, so its highest target is the lower of the brew
    target and the number just under the drinking ceiling.
    """
    brew_c = shipped["target_c"]
    return {COFFEE: brew_c, HOT_WATER: min(brew_c, float32_below(drinking_ceiling_c(tolerance)))}


def declaration_with_ready_temperature(source, milli_c, destination):
    """The steam declaration with its ready temperature written differently.

    Written back out and handed to the ordinary loader rather than the loaded
    record being reached into, so the loop is brought up on exactly the terms
    the shipped declaration is, including the margin the loop checks the target
    against. Everything else in the file is carried across untouched.
    """
    word = sweep._declared_word(sweep.STEAM_DECLARATION_HEADER, STEAM_READY_MACRO)
    rewritten = []
    found = False
    for raw in margin.origins.read(source).splitlines():
        head, separator, tail = raw.partition("=")
        if separator and head.strip() == word:
            _, _, rest = tail.strip().partition(" ")
            if not rest.startswith("milli-c"):
                raise CastingError("%s states '%s' in a unit other than milli-c" % (source, word))
            rewritten.append("%s = %d %s" % (word, milli_c, rest))
            found = True
        else:
            rewritten.append(raw.rstrip())
    if not found:
        raise CastingError("%s states no '%s', so its ready temperature cannot be rewritten"
                           % (source, word))
    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rewritten) + "\n")
    return destination


# --- The course ------------------------------------------------------------


def course_of(levels, hold, delivery, recovery):
    """The levels each control interval commands, and the window each phase of
    them occupies.

    The first window is the warm-up and the hold together; where one ends and
    the other begins is read off the run. Each level then has a delivery, its
    recovery, a delivery followed on the next interval by a second one, and the
    recovery after that. The second is started on the interval after the first
    ends -- the earliest a flow command can follow the last, and the flow entry
    point refuses nothing on grounds of the block's state -- so the block is
    still recovering from the first.
    """
    steps = []
    windows = []

    def add(phase, level, count):
        windows.append({"phase": phase, "level": level, "start": len(steps),
                        "end": len(steps) + count})
        steps.extend([level] * count)

    add(WARM_UP, 0, hold)
    for level in levels:
        add(DELIVERY, level, delivery)
        add(RECOVERY, 0, recovery)
        add(DELIVERY, level, delivery)
        add(BACK_TO_BACK, level, delivery)
        add(RECOVERY_AFTER_BACK_TO_BACK, 0, recovery)
    return steps, windows


def peak_of(series, start=0, end=None):
    """The highest value over a window of a series, and the interval it was at.

    Every interval of the window is looked at, and the earliest of equal
    highest values is the one reported.
    """
    end = len(series) if end is None else end
    if not 0 <= start < end <= len(series):
        raise CastingError("the window %d to %d covers no interval of a series of %d"
                           % (start, end, len(series)))
    at = max(range(start, end), key=lambda index: (series[index], -index))
    return series[at], at


def settled_by(series, start, end, centre, band=SETTLED_BAND_C, tail=SETTLED_TAIL_STEPS):
    """Whether a series sits within `band` of `centre` over the last `tail`
    intervals of a window."""
    if end - start < tail:
        return False
    return all(abs(value - centre) <= band for value in series[end - tail:end])


def analyse(series, windows, band=SETTLED_BAND_C, tail=SETTLED_TAIL_STEPS):
    """Divide one run into its phases, find each one's hottest casting, and say
    what had not settled.

    The hold value is the casting's mean over the end of the first window. The
    warm-up is the stretch of that window before the casting came to rest within
    `band` of it for good, and the hold is the rest. A recovery is held to the
    same value: it must have passed its maximum before its tail begins and be
    back inside the band throughout the tail.

    Returns the phases -- which partition the run, so every interval belongs to
    exactly one -- and the list of what had not settled, empty when the run is
    one a peak can be taken over.
    """
    problems = []
    first = windows[0]
    if first["end"] - first["start"] < tail:
        raise CastingError("the first window is shorter than the tail it is judged settled over")
    hold_c = sum(series[first["end"] - tail:first["end"]]) / float(tail)

    came_to_rest = first["end"]
    while came_to_rest > first["start"] and abs(series[came_to_rest - 1] - hold_c) <= band:
        came_to_rest -= 1
    if came_to_rest > first["end"] - tail:
        problems.append("the casting had not come to rest by the end of the hold")

    phases = []
    split = [(WARM_UP, first["start"], came_to_rest), (HOLD, came_to_rest, first["end"])]
    for phase, start, end in split:
        if end > start:
            phases.append({"phase": phase, "level": 0, "start": start, "end": end})
    for window in windows[1:]:
        phases.append(dict(window))

    for phase in phases:
        phase["peak_c"], phase["peak_at"] = peak_of(series, phase["start"], phase["end"])

    for window in windows[1:]:
        if not window["phase"].startswith(RECOVERY):
            continue
        _, peak_at = peak_of(series, window["start"], window["end"])
        if peak_at >= window["end"] - tail:
            problems.append("the casting was still rising at the end of a recovery that began at "
                            "interval %d" % window["start"])
        elif not settled_by(series, window["start"], window["end"], hold_c, band, tail):
            problems.append("the casting had not settled back to its holding value by the end of "
                            "a recovery that began at interval %d" % window["start"])
    return phases, problems, hold_c


def held_against_reported(found, channel, intervals, start=0):
    """The hottest casting a draw reported from `start` on, with the interval it
    was at, taken from the series and refused unless it agrees with what the
    artefact printed.

    Every run that sets a figure goes through here. The series is the parsed
    trajectory; the printed lines are read again, separately, by
    `reported_castings`. A series that is not one reading per control interval
    of the course -- a trimmed trajectory, a channel that was not the casting --
    or a peak below any casting temperature the artefact printed, is refused
    rather than reported, because a peak taken over less than was reported
    understates a safety figure.
    """
    series = found["channels"][channel]
    reported = reported_castings(found["stdout"], channel)
    if len(series) != intervals:
        raise CastingError("the draw reported %d intervals of a course of %d"
                           % (len(series), intervals))
    if len(reported) != intervals:
        raise CastingError("the artefact printed %d %s readings for a course of %d intervals"
                           % (len(reported), channel, intervals))
    peak_c, peak_at = peak_of(series, start, intervals)
    printed_c = max(reported[start:])
    if peak_c < printed_c:
        raise CastingError("the peak taken from the %s series, %s C, is below the %s C the "
                           "artefact printed" % (channel, _temperature(peak_c),
                                                 _temperature(printed_c)))
    return peak_c, peak_at, printed_c


def run_phased(draw, levels, hold, delivery, recovery, channel):
    """One run of the course, lengthened until every window that has to settle
    has, and the phases found in it.

    `draw` takes the course and returns the findings of a draw; `channel` names
    the series of those findings the casting is read from. A run that has not
    settled at the longest length is refused: reporting a peak over a recovery
    that had not finished would be reporting part of the recovery, and leaving
    the corner out would understate a safety figure. So is a run whose series
    does not agree with what the artefact printed.
    """
    problems = []
    for factor in LENGTHENINGS:
        steps, windows = course_of(levels, hold * factor, delivery, recovery * factor)
        found = draw([(sweep.INTERVAL_MS, level) for level in steps])
        peak_c, peak_at, printed_c = held_against_reported(found, channel, len(steps))
        series = found["channels"][channel]
        phases, problems, hold_c = analyse(series, windows)
        if not problems:
            return {"series": series, "phases": phases, "hold_c": hold_c, "peak_c": peak_c,
                    "peak_at": peak_at, "lengthened": factor, "intervals": len(steps),
                    "printed_peak_c": printed_c}
    raise CastingError("a run still had not settled when its phases were %d times their "
                       "starting length: %s" % (LENGTHENINGS[-1], "; ".join(problems)))


def phase_at(phases, interval):
    """The phase an interval of a run belongs to."""
    for phase in phases:
        if phase["start"] <= interval < phase["end"]:
            return phase
    raise CastingError("interval %d belongs to no phase of the run" % interval)


# --- The whole analysis ----------------------------------------------------


def require_ran(side, corner):
    """Refuse to go on when a corner of the enumeration produced no machine.

    The figure is the worst over every corner the enumeration covers; a record
    written with a corner left out would be the worst over fewer than it says,
    and would understate a safety figure without saying so.
    """
    if not corner["ran"]:
        raise CastingError("the %s enumeration's corner %s (%s, %s end) produced no machine: the "
                           "structure admits none there, or the description declares no error to "
                           "take it to. No peak is written over fewer corners than the "
                           "enumeration covers"
                           % (side, corner["which"], _coefficient(corner), corner["end"]))


def corner_nominal(corner, nominal):
    """The coefficients one corner's machine is built from."""
    values = dict(nominal)
    for name in corner["writes"]:
        values[name] = nominal[name] * corner["factor"]
    return values


def a_run(side, kind, corner, target_c, result, levels):
    """The part of one run the record and the tests read."""
    peak_phase = phase_at(result["phases"], result["peak_at"])
    return {
        "side": side,
        "kind": kind,
        "corner": corner,
        "target_c": target_c,
        "levels": levels,
        "phases": result["phases"],
        "hold_c": result["hold_c"],
        "peak_c": result["peak_c"],
        "peak_at": result["peak_at"],
        "peak_phase": peak_phase["phase"],
        "peak_level": peak_phase["level"],
        "lengthened": result["lengthened"],
        "intervals": result["intervals"],
        "printed_peak_c": result["printed_peak_c"],
    }


def run(description=None, limits=None, tolerance=sweep.TOLERANCE_DECLARATION,
        declaration=sweep.STEAM_CONTROL_DECLARATION, pio=base.DEFAULT_PIO, executable=None,
        workspace=BUILD_DIR):
    """Read the corner enumeration and run every phase of both thermoblocks at
    every corner of it.

    `description`, `limits` and `tolerance` default to the files the target
    build carries compiled in, which is what makes the record a statement about
    the machine this project is building. They are arguments so the same method
    can be pointed at a replacement model without anything here being edited.
    """
    carried_description, carried_limits = cross_tier.carried_declarations()
    description = description or carried_description
    limits = limits or carried_limits

    vocabulary, marker = sweep._vocabularies()
    nominal = sweep.nominal_values(description, vocabulary, marker)
    scale = cross_tier.converter_scale()
    executable = executable or sweep.build_host(pio)
    os.makedirs(workspace, exist_ok=True)

    shipped = margin.margin_record(executable, description, limits, declaration)
    coffee_targets = targets_admitted(shipped, tolerance)
    steam_ready_c = shipped["steam_highest_c"]
    ambient = "ambient_temperature_c"
    if ambient not in nominal:
        raise CastingError("%s states no '%s', so there is no cold machine to warm up from"
                           % (description, ambient))

    runs = []

    machines = [(None, description, nominal)]
    for corner in shipped["corners"]:
        require_ran(COFFEE, corner)
        written = margin.corner_description(corner, nominal, description,
                                            os.path.join(workspace, COFFEE))
        machines.append((corner, written, corner_nominal(corner, nominal)))
    for corner, written, _ in machines:
        which = 0 if corner is None else corner["which"]
        for kind, target_c in coffee_targets.items():
            name = "casting-peak-%s-%d" % (kind.replace(" ", "-"), which)

            def draw(course, written=written, target_c=target_c, name=name):
                return sweep.brew_draw(executable, written, limits, course, scale, name,
                                       control_description=description, target_c=target_c)
            result = run_phased(draw, COFFEE_LEVELS, HOLD_STEPS, DELIVERY_STEPS, RECOVERY_STEPS,
                                CASTING_CHANNEL[COFFEE])
            runs.append(a_run(COFFEE, kind, corner, target_c, result, COFFEE_LEVELS))

    # The steam draw builds the loop from the description it is given -- there
    # is no second description to hold it at while the machine moves -- so a
    # corner's loop is a loop of that corner's machine, and it comes up only at
    # a ready temperature that machine's own enumeration leaves room for. The
    # shipped loop never commands more than the machine at the declared
    # coefficients admits, so each machine is run at the lower of the two: the
    # target a loop that knew its machine to be at the corner would admit may be
    # higher than the shipped loop would ever command, and running at it would
    # report a peak for a command nobody gives.
    steam_machines = [(None, description, nominal, shipped)]
    for corner in shipped["steam_corners"]:
        require_ran(STEAM, corner)
        written = margin.corner_description(corner, nominal, description,
                                            os.path.join(workspace, STEAM))
        steam_machines.append((corner, written, corner_nominal(corner, nominal),
                               margin.margin_record(executable, written, limits, declaration)))
    for corner, written, values, reading in steam_machines:
        which = 0 if corner is None else corner["which"]
        name = "casting-peak-steam-%d" % which
        ready_c = min(steam_ready_c, reading["steam_highest_c"])
        ready = declaration_with_ready_temperature(
            declaration, int(round(ready_c * 1000.0)),
            os.path.join(workspace, "steam-highest-%d.declaration" % which))

        def steam(course, written=written, values=values, name=name, ready=ready):
            return sweep.steam_draw(executable, written, limits, ready, values[ambient], course,
                                    name)
        result = run_phased(steam, STEAM_LEVELS, STEAM_HOLD_STEPS, STEAM_DELIVERY_STEPS,
                            STEAM_RECOVERY_STEPS, CASTING_CHANNEL[STEAM])
        runs.append(a_run(STEAM, STEAM, corner, ready_c, result, STEAM_LEVELS))

    # How the steam peak depends on how long the wand is held open, at the
    # machine at the declared coefficients. A draw longer than the feed can
    # replace does not settle in the model, so the figure above is the figure
    # for the draw it was run with and the record says how it moves with the
    # length.
    nominal_ready = declaration_with_ready_temperature(
        declaration, int(round(steam_ready_c * 1000.0)),
        os.path.join(workspace, "steam-highest-length.declaration"))
    steam_lengths = []
    for seconds in STEAM_DRAW_SECONDS:
        drawn = seconds * 1000 // sweep.INTERVAL_MS
        course = ([(sweep.INTERVAL_MS, 0)] * STEAM_HOLD_STEPS
                  + [(sweep.INTERVAL_MS, STEAM_LEVELS[0])] * drawn)
        found = sweep.steam_draw(executable, description, limits, nominal_ready,
                                 nominal[ambient], course, "casting-peak-steam-length-%d" % seconds)
        peak_c, _, _ = held_against_reported(
            found, CASTING_CHANNEL[STEAM], len(course), STEAM_HOLD_STEPS)
        steam_lengths.append((seconds, peak_c))

    sensing = {COFFEE: shipped["margin"]["sensing_error_c"],
               STEAM: shipped["steam_margin"]["sensing_error_c"]}
    figures = {}
    for side in (COFFEE, STEAM):
        worst = worst_run([run_ for run_ in runs if run_["side"] == side])
        figures[side] = {
            "run": worst,
            "peak_c": worst["peak_c"],
            "sensing_error_c": sensing[side],
            "figure_c": worst["peak_c"] + sensing[side],
        }

    findings = {
        "description": description,
        "limits": limits,
        "tolerance": tolerance,
        "declaration": declaration,
        "executable": executable,
        "workspace": workspace,
        "shipped": shipped,
        "coffee_targets": coffee_targets,
        "drinking_ceiling_c": drinking_ceiling_c(tolerance),
        "steam_ready_c": steam_ready_c,
        "runs": runs,
        "figures": figures,
        "steam_lengths": steam_lengths,
    }
    findings["digests"] = {path: sweep.digest_of(path) for path in input_paths(findings)}
    return findings


def worst_run(runs):
    """The single run with the highest peak: the worst single corner, never a
    sum across them. Ties go to the earlier run."""
    if not runs:
        raise CastingError("there is no run to take a worst corner of")
    best = runs[0]
    for candidate in runs[1:]:
        if candidate["peak_c"] > best["peak_c"]:
            best = candidate
    return best


_FINDINGS = {}


def run_once(**arguments):
    """One run of the whole analysis per process, shared by every reader of it.

    The sweep costs a course per corner, and a test module asking several
    questions of one run would otherwise pay for each of them.
    """
    key = tuple(sorted((name, value) for name, value in arguments.items()
                       if isinstance(value, str)))
    if key not in _FINDINGS:
        _FINDINGS[key] = run(**arguments)
    return _FINDINGS[key]


# --- The record ------------------------------------------------------------


def _relative(path):
    """A path as it is written into the record: relative to the repository, so
    the record reads the same wherever the tree was checked out."""
    return os.path.relpath(os.path.abspath(path), REPOSITORY_DIR)


def _temperature(value):
    return TEMPERATURE_FORMAT % value


def _corner_label(corner):
    """How a corner is named in a row: the machine at the declared coefficients
    is not one of the enumeration's and is not given a number as if it were."""
    return "nominal" if corner is None else str(corner["which"])


def _coefficient(corner):
    return NOTHING if corner is None else margin._coefficient_cell(corner)


#: The statement at the head of the record about what its peaks are and are not.
BANNER = ("> **Diagnostic, not a board input.** These peaks are those of the control as it "
          "shipped. This record is not an input to any board until the regeneration "
          "criterion of DEL-CASTING-MARGIN-HELD-IN-EVERY-PHASE has run and the record has been "
          "regenerated from the corrected control. The steam peak is bounded by the course's draw length: it is "
          "the peak of a draw of that length, and a longer draw can climb higher, as the "
          "draw-length table below shows.")


def report_text(findings):
    """The whole record: the peak each thermoblock's casting reaches under
    control, what sets it, and what every corner reached.

    Written by the tool rather than by hand, so that pointing the method at a
    replacement model needs nothing changed here and a record is never left
    describing the previous machine.
    """
    shipped = findings["shipped"]
    figures = findings["figures"]
    lines = []
    write = lines.append

    write("# The hottest each thermoblock's casting gets while the controller holds its heater")
    write("")
    write("**Generated by `firmware/emulation/tools/run_casting_peak.py`. Do not edit by hand — "
          "re-run `%s`.**" % REGENERATE_COMMAND)
    write("")
    write(BANNER)
    write("")
    write("The proof-of-life removal interval starts from the temperature a heater's casting "
          "has when the controller stops, and the commanded figure does not bound it: the coffee "
          "loop controls the water leaving the block and the steam loop controls pressure during "
          "a draw, and in both the casting runs hotter than the commanded figure by an amount no "
          "declared figure fixes. This record is the hottest the plant model's casting reaches "
          "while the shipped control path is holding the heater, taken over every operating "
          "phase the controller commands and every corner of the declared error.")
    write("")
    write("Each heater is run on its own, since the two heated masses are independent, with the "
          "machine built from one corner's coefficients and the control path held at the "
          "description that shipped. The corners are the control path's own enumeration, read "
          "back through the same reading the protection-margin record uses: each end of each "
          "coefficient carrying a declared error, on its own, plus each stated joint corner. "
          "The corners combine by the worst single corner and never by summing or in "
          "quadrature. The machine at the declared coefficients is run as well and reported "
          "beside them.")
    write("")
    write("Each loop's declared sensing error is added to the hottest casting temperature the "
          "runs report, as a simultaneous degradation. The controller is run on the plant's "
          "true values, so a sensor reading low, which holds the casting hotter than the "
          "control path believes, is not otherwise in the peak.")
    write("")
    write("Nothing here is a measurement. The casting is the model's, graded **inferred**, and "
          "measuring it on the machine is not what this record does.")
    write("")

    write(RUNS_HEADING)
    write("")
    write("| What | File | sha256 |")
    write("|---|---|---|")
    for what, key in INPUTS:
        path = findings[key]
        write("| %s | `%s` | `%s` |" % (what, _relative(path), findings["digests"][path]))
    write("")
    write(sweep.supply_span_statement(findings["description"]))
    write("")
    write("A replacement model is read by naming it: `--description`, `--limits`, "
          "`--tolerance` and `--steam-declaration` each point the same method at another file.")
    write("")
    write("Targets, each the highest the control path admits and read rather than chosen:")
    write("")
    write("| Served | Target (C) | Where it is read from |")
    write("|---|---|---|")
    write("| %s | %s | the highest target the protection-margin reading narrows the loop's "
          "admission to (bound: %s) |" % (
              COFFEE, _temperature(findings["coffee_targets"][COFFEE]),
              shipped["capping_bound_name"]))
    write("| %s | %s | the number just under the %s C drinking-temperature ceiling "
          "`%s` declares, which the control path refuses a drinking-point target at or above |" % (
              HOT_WATER, _temperature(findings["coffee_targets"][HOT_WATER]),
              _temperature(findings["drinking_ceiling_c"]), _relative(findings["tolerance"])))
    write("| %s | %s | the highest ready temperature the steam loop comes up at, as the "
          "protection-margin reading reports it (the declared ready temperature is %s C); at a "
          "corner whose own machine admits less, that lower one, because the steam draw builds "
          "the loop from the description of the machine it is run against |" % (
              STEAM, _temperature(findings["steam_ready_c"]),
              _temperature(shipped["steam_ready_c"])))
    write("")
    write("Each coffee-thermoblock course warms the machine from cold and holds it with no draw "
          "(%d control intervals of %d ms, lengthened if the casting has not come to rest), then "
          "for each of two pump levels, %d permille of full pump scale (the level the sweep "
          "draws a shot at) and %d permille (full pump scale), runs a delivery of %d intervals, "
          "a recovery of %d, a delivery followed on the next interval by a second of %d, and a "
          "recovery of %d. Each steam course does the same with the wand opened at %.1f "
          "millilitres a second for %d intervals and recoveries of %d. A recovery that has not "
          "passed its maximum and settled back to within %.2f C of the holding value for %d "
          "intervals by its end is lengthened and run again, up to %d times its length, and "
          "refused beyond that." % (
              HOLD_STEPS, sweep.INTERVAL_MS, COFFEE_LEVELS[0], COFFEE_LEVELS[1], DELIVERY_STEPS,
              RECOVERY_STEPS, DELIVERY_STEPS, RECOVERY_STEPS, STEAM_LEVELS[0] / 1000.0,
              STEAM_DELIVERY_STEPS, STEAM_RECOVERY_STEPS, SETTLED_BAND_C, SETTLED_TAIL_STEPS,
              LENGTHENINGS[-1]))
    write("")

    write(FIGURES_HEADING)
    write("")
    write("The figure for each thermoblock is the hottest casting temperature any run reported, "
          "over every control interval, at the worst single corner, plus that loop's declared "
          "sensing error. Grade: **inferred** from the plant model.")
    write("")
    write("| Thermoblock | Peak casting temperature (C) | Declared sensing error (C) | "
          "Peak plus sensing error (C) | Phase | Corner | Served | Coefficient | End |")
    write("|---|---|---|---|---|---|---|---|---|")
    for side, label in ((COFFEE, "Coffee thermoblock"), (STEAM, "Steam thermoblock")):
        figure = figures[side]
        run_ = figure["run"]
        corner = run_["corner"]
        write("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            label, _temperature(figure["peak_c"]), _temperature(figure["sensing_error_c"]),
            _temperature(figure["figure_c"]), run_["peak_phase"], _corner_label(corner),
            run_["kind"], _coefficient(corner),
            NOTHING if corner is None else corner["end"]))
    write("")
    for side, label in ((COFFEE, "coffee"), (STEAM, "steam")):
        run_ = figures[side]["run"]
        corner = run_["corner"]
        write("The %s thermoblock's peak is reached in its %s phase, at interval %d of a course "
              "of %d, %s, %s." % (
                  label, run_["peak_phase"], run_["peak_at"], run_["intervals"],
                  "at the machine's declared coefficients" if corner is None else
                  "at corner %d (%s, %s end)" % (corner["which"], _coefficient(corner),
                                                 corner["end"]),
                  "commanded at %s C%s" % (
                      _temperature(run_["target_c"]),
                      " (the pump at %d permille)" % run_["peak_level"] if run_["peak_level"]
                      and side == COFFEE else "")))
    write("")

    write(PHASES_HEADING)
    write("")
    write("For each phase, the hottest casting any run reached in it, and the run that reached "
          "it. The peak above is the largest of these.")
    write("")
    write("| Thermoblock | Phase | Peak (C) | Corner | Served |")
    write("|---|---|---|---|---|")
    for side, label in ((COFFEE, "Coffee thermoblock"), (STEAM, "Steam thermoblock")):
        for phase in PHASES:
            best = None
            for run_ in findings["runs"]:
                if run_["side"] != side:
                    continue
                for found in run_["phases"]:
                    if found["phase"] == phase and (best is None or found["peak_c"] > best[0]):
                        best = (found["peak_c"], run_)
            if best is None:
                write("| %s | %s | %s | %s | %s |" % (label, phase, NOTHING, NOTHING, NOTHING))
                continue
            write("| %s | %s | %s | %s | %s |" % (
                label, phase, _temperature(best[0]), _corner_label(best[1]["corner"]),
                best[1]["kind"]))
    write("")

    write(CORNERS_HEADING)
    write("")
    write("Every corner run, with the hottest casting it reached in any phase. A corner at the "
          "end `params/thermoblock.md` calls one-sided is run too and carries `not-claimed`: "
          "the description stands behind no machine there, and the peak is included all the "
          "same because it can only raise a safety figure. Every corner the enumeration "
          "covers is run: the tool refuses to write this record when one produces no machine.")
    write("")
    write("| Thermoblock | Served | Target (C) | Corner | Coefficient | End | Written at | "
          "Claimed | Hold (C) | Peak (C) | Phase |")
    write("|---|---|---|---|---|---|---|---|---|---|---|")
    for run_ in findings["runs"]:
        corner = run_["corner"]
        write("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            "Coffee" if run_["side"] == COFFEE else "Steam", run_["kind"],
            _temperature(run_["target_c"]), _corner_label(corner), _coefficient(corner),
            NOTHING if corner is None else corner["end"],
            NOTHING if corner is None else margin.FIGURE_FORMAT % corner["factor"],
            "claimed" if corner is None or not margin.the_end_the_description_does_not_claim(corner)
            else "not-claimed",
            _temperature(run_["hold_c"]), _temperature(run_["peak_c"]), run_["peak_phase"]))
    write("")

    write(STEAM_LENGTH_HEADING)
    write("")
    write("The steam courses above hold the wand open for %d seconds, about what a jug of milk "
          "takes. A draw has no end of its own, and the model's casting does not settle under "
          "one held longer than the feed can replace, so a longer draw can climb higher. The "
          "steam figure above is therefore the figure for a draw of that length and for no "
          "longer one; the table shows where a longer draw does and does not rise. The hottest "
          "casting temperature over the draw, at the machine's declared coefficients with the "
          "ready temperature at %s C, by how long the wand is held:" % (
              STEAM_DRAW_SECONDS[0], _temperature(findings["steam_ready_c"])))
    write("")
    write("| Wand held open (s) | Peak casting temperature (C) |")
    write("|---|---|")
    for seconds, peak_c in findings["steam_lengths"]:
        write("| %d | %s |" % (seconds, _temperature(peak_c)))
    write("")

    write("## What this does not settle")
    write("")
    write("Whether the casting is where the model says it is. No casting on this machine has "
          "been instrumented, the declared errors the corners are taken from are judgements "
          "rather than readings, and the thermal masses and loss coefficients that set how far "
          "the casting runs ahead of the water leaving it are estimates.")
    write("")
    write("How long a steam draw lasts. The steam figure is for the draw the courses above "
          "open the wand for. The table above shows what a longer one does in the model, and "
          "nothing in this record says how long a draw the controller may be asked to hold.")
    write("")
    write("The trip points. This record stops at the hottest casting; the time a heater takes "
          "to climb from it to its protection's trip point is not derived here or in the "
          "controller boards' figures record, which only quotes this record's figures and "
          "keeps the interval pending. It is derived from this record's peak by "
          "SOL-PROOF-OF-LIFE-INTERVAL-DERIVED-FROM-HELD-CASTING-PEAK, once the control holds "
          "the casting below its trip point.")
    return "\n".join(lines) + "\n"


# --- Whether a committed record still describes what it was run against ----


def input_paths(findings):
    """The files a run was generated from, in the order the record lists them."""
    return [findings[key] for _, key in INPUTS]


def default_inputs():
    """The files the method reads when it is not pointed at others, without
    running it."""
    description, limits = cross_tier.carried_declarations()
    return input_paths({"description": description, "limits": limits,
                        "tolerance": sweep.TOLERANCE_DECLARATION,
                        "declaration": sweep.STEAM_CONTROL_DECLARATION})


def recorded_inputs(text):
    """The files a committed record says it was generated from, as
    (path, sha256) in the order its 'What was run' table lists them."""
    return [(row[1].strip("`"), row[2].strip("`")) for row in _table_rows(text, RUNS_HEADING)
            if len(row) == 3 and re.fullmatch(r"`[0-9a-f]{64}`", row[2])]


def stale_inputs(text, paths):
    """What keeps a committed record from describing the files it would be
    generated from now.

    Each file is held to its own row of the record's table, by path and by
    digest, so a digest printed in prose or against another file's row does not
    count. A file with no row, or a row whose digest is not the file's present
    one, is returned as the path; a row for a file the generator does not read
    is returned as the path the record names. An empty result is a record that
    lists exactly the inputs read, each at its present content, comment or not.
    """
    recorded = recorded_inputs(text)
    wanted = [(_relative(path), path) for path in paths]
    stale = [path for relative, path in wanted
             if (relative, sweep.digest_of(path)) not in recorded]
    known = {relative for relative, _ in wanted}
    return stale + [relative for relative, _ in recorded if relative not in known]


def reported_castings(output, channel):
    """Every casting temperature a draw's output reports, read straight off its
    lines.

    Independent of the trajectory parsing the runs go through, so that a peak
    taken over a parsed series can be held against what the artefact printed.
    """
    prefix = channel + "="
    found = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith(("HOST trajectory ", "HOST steam-trajectory ")):
            continue
        for word in line.split():
            if word.startswith(prefix):
                found.append(float(word[len(prefix):]))
    return found


# --- Reading a committed record back ---------------------------------------


def _table_rows(text, heading):
    """Every table row under one heading of a committed record."""
    return margin._table_rows(text, heading)


def figure_rows(text):
    """The peak table of a committed record, one row per thermoblock, as
    (thermoblock, peak, sensing error, figure, phase, corner, served, coefficient, end)."""
    return [tuple(row) for row in _table_rows(text, FIGURES_HEADING)
            if len(row) == 9 and row[0] not in ("Thermoblock", "---")]


def phase_rows(text):
    """The per-phase table of a committed record, as (thermoblock, phase, peak,
    corner, served)."""
    return [tuple(row) for row in _table_rows(text, PHASES_HEADING)
            if len(row) == 5 and row[0] not in ("Thermoblock", "---")]


def length_rows(text):
    """The steam draw-length table of a committed record, as (seconds, peak)."""
    return [tuple(row) for row in _table_rows(text, STEAM_LENGTH_HEADING)
            if len(row) == 2 and row[0] not in ("Wand held open (s)", "---")]


def corner_rows(text):
    """The per-corner table of a committed record, as (thermoblock, served,
    target, corner, coefficient, end, written at, claimed, hold, peak, phase)."""
    return [tuple(row) for row in _table_rows(text, CORNERS_HEADING)
            if len(row) == 11 and row[0] not in ("Thermoblock", "---")]


def _figures_record_rows(text):
    """Every table row under the figures record's proof-of-life interval section."""
    section = []
    within = False
    for line in text.splitlines():
        if line.startswith("### "):
            within = line.strip() == FIGURES_RECORD_SECTION
            continue
        if within and line.startswith("| "):
            section.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return section


def quoted_peaks(text, labels=(("Coffee thermoblock", COFFEE), ("Steam thermoblock", STEAM))):
    """The peak each thermoblock's row of the controller boards' figures record
    quotes, as the text it is written as, keyed by side.

    The figures record carries the same two columns as this tool's record
    under the same row labels, so what it quotes can be held against what this
    record gives: the peak itself, and the declared sensing error and sum
    beside it.
    """
    section = _figures_record_rows(text)
    quoted = {}
    for row in section:
        for label, side in labels:
            if row and row[0] == label and len(row) >= 4:
                quoted[side] = tuple(row[1:4])
    return quoted


def quoted_origins(text, labels=(("Coffee thermoblock", COFFEE), ("Steam thermoblock", STEAM))):
    """The 'where it comes from' cell each thermoblock's row of the controller
    boards' figures record gives, keyed by side."""
    section = _figures_record_rows(text)
    return {side: row[4] for row in section for label, side in labels
            if row and row[0] == label and len(row) >= 5}


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--description", default=None,
                        help="the parameter description to run the machine from")
    parser.add_argument("--limits", default=None,
                        help="what a reading off that machine may be")
    parser.add_argument("--tolerance", default=sweep.TOLERANCE_DECLARATION,
                        help="the bands a delivery is held to")
    parser.add_argument("--steam-declaration", default=sweep.STEAM_CONTROL_DECLARATION,
                        help="the figures the steam control law is given")
    parser.add_argument("--report", default=REPORT_PATH, help="where the record is written")
    parser.add_argument("--stdout", action="store_true",
                        help="print the record rather than writing it")
    parser.add_argument("--pio", default=base.DEFAULT_PIO,
                        help="the PlatformIO executable the host artefact is built with")
    parser.add_argument("--workspace", default=BUILD_DIR,
                        help="where this run's own descriptions and courses are written")
    arguments = parser.parse_args(argv)

    findings = run(description=arguments.description, limits=arguments.limits,
                   tolerance=arguments.tolerance, declaration=arguments.steam_declaration,
                   pio=arguments.pio, workspace=arguments.workspace)
    record = report_text(findings)
    if arguments.stdout:
        sys.stdout.write(record)
    else:
        with open(arguments.report, "w", encoding="utf-8") as handle:
            handle.write(record)
        print("%s written: coffee casting peaks at %s C, steam at %s C, over %d runs" % (
            arguments.report, _temperature(findings["figures"][COFFEE]["figure_c"]),
            _temperature(findings["figures"][STEAM]["figure_c"]), len(findings["runs"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
