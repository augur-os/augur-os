/**
 * Standardized Button Component
 *
 * Replaces ad-hoc button implementations across the application.
 * Supports all variants, sizes, and states with proper accessibility.
 */

import type React from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

// Button variant styles
const variantStyles = {
  // Primary solid button
  solid:
    "bg-[var(--accent-primary)] text-[var(--accent-foreground)] shadow-lg hover:opacity-90 hover:shadow-xl",
  // Secondary/outline button
  outline:
    "border border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)] hover:border-[var(--accent-primary)]",
  // Ghost button (subtle)
  ghost:
    "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]",
  // Dashed border button
  dashed:
    "border border-dashed border-[var(--text-muted)] text-[var(--text-secondary)] hover:border-[var(--text-primary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]",
  // Danger/destructive button
  danger: "bg-[var(--accent-danger)] text-white shadow-lg hover:opacity-90",
  // Success button
  success: "bg-[var(--accent-success)] text-white shadow-lg hover:opacity-90",
  // Link style button
  link: "text-[var(--accent-primary)] underline-offset-4 hover:underline",
  // Default (same as solid)
  default:
    "bg-[var(--accent-primary)] text-[var(--accent-foreground)] shadow-lg hover:opacity-90 hover:shadow-xl",
};

const sizeStyles = {
  xs: "h-7 px-2 text-xs gap-1",
  sm: "h-8 min-h-[44px] px-3 text-xs",
  md: "h-10 px-4 py-2",
  lg: "h-12 px-6 text-base",
  icon: "h-10 w-10 p-2",
  "icon-sm": "h-8 w-8 min-h-[44px] min-w-[44px] p-1.5",
  "icon-lg": "h-12 w-12 p-3",
};

const widthStyles = {
  auto: "",
  full: "w-full",
};

// Base button styles
const baseStyles =
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.98]";

export interface ButtonProps extends React.ComponentPropsWithRef<"button"> {
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizeStyles;
  width?: keyof typeof widthStyles;
  asChild?: boolean;
  isLoading?: boolean;
  loadingText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

function Button({
  className,
  variant = "solid",
  size = "md",
  width = "auto",
  asChild: _asChild = false,
  isLoading = false,
  loadingText,
  leftIcon,
  rightIcon,
  children,
  disabled,
  type = "button",
  ref,
  ...props
}: ButtonProps) {
  // Build className from styles
  const buttonClassName = cn(
    baseStyles,
    variantStyles[variant],
    sizeStyles[size],
    widthStyles[width],
    className,
  );

  // Show loading spinner when loading
  const content = isLoading ? (
    <>
      <Loader2 className="size-4 animate-spin" />
      {loadingText || children}
    </>
  ) : (
    <>
      {leftIcon && <span className="flex-shrink-0">{leftIcon}</span>}
      {children}
      {rightIcon && <span className="flex-shrink-0">{rightIcon}</span>}
    </>
  );

  return (
    <button
      className={buttonClassName}
      ref={ref}
      disabled={disabled || isLoading}
      type={type}
      {...props}
    >
      {content}
    </button>
  );
}

export { Button };

// Default export
export default Button;
