"""Carry what the artefact has to know about the machine into it, and refuse a wrong one.

The host tier opens the files it is exercised against at start-up, because it is
running on something with a filesystem. The machine is not, so they travel
compiled in: this renders each as an array of bytes into the build directory and
puts that directory on the include path, and one checked-in translation unit
apiece includes them. The rendered files are never checked in, because a copy of
a description is a second description -- two records answering the same question,
diverging the moment either is corrected.

There are four of them, and an environment built through this script declares
all of them or none. An artefact carrying a description of a machine and no
statement of what a reading off that machine may plausibly be would either
believe every reading or believe none; one carrying both and no band would come
up with a control law holding its deliveries to nothing; and one carrying all
three but no pump trim declaration has a control law that refuses to come up
at all, since control_init requires the trim on the same terms it requires the
band. None of those is a state anybody would choose deliberately -- so a
partial declaration is refused here rather than built.

Which files those are is read off the environment rather than named here, so a
second board declaring its own is covered without this script being edited.

Generating the bytes from a file is not on its own an argument that they are the
right bytes, so the check that compares them against what the verification tier
is pinned to runs here too, immediately after rendering and before anything is
compiled. It is the standalone script the task runner invokes, so there is one
implementation of it rather than two. It is handed the generated directory
rather than the files in it, so the two of them cannot come to disagree about
which names the build writes under.

Paths are resolved from PROJECT_DIR rather than the working directory, which is
not guaranteed.
"""

import os
import subprocess
import sys

Import("env")  # noqa: F821 -- injected by SCons

sys.path.insert(0, os.path.join(env.subst("$PROJECT_DIR"), "tools"))  # noqa: F821

import build_environments  # noqa: E402
import embedded_description  # noqa: E402

project_dir = env.subst("$PROJECT_DIR")  # noqa: F821
build_dir = env.subst("$BUILD_DIR")  # noqa: F821
environment_name = env.subst("$PIOENV")  # noqa: F821

# Where the rendered files are put. Under the build directory because they are
# derived: a tree that has been cleaned has no copy of them to go stale, and
# nothing about them is anybody's to edit. Both parts of the path come from the
# module that owns the format, so the check that reads them back is looking in
# the place this wrote them rather than in a place that agrees with it today.
generated_directory = os.path.join(build_dir, embedded_description.GENERATED_DIRECTORY)

try:
    declared = build_environments.load(project_dir)
except build_environments.ConfigurationError as error:
    sys.stderr.write(f"pio_embed_description: {error}\n")
    env.Exit(2)  # noqa: F821

named = [entry for entry in declared if entry.name == environment_name]
if not named:
    sys.stderr.write(
        f"pio_embed_description: '{environment_name}' is not an environment this build "
        "declares, so what it should carry cannot be read\n"
    )
    env.Exit(2)  # noqa: F821

# Each thing the artefact carries, beside the option the environment declares it
# in. The pairing is here rather than in the format module because which option
# names which file is a fact about this build rather than about the form the
# bytes take.
sources = [
    (
        embedded_description.DESCRIPTION,
        build_environments.EMBEDDED_DESCRIPTION_OPTION,
        named[0].embedded_description,
    ),
    (
        embedded_description.LIMITS,
        build_environments.EMBEDDED_LIMITS_OPTION,
        named[0].embedded_limits,
    ),
    (
        embedded_description.TOLERANCE,
        build_environments.EMBEDDED_TOLERANCE_OPTION,
        named[0].embedded_tolerance,
    ),
    (
        embedded_description.PUMP_TRIM,
        build_environments.EMBEDDED_PUMP_TRIM_OPTION,
        named[0].embedded_pump_trim,
    ),
]

stated = [entry for entry in sources if entry[2]]
unstated = [entry for entry in sources if not entry[2]]

if not stated:
    sys.stderr.write(
        f"pio_embed_description: '{environment_name}' is built with this script but declares "
        f"neither {' nor '.join(option for _, option, _ in sources)}, so there is nothing to "
        "carry into the artefact\n"
    )
    env.Exit(2)  # noqa: F821

if unstated:
    # A partial declaration. The artefact would compile and would be wrong in a
    # way nothing on the running machine reports: a description with no limits
    # beside it leaves the estimator correcting against every reading a broken
    # channel can produce, limits with no description leave it correcting a model
    # of nothing towards them, and either without the band leaves the control
    # path with nothing to hold a delivery to and so unable to come up at all.
    # None of those has a symptom that distinguishes it from a machine that has
    # merely drifted.
    sys.stderr.write(
        f"pio_embed_description: '{environment_name}' declares "
        f"{', '.join(option for _, option, _ in stated)} but no "
        f"{', '.join(option for _, option, _ in unstated)}. An artefact carrying a "
        "description of a machine and no statement of what a reading off it may plausibly be "
        "would either believe every reading or believe none, and one carrying neither a band "
        "nor a way to learn it holds its deliveries to nothing, so they travel together or "
        "not at all\n"
    )
    env.Exit(2)  # noqa: F821

os.makedirs(generated_directory, exist_ok=True)

for embedding, option, source in stated:
    source_path = os.path.join(project_dir, source)
    if not os.path.isfile(source_path):
        sys.stderr.write(
            f"pio_embed_description: no {embedding.description} at {source_path}\n"
        )
        env.Exit(2)  # noqa: F821

    with open(source_path, "rb") as handle:
        rendered = embedded_description.render(source, handle.read(), embedding)

    generated_path = os.path.join(generated_directory, embedding.generated_name)

    # Written only when it differs, so an unchanged file does not restamp the
    # rendered one and make the compiler rebuild the translation unit that
    # includes it. The bytes are re-read from the source every time regardless,
    # which is what keeps the comparison below asking about it as it is now.
    existing = None
    if os.path.isfile(generated_path):
        with open(generated_path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    if existing != rendered:
        with open(generated_path, "w", encoding="utf-8") as handle:
            handle.write(rendered)

result = subprocess.run(
    [
        sys.executable,
        os.path.join(project_dir, "tools", "check_embedded_description.py"),
        "--project",
        project_dir,
        "--generated",
        f"{environment_name}={generated_directory}",
    ],
    check=False,
)
if result.returncode != 0:
    env.Exit(result.returncode)  # noqa: F821

# Prepended rather than appended, so a copy of a generated header checked into
# the source tree could not win the include search and be compiled instead of
# what this rendered. A copy is the second description this whole arrangement
# exists to prevent, and it would be invisible: the file compared here would be
# the right one while the artefact carried the other. Once, whatever was
# rendered: the directory is one directory, and a second entry for it would put
# the same answer on the path twice.
env.Prepend(CPPPATH=[generated_directory])  # noqa: F821
