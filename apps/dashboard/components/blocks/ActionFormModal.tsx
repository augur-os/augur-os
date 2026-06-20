"use client";

import * as React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { useQueryClient } from "@tanstack/react-query";
import { useActionRunner } from "@/hooks/useActionRunner";
import type { DispatchMode } from "@/lib/actions/types";
import type { FormField, SelectOption } from "@/lib/plugin-schema/types";

/**
 * Normalize options that may come as raw strings from YAML or as SelectOption objects.
 */
function normalizeOptions(
  options: (string | SelectOption)[] | undefined,
): SelectOption[] {
  if (!options) return [];
  return options.map((opt) =>
    typeof opt === "string" ? { value: opt, label: opt } : opt,
  );
}

/**
 * Validate a single field value against its definition.
 * Returns an error message string or null if valid.
 */
function validateField(
  field: FormField,
  value: unknown,
): string | null {
  const strVal = typeof value === "string" ? value : String(value ?? "");

  // Required check
  if (field.required) {
    if (
      value === undefined ||
      value === null ||
      value === "" ||
      (Array.isArray(value) && value.length === 0)
    ) {
      return `${field.label} is required`;
    }
  }

  // Skip further validation if empty and not required
  if (strVal === "" && !field.required) return null;

  const v = field.validation;
  if (!v) return null;

  // min/max for number fields
  if (v.min !== undefined && typeof value === "number" && value < v.min) {
    return v.message ?? `${field.label} must be at least ${v.min}`;
  }
  if (v.max !== undefined && typeof value === "number" && value > v.max) {
    return v.message ?? `${field.label} must be at most ${v.max}`;
  }

  // minLength/maxLength for string fields
  if (v.minLength !== undefined && strVal.length < v.minLength) {
    return v.message ?? `${field.label} must be at least ${v.minLength} characters`;
  }
  if (v.maxLength !== undefined && strVal.length > v.maxLength) {
    return v.message ?? `${field.label} must be at most ${v.maxLength} characters`;
  }

  // Pattern
  if (v.pattern) {
    try {
      const re = new RegExp(v.pattern);
      if (!re.test(strVal)) {
        return v.message ?? `${field.label} format is invalid`;
      }
    } catch {
      // Invalid regex in YAML config — skip pattern validation
    }
  }

  return null;
}

interface ActionFormState {
  formValues: Record<string, unknown>;
  errors: Record<string, string>;
  confirmInput: string;
}

type ActionFormStateAction =
  | { type: "reset"; fields: FormField[] }
  | { type: "set-field-value"; name: string; value: unknown }
  | { type: "set-errors"; errors: Record<string, string> }
  | { type: "set-confirm-input"; value: string };

function buildDefaultFormValues(fields: FormField[]): Record<string, unknown> {
  const defaults: Record<string, unknown> = {};
  for (const field of fields) {
    if (field.defaultValue !== undefined) {
      defaults[field.name] = field.defaultValue;
    } else if (field.type === "checkbox" || field.type === "toggle") {
      defaults[field.name] = false;
    } else if (field.type === "multiselect") {
      defaults[field.name] = [];
    } else {
      defaults[field.name] = "";
    }
  }
  return defaults;
}

function actionFormReducer(
  state: ActionFormState,
  action: ActionFormStateAction,
): ActionFormState {
  switch (action.type) {
    case "reset":
      return {
        formValues: buildDefaultFormValues(action.fields),
        errors: {},
        confirmInput: "",
      };
    case "set-field-value": {
      const errors = state.errors[action.name]
        ? { ...state.errors }
        : state.errors;
      if (errors !== state.errors) {
        delete errors[action.name];
      }
      return {
        ...state,
        formValues: { ...state.formValues, [action.name]: action.value },
        errors,
      };
    }
    case "set-errors":
      return { ...state, errors: action.errors };
    case "set-confirm-input":
      return { ...state, confirmInput: action.value };
    default:
      return state;
  }
}

interface ActionFormFieldControlProps {
  field: FormField;
  fieldId: string;
  value: unknown;
  onValueChange: (name: string, value: unknown) => void;
}

function ActionFormFieldControl({
  field,
  fieldId,
  value,
  onValueChange,
}: ActionFormFieldControlProps) {
  switch (field.type) {
    case "text":
    case "date":
    case "datetime":
      return (
        <Input
          id={fieldId}
          type={field.type === "datetime" ? "datetime-local" : field.type}
          value={(value as string) ?? ""}
          placeholder={field.placeholder}
          onChange={(e) => onValueChange(field.name, e.target.value)}
        />
      );

    case "number":
      return (
        <Input
          id={fieldId}
          type="number"
          value={(value as string | number) ?? ""}
          placeholder={field.placeholder}
          min={field.validation?.min}
          max={field.validation?.max}
          onChange={(e) =>
            onValueChange(
              field.name,
              e.target.value === "" ? "" : Number(e.target.value),
            )
          }
        />
      );

    case "textarea":
      return (
        <textarea
          id={fieldId}
          aria-label={field.label}
          className="flex w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-primary)] min-h-[80px]"
          value={(value as string) ?? ""}
          placeholder={field.placeholder}
          onChange={(e) => onValueChange(field.name, e.target.value)}
        />
      );

    case "select": {
      const opts = normalizeOptions(field.options);
      return (
        <Select
          id={fieldId}
          value={(value as string) ?? ""}
          onChange={(e) => onValueChange(field.name, e.target.value)}
        >
          <option value="">-- Select --</option>
          {opts.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </Select>
      );
    }

    case "multiselect": {
      const opts = normalizeOptions(field.options);
      const selectedArr = Array.isArray(value) ? (value as string[]) : [];
      return (
        <Select
          id={fieldId}
          multiple
          value={selectedArr}
          onChange={(e) => {
            const selected = Array.from(
              e.target.selectedOptions,
              (o) => o.value,
            );
            onValueChange(field.name, selected);
          }}
        >
          {opts.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </Select>
      );
    }

    case "checkbox":
      return (
        <input
          id={fieldId}
          type="checkbox"
          checked={!!value}
          aria-label={field.label}
          className="size-4 rounded border-[var(--border-color)] text-[var(--accent-primary)] focus:ring-[var(--accent-primary)]"
          onChange={(e) => onValueChange(field.name, e.target.checked)}
        />
      );

    case "toggle":
      return (
        <button
          id={fieldId}
          type="button"
          role="switch"
          aria-checked={!!value}
          aria-label={field.label}
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
            value ? "bg-[var(--accent-primary)]" : "bg-[var(--bg-hover)]"
          }`}
          onClick={() => onValueChange(field.name, !value)}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition-transform ${
              value ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
      );

    case "radio": {
      const opts = normalizeOptions(field.options);
      return (
        <fieldset id={fieldId} aria-label={field.label}>
          {opts.map((opt) => (
            <label
              key={opt.value}
              className="flex items-center gap-2 text-sm text-[var(--text-primary)] py-1"
            >
              <input
                type="radio"
                name={field.name}
                value={opt.value}
                checked={value === opt.value}
                disabled={opt.disabled}
                onChange={() => onValueChange(field.name, opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </fieldset>
      );
    }

    case "file":
      return (
        <Input
          id={fieldId}
          type="file"
          accept={field.accept?.join(",")}
          onChange={(e) => {
            const file = e.target.files?.[0];
            onValueChange(field.name, file ?? null);
          }}
        />
      );

    default:
      return (
        <Input
          id={fieldId}
          type="text"
          value={(value as string) ?? ""}
          placeholder={field.placeholder}
          onChange={(e) => onValueChange(field.name, e.target.value)}
        />
      );
  }
}

export interface ActionFormModalProps {
  open: boolean;
  onClose: () => void;
  actionId: string;
  actionLabel: string;
  dispatch: DispatchMode;
  fields: FormField[];
  staticArgs?: Record<string, unknown>;
  mcpTool?: string;
  confirmText?: string;
  refetch?: string[];
  onSuccess?: () => void;
}
export default function ActionFormModal({
  open,
  onClose,
  actionId,
  actionLabel,
  dispatch,
  fields,
  staticArgs,
  mcpTool,
  confirmText,
  refetch,
  onSuccess,
}: ActionFormModalProps) {
  const { runAction, isExecuting } = useActionRunner();
  const queryClient = useQueryClient();
  const [formState, dispatchFormState] = React.useReducer(actionFormReducer, {
    formValues: {},
    errors: {},
    confirmInput: "",
  });
  const { formValues, errors, confirmInput } = formState;

  // Reset form state when modal opens
  React.useEffect(() => {
    if (open) {
      const timer = window.setTimeout(() => {
        dispatchFormState({ type: "reset", fields });
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [open, fields]);

  const setFieldValue = React.useCallback((name: string, value: unknown) => {
    dispatchFormState({ type: "set-field-value", name, value });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate all fields
    const newErrors: Record<string, string> = {};
    for (const field of fields) {
      const err = validateField(field, formValues[field.name]);
      if (err) newErrors[field.name] = err;
    }

    if (Object.keys(newErrors).length > 0) {
      dispatchFormState({ type: "set-errors", errors: newErrors });
      return;
    }

    // Merge static args with form values
    const args = { ...staticArgs, ...formValues };

    const ok = await runAction({
      id: actionId,
      label: actionLabel,
      description: actionLabel,
      dispatch,
      page: typeof window !== "undefined" ? window.location.pathname : "/",
      args,
    });

    if (!ok) return;

    // Invalidate block data for named blocks (or all blocks if refetch specified)
    if (refetch && refetch.length > 0) {
      queryClient.invalidateQueries({ queryKey: ["block-data"] });
    }

    onSuccess?.();
    onClose();
  };

  const isConfirmBlocked = confirmText
    ? confirmInput !== confirmText
    : false;

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{actionLabel}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="p-6 pt-4 space-y-4">
          {fields.map((field) => {
            const fieldId = `action-form-${field.name}`;
            const error = errors[field.name];

            return (
              <div key={field.name} className="space-y-1.5">
                <div className="flex items-center gap-0.5">
                  <label
                    htmlFor={fieldId}
                    className="text-sm font-medium text-[var(--text-primary)]"
                  >
                    {field.label}
                  </label>
                  {field.required && (
                    <span className="text-[var(--accent-danger)] text-sm" aria-hidden="true">*</span>
                  )}
                </div>
                <ActionFormFieldControl
                  field={field}
                  fieldId={fieldId}
                  value={formValues[field.name]}
                  onValueChange={setFieldValue}
                />

                {field.helpText && (
                  <p className="text-xs text-[var(--text-muted)]">
                    {field.helpText}
                  </p>
                )}

                {error && (
                  <p className="text-xs text-[var(--accent-danger)]">{error}</p>
                )}
              </div>
            );
          })}

          {confirmText && (
            <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]">
              <label
                htmlFor="action-form-confirm"
                className="text-sm font-medium text-[var(--text-primary)]"
              >
                Type <strong>{confirmText}</strong> to confirm
              </label>
              <Input
                id="action-form-confirm"
                placeholder={`Type ${confirmText} to confirm`}
                value={confirmInput}
                onChange={(e) =>
                  dispatchFormState({
                    type: "set-confirm-input",
                    value: e.target.value,
                  })
                }
              />
            </div>
          )}

          <DialogFooter className="pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="solid"
              disabled={isConfirmBlocked || isExecuting}
              isLoading={isExecuting}
            >
              Run action
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
