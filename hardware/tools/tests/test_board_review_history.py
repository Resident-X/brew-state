#!/usr/bin/env python3
"""The layout review record history check, run on throwaway git repositories.

Each repository is built in a temporary folder outside this one, holding a
board's folder with a KiCad project, a schematic and a layout, each a few
characters of text since the check reads only which files changed, and a
layout-review.md committed round by round as the method's review step commits
it, compliant or with one known defect. The command is held to the verdict that
history should get, in its text form and its JSON form. Only git and Python
are needed.
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_review_history  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))

VERDICT_HEADER = "| Item | Kind | Severity | Verdict | Rests on | Why |\n|---|---|---|---|---|---|\n"
FINDING_HEADER = ("| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |\n"
                  "|---|---|---|---|---|---|---|---|\n")


def finding(number, what="U1 sits far from U2.", raised="WORK-1", severity="quality", closed=""):
    return f"| {number} | {raised} | {severity} | {what} | yes | WORK-1 | no | {closed} |"


def round_text(number, judged, findings=None, verdicts=None, opening="Judged on the views.", plan=False):
    """One round of the record: its opening lines, a verdict table, and a findings table when it has findings."""
    findings = [finding(f"{number}.1")] if findings is None else findings
    verdicts = verdicts or [f"| WORK-1 | judgement | quality | {'fail' if findings else 'pass'} | whole board | Why {number}. |",
                            "| GROUND-1 | rule | function | pass | whole board | Planes. |"]
    text = (f"## Round {number}\n\n- **Board judged**: commit {judged}.\n- **Views**: {opening}\n\n"
            f"### Verdicts\n\n{VERDICT_HEADER}" + "\n".join(verdicts) + "\n\n")
    if plan:
        text += "### Plan and free pass\n\n- **Plan**: as planned.\n\n"
    if findings:
        text += f"### Findings\n\n{FINDING_HEADER}" + "\n".join(findings) + "\n"
    return text


class Repo:
    """A throwaway repository holding one board's folder, b/, and its review record."""

    def __init__(self, test):
        self.test = test
        self.root = tempfile.mkdtemp(prefix="board-review-history-test-")
        test.addCleanup(shutil.rmtree, self.root, True)
        self.path = os.path.join(self.root, "repo")
        self.folder = os.path.join(self.path, "b")
        os.makedirs(self.folder)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "tag.gpgsign", "false")
        self.rounds = {}
        self.version = 0
        self.write("b/b.kicad_pro", "{}\n")
        self.write("b/b.kicad_sch", "(kicad_sch (version 1))\n")
        self.write("b/b.kicad_pcb", "(kicad_pcb (version 1))\n")
        self.write("b/separation-basis.yaml", "standard: none\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "b: design")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.path, capture_output=True, text=True,
                              check=True).stdout.strip()

    def write(self, name, text):
        with open(os.path.join(self.path, name), "w", encoding="utf-8") as handle:
            handle.write(text)

    def head(self):
        return self.git("rev-parse", "HEAD")

    def commit(self, message="step"):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.head()

    def redesign(self, name="b/b.kicad_pcb", message="b: change the design"):
        """Change a design file and commit it; the commit."""
        self.version += 1
        self.write(name, f"(kicad_pcb (version 1) (revision {self.version}))\n")
        return self.commit(message)

    def record(self, replace=None):
        """The record as it stands, rounds in order, with `replace` giving round texts by number."""
        self.rounds.update(replace or {})
        self.write("b/layout-review.md", "# Layout review\n\n" + "\n".join(self.rounds[n] for n in sorted(self.rounds)))

    def record_round(self, number, judged, **kwargs):
        """Record a round at its end and commit the record alone; the commit."""
        self.record({number: round_text(number, judged, **kwargs)})
        return self.commit(f"b: record round {number}")

    def built(self, rounds=2):
        """A record built round by round: each round judges a design committed before it, and the board changes only
        after the round is recorded, except after the last. Returns each round's judged and end-of-round commits."""
        made = []
        for number in range(1, rounds + 1):
            judged = self.redesign(message=f"b: design for round {number}")
            made.append((judged, self.record_round(number, judged[:12])))
        return made

    def run(self, folder=None, *extra):
        """The command's exit status, its report's lines and its JSON document, the two forms' statuses equal."""
        args = ["--folder", folder or self.folder, *extra]
        stream, document = io.StringIO(), io.StringIO()
        status = board_review_history.main(args, out=stream)
        self.test.assertEqual(board_review_history.main(args + ["--json"], out=document), status,
                              "the JSON run exits with the text run's status")
        return status, stream.getvalue().splitlines(), json.loads(document.getvalue())


def checks(document):
    return [f"{check['check']}: {check['detail']}" for check in document["checks"] if check["verdict"] == "FAIL"]


class Base(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(self)

    def assertPasses(self, folder=None):
        status, lines, document = self.repo.run(folder)
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(document["result"], "PASS")
        self.assertTrue(lines[-1].startswith("RESULT | PASS |"), lines[-1])
        return lines, document

    def assertFails(self, *words, check=None):
        """Every word is in a failed check of the given name, in the JSON form and the printed form alike, and each
        failure names the board."""
        status, lines, document = self.repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertEqual(document["result"], "FAIL")
        self.assertEqual(document["board"], "b")
        self.assertTrue(lines[-1].startswith("RESULT | FAIL |"), lines[-1])
        failed = [c for c in document["checks"] if c["verdict"] == "FAIL" and (check is None or c["check"] == check)]
        printed = [line for line in lines if line.startswith("CHECK | ") and line.split(" | ")[2] == "FAIL"]
        self.assertTrue(failed, "no failed check" + (f" {check}" if check else "") + "\n" + "\n".join(lines))
        for detail in (c["detail"] for c in failed):
            self.assertTrue(detail.startswith("b: "), "a failure names the board")
        for word in words:
            self.assertTrue(any(word in c["detail"] for c in failed), f"no failed check says '{word}':\n" +
                            "\n".join(checks(document)))
            self.assertTrue(any(board_review_history.clean(word) in line for line in printed),
                            f"no printed failed check says '{word}':\n" + "\n".join(lines))
        return document


class Passes(Base):
    def test_a_record_built_round_by_round_passes(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        self.repo.built(3)
        lines, document = self.assertPasses()
        self.assertEqual(document["board"], "b")
        self.assertEqual([c["check"] for c in document["checks"]],
                         ["rounds kept", "round structure"] + [f"round {n} {what}" for n in (1, 2, 3)
                                            for what in ("as first recorded", "order")] + ["closing round"])
        self.assertIn("CHECK | closing round | PASS |", "\n".join(lines))

    def test_a_finding_closed_after_its_round_was_recorded_passes(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew, and a record whose only change after a round is a finding's closure.
        made = self.repo.built(1)
        self.repo.record({1: round_text(1, made[0][0][:12], findings=[finding("1.1", closed="a reason: met")])})
        self.repo.commit("b: close finding 1.1")
        self.assertPasses()

    def test_a_record_file_beside_the_design_changed_after_the_closing_round_is_no_design_change(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: the files KiCad reads for it, never the board's own records, the review record among them
        self.repo.built(1)
        self.repo.write("b/separation-basis.yaml", "standard: other\n")
        self.repo.write("b/notes.md", "notes\n")
        self.repo.commit("b: records")
        self.assertPasses()

    def test_a_yml_or_other_record_file_in_the_folder_is_no_design_change_but_any_other_file_in_it_is(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: the files KiCad reads for it, never the board's own records, the review record among them
        self.repo.built(1)
        self.repo.write("b/separation-basis.yml", "standard: other\n")
        os.makedirs(os.path.join(self.repo.path, "other"))
        self.repo.write("other/anything.txt", "outside the board's folder\n")
        self.repo.commit("b: a yml record and a file outside the folder")
        self.assertPasses()
        self.repo.write("b/b.kicad_dru", "(version 1)\n")
        self.repo.commit("b: a rules file")
        self.assertFails("b/b.kicad_dru", check="closing round")
        self.repo.git("reset", "-q", "--hard", "HEAD~1")
        self.repo.write("b/notes.txt", "a file KiCad may read\n")
        self.repo.commit("b: another file in the folder")
        self.assertFails("b/notes.txt", check="closing round")

    def test_a_library_a_library_table_names_outside_the_folder_is_a_design_file(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: the files KiCad reads for it
        os.makedirs(os.path.join(self.repo.path, "shared"))
        self.repo.write("shared/x.kicad_sym", "(kicad_symbol_lib (version 1))\n")
        self.repo.write("b/sym-lib-table", '(sym_lib_table (lib (name "x")(type "KiCad")'
                        '(uri "${KIPRJMOD}/../shared/x.kicad_sym")(options "")(descr "")))\n')
        judged = self.repo.commit("b: a library outside the folder")
        self.repo.record_round(1, judged[:12])
        self.assertPasses()
        self.repo.write("shared/x.kicad_sym", "(kicad_symbol_lib (version 1) (changed))\n")
        self.repo.commit("b: the library changes after the closing round")
        self.assertFails("shared/x.kicad_sym", check="closing round")

    def test_a_round_with_no_findings_and_no_findings_table_passes(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12], findings=[])
        self.assertPasses()

    def test_a_round_stating_it_raises_no_finding_passes_but_any_other_text_in_its_place_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12], findings=[]) + "### Findings\n\nThis round raises no finding.\n"})
        self.repo.commit("b: round 1 raises no finding")
        self.assertPasses()
        self.repo.record({1: self.repo.rounds[1].replace("This round raises no finding.", "Finding 1.1 is open.")})
        self.repo.commit("b: prose in its place")
        self.assertFails("its Findings table: it holds no table", check="round structure")

    def test_a_record_at_the_repository_root_passes_from_the_root(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: given a board's folder
        for name in ("b.kicad_pro", "b.kicad_sch", "b.kicad_pcb"):
            self.repo.git("mv", f"b/{name}", name)
        self.repo.git("mv", "b/separation-basis.yaml", "separation-basis.yaml")
        self.repo.commit("move the board to the root")
        judged = self.repo.head()
        self.repo.write("layout-review.md", "# Review\n\n" + round_text(1, judged[:12]))
        self.repo.commit("record")
        status, lines, document = self.repo.run(self.repo.path)
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(document["board"], ".")

    def test_a_sheet_the_schematic_reaches_beside_the_board_is_a_design_file(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: the files KiCad reads for it
        self.repo.write("b/b.kicad_sch", '(kicad_sch (version 1) (sheet (property "Sheetfile" "../shared/s.kicad_sch")))\n')
        os.makedirs(os.path.join(self.repo.path, "shared"))
        self.repo.write("shared/s.kicad_sch", "(kicad_sch (version 1))\n")
        judged = self.repo.commit("b: a sheet outside the folder")
        self.repo.record_round(1, judged[:12])
        self.assertPasses()
        self.repo.write("shared/s.kicad_sch", "(kicad_sch (version 1) (changed))\n")
        self.repo.commit("b: the sheet changes after the closing round")
        self.assertFails("shared/s.kicad_sch", check="closing round")


class Fails(Base):
    def test_a_round_deleted_by_a_commit_that_keeps_only_the_latest_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round recorded in an earlier commit is missing, naming the board, the round and what differs.
        made = self.repo.built(3)
        self.repo.rounds = {3: self.repo.rounds[3]}
        self.repo.record()
        deleting = self.repo.commit("b: keep only the latest round")
        document = self.assertFails(f"round 1 was recorded at {made[0][1][:12]}", "round 2 was recorded at",
                                    check="rounds kept")
        self.assertNotIn(deleting[:12], " ".join(checks(document)))
        self.assertEqual([c["verdict"] for c in document["checks"] if c["check"] == "round 3 as first recorded"],
                         ["PASS"], "the round that is kept is still judged")

    def test_a_round_deleted_then_restored_unchanged_passes_and_restored_altered_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit
        self.repo.built(2)
        full = dict(self.repo.rounds)
        self.repo.rounds = {2: full[2]}
        self.repo.record()
        self.repo.commit("b: drop round 1")
        self.repo.rounds = dict(full)
        self.repo.record()
        self.repo.commit("b: restore round 1")
        self.assertPasses()
        self.repo.record({1: full[1].replace("Why 1.", "Reworded 1.")})
        self.repo.commit("b: restore round 1 differently")
        self.assertFails("round 1 differs from its end-of-round commit", "its verdict table row for WORK-1 differs",
                         check="round 1 as first recorded")

    def test_a_finding_removed_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12], findings=[finding("1.1"), finding("1.2", "R3 is short.")])
        self.repo.record({1: round_text(1, judged[:12], findings=[finding("1.1")])})
        self.repo.commit("b: tidy the record")
        self.assertFails("finding 1.2 was removed", check="round 1 as first recorded")

    def test_a_finding_added_to_a_recorded_round_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12])
        self.repo.record({1: round_text(1, judged[:12], findings=[finding("1.1"), finding("1.2", "New.")])})
        self.repo.commit("b: late finding")
        self.assertFails("finding 1.2 was added", check="round 1 as first recorded")

    def test_a_finding_renumbered_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12], findings=[finding("1.1"), finding("1.2", "R3 is short.")])
        self.repo.record({1: round_text(1, judged[:12], findings=[finding("1.1"), finding("1.3", "R3 is short.")])})
        self.repo.commit("b: renumber")
        self.assertFails("finding 1.2 was removed", "finding 1.3 was added", check="round 1 as first recorded")

    def test_a_finding_reworded_or_rerated_fails_in_each_compared_column(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12])
        for column, edited in (("What and where", finding("1.1", what="Reworded.")),
                               ("Severity", finding("1.1", severity="safety")),
                               ("Raised by", finding("1.1", raised="WORK-2"))):
            with self.subTest(column=column):
                self.repo.record({1: round_text(1, judged[:12], findings=[edited])})
                self.repo.commit(f"b: edit {column}")
                self.assertFails(f"finding 1.1's {column} now reads", check="round 1 as first recorded")
                self.repo.git("reset", "-q", "--hard", "HEAD~1")
                self.repo.rounds[1] = round_text(1, judged[:12])

    def test_a_closed_by_edit_alongside_a_rule_or_shortfall_edit_passes_since_only_the_named_fields_are_compared(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: a record whose only change after a round is a finding's closure
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12])
        closed = finding("1.1", closed="reason: met").replace("| yes | WORK-1 | no |", "| no | PLACE-2 | yes |")
        self.repo.record({1: round_text(1, judged[:12], findings=[closed])})
        self.repo.commit("b: close and re-judge the rule")
        self.assertPasses()

    def test_an_opening_line_or_a_verdict_row_changed_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12])
        self.repo.record({1: round_text(1, judged[:12], opening="Judged on other views.")})
        self.repo.commit("b: reword the opening")
        self.assertFails("its opening lines differ, first at '- **Views**: Judged on other views.'",
                         check="round 1 as first recorded")
        self.repo.rounds[1] = round_text(1, judged[:12], verdicts=["| WORK-1 | judgement | quality | pass | whole board | x |"])
        self.repo.record()
        self.repo.commit("b: change the verdicts")
        self.assertFails("its verdict table no longer has the row for GROUND-1",
                         "its verdict table row for WORK-1 differs", check="round 1 as first recorded")

    def test_a_verdict_row_reordered_or_a_header_renamed_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit
        judged = self.repo.redesign()
        rows = ["| A-1 | rule | quality | pass | x | y |", "| B-1 | rule | quality | pass | x | y |"]
        self.repo.record_round(1, judged[:12], findings=[], verdicts=rows)
        self.repo.record({1: round_text(1, judged[:12], findings=[], verdicts=rows[::-1])})
        self.repo.commit("b: reorder")
        self.assertFails("its verdict table rows are in a different order", check="round 1 as first recorded")

    def test_a_later_round_is_judged_against_its_own_first_record_not_the_first_rounds(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        self.repo.built(2)
        self.repo.record({2: round_text(2, self.repo.rounds[2].split("commit ")[1][:12], opening="Changed.")})
        self.repo.commit("b: edit round 2")
        document = self.assertFails(check="round 2 as first recorded")
        self.assertEqual([c["verdict"] for c in document["checks"] if c["check"] == "round 1 as first recorded"],
                         ["PASS"])

    def test_a_design_change_committed_before_the_round_that_judged_it_fails_the_order(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round's end-of-round commit is not an ancestor of a later commit that changes the board's design files, naming the board, the round and what differs.
        judged = self.repo.redesign(message="b: design to judge")
        change = self.repo.redesign(message="b: the change round 1 calls for")
        self.repo.record_round(1, judged[:12])
        self.assertFails(f"does not come before {change[:12]}, which changes b/b.kicad_pcb after the round's Board "
                         f"judged commit {judged[:12]}", check="round 1 order")

    def test_a_round_recorded_in_the_commit_that_changes_the_design_fails_the_order(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round's end-of-round commit is not an ancestor of a later commit that changes the board's design files
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12])})
        self.repo.version += 1
        self.repo.write("b/b.kicad_sch", "(kicad_sch (version 1) (changed))\n")
        together = self.repo.commit("b: record and change together")
        self.assertFails(f"does not come before {together[:12]}, which changes b/b.kicad_sch", check="round 1 order")

    def test_a_design_change_on_a_line_of_history_the_record_commit_is_not_an_ancestor_of_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round's end-of-round commit is not an ancestor of a later commit that changes the board's design files
        judged = self.repo.redesign()
        self.repo.git("checkout", "-q", "-b", "side")
        side = self.repo.redesign("b/b.kicad_sch", "b: change on the side")
        self.repo.git("checkout", "-q", "main")
        self.repo.record_round(1, judged[:12])
        self.repo.git("merge", "-q", "--no-ff", "-m", "merge side", "side")
        self.assertFails(f"does not come before {side[:12]}", check="round 1 order")

    def test_a_board_judged_commit_not_in_the_history_fails_the_order(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round's end-of-round commit is not an ancestor of a later commit that changes the board's design files, naming the board, the round and what differs.
        self.repo.redesign()
        self.repo.record_round(1, "0123456789ab")
        self.assertFails("round 1's Board judged commit 0123456789ab is not in this repository's history",
                         check="round 1 order")

    def test_a_round_naming_no_board_judged_commit_fails_the_order(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round's end-of-round commit is not an ancestor of a later commit that changes the board's design files, naming the board, the round and what differs.
        self.repo.redesign()
        self.repo.record({1: "## Round 1\n\n- **Views**: none.\n"})
        self.repo.commit("b: no Board judged")
        self.assertFails("round 1's Board judged commit (none given) is not in this repository's history",
                         check="round 1 order")

    def test_a_design_changed_after_the_closing_round_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when the board's design files have changed since the closing round's commit, naming the board, the round and what differs.
        made = self.repo.built(2)
        later = self.repo.redesign("b/b.kicad_sch", "b: change after closing")
        document = self.assertFails(f"design files changed after closing round 2's commit {made[1][1][:12]}: "
                                    "b/b.kicad_sch", check="closing round")
        self.assertNotIn(later[:12], " ".join(checks(document)))

    def test_a_design_change_after_an_earlier_round_but_before_the_closing_round_passes(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: when the board's design files have changed since the closing round's commit
        self.repo.built(2)
        self.assertPasses()

    def test_a_record_with_no_round_or_an_unreadable_findings_table_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        self.repo.write("b/layout-review.md", "# Layout review\n\nNothing yet.\n")
        self.repo.commit("b: empty record")
        self.assertFails("the record at HEAD holds no round", check="rounds kept")
        judged = self.repo.head()
        broken = round_text(1, judged[:12]).replace("| Finding | Raised by |", "| Number | Raised by |")
        self.repo.record({1: broken})
        self.repo.commit("b: findings table without a Finding column")
        self.assertFails("round 1 of the record at HEAD", "its Findings table has no Finding column",
                         check="round structure")


class Headings(Base):
    """A round, or a part of one, written in a form the command cannot read is one it cannot guard, so it fails the
    record."""

    def recorded(self, edit):
        """Round 1 recorded with its heading line edited, and no design change after it."""
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace("## Round 1\n", edit(1), 1)})
        return self.repo.commit("b: record round 1")

    def test_a_round_heading_in_another_form_fails_the_round_headings(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round recorded in an earlier commit is missing, naming the board, the round and what differs.
        for form in ("## Round {} - re-review\n", "### Round {}\n", "# Round {}\n", "## Round {}\r\n", "##Round {}\n",
                     "## Round 0{}\n", "## round {}\n", "## **Round {}**\n", "    ## Round {}\n", "Round {}\n"):
            with self.subTest(form=form):
                self.recorded(lambda n: form.format(n))
                document = self.assertFails("line 3 of the record at HEAD reads", "which mentions a round heading that is not exactly '## Round <n>'",
                                            check="round structure")
                self.repo.git("reset", "-q", "--hard", "HEAD~2")
                self.repo.rounds = {}

    def test_a_malformed_heading_only_in_an_older_version_fails_naming_that_commit(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round recorded in an earlier commit is missing, naming the board, the round and what differs.
        made = self.repo.built(1)
        self.repo.rounds[1] = self.repo.rounds[1].replace("## Round 1\n", "## Round 1 - first\n")
        self.repo.record()
        bad = self.repo.commit("b: an odd heading")
        self.repo.rounds[1] = self.repo.rounds[1].replace("## Round 1 - first\n", "## Round 1\n")
        self.repo.record()
        self.repo.commit("b: put it right")
        self.assertFails(f"the version of the record at {bad[:12]} reads '## Round 1 - first'", check="round structure")

    def test_a_heading_inside_a_code_fence_is_not_a_round_heading(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace(
            "### Verdicts", "```\n### Round 9 output\n```\n\n### Verdicts", 1)})
        self.repo.commit("b: record round 1 quoting a tool's output")
        self.assertPasses()

    def test_an_unclosed_code_fence_fails_whether_at_head_or_only_in_an_older_version(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round recorded in an earlier commit is missing, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace("### Verdicts", "```\n### Verdicts", 1)})
        self.repo.commit("b: record round 1 with a fence left open")
        self.assertFails("a code fence opened at line", "of the record at HEAD is never closed", check="round structure")
        self.repo.git("reset", "-q", "--hard", "HEAD~1")
        self.repo.rounds = {}
        made = self.repo.built(1)
        self.repo.rounds[1] = self.repo.rounds[1].replace("### Verdicts", "~~~\n### Verdicts", 1)
        self.repo.record()
        bad = self.repo.commit("b: a fence left open")
        self.repo.rounds[1] = self.repo.rounds[1].replace("~~~\n### Verdicts", "### Verdicts", 1)
        self.repo.record()
        self.repo.commit("b: close it up")
        self.assertFails(f"of the version of the record at {bad[:12]} is never closed", check="round structure")

    def test_a_code_fence_closed_by_the_other_character_stays_open(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round recorded in an earlier commit is missing, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace("### Verdicts", "```\n~~~\n### Round 9\n### Verdicts", 1)})
        self.repo.commit("b: a fence closed by the wrong mark")
        self.assertFails("is never closed", check="round structure")

    def test_fenced_content_with_round_like_lines_passes_when_the_fence_closes(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace(
            "### Verdicts", "~~~\n## round 2\n## Round 02\n```\n**Round 3**\n~~~\n\n### Verdicts", 1)})
        self.repo.commit("b: record round 1 quoting round-like lines")
        self.assertPasses()

    def test_a_round_heading_given_twice_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]) + "\n" + round_text(1, judged[:12])})
        self.repo.commit("b: round 1 twice")
        self.assertFails("holds round 1 more than once", check="round structure")

    def structured(self, edit, first=1):
        """Round 1 recorded, then its text edited and recorded again in a second commit; the text the edit gave."""
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12])
        edited = edit(self.repo.rounds[1])
        self.repo.record({1: edited})
        self.repo.commit("b: edit round 1")
        return edited

    def test_a_findings_subheading_renamed_with_a_finding_rewritten_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        for name in ("Findings and closures", "Finding", "findings", "Findings:"):
            with self.subTest(name=name):
                self.repo = Repo(self)
                self.structured(lambda text: text.replace("### Findings", f"### {name}").replace(
                    "U1 sits far from U2.", "TOTALLY CHANGED"))
                self.assertFails("line 15 reads", f"'### {name}', a heading the command cannot read",
                                 check="round structure")

    def test_a_subheading_at_another_level_fails_the_structure(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        for form in ("#### Findings", "## Findings", "# Findings", "###Findings", " ### Findings", "<h3>Findings</h3>",
                     "Findings\n--------"):
            with self.subTest(form=form):
                self.repo = Repo(self)
                self.structured(lambda text: text.replace("### Findings", form).replace("U1 sits far", "U1 sits near"))
                self.assertFails("a heading the command cannot read", check="round structure")

    def test_a_fenced_level_two_line_before_the_findings_table_does_not_cut_the_round(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        fenced = lambda text: text.replace("- **Views**", "```\n## x\n```\n\n- **Views**", 1)
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12])
        self.repo.rounds[1] = fenced(self.repo.rounds[1])
        self.repo.record()
        self.repo.commit("b: quote a level-two line in round 1")
        self.assertFails("its opening lines differ", check="round 1 as first recorded")
        self.repo.git("reset", "-q", "--hard", "HEAD~1")
        self.repo.rounds = {}
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12])
        self.repo.rounds[1] = fenced(self.repo.rounds[1])
        self.repo.record()
        self.repo.commit("b: quote it")
        self.repo.rounds[1] = self.repo.rounds[1].replace("U1 sits far from U2.", "TOTALLY CHANGED")
        self.repo.record()
        self.repo.commit("b: rewrite a finding")
        self.assertFails("finding 1.1's What and where now reads 'TOTALLY CHANGED'", check="round 1 as first recorded")

    def test_a_fenced_level_two_line_inside_a_round_passes_when_the_round_is_otherwise_whole(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12], plan=True).replace(
            "### Findings", "```\n## x\n### Findings\n#### y\n```\n\n### Findings", 1)})
        self.repo.record_round(2, judged[:12])
        self.assertPasses()

    def test_a_level_two_heading_that_is_not_a_round_inside_a_round_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        self.structured(lambda text: text.replace("### Findings", "## Notes\n\n### Findings"))
        self.assertFails("round 1 of the record at HEAD: line", "'## Notes', a heading the command cannot read",
                         check="round structure")

    def test_a_part_given_twice_or_a_missing_verdicts_part_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12], plan=True) + "\n### Plan and free pass\n\nAgain.\n"})
        self.repo.commit("b: a part twice")
        self.assertFails("gives its '### Plan and free pass' part a second time", check="round structure")
        self.repo.git("reset", "-q", "--hard", "HEAD~1")
        self.repo.rounds = {}
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace("### Findings", "### Findings\n\nx\n\n### Findings", 1)})
        self.repo.commit("b: findings twice")
        self.assertFails("gives its '### Findings' part a second time", check="round structure")
        self.repo.git("reset", "-q", "--hard", "HEAD~1")
        self.repo.rounds = {}
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace("### Verdicts", "### Verdict", 1)})
        self.repo.commit("b: no verdicts part")
        self.assertFails("round 1 of the record at HEAD: it has no '### Verdicts' part", check="round structure")

    def test_a_findings_or_verdicts_part_the_command_cannot_read_fails(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        header = "| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |"
        cases = {
            "its Findings table: it holds no table": lambda t: t[:t.index(header)] + "Finding: none\n",
            "its Findings table: its verdict table has no separator row of dashes": lambda t: t.replace(
                "|---|---|---|---|---|---|---|---|\n", ""),
            "its Findings table has no Raised by column": lambda t: t.replace("Raised by", "Raised"),
            "its Findings table gives finding 1.1 more than once": lambda t: t + finding("1.1", what="again") + "\n",
            "which is not part of its one table": lambda t: t + "\nSee also finding 1.1.\n",
            "its Findings table: line": lambda t: t + "\n" + header + "\n|---|---|---|---|---|---|---|---|\n",
            "its Verdicts table is headed 'Item | Kind | Severity | Result | Rests on | Why'": lambda t: t.replace(
                "| Verdict |", "| Result |"),
            "its Verdicts table: it holds no table": lambda t: re.sub(r"(?m)^\|.*\n", "", t[:t.index("### Findings")]) +
            t[t.index("### Findings"):],
        }
        for expected, edit in cases.items():
            with self.subTest(expected=expected):
                self.repo = Repo(self)
                self.structured(edit)
                self.assertFails(expected, check="round structure")

    def test_an_unreadable_part_in_an_older_version_only_fails_naming_that_commit(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        self.repo.built(1)
        good = self.repo.rounds[1]
        self.repo.rounds[1] = good.replace("### Findings", "### Findings and closures")
        self.repo.record()
        bad = self.repo.commit("b: rename")
        self.repo.rounds[1] = good
        self.repo.record()
        self.repo.commit("b: restore")
        self.assertFails(f"round 1 of the version of the record at {bad[:12]}: line", check="round structure")

    def test_a_backtick_line_with_a_backtick_in_its_info_string_is_no_fence_so_the_round_after_it_is_seen(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when any round's opening lines, verdict table or findings differ from that round's end-of-round commit, naming the board, the round and what differs.
        judged = self.repo.redesign()
        self.repo.record_round(1, judged[:12], plan=True)
        attack = self.repo.rounds[1] + "\n```x```\n" + round_text(2, judged[:12]) + "```\n"
        self.repo.write("b/layout-review.md", "# Layout review\n\n" + attack)
        self.repo.commit("b: hide a round behind a line that is no fence")
        # round 2 is seen as a round, and the trailing fence it cannot close fails the structure
        self.assertFails("a code fence opened at line", "is never closed", check="round structure")
        statuses = [c["check"] for c in self.repo.run()[2]["checks"]]
        self.assertIn("round 2 as first recorded", statuses)

    def test_a_fence_follows_the_commonmark_rule(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        quoted = "````\n```\n## Round 9\n```\n## Round 8\n````\n\n### Verdicts"
        judged = self.repo.redesign()
        self.repo.record({1: round_text(1, judged[:12]).replace("### Verdicts", quoted, 1)})
        self.repo.commit("b: a four-backtick fence holding a three-backtick block")
        self.assertPasses()
        lines, _ = board_review_history.record_lines(quoted)
        self.assertEqual([line for _, line, fenced in lines if line.startswith("## Round")], ["## Round 9", "## Round 8"])
        self.assertTrue(all(fenced for _, line, fenced in lines[:6]))
        self.assertFalse(lines[-1][2])
        for form in ("   ```", "~~~~ info", "```py"):
            self.assertTrue(board_review_history.record_lines(form)[0][0][2], form)
        for form in ("    ```", "```x```", "~~", "`` `", "x ```"):
            self.assertFalse(board_review_history.record_lines(form)[0][0][2], form)

    def test_a_closer_shorter_than_its_opener_or_with_text_after_it_leaves_the_fence_open(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: fails when a round recorded in an earlier commit is missing, naming the board, the round and what differs.
        for opener, closer in (("````", "```"), ("```", "``` x"), ("~~~~", "~~~"), ("```", "    ```")):
            with self.subTest(opener=opener, closer=closer):
                self.repo = Repo(self)
                judged = self.repo.redesign()
                self.repo.record({1: round_text(1, judged[:12]).replace(
                    "### Verdicts", f"{opener}\n{closer}\n### Verdicts", 1)})
                self.repo.commit("b: a fence the closer does not close")
                self.assertFails("is never closed", check="round structure")

    def test_a_conforming_record_passes_the_round_structure(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        self.repo.built(2)
        _, document = self.assertPasses()
        self.assertEqual([c["verdict"] for c in document["checks"] if c["check"] == "round structure"], ["PASS"])


class Proof(unittest.TestCase):
    def test_the_proof_board_record_in_this_repository_passes(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It passes a record whose rounds only ever grew.
        shallow = subprocess.run(["git", "-C", REPO, "rev-parse", "--is-shallow-repository"], capture_output=True,
                                 text=True).stdout.strip()
        if shallow != "false":
            self.skipTest("the repository's history is not whole")
        out = io.StringIO()
        status = board_review_history.main(["--folder", os.path.join(REPO, "hardware", "proof", "review-proof")], out=out)
        self.assertEqual(status, 0, out.getvalue())


class Refusals(Base):
    def assertRefused(self, *words, folder=None):
        status, lines, document = self.repo.run(folder)
        self.assertEqual(status, 2, "\n".join(lines))
        self.assertEqual(document["result"], "REFUSED")
        self.assertEqual(document["checks"], [], "a refused record is not judged at all")
        self.assertTrue(lines[-1].startswith("RESULT | REFUSED |"), lines[-1])
        for word in words:
            self.assertTrue(any(word in line for line in lines if line.startswith("REFUSED |")), "\n".join(lines))
            self.assertTrue(any(word in refusal["what"] or word in refusal["why"] for refusal in document["refusals"]),
                            document["refusals"])
        return document

    def test_a_shallow_clone_is_refused(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: it refuses, rather than judging, a shallow clone
        self.repo.built(2)
        shallow = os.path.join(self.repo.root, "shallow")
        subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{self.repo.path}", shallow], check=True,
                       capture_output=True)
        self.assertRefused("the repository is a shallow clone", folder=os.path.join(shallow, "b"))

    def test_a_record_that_is_untracked_absent_or_differs_from_head_is_refused(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: it refuses, rather than judging, a record or design file that is untracked, absent or differs from HEAD
        self.repo.built(1)
        self.repo.write("b/layout-review.md", "edited\n")
        document = self.assertRefused("has changes that are not committed")
        self.assertEqual([refusal["what"] for refusal in document["refusals"]], ["b/layout-review.md"])
        self.repo.git("checkout", "--", "b/layout-review.md")
        os.remove(os.path.join(self.repo.folder, "layout-review.md"))
        self.assertRefused("is deleted in the working tree")
        self.repo.git("rm", "-q", "--cached", "b/layout-review.md")
        self.repo.commit("stop tracking the record")
        self.assertRefused("is not tracked in the repository")
        self.repo.git("checkout", "HEAD~1", "--", "b/layout-review.md")
        self.repo.git("reset", "-q", "b/layout-review.md")
        self.assertRefused("is not tracked in the repository")

    def test_a_design_file_that_is_untracked_absent_or_differs_from_head_is_refused(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: it refuses, rather than judging, a record or design file that is untracked, absent or differs from HEAD
        self.repo.built(1)
        for name in ("b/b.kicad_pcb", "b/b.kicad_sch", "b/b.kicad_pro"):
            with self.subTest(changed=name):
                with open(os.path.join(self.repo.path, name), encoding="utf-8") as handle:
                    original = handle.read()
                self.repo.write(name, original + "(edit)\n")
                document = self.assertRefused("has changes that are not committed")
                self.assertEqual([refusal["what"] for refusal in document["refusals"]], [name])
                self.repo.git("checkout", "--", name)
        os.remove(os.path.join(self.repo.folder, "b.kicad_pcb"))
        self.assertRefused("is deleted in the working tree")
        self.repo.git("checkout", "--", "b/b.kicad_pcb")
        self.repo.write("b/b.kicad_dru", "(version 1)\n")
        self.assertRefused("b/b.kicad_dru", "is not tracked in the repository")

    def test_a_folder_that_is_missing_or_holds_no_single_project_or_is_outside_a_work_tree_is_refused(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: given a board's folder, it refuses, rather than judging, what it cannot read
        self.repo.built(1)
        self.assertRefused("there is no board folder here to judge", folder=os.path.join(self.repo.path, "nowhere"))
        loose = os.path.join(self.repo.root, "loose")
        os.makedirs(loose)
        self.assertRefused("not inside a git work tree", folder=loose)
        self.repo.write("b/c.kicad_pro", "{}\n")
        self.repo.commit("a second project")
        self.assertRefused("the folder tracks 2 KiCad projects")
        self.repo.git("rm", "-q", "b/b.kicad_pro", "b/c.kicad_pro")
        self.repo.commit("no project")
        self.assertRefused("the folder tracks no KiCad project")

    def test_a_repository_with_no_commit_is_refused(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: it refuses, rather than judging, what it cannot read
        empty = os.path.join(self.repo.root, "empty")
        os.makedirs(os.path.join(empty, "b"))
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=empty, check=True, capture_output=True)
        self.assertRefused("the repository has no commit", folder=os.path.join(empty, "b"))


class Output(Base):
    def test_the_text_and_json_outputs_give_the_same_checks_and_verdict(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: It reports in a text form and in a JSON form that carry the same checks and verdict
        made = self.repo.built(2)
        self.repo.record({1: round_text(1, made[0][0][:12], findings=[finding("1.1", what="Reworded.")])})
        self.repo.commit("b: reword")
        status, lines, document = self.repo.run()
        self.assertEqual(status, 1)
        from_text = [line.split(" | ", 3)[1:] for line in lines if line.startswith("CHECK | ")]
        from_json = [[check["check"], check["verdict"], board_review_history.clean(check["detail"])]
                     for check in document["checks"]]
        self.assertEqual(from_text, from_json)
        self.assertIn(["round 2 as first recorded", "PASS"], [row[:2] for row in from_json])
        self.assertEqual(lines[-1], f"RESULT | {document['result']} | {document['detail']}")
        self.assertEqual(document["detail"], "1 of 7 checks failed")
        self.assertEqual(len(lines), len(from_text) + 1, "every line but the result is a check")
        self.assertEqual(document["refusals"], [])

    def test_the_task_runs_the_command_from_the_repositorys_taskfile(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: Provide one task-runner command that, given a board's folder, reads its layout review record and the repository's history
        self.repo.built(2)
        result = subprocess.run(["task", "hw:review-history", "--", "--folder", self.repo.folder], cwd=REPO,
                                capture_output=True, text=True, timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT | PASS |", result.stdout)
        self.repo.redesign("b/b.kicad_sch", "b: change after closing")
        result = subprocess.run(["task", "hw:review-history", "--", "--folder", self.repo.folder, "--json"], cwd=REPO,
                                capture_output=True, text=True, timeout=300)
        self.assertNotEqual(result.returncode, 0, "a failing record fails the task")
        self.assertEqual(json.loads(result.stdout[:result.stdout.rindex("}") + 1])["result"], "FAIL")


class Documentation(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    def test_the_method_runs_the_command_in_place_of_the_hand_run_checks(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C2: Change the method's layout review step so that its completion checks for each round standing as first recorded and for the closing round judging the board as it stands are made by running the history command and reading its verdict, naming the command and what its failure means, and remove the hand-run git commands those checks now give.
        method = self.read("docs", "board-design-method.md")
        step = method[method.index("Judge the record against the board and the repository rather than taking its word:\n"):
                      method.index("**This step is shown to find what it checks for**")]
        for words in ("task hw:review-history -- --folder", "RESULT | PASS", "RESULT | FAIL", "RESULT | REFUSED", "exits 0", "1 and", "2 and",
                      "Each round stands as it was first recorded", "the closing round judged the board as it stands"):
            self.assertIn(words, step)
        for command in ("merge-base --is-ancestor", "-G '^#+ Round", "git diff --quiet", "git log --reverse"):
            self.assertNotIn(command, method, "the hand-run check is gone from the method")
        self.assertNotIn("<record commit>", method)

    def test_the_task_and_the_hardware_notes_describe_the_command(self):
        # SOL-BOARD-REVIEW-RECORD-HISTORY-CHECK.C1: Provide one task-runner command
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:review-history:"):taskfile.index("  hw:test:\n")]
        for words in ("board_review_history.py", "--folder", "Exits 0 on a pass, 1 on a fail, 2 when refused",
                      "git and Python"):
            self.assertIn(words, task)
        notes = self.read("hardware", "README.md")
        for words in ("task hw:review-history -- --folder", "layout review record", "refuses", "needs git and Python only",
                      "2 when the command is refused"):
            self.assertIn(words, notes)
        for words in ("the round structure", "`### Plan and free pass`", "This round raises no finding.",
                      "the separation basis record among them"):
            self.assertIn(words, notes)
        self.assertIn("`round structure`", self.read("docs", "board-design-method.md"))
        self.assertIn("each round only the parts the command reads", task)


if __name__ == "__main__":
    unittest.main()
