"""The system prompt a session used, read from the transcript Claude Code writes for the session.

The start report of a session carries no system prompt. Claude Code records the
request shape of every session in a transcript file named by the session's
identifier, in a folder named for the folder the session ran in; the record of type
`api-request-shape` holds the system prompt as a list of text blocks. A fork's
prompt is read from the fork's own transcript and compared with its parent's.
"""

from __future__ import annotations

import json
import os
import re
from typing import List, Optional

SHAPE_RECORD = "api-request-shape"
TRANSCRIPT_SUFFIX = ".jsonl"
PROJECTS_ENV = "CLAUDE_CONFIG_DIR"


class TranscriptMissing(Exception):
    """The transcript of a session, or the request shape in it, cannot be found; the text says where it looked."""


def projects_root(environ: Optional[dict] = None) -> str:
    environ = os.environ if environ is None else environ
    base = environ.get(PROJECTS_ENV) or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(base, "projects")


def folder_name(cwd: str) -> str:
    """The name of the transcript folder for sessions run in `cwd`: every character but a letter or digit becomes a hyphen."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(cwd))


def find_transcript(session_id: str, cwd: str, root: Optional[str] = None) -> str:
    """The transcript file of the session, in the folder for `cwd` or else in any folder under the projects root."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id or ""):
        raise TranscriptMissing(f"the session identifier {session_id!r} is not one that names a transcript file")
    root = root or projects_root()
    name = session_id + TRANSCRIPT_SUFFIX
    direct = os.path.join(root, folder_name(cwd), name)
    if os.path.isfile(direct):
        return direct
    try:
        folders = sorted(os.listdir(root))
    except OSError as error:
        raise TranscriptMissing(f"the transcripts folder {root} cannot be read ({error}); name the folder Claude Code writes "
                                f"its transcripts to in {PROJECTS_ENV}")
    for folder in folders:
        found = os.path.join(root, folder, name)
        if os.path.isfile(found):
            return found
    raise TranscriptMissing(f"no transcript {name} under {root}; the session ran in {cwd}, so Claude Code should have "
                            f"written {direct}")


def system_prompts(path: str, session_id: str) -> List[str]:
    """The system prompt of each distinct request shape the transcript records for the session, in order: the shape's
    system text blocks joined by a line break."""
    found: List[str] = []
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
    except (OSError, UnicodeDecodeError) as error:
        raise TranscriptMissing(f"the transcript {path} cannot be read ({error})")
    for line in lines:
        if SHAPE_RECORD not in line:
            continue
        try:
            record = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(record, dict) or record.get("type") != SHAPE_RECORD or record.get("sessionId") != session_id:
            continue
        shape = record.get("shape")
        blocks = shape.get("system") if isinstance(shape, dict) else None
        if not isinstance(blocks, list):
            raise TranscriptMissing(f"the request shape in {path} has no `system` list; the transcript format has changed")
        texts = [block.get("text") for block in blocks if isinstance(block, dict) and block.get("type") == "text"]
        if not texts or not all(isinstance(text, str) for text in texts):
            raise TranscriptMissing(f"the request shape in {path} holds no system text blocks; the transcript format has changed")
        prompt = "\n".join(texts)
        if prompt not in found:
            found.append(prompt)
    return found


def session_system_prompt(session_id: str, cwd: str, root: Optional[str] = None) -> str:
    """The one system prompt the session used. A transcript with no request shape, or with more than one distinct system
    prompt for the session, raises TranscriptMissing saying so."""
    path = find_transcript(session_id, cwd, root)
    prompts = system_prompts(path, session_id)
    if not prompts:
        raise TranscriptMissing(f"the transcript {path} holds no {SHAPE_RECORD} record for session {session_id}")
    if len(prompts) > 1:
        raise TranscriptMissing(f"the transcript {path} records {len(prompts)} different system prompts for session {session_id}")
    return prompts[0]
