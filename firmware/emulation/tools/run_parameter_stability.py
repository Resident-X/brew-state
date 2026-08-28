#!/usr/bin/env python3
"""Take every corner the description's declared error implies, hold the machine
in the state it delivers from for long enough to see what the loop does with it,
and record whether the response came to rest inside the band the design holds
that delivery to or did not.

WHY THE DEVIATION FIGURE BESIDE THIS ONE CANNOT ANSWER IT

run_parameter_sweep.py already perturbs every coefficient carrying a declared
error to both ends of it and re-runs both closed loops against each perturbed
machine. What it takes off those runs is how far the delivery moved, as a
fraction of the margin the design declares it holds that delivery inside. That
is a magnitude, and a magnitude cannot tell two very different machines apart: a
loop that is pushed further from where it started and then recovers, and a loop
that has lost authority and is walking away, both report a larger number. The
first is a machine holding the behaviour the robustness declaration beside the
description classifies as one that must hold across the declared error; the
second is not. A ranking of magnitudes was never built to make that distinction,
and reading one out of it would be reading a figure for something it is not.

So the question here is a different one taken off the same apparatus: at each
corner, does the response settle, and does it settle inside the band. The
corner-perturbation and course-driving machinery is the sweep's, reused rather
than reimplemented, for the reason the identifiability analysis beside this file
gives for reusing it: two harnesses that must agree about what a perturbed
machine does will eventually stop agreeing, and there would then be nothing to
say which of them was the machine.

WHAT STANDARD IS BEING APPLIED, AND WHERE IT COMES FROM

params/robustness.declaration classifies
staying-stable-across-the-declared-error-range as `bounded`, which is a
deliberately weaker class than `invariant`. A behaviour in the bounded class is
permitted to move as the model does, but only inside the range the description
declares; it is not asked to hold against an arbitrarily wrong model. That is
exactly the standard applied here -- every corner is a corner the description's
own declared error names, nothing beyond the declared range is run, and no claim
is made about a machine found to sit outside it.

That class is read out of the declaration through the build-time check's own
reader rather than restated here, and this analysis refuses to run if the
behaviour has been reclassified. A behaviour promoted to `invariant` would mean
this record's standard is the wrong one -- the corners it runs are drawn from the
declared range, and a claim about an arbitrarily wrong model cannot be made from
them -- and a reclassification that left this file quietly reporting against the
old class is precisely the failure of a record nobody re-read.

WHY THE HORIZON HAS TO BE LONGER THAN THE SWEEP'S COURSES

The sweep's own courses are a shot and a wand-open, and its figures are taken
over the window in which each delivery is actually being made. They are the
right length for a magnitude and too short for a settling: at the end of the
sweep's shot the coffee loop is still some kelvin from where it will end up, and
a verdict taken there would call a converging machine unsettled. So this
analysis runs its own courses -- the sweep's own phases, with the delivering
phase lengthened -- and takes its verdict over the trailing part of that
extension.

The extension is a longer *delivering* stretch and not a longer rest, and that
follows from the sweep's own reasoning about what its judged window is: the band
a delivery is held to states how far the thing being delivered may sit from what
the design promises, and nothing is being delivered while the pump is shut. A
tail spent idle would be a verdict about a quantity the band does not apply to.
So the coffee side's shot holds at the level the description's own account calls
the rate a shot is actually drawn at, for the whole of the extension, and the
steam side's wand stays open.

How long the extension is, is a judgement, and it is made against the settling
allowance each side's own course already stands on rather than picked. The
coffee course's flush is fifty seconds because that is where that loop settles
from cold at the declared coefficients with room to spare; the steam course's
settle is thirty seconds because that is what the steam law's own suite gives a
block to reach its ready state. Those are the two figures this project already
stands behind for "long enough for this loop to arrive", and the extensions are
stated multiples of them.

The multiples are not the same on the two sides, and the reason is a property of
the machine rather than a taste. On the coffee side the loop shows a slow
standing mode under a sustained draw -- an excursion of some kelvin decays with a
time constant around a hundred seconds, far longer than the flush that brought
the machine to temperature -- so the extension is fifteen flushes, which carries
the widest excursion the declared errors produce down inside the band with the
better part of the tail still to run. The record reports how much of the tail
that took, so a reader can see the horizon was not sized to the answer it
wanted.

The steam side cannot be extended the same way, and the bound is not
computational. While a wand is held open the loop answers a standing pressure
deficit with block temperature, so the block climbs for as long as the draw
lasts; and past the two hundred degrees the steam control declaration records
the machine's own protection as taking over at, this description says nothing
that can be believed -- its saturation slope is a local one at a hundred degrees
and gives about a quarter of the true pressure up there, and the protective
devices that would actually have opened are not modelled at all. So the steam
extension is two settles rather than fifteen -- two is what leaves the hottest
corner this description produces a comfortable distance under that bound, where
three would bring it within about a tenth of the block's own rise over the draw
-- and every steam run's peak block temperature is checked against that declared
bound. A run that crossed it would not be a finding about a coefficient; it would
be this file's horizon reaching past what the description answers for, and it
stops the analysis rather than being reported.

WHAT COUNTS AS SETTLING

The verdict is taken over the trailing half of the extension, against the
separation between the corner's delivery and the unperturbed machine's delivery
run over the same lengthened course. Against the unperturbed run rather than
against the commanded target, because what is being asked is whether the closed
loop's response *to the perturbation* stays bounded -- and because the two sides
declare their bands differently, one as a half-width around a commanded
temperature and one as a span the delivered pressure has to stay inside, while a
separation from the same machine's own delivery is the same kind of statement on
both.

Two things have to hold, and they are checked in the order they are worth being
told about. The separation must not still be growing across the window -- the
worst it reaches in the window's late half is compared against the worst in its
early half -- and it must lie inside the band that side is held to. A corner
failing the first is reported as diverging; a corner failing only the second has
come to rest somewhere the design does not hold the delivery, which is a
different finding and named differently. Reporting the second where the first is
true would tell a reader a loop had settled when it had not.

How much larger the late half has to be before the difference is growth at all
is floored, because what sits below that floor is the loop's own integer command
quantisation and not a divergence. The floor is each side's own: the smaller of
one count of the machine's converter and a stated small fraction of that side's
band. The seam declares one converter scale for every channel alike, so one count
is a twentieth of one band and a quarter of the other, and a floor worth a
quarter of the band it is judged beside would call a response eating that much
margin per half-window settled -- which is the finding this file exists to make,
made backwards.

That the unperturbed run itself settles is established rather than assumed, and
so is that it settles near the middle of its own band rather than merely
somewhere inside it. A separation taken against a reference that is still
travelling is a comparison of two transients, and every verdict below would be
about the reference. A separation taken against a reference resting on the edge
of its band is not a transient, but it is not a distance from what the design
promises either: a corner a band away on the other side would read as settled
while its own delivery was marginal, and what a verdict here claims is about the
delivery.

TWO PROPERTIES OF THE DECLARED ERROR AN INDEPENDENT TWO-SIDED SWEEP DOES NOT
CARRY

The first is one-sidedness. The description declares three of its coefficients
as reaching downwards -- the two ends of the coffee pump's characteristic and
the steam feed's rate, each of them a figure standing in for something it is
not, whose true value sits below the value rather than either side of it. There
is no grammar for that: the file carries a fraction and the fraction is
symmetric, and which coefficients are one-sided is stated in the prose beside
the numbers. Running such a coefficient's upper corner would be running a
machine the description does not claim, and excluding it altogether would leave
its half of the declared range unchecked -- which is not admissible in a record
claiming to establish stability across that range. So it is run at its one
declared corner, on the same standard as a two-sided coefficient's pair, and the
record names which coefficients those are and that only one corner was taken.

The second is correlation. The description says in as many words that its
element ratings are not independent: both are fed from one supply, so a sagging
mains makes both low at once. A sweep moving one coefficient at a time cannot
exercise that by construction, whatever it does to each of them separately. So
one further corner is run with both ratings low together.

How far together is the one judgement in it. A shared supply droop is a shared
*fractional* movement -- power goes as the square of the voltage on both
elements alike -- so the two are moved by one fraction rather than each to its
own corner. That fraction is the smaller of the two declared errors, which is
the largest equal fractional sag both coefficients' declared errors admit; a
larger one would put the tighter of the two outside the range the description
claims, and the whole standard here is that nothing beyond the declared range is
run. Taking each element to its own declared corner instead would be a different
claim -- two independent errors that happen to point the same way -- and it is
not the one the description makes. Nothing is lost by the smaller figure: the
steam rating's own wider corner is already run on its own, so what the joint
corner adds is the simultaneity and not a wider excursion.

Whether that stated dependence is the real one is a characterisation question
and is not asked here. What is established is that the sweep does not silently
assume an independence the description never claimed.

WHAT THIS IS NOT

It is not a stability proof. What is run is a set of corners the declared error
names, on two courses, and what comes back is what those runs did. A machine can
settle at every corner of a box and misbehave inside it, and nothing here rules
that out; corners are where a monotone response is worst and this description's
relations are not all monotone.

It is not a margin calculation. How far a commanded target should be moved to
keep a delivery inside its band across this range is a different question, and
it is not answered here.

And it is analysis against an estimated model. Every coefficient is an estimate
and so is the error declared against it, so a verdict here is a statement about
what this description implies rather than about what the machine does. The
record names the files and their digests so the same method can be pointed at
the measured model that is meant to replace them.
"""

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))
REPOSITORY_DIR = os.path.abspath(os.path.join(FIRMWARE_DIR, ".."))

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FIRMWARE_DIR, "tools"))

import check_robustness_declaration as robustness  # noqa: E402
import run_cross_tier_check as cross_tier  # noqa: E402
import run_emulation_check as base  # noqa: E402
import run_parameter_sweep as sweep  # noqa: E402

#: Where the verdicts and the horizon they were taken over are kept. Beside the
#: dominance ranking and the identifiability finding rather than inside either,
#: for the reason those two are kept apart from one another: three questions off
#: one apparatus, and a reader who has the answer to one has not been given the
#: others.
REPORT_PATH = os.path.join(REPOSITORY_DIR, "docs", "parameter-stability.md")

#: Where this analysis's own perturbed descriptions are written.
#:
#: A directory of its own rather than the sweep's, on the terms the sweep states
#: for a second model: every run writes one description per coefficient per
#: corner under the same names, so two analyses sharing a directory leave the
#: second's standing where the first's were. Nothing reading a finished run would
#: notice, and anything going back to the files to establish what a run actually
#: handed the machine would be reading the other analysis's.
BUILD_DIR = os.path.join(FIRMWARE_DIR, ".pio", "build", cross_tier.HOST_ENVIRONMENT, "stability")

#: The declaration that says what a wrong model is permitted to take away, and
#: the behaviour in it this analysis is the verification of.
#:
#: Named here and read there. What class that behaviour carries decides what
#: standard these runs have to be held to, and a class that moved without this
#: record moving with it is the failure a graph of decisions exists to prevent --
#: so it is read on every run rather than restated.
ROBUSTNESS_DECLARATION = os.path.join(FIRMWARE_DIR, "params", "robustness.declaration")
THE_BEHAVIOUR = "staying-stable-across-the-declared-error-range"

#: The class that behaviour has to carry for the corners run here to be the right
#: ones. Bounded means the behaviour holds across the range the description
#: declares and is not claimed beyond it, which is what a sweep over declared
#: corners can establish. Were it invariant, the standard would be a machine
#: arbitrarily far from the description and no set of declared corners could
#: speak to it.
BOUNDED = "PLANT_ROBUSTNESS_BOUNDED"

#: Where the temperature past which the steam path's own protection decides what
#: happens is declared, and the word it is declared under. Read out of the
#: grammar that already bounds the steam control declaration against it rather
#: than written here as a number, so a machine whose protection opens elsewhere
#: moves this analysis's horizon without anything here being edited.
STEAM_GRAMMAR_SOURCE = os.path.join(FIRMWARE_DIR, "src", "delivery", "steam_control_declaration.c")
STEAM_BLOCK_CEILING_MACRO = "STEAM_CONTROL_DECLARATION_TEMPERATURE_HIGH_MILLI_C"

# --- How long each side is held in the state it delivers from ----------------
#
# Both extensions are stated multiples of the settling allowance that side's own
# course already stands on, rather than figures of this file's own: the coffee
# course's flush is where that loop settles from cold at the declared
# coefficients, and the steam course's settle is what the steam law's own suite
# gives a block to reach its ready state.

#: The coffee side's extension, as a multiple of the flush its course already
#: allows for settling from cold.
#:
#: Fifteen and not one, because the two are not the same settling. The flush
#: brings a cold machine to temperature at a steady trickle; what has to settle
#: here is the standing mode this loop shows under a sustained draw, whose
#: excursion at the widest corner the declared errors produce is some eight
#: kelvin and decays with a time constant of order a hundred seconds -- twice the
#: flush on its own. Fifteen flushes is seven and a half minutes of drawing,
#: which carries that excursion inside the band with the better part of the tail
#: still to run; how much of the tail it actually took is reported, so the
#: horizon can be seen not to have been sized to the answer.
BREW_TAIL_MULTIPLE = 15

#: The steam side's extension, as a multiple of the settle its course already
#: allows.
#:
#: Two and not fifteen, and the figure is fixed by a bound rather than by how
#: long a settling would like to be. While a wand is held open the loop answers a
#: standing pressure deficit with block temperature, so the block climbs for as
#: long as the draw lasts. Past the temperature the steam grammar records the
#: machine's own protection as taking over at, this description says nothing that
#: can be believed: its saturation slope is a local one at the boiling point and
#: gives about a quarter of the true pressure up there, and the protective
#: devices that would have opened are not modelled at all.
#:
#: Two settles is what leaves the hottest corner this description produces -- the
#: shallowest saturation slope, since a block has to run hotter to make the same
#: pressure through a shallower one -- a comfortable distance under that bound
#: rather than a few degrees from it. Three would bring it within about a tenth
#: of the block's own rise over the draw, which is near enough that a model moved
#: a little would push a run past the bound and stop the analysis. How much
#: margin was actually left is read off the runs and reported, so this figure can
#: be seen to be the one the bound admits rather than the one that made an answer
#: come out.
#:
#: The steam side can afford the shorter extension where the coffee side cannot,
#: and that is a property of the two loops rather than a concession: the steam
#: sensor sits on the block with nothing between them, so that loop has no slow
#: standing mode of the kind the coffee side's conduction corner produces between
#: the casting and the group.
STEAM_TAIL_MULTIPLE = 2

BREW_TAIL_STEPS = BREW_TAIL_MULTIPLE * sweep.BREW_FLUSH_STEPS
STEAM_TAIL_STEPS = STEAM_TAIL_MULTIPLE * sweep.STEAM_SETTLE_STEPS

#: Which part of the extension the verdict is taken over: the trailing half.
#:
#: The trailing part rather than the whole, because the beginning of the
#: extension is the corner's own excursion arriving and a window that included it
#: would report every corner as having been outside the band at some point --
#: which is what the dominance figure beside this record already says, and says
#: better. Half rather than a smaller slice, because the window is also where a
#: divergence has to be visible, and a comparison of a short window's two halves
#: is a comparison over too little of the loop's own slow mode to mean anything.
SETTLING_WINDOW_FRACTION = 0.5

#: How much of a side's own band the growth floor is allowed to be worth.
#:
#: The floor below which a change in the separation is read as the loop's own
#: command quantisation rather than as growth is one count of the machine's
#: converter, and the seam declares one full scale for every channel alike. That
#: is a figure about the board and not about either delivery, and it lands very
#: differently on the two sides: one count is about a twentieth of the coffee
#: side's one-kelvin band and about a quarter of the steam side's fifth-of-a-bar
#: one. A quarter of a band per half-window is not a floor, it is most of the
#: margin -- a steam response growing at just under it would be called settled
#: while eating the band it is being judged against.
#:
#: So the floor each side actually uses is the smaller of the seam's figure and
#: this fraction of that side's own declared band. A twentieth is chosen: it is
#: small enough that what hides under it cannot consume a band over the handful
#: of half-windows a verdict is taken across, and large enough to stand above the
#: command beat the floor exists for -- on the coffee side the seam's own figure
#: is already a twentieth of the band and is what gets used, which is the
#: evidence that a twentieth is not below the beat rather than an argument that
#: it is not.
#:
#: This is deliberately not the reasoning the identifiability analysis beside
#: this file gives for its own floor, and the difference is the direction the
#: error falls in. There a generous floor errs towards "not shown identifiable",
#: which is the safe answer -- it declines to claim something. Here a generous
#: floor errs towards "settled", which is a claim, and the unsafe one: it says a
#: response came back when it may not have. A floor that may only be too small is
#: what this analysis wants and a floor that may be too large is what that one
#: can afford, so the reasoning cannot be inherited even though the seam figure
#: is the same.
GROWTH_FLOOR_BAND_FRACTION = 0.05

#: How near the middle of its own band the unperturbed machine has to sit before
#: a separation taken against it stands in for a distance from the target.
#:
#: Every verdict below is a separation between a corner's delivery and the
#: unperturbed machine's, and the band it is compared against is a distance from
#: what the design promises. Those are the same statement only where the
#: reference is itself close to what the design promises: a reference sitting on
#: one edge of its band and a corner sitting on the other are a band apart while
#: the separation between them reads as one band, and both are marginal while
#: the table calls the corner settled.
#:
#: Requiring only that the reference be somewhere inside its band -- which is
#: what this guard asked for first, and is not enough -- leaves the separation
#: worth up to a whole band less than the corner's real distance from target. A
#: fifth is required instead, so that a corner called settled at the very edge of
#: the band is at worst a fifth of a band outside it rather than a whole one, and
#: the reader of a "settled within the band" verdict is being told something
#: about the delivery and not only about the two runs' agreement.
#:
#: A fifth rather than a tenth because the reference is a real closed loop under
#: a sustained draw and not a set point: it carries the same standing ripple
#: every corner does, and a bound tight enough to catch that ripple would refuse
#: the analysis over a property of the loop rather than over a reference that had
#: not arrived. A fifth rather than a half because a half is not a bound at all
#: on the argument above. The shipped model sits at about a twenty-fifth of the
#: coffee band from its commanded temperature and about a thirtieth of the steam
#: band from the middle of its span, so this guard has room in hand on both sides
#: -- which is what makes it a guard against a model that moved rather than a
#: figure fitted to this one.
REFERENCE_CENTRED_WITHIN = 0.2

# --- What the description declares one-sided ---------------------------------

#: The coefficients whose declared error reaches in one direction only, and which
#: direction that is.
#:
#: This is the one thing here that is stated in a file rather than read out of
#: one, and it is stated because there is nowhere to read it from. A description
#: line carries a fraction, and a fraction is symmetric by construction: the
#: grammar has no way to say that a value is a ceiling on the truth rather than a
#: centre. Which coefficients are one-sided is written in the prose beside the
#: numbers -- params/thermoblock.md, under how wrong each value is assumed to be
#: -- and all three are one-sided the same way and for the same kind of reason.
#: Each is a figure standing in for something it is not: the two ends of the
#: coffee pump's characteristic, which no pump is at both of at once, and the
#: steam feed's open-path rate, which has no figure standing opposite it at all.
#: A real machine sits below each of them rather than either side.
#:
#: Adding to the sweep's own corner logic instead was the alternative and is
#: refused. That logic is what the committed dominance figures were taken with,
#: and a one-sided corner set would move them -- which this analysis is not
#: entitled to do. So the record is here, scoped to the question that needs it.
#:
#: A coefficient named here that a description does not carry is not an error:
#: pointing this method at a replacement model is the whole of what makes it
#: repeatable, and a replacement need not carry the same coefficients. Which of
#: them were found and which were not is reported, so a name that has gone stale
#: is visible rather than silent.
#:
#: Nothing structural ties this table to the prose it was read out of, and there
#: is no field in the description's grammar that could: one-sidedness is a
#: sentence in params/thermoblock.md and the file beside it carries a symmetric
#: fraction. So a coefficient declared one-sided in that prose after this table
#: was written, or a value or fraction moved under it, would leave this analysis
#: running the old assumption and reporting it as current. The tripwire is a test
#: rather than a check here -- the suite pins the exact nominal and fraction each
#: name in this table and in MAINS_COUPLED below is presently written at, read
#: through the sweep's own reader off the live description, so any movement in
#: those five lines fails loudly instead of being carried silently.
REACHING_DOWNWARDS = "low"
ONE_SIDED = {
    "pump.pressure_bar": REACHING_DOWNWARDS,
    "pump.flow_ml_per_s": REACHING_DOWNWARDS,
    "steam.feed_flow_ml_per_s": REACHING_DOWNWARDS,
}

# --- What the description declares moves together ----------------------------

#: The two coefficients the description says are not independent of one another,
#: and which nothing in a one-at-a-time sweep can exercise together.
#:
#: Stated here for the reason the one-sidedness above is: the description says it
#: in prose -- both elements are fed from one supply, so a sagging mains makes
#: both low at once -- and carries no grammar for a relationship between two
#: values. It is the only such relationship the description states, and a general
#: sweep over every pairing a description might one day declare is deliberately
#: not what this is.
#:
#: The direction is downwards and there is one corner rather than four. A mains
#: droop lowers a supply; there is no shared cause the description names that
#: would raise both at once, and inventing the other three corners of a box would
#: be running machines the description does not claim.
#:
#: It is written as which element each delivery is made by rather than as a bare
#: pair, because one thing downstream needs to know that and cannot work it out:
#: comparing the joint corner against an independent one is only a comparison at
#: all when the independent corner is the one that side's own element makes. The
#: coffee delivery is made by the coffee element and the steam delivery by the
#: steam one, and this description carries no path between them.
#:
#: This table is prose from params/thermoblock.md in the same way the one-sided
#: table above is -- the description states that both elements are fed from one
#: supply, and its grammar has nowhere to put a relationship between two values
#: -- so the same tripwire covers it. See the account above REACHING_DOWNWARDS.
MAINS_COUPLED_BY_SIDE = {
    sweep.BREW_SIDE: "brew.heater_power_w",
    sweep.STEAM_SIDE: "steam.heater_power_w",
}
MAINS_COUPLED = (MAINS_COUPLED_BY_SIDE[sweep.BREW_SIDE], MAINS_COUPLED_BY_SIDE[sweep.STEAM_SIDE])

#: How the joint corner is named wherever a corner has to be named. It is not a
#: coefficient of the description and must not read as one, so it names both
#: coefficients and what moves them.
JOINT_COEFFICIENT = "%s + %s (joint mains droop)" % MAINS_COUPLED
JOINT_CORNER = "low together"

# --- The verdicts ------------------------------------------------------------

#: What a corner can leave this analysis with, written as it is into the record.
#:
#: The two ways of failing are kept apart rather than collapsed, because they are
#: different findings about the machine and only one of them is about stability
#: at all. A response still growing at the end of the horizon is a loop that has
#: not come back; a response that has come to rest outside the band is a loop
#: that has, at a delivery the design does not accept. A record that said only
#: "did not settle" would leave a reader unable to tell a machine that needs a
#: different loop from one that needs a wider band or a smaller draw.
SETTLED = "settled within the band"
SETTLED_OUTSIDE_THE_BAND = "did not settle: came to rest outside the band"
STILL_DIVERGING = "did not settle: still growing at the horizon"

#: What is recorded for a corner the structure would not admit as a machine. It
#: is a finding about the description's own declared error rather than a verdict
#: about a loop, and it is kept apart from the three above for that reason.
CORNER_REFUSED = "not run: refused as a machine"

#: How the figures are written into the record. Three significant figures, on the
#: terms the two records beside this one state: more than an analysis of a
#: description whose own errors run from two per cent to eighty can support.
FIGURE_FORMAT = "%.3g"

#: How a perturbed coefficient is written into a description. The sweep's own
#: format, because the perturbed machines this runs are meant to be the same
#: machines the sweep would write and a second format here would round them
#: differently.
VALUE_FORMAT = sweep.VALUE_FORMAT


class StabilityError(RuntimeError):
    """The analysis could not be run, or could not be run over everything it
    covers."""


# --- What the declaration says the standard is -------------------------------


def declared_class(declaration=ROBUSTNESS_DECLARATION, include_directory=None):
    """The class the robustness declaration puts this analysis's behaviour in.

    Read through the build-time check's own reader rather than by a pattern of
    this file's, on the terms every other reading in this tier is taken: a
    second reader would be a second opinion about what a classification says,
    and the two would eventually disagree about a file neither is wrong about.

    What comes back is the word the declaration writes, together with the word
    the vocabulary spells the bounded class as -- so a caller can compare the two
    without holding an opinion about either.
    """
    include_directory = sweep.INCLUDE_DIR if include_directory is None else include_directory
    words, problems = robustness.load_vocabulary(include_directory)
    if words is None:
        raise StabilityError("; ".join(problems))
    if BOUNDED not in words:
        raise StabilityError(
            "the robustness vocabulary declares no %s, so the class this analysis is the "
            "verification of cannot be named" % BOUNDED)
    problems, classified = robustness.inspect(declaration, words)
    if problems:
        raise StabilityError("; ".join(problems))
    if THE_BEHAVIOUR not in classified:
        raise StabilityError(
            "%s classifies no '%s', so what standard these corners are to be held to is not "
            "declared anywhere and this analysis would be applying one of its own"
            % (declaration, THE_BEHAVIOUR))
    return classified[THE_BEHAVIOUR], words[BOUNDED]


def bounded_or_refuse(declaration=ROBUSTNESS_DECLARATION, include_directory=None):
    """The class, having established it is the one these corners can speak to.

    A behaviour promoted out of the bounded class is not a detail this analysis
    may carry on through. The corners run here are drawn from the range the
    description declares, and a behaviour required to hold however wrong the
    model is cannot be established from them at all -- so a record that went on
    being written would be answering the old question under the new question's
    name.
    """
    carried, bounded = declared_class(declaration, include_directory)
    if carried != bounded:
        raise StabilityError(
            "%s classifies '%s' as '%s' rather than '%s'. The corners this analysis runs are the "
            "ones the description's own declared error names, which can establish a behaviour "
            "across that declared range and cannot establish one that has to hold however wrong "
            "the model is -- so this record would be answering a question nobody is now asking"
            % (declaration, THE_BEHAVIOUR, carried, bounded))
    return carried


# --- The bound the steam horizon is held under -------------------------------


def steam_block_ceiling_c(source=STEAM_GRAMMAR_SOURCE):
    """The block temperature past which this description answers for nothing.

    It is the figure the steam control grammar already bounds a ready target
    against, and the account beside it says what it is: the temperature the
    machine's own protection takes over at, past which what happens is decided by
    a thermostat this model does not carry. Two further things about the
    description fail there at once -- its saturation slope is a local one at the
    boiling point and gives a fraction of the true pressure that far above it --
    so a verdict taken off a run that went there would be a verdict about
    arithmetic rather than about a machine.

    Read from the grammar rather than written here, so a machine whose protection
    opens elsewhere moves this horizon without anything in this file being
    edited.
    """
    found = re.search(
        r"^\s*#\s*define\s+%s\s+(-?\d+)\s*$" % re.escape(STEAM_BLOCK_CEILING_MACRO),
        sweep.origins.read(source), re.MULTILINE)
    if found is None:
        raise StabilityError(
            "%s declares no %s, so the temperature past which this description answers for "
            "nothing "
            "cannot be read and this analysis has no bound to hold its horizon under"
            % (source, STEAM_BLOCK_CEILING_MACRO))
    return int(found.group(1)) / 1000.0


def steam_block_peak_c(findings):
    """The hottest the steam block got over one draw."""
    at = sweep.closed_loop.QUANTITY_KEYS.index("steam-c")
    return max((reported["quantities"][at] for reported in findings["trajectory"]), default=0.0)


# --- The two lengthened courses ----------------------------------------------


def brew_course(tail=BREW_TAIL_STEPS):
    """The coffee side's course with its hold lengthened, as (interval, pump
    level) per control interval.

    The sweep's own five phases and the sweep's own figures, with the hold -- and
    only the hold -- carrying the extension. Lengthening the hold rather than
    appending a second phase is what keeps this one shot rather than two: a
    course that tapered off, rested and then drew again would be asking what the
    loop does about a second extraction, which is a different question and one
    whose answer would depend on how long the rest between them was.

    The rest at the end is kept even though no verdict is taken over it. It costs
    three seconds of a seven-minute run and it keeps the course the same shape as
    the one the dominance figures were taken over, so the two can be read against
    one another without a reader wondering which phases each had.
    """
    levels = [sweep.BREW_FLUSH_PERMILLE] * sweep.BREW_FLUSH_STEPS
    levels += [sweep.BREW_PRE_INFUSION_PERMILLE] * sweep.BREW_PRE_INFUSION_STEPS
    levels += [int(round(sweep.BREW_PEAK_PERMILLE * float(at + 1) / sweep.BREW_RAMP_STEPS))
               for at in range(sweep.BREW_RAMP_STEPS)]
    levels += [sweep.BREW_PEAK_PERMILLE] * (sweep.BREW_HOLD_STEPS + tail)
    levels += [int(round(sweep.BREW_PEAK_PERMILLE
                         * (1.0 - float(at + 1) / sweep.BREW_TAPER_STEPS)))
               for at in range(sweep.BREW_TAPER_STEPS)]
    levels += [0] * sweep.BREW_REST_STEPS
    return [(sweep.INTERVAL_MS, level) for level in levels]


def brew_hold_ends_at(tail=BREW_TAIL_STEPS):
    """The interval the lengthened hold runs to, exclusive.

    Computed from the sweep's own phase lengths rather than by looking for where
    the course stops asking for the peak level, because the taper's first step is
    a rounding away from that level and a search would end the hold one interval
    early or late depending on where the arithmetic landed.
    """
    return (sweep.BREW_FLUSH_STEPS + sweep.BREW_PRE_INFUSION_STEPS + sweep.BREW_RAMP_STEPS
            + sweep.BREW_HOLD_STEPS + tail)


def steam_course(tail=STEAM_TAIL_STEPS):
    """The steam side's course with its draw lengthened, as (interval, demanded
    rate) per control interval.

    The wand is held open for the extension rather than the machine being left to
    stand afterwards, for the reason the coffee side's hold is lengthened: the
    band this side is judged against states the character of the steam coming
    out, and there is none coming out once the wand is shut.
    """
    demand = [0] * sweep.STEAM_SETTLE_STEPS
    demand += [sweep.STEAM_DEMAND_MILLI_ML_PER_S] * (sweep.STEAM_DRAW_STEPS + tail)
    demand += [0] * sweep.STEAM_REST_STEPS
    return [(sweep.INTERVAL_MS, rate) for rate in demand]


def steam_draw_ends_at(tail=STEAM_TAIL_STEPS):
    """The interval the lengthened draw runs to, exclusive."""
    return sweep.STEAM_SETTLE_STEPS + sweep.STEAM_DRAW_STEPS + tail


def settling_window(ends_at, tail, fraction=SETTLING_WINDOW_FRACTION):
    """The intervals a verdict is taken over: the trailing part of the extension.

    Returned as the list of intervals the sweep's own separation reader takes,
    rather than as a pair, so that what is compared here and what the dominance
    figures are compared over are the same kind of thing read by the same
    function.
    """
    length = int(round(tail * fraction))
    if length < 2:
        raise StabilityError(
            "a settling window of %d interval(s) cannot be halved into an early and a late part, "
            "so there is nothing to compare a response's growth across" % length)
    return list(range(ends_at - length, ends_at))


def reading_resolution():
    """What one count of the machine's converter is worth, in a delivered
    quantity's own unit.

    Read out of the hardware seam through the reader the cross-tier comparison
    already stands its readings up through, rather than written here. The seam
    declares one full scale for every channel, so this is one figure and not two;
    a board declaring another moves the floor below without anything here being
    edited.
    """
    counts, milli = cross_tier.converter_scale()
    if counts <= 0 or milli <= 0:
        raise StabilityError(
            "the hardware seam declares a converter full scale of %d counts at %d milli-units, so "
            "there is no resolution for a change in a separation to be measured against"
            % (counts, milli))
    return float(milli) / float(counts) / 1000.0


def growth_floors(bands, reading=None, fraction=GROWTH_FLOOR_BAND_FRACTION):
    """What a change in each side's separation has to clear to be growth at all.

    One figure per side rather than the seam's single one, because the seam's
    figure is about the board and the question is about a delivery. The seam
    declares one converter full scale for every channel alike, so one count is
    worth what it is worth against whichever quantity it is being read beside --
    a twentieth of the coffee side's band and a quarter of the steam side's. A
    floor worth a quarter of a band is not separating a rounding from a
    divergence; it is admitting a divergence that spends a quarter of the margin
    per half-window and calling it settled.

    So each side takes the smaller of the seam's own figure and a stated fraction
    of its own declared band, and which of the two bound it is reported rather
    than left to be worked out. The reasoning for the fraction, and for why this
    analysis cannot take the identifiability analysis's view that a generous
    floor is the safe one, is at GROWTH_FLOOR_BAND_FRACTION.
    """
    reading = reading_resolution() if reading is None else reading
    floors = {}
    for side, band in bands.items():
        if band <= 0.0:
            raise StabilityError(
                "the %s side is held to a band of %g, so there is no margin for a growth floor to "
                "be a fraction of and nothing for a separation to be judged against"
                % (side, band))
        floors[side] = min(reading, fraction * band)
    return floors


def halves(window):
    """One window's early and late halves, as two windows.

    An odd window gives the earlier half the extra interval, which is the
    direction that cannot manufacture growth: a late half made larger than its
    early half has more intervals to find a worst case in, and would report a
    settled response as growing on nothing but its own arithmetic.
    """
    at = len(window) - len(window) // 2
    return window[:at], window[at:]


# --- What one corner's response did ------------------------------------------


def settle_of(reference, perturbed, window, band, floor):
    """Whether one corner's response came to rest, and inside what.

    The separation between the two runs' deliveries is what is judged, and it is
    read through the sweep's own worst-separation reader over each half of the
    window -- the same function the dominance figures are taken with, so that
    what "how far apart" means cannot come to be two different answers.

    Two conditions, checked in the order they are worth being told about. A
    separation whose worst case in the window's late half stands above its worst
    case in the early half is still growing, which is the finding about stability
    and is reported first. A separation that is not growing but stands outside
    the band is a loop that has come to rest at a delivery the design does not
    accept, which is a finding about the delivery. Reporting the second where the
    first is true would tell a reader a response had settled when it had not.

    Growth is judged on the worst case in each half rather than on where the
    separation happened to be at each end, because a response with any ripple on
    it crosses its own final value repeatedly and two instantaneous readings
    would report whichever side of it the two intervals fell on.

    `floor` is how much larger the late half has to be before the difference is
    growth at all, and it is this side's own: the smaller of one count of the
    machine's converter and a stated small fraction of the band this side is held
    to. A floor is needed here and it is not for the reason a reader arriving
    from the identifiability analysis beside this file would expect. What sits
    down there is not the model's arithmetic rounding: it is the integer
    quantisation of the commands the loop issues, which is orders of magnitude
    coarser than one last place of a single-precision figure. Two runs of the
    same machine a hair apart command the same duties for long stretches and then
    part by one permille, which puts a slow beat on the separation between them
    -- and a beat crosses a window boundary in whichever direction it happened to
    be going. Without a floor those crossings are read as divergences, which is
    an instability finding manufactured out of a rounding.

    One converter count is the coarsest distinction anything on this board draws
    and it stands well above that beat, which is what makes it the floor rather
    than one last place of the model's own arithmetic. What it is not allowed to
    be is a large part of the band it is being read beside, and that is the other
    half of what fixes it: the seam's figure is a statement about the board and
    lands as a twentieth of one side's band and a quarter of the other's, so each
    side takes whichever of the two is smaller. What it costs either way is
    stated where the record states what it does not settle: a separation growing
    more slowly than this side's floor per half-window is called settled here.
    """
    early, late = halves(window)
    at_first, _ = sweep.worst_separation(reference, perturbed, early)
    at_last, _ = sweep.worst_separation(reference, perturbed, late)
    worst, worst_at = sweep.worst_separation(reference, perturbed, window)
    growing = at_last > at_first + floor
    if growing:
        verdict = STILL_DIVERGING
    elif worst > band:
        verdict = SETTLED_OUTSIDE_THE_BAND
    else:
        verdict = SETTLED
    return {
        "early": at_first,
        "late": at_last,
        "worst": worst,
        "worst_at": worst_at,
        "band": band,
        "floor": floor,
        "growing": growing,
        "verdict": verdict,
    }


def last_outside_the_band(reference, perturbed, tail, band):
    """How far into the extension the separation last stood outside the band, as
    a fraction of the extension.

    What this is for is the horizon's own account of itself. A verdict of settled
    says the separation was inside the band across the whole of the window it was
    judged over, and says nothing about whether it got there with room to spare
    or on the last interval before the window opened. The horizon is long enough
    exactly when every settling corner is inside the band well before the window
    opens, and this is the figure that says so -- reported rather than asserted,
    because a horizon that had quietly become too short for a changed model would
    otherwise show up as a settled corner turning unsettled with nothing to say
    why.

    A corner that never left the band anywhere in the extension comes back as
    nothing, which is the honest answer for it: the horizon was not needed to
    bring that corner inside the band, so there is no length of it that figure
    could be a fraction of.
    """
    latest = None
    for at in tail:
        if abs(perturbed[at] - reference[at]) > band:
            latest = at
    if latest is None:
        return 0.0
    return float(latest - tail[0] + 1) / float(len(tail))


# --- Which corners each coefficient is run at --------------------------------


def corners_of(name, nominal, fraction):
    """The corners one coefficient is run at, as (corner, value).

    Both ends of the declared error, as the sweep takes them, unless the
    description declares the coefficient one-sided -- in which case only the
    declared end is a machine the description claims, and the other would be a
    run of something nobody has asserted exists.
    """
    reaching = ONE_SIDED.get(name)
    taken = []
    for corner, factor in (("low", 1.0 - fraction), ("high", 1.0 + fraction)):
        if reaching is not None and corner != reaching:
            continue
        taken.append((corner, nominal * factor))
    if not taken:
        raise StabilityError(
            "'%s' is recorded as reaching '%s', which is not a corner this sweep takes, so it "
            "would be run at nothing and its half of the declared range left unchecked"
            % (name, reaching))
    return taken


def one_sided_account(covered):
    """Which of the coefficients recorded as one-sided this description carries,
    and which it does not.

    Both halves are reported. A name that has gone stale -- a coefficient
    renamed, or a replacement model that does not carry it -- would otherwise
    leave this analysis quietly running both corners of something the record
    still claims it ran one of.
    """
    present = set(name for name, _, _ in covered)
    found = sorted(name for name in ONE_SIDED if name in present)
    missing = sorted(name for name in ONE_SIDED if name not in present)
    return found, missing


def joint_sag(covered):
    """The equal fractional sag both mains-coupled coefficients admit, and what
    each is written at.

    The smaller of the two declared errors, applied to both. A shared supply
    droop moves both elements by one fraction rather than each to its own corner
    -- power goes as the square of the voltage on both alike -- and the largest
    such fraction the description admits is the one the tighter of the two
    declares. Anything larger would put that coefficient outside the range the
    description claims, which is the one thing this analysis does not do.

    Nothing comes back if the description does not carry both coefficients: the
    dependence is a statement about two named values, and it cannot be run
    against a model carrying one of them.
    """
    declared = dict((name, (nominal, fraction)) for name, nominal, fraction in covered)
    if not all(name in declared for name in MAINS_COUPLED):
        return None
    sag = min(declared[name][1] for name in MAINS_COUPLED)
    return sag, dict((name, declared[name][0] * (1.0 - sag)) for name in MAINS_COUPLED)


# --- Running the corners -----------------------------------------------------


def _draws(executable, description, limits, declaration, ready_c, scale, courses, label):
    """The unperturbed machine put through both lengthened courses.

    A refusal here is raised rather than recorded, which is what separates this
    from the reader every corner is drawn through. A corner the structure will
    not admit is a finding about the declared error and the run goes on without
    it; a reference the structure will not admit is the machine every verdict
    would have been taken against, and there is nothing left to record.
    """
    return {
        sweep.BREW_SIDE: sweep.brew_draw(executable, description, limits,
                                         courses[sweep.BREW_SIDE], scale,
                                         "stability-%s-brew" % label),
        sweep.STEAM_SIDE: sweep.steam_draw(executable, description, limits, declaration, ready_c,
                                           courses[sweep.STEAM_SIDE],
                                           "stability-%s-steam" % label),
    }


def reference_delivers_in_band(runs, windows, bands, declaration):
    """Establish that the unperturbed machine itself settled, and say where.

    Every verdict below is a separation taken against this run, so a reference
    that is still travelling at the horizon would have each corner compared
    against a transient rather than against a machine at rest. That failure does
    not announce itself: the separations would still be small for corners moving
    the same way as the reference and large for corners moving the other, and the
    table would look like a finding.

    The two sides are judged against their own declarations rather than against
    one another: the coffee side against the half-width the tolerance declaration
    states around the temperature that was commanded, the steam side against the
    two edges the steam declaration puts the delivered pressure between.

    Two things are asked of each side and the second is the one that makes the
    verdicts below mean what they say. The first is that the reference is inside
    its band at all -- a reference outside it is a machine that never arrived, and
    nothing can be established against it. The second is that it is inside the
    band by a wide margin: near the middle of it, within the fraction
    REFERENCE_CENTRED_WITHIN states and not merely somewhere between the edges.

    That second bound is what lets a separation from this run stand in for a
    distance from what the design promises. Every corner below is judged on how
    far its delivery sits from this one, and the band it is judged against is a
    distance from a target -- so the two are the same statement only where the
    reference is close to the target. A reference sitting on one edge with a
    corner on the other would show a separation of one band while both were
    marginal, and the table would call the corner settled. The account of why a
    fifth rather than something looser or tighter is at REFERENCE_CENTRED_WITHIN.
    """
    brew = runs[sweep.BREW_SIDE]["delivered"]
    worst = max(abs(brew[at] - sweep.BREW_TARGET_C) for at in windows[sweep.BREW_SIDE])
    if worst > bands[sweep.BREW_SIDE]:
        raise StabilityError(
            "the unperturbed coffee draw sat %.4f C from the %.1f C it was commanded over the "
            "window every verdict is taken in, outside the %.4f C band the design holds it to -- "
            "so the machine the corners are compared against had not settled either"
            % (worst, sweep.BREW_TARGET_C, bands[sweep.BREW_SIDE]))
    _near_enough_to_the_middle(
        worst, bands[sweep.BREW_SIDE],
        "the unperturbed coffee draw sat %.4f C from the %.1f C it was commanded"
        % (worst, sweep.BREW_TARGET_C),
        "C")

    floor = sweep._declared_figure(
        declaration, sweep._declared_word(sweep.STEAM_DECLARATION_HEADER,
                                          sweep.STEAM_FLOOR_MACRO)) / 1000.0
    ceiling = sweep._declared_figure(
        declaration, sweep._declared_word(sweep.STEAM_DECLARATION_HEADER,
                                          sweep.STEAM_CEILING_MACRO)) / 1000.0
    steam = runs[sweep.STEAM_SIDE]["delivered"]
    outside = [at for at in windows[sweep.STEAM_SIDE] if not floor <= steam[at] <= ceiling]
    if outside:
        raise StabilityError(
            "the unperturbed steam draw left the %.3f..%.3f bar band the design holds it to on %d "
            "of the %d intervals every verdict is taken over, so the machine the corners are "
            "compared against had not settled either"
            % (floor, ceiling, len(outside), len(windows[sweep.STEAM_SIDE])))
    middle = (floor + ceiling) / 2.0
    from_middle = max(abs(steam[at] - middle) for at in windows[sweep.STEAM_SIDE])
    _near_enough_to_the_middle(
        from_middle, bands[sweep.STEAM_SIDE],
        "the unperturbed steam draw sat %.4f bar from the %.3f bar middle of the %.3f..%.3f bar "
        "span it is held inside" % (from_middle, middle, floor, ceiling),
        "bar")
    return {"brew_worst_from_target": worst, "steam_floor": floor, "steam_ceiling": ceiling,
            "steam_middle": middle, "steam_worst_from_middle": from_middle,
            "centred_within": REFERENCE_CENTRED_WITHIN}


def _near_enough_to_the_middle(distance, band, what, unit, fraction=REFERENCE_CENTRED_WITHIN):
    """Refuse a reference that is inside its band and not near the middle of it.

    Its own function because both sides ask it and the two would otherwise state
    the same standard twice, in two places free to drift apart -- and because the
    thing being refused is subtle enough that a reader meeting it on one side has
    to be able to find the whole of the reasoning from either.
    """
    if distance > fraction * band:
        raise StabilityError(
            "%s over the window every verdict is taken in. That is inside the %.4f %s band the "
            "design holds it to and further than %g of it from the middle, which is too far off "
            "the target for a separation taken against this run to stand in for a distance from "
            "the target: a corner sitting a band away on the other side would be reported as "
            "settled while its delivery was marginal. The analysis stops rather than issuing "
            "verdicts that read as being about a delivery and are only about two runs agreeing"
            % (what, band, unit, fraction))


def _under_the_ceiling(peak, ceiling, label):
    """Establish that one steam run stayed inside what the description answers
    for.

    A crossing is not a finding about the coefficient that produced it. Every
    steam run here is held open for the same extension, so a run that went past
    the bound says this analysis's horizon reaches beyond what the description
    can be believed about -- which is a fault in the horizon and stops the
    analysis rather than being reported as a verdict.
    """
    if peak >= ceiling:
        raise StabilityError(
            "the %s steam draw carried the block to %.1f C, at or past the %.1f C the steam "
            "grammar records the machine's own protection as taking over at. Past there this "
            "description's saturation slope gives a fraction of the true pressure and the "
            "protective devices are not modelled at all, so no verdict can be taken off this run "
            "-- the horizon this analysis holds the wand open for is longer than the description "
            "answers for" % (label, peak, ceiling))


def _draw_each_side(executable, description, limits, declaration, ready_c, scale, courses, label):
    """One machine put through both lengthened courses, with a side the structure
    would not admit recorded rather than raised.

    The one place a corner's draws are made, so that every corner -- each
    single-coefficient one and the joint one alike -- is admitted on exactly the
    same terms. A corner the structure refuses is a finding about the
    description's declared error and not a failure of this analysis: the declared
    error reaches a value these equations stop describing a machine at, which is
    worth recording beside the corners that did run. Raising instead would stop
    the whole analysis on one inadmissible corner, and having two copies of this
    -- one that records and one that raises -- would mean the joint corner and
    the independent ones were admitted on different terms while a comment said
    they were not.

    Comes back as a pair: what ran, and why each side that did not was refused.
    """
    runs, refused = {}, {}
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        try:
            if side == sweep.BREW_SIDE:
                runs[side] = sweep.brew_draw(executable, description, limits, courses[side], scale,
                                             "stability-%s-brew" % label)
            else:
                runs[side] = sweep.steam_draw(executable, description, limits, declaration,
                                              ready_c, courses[side],
                                              "stability-%s-steam" % label)
        except (sweep.SweepError, cross_tier.CrossTierError) as refusal:
            refused[side] = str(refusal).splitlines()[0]
    return runs, refused


def _corner_record(coefficient, corner, values, runs, reference, windows, tails, bands, floors,
                   ceiling, description, refused=None):
    """What one perturbed machine did on both sides."""
    record = {
        "coefficient": coefficient,
        "corner": corner,
        "values": values,
        "description": description,
        "sides": {},
        "refused": dict(refused or {}),
    }
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        run = runs.get(side)
        if run is None:
            continue
        if side == sweep.STEAM_SIDE:
            record["steam_block_peak_c"] = steam_block_peak_c(run)
            _under_the_ceiling(record["steam_block_peak_c"], ceiling,
                               "%s %s corner's" % (coefficient, corner))
        settle = settle_of(reference[side]["delivered"], run["delivered"], windows[side],
                           bands[side], floors[side])
        settle["moved"] = sweep.delivery_moved(reference[side]["delivered"], run["delivered"])
        settle["last_outside"] = last_outside_the_band(
            reference[side]["delivered"], run["delivered"], tails[side], bands[side])
        record["sides"][side] = settle
    return record


def _verdict_of(record):
    """One corner's verdict over both sides: the worse of the two.

    Worse rather than either side's own, because a corner is a machine and a
    machine whose coffee side settles and whose steam side does not has not
    settled. The per-side verdicts are reported beside it, since which side
    failed is most of what a reader needs.
    """
    order = (CORNER_REFUSED, STILL_DIVERGING, SETTLED_OUTSIDE_THE_BAND, SETTLED)
    reached = [settle["verdict"] for settle in record["sides"].values()]
    reached += [CORNER_REFUSED] * len(record["refused"])
    if not reached:
        return CORNER_REFUSED
    return min(reached, key=order.index)


def joint_corner(covered, executable, description, limits, declaration, ready_c, scale, courses,
                 reference, windows, tails, bands, floors, ceiling, workspace):
    """The one corner with both mains-coupled coefficients low together, or
    nothing where this description does not carry both of them.

    Its own function rather than a tail of the run loop, so that the claim it
    makes about itself can be put to it: the joint machine is written, drawn and
    judged on exactly the terms every single-coefficient corner is. Both
    coefficients are written into one description by chaining the same rewrite
    the independent corners use, each taking the previous as its source; both
    draws are made through the same admitting reader they are, so a joint machine
    the structure would not admit is recorded as a refused corner rather than
    stopping the analysis; and the record it leaves is the same record with the
    same keys, so nothing downstream has to know which kind of corner it is
    reading.

    That last point is why this is worth a function. A joint corner whose draws
    were made some other way would be a corner admitted on different terms from
    the ones beside it while a comment beside it said otherwise -- and an
    inadmissible joint machine would end the run rather than being reported,
    which is the one outcome a record of what the declared error implies must not
    have.
    """
    sag = joint_sag(covered)
    if sag is None:
        return None
    fraction, values = sag
    written = description
    for at, name in enumerate(MAINS_COUPLED):
        written = cross_tier.description_with(
            name, VALUE_FORMAT % values[name],
            os.path.join(workspace, "joint-mains-droop-%d.params" % at), source=written)
    runs, refused = _draw_each_side(executable, written, limits, declaration, ready_c, scale,
                                    courses, "joint")
    joint = _corner_record(JOINT_COEFFICIENT, JOINT_CORNER, values, runs, reference, windows,
                           tails, bands, floors, ceiling, written, refused=refused)
    joint["fraction"] = fraction
    joint["nominal"] = None
    joint["joint"] = True
    joint["verdict"] = _verdict_of(joint)
    return joint


def run(description=None, limits=None, declaration=sweep.STEAM_CONTROL_DECLARATION,
        tolerance=sweep.TOLERANCE_DECLARATION, pio=base.DEFAULT_PIO, executable=None,
        workspace=BUILD_DIR, brew_tail=BREW_TAIL_STEPS, steam_tail=STEAM_TAIL_STEPS,
        reading=None):
    """Run every corner the declared error implies and say what each response
    did.

    `description`, `limits`, `declaration` and `tolerance` default to the four
    files the target build carries, and are arguments so the same method can be
    pointed at a replacement model without anything here being edited -- which is
    the whole of what makes the verdicts repeatable rather than an account of one
    afternoon.

    `workspace` is where this run's perturbed descriptions are written, and it is
    an argument for the reason the sweep's is: two models write a description per
    coefficient per corner under the same names, and sharing a directory would
    leave the second run's standing where the first's had been.

    `brew_tail` and `steam_tail` are the two extensions, in control intervals.
    They are arguments so that what "long enough" means can be put to the method
    rather than only read out of it: a horizon that is too short reports a
    converging machine as unsettled, and the only way to establish that this one
    is not too short is to be able to run a shorter one and watch the verdict
    change.

    `reading` is what one count of the machine's converter is worth. It is one of
    the two things the floor a change in a separation has to clear is the smaller
    of -- the other is a stated fraction of each side's own band, which does not
    move with it -- and it defaults to what the seam declares. It is an argument
    for the reason the horizon is: whether a floor is deciding anything can only
    be established by moving it and watching a verdict change.
    """
    carried_description, carried_limits = cross_tier.carried_declarations()
    description = description or carried_description
    limits = limits or carried_limits

    carried_class = bounded_or_refuse()
    ceiling = steam_block_ceiling_c()

    covered, unweighed = sweep.swept_coefficients(description)
    bands = {sweep.BREW_SIDE: sweep.brew_band_c(tolerance),
             sweep.STEAM_SIDE: sweep.steam_band_bar(declaration)}
    ready_c = sweep.steam_ready_temperature_c(declaration)
    scale = cross_tier.converter_scale()
    seam_reading = reading_resolution() if reading is None else reading
    floors = growth_floors(bands, seam_reading)
    executable = executable or sweep.build_host(pio)

    courses = {sweep.BREW_SIDE: brew_course(brew_tail),
               sweep.STEAM_SIDE: steam_course(steam_tail)}
    ends = {sweep.BREW_SIDE: brew_hold_ends_at(brew_tail),
            sweep.STEAM_SIDE: steam_draw_ends_at(steam_tail)}
    tails = {sweep.BREW_SIDE: list(range(ends[sweep.BREW_SIDE] - brew_tail,
                                         ends[sweep.BREW_SIDE])),
             sweep.STEAM_SIDE: list(range(ends[sweep.STEAM_SIDE] - steam_tail,
                                          ends[sweep.STEAM_SIDE]))}
    windows = {sweep.BREW_SIDE: settling_window(ends[sweep.BREW_SIDE], brew_tail),
               sweep.STEAM_SIDE: settling_window(ends[sweep.STEAM_SIDE], steam_tail)}

    os.makedirs(workspace, exist_ok=True)

    reference = _draws(executable, description, limits, declaration, ready_c, scale, courses,
                       "nominal")
    _under_the_ceiling(steam_block_peak_c(reference[sweep.STEAM_SIDE]), ceiling, "unperturbed")
    settled_reference = reference_delivers_in_band(reference, windows, bands, declaration)

    corners = []
    for name, value, fraction in covered:
        for corner, perturbed_value in corners_of(name, value, fraction):
            written = cross_tier.description_with(
                name, VALUE_FORMAT % perturbed_value,
                os.path.join(workspace, "%s-%s.params" % (name, corner)), source=description)
            runs, refused = _draw_each_side(executable, written, limits, declaration, ready_c,
                                            scale, courses, "%s-%s" % (name, corner))
            record = _corner_record(name, corner, {name: perturbed_value}, runs, reference,
                                    windows, tails, bands, floors, ceiling, written,
                                    refused=refused)
            record["fraction"] = fraction
            record["nominal"] = value
            record["joint"] = False
            record["verdict"] = _verdict_of(record)
            corners.append(record)

    joint = joint_corner(covered, executable, description, limits, declaration, ready_c, scale,
                         courses, reference, windows, tails, bands, floors, ceiling, workspace)
    if joint is not None:
        corners.append(joint)

    found, missing = one_sided_account(covered)
    return {
        "description": description,
        "limits": limits,
        "declaration": declaration,
        "tolerance": tolerance,
        "digests": {path: sweep.digest_of(path)
                    for path in (description, limits, declaration, tolerance)},
        "executable": executable,
        "robustness_declaration": ROBUSTNESS_DECLARATION,
        "robustness_class": carried_class,
        "bands": bands,
        # What the seam declares one converter count is worth, and what each side
        # actually judges growth against. Both, because they are not the same
        # figure on the steam side and a record naming one of them would leave a
        # reader unable to tell which bound decided a verdict.
        "reading": seam_reading,
        "floors": floors,
        "courses": courses,
        "tails": {sweep.BREW_SIDE: brew_tail, sweep.STEAM_SIDE: steam_tail},
        "ends": ends,
        "windows": {side: (window[0], window[-1]) for side, window in windows.items()},
        "reference": reference,
        "reference_settled": settled_reference,
        "steam_block_ceiling_c": ceiling,
        # The hottest any steam run's block got, across the unperturbed machine
        # and every corner. Recorded rather than only checked, because what a
        # reader has to be able to see is how much of the margin between the
        # horizon and the bound this run actually used -- a peak sitting just
        # under the ceiling is a horizon that a slightly different model would
        # push past it.
        "steam_block_peak_c": max(
            [steam_block_peak_c(reference[sweep.STEAM_SIDE])]
            + [record["steam_block_peak_c"] for record in corners
               if "steam_block_peak_c" in record]),
        "corners": corners,
        "joint": joint,
        "one_sided_found": found,
        "one_sided_missing": missing,
        "unweighed": unweighed,
        "converter_scale": scale,
        "steam_ready_c": ready_c,
        "workspace": workspace,
    }


_FINDINGS = {}


def run_once(**arguments):
    """The findings of one analysis, shared by everything that asks.

    Two host draws per corner over courses several times the length of the
    sweep's own is the most expensive thing in this tier, and every caller wants
    the same ones. Keyed on the machine and the horizon rather than kept as a
    single record, so a suite putting a replacement model or a shorter horizon to
    the same method gets that run rather than the shipped one.
    """
    key = (arguments.get("description"), arguments.get("limits"),
           arguments.get("declaration", sweep.STEAM_CONTROL_DECLARATION),
           arguments.get("tolerance", sweep.TOLERANCE_DECLARATION),
           arguments.get("workspace", BUILD_DIR),
           arguments.get("brew_tail", BREW_TAIL_STEPS),
           arguments.get("steam_tail", STEAM_TAIL_STEPS),
           arguments.get("reading"))
    if key not in _FINDINGS:
        _FINDINGS[key] = run(**arguments)
    return _FINDINGS[key]


# --- The record --------------------------------------------------------------

#: The heading each part of the record sits under, named here because the checks
#: that the committed record still says what this method produces read it back by
#: them.
MODEL_HEADING = "## The model this was run against"
STANDARD_HEADING = "## What standard these corners are held to"
HORIZON_HEADING = "## How long each side was held delivering"
CORNERS_HEADING = "## Which corners were run"
VERDICT_HEADING = "## What each corner's response did"
JOINT_HEADING = "## The one dependence the description states"
UNSETTLED_HEADING = "## What did not settle"


def _relative(path):
    return os.path.relpath(os.path.abspath(path), REPOSITORY_DIR)


def _listed(items):
    """Several things named in a sentence, joined the way a sentence joins them."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return "%s and %s" % (", ".join(items[:-1]), items[-1])


def _seconds(intervals):
    return intervals * sweep.INTERVAL_MS / 1000.0


def unsettled(findings):
    """Every corner this analysis could not call settled, with which side and
    which way it failed.

    Taken over both sides of every corner rather than off the corner's own
    verdict, because a corner that settled on one side and not the other is one
    finding about each and a reader has to be told which side it was.
    """
    named = []
    for record in findings["corners"]:
        for side, settle in sorted(record["sides"].items()):
            if settle["verdict"] != SETTLED:
                named.append((record, side, settle))
        for side, why in sorted(record["refused"].items()):
            named.append((record, side, {"verdict": CORNER_REFUSED, "why": why}))
    return named


def horizon_margin(findings):
    """How much of each side's extension the slowest settling corner still had to
    run once it was inside the band, as {side: (fraction, coefficient, corner)}.

    The figure the horizon's adequacy is read off. A corner that only came inside
    the band on the last interval before the window opened is one this horizon
    barely reached a verdict about, and a model that moved a little further would
    have it reported as unsettled with nothing to say the horizon was the reason.
    Reported rather than asserted, so a horizon that has become too short shows up
    as a figure creeping towards the window's own edge before it shows up as a
    verdict changing.
    """
    worst = {}
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        found = (0.0, None, None)
        for record in findings["corners"]:
            settle = record["sides"].get(side)
            if settle is None or settle["verdict"] != SETTLED:
                continue
            if settle["last_outside"] > found[0]:
                found = (settle["last_outside"], record["coefficient"], record["corner"])
        worst[side] = found
    return worst


def _corner_value_text(record):
    """What a corner wrote into the description, as one cell.

    Written at the format the description was actually handed rather than at the
    three figures the rest of the record reports in. The column's whole claim is
    that it says what machine was run, and a value rounded to what a reader wants
    to see is a different machine from the one the declared error names -- which
    would leave the record naming corners nobody could reproduce against a
    replacement model.
    """
    return ", ".join("%s = %s" % (name, VALUE_FORMAT % value)
                     for name, value in sorted(record["values"].items()))


def _verdict_cell(record, side):
    if side in record["refused"]:
        return CORNER_REFUSED
    settle = record["sides"].get(side)
    return "—" if settle is None else settle["verdict"]


def _figure_cell(record, side, key):
    settle = record["sides"].get(side)
    return "—" if settle is None else FIGURE_FORMAT % settle[key]


def _floor_text(findings, side):
    """One side's growth floor, in that side's own unit and with the bound that
    fixed it named.

    Both, because a bare number is what this record carried first and it left a
    reader unable to say what it was a number of: the two sides are judged in
    kelvin and in bar, and the floor is the seam's converter count on one side
    and a fraction of the band on the other.
    """
    _, unit = sweep.JUDGED[side]
    floor = findings["floors"][side]
    bounded_by = ("one count of the machine's converter"
                  if floor >= findings["reading"]
                  else "%g of that side's own band" % GROWTH_FLOOR_BAND_FRACTION)
    return "%s %s, which is %s" % (FIGURE_FORMAT % floor, unit, bounded_by)


def report_text(findings):
    """The whole record: the standard, the horizon, the corners and the verdict
    at each.

    Written by the analysis rather than by hand and written whole, for the reason
    the two records beside it are: pointing the method at a replacement model has
    to need nothing changed about how it runs, and a record whose prose is
    re-edited every time the model moves is one that will be left describing the
    previous machine.
    """
    lines = []
    write = lines.append
    margin = horizon_margin(findings)
    did_not = unsettled(findings)

    write("# Whether the loop's response stays bounded across the declared error")
    write("")
    write("**Generated by `firmware/emulation/tools/run_parameter_stability.py`. Do not edit by "
          "hand — re-run it.**")
    write("")
    write("Every coefficient the machine's description says it may be wrong about is taken to the "
          "corners that error implies, and both closed loops are held in the state they deliver "
          "from for long enough to see what the loop does with each one. What is recorded is "
          "whether the response came to rest, and whether it came to rest inside the band the "
          "design holds that delivery to.")
    write("")
    write("That is a different question from the one `docs/parameter-dominance.md` answers off "
          "the "
          "same corner-perturbation machinery, and neither answers the other. That record "
          "measures "
          "how far the delivery moved, as a fraction of the declared margin. A magnitude cannot "
          "tell a loop that was pushed further and recovered from a loop that has lost authority "
          "and is walking away — both report a larger number — and the distinction is the whole "
          "of "
          "what is asked here.")
    write("")
    write("Nothing here is a measurement, and nothing here is a stability proof. It is a set of "
          "corners the declared error names, run on two courses against an estimated model whose "
          "own figures are estimates. A machine can settle at every corner of a box and misbehave "
          "inside it.")
    write("")
    write("Nothing in `docs/parameter-dominance.md` is changed or restated by this record. That "
          "record's ranking of the coefficients, the deviation each one costs as a fraction of "
          "the declared margin, and the corner set those figures were taken over all stand "
          "exactly as they were: this analysis re-runs its own corners over its own longer "
          "courses and writes its verdicts here, and takes nothing away from the figures beside "
          "it. The one thing it adds there is a pointer to this file.")
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
    write("A replacement model is run by naming it: `--description`, `--limits`, "
          "`--steam-declaration` and `--tolerance` each point the same method at another file, "
          "and "
          "`--workspace` gives that run its own scratch directory. Nothing about how the corners "
          "are taken or how a verdict is reached changes with them, which is what makes this "
          "repeatable against the measured model that is meant to replace this estimated one.")
    write("")

    write(STANDARD_HEADING)
    write("")
    write("`%s` classifies **%s** as **%s**. A behaviour in that class is permitted to move as "
          "the "
          "model does, but only inside the range the description declares — it is not asked to "
          "hold against an arbitrarily wrong model, which is what that declaration reserves for "
          "the behaviours whose failure is an unsafe machine. That is exactly what is established "
          "below: every corner run is one the "
          "description's own declared error names, nothing beyond that range is run, and nothing "
          "is claimed about a machine found to sit outside it."
          % (_relative(findings["robustness_declaration"]), THE_BEHAVIOUR,
             findings["robustness_class"]))
    write("")
    write("The class is read out of that declaration on every run rather than restated here. A "
          "behaviour promoted out of it would mean these corners are the wrong ones, and this "
          "analysis stops rather than going on writing a record against a standard nobody now "
          "holds.")
    write("")

    write(HORIZON_HEADING)
    write("")
    write("The sweep's own courses are a shot and a wand-open, and they are the right length for "
          "a "
          "magnitude and too short for a settling: at the end of that shot the coffee loop is "
          "still some kelvin from where it ends up. So each side's course is run again here with "
          "its **delivering** phase lengthened — the coffee side's hold, the steam side's open "
          "wand — and the verdict is taken over the trailing half of that extension. A tail spent "
          "idle would be a verdict about a quantity the band does not apply to, since nothing is "
          "being delivered while the pump is shut.")
    write("")
    write("| Side | Judged on | Declared half-width | Whole course | Extension | Verdict taken "
          "over |")
    write("|---|---|---|---|---|---|")
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        what, unit = sweep.JUDGED[side]
        first, last = findings["windows"][side]
        write("| %s | %s | %s %s | %d intervals (%.0f s) | %d intervals (%.0f s) | intervals "
              "%d–%d (%.0f s) |"
              % (side, what, FIGURE_FORMAT % findings["bands"][side], unit,
                 len(findings["courses"][side]), _seconds(len(findings["courses"][side])),
                 findings["tails"][side], _seconds(findings["tails"][side]),
                 first, last, _seconds(last - first + 1)))
    write("")
    write("Each extension is a stated multiple of the settling allowance that side's own course "
          "already stands on, rather than a figure chosen here: the coffee course's %.0f s flush "
          "is where that loop settles from cold at the declared coefficients, and the steam "
          "course's %.0f s settle is what the steam law's own suite gives a block to reach its "
          "ready state. The coffee side takes %d of them and the steam side %d, and the two "
          "differ "
          "for a reason about the machine rather than a preference."
          % (_seconds(sweep.BREW_FLUSH_STEPS), _seconds(sweep.STEAM_SETTLE_STEPS),
             BREW_TAIL_MULTIPLE, STEAM_TAIL_MULTIPLE))
    write("")
    write("On the coffee side the loop shows a slow standing mode under a sustained draw: the "
          "widest excursion these declared errors produce decays with a time constant of order a "
          "hundred seconds, which is twice the flush on its own. The extension has to be long "
          "against that rather than against the flush.")
    write("")
    write("The steam side cannot be extended the same way, and the bound is not a matter of what "
          "it would cost to run. While a wand is held open the loop answers a standing pressure "
          "deficit with block temperature, so the block climbs for as long as the draw lasts. "
          "Past "
          "the **%.0f C** the steam grammar records the machine's own protection as taking over "
          "at, this description says nothing that can be believed — its saturation slope is a "
          "local one at the boiling point and gives about a quarter of the true pressure up "
          "there, "
          "and the protective devices that would actually have opened are not modelled at all. "
          "Every steam run's peak block temperature is checked against that bound, and a run that "
          "crossed it stops this analysis rather than being reported: it would be this horizon "
          "reaching past what the description answers for, which is a fault in the horizon and "
          "not "
          "a finding about a coefficient." % findings["steam_block_ceiling_c"])
    write("")
    write("The hottest any steam run's block actually got over this horizon, across the "
          "unperturbed machine and every corner, was **%.1f C** — %.1f C under that bound. That "
          "margin is reported for the same reason the one below is: a peak creeping towards the "
          "ceiling is a horizon a slightly different model would push past, and that is worth "
          "seeing before a run stops."
          % (findings["steam_block_peak_c"],
             findings["steam_block_ceiling_c"] - findings["steam_block_peak_c"]))
    write("")
    write("**How long is long enough is reported rather than asserted.** The horizon is long "
          "enough exactly when every settling corner is inside the band well before the verdict "
          "window opens, which is at the halfway point of the extension. The latest any settling "
          "corner still stood outside its band was:")
    write("")
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        fraction, coefficient, corner = margin[side]
        write("- %s: %s of the extension%s — against a window that opens at 0.5."
              % (side, FIGURE_FORMAT % fraction,
                 ", set by `%s` at its %s corner" % (coefficient, corner)
                 if coefficient else ", because no corner ever left the band"))
    write("")
    write("The unperturbed machine is established to have settled too, and not assumed: over the "
          "window every verdict is taken in, the coffee side sat no more than %s C from the %.1f "
          "C "
          "it was commanded and the steam side no more than %s bar from the %.3f bar middle of "
          "the %.3f..%.3f bar span it is held inside. A separation taken against a reference "
          "still travelling would be a comparison of two transients."
          % (FIGURE_FORMAT % findings["reference_settled"]["brew_worst_from_target"],
             sweep.BREW_TARGET_C,
             FIGURE_FORMAT % findings["reference_settled"]["steam_worst_from_middle"],
             findings["reference_settled"]["steam_middle"],
             findings["reference_settled"]["steam_floor"],
             findings["reference_settled"]["steam_ceiling"]))
    write("")
    write("Being somewhere inside the band is not enough of the reference and is not what is "
          "asked of it. Every verdict below is a separation from this run, and the band it is "
          "compared against is a distance from what the design promises — so the two are the same "
          "statement only where the reference is close to what the design promises. A reference "
          "on one edge of its band with a corner on the other would show a separation of one band "
          "while both were marginal. So the reference is required to sit within **%g** of the "
          "band from the target on the coffee side and from the middle of the span on the steam "
          "side, and this analysis stops rather than issuing verdicts against a reference further "
          "off than that. The figures above are %s and %s of the band respectively."
          % (findings["reference_settled"]["centred_within"],
             FIGURE_FORMAT % (findings["reference_settled"]["brew_worst_from_target"]
                              / findings["bands"][sweep.BREW_SIDE]),
             FIGURE_FORMAT % (findings["reference_settled"]["steam_worst_from_middle"]
                              / findings["bands"][sweep.STEAM_SIDE])))
    write("")

    write(CORNERS_HEADING)
    write("")
    write("Both ends of every coefficient's declared error, with two departures from that, each "
          "of which is a property of the declared error rather than of this method.")
    write("")
    if findings["one_sided_found"]:
        write("**One-sided coefficients are run at their one declared corner.** %s reach "
              "downwards "
              "only: each is a figure standing in for something it is not — the two ends of the "
              "coffee pump's characteristic, which no pump is at both of at once, and the steam "
              "feed's open-path rate, which has nothing standing opposite it — and the "
              "description "
              "says in its own prose that a real machine sits below each rather than either side. "
              "Running the upper corner would be running a machine the description does not "
              "claim; "
              "excluding the coefficient altogether would leave its half of the declared range "
              "unchecked, which a record claiming to establish stability across that range cannot "
              "do. So one corner is taken, on the same standard as a two-sided coefficient's pair."
              % _listed("`%s`" % name for name in findings["one_sided_found"]))
        write("")
        write("The description carries no grammar for this: a line states a fraction and a "
              "fraction is symmetric. The record of which coefficients are one-sided is held in "
              "the tool that needs it rather than added to the sweep's own corner logic, because "
              "changing that logic would move the committed dominance figures, which this "
              "analysis "
              "is not entitled to do.")
        write("")
    if findings["one_sided_missing"]:
        write("Recorded as one-sided and not carried by this description: %s. Nothing was run for "
              "them and nothing here is about them; they are named so a coefficient that has been "
              "renamed shows up rather than leaving this record claiming a corner set it did not "
              "take." % _listed("`%s`" % name for name in findings["one_sided_missing"]))
        write("")
    write("**Two coefficients the description says are not independent of one another are also "
          "run together**, as one further corner alongside the independent ones. What that "
          "dependence is, and why it is one corner rather than four, is set out under **%s** "
          "below." % JOINT_HEADING.lstrip("# "))
    write("")
    if findings["unweighed"]:
        write("Coefficients carrying no declared error, or an error declared as nothing, are not "
              "corners at all and are not run: %s. There is nothing to move them by, which is the "
              "same account `docs/parameter-dominance.md` gives of them."
              % _listed("`%s` (%s)" % (name, condition)
                        for name, condition, _ in findings["unweighed"]))
        write("")

    write(VERDICT_HEADING)
    write("")
    write("Each corner against the unperturbed machine run over the same lengthened course, on "
          "both sides. What is compared is the separation between the two deliveries — against "
          "the "
          "unperturbed run rather than against the commanded target, because what is being asked "
          "is whether the loop's response *to the perturbation* stays bounded, and because a "
          "separation from the same machine's own delivery is the same kind of statement on a "
          "side "
          "declaring a half-width around a command and a side declaring a span the delivered "
          "pressure has to stay inside.")
    write("")
    write("The **early** and **late** columns are the worst separation in each half of the "
          "verdict "
          "window. A response whose late half stands above its early half is still growing, which "
          "is reported as diverging whatever its size; one that is not growing but stands outside "
          "the band has come to rest at a delivery the design does not accept, which is a "
          "different finding and is named differently.")
    write("")
    write("There are three verdicts a corner can leave with, and they are named here so a reader "
          "can see what this table could have said as well as what it does. **%s** is a response "
          "that came to rest inside the margin the design holds that delivery to. **%s** is one "
          "the loop brought to rest somewhere else — it has authority and is using it at a "
          "delivery the design does not accept, which asks for a wider band or a smaller draw. "
          "**%s** is one that had not come back at all, which is the finding this record exists "
          "to "
          "make and the one no deviation figure can report. A corner the structure would not "
          "admit "
          "as a machine is **%s**, which is a finding about the description's declared error "
          "rather than about a loop."
          % (SETTLED, SETTLED_OUTSIDE_THE_BAND, STILL_DIVERGING, CORNER_REFUSED))
    write("")
    write("The late half has to stand a stated amount above the early half before the difference "
          "counts as growth, and that amount is each side's own: **%s** on the coffee side and "
          "**%s** on the steam side. A floor is needed and not for the reason a reader arriving "
          "from `docs/parameter-identifiability.md` would expect: what sits below it is not the "
          "model's "
          "arithmetic rounding but the integer quantisation of the commands the loop issues. Two "
          "runs of the same machine a hair apart command the same duties for long stretches and "
          "then part by one permille, which puts a slow beat on the separation between them — and "
          "a beat crosses a window boundary in whichever direction it happened to be going. "
          "Without the floor those crossings read as divergences, which is an instability finding "
          "manufactured out of a rounding. One converter count is the coarsest distinction "
          "anything on this board draws and stands well above that beat."
          % (_floor_text(findings, sweep.BREW_SIDE), _floor_text(findings, sweep.STEAM_SIDE)))
    write("")
    write("The two figures differ because neither the seam nor the band alone can fix a floor. "
          "The seam declares one converter full scale for every channel alike, so one count is "
          "worth **%s** in whatever unit it is read beside — which is %s of the coffee side's "
          "band and %s of the steam side's. A floor worth a quarter of the band it is being "
          "judged against is not separating a rounding from a divergence; it is admitting a "
          "response that eats a "
          "quarter of the margin per half-window and calling it settled. So each side takes "
          "whichever is smaller of that count and **%g** of its own band. The coffee side is "
          "bounded by the seam's count and the steam side by its band, and which of the two "
          "decided is named beside each figure above."
          % (FIGURE_FORMAT % findings["reading"],
             FIGURE_FORMAT % (findings["reading"] / findings["bands"][sweep.BREW_SIDE]),
             FIGURE_FORMAT % (findings["reading"] / findings["bands"][sweep.STEAM_SIDE]),
             GROWTH_FLOOR_BAND_FRACTION))
    write("")
    write("This is deliberately not the reasoning `docs/parameter-identifiability.md` gives for "
          "its own floor, and the difference is which way an error falls. There a generous floor "
          "errs towards *not shown identifiable*, which declines to claim something. Here a "
          "generous floor errs towards *settled*, which is a claim, and the unsafe one — it says "
          "a response came back when it may not have. A floor that can only be too small is what "
          "this record wants; a floor that may be too large is what that one can afford.")
    write("")
    write("| Coefficient | Corner | Written as | Brew early | Brew late | Brew verdict | Steam "
          "early | Steam late | Steam verdict |")
    write("|---|---|---|---|---|---|---|---|---|")
    for record in findings["corners"]:
        write("| `%s` | %s | %s | %s | %s | %s | %s | %s | %s |"
              % (record["coefficient"], record["corner"], _corner_value_text(record),
                 _figure_cell(record, sweep.BREW_SIDE, "early"),
                 _figure_cell(record, sweep.BREW_SIDE, "late"),
                 _verdict_cell(record, sweep.BREW_SIDE),
                 _figure_cell(record, sweep.STEAM_SIDE, "early"),
                 _figure_cell(record, sweep.STEAM_SIDE, "late"),
                 _verdict_cell(record, sweep.STEAM_SIDE)))
    write("")
    still = [record for record in findings["corners"]
             for settle in record["sides"].values()
             if settle["verdict"] == SETTLED and not settle["moved"]]
    if still:
        write("A separation of nothing is a corner that moved that side's delivery nowhere at "
              "all, "
              "which settles trivially and is not evidence that a loop recovered from anything. "
              "The corners that never moved the side they were judged on are the ones whose "
              "figures are zero, and `docs/parameter-dominance.md` is where what a coefficient "
              "does reach is recorded.")
        write("")

    write(JOINT_HEADING)
    write("")
    if findings["joint"] is None:
        write("This description does not carry both of %s, so the one dependence its own "
              "construction implies cannot be run against it. A dependence is a statement about "
              "two "
              "named values and there is nothing here to move together."
              % _listed("`%s`" % name for name in MAINS_COUPLED))
        write("")
    else:
        joint = findings["joint"]
        write("Every corner above moves one coefficient with every other held where the "
              "description puts it. The description says in as many words that two of its values "
              "are not independent: %s are both fed from one supply, so a sagging mains makes "
              "both "
              "low at once. A sweep moving one coefficient at a time cannot exercise that by "
              "construction, whatever it does to each of them separately."
              % _listed("`%s`" % name for name in MAINS_COUPLED))
        write("")
        write("So one further corner is run with both low together, at an **equal fractional sag "
              "of %s** — the smaller of the two declared errors, which is the largest equal "
              "fractional movement both admit. A shared supply droop is a shared fractional "
              "movement, since power goes as the square of the voltage on both elements alike; a "
              "larger figure would put the tighter of the two outside the range the description "
              "claims, and running nothing beyond the declared range is the whole standard here. "
              "Taking each element to its own declared corner instead would be a different claim "
              "— "
              "two independent errors that happen to point the same way — and not the one the "
              "description makes. Nothing is lost by the smaller figure: the steam rating's own "
              "wider corner is already run on its own above, so what this corner adds is the "
              "simultaneity rather than a wider excursion."
              % (FIGURE_FORMAT % joint["fraction"]))
        write("")
        write("| What | Written as | Side | Early | Late | Verdict |")
        write("|---|---|---|---|---|---|")
        for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
            write("| `%s` | %s | %s | %s | %s | %s |"
                  % (JOINT_COEFFICIENT, _corner_value_text(joint), side,
                     _figure_cell(joint, side, "early"), _figure_cell(joint, side, "late"),
                     _verdict_cell(joint, side)))
        write("")
        same, differing, incomparable = joint_against_the_independent_corners(findings)
        if same:
            write("Where the two can be compared, this description makes the joint corner the "
                  "independent one over again: %s. That is not a fault in the run and it is a "
                  "finding about the description rather than about the machine — these relations "
                  "carry no coupling between the two sides at all, which the description names "
                  "among the things it leaves out, so nothing the steam element does can reach "
                  "the "
                  "coffee delivery or the other way about. What the corner establishes here is "
                  "that this analysis does not assume an independence the description never "
                  "claimed; what it would find on a description carrying a shared supply budget "
                  "is "
                  "a different figure, and that is the description to re-run it against."
                  % _listed("the %s side's separation is the one `%s` produces on its own at the "
                            "same sag" % (side, name) for side, name in same))
            write("")
        if differing:
            write("On %s the joint corner does not reproduce that side's own element corner at "
                  "the same sag, so moving the two together reaches that delivery differently "
                  "from moving the element that makes it by itself. That is what a description "
                  "carrying a path between the two sides would produce, and it is worth looking "
                  "at against a description these relations say carries none."
                  % _listed("the %s side, against `%s`" % (side, name)
                            for side, name in differing))
            write("")
        if incomparable:
            write("On %s there is no like-for-like comparison to be made, and that is a "
                  "consequence of the sag being the smaller of the two declared errors rather "
                  "than a finding about the machine. The only independent corner this comparison "
                  "could be made against is that side's own element moved alone by the same "
                  "fraction, and that side's element carries the wider declared error — so its "
                  "independent corner above is a further-moved machine and not the same machine "
                  "moved alone. Its own corner is run and reported above, and the joint corner's "
                  "own figures for that side are in the table above this paragraph. What is not "
                  "available is the comparison, and nothing is claimed either way about a "
                  "coupling from it: the other side is where that question is answered here."
                  % _listed("the %s side" % side for side in incomparable))
            write("")
        write("Whether that stated dependence is the real one is a characterisation question and "
              "is not asked here. A general sweep over every pairing a description might one day "
              "declare is deliberately not what this is: the one dependence run is the one the "
              "reference description's own construction already implies.")
        write("")

    write(UNSETTLED_HEADING)
    write("")
    if did_not:
        write("%d corner-and-side%s did not settle within the band, and each is named here rather "
              "than left to be found in the table above. A corner that fails to settle is a "
              "finding of its own and not a larger deviation figure — the deviation record beside "
              "this one cannot report it, because a magnitude is the same number whichever of the "
              "two happened."
              % (len(did_not), "" if len(did_not) == 1 else "s"))
        write("")
        for record, side, settle in did_not:
            if settle["verdict"] == CORNER_REFUSED:
                write("- `%s`, %s corner, %s side — %s. The structure would not admit it as a "
                      "machine, so there is no response here to have settled or not."
                      % (record["coefficient"], record["corner"], side, settle["why"]))
            elif settle["verdict"] == STILL_DIVERGING:
                write("- `%s`, %s corner, %s side — **still growing at the horizon.** The worst "
                      "separation in the late half of the verdict window is %s against %s in the "
                      "early half, so the response had not come back by the end of %.0f s of "
                      "delivering. This is the finding this record exists to make."
                      % (record["coefficient"], record["corner"], side,
                         FIGURE_FORMAT % settle["late"], FIGURE_FORMAT % settle["early"],
                         _seconds(findings["tails"][side])))
            else:
                what, unit = sweep.JUDGED[side]
                write("- `%s`, %s corner, %s side — **came to rest outside the band.** The "
                      "separation stopped growing but stands at %s %s against the %s %s the "
                      "design "
                      "holds this delivery inside. The loop has authority and is using it at a "
                      "delivery the design does not accept, which is a different finding from a "
                      "loop that has not come back."
                      % (record["coefficient"], record["corner"], side,
                         FIGURE_FORMAT % settle["worst"], unit,
                         FIGURE_FORMAT % settle["band"], unit))
        write("")
    else:
        write("**Every corner settled inside the band on both sides.** That is a positive finding "
              "rather than an absence of one: at each end of every declared error this "
              "description "
              "carries, and at the one joint corner its own construction implies, the closed "
              "loop's response came to rest and came to rest inside the margin the design holds "
              "that delivery to. It is a statement about this estimated model, and the measured "
              "model that is meant to replace it is what would make it a statement about a "
              "machine.")
        write("")

    write("## What this does not settle")
    write("")
    write("**Corners are not the interior.** What is run is the ends of each declared error, one "
          "coefficient at a time, plus the one joint corner the description's own construction "
          "implies. A machine can settle at every corner of a box and misbehave inside it: these "
          "relations are not all monotone, and nothing here rules that out.")
    write("")
    write("**A separation growing more slowly than that side's floor per half-window is called "
          "settled.** The floor that keeps the loop's own command quantisation from reading as a "
          "divergence is the same floor a genuinely slow divergence would hide under. Bounding it "
          "to %g of each side's own band caps what can hide there as a fraction of the margin — "
          "which is what the seam's single full scale, declared for every channel alike, does not "
          "do — but it does not remove it. Nothing here bounds how slowly a response could be "
          "walking away and still be called settled; what bounds it in practice is that a verdict "
          "window is minutes of delivering rather than seconds, and that the growth a floor can "
          "swallow over one is a fraction of the band rather than a multiple of it."
          % GROWTH_FLOOR_BAND_FRACTION)
    write("")
    write("**It is not a margin calculation.** How far a commanded target would have to move to "
          "keep a delivery inside its band across this range is a different question and is not "
          "answered here.")
    write("")
    write("**It is two courses.** A corner can settle on a held temperature and a wand-open draw "
          "and misbehave on a profile-commanded shot nobody has run. What the verdicts state is "
          "what these two courses establish.")
    write("")
    write("**The one dependence run is the one the description states.** Whether the two element "
          "ratings really move together as an equal fractional sag is a characterisation "
          "question. "
          "Every other pairing of coefficients is left independent because the description says "
          "nothing about them, not because anything here has established that they are.")
    write("")
    write("**It is an estimated model.** Every coefficient is an estimate and so is the error "
          "declared against it, so a verdict is a statement about what this description implies "
          "rather than about what the machine does. The record names the files and their digests "
          "so the same method can be pointed at the measured model meant to replace them.")
    write("")

    return "\n".join(lines) + "\n"


def joint_against_the_independent_corners(findings):
    """How the joint corner's separation on each side compares with the one that
    side's own element corner produces alone, where the two are comparable at
    all.

    Computed rather than stated, though what it will presently return follows
    from the description: these relations carry no coupling between the two
    sides, so nothing the steam element does can reach the coffee delivery. A
    sentence written into the record instead would go on claiming the two
    coincide after a description carrying a shared supply budget had made them
    come apart.

    Comparable means two things at once, and dropping either turns this into a
    comparison of two different perturbations reported as a finding.

    The first is that the independent corner has to be the one that side's own
    element makes. The coffee delivery is made by the coffee element and the
    steam delivery by the steam one; asking what the joint corner did to the
    steam pressure and holding the answer against what the *coffee* element's own
    corner did to it compares a perturbation with something that never touched
    that delivery, and would report "differing" for every description in which
    the two sides are unconnected -- which is exactly what this description says
    they are. That is the wrong way round: the absence of a coupling is what
    would make the two coincide, not what would make them differ.

    The second is that the independent corner has to have been run at the joint
    corner's own sag rather than merely at that coefficient's own declared
    corner. Those are two different machines wherever the coefficient's declared
    error is wider than the sag -- which on this description is true of the steam
    rating and not of the coffee one, since the sag is the smaller of the two
    declared errors and that is the coffee element's. So the coffee side has a
    like-for-like comparison here and the steam side has none, and the steam side
    is reported as having none rather than being compared against a machine moved
    further or against the other side's element.

    Three lists come back: the sides on which the joint corner reproduced that
    side's own independent corner exactly, the sides on which it did not, and the
    sides where nothing comparable was run at all.
    """
    joint = findings["joint"]
    if joint is None:
        return [], [], []
    same, differing, incomparable = [], [], []
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        at_joint = joint["sides"].get(side)
        if at_joint is None:
            continue
        own = MAINS_COUPLED_BY_SIDE.get(side)
        comparable = [record for record in findings["corners"]
                      if not record["joint"] and record["coefficient"] == own
                      and record["corner"] == "low"
                      and record["fraction"] == joint["fraction"]
                      and side in record["sides"]]
        if not comparable:
            incomparable.append(side)
            continue
        for record in comparable:
            alone = record["sides"][side]
            where = (side, record["coefficient"])
            if alone["early"] == at_joint["early"] and alone["late"] == at_joint["late"]:
                same.append(where)
            else:
                differing.append(where)
    return same, differing, incomparable


def _table_rows(text, heading):
    """The `| `name` | ... |` rows under one heading, as lists of cells.

    Read back through one reader rather than by whatever pattern each caller
    invents, for the reason the two records beside this one give: a check that a
    committed record is still the one this method produces is only worth
    something if the reading and the writing agree about which table is which and
    where in it a figure sits.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if line.startswith(heading):
            inside = True
            continue
        if inside and line.startswith("#"):
            break
        if not inside or not line.startswith("| `"):
            continue
        rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def verdict_rows(text):
    """Every corner's verdict read back out of a written record, with the figures
    each was reached from.

    The figures and not only the verdicts, because a verdict with nothing behind
    it cannot be argued with and a check comparing verdicts alone would let every
    number in the table drift until one of them crossed a threshold. That is the
    failure that has already happened once to the dominance record beside this
    one.
    """
    rows = []
    for cells in _table_rows(text, VERDICT_HEADING):
        if len(cells) != 9:
            continue
        rows.append({
            "coefficient": cells[0].strip("`"),
            "corner": cells[1],
            "written_as": cells[2],
            "brew_early": cells[3],
            "brew_late": cells[4],
            "brew_verdict": cells[5],
            "steam_early": cells[6],
            "steam_late": cells[7],
            "steam_verdict": cells[8],
        })
    return rows


def horizon_rows(text):
    """The horizon read back out of a written record, as one row per side: the
    band, the whole course, the extension, and the intervals a verdict was taken
    over.

    Read back because the horizon is half of what the criterion asks be
    committed. A record carrying verdicts and not the horizon they were taken
    over is one nobody can reproduce: the same corners run to a shorter horizon
    give different verdicts and the record would not say so.
    """
    rows = []
    inside = False
    for line in text.splitlines():
        if line.startswith(HORIZON_HEADING):
            inside = True
            continue
        if inside and line.startswith("#"):
            break
        if not inside or not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 6 or cells[0] in ("Side", "---"):
            continue
        rows.append(dict(zip(("side", "judged_on", "band", "course", "extension", "window"),
                             cells)))
    return rows


def joint_rows(text):
    """The joint corner read back out of a written record, as (what, written as,
    side, verdict).

    Its own reader because it is its own finding: a record that had stopped
    running the one dependence the description states would read, from the
    verdict table alone, exactly like one where that dependence did not exist.
    """
    return [(cells[0].strip("`"), cells[1], cells[2], cells[5])
            for cells in _table_rows(text, JOINT_HEADING) if len(cells) == 6]


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--description",
                        help="the parameter description to run, defaulting to the one the target "
                             "build carries compiled in")
    parser.add_argument("--limits",
                        help="what a reading off that machine may be, defaulting to the one the "
                             "target build carries compiled in")
    parser.add_argument("--steam-declaration", default=sweep.STEAM_CONTROL_DECLARATION,
                        help="the figures the steam control law is given")
    parser.add_argument("--tolerance", default=sweep.TOLERANCE_DECLARATION,
                        help="the bands a delivery is held to")
    parser.add_argument("--report", default=REPORT_PATH,
                        help="where the record of the verdicts is written")
    parser.add_argument("--stdout", action="store_true",
                        help="print the record rather than writing it")
    parser.add_argument("--pio", default=base.DEFAULT_PIO,
                        help="the PlatformIO executable that builds the host environment")
    parser.add_argument("--workspace", default=BUILD_DIR,
                        help="where this run's perturbed descriptions are written. Give a second "
                             "model a directory of its own, for the reason the sweep this reuses "
                             "states: every run writes one description per coefficient per corner "
                             "under the same names")
    parser.add_argument("--brew-tail", type=int, default=BREW_TAIL_STEPS,
                        help="how many control intervals the coffee side's hold is lengthened by")
    parser.add_argument("--steam-tail", type=int, default=STEAM_TAIL_STEPS,
                        help="how many control intervals the steam side's draw is lengthened by")
    parser.add_argument("--reading", type=float, default=None,
                        help="what one count of the machine's converter is worth, in a delivered "
                             "quantity's own unit. It is one of the two things each side's growth "
                             "floor is the smaller of, and it is exposed here for the reason the "
                             "two horizons are: whether a floor is deciding anything can only be "
                             "established by moving it and watching a verdict change. Defaults to "
                             "what the hardware seam declares")
    arguments = parser.parse_args(argv)

    findings = run(description=arguments.description, limits=arguments.limits,
                   declaration=arguments.steam_declaration, tolerance=arguments.tolerance,
                   pio=arguments.pio, workspace=arguments.workspace,
                   brew_tail=arguments.brew_tail, steam_tail=arguments.steam_tail,
                   reading=arguments.reading)
    text = report_text(findings)

    if arguments.stdout:
        sys.stdout.write(text)
        return 0

    os.makedirs(os.path.dirname(arguments.report), exist_ok=True)
    with open(arguments.report, "w", encoding="utf-8") as handle:
        handle.write(text)
    did_not = unsettled(findings)
    print("ran %d corner(s) of %s to a %.0f s coffee horizon and a %.0f s steam horizon, %d of "
          "them not settled, and wrote the record to %s"
          % (len(findings["corners"]), _relative(findings["description"]),
             _seconds(findings["tails"][sweep.BREW_SIDE]),
             _seconds(findings["tails"][sweep.STEAM_SIDE]),
             len(did_not), _relative(arguments.report)))
    for record, side, settle in did_not:
        print("  %-52s %-14s %-6s %s"
              % (record["coefficient"], record["corner"], side, settle["verdict"]))
    for side in (sweep.BREW_SIDE, sweep.STEAM_SIDE):
        fraction, coefficient, corner = horizon_margin(findings)[side]
        print("  horizon margin, %-6s last outside the band at %s of the extension%s"
              % (side, FIGURE_FORMAT % fraction,
                 " (%s, %s)" % (coefficient, corner) if coefficient else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
