#!/bin/bash
# cleanup.sh — interactive disk cleanup. Asks y/n for every action, deletes only on confirmation.
# Default answer is N — press Enter to skip.
#
# Run scan.sh FIRST to identify what's worth deleting on your current system.
# Then edit this script's paths to match what scan.sh found.

set -u
freed=0

confirm() {
  local label="$1" target="$2" size_label="${3:-}"
  if [ ! -e "$target" ]; then
    printf "  [skip — not found] %s\n" "$label"
    ANSWER=N
    return
  fi
  local actual
  actual=$(du -sh "$target" 2>/dev/null | cut -f1)
  printf "\n>> %s\n   path: %s\n   size: %s\n   delete? [y/N] " \
    "$label" "$target" "${size_label:-$actual}"
  read -r reply </dev/tty
  case "$reply" in
    y|Y|yes|YES) ANSWER=Y ;;
    *)            ANSWER=N ;;
  esac
}

do_rm() {
  local target="$1"
  local kb
  kb=$(du -sk "$target" 2>/dev/null | cut -f1)
  rm -rf "$target"
  if [ ! -e "$target" ]; then
    printf "   ✓ deleted (%.1f MB)\n" "$(echo "$kb" | awk '{print $1/1024}')"
    freed=$((freed + kb))
  else
    printf "   ✗ failed — quit the app holding the file, or try with sudo\n"
  fi
}

bigsection() { printf "\n=========== %s ===========\n" "$1"; }

bigsection "STEP 1 / APFS LOCAL SNAPSHOTS"
echo "These usually account for the biggest hidden disk usage on macOS."
echo "Listing current snapshots..."
tmutil listlocalsnapshots / 2>/dev/null | sed 's/^/  /' || echo "  (none)"
printf "\nThin local snapshots aggressively (the big one)? [y/N] "
read -r reply </dev/tty
case "$reply" in
  y|Y|yes|YES)
    echo "  Running: sudo tmutil thinlocalsnapshots / 999999999999 4"
    sudo tmutil thinlocalsnapshots / 999999999999 4
    echo "  ✓ done"
    ;;
  *) echo "  skipped" ;;
esac

bigsection "STEP 2 / IDENTIFIED QUICK WINS"

confirm "Cursor state.vscdb backup (duplicate of live DB — quit Cursor first)" \
  "$HOME/Library/Application Support/Cursor/User/globalStorage/state.vscdb.backup"
[ "$ANSWER" = Y ] && do_rm "$HOME/Library/Application Support/Cursor/User/globalStorage/state.vscdb.backup"

confirm "Codex log SQLite (~1.4 GB of logs)" \
  "$HOME/.codex/logs_2.sqlite"
[ "$ANSWER" = Y ] && do_rm "$HOME/.codex/logs_2.sqlite"

confirm "Chrome on-device AI model (Chrome will redownload if used)" \
  "$HOME/Library/Application Support/Google/Chrome/OptGuideOnDeviceModel"
[ "$ANSWER" = Y ] && do_rm "$HOME/Library/Application Support/Google/Chrome/OptGuideOnDeviceModel"

confirm "macOS aerial wallpaper video (system redownloads as needed)" \
  "$HOME/Library/Application Support/com.apple.wallpaper/aerials/videos/B13D40FC-C033-436D-A197-185900EC3552.mov"
[ "$ANSWER" = Y ] && do_rm "$HOME/Library/Application Support/com.apple.wallpaper/aerials/videos/B13D40FC-C033-436D-A197-185900EC3552.mov"

confirm "Google Updater extension cache" \
  "$HOME/Library/Application Support/Google/GoogleUpdater/crx_cache"
[ "$ANSWER" = Y ] && do_rm "$HOME/Library/Application Support/Google/GoogleUpdater/crx_cache"

confirm "Old cursor-agent node binary (newer version exists)" \
  "$HOME/.local/share/cursor-agent/versions/2026.01.28-fd13201/node"
[ "$ANSWER" = Y ] && do_rm "$HOME/.local/share/cursor-agent/versions/2026.01.28-fd13201/node"

confirm "Old Pylance VS Code extension (2025.10.4 — newer is installed)" \
  "$HOME/.vscode/extensions/ms-python.vscode-pylance-2025.10.4"
[ "$ANSWER" = Y ] && do_rm "$HOME/.vscode/extensions/ms-python.vscode-pylance-2025.10.4"

confirm "Old Copilot Chat extension (0.37.6 — newer is installed)" \
  "$HOME/.vscode/extensions/github.copilot-chat-0.37.6"
[ "$ANSWER" = Y ] && do_rm "$HOME/.vscode/extensions/github.copilot-chat-0.37.6"

bigsection "STEP 3 / DEV CACHES (regenerate on next install/build)"

confirm "Augur dashboard node_modules (2.4 GB)" \
  "$HOME/Projects/Augur/apps/dashboard/node_modules"
[ "$ANSWER" = Y ] && do_rm "$HOME/Projects/Augur/apps/dashboard/node_modules"

confirm "my-startup node_modules (789 MB)" \
  "$HOME/Projects/my-startup/node_modules"
[ "$ANSWER" = Y ] && do_rm "$HOME/Projects/my-startup/node_modules"

confirm "my-startup .next build cache (377 MB)" \
  "$HOME/Projects/my-startup/.next"
[ "$ANSWER" = Y ] && do_rm "$HOME/Projects/my-startup/.next"

confirm "Augur Python venv (588 MB)" \
  "$HOME/Projects/Augur/.venv"
[ "$ANSWER" = Y ] && do_rm "$HOME/Projects/Augur/.venv"

confirm "augur-os Python venv (450 MB)" \
  "$HOME/Projects/augur-os/.venv"
[ "$ANSWER" = Y ] && do_rm "$HOME/Projects/augur-os/.venv"

confirm "episodic-memory plugin node_modules (737 MB)" \
  "$HOME/.claude/plugins/cache/superpowers-marketplace/episodic-memory/1.2.0/node_modules"
[ "$ANSWER" = Y ] && do_rm "$HOME/.claude/plugins/cache/superpowers-marketplace/episodic-memory/1.2.0/node_modules"

bigsection "STEP 4 / LOCAL LLM MODELS"
echo "Multiple LLM apps with overlapping models. Pick what you actually use."
echo

confirm "Ollama models (~6.3 GB) — keep if you use ollama" \
  "$HOME/.ollama/models"
[ "$ANSWER" = Y ] && do_rm "$HOME/.ollama/models"

confirm "Atomic Chat models (~9 GB total — Qwen 9B + Qwen 4B)" \
  "$HOME/Library/Application Support/Atomic Chat/data/llamacpp/models"
[ "$ANSWER" = Y ] && do_rm "$HOME/Library/Application Support/Atomic Chat/data/llamacpp/models"

confirm "Jan models (~5.5 GB total — Jan v3 + v3.5)" \
  "$HOME/Library/Application Support/Jan/data/llamacpp/models"
[ "$ANSWER" = Y ] && do_rm "$HOME/Library/Application Support/Jan/data/llamacpp/models"

bigsection "DONE"
freed_mb=$(echo "$freed" | awk '{print $1/1024}')
freed_gb=$(echo "$freed" | awk '{printf "%.2f", $1/1024/1024}')
printf "Reclaimed in this session: %s MB (%s GB)\n" "$freed_mb" "$freed_gb"
echo "(snapshot thinning is not counted above — check 'df -h /' to see real free space)"
df -h /