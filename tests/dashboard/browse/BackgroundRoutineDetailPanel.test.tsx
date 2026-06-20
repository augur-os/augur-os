/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import type { Routine } from "@/lib/browse/types";
import { BackgroundRoutineDetailPanel } from "@/components/shared/BackgroundRoutineDetailPanel";

const routine: Routine = {
  id: "routine:dream",
  display_name: "Dream synthesis",
  source_kind: "routine",
  source_path: "project-brain/capabilities/skills/dream/routine.yaml",
  cadence: {
    type: "cron",
    spec: "0 3 * * *",
    next_run_estimated: "2026-05-24T03:00:00Z",
  },
  status: "enabled",
  spawn_kind: "ai-cli-spawn",
  config_path: "project-brain/capabilities/skills/dream/routine.yaml",
  ai_cost: {
    cli: "codex",
    estimated_tokens_per_run: 4000,
    estimated_tokens_per_day: 4000,
  },
  last_run_at: "2026-05-22T03:00:00Z",
  last_run_status: "success",
  recent_runs_24h: 1,
  tags: ["dream"],
  description: "Synthesize overnight notes",
  title: "Dream synthesis",
  source: "routine",
  kind: "background-routine",
  workspace: "~/Projects/Augur",
  schedule_human: "daily",
  prompt_summary: "Synthesize notes",
  prompt_body: "Run dream synthesis",
  model: "codex",
  next_run_at: "2026-05-24T03:00:00Z",
  warnings: [],
};

describe("BackgroundRoutineDetailPanel", () => {
  it("renders generated routine actions and routes AI prompts", () => {
    const onItemPrompt = jest.fn();

    render(
      <BackgroundRoutineDetailPanel
        routine={routine}
        onClose={jest.fn()}
        onItemPrompt={onItemPrompt}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Run now" }));

    expect(onItemPrompt).toHaveBeenCalledWith(expect.stringContaining("Dream synthesis"));
    expect(onItemPrompt).toHaveBeenCalledWith(expect.stringContaining("project-brain/capabilities/skills/dream/routine.yaml"));
  });
});
