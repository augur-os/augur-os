"use client";

import { useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";

interface Shortcut {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  description: string;
  action: () => void;
}

function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) {
    return false;
  }

  return (
    element.tagName === "INPUT" ||
    element.tagName === "TEXTAREA" ||
    element.isContentEditable
  );
}

function keyMatchesShortcut(event: KeyboardEvent, shortcut: Shortcut): boolean {
  return (
    event.key.toLowerCase() === shortcut.key.toLowerCase() ||
    (shortcut.key === "?" && event.key === "?" && event.shiftKey)
  );
}

function modifierMatches(
  actualPressed: boolean,
  requiredPressed: boolean | undefined,
  enforceAbsentWhenUndefined: boolean,
): boolean {
  if (requiredPressed) {
    return actualPressed;
  }

  if (enforceAbsentWhenUndefined) {
    return !actualPressed;
  }

  return true;
}

function matchesShortcut(event: KeyboardEvent, shortcut: Shortcut): boolean {
  const keyMatch = keyMatchesShortcut(event, shortcut);
  const ctrlMatch = modifierMatches(event.ctrlKey, shortcut.ctrl, true);
  const metaMatch = modifierMatches(event.metaKey, shortcut.meta, true);
  const shiftMatch = modifierMatches(event.shiftKey, shortcut.shift, false);

  return (
    keyMatch && ctrlMatch && metaMatch && (shortcut.shift ? shiftMatch : true)
  );
}

export function useKeyboardShortcuts(
  customShortcuts?: Shortcut[],
  onShowHelp?: () => void,
) {
  const router = useRouter();

  const shortcuts: Shortcut[] = useMemo(
    () => [
      {
        key: "h",
        description: "Go to Dashboard",
        action: () => router.push("/"),
      },
      {
        key: "c",
        description: "Go to Career",
        action: () => router.push("/career"),
      },
      {
        key: "a",
        description: "Go to Admin",
        action: () => router.push("/admin"),
      },
      { key: "d", description: "Go to Dev", action: () => router.push("/dev") },
      {
        key: "s",
        description: "Go to Productivity",
        action: () => router.push("/life"),
      },
      {
        key: "l",
        description: "Go to Life",
        action: () => router.push("/life"),
      },
      {
        key: "?",
        shift: true,
        description: "Show keyboard shortcuts",
        action: () => onShowHelp?.(),
      },
      {
        key: "/",
        meta: true,
        description: "Show keyboard shortcuts",
        action: () => onShowHelp?.(),
      },
      { key: "Escape", description: "Close dialog/modal", action: () => {} }, // Placeholder, handled by modals
      ...(customShortcuts || []),
    ],
    [customShortcuts, onShowHelp, router],
  );
  const shortcutsRef = useRef(shortcuts);
  useEffect(() => {
    shortcutsRef.current = shortcuts;
  }, [shortcuts]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) {
        return;
      }

      for (const shortcut of shortcutsRef.current) {
        if (matchesShortcut(event, shortcut)) {
          event.preventDefault();
          shortcut.action();
          return;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return shortcuts;
}

export const SHORTCUT_LIST = [
  { keys: ["?"], description: "Show keyboard shortcuts" },
  { keys: ["H"], description: "Go to Dashboard" },
  { keys: ["C"], description: "Go to Career" },
  { keys: ["A"], description: "Go to Operations" },
  { keys: ["B"], description: "Go to Brain" },
  { keys: ["S"], description: "Go to Sense" },
  { keys: ["L"], description: "Go to Lifestyle" },
  { keys: ["Esc"], description: "Close dialog/modal" },
];
