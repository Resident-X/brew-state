#!/usr/bin/env python3
"""The review kit's rerun of named units, the output folder's lock and record, and the refusals about them.

The stub plays the sessions and the clock is injected; synthetic review and output folders in temporary directories.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import decl, planner, scheduler, store  # noqa: E402
from review_kit import executor as ex  # noqa: E402

NO_OBJECT = ex.Reply(text="Nothing I could put in a table.")


def declared():
    return decl.parse(json.dumps(fx.declaration_dict()), "caller.json")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def failing_g2():
    return {f"G2.r1.a{n}": NO_OBJECT for n in (1, 2, 3)}


class RerunTests(unittest.TestCase):
    def test_only_the_named_units_run_along_the_recorded_path_with_identical_bytes(self):
        # SOL-HW-REVIEW-KIT.C7: given the names of units to run again, the scheduler runs only those along the recorded path with identical bytes
        harness = fx.Harness(self, script=failing_g2())
        first = harness.fresh()
        first_root = harness.executor.calls[0]
        harness.new_stub()
        again = harness.again(["u2", "u3"])
        calls = harness.executor.calls
        self.assertEqual([c.label for c in calls], ["root", "G2.r1.a1"])
        self.assertEqual(calls[0].message.encode("utf-8"), first_root.message.encode("utf-8"))
        self.assertEqual(calls[0].key, first_root.key)
        self.assertEqual(calls[0].spec.digest, harness.spec.digest)
        self.assertEqual(calls[1].message, [c for c in harness.executor.calls if c.label == "G2.r1.a1"][0].message)
        self.assertEqual([n["id"] for n in again["nodes"] if n["group"] == "G1"], [n["id"] for n in first["nodes"] if n["group"] == "G1"])

    def test_rerun_forks_carry_the_same_bytes_as_the_first_run(self):
        # SOL-HW-REVIEW-KIT.C7: a rerun rebuilds the recorded path with identical bytes
        harness = fx.Harness(self, script=failing_g2())
        harness.fresh()
        first = {c.label: c.message for c in harness.executor.calls}
        harness.new_stub()
        harness.again(["u2"])
        self.assertEqual(harness.executor.calls[1].message, first["G2.r1.a1"])

    def test_results_of_the_named_units_are_replaced_and_the_others_kept(self):
        # SOL-HW-REVIEW-KIT.C7: the scheduler replaces their results
        harness = fx.Harness(self, script=failing_g2())
        first = harness.fresh()
        self.assertTrue(first["units"]["u2"]["failed"])
        harness.new_stub()
        again = harness.again(["u2", "u3"])
        self.assertEqual({u: s["failed"] for u, s in again["units"].items()}, {"u1": False, "u2": False, "u3": False, "u4": False})
        lanes = {l["group"]: l for l in again["lanes"]}
        self.assertIsNone(lanes["G2"]["failure"])
        self.assertEqual(len(lanes["G2"]["record"]["attempts"]), 1)
        old = {l["group"]: l for l in first["lanes"]}
        self.assertEqual(lanes["G1"], old["G1"])
        self.assertEqual(lanes["G3"], old["G3"])
        self.assertEqual([n["id"] for n in again["nodes"] if n["group"] == "G2"], ["G2.r1.a1"])
        on_disk = store.read_record(harness.out)
        self.assertEqual(on_disk, json.loads(json.dumps(again)))

    def test_every_replica_of_a_named_units_group_runs_again(self):
        # SOL-HW-REVIEW-KIT.C7: the scheduler runs only those units
        harness = fx.Harness(self, replicas=2)
        harness.fresh()
        harness.new_stub()
        harness.again(["u4"])
        self.assertEqual([c.label for c in harness.executor.calls], ["root", "G3.r1.a1", "G3.r2.a1"])

    def test_record_says_which_units_were_run_again_when_and_whether_a_new_shared_context_was_started(self):
        # SOL-HW-REVIEW-KIT.C7: records which units were run again, when, and that a new shared context was started if the first one's cache had lapsed
        harness = fx.Harness(self)
        first = harness.fresh()
        self.assertEqual(first["runs"], [{"kind": "fresh", "at": "1970-01-01T00:16:40Z", "units": ["u1", "u2", "u3", "u4"],
                                          "new_shared_context": True}])
        harness.clock.t = 5000.0
        # inside the cache's lifetime the root's first call reads the whole prefix and writes nothing
        harness.root_reply = ex.Reply(text="ACK", read=100, write=0)
        harness.new_stub()
        hit = harness.again(["u1"])
        self.assertEqual(hit["runs"][1], {"kind": "rerun", "at": "1970-01-01T01:23:20Z", "units": ["u1"], "new_shared_context": False})
        self.assertFalse(hit["shared_context"]["new"])
        # after the cache lapsed it is written once
        harness.clock.t = 90000.0
        harness.root_reply = ex.Reply(text="ACK", read=0, write=100)
        harness.new_stub()
        lapsed = harness.again(["u1", "u4"])
        self.assertEqual(lapsed["runs"][2], {"kind": "rerun", "at": "1970-01-02T01:00:00Z", "units": ["u1", "u4"],
                                             "new_shared_context": True})
        self.assertTrue(lapsed["shared_context"]["new"])
        self.assertEqual(len(lapsed["runs"]), 3)
        self.assertEqual(lapsed["shared_context"]["prefix_sha"], harness.shared.prefix_sha)

    def test_a_rerun_that_fails_again_is_recorded_as_failed(self):
        # SOL-HW-REVIEW-KIT.C7: the scheduler replaces their results
        harness = fx.Harness(self, script=failing_g2())
        harness.fresh()
        harness.new_stub(failing_g2())
        again = harness.again(["u2", "u3"])
        self.assertTrue(again["units"]["u3"]["failed"])


class RefusalTests(unittest.TestCase):
    def setUp(self):
        self.harness = fx.Harness(self, script=failing_g2())
        self.first = self.harness.fresh()
        self.harness.new_stub()

    def refused(self, names, kind):
        with self.assertRaises(kind) as raised:
            self.harness.again(names)
        self.assertEqual(self.harness.executor.calls, [])
        self.assertFalse(os.path.exists(os.path.join(self.harness.out, store.LOCK_NAME)))
        self.assertEqual(store.read_record(self.harness.out), json.loads(json.dumps(self.first)))
        return str(raised.exception)

    def test_a_name_that_is_not_a_unit_of_the_review_is_refused(self):
        # SOL-HW-REVIEW-KIT.C7: it refuses a name that is not a unit of the review
        text = self.refused(["u2", "u3", "u9"], store.UnknownUnit)
        self.assertIn("'u9'", text)
        self.assertIn("['u1', 'u2', 'u3', 'u4']", text)

    def test_a_run_that_leaves_out_a_unit_whose_last_run_failed_is_refused_naming_it(self):
        # SOL-HW-REVIEW-KIT.C7: it refuses a run that leaves out a unit whose last run failed, naming it
        text = self.refused(["u1"], store.FailedUnitLeftOut)
        self.assertIn("unit u2 failed", text)
        self.assertIn("u3", text)

    def test_a_failed_unit_that_runs_with_its_group_is_not_left_out(self):
        # SOL-HW-REVIEW-KIT.C7: it refuses a run that leaves out a unit whose last run failed
        self.harness.again(["u2"])  # u3 is not named, but its group runs again and so does it
        self.assertEqual([c.label for c in self.harness.executor.calls], ["root", "G2.r1.a1"])

    def test_a_review_folder_whose_hash_differs_from_the_recorded_one_is_refused(self):
        # SOL-HW-REVIEW-KIT.C7: it refuses a review folder whose hash differs from the recorded one
        fx.write(self.harness.review, "docs/guide.md", "changed\n")
        text = self.refused(["u2", "u3"], store.FolderChanged)
        self.assertIn(self.first["review_hash"][:12], text)
        self.assertIn("differs", text)

    def test_a_file_added_to_the_review_folder_changes_its_hash_too(self):
        # SOL-HW-REVIEW-KIT.C7: a review folder whose hash differs from the recorded one is refused
        fx.write(self.harness.review, "docs/extra.md", "new\n")
        self.refused(["u2", "u3"], store.FolderChanged)

    def test_an_empty_directory_added_to_the_review_folder_changes_its_hash_and_the_rerun_is_refused(self):
        # SOL-HW-REVIEW-KIT.C7: a review folder whose hash differs from the recorded one is refused
        os.mkdir(os.path.join(self.harness.review, "docs", "empty"))
        self.refused(["u2", "u3"], store.FolderChanged)

    def test_a_file_replaced_by_a_link_to_the_same_bytes_changes_the_hash_and_the_rerun_is_refused(self):
        # SOL-HW-REVIEW-KIT.C7: a review folder whose hash differs from the recorded one is refused
        path = os.path.join(self.harness.review, "docs", "guide.md")
        elsewhere = os.path.join(self.harness.base, "guide-copy.md")
        with open(path, "rb") as handle, open(elsewhere, "wb") as copy:
            copy.write(handle.read())
        os.remove(path)
        os.symlink(elsewhere, path)
        self.refused(["u2", "u3"], store.FolderChanged)

    def test_no_names_is_refused(self):
        # SOL-HW-REVIEW-KIT.C7: given the names of units to run again
        self.assertIn("no unit is named", self.refused([], store.NothingToRerun))

    def test_a_declaration_that_no_longer_gives_the_recorded_path_is_refused(self):
        # SOL-HW-REVIEW-KIT.C7: a rerun rebuilds the recorded path
        raw = fx.declaration_dict()
        raw["schema"]["tables"][0]["verdicts"].append("n/a")
        other = fx.Harness(self, raw=raw, base=self.harness.base)
        other.new_stub()
        with self.assertRaises(store.PlanChanged):
            other.again(["u2", "u3"])
        self.assertEqual(other.executor.calls, [])

    def test_a_missing_or_damaged_record_is_refused_naming_the_file(self):
        # SOL-HW-REVIEW-KIT.C7: a rerun reads the recorded path
        path = os.path.join(self.harness.out, store.RECORD_NAME)
        for content, why in (("{", "cannot be read"), ("[]", "is not an object"),
                             (json.dumps({"version": 1}), "lacks `review_hash`")):
            with self.subTest(why=why):
                with open(path, "w") as handle:
                    handle.write(content)
                with self.assertRaises(store.RecordUnreadable) as raised:
                    self.harness.again(["u2", "u3"])
                self.assertIn(path, str(raised.exception))
                self.assertIn(why, str(raised.exception))
        os.unlink(path)
        with self.assertRaises(store.RecordUnreadable) as raised:
            self.harness.again(["u2", "u3"])
        self.assertIn("does not exist", str(raised.exception))
        self.assertEqual(self.harness.executor.calls, [])


class FreshRunAndLockTests(unittest.TestCase):
    def test_a_fresh_run_refuses_an_output_folder_that_already_holds_a_record(self):
        # SOL-HW-REVIEW-KIT.C7: a fresh run refuses an output folder that already holds a record
        harness = fx.Harness(self)
        harness.fresh()
        before = read(os.path.join(harness.out, store.RECORD_NAME))
        harness.new_stub()
        with self.assertRaises(store.OutputHasRecord) as raised:
            harness.fresh()
        self.assertIn(harness.out, str(raised.exception))
        self.assertIn("name the units to run again", str(raised.exception))
        self.assertEqual(harness.executor.calls, [])
        self.assertEqual(read(os.path.join(harness.out, store.RECORD_NAME)), before)
        self.assertFalse(os.path.exists(os.path.join(harness.out, store.LOCK_NAME)))

    def test_the_output_folder_holds_a_lock_while_a_run_is_in_it(self):
        # SOL-HW-REVIEW-KIT.C7: the output folder holds a lock while a run is in it
        seen = {}

        class Watching(ex.StubExecutor):
            def execute(inner, call):
                lock = os.path.join(harness.out, store.LOCK_NAME)
                seen.setdefault(call.label, os.path.exists(lock))
                if call.label == "G1.r1.a1":
                    with self.assertRaises(store.OutputInUse) as raised:
                        with store.RunLock(harness.out):
                            pass
                    seen["refusal"] = str(raised.exception)
                    seen["still"] = os.path.exists(lock)
                return super().execute(call)

        harness = fx.Harness(self, executor_class=Watching)
        harness.fresh()
        self.assertTrue(all(seen[label] for label in ("root", "G1.r1.a1", "G2.r1.a1", "G3.r1.a1")))
        self.assertTrue(seen["still"])
        self.assertIn("in use by another run", seen["refusal"])
        self.assertFalse(os.path.exists(os.path.join(harness.out, store.LOCK_NAME)))

    def test_a_second_run_in_a_locked_folder_is_refused_without_starting_a_session(self):
        # SOL-HW-REVIEW-KIT.C7: the output folder holds a lock while a run is in it
        harness = fx.Harness(self)
        with store.RunLock(harness.out):
            with self.assertRaises(store.OutputInUse):
                harness.fresh()
            self.assertEqual(harness.executor.calls, [])
            harness.new_stub()
            with self.assertRaises(store.OutputInUse):
                harness.again(["u1"])
            self.assertEqual(harness.executor.calls, [])

    def test_the_lock_is_released_when_a_run_fails(self):
        # SOL-HW-REVIEW-KIT.C7: the output folder holds a lock while a run is in it
        harness = fx.Harness(self, root=ex.Reply(exit_code=1, is_error=True, text="boom"))
        with self.assertRaises(scheduler.RootFailed):
            harness.fresh()
        self.assertFalse(os.path.exists(os.path.join(harness.out, store.LOCK_NAME)))
        harness.root_reply = None
        harness.new_stub()
        harness.fresh()  # no record was written, so the folder is free for a fresh run
        self.assertTrue(store.holds_record(harness.out))

    def test_the_plan_is_written_before_the_first_session_and_the_record_after_the_last(self):
        # SOL-HW-REVIEW-KIT.C7: the output folder holds the plan record and the run record
        order = []

        class Watching(ex.StubExecutor):
            def execute(inner, call):
                order.append((call.label, os.path.exists(os.path.join(harness.out, store.PLAN_NAME)),
                              os.path.exists(os.path.join(harness.out, store.RECORD_NAME))))
                return super().execute(call)

        harness = fx.Harness(self, executor_class=Watching)
        harness.fresh()
        self.assertTrue(all(plan and not record for _, plan, record in order))
        self.assertTrue(store.holds_record(harness.out))
        with open(os.path.join(harness.out, store.PLAN_NAME)) as handle:
            self.assertEqual(planner.Plan.from_dict(json.load(handle)), harness.plan)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_atomic_write_leaves_the_old_file_and_no_partial_when_it_fails(self):
        # SOL-HW-REVIEW-KIT.C7: the record is written whole or not at all
        path = os.path.join(self.tmp.name, "sub", "record.json")
        store.atomic_write_json(path, {"a": 1})
        with self.assertRaises(TypeError):
            store.atomic_write_json(path, {"a": object()})
        with open(path) as handle:
            self.assertEqual(json.load(handle), {"a": 1})
        self.assertEqual(os.listdir(os.path.dirname(path)), ["record.json"])
        store.atomic_write_json(path, {"é": "ü"})
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), {"é": "ü"})

    def test_folder_hash_follows_content_names_and_additions_only(self):
        # SOL-HW-REVIEW-KIT.C7: a review folder whose hash differs from the recorded one
        folder = fx.review_folder(os.path.join(self.tmp.name, "r"))
        same = store.folder_hash(folder)
        self.assertEqual(store.folder_hash(folder), same)
        fx.write(folder, "docs/guide.md", "different")
        changed = store.folder_hash(folder)
        self.assertNotEqual(changed, same)
        os.rename(os.path.join(folder, "docs", "guide.md"), os.path.join(folder, "docs", "renamed.md"))
        self.assertNotIn(store.folder_hash(folder), (same, changed))
        copy = fx.review_folder(os.path.join(self.tmp.name, "copy"))
        self.assertEqual(store.folder_hash(copy), same)

    def test_folder_hash_holds_directories_and_links_to_directories(self):
        # SOL-HW-REVIEW-KIT.C7: a review folder whose hash differs from the recorded one
        folder = fx.review_folder(os.path.join(self.tmp.name, "r"))
        plain = store.folder_hash(folder)
        os.mkdir(os.path.join(folder, "empty"))
        empty = store.folder_hash(folder)
        self.assertNotEqual(empty, plain)
        os.rmdir(os.path.join(folder, "empty"))
        self.assertEqual(store.folder_hash(folder), plain)
        os.symlink(os.path.join(folder, "docs"), os.path.join(folder, "dirlink"))
        linked = store.folder_hash(folder)
        self.assertNotIn(linked, (plain, empty))
        os.remove(os.path.join(folder, "dirlink"))
        os.symlink(os.path.join(folder, "nowhere"), os.path.join(folder, "dirlink"))
        self.assertNotEqual(store.folder_hash(folder), linked)

    def test_a_stale_lock_is_refused_with_what_to_do(self):
        # SOL-HW-REVIEW-KIT.C7: the output folder holds a lock while a run is in it
        out = os.path.join(self.tmp.name, "out")
        os.makedirs(out)
        with open(os.path.join(out, store.LOCK_NAME), "w") as handle:
            handle.write("{}")
        with self.assertRaises(store.OutputInUse) as raised:
            with store.RunLock(out):
                pass
        self.assertIn(os.path.join(out, store.LOCK_NAME), str(raised.exception))
        self.assertIn("remove", str(raised.exception))
        self.assertTrue(os.path.exists(os.path.join(out, store.LOCK_NAME)))


if __name__ == "__main__":
    unittest.main()
