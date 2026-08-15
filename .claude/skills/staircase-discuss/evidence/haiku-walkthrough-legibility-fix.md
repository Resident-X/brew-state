# Haiku legibility walkthrough — staircase-discuss SKILL.md (SOL-WF-DISCUSSION-SKILL-LEGIBILITY-FIX.C1)

Demonstration evidence for SOL-WF-DISCUSSION-SKILL-LEGIBILITY-FIX.C1: a fresh
Haiku-class agent, given ONLY the amended `SKILL.md` and no other context or
CLI access, drove the full open → record → crystallize → resume → close
lifecycle and answered each of the three previously-broken points correctly from
the prose alone.

## Method

A fresh-context agent pinned to the Haiku model (the weak-agent legibility
canary) was handed only `.claude/skills/staircase-discuss/SKILL.md` and asked to
answer, from the prose alone (no commands, no outside knowledge), the seven
lifecycle steps — with items 3, 4, 5 targeting the three amended gaps.

## Result — the three amended gaps, answered from prose alone

**Gap 1 — `--project` scoping (item 3).** The canary correctly stated that
`--project` is accepted (and required) only on `wf ensure-capture`,
`wf submit-turn`, `wf list-sessions`, `wf resume-session`; that run-scoped/read
commands (`wf get`, `wf observe`, `show`, `query`, `trace`) reject it with
`unknown flag: --project`; and that crystallized intent hands off to
`/staircase-wf`, never a self-assembled `wf start` CLI call.

**Gap 2 — resume window default + `--limit` (item 4).** The canary correctly
stated that `resume-session` returns the most-recent 256 turns by default (the
turn store page size), that `--limit N` widens or narrows the tail window, and
that comparing `data.total_turns` against the window size reveals whether earlier
turns were elided.

**Gap 3 — legend + oldest-first ordering (item 5).** The canary correctly stated
that `data.window` is in oldest-first (ascending) order — the first entry is the
oldest turn, the last entry is the most recent — and that the meaning of an
enumerated value is read from the self-describing `data.legend`, not inferred.

## Verdict

`LEGIBILITY VERDICT: PASS` — items 3, 4, and 5 were all answerable unambiguously
from the amended prose alone. The full lifecycle (open/record/crystallize/resume/
close) was followed correctly end to end.
