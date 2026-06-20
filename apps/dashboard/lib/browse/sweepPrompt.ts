export interface SweepPromptInput {
  sourceTab: "sources" | "notes" | "documents" | "pages";
  selectionId: string;
  targetCount: number;
  refusalCount: number;
  filterSummary: Record<string, unknown>;
}

export function buildSweepPrompt(input: SweepPromptInput): string {
  const filterSummary = JSON.stringify(input.filterSummary);
  const sourceLabel = input.sourceTab === "documents"
    ? "document-source files"
    : input.sourceTab === "pages"
      ? "page artifacts"
      : input.sourceTab;

  return [
    `Browse Sweep visible was triggered from the ${sourceLabel} tab.`,
    "",
    "This is an apply-oriented cleanup request. Use ADR-736 tiered classification and the existing loop-hygiene rubric.",
    "The dashboard has already called hygiene-create-selection and persisted the exact filtered Browse selection.",
    "",
    `Selection id: ${input.selectionId}`,
    `Target count: ${input.targetCount}`,
    `Refusal count: ${input.refusalCount}`,
    `Active filters/search: ${filterSummary}`,
    "",
    "Required MCP workflow:",
    `1. Call hygiene-scan-selection with selection_id=${input.selectionId}.`,
    "2. Classify the scan results with ADR-736 cached decisions where available.",
    "3. Run user Q&A for any required Tier 2 or Tier 3 ambiguity before applying.",
    "4. Call hygiene-apply-selection with dry_run=false only after required questions are answered.",
    "5. Report every archive move, refusal, skipped target, and safety refusal.",
    "6. Confirm Archive tab exposure: archived items should be visible through the Browse Archive tab after apply.",
    "For document-source files, move high-confidence files into the correct Au-docs folder and ask only when destination, filename, privacy, or version grouping is ambiguous.",
    "",
    "manual recovery must be included in the final report.",
    "For docs-archive targets, point to the per-folder .archive/_manifest.jsonl record.",
    "For git-aware targets, point to the archived path and normal git recovery commands.",
    "",
    "Do not make hidden dashboard LLM calls or run local scripts from the UI. The current agent session is the classifier.",
  ].join("\n");
}
