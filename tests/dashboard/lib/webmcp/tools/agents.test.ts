/**
 * @jest-environment node
 */
import { describe, it, expect, beforeEach } from "@jest/globals";
import { StateRegistry } from "@/lib/webmcp/state-registry";
import {
  agentsListExecute,
  agentsReadExecute,
  agentsInteractExecute,
} from "@/lib/webmcp/tools/agents";
import type { AgentBubbleState } from "@/lib/webmcp/types";

// --- Fixtures ---

function makeAgent(
  bubbleId: string,
  actionId: string,
  label: string,
  status: AgentBubbleState["status"],
  output: string,
): AgentBubbleState {
  return { bubbleId, actionId, label, status, output, lastUpdated: Date.now() };
}

describe("agents.list", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns empty list when no agents are registered", async () => {
    const result = await agentsListExecute({}, registry);
    expect(result.agents).toHaveLength(0);
  });

  it("returns all registered agents with bubbleId, label, and status", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "running", "Thinking..."));
    registry.reportAgent(makeAgent("bubble-2", "ai:search", "Search Agent", "complete", "Done."));

    const result = await agentsListExecute({}, registry);
    expect(result.agents).toHaveLength(2);
    const ids = result.agents.map((a) => a.bubbleId);
    expect(ids).toContain("bubble-1");
    expect(ids).toContain("bubble-2");
  });

  it("maps bubbleId, label, and status onto output items", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "running", "Working..."));

    const result = await agentsListExecute({}, registry);
    expect(result.agents).toHaveLength(1);
    const agent = result.agents[0];
    expect(agent.bubbleId).toBe("bubble-1");
    expect(agent.label).toBe("Chat Agent");
    expect(agent.status).toBe("running");
  });

  it("does not include output or actionId in list output", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "running", "secret output"));

    const result = await agentsListExecute({}, registry);
    const agent = result.agents[0] as Record<string, unknown>;
    expect(agent.output).toBeUndefined();
    expect(agent.actionId).toBeUndefined();
  });
});

describe("agents.read", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns NOT_FOUND when agent does not exist", async () => {
    const result = await agentsReadExecute({ bubbleId: "nonexistent" }, registry);
    expect(result).toMatchObject({ error: true, code: "NOT_FOUND" });
    expect((result as { message: string }).message).toContain("nonexistent");
  });

  it("returns full agent state for a registered agent", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "running", "Processing request..."));

    const result = await agentsReadExecute({ bubbleId: "bubble-1" }, registry);
    expect(result).toMatchObject({
      bubbleId: "bubble-1",
      label: "Chat Agent",
      status: "running",
      output: "Processing request...",
    });
  });

  it("reflects updated output after reportAgent is called again", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "running", "Step 1"));
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "complete", "Step 1\nStep 2\nDone."));

    const result = await agentsReadExecute({ bubbleId: "bubble-1" }, registry);
    if ("output" in result) {
      expect(result.output).toBe("Step 1\nStep 2\nDone.");
      expect(result.status).toBe("complete");
    }
  });

  it("returns error status agents correctly", async () => {
    registry.reportAgent(makeAgent("bubble-err", "ai:task", "Task Agent", "error", "Error: timeout"));

    const result = await agentsReadExecute({ bubbleId: "bubble-err" }, registry);
    expect(result).toMatchObject({ status: "error", output: "Error: timeout" });
  });
});

describe("agents.interact", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("returns NOT_FOUND when agent does not exist", async () => {
    const result = await agentsInteractExecute({ bubbleId: "nonexistent", input: "yes" }, registry);
    expect(result).toMatchObject({ error: true, code: "NOT_FOUND" });
    expect((result as { message: string }).message).toContain("nonexistent");
  });

  it("returns success with bubbleId for a registered agent", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "attention", "Waiting for confirmation..."));

    const result = await agentsInteractExecute({ bubbleId: "bubble-1", input: "yes, proceed" }, registry);
    expect(result).toMatchObject({ success: true, bubbleId: "bubble-1" });
  });

  it("succeeds for agents in any status", async () => {
    for (const status of ["running", "attention", "complete", "error"] as AgentBubbleState["status"][]) {
      registry.reportAgent(makeAgent("bubble-test", "ai:chat", "Agent", status, "output"));
      const result = await agentsInteractExecute({ bubbleId: "bubble-test", input: "test" }, registry);
      expect(result).toMatchObject({ success: true, bubbleId: "bubble-test" });
    }
  });
});

describe("StateRegistry agent lifecycle", () => {
  let registry: StateRegistry;

  beforeEach(() => {
    registry = new StateRegistry();
  });

  it("removes agent on removeAgent call", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "running", ""));
    registry.removeAgent("bubble-1");

    const result = await agentsListExecute({}, registry);
    expect(result.agents).toHaveLength(0);
  });

  it("clears all agents on registry.clear()", async () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Agent 1", "running", ""));
    registry.reportAgent(makeAgent("bubble-2", "ai:search", "Agent 2", "complete", ""));
    registry.clear();

    const result = await agentsListExecute({}, registry);
    expect(result.agents).toHaveLength(0);
  });

  it("updates agent state on repeated reportAgent with same bubbleId", () => {
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "running", ""));
    registry.reportAgent(makeAgent("bubble-1", "ai:chat", "Chat Agent", "complete", "Finished"));

    const agent = registry.getAgent("bubble-1");
    expect(agent?.status).toBe("complete");
    expect(agent?.output).toBe("Finished");
  });

  it("getAgent returns undefined for unknown bubbleId", () => {
    expect(registry.getAgent("unknown")).toBeUndefined();
  });
});
