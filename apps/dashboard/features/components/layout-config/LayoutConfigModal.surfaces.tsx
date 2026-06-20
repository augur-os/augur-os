"use client";

import {
  X,
  RotateCcw,
  Layout,
} from "lucide-react";
import type {
  WidgetVisibility,
  Favorites,
  LayoutBlocks,
  ActiveTab,
} from "./types";
import { TabButton, SettingsSection } from "./ui-helpers";
import { AppearanceTab } from "./AppearanceTab";
import {
  FavoritesTabContent,
  SidebarTabContent,
  TabsReorderContent,
} from "./NavigationTab";
import { VisibilityTabContent, SizingTabContent } from "./WorkspaceTab";

import type { LayoutSurfaceProps } from "./LayoutConfigModal.types";

const LAYOUT_FOOTER_RESET_LABELS: Record<string, string> = {
  navigation: "Reset Navigation",
  workspace: "Reset Workspace",
};

// ── Tab content router ──────────────────────────────────────────────────────

export function TabContent({
  activeTab,
  pathname,
  fontFamily,
  onFontFamilyChange,
  fontSize,
  onFontSizeChange,
  favorites,
  onToggleFavorite,
  sidebarVisibility,
  onToggleSidebarVisibility,
  sectionOrder,
  onReorderSections,
  onReorderTabs,
  currentVisibility,
  onToggleWidget,
  layoutBlocks,
  onSetBlock,
  onResetBlock,
  hasWidgets,
  hasBlocks,
}: {
  activeTab: ActiveTab;
  pathname: string;
  fontFamily: string;
  onFontFamilyChange: (family: string) => void;
  fontSize: string;
  onFontSizeChange: (size: string) => void;
  favorites: Favorites;
  onToggleFavorite: (href: string) => void;
  sidebarVisibility: Record<string, boolean>;
  onToggleSidebarVisibility: (href: string, isVisible: boolean) => void;
  sectionOrder: string[];
  onReorderSections: (newOrder: string[]) => void;
  onReorderTabs: (
    hubId: string,
    tabOrder: { pageId: string; order: number }[],
  ) => void;
  currentVisibility: WidgetVisibility;
  onToggleWidget: (widgetId: string) => void;
  layoutBlocks: LayoutBlocks;
  onSetBlock: (
    id: string,
    patch: { width?: string; height?: string | number },
  ) => void;
  onResetBlock: (id: string) => void;
  hasWidgets: boolean;
  hasBlocks: boolean;
}) {
  if (activeTab === "appearance") {
    return (
      <AppearanceTab
        fontFamily={fontFamily}
        onFontFamilyChange={onFontFamilyChange}
        fontSize={fontSize}
        onFontSizeChange={onFontSizeChange}
      />
    );
  }

  if (activeTab === "navigation") {
    return (
      <div className="space-y-4">
        <SettingsSection
          title="Favorites"
          description="Pin high-frequency pages so they are always visible in the sidebar."
        >
          <FavoritesTabContent
            favorites={favorites}
            onToggleFavorite={onToggleFavorite}
          />
        </SettingsSection>
        <SettingsSection
          title="Sidebar Structure"
          description="Reorder top-level sidebar sections and toggle visibility of pages."
        >
          <SidebarTabContent
            sidebarVisibility={sidebarVisibility}
            onToggleVisibility={onToggleSidebarVisibility}
            sectionOrder={sectionOrder}
            onReorderSections={onReorderSections}
          />
        </SettingsSection>
        <SettingsSection
          title="Hub Tabs Order"
          description="Reorder tabs for the current hub. Overview remains pinned first."
        >
          <TabsReorderContent
            pathname={pathname}
            onReorderTabs={onReorderTabs}
          />
        </SettingsSection>
      </div>
    );
  }

  if (!hasWidgets && !hasBlocks) {
    return (
      <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/30 p-5">
        <h3 className="text-sm font-semibold text-[var(--text-primary)]">
          Workspace Controls
        </h3>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          No widget visibility or sizing controls are available for this route.
          Open a hub page with widgets to configure workspace layout options.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {hasWidgets ? (
        <SettingsSection
          title="Widget Visibility"
          description="Show or hide dashboard widgets for the current page."
        >
          <VisibilityTabContent
            pathname={pathname}
            currentVisibility={currentVisibility}
            onToggleWidget={onToggleWidget}
          />
        </SettingsSection>
      ) : null}
      {hasBlocks ? (
        <SettingsSection
          title="Block Sizing"
          description="Adjust per-widget width and height preferences."
        >
          <SizingTabContent
            layoutBlocks={layoutBlocks}
            onSetBlock={onSetBlock}
            onResetBlock={onResetBlock}
          />
        </SettingsSection>
      ) : null}
    </div>
  );
}

// ── Footer ──────────────────────────────────────────────────────────────────

function FooterActions({
  activeTab,
  onResetFavorites,
  onResetSidebar,
  onResetVisibility,
  onResetLayout,
  onClose,
  showDoneButton = true,
}: {
  activeTab: ActiveTab;
  onResetFavorites: () => void;
  onResetSidebar: () => void;
  onResetVisibility: () => void;
  onResetLayout: () => void;
  onClose: () => void;
  showDoneButton?: boolean;
}) {
  const hasReset = activeTab === "navigation" || activeTab === "workspace";

  const handleReset = () => {
    if (activeTab === "navigation") {
      onResetFavorites();
      onResetSidebar();
    }
    if (activeTab === "workspace") {
      onResetVisibility();
      onResetLayout();
    }
  };

  return (
    <div
      className={`px-3 py-2 border-t border-[var(--border-color)] flex items-center ${showDoneButton ? "justify-between" : "justify-start"}`}
    >
      {hasReset ? (
        <button type="button"
          onClick={handleReset}
          className={`flex items-center gap-1.5 px-2 py-1 text-sm rounded-lg transition-colors ${
            activeTab === "workspace"
              ? "text-[var(--accent-danger)] hover:bg-[var(--accent-danger)]/10"
              : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]"
          }`}
        >
          <RotateCcw className="size-3" />
          {LAYOUT_FOOTER_RESET_LABELS[activeTab]}
        </button>
      ) : showDoneButton ? (
        <div />
      ) : null}
      {showDoneButton ? (
        <button type="button"
          onClick={onClose}
          className="px-3 py-1 text-sm font-semibold bg-[var(--accent-primary)] hover:opacity-90 text-[var(--accent-foreground)] rounded-lg transition-colors"
        >
          Close settings
        </button>
      ) : null}
    </div>
  );
}

export function EmbeddedLayoutSettings({
  availableTabs,
  effectiveTab,
  activeTabMeta,
  tabContentNode,
  onSelectTab,
  onResetFavorites,
  onResetSidebar,
  onResetVisibility,
  onResetLayout,
  onClose,
}: LayoutSurfaceProps) {
  return (
    <div className="relative">
      <div className="relative w-full overflow-hidden rounded-2xl border border-[var(--border-color)] bg-[var(--bg-card)] shadow-[0_20px_60px_-40px_rgba(0,0,0,0.65)]">
        <div className="grid lg:grid-cols-[250px_minmax(0,1fr)]">
          <aside className="border-b border-[var(--border-color)] bg-[var(--bg-secondary)]/40 p-5 lg:border-b-0 lg:border-r">
            <div className="mb-5 flex items-start gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg border border-[var(--accent-primary)]/20 bg-[var(--accent-primary)]/10">
                <Layout className="size-5 text-[var(--accent-primary)]" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  Layout Settings
                </h2>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  Configure page structure by intent.
                </p>
              </div>
            </div>

            <nav className="space-y-1.5">
              {availableTabs.map((tab) => {
                const selected = tab.id === effectiveTab;
                return (
                  <button type="button"
                    key={tab.id}
                    onClick={() => onSelectTab(tab.id)}
                    className={`w-full rounded-xl border px-3 py-2 text-left transition-colors ${
                      selected
                        ? "border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10"
                        : "border-[var(--border-color)] hover:bg-[var(--bg-hover)]"
                    }`}
                  >
                    <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-primary)]">
                      {tab.icon}
                      {tab.label}
                    </div>
                    <p className="mt-1 text-xs text-[var(--text-secondary)]">
                      {tab.description}
                    </p>
                  </button>
                );
              })}
            </nav>
          </aside>

          <section className="min-w-0">
            <header className="border-b border-[var(--border-color)] px-6 py-5">
              <h3 className="text-lg font-semibold text-[var(--text-primary)]">
                {activeTabMeta?.label}
              </h3>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                {activeTabMeta?.description}
              </p>
            </header>

            <div className="p-6 md:p-7">{tabContentNode}</div>

            <FooterActions
              activeTab={effectiveTab}
              onResetFavorites={onResetFavorites}
              onResetSidebar={onResetSidebar}
              onResetVisibility={onResetVisibility}
              onResetLayout={onResetLayout}
              onClose={onClose}
              showDoneButton={false}
            />
          </section>
        </div>
      </div>
    </div>
  );
}

export function DialogLayoutSettings({
  availableTabs,
  effectiveTab,
  tabContentNode,
  onSelectTab,
  onResetFavorites,
  onResetSidebar,
  onResetVisibility,
  onResetLayout,
  onClose,
}: LayoutSurfaceProps) {
  return (
    <dialog
      open
      className="fixed inset-0 z-50 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center border-0 bg-transparent p-0 text-inherit"
      aria-label="Layout settings"
      onCancel={(e) => { e.preventDefault(); onClose(); }}
    >
      <button
        type="button"
        aria-label="Close layout settings"
        className="absolute inset-0 border-0 bg-black/15 p-0 backdrop-blur-[2px] animate-in fade-in duration-150"
        onClick={onClose}
      />
      <div
        className="relative mx-4 w-full max-w-sm overflow-hidden rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] shadow-2xl backdrop-blur-xl animate-in fade-in zoom-in-95 duration-200"
      >
        <div className="flex items-start justify-between border-b border-[var(--border-color)] px-3 py-2">
          <div className="flex items-start gap-3">
            <div className="flex size-7 items-center justify-center rounded-lg border border-[var(--accent-primary)]/20 bg-[var(--accent-primary)]/10">
              <Layout className="size-3.5 text-[var(--accent-primary)]" />
            </div>
            <div>
              <h2 className="text-xs font-semibold uppercase tracking-wider text-[var(--text-primary)]">
                Layout Settings
              </h2>
            </div>
          </div>
          <button type="button"
            onClick={onClose}
            className="rounded-md p-1.5 transition-colors hover:bg-[var(--bg-hover)]"
            aria-label="Close layout settings"
          >
            <X className="size-3.5 text-[var(--text-muted)]" aria-hidden="true" />
          </button>
        </div>

        <div className="flex gap-1 overflow-x-auto border-b border-[var(--border-color)] px-3 py-1.5">
          {availableTabs.map((t) => (
            <TabButton
              key={t.id}
              tab={t.id}
              activeTab={effectiveTab}
              label={t.label}
              icon={t.icon}
              onSelect={onSelectTab}
            />
          ))}
        </div>

        <div className="max-h-[60vh] overflow-y-auto p-2">{tabContentNode}</div>

        <FooterActions
          activeTab={effectiveTab}
          onResetFavorites={onResetFavorites}
          onResetSidebar={onResetSidebar}
          onResetVisibility={onResetVisibility}
          onResetLayout={onResetLayout}
          onClose={onClose}
          showDoneButton
        />
      </div>
    </dialog>
  );
}
