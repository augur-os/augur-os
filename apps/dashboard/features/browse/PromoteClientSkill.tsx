'use client';

import React, { useState, useCallback } from 'react';
import { Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { useMcpMutation } from '@/lib/mcp/useMcpMutation';
import { InstallSuccess } from './InstallSuccess';
import { StepHeader } from './StepHeader';

interface PromotableSkill {
  name: string;
  client: string;
  path: string;
  description: string;
  has_skill_md: boolean;
}

interface PromoteClientSkillProps {
  onBack: () => void;
  onClose: () => void;
}

const CLIENT_LABELS: Record<string, string> = {
  'claude-code': 'Claude Code',
  codex: 'Codex',
  gemini: 'Gemini',
};

const CLIENT_COLORS: Record<string, string> = {
  'claude-code': 'bg-indigo-950 text-indigo-400',
  codex: 'bg-green-950 text-green-400',
  gemini: 'bg-yellow-950 text-yellow-400',
};

export function PromoteClientSkill({ onBack, onClose }: PromoteClientSkillProps) {
  const [promoted, setPromoted] = useState<{ name: string } | null>(null);
  const [promotingName, setPromotingName] = useState<string | null>(null);

  const { data, loading, error, refetch } = useMcpQuery<{
    skills: PromotableSkill[];
    scanned_paths: string[];
  }>('list-promotable-skills', 'list-promotable-skills', 'realtime', {
    select: (raw: unknown) => raw as { skills: PromotableSkill[]; scanned_paths: string[] },
  });

  const { mutate: promote } = useMcpMutation<Record<string, unknown>>('promote-skill', {
    invalidates: ['browse-index', 'list-promotable-skills'],
  });

  const handlePromote = useCallback(
    async (skill: PromotableSkill) => {
      setPromotingName(skill.name);
      await promote({
        skill_path: skill.path,
        target_bundle: '',
        skill_name: skill.name,
      });
      toast.success(`${skill.name} promoted to Augur`);
      setPromoted({ name: skill.name });
      refetch();
      setPromotingName(null);
    },
    [promote, refetch],
  );

  if (promoted) {
    return (
      <InstallSuccess
        headline="Skill promoted"
        skills={[{ name: promoted.name, toolCount: 0 }]}
        onClose={onClose}
        onViewInBrowse={onClose}
      />
    );
  }

  return (
    <div>
      <StepHeader title="Promote Client Skill" onBack={onBack} />

      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {error && <p className="text-xs text-destructive">{error}</p>}

      {data && data.skills.length === 0 && (
        <div className="rounded-lg bg-muted p-6 text-center">
          <p className="text-sm text-muted-foreground">No promotable skills found</p>
          <p className="mt-1 text-xs text-muted-foreground/60">
            Scanned: {data.scanned_paths.join(', ')}
          </p>
        </div>
      )}

      {data && data.skills.length > 0 && (
        <div>
          <p className="mb-3 text-xs text-muted-foreground/60">
            Skills found in client folders that aren&apos;t yet in Augur:
          </p>
          <div className="space-y-2">
            {data.skills.map((skill) => (
              <div
                key={`${skill.client}-${skill.name}`}
                className="flex items-center justify-between rounded-lg border border-border bg-card p-3 transition-colors hover:border-purple-500"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">{skill.name}</span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${
                        CLIENT_COLORS[skill.client] || 'bg-muted text-muted-foreground'
                      }`}
                    >
                      {CLIENT_LABELS[skill.client] || skill.client}
                    </span>
                  </div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground/60">{skill.path}</p>
                  {skill.description && (
                    <p className="mt-0.5 text-xs text-muted-foreground">{skill.description}</p>
                  )}
                </div>
                <Button
                  variant="solid"
                  size="sm"
                  className="bg-purple-600 hover:bg-purple-500"
                  isLoading={promotingName === skill.name}
                  onClick={() => handlePromote(skill)}
                >
                  Promote
                </Button>
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground/40 italic">
            Scans {data.scanned_paths.join(', ')}
          </p>
        </div>
      )}
    </div>
  );
}
