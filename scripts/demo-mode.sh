#!/usr/bin/env bash
# demo-mode.sh — Atomically toggle demo mode settings across all Claude Code instances.
# Usage: scripts/demo-mode.sh [on|off|status]
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE_ROOT="$(python3 "$PROJECT_ROOT/scripts/resolve-runtime-dir.py")"
RUNTIME_DIR="$STATE_ROOT/demo"
STATE_FILE="$RUNTIME_DIR/state.json"
BACKUP_GLOBAL="$RUNTIME_DIR/settings-backup-global.json"
BACKUP_LOCAL="$RUNTIME_DIR/settings-backup-local.json"

GLOBAL_SETTINGS="$HOME/.claude/settings.json"
LOCAL_SETTINGS="$PROJECT_ROOT/.claude/settings.local.json"
BACKUP_STATUSLINE="$RUNTIME_DIR/statusline-backup.json"

# ── Helpers ─────────────────────────────────────────────────────────────────

ensure_runtime_dir() {
  mkdir -p "$RUNTIME_DIR"
}

read_state() {
  if [[ -f "$STATE_FILE" ]]; then
    jq -r '.active // false' "$STATE_FILE" 2>/dev/null || echo "false"
  else
    echo "false"
  fi
}

backup_file() {
  local src="$1" dst="$2"
  if [[ -f "$src" ]]; then
    cp "$src" "$dst"
  else
    echo '{}' > "$dst"
  fi
}

merge_json() {
  # Deep merge $2 into $1, output to $1
  local target="$1" overlay="$2"
  if [[ -f "$target" ]]; then
    local merged
    merged=$(jq -s '.[0] * .[1]' "$target" "$overlay")
    echo "$merged" > "$target"
  else
    cp "$overlay" "$target"
  fi
}

merge_json_preserve() {
  # Merge overlay into target preserving existing keys (only add new ones)
  # Used for local settings where we don't want to overwrite permissions etc.
  local target="$1" overlay="$2"
  if [[ -f "$target" ]]; then
    local merged
    merged=$(jq -s '.[1] * .[0]' "$target" "$overlay")
    # Now add overlay keys that are missing from target
    merged=$(jq -s '.[0] * .[1]' "$target" "$overlay")
    echo "$merged" > "$target"
  else
    cp "$overlay" "$target"
  fi
}

# ── Demo ON ─────────────────────────────────────────────────────────────────

demo_on() {
  local current
  current=$(read_state)
  if [[ "$current" == "true" ]]; then
    echo "Demo mode is already ON."
    echo "Run 'scripts/demo-mode.sh status' for details."
    return 0
  fi

  ensure_runtime_dir

  # Step 1: Back up current settings
  backup_file "$GLOBAL_SETTINGS" "$BACKUP_GLOBAL"
  backup_file "$LOCAL_SETTINGS" "$BACKUP_LOCAL"

  # Step 2: Apply global demo settings (fast mode + simplified status line)
  local global_overlay
  global_overlay=$(mktemp)
  cat > "$global_overlay" <<'GLOBAL_JSON'
{
  "preferFastMode": true,
  "statusLine": {
    "type": "command",
    "command": "input=$(cat); dir_name=$(basename $(echo \"$input\" | jq -r '.workspace.current_dir')); used=$(echo \"$input\" | jq -r '.context_window.used_percentage // empty'); if [ -n \"$used\" ] && [ \"$used\" != \"null\" ]; then printf \"%s | %s%%\" \"$dir_name\" \"$used\"; else printf \"%s\" \"$dir_name\"; fi"
  }
}
GLOBAL_JSON
  merge_json "$GLOBAL_SETTINGS" "$global_overlay"
  rm -f "$global_overlay"

  # Step 3: Apply project-level demo settings (merge, preserving existing keys like permissions)
  local local_overlay
  local_overlay=$(mktemp)
  cat > "$local_overlay" <<'LOCAL_JSON'
{
  "MAX_THINKING_TOKENS": 8000,
  "DISABLE_NONESSENTIAL_MODEL_CALLS": "1",
  "showTurnDuration": false,
  "spinnerTipsEnabled": false,
  "CLAUDE_CODE_AUTOCOMPACT_PCT_OVERRIDE": 60
}
LOCAL_JSON
  merge_json "$LOCAL_SETTINGS" "$local_overlay"
  rm -f "$local_overlay"

  # Step 4: Write state file
  cat > "$STATE_FILE" <<STATE_JSON
{
  "active": true,
  "activated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "components": ["fast_mode", "reduced_thinking", "auto_compact", "simplified_statusline"]
}
STATE_JSON

  echo "✦ Demo mode ON"
  echo ""
  echo "  Applied:"
  echo "    ✓ Fast mode enabled (global)"
  echo "    ✓ Simplified status line (project name + context %)"
  echo "    ✓ Thinking tokens reduced to 8000"
  echo "    ✓ Non-essential model calls disabled"
  echo "    ✓ Turn duration + spinner tips hidden"
  echo "    ✓ Auto-compact threshold at 60%"
  echo ""
  echo "  Backups saved to: state/demo/"
  echo "  Restore with: scripts/demo-mode.sh off"
}

# ── Demo OFF ────────────────────────────────────────────────────────────────

demo_off() {
  local current
  current=$(read_state)
  if [[ "$current" != "true" ]]; then
    echo "Demo mode is already OFF."
    return 0
  fi

  # Step 1: Restore global settings from backup
  if [[ -f "$BACKUP_GLOBAL" ]]; then
    cp "$BACKUP_GLOBAL" "$GLOBAL_SETTINGS"
  fi

  # Step 2: Restore project-level settings from backup
  if [[ -f "$BACKUP_LOCAL" ]]; then
    local backup_content
    backup_content=$(cat "$BACKUP_LOCAL")
    if [[ "$backup_content" == "{}" ]]; then
      # No original local settings — remove the file we created
      rm -f "$LOCAL_SETTINGS"
    else
      cp "$BACKUP_LOCAL" "$LOCAL_SETTINGS"
    fi
  fi

  # Step 3: Clean up state and backups
  rm -f "$STATE_FILE" "$BACKUP_GLOBAL" "$BACKUP_LOCAL"

  echo "✦ Demo mode OFF"
  echo ""
  echo "  Restored:"
  echo "    ✓ Global settings restored from backup"
  echo "    ✓ Project settings restored from backup"
  echo "    ✓ State and backup files cleaned up"
}

# ── Demo STATUS ─────────────────────────────────────────────────────────────

demo_status() {
  local current
  current=$(read_state)
  if [[ "$current" == "true" ]]; then
    echo "✦ Demo mode: ON"
    echo ""
    if [[ -f "$STATE_FILE" ]]; then
      local activated components
      activated=$(jq -r '.activated_at // "unknown"' "$STATE_FILE")
      components=$(jq -r '.components // [] | join(", ")' "$STATE_FILE")
      echo "  Activated: $activated"
      echo "  Components: $components"
    fi
    echo ""
    echo "  Global settings (fast mode):"
    if [[ -f "$GLOBAL_SETTINGS" ]]; then
      jq '{preferFastMode}' "$GLOBAL_SETTINGS" 2>/dev/null || echo "    (unable to read)"
    fi
    echo ""
    echo "  Project settings (demo overrides):"
    if [[ -f "$LOCAL_SETTINGS" ]]; then
      jq '.' "$LOCAL_SETTINGS" 2>/dev/null || echo "    (unable to read)"
    fi
  else
    echo "✦ Demo mode: OFF"
    echo ""
    echo "  Enable with: scripts/demo-mode.sh on"
  fi
}

# ── Main ────────────────────────────────────────────────────────────────────

case "${1:-toggle}" in
  on)     demo_on ;;
  off)    demo_off ;;
  status) demo_status ;;
  toggle)
    current=$(read_state)
    if [[ "$current" == "true" ]]; then
      demo_off
    else
      demo_on
    fi
    ;;
  *)
    echo "Usage: scripts/demo-mode.sh [on|off|status|toggle]"
    exit 1
    ;;
esac
