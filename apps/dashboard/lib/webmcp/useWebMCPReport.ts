"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import type { FormField, RenderState, WebMCPPageDescriptor } from "./types";
import type { BlockType, DataSource } from "@/lib/blocks/types";

interface WebMCPReportProps {
  blockId: string;
  instanceId: string;
  type: BlockType;
  config: Record<string, unknown>;
  dataSource?: DataSource;
  data: unknown;
  loading: boolean;
  error: string | null;
}

function deriveRenderState(loading: boolean, error: string | null, data: unknown): RenderState {
  if (loading) return "loading";
  if (error) return "error";
  if (data === null || data === undefined) return "empty";
  if (Array.isArray(data) && data.length === 0) return "empty";
  return "ready";
}

/**
 * Reports block state to the WebMCP state registry (write-only).
 * Call this in BlockRenderer after data fetching.
 */
export function useWebMCPReport(props: WebMCPReportProps): void {
  const { blockId, instanceId, type, config, data, loading, error } = props;

  // Report mount/unmount
  useEffect(() => {
    return () => {
      const registry = (window as any).__webmcpRegistry;
      if (registry) registry.removeBlock(blockId, instanceId);
    };
  }, [blockId, instanceId]);

  // Report state on every change
  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;

    registry.reportBlock({
      blockId,
      instanceId,
      type,
      mounted: true,
      renderState: deriveRenderState(loading, error, data),
      config,
      data,
      error: error ?? undefined,
      lastUpdated: Date.now(),
    });
  }, [blockId, instanceId, type, config, data, loading, error]);
}

interface WebMCPPageReportProps {
  pageId: string;
  skillId: string;
  hub: string;
  path: string;
  blocks: string[];
  loading: boolean;
  error: string | null;
}

/**
 * Reports page state to the WebMCP state registry (write-only).
 * Call this in ConfigPage or block components after data fetching.
 */
function useWebMCPPageReport(props: WebMCPPageReportProps): void {
  const { pageId, skillId, hub, path, blocks, loading, error } = props;

  // Report unmount
  useEffect(() => {
    return () => {
      const registry = (window as any).__webmcpRegistry;
      if (registry) registry.removePage(pageId);
    };
  }, [pageId]);

  // Report state on every change
  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;

    registry.reportPage({
      pageId,
      skillId,
      hub,
      path,
      mounted: true,
      renderState: deriveRenderState(loading, error, true),
      blocks,
      lastUpdated: Date.now(),
    });
  }, [pageId, skillId, hub, path, blocks, loading, error]);
}

interface WebMCPViewReportProps {
  viewId: string;
  title: string;
  editing: boolean;
  blocks: Array<{
    instanceId: string;
    blockId: string;
    position: { x: number; y: number; w: number; h: number };
  }>;
  layout: { columns: number; rowHeight: number };
}

/**
 * Reports view state to the WebMCP state registry (write-only).
 * Call this in ViewCanvas so agents can inspect current view composition.
 */
function useWebMCPViewReport(props: WebMCPViewReportProps): void {
  const { viewId, title, editing, blocks, layout } = props;

  // Report unmount
  useEffect(() => {
    return () => {
      const registry = (window as any).__webmcpRegistry;
      if (registry) registry.removeView(viewId);
    };
  }, [viewId]);

  // Report state on every change
  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;

    registry.reportView({
      viewId,
      title,
      mounted: true,
      editing,
      blocks,
      layout,
      lastUpdated: Date.now(),
    });
  }, [viewId, title, editing, blocks, layout]);
}

/**
 * Reports the current navigation state to the WebMCP state registry.
 * Call this inside a component with access to usePathname (e.g., WebMCPProvider).
 */
export function useWebMCPNavigationReport(): void {
  const pathname = usePathname();

  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;

    const segments = pathname.split("/").filter(Boolean);
    const hub = segments[0] || null;

    // Get available tabs from the tab registry
    let availableTabs: Array<{ label: string; href: string }> = [];
    try {
      const { getHubConfig } = require("@/lib/tabs/registry");
      const config = hub ? getHubConfig(hub) : null;
      if (config?.tabs) {
        availableTabs = config.tabs.map((t: any) => ({ label: t.label, href: t.href }));
      }
    } catch {
      // Tab registry may not be available; availableTabs stays empty
    }

    registry.reportNavigation({
      path: pathname,
      hub,
      activeTab: segments[1] || null,
      breadcrumbs: segments,
      availableTabs,
    });
  }, [pathname]);
}

interface UseWebMCPFormProps {
  formId: string;
  pageId?: string;
  fields: FormField[];
  values: Record<string, unknown>;
  onFill: (fields: Record<string, unknown>) => void;
  onSubmit: () => void;
}

/**
 * Opt-in hook for form components to register themselves with the WebMCP registry.
 * Once registered, agents can use forms.discover, forms.fill, and forms.submit tools
 * to inspect and interact with the form programmatically.
 *
 * Call this in config modals, settings panels, and install wizards.
 */
function useWebMCPForm(props: UseWebMCPFormProps): void {
  const { formId, pageId, fields, values, onFill, onSubmit } = props;

  // Report form state on mount/change, remove on unmount
  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;
    registry.reportForm({
      formId,
      pageId,
      fields,
      values,
      dirty: false,
      submitting: false,
      lastUpdated: Date.now(),
    });
    return () => { registry.removeForm(formId); };
  }, [formId, pageId, fields, values]);

  // Subscribe to fill/submit events from WebMCP tools
  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;
    const unsubFill = registry.onFormFill(formId, onFill);
    const unsubSubmit = registry.onFormSubmit(formId, onSubmit);
    return () => {
      unsubFill();
      unsubSubmit();
    };
  }, [formId, onFill, onSubmit]);
}

/**
 * Opt-in hook for custom page authors to declare their page's capabilities.
 * Call this once at the top of your custom page component.
 * The page will appear in pages.discover once mounted.
 */
function useWebMCPPage(descriptor: WebMCPPageDescriptor): void {
  const pathname = usePathname();

  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;

    const hub = pathname.split("/")[1] || "";

    registry.reportPage({
      pageId: descriptor.pageId,
      skillId: descriptor.pageId.split(":")[0],
      hub,
      path: pathname,
      mounted: true,
      renderState: "ready",
      blocks: [],
      lastUpdated: Date.now(),
    });

    return () => {
      registry.removePage(descriptor.pageId);
    };
  }, [descriptor.pageId, pathname]);
}

/**
 * Subscribes to config change and refresh events from WebMCP tool calls.
 * Returns configOverride (set by blocks.configure) and refetchSignal
 * (incremented by blocks.act("refresh")).
 *
 * Call this in BlockRenderer BEFORE useBlockData so configOverride
 * can be merged into the effective config.
 */
export function useWebMCPSubscribe(blockId: string): {
  configOverride: Record<string, unknown> | null;
  refetchSignal: number;
} {
  const [configOverride, setConfigOverride] = useState<Record<string, unknown> | null>(null);
  const [refetchSignal, setRefetchSignal] = useState(0);

  useEffect(() => {
    const registry = (window as any).__webmcpRegistry;
    if (!registry) return;

    const unsubConfig = registry.onConfigChange(blockId, (newConfig: Record<string, unknown>) => {
      setConfigOverride(newConfig);
    });
    const unsubRefresh = registry.onRefresh(blockId, () => {
      setRefetchSignal((n: number) => n + 1);
    });

    return () => {
      unsubConfig();
      unsubRefresh();
    };
  }, [blockId]);

  return { configOverride, refetchSignal };
}
