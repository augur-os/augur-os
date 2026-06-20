import type { PreparedActionDraft } from "@/lib/actions/preparedActionDraft";
import type { ActiveFolderContext } from "@/lib/browse/folderContext";

type ProblemCountItem = {
  metadata?: {
    problem_count?: unknown;
  };
};

export const PROJECT_INVENTORY_QUESTION_PROMPT =
  "What should I know about this project based on the AI setup and inventory Augur just found?";

export function canAskProjectInventoryQuestion(
  context: ActiveFolderContext | null | undefined,
): boolean {
  return Boolean(
    context?.scope === "brain" &&
      context.brain_id?.startsWith("project-") &&
      context.project_root,
  );
}

export function sumProjectProblemCounts(items: ProblemCountItem[]): number {
  return items.reduce((total, item) => {
    const count = Number(item.metadata?.problem_count ?? 0);
    if (!Number.isFinite(count) || count < 0) return total;
    return total + count;
  }, 0);
}

export function buildProjectInventoryQuestionDraft(
  context: ActiveFolderContext,
  summary: { inventoryCount?: number; problemCount?: number } = {},
): PreparedActionDraft {
  const promptParts = [
    PROJECT_INVENTORY_QUESTION_PROMPT,
    "",
    `Active folder: ${context.label}`,
    `Brain id: ${context.brain_id ?? "unknown"}`,
    `Project root: ${context.project_root ?? "unknown"}`,
  ];

  if (summary.inventoryCount !== undefined) {
    promptParts.push(`Inventory records visible in Browse: ${summary.inventoryCount}`);
  }

  if (summary.problemCount !== undefined) {
    promptParts.push(`Problem badges visible in Browse: ${summary.problemCount}`);
  }

  promptParts.push("", "Answer only. Do not save or retain anything unless I explicitly ask.");

  return {
    id: "ask-project-inventory-summary",
    label: "Ask Augur about this project",
    prompt: promptParts.join("\n"),
    page: "/browse",
    dispatch: "chat",
    tier: "standard",
    createdAt: new Date().toISOString(),
  };
}
