import os from "node:os";

// RAM-aware Node heap clamp. Mirrors lib/heap-clamp.sh exactly.
// safe ceiling = max(2048, floor(total_mb * 0.30)); clamp DOWN only.
// AUGUR_TEST_TOTAL_RAM_MB overrides detection. total 0/unknown => no clamp.
export function detectTotalRamMb() {
  const override = process.env.AUGUR_TEST_TOTAL_RAM_MB;
  if (override !== undefined && override !== "") return Number(override) | 0;
  const mb = Math.floor(os.totalmem() / 1024 / 1024);
  return Number.isFinite(mb) && mb > 0 ? mb : 0;
}

export function safeHeapMb(desiredMb) {
  const totalMb = detectTotalRamMb();
  if (totalMb <= 0) return desiredMb;
  const safeMax = Math.max(2048, Math.floor((totalMb * 30) / 100));
  return Math.min(desiredMb, safeMax);
}
