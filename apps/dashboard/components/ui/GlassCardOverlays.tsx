import { cn } from "@/lib/utils";
import type { ColorScheme } from "./glassCardStyles";

interface GlassCardOverlaysProps {
  showBgOverlay: boolean;
  showHoverGlow: boolean;
  interactive: boolean;
  scheme: ColorScheme;
}

export function GlassCardOverlays({
  showBgOverlay,
  showHoverGlow,
  interactive,
  scheme,
}: GlassCardOverlaysProps) {
  return (
    <>
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[var(--border-color)]/20 to-transparent pointer-events-none" />

      {showBgOverlay && (
        <div
          className={cn(
            "absolute inset-0 bg-gradient-to-br via-transparent to-transparent pointer-events-none opacity-50",
            scheme.bgOverlay,
          )}
        />
      )}

      {showHoverGlow && interactive && (
        <div
          className={cn(
            "absolute inset-0 opacity-0 group-hover:opacity-100 blur-xl transition-opacity duration-300",
            scheme.bgGlow,
          )}
        />
      )}
    </>
  );
}
