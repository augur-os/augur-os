'use client';

import { useState } from 'react';
import { GlassCard } from '@/components/ui/GlassCard';

interface FieldDef {
  name: string;
  type: string;
  label?: string;
  default?: unknown;
  required?: boolean;
  options?: string[];
}

interface AutoFormProps {
  fields?: FieldDef[];
  onSubmit?: (values: Record<string, unknown>) => void;
  submitLabel?: string;
  mcpTool?: string;
  mcpServer?: string;
  apiUrl?: string;
  blockType?: string;
  blockId?: string;
}

function initValues(fields: FieldDef[]): Record<string, unknown> {
  const init: Record<string, unknown> = {};
  for (const f of fields) {
    if (f.default !== undefined) {
      init[f.name] = f.default;
    } else if (f.type === 'boolean') {
      init[f.name] = false;
    } else if (f.type === 'number') {
      init[f.name] = 0;
    } else if (f.options && f.options.length > 0) {
      init[f.name] = f.options[0];
    } else {
      init[f.name] = '';
    }
  }
  return init;
}

const inputBase =
  'w-full rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-colors';

const inputStyle = {
  background: 'var(--bg-card)',
  color: 'var(--text-primary)',
  border: '1px solid var(--border-color)',
};

export default function AutoForm({
  fields = [],
  onSubmit,
  submitLabel = 'Submit',
  mcpTool,
  mcpServer,
  apiUrl,
  blockType,
  blockId,
}: AutoFormProps) {
  const [values, setValues] = useState<Record<string, unknown>>(() => initValues(fields));
  const [submitted, setSubmitted] = useState(false);
  const [jsonParams, setJsonParams] = useState('{}');
  const [responseText, setResponseText] = useState('');
  const [errorText, setErrorText] = useState('');

  function set(name: string, value: unknown) {
    setValues((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitted(false);
    setErrorText('');

    if (mcpTool && apiUrl) {
      let params: Record<string, unknown> = {};
      if (fields.length > 0) {
        params = values;
      } else {
        try {
          const parsed = JSON.parse(jsonParams);
          if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
            throw new Error('Params must be a JSON object');
          }
          params = parsed as Record<string, unknown>;
        } catch (error) {
          setErrorText(error instanceof Error ? error.message : 'Invalid JSON params');
          return;
        }
      }

      try {
        const res = await fetch(apiUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            blockType: blockType || 'mcp-tool-form',
            blockId,
            params: {
              ...params,
              mcpTool,
              ...(mcpServer ? { mcpServer } : {}),
            },
          }),
        });
        const result = await res.json();

        if (!res.ok || result.error) {
          throw new Error(result.error || 'MCP execution failed');
        }

        setResponseText(JSON.stringify(result.data ?? result, null, 2));
      } catch (error) {
        setErrorText(error instanceof Error ? error.message : 'MCP execution failed');
        return;
      }
    } else if (onSubmit) {
      onSubmit(values);
    } else {
      console.log('[AutoForm] submitted:', values);
    }

    setSubmitted(true);
    setTimeout(() => setSubmitted(false), 2000);
  }

  if (fields.length === 0 && !mcpTool) {
    return (
      <GlassCard className="p-4">
        <p className="text-sm text-center" style={{ color: 'var(--text-muted)' }}>
          No fields configured.
        </p>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
        {fields.length === 0 && mcpTool && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
              JSON Params
            </label>
            <textarea
              className={`${inputBase} min-h-[120px] font-mono`}
              style={inputStyle}
              value={jsonParams}
              onChange={(e) => setJsonParams(e.target.value)}
              placeholder='{"query":"example"}'
            />
          </div>
        )}

        {fields.map((field) => {
          const label = field.label ?? field.name;
          const value = values[field.name];

          if (field.options && field.options.length > 0) {
            return (
              <div key={field.name} className="flex flex-col gap-1">
                <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {label}
                  {field.required && <span className="ml-0.5 text-red-400">*</span>}
                </label>
                <select
                  className={inputBase}
                  style={inputStyle}
                  value={String(value ?? '')}
                  required={field.required}
                  onChange={(e) => set(field.name, e.target.value)}
                >
                  {field.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </div>
            );
          }

          if (field.type === 'boolean') {
            return (
              <div key={field.name} className="flex items-center gap-2">
                <input
                  id={`field-${field.name}`}
                  type="checkbox"
                  className="w-4 h-4 rounded accent-blue-500 cursor-pointer"
                  checked={Boolean(value)}
                  onChange={(e) => set(field.name, e.target.checked)}
                />
                <label
                  htmlFor={`field-${field.name}`}
                  className="text-sm cursor-pointer select-none"
                  style={{ color: 'var(--text-primary)' }}
                >
                  {label}
                  {field.required && <span className="ml-0.5 text-red-400">*</span>}
                </label>
              </div>
            );
          }

          if (field.type === 'number') {
            return (
              <div key={field.name} className="flex flex-col gap-1">
                <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {label}
                  {field.required && <span className="ml-0.5 text-red-400">*</span>}
                </label>
                <input
                  type="number"
                  className={inputBase}
                  style={inputStyle}
                  value={String(value ?? 0)}
                  required={field.required}
                  onChange={(e) => set(field.name, e.target.valueAsNumber)}
                />
              </div>
            );
          }

          // Default: string / text
          return (
            <div key={field.name} className="flex flex-col gap-1">
              <label className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                {label}
                {field.required && <span className="ml-0.5 text-red-400">*</span>}
              </label>
              <input
                type="text"
                className={inputBase}
                style={inputStyle}
                value={String(value ?? '')}
                required={field.required}
                placeholder={label}
                onChange={(e) => set(field.name, e.target.value)}
              />
            </div>
          );
        })}

        <button
          type="submit"
          className="mt-1 w-full rounded-md px-4 py-2 text-sm font-medium transition-all duration-150 hover:opacity-90 active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60"
          style={{
            background: submitted ? 'hsl(var(--chart-3))' : 'hsl(var(--chart-1))',
            color: 'hsl(var(--primary-foreground))',
          }}
        >
          {submitted ? 'Submitted!' : submitLabel}
        </button>

        {errorText && (
          <div className="text-xs text-red-400 whitespace-pre-wrap break-words">
            {errorText}
          </div>
        )}

        {responseText && (
          <pre
            className="text-xs p-3 rounded-md overflow-auto max-h-64"
            style={{
              background: 'var(--bg-secondary)',
              color: 'var(--text-secondary)',
              border: '1px solid var(--border-color)',
            }}
          >
            {responseText}
          </pre>
        )}
      </form>
    </GlassCard>
  );
}
