#!/bin/bash
# scan.sh — read-only scan of disk space hogs on macOS.
# DELETES NOTHING. Writes a sorted report to ~/Desktop/disk-cleanup-report.txt.
#
# Usage:   bash scan.sh
# Companion script: cleanup.sh (interactive deletions based on findings)

set -u
OUT="$HOME/Desktop/disk-cleanup-report.txt"
{
echo "=== Disk scan $(date) ==="
echo
echo "## DISK USAGE"; df -h /
echo; echo "## TOP 25 IN HOME"
du -sh "$HOME"/* "$HOME"/.[!.]* 2>/dev/null | sort -hr | head -25
echo; echo "## DEV CACHES (safe to delete — regenerated on next build)"
find "$HOME" -type d \( -name node_modules -o -name .venv -o -name venv -o -name __pycache__ \
  -o -name .gradle -o -name .m2 -o -name target -o -name build -o -name dist \
  -o -name .next -o -name .nuxt -o -name .turbo -o -name DerivedData -o -name Pods \
  -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -print 2>/dev/null \
  | while IFS= read -r d; do du -sk "$d" 2>/dev/null; done | sort -nr \
  | awk '{ kb=$1; $1=""; sub(/^ /,""); printf "%9.1f MB  %s\n", kb/1024, $0 }' | head -40
echo; echo "## AI / MODEL CACHES (Gemini, Claude, Cursor, Ollama, HF, LM Studio…)"
for d in \
  "$HOME/.cache/gemini" "$HOME/.config/gemini" "$HOME/.gemini" \
  "$HOME/Library/Application Support/Gemini" "$HOME/Library/Application Support/Google/Gemini" \
  "$HOME/Library/Caches/Gemini" "$HOME/Library/Caches/com.google.gemini" \
  "$HOME/.cache/huggingface" "$HOME/Library/Caches/huggingface" \
  "$HOME/.ollama" "$HOME/.lmstudio" "$HOME/Library/Application Support/LM Studio" \
  "$HOME/Library/Application Support/Cursor" "$HOME/Library/Application Support/Code" \
  "$HOME/Library/Application Support/Claude" \
  "$HOME/Library/Caches/com.anthropic.claudefordesktop" \
  "$HOME/Library/Caches/com.openai.chat" "$HOME/Library/Application Support/openai" \
  "$HOME/.cache/torch" "$HOME/.cache/whisper" \
  "$HOME/Library/Caches/pip" "$HOME/Library/Caches/Yarn" "$HOME/.npm" \
  "$HOME/Library/Caches/Homebrew" "$HOME/Library/Containers/com.docker.docker"; do
  [ -e "$d" ] && du -sh "$d" 2>/dev/null
done | sort -hr
echo; echo "## LARGEST FILES IN HOME (>500 MB)"
find "$HOME" -type f -size +500M 2>/dev/null \
  | while IFS= read -r f; do du -sk "$f" 2>/dev/null; done | sort -nr \
  | awk '{ kb=$1; $1=""; sub(/^ /,""); printf "%9.1f MB  %s\n", kb/1024, $0 }' | head -40
echo; echo "## DOWNLOADS OLDER THAN 6 MONTHS"
find "$HOME/Downloads" -type f -mtime +180 2>/dev/null \
  | while IFS= read -r f; do du -sk "$f" 2>/dev/null; done | sort -nr \
  | awk '{ kb=$1; $1=""; sub(/^ /,""); printf "%9.1f MB  %s\n", kb/1024, $0 }' | head -30
echo; echo "## TRASH"; du -sh "$HOME/.Trash" 2>/dev/null || echo "    (empty)"
echo; echo "## XCODE / iOS BACKUPS"
for d in \
  "$HOME/Library/Application Support/MobileSync/Backup" \
  "$HOME/Library/Developer/CoreSimulator/Devices" \
  "$HOME/Library/Developer/Xcode/DerivedData" \
  "$HOME/Library/Developer/Xcode/Archives" \
  "$HOME/Library/Developer/Xcode/iOS DeviceSupport"; do
  [ -e "$d" ] && du -sh "$d" 2>/dev/null
done | sort -hr
echo; echo "## DUPLICATES (>50 MB, identical content)"
find "$HOME" -type f -size +50M -not -path "*/node_modules/*" -not -path "*/.git/*" \
  -not -path "*/Library/Caches/*" -not -path "*/.Trash/*" 2>/dev/null \
  | while IFS= read -r f; do
      h=$(md5 -q "$f" 2>/dev/null); s=$(stat -f%z "$f" 2>/dev/null)
      printf '%s\t%s\t%s\n' "$h" "$s" "$f"
    done | sort \
  | awk -F'\t' '{
      if ($1==p){ if(c==1) printf "\nGROUP (%.1f MB each):\n  %s\n", ps/1024/1024, pp; printf "  %s\n", $3; c++ } else c=1
      p=$1; ps=$2; pp=$3 }'
echo; echo "## APFS LOCAL SNAPSHOTS (often the biggest hidden user)"
tmutil listlocalsnapshots / 2>/dev/null | sed 's/^/  /' || echo "  (none)"
echo; echo "=== Done. Report at $OUT ==="
} | tee "$OUT"
echo
echo "Open report:  open \"$OUT\""