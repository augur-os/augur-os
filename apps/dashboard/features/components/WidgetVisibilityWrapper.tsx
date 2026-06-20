"use client";

import { ReactNode } from "react";
import { useWidgetVisibility } from "@/features/components/layout-config/LayoutConfigModal";

interface WidgetVisibilityWrapperProps {
  id: string;
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Conditionally renders children based on the visibility settings
 * controlled via LayoutConfigModal.
 */
export default function WidgetVisibilityWrapper({
  id,
  children,
  fallback = null,
}: WidgetVisibilityWrapperProps) {
  const isVisible = useWidgetVisibility(id);

  if (!isVisible) {
    return fallback as any;
  }

  return <>{children}</>;
}
