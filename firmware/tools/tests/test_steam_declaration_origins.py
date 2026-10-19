#!/usr/bin/env python3
"""The gate that refuses a steam declaration figure with no honest origin.

Driven against synthetic declarations written into a temporary directory, with a
copy of the origin vocabulary the gate loads. The failing direction is the point:
a figure carrying no origin, an origin of a kind nobody declared, a kind with no
account, and an account that still names a relation the steam side has retired
must each be refused, and a correct declaration must be accepted.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import check_steam_declaration_origins as gate  # noqa: E402

ORIGIN_HEADER = """
#ifndef PLANT_ORIGIN_H
#define PLANT_ORIGIN_H
typedef enum {
    PLANT_ORIGIN_DOCUMENT = 0,
    PLANT_ORIGIN_ESTIMATED,
    PLANT_ORIGIN_MEASURED,
    PLANT_ORIGIN_KIND_COUNT
} plant_origin_kind_t;
#define PLANT_ORIGIN_DOCUMENT_WORD "document"
#define PLANT_ORIGIN_ESTIMATED_WORD "estimated"
#define PLANT_ORIGIN_MEASURED_WORD "measured"
#define PLANT_ORIGIN_MARKER '@'
#define PLANT_ORIGIN_NO_MACHINE_DECLARATION "describes-no-machine"
#endif
"""

KINDS = {"document", "estimated", "measured"}

GOOD = (
    "# A comment may say the affine slope was retired.\n"
    "ready-temperature-c = 130000 milli-c @estimated Derived from the orifice law and the "
    "saturation relation in thermoblock.params.\n"
    "feed-ceiling = 123 permille @estimated Derived from the orifice law and the band.\n"
)


def run_tool(declaration: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as root:
        include = os.path.join(root, "include")
        os.makedirs(include)
        with open(os.path.join(include, "plant_origin.h"), "w", encoding="utf-8") as handle:
            handle.write(ORIGIN_HEADER)
        path = os.path.join(root, "steam.declaration")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(declaration)
        return subprocess.run(
            [sys.executable, os.path.join(TOOLS, "check_steam_declaration_origins.py"),
             "--include-dir", include, "--declaration", path],
            capture_output=True, text=True, check=False,
        )


class Accepts(unittest.TestCase):
    def test_a_declaration_whose_accounts_name_no_retired_relation_is_accepted(self):
        done = run_tool(GOOD)
        self.assertEqual(0, done.returncode, done.stderr)

    def test_a_comment_naming_a_retired_relation_is_not_an_origin(self):
        self.assertEqual([], gate.problems(GOOD, KINDS))


class Refuses(unittest.TestCase):
    def refused(self, text: str, fragment: str):
        found = gate.problems(text, KINDS)
        self.assertEqual(1, len(found), found)
        self.assertIn(fragment, found[0])
        done = run_tool(text)
        self.assertEqual(1, done.returncode)
        self.assertIn(fragment, done.stderr)

    def test_a_figure_with_no_origin(self):
        self.refused("ready-pressure-bar = 1500 milli-bar\n", "carries no origin")

    def test_an_origin_kind_outside_the_vocabulary(self):
        self.refused("ready-pressure-bar = 1500 milli-bar @invented an account\n",
                     "outside the vocabulary")

    def test_an_origin_kind_with_no_account(self):
        self.refused("ready-pressure-bar = 1500 milli-bar @estimated\n", "no account")
        self.refused("ready-pressure-bar = 1500 milli-bar @estimated   \n", "no account")

    def test_an_account_naming_the_retired_slope_coefficient(self):
        self.refused(
            "ready-pressure-bar = 900 milli-bar @estimated Read through steam.pressure_bar_per_k "
            "and the saturation temperature.\n", "retired relation")

    def test_an_account_naming_the_retired_deficit_coefficient(self):
        self.refused(
            "feed-ceiling = 67 permille @estimated Sized against steam.pressure_fall_bar_per_ml.\n",
            "retired relation")

    def test_an_account_using_the_old_words_for_the_retired_relations(self):
        for words in ("the declared slope", "the affine relation", "a pressure-deficit that grows",
                      "the SAG COEFFICIENT", "pressure-per-kelvin"):
            self.refused(f"feed-ceiling = 67 permille @estimated Derived from {words}.\n",
                         "retired relation")

    def test_each_offending_line_is_reported_once_with_its_number(self):
        text = GOOD + "a-figure = 1 permille\nb-figure = 2 permille @estimated the affine slope\n"
        found = gate.problems(text, KINDS)
        self.assertEqual(2, len(found))
        self.assertTrue(found[0].startswith("line 4:"))
        self.assertTrue(found[1].startswith("line 5:"))


class RefusesWhatItCannotInspect(unittest.TestCase):
    def test_an_empty_declaration_is_refused_rather_than_passed(self):
        done = run_tool("# nothing here\n")
        self.assertEqual(1, done.returncode)

    def test_a_missing_declaration_is_refused(self):
        done = subprocess.run(
            [sys.executable, os.path.join(TOOLS, "check_steam_declaration_origins.py"),
             "--include-dir", TOOLS, "--declaration", "/nonexistent/steam.declaration"],
            capture_output=True, text=True, check=False)
        self.assertEqual(2, done.returncode)


class TheShippedDeclaration(unittest.TestCase):
    def test_passes_against_the_tree_it_ships_in(self):
        firmware = os.path.dirname(TOOLS)
        done = subprocess.run(
            [sys.executable, os.path.join(TOOLS, "check_steam_declaration_origins.py"),
             "--include-dir", os.path.join(firmware, "include"),
             "--declaration", os.path.join(firmware, "params", "steam_control.declaration")],
            capture_output=True, text=True, check=False)
        self.assertEqual(0, done.returncode, done.stderr)


if __name__ == "__main__":
    unittest.main()
