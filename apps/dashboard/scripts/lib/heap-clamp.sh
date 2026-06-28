# Shared RAM-aware Node heap clamp. Sourced by start-dev.sh.
# Contract: caller sets NODE_OLD_SPACE_MB; augur_clamp_heap rewrites it in place.
# Policy: safe ceiling = max(2048, floor(total_ram_mb * 0.30)); clamp DOWN only.
# AUGUR_TEST_TOTAL_RAM_MB overrides detection for tests. Returns 0 => skip clamp.

augur_detect_total_ram_mb() {
  if [ -n "${AUGUR_TEST_TOTAL_RAM_MB:-}" ]; then
    echo "${AUGUR_TEST_TOTAL_RAM_MB}"; return 0
  fi
  local bytes
  if command -v sysctl >/dev/null 2>&1; then
    bytes="$(sysctl -n hw.memsize 2>/dev/null || true)"
    if [ -n "$bytes" ] && [ "$bytes" -gt 0 ] 2>/dev/null; then
      echo $(( bytes / 1024 / 1024 )); return 0
    fi
  fi
  if [ -r /proc/meminfo ]; then
    awk '/^MemTotal:/ {printf "%d", $2/1024; exit}' /proc/meminfo; return 0
  fi
  echo 0
}

augur_clamp_heap() {
  local total_mb safe_max
  total_mb="$(augur_detect_total_ram_mb)"
  if [ "${total_mb:-0}" -le 0 ] 2>/dev/null; then
    return 0  # unknown RAM: preserve current behavior, no clamp
  fi
  safe_max=$(( total_mb * 30 / 100 ))
  if [ "$safe_max" -lt 2048 ]; then safe_max=2048; fi
  if [ "${NODE_OLD_SPACE_MB:-0}" -gt "$safe_max" ]; then
    echo "[start-dev] Clamping Node heap ${NODE_OLD_SPACE_MB}MB -> ${safe_max}MB (30% of ${total_mb}MB RAM) to prevent system OOM" >&2
    NODE_OLD_SPACE_MB="$safe_max"
  fi
}
