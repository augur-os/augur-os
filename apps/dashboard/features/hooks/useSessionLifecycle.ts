/**
 * ADR-157 Decision 4: Continuous Session Lifecycle Hook
 *
 * Orchestrates CLI session lifecycle events:
 * - Page navigation → auto-refocus
 * - Idle timeout → context save
 * - Chat close → graceful save
 */

import { useEffect, useRef, useCallback, useEffectEvent } from "react";

export interface SessionLifecycleCallbacks {
  /** Send a system command to the CLI without showing in chat history */
  sendSystemCommand: (command: string) => void;
  /** Whether the CLI is currently running */
  isRunning: boolean;
  /** Whether we're in operation mode */
  isOperationMode: boolean;
}

/** Idle timeout before auto-saving context (5 minutes) */
const IDLE_TIMEOUT_MS = 5 * 60 * 1000;

export function useSessionLifecycle({
  sendSystemCommand,
  isRunning,
  isOperationMode,
}: SessionLifecycleCallbacks) {
  const idleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clearIdleTimer = useCallback(() => {
    if (idleTimerRef.current) {
      clearTimeout(idleTimerRef.current);
      idleTimerRef.current = null;
    }
  }, []);

  // Reset idle timer on any user activity
  const resetIdleTimer = useCallback(() => {
    clearIdleTimer();

    if (!isRunning || !isOperationMode) return;

    idleTimerRef.current = setTimeout(() => {
      if (isRunning) {
        sendSystemCommand("/save");
      }
    }, IDLE_TIMEOUT_MS);
  }, [clearIdleTimer, isRunning, isOperationMode, sendSystemCommand]);
  const resetIdleTimerFromEffect = useEffectEvent(() => {
    resetIdleTimer();
  });

  // Track user activity for idle detection
  useEffect(() => {
    if (!isOperationMode || !isRunning) return;

    const events = ["keydown", "mousedown", "scroll", "touchstart"];
    const handler = () => resetIdleTimerFromEffect();

    for (const event of events) {
      window.addEventListener(event, handler, { passive: true });
    }

    // Start the initial idle timer
    resetIdleTimerFromEffect();

    return () => {
      for (const event of events) {
        window.removeEventListener(event, handler);
      }
      clearIdleTimer();
    };
  }, [clearIdleTimer, isOperationMode, isRunning]);

  /**
   * Call this before closing the chat to save context gracefully.
   */
  const saveBeforeClose = useCallback(() => {
    if (!isRunning || !isOperationMode) return;
    sendSystemCommand("/save");
  }, [isRunning, isOperationMode, sendSystemCommand]);

  return {
    saveBeforeClose,
    resetIdleTimer,
  };
}
