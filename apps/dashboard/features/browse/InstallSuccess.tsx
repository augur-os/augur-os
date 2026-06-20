'use client';

import React from 'react';
import { CheckCircle, Star } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import type { SourceInfo } from './types';

interface InstalledSkill {
  name: string;
  toolCount: number;
}

interface InstallSuccessProps {
  /** "3 skills installed" / "skill imported" / "skill promoted" */
  headline: string;
  /** e.g. "from productivity-pack by acme-tools" */
  subtitle?: string;
  skills: InstalledSkill[];
  source?: SourceInfo;
  onClose: () => void;
  onViewInBrowse: () => void;
}

export function InstallSuccess({
  headline,
  subtitle,
  skills,
  source,
  onClose,
  onViewInBrowse,
}: InstallSuccessProps) {
  const showStarCta = source?.url?.includes('github.com');

  return (
    <div className="flex flex-col items-center px-6 py-8">
      {/* Success icon */}
      <div className="mb-4 flex size-14 items-center justify-center rounded-full border-2 border-green-500 bg-green-500/10">
        <CheckCircle className="size-7 text-green-500" />
      </div>

      <h3 className="mb-1 text-lg font-semibold text-foreground">{headline}</h3>
      {subtitle && <p className="mb-5 text-sm text-muted-foreground">{subtitle}</p>}

      {/* Installed skills summary */}
      {skills.length > 0 && (
        <div className="mb-5 w-full rounded-lg border border-border bg-card p-4">
          {skills.map((s) => (
            <div key={s.name} className="flex items-center gap-2 py-1">
              <span className="size-1.5 rounded-full bg-green-500" />
              <span className="text-sm text-foreground">{s.name}</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {s.toolCount} tool{s.toolCount !== 1 ? 's' : ''} registered
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Star CTA */}
      {showStarCta && (
        <div className="mb-5 w-full rounded-xl border border-border bg-gradient-to-br from-card to-accent/5 p-5 text-center">
          <p className="mb-1 text-sm font-semibold text-foreground">Enjoying this skill pack?</p>
          <p className="mb-3 text-xs text-muted-foreground">
            Show appreciation to the creator: it helps others discover great skills
          </p>
          <a
            href={source?.url ?? ''}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-lg bg-yellow-500 px-6 py-2.5 text-sm font-semibold text-black hover:bg-yellow-400 transition-colors"
          >
            <Star className="size-4" />
            Star on GitHub
          </a>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Opens {source?.url ?? ''} in a new tab
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3">
        <Button variant="outline" onClick={onClose}>
          Close
        </Button>
        <Button variant="solid" onClick={onViewInBrowse}>
          View in Browse
        </Button>
      </div>
    </div>
  );
}
