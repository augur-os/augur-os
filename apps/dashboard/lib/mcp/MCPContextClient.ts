"use client";

/**
 * Client-side MCP Context Manager
 *
 * Lightweight event emitter for context switching.
 * Routes through /api/mcp/tool proxy to MCP tools (ADR-011).
 */

import { EventEmitter } from "events";
import { mcpCall } from "./client";

export interface ContextStats {
  current_page: string;
  active_tools: number;
  active_tool_names: string[];
  registered_tools: number;
  switch_count: number;
  avg_switch_time_ms: number;
  preload_hit_rate: number;
}

export interface ContextSwitchResult {
  success: boolean;
  removed: string[];
  added: string[];
  active_count: number;
  duration_ms: number;
  error?: string;
}

/**
 * Client-safe context manager
 * Communicates with MCP server via /api/mcp/tool proxy
 */
export class MCPContextClient extends EventEmitter {
  private static instance: MCPContextClient | null = null;
  private currentPage: string = "/";
  private toolSwitchInProgress: boolean = false;
  private preloadQueue: Set<string> = new Set();
  private preloadAbortControllers: Map<string, AbortController> = new Map();

  private constructor() {
    super();
  }

  public static getInstance(): MCPContextClient {
    if (typeof window === "undefined") {
      // Server-side: return dummy instance
      return new MCPContextClient();
    }

    if (!MCPContextClient.instance) {
      MCPContextClient.instance = new MCPContextClient();
    }
    return MCPContextClient.instance;
  }

  /**
   * Switch MCP context via switch-mcp-context tool
   */
  public async switchContext(
    newPage: string,
    preloaded: boolean = false,
  ): Promise<void> {
    if (this.toolSwitchInProgress) {
      console.log("[MCPContextClient] Switch already in progress");
      return;
    }

    if (this.currentPage === newPage) {
      return;
    }

    this.toolSwitchInProgress = true;
    const startTime = Date.now();

    // Abort any pending preloads
    for (const [page, controller] of this.preloadAbortControllers.entries()) {
      console.log(
        `[MCPContextClient] Aborting preload for ${page} due to context switch`,
      );
      controller.abort();
    }
    this.preloadAbortControllers.clear();

    try {
      this.emit("context-switching", { page: newPage });

      const result = await mcpCall<ContextSwitchResult>(
        "switch-mcp-context",
        { current_page: newPage, preloaded },
      );

      const duration = Date.now() - startTime;

      if (result.success) {
        this.currentPage = newPage;

        const eventData = {
          page: newPage,
          activeCount: result.active_count,
          duration: duration,
          removed: result.removed,
          added: result.added,
        };

        console.log(
          "[MCPContextClient] Emitting context-changed event:",
          eventData,
        );
        this.emit("context-changed", eventData);
        console.log(
          `[MCPContextClient] Context switched to ${newPage} in ${duration}ms, active: ${result.active_count}`,
        );
      } else {
        throw new Error(result.error || "Context switch failed");
      }
    } catch (error: any) {
      console.error("[MCPContextClient] Context switch failed:", error);
      this.emit("context-switch-failed", {
        error: error.message,
        page: newPage,
      });
      throw error;
    } finally {
      this.toolSwitchInProgress = false;
    }
  }

  /**
   * Preload context via preload-mcp-context tool
   */
  public async preloadContext(targetPage: string): Promise<void> {
    if (this.currentPage === targetPage) return;

    // Abort existing preload for this page if any
    const existingController = this.preloadAbortControllers.get(targetPage);
    if (existingController) {
      existingController.abort();
    }

    const controller = new AbortController();
    this.preloadAbortControllers.set(targetPage, controller);
    this.preloadQueue.add(targetPage);

    try {
      await mcpCall(
        "preload-mcp-context",
        { target_page: targetPage },
        { signal: controller.signal },
      );
      console.log(`[MCPContextClient] Preloaded ${targetPage}`);
    } catch (error: any) {
      if (error.name === "AbortError") {
        console.log(`[MCPContextClient] Preload for ${targetPage} was aborted`);
      } else {
        console.warn("[MCPContextClient] Preload failed:", error);
      }
    } finally {
      this.preloadQueue.delete(targetPage);
      if (this.preloadAbortControllers.get(targetPage) === controller) {
        this.preloadAbortControllers.delete(targetPage);
      }
    }
  }

  /**
   * Get context statistics via get-context tool
   */
  public async getStats(): Promise<ContextStats> {
    return mcpCall<ContextStats>("get-context", {});
  }

  public getCurrentPage(): string {
    return this.currentPage;
  }

  public isContextSwitching(): boolean {
    return this.toolSwitchInProgress;
  }
}

/**
 * Get singleton instance
 */
export function getMCPContextClient(): MCPContextClient {
  return MCPContextClient.getInstance();
}
