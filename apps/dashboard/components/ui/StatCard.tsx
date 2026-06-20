import React from "react";

interface StatCardProps {
  value: number | string;
  label: string;
  color: "red" | "orange" | "yellow" | "green" | "cyan" | "neutral";
  onClick?: () => void;
  active?: boolean;
  trend?: string;
  emoji?: string;
  bgColor?: string;
}

const colorClasses = {
  red: {
    active: "bg-[var(--accent-danger)]/20 border-[var(--accent-danger)]",
    inactive: "bg-[var(--accent-danger)]/10 border-[var(--accent-danger)]/20 hover:bg-[var(--accent-danger)]/20",
    text: "text-[var(--accent-danger)]",
    textMuted: "text-[var(--accent-danger)]/70",
  },
  orange: {
    active: "bg-[var(--accent-warning)]/20 border-[var(--accent-warning)]",
    inactive: "bg-[var(--accent-warning)]/10 border-[var(--accent-warning)]/20 hover:bg-[var(--accent-warning)]/20",
    text: "text-[var(--accent-warning)]",
    textMuted: "text-[var(--accent-warning)]/70",
  },
  yellow: {
    active: "bg-[var(--accent-warning)]/20 border-[var(--accent-warning)]",
    inactive: "bg-[var(--accent-warning)]/10 border-[var(--accent-warning)]/20 hover:bg-[var(--accent-warning)]/20",
    text: "text-[var(--accent-warning)]",
    textMuted: "text-[var(--accent-warning)]/70",
  },
  green: {
    active: "bg-[var(--accent-success)]/20 border-[var(--accent-success)]",
    inactive: "bg-[var(--accent-success)]/10 border-[var(--accent-success)]/20 hover:bg-[var(--accent-success)]/20",
    text: "text-[var(--accent-success)]",
    textMuted: "text-[var(--accent-success)]/70",
  },
  cyan: {
    active: "bg-[var(--accent-info)]/20 border-[var(--accent-info)]",
    inactive: "bg-[var(--accent-info)]/10 border-[var(--accent-info)]/20 hover:bg-[var(--accent-info)]/20",
    text: "text-[var(--accent-info)]",
    textMuted: "text-[var(--accent-info)]/70",
  },
  neutral: {
    active: "bg-[var(--bg-hover)] border-[var(--border-color)]",
    inactive:
      "bg-[var(--bg-secondary)] border-[var(--border-color)] hover:bg-[var(--bg-hover)]",
    text: "text-[var(--text-primary)]",
    textMuted: "text-[var(--text-muted)]",
  },
};

export function StatCard({
  value,
  label,
  color,
  onClick,
  active = false,
  trend,
  emoji,
  bgColor,
}: StatCardProps) {
  const colors = colorClasses[color];
  const Component = onClick ? "button" : "div";

  const bgClass = bgColor
    ? `${bgColor} border ${
        active
          ? colors.active
              .split(" ")
              .filter((c) => c.startsWith("border-"))
              .join(" ")
          : colors.inactive
              .split(" ")
              .filter((c) => c.startsWith("border-") || c.startsWith("hover:"))
              .join(" ")
      }`
    : active
      ? colors.active
      : colors.inactive;

  return (
    <Component
      onClick={onClick}
      className={`rounded-lg p-4 text-center transition-all border ${bgClass} ${onClick ? "cursor-pointer" : ""}`}
    >
      <div className={`text-3xl font-bold ${colors.text}`}>
        {emoji && <span className="mr-1">{emoji}</span>}
        {value}
      </div>
      <div className={`text-xs ${colors.textMuted}`}>{label}</div>
      {trend && (
        <div className={`text-xs mt-1 ${colors.textMuted}`}>{trend}</div>
      )}
    </Component>
  );
}
