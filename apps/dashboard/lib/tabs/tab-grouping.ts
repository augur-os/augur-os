import type { GroupedTab, TabEntry, TabItem } from './types';

/**
 * Type guard: is this tab entry a grouped dropdown?
 * True only if children is a non-empty array.
 */
export function isGroupedTab(tab: TabEntry): tab is GroupedTab {
  return 'children' in tab && Array.isArray((tab as GroupedTab).children) && (tab as GroupedTab).children.length > 0;
}

/**
 * Convert a skill-id like "home-automation" to "Home Automation".
 */
function formatSkillLabel(skillId: string): string {
  return skillId
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

/**
 * Group tabs by skillId. Skills with 2+ tabs become GroupedTab dropdowns.
 * Skills with 1 tab and tabs without skillId pass through as flat TabItems.
 * Order: groups appear at the position of the first tab with that skillId.
 */
export function groupBySkillId(tabs: TabItem[]): TabEntry[] {
  const bySkill = new Map<string, TabItem[]>();
  const flatTabs: { index: number; tab: TabItem }[] = [];
  const groupPositions = new Map<string, number>();

  for (let i = 0; i < tabs.length; i++) {
    const tab = tabs[i];
    const skill = tab.skillId;
    if (!skill) {
      flatTabs.push({ index: i, tab });
      continue;
    }
    if (!bySkill.has(skill)) {
      bySkill.set(skill, []);
      groupPositions.set(skill, i);
    }
    bySkill.get(skill)!.push(tab);
  }

  const entries: { index: number; entry: TabEntry }[] = [
    ...flatTabs.map(({ index, tab }) => ({ index, entry: tab as TabEntry })),
  ];

  for (const [skill, skillTabs] of bySkill) {
    const pos = groupPositions.get(skill)!;
    if (skillTabs.length === 1) {
      entries.push({ index: pos, entry: skillTabs[0] });
    } else {
      const group: GroupedTab = {
        id: skill,
        label: formatSkillLabel(skill),
        icon: skillTabs[0].icon,
        href: skillTabs[0].href,
        skillId: skill,
        children: skillTabs,
      };
      entries.push({ index: pos, entry: group });
    }
  }

  entries.sort((a, b) => a.index - b.index);
  return entries.map((e) => e.entry);
}
