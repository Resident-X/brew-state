#!/usr/bin/env bash
# Sum a Claude Code session's own token usage, and its Agent-tool subagents'
# separately, since a start timestamp. Used by stage0-build Step 6 to log the
# `orchestrator` row.
#
# Usage: session-usage.sh <session-transcript.jsonl> <since-iso8601-ts>
#
# A transcript writes one line per streamed content block, so one API message
# appears several times under the same message.id; the last line per id carries
# the final usage and is the one counted. Subagent transcripts record only the
# output count at stream start, not the final one, so their output tokens and
# cost are a floor: reported as output_tokens_floor and cost_usd_floor. For an
# exact subagent total use the Agent tool result's own token count.
#
# Prices are USD per million tokens. Update the table when a model or price
# changes (source: platform.claude.com/docs/en/about-claude/pricing). A model
# missing from the table is reported with cost_usd null. Placeholder messages
# (model "<synthetic>") are not API calls and are skipped.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <session-transcript.jsonl> <since-iso8601-ts>" >&2
  exit 2
fi
transcript="$1"
since="$2"
[[ -f "$transcript" ]] || { echo "no such transcript: $transcript" >&2; exit 1; }
if ! [[ "$since" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$ ]]; then
  echo "since must be ISO 8601 with Z or an offset, e.g. 2026-10-02T13:52:43Z: got $since" >&2
  exit 2
fi

prices='{
  "claude-fable-5-1":  {"in": 10, "out": 50, "w5m": 12.5, "w1h": 20, "read": 0.25},
  "claude-opus-5-5":   {"in": 4,  "out": 20, "w5m": 5,    "w1h": 8,  "read": 0.20},
  "claude-sonnet-5-5": {"in": 2,  "out": 10, "w5m": 2.5,  "w1h": 4,  "read": 0.20},
  "claude-haiku-4-5":  {"in": 1,  "out": 5,  "w5m": 1.25, "w1h": 2,  "read": 0.10}
}'

summarise() {
  local floor="$1"
  shift
  jq -s --arg since "$since" --argjson prices "$prices" --argjson floor "$floor" '
    # Accepts Z or a +HH:MM / -HH:MM offset, with or without fractional seconds.
    def epoch:
      sub("\\.[0-9]+"; "")
      | capture("^(?<base>[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?<off>Z|[+-][0-9]{2}:[0-9]{2})$")
      | (.base + "Z" | fromdateiso8601)
        - (if .off == "Z" then 0
           else (.off[0:1] as $sign
                 | ((.off[1:3] | tonumber) * 3600 + (.off[4:6] | tonumber) * 60)
                 | if $sign == "-" then -. else . end)
           end);
    def price($m): $prices[$m] // $prices[($m | sub("-[0-9]{8}$"; ""))];
    ($since | epoch) as $from
    | [ .[]
        | select(.type == "assistant" and .message.usage != null and .message.id != null)
        | select(.message.model != "<synthetic>")
        | select((.timestamp | epoch) >= $from) ]
    | group_by(.message.id) | map(last)
    | map({
        model: .message.model,
        input_tokens: (.message.usage.input_tokens // 0),
        w1h: (.message.usage.cache_creation.ephemeral_1h_input_tokens // 0),
        w5m: (.message.usage.cache_creation.ephemeral_5m_input_tokens
              // .message.usage.cache_creation_input_tokens // 0),
        cache_read_input_tokens: (.message.usage.cache_read_input_tokens // 0),
        output_tokens: (.message.usage.output_tokens // 0)
      })
    | group_by(.model)
    | map(
        (.[0].model) as $m
        | {
            model: $m,
            messages: length,
            input_tokens: (map(.input_tokens) | add),
            cache_creation_input_tokens: (map(.w1h + .w5m) | add),
            cache_read_input_tokens: (map(.cache_read_input_tokens) | add),
            output_tokens: (map(.output_tokens) | add),
            w1h: (map(.w1h) | add),
            w5m: (map(.w5m) | add)
          }
        | . + {cost_usd: (price($m) as $p
            | if $p == null then null
              else ((.input_tokens * $p.in + .w5m * $p.w5m + .w1h * $p.w1h
                     + .cache_read_input_tokens * $p.read + .output_tokens * $p.out) / 1e6)
              end)}
        | del(.w1h, .w5m)
        | if $floor then
            . + {output_tokens_floor: .output_tokens, cost_usd_floor: .cost_usd}
            | del(.output_tokens, .cost_usd)
          else . end)
  ' "$@"
}

echo "== orchestrator (this session's own turns) =="
summarise false "$transcript"

subdir="${transcript%.jsonl}/subagents"
shopt -s nullglob
subs=("$subdir"/agent-*.jsonl)
echo "== Agent-tool subagents (${#subs[@]} transcripts) =="
if ((${#subs[@]})); then
  summarise true "${subs[@]}"
else
  echo "[]"
fi
