"use client";

import { useUsageTracking } from "@/hooks/useUsageTracking";

export default function UsageTracker() {
  useUsageTracking();
  return null;
}
