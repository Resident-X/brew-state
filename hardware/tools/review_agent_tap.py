#!/usr/bin/env python3
"""A program that stands between the review fan-out command and the agent command line, and logs what each call did.

The fan-out command reports each session's time, tokens and cost but not the
documents a reviewer retrieved or the calls refused for a rate limit, and it
retries a refused call without keeping the refusal. This program is named in the
command's environment variable in place of the agent command line, runs the real
program named by REVIEW_TAP_AGENT with the arguments it was given, passes its
output and exit status on unchanged, and writes one JSON file for the call into
the folder named by REVIEW_TAP_LOG: when it began and ended, its session, whether
it resumed or forked a session, its exit status, whether the call was refused for
a rate limit, and each document it retrieved with whether the retrieval failed.
Only the layout review proof reads those files, so the command's own behaviour is
the same with or without it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_fan_out  # noqa: E402

AGENT_ENV = "REVIEW_TAP_AGENT"
LOG_ENV = "REVIEW_TAP_LOG"
#: The tool that retrieves a published document.
RETRIEVAL = "WebFetch"


def entry_of(args: List[str], began: float, ended: float, done: subprocess.CompletedProcess) -> Dict[str, Any]:
    """What the call did, as the log keeps it."""
    session = review_fan_out.parse_stream(done.stdout)
    result = session.result or {}
    failed = bool(result.get("is_error")) or done.returncode != 0
    refused = failed and (result.get("api_error_status") == 429
                          or bool(review_fan_out.RATE_PATTERN.search(done.stderr.strip())))
    retrievals = [{"url": str(given.get("url", "")), "failed": use in session.failed_tool_uses}
                  for name, given, use in session.tool_uses if name == RETRIEVAL]
    return {"began": began, "ended": ended, "session": session.id or result.get("session_id") or "",
            "resume": "--resume" in args, "fork": "--fork-session" in args, "exit": done.returncode,
            "rate_limited": refused, "retrievals": retrievals}


def main(argv: List[str]) -> int:
    program = os.environ.get(AGENT_ENV) or review_fan_out.DEFAULT_AGENT
    log = os.environ.get(LOG_ENV)
    if argv[:2] == ["auth", "status"] or not log:
        return subprocess.run([program, *argv]).returncode
    began = time.time()
    done = subprocess.run([program, *argv], capture_output=True, text=True, encoding="utf-8", errors="replace")
    ended = time.time()
    os.makedirs(log, exist_ok=True)
    with open(os.path.join(log, f"{began:.6f}-{uuid.uuid4()}.json"), "w", encoding="utf-8") as handle:
        json.dump(entry_of(argv, began, ended, done), handle)
    sys.stdout.write(done.stdout)
    sys.stderr.write(done.stderr)
    return done.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
