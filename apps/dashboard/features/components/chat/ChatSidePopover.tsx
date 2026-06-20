"use client";

import { useState, useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function ChatSidePopover({
  chatRef,
  portalRef,
  children,
}: {
  chatRef: React.RefObject<HTMLDivElement | null>;
  portalRef?: React.RefObject<HTMLDivElement | null>;
  children: ReactNode;
}) {
  const [pos, setPos] = useState<{ top: number; right: number } | null>(null);

  useEffect(() => {
    const el = chatRef.current;
    if (!el) return;
    const update = () => {
      const rect = el.getBoundingClientRect();
      setPos({
        top: rect.bottom - 8, // align near the bottom of the chat window
        right: window.innerWidth - rect.left + 8, // 8px gap to the left of chat
      });
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [chatRef]);

  if (!pos) return null;

  return createPortal(
    <div
      ref={portalRef}
      style={{
        position: "fixed",
        bottom: window.innerHeight - pos.top,
        right: pos.right,
        zIndex: 60,
      }}
    >
      {children}
    </div>,
    document.body,
  );
}
