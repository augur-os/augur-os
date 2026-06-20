"use client";

/**
 * EditorPreferences - ADR-114 Centralized Editor Settings
 *
 * Displays the top file extensions found in the codebase and lets users
 * configure which macOS application should open each type.
 * Empty / unset entries fall back to the system default handler.
 */

import { useState, useEffect } from "react";
import { Check, FileText, RotateCcw, Save } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SettingsCard } from "@/components/ui/SettingsCard";
import { mcpCall } from "@/lib/mcp/client";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

/** Extensions shown in the UI, ordered by frequency in the codebase. */
const FILE_TYPES: { ext: string; label: string; description: string }[] = [
  { ext: "md", label: "Markdown", description: "Docs, ADRs, notes, memory" },
  { ext: "py", label: "Python", description: "Automation scripts" },
  { ext: "tsx", label: "React TSX", description: "Dashboard components" },
  { ext: "ts", label: "TypeScript", description: "TypeScript modules" },
  { ext: "yaml", label: "YAML", description: "Config, manifests, chains" },
  { ext: "json", label: "JSON", description: "Data files, plugins" },
  { ext: "sh", label: "Shell", description: "Shell scripts" },
  { ext: "html", label: "HTML", description: "Templates" },
];

type EditorMap = Record<string, string>;

export function EditorPreferences() {
  const [editors, setEditors] = useState<EditorMap>({});
  const [savedEditors, setSavedEditors] = useState<EditorMap>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const { data: prefData, loading } = useMcpQuery<{
    file_editors?: EditorMap;
  }>(
    "editor-preferences",
    "get-preferences",
    "config",
    { args: { key: "file_editors" } },
  );

  // Sync fetched preferences into local state
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const map =
        prefData?.file_editors && typeof prefData.file_editors === "object"
          ? prefData.file_editors
          : {};
      setEditors(map);
      setSavedEditors(map);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [prefData]);

  const handleChange = (ext: string, value: string) => {
    setEditors((prev) => ({ ...prev, [ext]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      // Clean: remove empty entries so preferences stay tidy
      const cleaned: EditorMap = {};
      for (const [ext, app] of Object.entries(editors)) {
        const trimmed = app.trim();
        if (trimmed) cleaned[ext] = trimmed;
      }

      await mcpCall("update-preference", { key: "file_editors", value: cleaned });

      setEditors(cleaned);
      setSavedEditors(cleaned);
      setSaved(true);
      // TODO_BUG(auto-memory-leak): hmr-unsafe-interval — Module-level setInterval without globalThis guard — leaks on HMR reload
      setTimeout(() => setSaved(false), 2000);
    } catch {
      // Could show error, but keep it simple
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setEditors(savedEditors);
    setSaved(false);
  };

  const hasChanges = JSON.stringify(editors) !== JSON.stringify(savedEditors);
  const changedCount = FILE_TYPES.filter(
    ({ ext }) =>
      (editors[ext] || "").trim() !== (savedEditors[ext] || "").trim(),
  ).length;

  return (
    <div className="space-y-4">
      <SettingsCard
        icon={FileText}
        title="Default Editors"
        subtitle="Set which app opens each file type. Leave empty for the system default handler."
        variant={hasChanges ? "info" : saved ? "success" : "default"}
        badge={
          hasChanges ? `${changedCount} changed` : saved ? "Saved" : "Synced"
        }
        action={
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={!hasChanges || saving}
              leftIcon={<RotateCcw className="size-3.5" />}
            >
              Reset
            </Button>
            <Button
              variant={saved ? "success" : "outline"}
              size="sm"
              onClick={handleSave}
              disabled={!hasChanges || saving}
              leftIcon={
                saved ? (
                  <Check className="size-3.5" />
                ) : (
                  <Save className="size-3.5" />
                )
              }
            >
              {saving ? "Saving..." : saved ? "Saved" : "Save"}
            </Button>
          </div>
        }
      />

      <p className="text-xs text-[var(--text-muted)] px-1">
        Use the exact app name from /Applications (for example &quot;iA
        Writer&quot;, &quot;Visual Studio Code&quot;, &quot;Cursor&quot;,
        &quot;PyCharm&quot;).
      </p>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {[...Array(8)].map((_, i) => (
            <div
              key={i}
              className="h-36 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] animate-pulse"
            />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {FILE_TYPES.map(({ ext, label, description }) => {
            const appValue = editors[ext] || "";
            return (
              <SettingsCard
                key={ext}
                icon={FileText}
                title={label}
                subtitle={description}
                variant={appValue.trim() ? "info" : "muted"}
                badge={`.${ext}`}
              >
                <label htmlFor={`editor-app-${ext}`} className="block text-xs uppercase tracking-wide text-[var(--text-muted)] mb-1">
                  Application
                </label>
                <input
                  id={`editor-app-${ext}`}
                  type="text"
                  value={appValue}
                  onChange={(e) => handleChange(ext, e.target.value)}
                  placeholder="System default"
                  aria-label={`Application for ${label} files`}
                  className="w-full px-3 py-2 text-xs bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] placeholder:text-[var(--text-muted)]/50 focus:outline-none focus:border-[var(--accent-primary)]/60 focus:ring-1 focus:ring-[var(--accent-primary)]/30 transition-colors"
                />
                <p className="mt-2 text-xs text-[var(--text-muted)]">
                  {appValue.trim()
                    ? `Opens with ${appValue.trim()}`
                    : "Uses system default handler"}
                </p>
              </SettingsCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
