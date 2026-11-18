"""Find the Python that holds numpy, shapely, Pillow and PyYAML for the silkscreen command and its tests.

The command and its tests import those four packages in their own process. When
the running Python lacks one and SILKSCREEN_PYTHON names a Python that has all
of them (the virtual environment `task hw:silkscreen` makes), `rerun_under_silkscreen_python`
runs the same command line again under that Python, so a bare `python3` still works.
Standard library only.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from typing import List, Optional

PACKAGES = (("numpy", "numpy"), ("shapely", "shapely"), ("PIL", "Pillow"), ("yaml", "PyYAML"))
#: What every silkscreen subcommand reads, the proof included: the table's YAML.
TABLE_PACKAGES = (("yaml", "PyYAML"),)
VARIABLE = "SILKSCREEN_PYTHON"
GUARD = "SILKSCREEN_PYTHON_RERUN"
TASK = "task hw:silkscreen"


def missing_packages(needed=PACKAGES) -> List[str]:
    """The packages of `needed` the running Python cannot import, by their installable names."""
    return [package for module, package in needed if importlib.util.find_spec(module) is None]


def missing_message(package: str) -> str:
    """The sentence a stop for a missing package says: the package, what the command needs, the task and the variable."""
    return (f"the Python package {package} is not installed, and the silkscreen command needs numpy, shapely, Pillow and "
            f"PyYAML (hardware/README.md names them beside KiCad); {where_to_find()}")


def _has_all(python: str, needed=PACKAGES) -> bool:
    probe = "import " + ", ".join(module for module, _ in needed)
    try:
        return subprocess.run([python, "-c", probe], capture_output=True, timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def where_to_find() -> str:
    """The sentence naming the task and the variable, for a message about a missing package."""
    return f"run `{TASK}` to create the environment that holds them, or set {VARIABLE} to a Python that has them"


def rerun_under_silkscreen_python(argv: Optional[List[str]] = None, needed=PACKAGES) -> None:
    """Replace this process by the same command under SILKSCREEN_PYTHON when that is needed and possible.

    Returns when the running Python has every package, when SILKSCREEN_PYTHON is unset, when it is this
    Python, when this process was already started by it, or when it lacks a package too (the caller then
    stops naming the missing package).
    """
    if not missing_packages(needed) or os.environ.get(GUARD):
        return
    python = os.environ.get(VARIABLE, "")
    if not python or not os.path.isfile(python) or os.path.abspath(python) == os.path.abspath(sys.executable):
        return
    if not _has_all(python, needed):
        return
    argv = list(argv if argv is not None else getattr(sys, "orig_argv", [sys.executable] + sys.argv))
    argv[0] = python
    os.environ[GUARD] = "1"
    sys.stdout.flush()
    sys.stderr.flush()
    os.execv(python, argv)
