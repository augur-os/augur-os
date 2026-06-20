"use client";

import { type ComponentType } from "react";

export function SectionTitle({
  icon: Icon,
  title,
  description,
  iconClassName,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description: string;
  iconClassName: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <Icon className={`size-5 ${iconClassName}`} />
      <div>
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          {title}
        </h2>
        <p className="text-sm text-[var(--text-secondary)]">{description}</p>
      </div>
    </div>
  );
}
