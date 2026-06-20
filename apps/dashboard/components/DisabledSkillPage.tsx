import Link from "next/link";
import { Ban, Settings } from "lucide-react";

export default function DisabledSkillPage({
  skill,
  title,
}: {
  skill: string;
  title?: string;
}) {
  const label = title || skill;
  return (
    <div className="space-y-8">
      <header className="page-header">
        <div>
          <h1 className="page-title">Skill Disabled</h1>
          <p className="page-subtitle mt-1">
            <span className="font-medium text-[var(--text-primary)]">{label}</span> is
            currently disabled.
          </p>
        </div>
      </header>

      <div className="glass-panel p-8 text-[var(--text-secondary)] space-y-4">
        <div className="flex items-start gap-3">
          <div className="size-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center flex-shrink-0">
            <Ban className="size-5 text-amber-300" />
          </div>
          <div className="space-y-2">
            <div className="text-sm">
              Re-enable it from{" "}
              <span className="font-medium text-white">
                Setup → Skills Manager
              </span>
              .
            </div>
            <div className="text-xs text-[var(--text-muted)] font-mono">{skill}</div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link
            href="/setup"
            className="ui-button ui-button-sm"
            title="Open Setup"
          >
            <Settings className="size-4" />
            Open Setup
          </Link>
          <Link
            href="/browse"
            className="ui-button ui-button-sm"
            title="Browse Skills"
          >
            Browse Skills
          </Link>
        </div>
      </div>
    </div>
  );
}
