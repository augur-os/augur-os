"use client";

const EMPTY_ARRAY: never[] = [];

import { useCallback, useMemo, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

import { CommandCard } from "@/components/browse/CommandCard";
import { IntegrationTab } from "@/components/browse/IntegrationTab";
import { PromptCard } from "@/components/browse/PromptCard";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type {
  CapabilityProfileSection,
  PromptResult,
  SkillCommand,
  SkillPrompt,
} from "@/lib/browse/types";

type SkillDetailTabId = "overview" | "prompts" | "commands" | "integration";

interface SkillDetailTabsProps {
  skillId: string;
  skillLabel?: string;
  prompts: SkillPrompt[];
  commands: SkillCommand[];
  overviewContent: ReactNode;
  capabilityProfileSections?: CapabilityProfileSection[];
}

type TabMeta = {
  id: SkillDetailTabId;
  label: string;
  count?: number;
};

type ActiveTabState = {
  key: string;
  activeTab: SkillDetailTabId;
};

function getDefaultTab(prompts: SkillPrompt[], commands: SkillCommand[]): SkillDetailTabId {
  if (prompts.length > 0) return "prompts";
  if (commands.length > 0) return "commands";
  return "overview";
}

export function SkillDetailTabs({
  skillId,
  skillLabel,
  prompts,
  commands,
  overviewContent,
  capabilityProfileSections = EMPTY_ARRAY,
}: SkillDetailTabsProps) {
  const availableTabs = useMemo<TabMeta[]>(() => {
    const tabs: TabMeta[] = [{ id: "overview", label: "Overview" }];

    if (prompts.length > 0) {
      tabs.push({ id: "prompts", label: "Prompts", count: prompts.length });
    }

    if (commands.length > 0) {
      tabs.push({ id: "commands", label: "Commands", count: commands.length });
    }

    tabs.push({ id: "integration", label: "Integration" });
    return tabs;
  }, [commands.length, prompts.length]);

  const defaultTab = useMemo(
    () => getDefaultTab(prompts, commands),
    [commands, prompts],
  );

  const activeTabKey = `${skillId}:${defaultTab}`;
  const [activeTabState, setActiveTabState] = useState<ActiveTabState>({
    key: activeTabKey,
    activeTab: defaultTab,
  });
  const activeTab =
    activeTabState.key === activeTabKey ? activeTabState.activeTab : defaultTab;
  const setActiveTabForCurrentSkill = useCallback(
    (nextTab: SkillDetailTabId) => {
      setActiveTabState({ key: activeTabKey, activeTab: nextTab });
    },
    [activeTabKey],
  );

  const handlePromptResult = useCallback((_result: PromptResult) => {
    // PromptCard renders its own result inline; the wrapper only needs to satisfy the contract.
  }, []);

  const handleCommandResult = useCallback((_result: PromptResult) => {
    // CommandCard renders its own result inline; the wrapper only needs to satisfy the contract.
  }, []);

  const focusTab = useCallback((tabId: SkillDetailTabId) => {
    requestAnimationFrame(() => {
      document.getElementById(`skill-detail-tab-${tabId}`)?.focus();
    });
  }, []);

  const handleTabKeyDown = useCallback(
    (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
      const lastIndex = availableTabs.length - 1;
      let nextIndex: number | null = null;

      if (event.key === "ArrowRight") {
        nextIndex = index === lastIndex ? 0 : index + 1;
      } else if (event.key === "ArrowLeft") {
        nextIndex = index === 0 ? lastIndex : index - 1;
      } else if (event.key === "Home") {
        nextIndex = 0;
      } else if (event.key === "End") {
        nextIndex = lastIndex;
      }

      if (nextIndex === null) {
        return;
      }

      event.preventDefault();
      const nextTab = availableTabs[nextIndex];
      setActiveTabForCurrentSkill(nextTab.id);
      focusTab(nextTab.id);
    },
    [availableTabs, focusTab, setActiveTabForCurrentSkill],
  );

  const activePanel = useMemo(() => {
    switch (activeTab) {
      case "prompts":
        return prompts.length > 0 ? (
          <div className="space-y-4">
            {prompts.map((prompt) => (
              <PromptCard key={prompt.id} prompt={prompt} onResult={handlePromptResult} />
            ))}
          </div>
        ) : null;
      case "commands":
        return commands.length > 0 ? (
          <div className="space-y-4">
            {commands.map((command) => (
              <CommandCard key={command.id} command={command} onResult={handleCommandResult} />
            ))}
          </div>
        ) : null;
      case "integration":
        return (
          <IntegrationTab
            skillId={skillId}
            skillLabel={skillLabel}
          />
        );
      case "overview":
      default:
        return (
          <div className="space-y-4">
            <div>{overviewContent}</div>
            {capabilityProfileSections.map((section) => (
              <section
                key={section.id}
                className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]/40 p-3"
              >
                <h4 className="text-sm font-semibold text-[var(--text-primary)]">
                  {section.title}
                </h4>
                <div className="mt-2 space-y-2">
                  {section.items.map((item) => (
                    <div
                      key={`${section.id}-${item.label}`}
                      className="rounded-md bg-[var(--bg-card)]/70 p-2"
                    >
                      <div className="text-sm font-medium text-[var(--text-primary)]">
                        {item.label}
                      </div>
                      {item.description ? (
                        <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                          {item.description}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        );
    }
  }, [
    activeTab,
    capabilityProfileSections,
    commands,
    handleCommandResult,
    handlePromptResult,
    overviewContent,
    prompts,
    skillId,
    skillLabel,
  ]);

  return (
    <section className="space-y-4">
      <div
        role="tablist"
        aria-label={`${skillLabel ?? skillId} detail sections`}
        className="flex flex-wrap gap-2"
      >
        {availableTabs.map((tab, index) => {
          const selected = tab.id === activeTab;
          return (
            <Button
              key={tab.id}
              type="button"
              variant="ghost"
              size="sm"
              role="tab"
              aria-selected={selected}
              aria-controls={`skill-detail-tabpanel-${tab.id}`}
              id={`skill-detail-tab-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActiveTabForCurrentSkill(tab.id)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
              className={cn(
                "border text-xs font-medium shadow-none",
                selected
                  ? "border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 text-[var(--text-primary)] hover:bg-[var(--accent-primary)]/15"
                  : "border-[var(--border-color)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:border-[var(--accent-primary)]/30 hover:text-[var(--text-primary)]",
              )}
            >
              {tab.label}
              {typeof tab.count === "number" ? (
                <span className="text-[11px] opacity-70">{tab.count}</span>
              ) : null}
            </Button>
          );
        })}
      </div>

      {availableTabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          aria-labelledby={`skill-detail-tab-${tab.id}`}
          id={`skill-detail-tabpanel-${tab.id}`}
          hidden={tab.id !== activeTab}
          className="min-w-0"
        >
          {tab.id === activeTab ? activePanel : null}
        </div>
      ))}
    </section>
  );
}


