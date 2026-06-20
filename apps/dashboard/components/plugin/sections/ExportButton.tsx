'use client';

/**
 * ADR-274 D10: Export button for auto-page data sections.
 *
 * Downloads current (filtered) data as CSV or JSON. Filename supports
 * {date} and {skill} template tokens.
 */

import { Download } from 'lucide-react';
import Papa from 'papaparse';

import type { ExportDefinition } from './types';

interface ExportButtonProps {
  config: ExportDefinition;
  data: Record<string, unknown>[];
  skillId?: string;
}

function resolveFilename(template: string, skillId?: string): string {
  const date = new Date().toISOString().slice(0, 10);
  return template
    .replace(/\{date\}/g, date)
    .replace(/\{skill\}/g, skillId ?? 'export');
}

export function ExportButton({ config, data, skillId }: ExportButtonProps) {
  if (!config.enabled || data.length === 0) return null;

  const format = config.format ?? 'csv';
  const filename = resolveFilename(config.filename ?? `export-{date}`, skillId);

  const handleExport = () => {
    let content: string;
    let mimeType: string;
    let extension: string;

    if (format === 'json') {
      content = JSON.stringify(data, null, 2);
      mimeType = 'application/json';
      extension = 'json';
    } else {
      content = Papa.unparse(data);
      mimeType = 'text/csv';
      extension = 'csv';
    }

    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}.${extension}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <button type="button"
      onClick={handleExport}
      className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 shadow-sm hover:bg-gray-50 transition-colors"
      title={`Export as ${format.toUpperCase()}`}
      aria-label={`Export data as ${format.toUpperCase()}`}
    >
      <Download className="size-3.5" />
      Export
    </button>
  );
}
