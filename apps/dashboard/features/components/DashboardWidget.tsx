import React, { ReactNode, type CSSProperties } from "react";
import WidgetVisibilityWrapper from "@/features/components/WidgetVisibilityWrapper";

interface DashboardWidgetProps extends React.HTMLAttributes<HTMLDivElement> {
  id?: string;
  title: string;
  children: ReactNode;
  icon?: React.ComponentType<{ className?: string }>;
  action?: ReactNode;
  className?: string;
  fillHeight?: boolean;
  contentClassName?: string;
  maxHeight?: string | number | null;
  scrollable?: boolean;
}

export default function DashboardWidget({
  id,
  title,
  children,
  icon: Icon,
  action,
  className = "",
  fillHeight = true,
  contentClassName = "",
  maxHeight,
  scrollable = true,
  ...props
}: DashboardWidgetProps) {
  const resolvedMaxHeight =
    maxHeight === null
      ? undefined
      : (maxHeight ?? "var(--dashboard-block-max-height)");
  const wrapperStyle: CSSProperties | undefined = resolvedMaxHeight
    ? { maxHeight: resolvedMaxHeight }
    : undefined;
  const contentClasses = [
    fillHeight ? "flex-1" : "",
    "min-h-0",
    scrollable ? "overflow-y-auto" : "overflow-visible",
    contentClassName,
  ]
    .filter(Boolean)
    .join(" ");

  const content = (
    <div
      {...props}
      className={`glass-panel p-6 flex flex-col min-h-0 ${fillHeight ? "h-full" : ""} ${className}`}
      style={wrapperStyle}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-[var(--text-primary)]">
          {Icon && <Icon className="size-5 text-[var(--text-muted)]" />}
          <h2 className="text-lg font-extrabold tracking-tight">{title}</h2>
        </div>
        {action}
      </div>
      <div className={contentClasses}>{children}</div>
    </div>
  );

  if (id) {
    return <WidgetVisibilityWrapper id={id}>{content}</WidgetVisibilityWrapper>;
  }

  return content;
}
