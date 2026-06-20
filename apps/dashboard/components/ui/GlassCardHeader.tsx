import type { LucideIcon } from "lucide-react";
import type * as React from "react";
import { DefaultHeaderContent } from "./DefaultHeaderContent";
import type { ColorScheme } from "./glassCardStyles";

interface GlassCardHeaderProps {
  headerContent?: React.ReactNode;
  Icon?: LucideIcon;
  title?: string;
  subtitle?: string;
  scheme: ColorScheme;
  headerActions?: React.ReactNode;
}

export function GlassCardHeader({
  headerContent,
  Icon,
  title,
  subtitle,
  scheme,
  headerActions,
}: GlassCardHeaderProps) {
  if (!(headerContent || Icon || title)) {
    return null;
  }

  return (
    <div className="flex items-center justify-between p-5 pb-0">
      {headerContent || (
        <DefaultHeaderContent
          Icon={Icon}
          title={title}
          subtitle={subtitle}
          scheme={scheme}
        />
      )}
      {headerActions && (
        <div className="flex items-center gap-2">{headerActions}</div>
      )}
    </div>
  );
}
