#!/usr/bin/env python3
"""A stand-in for the agent command line, for the review fan-out command's tests.

It plays what the real command line prints under --output-format stream-json
--verbose: a start report, the tool uses, and a result report whose cost, API
time and turn count are cumulative from the session it was resumed from. What it
plays is read from the JSON file named by STUB_SCENARIO, and every call it
receives is written as a file in the folder named by STUB_LOG, with its
arguments, working directory, the time it ran between and the names of the
environment variables it was given. It sleeps to show concurrency.
"""

import json
import os
import re
import sys
import time
import uuid

DEFAULT_TABLES = {"Verdicts": [{"Item": "A-1", "Verdict": "pass", "Rests on": "read"}], "Findings": []}


def flag(args, name):
    return args[args.index(name) + 1] if name in args else None


def main():
    args = sys.argv[1:]
    with open(os.environ["STUB_SCENARIO"], encoding="utf-8") as handle:
        scenario = json.load(handle)
    log = os.environ["STUB_LOG"]
    if args[:2] == ["auth", "status"]:
        print(json.dumps({"loggedIn": scenario.get("auth", 0) == 0}))
        return scenario.get("auth", 0)
    prompt = flag(args, "-p")
    resume, forked = flag(args, "--resume"), "--fork-session" in args
    began = time.time()
    unit = re.search(r"UNIT=(\S+)", prompt)
    unit = unit.group(1) if unit else None
    setup = scenario.get("setup", {})
    base = {"cost": 0.0, "api_ms": 0, "turns": 0}
    if unit is None:
        outcome = dict(setup)
        session = str(uuid.uuid4())
        text = outcome.get("answer", "SETUP-READ-COMPLETE")
        reads = outcome.get("reads", [])
        model = scenario.get("model", "model-a")
        tools = scenario.get("setup_tools", flag(args, "--tools").split(","))
    else:
        counter = os.path.join(log, f"attempts-{unit}")
        count = 0
        if os.path.exists(counter):
            with open(counter, encoding="utf-8") as handle:
                count = len(handle.read().split())
        with open(counter, "a", encoding="utf-8") as handle:
            handle.write("x\n")
        attempts = scenario.get("units", {}).get(unit, [{}])
        outcome = dict(attempts[min(count, len(attempts) - 1)])
        session = str(uuid.uuid4()) if forked else resume
        text = outcome.get("text", json.dumps({"tables": scenario.get("tables", {}).get(unit, DEFAULT_TABLES)}))
        reads = []
        model = scenario.get("fork_model", flag(args, "--model") or scenario.get("model", "model-a"))
        tools = scenario.get("fork_tools", flag(args, "--tools").split(","))
        base = {"cost": setup.get("cost", 0.05), "api_ms": setup.get("api_ms", 500), "turns": setup.get("turns", 1)}
        if not forked:
            base = {key: base[key] + outcome.get("before", {}).get(key, 0) for key in base}
    time.sleep(outcome.get("sleep", scenario.get("sleep", 0)))
    entry = {"args": args, "cwd": os.getcwd(), "unit": unit, "forked": forked, "resume": resume, "session": session,
             "began": began, "ended": time.time(), "env": sorted(k for k in os.environ if k.startswith("CLAUDE_CODE")),
             "prompt": prompt}
    with open(os.path.join(log, f"{began:.6f}-{uuid.uuid4()}.json"), "w", encoding="utf-8") as handle:
        json.dump(entry, handle)
    start = {"type": "system", "subtype": "init", "session_id": session, "cwd": scenario.get("cwd", os.getcwd()),
             "tools": tools, "mcp_servers": scenario.get("mcp_servers", []), "model": model,
             "skills": scenario.get("skills", []), "slash_commands": [],
             "plugins": scenario.get("plugins", [{"name": "p", "path": "builtin"}])}
    print(json.dumps(start))
    for path in reads:
        print(json.dumps({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": path}}]}}))
    if outcome.get("rate_limit"):
        print(json.dumps({"type": "result", "is_error": True, "result": "API Error: 429 rate limit exceeded",
                          "session_id": session}))
        return 1
    if outcome.get("exit"):
        sys.stderr.write(outcome.get("stderr", "the reviewer crashed"))
        return outcome["exit"]
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}))
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": text, "session_id": session,
                      "num_turns": base["turns"] + outcome.get("turns", 1),
                      "duration_api_ms": base["api_ms"] + outcome.get("api_ms", 500),
                      "total_cost_usd": round(base["cost"] + outcome.get("cost", 0.05), 6),
                      "usage": {"input_tokens": outcome.get("fresh", 3), "output_tokens": outcome.get("generated", 100),
                                "cache_read_input_tokens": outcome.get("cache_read", 5000),
                                "cache_creation_input_tokens": outcome.get("cache_write", 200)}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
