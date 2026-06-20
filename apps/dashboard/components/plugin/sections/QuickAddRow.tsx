'use client';

/**
 * ADR-274 D2: Inline quick-add form for auto-page data sections.
 *
 * Renders a compact collapsible form row. On submit, dispatches the
 * referenced action via useActionRunner. Form resets after success.
 */

import { useState, useCallback } from 'react';
import { Plus, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';

import type { QuickAddDefinition } from './types';

interface QuickAddRowProps {
  config: QuickAddDefinition;
  onSubmit: (values: Record<string, string>) => Promise<void>;
}

export function QuickAddRow({ config, onSubmit }: QuickAddRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = useCallback((name: string, value: string) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  }, []);

  const handleSubmit = useCallback(async () => {
    // Validate required fields
    for (const field of config.fields) {
      if (field.required && !values[field.name]?.trim()) {
        setError(`${field.name} is required`);
        return;
      }
    }

    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(values);
      setValues({});
      setExpanded(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add item');
    } finally {
      setSubmitting(false);
    }
  }, [config.fields, values, onSubmit]);

  if (!config.enabled) return null;

  return (
    <div className="rounded-xl border border-dashed border-[var(--border-color)] bg-[var(--bg-card)]">
      <button type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 px-4 py-2.5 text-sm font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        aria-expanded={expanded}
      >
        <Plus className="size-4" />
        Add new
        {expanded ? (
          <ChevronUp className="ml-auto size-4" />
        ) : (
          <ChevronDown className="ml-auto size-4" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-[var(--border-color)] px-4 py-3">
          <div className="flex flex-wrap items-end gap-3">
            {config.fields.map((field) => (
              <div key={field.name} className="flex-1 min-w-[150px]">
                <label htmlFor={`quick-add-${field.name}`} className="mb-1 block text-xs font-medium text-[var(--text-muted)]">
                  {field.name}
                  {field.required && <span className="text-[var(--accent-danger)] ml-0.5">*</span>}
                </label>
                {field.type === 'select' ? (
                  <select
                    id={`quick-add-${field.name}`}
                    aria-label={field.name}
                    value={values[field.name] ?? ''}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1.5 text-sm text-[var(--text-primary)] focus:border-[var(--accent-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]"
                  >
                    <option value="">Select…</option>
                    {field.options?.map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    id={`quick-add-${field.name}`}
                    type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'}
                    aria-label={field.name}
                    value={values[field.name] ?? ''}
                    onChange={(e) => handleChange(field.name, e.target.value)}
                    placeholder={field.placeholder}
                    className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-1.5 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--accent-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-primary)]"
                  />
                )}
              </div>
            ))}

            <button type="button"
              onClick={handleSubmit}
              disabled={submitting}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[var(--accent-primary)] px-4 py-1.5 text-sm font-medium text-[var(--accent-foreground,white)] hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {submitting ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
              Add
            </button>
          </div>

          {error && (
            <p className="mt-2 text-xs text-[var(--accent-danger)]" role="alert">{error}</p>
          )}
        </div>
      )}
    </div>
  );
}
