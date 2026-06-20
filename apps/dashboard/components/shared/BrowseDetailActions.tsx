'use client';

import { useState } from 'react';
import { Zap } from 'lucide-react';
import { toast } from 'sonner';
import { resolveIcon as resolveIconFromMap } from '@/lib/icon-map';
import { runCliExecPrompt } from '@/lib/browse/cliExecClient';
import type { SkillAction } from '@/lib/browse/types';

function resolveIcon(name?: string): React.ElementType {
  return resolveIconFromMap(name, Zap);
}

interface BrowseDetailActionsProps {
  actions: SkillAction[];
  skillId: string;
}

export function BrowseDetailActions({ actions, skillId: _skillId }: BrowseDetailActionsProps) {
  const [executingAction, setExecutingAction] = useState<string | null>(null);

  if (actions.length === 0) return null;

  return (
    <div className="space-y-2">
      {actions.map((action) => {
        const Icon = resolveIcon(action.icon);
        return (
          <div key={action.id} className="flex items-center gap-2">
            <button type="button"
              onClick={() => {
                if (action.dispatch === 'modal') {
                  toast.info(`"${action.label}" requires a dedicated modal.`);
                  return;
                }

                const prompt = action.description || action.label || action.id;
                setExecutingAction(action.id);
                const toastId = toast.loading(`Running ${action.label}...`);
                void runCliExecPrompt(prompt)
                  .then(() => toast.success(`${action.label} completed`, { id: toastId }))
                  .catch((error) => {
                    const message = error instanceof Error ? error.message : `${action.label} failed`;
                    toast.error(message, { id: toastId });
                  })
                  .finally(() => setExecutingAction(null));
              }}
              disabled={executingAction !== null}
              aria-label={action.label}
              className="flex items-center gap-1.5 px-3 py-1.5 min-h-[44px] text-sm rounded-lg bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/20 transition-colors disabled:opacity-50 cursor-pointer"
              title={action.description}
            >
              <Icon className="size-3.5" />
              {action.label}
            </button>
          </div>
        );
      })}
    </div>
  );
}
