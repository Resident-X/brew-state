#!/usr/bin/env python3
"""Read the margin a commanded target keeps from the coffee block's protection
trip point out of the loop that enforces it, and run a delivery at every corner
of the declared error that margin was sized from.

Two things this needs are already in place and neither is rebuilt here. The
control path computes that margin itself, out of the description it was brought
up against and the error that description declares against its own coefficients:
it enumerates one corner per coefficient plus the one joint corner the
description's own construction implies, asks the plant model what each corner
costs the gap between a commanded target and the trip point, and takes the worst
of them. And the brew side already has a closed loop that can be run on the host
against a machine description named from outside it, with the control path held
at a second description while the machine moves. What is added here is the
reading of the first and the sweep of the second.

Nothing here recomputes the mapping. The corners, what each of them writes, what
each of them cost, and the margin they combine into are all read back through
the control path's own reads by the host artefact's `--protection-margin-record`
mode, and this tool consumes what the machine says. A second enumeration
standing beside the loop would eventually describe corners the loop was not
taking its margin over, and the disagreement would be invisible: the record
would go on reading plausibly.

The delivery at each corner is run with the machine built from that corner's
coefficients and the control path held at the description that shipped. That
split is the whole of what makes it a robustness check rather than a
commissioning one: a loop reconstructing from the very coefficients the machine
was perturbed with has a perfect model at every corner, and every corner would
then land in band whatever the margin was.

Where a delivery is commanded matters as much as which machine it is run
against, and it is not a figure this file chooses. The target is the highest one
the loop will actually take, narrowed on its own admission path -- which is what
"commanded at the widened margin" comes to on a machine whose margin is the
tightest of that path's ceilings. Which ceiling actually stops the narrowing is
therefore a finding and not an assumption, and it is reported as one: on a
machine where some other ceiling is tighter, the protection margin refuses
nothing at all, and a reader who took this sweep for evidence that the margin
had been exercised would be taking it for something it is not.

How far that machine stands from the case where its margin does bind is
reported as a figure rather than left as a sentence: the tool narrows on the
smallest widening of one coefficient's declared error at which the margin
overtakes whatever ceiling is presently tighter. It is read rather than swept
-- no delivery is run against a widened description, because a description
nobody claims is not a machine a verdict can be taken about, and a table of
failures against one would read as findings about this design.

Which coefficient that narrowing widens is read off the mapping rather than
named here: the one whose corner contributes most at the end a widening can
actually be pushed to. A declared error is a fraction of a value, so the end
that writes the coefficient low runs out where the fraction reaches one and the
corner stops being a machine the structure admits; the end that writes it high
has no such stop.

Nothing here decides whether the answer is good news, on the terms every other
runner in this directory is written on.
"""

from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))
REPOSITORY_DIR = os.path.abspath(os.path.join(FIRMWARE_DIR, ".."))

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FIRMWARE_DIR, "tools"))

import check_parameter_origins as origins  # noqa: E402
import run_cross_tier_check as cross_tier  # noqa: E402
import run_emulation_check as base  # noqa: E402
import run_parameter_stability as stability  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402

#: Which coefficients the description's own prose calls one-sided, taken from
#: the sibling stability analysis rather than written again here. It is the one
#: place that fact is recorded on this side of the plant seam, and a second copy
#: would be free to go stale against the first while both went on reading
#: plausibly.
ONE_SIDED = stability.ONE_SIDED

#: Where the mapping and the corner verdicts are kept.
REPORT_PATH = os.path.join(REPOSITORY_DIR, "docs", "protection-margin.md")

#: Where this tool's own working files go: the widened description, the corner
#: descriptions and the course files. Under the host build's own directory
#: because they are inputs to that artefact's runs and to nothing else, and in a
#: directory of this tool's own so that two analyses cannot leave each other's
#: descriptions standing under the same names.
BUILD_DIR = os.path.join(FIRMWARE_DIR, ".pio", "build", cross_tier.HOST_ENVIRONMENT, "margin")

#: What names the reading on the host artefact's command line.
RECORD_OPTION = "--protection-margin-record"

#: The word the loop reports for the bound this analysis is about. It is the
#: name the artefact prints rather than the enumerated value beside it, because
#: a record naming a bound by its number goes on reading plausibly after a value
#: is inserted ahead of it in the enumeration.
MARGIN_BOUND = "inside-protection-margin"

#: How far the widening search is allowed to go, as a fraction of the
#: coefficient's own value, and how finely it narrows.
#:
#: The ceiling is deliberately far past anything a description would state: what
#: is being found is how far this machine's declared error has to be stretched
#: before its own protection becomes the binding bound, and a search that
#: stopped at a plausible figure would report "no such widening" for a machine
#: where there is one. Twenty halvings puts the answer inside a thousandth of a
#: fraction, which is finer than the figure is ever read to.
WIDENING_CEILING = 8.0
WIDENING_STEPS = 20

#: The coefficient the draw's level is stated against, and the rate that level
#: asks the shipped machine for.
#:
#: The rate is the description's own: brew.outlet_held_volume_ml's account
#: reasons about "the two-and-a-bit millilitres per second a shot is actually
#: drawn at", and this is a shot. The level it comes to is worked out per run
#: from what the description says full pump scale draws, so a corrected pump
#: coefficient moves the level rather than silently moving the rate.
FULL_SCALE_COEFFICIENT = "pump.flow_ml_per_s"
DRAW_RATE_ML_PER_S = 1.0

#: How many control intervals each corner's draw runs for.
#:
#: Six hundred simulated seconds. The host draw builds its machine from the
#: description and stands it nowhere, so a draw begins on a block at ambient and
#: the first several hundred seconds of it are the climb; at the shipped
#: coefficients the delivery is inside a thirtieth of a degree of its command
#: well before the judged stretch begins, which is what leaves a verdict about
#: the machine rather than about how far along the climb the run happened to
#: stop.
DRAW_STEPS = 60000

#: How the record's figures are written. Three significant figures, on the terms
#: the sibling analyses write theirs: more than a mapping over a description
#: whose own declared errors run from two per cent to eighty can support, and
#: fewer than a difference in the last place of a single-precision model.
FIGURE_FORMAT = "%.3g"

#: What a table cell holds where the run had no figure for it.
NOTHING = "—"

#: The headings the record carries, as constants so the readers below and the
#: test that keeps the record honest find the same sections this writes.
MODEL_HEADING = "## The model this was run against"
STANDING_HEADING = "## Where a commanded target actually stops"
MAPPING_HEADING = "## What each declared error contributes to the margin"
VERDICT_HEADING = "## What each corner's delivery did"
STEAM_MAPPING_HEADING = "## What each declared error contributes to the steam side's margin"
STEAM_VERDICT_HEADING = "## What each corner's steam draw did"
REFUSED_HEADING = "## What could not be delivered against"


class MarginError(RuntimeError):
    """The mapping could not be read, or could not be swept over everything it
    covers."""


# --- Reading the mapping back out of the loop ------------------------------


def parse_record(output):
    """Turn the reading's `HOST ` lines into the record this tool works from."""
    findings = {
        "target_c": None,
        "capping_bound": None,
        "capping_bound_name": None,
        "capping_available_c": None,
        "trip_known": None,
        "trip_c": None,
        "margin": None,
        "corners": [],
        "steam_ready_c": None,
        "steam_highest_c": None,
        "steam_margin": None,
        "steam_corners": [],
        "completed": False,
    }

    def corner_of(fields):
        return {
            "which": int(fields["which"]),
            "joint": fields["kind"] == "joint",
            "at": int(fields["at"]),
            "end": fields["end"],
            "declared": float(fields["declared"]),
            "factor": float(fields["factor"]),
            "ran": int(fields["ran"]) != 0,
            "contribution_c": float(fields["contribution-c"]),
            "moves": int(fields["moves"]),
            "writes": [] if fields["writes"] == "-" else fields["writes"].split(","),
        }

    def margin_of(fields):
        return {
            "widened_c": float(fields["widened-c"]),
            "unwidened_c": float(fields["unwidened-c"]),
            "worst_c": float(fields["worst-c"]),
            "corners": int(fields["corners"]),
            "run": int(fields["run"]),
            "contributing": int(fields["contributing"]),
            "worst_at": int(fields["worst-at"]),
            "worst_joint": int(fields["worst-joint"]) != 0,
        }
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("HOST "):
            continue
        parts = line.split()[1:]
        kind = parts[0]
        fields = cross_tier.closed_loop.keyed(parts[1:])
        if kind == "margin-target":
            findings["target_c"] = float(fields["target-c"])
            findings["capping_bound"] = int(fields["capping-bound"])
            findings["capping_bound_name"] = fields["capping-bound-name"]
            findings["capping_available_c"] = float(fields["capping-available-c"])
        elif kind == "margin-trip":
            findings["trip_known"] = int(fields["known"]) != 0
            findings["trip_c"] = float(fields["trip-c"])
        elif kind == "margin":
            findings["margin"] = margin_of(fields)
        elif kind == "margin-corner":
            findings["corners"].append(corner_of(fields))
        elif kind == "steam-margin-target":
            findings["steam_ready_c"] = float(fields["ready-c"])
            findings["steam_highest_c"] = float(fields["highest-c"])
        elif kind == "steam-margin":
            findings["steam_margin"] = margin_of(fields)
        elif kind == "steam-margin-corner":
            findings["steam_corners"].append(corner_of(fields))
        elif kind == "done":
            findings["completed"] = True
    return findings


def margin_record(executable, description, limits, declaration=sweep.STEAM_CONTROL_DECLARATION):
    """The whole mapping, read off one instance of the loop.

    One invocation and not one per corner: the margin follows whatever
    description the instance is holding, so corners read from two instances
    would belong to two enumerations and the record would describe corners the
    committed margin was not taken over.
    """
    completed = base.subprocess.run(
        [executable, description, limits, RECORD_OPTION, declaration],
        cwd=FIRMWARE_DIR, stdin=base.subprocess.DEVNULL, capture_output=True, text=True)

    findings = parse_record(completed.stdout)
    if not findings["completed"] or findings["margin"] is None:
        raise MarginError(
            "the margin reading did not finish against %s. Its output follows:\n%s\n%s"
            % (description, completed.stdout[-4000:], completed.stderr[-4000:]))
    if findings["steam_margin"] is None:
        raise MarginError(
            "the margin reading against %s printed no steam-side margin, so only one of the two "
            "loops sizing a margin against this description was read" % description)
    for side, corners, record in (("coffee", findings["corners"], findings["margin"]),
                                  ("steam", findings["steam_corners"],
                                   findings["steam_margin"])):
        if len(corners) != record["corners"]:
            raise MarginError(
                "the reading printed %d %s corners against an enumeration of %d, so the mapping "
                "is not the one that margin was taken over"
                % (len(corners), side, record["corners"]))
    findings["description"] = description
    findings["limits"] = limits
    return findings


# --- Rewriting a description's declared error ------------------------------


def error_with(coefficient, fraction, destination, source, vocabulary, marker):
    """`source` with one coefficient's declared error rewritten, written to
    `destination`.

    The sibling analyses rewrite a coefficient's *value* and hand the result to
    the ordinary loader; this rewrites what the description says that value may
    be wrong by, and hands it to the same loader on exactly the same terms. A
    record reached into instead would be an arrangement no description could
    produce, and the margin would then be sized off an uncertainty nothing
    states.

    The value and the origin either side of the error are carried across
    untouched: what the machine is has not changed, and where a figure came from
    does not stop being true because a run asked what would happen if it were
    known worse.
    """
    rewritten = []
    found = False
    for raw in origins.read(source).splitlines():
        line = raw.rstrip()
        if "=" not in line or line.strip().startswith("#"):
            rewritten.append(line)
            continue
        name, tail = line.split("=", 1)
        if name.strip() != coefficient:
            rewritten.append(line)
            continue
        origin = tail.find(vocabulary.marker)
        if origin < 0:
            raise MarginError(
                "%s states '%s' with no origin, which its own loader would refuse -- so there is "
                "no account for a rewritten error to sit beside" % (source, coefficient))
        cuts = [at for at in (tail.find(marker), origin) if at >= 0]
        value = tail[:min(cuts)].strip()
        rewritten.append("%s= %s %s %s %s" % (name, value, marker,
                                              sweep.VALUE_FORMAT % fraction, tail[origin:]))
        found = True
    if not found:
        raise MarginError(
            "%s states no '%s', so its declared error cannot be rewritten" % (source, coefficient))

    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rewritten) + "\n")
    return destination


# --- Finding where the margin becomes the binding bound --------------------


def widenable_coefficient(record):
    """The coefficient whose declared error this tool widens, read off the
    mapping rather than named here.

    The corner that contributes most at the end that writes its coefficient
    high. A declared error is a fraction of a value, so the low end runs out
    where the fraction reaches one and the corner stops being a machine the
    structure admits; the high end has no such stop, and is therefore the only
    end a search is free to push until the margin binds.
    """
    upward = [corner for corner in record["corners"]
              if corner["ran"] and not corner["joint"] and corner["end"] == "high"
              and corner["writes"] and corner["contribution_c"] > 0.0]
    if not upward:
        raise MarginError(
            "no corner of this description costs the trip-point gap anything at the end a "
            "widening could be pushed, so there is no widening that would make the protection "
            "margin the binding bound")
    best = max(upward, key=lambda corner: corner["contribution_c"])
    return best["writes"][0], best["declared"]


def widening_that_binds(executable, description, limits, workspace, vocabulary, marker):
    """The least widening of one coefficient's declared error at which the
    protection margin is what caps a commanded target, and the description
    carrying it.

    Narrowed rather than chosen, and narrowed on the loop's own report of which
    bound stopped it rather than on any arithmetic here: what is being found is
    the point at which one of the control path's ceilings overtakes another, and
    a figure computed from the outside would be this file's opinion about where
    that happens.
    """
    coefficient, declared = widenable_coefficient(margin_record(executable, description, limits))
    below = declared
    above = None

    fraction = declared
    for _ in range(WIDENING_STEPS):
        fraction = fraction * 2.0
        if fraction > WIDENING_CEILING:
            break
        written = error_with(coefficient, fraction,
                             os.path.join(workspace, "widened-probe.params"), description,
                             vocabulary, marker)
        if margin_record(executable, written, limits)["capping_bound_name"] == MARGIN_BOUND:
            above = fraction
            break
        below = fraction
    if above is None:
        raise MarginError(
            "widening '%s' as far as %g of its own value never made the protection margin the "
            "binding bound, so this description cannot be swept at the margin" %
            (coefficient, WIDENING_CEILING))

    for _ in range(WIDENING_STEPS):
        middle = (below + above) / 2.0
        written = error_with(coefficient, middle,
                             os.path.join(workspace, "widened-probe.params"), description,
                             vocabulary, marker)
        if margin_record(executable, written, limits)["capping_bound_name"] == MARGIN_BOUND:
            above = middle
        else:
            below = middle

    written = error_with(coefficient, above, os.path.join(workspace, "widened.params"),
                         description, vocabulary, marker)
    return {"coefficient": coefficient, "declared": declared, "widened_to": above,
            "description": written}


# --- Running a delivery at one corner --------------------------------------


def corner_description(corner, nominal, source, workspace):
    """The machine one enumerated corner names, written out as a description.

    Built from what the loop said the corner writes and at what factor, so the
    machine a verdict is taken against is the machine the contribution was taken
    against. The joint corner writes more than one coefficient, and each rewrite
    takes the previous file as its source so the last one carries all of them --
    the same chaining the sibling stability analysis uses for the same corner.
    """
    written = source
    for at, name in enumerate(corner["writes"]):
        if name not in nominal:
            raise MarginError(
                "the loop's enumeration names '%s' at corner %d and %s states no such "
                "coefficient" % (name, corner["which"], source))
        written = cross_tier.description_with(
            name, sweep.VALUE_FORMAT % (nominal[name] * corner["factor"]),
            os.path.join(workspace, "corner-%d-%d.params" % (corner["which"], at)),
            source=written)
    return written


def draw_permille(nominal):
    """The pump level this analysis draws at, as a level and not as a rate.

    A level is what the control path's flow entry point takes and what the
    heater's own feedforward reads in the same step, so a course stated as a
    rate would have to be turned into one by dividing by what full pump scale
    draws -- and at a corner that moves the pump, the same rate would then be a
    different level on every machine and the sweep would be commanding a
    different course at every corner.

    The level is derived from the description rather than chosen: it is the
    level that asks the shipped machine for the rate its own account of
    brew.outlet_held_volume_ml reasons a shot is actually drawn at.
    """
    full_scale = nominal.get(FULL_SCALE_COEFFICIENT)
    if not full_scale:
        raise MarginError(
            "the description states no '%s', so there is no full pump scale to state this "
            "analysis's draw as a level of" % FULL_SCALE_COEFFICIENT)
    return int(round(DRAW_RATE_ML_PER_S / full_scale * 1000.0))


def margin_course(nominal):
    """The course every corner is run against: one level, held.

    One rate held for long enough that the loop has answered the machine it was
    actually given, and ending at that rate rather than tapering, because what
    this criterion asks is where a delivery lands and a taper is a stretch of
    the loop chasing a course rather than delivering. The dominance sweep's own
    course is deliberately not reused: it is built for comparing two runs of the
    same shape against each other, and against the band itself its taper alone
    spends nine tenths of what the design declares -- so a verdict taken over it
    would be a verdict about the course.

    It is long because the draw starts from a cold machine. The host draw builds
    its model from the description and nothing stands it at the target first, so
    the first several hundred simulated seconds are the block climbing; the
    length here is what leaves the loop settled well before the judged stretch
    begins.
    """
    return [(sweep.INTERVAL_MS, draw_permille(nominal))] * DRAW_STEPS


def the_end_the_description_does_not_claim(corner):
    """Whether a corner names a machine the description does not stand behind.

    One-sidedness is a sentence in `params/thermoblock.md` and not a field of
    the description's grammar -- the line beside a value carries a symmetric
    fraction and nothing that could say otherwise -- so the margin computation
    itself runs both ends of every coefficient, which can only widen a margin
    and is the safe direction for a protection bound. A *delivery verdict* is a
    different kind of claim: taken at the end the description does not claim, it
    would be a verdict about a machine nobody has said exists. So such a corner
    is enumerated and reported and is not held to the band, which is the same
    treatment the sibling analyses give it.
    """
    return any(name in ONE_SIDED and corner["end"] != ONE_SIDED[name]
               for name in corner["writes"])


def judged_window(course):
    """Which intervals a corner's verdict is taken over: the trailing tenth of
    the draw.

    Where the delivery *lands* rather than everything it did on the way. How
    tightly a setpoint is held while the loop is still answering the machine it
    has been given is declared a degrading behaviour in
    params/robustness.declaration and is permitted to get worse as the model
    does; where the delivery comes to rest is what the band is a statement
    about, and it is the question this criterion asks.
    """
    return list(range(len(course) - (len(course) // 10), len(course)))


def worst_departure(delivered, target_c, window):
    """How far the delivery sat from what it was commanded, at its worst over
    the judged window.

    Against the command rather than against an unperturbed run of the same
    course: what the band states is how far the water reaching the group may sit
    from the temperature that was asked for, so a comparison against another run
    would be answering how far two machines came apart instead.
    """
    return max(abs(delivered[at] - target_c) for at in window)


# --- The whole analysis ----------------------------------------------------


def steam_band_milli_bar(declaration):
    """The floor and ceiling the steam draw's delivered pressure is held between.

    Read out of the same declaration the loop is itself given, through the
    sweep's own readers: a second reading here would be a second opinion about
    which figures the band is, and the two would eventually disagree about
    whether a draw was in it.
    """
    floor = sweep._declared_figure(
        declaration, sweep._declared_word(sweep.STEAM_DECLARATION_HEADER, sweep.STEAM_FLOOR_MACRO))
    ceiling = sweep._declared_figure(
        declaration,
        sweep._declared_word(sweep.STEAM_DECLARATION_HEADER, sweep.STEAM_CEILING_MACRO))
    return floor, ceiling


def steam_verdict(findings, course, floor, ceiling):
    """Whether a steam draw came to rest inside the band, and the worst pressure
    it reached over the judged window.

    Where the draw *lands* rather than everything it did on the way, on exactly
    the terms the coffee side's own verdict is taken: how tightly a delivered
    character is held while the loop is still answering the machine it was given
    is declared a degrading behaviour, and where it comes to rest is what the
    band states. The window is the sweep's own -- from the interval feed first
    engaged to the last the wand was open -- narrowed to its trailing third.
    """
    window = sweep.steam_judged_window(course, findings["trajectory"])
    judged = window[(len(window) * 2) // 3:]
    pressures = [findings["trajectory"][at]["quantities"][
        sweep.closed_loop.QUANTITY_KEYS.index("steam-bar")] for at in judged]
    milli_bar = [int(round(value * 1000.0)) for value in pressures]
    outside = [value for value in milli_bar if value < floor or value > ceiling]
    worst = outside[0] if outside else min(milli_bar, key=lambda value: min(
        value - floor, ceiling - value))
    return (not outside), worst, (judged[0], judged[-1])


def run(description=None, limits=None, tolerance=sweep.TOLERANCE_DECLARATION,
        declaration=sweep.STEAM_CONTROL_DECLARATION,
        pio=base.DEFAULT_PIO, executable=None, workspace=BUILD_DIR):
    """Read the mapping, and deliver at every corner of it.

    `description`, `limits` and `tolerance` default to the files the target
    build carries compiled in, which is what makes the record a statement about
    the machine this project is building rather than about whichever description
    happened to be lying about. They are arguments so the same method can be
    pointed at a replacement model without anything here being edited, which is
    the whole of what makes it repeatable.
    """
    carried_description, carried_limits = cross_tier.carried_declarations()
    description = description or carried_description
    limits = limits or carried_limits

    vocabulary, marker = sweep._vocabularies()
    nominal = sweep.nominal_values(description, vocabulary, marker)
    band_c = sweep.brew_band_c(tolerance)
    scale = cross_tier.converter_scale()
    course = margin_course(nominal)
    window = judged_window(course)
    executable = executable or sweep.build_host(pio)

    os.makedirs(workspace, exist_ok=True)

    shipped = margin_record(executable, description, limits, declaration)
    margin_binds = shipped["capping_bound_name"] == MARGIN_BOUND

    # How far this description's declared error would have to be stretched
    # before its own protection is what stops a commanded target. Read only
    # where the margin does not already bind, and read rather than swept: a
    # widened description is one nobody claims, and a table of corner verdicts
    # taken against one would read as findings about this design.
    widening = None
    if not margin_binds:
        widening = widening_that_binds(executable, description, limits, workspace, vocabulary,
                                       marker)

    target_c = shipped["target_c"]
    verdicts = []
    refused = []
    for corner in shipped["corners"]:
        if not corner["ran"]:
            refused.append((corner, "the structure admits no machine at this corner, or the "
                                    "description declares no error to take it to"))
            continue
        try:
            written = corner_description(corner, nominal, description, workspace)
            drawn = sweep.brew_draw(executable, written, limits, course, scale,
                                    "margin-corner-%d" % corner["which"],
                                    control_description=description, target_c=target_c)
        except (MarginError, sweep.SweepError, cross_tier.CrossTierError) as refusal:
            refused.append((corner, str(refusal).splitlines()[0]))
            continue
        departure = worst_departure(drawn["delivered"], target_c, window)
        claimed = not the_end_the_description_does_not_claim(corner)
        verdicts.append({
            "corner": corner,
            "claimed": claimed,
            "worst_departure_c": departure,
            "within_band": departure <= band_c,
            "description": written,
        })

    # The steam side's own corners, run to the same standard. Its loop is built
    # from its declaration and from no description of a casting at all, so there
    # is no second description to hold it at while the machine moves: the split
    # this analysis has to arrange on the coffee side is structural there.
    steam_floor, steam_ceiling = steam_band_milli_bar(declaration)
    steam_course = sweep.steam_course()
    steam_ready_c = shipped["steam_ready_c"]
    steam_verdicts = []
    steam_window = None
    for corner in shipped["steam_corners"]:
        if not corner["ran"]:
            refused.append((corner, "the structure admits no machine at this corner, or the "
                                    "description declares no error to take it to"))
            continue
        try:
            written = corner_description(corner, nominal, description,
                                         os.path.join(workspace, "steam"))
            drawn = sweep.steam_draw(executable, written, limits, declaration, steam_ready_c,
                                     steam_course, "steam-margin-corner-%d" % corner["which"])
            held, worst, steam_window = steam_verdict(drawn, steam_course, steam_floor,
                                                      steam_ceiling)
        except (MarginError, sweep.SweepError, cross_tier.CrossTierError) as refusal:
            refused.append((corner, str(refusal).splitlines()[0]))
            continue
        steam_verdicts.append({
            "corner": corner,
            "claimed": not the_end_the_description_does_not_claim(corner),
            "worst_milli_bar": worst,
            "within_band": held,
            "description": written,
        })

    return {
        "description": description,
        "limits": limits,
        "tolerance": tolerance,
        "declaration": declaration,
        "executable": executable,
        "workspace": workspace,
        "shipped": shipped,
        "margin_binds": margin_binds,
        "widening": widening,
        "target_c": target_c,
        "band_c": band_c,
        "draw_permille": course[0][1],
        "verdicts": verdicts,
        "steam_verdicts": steam_verdicts,
        "steam_band_milli_bar": (steam_floor, steam_ceiling),
        "steam_window": steam_window,
        "refused": refused,
        "window": (window[0], window[-1]),
        "digests": {path: sweep.digest_of(path)
                    for path in (description, limits, tolerance, declaration)},
    }


_FINDINGS = {}


def run_once(**arguments):
    """One run of the whole analysis per process, shared by every reader of it.

    The corner sweep costs a draw per corner, and a test module asking three
    questions of one run would otherwise pay for three.
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


def _verdict_word(verdict):
    """What a corner's row reports.

    A corner at the end the description does not claim is reported as such
    rather than as a pass or a failure: it was run and its figure is here, and
    the description stands behind neither answer.
    """
    if not verdict["claimed"]:
        return "not-claimed"
    return "within-band" if verdict["within_band"] else "outside-band"


def _coefficient_cell(corner):
    if corner["joint"]:
        return "%s (joint mains droop)" % " + ".join(corner["writes"])
    return corner["writes"][0] if corner["writes"] else NOTHING


def report_text(findings):
    """The whole record: what the margin came to, where a commanded target
    actually stops, and what a delivery did at every corner.

    Written by the tool rather than by hand, and written whole rather than as a
    table pasted into prose somebody maintains separately: pointing the method
    at a replacement model has to need nothing changed here, and a record whose
    prose is re-edited by hand every time the model moves is one that will be
    left describing the previous machine.
    """
    shipped = findings["shipped"]
    margin = shipped["margin"]
    steam_margin = shipped["steam_margin"]
    steam_target = {"ready_c": shipped["steam_ready_c"], "highest_c": shipped["steam_highest_c"]}
    lines = []
    write = lines.append

    write("# The margin a commanded target keeps from the coffee block's protection")
    write("")
    write("**Generated by `firmware/emulation/tools/run_protection_margin.py`. Do not edit by "
          "hand — re-run the tool.**")
    write("")
    write("A trip point is not something the software drives to and not something it can "
          "negotiate with: it is a device that opens on the truth. What the design gets to decide "
          "is how far below it a target is commanded. That distance is widened for the error the "
          "machine's own description declares it may be wrong by — every coefficient taken to its "
          "own corner one at a time, plus the one joint corner the description's own construction "
          "implies, with the largest single corner's degradation added to the gap the trip point "
          "alone implies. The corners combine by worst case and never by summing or in "
          "quadrature.")
    write("")
    write("Every figure below is read back out of the control path that enforces the margin, "
          "through its own reads. Nothing here recomputes it: a second enumeration standing "
          "beside the loop would eventually describe corners the loop was not taking its margin "
          "over, and the record would go on reading plausibly while it did.")
    write("")
    write("Each corner's delivery is run with the machine built from that corner's coefficients "
          "and the control path held at the description that shipped. That split is what makes it "
          "a robustness check: a loop reconstructing from the very coefficients the machine was "
          "perturbed with has a perfect model at every corner, and every corner would land in "
          "band whatever the margin was.")
    write("")
    write("Nothing here is a measurement. The trip point is a figure read off a parts list, no "
          "fitted protective device on this machine has been measured, and the declared errors "
          "the margin is sized from are judgements rather than readings.")
    write("")

    write(MODEL_HEADING)
    write("")
    write("| What | File | sha256 |")
    write("|---|---|---|")
    for what, path in (("The machine's coefficients", findings["description"]),
                       ("What a reading off it may be", findings["limits"]),
                       ("The bands a delivery is held to", findings["tolerance"]),
                       ("The steam side's design figures", findings["declaration"])):
        write("| %s | `%s` | `%s` |" % (what, _relative(path), findings["digests"][path]))
    write("")
    write("A replacement model is read by naming it: `--description`, `--limits`, "
          "`--tolerance` and `--steam-declaration` each point the same method at another file, "
          "and nothing about how the mapping is read or how a corner is delivered against "
          "changes with them.")
    write("")

    write(STANDING_HEADING)
    write("")
    write("The highest target the loop takes is narrowed on its own admission path rather than "
          "worked out from any figure read out of the control source, and which of that path's "
          "ceilings stops the narrowing is a finding about this machine rather than an "
          "assumption of the method.")
    write("")
    write("| Highest target taken (C) | Bound that stops it | Widened margin (C) | "
          "Un-widened gap (C) | Trip point (C) |")
    write("|---|---|---|---|---|")
    write("| %s | %s | %s | %s | %s |" % (
        FIGURE_FORMAT % shipped["target_c"],
        shipped["capping_bound_name"],
        FIGURE_FORMAT % margin["widened_c"],
        FIGURE_FORMAT % margin["unwidened_c"],
        FIGURE_FORMAT % shipped["trip_c"] if shipped["trip_known"] else NOTHING))
    write("")
    if findings["margin_binds"]:
        write("The protection margin is that bound: a commanded target on this machine stops "
              "where the widened margin leaves it, so the sweep below is commanded at the margin "
              "itself, and the trip point above is what the loop's own refusal reports rather "
              "than a figure copied out of its source.")
    else:
        widening = findings["widening"]
        write("**The protection margin is not that bound.** Another of the admission path's "
              "ceilings is the tighter one on this machine, so the widened margin refuses "
              "nothing: every target it would refuse has already been refused by an earlier "
              "ceiling. The trip point is unreported for the same reason — the loop is never "
              "asked about it, and a figure named here that nothing was measured against would "
              "be this record inventing the number the whole mapping is anchored to.")
        write("")
        write("What that costs the sweep below is worth stating plainly. It is commanded at the "
              "hottest target this design admits, which is as close to the margin as a delivery "
              "on this machine can be commanded — but it is not evidence that the margin refusal "
              "does anything, because removing that refusal outright would leave every figure in "
              "this record unchanged.")
        write("")
        write("How far this machine stands from the case where its margin does bind is a figure "
              "rather than a sentence: the declared error against `%s` would have to widen from "
              "%s to %s of its own value before the protection margin overtook the ceiling that "
              "is presently tighter. That is read and not swept. No delivery below is run "
              "against a widened description, because a description nobody claims is not a "
              "machine a verdict can be taken about, and a table of failures against one would "
              "read as findings about this design." % (
                  widening["coefficient"], FIGURE_FORMAT % widening["declared"],
                  FIGURE_FORMAT % widening["widened_to"]))
    write("")

    write(MAPPING_HEADING)
    write("")
    write("Every corner the enumeration covers, at the target the sweep was commanded at. A "
          "corner is counted only in the degrading direction and clamped at nothing, so one that "
          "carries the machine away from the trip point contributes nothing rather than "
          "narrowing the margin. A corner that ran nothing is a coefficient the description "
          "declares no error against, or one whose corner the structure will not admit as a "
          "machine — which is a different finding from a contribution of nothing.")
    write("")
    write("| Corner | Kind | Coefficient | End | Declared error | Written at | Ran | "
          "Contribution (C) |")
    write("|---|---|---|---|---|---|---|---|")
    for corner in shipped["corners"]:
        write("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
            corner["which"], "joint" if corner["joint"] else "independent",
            _coefficient_cell(corner), corner["end"],
            FIGURE_FORMAT % corner["declared"], FIGURE_FORMAT % corner["factor"],
            "ran" if corner["ran"] else "not-run",
            FIGURE_FORMAT % corner["contribution_c"]))
    write("")
    write("The margin is %s C: the un-widened gap of %s C plus the worst single corner's %s C, "
          "which is corner %d. %d of %d corners ran and %d cost the gap anything." % (
              FIGURE_FORMAT % margin["widened_c"], FIGURE_FORMAT % margin["unwidened_c"],
              FIGURE_FORMAT % margin["worst_c"], margin["worst_at"], margin["run"],
              margin["corners"], margin["contributing"]))
    write("")

    write(VERDICT_HEADING)
    write("")
    write("Each corner's machine is delivered against over the same course — the pump held at %d "
          "permille of full scale for %d control intervals — commanded at %s C, the highest "
          "target the loop takes, with the control path held at the shipped description while "
          "the machine moves to the corner. The verdict is taken over intervals %d to %d, the "
          "trailing tenth of the draw, against the half-width of %s C the design declares." % (
              findings["draw_permille"], DRAW_STEPS, FIGURE_FORMAT % findings["target_c"],
              findings["window"][0], findings["window"][1], FIGURE_FORMAT % findings["band_c"]))
    write("")
    write("Both ends of every coefficient are run, including the ends `params/thermoblock.md` "
          "calls one-sided (%s). The description's grammar carries no statement of sidedness — "
          "the line beside a value carries a symmetric fraction and nothing that could say "
          "otherwise — so the margin above weighs both, which can only widen it and is the safe "
          "direction for a protection bound. A delivery verdict is a different kind of claim: at "
          "the end the description does not claim it would be a verdict about a machine nobody "
          "says exists, so those rows carry their figure and report `not-claimed` rather than a "
          "pass or a failure." % ", ".join("`%s`" % name for name in sorted(ONE_SIDED)))
    write("")
    write("| Corner | Coefficient | End | Written at | Worst departure (C) | Verdict |")
    write("|---|---|---|---|---|---|")
    for verdict in findings["verdicts"]:
        corner = verdict["corner"]
        write("| %d | %s | %s | %s | %s | %s |" % (
            corner["which"], _coefficient_cell(corner), corner["end"],
            FIGURE_FORMAT % corner["factor"],
            FIGURE_FORMAT % verdict["worst_departure_c"], _verdict_word(verdict)))
    write("")

    write(STEAM_MAPPING_HEADING)
    write("")
    write("The steam side sizes a margin of its own, against a trip point of its own, out of the "
          "same declared error. Its un-widened gap is nothing: that loop's ready phase holds a "
          "temperature against no declared temperature band at all — the band it is held to is a "
          "pressure one — so every kelvin of its margin is earned by declared model error rather "
          "than inherited.")
    write("")
    write("Its target is not commanded but declared: `%s` names the ready temperature the loop "
          "is brought up holding, and the loop refuses to come up at all where that target does "
          "not leave the widened margin between itself and the trip point. The declared target "
          "is %s C and the highest the loop would come up at is %s C, so the margin has %s C of "
          "room here and is not what stops this loop's target either." % (
              _relative(findings["declaration"]),
              FIGURE_FORMAT % steam_target["ready_c"],
              FIGURE_FORMAT % steam_target["highest_c"],
              FIGURE_FORMAT % (steam_target["highest_c"] - steam_target["ready_c"])))
    write("")
    write("| Corner | Kind | Coefficient | End | Declared error | Written at | Ran | "
          "Contribution (C) |")
    write("|---|---|---|---|---|---|---|---|")
    for corner in shipped["steam_corners"]:
        write("| %d | %s | %s | %s | %s | %s | %s | %s |" % (
            corner["which"], "joint" if corner["joint"] else "independent",
            _coefficient_cell(corner), corner["end"],
            FIGURE_FORMAT % corner["declared"], FIGURE_FORMAT % corner["factor"],
            "ran" if corner["ran"] else "not-run",
            FIGURE_FORMAT % corner["contribution_c"]))
    write("")
    write("The steam margin is %s C: the un-widened gap of %s C plus the worst single corner's "
          "%s C, which is corner %d. %d of %d corners ran and %d cost the gap anything." % (
              FIGURE_FORMAT % steam_margin["widened_c"],
              FIGURE_FORMAT % steam_margin["unwidened_c"],
              FIGURE_FORMAT % steam_margin["worst_c"], steam_margin["worst_at"],
              steam_margin["run"], steam_margin["corners"], steam_margin["contributing"]))
    write("")

    write(STEAM_VERDICT_HEADING)
    write("")
    write("Each corner's machine is drawn from over the steam side's own course, with the loop "
          "brought up at the ready temperature its declaration names. There is no second "
          "description to hold the loop at while the machine moves, and none is needed: that "
          "loop is built from its declaration and from no description of a casting at all, so "
          "the split the coffee side has to arrange is structural here.")
    write("")
    write("The verdict is the pressure the draw came to rest at, taken over %s, against the "
          "floor of %d and ceiling of %d milli-bar the declaration states." % (
              "intervals %d to %d, the trailing third of the stretch steam was actually being "
              "delivered over" % findings["steam_window"] if findings["steam_window"]
              else "the stretch steam was actually being delivered over",
              findings["steam_band_milli_bar"][0], findings["steam_band_milli_bar"][1]))
    write("")
    write("| Corner | Coefficient | End | Written at | Worst pressure (milli-bar) | Verdict |")
    write("|---|---|---|---|---|---|")
    for verdict in findings["steam_verdicts"]:
        corner = verdict["corner"]
        write("| %d | %s | %s | %s | %d | %s |" % (
            corner["which"], _coefficient_cell(corner), corner["end"],
            FIGURE_FORMAT % corner["factor"], verdict["worst_milli_bar"],
            _verdict_word(verdict)))
    write("")

    write(REFUSED_HEADING)
    write("")
    if not findings["refused"]:
        write("Nothing. Every corner the enumeration covers produced a machine and a delivery.")
    else:
        write("| Corner | Coefficient | End | Why |")
        write("|---|---|---|---|")
        for corner, why in findings["refused"]:
            write("| %d | %s | %s | %s |" % (corner["which"], _coefficient_cell(corner),
                                             corner["end"], why))
    write("")

    write("## What this does not settle")
    write("")
    write("Whether the fitted protective device opens where the parts list says it does. No "
          "thermostat on this machine has been read, whether it resets itself is not established, "
          "and the thermal fuse beside it has no rating recorded at all — so the trip point this "
          "margin is measured against is the earliest documented opening of one of three devices "
          "rather than the earliest opening of the protection as a whole.")
    write("")
    write("Whether the declared errors the margin is sized from are the real ones. They are "
          "judgements about how well a kind of coefficient is known, and the margin moves with "
          "them: a coefficient measured better or worse than assumed moves this figure without "
          "anything about the machine having changed.")
    write("")
    write("The measurement half of commanded margin. What a sensor may be wrong by is the other "
          "half and none of it is carried here; a margin that folded the two together would leave "
          "neither half separately answerable.")
    return "\n".join(lines) + "\n"


# --- Reading a committed record back --------------------------------------


def _table_rows(text, heading):
    """Every table row under one heading of a committed record."""
    rows = []
    within = False
    for line in text.splitlines():
        if line.startswith("## "):
            within = line.strip() == heading
            continue
        if within and line.startswith("| "):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def mapping_rows(text):
    """The mapping table of a committed record, as (corner, coefficient, end,
    declared, factor, ran, contribution)."""
    return [tuple(row) for row in _table_rows(text, MAPPING_HEADING)
            if len(row) == 8 and row[0] not in ("Corner", "---")]


def verdict_rows(text):
    """The verdict table of a committed record, as (corner, coefficient, end,
    factor, departure, verdict)."""
    return [tuple(row) for row in _table_rows(text, VERDICT_HEADING)
            if len(row) == 6 and row[0] not in ("Corner", "---")]


def steam_mapping_rows(text):
    """The steam side's mapping table of a committed record."""
    return [tuple(row) for row in _table_rows(text, STEAM_MAPPING_HEADING)
            if len(row) == 8 and row[0] not in ("Corner", "---")]


def steam_verdict_rows(text):
    """The steam side's verdict table of a committed record."""
    return [tuple(row) for row in _table_rows(text, STEAM_VERDICT_HEADING)
            if len(row) == 6 and row[0] not in ("Corner", "---")]


def standing_rows(text):
    """The standing table of a committed record, as one row per description the
    highest admissible target was read against."""
    return [tuple(row) for row in _table_rows(text, STANDING_HEADING)
            if len(row) == 5 and row[0] not in ("Highest target taken (C)", "---")]


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--description", default=None,
                        help="the parameter description to read the margin against")
    parser.add_argument("--limits", default=None,
                        help="what a reading off that machine may be")
    parser.add_argument("--tolerance", default=sweep.TOLERANCE_DECLARATION,
                        help="the bands a delivery is held to")
    parser.add_argument("--steam-declaration", default=sweep.STEAM_CONTROL_DECLARATION,
                        help="the figures the steam control law is given")
    parser.add_argument("--report", default=REPORT_PATH,
                        help="where the record is written")
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
        outside = [verdict for verdict in findings["verdicts"] if not verdict["within_band"]]
        print("%s written: margin %s C over %d corners, %d delivered against, %d outside the "
              "band, %d not delivered against" % (
                  arguments.report, FIGURE_FORMAT % findings["shipped"]["margin"]["widened_c"],
                  findings["shipped"]["margin"]["corners"], len(findings["verdicts"]),
                  len(outside), len(findings["refused"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
