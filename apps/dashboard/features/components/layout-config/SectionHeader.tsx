export function SectionHeader({ children }: { children: React.ReactNode }) {
  return (
    <div className="px-2 py-1.5 text-xs font-semibold text-[var(--accent-primary)] uppercase tracking-wider border-b border-[var(--border-color)] mb-2">
      {children}
    </div>
  );
}
