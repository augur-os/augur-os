import { Eye, EyeOff } from "lucide-react";
import type { WidgetVisibility, LayoutBlocks, PageWidget } from "./types";
import { PAGE_WIDGETS } from "./types";
import { SectionHeader } from "./ui-helpers";

export function VisibilityTabContent({
  pathname,
  currentVisibility,
  onToggleWidget,
}: {
  pathname: string;
  currentVisibility: WidgetVisibility;
  onToggleWidget: (widgetId: string) => void;
}) {
  const currentWidgets: PageWidget[] = PAGE_WIDGETS[pathname] || [];

  if (currentWidgets.length === 0) {
    return null;
  }

  return (
    <div className="space-y-1.5">
      <SectionHeader>Page Widgets</SectionHeader>
      <div className="space-y-0.5 px-1">
        {currentWidgets.map((widget) => {
          const isVisible = currentVisibility[widget.id] !== false;

          return (
            <button type="button"
              key={widget.id}
              onClick={() => onToggleWidget(widget.id)}
              className={`w-full flex items-center justify-between px-2 py-2 rounded-lg transition-colors ${
                isVisible
                  ? "bg-[var(--accent-primary)]/10 hover:bg-[var(--accent-primary)]/15"
                  : "hover:bg-[var(--bg-hover)]"
              }`}
            >
              <span
                className={`text-xs font-medium ${
                  isVisible
                    ? "text-[var(--text-primary)]"
                    : "text-[var(--text-muted)]"
                }`}
              >
                {widget.label}
              </span>
              {isVisible ? (
                <Eye className="size-3.5 text-[var(--accent-primary)]" />
              ) : (
                <EyeOff className="size-3.5 text-[var(--text-muted)]" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function SizingTabContent({
  layoutBlocks,
  onSetBlock,
  onResetBlock,
}: {
  layoutBlocks: LayoutBlocks;
  onSetBlock: (
    id: string,
    patch: { width?: string; height?: string | number },
  ) => void;
  onResetBlock: (id: string) => void;
}) {
  const entries = Object.entries(layoutBlocks);

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="space-y-1.5">
      <SectionHeader>Block Sizing</SectionHeader>
      <div className="space-y-1 px-1">
        {entries.map(([id, prefs]) => {
          const width = prefs.width ?? "auto";
          const heightValue =
            typeof prefs.height === "number"
              ? String(prefs.height)
              : prefs.height || "auto";

          return (
            <div
              key={id}
              className="flex flex-col gap-1.5 rounded-lg bg-[var(--bg-hover)]/50 px-2.5 py-2"
            >
              <div className="text-sm font-medium text-[var(--text-primary)] truncate">
                {id}
              </div>
              <div className="flex items-center gap-1.5 flex-wrap">
                <select
                  value={width}
                  onChange={(event) =>
                    onSetBlock(id, { width: event.target.value })
                  }
                  aria-label={`Width for ${id}`}
                  className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md px-1.5 py-0.5 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]/50"
                >
                  <option value="auto">W: auto</option>
                  <option value="full">W: full</option>
                </select>

                <select
                  value={heightValue}
                  onChange={(event) => {
                    const raw = event.target.value;
                    if (raw === "auto") {
                      onSetBlock(id, { height: "auto" });
                      return;
                    }

                    onSetBlock(id, { height: Number.parseInt(raw, 10) });
                  }}
                  aria-label={`Height for ${id}`}
                  className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md px-1.5 py-0.5 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)]/50"
                >
                  <option value="auto">H: auto</option>
                  <option value="320">320px</option>
                  <option value="520">520px</option>
                  <option value="720">720px</option>
                </select>

                <button type="button"
                  onClick={() => onResetBlock(id)}
                  className="px-1.5 py-0.5 rounded-md hover:bg-[var(--bg-hover)] text-xs text-[var(--text-muted)] hover:text-[var(--text-secondary)] transition-colors"
                >
                  Reset
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
