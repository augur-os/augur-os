"use client";

import { mcpCall } from "@/lib/mcp/client";

export type HubNavOrderItem = {
  hubId: string;
  navOrder: number;
};

export type TabNavOrderItem = {
  pageId: string;
  order: number;
  skillId?: string;
  title?: string;
  visible?: boolean;
  delete?: boolean;
};

export async function persistHubNavOrder(items: HubNavOrderItem[]) {
  return mcpCall<{ success?: boolean; error?: string }>("set-config", {
    scope: "nav-order-update",
    type: "hub",
    items,
  });
}

export async function persistTabNavOrder(
  hubId: string,
  items: TabNavOrderItem[],
) {
  return mcpCall<{ success?: boolean; error?: string }>("set-config", {
    scope: "nav-order-update",
    type: "tab",
    hubId,
    items,
  });
}
