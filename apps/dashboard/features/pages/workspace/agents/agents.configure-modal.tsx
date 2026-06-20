'use client';

import { useReducer } from 'react';
import { toast } from 'sonner';
import { XCircle } from 'lucide-react';
import { mcpCall } from '@/lib/mcp/client';
import { parseAgentCommand } from './agents.helpers';
import {
  type ClientRoutingPreferencesResponse,
  type ConfigureAgentAction,
  type ConfigureAgentModalProps,
  type ConfigureAgentState,
  type UpdatePreferenceResult,
} from './agents.types';

const CONFIGURABLE_CLIENT_OPTIONS = [
  { id: 'claude-code', label: 'Claude Code' },
  { id: 'codex', label: 'Codex' },
  { id: 'gemini', label: 'Gemini CLI' },
  { id: 'opencode', label: 'OpenCode' },
] as const;

const INITIAL_CONFIGURE_AGENT_STATE: ConfigureAgentState = {
  agentId: '',
  command: '',
  model: '',
  isSaving: false,
  saveError: null,
};

function configureAgentReducer(
  state: ConfigureAgentState,
  action: ConfigureAgentAction,
): ConfigureAgentState {
  switch (action.type) {
    case 'set-field':
      return { ...state, [action.field]: action.value };
    case 'save-start':
      return { ...state, isSaving: true, saveError: null };
    case 'save-error':
      return { ...state, isSaving: false, saveError: action.error };
    case 'reset':
      return INITIAL_CONFIGURE_AGENT_STATE;
    default:
      return state;
  }
}

export function ConfigureAgentModal({ isOpen, onClose, onSaved }: ConfigureAgentModalProps) {
  const [{ agentId, command, model, isSaving, saveError }, dispatch] = useReducer(
    configureAgentReducer,
    INITIAL_CONFIGURE_AGENT_STATE,
  );

  if (!isOpen) return null;

  const handleSave = async () => {
    dispatch({ type: 'save-start' });
    try {
      const cmd = parseAgentCommand(command);
      if (cmd.length === 0) {
        throw new Error('Command is required');
      }

      const result = await mcpCall<{ success?: boolean; error?: string }>('manage-cli-agents', {
        action: 'upsert',
        agent_id: agentId.trim(),
        config_data: JSON.stringify({
          cmd,
          cwd: '.',
          env: model.trim() ? { AUGUR_DEFAULT_MODEL: model.trim() } : {},
        }),
      });

      if (result?.success === false) {
        throw new Error(result.error || 'Failed to save agent configuration');
      }

      const routingPrefs = await mcpCall<ClientRoutingPreferencesResponse>('get-preferences', {
        key: 'client_routing',
      });
      const updatePreferenceResult = await mcpCall<UpdatePreferenceResult>('update-preference', {
        key: 'client_routing',
        value: {
          ...(routingPrefs?.client_routing ?? {}),
          default_client: agentId.trim(),
        },
      });
      if (updatePreferenceResult?.success === false) {
        throw new Error(
          updatePreferenceResult.error ||
            updatePreferenceResult.details ||
            updatePreferenceResult.message ||
            'Failed to update client routing preference',
        );
      }

      toast.success(`Saved agent '${agentId.trim()}'`);
      dispatch({ type: 'reset' });
      onSaved();
      onClose();
    } catch (error) {
      dispatch({
        type: 'save-error',
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] p-5 shadow-2xl">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Configure CLI Agent</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Add a local execution path the control center can use and monitor.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg text-[var(--text-muted)] transition-colors hover:text-[var(--text-primary)]"
            aria-label="Close configure agent modal"
          >
            <XCircle className="size-5" aria-hidden="true" />
          </button>
        </div>

        <div className="mt-5 space-y-4">
          <div>
            <label htmlFor="agent-id-input" className="mb-1 block text-xs text-[var(--text-muted)]">
              Client
            </label>
            <select
              id="agent-id-input"
              value={agentId}
              onChange={(event) =>
                dispatch({ type: 'set-field', field: 'agentId', value: event.target.value })
              }
              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-primary)] focus:outline-none"
            >
              <option value="">Choose a client</option>
              {CONFIGURABLE_CLIENT_OPTIONS.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="agent-command-input" className="mb-1 block text-xs text-[var(--text-muted)]">
              Command
            </label>
            <input
              id="agent-command-input"
              value={command}
              onChange={(event) =>
                dispatch({ type: 'set-field', field: 'command', value: event.target.value })
              }
              placeholder="e.g. codex --approval-mode never"
              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-primary)] focus:outline-none"
            />
          </div>
          <div>
            <label htmlFor="agent-model-input" className="mb-1 block text-xs text-[var(--text-muted)]">
              Default model hint
            </label>
            <input
              id="agent-model-input"
              value={model}
              onChange={(event) =>
                dispatch({ type: 'set-field', field: 'model', value: event.target.value })
              }
              placeholder="e.g. gpt-5.4"
              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] focus:border-[var(--accent-primary)] focus:outline-none"
            />
          </div>
        </div>

        {saveError ? (
          <div className="mt-4 rounded-lg border border-[var(--accent-danger)]/25 bg-[var(--accent-danger)]/10 px-3 py-2 text-sm text-[var(--accent-danger)]">
            {saveError}
          </div>
        ) : null}

        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-3 py-2 text-sm text-[var(--text-secondary)] transition-colors hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving || !agentId.trim() || !command.trim()}
            className="rounded-lg bg-[var(--accent-primary)] px-3 py-2 text-sm font-medium text-[var(--accent-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? 'Saving...' : 'Save Agent'}
          </button>
        </div>
      </div>
    </div>
  );
}
