import type { LucideIcon } from "lucide-react";
import type * as React from "react";

export type GlassCardColor =
  | "cyan"
  | "purple"
  | "emerald"
  | "amber"
  | "blue"
  | "rose"
  | "violet"
  | "pink";

export interface ColorScheme {
  gradient: string;
  bgGlow: string;
  border: string;
  bgOverlay: string;
}

export const colorSchemes: Record<GlassCardColor, ColorScheme> = {
  cyan: {
    gradient: "from-cyan-500 to-blue-500",
    bgGlow: "bg-cyan-500/20",
    border: "border-cyan-500/20 hover:border-cyan-500/40",
    bgOverlay: "from-cyan-500/5",
  },
  purple: {
    gradient: "from-purple-500 to-pink-500",
    bgGlow: "bg-purple-500/20",
    border: "border-purple-500/20 hover:border-purple-500/40",
    bgOverlay: "from-purple-500/5",
  },
  emerald: {
    gradient: "from-emerald-500 to-teal-500",
    bgGlow: "bg-emerald-500/20",
    border: "border-emerald-500/20 hover:border-emerald-500/40",
    bgOverlay: "from-emerald-500/5",
  },
  amber: {
    gradient: "from-amber-500 to-orange-500",
    bgGlow: "bg-amber-500/20",
    border: "border-amber-500/20 hover:border-amber-500/40",
    bgOverlay: "from-amber-500/5",
  },
  blue: {
    gradient: "from-blue-500 to-indigo-500",
    bgGlow: "bg-blue-500/20",
    border: "border-blue-500/20 hover:border-blue-500/40",
    bgOverlay: "from-blue-500/5",
  },
  rose: {
    gradient: "from-rose-500 to-pink-500",
    bgGlow: "bg-rose-500/20",
    border: "border-rose-500/20 hover:border-rose-500/40",
    bgOverlay: "from-rose-500/5",
  },
  violet: {
    gradient: "from-violet-500 to-purple-500",
    bgGlow: "bg-violet-500/20",
    border: "border-violet-500/20 hover:border-violet-500/40",
    bgOverlay: "from-violet-500/5",
  },
  pink: {
    gradient: "from-pink-500 to-rose-500",
    bgGlow: "bg-pink-500/20",
    border: "border-pink-500/20 hover:border-pink-500/40",
    bgOverlay: "from-pink-500/5",
  },
};

export interface GlassCardProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
  color?: GlassCardColor;
  icon?: LucideIcon;
  title?: string;
  subtitle?: string;
  showHoverGlow?: boolean;
  showBgOverlay?: boolean;
  interactive?: boolean;
  headerContent?: React.ReactNode;
  headerActions?: React.ReactNode;
}
