"use client";

import { useState } from "react";
import { extractVariables, resolvePromptBody } from "@/lib/browse/promptPlaceholders";

interface BrowsePromptTriggerProps {
  promptBody: string;
  placeholders: string[];
  onTrigger: (resolvedPrompt: string) => void;
}

/**
 * ADR-748: Trigger button on Browse prompt cards. On click, if the prompt has
 * {{placeholders}}, show an inline form; on submit (or immediately, when there
 * are no placeholders) call onTrigger with the resolved prompt body. The page
 * wires onTrigger to chatStore.openChat — the interactive default-CLI chat
 * window. Mirrors the BrowsePinButton standalone-component + threaded-prop
 * pattern. Placeholder parsing/substitution is reused verbatim from
 * @/lib/browse/promptPlaceholders (ADR-748 Task 7) — never redefined here.
 */
export function BrowsePromptTrigger({ promptBody, placeholders, onTrigger }: BrowsePromptTriggerProps) {
  const slots = placeholders.length > 0 ? placeholders : extractVariables(promptBody);
  const [open, setOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});

  const togglePromptSlots = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (slots.length === 0) {
      onTrigger(promptBody);
      return;
    }
    setOpen((prev) => !prev);
  };

  // TODO_CLEANUP: submitting with a blank slot dispatches the literal
  // "{{slot}}" text to the CLI — resolvePromptBody leaves unfilled slots
  // intact by design. Whether blank slots should be blocked or allowed is a
  // UX decision ADR-748 did not specify; left unguarded until that is settled.
  const handleSubmit = () => {
    onTrigger(resolvePromptBody(promptBody, values));
    setOpen(false);
    setValues({});
  };

  return (
    <>
      <button
        type="button"
        aria-label="Trigger prompt"
        aria-expanded={slots.length > 0 ? open : undefined}
        title="Trigger prompt in the CLI chat window"
        onClick={togglePromptSlots}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
            e.stopPropagation();
          }
        }}
        className="inline-flex min-h-[36px] cursor-pointer items-center gap-1 rounded-lg border border-[var(--accent-info)]/30 bg-[var(--accent-info)]/10 px-3 py-2 text-xs font-semibold text-[var(--accent-info)] transition-colors duration-200 hover:bg-[var(--accent-info)]/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-info)]/50"
      >
        Trigger
      </button>
      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="mt-2 w-full space-y-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)]/60 p-3"
        >
          {slots.map((slot) => (
            <label key={slot} className="block text-xs">
              <span className="text-[var(--text-muted)]">{slot}</span>
              <input
                aria-label={slot}
                value={values[slot] ?? ""}
                onChange={(e) =>
                  setValues((v) => ({ ...v, [slot]: e.target.value }))
                }
                className="mt-0.5 w-full rounded border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1 text-sm text-[var(--text-primary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-info)]/50"
              />
            </label>
          ))}
          <button
            type="button"
            onClick={handleSubmit}
            className="cursor-pointer rounded-lg bg-[var(--accent-info)] px-3 py-1.5 text-xs font-semibold text-white transition-opacity duration-200 hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-info)]/50"
          >
            Send to CLI
          </button>
        </div>
      )}
    </>
  );
}
