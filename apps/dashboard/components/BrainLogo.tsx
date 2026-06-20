"use client";

import { useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
// eslint-disable-next-line no-restricted-imports -- ADR-490 shell exception
import AugurIcon from "@/features/components/AugurIcon";

/**
 * Brain Logo with Easter Egg
 *
 * Fast click 3+ times on the logo to open the brain neural view.
 */
export default function BrainLogo() {
  const { push } = useRouter();
  const clickCountRef = useRef(0);
  const clickTimerRef = useRef<NodeJS.Timeout | null>(null);
  const [isActivating, setIsActivating] = useState(false);

  const CLICK_THRESHOLD = 3;
  const CLICK_TIMEOUT = 500;

  const activateBrainLogo = useCallback(() => {
    clickCountRef.current += 1;

    if (clickTimerRef.current) {
      clearTimeout(clickTimerRef.current);
    }

    if (clickCountRef.current >= CLICK_THRESHOLD) {
      setIsActivating(true);
      // TODO_BUG(auto-memory-leak): hmr-unsafe-interval — Module-level setInterval without globalThis guard — leaks on HMR reload
      setTimeout(() => {
        push("/workspace/overview");
        // Reset state after navigation so logo reappears
        // TODO_BUG(auto-memory-leak): hmr-unsafe-interval — Module-level setInterval without globalThis guard — leaks on HMR reload
        setTimeout(() => setIsActivating(false), 500);
      }, 400);
      clickCountRef.current = 0;
      return;
    }

    clickTimerRef.current = setTimeout(() => {
      clickCountRef.current = 0;
    }, CLICK_TIMEOUT);
  }, [push]);

  return (
    <button
      type="button"
      aria-label="Open neural view"
      className="flex items-center gap-3 cursor-pointer select-none group border-0 bg-transparent p-0 text-left"
      onClick={activateBrainLogo}
    >
      <div
        className={`w-8 h-8 rounded-full bg-[linear-gradient(135deg,var(--accent-primary),var(--accent-secondary))] flex items-center justify-center transition-transform ${isActivating ? "scale-150 opacity-0" : "group-hover:scale-105"}`}
        style={{ transition: "transform 0.3s, opacity 0.3s" }}
      >
        <AugurIcon className="size-5 text-white" />
      </div>
      <span
        className={`font-bold text-lg tracking-tight transition-opacity ${isActivating ? "opacity-0" : ""}`}
        style={{ transition: "opacity 0.3s" }}
      >
        Augur
      </span>
    </button>
  );
}
