import { test } from "node:test";
import assert from "node:assert/strict";
import { safeHeapMb } from "../lib/heap-clamp.mjs";

const withRam = (mb, fn) => {
  process.env.AUGUR_TEST_TOTAL_RAM_MB = String(mb);
  try { return fn(); } finally { delete process.env.AUGUR_TEST_TOTAL_RAM_MB; }
};

test("16GB clamps big caps to 4915, leaves 4096", () => {
  withRam(16384, () => {
    assert.equal(safeHeapMb(16384), 4915);
    assert.equal(safeHeapMb(12288), 4915);
    assert.equal(safeHeapMb(4096), 4096);
  });
});
test("64GB leaves tiers unchanged", () => {
  withRam(65536, () => assert.equal(safeHeapMb(16384), 16384));
});
test("4GB clamps to 2048 floor", () => {
  withRam(4096, () => assert.equal(safeHeapMb(12288), 2048));
});
test("unknown RAM (0) -> no clamp", () => {
  withRam(0, () => assert.equal(safeHeapMb(12288), 12288));
});
