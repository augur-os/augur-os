import type { ModelContext } from "../types";
import type {
  AgentsListInput,
  AgentsListOutput,
  AgentsReadInput,
  AgentsReadOutput,
  AgentsInteractInput,
  AgentsInteractOutput,
  WebMCPError,
} from "../types";
import type { StateRegistry } from "../state-registry";
import { mcpError } from "./errors";

// --- Exported execute functions (testable without navigator.modelContext) ---

export async function agentsListExecute(
  _input: AgentsListInput,
  registry: StateRegistry,
): Promise<AgentsListOutput> {
  const agents = registry.getAllAgents();
  return {
    agents: agents.map((a) => ({ bubbleId: a.bubbleId, label: a.label, status: a.status })),
  };
}

export async function agentsReadExecute(
  input: AgentsReadInput,
  registry: StateRegistry,
): Promise<AgentsReadOutput | WebMCPError> {
  const agent = registry.getAgent(input.bubbleId);
  if (!agent) return mcpError("NOT_FOUND", `Agent bubble "${input.bubbleId}" not found`);
  return { bubbleId: agent.bubbleId, label: agent.label, status: agent.status, output: agent.output };
}

export async function agentsInteractExecute(
  input: AgentsInteractInput,
  registry: StateRegistry,
): Promise<AgentsInteractOutput | WebMCPError> {
  const agent = registry.getAgent(input.bubbleId);
  if (!agent) return mcpError("NOT_FOUND", `Agent bubble "${input.bubbleId}" not found`);
  // Agent interaction would send input to the PTY — for now, just acknowledge
  return { success: true, bubbleId: input.bubbleId };
}

// --- Tool registration ---

export function registerAgentTools(mc: ModelContext, registry: StateRegistry): void {
  mc.registerTool({
    name: "agents.list",
    description:
      "List all running agent bubbles in the dashboard. Returns bubbleId, label, and status for each active agent. Use agents.read to get full output for a specific agent.",
    inputSchema: {
      type: "object",
      properties: {},
    },
    execute: async (input) => agentsListExecute(input as AgentsListInput, registry),
    annotations: { readOnlyHint: true },
  });

  mc.registerTool({
    name: "agents.read",
    description:
      "Read the current state and output of a specific agent bubble. Returns the full output buffer, label, and status. Use agents.list to find available bubbleIds.",
    inputSchema: {
      type: "object",
      properties: {
        bubbleId: { type: "string", description: "ID of the agent bubble to read" },
      },
      required: ["bubbleId"],
    },
    execute: async (input) => agentsReadExecute(input as AgentsReadInput, registry),
    annotations: { readOnlyHint: true },
  });

  mc.registerTool({
    name: "agents.interact",
    description:
      "Send input to a running agent bubble (e.g., to respond to an agent waiting for user input). The agent must be in 'attention' status to be waiting for input.",
    inputSchema: {
      type: "object",
      properties: {
        bubbleId: { type: "string", description: "ID of the agent bubble to interact with" },
        input: { type: "string", description: "Text input to send to the agent" },
      },
      required: ["bubbleId", "input"],
    },
    execute: async (input) => agentsInteractExecute(input as AgentsInteractInput, registry),
    annotations: { readOnlyHint: false },
  });
}
