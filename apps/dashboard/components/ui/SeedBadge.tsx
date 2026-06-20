/**
 * Shows a subtle indicator when block data comes from seed/demo files
 * rather than the user's vault.
 */
export function SeedBadge({ source, vaultStatus }: {
  source?: string;
  vaultStatus?: string;
}) {
  if (source !== "seed") return null;

  const hint = vaultStatus === "missing_dir"
    ? " — vault directory not found"
    : vaultStatus === "no_file"
    ? " — no data file yet"
    : "";

  return (
    <div className="text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded inline-flex items-center gap-1">
      <span className="opacity-60">Sample data</span>
      {hint && <span className="opacity-40">{hint}</span>}
    </div>
  );
}
