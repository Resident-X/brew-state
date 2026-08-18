"""Carry the parameter description into the artefact, and refuse a wrong one.

The host tier opens its description at start-up because it is running on
something with a filesystem. The machine is not, so the description travels
compiled in: this renders it as an array of bytes into the build directory and
puts that directory on the include path, and one checked-in translation unit
includes it. The rendered file is never checked in, because a copy of a
description is a second description -- two records answering the same question,
diverging the moment either is corrected.

Which description is read off the environment rather than named here, so a
second board declaring its own is covered without this script being edited.

Generating the bytes from the file is not on its own an argument that they are
the right bytes, so the check that compares them against the description the
verification tier is pinned to runs here too, immediately after rendering and
before anything is compiled. It is the standalone script the task runner
invokes, so there is one implementation of it rather than two.

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

# Where the rendered description is put. Under the build directory because it is
# derived: a tree that has been cleaned has no copy of it to go stale, and
# nothing about it is anybody's to edit. Both parts of the path come from the
# module that owns the format, so the check that reads the file back is looking
# in the place this wrote it rather than in a place that agrees with it today.
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
        "declares, so which description it should carry cannot be read\n"
    )
    env.Exit(2)  # noqa: F821

description = named[0].embedded_description
if not description:
    sys.stderr.write(
        f"pio_embed_description: '{environment_name}' is built with this script but declares "
        f"no {build_environments.EMBEDDED_DESCRIPTION_OPTION}, so there is no description to "
        "carry into the artefact\n"
    )
    env.Exit(2)  # noqa: F821

source_path = os.path.join(project_dir, description)
if not os.path.isfile(source_path):
    sys.stderr.write(f"pio_embed_description: no description at {source_path}\n")
    env.Exit(2)  # noqa: F821

with open(source_path, "rb") as handle:
    rendered = embedded_description.render(description, handle.read())

os.makedirs(generated_directory, exist_ok=True)
generated_path = os.path.join(generated_directory, embedded_description.GENERATED_NAME)

# Written only when it differs, so an unchanged description does not restamp the
# file and make the compiler rebuild the translation unit that includes it. The
# bytes are re-read from the description every time regardless, which is what
# keeps the comparison below asking about the description as it is now.
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
        f"{environment_name}={generated_path}",
    ],
    check=False,
)
if result.returncode != 0:
    env.Exit(result.returncode)  # noqa: F821

# Prepended rather than appended, so a copy of the generated header checked into
# the source tree could not win the include search and be compiled instead of
# what this rendered. A copy is the second description this whole arrangement
# exists to prevent, and it would be invisible: the file compared here would be
# the right one while the artefact carried the other.
env.Prepend(CPPPATH=[generated_directory])  # noqa: F821
