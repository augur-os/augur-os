'use client';

import { Activity, Brain } from "lucide-react";
import type { BrainHarnessController } from "./harness.controller";
import { ManagerSection, RefreshSnapshotButton } from "./harness.manager";
import { HarnessWorkspace, ProvenanceDetails, ReadinessSection } from "./harness.workspace";

function BrainHarnessHeader() {
  return (
    <header className="flex items-start gap-3">
      <div className="rounded-xl border border-cyan-500/25 bg-cyan-500/10 p-3">
        <Activity className="size-5 text-cyan-400" aria-hidden="true" />
      </div>
      <div>
        <h2 className="text-2xl font-bold text-[var(--text-primary)]">Brain Harness</h2>
        <p className="mt-1 text-sm text-[var(--text-muted)]">
          Inspect capability wiring and diagnostics from the latest brain harness snapshot.
        </p>
      </div>
    </header>
  );
}

export function BrainHarnessEmpty({ controller }: { controller: BrainHarnessController }) {
  return (
    <div className="space-y-6 p-4 md:p-6">
      <BrainHarnessHeader />
      <ManagerSection controller={controller} />
      <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-5">
        <div className="flex items-start gap-3">
          <Brain className="mt-1 size-5 text-[var(--text-secondary)]" aria-hidden="true" />
          <div>
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Harness snapshot has not been generated yet.</h2>
            <p className="mt-1 text-sm text-[var(--text-muted)]">Generate the first snapshot to inspect capability wiring and diagnostics.</p>
          </div>
        </div>
        <RefreshSnapshotButton controller={controller} label="Generate snapshot" />
      </section>
    </div>
  );
}

export function BrainHarnessReady({ controller }: { controller: BrainHarnessController }) {
  const snapshot = controller.snapshot;
  if (!snapshot) return null;

  return (
    <div className="space-y-6 p-4 md:p-6">
      <BrainHarnessHeader />
      <ManagerSection controller={controller} />
      <ReadinessSection controller={controller} snapshot={snapshot} />
      <HarnessWorkspace controller={controller} snapshot={snapshot} />
      <ProvenanceDetails provenance={snapshot.provenance} />
    </div>
  );
}
