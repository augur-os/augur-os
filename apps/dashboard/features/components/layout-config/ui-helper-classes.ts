export function modeButtonClass(isActive: boolean) {
  return isActive
    ? "border-[var(--accent-primary)]/20 bg-[var(--accent-primary)]/10 text-[var(--text-primary)]"
    : "border-[var(--border-color)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)]";
}

export function selectionCardClass(isActive: boolean) {
  return isActive
    ? "bg-[var(--accent-primary)]/10 border-[var(--accent-primary)]/20"
    : "border-transparent hover:bg-[var(--bg-hover)]";
}
