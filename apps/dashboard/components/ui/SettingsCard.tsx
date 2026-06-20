"use client";

/**
 * SettingsCard - Unified card component for Settings page
 *
 * Consistent building block for all items in Settings sections.
 * Matches the ServiceCard layout: icon on top row with badges, title below.
 */

import { LucideIcon } from "lucide-react";

export type CardVariant =
  | "default"
  | "success"
  | "warning"
  | "error"
  | "info"
  | "muted";

interface SettingsCardProps {
  /** Card title */
  title: string;
  /** Subtitle or path text (shown in mono font if isPath=true) */
  subtitle?: string;
  /** Whether subtitle is a path (renders in monospace) */
  isPath?: boolean;
  /** Icon to display */
  icon: LucideIcon;
  /** Color variant */
  variant?: CardVariant;
  /** Primary badge text */
  badge?: string;
  /** Secondary badge text */
  secondaryBadge?: string;
  /** Right side content (value display) */
  value?: string;
  /** Value label */
  valueLabel?: string;
  /** Right side action component */
  action?: React.ReactNode;
  /** Click handler */
  onClick?: () => void;
  /** Additional className */
  className?: string;
  /** Children to render below main content */
  children?: React.ReactNode;
}

const variantConfig: Record<
  CardVariant,
  {
    iconBg: string;
    iconColor: string;
    borderColor: string;
    badgeBg: string;
    badgeColor: string;
    indicatorColor: string;
  }
> = {
  default: {
    iconBg: "bg-[var(--accent-primary)]/10",
    iconColor: "text-[var(--accent-primary)]",
    borderColor: "border-[var(--border-color)] hover:border-[var(--accent-primary)]/30",
    badgeBg: "bg-[var(--accent-primary)]/10",
    badgeColor: "text-[var(--accent-primary)]",
    indicatorColor: "bg-[var(--accent-primary)]",
  },
  success: {
    iconBg: "bg-[var(--accent-success)]/10",
    iconColor: "text-[var(--accent-success)]",
    borderColor: "border-[var(--accent-success)]/20 hover:border-[var(--accent-success)]/40",
    badgeBg: "bg-[var(--accent-success)]/10",
    badgeColor: "text-[var(--accent-success)]",
    indicatorColor: "bg-[var(--accent-success)]",
  },
  warning: {
    iconBg: "bg-[var(--accent-warning)]/10",
    iconColor: "text-[var(--accent-warning)]",
    borderColor: "border-[var(--accent-warning)]/20 hover:border-[var(--accent-warning)]/40",
    badgeBg: "bg-[var(--accent-warning)]/10",
    badgeColor: "text-[var(--accent-warning)]",
    indicatorColor: "bg-[var(--accent-warning)]",
  },
  error: {
    iconBg: "bg-[var(--accent-danger)]/10",
    iconColor: "text-[var(--accent-danger)]",
    borderColor: "border-[var(--accent-danger)]/20 hover:border-[var(--accent-danger)]/40",
    badgeBg: "bg-[var(--accent-danger)]/10",
    badgeColor: "text-[var(--accent-danger)]",
    indicatorColor: "bg-[var(--accent-danger)]",
  },
  info: {
    iconBg: "bg-[var(--accent-info)]/10",
    iconColor: "text-[var(--accent-info)]",
    borderColor: "border-[var(--accent-info)]/20 hover:border-[var(--accent-info)]/40",
    badgeBg: "bg-[var(--accent-info)]/10",
    badgeColor: "text-[var(--accent-info)]",
    indicatorColor: "bg-[var(--accent-info)]",
  },
  muted: {
    iconBg: "bg-[var(--text-muted)]/10",
    iconColor: "text-[var(--text-muted)]",
    borderColor: "border-[var(--border-color)] hover:border-[var(--text-muted)]/30",
    badgeBg: "bg-[var(--text-muted)]/10",
    badgeColor: "text-[var(--text-muted)]",
    indicatorColor: "bg-[var(--text-muted)]",
  },
};

export function SettingsCard({
  title,
  subtitle,
  isPath = false,
  icon: Icon,
  variant = "default",
  badge,
  secondaryBadge,
  value,
  valueLabel,
  action,
  onClick,
  className = "",
  children,
}: SettingsCardProps) {
  const config = variantConfig[variant];
  const Component = onClick ? "button" : "div";

  return (
    <Component
      onClick={onClick}
      className={`
        relative overflow-hidden rounded-xl border bg-[var(--bg-card)]
        transition-all duration-200 ${config.borderColor}
        ${onClick ? "cursor-pointer" : ""}
        ${className}
      `}
    >
      {/* Left status indicator bar */}
      <div
        className={`absolute left-0 top-0 bottom-0 w-1 ${config.indicatorColor}`}
      />

      <div className="p-4 pl-5">
        {/* Header row: Icon + Badges/Value/Action */}
        <div className="flex items-center justify-between mb-3">
          <div
            className={`w-9 h-9 rounded-lg flex items-center justify-center ${config.iconBg}`}
          >
            <Icon className={`w-[18px] h-[18px] ${config.iconColor}`} />
          </div>

          <div className="flex items-center gap-2">
            {secondaryBadge && (
              <span className="px-2 py-0.5 text-[10px] font-medium text-[var(--text-muted)] bg-[var(--bg-hover)] rounded-full">
                {secondaryBadge}
              </span>
            )}
            {badge && (
              <span
                className={`px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded-full ${config.badgeBg} ${config.badgeColor}`}
              >
                {badge}
              </span>
            )}
            {value && (
              <div className="text-right">
                <p className="text-sm font-bold text-[var(--text-primary)]">
                  {value}
                </p>
                {valueLabel && (
                  <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-tight">
                    {valueLabel}
                  </p>
                )}
              </div>
            )}
            {action}
          </div>
        </div>

        {/* Title and subtitle below */}
        <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-1">
          {title}
        </h3>
        {subtitle && (
          <p
            className={`text-xs text-[var(--text-muted)] leading-relaxed ${
              isPath ? "font-mono text-[10px] truncate" : ""
            }`}
          >
            {subtitle}
          </p>
        )}

        {/* Optional children content below */}
        {children && <div className="mt-3">{children}</div>}
      </div>
    </Component>
  );
}

export default SettingsCard;
