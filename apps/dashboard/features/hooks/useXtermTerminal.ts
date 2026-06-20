"use client";

import { useEffect, useRef, useCallback, useState } from "react";

// Lazy-loaded xterm types — the actual modules are imported dynamically
// to avoid SSR issues (xterm.js accesses the DOM at import time).
type XTerminal = import("@xterm/xterm").Terminal;
type XFitAddon = import("@xterm/addon-fit").FitAddon;

// Terminal themes matching app light/dark modes
const DARK_TERMINAL_THEME = {
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

const LIGHT_TERMINAL_THEME = {
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

interface UseXtermTerminalOptions {
  cliId: string | null;
  isRunning: boolean;
  focusMode?: boolean;
  onTerminalData?: (data: string) => void;
  onExit?: (code: number | null) => void;
  onRawOutput?: (data: string) => void;
  mode?: "light" | "dark";
}

interface CliStreamPayload {
  raw?: string;
  event?: string;
  code?: number | null;
  cursor?: number;
  reset?: boolean;
}

function buildCliStreamUrl(cliId: string, cursor: number, detached: boolean): string {
  const cursorSuffix = cursor > 0 ? `&cursor=${cursor}` : "";
  if (detached) {
    return `/api/cli?cliId=${cliId}&action=reconnect&format=raw${cursorSuffix}`;
  }
  return `/api/cli?cliId=${cliId}&stream=true&format=raw${cursorSuffix}`;
}

async function isCliDetached(
  cliId: string,
  signal: AbortSignal,
): Promise<boolean> {
  const statusRes = await fetch(`/api/cli?cliId=${cliId}`, { signal });
  if (!statusRes.ok) {
    return false;
  }
  const statusData = await statusRes.json();
  return statusData.status === "detached" || Boolean(statusData.detached);
}

function openCliStream(url: string, signal: AbortSignal): Promise<Response> {
  return fetch(url, { signal });
}

function postCliControl(body: Record<string, unknown>): Promise<Response> {
  return fetch("/api/cli", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function loadXtermModulesForContainer(
  container: HTMLDivElement,
  containerRef: React.MutableRefObject<HTMLDivElement | null>,
) {
  const [terminalModule, fitAddonModule, webLinksModule] = await Promise.all([
    import("@xterm/xterm"),
    import("@xterm/addon-fit"),
    import("@xterm/addon-web-links"),
    import("@xterm/xterm/css/xterm.css"),
  ]);
  return {
    stale: containerRef.current !== container,
    Terminal: terminalModule.Terminal,
    FitAddon: fitAddonModule.FitAddon,
    WebLinksAddon: webLinksModule.WebLinksAddon,
  };
}

interface SseChunkResult {
  lines: string[];
  buffer: string;
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function splitSseChunk(buffer: string, chunk: string): SseChunkResult {
  const parts = `${buffer}${chunk}`.split("\n");
  return {
    lines: parts.slice(0, -1),
    buffer: parts[parts.length - 1] || "",
  };
}

function parseSsePayload(line: string): CliStreamPayload | null {
  if (!line.startsWith("data: ")) {
    return null;
  }

  try {
    return JSON.parse(line.slice(6));
  } catch {
    return null;
  }
}

function decodeRawBase64(raw: string): { bytes: Uint8Array; text: string } {
  let binaryString = "";
  try {
    const padded = raw.padEnd(raw.length + ((4 - (raw.length % 4)) % 4), "=");
    binaryString = atob(padded);
  } catch (err) {
    console.warn("Failed to decode base64 terminal output", err);
    return { bytes: new Uint8Array(), text: "" };
  }
  const bytes = new Uint8Array(binaryString.length);

  for (let i = 0; i < binaryString.length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }

  // Decode as UTF-8 for the text parser. atob() returns Latin-1 which
  // mangles multi-byte UTF-8 characters (box-drawing, emoji, etc.)
  const text = new TextDecoder().decode(bytes);

  return { bytes, text };
}

function writeRawPayload(
  raw: string,
  terminal: XTerminal | null,
  onRawOutput?: (data: string) => void,
) {
  const decoded = decodeRawBase64(raw);

  // Always feed the parser so session state stays in sync with terminal output.
  onRawOutput?.(decoded.text);

  if (terminal) {
    terminal.write(decoded.bytes);
  }
}

async function streamSseOutput(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  terminalRef: React.MutableRefObject<XTerminal | null>,
  rawCursorRef: React.MutableRefObject<number>,
  onRawOutput: ((data: string) => void) | undefined,
  onPayload: (payload: CliStreamPayload) => boolean,
): Promise<boolean> {
  return streamSseOutputChunk(
    reader,
    terminalRef,
    rawCursorRef,
    onRawOutput,
    onPayload,
    new TextDecoder(),
    "",
  );
}

async function streamSseOutputChunk(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  terminalRef: React.MutableRefObject<XTerminal | null>,
  rawCursorRef: React.MutableRefObject<number>,
  onRawOutput: ((data: string) => void) | undefined,
  onPayload: (payload: CliStreamPayload) => boolean,
  decoder: TextDecoder,
  sseBuffer: string,
): Promise<boolean> {
  const { done, value } = await reader.read();
  if (done) {
    return false;
  }

  const decoded = decoder.decode(value, { stream: true });
  const parsed = splitSseChunk(sseBuffer, decoded);

  const exited = parsed.lines.some((line) => {
    const payload = parseSsePayload(line);
    if (!payload) {
      return false;
    }

    if (typeof payload.raw === "string") {
      if (payload.reset && terminalRef.current) {
        terminalRef.current.clear();
      }
      writeRawPayload(payload.raw, terminalRef.current, onRawOutput);
      if (typeof payload.cursor === "number" && Number.isFinite(payload.cursor)) {
        rawCursorRef.current = payload.cursor;
      }
    }

    return onPayload(payload);
  });

  if (exited) {
    return true;
  }

  return streamSseOutputChunk(
    reader,
    terminalRef,
    rawCursorRef,
    onRawOutput,
    onPayload,
    decoder,
    parsed.buffer,
  );
}

/**
 * Manages an xterm.js terminal instance connected to the raw PTY SSE stream.
 * By default the terminal is read-only (disableStdin: true) — input goes
 * through the chat input bar via POST /api/cli send action.
 *
 * When focusMode is enabled, stdin is enabled and keyboard input is forwarded
 * directly to the PTY via the onTerminalData callback. This allows interactive
 * CLI features (checkboxes, arrow keys, y/n prompts) to work.
 *
 * xterm.js modules are loaded lazily via dynamic import() to avoid SSR issues.
 * This hook should be called from a stable parent component (not inside a
 * dynamically imported component) so that its state survives re-renders.
 */
export function useXtermTerminal({
  cliId,
  isRunning,
  focusMode = false,
  onTerminalData,
  onExit,
  onRawOutput,
  mode = "dark",
}: UseXtermTerminalOptions) {
  const terminalRef = useRef<XTerminal | null>(null);
  const fitAddonRef = useRef<XFitAddon | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const streamConnectedRef = useRef(false);
  const initializingRef = useRef(false);
  const rawCursorRef = useRef(0);
  const wasRunningRef = useRef(false);

  const onExitRef = useRef(onExit);

  const onRawOutputRef = useRef(onRawOutput);

  useEffect(() => {
    onExitRef.current = onExit;
  }, [onExit]);

  useEffect(() => {
    onRawOutputRef.current = onRawOutput;
  }, [onRawOutput]);

  const [terminalReady, setTerminalReady] = useState(false);

  /**
   * Ref callback for the terminal container div.
   * Lazily loads xterm.js and initializes the terminal on first mount.
   */
  const terminalContainerRef = useCallback(
    (container: HTMLDivElement | null) => {
      if (!container) {
        // Unmounting — cleanup handled by the cleanup effect
        return;
      }

      // Already initialized into this container
      if (containerRef.current === container && terminalRef.current) return;

      // Prevent concurrent initialization
      if (initializingRef.current) return;
      initializingRef.current = true;

      // Dispose previous instance if switching containers
      if (terminalRef.current) {
        terminalRef.current.dispose();
        terminalRef.current = null;
        fitAddonRef.current = null;
        setTerminalReady(false);
      }

      containerRef.current = container;

      // Lazy-load xterm.js modules and initialize
      (async () => {
        try {
          if (containerRef.current !== container) {
            return;
          }
          const modules = await loadXtermModulesForContainer(
            container,
            containerRef,
          );
          if (modules.stale) {
            initializingRef.current = false;
            return;
          }
          const { Terminal, FitAddon, WebLinksAddon } = modules;

          const terminal = new Terminal({
            cursorBlink: false,
            disableStdin: true,
            fontSize: 13,
            fontFamily:
              "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Menlo', monospace",
            lineHeight: 1.2,
            theme:
              mode === "light" ? LIGHT_TERMINAL_THEME : DARK_TERMINAL_THEME,
            scrollback: 5000,
            convertEol: true,
          });

          const fitAddon = new FitAddon();
          terminal.loadAddon(fitAddon);
          terminal.loadAddon(new WebLinksAddon());

          terminal.open(container);

          // Initial fit after a frame so the container has layout dimensions
          requestAnimationFrame(() => {
            fitAddon.fit();
          });

          terminalRef.current = terminal;
          fitAddonRef.current = fitAddon;
          setTerminalReady(true);
        } catch (err) {
          console.error("Failed to initialize xterm.js:", err);
        } finally {
          initializingRef.current = false;
        }
      })();
    },
    [mode],
  );

  /**
   * Connect to the raw SSE stream for the given CLI and pipe data
   * directly into xterm.js.  Includes automatic reconnection on
   * unexpected disconnects (network hiccups, server restarts).
   */
  // INTENTIONAL_SKIP(adr-269): SSE stream — not a REST GET, React Query doesn't apply
  useEffect(() => {
    if (!cliId || !isRunning || !terminalRef.current || !terminalReady) {
      streamConnectedRef.current = false;
      if (!isRunning) {
        wasRunningRef.current = false;
      }
      return;
    }

    if (!wasRunningRef.current) {
      rawCursorRef.current = 0;
      wasRunningRef.current = true;
    }

    // Avoid duplicate connections
    if (streamConnectedRef.current) return;

    const controller = new AbortController();
    abortRef.current = controller;
    streamConnectedRef.current = true;

    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    const scheduleReconnect = (delayMs: number) => {
      if (controller.signal.aborted) {
        return;
      }
      reconnectTimer = setTimeout(connect, delayMs);
    };

    const handlePayload = (payload: CliStreamPayload): boolean => {
      if (payload.event !== "exit") {
        return false;
      }
      streamConnectedRef.current = false;
      // Wipe the ended session's scrollback — including any half-rendered TUI
      // frame captured at the moment of exit (e.g. an open slash-command menu)
      // — so it neither lingers after the session ends nor stacks beneath the
      // next session's output. The "CLI session ended." status banner is
      // rendered separately by the chat shell and is unaffected.
      terminalRef.current?.reset();
      onExitRef.current?.(payload.code ?? null);
      return true;
    };

    const connect = async () => {
      try {
        // ADR-535 0E: First check if server has a detached session we can reconnect to.
        // This handles browser tab refresh — the PTY is still alive on the server.
          let detached = false;
          try {
            detached = await isCliDetached(cliId, controller.signal);
          } catch {
            // Status check failed — fall through to normal stream connect
          }
          const url = buildCliStreamUrl(cliId, rawCursorRef.current, detached);

          const res = await openCliStream(url, controller.signal);

        if (!res.ok || !res.body) {
          scheduleReconnect(2000);
          return;
        }

        const reader = res.body.getReader();
        const exited = await streamSseOutput(
          reader,
          terminalRef,
          rawCursorRef,
          onRawOutputRef.current,
          handlePayload,
        );

        // Stream ended without exit event — reconnect
        if (!exited) {
          scheduleReconnect(1000);
        }
      } catch (err: unknown) {
        if (isAbortError(err)) {
          return;
        }
        // Suppress "Failed to fetch" errors - these are expected when server is restarting
        if (
          err instanceof TypeError &&
          (err as TypeError).message === "Failed to fetch"
        ) {
          scheduleReconnect(2000);
          return;
        }
        console.error("[XTERM] SSE stream error:", err);
        // Reconnect on error
        scheduleReconnect(2000);
      }
    };

    connect();

    return () => {
      controller.abort();
      streamConnectedRef.current = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [cliId, isRunning, terminalReady]);

  useEffect(() => {
    rawCursorRef.current = 0;
  }, [cliId]);

  /**
   * Fit the terminal to its container and report the new size to the
   * server so the PTY dimensions stay in sync.
   */
  const handleResize = useCallback(() => {
    if (!fitAddonRef.current || !terminalRef.current || !cliId) return;

    fitAddonRef.current.fit();
    const { cols, rows } = terminalRef.current;

    // INTENTIONAL_SKIP(adr-269): fire-and-forget POST mutation — not a REST GET
    // Report new dimensions to server for PTY resize
    postCliControl({ action: "resize", cliId, cols, rows }).catch(() => {
      // Best-effort resize — don't break on failure
    });
  }, [cliId]);

  /**
   * Watch the container for size changes and re-fit automatically.
   */
  useEffect(() => {
    if (!containerRef.current || !terminalReady) return;

    const observer = new ResizeObserver(() => {
      handleResize();
    });
    observer.observe(containerRef.current);

    return () => observer.disconnect();
  }, [handleResize, terminalReady]);

  /**
   * Toggle terminal stdin and cursor based on focus mode.
   * When in focus mode, the terminal accepts direct keyboard input.
   */
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

  /**
   * Forward terminal keyboard input to PTY via callback when in focus mode.
   * xterm.js onData fires with the typed character or escape sequence
   * (e.g., arrow keys, space for checkboxes, Enter to confirm).
   */
  useEffect(() => {
    if (!terminalRef.current || !focusMode || !onTerminalData || !terminalReady)
      return;

    const disposable = terminalRef.current.onData((data: string) => {
      onTerminalData(data);
    });

    return () => disposable.dispose();
  }, [focusMode, onTerminalData, terminalReady]);

  /**
   * Intercept Escape key in focus mode to prevent it from reaching the PTY.
   * The parent component handles Escape to exit focus mode.
   */
  useEffect(() => {
    if (!terminalRef.current || !focusMode || !terminalReady) return;

    const terminal = terminalRef.current;

    terminal.attachCustomKeyEventHandler((event: KeyboardEvent) => {
      if (event.key === "Escape") {
        return false; // Block Escape from reaching PTY
      }
      return true;
    });

    return () => {
      terminal.attachCustomKeyEventHandler(() => true);
    };
  }, [focusMode, terminalReady]);

  /**
   * Update terminal theme when mode changes.
   */
  useEffect(() => {
    if (!terminalRef.current || !terminalReady) return;
    terminalRef.current.options.theme =
      mode === "light" ? LIGHT_TERMINAL_THEME : DARK_TERMINAL_THEME;
  }, [mode, terminalReady]);

  /**
   * Clear the terminal contents (e.g., when switching CLIs).
   */
  const clearTerminal = useCallback(() => {
    terminalRef.current?.clear();
  }, []);

  /**
   * Cleanup on unmount.
   */
  const disposeTerminal = useCallback(() => {
    setTerminalReady(false);
    abortRef.current?.abort();
    rawCursorRef.current = 0;
    terminalRef.current?.dispose();
    terminalRef.current = null;
  }, []);

  useEffect(() => {
    return disposeTerminal;
  }, [disposeTerminal]);

  return {
    terminalContainerRef,
    clearTerminal,
    handleResize,
    terminalRef,
    containerRef,
  };
}
