import { Rocket } from "lucide-react";

export default function SetupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-8">
      <header className="page-header relative">
        <div className="flex items-center gap-4">
          <div className="size-12 rounded-xl bg-gradient-to-br from-[var(--accent-primary)]/20 to-[var(--accent-secondary)]/10 border border-[var(--accent-primary)]/20 flex items-center justify-center shadow-sm">
            <Rocket className="size-6 text-[var(--accent-primary)]" />
          </div>
          <div className="space-y-1">
            <h1 className="text-3xl font-bold tracking-tight text-[var(--text-primary)]">
              Setup
            </h1>
            <p className="text-sm text-[var(--text-secondary)]">
              Finish the checks that unlock daily value. Revisit whenever your
              environment changes.
            </p>
          </div>
        </div>
        {/* Decorative accent line */}
        <div className="absolute -bottom-4 left-0 right-0 h-px bg-gradient-to-r from-[var(--accent-primary)]/30 via-[var(--border-color)] to-transparent" />
      </header>

      <div>{children}</div>
    </div>
  );
}
