import type { ActiveTab } from "./types";

export function TabButton({
  tab,
  activeTab,
  label,
  icon,
  onSelect,
  embedded = false,
}: {
  tab: ActiveTab;
  activeTab: ActiveTab;
  label: string;
  icon: React.ReactNode;
  onSelect: (tab: ActiveTab) => void;
  embedded?: boolean;
}) {
  const isActive = activeTab === tab;

  return (
    <button type="button"
      onClick={() => onSelect(tab)}
      className={`flex items-center gap-1.5 font-semibold rounded-lg transition-colors whitespace-nowrap ${
        embedded ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs"
      } ${
        isActive
          ? "bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]"
          : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
      }`}
    >
      {icon}
      {label}
    </button>
  );
}
