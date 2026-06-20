'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { mcpCall } from '@/lib/mcp/client';
import { useMcpPoll } from '@/lib/mcp/useMcpPoll';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import {
  deriveControlState,
  type AgentRegistryResponse,
  type SyncStatusResponse,
  type RemoteProvidersResponse,
  type DefaultCliResponse,
  type LocalBackendStatusResponse,
  type ControlCta,
} from './control-state';
import { type ClientRoutingPreferencesResponse } from './agents.types';
import { runPrimaryAction } from './agents.helpers';
import { AgentsControlView } from './agents.control-view';

const REFRESH_INTERVAL_MS = 60000;

export default function AgentsPage() {
  const router = useRouter();
  const clientsSectionRef = useRef<HTMLDivElement | null>(null);
  const [isConfigureOpen, setIsConfigureOpen] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isRunningTests, setIsRunningTests] = useState(false);

  const registryQuery = useMcpPoll<AgentRegistryResponse>(
    ['ai', 'agent-registry'],
    'agent-registry',
    REFRESH_INTERVAL_MS,
    { preset: 'device' },
  );

  const syncStatusQuery = useMcpPoll<SyncStatusResponse>(
    ['ai', 'sync-status'],
    'get-sync-status',
    REFRESH_INTERVAL_MS,
    { preset: 'device' },
  );

  const providersQuery = useMcpQuery<RemoteProvidersResponse>(
    ['ai', 'remote-providers'],
    'get-settings',
    'config',
    { args: { scope: 'remote-providers' } },
  );

  const defaultCliQuery = useMcpQuery<DefaultCliResponse>(
    ['ai', 'client-routing-default'],
    'get-preferences',
    'config',
    {
      args: { key: 'client_routing' },
      select: (raw) => ({
        default_cli: (raw as ClientRoutingPreferencesResponse)?.client_routing?.default_client ?? '',
      }),
    },
  );

  const localBackendQuery = useMcpQuery<LocalBackendStatusResponse>(
    ['ai', 'local-backend-status'],
    'get-local-backend-status',
    'config',
  );

  const controlState = useMemo(
    () =>
      deriveControlState({
        registry: registryQuery.data,
        syncStatus: syncStatusQuery.data,
        remoteProviders: providersQuery.data,
        defaultCli: defaultCliQuery.data,
        localBackend: localBackendQuery.data,
      }),
    [defaultCliQuery.data, localBackendQuery.data, providersQuery.data, registryQuery.data, syncStatusQuery.data],
  );
  const registryCoverage = useMemo(() => {
    const agents = registryQuery.data?.agents ?? [];
    return {
      mcpCapable: agents.filter((agent) => agent.hasMcpServers).length,
      isolated: agents.filter((agent) => agent.hasIsolation).length,
      roles: Array.from(
        new Set(agents.flatMap((agent) => (agent.role ? [agent.role] : []))),
      ).slice(0, 4),
    };
  }, [registryQuery.data?.agents]);

  useEffect(() => {
    if (registryQuery.data || syncStatusQuery.data || providersQuery.data || defaultCliQuery.data || localBackendQuery.data) {
      const timer = window.setTimeout(() => {
        setLastUpdated(new Date());
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [defaultCliQuery.data, localBackendQuery.data, providersQuery.data, registryQuery.data, syncStatusQuery.data]);

  const isLoading =
    registryQuery.loading || syncStatusQuery.loading || providersQuery.loading || defaultCliQuery.loading || localBackendQuery.loading;
  const runCheckLabel =
    controlState.primaryCta.action === 'run-provider-test'
      ? 'Check Provider Config'
      : controlState.primaryCta.action === 'check-local-backend'
        ? controlState.primaryCta.label
        : 'Run Test';
  const primaryRunsCheck =
    controlState.primaryCta.action === 'run-provider-test' ||
    controlState.primaryCta.action === 'check-local-backend' ||
    controlState.primaryCta.action === 'run-agent-tests';
  const localPath = controlState.paths.find((path) => path.id === 'local');
  const apiPath = controlState.paths.find((path) => path.id === 'api');
  const firstFix = controlState.attention[0] ?? null;

  const handleRefresh = () => {
    registryQuery.refetch();
    syncStatusQuery.refetch();
    providersQuery.refetch();
    defaultCliQuery.refetch();
    localBackendQuery.refetch();
  };

  const handleRunCheck = async (cta: ControlCta = controlState.primaryCta) => {
    setIsRunningTests(true);
    try {
      if (cta.action === 'run-provider-test') {
        if (!cta.targetId) {
          throw new Error('No ready provider available to test');
        }
        const result = await mcpCall<{ success?: boolean; error?: string }>('set-config', {
          scope: 'remote-provider-test',
          providerId: cta.targetId,
        });
        if (result?.success === false) {
          throw new Error(result.error || 'Failed to run provider test');
        }
        toast.success(`Provider config looks valid for ${cta.targetId}`);
      } else if (cta.action === 'check-local-backend') {
        const result = await mcpCall<LocalBackendStatusResponse>('get-local-backend-status', {});
        if (!result?.ollama?.ready) {
          throw new Error('Local backend is not ready');
        }
        toast.success('Local backend is ready');
      } else {
        const result = await mcpCall<{ success?: boolean; error?: string }>('client-test', {
          agent: 'all',
          level: 4,
        });
        if (result?.success === false) {
          throw new Error(result.error || 'Failed to run execution test');
        }
        toast.success('Execution test completed');
      }
      handleRefresh();
    } catch (runError) {
      toast.error(runError instanceof Error ? runError.message : 'Failed to run path check');
    } finally {
      setIsRunningTests(false);
    }
  };
  const handlePrimaryAction = () => {
    runPrimaryAction(controlState.primaryCta, {
      router,
      onOpenConfigure: () => setIsConfigureOpen(true),
      onRunCheck: handleRunCheck,
      clientsSection: clientsSectionRef.current,
    });
  };

  return (
    <AgentsControlView
      apiPath={apiPath}
      clientsSectionRef={clientsSectionRef}
      controlState={controlState}
      firstFix={firstFix}
      isConfigureOpen={isConfigureOpen}
      isLoading={isLoading}
      isRunningTests={isRunningTests}
      lastUpdated={lastUpdated}
      localPath={localPath}
      onConfigureClose={() => setIsConfigureOpen(false)}
      onConfigureSaved={handleRefresh}
      onPrimaryAction={handlePrimaryAction}
      onRefresh={handleRefresh}
      onRunCheck={handleRunCheck}
      primaryRunsCheck={primaryRunsCheck}
      registryAgents={registryQuery.data?.agents ?? []}
      registryCoverage={registryCoverage}
      runCheckLabel={runCheckLabel}
    />
  );
}
