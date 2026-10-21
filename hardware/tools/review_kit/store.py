"""The review folder and the output folder as files: atomic JSON writes, the run lock, the record, and the refusals about them.

The output folder holds the plan record, the run record and the saved streams. A
fresh run refuses an output folder that already holds a record; a run holds a lock
in the output folder while it is in it, so two runs never share one. A rerun reads
the record back and is refused for a unit the review does not have, for leaving
out a unit whose last run failed, and for a review folder whose hash differs from
the one recorded.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from typing import Any, Dict, Optional, Sequence

PLAN_NAME, RECORD_NAME, LOCK_NAME = "plan.json", "record.json", "run.lock"
RECORD_VERSION = 1


class StoreRefusal(Exception):
    """A run the output or review folder does not allow; the text names the cause and what to do."""


class OutputHasRecord(StoreRefusal):
    pass


class OutputInUse(StoreRefusal):
    pass


class RecordUnreadable(StoreRefusal):
    pass


class UnknownUnit(StoreRefusal):
    pass


class FailedUnitLeftOut(StoreRefusal):
    pass


class FolderChanged(StoreRefusal):
    pass


class NothingToRerun(StoreRefusal):
    pass


class PlanChanged(StoreRefusal):
    pass


def atomic_write_json(path: str, content: Any) -> None:
    """The file whole or not at all: written beside it, flushed to disk, then renamed over it."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".part-", suffix=".json", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump(content, out, indent=1, ensure_ascii=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def folder_hash(folder: str) -> str:
    """The hash of a folder's content: every file's relative path and bytes, in order of path, and every link's target."""
    digest = hashlib.sha256()
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(root, name)
            relative = os.path.relpath(path, folder).replace(os.sep, "/")
            digest.update(relative.encode("utf-8") + b"\0")
            if os.path.islink(path) and not os.path.exists(path):
                digest.update(b"link:" + os.readlink(path).encode("utf-8"))
            else:
                with open(path, "rb") as handle:
                    for chunk in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(chunk)
            digest.update(b"\0")
    return digest.hexdigest()


def holds_record(out: str) -> bool:
    return os.path.exists(os.path.join(out, RECORD_NAME))


def check_fresh(out: str) -> None:
    if holds_record(out):
        raise OutputHasRecord(f"the output folder {out} already holds a record ({RECORD_NAME}); use a new output folder, or "
                              "name the units to run again")


class RunLock:
    """The lock a run holds in the output folder while it is in it, released when the run ends however it ends."""

    def __init__(self, out: str, now: float = 0.0):
        self.out, self.path, self.now, self.held = out, os.path.join(out, LOCK_NAME), now, False

    def __enter__(self) -> "RunLock":
        os.makedirs(self.out, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise OutputInUse(f"the output folder {self.out} is in use by another run ({LOCK_NAME} is held); wait for it to "
                              f"end, or remove {self.path} if no run is in the folder") from None
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid(), "started": self.now}, handle)
        self.held = True
        return self

    def __exit__(self, *exc) -> None:
        if self.held:
            try:
                os.unlink(self.path)
            except FileNotFoundError:
                pass
            self.held = False


def write_plan(out: str, plan: Dict[str, Any]) -> None:
    atomic_write_json(os.path.join(out, PLAN_NAME), plan)


def write_record(out: str, record: Dict[str, Any]) -> None:
    atomic_write_json(os.path.join(out, RECORD_NAME), record)


def read_record(out: str) -> Dict[str, Any]:
    """The run record, or a RecordUnreadable naming the file and what is wrong with it."""
    path = os.path.join(out, RECORD_NAME)
    try:
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
    except FileNotFoundError:
        raise RecordUnreadable(f"{path} does not exist, so there is no run to run units of again; start a fresh run") from None
    except (OSError, ValueError) as error:
        raise RecordUnreadable(f"{path} cannot be read ({error}); start a fresh run in a new output folder") from None
    problems = []
    if not isinstance(record, dict):
        problems.append("is not an object")
    else:
        if record.get("version") != RECORD_VERSION:
            problems.append(f"has version {record.get('version')!r}, not {RECORD_VERSION}")
        for key, kind in (("review_hash", str), ("plan", dict), ("units", dict), ("lanes", list), ("runs", list), ("nodes", list)):
            if not isinstance(record.get(key), kind):
                problems.append(f"lacks `{key}` as a {kind.__name__}")
    if problems:
        raise RecordUnreadable(f"{path} {'; '.join(problems)}; start a fresh run in a new output folder")
    return record


def check_rerun(record: Dict[str, Any], review_hash: str, names: Sequence[str], running: Optional[Sequence[str]] = None) -> None:
    """The refusals of a rerun, in order: nothing named, a name the review does not have, a unit whose last run failed
    left out, and a review folder whose hash differs from the recorded one. `running` is every unit the rerun will run: the
    named ones and the others of their groups, which run with them; it defaults to the named ones."""
    if not names:
        raise NothingToRerun("no unit is named to run again; name at least one, or start a fresh run")
    known = list(record["units"])
    for name in names:
        if name not in record["units"]:
            raise UnknownUnit(f"{name!r} is not a unit of this review (its units are {known}); name units from that list")
    running = set(running if running is not None else names) | set(names)
    failed = [unit for unit, state in record["units"].items() if state.get("failed") and unit not in running]
    if failed:
        raise FailedUnitLeftOut(f"unit {failed[0]} failed on its last run and is not named{'' if len(failed) == 1 else f' (nor are {failed[1:]})'}; "
                                "name it too, so the record does not keep a failed result as if it stood")
    if review_hash != record["review_hash"]:
        raise FolderChanged(f"the review folder's hash {review_hash[:12]} differs from the recorded {record['review_hash'][:12]}, "
                            "so the shared context would not be the same bytes; run the whole review again in a new output folder")


def check_same_path(record: Dict[str, Any], plan: Any) -> None:
    """A rerun follows the recorded path: the declaration must give the groups, specification and shared context recorded."""
    now, was = plan.to_dict(), record["plan"]
    for key, what in (("spec_digest", "session specification"), ("groups", "groups of units")):
        if now[key] != was.get(key):
            raise PlanChanged(f"the declaration now gives different {what} from the recorded run, so the recorded path cannot "
                              "be rebuilt; run the whole review again in a new output folder")
    if now["shared"]["prefix_sha"] != was.get("shared", {}).get("prefix_sha"):
        raise PlanChanged("the shared context now has a different prefix hash from the recorded run, so the cache cannot be "
                          "hit; run the whole review again in a new output folder")
