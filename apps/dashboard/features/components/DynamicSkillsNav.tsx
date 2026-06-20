"use client";

import { useMemo } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Package } from "lucide-react";
import { Tooltip } from "@/components/ui/Tooltip";
import { skillNavItems } from "@/lib/tabs/generated-skill-nav";

/**
 * Sidebar section for standalone skills that opted into nav visibility (ADR-165).
 *
 * All data comes from build-time generated-skill-nav.ts — zero runtime fetches,
 * zero hardcoded exclusion lists. Skills opt in via `nav: { visible: true }` in
 * their skill config.
 */

const CATEGORY_PRIORITY = ["Tools", "Integrations", "System", "Extensions"];

export default function DynamicSkillsNav() {
  const pathname = usePathname();

  const activeSlug = useMemo(() => {
    if (!pathname.startsWith("/browse/")) return null;
    return pathname.split("/")[2] || null;
  }, [pathname]);

  const groupedSkills = useMemo(() => {
    const groups: Record<string, typeof skillNavItems> = {};
    for (const item of skillNavItems) {
      if (!groups[item.category]) groups[item.category] = [];
      groups[item.category].push(item);
    }
    return groups;
  }, []);

  if (skillNavItems.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 mt-2">
      {CATEGORY_PRIORITY.map((category) => {
        const categorySkills = groupedSkills[category];
        if (!categorySkills?.length) return null;

        return (
          <div key={category} className="flex flex-col gap-2">
            <div className="nav-section nav-section-tertiary">{category}</div>
            <div className="flex flex-col gap-2">
              {categorySkills.map((skill) => (
                <Tooltip
                  key={skill.slug}
                  content={`Open ${skill.label}`}
                  side="right"
                  className="contents"
                >
                  <Link
                    href={skill.route}
                    prefetch={false}
                    className={`nav-link ${activeSlug === skill.slug ? "nav-link-active" : ""}`}
                  >
                    <Package className="size-5 opacity-70" />
                    <span className="text-sm font-medium truncate">
                      {skill.label}
                    </span>
                  </Link>
                </Tooltip>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
