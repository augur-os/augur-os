"use client";

import { HelpCircle } from "lucide-react";
import { TOOL_BUTTON_IDLE_CLASS } from "@/components/chat/utils";

export interface AssistButtonProps {
  onClick: () => void;
}

export function AssistButton({ onClick }: AssistButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium transition-colors ${TOOL_BUTTON_IDLE_CLASS}`}
      title="Get help with this page"
    >
      <HelpCircle className="size-3" />
      <span>Assist</span>
    </button>
  );
}
