/**
 * Agent Bubble PTY Hook — ADR-160
 *
 * Lightweight version of useXtermTerminal tailored for agent bubbles.
 * - Smaller terminal (80x8)
 * - Read-only by default, writable on double-click in operation mode
 * - Output pattern detection for attention/error states
 * - Auto-kill after timeout
 */
"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { detectAttention, detectError } from "@/lib/chat/attentionPatterns";
import { useAgentBubbleStore } from "@/lib/stores/agentBubbleStore";

type XTerminal = import("@xterm/xterm").Terminal;
type XFitAddon = import("@xterm/addon-fit").FitAddon;

const DARK_THEME = {
  background: "#0a0a0f",
  foreground: "#e4e4e7",
  cursor: "#e4e4e7",
  selectionBackground: "#3b3b5c",
  black: "#09090b",
  red: "#ef4444",
  green: "#22c55e",
  yellow: "#eab308",
  blue: "#3b82f6",
  magenta: "#a855f7",
  cyan: "#06b6d4",
  white: "#e4e4e7",
  brightBlack: "#71717a",
  brightRed: "#f87171",
  brightGreen: "#4ade80",
  brightYellow: "#facc15",
  brightBlue: "#60a5fa",
  brightMagenta: "#c084fc",
  brightCyan: "#22d3ee",
  brightWhite: "#fafafa",
};

const LIGHT_THEME = {
  background: "#F9F8F6",
  foreground: "#111111",
  cursor: "#111111",
  selectionBackground: "rgba(45, 45, 45, 0.25)",
  black: "#111111",
  red: "#B34434",
  green: "#4A6759",
  yellow: "#C06850",
  blue: "#6B5B95",
  magenta: "#5D5650",
  cyan: "#4A6759",
  white: "#555555",
  brightBlack: "#555555",
  brightRed: "#D45545",
  brightGreen: "#5A7869",
  brightYellow: "#D07860",
  brightBlue: "#7B6BA5",
  brightMagenta: "#6D6650",
  brightCyan: "#5A7869",
  brightWhite: "#333333",
};

interface UseAgentBubblePtyOptions {
  bubbleId: string;
  cliId: string | null;
  isRunning: boolean;
  isExpanded: boolean;
  focusMode?: boolean;
  onTerminalData?: (data: string) => void;
  onExit?: (code: number | null) => void;
  mode?: "light" | "dark";
  timeoutMs?: number;
}

interface CliStreamPayload {
  raw?: string;
  event?: string;
  code?: number | null;
}

function openCliRawStream(cliId: string, signal: AbortSignal): Promise<Response> {
  return fetch(`/api/cli?cliId=${cliId}&stream=true&format=raw`, { signal });
}

async function readCliStatus(cliId: string): Promise<{ status?: string }> {
  const statusRes = await fetch(`/api/cli?cliId=${cliId}`);
  return (await statusRes.json()) as { status?: string };
}

function postCliControl(body: Record<string, unknown>): Promise<Response> {
  return fetch("/api/cli", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function loadTerminalModulesForContainer(
  container: HTMLDivElement,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
) {
  const [terminalModule, fitAddonModule] = await Promise.all([
    import("@xterm/xterm"),
    import("@xterm/addon-fit"),
    import("@xterm/xterm/css/xterm.css"),
  ]);
  return {
    stale: containerRef.current !== container,
    Terminal: terminalModule.Terminal,
    FitAddon: fitAddonModule.FitAddon,
  };
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

export function useAgentBubblePty({
  bubbleId,
  cliId,
  isRunning,
  isExpanded,
  focusMode = false,
  onTerminalData,
  onExit,
  mode = "dark",
  timeoutMs = 900_000,
}: UseAgentBubblePtyOptions) {
  const terminalRef = useRef<XTerminal | null>(null);
  const fitAddonRef = useRef<XFitAddon | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const streamConnectedRef = useRef(false);
  const initializingRef = useRef(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastOutputRef = useRef<number>(0);
  const idleTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const onExitRef = useRef(onExit);

  useEffect(() => {
    onExitRef.current = onExit;
  }, [onExit]);

  const updateBubble = useAgentBubbleStore((s) => s.updateBubble);

  const [terminalReady, setTerminalReady] = useState(false);

  // Lazy-init terminal only when expanded
  const terminalContainerRef = useCallback(
    (container: HTMLDivElement | null) => {
      if (!container) return;
      if (containerRef.current === container && terminalRef.current) return;
      if (initializingRef.current) return;
      initializingRef.current = true;

      if (terminalRef.current) {
        terminalRef.current.dispose();
        terminalRef.current = null;
        fitAddonRef.current = null;
        setTerminalReady(false);
      }

    containerRef.current = container;

    (async () => {
      try {
        if (containerRef.current !== container) {
          return;
        }
        const modules = await loadTerminalModulesForContainer(
          container,
          containerRef,
        );
        if (modules.stale) {
          initializingRef.current = false;
          return;
        }
        const { Terminal, FitAddon } = modules;

          const terminal = new Terminal({
            cursorBlink: false,
            disableStdin: true,
            fontSize: 12,
            fontFamily:
              "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Menlo', monospace",
            lineHeight: 1.15,
            theme: mode === "light" ? LIGHT_THEME : DARK_THEME,
            scrollback: 1000,
            convertEol: true,
            rows: 16,
            cols: 100,
          });

          const fitAddon = new FitAddon();
          terminal.loadAddon(fitAddon);
          terminal.open(container);

          requestAnimationFrame(() => {
            fitAddon.fit();
            // Sync PTY size to match fitted terminal dimensions
            const { cols, rows } = terminal;
            if (cols > 0 && rows > 0) {
              fetch("/api/cli", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  action: "resize",
                  cliId: `agent-bubble-${bubbleId}`,
                  cols,
                  rows,
                }),
              }).catch(() => {});
            }
          });

          terminalRef.current = terminal;
          fitAddonRef.current = fitAddon;
          setTerminalReady(true);
        } catch (err) {
          console.error("[AgentBubblePty] Failed to initialize xterm:", err);
        } finally {
          initializingRef.current = false;
        }
      })();
    },
    [mode, bubbleId],
  );

  // INTENTIONAL_SKIP(adr-269): SSE stream — not a REST GET, React Query doesn't apply
  // Connect to SSE stream
  useEffect(() => {
    if (
      !cliId ||
      !isRunning ||
      !isExpanded ||
      !terminalRef.current ||
      !terminalReady
    ) {
      streamConnectedRef.current = false;
      return;
    }

    if (streamConnectedRef.current) return;

    const controller = new AbortController();
    abortRef.current = controller;
    streamConnectedRef.current = true;
    lastOutputRef.current = Date.now();

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = async () => {
      try {
        const res = await openCliRawStream(cliId, controller.signal);

        if (!res.ok || !res.body) {
          // 409 = CLI process has exited — stop reconnecting and update bubble.
          // Check the non-streaming status endpoint for exit code before deciding status.
          if (res.status === 409) {
            streamConnectedRef.current = false;
            try {
              const statusData = await readCliStatus(cliId);
              if (statusData.status === "exited") {
                // Process finished — mark as complete (we can't know exit code here,
                // but a clean exit is the common case for oneshot bubbles)
                updateBubble(bubbleId, {
                  status: "complete",
                  completedAt: Date.now(),
                });
              } else {
                updateBubble(bubbleId, {
                  status: "error",
                  completedAt: Date.now(),
                });
              }
            } catch {
              updateBubble(bubbleId, {
                status: "error",
                completedAt: Date.now(),
              });
            }
            onExitRef.current?.(null);
            return;
          }
          reconnectTimer = setTimeout(connect, 2000);
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();

        const readStream = async (sseBuffer: string): Promise<void> => {
          const { done, value } = await reader.read();
          if (done) {
            reconnectTimer = setTimeout(connect, 1000);
            return;
          }

          const decoded = decoder.decode(value, { stream: true });
          const parts = `${sseBuffer}${decoded}`.split("\n");
          const nextBuffer = parts.pop() || "";

          for (const line of parts) {
            if (!line.startsWith("data: ")) continue;

            let payload: CliStreamPayload;
            try {
              payload = JSON.parse(line.slice(6));
            } catch {
              continue;
            }

            if (typeof payload.raw === "string") {
              let binaryString = "";
              try {
                const padded = payload.raw.padEnd(
                  payload.raw.length + ((4 - (payload.raw.length % 4)) % 4),
                  "=",
                );
                binaryString = atob(padded);
              } catch (err) {
                console.warn("Failed to decode base64 terminal output", err);
                continue;
              }
              const bytes = new Uint8Array(binaryString.length);
              for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
              }
              const text = new TextDecoder().decode(bytes);

              if (terminalRef.current) {
                terminalRef.current.write(bytes);
              }

              lastOutputRef.current = Date.now();

              // Check for attention/error patterns
              const lines = text.split("\n");
              for (const l of lines) {
                if (detectError(l)) {
                  updateBubble(bubbleId, { status: "error" });
                } else if (detectAttention(l)) {
                  updateBubble(bubbleId, { status: "attention" });
                }
              }
            }

            if (payload.event === "exit") {
              streamConnectedRef.current = false;
              const exitCode = payload.code ?? null;
              if (exitCode === 0) {
                updateBubble(bubbleId, {
                  status: "complete",
                  completedAt: Date.now(),
                });
              } else {
                updateBubble(bubbleId, {
                  status: "error",
                  completedAt: Date.now(),
                });
              }
              onExitRef.current?.(exitCode);
              return;
            }
          }
          return readStream(nextBuffer);
        };

        await readStream("");
      } catch (err) {
        if (isAbortError(err)) return;
        if (!controller.signal.aborted) {
          reconnectTimer = setTimeout(connect, 2000);
        }
      }
    };

    connect();

    return () => {
      controller.abort();
      streamConnectedRef.current = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [cliId, isRunning, isExpanded, terminalReady, bubbleId, updateBubble]);

  // Auto-kill timeout
  useEffect(() => {
    if (!isRunning || !cliId) return;

    timeoutRef.current = setTimeout(() => {
      updateBubble(bubbleId, { status: "attention" });
      // Kill the CLI process
      postCliControl({ action: "stop", cliId }).catch(() => {});
    }, timeoutMs);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isRunning, cliId, timeoutMs, bubbleId, updateBubble]);

  // Idle detection (no output for 60s = attention)
  // Only runs when SSE is connected — prevents false positives when bubble
  // hasn't connected to the stream yet (e.g., during terminal initialization).
  useEffect(() => {
    if (!isRunning) return;

    idleTimerRef.current = setInterval(() => {
      if (!streamConnectedRef.current) return;
      const idle = Date.now() - lastOutputRef.current;
      if (idle > 60_000) {
        const bubble = useAgentBubbleStore
          .getState()
          .bubbles.find((b) => b.id === bubbleId);
        if (bubble && bubble.status === "running") {
          updateBubble(bubbleId, { status: "attention" });
        }
      }
    }, 15_000);

    return () => {
      if (idleTimerRef.current) clearInterval(idleTimerRef.current);
    };
  }, [isRunning, bubbleId, updateBubble]);

  // Focus mode toggle
  useEffect(() => {
    if (!terminalRef.current || !terminalReady) return;
    const terminal = terminalRef.current;

    if (focusMode) {
      terminal.options.disableStdin = false;
      terminal.options.cursorBlink = true;
      terminal.focus();
    } else {
      terminal.options.disableStdin = true;
      terminal.options.cursorBlink = false;
    }
  }, [focusMode, terminalReady]);

  // Forward keyboard input to PTY
  useEffect(() => {
    if (!terminalRef.current || !focusMode || !onTerminalData || !terminalReady)
      return;

    const disposable = terminalRef.current.onData((data: string) => {
      onTerminalData(data);
    });

    return () => disposable.dispose();
  }, [focusMode, onTerminalData, terminalReady]);

  // Resize on container changes
  useEffect(() => {
    if (!containerRef.current || !terminalReady) return;

    const observer = new ResizeObserver(() => {
      fitAddonRef.current?.fit();
      // Sync PTY size to match new terminal dimensions
      const term = terminalRef.current;
      if (term && cliId) {
        const { cols, rows } = term;
        if (cols > 0 && rows > 0) {
          postCliControl({ action: "resize", cliId, cols, rows }).catch(() => {});
        }
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [terminalReady, cliId]);

  // Theme update
  useEffect(() => {
    if (!terminalRef.current || !terminalReady) return;
    terminalRef.current.options.theme =
      mode === "light" ? LIGHT_THEME : DARK_THEME;
  }, [mode, terminalReady]);

  // Cleanup on unmount
  const disposeTerminal = useCallback(() => {
    setTerminalReady(false);
    abortRef.current?.abort();
    terminalRef.current?.dispose();
    terminalRef.current = null;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (idleTimerRef.current) clearInterval(idleTimerRef.current);
  }, []);

  useEffect(() => {
    return disposeTerminal;
  }, [disposeTerminal]);

  return {
    terminalContainerRef,
    containerRef,
    terminalRef,
  };
}
