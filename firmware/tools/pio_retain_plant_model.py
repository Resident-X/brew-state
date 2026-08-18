"""Keep the plant model's operations in the artefact the machine would run.

The linker discards code nothing reaches. On a build for a machine that is
exactly wrong for the plant model: the artefact is made to carry the model, and
at this point in the work nothing on the machine drives it yet -- the estimator
and the control law that will are separate deliverables. Left to the linker,
the equations are dropped, and everything downstream of that becomes untrue at
once. The artefact stops carrying the model it was built to carry. The maths
those equations call into stops being needed, so a build that could never have
resolved it succeeds anyway, and the toolchain question nobody has answered for
this target goes on unanswered while looking settled.

So the operations the plant seam declares are named to the linker as wanted.
They are read out of the seam header rather than listed here, because a seam
that gains an operation would otherwise gain one nothing retains, and the
discovery is what keeps that from being somebody's job to remember.

This is a target concern only. A host build links an entry point that drives
the model through every operation it declares, so there is nothing there for
the linker to discard.
"""

import os
import sys

Import("env")  # noqa: F821 -- injected by SCons

project_dir = env.subst("$PROJECT_DIR")  # noqa: F821
sys.path.insert(0, os.path.join(project_dir, "tools"))

import plant_seam_operations  # noqa: E402

# Read out of the seam header, and read through the module the check that looks
# for these in the artefact reads them through. A list kept here would be a
# second list, and a seam gaining an operation would leave one of the two
# behind -- retained and never looked for, or looked for and discarded.
try:
    operations = plant_seam_operations.operations(os.path.join(project_dir, "include"))
except plant_seam_operations.NoSeamOperations as error:
    sys.stderr.write(f"pio_retain_plant_model: {error}\n")
    env.Exit(2)  # noqa: F821

env.Append(LINKFLAGS=[f"-Wl,--undefined={name}" for name in operations])  # noqa: F821
