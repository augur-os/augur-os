"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import type { EditableField } from "@/lib/blocks/types";
import { useActionRunner } from "@/hooks/useActionRunner";

interface EditableCellProps {
  field: EditableField;
  value: unknown;
  rowId: string;
  onSaved?: () => void;
}

export function EditableCell({ field, value, rowId, onSaved }: EditableCellProps) {
  const { runAction } = useActionRunner();
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState<unknown>("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(null);

  // Auto-focus input on entering edit mode
  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus();
      if (inputRef.current instanceof HTMLInputElement || inputRef.current instanceof HTMLTextAreaElement) {
        inputRef.current.select();
      }
    }
  }, [editing]);

  const save = useCallback(
    async (newValue: unknown) => {
      if (newValue === value) {
        setEditing(false);
        return;
      }
      setSaving(true);
      setError(null);
      try {
        await runAction({
          id: field.save_action,
          label: `Save ${field.field}`,
          description: `Update ${field.field} via inline edit`,
          dispatch: "fire",
          page: typeof window !== "undefined" ? window.location.pathname : "/",
          args: { id: rowId, field: field.field, value: newValue },
          mcp_tools: [field.save_action],
        });
        setEditing(false);
        onSaved?.();
      } catch {
        if (field.type === "markdown") {
          setError("Save failed. You can retry or press Escape to discard.");
        } else {
          setEditValue(value); // revert
          setEditing(false);
        }
      } finally {
        setSaving(false);
      }
    },
    [value, field, rowId, runAction, onSaved],
  );

  // Toggle type: always renders as checkbox, no edit mode
  if (field.type === "toggle") {
    return (
      <label
        style={{
          display: "inline-flex",
          alignItems: "center",
          cursor: saving ? "wait" : "pointer",
          opacity: saving ? 0.6 : 1,
        }}
      >
        <span className="sr-only">Toggle {field.field}</span>
        <input
          type="checkbox"
          checked={Boolean(value)}
          disabled={saving}
          aria-label={`Toggle ${field.field}`}
          onChange={(e) => {
            save(e.target.checked);
          }}
          style={{ cursor: saving ? "wait" : "pointer" }}
        />
      </label>
    );
  }

  // Read mode
  if (!editing) {
    return (
      <span
        onDoubleClick={() => {
          setEditValue(value);
          setError(null);
          setEditing(true);
        }}
        title="Double-click to edit"
        style={{
          cursor: "text",
          padding: "2px 4px",
          borderRadius: 4,
          minWidth: 20,
          display: "inline-block",
        }}
        className="hover:bg-[var(--bg-hover)]"
      >
        {String(value ?? "")}
      </span>
    );
  }

  // Edit mode: select
  if (field.type === "select") {
    return (
      <select
        ref={inputRef as React.RefObject<HTMLSelectElement>}
        value={String(editValue ?? "")}
        disabled={saving}
        aria-label={`Edit ${field.field}`}
        onChange={(e) => {
          const newVal = e.target.value;
          setEditValue(newVal);
          save(newVal);
        }}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setEditValue(value);
            setEditing(false);
          }
        }}
        style={{
          backgroundColor: "var(--bg-secondary)",
          border: "1px solid var(--accent-primary)",
          borderRadius: 4,
          padding: "2px 4px",
          color: "var(--text-primary)",
          fontSize: "inherit",
          opacity: saving ? 0.6 : 1,
        }}
      >
        {(field.options ?? []).map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    );
  }

  // Edit mode: markdown (textarea)
  if (field.type === "markdown") {
    return (
      <div className="flex flex-col gap-1">
        <textarea
          ref={inputRef as React.RefObject<HTMLTextAreaElement>}
          value={String(editValue ?? "")}
          disabled={saving}
          aria-label={`Edit ${field.field}`}
          placeholder={field.placeholder}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              save(editValue);
            }
            if (e.key === "Escape") {
              setEditValue(value);
              setError(null);
              setEditing(false);
            }
          }}
          className="min-h-[60px] resize-y rounded border border-[var(--accent-primary)] bg-[var(--bg-secondary)] px-1.5 py-1 text-[length:inherit] text-[var(--text-primary)] disabled:opacity-60"
        />
        {error && (
          <span className="text-xs text-[var(--accent-danger)]">
            {error}
          </span>
        )}
        <div className="flex gap-1">
          <button type="button"
            onClick={() => save(editValue)}
            disabled={saving}
            className="rounded border border-[var(--accent-primary)] bg-[var(--accent-primary)] px-2 py-0.5 text-xs text-white disabled:cursor-wait"
          >
            {saving ? "Saving..." : "Save"}
          </button>
          <button type="button"
            onClick={() => {
              setEditValue(value);
              setError(null);
              setEditing(false);
            }}
            disabled={saving}
            className="cursor-pointer rounded border border-[var(--border-color,#ccc)] bg-transparent px-2 py-0.5 text-xs text-[var(--text-muted)]"
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }

  // Edit mode: text (default) and number
  return (
    <input
      ref={inputRef as React.RefObject<HTMLInputElement>}
      type={field.type === "number" ? "number" : "text"}
      value={String(editValue ?? "")}
      disabled={saving}
      aria-label={`Edit ${field.field}`}
      placeholder={field.placeholder}
      min={field.min}
      max={field.max}
      onChange={(e) => {
        const val = field.type === "number" ? Number(e.target.value) : e.target.value;
        setEditValue(val);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          save(editValue);
        }
        if (e.key === "Escape") {
          setEditValue(value);
          setEditing(false);
        }
      }}
      onBlur={() => {
        if (!saving) {
          save(editValue);
        }
      }}
      className="w-full rounded border border-[var(--accent-primary)] bg-[var(--bg-secondary)] px-1 py-0.5 text-[length:inherit] text-[var(--text-primary)] disabled:opacity-60"
    />
  );
}
