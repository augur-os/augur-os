"use client";

import Markdown from "@/components/Markdown";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";

interface IntegrationTabProps {
  skillId: string | null;
  skillLabel?: string;
}

interface CliHelpResponse {
  markdown?: string;
  help?: string;
  output?: string;
  text?: string;
  reference?: string;
  defaultCli?: string;
  default_cli?: string;
  defaultCliName?: string;
  default_cli_name?: string;
  cli?: string;
  cliName?: string;
  cliId?: string;
  name?: string;
}

function firstNonEmptyString(...values: Array<string | undefined>): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}

function resolveDefaultCli(data: CliHelpResponse | null): string {
  return firstNonEmptyString(
    data?.defaultCli,
    data?.default_cli,
    data?.defaultCliName,
    data?.default_cli_name,
    data?.cli,
    data?.cliName,
    data?.cliId,
    data?.name,
  );
}

function resolveHelpText(data: CliHelpResponse | null): string {
  return firstNonEmptyString(
    data?.markdown,
    data?.help,
    data?.output,
    data?.text,
    data?.reference,
  );
}

export function IntegrationTab({ skillId, skillLabel }: IntegrationTabProps) {
  const resolvedSkillId = skillId?.trim() ?? "";
  const { data, loading, error } = useMcpQuery<CliHelpResponse>(
    ["skill-cli-help", resolvedSkillId || "__none__"],
    "get-skill-cli-help",
    "config",
    {
      enabled: Boolean(resolvedSkillId),
      args: resolvedSkillId ? { skill_id: resolvedSkillId } : undefined,
    },
  );

  const activeData = resolvedSkillId && !loading && !error ? data : null;
  const defaultCli = resolveDefaultCli(activeData);
  const helpText = resolveHelpText(activeData);
  const title = skillLabel ?? resolvedSkillId ?? "Skill";

  return (
    <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h3 className="text-sm font-semibold text-[var(--text-primary)] truncate">
            {title} CLI reference
          </h3>
          <p className="text-xs text-[var(--text-muted)]">
            Active CLI reference for this skill.
          </p>
        </div>

        {defaultCli ? (
          <span className="rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-2 py-1 text-xs font-medium text-[var(--text-secondary)]">
            Default CLI: {defaultCli}
          </span>
        ) : null}
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-[var(--text-muted)]">
          Loading CLI reference…
        </p>
      ) : null}

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded-lg border border-[var(--accent-danger)]/30 bg-[var(--accent-danger)]/10 px-3 py-2 text-sm text-[var(--accent-danger)]"
        >
          {error}
        </p>
      ) : null}

      {!loading && !error && !resolvedSkillId ? (
        <p className="mt-4 text-sm text-[var(--text-muted)]">
          Select a skill to load its CLI reference.
        </p>
      ) : null}

      {!loading && !error && resolvedSkillId && !helpText ? (
        <p className="mt-4 text-sm text-[var(--text-muted)]">
          No CLI reference is available for this skill yet.
        </p>
      ) : null}

      {!loading && !error && helpText ? (
        <div className="mt-4">
          <Markdown markdown={helpText} />
        </div>
      ) : null}
    </section>
  );
}


