import { cn } from "@/lib/utils";
import { GlassCardBody } from "./GlassCardBody";
import { GlassCardHeader } from "./GlassCardHeader";
import { GlassCardOverlays } from "./GlassCardOverlays";
import {
  colorSchemes,
  type GlassCardColor,
  type GlassCardProps,
} from "./glassCardStyles";

/**
 * GlassCard - Standard glass-effect card component for Augur dashboard.
 */
function GlassCard({
  className,
  children,
  color = "cyan",
  icon: Icon,
  title,
  subtitle,
  showHoverGlow = true,
  showBgOverlay = true,
  interactive = false,
  headerContent,
  headerActions,
  ref,
  ...props
}: GlassCardProps) {
  const scheme = colorSchemes[color];

  return (
    <div
      ref={ref}
      className={cn(
        "relative overflow-hidden rounded-2xl border bg-[var(--bg-card)] shadow-sm transition-all duration-300",
        scheme.border,
        interactive && "hover:shadow-md cursor-pointer",
        interactive && showHoverGlow && "group",
        !interactive && "hover:border-[var(--border-color)]",
        className,
      )}
      {...props}
    >
      <GlassCardOverlays
        showBgOverlay={showBgOverlay}
        showHoverGlow={showHoverGlow}
        interactive={interactive}
        scheme={scheme}
      />

      <div className="relative z-10">
        <GlassCardHeader
          headerContent={headerContent}
          Icon={Icon}
          title={title}
          subtitle={subtitle}
          scheme={scheme}
          headerActions={headerActions}
        />
        <GlassCardBody>{children}</GlassCardBody>
      </div>
    </div>
  );
}

export { GlassCard };
export type { GlassCardColor, GlassCardProps };
