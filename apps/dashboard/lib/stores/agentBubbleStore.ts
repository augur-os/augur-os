/**
 * Agent Bubble Store — ADR-160
 *
 * Manages the lifecycle of agent bubbles independently from the main chatStore.
 * Supports up to MAX_BUBBLES concurrent bubbles with a FIFO queue for overflow.
 */
import { create } from "zustand";

export const MAX_BUBBLES = 5;

export type AgentBubbleStatus = "running" | "attention" | "complete" | "error";

export interface AgentBubbleState {
  id: string;
  actionId: string;
  actionLabel: string;
  status: AgentBubbleStatus;
  isExpanded: boolean;
  pid?: number;
  startedAt: number;
  completedAt?: number;
}

export interface QueuedBubble {
  actionId: string;
  actionLabel: string;
  prompt: string;
  pageContext?: string;
}

export interface AgentBubbleStoreState {
  bubbles: AgentBubbleState[];
  queue: QueuedBubble[];

  addBubble: (bubble: Omit<AgentBubbleState, "id">) => string | null;
  removeBubble: (id: string) => void;
  updateBubble: (id: string, patch: Partial<AgentBubbleState>) => void;
  toggleExpanded: (id: string) => void;
  getBubbleCount: () => number;
  enqueue: (item: QueuedBubble) => void;
  dequeue: () => QueuedBubble | null;
  getQueueCount: () => number;
}

export const useAgentBubbleStore = create<AgentBubbleStoreState>(
  (set, get) => ({
    bubbles: [],
    queue: [],

    addBubble: (bubble) => {
      const state = get();
      if (state.bubbles.length >= MAX_BUBBLES) {
        return null;
      }
      const id = crypto.randomUUID();
      set((s) => ({
        bubbles: [...s.bubbles, { ...bubble, id }],
      }));
      return id;
    },

    removeBubble: (id) => {
      set((s) => ({
        bubbles: s.bubbles.filter((b) => b.id !== id),
      }));

      // ADR-160: Auto-dequeue next item when a slot opens
      const state = get();
      if (state.queue.length > 0 && state.bubbles.length < MAX_BUBBLES) {
        const next = get().dequeue();
        if (next) {
          // Spawn the queued bubble asynchronously
          const newId = get().addBubble({
            actionId: next.actionId,
            actionLabel: next.actionLabel,
            status: "running",
            isExpanded: false,
            startedAt: Date.now(),
          });
          if (newId) {
            // Start CLI for the dequeued item
            fetch("/api/cli", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                action: "start",
                cliId: `agent-bubble-${newId}`,
                current_page: next.pageContext,
                oneshotPrompt: next.prompt,
              }),
            })
              .then(async (res) => {
                if (!res.ok) {
                  get().updateBubble(newId, { status: "error" });
                  return;
                }
                const data = await res.json();
                if (res.ok) {
                  get().updateBubble(newId, { pid: data.pid });
                } else {
                  get().updateBubble(newId, { status: "error" });
                }
              })
              .catch(() => {
                get().updateBubble(newId, { status: "error" });
              });
          }
        }
      }
    },

    updateBubble: (id, patch) => {
      set((s) => ({
        bubbles: s.bubbles.map((b) => (b.id === id ? { ...b, ...patch } : b)),
      }));
    },

    toggleExpanded: (id) => {
      set((s) => ({
        bubbles: s.bubbles.map((b) =>
          b.id === id ? { ...b, isExpanded: !b.isExpanded } : b,
        ),
      }));
    },

    getBubbleCount: () => get().bubbles.length,

    enqueue: (item) => {
      set((s) => ({
        queue: [...s.queue, item],
      }));
    },

    dequeue: () => {
      const state = get();
      if (state.queue.length === 0) return null;
      const [next, ...rest] = state.queue;
      set({ queue: rest });
      return next;
    },

    getQueueCount: () => get().queue.length,
  }),
);
