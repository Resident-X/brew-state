#!/usr/bin/env python3
"""What the build declares, read once so no gate has to be told it.

A gate handed the name of the thing it covers checks what somebody remembered
to name. This module is how a gate finds its subjects instead: it reads
`platformio.ini`, resolves what the build system would resolve, and answers
which environments produce a host artefact, which of them link this project's
own entry point, which run tests, and which structure each one selects.

`extends` and `${section.option}` are resolved here rather than by asking
PlatformIO, for two reasons. Asking it requires PlatformIO to be installed,
which would mean the gates could not be exercised against a synthetic tree on
a host that has none -- and a check that cannot be shown to fail is not a
check. And the properties the gates turn on are declared, not derived: an
environment says it must not build, or that it cannot carry the strict warning
settings, in its own entry, where the reason sits beside the declaration rather
than in a gate's argument list somewhere else.

Reading the build file separately from the build system is a divergence risk,
so anything this cannot resolve is refused rather than read as an absence. A
reference to a section that is not there, an inheritance cycle, and a host
environment that leaves its source filter to PlatformIO's default are all
errors here. The last is the one worth naming: an unread filter would make an
environment look as though it compiled nothing, and quietly drop out of every
set a gate covers -- the exact silence this exists to remove.

Nothing here decides whether a build is correct. It reports what the build
says it is, and the gates draw the conclusions.
"""

from __future__ import annotations

import configparser
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import filter_terms  # noqa: E402
from check_structure_selection import selected  # noqa: E402

#: The build file every environment is declared in.
PROJECT_CONFIG = "platformio.ini"

#: The prefix PlatformIO gives an environment's section.
ENVIRONMENT_PREFIX = "env:"

#: Where PlatformIO puts what it builds, one directory per environment.
BUILD_ROOT = os.path.join(".pio", "build")

#: What a linked host executable is called. PlatformIO names it this on every
#: host it builds for; the `.exe` form appears on Windows.
ARTEFACT_NAMES = ("program", "program.exe")

#: What a linked artefact for a board is called. It is a different name because
#: it is a different kind of thing: nothing runs it here, and what inspects it
#: is asking what the machine would carry rather than what a run produced.
MACHINE_ARTEFACT_NAMES = ("firmware.elf",)

#: The platform an environment names when it builds for the host rather than
#: for a target board.
HOST_PLATFORM = "native"

#: The source directory holding this project's own host entry point. An
#: environment compiling it links an executable that takes a parameter
#: description as its argument; one that does not, does not.
HOST_ENTRY_PREFIX = "app/native/"

#: The option PlatformIO uses to say the project's sources are compiled into
#: the test runner alongside the tests.
TEST_OPTION = "test_build_src"

#: An environment that must be refused rather than built declares it here, and
#: the value is the reason. A gate demanding a clean analysed build of one of
#: these would be demanding the opposite of what the build is for.
MUST_NOT_BUILD_OPTION = "custom_must_not_build"

#: An environment that must be refused rather than built may declare here what
#: its own refusal names in the build output. A refusal driven by the wrong
#: check reads the same as one driven by the right one on exit code alone, so
#: the gate that drives these environments tells them apart by this marker
#: rather than by whether the build merely failed.
MUST_NOT_BUILD_MARKER_OPTION = "custom_must_not_build_marker"

#: The marker every misconfigured environment named this before an environment
#: first needed one of its own. Environments declaring no marker of their own
#: are read as expecting this one, so the structure-selection environments
#: already in the build file did not have to be revisited to name it themselves.
DEFAULT_MUST_NOT_BUILD_MARKER = "check_structure_selection"

#: An environment that cannot scope compiler flags to this project's sources
#: alone declares it here, and the value is the reason. It is only honoured on
#: an environment that genuinely compiles foreign sources through the same
#: path -- see `strict_flags_exemption`.
STRICT_EXEMPTION_OPTION = "custom_strict_flags_exemption"

#: An environment built only to be swept for mutants declares it here, and the
#: value is the reason. It compiles through a toolchain the ordinary gates do
#: not require anyone to have, so the gates that cover every host build leave it
#: alone rather than making that toolchain a condition of running them. What
#: keeps the exclusion honest is that the same translation units are covered by
#: the environment this one is derived from, and that the sweep refuses to run
#: when it discovers none of these.
MUTATION_SWEEP_OPTION = "custom_mutation_sweep"

#: An environment that carries a parameter description inside its artefact
#: declares which description here, as a path relative to the project. A target
#: has no filesystem to read one from, so the description travels compiled in
#: rather than named for opening -- and the one thing that cannot then be read
#: off the running machine is which description it was. The declaration is what
#: makes that answerable before the artefact exists.
EMBEDDED_DESCRIPTION_OPTION = "custom_embedded_description"

#: The same declaration for the limits declaration that travels beside the
#: description. An artefact carrying a description of a machine and no statement
#: of what a reading off that machine may plausibly be would either believe every
#: reading or believe none, so the two travel together or not at all.
EMBEDDED_LIMITS_OPTION = "custom_embedded_limits"

#: The same declaration again, for the tolerance declaration that travels beside
#: both. It is not a statement about the machine at all -- it is how far from
#: the temperature it was asked for a delivery may sit -- but it reaches the
#: artefact by the same route and for the same reason: the control path cannot
#: come up without it, and a target has no filesystem to open it from. An
#: artefact carrying a description and bounds but no band would have a control
#: law with nothing to hold a delivery to, which is not a wider band but an
#: absent criterion.
EMBEDDED_TOLERANCE_OPTION = "custom_embedded_tolerance"

#: The same declaration again, for the pump trim declaration that travels
#: beside all three. It is not a statement about the machine either, on the
#: same terms the tolerance is not -- it is how hard the design corrects a rate
#: gap, a control-tuning policy on exactly the footing the steam side's own
#: declaration already is -- but it reaches the artefact by the same route and
#: for the same reason: control_init refuses to come up without it, and a
#: target has no filesystem to open it from. An artefact carrying a machine and
#: a band but no pump trim would have a control law that refuses to start at
#: all, which is a louder failure than the others but the same omission.
EMBEDDED_PUMP_TRIM_OPTION = "custom_embedded_pump_trim"

#: The macro a build names the description its artefact and its tests are
#: exercised against with. An environment naming one is pinning the host
#: verification tier to that description: it is the file the model's own tests
#: read, so it is the file a machine claiming to carry the verified model has
#: to be carrying.
#:
#: Read out of the build rather than named in a gate, because which description
#: that is belongs to the build. Read here rather than in each gate that wants
#: it, because two readers of the same declaration are two answers waiting to
#: disagree.
REFERENCE_MACRO = "REFERENCE_DESCRIPTION_PATH"

#: The same, for the limits declaration the host tier is pinned to. Separate
#: from the macro above because the two files are separate: a build could
#: legitimately pin one and forget the other, and that is precisely the omission
#: worth being able to see.
REFERENCE_LIMITS_MACRO = "REFERENCE_LIMITS_PATH"

#: The same, for the tolerance declaration the host tier is pinned to. Named on
#: its own terms rather than derived from either of the others, because it is
#: not a file that varies with the machine: one declaration states what every
#: delivery is held to, and a build naming a second one is a build in which two
#: answers to that exist.
REFERENCE_TOLERANCE_MACRO = "REFERENCE_TOLERANCE_PATH"

#: The same, for the pump trim declaration the host tier is pinned to. Named on
#: its own terms rather than derived from either of the others, for the reason
#: the tolerance's own macro is: it is not a file that varies with the machine
#: or with the drink, and a build naming a second one is a build in which two
#: answers to "how hard does this design correct a rate gap" exist at once.
REFERENCE_PUMP_TRIM_MACRO = "REFERENCE_PUMP_TRIM_PATH"

#: The flag options a reference description can be named in.
_FLAG_OPTIONS = ("build_flags", "build_src_flags")

#: `-D REFERENCE_DESCRIPTION_PATH='"..."'`, however the quoting survived.
_REFERENCE_FLAG = re.compile(r"-D\s*" + REFERENCE_MACRO + r"\s*=\s*[\"']*([^\"'\s]+)[\"']*")
_REFERENCE_LIMITS_FLAG = re.compile(
    r"-D\s*" + REFERENCE_LIMITS_MACRO + r"\s*=\s*[\"']*([^\"'\s]+)[\"']*"
)
_REFERENCE_TOLERANCE_FLAG = re.compile(
    r"-D\s*" + REFERENCE_TOLERANCE_MACRO + r"\s*=\s*[\"']*([^\"'\s]+)[\"']*"
)
_REFERENCE_PUMP_TRIM_FLAG = re.compile(
    r"-D\s*" + REFERENCE_PUMP_TRIM_MACRO + r"\s*=\s*[\"']*([^\"'\s]+)[\"']*"
)

#: `${section.option}`, the build file's own reference to another value.
_REFERENCE = re.compile(r"\$\{([^}\s]+)\.([^}\s]+)\}")


def _project_relative(path: str) -> str:
    """A declared path with the build file's own way of naming the project cut off.

    The build file writes `$PROJECT_DIR/params/x.params` because that is what
    the compiler needs; a gate comparing declarations wants the part that is the
    same wherever the tree is checked out.
    """
    if not path:
        return ""
    trimmed = path.replace("${PROJECT_DIR}/", "").replace("$PROJECT_DIR/", "")
    forward = trimmed.replace("\\", "/")
    # A prefix, not a set of characters. Stripping the characters would turn
    # `../params/x` into `params/x` -- a different file, and one that may exist.
    while forward.startswith("./"):
        forward = forward[2:]
    return forward


_TRUTHY = ("yes", "true", "1", "on")


class ConfigurationError(Exception):
    """The build file cannot be read, or refers to something that is not there."""


@dataclass(frozen=True)
class Environment:
    """One environment of the build, with every value already resolved."""

    name: str
    options: dict[str, str]

    def get(self, option: str, default: str = "") -> str:
        """One resolved option, with the whitespace a value may be wrapped over collapsed."""
        if option not in self.options:
            return default
        return " ".join(self.options[option].split())

    def declares(self, option: str) -> bool:
        return option in self.options

    @property
    def platform(self) -> str:
        return self.get("platform")

    @property
    def is_host(self) -> bool:
        """Whether this environment builds for the host rather than a board."""
        return self.platform == HOST_PLATFORM

    @property
    def source_filter(self) -> str:
        return self.get("build_src_filter")

    @property
    def source_flags(self) -> str:
        """The flags applied to this project's own sources and to nothing else."""
        return self.get("build_src_flags")

    @property
    def links_host_entry_point(self) -> bool:
        """Whether the artefact carries this project's own `main`.

        This is what separates an environment whose artefact can be run with a
        parameter description from one whose artefact the test runner supplies
        an entry point for.

        A term taking a directory wholesale includes what is under it, and a
        later term can take it back out again, so the filter is walked in order
        rather than searched for one prefix: reading only the additions would
        report an entry point an artefact does not have.
        """
        included = False
        for sign, normalised in filter_terms.terms(self.source_filter):
            if not filter_terms.covers(normalised, HOST_ENTRY_PREFIX.rstrip("/")):
                continue
            included = sign == "+"
        return included

    @property
    def runs_tests(self) -> bool:
        """Whether the test runner can be pointed at this environment."""
        return self.get(TEST_OPTION).strip().lower() in _TRUTHY

    @property
    def must_not_build_reason(self) -> str:
        """Why this environment is required to be refused, or empty if it is not."""
        return self.get(MUST_NOT_BUILD_OPTION).strip()

    @property
    def must_not_build_marker(self) -> str:
        """What this environment's own refusal must name in the build output.

        Declared per environment because more than one check can stop a build,
        and a gate accepting any failure as the right one would keep passing
        after the check it means to exercise stopped running at all. An
        environment naming none is read as expecting the marker the
        structure-selection check has always printed, which is what every
        misconfigured environment declared before this option existed.
        """
        return self.get(MUST_NOT_BUILD_MARKER_OPTION).strip() or DEFAULT_MUST_NOT_BUILD_MARKER

    @property
    def strict_flags_exemption(self) -> str:
        """Why this environment cannot carry the strict warning settings.

        Only an environment that compiles sources which are not this project's
        through the same path can hold one -- that is the whole content of the
        exemption. An exemption declared anywhere else is a way of turning the
        settings off, so it is reported as a problem rather than honoured, by
        the gate that asks.
        """
        return self.get(STRICT_EXEMPTION_OPTION).strip()

    @property
    def mutation_sweep_reason(self) -> str:
        """Why this environment is built for the mutation sweep alone, or empty.

        The declaration is what takes it out of the sets the ordinary gates
        cover. It is not a way of avoiding them: it says the environment exists
        to be compiled through a mutation-instrumenting toolchain, which is the
        one property that cannot be asked of a host anybody is expected to build
        on, and the sources it compiles are covered under the environment it
        extends.
        """
        return self.get(MUTATION_SWEEP_OPTION).strip()

    @property
    def embedded_description(self) -> str:
        """The parameter description this artefact carries compiled in, or empty.

        A path relative to the project. An environment declaring one is saying
        its artefact does not read a description at start-up because there is
        nowhere to read one from, so the bytes travel with the code.
        """
        return _project_relative(self.get(EMBEDDED_DESCRIPTION_OPTION).strip())

    @property
    def embedded_limits(self) -> str:
        """The limits declaration this artefact carries compiled in, or empty.

        Declared separately from the description rather than derived from its
        name. A path derived by substitution would be a second statement of
        which files belong together, made by a script rather than by the build,
        and it would go on producing a plausible answer after somebody renamed
        one of them.
        """
        return _project_relative(self.get(EMBEDDED_LIMITS_OPTION).strip())

    @property
    def embedded_tolerance(self) -> str:
        """The tolerance declaration this artefact carries compiled in, or empty.

        Declared in its own right, like the two beside it. The band is the one
        of the three that says nothing about this machine -- it is what the
        drink demands -- and it is declared here anyway, because which file an
        artefact carries is a fact about the artefact whatever the file happens
        to be about, and a build is entitled to be read rather than reasoned
        about.
        """
        return _project_relative(self.get(EMBEDDED_TOLERANCE_OPTION).strip())

    @property
    def embedded_pump_trim(self) -> str:
        """The pump trim declaration this artefact carries compiled in, or empty.

        Declared in its own right, like the tolerance beside it. Which file an
        artefact carries is a fact about the artefact whatever the file happens
        to be about, and a build is entitled to be read rather than reasoned
        about.
        """
        return _project_relative(self.get(EMBEDDED_PUMP_TRIM_OPTION).strip())

    @property
    def reference_descriptions(self) -> list[str]:
        """Every description this environment names as the one it is exercised
        against, as paths relative to the project, in the order they appear.

        A list rather than one value because naming two is a state the build can
        be in, and a reader collapsing it to one would answer a question the
        build has not settled. The callers that need a single answer are the
        ones that refuse the ambiguity.
        """
        found: list[str] = []
        for option in _FLAG_OPTIONS:
            for match in _REFERENCE_FLAG.finditer(self.get(option)):
                path = _project_relative(match.group(1))
                if path not in found:
                    found.append(path)
        return found

    @property
    def reference_limits(self) -> list[str]:
        """Every limits declaration this environment names as the one it is
        exercised against, on the same terms as the descriptions above.
        """
        found: list[str] = []
        for option in _FLAG_OPTIONS:
            for match in _REFERENCE_LIMITS_FLAG.finditer(self.get(option)):
                path = _project_relative(match.group(1))
                if path not in found:
                    found.append(path)
        return found

    @property
    def reference_tolerance(self) -> list[str]:
        """Every tolerance declaration this environment names as the one it is
        exercised against, on the same terms as the two above.
        """
        found: list[str] = []
        for option in _FLAG_OPTIONS:
            for match in _REFERENCE_TOLERANCE_FLAG.finditer(self.get(option)):
                path = _project_relative(match.group(1))
                if path not in found:
                    found.append(path)
        return found

    @property
    def reference_pump_trim(self) -> list[str]:
        """Every pump trim declaration this environment names as the one it is
        exercised against, on the same terms as the three above.
        """
        found: list[str] = []
        for option in _FLAG_OPTIONS:
            for match in _REFERENCE_PUMP_TRIM_FLAG.finditer(self.get(option)):
                path = _project_relative(match.group(1))
                if path not in found:
                    found.append(path)
        return found

    def build_directory(self, project: str) -> str:
        return os.path.join(project, BUILD_ROOT, self.name)

    def artefact(self, project: str) -> str:
        """The linked artefact, whether or not it has been built yet.

        Which names are candidates follows from what the environment builds for:
        a host build produces an executable something runs, a board build
        produces an image nothing here runs. Looking for the wrong one would
        report an artefact absent rather than found under its own name.
        """
        directory = self.build_directory(project)
        names = ARTEFACT_NAMES if self.is_host else MACHINE_ARTEFACT_NAMES
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.exists(candidate):
                return candidate
        return os.path.join(directory, names[0])

    def objects_under(self, project: str, source_subdirectory: str) -> str:
        """Where the objects built from one source directory are put."""
        return os.path.join(self.build_directory(project), source_subdirectory)

    def structure(self, available: list[str]) -> str | None:
        """The single plant structure this environment selects, if exactly one.

        None covers both an environment compiling no plant source at all and
        one whose selection is not a single structure. Neither is a subject for
        a per-structure gate; the check that a build names exactly one
        structure is what reports those, and it runs inside the build.
        """
        chosen, touches_plant = selected(self.source_filter, available)
        if not touches_plant or len(chosen) != 1:
            return None
        return next(iter(chosen))


def _sections(project: str) -> configparser.ConfigParser:
    path = os.path.join(project, PROJECT_CONFIG)
    if not os.path.isfile(path):
        raise ConfigurationError(f"no {PROJECT_CONFIG} at {path}")

    parser = configparser.ConfigParser(
        interpolation=None,
        comment_prefixes=(";", "#"),
        inline_comment_prefixes=None,
        strict=True,
    )
    try:
        with open(path, "r", encoding="utf-8") as handle:
            parser.read_file(handle, source=path)
    except configparser.Error as error:
        raise ConfigurationError(f"{path} cannot be read: {error}") from error
    return parser


def _inherited(parser: configparser.ConfigParser, section: str, seen: tuple[str, ...]) -> dict[str, str]:
    """One section's options, with anything it extends underneath it.

    A section's own value wins over an inherited one, which is what `extends`
    means, and a later parent wins over an earlier one. A cycle is reported
    rather than followed: it would otherwise be an interpreter recursion error
    naming nothing useful.
    """
    if section in seen:
        raise ConfigurationError(
            f"'{section}' extends itself, through {' -> '.join(seen + (section,))}"
        )
    if not parser.has_section(section):
        if seen:
            raise ConfigurationError(f"'{seen[-1]}' extends '{section}', which is not declared")
        raise ConfigurationError(f"'{section}' is not declared")

    options = dict(parser.items(section))

    inherited: dict[str, str] = {}
    # A parent list may be separated by commas, by newlines, or by both.
    for parent in options.get("extends", "").replace(",", " ").split():
        inherited.update(_inherited(parser, parent, seen + (section,)))

    inherited.update(options)
    inherited.pop("extends", None)
    return inherited


def _resolve(
    parser: configparser.ConfigParser,
    section: str,
    value: str,
    seen: tuple[str, ...] = (),
) -> str:
    """Substitute every `${section.option}` the value refers to.

    `${this.x}` names the section the value is written in. A reference to
    something that is not declared is an error rather than an empty string: a
    filter that silently loses a term is how a build ends up compiling
    something nobody meant it to.
    """

    def substitute(match: re.Match[str]) -> str:
        target, option = match.group(1), match.group(2)
        if target == "this":
            target = section
        if target == "sysenv":
            return os.environ.get(option, "")
        key = f"{target}.{option}"
        if key in seen:
            raise ConfigurationError(f"'{key}' refers to itself, through {' -> '.join(seen + (key,))}")
        try:
            referenced = _inherited(parser, target, ())
        except ConfigurationError as error:
            raise ConfigurationError(
                f"{section}: '${{{key}}}' is referenced, and {error}"
            ) from error
        if option not in referenced:
            raise ConfigurationError(f"{section}: '${{{key}}}' is referenced but not declared")
        return _resolve(parser, target, referenced[option], seen + (key,))

    return _REFERENCE.sub(substitute, value)


def load(project: str) -> list[Environment]:
    """Every environment the build declares, in the order it declares them."""
    parser = _sections(project)

    environments: list[Environment] = []
    for section in parser.sections():
        if not section.startswith(ENVIRONMENT_PREFIX):
            continue
        name = section[len(ENVIRONMENT_PREFIX) :]
        options = _inherited(parser, section, ())
        environment = Environment(
            name=name,
            options={
                option: _resolve(parser, section, value) for option, value in options.items()
            },
        )
        if environment.is_host and not environment.declares("build_src_filter"):
            # PlatformIO would compile everything under src/ here. Rather than
            # reproduce that default, this refuses: an environment whose filter
            # went unread would look as though it compiled nothing and drop out
            # of every set a gate covers without a word.
            raise ConfigurationError(
                f"'{name}' builds for the host and declares no build_src_filter, so what it "
                "compiles cannot be established without reproducing the build system's default"
            )
        environments.append(environment)
    return environments


def host_environments(environments: list[Environment]) -> list[Environment]:
    """Every environment that builds this project's sources for the host.

    The ones declared to be refused are not among them: requiring a clean
    build of a configuration that must not build at all would contradict the
    refusal it exists to demonstrate.

    Nor are the ones declared to exist for the mutation sweep. Every gate here
    builds what it covers, and building one of those requires a mutation
    toolchain -- so covering them would make that toolchain a condition of
    running the ordinary gates at all, on every host, for a build whose
    translation units are already covered under the environment it extends.
    """
    return [
        environment
        for environment in environments
        if environment.is_host
        and not environment.must_not_build_reason
        and not environment.mutation_sweep_reason
    ]


def artefact_environments(environments: list[Environment]) -> list[Environment]:
    """Every host environment that links an executable of this project's own."""
    return [
        environment
        for environment in host_environments(environments)
        if environment.links_host_entry_point
    ]


def test_environments(environments: list[Environment]) -> list[Environment]:
    """Every host environment the test runner can be pointed at."""
    return [
        environment for environment in host_environments(environments) if environment.runs_tests
    ]


def refused_environments(environments: list[Environment]) -> list[Environment]:
    """Every environment declared to be refused rather than built."""
    return [environment for environment in environments if environment.must_not_build_reason]


def mutation_environments(environments: list[Environment]) -> list[Environment]:
    """Every environment declared to exist for the mutation sweep.

    The sweep finds its subjects here rather than being handed a name, for the
    same reason every other gate does, and with one consequence worth stating:
    an environment excused from the gates that cover every host build and driven
    by nothing at all would be an exclusion with nothing on the other side of
    it. The sweep refusing to run when this is empty is what closes that.
    """
    return [environment for environment in environments if environment.mutation_sweep_reason]


def machine_environments(environments: list[Environment]) -> list[Environment]:
    """Every environment that builds an artefact for a machine.

    A build that is not for the host is for something that will be energised,
    and what a gate may demand of it differs in kind from what it may demand of
    an analysis build: the machine has to carry a model of itself, and the
    analysis builds deliberately include ones that do not. The environments
    declared to be refused are left out because a build required to fail is not
    an artefact anybody gets.

    Discovered from the platform rather than from the environment's name, so a
    second board arriving later is covered without a gate being told about it.
    """
    return [
        environment
        for environment in environments
        if not environment.is_host and not environment.must_not_build_reason
    ]


def _pinned(
    environments: list[Environment],
    named_by: Callable[[Environment], list[str]],
    macro: str,
    subject: str,
) -> tuple[str, list[str]]:
    """The one file of a kind the build pins its verification to, and what went wrong.

    This is the single reader of such a declaration. The gate that asks whether a
    machine carries the verified model and the gate that asks whether every
    value in it accounts for itself are asking about the same file, and a second
    reader of the same flag is the way those two answers start to differ. Which
    is why the description and the limits declaration are answered here by one
    body of code rather than by two that agree today: they are the same question
    asked about two files, and written twice they would drift the moment either
    was corrected.

    Naming none and naming two are both reported rather than resolved: a tier
    pinned to nothing has verified against nothing in particular, and a tier
    pinned to two has no single answer to be compared against.
    """
    named: dict[str, list[str]] = {}
    for environment in environments:
        for path in named_by(environment):
            named.setdefault(path, []).append(environment.name)

    if not named:
        return "", [
            f"no environment names a {subject} with {macro}, so there is no "
            f"{subject} the verification tier is pinned to"
        ]
    if len(named) > 1:
        detail = "; ".join(
            f"{path} by {', '.join(environments_naming)}"
            for path, environments_naming in sorted(named.items())
        )
        return "", [
            f"more than one {subject} is named with {macro} ({detail}), so which "
            "one the verification tier is pinned to is not settled"
        ]

    return next(iter(named)), []


def pinned_description(environments: list[Environment]) -> tuple[str, list[str]]:
    """The one description the build pins its verification to, and what went wrong.

    What the tier's own tests read the machine's coefficients out of, and so what
    an artefact claiming to carry the verified model has to be carrying.
    """
    return _pinned(
        environments,
        lambda environment: environment.reference_descriptions,
        REFERENCE_MACRO,
        "description",
    )


def pinned_limits(environments: list[Environment]) -> tuple[str, list[str]]:
    """The one limits declaration the build pins its verification to, and what went wrong.

    Asked separately from the description above because the two files are
    separate. A build can pin one and leave the other unnamed, and that omission
    is the one worth being able to see: an artefact carrying a description of a
    machine and no statement of what a reading off that machine may plausibly be
    would either believe every reading or believe none.
    """
    return _pinned(
        environments,
        lambda environment: environment.reference_limits,
        REFERENCE_LIMITS_MACRO,
        "limits declaration",
    )


def pinned_tolerance(environments: list[Environment]) -> tuple[str, list[str]]:
    """The one tolerance declaration the build pins its verification to, and what
    went wrong.

    Asked separately from the two above because it answers a separate question.
    Those two say what this machine is and what its sensors could report; this
    says how far from the temperature it was asked for a delivery may sit, which
    is a property of the drink and would read the same on a machine of another
    kind entirely. A build pinning the machine's files and leaving this one
    unnamed has a verification tier holding deliveries to nothing in particular,
    and a control path that cannot come up at all on the target -- which is the
    omission worth being able to see before an artefact exists.
    """
    return _pinned(
        environments,
        lambda environment: environment.reference_tolerance,
        REFERENCE_TOLERANCE_MACRO,
        "tolerance declaration",
    )


def pinned_pump_trim(environments: list[Environment]) -> tuple[str, list[str]]:
    """The one pump trim declaration the build pins its verification to, and
    what went wrong.

    Asked separately from the three above because it answers a separate
    question again: not what this machine is, what its sensors could report,
    or what the drink demands, but how hard DEC-CORRECTION-KEEPS-THE-ACCOUNT's
    trim corrects a rate gap -- a control-tuning policy that would read the
    same on a machine of another kind entirely, on exactly the footing the
    steam side's own gains already do. A build pinning the machine's files and
    the drink's tolerance but leaving this one unnamed has a verification tier
    that never exercised the actual trim gains the target carries: the tier's
    tests would have run some other pair of gains, or none, while the artefact
    goes out carrying whatever this build happened to embed.
    """
    return _pinned(
        environments,
        lambda environment: environment.reference_pump_trim,
        REFERENCE_PUMP_TRIM_MACRO,
        "pump trim declaration",
    )
