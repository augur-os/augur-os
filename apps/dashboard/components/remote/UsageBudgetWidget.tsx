"use client";

import { DollarSign, TrendingUp, AlertTriangle } from "lucide-react";
import { GlassCard } from "@/components/ui/GlassCard";
import type { UsageStats, BudgetSettings } from "@/lib/remote/types";

interface UsageBudgetWidgetProps {
  usage: UsageStats;
  budget: BudgetSettings;
}

export default function UsageBudgetWidget({
  usage,
  budget,
}: UsageBudgetWidgetProps) {
  const dailyCost = usage?.dailyCost ?? 0;
  const monthlyCost = usage?.monthlyCost ?? 0;
  const dailyLimit = budget?.dailyLimitUsd ?? 1;
  const monthlyLimit = budget?.monthlyLimitUsd ?? 1;
  const dailyPercentage = (dailyCost / dailyLimit) * 100;
  const monthlyPercentage = (monthlyCost / monthlyLimit) * 100;

  const getStatusColor = (percentage: number) => {
    if (percentage >= 100)
      return { bar: "bg-[var(--accent-danger)]", text: "text-[var(--accent-danger)]" };
    if (percentage >= budget.warnAtPercentage)
      return {
        bar: "bg-[var(--accent-warning)]",
        text: "text-[var(--accent-warning)]",
      };
    return {
      bar: "bg-[var(--accent-success)]",
      text: "text-[var(--accent-success)]",
    };
  };

  const dailyStatus = getStatusColor(dailyPercentage);
  const monthlyStatus = getStatusColor(monthlyPercentage);

  return (
    <GlassCard className="p-5">
      <div className="flex items-center gap-3 mb-4">
        <div className="size-10 rounded-lg bg-[var(--accent-success)]/20 border border-[var(--accent-success)]/20 flex items-center justify-center">
          <DollarSign className="size-5 text-[var(--accent-success)]" />
        </div>
        <div>
          <h3 className="font-semibold text-[var(--text-primary)]">
            Usage & Budget
          </h3>
          <p className="text-xs text-[var(--text-muted)]">
            Track your remote provider spending
          </p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Daily Budget */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[var(--text-muted)]">Daily</span>
            <div className="flex items-center gap-2">
              <span className={`text-sm font-medium ${dailyStatus.text}`}>
                ${dailyCost.toFixed(2)}
              </span>
              <span className="text-xs text-[var(--text-muted)]">
                / ${dailyLimit.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="h-2 rounded-full bg-[var(--bg-secondary)] overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${dailyStatus.bar}`}
              style={{ width: `${Math.min(dailyPercentage, 100)}%` }}
            />
          </div>
          {dailyPercentage >= budget.warnAtPercentage && (
            <div className="flex items-center gap-1.5 mt-2 text-xs">
              <AlertTriangle className={`size-3 ${dailyStatus.text}`} />
              <span className={dailyStatus.text}>
                {dailyPercentage >= 100
                  ? "Daily limit reached"
                  : `${dailyPercentage.toFixed(0)}% of daily budget used`}
              </span>
            </div>
          )}
        </div>

        {/* Monthly Budget */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-[var(--text-muted)]">Monthly</span>
            <div className="flex items-center gap-2">
              <span className={`text-sm font-medium ${monthlyStatus.text}`}>
                ${monthlyCost.toFixed(2)}
              </span>
              <span className="text-xs text-[var(--text-muted)]">
                / ${monthlyLimit.toFixed(2)}
              </span>
            </div>
          </div>
          <div className="h-2 rounded-full bg-[var(--bg-secondary)] overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${monthlyStatus.bar}`}
              style={{ width: `${Math.min(monthlyPercentage, 100)}%` }}
            />
          </div>
          {monthlyPercentage >= budget.warnAtPercentage && (
            <div className="flex items-center gap-1.5 mt-2 text-xs">
              <AlertTriangle className={`size-3 ${monthlyStatus.text}`} />
              <span className={monthlyStatus.text}>
                {monthlyPercentage >= 100
                  ? "Monthly limit reached"
                  : `${monthlyPercentage.toFixed(0)}% of monthly budget used`}
              </span>
            </div>
          )}
        </div>

        {/* Token Stats */}
        <div className="pt-3 border-t border-[var(--border-color)]">
          <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
            <TrendingUp className="size-3" />
            <span>
              {((usage.dailyTokens ?? 0) / 1000).toFixed(1)}K tokens today
              {" • "}
              {((usage.monthlyTokens ?? 0) / 1000).toFixed(1)}K this month
            </span>
          </div>
        </div>
      </div>
    </GlassCard>
  );
}
