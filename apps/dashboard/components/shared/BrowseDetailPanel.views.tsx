'use client';

import React, { useEffect } from 'react';
import { X, Loader2, MessageSquare, FolderOpen, FileText } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { resolveIcon as resolveIconFromMap } from '@/lib/icon-map';
import { mcpCall } from '@/lib/mcp/client';
import { executeBrowseAction } from '@/lib/browse/executeAction';
import type { BrowseItem, SkillDetail, SkillOwnership } from '@/lib/browse/types';
import { NoteClassificationEditor } from './NoteClassificationEditor';
import EditableMarkdown from '@/components/EditableMarkdown';
import {
  aiItemActionsFor,
  directItemActionsFor,
  type AiItemActionItem,
  type DirectItemAction,
} from '@/lib/browse/itemActions';
import type { ActiveFolderContext } from '@/lib/browse/folderContext';
import {
  EMPTY_CAPTIONS_TRACK,
  HEALTH_STYLES,
  MARKDOWN_EXTENSIONS,
  NOTE_CLASSIFICATION_CATEGORY_IDS,
  NOTE_TYPE_ICONS,
  NOTE_TYPE_LABELS,
  OWNERSHIP_LABELS,
  OWNERSHIP_STYLES,
  PRIMARY_SAFE_TYPES,
  SOURCE_LABELS,
  TEXT_FILE_EXTENSIONS,
} from './BrowseDetailPanel.constants';
import {
  articleEnrichmentSections,
  fileItemRows,
  isRealFilePath,
  mediaKindForFileItem,
  noteDetailRows,
  noteTypeForItem,
  pathExtension,
  rawNoteType,
  stripFrontmatter,
  stripHtmlComments,
} from './BrowseDetailPanel.helpers';
import {
  AudioNoteSection,
  DynamicIcon,
  ItemProblemsSection,
  QualityTierBadge,
} from './BrowseDetailPanel.sections';

/* ──────────────────────────────────────────────────────────────────────────
 * File-backed browse items — agents, ADRs, wiki, scripts, mcp-tools, mcp-servers,
 * api-routes, tests, logs, documents, pages, actions, integrations, … — are NOT
 * notes. Routing them through the note panel mislabelled them as "Thought" with a
 * speech-bubble icon and an almost-empty body. FileItemDetailPanel gives each the
 * correct category icon + label, real metadata, the file's content (markdown
 * rendered, code/text in a <pre>), and Open/Reveal — or the item's own primary
 * action for synthetic targets like ADRs. See dev-debug session 2026-05-22.
 * ────────────────────────────────────────────────────────────────────────── */

/**
 * Category-aware detail view for every file-backed browse item. Keyed by item.id
 * in the dispatcher so a fresh instance mounts per item; the fetch effect only
 * sets state inside async callbacks (react-hooks/set-state-in-effect).
 */
export function FileItemDetailPanel({
  item,
  onClose,
  label,
  iconName,
  category,
  onItemPrompt,
  onItemDirect,
  activeFolderContext,
}: {
  item: BrowseItem;
  onClose: () => void;
  label: string;
  iconName?: string;
  category?: string;
  onItemPrompt?: (prompt: string) => void;
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
  activeFolderContext?: ActiveFolderContext | null;
}) {
  const router = useRouter();
  const rows = fileItemRows(item);
  const primary = item.primaryAction;
  // AI actions hand a resolved, item-aware prompt to the dashboard chat as an
  // editable draft (no CLI auto-starts; the user reviews/edits and sends).
  const aiActions = onItemPrompt ? aiItemActionsFor(category, item, { activeFolderContext }) : [];
  const directActions = onItemDirect ? directItemActionsFor(category, item) : [];
  const path = item.path || '';
  const ext = pathExtension(path);
  const realFile = isRealFilePath(path);
  const showFileUtilityActions = realFile;
  const mediaKind = realFile ? mediaKindForFileItem(item, ext) : '';
  const mediaSrc = mediaKind ? `/api/vault-asset?path=${encodeURIComponent(path)}` : '';
  const readable = realFile && TEXT_FILE_EXTENSIONS.has(ext);
  const isMarkdown = MARKDOWN_EXTENSIONS.has(ext);
  const showPrimaryAction = Boolean(primary?.target) && PRIMARY_SAFE_TYPES.has(primary.type);
  const hasActions = showPrimaryAction || showFileUtilityActions || aiActions.length > 0 || directActions.length > 0;

  const [{ content, loading, error }, dispatchContentState] = React.useReducer(
    (
      state: { content: string | null; loading: boolean; error: string | null },
      action:
        | { type: 'loading' }
        | { type: 'loaded'; content: string }
        | { type: 'error'; error: string },
    ) => {
      switch (action.type) {
        case 'loading':
          return { content: null, loading: true, error: null };
        case 'loaded':
          return { content: action.content, loading: false, error: null };
        case 'error':
          return { ...state, loading: false, error: action.error };
        default:
          return state;
      }
    },
    { content: readable ? null : '', loading: readable, error: null },
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);
  useEffect(() => {
    if (!readable) {
      dispatchContentState({ type: 'loaded', content: '' });
      return;
    }
    let cancelled = false;
    dispatchContentState({ type: 'loading' });
    mcpCall<{ content?: string; status?: string; message?: string }>('file-read', { path })
      .then((res) => {
        if (cancelled) return;
        if (res?.status === 'error') {
          dispatchContentState({
            type: 'error',
            error: res.message || 'Failed to load content',
          });
          return;
        }
        dispatchContentState({
          type: 'loaded',
          content: typeof res?.content === 'string' ? res.content : '',
        });
      })
      .catch((err) => {
        if (cancelled) return;
        dispatchContentState({
          type: 'error',
          error: err instanceof Error ? err.message : 'Failed to load content',
        });
      });
    return () => {
      cancelled = true;
    };
  }, [path, readable]);

  const runAction = (action: BrowseItem['primaryAction']) => {
    void executeBrowseAction(action, { router });
  };

  const markdownBody = content ? stripHtmlComments(stripFrontmatter(content)) : '';
  const actionButtonClass =
    'inline-flex min-h-[30px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-primary)] px-3 py-1 text-xs font-semibold text-[var(--text-primary)] transition-colors hover:bg-[var(--bg-hover)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50';
  // One emphasized primary CTA per panel so the action row has a clear entry
  // point instead of N equal-weight buttons. When the item exposes its own
  // primary action that takes the lead; otherwise Open File is the de-facto
  // primary for file-backed items.
  const primaryActionButtonClass =
    'inline-flex min-h-[30px] cursor-pointer items-center gap-1.5 rounded-lg border border-[var(--accent-primary)]/30 bg-[var(--accent-primary)]/10 px-3 py-1 text-xs font-semibold text-[var(--accent-primary)] transition-colors hover:bg-[var(--accent-primary)]/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50';

  return (
    <section className="h-full flex flex-col overflow-hidden" aria-label={`${item.title} detail panel`}>
      <div className="flex items-start gap-3 p-4 border-b border-[var(--border-color)] shrink-0">
        <div className="size-10 rounded-xl bg-[var(--accent-primary)]/10 flex items-center justify-center shrink-0">
          {React.createElement(resolveIconFromMap(iconName, FileText), {
            className: 'size-5 text-[var(--accent-primary)]',
          })}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] truncate" dir="auto">
              {item.title}
            </h2>
            <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]">
              {label}
            </span>
          </div>
          <p className="text-sm text-[var(--text-muted)] line-clamp-2">
            {item.description || path}
          </p>
        </div>
        <button type="button"
          title="Close (Esc)"
          aria-label="Close detail panel"
          onClick={onClose}
          className="p-2.5 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] shrink-0 transition-colors duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {rows.length > 0 && (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Details
            </h3>
            <dl className="grid gap-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
              {rows.map((row) => (
                <div key={row.label} className="min-w-0">
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
        )}

        <ItemProblemsSection item={item} />

        {hasActions && (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Actions
            </h3>
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-3">
              {showPrimaryAction && (
                <button
                  type="button"
                  onClick={() => runAction(primary)}
                  className={primaryActionButtonClass}
                >
                  {primary.label || 'Open'}
                </button>
              )}
              {showFileUtilityActions && (
                <>
                  <button
                    type="button"
                    onClick={() => runAction({ label: 'Open File', type: 'open-file', target: path })}
                    className={showPrimaryAction ? actionButtonClass : primaryActionButtonClass}
                  >
                    <FileText className="size-3.5" />
                    Open File
                  </button>
                  <button
                    type="button"
                    onClick={() => runAction({ label: 'Reveal in Finder', type: 'reveal-file', target: path })}
                    className={actionButtonClass}
                  >
                    <FolderOpen className="size-3.5" />
                    Reveal in Finder
                  </button>
                </>
              )}
              {aiActions.map((action) => (
                <button
                  key={action.id}
                  type="button"
                  onClick={() => onItemPrompt?.(action.template(item))}
                  className={actionButtonClass}
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
                  className={actionButtonClass}
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
        )}

        {mediaKind && mediaSrc ? (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Preview
            </h3>
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
              {mediaKind === 'audio' ? (
                <audio aria-label="Audio preview" controls src={mediaSrc} className="w-full">
                  <track kind="captions" src={EMPTY_CAPTIONS_TRACK} srcLang="en" label="No captions available" />
                </audio>
              ) : (
                <video
                  aria-label="Video preview"
                  controls
                  src={mediaSrc}
                  className="max-h-[50vh] w-full rounded-lg bg-gray-950"
                >
                  <track kind="captions" src={EMPTY_CAPTIONS_TRACK} srcLang="en" label="No captions available" />
                </video>
              )}
              <p className="mt-2 text-xs text-[var(--text-muted)]">
                Use Open File if the embedded preview cannot play this codec.
              </p>
            </div>
          </section>
        ) : null}

        {readable && (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              {isMarkdown ? 'Content' : 'Source'}
            </h3>
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                  <Loader2 className="size-4 animate-spin" />
                  Loading…
                </div>
              ) : error ? (
                <p className="text-sm text-[var(--accent-danger)]">{error}</p>
              ) : isMarkdown && markdownBody ? (
                <EditableMarkdown markdown={markdownBody} />
              ) : content ? (
                <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-[var(--bg-primary)] p-3 font-mono text-xs leading-relaxed text-[var(--text-primary)]">
                  {content}
                </pre>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">No content available.</p>
              )}
            </div>
          </section>
        )}
      </div>
    </section>
  );
}

export function NoteItemDetailView({
  item,
  onClose,
  category,
  onItemPrompt,
  onItemDirect,
  activeFolderContext,
}: {
  item: BrowseItem;
  onClose: () => void;
  category?: string;
  onItemPrompt?: (prompt: string) => void;
  onItemDirect?: (action: DirectItemAction, item: AiItemActionItem) => void | Promise<void>;
  activeFolderContext?: ActiveFolderContext | null;
}) {
  const itemKind = item.metadata?.kind ?? '';
  const isProfileKind = itemKind === 'memory-entry' || itemKind === 'voice-profile' || itemKind === 'interview-slot';
  const showClassificationEditor = !isProfileKind && (
    category ? NOTE_CLASSIFICATION_CATEGORY_IDS.has(category) : rawNoteType(item) !== null
  );
  const noteType = noteTypeForItem(item);
  // For profile-tab kinds, prefer the card's typeBadge over the note-type fallback
  const headerLabel = isProfileKind ? (item.typeBadge || NOTE_TYPE_LABELS[noteType]) : NOTE_TYPE_LABELS[noteType];
  const Icon = NOTE_TYPE_ICONS[noteType as keyof typeof NOTE_TYPE_ICONS] ?? MessageSquare;
  const rows = noteDetailRows(item);
  const enrichmentSections = articleEnrichmentSections(item);
  const aiActions = onItemPrompt ? aiItemActionsFor(category, item, { activeFolderContext }) : [];
  const directActions = onItemDirect ? directItemActionsFor(category, item) : [];
  const path = item.path || item.primaryAction.target || '';
  const ext = pathExtension(path);
  const realFile = isRealFilePath(path);
  const readable = realFile && TEXT_FILE_EXTENSIONS.has(ext);
  const isMarkdown = MARKDOWN_EXTENSIONS.has(ext);
  const [{ content, loading, error }, dispatchContentState] = React.useReducer(
    (
      state: { content: string | null; loading: boolean; error: string | null },
      action:
        | { type: 'loading' }
        | { type: 'loaded'; content: string }
        | { type: 'error'; error: string },
    ) => {
      switch (action.type) {
        case 'loading':
          return { content: null, loading: true, error: null };
        case 'loaded':
          return { content: action.content, loading: false, error: null };
        case 'error':
          return { ...state, loading: false, error: action.error };
        default:
          return state;
      }
    },
    { content: readable ? null : '', loading: readable, error: null },
  );
  const markdownBody = content ? stripHtmlComments(stripFrontmatter(content)) : '';

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  useEffect(() => {
    if (!readable) {
      dispatchContentState({ type: 'loaded', content: '' });
      return;
    }
    let cancelled = false;
    dispatchContentState({ type: 'loading' });
    mcpCall<{ content?: string; status?: string; message?: string }>('file-read', { path })
      .then((res) => {
        if (cancelled) return;
        if (res?.status === 'error') {
          dispatchContentState({
            type: 'error',
            error: res.message || 'Failed to load preview',
          });
          return;
        }
        dispatchContentState({
          type: 'loaded',
          content: typeof res?.content === 'string' ? res.content : '',
        });
      })
      .catch((err) => {
        if (cancelled) return;
        dispatchContentState({
          type: 'error',
          error: err instanceof Error ? err.message : 'Failed to load preview',
        });
      });
    return () => {
      cancelled = true;
    };
  }, [path, readable]);

  return (
    <section className="h-full flex flex-col overflow-hidden" aria-label={`${item.title} detail panel`}>
      <div className="flex items-start gap-3 p-4 border-b border-[var(--border-color)] shrink-0">
        <div className="size-10 rounded-xl bg-[var(--accent-primary)]/10 flex items-center justify-center shrink-0">
          <Icon className="size-5 text-[var(--accent-primary)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold text-[var(--text-primary)] truncate" dir="auto">
              {item.title}
            </h2>
            <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]">
              {headerLabel || ''}
            </span>
          </div>
          <p className="text-sm text-[var(--text-muted)] line-clamp-2">
            {item.description || item.path}
          </p>
        </div>
        <button type="button"
          title="Close (Esc)"
          aria-label="Close detail panel"
          onClick={onClose}
          className="p-2.5 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] shrink-0 transition-colors duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {showClassificationEditor ? <NoteClassificationEditor item={item} /> : null}
        <section>
          <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
            Note Details
          </h3>
          <dl className="grid gap-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
            {rows.map((row) => (
              <div key={row.label} className="min-w-0">
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
        <ItemProblemsSection item={item} />
        {(aiActions.length > 0 || directActions.length > 0) ? (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Actions
            </h3>
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-3">
              <div className="flex flex-wrap items-center gap-2">
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
            </div>
          </section>
        ) : null}
        {readable ? (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Preview
            </h3>
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
              {loading ? (
                <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                  <Loader2 className="size-4 animate-spin" />
                  Loading…
                </div>
              ) : error ? (
                <p className="text-sm text-[var(--accent-danger)]">{error}</p>
              ) : isMarkdown && markdownBody ? (
                <EditableMarkdown markdown={markdownBody} />
              ) : content ? (
                <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-[var(--bg-primary)] p-3 font-mono text-xs leading-relaxed text-[var(--text-primary)]">
                  {content}
                </pre>
              ) : (
                <p className="text-sm text-[var(--text-muted)]">No preview available.</p>
              )}
            </div>
          </section>
        ) : null}
        {enrichmentSections.length > 0 ? (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Article Enrichment
            </h3>
            <div className="space-y-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4">
              {enrichmentSections.map((section) => (
                <div key={section.id} className="min-w-0">
                  <h4 className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                    {section.label}
                  </h4>
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm leading-6 text-[var(--text-secondary)]">
                    {section.value}
                  </p>
                </div>
              ))}
            </div>
          </section>
        ) : null}
        {item.metadata?.summary || item.metadata?.excerpt ? (
          <section>
            <h3 className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wider mb-2">
              Summary
            </h3>
            <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-secondary)]/60 p-4 text-sm leading-6 text-[var(--text-secondary)]">
              {item.metadata.summary || item.metadata.excerpt}
            </div>
          </section>
        ) : null}
        {noteType === 'voice-memo' || noteType === 'meeting' ? (
          <AudioNoteSection item={item} noteType={noteType} />
        ) : null}
      </div>
    </section>
  );
}

export function BrowseDetailHeader({
  detail,
  onClose,
  ownership,
}: {
  detail: SkillDetail;
  onClose: () => void;
  ownership: SkillOwnership;
}) {
  return (
    <div className="flex items-start gap-3 p-4 border-b border-[var(--border-color)] shrink-0">
      <div className="size-10 rounded-xl bg-[var(--accent-primary)]/10 flex items-center justify-center shrink-0">
        <DynamicIcon name={detail.icon} className="size-5 text-[var(--accent-primary)]" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-[var(--text-primary)] truncate">
            {detail.title}
          </h2>
          {detail.health && detail.health.status !== 'unknown' ? (
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${HEALTH_STYLES[detail.health.status] ?? HEALTH_STYLES.unknown}`}
            >
              {detail.health.status}
            </span>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5 mt-1">
          {detail.hub && detail.hub !== 'unknown' ? (
            <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]">
              {detail.hub}
            </span>
          ) : null}
          <QualityTierBadge detail={detail} />
          {detail.masterClient ? (
            <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-[var(--bg-primary)] text-[var(--text-muted)]">
              {detail.masterClient}
            </span>
          ) : null}
          <span className={`px-2 py-0.5 rounded-md text-[11px] font-medium ${OWNERSHIP_STYLES[ownership]}`}>
            {OWNERSHIP_LABELS[ownership]}
          </span>
          {detail.source && ownership !== 'external' ? (
            <span className="px-2 py-0.5 rounded-md text-[11px] font-medium bg-[var(--accent-info)]/10 text-[var(--accent-info)]">
              {SOURCE_LABELS[detail.source] ?? detail.source}
            </span>
          ) : null}
          {detail.updateAvailable ? (
            <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-[var(--accent-warning)]/15 text-[var(--accent-warning)]">
              Update available
            </span>
          ) : null}
        </div>
        <p className="text-sm text-[var(--text-muted)] line-clamp-2">
          {detail.problemStatement ?? detail.description}
        </p>
      </div>
      <button type="button"
        title="Close (Esc)"
        aria-label="Close detail panel"
        onClick={onClose}
        className="p-2.5 rounded-lg bg-[var(--bg-secondary)] hover:bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] shrink-0 transition-colors duration-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-primary)]/50"
      >
        <X className="size-4" aria-hidden="true" />
      </button>
    </div>
  );
}
