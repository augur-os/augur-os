#!/usr/bin/env bash
# Tests the RAM-aware heap clamp logic in start-dev.sh in isolation.
# We source only the clamp block by extracting it; here we test the function
# + clamp math via a tiny harness that mirrors the script's contract.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Helper: run the clamp with a faked RAM + desired cap, echo the result.
run_clamp() {
  AUGUR_TEST_TOTAL_RAM_MB="$1" NODE_OLD_SPACE_MB="$2" bash -c '
    source "'"$SCRIPT_DIR"'/lib/heap-clamp.sh"
    NODE_OLD_SPACE_MB="'"$2"'"
    augur_clamp_heap
    echo "$NODE_OLD_SPACE_MB"
  '
}

fail=0
assert_eq() { if [ "$1" != "$2" ]; then echo "FAIL: expected $2 got $1 ($3)"; fail=1; else echo "ok: $3"; fi; }

assert_eq "$(run_clamp 16384 16384)" 4915 "16GB worktree 16384 -> 4915"
assert_eq "$(run_clamp 16384 12288)" 4915 "16GB focused 12288 -> 4915"
assert_eq "$(run_clamp 16384 4096)"  4096 "16GB default 4096 stays"
assert_eq "$(run_clamp 65536 16384)" 16384 "64GB worktree unchanged (<19660)"
assert_eq "$(run_clamp 4096 12288)"  2048 "4GB clamps to 2048 floor"
assert_eq "$(run_clamp 0 12288)"     12288 "unknown RAM -> no clamp"
exit $fail
