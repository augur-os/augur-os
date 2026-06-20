'use client';

import React from 'react';
import { Loader2, Puzzle, MessageSquare, FileText } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { resolveIcon as resolveIconFromMap } from '@/lib/icon-map';
import { executeBrowseAction } from '@/lib/browse/executeAction';
import type { BrowseItem, SkillDetail, SkillOwnership } from '@/lib/browse/types';
import type { SkillCoverageFindings } from '@/lib/browse/skillCoverage';
import type { SkillDemo } from '@/lib/browse/cardModel';
import { BrowsePromptTrigger } from './BrowsePromptTrigger';
import { problemDetailRowsForItem } from '@/lib/browse/problems';
import type { AiItemActionItem, DirectItemAction } from '@/lib/browse/itemActions';
import { EMPTY_CAPTIONS_TRACK } from './BrowseDetailPanel.constants';
import { audioTranscript, splitMetadataList } from './BrowseDetailPanel.helpers';
import type {
  CapabilityProfileSection,
  GeneratedAiAction,
  SkillPrompt,
} from './BrowseDetailPanel.types';

export function DynamicIcon({ name, className }: { name?: string; className?: string }) {
  return React.createElement(resolveIconFromMap(name, Puzzle), { className });
}

export function AudioNoteSection({ item, noteType }: { item: BrowseItem; noteType: string }) {
  const metadata = item.metadata ?? {};
  const attendeeSlugs = splitMetadataList(metadata.attendee_slugs || metadata.attendeeSlugs);
  const audioPath = metadata.audio_path || metadata.audioPath;
  const duration = Math.round(Number(metadata.duration_seconds || metadata.durationSeconds || 0) / 60);
  const durationLabel = Number.isFinite(duration) && duration > 0 ? `${duration} min` : '? min';
  const isMeeting = noteType === 'meeting';

  return (
    <section>
      <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        {isMeeting ? 'Meeting Audio' : 'Voice Memo Audio'}
      </h3>
      <div className="space-y-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
        {audioPath ? (
          <audio
            controls
            src={`/api/vault-asset?path=${encodeURIComponent(audioPath)}`}
            aria-label={isMeeting ? 'Meeting audio playback' : 'Voice memo audio playback'}
            className="w-full"
          >
            <track kind="captions" src={EMPTY_CAPTIONS_TRACK} srcLang="en" label="No captions available" />
          </audio>
        ) : null}
        <div className="text-xs text-[var(--text-muted)]">
          Duration: {durationLabel} · provider: {metadata.provider ?? '?'}
          {isMeeting ? ` · attendees: ${metadata.attendee_count || metadata.attendeeCount || '?'}` : ''}
        </div>
        {isMeeting ? (
          <div>
            <div className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">Attendees</div>
            {attendeeSlugs.length > 0 ? (
              <div className="mt-1 flex flex-wrap gap-1">
                {attendeeSlugs.map((slug) => (
                  <a
                    key={slug}
                    href={`/browse?view=wiki&search=${encodeURIComponent(slug)}`}
                    className="rounded bg-[var(--bg-secondary)] px-2 py-0.5 text-xs text-[var(--text-primary)]"
                  >
                    {slug}
                  </a>
                ))}
              </div>
            ) : (
              <div className="mt-1 text-xs text-[var(--text-muted)]">No matched attendee links yet</div>
            )}
          </div>
        ) : null}
        <details>
          <summary className="cursor-pointer text-sm text-[var(--text-secondary)]">
            {isMeeting ? 'Transcript (with speakers)' : 'Transcript'}
          </summary>
          <pre className="mt-2 max-h-[60vh] overflow-auto whitespace-pre-wrap rounded bg-[var(--bg-primary)] p-2 text-xs text-[var(--text-primary)]">
            {audioTranscript(metadata)}
          </pre>
        </details>
        {isMeeting ? (
          <button type="button"
            className="rounded border border-[var(--border-color)] px-3 py-1 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
            onClick={() => {
              // TODO_HOOK: ADR-740 timeline-merge call wired in a follow-up.
            }}
          >
            Merge to timeline
          </button>
        ) : null}
      </div>
    </section>
  );
}

/**
 * ADR-741 check-resolvable findings for this skill. The audit has no browse
 * view of its own — findings ride the skill card (a state tag) and this panel
 * section. See lib/browse/skillCoverage.ts.
 */
export function CoverageFindingsSection({ findings }: { findings: SkillCoverageFindings }) {
  return (
    <section data-testid="skill-coverage-findings">
      <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        Coverage (ADR-741)
      </h3>
      <div className="space-y-2 rounded-xl border border-[var(--accent-warning)]/30 bg-[var(--accent-warning)]/5 p-4">
        {findings.orphaned && (
          <div className="text-sm">
            <span className="font-semibold text-[var(--accent-danger)]">Orphaned skill</span>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              {findings.orphaned.remediation}
            </p>
          </div>
        )}
        {findings.unrouted.map((finding) => (
          <div key={`unrouted-${finding.intent_phrase}`} className="text-sm">
            <span className="font-semibold text-[var(--text-primary)]">
              Unrouted intent:
            </span>{' '}
            <span className="font-mono text-xs text-[var(--text-primary)]">
              {finding.intent_phrase}
            </span>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{finding.remediation}</p>
          </div>
        ))}
        {findings.collisions.map((finding) => (
          <div key={`collision-${finding.phrase}`} className="text-sm">
            <span className="font-semibold text-[var(--text-primary)]">
              Routing collision:
            </span>{' '}
            <span className="font-mono text-xs text-[var(--text-primary)]">
              {finding.phrase}
            </span>
            <p className="mt-0.5 text-xs text-[var(--text-secondary)]">
              shared with {finding.skill_ids.join(', ')}: {finding.remediation}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

/**
 * Demo runbooks shipped in the skill's demos/ directory. Rule 32: demos have
 * no browse view of their own — they ride the owning skill's card (a badge)
 * and this detail-panel section. Each row reuses the standard open-file
 * action so the runbook opens like any other file-backed browse item.
 */
export function SkillDemosSection({ demos }: { demos: SkillDemo[] }) {
  const router = useRouter();
  return (
    <section data-testid="skill-demos">
      <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        Demos
      </h3>
      <ul className="space-y-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4" aria-label="Demo runbooks">
        {demos.map((demo) => (
          <li key={demo.path} className="flex items-center gap-2 min-w-0">
            <div className="flex-1 min-w-0">
              <div className="text-sm text-[var(--text-primary)] truncate">{demo.name}</div>
              <div className="text-xs font-mono text-[var(--text-muted)] truncate">{demo.path}</div>
            </div>
            <button
              type="button"
              onClick={() => {
                void executeBrowseAction(
                  { label: 'Open File', type: 'open-file', target: demo.path },
                  { router },
                );
              }}
              className="inline-flex min-h-[30px] shrink-0 cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
              title={`Open ${demo.name}`}
            >
              <FileText className="size-3.5" />
              Open
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ItemProblemsSection({ item }: { item: BrowseItem }) {
  const rows = problemDetailRowsForItem(item);
  if (rows.length === 0) return null;
  return (
    <section>
      <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        Problems
      </h3>
      <dl className="grid gap-3 rounded-xl border border-[var(--accent-warning)]/30 bg-[var(--accent-warning)]/5 p-4">
        {rows.map((row) => (
          <div key={`${row.label}-${row.value}`} className="min-w-0">
            <dt className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
              {row.label}
            </dt>
            <dd className="mt-1 break-words text-sm text-[var(--text-primary)]">
              {row.value}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function QualityTierBadge({ detail }: { detail: SkillDetail }) {
  if (!detail.qualityTier) return null;

  const className = detail.qualityTier === 'A'
    ? 'bg-[var(--accent-success)]/15 text-[var(--accent-success)]'
    : detail.qualityTier === 'B'
      ? 'bg-[var(--accent-info)]/15 text-[var(--accent-info)]'
      : detail.qualityTier === 'C'
        ? 'bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]'
        : 'bg-[var(--accent-danger)]/15 text-[var(--accent-danger)]';

  return (
    <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold ${className}`}>
      {detail.qualityTier} {detail.qualityScore ? `(${detail.qualityScore})` : ''}
    </span>
  );
}

export function OwnershipSkillSection({
  adoptError,
  adoptSkill,
  adoptSource,
  adopting,
  ownership,
  upstream,
}: {
  adoptError: string | null;
  adoptSkill: () => void;
  adoptSource: string;
  adopting: boolean;
  ownership: SkillOwnership;
  upstream: Array<{ label: string; value: string }>;
}) {
  if (ownership === 'external') {
    return (
      <section>
        <div className="rounded-xl border border-dashed border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/5 p-4">
          <h3 className="text-sm font-medium text-[var(--text-primary)] mb-1">
            Adopt this skill
          </h3>
          <p className="text-xs text-[var(--text-muted)] mb-3">
            Adopt it into a managed Augur skill folder to customize instructions, add scripts, or connect it to the dashboard.
          </p>
          <button type="button"
            disabled={adopting || !adoptSource}
            onClick={() => { adoptSkill(); }}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-[var(--accent-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg-card)]"
          >
            {adopting ? <Loader2 className="size-3 animate-spin" /> : null}
            {adopting ? 'Adopting...' : 'Adopt to Augur'}
          </button>
          {!adoptSource ? (
            <p className="text-xs text-[var(--accent-warning)] mt-2">
              No source metadata is available for this skill yet.
            </p>
          ) : null}
          {adoptError ? (
            <p className="text-xs text-[var(--accent-danger)] mt-2">{adoptError}</p>
          ) : null}
        </div>
      </section>
    );
  }

  if (ownership !== 'adopted' || upstream.length === 0) return null;

  return (
    <section>
      <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 backdrop-blur-sm p-4">
        <h3 className="text-sm font-medium text-[var(--text-primary)] mb-3">
          Upstream
        </h3>
        <dl className="grid gap-3 sm:grid-cols-2">
          {upstream.map((item) => (
            <div key={item.label} className="min-w-0">
              <dt className="text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
                {item.label}
              </dt>
              <dd className="mt-1 text-sm text-[var(--text-primary)] break-words">
                {item.value}
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

export function GeneratedSkillActionsSection({
  aiActions,
  directActions,
  item,
  onItemDirect,
  onItemPrompt,
  show,
}: {
  aiActions: GeneratedAiAction[];
  directActions: DirectItemAction[];
  item: AiItemActionItem;
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
  onItemPrompt?: (prompt: string) => void;
  show: boolean;
}) {
  if (!show) return null;

  return (
    <section>
      <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        Item Actions
      </h3>
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-3">
        {aiActions.map((action) => (
          <button
            key={action.id}
            type="button"
            onClick={() => onItemPrompt?.(action.template(item))}
            className="inline-flex min-h-[30px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            title={action.label}
          >
            {React.createElement(resolveIconFromMap(action.icon, MessageSquare), {
              className: 'size-3.5',
            })}
            {action.label}
          </button>
        ))}
        {directActions.map((action) => (
          <button
            key={action.id}
            type="button"
            onClick={() => onItemDirect?.(action, item)}
            className="inline-flex min-h-[30px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
            title={action.label}
          >
            {React.createElement(resolveIconFromMap(action.icon, MessageSquare), {
              className: 'size-3.5',
            })}
            {action.label}
          </button>
        ))}
      </div>
    </section>
  );
}

export function SkillPromptsSection({
  onTriggerPrompt,
  prompts,
}: {
  onTriggerPrompt?: (resolvedPrompt: string) => void;
  prompts: SkillPrompt[];
}) {
  if (prompts.length === 0 || !onTriggerPrompt) return null;

  return (
    <section>
      <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        Prompts
      </h3>
      <ul className="space-y-2" aria-label="Triggerable prompts">
        {prompts.map((prompt) => (
          <SkillPromptRow
            key={prompt.id}
            prompt={prompt}
            onTriggerPrompt={onTriggerPrompt}
          />
        ))}
      </ul>
    </section>
  );
}

function SkillPromptRow({
  onTriggerPrompt,
  prompt,
}: {
  onTriggerPrompt: (resolvedPrompt: string) => void;
  prompt: SkillPrompt;
}) {
  const source = prompt.source ?? 'skill';
  const sourceClass = source === 'vault'
    ? 'bg-[var(--accent-warning)]/15 text-[var(--accent-warning)] border-[var(--accent-warning)]/25'
    : 'bg-[var(--bg-secondary)] text-[var(--text-muted)] border-[var(--border-color)]';

  return (
    <li className="flex items-center gap-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]/40 px-3 py-2">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-[var(--text-primary)] truncate">
            {prompt.label}
          </span>
          <span
            className={`px-2 py-0.5 rounded text-[11px] font-medium border ${sourceClass}`}
            title={`Source: ${source}`}
          >
            {source}
          </span>
        </div>
        {prompt.description ? (
          <p className="text-xs text-[var(--text-muted)] line-clamp-2 mt-0.5">
            {prompt.description}
          </p>
        ) : null}
      </div>
      <BrowsePromptTrigger
        promptBody={prompt.prompt}
        placeholders={prompt.placeholders ?? []}
        onTrigger={onTriggerPrompt}
      />
    </li>
  );
}

export function CapabilityProfileSections({
  sections,
  show,
}: {
  sections: CapabilityProfileSection[];
  show: boolean;
}) {
  if (!show) return null;

  return (
    <section>
      <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
        Capability Profile
      </h3>
      <div className="space-y-3">
        {sections.map((section) => (
          <section
            key={section.id}
            className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 backdrop-blur-sm p-4"
          >
            <h4 className="text-sm font-semibold text-[var(--text-primary)]">
              {section.title}
            </h4>
            <div className="mt-3 space-y-2">
              {section.items.map((item) => (
                <div
                  key={`${section.id}-${item.label}`}
                  className="rounded-lg bg-[var(--bg-card)]/70 p-3"
                >
                  <div className="text-sm font-medium text-[var(--text-primary)]">
                    {item.label}
                  </div>
                  {item.description ? (
                    <div className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">
                      {item.description}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
