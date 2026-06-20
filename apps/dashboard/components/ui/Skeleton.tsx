/**
 * Loading Skeleton Components
 *
 * Provides skeleton loading states for cards, text, and common UI patterns.
 * Uses CSS animations for smooth pulse effect.
 */

import React from "react";
import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /**
   * Visual variant of the skeleton
   */
  variant?: "text" | "circular" | "rectangular" | "rounded" | "shimmer";
  /**
   * Width of the skeleton (can be any CSS value)
   */
  width?: string | number;
  /**
   * Height of the skeleton (can be any CSS value)
   */
  height?: string | number;
  /**
   * Disable animation (static placeholder)
   */
  disableAnimation?: boolean;
}

const SKELETON_VARIANT_STYLES = {
  text: "rounded h-4 w-full",
  circular: "rounded-full",
  rectangular: "rounded-none",
  rounded: "rounded-lg",
  shimmer: "rounded-lg h-4 w-full",
} as const;

/**
 * Base Skeleton component
 */
function Skeleton({
  className,
  variant = "text",
  width,
  height,
  disableAnimation = false,
  style,
  ...props
}: SkeletonProps) {
  const baseStyles = "bg-[var(--bg-secondary)]";

  const animationStyles = disableAnimation
    ? ""
    : variant === "shimmer"
      ? "animate-shimmer"
      : "animate-pulse";

  const dimensionStyles: React.CSSProperties = {
    width: typeof width === "number" ? `${width}px` : width,
    height: typeof height === "number" ? `${height}px` : height,
    ...style,
  };

  return (
    <div
      className={cn(
        baseStyles,
        SKELETON_VARIANT_STYLES[variant],
        animationStyles,
        className,
      )}
      style={dimensionStyles}
      {...props}
    />
  );
}

/**
 * Text skeleton with multiple lines
 */
interface SkeletonTextProps {
  lines?: number;
  lineHeight?: number;
  lastLineWidth?: string;
  className?: string;
}

function SkeletonText({
  lines = 3,
  lineHeight = 16,
  lastLineWidth = "60%",
  className,
}: SkeletonTextProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          height={lineHeight}
          style={{
            width: i === lines - 1 ? lastLineWidth : "100%",
          }}
        />
      ))}
    </div>
  );
}

/**
 * Card skeleton with header, content, and footer
 */
interface SkeletonCardProps {
  hasHeader?: boolean;
  hasFooter?: boolean;
  lines?: number;
  className?: string;
}

function SkeletonCard({
  hasHeader = true,
  hasFooter = true,
  lines = 3,
  className,
}: SkeletonCardProps) {
  return (
    <div className={cn("glass-panel p-4 space-y-4", className)}>
      {hasHeader && (
        <div className="flex items-center gap-3">
          <Skeleton variant="circular" width={40} height={40} />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" width="60%" />
            <Skeleton variant="text" width="40%" />
          </div>
        </div>
      )}

      <SkeletonText lines={lines} />

      {hasFooter && (
        <div className="flex justify-end gap-2 pt-2">
          <Skeleton variant="rounded" width={80} height={32} />
          <Skeleton variant="rounded" width={80} height={32} />
        </div>
      )}
    </div>
  );
}

/**
 * Stats grid skeleton
 */
interface SkeletonStatsProps {
  count?: number;
  className?: string;
}

function SkeletonStats({ count = 4, className }: SkeletonStatsProps) {
  return (
    <div className={cn("grid grid-cols-2 md:grid-cols-4 gap-4", className)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="glass-panel p-4 space-y-2">
          <Skeleton variant="text" width="60%" />
          <Skeleton variant="text" width="40%" height={28} />
        </div>
      ))}
    </div>
  );
}

/**
 * Table skeleton
 */
interface SkeletonTableProps {
  rows?: number;
  columns?: number;
  className?: string;
}

function SkeletonTable({
  rows = 5,
  columns = 4,
  className,
}: SkeletonTableProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {/* Header */}
      <div className="flex gap-4 pb-2 border-b border-[var(--border-color)]">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} variant="text" className="flex-1" />
        ))}
      </div>

      {/* Rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={rowIndex} className="flex gap-4 py-2">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton
              key={colIndex}
              variant="text"
              className="flex-1"
              style={{ width: colIndex === 0 ? "40%" : "100%" }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * Dashboard widget skeleton
 */
interface SkeletonWidgetProps {
  title?: string;
  children?: React.ReactNode;
  className?: string;
}

function SkeletonWidget({
  title = "Loading...",
  children,
  className,
}: SkeletonWidgetProps) {
  return (
    <div className={cn("glass-panel", className)}>
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--border-color)]">
        <Skeleton variant="circular" width={20} height={20} />
        <Skeleton variant="text" width={120} />
      </div>
      <div className="p-4">{children || <SkeletonText lines={3} />}</div>
    </div>
  );
}

/**
 * Full page skeleton for initial load
 */
function SkeletonPage() {
  return (
    <div className="space-y-6 animate-pulse">
      {/* Header */}
      <div className="space-y-2">
        <Skeleton variant="rounded" width={300} height={36} />
        <Skeleton variant="text" width={200} />
      </div>

      {/* Stats */}
      <SkeletonStats />

      {/* Content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SkeletonWidget />
        <SkeletonWidget />
      </div>
    </div>
  );
}

export {
  Skeleton,
  SkeletonText,
  SkeletonCard,
  SkeletonStats,
  SkeletonTable,
  SkeletonWidget,
  SkeletonPage,
};

