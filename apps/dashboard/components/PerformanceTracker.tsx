"use client";

import { usePagePerformance } from "@/hooks/usePagePerformance";
import { useInteractionTracker } from "@/hooks/useInteractionTracker";

export default function PerformanceTracker() {
  usePagePerformance();
  useInteractionTracker();
  return null;
}
