"use client";

import {
  AlertCircle,
  Activity,
  Brain,
  FileText,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { formatNumber, formatPercent, pluralize } from "./insights.helpers";
import {
  AskClusterItem,
  AskOutcomeItem,
  EmptyState,
  HealthyWikiActions,
  InsightItem,
  MetricCard,
  RunSummary,
} from "./insights.items";
import type { BrainInsightsState, RankedInsight, UncoveredSourceFamilies } from "./insights.types";
import type { AskCluster, AskOutcome } from "./types";

export function InsightsPageView({
  askClusters,
  askOutcomes,
  compounding,
  error,
  errors,
  isInitialLoading,
  lastVisitTimestamp,
  latestRuns,
  newInsightsCount,
  notice,
  rankedInsights,
  refetch,
  runWikiUpdate,
  structureIssueCount,
  uncoveredFamilies,
  wikiBatches,
  wikiCompiler,
  wikiCoverage,
  wikiIndex,
  wikiIsCurrent,
  wikiStatus,
  wikiStructure,
  wikiUpdateAction,
  wikiUpdateRunning,
}: {
  askClusters: AskCluster[];
  askOutcomes: AskOutcome[];
  compounding: NonNullable<BrainInsightsState["wikiStatus"]>["compounding_health"] | null;
  error: string | null;
  errors: string[];
  isInitialLoading: boolean;
  lastVisitTimestamp: number | null;
  latestRuns: BrainInsightsState["latestRuns"];
  newInsightsCount: number;
  notice: BrainInsightsState["notice"];
  rankedInsights: RankedInsight[];
  refetch: () => void;
  runWikiUpdate: BrainInsightsState["runWikiUpdate"];
  structureIssueCount: number;
  uncoveredFamilies: UncoveredSourceFamilies;
  wikiBatches: NonNullable<BrainInsightsState["wikiStatus"]>["batches"] | null;
  wikiCompiler: NonNullable<BrainInsightsState["wikiStatus"]>["compiler"] | null;
  wikiCoverage: NonNullable<BrainInsightsState["wikiStatus"]>["coverage"] | null;
  wikiIndex: NonNullable<BrainInsightsState["wikiStatus"]>["index"] | null;
  wikiIsCurrent: boolean;
  wikiStatus: BrainInsightsState["wikiStatus"];
  wikiStructure: NonNullable<BrainInsightsState["wikiStatus"]>["structure"] | null;
  wikiUpdateAction: BrainInsightsState["wikiUpdateAction"];
  wikiUpdateRunning: boolean;
}) {
  return (
    <div className="space-y-6">
      <InsightsPageHeader onRefresh={refetch} />

      {(error || errors.length > 0) && (
        <div role="alert" className="rounded-lg border border-[var(--accent-danger)]/40 bg-[var(--accent-danger)]/10 p-4 text-sm text-[var(--accent-danger)]">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div className="space-y-1">
              <p className="font-medium">Brain Insights returned errors.</p>
              {[error, ...errors].flatMap((message) =>
                message ? [<p key={message}>{message}</p>] : [],
              )}
            </div>
          </div>
        </div>
      )}

      {notice && (
        <div
          role={notice.type === "error" ? "alert" : "status"}
          className={`rounded-lg border px-4 py-3 text-sm ${
            notice.type === "error" ? "border-[var(--accent-danger)] text-[var(--accent-danger)]" : "border-[var(--border-color)] text-[var(--text-secondary)]"
          }`}
        >
          {notice.message}
        </div>
      )}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Source coverage"
          value={formatPercent(wikiCoverage?.concept_coverage_ratio)}
          detail={`${formatNumber(wikiCompiler?.sources_compiled_with_concepts)} of ${formatNumber(wikiCompiler?.sources_total)} sources compiled with concepts`}
        />
        <MetricCard
          label="Pending sources"
          value={formatNumber(wikiCompiler?.sources_pending_or_changed)}
          detail={wikiCompiler?.current ? "Compiler sources are current" : "Changed sources need concept extraction"}
        />
        <MetricCard
          label="Compounding"
          value={formatNumber(compounding?.average_sources_per_concept_page)}
          detail={`${formatNumber(compounding?.concept_page_count)} concept pages, target ${compounding?.target_sources_per_page || "unknown"}`}
        />
        <MetricCard
          label="RAG wiki index"
          value={formatNumber(wikiIndex?.wiki_rag_entries)}
          detail={wikiIndex?.indexed ? "Wiki entries are indexed" : "Wiki index is not available"}
        />
      </section>

      {wikiIndex?.demo_query && (
        <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <h2 className="text-base font-semibold text-[var(--text-primary)]">Demo RAG proof</h2>
              <p className="mt-2 text-sm text-[var(--text-secondary)]">{wikiIndex.demo_query}</p>
            </div>
            <div className="flex flex-wrap gap-2 sm:justify-end">
              <span className="rounded-full border border-[var(--border-color)] px-3 py-1 text-xs text-[var(--text-secondary)]">
                {wikiIndex.demo_hit_count ?? 0} hits
              </span>
              <span className="rounded-full border border-[var(--border-color)] px-3 py-1 text-xs text-[var(--text-secondary)]">
                {wikiIndex.demo_ready ? "ready" : "not ready"}
              </span>
            </div>
          </div>
          {(wikiIndex.demo_hits ?? []).length > 0 && (
            <div className="mt-4 divide-y divide-[var(--border-color)]">
              {(wikiIndex.demo_hits ?? []).slice(0, 3).map((hit) => (
                <div key={`${hit.file ?? "hit"}:${hit.content ?? ""}`} className="py-3 first:pt-0 last:pb-0">
                  <div className="truncate text-xs font-medium text-[var(--text-primary)]" title={hit.file ?? ""}>
                    {hit.file}
                  </div>
                  {hit.content && <div className="mt-1 line-clamp-2 text-xs text-[var(--text-secondary)]">{hit.content}</div>}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,360px)]">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Latest insights</h2>
          </div>
          <p className="text-sm text-[var(--text-secondary)]">
            {lastVisitTimestamp
              ? `${pluralize(newInsightsCount, "change")} since last visit`
              : "First visit tracked in this browser"}
          </p>
          {isInitialLoading ? (
            <EmptyState>Loading Brain insights…</EmptyState>
          ) : rankedInsights.length > 0 ? (
            <div className="space-y-3">
              {rankedInsights.map(({ insight, run, isNew, impact }) => (
                <InsightItem
                  key={`${run.id}-${insight.title}-${insight.summary ?? ""}`}
                  insight={insight}
                  run={run}
                  isNew={isNew}
                  impact={impact}
                />
              ))}
            </div>
          ) : (
            <EmptyState>No inbox insights were returned yet.</EmptyState>
          )}
        </div>

        <aside className="space-y-3">
          <div className="flex items-center gap-2">
            <FileText className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Wiki status</h2>
          </div>
          <section className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4">
            <div className="text-xs font-medium uppercase text-[var(--text-muted)]">Verdict</div>
            <div className="mt-1 break-words text-sm font-semibold text-[var(--text-primary)]">{wikiStatus?.verdict || "Wiki status unavailable"}</div>
            <div className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div>
                <div className="text-xs uppercase text-[var(--text-muted)]">Pages</div>
                <div className="mt-1 font-medium text-[var(--text-primary)]">{formatNumber(wikiStructure?.pages)}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-[var(--text-muted)]">Structure issues</div>
                <div className="mt-1 font-medium text-[var(--text-primary)]">{formatNumber(structureIssueCount)}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-[var(--text-muted)]">Thin pages</div>
                <div className="mt-1 font-medium text-[var(--text-primary)]">{formatNumber(compounding?.thin_page_count)}</div>
              </div>
              <div>
                <div className="text-xs uppercase text-[var(--text-muted)]">Batches</div>
                <div className="mt-1 font-medium text-[var(--text-primary)]">{formatNumber(wikiBatches?.batch_count)}</div>
              </div>
            </div>
            {uncoveredFamilies.length > 0 && (
              <div className="mt-4">
                <div className="text-xs font-medium uppercase text-[var(--text-muted)]">Uncovered source families</div>
                <div className="mt-2 space-y-2">
                  {uncoveredFamilies.map((family) => (
                    <div
                      key={family.family || "unknown"}
                      className="rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-xs text-[var(--text-secondary)]"
                    >
                      <span className="font-medium text-[var(--text-primary)]">{family.family || "unknown"}</span>
                      <span> - {formatNumber(family.uncovered)} uncovered of {formatNumber(family.total)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {wikiUpdateAction ? (
              <div className="mt-4 space-y-3">
                {wikiUpdateAction.reason && <p className="text-sm text-[var(--text-secondary)]">{wikiUpdateAction.reason}</p>}
                <button
                  type="button"
                  onClick={runWikiUpdate}
                  disabled={wikiUpdateRunning}
                  className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {wikiUpdateRunning ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <RefreshCw className="size-4" aria-hidden="true" />}
                  Prepare wiki update
                </button>
              </div>
            ) : wikiIsCurrent ? (
              <HealthyWikiActions />
            ) : (
              <p className="mt-3 text-sm text-[var(--text-secondary)]">
                Wiki maintenance status is available, but no update action is currently exposed.
              </p>
            )}
          </section>
        </aside>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Activity className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
            <h2 className="text-base font-semibold text-[var(--text-primary)]">Latest inbox runs</h2>
          </div>
          {isInitialLoading ? (
            <EmptyState>Loading inbox runs…</EmptyState>
          ) : latestRuns.length > 0 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {latestRuns.map((run) => (
                <RunSummary key={run.id} run={run} />
              ))}
            </div>
          ) : (
            <EmptyState>No inbox runs were returned.</EmptyState>
          )}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Retained ask outcomes</h2>
          {isInitialLoading ? (
            <EmptyState>Loading retained ask outcomes…</EmptyState>
          ) : askOutcomes.length > 0 ? (
            <div className="space-y-3">
              {askOutcomes.map((outcome) => (
                <AskOutcomeItem key={`${outcome.question ?? "outcome"}-${outcome.summary ?? ""}`} outcome={outcome} />
              ))}
            </div>
          ) : (
            <EmptyState>No retained ask outcomes were returned.</EmptyState>
          )}
        </div>
        <div className="space-y-3">
          <h2 className="text-base font-semibold text-[var(--text-primary)]">Ask clusters</h2>
          {isInitialLoading ? (
            <EmptyState>Loading ask clusters…</EmptyState>
          ) : askClusters.length > 0 ? (
            <div className="space-y-3">
              {askClusters.map((cluster) => (
                <AskClusterItem key={cluster.id || cluster.label || cluster.summary || "cluster"} cluster={cluster} />
              ))}
            </div>
          ) : (
            <EmptyState>No retained ask clusters were returned.</EmptyState>
          )}
        </div>
      </section>
    </div>
  );
}

function InsightsPageHeader({ onRefresh }: { onRefresh: () => void }) {
  return (
    <section className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <Brain className="size-5 text-[var(--text-secondary)]" aria-hidden="true" />
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Brain Insights</h2>
        </div>
        <p className="mt-2 max-w-3xl text-sm text-[var(--text-secondary)]">
          Review recent inbox-derived insights, retained ask outcomes, and wiki readiness signals before starting the next Brain maintenance step.
        </p>
      </div>
      <button
        type="button"
        onClick={onRefresh}
        className="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-md border border-[var(--border-color)] bg-[var(--bg-card)] px-3 py-2 text-sm font-medium text-[var(--text-secondary)] transition-colors hover:text-[var(--text-primary)] sm:w-auto sm:min-w-[120px]"
      >
        <RefreshCw className="size-4" aria-hidden="true" />
        Refresh
      </button>
    </section>
  );
}
