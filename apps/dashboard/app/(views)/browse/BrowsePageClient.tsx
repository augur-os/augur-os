"use client";

import { Suspense } from "react";
import { useBrowsePageController } from "./BrowsePageClient.controller";
import { BrowsePageScaffold } from "./BrowsePageClient.views";

function BrowsePageInner() {
  const controller = useBrowsePageController();
  return <BrowsePageScaffold controller={controller} />;
}

export function BrowsePageClient() {
  return (
    <Suspense fallback={<BrowsePageLoading />}>
      <BrowsePageInner />
    </Suspense>
  );
}

function BrowsePageLoading() {
  return (
    <div className="pl-1 pr-1" aria-live="polite" aria-label="Loading browse page">
      <div className="h-8 w-48 rounded-lg bg-[var(--bg-secondary)] motion-safe:animate-pulse" />
      <div className="h-4 w-64 mt-2 rounded bg-[var(--bg-secondary)] motion-safe:animate-pulse" />
      <div className="flex gap-2 mt-4">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-8 w-20 rounded-lg bg-[var(--bg-secondary)] motion-safe:animate-pulse" />
        ))}
      </div>
      <div className="mt-4 h-10 rounded-lg bg-[var(--bg-secondary)] motion-safe:animate-pulse" />
      <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Array.from({ length: 6 }).map((_, index) => (
          <div key={index} className="h-28 rounded-xl bg-[var(--bg-secondary)] motion-safe:animate-pulse flex p-4 gap-3">
            <div className="size-10 rounded-lg bg-[var(--bg-hover)] motion-safe:animate-pulse shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-3/4 rounded bg-[var(--bg-hover)] motion-safe:animate-pulse" />
              <div className="h-3 w-1/2 rounded bg-[var(--bg-hover)] motion-safe:animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
