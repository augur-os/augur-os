'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { GlassCard } from '@/components/ui/GlassCard';
import { useChatStore } from '@/lib/stores/chatStore';
import { mcpCall } from '@/lib/mcp/client';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import type { PreparedActionDispatch } from '@/lib/actions/preparedActionDraft';

interface Action {
  id: string;
  label: string;
  icon?: string;
  description?: string;
  dispatch?: string;
  page?: string;
  prompt?: string;
  command?: string;
  args?: Record<string, unknown>;
  mcp_tools?: string[];
  recommended_agent?: string;
}

interface ActionButtonsProps {
  actions?: Action[];
  hub?: string;
  maxButtons?: number;
}

const DEFAULT_ACTIONS: Action[] = [
  { id: 'action-1', label: 'Action 1', icon: '⚡' },
  { id: 'action-2', label: 'Action 2', icon: '📋' },
  { id: 'action-3', label: 'Action 3', icon: '🔍' },
];

const ICON_FALLBACK: Record<string, string> = {
  fire: '🔥',
  oneshot: '⚡',
  ide: '💻',
  chat: '💬',
  modal: '📋',
};

export default function ActionButtons({ actions, hub, maxButtons = 8 }: ActionButtonsProps) {
  const router = useRouter();
  const chatStore = useChatStore();
  const [runningActionId, setRunningActionId] = useState<string | null>(null);

  const { data: fetched, loading } = useMcpQuery<Action[]>(
    ['action-buttons', hub ?? ''],
    'list-skills',
    'config',
    {
      enabled: !!hub,
      args: hub ? { page: hub } : undefined,
      select: (raw: unknown) => {
        const data = raw as { buttons?: Array<{ id: string; label: string; icon?: string; description?: string; dispatch?: string; page?: string; prompt?: string; args?: Record<string, unknown>; mcp_tools?: string[]; recommended_agent?: string }> };
        const buttons = Array.isArray(data.buttons) ? data.buttons : [];
        return buttons.map((b) => ({
          id: b.id,
          label: b.label,
          icon: b.icon || ICON_FALLBACK[b.dispatch || ''] || '⚡',
          description: b.description,
          dispatch: b.dispatch,
          page: b.page,
          prompt: b.prompt,
          args: b.args,
          mcp_tools: b.mcp_tools,
          recommended_agent: b.recommended_agent,
        }));
      },
    },
  );

  const displayActions = (hub ? (fetched ?? []) : actions ?? DEFAULT_ACTIONS).slice(0, maxButtons);

  function buildPrompt(action: Action): string {
    if (action.prompt) return action.prompt;
    if (action.command) return action.command;
    return `**Action Request**: ${action.label}

## Context
- Description: ${action.description || 'No description provided'}
- Page: ${window.location.pathname}
`;
  }

  function currentHub(): string {
    return hub || window.location.pathname.split('/').filter(Boolean)[0] || 'dashboard';
  }

  function openPreparedActionDraft(action: Action, dispatch: PreparedActionDispatch): void {
    const prompt = buildPrompt(action);
    const pathname = window.location.pathname;
    const activeHub = currentHub();

    chatStore.openChatWithPreparedActionDraft(
      {
        id: action.id,
        label: action.label,
        description: action.description,
        prompt,
        page: action.page || hub || activeHub,
        tier: 'standard',
        dispatch,
        recommendedAgent: action.recommended_agent,
        createdAt: new Date().toISOString(),
      },
      {
        page: pathname,
        actionId: action.id,
        actionName: action.label,
        hub: activeHub,
      },
    );
    if (!chatStore.isEnlarged) {
      chatStore.toggleEnlarged();
    }
  }

  async function runFireAction(action: Action): Promise<void> {
    const pageContext = window.location.pathname;
    const activeHub = currentHub();
    const context = {
      page: pageContext,
      hub: activeHub,
      tier: 'standard',
    };
    // A fire action must declare an mcp_tool (ADR-807). The script-lookup
    // fallback (execute-fast-action) was retired.
    const mcpTool = action.mcp_tools?.[0];
    if (!mcpTool) {
      throw new Error('fire action requires an mcp_tool');
    }
    const result = await mcpCall<{ success?: boolean; error?: string; details?: string; message?: string }>(mcpTool, {
      ...(action.args ?? {}),
      context,
    });

    if (!result.success) {
      throw new Error(result.error || result.details || 'Action failed');
    }
    toast.success(result.message || `Ran ${action.label}`);
  }

  async function handleClick(action: Action) {
    if (runningActionId) return;

    // If action belongs to a different page, navigate first.
    if (action.page && action.page !== window.location.pathname && action.page !== '*') {
      router.push(action.page);
      return;
    }

    setRunningActionId(action.id);
    try {
      switch (action.dispatch) {
        case 'fire':
          await runFireAction(action);
          break;
        case 'oneshot':
          openPreparedActionDraft(action, 'oneshot');
          break;
        case 'chat':
          openPreparedActionDraft(action, 'chat');
          break;
        case 'ide':
          openPreparedActionDraft(action, 'ide');
          break;
        case 'modal':
          toast.info(`"${action.label}" requires a modal host on this page.`);
          break;
        default:
          toast.info(`"${action.label}" has unsupported dispatch "${action.dispatch || 'unknown'}".`);
          break;
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Action failed';
      toast.error(message);
    } finally {
      setRunningActionId(null);
    }
  }

  if (loading) {
    return (
      <GlassCard className="p-4">
        <div className="text-sm text-center py-4" style={{ color: 'var(--text-muted)' }}>
          Loading actions...
        </div>
      </GlassCard>
    );
  }

  if (displayActions.length === 0) {
    return (
      <GlassCard className="p-4">
        <div className="text-sm text-center py-4" style={{ color: 'var(--text-muted)' }}>
          {hub ? `No actions found for hub "${hub}"` : 'No actions configured'}
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard className="p-4">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
        {displayActions.map((action) => (
          <button
            key={action.id}
            onClick={() => handleClick(action)}
            disabled={runningActionId === action.id}
            className="flex flex-col items-center gap-1.5 rounded-lg px-3 py-3 text-center transition-all duration-150 hover:scale-[1.03] active:scale-[0.97] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/60"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              opacity: runningActionId === action.id ? 0.7 : 1,
            }}
            title={action.description}
            aria-label={action.label}
          >
            {action.icon && (
              <span className="text-xl leading-none" aria-hidden="true">
                {action.icon}
              </span>
            )}
            <span className="text-xs font-medium leading-tight" style={{ color: 'var(--text-secondary)' }}>
              {action.label}
            </span>
            {action.description && (
              <span className="text-[10px] leading-tight line-clamp-2" style={{ color: 'var(--text-muted)' }}>
                {action.description}
              </span>
            )}
          </button>
        ))}
      </div>
    </GlassCard>
  );
}
