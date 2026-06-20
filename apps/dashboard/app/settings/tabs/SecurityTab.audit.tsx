"use client";

import { Fragment } from "react";
import {
  ShieldAlert,
  Loader2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Search,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { SectionTitle } from "./SecurityTab.shared";
import type {
  AuditReport,
  SecurityFinding,
  SecurityTabController,
} from "./SecurityTab.controller";

const SEVERITY_STYLES: Record<string, { badge: string; text: string }> = {
  HIGH: {
    badge:
      "bg-[var(--accent-danger)]/20 text-[var(--accent-danger)] border-[var(--accent-danger)]/30",
    text: "text-[var(--accent-danger)]",
  },
  MEDIUM: {
    badge:
      "bg-[var(--accent-warning)]/20 text-[var(--accent-warning)] border-[var(--accent-warning)]/30",
    text: "text-[var(--accent-warning)]",
  },
  LOW: {
    badge:
      "bg-[var(--accent-info)]/20 text-[var(--accent-info)] border-[var(--accent-info)]/30",
    text: "text-[var(--accent-info)]",
  },
};

function formatCategory(cat: string): string {
  return cat.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function CodebaseSecurityAuditSection({
  controller,
}: {
  controller: SecurityTabController;
}) {
  return (
    <section>
      <div className="flex items-center justify-between mb-4">
        <SectionTitle
          icon={ShieldAlert}
          title="Codebase Security Audit"
          description="Scan for vulnerabilities, secrets, and dependency issues"
          iconClassName="text-[var(--accent-danger)]"
        />
        {controller.auditReport && (
          <p className="text-xs text-[var(--text-muted)]">
            Last audit: {new Date(controller.auditReport.timestamp).toLocaleString()}
          </p>
        )}
      </div>
      <SecurityAuditActions controller={controller} />
      <AuditReportPanel controller={controller} />
    </section>
  );
}

function SecurityAuditActions({
  controller,
}: {
  controller: SecurityTabController;
}) {
  return (
    <div className="flex gap-3 mb-4">
      <Button
        onClick={controller.handleAiReview}
        disabled={controller.isExecuting}
        className="flex-1 h-12 gap-3 text-base bg-[var(--accent-danger)] hover:brightness-110 text-[var(--text-on-accent,#fff)] disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {controller.isExecuting ? (
          <Loader2 className="size-5 animate-spin" />
        ) : (
          <ShieldAlert className="size-5" />
        )}
        Run Security Audit
      </Button>
      <Button
        variant="outline"
        onClick={controller.handleQuickScan}
        disabled={controller.scanning}
        className="gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {controller.scanning ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Zap className="size-4" />
        )}
        Quick Scan
      </Button>
    </div>
  );
}

function AuditReportPanel({ controller }: { controller: SecurityTabController }) {
  const report = controller.auditReport;
  if (!report) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-8 text-center">
        <Search className="size-8 text-[var(--text-muted)] mx-auto mb-2" />
        <p className="text-sm text-[var(--text-secondary)]">
          No audit reports yet. Run a security audit to see results.
        </p>
      </div>
    );
  }

  return (
    <>
      <AuditSummaryCards report={report} />
      {report.findings?.length > 0 ? (
        <FindingsTable
          findings={report.findings}
          expandedRow={controller.expandedRow}
          onExpandedRowChange={controller.setExpandedRow}
        />
      ) : (
        <EmptyAuditFindings />
      )}
    </>
  );
}

function AuditSummaryCards({ report }: { report: AuditReport }) {
  const cards = [
    {
      label: "High",
      value: report.analysis_summary.high_severity,
      accent: "--accent-danger",
    },
    {
      label: "Medium",
      value: report.analysis_summary.medium_severity,
      accent: "--accent-warning",
    },
    {
      label: "Low",
      value: report.analysis_summary.low_severity,
      accent: null,
    },
    {
      label: "Files Reviewed",
      value: report.analysis_summary.files_reviewed,
      accent: null,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className={`p-4 rounded-xl border bg-[var(--bg-card)] ${card.accent && card.value > 0 ? `border-[var(${card.accent})]/30` : "border-[var(--border-color)]"}`}
        >
          <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider">
            {card.label}
          </p>
          <p className={`text-2xl font-bold ${card.accent && card.value > 0 ? `text-[var(${card.accent})]` : "text-[var(--text-primary)]"}`}>
            {card.value}
          </p>
        </div>
      ))}
    </div>
  );
}

function FindingsTable({
  findings,
  expandedRow,
  onExpandedRowChange,
}: {
  findings: SecurityFinding[];
  expandedRow: number | null;
  onExpandedRowChange: (row: number | null) => void;
}) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="bg-[var(--bg-secondary)] text-[var(--text-muted)] font-medium border-b border-[var(--border-color)]">
            <tr>
              <th scope="col" className="p-3 w-8"><span className="sr-only">Expand</span></th>
              <th scope="col" className="p-3 w-20">Severity</th>
              <th scope="col" className="p-3 w-16">Conf.</th>
              <th scope="col" className="p-3">Category</th>
              <th scope="col" className="p-3">File</th>
              <th scope="col" className="p-3 w-12">Line</th>
              <th scope="col" className="p-3">Description</th>
              <th scope="col" className="p-3 w-20">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]">
            {findings.map((finding, index) => (
              <FindingRows
                key={`${finding.file}:${finding.line}:${finding.category}:${index}`}
                finding={finding}
                index={index}
                isExpanded={expandedRow === index}
                onExpandedRowChange={onExpandedRowChange}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FindingRows({
  finding,
  index,
  isExpanded,
  onExpandedRowChange,
}: {
  finding: SecurityFinding;
  index: number;
  isExpanded: boolean;
  onExpandedRowChange: (row: number | null) => void;
}) {
  const style = SEVERITY_STYLES[finding.severity] || SEVERITY_STYLES.LOW;
  const hasDetail = Boolean(finding.exploit_scenario || finding.recommendation);
  const toggle = () => {
    if (hasDetail) {
      onExpandedRowChange(isExpanded ? null : index);
    }
  };

  return (
    <Fragment>
      <tr
        className={`hover:bg-[var(--bg-hover)] transition-colors duration-200 ${hasDetail ? "cursor-pointer" : ""}`}
        onClick={toggle}
        onKeyDown={
          hasDetail
            ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  toggle();
                }
              }
            : undefined
        }
        tabIndex={hasDetail ? 0 : undefined}
        role={hasDetail ? "button" : undefined}
        aria-expanded={hasDetail ? isExpanded : undefined}
      >
        <td className="p-3">
          {hasDetail &&
            (isExpanded ? (
              <ChevronDown className="size-3.5 text-[var(--text-muted)]" />
            ) : (
              <ChevronRight className="size-3.5 text-[var(--text-muted)]" />
            ))}
        </td>
        <td className="p-3">
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${style.badge}`}>
            {finding.severity}
          </span>
        </td>
        <td className="p-3 text-[var(--text-muted)] font-mono text-xs">
          {Math.round(finding.confidence * 100)}%
        </td>
        <td className="p-3 text-[var(--text-secondary)]">
          {formatCategory(finding.category)}
        </td>
        <td className="p-3 max-w-[200px]">
          <code className="text-xs bg-[var(--bg-secondary)] px-1.5 py-0.5 rounded border border-[var(--border-color)] truncate block max-w-full" title={finding.file}>
            {finding.file}
          </code>
        </td>
        <td className="p-3 text-[var(--text-muted)] font-mono text-xs">
          {finding.line || "—"}
        </td>
        <td className="p-3 text-[var(--text-secondary)] max-w-[300px] truncate">
          {finding.description}
        </td>
        <td className="p-3">
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${finding.source === "claude" ? "bg-[var(--accent-secondary)]/20 text-[var(--accent-secondary)]" : "bg-[var(--bg-hover)] text-[var(--text-muted)]"}`}>
            {finding.source === "claude" ? "Claude" : "Scanner"}
          </span>
        </td>
      </tr>
      {isExpanded && hasDetail && <FindingDetailRow finding={finding} />}
    </Fragment>
  );
}

function FindingDetailRow({ finding }: { finding: SecurityFinding }) {
  return (
    <tr>
      <td colSpan={8} className="px-6 py-4 bg-[var(--bg-secondary)]">
        <div className="space-y-2 text-sm">
          {finding.exploit_scenario && (
            <div>
              <span className="font-medium text-[var(--text-primary)]">
                Exploit Scenario:{" "}
              </span>
              <span className="text-[var(--text-secondary)]">
                {finding.exploit_scenario}
              </span>
            </div>
          )}
          {finding.recommendation && (
            <div>
              <span className="font-medium text-[var(--text-primary)]">
                Recommendation:{" "}
              </span>
              <span className="text-[var(--text-secondary)]">
                {finding.recommendation}
              </span>
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}

function EmptyAuditFindings() {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-8 text-center">
      <CheckCircle2 className="size-8 text-[var(--accent-success)] mx-auto mb-2" />
      <p className="text-sm text-[var(--text-secondary)]">
        No security issues found in the last audit.
      </p>
    </div>
  );
}
