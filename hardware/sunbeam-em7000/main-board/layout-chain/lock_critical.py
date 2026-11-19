#!/usr/bin/env python3
"""lock_critical.py IN.kicad_pcb OUT.kicad_pcb   (plain Python; the board's .kicad_pro beside IN; KICAD_CLI names kicad-cli)

Copies IN to OUT and locks, in OUT, every track, arc, via and zone on a net of the board's critical classes, through the locked-copper
check's own lock command (hardware/tools/locked_copper.py), which asks KiCad which nets each class holds. The classes are the ones
the board declares critical in its design rules: every class but Default, which holds the nets nothing singles out, and Noisy, which
is routed to the spacing rules and not locked.
"""
import os
import shutil
import subprocess
import sys

CRITICAL_CLASSES = ("Fast", "Ground", "Mains", "MainsBranch", "MainsTrunk", "Mains_Entry", "Sense", "Supply3V3", "Supply5V")
TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools")


def main(argv):
    src, out = argv[1], argv[2]
    kicad_cli = os.environ.get("KICAD_CLI", "")
    if not kicad_cli:
        print("CANNOT RUN | KICAD_CLI must name kicad-cli, which the lock command asks which nets each class holds; it is not set", file=sys.stderr)
        return 2
    shutil.copyfile(src, out)
    stem_in, stem_out = os.path.splitext(src)[0], os.path.splitext(out)[0]
    project = stem_out + ".kicad_pro"
    if not os.path.isfile(project) and os.path.isfile(stem_in + ".kicad_pro"):
        shutil.copyfile(stem_in + ".kicad_pro", project)
    command = [sys.executable, os.path.join(TOOLS, "locked_copper.py"), "--kicad-cli", kicad_cli, "lock", "--board", out, "--project", project]
    for name in CRITICAL_CLASSES:
        command += ["--class", name]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        sys.stderr.write(done.stdout + done.stderr)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv))
