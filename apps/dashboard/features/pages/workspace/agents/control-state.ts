export interface RegistryAgent {
  id: string;
  role?: string;
  defaultModel?: string;
  source?: 'project' | 'plugin' | string;
  plugin?: string | null;
  tiers?: string[];
  hasMcpServers?: boolean;
  hasIsolation?: boolean;
}

export interface AgentRegistryResponse {
  schema?: string;
  agents?: RegistryAgent[];
  total?: number;
  by_source?: {
    project?: number;
    plugin?: number;
  };
  sync_status?: Record<string, number>;
}

export interface SyncClientStatus {
  status?: 'healthy' | 'issues' | 'not_installed' | 'unknown' | string;
  synced_skills?: string[];
  last_sync?: string | null;
  issues?: string[];
}

export interface SyncStatusResponse {
  success?: boolean;
  clients?: Record<string, SyncClientStatus>;
}

export interface RemoteProvider {
  id: string;
  name?: string;
  enabled?: boolean;
  hasApiKey?: boolean;
  apiKey?: string;
  api_key?: string;
  defaultModel?: string;
  config?: {
    enabled?: boolean;
    hasApiKey?: boolean;
    defaultModel?: string;
  };
}

export interface RemoteProvidersResponse {
  providers?: RemoteProvider[];
}

export interface DefaultCliResponse {
  default_cli?: string;
}

export interface LocalBackendStatusResponse {
  ollama?: {
    ready?: boolean;
    installed?: boolean;
    server_running?: boolean;
    configured_model?: string;
  };
}

export interface ControlStateInput {
  registry?: AgentRegistryResponse | null;
  syncStatus?: SyncStatusResponse | null;
  remoteProviders?: RemoteProvidersResponse | null;
  defaultCli?: DefaultCliResponse | null;
  localBackend?: LocalBackendStatusResponse | null;
}

export interface ControlAttentionItem {
  id: string;
  level: 'setup-required' | 'degraded' | 'offline';
  source: 'provider' | 'client' | 'system';
  sourceId: string;
  title: string;
  detail: string;
}

export interface ControlCta {
  action:
    | 'open-provider-settings'
    | 'open-sync-status'
    | 'run-agent-tests'
    | 'run-provider-test'
    | 'check-local-backend'
    | 'configure-agent';
  label: string;
  detail: string;
  targetId?: string;
}

export interface ExecutionSummary {
  currentPath: 'local' | 'api' | 'none';
  status: 'healthy' | 'degraded' | 'offline';
  summary: string;
  detail: string;
}

export interface ExecutionPathStatus {
  id: 'local' | 'api';
  label: string;
  status: 'healthy' | 'degraded' | 'offline' | 'setup-required';
  summary: string;
  total: number;
  ready: number;
}

export interface ControlState {
  execution: ExecutionSummary;
  dispatch: {
    defaultClientId: string | null;
    defaultClientStatus: 'healthy' | 'issues' | 'not_installed' | 'unknown' | 'unconfigured' | 'api';
    summary: string;
    detail: string;
  };
  paths: ExecutionPathStatus[];
  attention: ControlAttentionItem[];
  primaryCta: ControlCta;
  stats: {
    registeredAgents: number;
    projectAgents: number;
    pluginAgents: number;
  };
  clients: Array<{
    id: string;
    status: 'healthy' | 'issues' | 'not_installed' | 'unknown';
    issues: string[];
    syncedSkills: number;
    lastSync: string | null;
  }>;
  providers: Array<{
    id: string;
    name: string;
    enabled: boolean;
    hasApiKey: boolean;
    defaultModel: string;
    status: 'ready' | 'setup-required' | 'disabled';
  }>;
}

function pluralize(count: number, singular: string, plural: string): string {
  return count === 1 ? singular : plural;
}

export function deriveControlState(input: ControlStateInput): ControlState {
  const registryAgents = input.registry?.agents ?? [];
  const providersRaw = input.remoteProviders?.providers ?? [];
  const syncClientsRaw = input.syncStatus?.clients ?? {};
  const configuredDefaultCli = input.defaultCli?.default_cli?.trim() || '';
  const ollamaReady = input.localBackend?.ollama?.ready === true;
  const ollamaConfiguredModel = input.localBackend?.ollama?.configured_model ?? '';

  const providers = providersRaw.map((provider) => {
    const enabled = provider.enabled ?? provider.config?.enabled ?? false;
    const hasApiKey = Boolean(provider.hasApiKey ?? provider.config?.hasApiKey ?? provider.apiKey ?? provider.api_key);
    const status = !enabled ? 'disabled' : hasApiKey ? 'ready' : 'setup-required';
    return {
      id: provider.id,
      name: provider.name ?? provider.id,
      enabled,
      hasApiKey,
      defaultModel: provider.defaultModel ?? provider.config?.defaultModel ?? '',
      status,
    } as const;
  });

  const clients: ControlState['clients'] = Object.entries(syncClientsRaw).map(([id, value]) => {
    const rawStatus = value?.status;
    const normalizedStatus =
      rawStatus === 'healthy' || rawStatus === 'issues' || rawStatus === 'not_installed'
        ? rawStatus
        : 'unknown';
    return {
      id,
      status: normalizedStatus,
      issues: value?.issues ?? [],
      syncedSkills: value?.synced_skills?.length ?? 0,
      lastSync: value?.last_sync ?? null,
    };
  });

  const localClientTotal = clients.length;
  const localHealthyClients = clients.filter((client) => client.status === 'healthy').length;
  const localIssueCount = clients.filter((client) => client.status === 'issues').length;
  const localOfflineCount = clients.filter((client) => client.status === 'not_installed').length;
  const localTotal = localClientTotal + (input.localBackend?.ollama ? 1 : 0);
  const localHealthy = localHealthyClients + (ollamaReady ? 1 : 0);

  const apiTotal = providers.filter((provider) => provider.enabled).length;
  const apiReady = providers.filter((provider) => provider.status === 'ready').length;
  const apiSetupRequired = providers.filter((provider) => provider.status === 'setup-required').length;
  const readyApiProviderId = providers.find((provider) => provider.status === 'ready')?.id;

  const attention: ControlAttentionItem[] = [];

  for (const provider of providers) {
    if (provider.status === 'setup-required') {
      attention.push({
        id: `provider-${provider.id}-setup`,
        level: 'setup-required',
        source: 'provider',
        sourceId: provider.id,
        title: `${provider.id} requires setup`,
        detail: 'Provider is enabled but API key is missing.',
      });
    }
  }

  for (const client of clients) {
    if (client.status === 'issues') {
      attention.push({
        id: `client-${client.id}-degraded`,
        level: 'degraded',
        source: 'client',
        sourceId: client.id,
        title: `${client.id} sync has issues`,
        detail: client.issues[0] ?? 'Client sync reports issues and needs repair.',
      });
      continue;
    }
    if (client.status === 'not_installed' && configuredDefaultCli === client.id) {
      attention.push({
        id: `client-${client.id}-offline`,
        level: 'offline',
        source: 'client',
        sourceId: client.id,
        title: `${client.id} is offline`,
        detail: 'Client is not installed or has no synced agents.',
      });
    }
  }

  let execution: ExecutionSummary;
  if (localHealthy > 0) {
    execution = {
      currentPath: 'local',
      status: 'healthy',
      summary: `${localHealthy} ${pluralize(localHealthy, 'local path', 'local paths')} ready`,
      detail: 'Local execution is available through synced clients or the local backend.',
    };
  } else if (apiReady > 0) {
    execution = {
      currentPath: 'api',
      status: 'healthy',
      summary: `${apiReady} ${pluralize(apiReady, 'API provider', 'API providers')} ready`,
      detail: 'Remote execution is available through configured providers.',
    };
  } else if (apiSetupRequired > 0 || localIssueCount > 0) {
    execution = {
      currentPath: 'none',
      status: 'degraded',
      summary: 'Execution requires setup or repair',
      detail: 'Fix provider keys and client sync issues to restore execution.',
    };
  } else {
    execution = {
      currentPath: 'none',
      status: 'offline',
      summary: 'No execution paths available',
      detail: 'Configure a local client or API provider to enable agent execution.',
    };
  }

  const localPathStatus: ExecutionPathStatus = {
    id: 'local',
    label: 'Local routes',
    status:
      localHealthy > 0
        ? 'healthy'
        : localIssueCount > 0
          ? 'degraded'
          : localOfflineCount > 0 || localTotal === 0
            ? 'offline'
            : 'offline',
    summary: `${localHealthy}/${localTotal} healthy`,
    total: localTotal,
    ready: localHealthy,
  };

  const apiPathStatus: ExecutionPathStatus = {
    id: 'api',
    label: 'API providers',
    status:
      apiReady > 0
        ? 'healthy'
        : apiSetupRequired > 0
          ? 'setup-required'
          : apiTotal > 0
            ? 'offline'
            : 'offline',
    summary: `${apiReady}/${apiTotal} configured`,
    total: apiTotal,
    ready: apiReady,
  };

  const defaultClient = configuredDefaultCli
    ? clients.find((client) => client.id === configuredDefaultCli) ?? null
    : null;
  const defaultClientRegistryEntry = configuredDefaultCli
    ? registryAgents.find((agent) => agent.id === configuredDefaultCli) ?? null
    : null;
  const defaultClientLabel = defaultClientRegistryEntry?.id ?? configuredDefaultCli;

  let dispatch: ControlState['dispatch'];
  if (configuredDefaultCli === 'ollama') {
    dispatch = {
      defaultClientId: 'ollama',
      defaultClientStatus: ollamaReady ? 'healthy' : 'unknown',
      summary: 'Default dispatch target: ollama',
      detail: ollamaReady
        ? `Actions routed locally will use Ollama${ollamaConfiguredModel ? ` with ${ollamaConfiguredModel}` : ''}.`
        : 'Ollama is the configured default client, but the local backend is not ready yet.',
    };
  } else if (defaultClient) {
    dispatch = {
      defaultClientId: defaultClient.id,
      defaultClientStatus: defaultClient.status,
      summary: `Default dispatch target: ${defaultClientLabel}`,
      detail:
        defaultClient.status === 'healthy'
          ? `IDE-dispatched actions will use ${defaultClientLabel} first.`
          : defaultClient.status === 'issues'
            ? `${defaultClientLabel} is the configured default, but sync issues may block local execution until it is repaired.`
            : `${defaultClientLabel} is the configured default, but it is not currently available for local execution.`,
    };
  } else if (configuredDefaultCli) {
    dispatch = {
      defaultClientId: configuredDefaultCli,
      defaultClientStatus: 'unknown',
      summary: `Default dispatch target: ${configuredDefaultCli}`,
      detail: `${configuredDefaultCli} is configured as the default client, but it is not reporting sync status yet.`,
    };
  } else if (apiReady > 0) {
    dispatch = {
      defaultClientId: null,
      defaultClientStatus: 'unknown',
      summary: 'Default dispatch target: implicit IDE route',
      detail: 'No explicit default client is configured, so Augur falls back to the implicit IDE route. API providers remain available but are not the default dispatch target.',
    };
  } else {
    dispatch = {
      defaultClientId: null,
      defaultClientStatus: 'unknown',
      summary: 'Default dispatch target: implicit IDE route',
      detail: 'No explicit default client is configured, so Augur falls back to the implicit IDE route. Set a default client if you want deterministic dispatch behavior.',
    };
  };

  const needsDefaultClientRepair =
    configuredDefaultCli.length > 0 &&
    configuredDefaultCli !== 'ollama' &&
    (!defaultClient || defaultClient.status === 'not_installed' || defaultClient.status === 'unknown');

  let primaryCta: ControlCta;
  if (apiSetupRequired > 0) {
    primaryCta = {
      action: 'open-provider-settings',
      label: 'Configure Provider Keys',
      detail: 'Set API keys for enabled providers to unlock API execution.',
    };
  } else if (configuredDefaultCli === 'ollama' && !ollamaReady) {
    primaryCta = {
      action: 'check-local-backend',
      label: 'Repair Local Backend',
      detail: 'Start Ollama and install the configured model to restore the local dispatch path.',
    };
  } else if (localIssueCount > 0 || needsDefaultClientRepair) {
    primaryCta = {
      action: 'open-sync-status',
      label: 'Repair Client Sync',
      detail: 'Review client sync status and resolve degraded or offline clients.',
    };
  } else if (configuredDefaultCli === 'ollama' && ollamaReady) {
    primaryCta = {
      action: 'check-local-backend',
      label: 'Verify Local Backend',
      detail: 'Confirm the configured Ollama backend is still ready for local execution.',
    };
  } else if (localHealthyClients > 0) {
    primaryCta = {
      action: 'run-agent-tests',
      label: 'Run Execution Test',
      detail: 'Verify that currently available execution paths are healthy.',
    };
  } else if (apiReady > 0) {
    primaryCta = {
      action: 'run-provider-test',
      label: 'Check Provider Config',
      detail: 'Confirm that the active API provider is configured and available for remote execution.',
      targetId: readyApiProviderId,
    };
  } else {
    primaryCta = {
      action: 'configure-agent',
      label: 'Configure First Agent',
      detail: 'Add a local CLI agent to initialize execution paths.',
    };
  }

  return {
    execution,
    dispatch,
    paths: [localPathStatus, apiPathStatus],
    attention,
    primaryCta,
    stats: {
      registeredAgents: input.registry?.total ?? registryAgents.length,
      projectAgents:
        input.registry?.by_source?.project ??
        registryAgents.filter((agent) => agent.source === 'project').length,
      pluginAgents:
        input.registry?.by_source?.plugin ??
        registryAgents.filter((agent) => agent.source === 'plugin').length,
    },
    clients: clients.sort((a, b) => a.id.localeCompare(b.id)),
    providers: providers.sort((a, b) => a.id.localeCompare(b.id)),
  };
}
