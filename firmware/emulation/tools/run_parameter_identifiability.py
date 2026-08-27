#!/usr/bin/env python3
"""Ask, of every coefficient the control path's reconstructed state rests on,
whether this machine could tell it apart from the others at all.

The perturbed re-runs this reads are not taken again. run_parameter_sweep.py
already puts both ends of every coefficient's declared error through both closed
loops, and that sweep exists to answer a different question off the same runs:
how far the *delivery* moved. This asks how far the *channels the machine can
observe* moved, which is the same re-run read at a different place. Building a
second perturbation harness to ask it would have meant two harnesses that must
agree about what a perturbed machine does, and the first time they stopped
agreeing there would be nothing to say which of them was the machine.

The two questions are not the same and neither answers the other. A coefficient
can dominate the delivery -- its own declared error walking the drink most of the
way out of the band the design holds it to -- and still be one no reading of this
machine can separate from another coefficient's error. Such a coefficient is the
worst case there is: it is spending the margin, and no amount of running the
machine will ever say that it is the one spending it, because every channel that
could tell would move the same way if a different coefficient were wrong instead.

WHAT IS COMPARED

For each coefficient the sweep perturbed, half the difference between the run at
the top of its declared error and the run at the bottom is taken, channel by
channel and interval by interval. That is its signature: the shape its own
uncertainty stamps on what the machine can see. Half the difference of the two
corners rather than one corner against the middle, because it is the part of the
response linear in the coefficient -- and the linear part is the only part
another coefficient's uncertainty could stand in for. A comparison that kept the
curvature would be free to separate two coefficients on how differently their
relations bend at their own corners, which is a difference no observation of a
machine sitting anywhere else could exploit.

A coefficient is identifiable here when two things hold. Its signature has to
reach at least one channel by more than that channel could resolve -- otherwise
nothing observes it, whatever else is true. And no combination of the other
in-scope coefficients' signatures may reproduce it: what is computed is the part
of its signature that lies outside everything the others together can span, and
that part has to survive the same resolution. A coefficient failing either is
named as not shown identifiable rather than left out or assumed identifiable,
because an unproven identifiability and a disproven one read alike from a table
and only one of them is safe to design against.

WHAT "COULD RESOLVE" IS TAKEN FROM

Two floors, neither of them a figure chosen here, and the coarser of the two is
what a difference has to clear.

The first is what the machine's own reading of a channel could carry. The
hardware seam's implementation declares a converter full scale and a count at
that scale, and every reading the control path acts on is that division; a
difference smaller than one count is a difference the machine reports as no
difference at all. It is read out of the seam's source, the same figure and by
the same reader the cross-tier comparison already stands its readings up
through, so a board with a finer converter moves this analysis without anything
here being edited.

The second is what the sweep's own arithmetic could express. Every quantity the
model carries is IEEE-754 binary32, so two runs' figures for one channel cannot
sit closer than one unit in the last place at the magnitude that channel
reached -- and the magnitude taken is the largest reached anywhere in the sweep,
including under perturbation, because a run that carried a channel higher than
the unperturbed one carried the last place up with it.

The reading floor is presently the coarser of the two by three and a half orders
of magnitude on every channel, so it is what decides. Taking the wider of them
rather than naming one is what keeps that true of a machine whose converter is
finer than the model's own arithmetic, which is a board somebody could
legitimately choose.

Two things about that reading floor have to be read with it. The seam declares
one full scale for every channel, so the same figure stands against degrees,
bar and millilitres a second alike -- which is a fact about a board nobody has
yet chosen instruments for rather than a per-channel instrument declaration, and
it is generous on the channels whose range is small. And the test is taken on
the largest single disagreement rather than on a sustained one: a bias sitting
just under a count for the whole of a draw is separable in practice by
averaging, and is called unresolvable here. Both err the same way, toward
naming a coefficient not shown identifiable, which is the direction that cannot
mislead somebody into leaving an instrument out.

WHAT THE PERTURBATION MOVES, AND WHY IT IS DONE TWICE

The same determination is taken twice, over two sweeps that differ in one thing
and nothing else, and both are reported.

In the first, each corner run hands one perturbed description to the whole
build, and the build gives it to both the plant and the control path -- so the
machine is different and the control path's own estimator already knows it. The
question that answers is precise: if this machine were built to a coefficient
that far from the description and everything about it were consistent, would the
channels look different from a machine built to a different coefficient instead?
That is a commissioning question, and it is the one the sweep was originally
built to ask.

In the second, the perturbed description goes to the machine alone and the
control path is held at the unperturbed one throughout. That is what fouling and
ageing do: the casting moves away from figures its controller still believes.
The reconstruction is then biased rather than merely different -- the loop holds
its own estimate at the target instead of the delivery -- and what the channels
carry changes with it.

Which way it changes is computed here and not assumed, and it is not one way.
Holding the control path still withdraws a correction, and a correction
withdrawn can leave a coefficient's own error standing on the channels as
readily as it can absorb it: on the model this presently runs against, the
figure a verdict is taken on falls under drift for some coefficients and rises
for others, and so does the reach the signature manages at all. So neither
reading bounds the other, and neither is the conservative one to read alone. The
record states which coefficients moved which way out of the two determinations,
and names each crossing between the two sets of verdicts one at a time, rather
than asserting a direction that a different model could contradict.

Neither reading replaces the other. They answer different questions and a design
needs both: whether two machines built differently could be told apart, and
whether one machine going wrong could be caught. A coefficient identifiable
under the first and not the second is the case worth naming, and the record
names it, because it is the one where a machine that passes every commissioning
check can still drift with nothing to report it.

Only the coffee side can be asked the second question, and the reason is
structural rather than a limitation here: the steam law is built from its own
declaration and from no description of a casting at all, so there is nothing on
that side for a perturbation to be kept out of and its figures stand where they
were under either reading. The record says so from the runs rather than
asserting it.

WHAT IS IN SCOPE

The coefficients the control path's reconstructed state depends on, and this is
established from the runs rather than listed here. The seam reconstructs one
state -- the temperature of the water on its way to the group, which no channel
observes -- and the sweep's coffee-side draw reports, at every interval, the
plant's own value of that same temperature. So a coefficient is in scope exactly
when perturbing it moved that figure.

That figure is the true state rather than the reconstruction of it: the
estimator holds a plant model of its own, corrected against the sensors, and
what it answers is a different number. It stands in because what is being asked
is which coefficients the reconstruction rests on, and the reconstruction is the
same relations over the same coefficients -- so a coefficient the true outlet
temperature does not depend on is one no reconstruction of it can depend on
either. What the substitution can miss is a coefficient whose effect on the true
outlet the closed loop cancels while the reconstruction still rests on it; a
list written into this file instead would miss more, and would go on looking
right after the model changed.

Every coefficient the sweep perturbed is laid out against the channels all the
same, in scope or not, and the ones out of scope are named with the reason. Two
of them are coefficients the dominance ranking could not weigh, and they are
here rather than excluded for the reason that ranking excluded them: a
coefficient reaching no delivery still moves channels, so it still confounds a
fit against those channels, and leaving it out would report a separability the
machine does not have. It is given no verdict of its own, since no
reconstruction rests on it.

The steam knob is not among the channels and could not be. It reports where an
operator has put a valve, which no coefficient of a casting can move.

WHAT THIS IS NOT

It is not a fit. Nothing here recovers a coefficient from data; what is asked is
whether the channels carry a signature that could distinguish it, which is the
question that has to be settled before an instrument is bought and the only one
that can be settled before the machine is measured. A coefficient this names
identifiable may still be recovered badly by a real fit against real noise over
a real draw, and this says nothing about that.

It is not a recommendation to buy anything either. Where the analysis says a
channel nothing is presently fitted to is what separates two coefficients, that
is a finding and not a purchase: what instrument, at what cost, on what part of
the path, is the physical track's decision.

And it is analysis against an estimated model. Every coefficient in the
description is an estimate and so is the error declared against it, so this is
meant to be re-run against a measured model rather than argued about against
this one -- which is why the record it writes names the files and their digests
and why pointing the same method at a replacement needs no edit to it.
"""

import argparse
import math
import os
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
import seam_channels  # noqa: E402

#: Where the finding and the per-channel figures it was drawn from are kept.
#: Beside the dominance ranking rather than inside it, because the two answer
#: different questions off the same runs and a reader who has the answer to one
#: has not been given the other.
REPORT_PATH = os.path.join(REPOSITORY_DIR, "docs", "parameter-identifiability.md")

#: How many bits of significand IEEE-754 binary32 carries, counting the implicit
#: one. Used to size one unit in the last place at a given magnitude; named
#: rather than written as a number at the point of use, because it is a property
#: of the format every quantity in the model is carried in and not a tuning
#: figure this analysis chose.
SINGLE_PRECISION_SIGNIFICAND_BITS = 24

#: The relative size below which a vector's remainder, after being taken
#: orthogonal to the ones before it, is rounding rather than direction.
#:
#: Derived and not chosen: the projections below are done in the double
#: precision Python carries, whose significand is 53 bits, and modified
#: Gram-Schmidt with a second orthogonalising pass leaves a relative error of
#: order the number of vectors times that. A remainder smaller than that is not
#: a direction the arithmetic can distinguish from its own rounding, and
#: normalising it would amplify rounding into a basis vector.
#:
#: It decides only which directions the basis carries, never whether a
#: coefficient is identifiable. That is decided on the reconstructed remainder
#: against the machine's own reading resolution, which is fifteen orders of
#: magnitude coarser than this.
DOUBLE_PRECISION_RELATIVE_FLOOR = 2.0 ** -52

#: The three verdicts a coefficient can leave this analysis with, written as
#: they are into the record. The two ways of failing are kept apart rather than
#: collapsed into one, because they are different findings about the machine: a
#: coefficient nothing observes needs a channel that does not exist, and one
#: whose signature the others reproduce needs a channel that separates it from
#: them -- and the second may already be fitted.
IDENTIFIABLE = "identifiable"
BELOW_WHAT_A_READING_CARRIES = "not shown identifiable: below what any channel could resolve"
REPRODUCED_BY_THE_OTHERS = "not shown identifiable: reproduced by a combination of the others"

#: Why a coefficient the sweep perturbed is not asked about here.
REACHES_NO_RECONSTRUCTION = "reaches no reconstructed state"

#: What the two readings are called wherever one of them has to be named.
#:
#: They are named for what was done to the machine rather than for the harness
#: arrangement that produced them -- "coupled" and "decoupled" say what the two
#: descriptions did and not what the machine did, and a reader of the record is
#: being told about a machine. The first is two machines each built consistently
#: to its own coefficients; the second is one machine that has moved away from
#: the figures its controller still holds.
BUILT_DIFFERENTLY = "built differently"
DRIFTED = "drifted"

#: What a coefficient the first reading shows identifiable and the second does
#: not is called. It is the finding the second reading exists to produce: a
#: machine that passes every commissioning check and then drifts with nothing to
#: report it.
HIDDEN_BY_DRIFT = "identifiable when built differently, not when drifted"

#: How the second reading's scratch directory is named from the first's.
#:
#: A directory of its own rather than the first reading's, on the terms the
#: sweep already states for a second model: every run writes one description per
#: coefficient per corner under the same names, so two sweeps sharing a
#: directory leave the second's standing where the first's were. Nothing reading
#: a finished run would notice, and anything going back to the files to
#: establish what a run handed the machine would be reading the other reading's.
#:
#: Derived from the first reading's directory rather than fixed, so that a
#: replacement model analysed in a directory of its own gets a second reading in
#: a directory of its own too. A fixed path here would put every model's second
#: reading in the same place, which is the collision this avoids reintroduced
#: one level down.
DRIFTED_WORKSPACE_SUFFIX = "-drifted"


def drifted_workspace(workspace):
    """Where the second reading of a sweep taken in `workspace` writes its own
    perturbed descriptions."""
    return workspace + DRIFTED_WORKSPACE_SUFFIX

#: The table in the hardware seam's implementation that says which converter
#: input, if any, stands behind each of the seam's sensor channels, and what it
#: writes where there is none. Named here rather than matched by a pattern of
#: this file's, so that a table renamed in the seam fails this analysis where it
#: is looked for rather than leaving it reporting every channel as unfitted.
SENSOR_INPUT_TABLE = "sensor_adc_channel"
NO_SENSOR_INPUT = "SENSOR_INPUT_NONE"

#: What the seam's own name for the flow channel carries, which is how the drawn
#: rate this analysis reads is matched to a channel of the seam. The four
#: quantities a converter carries are matched by their declaration order, which
#: is what both draws' own tables state they follow; the drawn rate is printed
#: outside that ordered set and so has no position to be matched by.
SEAM_FLOW_CHANNEL = "FLOW"

#: How the figures are written into the record. Three significant figures, which
#: is more than an analysis of a description whose own errors run from two per
#: cent to eighty can support.
FIGURE_FORMAT = "%.3g"


class IdentifiabilityError(RuntimeError):
    """The analysis could not be run, or could not be run over everything it
    covers."""


# --- What a difference on a channel has to clear ----------------------------


def reading_resolution():
    """What one count of the machine's converter is worth, in a channel's own
    unit.

    Read out of the hardware seam's implementation through the reader the
    cross-tier comparison already stands its readings up through, rather than
    written here. The seam declares one full scale for every channel, so this is
    one figure and not five; a board declaring another moves every floor below
    without anything here being edited, which is the whole reason it is read
    rather than stated.
    """
    counts, milli = cross_tier.converter_scale()
    if counts <= 0 or milli <= 0:
        raise IdentifiabilityError(
            "the hardware seam declares a converter full scale of %d counts at %d milli-units, "
            "so there is no reading resolution for a difference to be measured against"
            % (counts, milli))
    return float(milli) / float(counts) / 1000.0


def arithmetic_resolution(peak):
    """One unit in the last place of a single-precision figure of this size.

    The floor beneath which two runs of the model could not have differed on a
    channel at all, whatever the machine's instrument could have carried: every
    quantity the model holds is binary32, and the sweep reads the figures back
    at nine significant digits, which round-trips that format exactly. So a
    reported difference smaller than this is not a small effect but an effect
    the arithmetic had no room to express.

    A channel that carried nothing anywhere in the sweep has every difference on
    it exactly zero, so what is returned for it divides zero. One last place at
    unity is returned so the arithmetic has a number to work with, and no
    verdict anywhere depends on which number that is.
    """
    if peak <= 0.0:
        return 2.0 ** -SINGLE_PRECISION_SIGNIFICAND_BITS
    return 2.0 ** (math.frexp(peak)[1] - SINGLE_PRECISION_SIGNIFICAND_BITS)


def floors(findings, reading=None):
    """What a difference on each channel of each side has to clear to be a
    difference at all.

    The wider of the two: what the machine's reading could carry, and what the
    model's own arithmetic could express. Taking the wider rather than naming
    one is what keeps this right for a board whose converter is finer than
    binary32 -- a reading that resolves what the model cannot compute is
    resolving the model's rounding.
    """
    reading = reading_resolution() if reading is None else reading
    return dict(
        (side, dict((key, {
            "reading": reading,
            "arithmetic": arithmetic_resolution(peaks[key]),
            "peak": peaks[key],
            "floor": max(reading, arithmetic_resolution(peaks[key])),
        }) for key in sweep.OBSERVED_CHANNELS))
        for side, peaks in findings["peaks"].items())


# --- One coefficient's signature, in units of what a channel could resolve ---


def component_layout(findings):
    """The order the channels are laid end to end in, as (side, channel).

    One order, fixed here and used for every coefficient, because the comparison
    below is between one coefficient's signature and another's and two
    signatures laid out differently are not comparable at all. The sides are
    taken in the sweep's own order so the layout follows the runs rather than
    whatever order a dictionary happened to iterate in.
    """
    return [(side, key)
            for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE)
            if side in findings["reference"]
            for key in sweep.OBSERVED_CHANNELS]


def scaled_signature(entry, layout, floor):
    """One coefficient's signature over every channel, in units of what that
    channel could resolve.

    Dividing each channel by its own floor is what makes a degree of block
    temperature and a hundredth of a bar of steam pressure the same kind of
    number, and it is the one scaling that is not a choice: it weighs each
    channel by how finely the machine can see it, which is exactly the weighting
    the question "could the machine tell these apart" asks for. Any other -- by
    each channel's own range, by its variance over the draw, by nothing at all
    -- would be a statement about the units the channels happen to be carried
    in.

    Laid out end to end rather than kept per channel, because what follows asks
    whether one whole signature lies inside what the others span, and a
    signature is the whole of what a coefficient did across every channel of
    both draws.
    """
    laid = []
    for side, key in layout:
        divisor = floor[side][key]["floor"]
        series = entry["signature"].get(side, {}).get(key)
        if series is None:
            raise IdentifiabilityError(
                "'%s' has no recorded effect on the %s side's %s, so the sweep did not put both "
                "of its corners through that draw and there is no signature to compare"
                % (entry["coefficient"], side, key))
        laid.extend(value / divisor for value in series)
    return laid


def channel_spans(findings, layout):
    """Where each channel's own stretch of a laid-out signature begins and ends.

    Kept so that a remainder computed over the whole layout can still be
    reported per channel, and so that a coefficient's reach can be reported per
    channel too. Where a signature lands is as much of the finding as how large
    it is: a coefficient reaching only a channel nothing is fitted to and one
    reaching a channel the machine already reads are opposite cases, and a
    figure taken over the whole layout tells them apart nowhere.
    """
    spans = {}
    at = 0
    for side, key in layout:
        length = len(findings["reference"][side]["channels"][key])
        spans[(side, key)] = (at, at + length)
        at += length
    return spans


# --- Whether one signature lies inside what the others span -----------------


def _dot(left, right):
    return math.fsum(a * b for a, b in zip(left, right))


def _norm(vector):
    return math.sqrt(math.fsum(value * value for value in vector))


def span_of(vectors):
    """An orthonormal basis for what a set of signatures spans, and how each
    signature is built out of it.

    Modified Gram-Schmidt with a second orthogonalising pass. The case this has
    to survive is two signatures pointing nearly the same way, which is exactly
    the case an orthogonalisation loses accuracy on -- and losing it here does
    not produce an obviously wrong answer, it produces a remainder made of the
    arithmetic's own rounding, read as a coefficient being distinguishable when
    what is true is that the arithmetic could not tell that it is not. The
    modified form is what keeps that loss proportional to how near the two are
    rather than to its square; the second pass is cheap insurance on top, and at
    the score of vectors this runs over it costs nothing worth measuring.
    Forming the normal equations and solving those instead would square the
    conditioning, which is the same failure by another route, and is why the
    weights below are recovered by back-substitution rather than that way.

    A vector whose remainder falls below what the arithmetic can distinguish
    from rounding is dropped rather than normalised, which is what keeps a
    signature that is exactly a combination of earlier ones from contributing a
    direction made of rounding. Dropping it does not change what the set spans.

    Three things come back: the basis, which vector each of its directions came
    from, and the overlaps taken along the way. The last is what the vectors
    look like written in that basis, upper-triangular by construction, and it is
    kept because the size of the combination that reproduces a signature is part
    of whether that reproduction means anything -- a combination reproducing one
    coefficient's uncertainty only by supposing the others out by a hundred
    times their own declared errors is arithmetic rather than a finding about a
    machine, and nothing that discards these overlaps can tell the two apart.
    """
    basis = []
    from_vector = []
    overlaps = []
    guard = DOUBLE_PRECISION_RELATIVE_FLOOR * (len(vectors) + 1)
    for at, vector in enumerate(vectors):
        remainder = list(vector)
        started_at = _norm(remainder)
        if started_at == 0.0:
            continue
        along_basis = [0.0] * len(basis)
        for _ in range(2):
            for where, direction in enumerate(basis):
                overlap = _dot(direction, remainder)
                if overlap != 0.0:
                    along_basis[where] += overlap
                    remainder = [value - overlap * along
                                 for value, along in zip(remainder, direction)]
        left = _norm(remainder)
        if left <= guard * started_at:
            continue
        basis.append([value / left for value in remainder])
        from_vector.append(at)
        overlaps.append(along_basis + [left])
    return basis, from_vector, overlaps


def orthonormal_basis(vectors):
    """An orthonormal basis for what a set of signatures spans, for a caller
    that wants the span and not how anything is built out of it."""
    return span_of(vectors)[0]


def combination_size(basis, from_vector, overlaps, subject, count):
    """How much of the others a combination reproducing one signature has to
    use, as the sum of the sizes of its terms.

    Every signature here is already scaled to one declared error of its own
    coefficient, so a term of one is that coefficient being out by exactly the
    amount the description admits it may be out by. A total below one therefore
    says the confounding combination sits inside the others' own declared
    errors, which is a statement about this machine; a total of a hundred says
    the arithmetic found a combination nobody has any reason to think the
    machine is in, which is not.

    The weights are recovered by back-substitution through the overlaps the
    orthogonalisation already took, rather than by forming and solving the
    normal equations, which would square the conditioning at exactly the point
    where two signatures nearly coincide and the weights grow.

    Where the others are themselves dependent, the combination is not unique --
    a vector dropped as reproducible by the ones before it contributes nothing
    and is reported as used not at all. That is the representative that uses no
    more of the set than it has to; another exists for every direction the
    dependency leaves free, and none of them is smaller.
    """
    if not basis:
        return 0.0
    against = [_dot(direction, subject) for direction in basis]
    weights = [0.0] * count
    for where in range(len(basis) - 1, -1, -1):
        standing = against[where]
        for later in range(where + 1, len(basis)):
            standing -= overlaps[later][where] * weights[from_vector[later]]
        weights[from_vector[where]] = standing / overlaps[where][where]
    return math.fsum(abs(weight) for weight in weights)


def unreproduced_part(subject, others, basis):
    """The part of one signature that no combination of the others reproduces.

    Both arguments arrive as coordinates against a basis for everything under
    consideration, which is what makes this affordable: every signature lies in
    that span by construction, so the whole comparison can be done in as many
    dimensions as there are coefficients rather than as many as there are
    intervals.

    The remainder is what is left of the subject after removing everything the
    others can account for, and it is arrived at by projection rather than by
    fitting coefficients and subtracting their combination. The two are the same
    quantity; the first does not require the coefficients to be recoverable,
    which is precisely what is in doubt when two signatures nearly coincide.

    It is then written back out over the channels, because what a reader has to
    be told is which channel carries the part nothing else reproduces -- and
    that cannot be read off a coordinate. On this machine one of those channels
    has no instrument on it, which changes what the finding means.

    Three things come back: that written-out remainder, what fraction of the
    subject's own size it is, and how much of the others the combination that
    got nearest had to use. The three answer different questions and only the
    first can be put against a resolution. The fraction says how nearly the
    others reproduce this signature at all, and it can only fall as more
    signatures are admitted to the comparison -- where the largest single figure
    in the remainder can move either way, since a fit that shrinks a whole
    remainder is free to shift where its widest disagreement lands. The size of
    the combination says whether the reproduction is a statement about the
    machine or about the arithmetic.
    """
    within, from_vector, overlaps = span_of(others)

    remainder = list(subject)
    for direction in within:
        overlap = _dot(direction, remainder)
        if overlap != 0.0:
            remainder = [value - overlap * along for value, along in zip(remainder, direction)]

    written = [0.0] * len(basis[0]) if basis else []
    for weight, direction in zip(remainder, basis):
        if weight == 0.0:
            continue
        written = [standing + weight * along for standing, along in zip(written, direction)]

    whole = _norm(subject)
    return (written,
            (_norm(remainder) / whole if whole > 0.0 else 0.0),
            combination_size(within, from_vector, overlaps, subject, len(others)))


# --- The second reading: the machine alone ----------------------------------


_DRIFTED = {}


def drifted_sweep(findings):
    """The same sweep again, with every perturbation applied to the machine
    alone and the control path held at the description this one was taken
    against.

    The coupled findings are handed in rather than the files being named again,
    for two reasons. The description, the limits, the steam declaration and the
    band a delivery is held to have to be the same four files or the two
    readings are of two machines and nothing can be concluded from their
    disagreeing. And the host artefact is already built, so re-deriving it here
    would pay for a second build to produce the same executable.

    What is not shared is the workspace: the perturbed descriptions this reading
    writes carry the same names as the first reading's, and one directory could
    hold only one of them.

    Cached against the machine it is about, on the terms the sweep caches its own
    run: four host draws per coefficient is the most expensive thing in this
    tier and every caller wants the same ones. Keyed rather than kept as a single
    record, so that a suite analysing a replacement model gets that model's
    second reading rather than the shipped machine's.
    """
    key = (findings["description"], findings["limits"], findings["declaration"],
           findings["tolerance"], findings["workspace"])
    if key not in _DRIFTED:
        _DRIFTED[key] = sweep.run(
            description=findings["description"], limits=findings["limits"],
            declaration=findings["declaration"], tolerance=findings["tolerance"],
            executable=findings["executable"],
            workspace=drifted_workspace(findings["workspace"]),
            control_description=findings["description"])
    return _DRIFTED[key]


def sides_the_readings_differ_on(findings, drifted_findings):
    """Which sides' recorded signatures the two readings do not agree about.

    Computed rather than stated, though what it will presently return is
    predictable from the structure: the steam law is built from its own
    declaration and from no description of a casting, so holding a control
    description still cannot change anything that side does. Reporting that from
    the runs is what keeps the record right on the day some steam-side law does
    reconstruct something -- a statement written here instead would go on
    claiming the two readings coincide there after they had stopped.
    """
    by_name = dict((entry["coefficient"], entry) for entry in drifted_findings["swept"])
    differing = []
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        moved = False
        for entry in findings["swept"]:
            other = by_name.get(entry["coefficient"])
            if other is None:
                continue
            for key in sweep.OBSERVED_CHANNELS:
                if entry["signature"].get(side, {}).get(key) != \
                        other["signature"].get(side, {}).get(key):
                    moved = True
                    break
            if moved:
                break
        if moved:
            differing.append(side)
    return differing


# --- The finding ------------------------------------------------------------


def in_scope(entry):
    """Whether the control path's reconstructed state rests on this coefficient.

    Asked of what the sweep's coffee-side draw did rather than of a list: that
    draw reports, at every interval, the plant's own temperature of the water on
    its way to the group -- the true value of the one state the estimator seam
    reconstructs and the control law drives on.

    The true value and not the reconstruction of it, which is a different number
    held in a plant model of the estimator's own and corrected against the
    sensors. It stands in because the reconstruction is those same relations
    over those same coefficients, so a coefficient the true outlet temperature
    does not depend on is one no reconstruction of it can depend on either. What
    that substitution can miss is a coefficient whose effect on the true outlet
    the closed loop cancels while the reconstruction still rests on it.
    """
    return entry["reaches_outlet"]


def determine(findings, reading=None):
    """Which coefficients this machine could tell apart, and which it could not.

    Every coefficient the sweep perturbed is laid out over the channels, because
    a coefficient out of scope for the question still confounds the answer if it
    moves the same channels -- so both figures are computed and both reported:
    the part of a signature that the other in-scope coefficients cannot
    reproduce, which is what the verdict is taken on, and the part that no
    coefficient the sweep touched can reproduce, which is what a fit would
    actually be up against.
    """
    layout = component_layout(findings)
    floor = floors(findings, reading)
    spans = channel_spans(findings, layout)

    laid = dict((entry["coefficient"], scaled_signature(entry, layout, floor))
                for entry in findings["swept"])
    basis = orthonormal_basis([laid[entry["coefficient"]] for entry in findings["swept"]])
    coordinates = dict((name, [_dot(direction, vector) for direction in basis])
                       for name, vector in laid.items())

    scoped = [entry["coefficient"] for entry in findings["swept"] if in_scope(entry)]
    if not scoped:
        raise IdentifiabilityError(
            "no coefficient the sweep perturbed moved the temperature the control path "
            "reconstructs, so either this build keeps no such state or the sweep moved nothing, "
            "and there is no identifiability here to establish")
    every = [entry["coefficient"] for entry in findings["swept"]]

    determination = []
    for entry in findings["swept"]:
        name = entry["coefficient"]
        vector = laid[name]

        reached = {}
        for side, key in layout:
            first, last = spans[(side, key)]
            reached[(side, key)] = max((abs(value) for value in vector[first:last]), default=0.0)
        largest = max(reached.values())
        loudest = max(reached, key=lambda where: reached[where])

        record = {
            "coefficient": name,
            "in_scope": in_scope(entry),
            "reached": reached,
            "largest": largest,
            "loudest": loudest,
        }

        if in_scope(entry):
            for what, against in (("against_scoped", scoped), ("against_every", every)):
                written, fraction, used = unreproduced_part(
                    coordinates[name],
                    [coordinates[other] for other in against if other != name],
                    basis)
                record[what] = {
                    "unique": max((abs(value) for value in written), default=0.0),
                    "fraction": fraction,
                    "used": used,
                    "unique_by_channel": dict(
                        ((side, key),
                         max((abs(value) for value in written[spans[(side, key)][0]:
                                                             spans[(side, key)][1]]), default=0.0))
                        for side, key in layout),
                }
            # The verdict, in the order the two conditions are worth being told
            # about. A coefficient nothing observes at all is a finding about
            # the machine's instruments; a coefficient observed but not
            # separable is a finding about which instruments. Reporting the
            # second where the first is true would send a reader looking for a
            # channel to separate a coefficient no channel carries.
            if largest <= 1.0:
                record["verdict"] = BELOW_WHAT_A_READING_CARRIES
            elif record["against_scoped"]["unique"] <= 1.0:
                record["verdict"] = REPRODUCED_BY_THE_OTHERS
            else:
                record["verdict"] = IDENTIFIABLE
        else:
            record["verdict"] = REACHES_NO_RECONSTRUCTION

        determination.append(record)

    # Ordered so that what a reader has to act on comes first: everything the
    # analysis could not show identifiable, then everything it could, each by
    # how far its own signature stands clear of what could be read. Ties broken
    # by name so two coefficients this cannot separate come out in the same
    # order on every run.
    determination.sort(key=lambda record: (
        not record["in_scope"],
        record["verdict"] == IDENTIFIABLE,
        -record["largest"],
        record["coefficient"]))

    return {
        "layout": layout,
        "floors": floor,
        "spans": spans,
        "reading": reading_resolution() if reading is None else reading,
        "scoped": scoped,
        "determination": determination,
    }


def hidden_by_drift(finding, drifted_finding):
    """Every coefficient the first reading shows identifiable that the second
    does not.

    Taken over the coefficients the first reading found identifiable, because
    that is what the finding is a statement about: a coefficient the first
    reading could not show identifiable either was never a commissioning check
    anybody would have passed on, and there is nothing for drift to hide that
    was not hidden already.

    A coefficient the second reading gives no verdict of its own -- because that
    reading found no reconstruction resting on it -- counts here on the same
    terms as one it named not shown identifiable. Both are the machine failing
    to reveal the coefficient once it has drifted, which is the whole of what
    this asks; separating them would be reporting the reason a drifting machine
    says nothing as though it changed whether it says nothing.

    The two readings' figures come back beside the verdicts, because the size of
    the drop is as much of the finding as the crossing of the threshold. A
    coefficient whose distinguishing part falls from a hundred times what could
    be read to just under it, and one that falls from just over to just under,
    are the same verdict about very different machines.
    """
    when_drifted = dict((record["coefficient"], record)
                        for record in drifted_finding["determination"])
    hidden = []
    for record in finding["determination"]:
        if not record["in_scope"] or record["verdict"] != IDENTIFIABLE:
            continue
        drifted = when_drifted.get(record["coefficient"])
        if drifted is not None and drifted["verdict"] == IDENTIFIABLE:
            continue
        hidden.append({
            "coefficient": record["coefficient"],
            "built_differently": record,
            "drifted": drifted,
            "verdict_when_drifted": (REACHES_NO_RECONSTRUCTION if drifted is None
                                     else drifted["verdict"]),
        })
    return hidden


def readings_agree_on(finding, drifted_finding):
    """The coefficients both readings show identifiable, the ones neither shows
    identifiable, and the ones only the second shows identifiable.

    The three cases the crossing above does not cover, taken together so that
    the four between them account for every coefficient a verdict was reached
    about. Two readings and two verdicts leave four ways for a coefficient to
    come out, and a record naming only the one it was built to find would leave
    a reader intersecting two tables by eye for the other three.

    The third is the counterpart of the crossing and it is asked for the same
    reason the crossing is: a coefficient the drifted machine reveals and the
    built-differently one does not is what a claim that drift can only hide
    would rule out in advance. Whether this model produces one is a finding
    about this model, so it is computed here rather than assumed away.

    A coefficient only one reading found a reconstruction resting on has no pair
    of verdicts to agree or disagree about, and is left out of all three -- the
    scope section already reports that disagreement, and folding it in here
    would report a difference in what was asked as a difference in the answer.
    """
    when_drifted = dict((record["coefficient"], record)
                        for record in drifted_finding["determination"])
    both, neither, only_drifted = [], [], []
    for record in finding["determination"]:
        if not record["in_scope"]:
            continue
        drifted = when_drifted.get(record["coefficient"])
        if drifted is None or not drifted["in_scope"]:
            continue
        was = record["verdict"] == IDENTIFIABLE
        now = drifted["verdict"] == IDENTIFIABLE
        if was and now:
            both.append(record["coefficient"])
        elif not was and not now:
            neither.append(record["coefficient"])
        elif now:
            only_drifted.append(record["coefficient"])
    return both, neither, only_drifted


#: The two figures the two readings are compared on where the comparison is
#: about size rather than about a verdict, named here because the record and the
#: checks over it both have to say which one a count is of.
#:
#: The first is what the verdict is taken on; the second is what has to clear a
#: floor before the first is even asked. They can move opposite ways for one
#: coefficient, which is why both are reported rather than one standing for the
#: pair.
THE_VERDICT_FIGURE = "the part no combination of the others reproduces"
THE_REACH_FIGURE = "the largest the signature reached on any channel"


def moved_between_readings(finding, drifted_finding):
    """Which way each coefficient's figures moved when the control path was held
    still, as {figure: (fell, rose, stood still)}.

    Computed rather than stated, because the direction is not one direction and
    a record asserting one would be asserting it of whichever model it was first
    written against. Withdrawing the loop's correction can leave a coefficient's
    own error standing on the channels as readily as it can absorb it, and both
    happen -- so neither reading is an upper bound on the other and a reader told
    that one of them was would be reading the tables through a claim they do not
    support.

    A figure moved by no more than the arithmetic's own rounding is reported as
    having stood still. The guard is the one the orthogonalisation already uses
    and it is derived for the same reason: below it a difference between two
    projections is the double precision they were taken in and not a difference
    between two machines.
    """
    when_drifted = dict((record["coefficient"], record)
                        for record in drifted_finding["determination"])
    moved = dict((figure, ([], [], [])) for figure in (THE_VERDICT_FIGURE, THE_REACH_FIGURE))
    scoped = [record for record in finding["determination"] if record["in_scope"]]
    guard = DOUBLE_PRECISION_RELATIVE_FLOOR * (len(scoped) + 1)
    for record in scoped:
        drifted = when_drifted.get(record["coefficient"])
        if drifted is None or not drifted["in_scope"]:
            continue
        for figure, of in ((THE_VERDICT_FIGURE, lambda one: one["against_scoped"]["unique"]),
                           (THE_REACH_FIGURE, lambda one: one["largest"])):
            was, now = of(record), of(drifted)
            fell, rose, stood = moved[figure]
            entry = (record["coefficient"], was, now)
            if abs(now - was) <= guard * max(abs(was), abs(now)):
                stood.append(entry)
            elif now < was:
                fell.append(entry)
            else:
                rose.append(entry)
    return moved


def why_no_instrument_recovers(hidden):
    """Why an instrument on a channel this record models does not buy back what
    drift hides, coefficient by coefficient.

    Asked because the crossing reads like a shopping list and is not one, and
    the record contradicted itself over exactly that: it concluded from the same
    figures that the unfitted channel was presently not worth spending on, and
    then named the coefficient that channel would not recover as one an
    instrument would be bought for.

    It is not a fact about this model. Both figures a verdict is taken on -- the
    reach and the part no combination of the others reproduces -- are maxima
    over every channel the signature is laid out against, fitted or not. A
    coefficient that failed one of them failed it on all of them, so a channel
    given an instrument carries the same nothing the analysis already has for
    it, and the crossing can never be the case for fitting one. Where an
    instrument on a modelled channel would buy something, it is a coefficient
    shown identifiable by that channel alone, which each reading's own account
    of the unfitted channels reports.

    The reason is still taken per coefficient, because the three ways the second
    reading can lose one are three different things to tell a reader and only
    one of them is about a confounding.
    """
    reasons = []
    for entry in hidden:
        drifted = entry["drifted"]
        if drifted is None or not drifted["in_scope"]:
            why = ("the drifted reading found no reconstruction resting on it, so it has no "
                   "remainder to land on a channel at all")
        elif drifted["verdict"] == BELOW_WHAT_A_READING_CARRIES:
            why = ("nothing the drifted machine observes moves by an amount a reading could "
                   "carry, on any channel here")
        else:
            why = ("what the drifted machine shows is what it would show if a combination of the "
                   "others had drifted instead, and that holds on every channel here rather than "
                   "on the fitted ones only")
        reasons.append((entry, why))
    return reasons


# --- The record -------------------------------------------------------------

#: The heading each part of the record sits under, named here because the checks
#: that the committed record still says what this method produces read it back
#: by them.
MODEL_HEADING = "## The model this was run against"
READINGS_HEADING = "## The two readings"
FLOOR_HEADING = "## What each channel could resolve"
SCOPE_HEADING = "## Which coefficients the question is about"
SIGNATURE_HEADING = "## What each coefficient did to each channel"
DETERMINATION_HEADING = "## What this machine could tell apart"
DRIFT_DETERMINATION_HEADING = "## What a drifting machine would reveal"
HIDDEN_HEADING = "## What drift hides"

#: How each reading is put into a sentence that is about a machine rather than
#: about the harness that produced it. Two forms, because both are needed and
#: neither reads as the other: one names the machine a reading was taken over,
#: and one is the clause that qualifies a finding about it.
READING_CLAUSE = {
    BUILT_DIFFERENTLY: "a machine built throughout to coefficients that far from the description",
    DRIFTED: "a machine that has moved away from the description its controller still holds",
}
WHEN_THE_MACHINE_IS = {
    BUILT_DIFFERENTLY: "when it is built differently",
    DRIFTED: "when it has drifted",
}


def signature_heading(side, reading):
    """The sub-heading one reading's per-channel table for one side sits under.

    Both halves are in the name because the record carries one of these tables
    per side per reading, and two of them cover the same side. A reader -- and
    the check that the committed record is still the one this method produces --
    finds a table by its heading, and a heading naming only the side would find
    whichever of the two happened to be written first while reporting the other
    one's figures as missing.
    """
    return "### On the %s draw, %s" % (side, reading)


def _fitted_channels(source_path=None):
    """Which of the seam's sensor channels the board this project is building
    has an input behind.

    Read out of the seam's own implementation rather than written here, on the
    terms every other reading of that source in this tier is taken: a channel
    wired up later, or one whose input is taken away, moves what this record
    says about it without anything here being edited. The table names its
    entries in comments beside the channel each stands for, so what is read is
    which entries are the seam's own "nothing behind this" marker.
    """
    source_path = cross_tier.HW_SEAM_SOURCE if source_path is None else source_path
    source = seam_channels.strip_comments_and_strings(sweep.origins.read(source_path))
    opened = source.find(SENSOR_INPUT_TABLE)
    if opened < 0:
        raise IdentifiabilityError(
            "%s declares no %s, so which channels this board carries an input for cannot be read"
            % (source_path, SENSOR_INPUT_TABLE))
    opened = source.find("{", opened)
    closed = source.find("}", opened) if opened >= 0 else -1
    if opened < 0 or closed < 0:
        raise IdentifiabilityError(
            "%s declares %s with no initialiser to read the mapping out of"
            % (source_path, SENSOR_INPUT_TABLE))

    declared = seam_channels.sensor_channels()
    entries = [entry.strip() for entry in source[opened + 1:closed].split(",")]
    entries = [entry for entry in entries if entry]
    if len(entries) != len(declared):
        raise IdentifiabilityError(
            "%s maps %d sensor inputs and the seam enumerates %d channels, so which channel each "
            "entry stands for cannot be established"
            % (source_path, len(entries), len(declared)))
    return dict((declared[at], entries[at] != NO_SENSOR_INPUT)
                for at in range(len(declared)))


def _channel_is_fitted(source_path=None):
    """Which reported channel a converter input presently stands behind.

    The seam's channels and the names the two draws report their quantities
    under are two vocabularies, and the correspondence between them is the order
    both are declared in -- which is what the draws' own comments say and what a
    check in this tier's tests holds them to. The drawn rate is matched to the
    seam's flow channel by name rather than by position, since it is reported
    outside that ordered set.
    """
    fitted = _fitted_channels(source_path)
    declared = seam_channels.sensor_channels()
    by_channel = {}
    for at, key in enumerate(sweep.closed_loop.QUANTITY_KEYS):
        by_channel[key] = fitted[declared[at]]
    flow = [name for name in declared.values() if SEAM_FLOW_CHANNEL in name]
    if len(flow) != 1:
        raise IdentifiabilityError(
            "the hardware seam enumerates %d channels whose name says flow, so which one the "
            "drawn rate would be read on cannot be established" % len(flow))
    by_channel[cross_tier.FLOW_KEY] = fitted[flow[0]]
    return by_channel


def _relative(path):
    return os.path.relpath(os.path.abspath(path), REPOSITORY_DIR)


def _heading_name(heading):
    """What one of this record's sections is called, without the marks that make
    it a heading.

    Taken off the heading itself so that a sentence pointing a reader at another
    section goes on pointing at it after that section is renamed. A name written
    out a second time in the prose is a cross-reference that rots the first time
    the two are edited apart.
    """
    return heading.lstrip("#").strip()


def _listed(items):
    """Several things named in a sentence, joined the way a sentence joins them.

    Written out rather than left as comma-separated, because these lists are
    read as prose and a list of two joined by a comma reads as a sentence with a
    word missing. The record is generated whole precisely so nobody has to
    hand-edit it after a run, which means the generation has to produce prose
    and not a table wearing prose's punctuation.
    """
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


#: The heading one reading's own account of its verdicts sits under. Two
#: readings under one record cannot both be introduced by the same sentence, and
#: a reader arriving at the second half has to be told which machine it is about
#: without scrolling back.
VERDICTS_HEADING = {
    BUILT_DIFFERENTLY: "### What the verdicts say",
    DRIFTED: "### What the verdicts say once the machine has drifted",
}


def _write_floor_table(write, finding, fitted):
    """What a difference on each channel of each side had to clear, for one
    reading."""
    write("| Side | Channel | Fitted | Largest magnitude reached | One last place there | What a "
          "reading could carry | Floor used |")
    write("|---|---|---|---|---|---|---|")
    for side, key in finding["layout"]:
        floor = finding["floors"][side][key]
        unit = sweep.CHANNEL_UNIT[key]
        write("| %s | `%s` | %s | %s %s | %s %s | %s %s | %s %s |"
              % (side, key, "yes" if fitted[key] else "no",
                 FIGURE_FORMAT % floor["peak"], unit,
                 FIGURE_FORMAT % floor["arithmetic"], unit,
                 FIGURE_FORMAT % floor["reading"], unit,
                 FIGURE_FORMAT % floor["floor"], unit))
    write("")


def floors_that_differ(finding, drifted_finding):
    """Which channels the two readings did not arrive at the same floor for.

    Each reading takes its own peaks off its own runs, so each has its own
    arithmetic floor, and nothing obliges the two to agree. What is presently
    true -- that the machine's reading resolution is far coarser than either
    reading's arithmetic and therefore decides both -- is a fact about a board
    nobody has chosen instruments for, and it stops being true on a finer one.
    So the record establishes it from the two findings rather than stating it.
    """
    differing = []
    for side, key in finding["layout"]:
        theirs = drifted_finding["floors"].get(side, {}).get(key)
        if theirs is None or theirs["floor"] != finding["floors"][side][key]["floor"]:
            differing.append((side, key))
    return differing


def _write_determination_table(write, finding):
    """One reading's verdicts, with every figure each was reached from."""
    write("| Coefficient | Largest reach | On | Unique against the in-scope set | Unique against "
          "every coefficient | Unique as a fraction of itself | Others used | Verdict |")
    write("|---|---|---|---|---|---|---|---|")
    for record in finding["determination"]:
        if not record["in_scope"]:
            continue
        side, key = record["loudest"]
        write("| `%s` | %s | %s `%s` | %s | %s | %s | %s | %s |"
              % (record["coefficient"], FIGURE_FORMAT % record["largest"], side, key,
                 FIGURE_FORMAT % record["against_scoped"]["unique"],
                 FIGURE_FORMAT % record["against_every"]["unique"],
                 FIGURE_FORMAT % record["against_scoped"]["fraction"],
                 FIGURE_FORMAT % record["against_scoped"]["used"], record["verdict"]))
    write("")


def _write_verdict_prose(write, finding, reading, already_unshown=None):
    """One reading's account of what its own verdicts amount to.

    Written per reading rather than once over both, because the sentences are
    statements about a machine and the two readings are about two different
    machines. A single account would have to name which reading each figure came
    from in every clause, which is the same words with the reading spelled out
    twice and a reader left to keep track.

    What the other reading could not show either is handed in, and an account
    given it writes no paragraph for those coefficients. A verdict that did not
    change between the two readings is one finding and not two, and writing it
    out under each reading with that reading's own figures leaves a reader
    working out whether two paragraphs about the same coefficient are one
    finding or a disagreement. Those are stated once, where the two readings are
    compared, and the figures behind each reading's verdict are in that
    reading's own table either way.
    """
    already_unshown = set() if already_unshown is None else set(already_unshown)
    shown = [record for record in finding["determination"]
             if record["in_scope"] and record["verdict"] == IDENTIFIABLE]
    unshown = [record for record in finding["determination"]
               if record["in_scope"] and record["verdict"] != IDENTIFIABLE]
    told_here = [record for record in unshown
                 if record["coefficient"] not in already_unshown]
    write(VERDICTS_HEADING[reading])
    write("")
    write("Of the %d coefficients the reconstruction rests on, %d are shown identifiable from "
          "what this machine observes %s%s"
          % (len(finding["scoped"]), len(shown), WHEN_THE_MACHINE_IS[reading],
             ": %s." % _listed("`%s`" % record["coefficient"] for record in shown)
             if shown else "."))
    write("")
    narrow = [record for record in shown if record["against_scoped"]["unique"] < 2.0]
    if narrow:
        write("Of those, %s clear the floor by less than a factor of two — %s respectively. They "
              "are shown identifiable on the arithmetic and should not be read as comfortably so: "
              "each rests on a distinguishing signal of about one step of a converter nobody has "
              "chosen, and a per-channel scale or any reading noise would take them below it. "
              "They are the rows to re-run first against the measured model."
              % (_listed("`%s`" % record["coefficient"] for record in narrow),
                 _listed(FIGURE_FORMAT % record["against_scoped"]["unique"]
                         for record in narrow)))
        write("")
    if unshown and not told_here:
        write("The rest are **not shown identifiable**, and they are the same ones the other "
              "reading could not show either. They are stated once under **%s** below rather "
              "than a second time here, since a verdict that did not change between the two "
              "readings is one finding and not two. Each one's figures under this reading are in "
              "the table above." % _heading_name(HIDDEN_HEADING))
        write("")
    elif unshown:
        write("The rest are **not shown identifiable**, and each is named here rather than left "
              "out of the table or given the benefit of the doubt%s:"
              % ("" if len(told_here) == len(unshown) else
                 " — except %s, which the other reading could not show either and which are "
                 "stated once under **%s** below rather than twice"
                 % (_listed("`%s`" % record["coefficient"] for record in unshown
                            if record["coefficient"] in already_unshown),
                    _heading_name(HIDDEN_HEADING))))
        write("")
        for record in told_here:
            side, key = record["loudest"]
            if record["verdict"] == BELOW_WHAT_A_READING_CARRIES:
                write("- `%s` — its declared error's largest effect on any channel is %s of what "
                      "that channel could resolve, on the %s draw's `%s`. Nothing this machine "
                      "observes moves by an amount it could report, so no amount of running it "
                      "would ever say this coefficient is wrong, and drift correction cannot "
                      "reach it. A channel that carried it would have to be one nothing here "
                      "measures."
                      % (record["coefficient"], FIGURE_FORMAT % record["largest"], side, key))
            else:
                write("- `%s` — it does reach the channels, by up to %s of what the %s draw's "
                      "`%s` could resolve, but the part of its signature that no combination of "
                      "the other in-scope coefficients reproduces comes to %s of that resolution "
                      "— %s of the signature's own size. What the machine sees when this "
                      "coefficient is wrong is what it would see if a combination of the others "
                      "were wrong instead, so an observation cannot say which. That combination "
                      "totals %s of the others' own declared errors%s."
                      % (record["coefficient"], FIGURE_FORMAT % record["largest"], side, key,
                         FIGURE_FORMAT % record["against_scoped"]["unique"],
                         FIGURE_FORMAT % record["against_scoped"]["fraction"],
                         FIGURE_FORMAT % record["against_scoped"]["used"],
                         ", so it is a machine the description already admits to being possible"
                         if record["against_scoped"]["used"] <= 1.0 else
                         ", which is more than the description admits those coefficients may be "
                         "out by — so the confounding is arithmetic that the description's own "
                         "error budget already rules out, and this verdict is conservative"))
        write("")
    else:
        write("Nothing the reconstruction rests on was left unshown. Every in-scope coefficient "
              "reaches a channel by more than that channel could resolve, and carries a part no "
              "combination of the others reproduces.")
        write("")


def _write_unfitted_account(write, finding, fitted, unfitted, reading):
    """What an unfitted channel is presently buying under one reading.

    This is the question the analysis exists to inform, and it has to be
    answered in the record whichever way it comes out. A record that spoke up
    only where an instrument would help would leave a reader unable to tell "no
    instrument is needed" from "nobody asked", and those are opposite findings.

    It is answered under each reading rather than under the first alone, because
    the first is the optimistic one: an instrument the commissioning question
    says nothing would be bought by is exactly the instrument a drifting machine
    might need, and a case made from one reading only would be the case the
    solution behind this record warns against making.
    """
    depends_on_unfitted = []
    carried_by_unfitted = []
    for record in finding["determination"]:
        if not record["in_scope"]:
            continue
        by_channel = record["against_scoped"]["unique_by_channel"]
        on_fitted = max((value for (_, key), value in by_channel.items() if fitted[key]),
                        default=0.0)
        on_unfitted = max((value for (_, key), value in by_channel.items() if not fitted[key]),
                          default=0.0)
        if on_unfitted > 1.0:
            carried_by_unfitted.append((record, on_unfitted))
            if on_fitted <= 1.0:
                depends_on_unfitted.append(record)
    if depends_on_unfitted:
        write("%s, these are shown identifiable only by a channel nothing is presently fitted "
              "to: %s. On the instruments this board actually carries, the part of each one's "
              "signature that nothing else reproduces sits below what a reading could resolve. "
              "That is the strongest case this reading can make for adding an observation "
              "channel, and it is left as a case rather than a decision."
              % (WHEN_THE_MACHINE_IS[reading].capitalize(),
                 ", ".join("`%s`" % record["coefficient"] for record in depends_on_unfitted)))
        write("")
    elif carried_by_unfitted:
        write("No verdict above turns on a channel this board has no instrument behind. %s does "
              "carry a part of a signature nothing else reproduces — %s — but every coefficient "
              "it separates is already separated by a channel that is fitted, so on this model, "
              "%s, adding that instrument would confirm a finding rather than produce one. That "
              "is a negative answer to the question this analysis exists to inform, and it is "
              "worth as much as a positive one: it is the case for *not* spending on that channel "
              "yet, and it is a statement about this estimated model that a measured one could "
              "overturn."
              % (_listed("`%s`" % key for key in unfitted) or "The unfitted channel",
                 _listed("%s of what it could resolve for `%s`"
                         % (FIGURE_FORMAT % value, record["coefficient"])
                         for record, value in carried_by_unfitted),
                 WHEN_THE_MACHINE_IS[reading]))
        write("")
        write("A figure there for a coefficient the tables above show moving that channel by "
              "nothing at all is not a contradiction, and it is the one number here most easily "
              "misread. What is being reported is the remainder, not the reach: the combination "
              "of the other coefficients that comes nearest to reproducing this one's signature "
              "does move that channel, so the disagreement between the coefficient and its "
              "nearest imitation shows up there even though the coefficient itself never touched "
              "it. A channel a coefficient leaves alone can separate it from something that does "
              "not.")
        write("")
    elif unfitted:
        write("No coefficient's distinguishing signature reaches %s at all %s, so on these two "
              "draws an instrument on that channel would separate nothing the fitted channels do "
              "not already separate."
              % (", ".join("`%s`" % key for key in unfitted), WHEN_THE_MACHINE_IS[reading]))
        write("")


#: How the record opens its statement about the two readings' directions, and
#: how the three ways their verdicts can agree are each introduced. Named here
#: because each has to be found back in a written record -- once, and only once
#: -- by anything checking that the record still states what the analysis
#: computes.
NEITHER_READING_BOUNDS = "Neither reading bounds the other"
BOTH_READINGS_SHOW = "**Both readings show these identifiable:**"
NEITHER_READING_SHOWS = "**Neither reading shows these identifiable:**"
ONLY_DRIFTED_SHOWS = "**Shown identifiable only once drifted:**"

#: How the record says what an instrument would do about the coefficients drift
#: hides. Findable in a written record on its own, because a reader and a check
#: both have to be able to tell "no instrument on these channels recovers it"
#: from "nobody asked" -- and because the record says the opposite of it, about
#: the same channel, sixteen lines earlier if this is ever dropped.
NO_INSTRUMENT_RECOVERS = "no instrument on a channel this record models would recover"


def _moved_clause(groups):
    """Which way one figure moved between the two readings, as a clause naming
    the coefficients under each direction."""
    said = []
    for how, group in (("falls for", groups[0]), ("rises for", groups[1]),
                       ("stands where it was for", groups[2])):
        if group:
            said.append("%s %d (%s)"
                        % (how, len(group), _listed("`%s`" % name for name, _, _ in group)))
    return _listed(said)


def _write_reading_comparison(write, finding, drifted_finding):
    """Which way the two readings' figures actually moved, stated from the two
    determinations.

    Here rather than left implicit, because the obvious thing to say about a
    loop that no longer knows its machine -- that it lets less of a
    coefficient's error reach the channels -- is a claim about a direction, and
    the two tables it sits between can falsify it. Saying it anyway would put a
    reader through the tables looking for a pattern the figures do not carry,
    and would make the first reading look like a safe upper bound on the second
    when it is not one.
    """
    moved = moved_between_readings(finding, drifted_finding)
    counted = len(moved[THE_VERDICT_FIGURE][0]) + len(moved[THE_VERDICT_FIGURE][1]) \
        + len(moved[THE_VERDICT_FIGURE][2])
    if not counted:
        return
    write("%s, and the two determinations establish that rather than it being assumed. Of the %d "
          "coefficients both readings put a verdict to, %s %s. And %s %s."
          % (NEITHER_READING_BOUNDS, counted,
             THE_VERDICT_FIGURE, _moved_clause(moved[THE_VERDICT_FIGURE]),
             THE_REACH_FIGURE, _moved_clause(moved[THE_REACH_FIGURE])))
    write("")
    write("Holding the control path still withdraws a correction, and a correction withdrawn can "
          "leave a coefficient's own error standing on the channels as readily as it can absorb "
          "it. Which of the two happens is a fact about the coefficient and is read off the "
          "tables rather than argued for here. So the first reading is not an upper bound on the "
          "second, neither of them is the conservative one to read alone, and the crossings "
          "between the two sets of verdicts are named one at a time under **%s** below rather "
          "than inferred from a direction." % _heading_name(HIDDEN_HEADING))
    write("")


def _write_instrument_account(write, hidden):
    """What an instrument would do about the coefficients drift hides, which is
    nothing, and why that is structural rather than this model's answer.

    Said here because the crossing reads like a shopping list, and because the
    same record already reports -- out of the same figures and a few lines
    earlier -- that the channel nothing is fitted to presently separates nothing
    the fitted channels do not. A section closing on "these are the coefficients
    an instrument would be bought for" contradicts that, and of the two it is
    the shopping list that the figures do not support.
    """
    write("These are the rows the first reading on its own would have said nothing about. They "
          "are not, on that account, rows an instrument would be bought for: %s any of them, and "
          "that follows from what the verdict is rather than from this model. Both figures a "
          "verdict is taken on are the largest over every channel the signature is laid out "
          "against, fitted or not — so a coefficient that failed one of them failed it on all of "
          "them, and a channel given an instrument would carry the same nothing this analysis "
          "already has for it." % NO_INSTRUMENT_RECOVERS)
    write("")
    grouped = {}
    for entry, why in why_no_instrument_recovers(hidden):
        grouped.setdefault(why, []).append(entry["coefficient"])
    for why in sorted(grouped):
        write("%s — %s." % (_listed("`%s`" % name for name in grouped[why]), why))
        write("")
    write("Recovering what drift hides would need an observation this analysis does not model, "
          "and naming one is the physical track's decision taken against this record rather than "
          "inside it. Where an instrument on a channel this record does model would buy "
          "something, it is a coefficient that channel alone shows identifiable, and each "
          "reading's own account of the unfitted channels above is where that is reported.")
    write("")


def _write_agreement(write, finding, drifted_finding):
    """The three ways the two readings can come out other than the crossing,
    each stated once.

    Under the crossing rather than under either reading, because each is a
    statement about the pair and not about a machine. Written out rather than
    left as two lists of verdicts for a reader to intersect: the whole reason
    both readings are in one record is that the finding is in the comparison,
    and a comparison a reader has to perform by eye is one that will be
    performed wrong or not at all.
    """
    both, neither, only_drifted = readings_agree_on(finding, drifted_finding)
    rose = len(moved_between_readings(finding, drifted_finding)[THE_VERDICT_FIGURE][1])
    scoped = len(finding["scoped"])
    write("The other three ways the two readings can come out are stated here once rather than "
          "under each of them, since a verdict both readings reach is one finding and not two.")
    write("")
    write("%s %s. A machine built to a different figure for any of them could be told apart at "
          "commissioning, and a machine that has drifted in it could be told apart in service, so "
          "a drift check has these to work with."
          % (BOTH_READINGS_SHOW,
             "%s — %d of the %d the reconstruction rests on"
             % (_listed("`%s`" % name for name in both), len(both), scoped)
             if both else "none — no coefficient the reconstruction rests on is shown "
             "identifiable "
             "under both readings"))
    write("")
    write("%s %s. Drift hides nothing about them that a machine built differently did not hide "
          "already, so they are not what the second reading was taken to find; each one's figures "
          "under each reading are in the two determination tables above, and the account of why "
          "it was not shown is given once, under the reading that could not show it first."
          % (NEITHER_READING_SHOWS,
             "%s — %d of the %d" % (_listed("`%s`" % name for name in neither),
                                    len(neither), scoped)
             if neither else "none — every coefficient the reconstruction rests on is shown "
             "identifiable by at least one of the two readings"))
    write("")
    write("%s %s"
          % (ONLY_DRIFTED_SHOWS,
             "%s — %d of the %d. A machine that has drifted reveals these where one built to a "
             "different figure for them does not, which is the crossing above taken the other way "
             "round and worth as much: it says the commissioning reading is not the one to design "
             "a drift check from."
             % (_listed("`%s`" % name for name in only_drifted), len(only_drifted), scoped)
             if only_drifted else
             "none on this model. Nothing the machine could not be told apart on at commissioning "
             "becomes something it could be told apart on in service. That is a finding about "
             "this "
             "model rather than a rule the method enforces — the figure a verdict is taken on "
             "does "
             "rise under drift for %d of the coefficients here, just never far enough to carry a "
             "verdict across." % rose))
    write("")


def report_text(findings, finding, drifted_findings, drifted_finding):
    """The whole record: what was compared, against what resolution, and what
    came back under each of the two readings.

    Written by the analysis rather than by hand and written whole rather than as
    tables pasted into prose somebody maintains separately, for the reason the
    dominance record beside it is: pointing the method at a replacement model has
    to need nothing changed about how it runs, and a record whose prose is
    re-edited by hand every time the model moves is one that will be left
    describing the previous machine.

    Both readings are written into one record rather than into two, and that is
    the point of taking the second at all. They answer different questions off
    the same four files, and a reader who has one record has been given one
    answer while the other question goes on looking answered. The case the
    second reading exists to produce -- a coefficient the first shows
    identifiable and the second does not -- cannot be stated by either record
    alone.
    """
    fitted = _channel_is_fitted()
    hidden = hidden_by_drift(finding, drifted_finding)
    lines = []
    write = lines.append

    write("# Which of this machine's coefficients it could tell apart")
    write("")
    write("**Generated by `firmware/emulation/tools/run_parameter_identifiability.py`. Do not "
          "edit by hand — re-run it.**")
    write("")
    write("Every coefficient the machine's description says it may be wrong about is perturbed to "
          "both ends of its own declared error and both closed loops are re-run against each "
          "perturbed machine — the same re-runs `docs/parameter-dominance.md` is taken from, read "
          "at a different place. That record asks how far the *delivery* moved. This one asks how "
          "far the *channels the machine can observe* moved, and whether what one coefficient did "
          "to them could have been done by a combination of the others instead.")
    write("")
    write("It asks that twice. Once of a machine built throughout to different coefficients, "
          "which is what a commissioning check would be up against, and once of a machine that "
          "has drifted away from the description its own controller still holds, which is what "
          "fouling and ageing leave behind. Both readings are below and neither replaces the "
          "other. The case worth looking for is a coefficient the first shows identifiable and "
          "the second does not: a machine that passes every check at build and then goes wrong "
          "with nothing to report it.")
    write("")
    write("A coefficient's signature here is half the difference between the run at the top of "
          "its declared error and the run at the bottom, channel by channel and interval by "
          "interval. Half the difference of the two corners rather than one corner against the "
          "middle, because that is the part of the response linear in the coefficient — and the "
          "linear part is the only part another coefficient's uncertainty could stand in for. A "
          "comparison that kept the curvature as well would separate two coefficients on how "
          "differently their relations bend at their own corners, which is a difference no "
          "observation of a machine sitting anywhere else could exploit.")
    write("")
    write("A coefficient is called identifiable only when both of two things hold: its signature "
          "reaches at least one channel by more than that channel could resolve, and the part of "
          "its signature that no combination of the other in-scope coefficients reproduces "
          "survives the same resolution. Anything failing either is named as **not shown "
          "identifiable** rather than left out or assumed identifiable — an unproven "
          "identifiability and a disproven one read alike from a table, and only one of them is "
          "safe to design against.")
    write("")
    write("This is not a fit and it is not a purchase order. Nothing here recovers a coefficient "
          "from data: what is asked is whether the channels carry a signature that could "
          "distinguish it, which is what has to be settled before an instrument is bought and the "
          "only part of the question that can be settled before the machine is measured. Where "
          "the answer turns on a channel nothing is presently fitted to, that is a finding about "
          "what an instrument would buy — what to fit, at what cost, on what part of the path is "
          "not decided here.")
    write("")

    write(MODEL_HEADING)
    write("")
    write("| What | File | sha256 |")
    write("|---|---|---|")
    for what, path in (("The machine's coefficients", findings["description"]),
                       ("What a reading off it may be", findings["limits"]),
                       ("The steam side's design figures", findings["declaration"]),
                       ("The bands a delivery is held to", findings["tolerance"])):
        write("| %s | `%s` | `%s` |" % (what, _relative(path), findings["digests"][path]))
    write("")
    write("Both readings are taken against these four files and no others, which is what makes "
          "them comparable: a difference between the two answers is then the difference between "
          "the two questions and not between two machines.")
    write("")
    write("A replacement model is analysed by naming it: `--description`, `--limits`, "
          "`--steam-declaration` and `--tolerance` each point the same method at another file, "
          "and `--workspace` gives that run its own scratch directory. Nothing about how the "
          "signatures are taken or how the verdict is reached changes with them, which is what "
          "makes this repeatable against the measured model that is meant to replace this "
          "estimated one rather than something to be argued about against this one.")
    write("")

    write(READINGS_HEADING)
    write("")
    write("The two sweeps differ in one thing and nothing else.")
    write("")
    write("**%s.** Each corner hands the perturbed description to the machine and to the coffee "
          "side's control path alike, so the machine is different and its own loop already knows "
          "it. What is compared is two machines each built consistently to its own coefficients, "
          "and what it answers is whether the channels could tell them apart."
          % BUILT_DIFFERENTLY.capitalize())
    write("")
    write("**%s.** The perturbed description goes to the machine alone. The control path is built "
          "from `%s` for every run, whatever the machine was perturbed to, so the loop is driving "
          "a reconstruction that is wrong about the machine rather than a different machine it is "
          "right about. It holds its own estimate at the target instead of the delivery, and what "
          "the channels carry is what a machine nothing is correcting for shows rather than "
          "what a "
          "machine built to those figures shows."
          % (DRIFTED.capitalize(), _relative(drifted_findings["control_description"])))
    write("")
    moved = sides_the_readings_differ_on(findings, drifted_findings)
    stood_still = [side for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE) if side not in moved]
    if moved and stood_still:
        write("Holding the control path still changed what the %s draw recorded and left the %s "
              "draw's figures exactly where they were. That is not a partial run: the steam law "
              "is built from its own declaration and from no description of a casting at all, so "
              "there is nothing on that side for a perturbation to be kept out of, and the two "
              "readings can only come apart where a control path holds a model. The record "
              "establishes this from the runs rather than assuming it, so a steam-side law that "
              "did start reconstructing something would move this sentence rather than be missed "
              "by it."
              % (_listed(moved), _listed(stood_still)))
    elif moved:
        write("Holding the control path still changed what both draws recorded, so both sides "
              "carry a control path driving from a model of the machine.")
    else:
        write("Holding the control path still changed nothing either draw recorded. Either "
              "nothing in this build drives from a reconstruction of the machine, or the two "
              "descriptions reaching the loop were the same one — and in both cases the second "
              "reading below is the first one again and establishes nothing about drift.")
    write("")

    write(FLOOR_HEADING)
    write("")
    write("A difference on a channel has to clear the wider of two floors to be a difference at "
          "all. Neither is a figure chosen here.")
    write("")
    write("The first is what a reading off this machine could carry: the hardware seam's "
          "implementation declares a converter full scale and a count at that scale, and every "
          "reading the control path acts on is that division — so a difference below one count is "
          "one the machine reports as no difference. On the seam as it presently stands that is "
          "**%s** in each channel's own unit, the same on every channel because the seam declares "
          "one full scale for all of them." % (FIGURE_FORMAT % finding["reading"]))
    write("")
    write("That single full scale is a fact about a board nobody has yet chosen instruments for, "
          "and it is not a per-channel instrument declaration. It is generous where a channel's "
          "own range is small: it is a two-hundred-unit scale standing against a steam pressure "
          "that reaches a bar and a half and a drawn rate that reaches three millilitres a "
          "second. Every verdict below is taken against it, so a verdict resting on a figure only "
          "just above 1 is one that a per-channel scale — or a converter with any noise on it — "
          "would move. Read those rows as the analysis declining to claim much rather than as a "
          "finding.")
    write("")
    write("The second is what the model's own arithmetic could express. Every quantity it carries "
          "is IEEE-754 binary32, so two runs' figures for a channel cannot sit closer than one "
          "unit in the last place at the magnitude that channel reached — and the magnitude taken "
          "is the largest reached anywhere in the sweep, perturbed runs included, because a run "
          "that carried a channel higher carried the last place up with it.")
    write("")
    _write_floor_table(write, finding, fitted)
    apart = floors_that_differ(finding, drifted_finding)
    if apart:
        write("The drifted reading takes its own peaks off its own runs, and on %s it arrives at "
              "a different floor. Its verdicts are taken against these:"
              % _listed("the %s draw's `%s`" % (side, key) for side, key in apart))
        write("")
        _write_floor_table(write, drifted_finding, fitted)
    else:
        write("The drifted reading takes its own peaks off its own runs and arrives at the same "
              "floor on every channel, so both determinations below are taken against the figures "
              "in this table. That holds because the machine's own reading resolution is the "
              "coarser of the two floors everywhere, and it is established here from the two "
              "readings rather than assumed of a board with a finer converter.")
        write("")
    unfitted = sorted(set(key for _, key in finding["layout"] if not fitted[key]))
    if unfitted:
        write("The channels marked unfitted are enumerated by the hardware seam and have no "
              "converter input behind them on the board being built: %s. They are analysed all "
              "the same, and that is the point of analysing them — a channel nothing sits on is "
              "exactly where the question of whether an instrument would buy anything gets "
              "decided, and it cannot be decided about a channel nobody recorded."
              % ", ".join("`%s`" % key for key in unfitted))
        write("")

    write(SCOPE_HEADING)
    write("")
    write("The coefficients the control path's reconstructed state rests on. The estimator seam "
          "reconstructs one state — the temperature of the water on its way to the group, which "
          "no channel observes — and the coffee-side draw reports the plant's own value of that "
          "same temperature at every interval, so a coefficient is in scope exactly when "
          "perturbing it moved that figure. Read off the runs rather than listed, because a list "
          "would be a second opinion about what the reconstruction rests on and would go on "
          "looking right after the model changed.")
    write("")
    write("The figure read is the true state and not the reconstruction of it, which is a "
          "different number: the estimator holds a plant model of its own and corrects it against "
          "the sensors. The true value stands in because the reconstruction is those same "
          "relations over those same coefficients, so a coefficient the true outlet temperature "
          "does not depend on is one no reconstruction of it can depend on either. What the "
          "substitution could miss is a coefficient whose effect on the true outlet the closed "
          "loop cancels while the reconstruction still rests on it.")
    write("")
    write("A coefficient out of scope is still laid out against every channel in the tables "
          "below, and still counts in the wider comparison, because a coefficient no "
          "reconstruction rests on still moves channels and so still confounds a fit against "
          "them. It is given no verdict of its own. Two of them are the coefficients the "
          "dominance ranking could not weigh — they reach a modelled quantity the design declares "
          "no band for — and they are here for exactly that reason: excluded, they would leave "
          "this record claiming a separability the machine does not have.")
    write("")
    write("| Coefficient | In scope | Why |")
    write("|---|---|---|")
    for record in finding["determination"]:
        write("| `%s` | %s | %s |"
              % (record["coefficient"], "yes" if record["in_scope"] else "no",
                 "its declared error moves the temperature the control path reconstructs"
                 if record["in_scope"] else
                 "neither end of its declared error moved the temperature the control path "
                 "reconstructs, so no reconstruction rests on it and nothing here is asked of it"))
    write("")
    only_when_built = sorted(set(finding["scoped"]) - set(drifted_finding["scoped"]))
    only_when_drifted = sorted(set(drifted_finding["scoped"]) - set(finding["scoped"]))
    if only_when_built or only_when_drifted:
        write("The two readings do not agree about this set. %s Whether the reconstruction rests "
              "on a coefficient is asked of each reading's own runs, so a coefficient reaching "
              "the delivered temperature on a machine its controller knows and not on one that "
              "has drifted is a finding in itself and not a fault in the scoping."
              % " ".join(filter(None, [
                  "In scope only when the machine is built differently: %s."
                  % _listed("`%s`" % name for name in only_when_built)
                  if only_when_built else "",
                  "In scope only when it has drifted: %s."
                  % _listed("`%s`" % name for name in only_when_drifted)
                  if only_when_drifted else ""])))
        write("")
    else:
        write("Both readings arrive at this same set from their own runs.")
        write("")

    write(SIGNATURE_HEADING)
    write("")
    write("The largest the coefficient's own declared error moved each channel, in that "
          "channel's unit, over each draw, under each reading. This is the record the verdicts "
          "below were drawn from: a verdict is taken over the whole interval-by-interval "
          "signature and not off these peaks, but a coefficient's peaks are what say at a glance "
          "which channels it reaches at all. A figure of nothing is a channel this coefficient "
          "left exactly where it was, which is as much a part of a signature as a channel it "
          "moved.")
    write("")
    for reading, of in ((BUILT_DIFFERENTLY, finding), (DRIFTED, drifted_finding)):
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            keys = [key for at_side, key in of["layout"] if at_side == side]
            if not keys:
                continue
            write(signature_heading(side, reading))
            write("")
            write("| Coefficient | %s |" % " | ".join("`%s` (%s)" % (key, sweep.CHANNEL_UNIT[key])
                                                      for key in keys))
            write("|---|%s" % ("---|" * len(keys)))
            for record in of["determination"]:
                cells = []
                for key in keys:
                    floor = of["floors"][side][key]["floor"]
                    cells.append(FIGURE_FORMAT % (record["reached"][(side, key)] * floor))
                write("| `%s` | %s |" % (record["coefficient"], " | ".join(cells)))
            write("")

    write(DETERMINATION_HEADING)
    write("")
    write("Every in-scope coefficient on %s, with what its signature reached and how much of it "
          "nothing else accounts for. Both figures are in multiples of the floor that channel had "
          "to clear, so a figure of 1 sits exactly at what could be resolved and a figure below 1 "
          "is a difference this machine reports as none." % READING_CLAUSE[BUILT_DIFFERENTLY])
    write("")
    write("A figure only just above 1 is a coefficient shown identifiable by a hair: the part of "
          "its signature nothing else reproduces is barely more than the smallest step the "
          "machine's own reading could carry, and a real converter with any noise on it would not "
          "carry it. Read the figure and not only the verdict — the verdict is a threshold and "
          "the figure is how far the coefficient stands from it.")
    write("")
    write("The two unique-part columns answer different questions and both are worth reading. The "
          "first is against the other coefficients the reconstruction rests on, which is what the "
          "verdict is taken on. The second is against every coefficient the sweep perturbed, "
          "including the ones out of scope — because a coefficient out of scope for this question "
          "still moves the same channels, and a fit against real readings would be up against all "
          "of them at once. A coefficient whose two figures differ is one whose separability "
          "depends on an out-of-scope coefficient being known independently.")
    write("")
    write("The two figures after those are the same remainder taken as a fraction of the "
          "signature's own size, and how much of the others the combination that came nearest had "
          "to use. Neither is what the verdict is taken on and both are worth reading beside it. "
          "A coefficient whose remainder is a thousandth of its own signature is one the others "
          "very nearly reproduce, whatever resolution the leftover happens to clear. And every "
          "signature here is scaled to one declared error of its own coefficient, so a "
          "combination totalling less than 1 is one that sits inside the others' own declared "
          "errors — a statement about this machine — where a total in the hundreds would be the "
          "arithmetic finding a combination nobody has reason to think the machine is in.")
    write("")
    _write_determination_table(write, finding)
    _write_verdict_prose(write, finding, BUILT_DIFFERENTLY)
    _write_unfitted_account(write, finding, fitted, unfitted, BUILT_DIFFERENTLY)

    write(DRIFT_DETERMINATION_HEADING)
    write("")
    write("The same determination taken again over %s. Every column means what it means above; "
          "what has changed is which machine the signatures came off. The control path was built "
          "from the unperturbed description throughout, so its reconstruction is biased rather "
          "than merely different, and what each coefficient's own error leaves on the channels is "
          "what it leaves on a machine nothing is correcting for it."
          % READING_CLAUSE[DRIFTED])
    write("")
    write("This is the reading a machine in service is under, and it is the one to design a drift "
          "check against.")
    write("")
    _write_determination_table(write, drifted_finding)
    _write_reading_comparison(write, finding, drifted_finding)
    _write_verdict_prose(write, drifted_finding, DRIFTED,
                         already_unshown=readings_agree_on(finding, drifted_finding)[1])
    _write_unfitted_account(write, drifted_finding, fitted, unfitted, DRIFTED)

    write(HIDDEN_HEADING)
    write("")
    write("A coefficient shown identifiable when the machine is built differently and **not** "
          "shown identifiable once it has drifted. This is the case the second reading exists to "
          "find, and it is the one that cannot be seen from either reading alone: such a "
          "coefficient passes every check that can be made at build, and then moves with nothing "
          "the machine observes able to say that it has.")
    write("")
    if hidden:
        write("%d of the %d coefficients the first reading shows identifiable %s named **%s**:"
              % (len(hidden),
                 len([record for record in finding["determination"]
                      if record["in_scope"] and record["verdict"] == IDENTIFIABLE]),
                 "is" if len(hidden) == 1 else "are", HIDDEN_BY_DRIFT))
        write("")
        write("| Coefficient | Unique when built differently | Unique when drifted | Largest "
              "reach when drifted | Verdict when drifted |")
        write("|---|---|---|---|---|")
        for entry in hidden:
            drifted = entry["drifted"]
            write("| `%s` | %s | %s | %s | %s |"
                  % (entry["coefficient"],
                     FIGURE_FORMAT % entry["built_differently"]["against_scoped"]["unique"],
                     (FIGURE_FORMAT % drifted["against_scoped"]["unique"]
                      if drifted is not None and drifted["in_scope"] else "—"),
                     FIGURE_FORMAT % drifted["largest"] if drifted is not None else "—",
                     entry["verdict_when_drifted"]))
        write("")
        for entry in hidden:
            drifted = entry["drifted"]
            if drifted is None or not drifted["in_scope"]:
                write("- `%s` — the drifted reading found no reconstruction resting on it at all, "
                      "so it leaves that reading with no verdict of its own. Whatever a machine "
                      "built to a different figure for it would show, a machine that has drifted "
                      "to one shows nothing."
                      % entry["coefficient"])
            elif drifted["verdict"] == BELOW_WHAT_A_READING_CARRIES:
                side, key = drifted["loudest"]
                write("- `%s` — built differently it stands %s clear of what a reading could "
                      "carry. Drifted, its largest effect on any channel is %s of what that "
                      "channel could resolve, on the %s draw's `%s`: the loop absorbs it. A "
                      "machine commissioned against this coefficient and then left to drift in it "
                      "reports nothing, and no instrument already fitted would say otherwise."
                      % (entry["coefficient"],
                         FIGURE_FORMAT % entry["built_differently"]["against_scoped"]["unique"],
                         FIGURE_FORMAT % drifted["largest"], side, key))
            else:
                write("- `%s` — built differently the part of its signature nothing else "
                      "reproduces stands at %s of what a reading could carry. Drifted, it falls "
                      "to %s, which is below it: the machine still moves, but what it shows is "
                      "what it would show if a combination of the others had drifted instead, so "
                      "an observation cannot say which drifted."
                      % (entry["coefficient"],
                         FIGURE_FORMAT % entry["built_differently"]["against_scoped"]["unique"],
                         FIGURE_FORMAT % drifted["against_scoped"]["unique"]))
        write("")
        _write_instrument_account(write, hidden)
    else:
        write("**No coefficient is in this position on this model.** Every coefficient the first "
              "reading shows identifiable the second reading shows identifiable too. That is a "
              "finding and not an absence of one: it says the loop's own correction does not "
              "absorb any coefficient's declared error far enough to take it below what a reading "
              "could carry, so a drift check on this machine is up against the same set the "
              "commissioning question is. It is a statement about this estimated model, and a "
              "measured one could overturn it.")
        write("")
    _write_agreement(write, finding, drifted_finding)

    write("## What this does not settle")
    write("")
    write("**Drift here is one coefficient moved to the end of its own declared error, all at "
          "once.** A machine that fouls or ages moves gradually and moves several coefficients "
          "together, and neither is what the second reading above puts to it: it takes exactly "
          "the perturbation the first reading takes and withholds it from the control path. What "
          "that establishes is how far one coefficient's own error reaches the channels when the "
          "loop is not told about it, one coefficient at a time. It does not establish what a "
          "real drift trajectory would show, "
          "and a drift check designed against it would still have to be run against a machine "
          "actually drifting.")
    write("")
    write("**The floor is one board's single full scale, and the test is on the widest single "
          "disagreement.** The seam declares one converter scale for every channel, which is "
          "generous where a channel's own range is small, and no instrument has been chosen to "
          "replace it with a per-channel figure. A sustained disagreement sitting just under one "
          "count for a whole draw is separable in practice by averaging and is called "
          "unresolvable here. Both err toward naming a coefficient not shown identifiable, which "
          "is the direction that cannot mislead somebody into leaving an instrument out.")
    write("")
    write("It is not a fit. A coefficient named identifiable here carries a signature the "
          "channels could distinguish; whether a real fit against real readings over a real draw "
          "recovers it is a different question, and it waits on the machine. Structural reach is "
          "what is asked and structural reach is what is answered.")
    write("")
    write("It is two scenarios, not every scenario. A coefficient can be unreachable on the "
          "courses run here — a flush and a shot on the coffee side, a settle and a wand-open on "
          "the steam side — and reachable on a draw nobody has run. What the verdicts state is "
          "what these two draws establish, and a coefficient not shown identifiable is one this "
          "has not shown rather than one shown to be unreachable for ever.")
    write("")
    write("It is an estimated model. Every figure in the description is an estimate and so is the "
          "error declared against it, so the signatures are estimates of estimates. The record "
          "names the files and their digests so it can be re-run against the measured model that "
          "is meant to replace them, which is when the answer becomes a statement about a "
          "machine.")
    write("")
    write("And it names no instrument. Where the finding turns on a channel nothing is fitted to, "
          "what to fit and at what cost is the physical track's decision, taken against this "
          "analysis rather than inside it.")
    write("")

    return "\n".join(lines) + "\n"


def _table_rows(text, heading):
    """The `| `name` | ... |` rows under one heading, as lists of cells.

    Read back through one reader rather than by whatever pattern each caller
    invents, for the reason the dominance record's own read-back exists: the
    check that a committed record is still the one this method produces is only
    worth something if the reading and the writing agree about which table is
    which and where in it a figure sits.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if line.startswith(heading):
            inside = True
            continue
        # Any heading ends the table, at whatever depth. Stopping only at the
        # top level would run one side's per-channel table straight into the
        # next side's, and the two carry the same coefficients under the same
        # names -- so the reader would silently return the second side's figures
        # for the first side's rows.
        if inside and line.startswith("#"):
            break
        if not inside or not line.startswith("| `"):
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def determination_rows(text, heading=DETERMINATION_HEADING):
    """One reading's determination read back out of a written record: per
    coefficient, the verdict and every figure it was reached from.

    The figures and not only the verdict, because the figures are half of what
    the record exists to carry -- a verdict with no figure behind it cannot be
    argued with, and a check that compared only verdicts would let every number
    in the table drift while staying green until one of them crossed a
    threshold. That is the failure that has already happened once to the
    dominance record beside this one.

    Which reading is asked for by heading, because the record carries two
    determinations of the same coefficients under the same column names and a
    reader that took whichever came first would check one of them twice.
    """
    rows = []
    for cells in _table_rows(text, heading):
        if len(cells) != 8:
            continue
        rows.append({
            "coefficient": cells[0].strip("`"),
            "largest": float(cells[1]),
            "loudest": cells[2],
            "unique_scoped": float(cells[3]),
            "unique_every": float(cells[4]),
            "fraction": float(cells[5]),
            "used": float(cells[6]),
            "verdict": cells[7],
        })
    return rows


def hidden_rows(text):
    """The coefficients a written record names as identifiable when the machine
    is built differently and not once it has drifted, as (coefficient, verdict
    when drifted).

    Read back for the reason the determination is: the crossing is what the
    second reading exists to produce, and a record that had stopped naming one
    would read exactly like a machine that had none. An empty list is the
    record's own positive statement that nothing crosses, which is why the
    section is written either way.
    """
    return [(cells[0].strip("`"), cells[4])
            for cells in _table_rows(text, HIDDEN_HEADING) if len(cells) == 5]


def signature_rows(text, side, reading=BUILT_DIFFERENTLY):
    """One reading's per-channel figures for one side, read back out of a
    written record, as {coefficient: [figure per channel]}, in the order the
    channels are laid out.
    """
    rows = {}
    for cells in _table_rows(text, signature_heading(side, reading)):
        if len(cells) != len(sweep.OBSERVED_CHANNELS) + 1:
            continue
        rows[cells[0].strip("`")] = [float(cell) for cell in cells[1:]]
    return rows


def scope_rows(text):
    """Which coefficients the record says the question is about, as
    (coefficient, in scope)."""
    return [(cells[0].strip("`"), cells[1] == "yes")
            for cells in _table_rows(text, SCOPE_HEADING) if len(cells) == 3]


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--description",
                        help="the parameter description to analyse, defaulting to the one the "
                             "target build carries compiled in")
    parser.add_argument("--limits",
                        help="what a reading off that machine may be, defaulting to the one the "
                             "target build carries compiled in")
    parser.add_argument("--steam-declaration", default=sweep.STEAM_CONTROL_DECLARATION,
                        help="the figures the steam control law is given")
    parser.add_argument("--tolerance", default=sweep.TOLERANCE_DECLARATION,
                        help="the bands a delivery is held to")
    parser.add_argument("--report", default=REPORT_PATH,
                        help="where the record of the finding is written")
    parser.add_argument("--stdout", action="store_true",
                        help="print the record rather than writing it")
    parser.add_argument("--pio", default=base.DEFAULT_PIO,
                        help="the PlatformIO executable that builds the host environment")
    parser.add_argument("--workspace", default=sweep.BUILD_DIR,
                        help="where this run's perturbed descriptions are written. Give a second "
                             "model a directory of its own, for the reason the sweep this reads "
                             "states: every run writes one description per coefficient per corner "
                             "under the same names")
    arguments = parser.parse_args(argv)

    findings = sweep.run(description=arguments.description, limits=arguments.limits,
                         declaration=arguments.steam_declaration, tolerance=arguments.tolerance,
                         pio=arguments.pio, workspace=arguments.workspace)
    finding = determine(findings)

    # The second reading, over the same four files and the same host artefact,
    # with every perturbation kept out of the control path. It is taken here
    # rather than being a mode this tool can be asked for, because the finding
    # the record exists to carry is the disagreement between the two and a run
    # producing one of them has not produced it.
    drifted_findings = drifted_sweep(findings)
    drifted_finding = determine(drifted_findings)

    text = report_text(findings, finding, drifted_findings, drifted_finding)

    if arguments.stdout:
        sys.stdout.write(text)
        return 0

    os.makedirs(os.path.dirname(arguments.report), exist_ok=True)
    with open(arguments.report, "w", encoding="utf-8") as handle:
        handle.write(text)
    print("analysed %d coefficient(s) of %s under both readings, %d of them in scope, and wrote "
          "the record to %s"
          % (len(finding["determination"]), _relative(findings["description"]),
             len(finding["scoped"]), _relative(arguments.report)))
    when_drifted = dict((record["coefficient"], record["verdict"])
                        for record in drifted_finding["determination"])
    for record in finding["determination"]:
        if record["in_scope"]:
            print("  %-40s %-64s %s"
                  % (record["coefficient"], record["verdict"],
                     when_drifted.get(record["coefficient"], REACHES_NO_RECONSTRUCTION)))
    for entry in hidden_by_drift(finding, drifted_finding):
        print("  %-40s %s" % (entry["coefficient"], HIDDEN_BY_DRIFT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
