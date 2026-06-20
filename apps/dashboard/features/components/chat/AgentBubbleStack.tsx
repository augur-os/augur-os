/**
 * AgentBubbleStack — ADR-160
 *
 * Renders agent bubbles stacked vertically above the FloatingChat window.
 * Each bubble is an independent CLI session for a oneshot agent task.
 */
"use client";

import { useChatStore } from "@/lib/stores/chatStore";
import { useAgentBubbleStore } from "@/lib/stores/agentBubbleStore";
import { AgentBubble } from "./AgentBubble";

export function AgentBubbleStack() {
  const bubbles = useAgentBubbleStore((s) => s.bubbles);
  const queueCount = useAgentBubbleStore((s) => s.queue.length);
  const isChatOpen = useChatStore((s) => s.isOpen);
  const isEnlarged = useChatStore((s) => s.isEnlarged);

  if (bubbles.length === 0 && queueCount === 0) return null;

  // Position above FloatingChat window or FAB.
  // FAB: 48px tall at bottom-6 (24px). Bubbles must clear it: 24 + 48 + 8 = 80px.
  // Chat window: 600px normal, 960px enlarged, capped at 100vh-3rem.
  let bottomOffset: string;
  if (!isChatOpen) {
    bottomOffset = "calc(1.5rem + 56px)";
  } else if (isEnlarged) {
    bottomOffset = "calc(1.5rem + min(960px, calc(100vh - 3rem)) + 8px)";
  } else {
    bottomOffset = "calc(1.5rem + min(600px, calc(100vh - 3rem)) + 8px)";
  }

  return (
    <div
      className="fixed right-6 z-50 flex flex-col-reverse items-end gap-2 pointer-events-auto"
      style={{ bottom: bottomOffset }}
    >
      {bubbles.map((bubble) => (
        <AgentBubble key={bubble.id} bubble={bubble} />
      ))}

      {/* Queue indicator */}
      {queueCount > 0 && (
        <div className="inline-flex items-center h-7 px-3 rounded-full border border-[var(--border-color)] bg-[var(--bg-card)] shadow-sm">
          <span className="text-[10px] text-[var(--text-secondary)]">
            {queueCount} queued
          </span>
        </div>
      )}
    </div>
  );
}
