"""Synthetic declarations and review folders for the review kit's tests: generic names, temporary folders, no real review."""

from __future__ import annotations

import copy
import json
import os
import struct
import zlib
from typing import Any, Dict, Optional

TEMPLATE = "Judge these items of {area}:\n{items}\n\n{schema}"

BASE: Dict[str, Any] = {
    "artefacts": {
        "guide.md": {"kind": "text", "source": "docs/guide.md"},
        "facts.txt": {"kind": "extract", "source": "extracts/facts.txt", "producer": "make_facts"},
        "view_a.png": {"kind": "image", "source": "views/view_a.png"},
        "view_b.png": {"kind": "image", "source": "views/view_b.png"},
    },
    "templates": {"t": TEMPLATE},
    "units": {
        "u1": {"items": ["i1", "i2"], "template": "t", "needs": ["guide.md", "view_a.png"],
               "expected_output_tokens": 400, "values": {"area": "alpha"}},
        "u2": {"items": ["j1"], "template": "t", "needs": ["guide.md", "facts.txt"], "couples_with": ["u3"],
               "expected_output_tokens": 300, "values": {"area": "beta"}},
        "u3": {"items": ["k1", "k2"], "template": "t", "needs": ["view_b.png"], "expected_output_tokens": 200,
               "stakes": "high", "values": {"area": "gamma"}},
        "u4": {"items": ["m1"], "template": "t", "needs": ["guide.md"], "expected_output_tokens": 100,
               "values": {"area": "delta"}},
    },
    "schema": {
        "tables": [
            {"name": "Verdicts", "columns": ["Item", "Verdict", "Note"], "key": "Item", "verdict_column": "Verdict",
             "verdicts": ["pass", "fail", "cannot judge"]},
            {"name": "Findings", "columns": ["No", "Item", "Detail"], "key": "Item", "numeric": ["No"]},
        ],
        "findings": {"table": "Findings", "number": "No", "citations": [["Verdicts", "Note"]],
                     "citation": "finding (?P<number>\\d+)"},
    },
    "deny": ["*seed*", "private/*"],
    "budget": {"wall_s": 600, "usd": 5.0, "context_tokens": 100000},
}


def declaration_dict(**changes: Any) -> Dict[str, Any]:
    """A copy of the base declaration; a change names a top-level key and gives its replacement."""
    found = copy.deepcopy(BASE)
    found.update(copy.deepcopy(changes))
    return found


def keyed_declaration_dict() -> Dict[str, Any]:
    """The base declaration with a verdict table whose key is two columns, the item then a part of it."""
    found = declaration_dict()
    found["schema"]["tables"][0] = {"name": "Verdicts", "columns": ["Item", "Part", "Verdict", "Note"],
                                    "key": ["Item", "Part"], "verdict_column": "Verdict",
                                    "verdicts": ["pass", "fail", "cannot judge"]}
    return found


def declaration_text(raw: Optional[Dict[str, Any]] = None) -> str:
    return json.dumps(raw if raw is not None else BASE, indent=1)


def png(width: int, height: int, shade: int = 0) -> bytes:
    """A valid PNG of the size, one grey shade."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    rows = b"".join(b"\x00" + bytes([shade]) * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def write(folder: str, relative: str, data: Any) -> str:
    path = os.path.join(folder, relative)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8"})) as handle:
        handle.write(data)
    return path


def review_folder(folder: str, guide: str = None) -> str:
    """The files the base declaration names, in a review folder."""
    write(folder, "docs/guide.md", guide if guide is not None else "# Guide\n" + "Check each item against the views. " * 200)
    write(folder, "extracts/facts.txt", "fact one\nfact two\n" * 50)
    write(folder, "views/view_a.png", png(300, 200, 10))
    write(folder, "views/view_b.png", png(560, 280, 20))
    return folder


# --- A review run over the stub ----------------------------------------------------------------

import json as _json  # noqa: E402
import tempfile  # noqa: E402

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TOOLS_DIR not in __import__("sys").path:
    __import__("sys").path.insert(0, TOOLS_DIR)

from review_kit import catalogue, decl, messages, planner, scheduler, store  # noqa: E402
from review_kit import executor as ex  # noqa: E402


class FakeClock:
    """A clock that moves only when slept on, and keeps the waits it was asked for."""

    def __init__(self):
        self.t = 1000.0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


def good_answer(declaration, units, verdict="pass"):
    items = [item for unit in units for item in declaration.units[unit].items]
    return {"tables": {"Verdicts": [{"Item": item, "Verdict": verdict, "Note": ""} for item in items], "Findings": []}}


class Harness:
    """A declaration, a review folder, an output folder and a stub, ready to run.

    `script` maps a node id (such as `G1.r1.a1`) to the Reply, or list of Replies, the stub plays for it; any other fork
    answers every item with a pass, and the shared context answers its acknowledgement.
    """

    def __init__(self, test, raw=None, script=None, bound=4, attempts=3, concurrency=None, policy=None, replicas=1,
                 variants=(), root=None, executor_class=None, base=None, out_name="out"):
        if base is None:
            self.tmp = tempfile.TemporaryDirectory()
            test.addCleanup(self.tmp.cleanup)
            base = self.tmp.name
        self.base = base
        self.review = review_folder(os.path.join(base, "review"))
        self.out = os.path.join(base, out_name)
        self.raw = raw or declaration_dict()
        self.script = dict(script or {})
        self.root_reply = root
        self.clock = FakeClock()
        self.policy = policy or ex.RetryPolicy(retries=2, first_s=10, factor=3, longest_s=100)
        self.attempts, self.concurrency, self.bound = attempts, concurrency, bound
        self.replicas, self.variants = replicas, variants
        self.executor_class = executor_class or ex.StubExecutor
        self.build()

    def build(self):
        self.declaration = decl.parse(_json.dumps(self.raw), "caller.json")
        found = catalogue.admit(self.declaration, self.review, results_folder=self.out)
        self.shared = messages.shared_context(found)
        self.spec = messages.make_spec(self.declaration, ("Read", "Glob"), self.review, "claude-sonnet-5-5")
        self.plan = planner.make_plan(self.declaration, found, self.shared, self.spec, bound=self.bound, cli_version="9.9.9",
                                      tool_commit="abc1234", replicas=self.replicas, variants=self.variants)
        self.executor = self.executor_class(replies=self.reply, clock=self.clock, policy=self.policy)
        self.scheduler = scheduler.Scheduler(self.executor, self.clock, self.concurrency, self.attempts)

    def reply(self, call, number):
        if call.label == "root":
            return self.root_reply or ex.Reply(text=messages.ACK, write=100)
        if call.label in self.script:
            return self.script[call.label]
        group = next(g for g in self.plan.groups if g.id == call.label.split(".")[0])
        return ex.Reply(structured=good_answer(self.declaration, group.units), text="done")

    def fresh(self):
        return scheduler.run_review(self.scheduler, self.declaration, self.plan, self.shared, self.spec, self.out, self.review)

    def again(self, names):
        return scheduler.rerun_review(self.scheduler, self.declaration, self.plan, self.shared, self.spec, self.out,
                                      self.review, names)

    def new_stub(self, script=None):
        """A stub with no calls yet and a script of its own, as a later run of the same review would have."""
        self.script = dict(script or {})
        self.executor = self.executor_class(replies=self.reply, clock=self.clock, policy=self.policy)
        self.scheduler = scheduler.Scheduler(self.executor, self.clock, self.concurrency, self.attempts)
