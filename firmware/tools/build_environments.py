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
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

#: `${section.option}`, the build file's own reference to another value.
_REFERENCE = re.compile(r"\$\{([^}\s]+)\.([^}\s]+)\}")

#: One `+<path>` or `-<path>` term of a source filter.
_FILTER_TERM = re.compile(r"([+-])\s*<([^>]*)>")


def _covers(term: str, path: str) -> bool:
    """Whether a filter term takes in the given path, wholesale or exactly."""
    if term in ("", "*"):
        return True
    return path == term or path.startswith(term + "/")

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
        for sign, path in _FILTER_TERM.findall(self.source_filter):
            normalised = path.strip().replace("\\", "/").lstrip("./").rstrip("/")
            if not _covers(normalised, HOST_ENTRY_PREFIX.rstrip("/")):
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

    def build_directory(self, project: str) -> str:
        return os.path.join(project, BUILD_ROOT, self.name)

    def artefact(self, project: str) -> str:
        """The linked executable, whether or not it has been built yet."""
        directory = self.build_directory(project)
        for name in ARTEFACT_NAMES:
            candidate = os.path.join(directory, name)
            if os.path.exists(candidate):
                return candidate
        return os.path.join(directory, ARTEFACT_NAMES[0])

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
