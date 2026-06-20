"use client";

import { useEffect, useRef, useState } from "react";
import { Code2 } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";

interface WidgetConfig {
  title?: string;
  html?: string;
  height?: number;
}

interface WidgetData {
  title?: string;
  html: string;
  height?: number;
}

const CDN_ALLOWLIST = [
  "https://cdnjs.cloudflare.com",
  "https://cdn.jsdelivr.net",
  "https://unpkg.com",
  "https://esm.sh",
];

const THEME_CSS = `
:root {
  --color-background-primary: hsl(var(--background, 0 0% 100%));
  --color-background-secondary: hsl(var(--muted, 210 40% 96%));
  --color-background-tertiary: hsl(var(--card, 0 0% 100%));
  --color-text-primary: hsl(var(--foreground, 222 84% 5%));
  --color-text-secondary: hsl(var(--muted-foreground, 215 16% 47%));
  --color-text-tertiary: hsl(var(--muted-foreground, 215 16% 47%) / 0.7);
  --color-border-tertiary: hsl(var(--border, 214 32% 91%));
  --color-border-secondary: hsl(var(--border, 214 32% 91%));
  --color-border-primary: hsl(var(--ring, 222 84% 5%));
  --color-background-info: hsl(217 91% 60% / 0.1);
  --color-background-danger: hsl(var(--destructive, 0 84% 60%) / 0.1);
  --color-background-success: hsl(142 76% 36% / 0.1);
  --color-background-warning: hsl(38 92% 50% / 0.1);
  --color-text-info: hsl(217 91% 60%);
  --color-text-danger: hsl(var(--destructive, 0 84% 60%));
  --color-text-success: hsl(142 76% 36%);
  --color-text-warning: hsl(38 92% 50%);
  --font-sans: system-ui, -apple-system, sans-serif;
  --font-serif: Georgia, serif;
  --font-mono: ui-monospace, monospace;
  --border-radius-md: 8px;
  --border-radius-lg: 12px;
  --border-radius-xl: 16px;
}
body {
  margin: 0;
  padding: 0;
  font-family: var(--font-sans);
  font-size: 16px;
  line-height: 1.7;
  color: var(--color-text-primary);
  background: transparent;
}
`;

function buildSrcdoc(html: string): string {
  const csp = [
    "default-src 'none'",
    `script-src 'unsafe-inline' ${CDN_ALLOWLIST.join(" ")}`,
    `style-src 'unsafe-inline' ${CDN_ALLOWLIST.join(" ")}`,
    `connect-src ${CDN_ALLOWLIST.join(" ")}`,
    `font-src ${CDN_ALLOWLIST.join(" ")}`,
  ].join("; ");

  const resizeScript = `
    <script>
      function notifyResize() {
        window.parent.postMessage(
          { type: "augur:resize", height: document.body.scrollHeight },
          "*"
        );
      }
      new ResizeObserver(notifyResize).observe(document.body);
      window.addEventListener("load", notifyResize);
    </script>
  `;

  return `<meta http-equiv="Content-Security-Policy" content="${csp}">
<style>${THEME_CSS}</style>
${html}
${resizeScript}`;
}

export default function WidgetBlock(props: BlockProps<WidgetConfig>) {
  const { config, dataSource, onExpand } = props;
  const { title = "Widget" } = config;
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [iframeHeight, setIframeHeight] = useState(config.height ?? 300);

  const selfFetched = useBlockData<WidgetData>(dataSource, config, "widget");
  const data = (props.data as WidgetData | null) ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;
  const html = data?.html ?? config.html;

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (!event.data || typeof event.data !== "object") return;

      if (event.data.type === "augur:resize" && typeof event.data.height === "number") {
        setIframeHeight(Math.min(event.data.height + 16, 2000));
      }

      if (event.data.type === "augur:action" && typeof event.data.action === "string") {
        console.log("[WidgetBlock] Action request:", event.data.action, event.data.args);
      }
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  return (
    <BlockShell
      title={data?.title ?? title}
      icon={Code2}
      color="violet"
      onExpand={onExpand}
      staleError={error}
    >
      {loading ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="h-24 w-full rounded bg-[var(--bg-hover)] animate-pulse" />
        </div>
      ) : !html && error ? (
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center">
            <p className="text-xs text-red-400/80">Failed to load widget</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        </div>
      ) : html ? (
        <iframe
          ref={iframeRef}
          srcDoc={buildSrcdoc(html)}
          className="w-full border-0"
          sandbox="allow-scripts"
          title={data?.title ?? title}
          style={{ height: `${iframeHeight}px` }}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center p-4">
          <p className="text-xs text-[var(--text-muted)] italic">
            No widget content
          </p>
        </div>
      )}
    </BlockShell>
  );
}
