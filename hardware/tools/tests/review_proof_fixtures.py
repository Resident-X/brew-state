"""The rules the layout review proof design's review added in KiCad's own form, against KiCad itself.

The crystal keep-clear, the ground pad reliefs and the floorplan's regions are
custom rules in the design's rules file, which KiCad enforces; the check adds
nothing to them but reporting what KiCad finds. These run the shipped check on
copies of hardware/proof/review-proof in temporary git work trees outside the
repository, each with a fault seeded for one rule, with the real kicad-cli named
by KICAD_CLI (or found on the search path). A missing tool fails the run, since a
rule that cannot be exercised has not been shown to work.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_fixtures  # noqa: E402
import board_kicad_fixtures  # noqa: E402
import board_prove  # noqa: E402
import review_seed  # noqa: E402


KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI)


class ReviewProofCopy(unittest.TestCase):
    """A fresh copy of the layout review proof design in its own git work tree."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="review-proof-test-")
        self.addCleanup(self.scratch.cleanup)
        self.seed = board_prove.prepare(self.scratch.name, review_seed.DESIGN, review_seed.NAME)

    def check(self):
        status, lines, stderr = board_prove.check(self.seed, KICAD_CLI)
        self.assertNotEqual(status, 2, stderr)
        return status, [line.split(" | ") for line in lines if line.startswith("VIOLATION | ")]

    def named(self, violations, text):
        return [v for v in violations if text in v[4]]

    def thermal_gap(self, gap: str) -> None:
        def edit(tree: list) -> None:
            for zone in review_seed.sexpr.children(tree, "zone"):
                fill = review_seed.sexpr.child(zone, "fill")
                for node in review_seed.sexpr.children(fill, "thermal_gap") if fill else []:
                    node[1] = gap
        self.seed.layout(edit)


if __name__ == "__main__":
    unittest.main()


class SharedReviewProofCopy(board_kicad_fixtures.SharedCopy):
    """A copy of the layout review proof design and the result of checking it, made once for the class and shared by its tests, which only read them."""

    @classmethod
    def prepare_seed(cls, root: str):
        return board_prove.prepare(root, review_seed.DESIGN, review_seed.NAME)

    def check(self):
        status, lines = super().check()
        return status, [line.split(" | ") for line in lines if line.startswith("VIOLATION | ")]
