"use client";

import { useMemo } from "react";
import { Activity } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import type { ProviderListResponse, UsageStats } from "@/lib/remote/types";

const DEFAULT_USAGE: UsageStats = {
  dailyCost: 0,
  monthlyCost: 0,
  dailyTokens: 0,
  monthlyTokens: 0,
  byProvider: {},
};

/**
 * ADR-773: Read-only AI activity, extracted out of ProvidersPage so the AI &
 * Models tab reads as a Configure zone over a demoted Activity zone. Re-uses the
 * cached `['remote','providers']` query key, so it shares ProvidersPage's fetch
 * (no double load).
 */
export function AiActivitySection() {
  const { data: providersData } = useMcpQuery<ProviderListResponse>(
    ["remote", "providers"],
    "get-settings",
    "config",
    { args: { scope: "remote-providers" } },
  );

  const usage = useMemo<UsageStats>(
    () => ({ ...DEFAULT_USAGE, ...providersData?.usage }),
    [providersData],
  );

  const byProvider = Object.entries(usage.byProvider);

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-3">
        <Activity
          className="size-5 text-[var(--accent-warning)]"
          aria-hidden="true"
        />
        <div>
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Activity &amp; status
          </h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Read-only: remote provider spend and token usage.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <GlassCard className="p-4 text-center">
          <p className="text-2xl font-bold text-[var(--accent-warning)]">
            ${usage.dailyCost.toFixed(2)}
          </p>
          <p className="text-xs text-[var(--text-muted)]">Cost today</p>
        </GlassCard>
        <GlassCard className="p-4 text-center">
          <p className="text-2xl font-bold text-[var(--text-primary)]">
            {usage.dailyTokens.toLocaleString()}
          </p>
          <p className="text-xs text-[var(--text-muted)]">Tokens today</p>
        </GlassCard>
        <GlassCard className="p-4 text-center">
          <p className="text-2xl font-bold text-[var(--accent-warning)]">
            ${usage.monthlyCost.toFixed(2)}
          </p>
          <p className="text-xs text-[var(--text-muted)]">Cost this month</p>
        </GlassCard>
        <GlassCard className="p-4 text-center">
          <p className="text-2xl font-bold text-[var(--text-primary)]">
            {usage.monthlyTokens.toLocaleString()}
          </p>
          <p className="text-xs text-[var(--text-muted)]">Tokens this month</p>
        </GlassCard>
      </div>

      {byProvider.length > 0 ? (
        <GlassCard className="overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border-color)]">
            <h3 className="text-sm font-medium text-[var(--text-primary)]">
              By Provider
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[480px]">
              <thead>
                <tr className="border-b border-[var(--border-color)]">
                  <th scope="col" className="px-4 py-3 text-left text-sm font-medium text-[var(--text-muted)]">
                    Provider
                  </th>
                  <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-[var(--text-muted)]">
                    Requests
                  </th>
                  <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-[var(--text-muted)]">
                    Tokens
                  </th>
                  <th scope="col" className="px-4 py-3 text-right text-sm font-medium text-[var(--text-muted)]">
                    Cost
                  </th>
                </tr>
              </thead>
              <tbody>
                {byProvider.map(([provider, stats]) =>
                  stats ? (
                    <tr
                      key={provider}
                      className="border-b border-[var(--border-color)]"
                    >
                      <td className="px-4 py-3 text-[var(--text-secondary)] capitalize">
                        {provider}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-[var(--text-muted)]">
                        {stats.requests.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-[var(--text-muted)]">
                        {stats.tokens.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right text-xs text-[var(--accent-warning)]">
                        ${stats.cost.toFixed(4)}
                      </td>
                    </tr>
                  ) : null,
                )}
              </tbody>
            </table>
          </div>
        </GlassCard>
      ) : (
        <GlassCard className="p-6 text-center">
          <p className="text-sm text-[var(--text-muted)]">
            No remote provider usage recorded yet.
          </p>
        </GlassCard>
      )}
    </section>
  );
}
