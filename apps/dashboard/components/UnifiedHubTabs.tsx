"use client";

const EMPTY_ARRAY: never[] = [];

import type { TabEntry } from "@/lib/tabs/types";
import { HubTabBar } from "./HubTabBar";

export type UnifiedHubTabsProps = {
  tabs: TabEntry[];
  overflow?: TabEntry[];
};

/**
 * Simplified tab bar for hand-crafted layouts (settings, etc.).
 * Delegates to HubTabBar — the full implementation that also supports
 * blocks and autoPages for plugin hub layouts.
 */
export default function UnifiedHubTabs({
  tabs = EMPTY_ARRAY,
  overflow,
}: UnifiedHubTabsProps) {
  return <HubTabBar tabs={tabs} overflow={overflow} />;
}
