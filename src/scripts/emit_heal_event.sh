#!/usr/bin/env bash
# emit_heal_event.sh — Sourceable shell helper for ADR-084 self-heal events.
# Appends a JSONL event to state/self_heal_events.jsonl.
# Usage: source this file, then call emit_heal_event <source> <category> <severity> <message>

emit_heal_event() {
    local source="$1" category="$2" severity="$3" message="$4"
    local runtime_dir="${AUGUR_STATE:-${AUGUR_RUNTIME:-}}"
    if [ -z "$runtime_dir" ]; then
        runtime_dir="$(
            python3 - <<'PY' 2>/dev/null
from pathlib import Path

try:
    from src.config.paths import get_runtime_dir
    print(get_runtime_dir())
except Exception:
    import os
    if os.uname().sysname == "Darwin":
        print(Path.home() / "Library" / "Application Support" / "Augur" / "state")
    else:
        print(Path.home() / ".local" / "state" / "augur")
PY
        )"
    fi
    local event_file="${runtime_dir}/self_heal_events.jsonl"
    mkdir -p "$runtime_dir" 2>/dev/null
    # Escape double quotes in message for valid JSON
    message="${message//\"/\\\"}"
    local tmp_file
    tmp_file="$(mktemp "${event_file}.XXXXXX" 2>/dev/null)" || {
        # If mktemp fails, fall back to direct append
        printf '{"timestamp":"%s","source":"%s","category":"%s","severity":"%s","message":"%s","pid":%d}\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" "$source" "$category" "$severity" "$message" $$ \
            >> "$event_file" 2>/dev/null
        return 0
    }
    printf '{"timestamp":"%s","source":"%s","category":"%s","severity":"%s","message":"%s","pid":%d}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" "$source" "$category" "$severity" "$message" $$ \
        > "$tmp_file" 2>/dev/null
    cat "$tmp_file" >> "$event_file" 2>/dev/null
    rm -f "$tmp_file" 2>/dev/null
    return 0
}
