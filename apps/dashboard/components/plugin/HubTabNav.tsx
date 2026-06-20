'use client';

import { useState, useEffect } from 'react';
import { pluginTabRegistry } from '@/lib/tabs/generated-registry';
import type { HubConfig } from '@/lib/tabs/types';
import { useModeStore } from '@/lib/stores/modeStore';
import { HubTabBar } from '@/components/HubTabBar';
import { UserBlocksSection } from './UserBlocksSection';
// eslint-disable-next-line no-restricted-imports -- ADR-490 plugin shell exception for tab customization UI
import TabCustomizePanel from '@/features/components/TabCustomizePanel';

/**
 * Custom event dispatched after tab customization saves.
 * Carries the updated HubConfig so HubTabNav can update without reload.
 */
const TAB_CONFIG_UPDATED_EVENT = 'augur:tab-config-updated';

export function HubTabNav({ hubId }: { hubId: string }) {
  const registryConfig = pluginTabRegistry[hubId];
  const [overrideConfig, setOverrideConfig] = useState<HubConfig | null>(null);
  const [customizeOpen, setCustomizeOpen] = useState(false);
  const { mode } = useModeStore();

  // Listen for tab config updates from the customize panel
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.hubId === hubId && detail?.hubConfig) {
        setOverrideConfig(detail.hubConfig);
      }
    };
    window.addEventListener(TAB_CONFIG_UPDATED_EVENT, handler);
    return () => window.removeEventListener(TAB_CONFIG_UPDATED_EVENT, handler);
  }, [hubId]);

  const config = overrideConfig || registryConfig;
  if (!config) return null;

  const isBuilderMode = mode === 'development';
  const maxTabs = (config.tabs?.length ?? 0) + (config.overflow?.length ?? 0);

  return (
    <div className="space-y-6">
      <header className="page-header relative">
        <div className="space-y-1">
          <h1 className="page-title">{config.title || hubId}</h1>
          {config.subtitle && (
            <p className="page-subtitle">{config.subtitle}</p>
          )}
        </div>
        <div className="absolute -bottom-3 left-0 right-0 h-px bg-gradient-to-r from-[var(--accent-primary)]/30 via-[var(--border-color)] to-transparent" />
      </header>
      <HubTabBar
        tabs={config.tabs || []}
        overflow={config.overflow}
        blocks={config.blocks}
        autoPages={config.autoPages}
        configPages={config.configPages}
        basePath={config.basePath}
        hubId={hubId}
        tabCustomizeLabel={
          isBuilderMode ? `Customize ${config.title || hubId} tabs` : undefined
        }
        tabCustomizeOpen={customizeOpen}
        onOpenTabCustomize={() => setCustomizeOpen(true)}
        onCloseTabCustomize={() => setCustomizeOpen(false)}
        tabCustomizePanel={
          isBuilderMode && customizeOpen ? (
            <TabCustomizePanel
              hubId={hubId}
              hubConfig={config}
              maxTabs={maxTabs}
              onClose={() => setCustomizeOpen(false)}
              onSave={(updatedConfig: HubConfig) => {
                setOverrideConfig(updatedConfig);
                window.dispatchEvent(
                  new CustomEvent(TAB_CONFIG_UPDATED_EVENT, {
                    detail: { hubId, hubConfig: updatedConfig },
                  }),
                );
                setCustomizeOpen(false);
              }}
            />
          ) : undefined
        }
      />
      <UserBlocksSection hubId={hubId} />
    </div>
  );
}
