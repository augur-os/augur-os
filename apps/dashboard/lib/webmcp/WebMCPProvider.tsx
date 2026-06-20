"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { StateRegistry } from "./state-registry";
import { registerBlockTools } from "./tools/blocks";
import { registerPageTools } from "./tools/pages";
import { registerViewTools } from "./tools/views";
import { registerNavigationTools } from "./tools/navigation";
import { registerCatalogTools } from "./tools/catalog";
import { registerFormTools } from "./tools/forms";
import { registerAgentTools } from "./tools/agents";
import { useWebMCPNavigationReport } from "./useWebMCPReport";

// Import polyfill — side effect ensures navigator.modelContext exists
import "./polyfill";

interface WebMCPProviderProps {
  children: ReactNode;
}

/**
 * React context provider for WebMCP.
 *
 * On mount:
 * 1. Creates a StateRegistry and exposes it as window.__webmcpRegistry
 * 2. Registers the 4 block tools with navigator.modelContext
 *
 * On unmount:
 * 3. Unregisters tools and clears the registry
 *
 * Must be placed inside QueryProvider (needs React Query for cache access).
 */
export function WebMCPProvider({ children }: WebMCPProviderProps) {
  const registryRef = useRef<StateRegistry | null>(null);
  const registeredRef = useRef(false);
  const router = useRouter();

  useWebMCPNavigationReport();

  useEffect(() => {
    const registry = new StateRegistry();
    registryRef.current = registry;
    (window as any).__webmcpRegistry = registry;
    (window as any).__webmcpRouter = router;

    if (navigator.modelContext && !registeredRef.current) {
      registerBlockTools(navigator.modelContext, registry);
      registerPageTools(navigator.modelContext, registry);
      registerViewTools(navigator.modelContext);
      registerNavigationTools(navigator.modelContext, registry);
      registerCatalogTools(navigator.modelContext, registry);
      registerFormTools(navigator.modelContext, registry);
      registerAgentTools(navigator.modelContext, registry);
      registeredRef.current = true;
    }

    return () => {
      if (navigator.modelContext && registeredRef.current) {
        const toolNames = [
          "blocks.discover",
          "blocks.read",
          "blocks.configure",
          "blocks.act",
          "pages.discover",
          "pages.read",
          "views.manage",
          "views.compose",
          "navigation.goto",
          "navigation.state",
          "catalog.search",
          "catalog.preview",
          "forms.discover",
          "forms.fill",
          "forms.submit",
          "agents.list",
          "agents.read",
          "agents.interact",
        ];
        for (const name of toolNames) {
          try {
            navigator.modelContext.unregisterTool(name);
          } catch {
            // Tool may already be unregistered
          }
        }
        registeredRef.current = false;
      }

      registry.clear();
      delete (window as any).__webmcpRegistry;
      delete (window as any).__webmcpRouter;
    };
  }, [router]);

  return <>{children}</>;
}
