import { deriveControlState } from '@/features/pages/workspace/agents/control-state';

describe('deriveControlState', () => {
  it('marks enabled API providers without keys as setup-required attention', () => {
    const state = deriveControlState({
      registry: {
        schema: '2.0',
        agents: [
          {
            id: 'codex',
            role: 'executor',
            source: 'project',
            defaultModel: 'gpt-5',
          },
        ],
        total: 1,
      },
      syncStatus: {
        success: true,
        clients: {
          codex: {
            status: 'healthy',
            issues: [],
            synced_skills: ['ai'],
          },
        },
      },
      remoteProviders: {
        providers: [
          {
            id: 'openai',
            name: 'OpenAI',
            enabled: true,
            defaultModel: 'gpt-5',
          },
          {
            id: 'anthropic',
            name: 'Anthropic',
            enabled: true,
            api_key: 'anthropic-secret',
            defaultModel: 'claude-sonnet-4-5',
          },
        ],
      },
    });

    expect(state.attention.some((item) => item.level === 'setup-required' && item.sourceId === 'openai')).toBe(true);
    expect(state.primaryCta.action).toBe('open-provider-settings');
  });

  it('prefers healthy local execution as the current execution summary', () => {
    const state = deriveControlState({
      registry: {
        schema: '2.0',
        agents: [
          {
            id: 'codex',
            role: 'executor',
            source: 'project',
            defaultModel: 'gpt-5',
          },
          {
            id: 'claude-code',
            role: 'executor',
            source: 'plugin',
            defaultModel: 'sonnet',
          },
        ],
        total: 2,
      },
      syncStatus: {
        success: true,
        clients: {
          'claude-code': {
            status: 'healthy',
            issues: [],
            synced_skills: ['ai', 'brain'],
          },
          codex: {
            status: 'issues',
            issues: ['Stale symlink: old-agent.md'],
            synced_skills: ['ai'],
          },
        },
      },
      defaultCli: {
        default_cli: 'claude-code',
      },
      remoteProviders: {
        providers: [
          {
            id: 'openai',
            name: 'OpenAI',
            enabled: true,
            apiKey: 'sk-live',
            defaultModel: 'gpt-5',
          },
        ],
      },
    });

    expect(state.execution.currentPath).toBe('local');
    expect(state.execution.status).toBe('healthy');
    expect(state.execution.summary.toLowerCase()).toContain('local');
    expect(state.dispatch.defaultClientId).toBe('claude-code');
    expect(state.dispatch.summary).toContain('claude-code');
  });

  it('keeps first-agent setup reachable when all discovered clients are not installed', () => {
    const state = deriveControlState({
      syncStatus: {
        success: true,
        clients: {
          codex: {
            status: 'not_installed',
            issues: [],
            synced_skills: [],
          },
          claude: {
            status: 'not_installed',
            issues: [],
            synced_skills: [],
          },
        },
      },
      remoteProviders: {
        providers: [],
      },
      defaultCli: {
        default_cli: '',
      },
    });

    expect(state.primaryCta.action).toBe('configure-agent');
    expect(state.attention).toHaveLength(0);
  });

  it('treats ollama as a real local dispatch route when it is the configured default', () => {
    const state = deriveControlState({
      defaultCli: {
        default_cli: 'ollama',
      },
      localBackend: {
        ollama: {
          ready: true,
          configured_model: 'qwen3.5:9b',
        },
      },
      syncStatus: {
        success: true,
        clients: {},
      },
      remoteProviders: {
        providers: [],
      },
    });

    expect(state.execution.currentPath).toBe('local');
    expect(state.dispatch.defaultClientId).toBe('ollama');
    expect(state.primaryCta.action).toBe('check-local-backend');
  });

  it('describes the implicit IDE fallback when API providers are ready but no default client is configured', () => {
    const state = deriveControlState({
      syncStatus: {
        success: true,
        clients: {},
      },
      remoteProviders: {
        providers: [
          {
            id: 'openai',
            enabled: true,
            apiKey: 'sk-live',
            defaultModel: 'gpt-5.4',
          },
        ],
      },
      defaultCli: {
        default_cli: '',
      },
    });

    expect(state.execution.currentPath).toBe('api');
    expect(state.dispatch.summary).toContain('implicit IDE');
    expect(state.primaryCta.action).toBe('run-provider-test');
    expect(state.primaryCta.targetId).toBe('openai');
  });

  it('describes the implicit IDE fallback when local clients are healthy but no default client is configured', () => {
    const state = deriveControlState({
      syncStatus: {
        success: true,
        clients: {
          codex: {
            status: 'healthy',
            issues: [],
            synced_skills: ['ai'],
          },
        },
      },
      defaultCli: {
        default_cli: '',
      },
    });

    expect(state.execution.currentPath).toBe('local');
    expect(state.dispatch.summary).toContain('implicit IDE');
    expect(state.primaryCta.action).toBe('run-agent-tests');
  });
});
