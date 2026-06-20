'use client';

import { useBrainHarnessController } from "./harness.controller";
import { BrainHarnessEmpty, BrainHarnessReady } from "./harness.view";

export default function BrainHarnessPage() {
  const controller = useBrainHarnessController();

  if (controller.loading) {
    return <div className="p-4 text-sm text-[var(--text-muted)] md:p-6">Loading harness snapshot…</div>;
  }
  if (controller.error) {
    return <div className="p-4 text-sm text-[var(--accent-danger)] md:p-6">Brain Harness snapshot could not be loaded.</div>;
  }

  return controller.snapshot ? (
    <BrainHarnessReady controller={controller} />
  ) : (
    <BrainHarnessEmpty controller={controller} />
  );
}
