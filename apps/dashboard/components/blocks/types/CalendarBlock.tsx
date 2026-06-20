"use client";

import { Calendar, WifiOff } from "lucide-react";
import type { BlockProps } from "@/lib/blocks/types";
import { useBlockData } from "@/lib/blocks/useBlockData";
import { BlockShell } from "../BlockShell";

interface CalendarConfig {
  title?: string;
  days?: number;
  limit?: number;
}
interface CalendarEvent {
  id?: string;
  title: string;
  date?: string;
  time?: string;
}

function normalizeEvents(data: unknown): CalendarEvent[] {
  // Extract events array from various response shapes
  let raw: unknown[] = [];
  if (Array.isArray(data)) {
    raw = data;
  } else if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    if (Array.isArray(obj.events)) raw = obj.events;
    else if (Array.isArray(obj.items)) raw = obj.items;
    else if (Array.isArray(obj.data)) raw = obj.data;
  }

  return raw.map((e: any) => {
    // Handle Google Calendar format (summary, start.dateTime) and Apple format (title, start)
    const title = e.summary || e.title || "Untitled";
    const startRaw =
      e.start?.dateTime || e.start?.date || e.startTime || e.start || "";
    const endRaw = e.end?.dateTime || e.end?.date || e.endTime || e.end || "";

    let date: string | undefined;
    let time: string | undefined;
    if (startRaw) {
      const d = new Date(startRaw);
      if (!isNaN(d.getTime())) {
        date = d.toLocaleDateString("en-US", {
          weekday: "short",
          month: "short",
          day: "numeric",
        });
        time = d.toLocaleTimeString("en-US", {
          hour: "numeric",
          minute: "2-digit",
          hour12: true,
        });
        if (endRaw) {
          const ed = new Date(endRaw);
          if (!isNaN(ed.getTime())) {
            time += ` – ${ed.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })}`;
          }
        }
      }
    }

    return { id: e.id || e.iCalUID, title, date, time };
  });
}

function isNotConnected(
  data: unknown,
): data is { connected: false; message?: string; setup_hint?: string } {
  return (
    data !== null &&
    typeof data === "object" &&
    "connected" in (data as object) &&
    (data as Record<string, unknown>).connected === false
  );
}

export default function CalendarBlock(props: BlockProps<CalendarConfig>) {
  const { config, dataSource, mode, onExpand } = props;
  const { title = "Calendar", limit = 5 } = config;
  const selfFetched = useBlockData(dataSource, config, "calendar");
  const data = props.data ?? selfFetched.data;
  const loading = props.loading ?? selfFetched.loading;
  const error = props.error ?? selfFetched.error;

  if (!loading && isNotConnected(data)) {
    return (
      <BlockShell title={title} icon={Calendar} color="rose" onExpand={onExpand}>
        <div className="flex flex-col items-center justify-center p-6 gap-2 text-center">
          <WifiOff className="size-5 text-[var(--text-muted)] mb-1" />
          <p className="text-sm text-[var(--text-secondary)]">
            {data.message ?? "Service not connected"}
          </p>
          {data.setup_hint && (
            <p className="text-xs text-[var(--text-muted)]">{data.setup_hint}</p>
          )}
        </div>
      </BlockShell>
    );
  }

  const events = normalizeEvents(data);

  return (
    <BlockShell
      title={title}
      icon={Calendar}
      color="rose"
      onExpand={onExpand}
      staleError={error}
    >
      <div className="p-4 space-y-2">
        {loading &&
          Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="flex items-center gap-3 py-1.5">
              <div className="w-1 h-8 rounded-full bg-rose-500/30 animate-pulse" />
              <div className="flex-1 space-y-1">
                <div className="h-3 w-3/4 rounded bg-[var(--bg-hover)] animate-pulse" />
                <div className="h-2 w-1/2 rounded bg-[var(--bg-hover)] animate-pulse" />
              </div>
            </div>
          ))}

        {!loading && events.length === 0 && !error && (
          <p className="text-xs text-[var(--text-muted)] italic text-center py-4">
            No upcoming events
          </p>
        )}
        {!loading && events.length === 0 && error && (
          <div className="text-center py-6">
            <p className="text-xs text-red-400/80">Failed to load data</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">{error}</p>
          </div>
        )}
        {!loading &&
          events.slice(0, limit).map((event, i) => (
            <div
              key={event.id || i}
              className="flex items-start gap-2 py-1.5 border-b border-[var(--border-color)]/20 last:border-0"
            >
              <div className="w-1 h-6 rounded-full bg-rose-500/60 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-[var(--text-primary)] truncate">
                  {event.title}
                </p>
                {(event.date || event.time) && (
                  <p className="text-[10px] text-[var(--text-muted)]">
                    {[event.date, event.time].filter(Boolean).join(" · ")}
                  </p>
                )}
              </div>
            </div>
          ))}
      </div>
    </BlockShell>
  );
}
