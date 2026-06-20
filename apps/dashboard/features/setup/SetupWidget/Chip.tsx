"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { SetupStatus } from "../types";

interface ChipProps {
  status: SetupStatus;
  onOpen: () => void;
}

export function Chip({ status, onOpen }: ChipProps) {
  const alert = status.state === "alert";
  const label = alert ? "Setup needs attention" : "Setup complete";

  return (
    <button
      type="button"
      onClick={onOpen}
      aria-label={label}
      className={`inline-flex h-8 items-center gap-2 rounded-full border px-3 text-xs font-medium ${
        alert
          ? "border-amber-500/50 text-amber-700 hover:bg-amber-500/10"
          : "border-emerald-500/40 text-emerald-700 hover:bg-emerald-500/10"
      }`}
    >
      {alert ? <AlertTriangle className="size-4" /> : <CheckCircle2 className="size-4" />}
      <span>{label}</span>
    </button>
  );
}
