import UnifiedHubTabs from "@/components/UnifiedHubTabs";
import { coreTabRegistry } from "@/lib/tabs/registry";
import { Settings } from "lucide-react";

const hub = coreTabRegistry.settings;

export default function SettingsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-8">
      <header className="page-header relative">
        <div className="flex items-center gap-4">
          <div className="size-12 rounded-xl bg-gradient-to-br from-[var(--accent-primary)]/20 to-[var(--accent-secondary)]/10 border border-[var(--accent-primary)]/20 flex items-center justify-center shadow-sm">
            <Settings className="size-6 text-[var(--accent-primary)]" />
          </div>
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)]">
              {hub.title}
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">
              {hub.subtitle}
            </p>
          </div>
        </div>
        {/* Decorative accent line */}
        <div className="absolute -bottom-4 left-0 right-0 h-px bg-gradient-to-r from-[var(--accent-primary)]/30 via-[var(--border-color)] to-transparent" />
      </header>

      <UnifiedHubTabs tabs={hub.tabs} />

      <div>{children}</div>
    </div>
  );
}
