import type * as React from "react";

interface GlassCardBodyProps {
  children: React.ReactNode;
}

export function GlassCardBody({ children }: GlassCardBodyProps) {
  if (!children) {
    return null;
  }

  return <div className="p-5">{children}</div>;
}
