"use client";

import Link from "next/link";
import { AlertTriangle, ArrowLeft, Home } from "lucide-react";

/**
 * Not Found Page
 *
 * Displayed when user navigates to a route that doesn't exist.
 * Provides clear messaging and navigation back to valid areas.
 */
export default function NotFound() {
  return (
    <div className="min-h-[calc(100vh-6rem)] flex items-center justify-center bg-[var(--bg-primary)]">
      <div className="text-center max-w-md mx-auto p-8">
        {/* Icon */}
        <div className="mx-auto size-16 rounded-full bg-[var(--accent-warning)]/20 flex items-center justify-center mb-6">
          <AlertTriangle className="size-8 text-[var(--accent-warning)]" />
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-2">
          Page Not Available
        </h1>

        {/* Description */}
        <p className="text-[var(--text-muted)] mb-6">
          The requested page could not be found. It may have been moved or is
          not yet available.
          <br />
          <span className="text-sm opacity-75">
            If you just mounted a new plugin, try restarting the dev server.
          </span>
        </p>

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/browse"
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-[var(--accent-foreground,white)] hover:opacity-90 transition-opacity"
          >
            <Home className="size-4" />
            Browse
          </Link>
          <button type="button"
            onClick={() => history.back()}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
          >
            <ArrowLeft className="size-4" />
            Go Back
          </button>
        </div>
      </div>
    </div>
  );
}
