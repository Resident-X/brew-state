#!/usr/bin/env python3
"""Drive one commanded draw through both closed loops and compare what the
plant model did.

The two loops already share the model's source. What they do not share is a
build of it: the host tier compiles it into an executable alongside the control
logic and the simulated hardware seam, and this tier compiles it into a shared
library the register models call through a bridge. Nor do they share a route to
it -- one is a direct call, the other a round trip through modelled peripherals.
A shared source file rules out a re-expression of the equations; it says nothing
about whether two independently compiled copies of them, reached by different
routes, produce the same numbers.

So this runs the same draw twice and puts the two answers side by side. It
decides nothing beyond whether each pair of figures is within the stated
tolerance: what the tolerance means and whether the run is evidence of anything
is the suite's business, on the same terms every other runner in this directory
is written.

The draw itself is not restated here. What the emulation run commanded -- the
temperature, the course of pump levels, how many intervals it ran for and what
its clock actually did -- is read off that run and handed to the host tier, so
the second loop runs the first one's draw rather than a draw somebody wrote down
twice.
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EMULATION_DIR = os.path.abspath(os.path.join(HERE, ".."))
FIRMWARE_DIR = os.path.abspath(os.path.join(EMULATION_DIR, ".."))

sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(FIRMWARE_DIR, "tools"))

import build_environments  # noqa: E402
import run_closed_loop_check as closed_loop  # noqa: E402
import run_emulation_check as base  # noqa: E402
import seam_channels  # noqa: E402

#: The host environment whose executable closes the loop against the plant model
#: through the simulated implementation of the hardware seam. Held here rather
#: than passed in, for the reason the target environment is held in the module
#: this one is built on: a check that can be pointed at another artefact is not
#: a check about this one.
HOST_ENVIRONMENT = "native"

#: Where the draw's own working files are written. Under the host build's own
#: directory because they are inputs to that artefact's run and to nothing else.
BUILD_DIR = os.path.join(FIRMWARE_DIR, ".pio", "build", HOST_ENVIRONMENT, "cross_tier")

#: The hardware-seam implementation whose converter scaling both loops have to
#: report through. The host tier has no converter, so it is handed this one's
#: full scale; taking it from the seam's own source rather than from a figure
#: written here is what keeps the two loops reading the same instrument.
HW_SEAM_SOURCE = os.path.join(FIRMWARE_DIR, "src", "hw", "stm32", "hw_stm32.c")

#: The cadence the control logic declares it runs at, which is what the first
#: accepted step of either loop is advanced by whatever the clock read before it.
DECLARED_INTERVAL_MS = 10

#: What each compared quantity is called when a divergence has to be reported to
#: somebody, in the order both loops report them -- which is the order the names
#: they are printed under are declared in, so the two cannot come apart.
QUANTITY_NAMES = (
    "brew temperature (C)",
    "steam temperature (C)",
    "brew pressure (bar)",
    "steam pressure (bar)",
)

assert len(QUANTITY_NAMES) == len(closed_loop.QUANTITY_KEYS), (
    "every quantity the two loops report under a name has to have a name to "
    "report a divergence in it by")

#: How far apart the two loops' figures for one quantity may sit.
#:
#: Derived from what single precision accumulates, not from what a drink can
#: tolerate. Every quantity the model carries is IEEE-754 binary32, and one
#: figure has to cover all four compared, so it is sized against whichever of
#: them carries the coarsest last place. Over this draw the brew temperature
#: reaches about 29 C, where a unit in the last place is about 1.9e-6 C; the brew
#: pressure reaches about 7.4 bar, where one is about 4.8e-7 bar; the steam pair
#: stand at 20 C and nothing. So the temperature sets the figure and the pressure
#: sits comfortably inside it -- moving the pressure did not loosen what this has
#: to admit.
#:
#: The two loops reach the model through separately compiled copies of the same
#: source -- the host build's toolchain under the analysis settings, and a plain
#: shared-library build -- so an expression contracted differently or a library
#: rounding differently can put an independent unit in the last place into any
#: operation. Over the draw's three hundred intervals, an error accumulating
#: linearly rather than cancelling reaches about 5.7e-4 C, and this sits just
#: above that.
#:
#: Closing the loop does not widen it. The loop is negative feedback through a
#: proportional term of thirty permille per kelvin onto a mass of a few hundred
#: joules per kelvin: a last-place difference in what one loop reconstructs
#: reaches the next interval's temperature some seven orders of magnitude smaller
#: than it started, so what the comparison accumulates is the model's own
#: arithmetic and not a loop winding it up. What the loop can do that an open
#: run could not is put the two figures either side of a converter count, since
#: the count is a truncation and a truncation has no small answer -- but that is
#: a separation of a whole count, tens of times this figure, and it is meant to
#: be reported rather than admitted.
#:
#: It is deliberately not the band a delivery is held to. That band answers how
#: far a drink may sit from what was asked for -- three orders of magnitude
#: looser than this -- and a comparison of two computations of the same
#: equations hidden behind it would pass with the two models disagreeing about
#: the machine by an amount anyone could taste.
#:
#: The same figure the plant model's own suite already justifies for comparing
#: an accumulated result against a single computation of it, which is the same
#: kind of question asked of the same equations.
TOLERANCE = 1.0e-3

class CrossTierError(RuntimeError):
    """The draw did not get far enough on one side to have anything to compare."""


def converter_scale():
    """The full scale of the converter the emulated loop reads its sensors
    through, as a count and as what that count is worth in milli-units."""
    return (seam_channels.defined_value(HW_SEAM_SOURCE, "ADC_FULL_SCALE_COUNTS"),
            seam_channels.defined_value(HW_SEAM_SOURCE, "SENSOR_FULL_SCALE_MILLI"))


def carried_declarations():
    """The description and the limits declaration the target artefact carries.

    Read off the build rather than named here, so the host tier's draw is run
    against the same two files the emulated artefact was built around. Naming
    them in this file would be a second statement of which files the machine is
    described by, and it would go on producing a plausible answer after the
    build named others.
    """
    declared = build_environments.load(FIRMWARE_DIR)
    for environment in declared:
        if environment.name != base.TARGET_ENVIRONMENT:
            continue
        description = environment.embedded_description
        limits = environment.embedded_limits
        if not description or not limits:
            raise CrossTierError(
                "'%s' does not declare both a description and a limits declaration to carry"
                % base.TARGET_ENVIRONMENT)
        return (os.path.join(FIRMWARE_DIR, description), os.path.join(FIRMWARE_DIR, limits))
    raise CrossTierError("the build declares no '%s' environment" % base.TARGET_ENVIRONMENT)


def course_of(emulation):
    """The draw the emulated loop ran, as (interval, pump level) per interval.

    Both halves are read off that run rather than restated here. The cadence is
    read off it because the control logic advances its estimator by the interval
    that actually elapsed rather than the one the loop is meant to run at, and a
    loop closed through an emulated machine does not keep a perfectly even one --
    so reproducing that draw means reproducing what its clock did. The pump
    levels are read off it because the course is the emulated run's own
    declaration and a second reader of it here would be a second answer waiting
    to disagree.

    The first interval is the declared one: the first accepted step has no
    predecessor to have elapsed from, so what the clock read before it is not
    something either loop acts on.
    """
    trajectory = emulation["trajectory"]
    if not trajectory:
        raise CrossTierError("the emulation run reported no trajectory to take a course from")

    course = [(DECLARED_INTERVAL_MS, trajectory[0]["pump_permille"])]
    for index in range(1, len(trajectory)):
        elapsed = trajectory[index]["clock_millis"] - trajectory[index - 1]["clock_millis"]
        if elapsed <= 0:
            raise CrossTierError(
                "the emulated loop's clock did not advance across interval %d" % index)
        course.append((elapsed, trajectory[index]["pump_permille"]))
    return course


def build_host(pio=base.DEFAULT_PIO):
    """Build the host environment and return the executable it wrote."""
    completed = base.subprocess.run(
        [pio, "run", "-e", HOST_ENVIRONMENT],
        cwd=FIRMWARE_DIR, capture_output=True, text=True)
    if completed.returncode != 0:
        raise CrossTierError(
            "the host build failed, so there is no loop to draw through:\n%s\n%s"
            % (completed.stdout[-4000:], completed.stderr[-4000:]))
    executable = os.path.join(FIRMWARE_DIR, ".pio", "build", HOST_ENVIRONMENT, "program")
    if not os.path.exists(executable):
        raise CrossTierError("the host build reported success but wrote no %s" % executable)
    return executable


def write_course(course, path):
    """The draw, as the file the host loop is handed it in: one line per control
    interval, carrying the milliseconds the clock advances before it and the
    level the pump is asked for during it.

    One file rather than two, so that a cadence of one length cannot be run
    against a course of another -- which is not a run with a mistake in it but
    two different draws.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join("%d %d\n" % (interval, level) for interval, level in course))
    return path


def parse_host(output):
    """Turn the host draw's `HOST ` lines into the record the suite reads."""
    findings = {
        "trajectory_baseline": [],
        "trajectory": [],
        "pre_draw_steps": None,
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
        if kind == "trajectory-baseline":
            findings["trajectory_baseline"] = closed_loop.quantities_of(
                closed_loop.keyed(parts[1:]), "the host loop's baseline")
        elif kind == "trajectory":
            fields = closed_loop.keyed(parts[1:])
            where = "the host loop's trajectory line %d" % len(findings["trajectory"])
            for name in ("interval", "result", "pump", "heater", "steps"):
                if name not in fields:
                    raise closed_loop.Unkeyed("%s reports no %s" % (where, name))
            findings["trajectory"].append({
                "interval": int(fields["interval"]),
                "result": int(fields["result"]),
                "pump_permille": int(fields["pump"]),
                "heater_permille": int(fields["heater"]),
                "plant_steps": int(fields["steps"]),
                "quantities": closed_loop.quantities_of(fields, where),
            })
        elif kind == "pre-draw-steps":
            findings["pre_draw_steps"] = int(parts[1])
        elif kind == "plant-step-count":
            findings["plant_step_count"] = int(parts[1])
        elif kind == "draw-intervals":
            findings["draw_intervals"] = int(parts[1])
        elif kind == "done":
            findings["completed"] = True
    return findings


def host_draw(executable, description, limits, target_c, course, scale, name="draw"):
    """Run one draw through the host tier's loop and report what it did.

    `description` is an argument rather than read from the build because the
    negative case this harness has to support is a draw run against a
    description the other loop is not using, and a run that could not be given
    one would leave the comparison unable to be shown failing at all.
    """
    course_file = write_course(course, os.path.join(BUILD_DIR, "%s-course.txt" % name))
    counts, milli = scale
    completed = base.subprocess.run(
        [executable, description, limits, "--cross-tier-draw",
         repr(float(target_c)), str(counts), str(milli), course_file],
        cwd=FIRMWARE_DIR, stdin=base.subprocess.DEVNULL, capture_output=True, text=True)

    findings = parse_host(completed.stdout)
    findings["executable"] = executable
    findings["description"] = description
    findings["limits"] = limits
    findings["course_file"] = course_file
    findings["returncode"] = completed.returncode
    findings["stdout"] = completed.stdout
    findings["stderr"] = completed.stderr
    if not findings["completed"]:
        raise CrossTierError(
            "the host draw did not finish. Its output follows:\n%s\n%s"
            % (completed.stdout[-8000:], completed.stderr[-4000:]))
    return findings


def description_with(coefficient, value, destination):
    """The carried description with one coefficient written differently.

    Written back out and handed to the ordinary loader rather than the record
    being reached into, so a description a run is deliberately given is admitted
    on exactly the terms the shipped one is -- including the range the structure
    declares the coefficient admissible within, which is what decides whether
    what was written is still a machine.

    Everything after the value is the value's account of itself and its assumed
    error, and it is carried across untouched: what a figure was arrived at from
    does not stop being true because a run asked what would happen if the figure
    were otherwise.

    This exists so the comparison can be shown failing. A check that has never
    been seen to fail and one that cannot fail read the same from the outside,
    and the second is not a check.
    """
    description, _ = carried_declarations()
    with open(description, encoding="utf-8") as handle:
        lines = handle.read().splitlines()

    rewritten = []
    replaced = False
    for line in lines:
        head, separator, tail = line.partition("=")
        if separator and head.strip() == coefficient:
            # The account begins at whichever of the two markers comes first, and
            # a line legitimately carries neither.
            markers = [at for at in (tail.find("~"), tail.find("@")) if at >= 0]
            annotation = tail[min(markers):] if markers else ""
            rewritten.append(("%s = %s %s" % (coefficient, value, annotation)).rstrip())
            replaced = True
        else:
            rewritten.append(line)

    if not replaced:
        raise CrossTierError(
            "%s declares no coefficient '%s' to write differently" % (description, coefficient))

    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "w", encoding="utf-8") as handle:
        handle.write("\n".join(rewritten) + "\n")
    return destination


def compare(emulation, host, tolerance=TOLERANCE):
    """Every way the two loops' plant trajectories fail to be the same one.

    Reported as a list of sentences rather than as a verdict, and each names the
    quantity, the interval and how far apart the two figures are -- because a
    comparison that answers only "no" leaves whoever has to fix it running the
    whole thing again by hand to find out where.

    The worst separation seen on each quantity is reported alongside, whether or
    not anything failed: a run that passed with nothing to spare and one that
    passed exactly are different situations, and a check reporting only its
    verdict cannot tell them apart.
    """
    findings = {
        "tolerance": tolerance,
        "divergences": [],
        "worst": [0.0] * len(QUANTITY_NAMES),
        "worst_at": [None] * len(QUANTITY_NAMES),
        "intervals": 0,
    }

    def separation(where, emulated, hosted):
        for index, name in enumerate(QUANTITY_NAMES):
            apart = abs(emulated[index] - hosted[index])
            # The first place is recorded whatever it separated by, and after
            # that only somewhere wider. A run where the two loops agreed
            # exactly everywhere has a worst separation of nothing, and there is
            # a first place where it was nothing -- so a comparison that
            # recorded a place only on a strict increase would report the best
            # possible result as having happened nowhere, which is the one
            # result whose report nobody can act on.
            if findings["worst_at"][index] is None or apart > findings["worst"][index]:
                findings["worst"][index] = apart
                findings["worst_at"][index] = where
            if apart > tolerance:
                findings["divergences"].append(
                    "%s: %s -- the emulation tier says %.9g and the host tier says %.9g, "
                    "%.3e apart, over a tolerance of %.3e"
                    % (where, name, emulated[index], hosted[index], apart, tolerance))

    emulated_baseline = emulation["trajectory_baseline"]
    hosted_baseline = host["trajectory_baseline"]
    if len(emulated_baseline) != len(QUANTITY_NAMES) or len(hosted_baseline) != len(QUANTITY_NAMES):
        findings["divergences"].append(
            "the two loops did not both report a full set of quantities before the draw began")
        return findings
    separation("before the draw", emulated_baseline, hosted_baseline)

    emulated = emulation["trajectory"]
    hosted = host["trajectory"]
    if len(emulated) != len(hosted):
        findings["divergences"].append(
            "the emulation tier ran %d control intervals and the host tier ran %d, so there is "
            "no interval-by-interval comparison to draw" % (len(emulated), len(hosted)))
        return findings

    findings["intervals"] = len(emulated)
    for index in range(len(emulated)):
        left, right = emulated[index], hosted[index]
        if left["result"] != right["result"]:
            findings["divergences"].append(
                "interval %d: the emulation tier's control step reported %d and the host "
                "tier's reported %d, so the two loops did not take the same path"
                % (index, left["result"], right["result"]))
        if left["plant_steps"] != right["plant_steps"]:
            findings["divergences"].append(
                "interval %d: the emulation tier had advanced the model %d times and the host "
                "tier %d times, so the two are not the same number of intervals into the draw"
                % (index, left["plant_steps"], right["plant_steps"]))
        separation("interval %d" % index, left["quantities"], right["quantities"])

    return findings


def run(pio=base.DEFAULT_PIO, tolerance=TOLERANCE):
    """Run both loops through one draw and report what each did and how far apart."""
    emulation = closed_loop.run_once(pio=pio)
    if emulation["target_brew_c"] is None:
        raise CrossTierError("the emulation run did not report what it commanded")

    scale = converter_scale()
    description, limits = carried_declarations()
    course = course_of(emulation)
    executable = build_host(pio)

    host = host_draw(executable, description, limits, emulation["target_brew_c"], course, scale)

    return {
        "emulation": emulation,
        "host": host,
        "comparison": compare(emulation, host, tolerance),
        "course": course,
        "converter_scale": scale,
        "description": description,
        "limits": limits,
        "executable": executable,
        "tolerance": tolerance,
    }


_FINDINGS = None


def run_once(**arguments):
    """The findings of one side-by-side run, shared by everything that asks."""
    global _FINDINGS
    if _FINDINGS is None:
        _FINDINGS = run(**arguments)
    return _FINDINGS


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pio", default=base.DEFAULT_PIO,
                        help="the PlatformIO executable that builds the two environments")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE,
                        help="how far apart the two loops' figures for one quantity may sit")
    arguments = parser.parse_args(argv)

    findings = run(pio=arguments.pio, tolerance=arguments.tolerance)
    comparison = findings["comparison"]
    print("compared %d control intervals against a tolerance of %.3e"
          % (comparison["intervals"], comparison["tolerance"]))
    for index, name in enumerate(QUANTITY_NAMES):
        print("  %-24s worst separation %.3e at %s"
              % (name, comparison["worst"][index], comparison["worst_at"][index]))
    for divergence in comparison["divergences"]:
        print("DIVERGENCE %s" % divergence)
    return 1 if comparison["divergences"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
