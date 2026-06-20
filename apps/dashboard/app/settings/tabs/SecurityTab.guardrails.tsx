"use client";

import { type ComponentType } from "react";
import {
  Shield,
  Lock,
  Eye,
  FolderX,
  Save,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SectionTitle } from "./SecurityTab.shared";
import type { SecurityTabController } from "./SecurityTab.controller";

interface GuardrailCardProps {
  title: string;
  description: string;
  enabled: boolean;
  icon: ComponentType<{ className?: string }>;
  color: "emerald" | "amber" | "purple";
  onToggle?: () => void;
}

const GUARDRAIL_ICON_TINTS: Record<GuardrailCardProps["color"], string> = {
  emerald: "bg-[var(--accent-success)]/20 text-[var(--accent-success)]",
  amber: "bg-[var(--accent-warning)]/20 text-[var(--accent-warning)]",
  purple: "bg-[var(--accent-secondary)]/20 text-[var(--accent-secondary)]",
};

function GuardrailCard({
  title,
  description,
  enabled,
  icon: Icon,
  color,
  onToggle,
}: GuardrailCardProps) {
  const iconTint = GUARDRAIL_ICON_TINTS[color] ?? GUARDRAIL_ICON_TINTS.emerald;
  const enabledBadge =
    "bg-[var(--accent-success)]/20 text-[var(--accent-success)] border-[var(--accent-success)]/30";
  const disabledBadge =
    "bg-[var(--bg-hover)] text-[var(--text-muted)] border-[var(--border-color)]";
  const enabledBorder = "border-[var(--accent-success)]/30";
  const content = (
    <div className="flex items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconTint}`}>
          <Icon className="size-4" />
        </div>
        <div className="space-y-0.5">
          <h4 className="text-sm font-medium text-[var(--text-primary)]">
            {title}
          </h4>
          <p className="text-xs text-[var(--text-muted)]">{description}</p>
        </div>
      </div>
      <div className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${enabled ? enabledBadge : disabledBadge}`}>
        {enabled ? "Active" : "Off"}
      </div>
    </div>
  );

  if (onToggle) {
    return (
      <button
        type="button"
        className={`w-full p-4 text-left rounded-xl border ${enabled ? enabledBorder : "border-[var(--border-color)]"} cursor-pointer hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)] focus-visible:ring-offset-2 bg-[var(--bg-card)] transition-colors duration-200`}
        onClick={onToggle}
        aria-pressed={enabled}
        aria-label={`${title}: ${enabled ? "active" : "off"}`}
      >
        {content}
      </button>
    );
  }

  return (
    <article className={`p-4 rounded-xl border ${enabled ? enabledBorder : "border-[var(--border-color)]"} bg-[var(--bg-card)] transition-colors duration-200`}>
      {content}
    </article>
  );
}

export function AiGuardrailsSection({ controller }: { controller: SecurityTabController }) {
  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <SectionTitle
          icon={Lock}
          title="AI Guardrails"
          description="Security controls for AI execution"
          iconClassName="text-[var(--accent-warning)]"
        />
        <div className="flex items-center gap-2">
          {controller.hasChanges && (
            <Button
              onClick={controller.handleSaveAiSettings}
              disabled={controller.saving}
              className="gap-2"
            >
              <Save className="size-4" />
              {controller.saving ? "Saving…" : "Save"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={controller.refreshSecuritySettings}
            disabled={controller.securityLoading}
            aria-label="Refresh security settings"
          >
            <RefreshCw className={`size-4 ${controller.securityLoading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <GuardrailCard
          title="Explicit Consent Required"
          description="Every remote AI request must be manually approved"
          enabled={controller.security.requireExplicitConsent}
          icon={Lock}
          color="emerald"
          onToggle={() => controller.toggleSecurity("requireExplicitConsent")}
        />
        <GuardrailCard
          title="Block on Secrets"
          description="Block requests containing API keys or credentials"
          enabled={controller.security.blockOnSecrets}
          icon={Shield}
          color="emerald"
          onToggle={() => controller.toggleSecurity("blockOnSecrets")}
        />
        <GuardrailCard
          title="Warn on PII"
          description="Warn when personal information is being sent"
          enabled={controller.security.warnOnPii}
          icon={Eye}
          color="amber"
          onToggle={() => controller.toggleSecurity("warnOnPii")}
        />
        <GuardrailCard
          title="Sensitive Folders"
          description={`${controller.security.sensitiveFolders.length} ${controller.security.sensitiveFolders.length === 1 ? "folder" : "folders"} excluded from context`}
          enabled={controller.security.sensitiveFolders.length > 0}
          icon={FolderX}
          color="purple"
        />
      </div>
    </section>
  );
}
