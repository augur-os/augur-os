import type { ModelContext } from "../types";
import type {
  ViewsManageInput,
  ViewsManageOutput,
  ViewsComposeInput,
  ViewsComposeOutput,
  WebMCPError,
} from "../types";
import { mcpError } from "./errors";

// --- Exported execute functions (testable without navigator.modelContext) ---

export async function viewsManageExecute(
  input: ViewsManageInput,
): Promise<ViewsManageOutput | WebMCPError> {
  const { action, viewId, title, layout, icon, pinned } = input;

  try {
    switch (action) {
      case "list": {
        const response = await fetch("/api/views");
        if (!response.ok) {
          return mcpError("FETCH_FAILED", `Failed to list views: ${response.status} ${response.statusText}`);
        }
        const views = await response.json();
        return { success: true, views };
      }

      case "create": {
        if (!title) {
          return mcpError("INVALID_CONFIG", "title is required for create action");
        }
        const response = await fetch("/api/views", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, layout, icon, pinned }),
        });
        if (!response.ok) {
          return mcpError("FETCH_FAILED", `Failed to create view: ${response.status} ${response.statusText}`);
        }
        const view = await response.json();
        return { success: true, view };
      }

      case "read": {
        if (!viewId) {
          return mcpError("INVALID_CONFIG", "viewId is required for read action");
        }
        const response = await fetch(`/api/views/${viewId}`);
        if (!response.ok) {
          if (response.status === 404) {
            return mcpError("NOT_FOUND", `View "${viewId}" not found`);
          }
          return mcpError("FETCH_FAILED", `Failed to read view: ${response.status} ${response.statusText}`);
        }
        const view = await response.json();
        return { success: true, view };
      }

      case "update": {
        if (!viewId) {
          return mcpError("INVALID_CONFIG", "viewId is required for update action");
        }
        const updates: Record<string, unknown> = {};
        if (title !== undefined) updates.title = title;
        if (layout !== undefined) updates.layout = layout;
        if (icon !== undefined) updates.icon = icon;
        if (pinned !== undefined) updates.pinned = pinned;

        const response = await fetch(`/api/views/${viewId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        });
        if (!response.ok) {
          if (response.status === 404) {
            return mcpError("NOT_FOUND", `View "${viewId}" not found`);
          }
          return mcpError("FETCH_FAILED", `Failed to update view: ${response.status} ${response.statusText}`);
        }
        const view = await response.json();
        return { success: true, view };
      }

      case "delete": {
        if (!viewId) {
          return mcpError("INVALID_CONFIG", "viewId is required for delete action");
        }
        const response = await fetch(`/api/views/${viewId}`, { method: "DELETE" });
        if (!response.ok) {
          if (response.status === 404) {
            return mcpError("NOT_FOUND", `View "${viewId}" not found`);
          }
          return mcpError("FETCH_FAILED", `Failed to delete view: ${response.status} ${response.statusText}`);
        }
        return { success: true };
      }

      default: {
        return mcpError("INVALID_ACTION", `Unknown action "${action as string}"`);
      }
    }
  } catch (err) {
    return mcpError("FETCH_FAILED", err instanceof Error ? err.message : String(err));
  }
}

export async function viewsComposeExecute(
  input: ViewsComposeInput,
): Promise<ViewsComposeOutput | WebMCPError> {
  const { viewId, action, blockId, instanceId, position, config } = input;

  try {
    switch (action) {
      case "add": {
        if (!blockId) {
          return mcpError("INVALID_CONFIG", "blockId is required for add action");
        }
        const response = await fetch(`/api/views/${viewId}/blocks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ blockId, instanceId, position, config }),
        });
        if (!response.ok) {
          if (response.status === 404) {
            return mcpError("NOT_FOUND", `View "${viewId}" not found`);
          }
          return mcpError("FETCH_FAILED", `Failed to add block: ${response.status} ${response.statusText}`);
        }
        const view = await response.json();
        return { success: true, view };
      }

      case "remove": {
        if (!instanceId) {
          return mcpError("INVALID_CONFIG", "instanceId is required for remove action");
        }
        const response = await fetch(`/api/views/${viewId}/blocks/${instanceId}`, {
          method: "DELETE",
        });
        if (!response.ok) {
          if (response.status === 404) {
            return mcpError("NOT_FOUND", `View "${viewId}" or block instance "${instanceId}" not found`);
          }
          return mcpError("FETCH_FAILED", `Failed to remove block: ${response.status} ${response.statusText}`);
        }
        const view = await response.json();
        return { success: true, view };
      }

      case "move": {
        if (!instanceId || !position) {
          return mcpError("INVALID_CONFIG", "instanceId and position are required for move action");
        }
        // Move updates block positions via PUT on the view
        const response = await fetch(`/api/views/${viewId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ blockPositions: [{ instanceId, position }] }),
        });
        if (!response.ok) {
          if (response.status === 404) {
            return mcpError("NOT_FOUND", `View "${viewId}" not found`);
          }
          return mcpError("FETCH_FAILED", `Failed to move block: ${response.status} ${response.statusText}`);
        }
        const view = await response.json();
        return { success: true, view };
      }

      default: {
        return mcpError("INVALID_ACTION", `Unknown compose action "${action as string}"`);
      }
    }
  } catch (err) {
    return mcpError("FETCH_FAILED", err instanceof Error ? err.message : String(err));
  }
}

// --- Tool registration ---

export function registerViewTools(mc: ModelContext): void {
  mc.registerTool({
    name: "views.manage",
    description:
      "Create, read, update, delete, or list view canvases. Views are user-defined dashboards that contain a grid of block instances.",
    inputSchema: {
      type: "object",
      properties: {
        action: {
          type: "string",
          enum: ["list", "create", "read", "update", "delete"],
          description: "Action to perform",
        },
        viewId: { type: "string", description: "View ID (required for read, update, delete)" },
        title: { type: "string", description: "View title (required for create)" },
        layout: {
          type: "object",
          description: "Grid layout config",
          properties: {
            columns: { type: "number" },
            rowHeight: { type: "number" },
          },
        },
        icon: { type: "string", description: "Icon name for the view" },
        pinned: { type: "boolean", description: "Whether the view is pinned" },
      },
      required: ["action"],
    },
    execute: async (input) => viewsManageExecute(input as ViewsManageInput),
    annotations: { readOnlyHint: false },
  });

  mc.registerTool({
    name: "views.compose",
    description:
      "Add, remove, or move blocks within a view canvas. Use add to place a block, remove to delete a block instance, move to reposition.",
    inputSchema: {
      type: "object",
      properties: {
        viewId: { type: "string", description: "View ID to compose" },
        action: {
          type: "string",
          enum: ["add", "remove", "move"],
          description: "Compose action",
        },
        blockId: { type: "string", description: "Block ID to add (required for add)" },
        instanceId: {
          type: "string",
          description: "Block instance ID (required for remove, move)",
        },
        position: {
          type: "object",
          description: "Grid position {x, y, w, h} (required for move, optional for add)",
          properties: {
            x: { type: "number" },
            y: { type: "number" },
            w: { type: "number" },
            h: { type: "number" },
          },
        },
        config: { type: "object", description: "Initial config for the block instance (add only)" },
      },
      required: ["viewId", "action"],
    },
    execute: async (input) => viewsComposeExecute(input as ViewsComposeInput),
    annotations: { readOnlyHint: false },
  });
}
