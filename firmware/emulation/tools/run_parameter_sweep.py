#!/usr/bin/env python3
"""Perturb every coefficient the machine's description says it may be wrong
about, re-run both closed loops, and rank the coefficients by how much of the
declared delivery margin each one's own uncertainty is already spending.

Two things this needs are already in place and neither is restated here. The
description carries, against every value, the fraction of that value the design
is entitled to assume it may be out by -- an uncertainty budget the build
already refuses a description for going without. And both sides the machine
serves already have a closed loop that can be run on the host against a
description named from outside it: the brew side's through
src/app/native/cross_tier_draw.c, the steam side's through
src/app/native/steam_draw.c. What is added here is the sweep between them.

For each coefficient in turn, every other coefficient is held where the
description puts it and the one under test is written out at both ends of its
own declared error. Both corners rather than one, because an error is a
two-sided statement and a relation that is gentle in one direction and steep in
the other would be reported at whichever end happened to be picked. Both loops
are then run against each corner and against the description untouched, and what
is recorded is how far the delivery moved.

What "how far" means is the declared margin and not a raw number of degrees or
bar, and that is what lets one ranking cover both sides rather than two that
cannot be compared. The brew loop is judged on the temperature of the water
reaching the group, against the half-width params/tolerance.declaration states
for it; the steam loop is judged on the pressure of the steam coming out,
against the half-width the floor and ceiling in params/steam_control.declaration
imply. Both are what the design has declared it is holding the delivery to, so a
deviation expressed as a fraction of one is the same kind of statement as a
deviation expressed as a fraction of the other -- where a tenth of a degree
against a twentieth of a bar is not.

That fraction of the declared band *is* the ranking figure, and it is not
divided by anything further. It is called dominance here because it answers the
question the ranking exists for: of the margin the design has declared it holds
this delivery inside, how much is one coefficient's own present uncertainty
already spending? A coefficient whose declared error alone walks the delivery
most of the way to the edge of its band is the one worth measuring next,
whatever relation it happens to sit in, because the margin it is spending is
margin nothing else can then use.

Dividing that fraction by the coefficient's declared error -- which reads as the
obvious way to put a coefficient known to a hair and one known only roughly onto
the same footing -- would be the wrong figure here, and wrong in a way that is
easy to miss because it looks like a normalisation. The deviation was produced
by moving the coefficient at exactly its declared error, so it already carries
that error inside it: deviation is about sensitivity times declared error, and
dividing by the declared error again leaves sensitivity on its own. That is a
statement about the model -- how steeply the delivery answers this relation, per
unit of relative movement in it -- and it is deliberately blind to how well the
coefficient is presently known, which is the one thing the ranking is being
asked about. Order on it and a coefficient the description already pins tightly
can be lifted over one it admits to being badly out on, purely because the first
sits in the steeper relation -- when the second is the one presently eating the
margin and the first is already known well enough not to be. Prioritising
measurement off that order sends the money at the parameter that needs it least,
which is the one outcome this ranking exists to prevent.

The sensitivity figure is still reported beside the dominance one, because the
two answer different questions and a reader is entitled to both: dominance says
where the margin is going today, sensitivity says how much would be bought by
knowing that coefficient better than it is. A coefficient high on one and low on
the other is exactly the case worth reading twice.

Not every coefficient can be given a figure at all, and the ones that cannot are
kept out of the ranking rather than set at its foot. A coefficient the
description declares no error against, or declares an error of nothing against,
has nothing for the sweep to move it by; a coefficient whose perturbation moves
no quantity the design declares a band for has nothing for a deviation to be a
fraction of. Either way there is no dominance figure to be had, and a row
carrying a figure of nothing would say the opposite of what is true: a reader
running down a ranked list looking for what matters least would find it at the
bottom and read it as a coefficient that barely matters, where what is actually
the case is that nothing here can judge it either way. Those go into an account
of their own, each named with which of the three left it there.

Nothing here decides whether a ranking is good news. What runs the sweep and
what judges it are deliberately not the same thing, on the terms every other
runner in this directory is written on.
"""

import argparse
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))
REPOSITORY_DIR = os.path.abspath(os.path.join(FIRMWARE_DIR, ".."))

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FIRMWARE_DIR, "tools"))

import check_assumed_error as assumed_error  # noqa: E402
import check_parameter_origins as origins  # noqa: E402
import run_closed_loop_check as closed_loop  # noqa: E402
import run_cross_tier_check as cross_tier  # noqa: E402
import run_emulation_check as base  # noqa: E402

#: Where the seam's own headers live, which is where the vocabulary an origin
#: and an assumed error are written in is declared. Read through the build-time
#: checks' own readers rather than by a pattern of this file's, so that what
#: counts as a declared error here and what counts as one at the gate cannot
#: come to be two different answers.
INCLUDE_DIR = os.path.join(FIRMWARE_DIR, "include")

#: The design's own policy figures for the steam side, which the steam loop is
#: given rather than compiled with, and the bands a delivery is held to. Neither
#: is perturbed by this sweep and both are named so a caller can point the sweep
#: at a machine whose design figures differ: what is under test here is the
#: description of a casting, and holding the design's own choices fixed while
#: the casting moves is what makes the answer a statement about the casting.
STEAM_CONTROL_DECLARATION = os.path.join(FIRMWARE_DIR, "params", "steam_control.declaration")
TOLERANCE_DECLARATION = os.path.join(FIRMWARE_DIR, "params", "tolerance.declaration")

#: Where the ranking and the account of how it was arrived at are kept.
REPORT_PATH = os.path.join(REPOSITORY_DIR, "docs", "parameter-dominance.md")

#: Where the sweep's own working files are written: the perturbed descriptions
#: and the course files. Under the host build's own directory because they are
#: inputs to that artefact's runs and to nothing else.
BUILD_DIR = os.path.join(FIRMWARE_DIR, ".pio", "build", cross_tier.HOST_ENVIRONMENT, "sweep")

#: The interval every run in this sweep is stepped at, in milliseconds. It is
#: the cadence the control logic declares it runs at; a sweep run at another one
#: would be asking what a machine does under a loop nobody is building.
INTERVAL_MS = cross_tier.DECLARED_INTERVAL_MS

# --- The brew side's course ------------------------------------------------
#
# The temperature the draw asks for. An ordinary brew temperature rather than
# the figure the cross-tier comparison commands, and the difference is the point
# of this being a course of its own: that run is affordable only if it stays
# short, so it asks for something a cold block reaches inside three seconds of
# simulated time and says in its own comments that it is not a claim about a
# drinkable shot. This run is host-native throughout and costs a twentieth of a
# second, so it can afford to ask the machine for the drink it is actually being
# built to make -- and what a coefficient's uncertainty costs is a question
# about the state the machine delivers from, not about the state it passes
# through on the way there.
BREW_TARGET_C = 93.0

# The machine is brought to that state with water moving rather than standing.
# With the pump off, the water on its way to the group reaches the block by
# conduction alone and sits tens of kelvin behind it, so the loop drives at its
# ceiling for the whole of any affordable run and then overshoots the target by
# some twenty degrees on the way down -- a loop pinned at a limit is one whose
# reading changes nothing it commands, and a sweep taken across that would be
# measuring an open loop. A steady trickle is what a machine of this kind is
# flushed with before a shot, and it is what brings the group to the block. Five
# thousand intervals is fifty seconds, which is where the loop settles from cold
# at the declared coefficients with room to spare.
BREW_FLUSH_STEPS = 5000
BREW_FLUSH_PERMILLE = 200

# Then the shot itself, as a shape and not a held level, in the five phases the
# emulated loop's own draw declares: nothing new is asked while the puck wets,
# the pump ramps on, holds, tapers off, and the machine is left standing. The
# figures are that draw's proportions carried onto this one's longer clock.
#
# What the hold is drawn at is the one figure here that is not a proportion, and
# it is taken from the description's own account of the machine rather than
# chosen: brew.outlet_held_volume_ml reasons about "the two-and-a-bit
# millilitres per second a shot is actually drawn at", which against the seven
# millilitres a second the same file declares at full pump scale is a little
# under a third of it. That it is also inside what this machine can hold at a
# brew temperature is not a coincidence and is worth stating: a kilowatt raising
# water from the declared feed temperature to the declared target runs out at
# something over three millilitres a second, so a course drawn much harder than
# this would sit the loop at its ceiling for the whole of the hold -- and a loop
# at its ceiling is one whose reading changes nothing it commands, which is a
# sweep over an open loop wearing a closed loop's name.
BREW_PRE_INFUSION_STEPS = 400
BREW_PRE_INFUSION_PERMILLE = 100
BREW_RAMP_STEPS = 300
BREW_HOLD_STEPS = 1200
BREW_TAPER_STEPS = 300
BREW_REST_STEPS = 300
BREW_PEAK_PERMILLE = 300

# --- The steam side's course -----------------------------------------------
#
# The block is started at the ready state the design declares it holds, read out
# of that declaration rather than written here, and given time to settle there
# before anything is asked of it -- the same thirty seconds the steam law's own
# suite gives it, and for the same reason: what the span is for is the loop
# trimming whatever its declared standing-load feedforward does not exactly
# answer, not for heating a cold machine.
STEAM_SETTLE_STEPS = 3000

# Then the wand is opened for twenty seconds, which is about what a jug of milk
# takes, and shut again with the machine left standing. The rate is one
# millilitre of water turned to vapour per second, which is the rate the steam
# law's own band tests draw at -- taken from there rather than chosen afresh, so
# that the machine this sweep leans on is the one that design was established
# against.
STEAM_DRAW_STEPS = 2000
STEAM_DEMAND_MILLI_ML_PER_S = 1000
STEAM_REST_STEPS = 500

#: How the two sides are named wherever the sweep reports one of them.
BREW_SIDE = "brew"
STEAM_SIDE = "steam"

#: What each side is judged on, and the unit that judgement is in.
JUDGED = {
    BREW_SIDE: ("the temperature of the water reaching the group", "C"),
    STEAM_SIDE: ("the pressure of the steam being drawn", "bar"),
}

#: The channels of the machine a perturbation's effect is recorded on, in the
#: order everything downstream reads them.
#:
#: The four the two tiers already compare themselves on, plus the rate the brew
#: path is drawing at. The first four are the ones a converter carries; the
#: fifth is a channel the seam enumerates and this board has nothing wired to,
#: and it is here for exactly that reason -- a channel no instrument sits on is
#: where the question of whether one would buy anything is decided, and it
#: cannot be decided about a channel nothing recorded.
#:
#: The steam knob is deliberately absent, and it is the one seam channel that
#: could never belong here. It reports where an operator has put a valve, which
#: no coefficient of a casting can move; a column for it would be a column of
#: nothing beside four that mean something, and would read as a channel this
#: analysis looked at and found unmoved rather than one it could not have been
#: asked about.
OBSERVED_CHANNELS = closed_loop.QUANTITY_KEYS + (cross_tier.FLOW_KEY,)

#: What each observed channel is carried in, for a record that has to put a
#: figure beside a unit.
CHANNEL_UNIT = {
    "brew-c": "C",
    "steam-c": "C",
    "brew-bar": "bar",
    "steam-bar": "bar",
    cross_tier.FLOW_KEY: "mL/s",
}

#: The words the two declarations spell their bands with, read out of the
#: headers that declare them rather than written here. A band renamed in a
#: header and not here would otherwise leave this sweep normalising against a
#: band it silently failed to find.
TOLERANCE_HEADER = os.path.join(INCLUDE_DIR, "delivery_tolerance.h")
STEAM_DECLARATION_HEADER = os.path.join(INCLUDE_DIR, "steam_control_declaration.h")
BREW_BAND_MACRO = "DELIVERY_TOLERANCE_BREW_TEMPERATURE_WORD"
STEAM_FLOOR_MACRO = "STEAM_CONTROL_DECLARATION_DRAW_FLOOR_WORD"
STEAM_CEILING_MACRO = "STEAM_CONTROL_DECLARATION_DRAW_CEILING_WORD"

#: The three ways a coefficient reaches the end of this tool without a dominance
#: figure. Each is a statement about what the ranking needed and did not have --
#: something to perturb the coefficient by, or a declared band for the
#: perturbation's effect to be a fraction of -- and each is written into the
#: record beside the coefficient it kept out, because "could not be weighed" and
#: "was weighed and came last" are opposite findings that read alike from a
#: table.
NO_DECLARED_ERROR = "carries no declared error to perturb it by"
ERROR_DECLARED_AS_NOTHING = "carries an error declared as nothing"
NO_BANDED_QUANTITY_REACHED = "reaches no quantity carrying a declared band"

#: How the ranking's figures are written into the report. Three significant
#: figures, which is more than a sweep over a description whose own errors run
#: from two per cent to eighty can support and fewer than a difference in the
#: last place of a single-precision model would move.
FIGURE_FORMAT = "%.3g"

#: How a perturbed coefficient is written into the description handed to the
#: machine. Nine significant figures, which is what round-trips the single
#: precision every coefficient is loaded into. It is deliberately not the format
#: the report is written in: a perturbation rounded to what a reader wants to
#: see would be a different machine from the one the declared error names, and
#: the sweep would be reporting the sensitivity to a figure nobody declared.
VALUE_FORMAT = "%.9g"


class SweepError(RuntimeError):
    """The sweep could not be run, or could not be run over everything it covers."""


# --- Reading what the description says it may be wrong about ---------------


def _vocabularies():
    """The two annotation vocabularies a description is written in.

    Both are loaded through the build-time checks' own readers. A second reader
    here would be a second opinion about what an origin is, what an assumed
    error is, and therefore about which coefficients this sweep even covers --
    and the two would eventually disagree in the direction that leaves a
    coefficient unswept while both of them go on reporting success.
    """
    vocabulary, problems = origins.load_vocabulary(INCLUDE_DIR)
    if vocabulary is None:
        raise SweepError("; ".join(problems))
    marker, problems = assumed_error.load_marker(INCLUDE_DIR, vocabulary.marker)
    if marker is None:
        raise SweepError("; ".join(problems))
    return vocabulary, marker


def nominal_values(path, vocabulary, marker):
    """Coefficient name -> the value the description states for it.

    Neither reader borrowed above keeps the value itself: one exists to
    establish that an origin was recorded and the other that an assumed error
    was, and neither has ever needed the number. So the value is read here --
    but read by cutting the line at the same two markers those readers cut it
    at, because where a value ends and its account of itself begins is exactly
    the thing two readers must not hold separate opinions about.
    """
    values = {}
    for number, raw in enumerate(origins.read(path).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(vocabulary.marker):
            continue
        if "=" not in line:
            continue
        name, remainder = line.split("=", 1)
        cuts = [at for at in (remainder.find(marker), remainder.find(vocabulary.marker))
                if at >= 0]
        if cuts:
            remainder = remainder[:min(cuts)]
        try:
            values[name.strip()] = float(remainder.strip())
        except ValueError:
            raise SweepError(
                "%s:%d: '%s' states a value the sweep cannot read as a number, which the "
                "machine's own loader would refuse too" % (path, number, name.strip()))
    return values


def swept_coefficients(path):
    """What the sweep covers, and what it does not with the reason why.

    Returns a pair: an ordered list of (name, nominal, fraction) for every
    coefficient this sweep will perturb, and a list of (name, condition, why)
    for every one it will not. The second is returned rather than dropped
    because a coefficient silently left out of a dominance ranking reads exactly
    like one that was ranked and came last.

    Only the two conditions that can be seen from the description alone are
    decided here -- nothing to perturb by, and nothing to take a fraction of.
    The third, a perturbation that reaches no quantity carrying a declared band,
    is not visible until the perturbation has been run, and is decided in `run`.
    """
    vocabulary, marker = _vocabularies()
    declared = assumed_error.Description(path, vocabulary, marker)
    if declared.exempt:
        raise SweepError(
            "%s says it describes no real machine, so there is no delivery for a perturbation "
            "of it to move and nothing to rank" % path)

    values = nominal_values(path, vocabulary, marker)

    covered = []
    unweighed = []
    for name, (number, fraction_text) in declared.values.items():
        if fraction_text is None:
            unweighed.append((name, NO_DECLARED_ERROR,
                            "the description records where the value came from and not what it "
                            "may be out by, so there is no movement of it this sweep is entitled "
                            "to make and nothing to weigh its sensitivity against"))
            continue
        wrong = assumed_error.inadmissible(fraction_text)
        if wrong is not None:
            raise SweepError("%s:%d: '%s' %s" % (path, number, name, wrong))
        fraction = float(fraction_text)
        if fraction == 0.0:
            unweighed.append((name, ERROR_DECLARED_AS_NOTHING,
                            "the description declares it exact, so there is nothing to perturb it "
                            "by and its own uncertainty spends none of any margin"))
            continue
        if name not in values or values[name] == 0.0:
            unweighed.append((name, ERROR_DECLARED_AS_NOTHING,
                            "the description states the value as nothing, so the fraction of it "
                            "the declared error names is also nothing and no perturbation of it "
                            "exists"))
            continue
        covered.append((name, values[name], fraction))

    if not covered:
        raise SweepError(
            "%s carries no coefficient with a declared error to perturb, so this sweep would "
            "report a ranking of nothing while appearing to have run" % path)
    return covered, unweighed


# --- Reading the bands the two deliveries are held to ----------------------


def _declared_word(header, macro):
    """The word one header declares a figure is written under."""
    words = dict(origins._DEFINE_STRING.findall(origins.read(header)))
    if macro not in words:
        raise SweepError("%s declares no %s, so the band it names cannot be found" %
                         (header, macro))
    return words[macro]


def _declared_figure(path, word):
    """The figure a declaration states under one word, as a whole number of the
    thousandths every one of these files is written in."""
    pattern = re.compile(r"^\s*%s\s*=\s*(-?\d+)\b" % re.escape(word), re.MULTILINE)
    found = pattern.search(origins.read(path))
    if found is None:
        raise SweepError("%s declares no '%s'" % (path, word))
    return int(found.group(1))


def brew_band_c(tolerance=TOLERANCE_DECLARATION):
    """The half-width the brew delivery is held inside, in degrees.

    It is stated as a half-width in the declaration itself, so it is used as one
    here. Reading it as a span would report every deviation as costing half what
    it actually costs of the margin.
    """
    return _declared_figure(tolerance, _declared_word(TOLERANCE_HEADER, BREW_BAND_MACRO)) / 1000.0


def steam_band_bar(declaration=STEAM_CONTROL_DECLARATION):
    """The half-width the steam delivery is held inside, in bar.

    The steam side declares its band as two edges rather than as a distance from
    a target, because what it holds is a span the delivered pressure has to stay
    within rather than a command it has to track. Half the distance between them
    is the same quantity the brew band states directly: how far a delivery may
    sit from the middle of what the design says is acceptable before it has
    spent the whole of its margin.
    """
    floor = _declared_figure(declaration, _declared_word(STEAM_DECLARATION_HEADER,
                                                         STEAM_FLOOR_MACRO))
    ceiling = _declared_figure(declaration, _declared_word(STEAM_DECLARATION_HEADER,
                                                           STEAM_CEILING_MACRO))
    if ceiling <= floor:
        raise SweepError(
            "%s declares a band whose ceiling is not above its floor, so there is no margin for "
            "a perturbation to spend" % declaration)
    return (ceiling - floor) / 2.0 / 1000.0


def steam_ready_temperature_c(declaration=STEAM_CONTROL_DECLARATION):
    """The block temperature the design holds the steam side at while idle.

    Where the steam draw starts the machine, read out of the declaration the
    loop is itself given rather than written into this file. A second copy here
    would be free to drift from the state the loop is actually holding to, and a
    draw begun somewhere the loop does not hold is a draw whose first seconds
    are the loop travelling rather than the machine delivering.
    """
    word = _declared_word(STEAM_DECLARATION_HEADER, "STEAM_CONTROL_DECLARATION_READY_TEMPERATURE_WORD")
    return _declared_figure(declaration, word) / 1000.0


# --- The two courses -------------------------------------------------------


def brew_course():
    """The brew side's course, as (interval, pump level) per control interval."""
    levels = [BREW_FLUSH_PERMILLE] * BREW_FLUSH_STEPS
    levels += [BREW_PRE_INFUSION_PERMILLE] * BREW_PRE_INFUSION_STEPS
    levels += [int(round(BREW_PEAK_PERMILLE * float(at + 1) / BREW_RAMP_STEPS))
               for at in range(BREW_RAMP_STEPS)]
    levels += [BREW_PEAK_PERMILLE] * BREW_HOLD_STEPS
    levels += [int(round(BREW_PEAK_PERMILLE * (1.0 - float(at + 1) / BREW_TAPER_STEPS)))
               for at in range(BREW_TAPER_STEPS)]
    levels += [0] * BREW_REST_STEPS
    return [(INTERVAL_MS, level) for level in levels]


def brew_judged_window(course):
    """Which intervals of the brew course the delivery is judged over.

    Every interval the shot is being drawn on, and none of the flush that
    brought the machine there or the rest that follows. The band this side is
    held to answers how far the water reaching the coffee sits from what was
    asked for, and there is no coffee being made while the machine is warming
    up -- a sweep that averaged the warm-up in would be ranking coefficients by
    what they do to a machine nobody is drinking from.
    """
    return [at for at in range(BREW_FLUSH_STEPS, len(course)) if course[at][1] > 0]


def steam_course():
    """The steam side's course, as (interval, demanded rate) per control interval."""
    demand = [0] * STEAM_SETTLE_STEPS
    demand += [STEAM_DEMAND_MILLI_ML_PER_S] * STEAM_DRAW_STEPS
    demand += [0] * STEAM_REST_STEPS
    return [(INTERVAL_MS, rate) for rate in demand]


def steam_judged_window(course, trajectory):
    """Which intervals of the steam draw the delivery is judged over.

    From the first interval on which feed actually engaged through to the last
    on which the wand was open. The window starts where steam is first delivered
    rather than where the wand turned, which is the band's own boundary: what
    the band states is the character of the steam coming out, and until feed
    engages there is none coming out to have a character. The interval before
    that is the block earning the thermal margin the first steam is made out of,
    which the steam law's own criteria assert about separately.

    The window is taken from the run it is measured against rather than from the
    perturbed one. Where feed engages moves a little with the coefficients, and
    a window that moved with it would be comparing two different stretches of
    two different draws.
    """
    last_drawing = max(at for at in range(len(course)) if course[at][1] > 0)
    engaged = [reported["interval"] for reported in trajectory
               if reported["feed_permille"] > 0 and reported["interval"] <= last_drawing]
    if not engaged:
        raise SweepError(
            "the steam draw never fed the block, so nothing was delivered and there is no "
            "delivery for a perturbation to have moved")
    return list(range(min(engaged), last_drawing + 1))


# --- Running one draw of each side ------------------------------------------


def build_host(pio=base.DEFAULT_PIO):
    """The host artefact both loops are run through."""
    return cross_tier.build_host(pio)


def observed_series(findings):
    """What each channel the machine observes carried, interval by interval,
    over one draw.

    One reading of the trajectory for both draws, because the two report the
    same channels under the same names and a second reading here would be a
    second opinion about which column is which. The four a converter carries are
    taken through the parser that already knows their order; the drawn rate is
    taken from the field beside them, since no converter carries it and it is
    printed outside that set for that reason.
    """
    series = dict((key, []) for key in OBSERVED_CHANNELS)
    for reported in findings["trajectory"]:
        for at, key in enumerate(closed_loop.QUANTITY_KEYS):
            series[key].append(reported["quantities"][at])
        series[cross_tier.FLOW_KEY].append(reported["brew_flow_ml_per_s"])
    return series


def brew_draw(executable, description, limits, course, scale, name, control_description=None):
    """One brew draw, and the delivered temperature it produced per interval.

    `control_description` is carried through to the draw untouched: it names the
    description the loop's control path reconstructs from, and left off the
    machine's own is used for both. What it is for is stated where the draw
    itself takes it, and nothing about how a delivery is read off the run
    changes with it.
    """
    findings = cross_tier.host_draw(executable, description, limits, BREW_TARGET_C, course,
                                    scale, name=name, control_description=control_description)
    delivered = [reported["outlet_c"] for reported in findings["trajectory"]]
    if any(value is None for value in delivered):
        raise SweepError(
            "the brew draw reported no delivered temperature, so this build's structure keeps no "
            "state for the water on its way to the group and there is no delivery here to judge")
    findings["delivered"] = delivered
    findings["channels"] = observed_series(findings)
    return findings


def parse_steam(output):
    """Turn the steam draw's `HOST ` lines into the record the sweep reads."""
    findings = {
        "trajectory_baseline": [],
        "trajectory": [],
        "settling_steps": None,
        "plant_step_count": None,
        "draw_intervals": None,
        "completed": False,
    }
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("HOST "):
            continue
        parts = line.split()[1:]
        kind = parts[0]
        if kind == "steam-trajectory-baseline":
            findings["trajectory_baseline"] = closed_loop.quantities_of(
                closed_loop.keyed(parts[1:]), "the steam loop's baseline")
        elif kind == "steam-trajectory":
            fields = closed_loop.keyed(parts[1:])
            where = "the steam loop's trajectory line %d" % len(findings["trajectory"])
            for name in ("interval", "result", "drawing", "demand", "heater", "feed", "steps",
                         cross_tier.FLOW_KEY):
                if name not in fields:
                    raise closed_loop.Unkeyed("%s reports no %s" % (where, name))
            findings["trajectory"].append({
                "interval": int(fields["interval"]),
                "result": int(fields["result"]),
                "drawing": int(fields["drawing"]) != 0,
                "demand_milli_ml_per_s": int(fields["demand"]),
                "heater_permille": int(fields["heater"]),
                "feed_permille": int(fields["feed"]),
                "plant_steps": int(fields["steps"]),
                "quantities": closed_loop.quantities_of(fields, where),
                # The brew path's drawn rate, which this draw never commands and
                # which is read all the same: a channel reported only where it
                # was expected to move cannot distinguish a path standing still
                # from a path nobody looked at, and which channels a coefficient
                # leaves alone is half of what its signature across them says.
                "brew_flow_ml_per_s": float(fields[cross_tier.FLOW_KEY]),
            })
        elif kind == "steam-settling-steps":
            findings["settling_steps"] = int(parts[1])
        elif kind == "steam-plant-step-count":
            findings["plant_step_count"] = int(parts[1])
        elif kind == "steam-draw-intervals":
            findings["draw_intervals"] = int(parts[1])
        elif kind == "done":
            findings["completed"] = True
    return findings


def steam_draw(executable, description, limits, declaration, initial_c, course, name):
    """One steam draw, and the delivered pressure it produced per interval."""
    course_file = cross_tier.write_course(course, os.path.join(BUILD_DIR, "%s-course.txt" % name))
    completed = base.subprocess.run(
        [executable, description, limits, "--steam-draw", declaration,
         repr(float(initial_c)), course_file],
        cwd=FIRMWARE_DIR, stdin=base.subprocess.DEVNULL, capture_output=True, text=True)

    findings = parse_steam(completed.stdout)
    findings["executable"] = executable
    findings["description"] = description
    findings["limits"] = limits
    findings["declaration"] = declaration
    findings["course_file"] = course_file
    findings["returncode"] = completed.returncode
    findings["stdout"] = completed.stdout
    findings["stderr"] = completed.stderr
    if not findings["completed"]:
        raise SweepError(
            "the steam draw did not finish. Its output follows:\n%s\n%s"
            % (completed.stdout[-8000:], completed.stderr[-4000:]))

    steam_bar = closed_loop.QUANTITY_KEYS.index("steam-bar")
    findings["delivered"] = [reported["quantities"][steam_bar]
                             for reported in findings["trajectory"]]
    findings["channels"] = observed_series(findings)
    return findings


# --- What a perturbation did -----------------------------------------------


def worst_separation(reference, perturbed, window):
    """How far the two runs' deliveries came apart over the judged window, and
    where.

    The worst separation rather than an average of them, because a band is a
    bound and what spends a margin is the excursion that comes nearest to
    leaving it. An average would report a perturbation that sat still for most
    of a shot and stepped out of the band once as costing almost nothing.
    """
    if len(reference) != len(perturbed):
        raise SweepError(
            "the two runs covered %d and %d intervals, so there is no interval-by-interval "
            "separation to take" % (len(reference), len(perturbed)))
    worst = 0.0
    worst_at = None
    for at in window:
        apart = abs(perturbed[at] - reference[at])
        if worst_at is None or apart > worst:
            worst = apart
            worst_at = at
    if worst_at is None:
        raise SweepError("the judged window covers no interval, so nothing was compared")
    return worst, worst_at


def delivery_moved(reference, perturbed):
    """Whether a perturbation moved the delivery this side is judged on at all.

    The whole run rather than the judged window, and moved-at-all rather than
    moved-by-something-worth-reporting, because this is the question of whether
    a coefficient reaches a quantity the design declares a band for -- not of
    how much of that band it spent. The two are separate findings and the
    ranking treats them differently: a coefficient that reaches the delivery and
    spends none of its margin has been weighed and scored nothing, while one
    that never reaches it at all has not been weighed and cannot be. Both come
    back as a figure of nothing and only the first of them means what that
    figure appears to say.

    Exact inequality is the right comparison and not a tolerance: both series
    are read back from what one artefact printed, so a coefficient the delivery
    does not depend on produces the same characters and a coefficient it depends
    on at all does not.
    """
    return any(was != now for was, now in zip(reference, perturbed))


def reached_quantities(reference, perturbed):
    """Which of the quantities a draw reports came back moved by a perturbation.

    Every quantity the two tiers compare themselves on, judged or not. It is
    what lets the account of an unweighable coefficient say which it is: one
    whose relation reaches the machine's modelled state and stops at a quantity
    nothing declares a band for, or one that on these scenarios reaches nothing
    the sweep can see at all. Naming the first as though it were the second
    would hide a modelled effect behind a shrug.
    """
    moved = set()
    for was, now in zip(reference["trajectory"], perturbed["trajectory"]):
        for at, key in enumerate(closed_loop.QUANTITY_KEYS):
            if key not in moved and was["quantities"][at] != now["quantities"][at]:
                moved.add(key)
    return moved


def signature_of(corners, reference):
    """One coefficient's effect on the observed channels of one side, as one
    signed series per channel.

    Signed and interval by interval rather than a worst-case magnitude, because
    what this feeds is a comparison of one coefficient's effect against
    another's rather than a figure for how large it was. Two coefficients that
    move a channel by the same amount in opposite directions, or by the same
    amount at different moments of the same draw, are told apart by nothing an
    absolute worst case keeps -- and being told apart is the whole of the
    question this series exists to answer.

    The two corners are combined rather than one of them taken, and combined as
    half the difference between them rather than as a mean of two magnitudes:
    half of what separates the machine at the top of the coefficient's declared
    error from the machine at the bottom. That is the part of the response which
    is linear in the coefficient, and the linear part is the only part another
    coefficient's uncertainty could stand in for. A comparison that kept the
    curvature as well would be free to separate two coefficients on how
    differently their relations bend at their own corners -- a difference no
    observation of a machine sitting anywhere else could exploit, and therefore
    not identifiability but an artefact of where the sweep chose to look.

    The two corner runs are subtracted from one another directly rather than
    each being taken against the unperturbed run first. The two are the same
    quantity in exact arithmetic and not in this one: each figure is a
    single-precision value read back at nine significant digits, which
    round-trips it exactly, so one subtraction of two of them is exact in the
    double precision Python carries -- while subtracting the unperturbed run
    from each and then differencing rounds twice, and leaves the recorded
    signature carrying a last place of this file's arithmetic rather than the
    machine's. Since how small a difference may be believed is decided further
    on against what the machine's own arithmetic could express, a reader of that
    figure must not be reading this subtraction's rounding instead.

    Where one corner was refused as a machine, the other is taken against the
    unperturbed run instead. To first order that is the same quantity -- one
    declared error's worth of movement -- and taking it is what keeps a
    coefficient with an inadmissible corner inside the comparison rather than
    quietly outside it.
    """
    for corner, run in corners.items():
        if len(run[OBSERVED_CHANNELS[0]]) != len(reference["channels"][OBSERVED_CHANNELS[0]]):
            raise SweepError(
                "the %s corner covered %d intervals and the unperturbed run covered %d, so there "
                "is no interval-by-interval effect on the observed channels to take"
                % (corner, len(run[OBSERVED_CHANNELS[0]]),
                   len(reference["channels"][OBSERVED_CHANNELS[0]])))
    if "high" in corners and "low" in corners:
        return dict((key, [(high - low) / 2.0
                           for high, low in zip(corners["high"][key], corners["low"][key])])
                    for key in OBSERVED_CHANNELS)
    if "high" in corners:
        return dict((key, [high - was for high, was in zip(corners["high"][key],
                                                           reference["channels"][key])])
                    for key in OBSERVED_CHANNELS)
    return dict((key, [was - low for was, low in zip(reference["channels"][key],
                                                     corners["low"][key])])
                for key in OBSERVED_CHANNELS)


def peak_of(series):
    """The largest magnitude one series reached.

    Taken as the wider of the two extremes rather than by taking an absolute
    value of every element, which is the same figure and does not build a second
    series the size of the first to get it.
    """
    if not series:
        return 0.0
    return max(max(series), -min(series))


def could_not_be_weighed(entry):
    """Why a coefficient that was perturbed still has no dominance figure.

    Reached only for a coefficient neither delivery answered, and it says which
    of the two ways that happened -- the effect stopping at a quantity held to
    nothing, or no effect this sweep can see at all. The first is a finding
    about what the design declares bands for and the second about what these two
    scenarios exercise, and a reader deciding where to spend measurement effort
    needs to know which one they are looking at.
    """
    reached = sorted(entry["reaches"])
    if not reached:
        return ("neither end of its declared error moved any quantity either draw reports, so on "
                "these two scenarios the relation it sits in does not carry to the machine's "
                "delivered state at all")
    return ("its declared error moves %s, which the machine models in full and the design "
            "declares no band for. Nothing either delivery is judged against moved at all, so "
            "there is no margin here for this coefficient's uncertainty to be a fraction of"
            % ", ".join("`%s`" % key for key in reached))


def digest_of(path):
    """What a file this sweep was run against presently holds.

    Recorded beside the file's name because a name alone does not say which
    machine: the whole point of the record is that a replacement model can be
    swept by pointing the same method at it, and a report naming a path that has
    since been rewritten would read as current while describing a machine
    nobody has any more.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run(description=None, limits=None, declaration=STEAM_CONTROL_DECLARATION,
        tolerance=TOLERANCE_DECLARATION, pio=base.DEFAULT_PIO, executable=None,
        workspace=BUILD_DIR, control_description=None):
    """Sweep every coefficient carrying a declared error, and rank what it did.

    `description` and `limits` default to the two files the target build carries
    compiled in, which is what makes the ranking a statement about the machine
    this project is building rather than about whichever description happened to
    be lying about. They are arguments so that the same sweep can be pointed at
    a replacement model without anything here being edited, which is the whole
    of what makes the method repeatable.

    `workspace` is where the perturbed descriptions this run writes are put, and
    it is an argument for the same reason: two sweeps of two different models
    write a file per coefficient per corner under the same names, and sharing a
    directory would leave the second run's descriptions standing where the
    first's had been. Nothing reading a finished run would notice -- the
    findings are in memory by then -- but anything that goes back to the files
    to establish what a run actually handed the machine would be reading the
    other model's.

    `control_description` decides which of two questions the sweep is asking,
    and it is the one argument here that changes what the answer means rather
    than which machine it is about. Left off, every perturbed corner is handed
    to the machine and to the coffee side's control path alike: what is then
    compared is two machines each built consistently to its own coefficients,
    which is the question a commissioning check asks. Named, the control path is
    held at that one description for every run while the machine is perturbed
    away from it -- which is what fouling and ageing do to a machine whose
    controller nobody has re-measured, and it is the question a machine in
    service asks. Both are worth taking and neither answers the other, so the
    argument exists rather than one of the two being chosen here.

    Only the coffee side can be asked the second question, and the reason is
    structural rather than a limit of this sweep: the steam law is built from
    its own declaration and from no description of a casting at all, so there is
    nothing on that side for a perturbation to be kept out of. Its runs are made
    the same way whichever question is being asked, and a caller comparing two
    sweeps will find that side's figures standing exactly where they were.
    """
    carried_description, carried_limits = cross_tier.carried_declarations()
    description = description or carried_description
    limits = limits or carried_limits

    covered, unweighed = swept_coefficients(description)
    bands = {BREW_SIDE: brew_band_c(tolerance), STEAM_SIDE: steam_band_bar(declaration)}
    ready_c = steam_ready_temperature_c(declaration)

    scale = cross_tier.converter_scale()
    brew = brew_course()
    steam = steam_course()
    executable = executable or build_host(pio)

    os.makedirs(workspace, exist_ok=True)

    reference = {
        BREW_SIDE: brew_draw(executable, description, limits, brew, scale, "nominal-brew",
                             control_description=control_description),
        STEAM_SIDE: steam_draw(executable, description, limits, declaration, ready_c, steam,
                               "nominal-steam"),
    }
    windows = {
        BREW_SIDE: brew_judged_window(brew),
        STEAM_SIDE: steam_judged_window(steam, reference[STEAM_SIDE]["trajectory"]),
    }

    # The largest magnitude each channel carried anywhere in this sweep, on each
    # side. It is the coarsest last place that channel's own single-precision
    # arithmetic had over the runs being compared, and so the floor beneath
    # which a difference between two of those runs could not have been expressed
    # at all. Taken across the perturbed runs as well as the unperturbed one,
    # because a perturbation that carries a channel higher than the reference
    # ever went carries the floor up with it, and a floor read off the reference
    # alone would credit such a run with a resolution its own figures never had.
    peaks = dict((side, dict((key, peak_of(reference[side]["channels"][key]))
                             for key in OBSERVED_CHANNELS))
                 for side in (BREW_SIDE, STEAM_SIDE))

    swept = []
    for name, value, fraction in covered:
        entry = {
            "coefficient": name,
            "nominal": value,
            "fraction": fraction,
            "corners": {},
            "deviation": {},
            "dominance": {},
            "sensitivity": {},
            "reaches": set(),
            "moves_banded": set(),
            # Whether the perturbation moved the temperature of the water on its
            # way to the group. Kept apart from the entry above even though the
            # two presently agree on the coffee side, because they are different
            # statements about different things: one says the coefficient
            # reached a quantity the design declares a band for, the other that
            # it reached the state the control path reconstructs and drives on.
            # They coincide today only because the band this design declares for
            # the coffee side happens to be declared on that state, and a design
            # that banded the block's own temperature instead would have them
            # come apart with nothing here to notice.
            "reaches_outlet": False,
            "refused": [],
        }
        # What each corner's run carried on each channel, kept only until the two
        # are combined into the coefficient's signature below. The runs
        # themselves rather than their difference from the unperturbed one,
        # because the signature is taken as one subtraction of two of them and a
        # difference computed here first would round twice. Two corners of two
        # sides of five channels over several thousand intervals is a large
        # thing to hold for every coefficient at once, and nothing wants the
        # corners once the signature exists.
        cornered = dict((side, {}) for side in (BREW_SIDE, STEAM_SIDE))
        for corner, factor in (("low", 1.0 - fraction), ("high", 1.0 + fraction)):
            perturbed_value = value * factor
            entry["corners"][corner] = perturbed_value
            written = cross_tier.description_with(
                name, VALUE_FORMAT % perturbed_value,
                os.path.join(workspace, "%s-%s.params" % (name, corner)),
                source=description)
            for side in (BREW_SIDE, STEAM_SIDE):
                label = "%s-%s-%s" % (name, corner, side)
                try:
                    if side == BREW_SIDE:
                        # The perturbed description goes to the machine. Where a
                        # control description was named it does not go to the
                        # control path as well, which is the whole of what makes
                        # this a drifted machine rather than a differently built
                        # one.
                        run_findings = brew_draw(executable, written, limits, brew, scale, label,
                                                 control_description=control_description)
                    else:
                        run_findings = steam_draw(executable, written, limits, declaration,
                                                  ready_c, steam, label)
                except (SweepError, cross_tier.CrossTierError) as refusal:
                    # A corner the structure will not admit as a machine is a
                    # finding about the description's own declared error rather
                    # than a failure of the sweep, so it is recorded and the
                    # other corner still answers. A coefficient neither corner
                    # of which can be run is refused outright below, because a
                    # coefficient nothing perturbed has not been ranked.
                    entry["refused"].append((corner, side, str(refusal).splitlines()[0]))
                    continue
                entry["reaches"].update(reached_quantities(reference[side], run_findings))
                if delivery_moved(reference[side]["delivered"], run_findings["delivered"]):
                    entry["moves_banded"].add(side)
                    if side == BREW_SIDE:
                        # The coffee side's delivery is the water on its way to
                        # the group, which is the state the control path
                        # reconstructs -- so a corner that moved it is a corner
                        # whose coefficient that reconstruction rests on.
                        entry["reaches_outlet"] = True
                cornered[side][corner] = run_findings["channels"]
                for key in OBSERVED_CHANNELS:
                    peaks[side][key] = max(peaks[side][key],
                                           peak_of(run_findings["channels"][key]))
                apart, where = worst_separation(reference[side]["delivered"],
                                                run_findings["delivered"], windows[side])
                if side not in entry["deviation"] or apart > entry["deviation"][side][0]:
                    entry["deviation"][side] = (apart, corner, where)

        entry["signature"] = dict((side, signature_of(cornered[side], reference[side]))
                                  for side in (BREW_SIDE, STEAM_SIDE) if cornered[side])

        for side in (BREW_SIDE, STEAM_SIDE):
            if side not in entry["deviation"]:
                raise SweepError(
                    "neither corner of '%s' could be run on the %s side, so it carries a declared "
                    "error the sweep did not perturb it by and this ranking does not cover it: %s"
                    % (name, side, "; ".join(what for _, _, what in entry["refused"])))
            apart = entry["deviation"][side][0]
            # Dominance: how much of this side's declared margin this
            # coefficient's own declared error is already spending. The band
            # rather than the declared error is what the deviation is divided
            # by, and that is the whole of the metric -- the deviation was
            # produced by moving the coefficient at its declared error, so the
            # error is already inside the numerator and dividing by it again
            # would cancel out precisely the uncertainty this ranking exists to
            # weigh.
            entry["dominance"][side] = apart / bands[side]
            # Sensitivity: the same deviation per unit of relative movement in
            # the coefficient, which is what remains once the declared error is
            # divided back out. Kept because it answers the other half of the
            # question -- what would be bought by knowing this coefficient
            # better than the description presently admits to -- but it is not
            # what anything is ordered on, because it is by construction
            # indifferent to how well the coefficient is actually known.
            entry["sensitivity"][side] = entry["dominance"][side] / fraction

        # The side a coefficient is placed on is the one where it spends the
        # most margin, not the one where the model answers it most steeply: a
        # coefficient reaching both deliveries is ranked on the delivery it is
        # nearest to pushing out of band.
        entry["worst_side"] = max((BREW_SIDE, STEAM_SIDE), key=lambda s: entry["dominance"][s])
        entry["rank_by"] = entry["dominance"][entry["worst_side"]]
        swept.append(entry)

    # Ties are broken by name so that two coefficients the sweep cannot separate
    # come out in the same order on every run, rather than in whichever order
    # the description happened to list them after somebody reordered it.
    swept.sort(key=lambda entry: (-entry["rank_by"], entry["coefficient"]))

    # A coefficient neither delivery answered was perturbed and still cannot be
    # given a figure: there is no declared band its effect reached, so there is
    # nothing for a deviation to be a fraction of. It leaves the ranking here
    # and is named in the account instead. Deciding it on whether the delivery
    # moved anywhere in the run, rather than on the dominance figure coming out
    # at nothing, is what keeps the two apart: a coefficient that reaches the
    # delivery outside the judged window has been weighed against a real band
    # and scored nothing there, which is a finding, and it stays ranked.
    ranking = [entry for entry in swept if entry["moves_banded"]]
    unweighed += [(entry["coefficient"], NO_BANDED_QUANTITY_REACHED, could_not_be_weighed(entry))
                  for entry in swept if not entry["moves_banded"]]

    return {
        "description": description,
        # What the coffee side's control path reconstructed from throughout,
        # which is the machine's own description where no second one was named.
        # Recorded rather than left to be inferred from whether an argument was
        # passed, because which of the two questions a set of findings answers
        # is not something a reader of them should have to reconstruct.
        "control_description": description if control_description is None else control_description,
        # Whether the perturbations reached the control path along with the
        # machine. It is the same statement as the pair above where the sweep is
        # unperturbed, and it is not the same statement once a corner is run:
        # a sweep naming the machine's own description as the control path's
        # holds the control path at the unperturbed figures while every corner
        # moves the machine, which the two paths alone cannot say.
        "control_path_follows_the_machine": control_description is None,
        "limits": limits,
        "declaration": declaration,
        "tolerance": tolerance,
        "digests": {path: digest_of(path)
                    for path in (description, limits, declaration, tolerance)},
        "executable": executable,
        "bands": bands,
        "peaks": peaks,
        "windows": {side: (window[0], window[-1]) for side, window in windows.items()},
        "courses": {BREW_SIDE: brew, STEAM_SIDE: steam},
        "reference": reference,
        "swept": swept,
        "ranking": ranking,
        "unweighed": unweighed,
        "converter_scale": scale,
        "steam_ready_c": ready_c,
        "workspace": workspace,
    }


_FINDINGS = None


def run_once(**arguments):
    """The findings of one sweep, shared by everything that asks.

    Four host draws per coefficient -- both ends of its declared error against
    both deliveries -- plus the two the deviations are taken against is the most
    expensive thing this tool does, and every caller of it wants the same ones.
    A second suite reading what the sweep produced reads the same run rather
    than paying for another one that would, being the same artefact against the
    same descriptions, say the same thing.
    """
    global _FINDINGS
    if _FINDINGS is None:
        _FINDINGS = run(**arguments)
    return _FINDINGS


# --- The record ------------------------------------------------------------

#: The heading the ranking's own table sits under, which is what a reader of the
#: committed record finds the figures back under.
RANKING_HEADING = "## The ranking"

#: The heading the per-side figures sit under.
SIDES_HEADING = "## What each side contributed"

#: The heading the coefficients that could not be given a figure sit under.
#: A heading of their own rather than a footnote to the ranking, because being
#: unweighable is a different finding from being weighed and coming last, and
#: the two are only told apart by where a reader finds them.
UNWEIGHED_HEADING = "## What the sweep could not weigh"


def _relative(path):
    """A path as it is written into the record: relative to the repository, so
    the record reads the same wherever the tree was checked out."""
    return os.path.relpath(os.path.abspath(path), REPOSITORY_DIR)


def report_text(findings):
    """The whole record: the method, the model it was run against, and the
    ranking that came back.

    Written by the sweep rather than by hand, and written whole rather than as a
    table pasted into prose somebody maintains separately. Pointing the sweep at
    a replacement model has to need nothing changed about how the sweep or the
    ranking are computed -- and a record whose prose has to be re-edited by hand
    every time the model moves is one that will be left describing the previous
    machine.
    """
    lines = []
    write = lines.append

    write("# Which parameters' uncertainty dominates delivery")
    write("")
    write("**Generated by `firmware/emulation/tools/run_parameter_sweep.py`. Do not edit by "
          "hand — re-run the sweep.**")
    write("")
    write("Every coefficient the machine's description says it may be wrong about is perturbed "
          "by its own declared error, one at a time with every other coefficient held where the "
          "description puts it, and both closed loops are re-run against each perturbed machine. "
          "What comes back is how far the delivery moved, expressed as a fraction of the margin "
          "the design has declared it holds that delivery inside. That fraction is the dominance "
          "figure everything here is ordered on, and it answers one question: of the margin this "
          "machine is already held to, how much is this coefficient's own present uncertainty "
          "spending?")
    write("")
    write("It is deliberately not divided by the coefficient's declared error, which looks like "
          "the obvious way to compare a coefficient known to a hair against one known only "
          "roughly. The deviation was produced by moving the coefficient at exactly its declared "
          "error, so that error is already inside it; dividing by it again leaves the model's raw "
          "sensitivity to the relation, blind to how well the coefficient is actually known — "
          "which is the one thing being asked about. That figure is reported beside the ranking "
          "rather than as it, because the two answer different questions: dominance says where "
          "the margin is going today, sensitivity says how much better delivery would get if the "
          "coefficient were pinned down. Measurement and procurement are prioritised off the "
          "first.")
    write("")
    write("Nothing here is a measurement. It is analysis against an estimated model whose own "
          "figures are estimates, and its purpose is to say where measuring the machine would "
          "buy the most — not to say what the machine does.")
    write("")

    write("## The model this was run against")
    write("")
    write("| What | File | sha256 |")
    write("|---|---|---|")
    for what, path in (("The machine's coefficients", findings["description"]),
                       ("What a reading off it may be", findings["limits"]),
                       ("The steam side's design figures", findings["declaration"]),
                       ("The bands a delivery is held to", findings["tolerance"])):
        write("| %s | `%s` | `%s` |" % (what, _relative(path), findings["digests"][path]))
    write("")
    write("A replacement model is swept by naming it: `--description`, `--limits`, "
          "`--steam-declaration` and `--tolerance` each point the same sweep at another file. "
          "Nothing about how the sweep runs or how the ranking is computed changes with them. "
          "`--workspace` gives that run its own scratch directory, which a second model needs: "
          "every run writes a perturbed description per coefficient per corner under the same "
          "names, so two models sharing a directory leave the second run's descriptions standing "
          "where the first's were.")
    write("")

    write("## How each side is judged")
    write("")
    write("| Side | Judged on | Declared half-width | Scenario | Judged over |")
    write("|---|---|---|---|---|")
    for side in (BREW_SIDE, STEAM_SIDE):
        what, unit = JUDGED[side]
        first, last = findings["windows"][side]
        scenario = ("a %.0f s flush onto the group, then a shot: pre-infusion, ramp, hold, "
                    "taper, rest, all at %.0f C commanded"
                    % (BREW_FLUSH_STEPS * INTERVAL_MS / 1000.0, BREW_TARGET_C)
                    if side == BREW_SIDE else
                    "%.0f s held at the declared %.0f C ready state, then the wand open for "
                    "%.0f s at %.2f mL/s, then shut"
                    % (STEAM_SETTLE_STEPS * INTERVAL_MS / 1000.0, findings["steam_ready_c"],
                       STEAM_DRAW_STEPS * INTERVAL_MS / 1000.0,
                       STEAM_DEMAND_MILLI_ML_PER_S / 1000.0))
        write("| %s | %s | %s %s | %s | intervals %d–%d |"
              % (side, what, FIGURE_FORMAT % findings["bands"][side], unit, scenario, first, last))
    write("")

    write(RANKING_HEADING)
    write("")
    write("Ordered by the dominance figure: the fraction of that side's declared margin the "
          "coefficient's own declared error moved the delivery by. A figure of 1 means this "
          "coefficient's present uncertainty alone spends the whole of the margin. The side named "
          "is whichever of the two set the figure. The last column is the same deviation with the "
          "declared error divided back out — the model's sensitivity to the relation — which is "
          "reported and not ranked on.")
    write("")
    write("The two margins are made comparable by convention rather than being the same kind of "
          "quantity, and it is worth knowing which convention. Brew declares a half-width around "
          "the temperature that was commanded, so a deviation there is measured from a target "
          "the delivery is meant to be tracking. Steam declares a floor and a ceiling the "
          "delivered pressure has to stay between, and half the distance between them is taken "
          "as the half-width — which the unperturbed run may already be sitting anywhere inside "
          "rather than at the middle of. Both answer \"how far may this delivery move before the "
          "design says it has gone too far\", which is what lets one order cover the two; "
          "neither is a statement about how much room was left where the perturbation started.")
    write("")
    write("| # | Coefficient | Declared error | Dominance | Set by | Worst deviation there | "
          "Sensitivity (per unit declared error) |")
    write("|---|---|---|---|---|---|---|")
    for position, entry in enumerate(findings["ranking"], start=1):
        side = entry["worst_side"]
        _, unit = JUDGED[side]
        write("| %d | `%s` | %s | %s | %s | %s %s | %s |"
              % (position, entry["coefficient"], FIGURE_FORMAT % entry["fraction"],
                 FIGURE_FORMAT % entry["rank_by"], side,
                 FIGURE_FORMAT % entry["deviation"][side][0], unit,
                 FIGURE_FORMAT % entry["sensitivity"][side]))
    write("")

    write("### What the order says")
    write("")
    over_band = [entry for entry in findings["ranking"]
                 if max(entry["dominance"].values()) > 1.0]
    unreached = [entry for entry in findings["ranking"] if entry["rank_by"] == 0.0]
    write("%d of the %d coefficients ranked move a delivery further than the whole of its own "
          "declared band on their declared error alone: %s. Those are the rows scoring above 1, "
          "which on this metric is necessarily the head of the list — each of them is a "
          "coefficient whose present uncertainty, on its own and with everything else held where "
          "the description puts it, already accounts for more than the entire margin the design "
          "says it holds that delivery inside. That is a statement about how loosely this machine "
          "is presently described rather than about the control laws — every figure in the "
          "description is an estimate, and the error against each of them is an estimate of an "
          "estimate."
          % (len(over_band), len(findings["ranking"]),
             ", ".join("`%s`" % entry["coefficient"] for entry in over_band) or "none"))
    write("")
    if unreached:
        write("These reach a delivery the design declares a band for and spent none of that band "
              "over the window it is judged in: %s. That is a figure the sweep arrived at rather "
              "than one it could not take — the relation carries to a quantity the design holds "
              "the machine to, and on this scenario it moved it nowhere the delivery is being "
              "judged."
              % ", ".join("`%s`" % entry["coefficient"] for entry in unreached))
        write("")
    if findings["unweighed"]:
        write("A further %d could not be given a figure at all, and are named under \"%s\" below "
              "rather than placed at the foot of this table: %s. A coefficient the sweep could "
              "not weigh and one it weighed and found spending nothing are opposite findings, "
              "and a position in a ranked list cannot tell them apart."
              % (len(findings["unweighed"]), UNWEIGHED_HEADING.lstrip("# "),
                 ", ".join("`%s`" % name for name, _, _ in findings["unweighed"])))
        write("")

    write(SIDES_HEADING)
    write("")
    write("The same coefficients against each side separately, in the order above. A coefficient "
          "that dominates one delivery and barely reaches the other is the case a ranking taken "
          "over a single side would have got wrong. Each dominance column is that side's own "
          "deviation over that side's own declared band, which is what makes a degree of brew "
          "temperature and a hundredth of a bar of steam pressure the same kind of statement and "
          "lets one order cover both.")
    write("")
    write("| Coefficient | Brew deviation (C) | Brew dominance | Steam deviation (bar) | "
          "Steam dominance |")
    write("|---|---|---|---|---|")
    for entry in findings["ranking"]:
        write("| `%s` | %s | %s | %s | %s |"
              % (entry["coefficient"],
                 FIGURE_FORMAT % entry["deviation"][BREW_SIDE][0],
                 FIGURE_FORMAT % entry["dominance"][BREW_SIDE],
                 FIGURE_FORMAT % entry["deviation"][STEAM_SIDE][0],
                 FIGURE_FORMAT % entry["dominance"][STEAM_SIDE]))
    write("")

    write(UNWEIGHED_HEADING)
    write("")
    write("These coefficients have no dominance figure, and they are listed here instead of at "
          "the foot of the ranking with a figure of nothing. A coefficient either carries no "
          "declared error for the sweep to move it by, or carries an error declared as nothing, "
          "or moves no quantity the design declares a band for — and in every one of those cases "
          "there is no margin for its uncertainty to be a fraction of. Placed last in a ranked "
          "list it would read as a coefficient that barely matters, where what is true is that "
          "nothing here can judge it either way. Those are different findings and only the first "
          "of them is safe to act on.")
    write("")
    if findings["unweighed"]:
        write("| Coefficient | Why it has no figure | What the sweep found |")
        write("|---|---|---|")
        for name, condition, why in findings["unweighed"]:
            write("| `%s` | %s | %s |" % (name, condition, why))
    else:
        write("Every coefficient the description carries was perturbed, and every one of them "
              "moved a delivery the design declares a band for. Nothing was set aside.")
    write("")

    write("## What this sweep does not cover")
    write("")
    refused = [(entry["coefficient"], corner, side, what)
               for entry in findings["swept"] for corner, side, what in entry["refused"]]
    if refused:
        write("These corners were refused as machines rather than run, and the coefficient was "
              "judged on the other one:")
        write("")
        for name, corner, side, what in refused:
            write("- `%s`, %s corner, %s side: %s" % (name, corner, side, what))
        write("")
    write("Whether the order above is quantitatively right for a real machine is not established "
          "here and cannot be: every figure in the model it was taken against is an estimate, so "
          "the ranking is meant to be redone against a measured model rather than argued about "
          "against this one.")
    write("")
    write("Identifiability — whether a coefficient a reconstructed state depends on can be told "
          "apart from the channels this machine observes at all — is a separate question and is "
          "not answered here. It is answered from the same perturbed re-runs by "
          "`firmware/emulation/tools/run_parameter_identifiability.py`, which reads each run's "
          "effect on the observed channels where this one reads its effect on the delivery, and "
          "records what it found in `docs/parameter-identifiability.md`. A coefficient can stand "
          "at the head of the ranking above and still be one no observation of this machine can "
          "tell from another, which is why the two records are kept apart and why neither figure "
          "should be read off the other's table.")
    write("")

    return "\n".join(lines) + "\n"


_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|([^|]*)\|([^|]*)\|([^|]*)\|")

_UNWEIGHED_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|([^|]*)\|")


def ranking_rows(text):
    """The ranking read back out of a written record, as (position, coefficient,
    declared error, dominance, side).

    Read back through this rather than by whatever pattern a reader invents,
    because the check that the committed record is still the one this method
    produces is only worth anything if the reading and the writing agree about
    where the figures are.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if line.startswith(RANKING_HEADING):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside:
            continue
        found = _ROW.match(line)
        if found:
            rows.append((int(found.group(1)), found.group(2), float(found.group(3).strip()),
                         float(found.group(4).strip()), found.group(5).strip()))
    return rows


def unweighed_rows(text):
    """The account of what could not be weighed, read back out of a written
    record, as (coefficient, condition).

    Read back through this for the same reason the ranking is: a check that the
    committed record still names an unweighable coefficient as unweighable, and
    does not have it standing in the ranked table, is only worth something if
    the reading and the writing agree about which table is which.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if line.startswith(UNWEIGHED_HEADING):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside:
            continue
        found = _UNWEIGHED_ROW.match(line)
        if found:
            rows.append((found.group(1), found.group(2).strip()))
    return rows


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--description",
                        help="the parameter description to sweep, defaulting to the one the "
                             "target build carries compiled in")
    parser.add_argument("--limits",
                        help="what a reading off that machine may be, defaulting to the one the "
                             "target build carries compiled in")
    parser.add_argument("--steam-declaration", default=STEAM_CONTROL_DECLARATION,
                        help="the figures the steam control law is given")
    parser.add_argument("--tolerance", default=TOLERANCE_DECLARATION,
                        help="the bands a delivery is held to")
    parser.add_argument("--report", default=REPORT_PATH,
                        help="where the record of the ranking is written")
    parser.add_argument("--stdout", action="store_true",
                        help="print the record rather than writing it")
    parser.add_argument("--pio", default=base.DEFAULT_PIO,
                        help="the PlatformIO executable that builds the host environment")
    parser.add_argument("--workspace", default=BUILD_DIR,
                        help="where this run's perturbed descriptions are written. Give a second "
                             "model a directory of its own: every run writes one description per "
                             "coefficient per corner under the same names, so two models sharing "
                             "a directory leave the second's standing where the first's were and "
                             "anything going back to the files to establish what a run handed the "
                             "machine reads the other model's")
    arguments = parser.parse_args(argv)

    findings = run(description=arguments.description, limits=arguments.limits,
                   declaration=arguments.steam_declaration, tolerance=arguments.tolerance,
                   pio=arguments.pio, workspace=arguments.workspace)
    text = report_text(findings)

    if arguments.stdout:
        sys.stdout.write(text)
        return 0

    os.makedirs(os.path.dirname(arguments.report), exist_ok=True)
    with open(arguments.report, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("swept %d coefficient(s) of %s, ranked %d, and wrote the record to %s"
          % (len(findings["swept"]), _relative(findings["description"]),
             len(findings["ranking"]), _relative(arguments.report)))
    for entry in findings["ranking"][:5]:
        print("  %-40s %8s  (%s)"
              % (entry["coefficient"], FIGURE_FORMAT % entry["rank_by"], entry["worst_side"]))
    for name, condition, _ in findings["unweighed"]:
        print("  %-40s %8s  (%s)" % (name, "--", condition))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
