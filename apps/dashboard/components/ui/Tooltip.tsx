"use client";

import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, LazyMotion, domAnimation, m } from "framer-motion";

interface TooltipProps {
  children: React.ReactNode;
  content: React.ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  className?: string;
  delay?: number;
}

export function Tooltip({
  children,
  content,
  side = "top",
  className = "",
  delay = 0,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const canPortal = typeof document !== "undefined";

  useEffect(() => {
    if (isVisible && triggerRef.current) {
      const updatePosition = () => {
        const rect = triggerRef.current!.getBoundingClientRect();
        const scrollX = window.scrollX;
        const scrollY = window.scrollY;
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        let top = 0;
        let left = 0;
        let usedSide = side;

        // Simple flip logic
        if (side === "top" && rect.top < 50) usedSide = "bottom";
        if (side === "bottom" && rect.bottom > viewportHeight - 50)
          usedSide = "top";
        if (side === "left" && rect.left < 100) usedSide = "right";
        if (side === "right" && rect.right > viewportWidth - 100)
          usedSide = "left";

        // Recalculate based on final side
        switch (usedSide) {
          case "top":
            top = rect.top + scrollY - 8;
            left = rect.left + scrollX + rect.width / 2;
            break;
          case "bottom":
            top = rect.bottom + scrollY + 8;
            left = rect.left + scrollX + rect.width / 2;
            break;
          case "left":
            top = rect.top + scrollY + rect.height / 2;
            left = rect.left + scrollX - 8;
            break;
          case "right":
            top = rect.top + scrollY + rect.height / 2;
            left = rect.right + scrollX + 8;
            break;
        }
        if (tooltipRef.current) {
          tooltipRef.current.style.top = `${top}px`;
          tooltipRef.current.style.left = `${left}px`;
        }
      };
      updatePosition();
      window.addEventListener("scroll", updatePosition, { passive: true });
      window.addEventListener("resize", updatePosition);

      return () => {
        window.removeEventListener("scroll", updatePosition);
        window.removeEventListener("resize", updatePosition);
      };
    }
  }, [isVisible, side]);

  const initial = {
    opacity: 0,
    scale: 0.95,
    ...(side === "top" ? { y: 4, x: "-50%" } : {}),
    ...(side === "bottom" ? { y: -4, x: "-50%" } : {}),
    ...(side === "left" ? { x: 4, y: "-50%" } : {}),
    ...(side === "right" ? { x: -4, y: "-50%" } : {}),
  };

  const animate = {
    opacity: 1,
    scale: 1,
    ...(side === "top" || side === "bottom" ? { x: "-50%", y: 0 } : {}),
    ...(side === "left" || side === "right" ? { x: 0, y: "-50%" } : {}),
  };

  // Safe portal rendering
  const portalContent =
    canPortal && isVisible
      ? createPortal(
          <m.div
            ref={tooltipRef}
            initial={initial}
            animate={animate}
            exit={initial}
            transition={{ duration: 0.15, delay: delay }}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              zIndex: 70, // Above modals (z-50) but below critical overlays (z-100)
              pointerEvents: "none",
            }}
            className="px-2.5 py-1.5 text-xs text-[var(--text-secondary)] bg-[var(--bg-popover)] border border-[var(--border-color)] rounded-md shadow-xl whitespace-nowrap backdrop-blur-sm"
          >
            {content}
          </m.div>,
          document.body,
        )
      : null;

  return (
    <div
      ref={triggerRef}
      className={`relative group ${className || "inline-block"}`}
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      {children}
      <LazyMotion features={domAnimation}>
        <AnimatePresence>{portalContent}</AnimatePresence>
      </LazyMotion>
    </div>
  );
}
