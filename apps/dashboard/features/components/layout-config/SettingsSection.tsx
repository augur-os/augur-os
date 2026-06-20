export function SettingsSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/30 p-4 md:p-5">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          {title}
        </h3>
        <p className="mt-1 text-xs text-[var(--text-secondary)]">
          {description}
        </p>
      </div>
      {children}
    </section>
  );
}
