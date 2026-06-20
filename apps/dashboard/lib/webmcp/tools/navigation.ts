import type { ModelContext } from "../types";
import type {
  NavigationGotoInput,
  NavigationGotoOutput,
  NavigationStateInput,
  NavigationStateOutput,
  WebMCPError,
} from "../types";
import type { StateRegistry } from "../state-registry";
import { mcpError } from "./errors";

export async function navigationGotoExecute(
  input: NavigationGotoInput,
  registry: StateRegistry,
): Promise<NavigationGotoOutput | WebMCPError> {
  const router = (window as any).__webmcpRouter;
  if (!router) {
    return mcpError("FETCH_FAILED", "Router not available", undefined);
  }

  const prevNav = registry.getNavigation();
  const previousPath = prevNav?.path || "/";

  router.push(input.path);

  // Wait briefly for pathname to update
  await new Promise((resolve) => setTimeout(resolve, 100));

  const hub = input.path.split("/")[1] || null;

  return {
    success: true,
    previousPath,
    newPath: input.path,
    hub,
  };
}

export async function navigationStateExecute(
  _input: NavigationStateInput,
  registry: StateRegistry,
): Promise<NavigationStateOutput | WebMCPError> {
  const nav = registry.getNavigation();
  if (!nav) {
    return mcpError("FETCH_FAILED", "Navigation state not available");
  }
  return nav;
}

export function registerNavigationTools(mc: ModelContext, registry: StateRegistry): void {
  mc.registerTool({
    name: "navigation.goto",
    description:
      "Navigate the dashboard to a given path. Returns previous and new path with hub context.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "The path to navigate to (e.g., '/career/companies')" },
      },
      required: ["path"],
    },
    execute: async (input) => navigationGotoExecute(input as NavigationGotoInput, registry),
    annotations: { readOnlyHint: false },
  });

  mc.registerTool({
    name: "navigation.state",
    description:
      "Get the current navigation state: active path, hub, tab, breadcrumbs, and available tabs.",
    inputSchema: {
      type: "object",
      properties: {},
    },
    execute: async (input) => navigationStateExecute(input as NavigationStateInput, registry),
    annotations: { readOnlyHint: true },
  });
}
