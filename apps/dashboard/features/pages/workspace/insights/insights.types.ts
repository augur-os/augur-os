import type { useBrainInsights } from "./hooks";
import type { BrainInsight, BrainInsightsRun } from "./types";

export type BrainInsightsState = ReturnType<typeof useBrainInsights>;
export type RankedInsight = {
  insight: BrainInsight;
  run: BrainInsightsRun;
  timestamp: number;
  impact: number;
  isNew: boolean;
};
export type UncoveredSourceFamilies = NonNullable<
  NonNullable<NonNullable<BrainInsightsState["wikiStatus"]>["coverage"]>["top_uncovered_source_families"]
>;
