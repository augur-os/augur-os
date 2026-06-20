"use client";

import { Skeleton } from "@/components/ui/Skeleton";

export default function Loading() {
  return (
    <div className="space-y-10 animate-in fade-in duration-300">
      {/* Header skeleton */}
      <header className="page-header mb-6">
        <div>
          <Skeleton className="h-10 w-48 mb-2" />
          <Skeleton className="h-5 w-32" />
        </div>
      </header>

      {/* Workflows Section skeleton */}
      <div className="space-y-4">
        <Skeleton className="h-7 w-36" />
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="glass-panel p-4">
              <div className="flex items-center gap-3 mb-3">
                <Skeleton className="size-9 rounded-lg" />
                <div className="flex-1">
                  <Skeleton className="h-6 w-12 mb-1" />
                  <Skeleton className="h-3 w-16" />
                </div>
              </div>
              <Skeleton className="h-3 w-24" />
            </div>
          ))}
        </div>
      </div>

      {/* Main Content Split skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:gap-8">
        {/* Activity Feed skeleton */}
        <div className="lg:col-span-2 space-y-5">
          <div className="flex items-center justify-between mb-1">
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-4 w-16" />
          </div>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="glass-panel p-4 flex items-center gap-4">
                <Skeleton className="size-10 rounded-xl" />
                <div className="flex-1 min-w-0">
                  <Skeleton className="h-3 w-20 mb-2" />
                  <Skeleton className="h-4 w-48" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right sidebar skeleton */}
        <div className="space-y-5">
          <div className="space-y-3">
            <Skeleton className="h-6 w-20" />
            <div className="grid grid-cols-2 gap-2">
              {[...Array(4)].map((_, i) => (
                <div
                  key={i}
                  className="glass-panel p-3 flex flex-col items-center gap-2"
                >
                  <Skeleton className="size-5" />
                  <Skeleton className="h-3 w-12" />
                </div>
              ))}
            </div>
          </div>

          <div className="pt-4 border-t border-[var(--border-color)]">
            <Skeleton className="h-6 w-28 mb-3" />
            <div className="glass-panel p-4 space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center justify-between">
                  <Skeleton className="h-4 w-20" />
                  <Skeleton className="h-4 w-8" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
