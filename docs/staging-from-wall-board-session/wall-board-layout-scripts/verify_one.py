#!/usr/bin/env python3
"""Run the pre-order check on ONE design of a clone (default heater-wall-board), nothing else changed.

usage: verify_one.py [--root CLONE] [--design heater-wall-board] [--today YYYY-MM-DD]
The check's own code is imported from the clone's hardware/tools/board_check.py and its report() is used
as is; only the first discover() call (the one report() makes) is filtered to the named design. The far-channel
comparison keeps seeing every design, as in the real run.
"""
import argparse, datetime, os, sys
ap = argparse.ArgumentParser()
ap.add_argument("--root", default=".", help="repository checkout root")
ap.add_argument("--design", default="heater-wall-board")
ap.add_argument("--assume-committed", action="store_true", help="experiments in a scratch copy only: treat every tracked file as committed")
ap.add_argument("--kicad-cli", default=os.environ.get("KICAD_CLI", "kicad-cli"))
a = ap.parse_args()
sys.path.insert(0, os.path.join(a.root, "hardware", "tools"))
import board_check as bc
orig = bc.discover
state = {"n": 0}
def discover(top, files):
    designs, orphans, problems = orig(top, files)
    state["n"] += 1
    if state["n"] == 1:
        designs = [d for d in designs if a.design in d.project]
        orphans = [o for o in orphans if a.design in o.design]
    return designs, orphans, problems
bc.discover = discover
if a.assume_committed:
    bc.Repository.uncommitted = lambda self, path: None if path in self.tracked else "is not tracked in the repository"
sys.exit(bc.run(a.root, a.kicad_cli))
