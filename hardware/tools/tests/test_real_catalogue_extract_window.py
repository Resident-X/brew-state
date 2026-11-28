"""The catalogue extracts of the real boards state a window that outlasts the design lock.

Each rule is a function of the extract's text, so a failing case is the same text with one line changed.
"""
from __future__ import annotations

import os
import re
import unittest

import yaml

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(TOOLS))
EXTRACTS = {
    "main board": os.path.join(REPO, "hardware", "sunbeam-em7000", "main-board", "catalogue-extract.yaml"),
    "heater wall board": os.path.join(REPO, "hardware", "sunbeam-em7000", "heater-wall-board", "catalogue-extract.yaml"),
}
README = os.path.join(REPO, "hardware", "README.md")
MINIMUM_DAYS = 3650


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def window_problems(text):
    problems = []
    days = yaml.safe_load(text).get("max_age_days")
    if isinstance(days, bool) or not isinstance(days, int) or days < MINIMUM_DAYS:
        problems.append(f"max_age_days is {days!r}, below the {MINIMUM_DAYS} days a held design needs")
    header = "\n".join(line for line in text.splitlines() if line.startswith("#"))
    if "not a claim of freshness" not in header or "re-dates" not in header:
        problems.append("the header does not say the window is not a claim of freshness and that the order re-dates the extract")
    return problems


class RealCatalogueExtractWindow(unittest.TestCase):
    # SOL-REAL-BOARD-CATALOGUE-EXTRACTS-OUTLAST-THE-DESIGN-LOCK.C1: Each real board's catalogue extract states a window long enough that holding the design does not make its read stale
    def test_each_real_extract_states_a_long_window_and_says_what_it_means(self):
        for name, path in EXTRACTS.items():
            with self.subTest(board=name):
                self.assertEqual(window_problems(read(path)), [])

    def test_the_window_rule_refuses_the_fortnight_window_and_a_silent_header(self):
        text = read(EXTRACTS["main board"])
        fortnight = re.sub(r"^max_age_days: \d+$", "max_age_days: 14", text, flags=re.M)
        self.assertNotEqual(fortnight, text)
        self.assertTrue(any("below the 3650" in p for p in window_problems(fortnight)))
        silent = text.replace("not a claim of freshness", "a claim")
        self.assertNotEqual(silent, text)
        self.assertTrue(any("header does not say" in p for p in window_problems(silent)))
        self.assertTrue(any("below the 3650" in p for p in window_problems(text.replace("max_age_days: 36500", "max_age_days: true"))))

    # SOL-REAL-BOARD-CATALOGUE-EXTRACTS-OUTLAST-THE-DESIGN-LOCK.C2: The hardware README states that the design task declares the extract's window and the order re-reads the extract
    def test_the_readme_names_who_declares_the_window_and_the_order_re_read(self):
        text = read(README)
        self.assertIn("declares the extract's window", text)
        self.assertIn("SOL-HW-CONTROLLER-BOARDS-ORDERED.C10", text)
        self.assertNotIn("keeps the extract current", text)


if __name__ == "__main__":
    unittest.main()
