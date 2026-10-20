#!/usr/bin/env python3
"""A stand-in for the agent command line, for the review fan-out command's tests.

It plays what the real command line prints under --output-format stream-json
--verbose: a start report, the tool uses, and a result report whose cost, API
time and turn count are cumulative from the session it was resumed from. What it
plays is read from the JSON file named by STUB_SCENARIO, and every call it
receives is written as a file in the folder named by STUB_LOG, with its
arguments, working directory, the time it ran between and the names of the
environment variables it was given. It sleeps to show concurrency. A setup
session reads method.md unless the scenario's `setup.reads` says otherwise,
`setup.narration` lists content blocks it writes before its reads (each its own
event, or with the first read in one event when `setup.same_event` is set), and
`setup.attempts`, when given, lists what each successive start of the setup session overrides in `setup` (the last holds for any further start), and `setup.uses` lists tools it uses besides Read (a name, or an object with `name`, an `input` and `failed`, which gives the use an id and, when true, a failed tool result). Any session's scenario entry may
also hold `start_omit` and `result_omit` (fields left out of the start report and
the result report), `start_set` and `result_set` (fields given other values),
`read_inputs` (the raw input of each Read it makes, in place of `reads`),
`failed_reads` (paths it reads whose tool result is an error), `lines` (lines it
prints as they are, after its start report), `garbled` (bytes that are not UTF-8,
printed to its output and its error stream) and `no_result` (it prints no result
report and exits 0) and `raw_unicode` (its assistant and result lines carry non-ASCII
characters raw, as the real command line's JSON does). A call with no unit whose prompt lacks the setup session's token plays the scenario's `single` entry, when it has one, as a lone reviewer judging the whole review in one session. The scenario's `auth_stdout`, when given, is what `auth
status` prints in place of its report, and `auth` its exit status.
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
        if scenario.get("auth_garbled"):
            sys.stdout.buffer.write(b"\xff\xfe{\x80}\n")
        else:
            print(scenario["auth_stdout"] if "auth_stdout" in scenario else json.dumps({"loggedIn": scenario.get("auth", 0) == 0}))
        return scenario.get("auth", 0)
    prompt = flag(args, "-p")
    resume, forked = flag(args, "--resume"), "--fork-session" in args
    began = time.time()
    unit = re.search(r"UNIT=(\S+)", prompt)
    unit = unit.group(1) if unit else None
    setup = scenario.get("setup", {})
    base = {"cost": 0.0, "api_ms": 0, "turns": 0}
    if unit is None:
        outcome = dict(scenario["single"] if "single" in scenario and "SETUP-READ-COMPLETE" not in prompt else setup)
        if "attempts" in outcome and "SETUP-READ-COMPLETE" in prompt:
            counter = os.path.join(log, "attempts-setup")
            count = len(open(counter, encoding="utf-8").read().split()) if os.path.exists(counter) else 0
            with open(counter, "a", encoding="utf-8") as handle:
                handle.write("x\n")
            outcome = {**outcome, **outcome["attempts"][min(count, len(outcome["attempts"]) - 1)]}
        session = str(uuid.uuid4())
        text = outcome.get("answer", "SETUP-READ-COMPLETE")
        reads = outcome.get("reads", ["method.md"])
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
             "skills": scenario.get("skills", []), "slash_commands": scenario.get("slash_commands", []),
             "plugins": scenario.get("plugins", [{"name": "p", "path": "builtin"}])}
    start.update(outcome.get("start_set", {}))
    for key in outcome.get("start_omit", []):
        start.pop(key, None)
    print(json.dumps(start))
    for line in outcome.get("lines", []):
        print(line)
    if outcome.get("garbled"):
        sys.stdout.flush()
        sys.stdout.buffer.write(b"\xff\xfe garbled \x80\n")
        sys.stdout.buffer.flush()
        sys.stderr.buffer.write(b"\xff\xfe garbled \x80\n")
        sys.stderr.buffer.flush()
    inputs = outcome.get("read_inputs", [{"file_path": path} for path in reads + outcome.get("failed_reads", [])])
    uses = [{"type": "tool_use", "id": f"toolu_{number}", "name": "Read", "input": given} for number, given in enumerate(inputs)]
    failed = [use["id"] for use in uses[len(inputs) - len(outcome.get("failed_reads", [])):]] if outcome.get("failed_reads") else []
    for number, spec in enumerate(outcome.get("uses", [])):
        spec = {"name": spec} if isinstance(spec, str) else spec
        use = {"type": "tool_use", "name": spec["name"], "input": spec.get("input", {})}
        if "failed" in spec:
            use["id"] = f"toolu_use{number}"
            if spec["failed"]:
                failed.append(use["id"])
        uses.append(use)
    narration = outcome.get("narration", [])
    if narration and outcome.get("same_event"):
        print(json.dumps({"type": "assistant", "message": {"content": narration + uses[:1]}}))
        uses = uses[1:]
    else:
        for block in narration:
            print(json.dumps({"type": "assistant", "message": {"content": [block]}}))
    for use in uses:
        print(json.dumps({"type": "assistant", "message": {"content": [use]}}))
        if use.get("id") in failed:
            print(json.dumps({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": use["id"], "is_error": True, "content": "File does not exist."}]}}))
    if outcome.get("rate_limit"):
        print(json.dumps({"type": "result", "is_error": True, "result": "API Error: 429 rate limit exceeded",
                          "api_error_status": 429, "session_id": session}))
        return 1
    if outcome.get("login"):
        sys.stderr.write("Not logged in · Please run /login")
        print(json.dumps({"type": "result", "is_error": True, "result": "Please run /login", "api_error_status": 401,
                          "session_id": session}))
        return 1
    if outcome.get("prose"):
        print(json.dumps({"type": "result", "subtype": "success", "is_error": True, "result": outcome["prose"],
                          "session_id": session}))
        return 1
    if outcome.get("no_result"):
        return 0
    if outcome.get("exit"):
        sys.stderr.write(outcome.get("stderr", "the reviewer crashed"))
        return outcome["exit"]
    ascii_only = not outcome.get("raw_unicode")
    print(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}, ensure_ascii=ascii_only))
    report = {"type": "result", "subtype": "success", "is_error": False, "result": text, "session_id": session,
              "num_turns": base["turns"] + outcome.get("turns", 1),
              "duration_api_ms": base["api_ms"] + outcome.get("api_ms", 500),
              "total_cost_usd": round(base["cost"] + outcome.get("cost", 0.05), 6),
              "usage": {"input_tokens": outcome.get("fresh", 3), "output_tokens": outcome.get("generated", 100),
                        "cache_read_input_tokens": outcome.get("cache_read", 5000),
                        "cache_creation_input_tokens": outcome.get("cache_write", 200)}}
    report.update(outcome.get("result_set", {}))
    for key in outcome.get("result_omit", []):
        report.pop(key, None)
    print(json.dumps(report, ensure_ascii=ascii_only))
    return 0


if __name__ == "__main__":
    sys.exit(main())
