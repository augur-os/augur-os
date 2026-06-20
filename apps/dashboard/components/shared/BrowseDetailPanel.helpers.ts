import { formatTimeAgo } from '@/lib/timestamps';
import type { BrowseItem, SkillDetail, SkillOwnership, SkillUpstream } from '@/lib/browse/types';
import {
  AUDIO_EXTENSIONS,
  NOTE_TYPE_LABELS,
  VIDEO_EXTENSIONS,
} from './BrowseDetailPanel.constants';

/** Strip YAML frontmatter (--- ... ---) from markdown content */
export function stripFrontmatter(md: string): string {
  const trimmed = md.trimStart();
  if (!trimmed.startsWith('---')) return md;
  const endIdx = trimmed.indexOf('---', 3);
  if (endIdx === -1) return md;
  return trimmed.slice(endIdx + 3).trimStart();
}

/** Strip HTML comments from markdown content */
export function stripHtmlComments(md: string): string {
  return md.replace(/<!--[\s\S]*?-->/g, '');
}

export function isGeneratedDoc(md: string): boolean {
  return md.includes('AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY');
}

export function normalizeOwnership(value: SkillDetail['ownership']): SkillOwnership {
  if (value === 'external' || value === 'adopted' || value === 'user') return value;
  return 'augur';
}

export function upstreamSummary(upstream?: SkillUpstream): Array<{ label: string; value: string }> {
  if (!upstream) return [];
  return [
    upstream.source ? { label: 'Source', value: upstream.source } : null,
    upstream.repo ? { label: 'Repo', value: upstream.repo } : null,
    upstream.ref ? { label: 'Ref', value: upstream.ref } : null,
    upstream.version ? { label: 'Version', value: upstream.version } : null,
    upstream.path ? { label: 'Path', value: upstream.path } : null,
    upstream.subpath ? { label: 'Subpath', value: upstream.subpath } : null,
  ].filter((item): item is { label: string; value: string } => item !== null);
}

export function metadataValue(metadata: BrowseItem['metadata'] | undefined, ...keys: string[]): string {
  if (!metadata) return '';
  for (const key of keys) {
    const value = metadata[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return '';
}

export function titleCaseMetadata(value: string): string {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function isWikiDetailItem(item: BrowseItem): boolean {
  const typeBadge = (item.typeBadge || '').toLowerCase();
  const pageType = metadataValue(item.metadata, 'pageType', 'page_type').toLowerCase();
  return typeBadge === 'wiki' ||
    typeBadge === 'wiki page' ||
    typeBadge === 'concept' ||
    typeBadge === 'query' ||
    typeBadge === 'overview' ||
    typeBadge === 'index' ||
    ['wiki', 'concept', 'query', 'overview', 'index'].includes(pageType);
}

export function wikiMaintenanceRows(item: BrowseItem): Array<{ label: string; value: string }> {
  if (!isWikiDetailItem(item)) return [];
  const pending = metadataValue(item.metadata, 'wikiPendingSources');
  const total = metadataValue(item.metadata, 'wikiSourceTotal');
  const batchQuality = metadataValue(item.metadata, 'wikiLastBatchQuality');
  const state = metadataValue(item.metadata, 'wikiMaintenanceState');
  const lastReindexed = metadataValue(item.metadata, 'wikiLastReindexedAt');
  const lastChecked = metadataValue(item.metadata, 'wikiMaintenanceCheckedAt');
  const rows: Array<{ label: string; value: string }> = [
    { label: 'Maintenance status', value: state ? titleCaseMetadata(state) : '' },
    { label: 'Pending sources', value: pending ? (total ? `${pending} / ${total}` : pending) : '' },
    { label: 'Last checked', value: lastChecked ? formatTimeAgo(lastChecked) : '' },
    { label: 'Last reindexed', value: lastReindexed ? formatTimeAgo(lastReindexed) : '' },
    { label: 'Batch quality', value: batchQuality ? titleCaseMetadata(batchQuality) : '' },
    { label: 'Batch reason', value: metadataValue(item.metadata, 'wikiLastBatchReason') },
  ];
  return rows.filter((row) => row.value);
}

export function noteTypeForItem(item: BrowseItem): string {
  const raw = (
    item.metadata?.['x-augur-note-type'] ||
    item.metadata?.noteType ||
    item.metadata?.note_type ||
    item.typeBadge ||
    'thought'
  )
    .toLowerCase()
    .replace(/[\s_]+/g, '-');
  if (raw === 'audio' || raw === 'voice') return 'voice-memo';
  return NOTE_TYPE_LABELS[raw] ? raw : 'thought';
}

export function isArticleNoteItem(item: BrowseItem): boolean {
  const noteType = noteTypeForItem(item);
  return noteType === 'url' || noteType === 'file';
}

export function enrichmentStatusForItem(item: BrowseItem): string {
  return metadataValue(
    item.metadata,
    'enrichment_status',
    'enrichmentStatus',
    'x-augur-enrichment-status',
  ) || 'raw';
}

export function enrichmentVersionForItem(item: BrowseItem): string {
  return metadataValue(
    item.metadata,
    'x-augur-enrichment-version',
    'enrichment_version',
    'enrichmentVersion',
  );
}

export function articleEnrichmentSections(item: BrowseItem): Array<{ id: string; label: string; value: string }> {
  const metadata = item.metadata;
  if (!metadata) return [];

  return [
    {
      id: 'executive-summary',
      label: 'Executive summary',
      value: metadataValue(metadata, 'executive_summary', 'executiveSummary'),
    },
    {
      id: 'key-insights',
      label: 'Key insights',
      value: metadataValue(metadata, 'key_insights', 'keyInsights'),
    },
    {
      id: 'why-it-matters',
      label: 'Why it matters',
      value: metadataValue(metadata, 'why_it_matters', 'whyItMatters'),
    },
    {
      id: 'verbatim-quotes',
      label: 'Verbatim quotes',
      value: metadataValue(metadata, 'verbatim_quotes', 'verbatimQuotes'),
    },
    {
      id: 'cross-references',
      label: 'Cross-references',
      value: metadataValue(metadata, 'cross_references', 'crossReferences', 'cross_references_json'),
    },
  ].filter((section) => section.value);
}

export function noteDetailRows(item: BrowseItem): Array<{ label: string; value: string }> {
  const metadata = item.metadata ?? {};
  const kind = metadata.kind ?? '';
  const isArticleNote = isArticleNoteItem(item);

  // Profile-tab cards (memory-entry / voice-profile / interview-slot) carry a
  // different metadata shape than notes. Render the rows that make sense for
  // each kind so the detail panel isn't a blank box (rule 32 — every tab uses
  // the same detail-panel surface; signals ride card metadata).
  if (kind === 'memory-entry' || kind === 'voice-profile' || kind === 'interview-slot') {
    const rows = [
      { label: 'Path', value: item.path || item.primaryAction.target },
      { label: 'Type', value: item.typeBadge ?? '' },
      { label: 'Client', value: metadata.client || '' },
      { label: 'Source', value: metadata.source || '' },
      { label: 'Language', value: metadata.language || '' },
      { label: 'Status', value: metadata.status || '' },
      { label: 'Category', value: metadata.category || '' },
      { label: 'Modified', value: metadata.modified || '' },
      { label: 'Size (bytes)', value: metadata.sizeBytes || '' },
    ];
    return rows.filter((row) => row.value);
  }

  const rows = [
    { label: 'Path', value: item.path || item.primaryAction.target },
    { label: 'Type', value: NOTE_TYPE_LABELS[noteTypeForItem(item)] },
    { label: 'Source domain', value: metadata.source_domain || metadata.sourceDomain || '' },
    { label: 'URL', value: metadata.canonical_url || metadata.url || '' },
    { label: 'Transcript', value: metadata.transcript_status || metadata.transcriptStatus || '' },
    { label: 'Duration', value: metadata.duration_seconds || metadata.durationSeconds || '' },
    { label: 'Attendees', value: metadata.attendee_count || metadata.attendeeCount || '' },
    { label: 'Enrichment', value: isArticleNote ? enrichmentStatusForItem(item) : metadata.enrichment_status || metadata.enrichmentStatus || '' },
    { label: 'Triggers', value: metadata.trigger_count || metadata.triggerCount || '' },
    { label: 'Variables', value: metadata.variable_count || metadata.variableCount || '' },
  ];
  return rows.filter((row) => row.value);
}

export function splitMetadataList(value?: string): string[] {
  return (value ?? '')
    .split(',')
    .flatMap((item) => {
      const trimmed = item.trim();
      return trimmed ? [trimmed] : [];
    });
}

export function audioTranscript(metadata: BrowseItem['metadata']): string {
  return (
    metadata?.transcript ||
    metadata?.transcript_preview ||
    metadata?.transcriptPreview ||
    '(transcript not available in metadata; open the source file)'
  );
}

export function pathExtension(path: string): string {
  const base = path.split(/[\\/]/).pop() ?? '';
  const idx = base.lastIndexOf('.');
  return idx > 0 ? base.slice(idx + 1).toLowerCase() : '';
}

export function mediaKindForFileItem(item: BrowseItem, ext: string): 'audio' | 'video' | '' {
  const raw = (
    item.metadata?.media_kind ||
    item.metadata?.mediaKind ||
    item.metadata?.document_kind ||
    ''
  ).toLowerCase();
  if (raw === 'audio' || raw === 'video') return raw;
  if (AUDIO_EXTENSIONS.has(ext)) return 'audio';
  if (VIDEO_EXTENSIONS.has(ext)) return 'video';
  return '';
}

/** Synthetic / non-filesystem targets (archive://ADR-001, index://, http://, …). */
export function isSyntheticPath(path: string): boolean {
  return /^[a-z][a-z0-9+.-]*:\/\//i.test(path);
}

export function isRealFilePath(path: string | undefined): path is string {
  return Boolean(path) && !isSyntheticPath(path as string);
}

/** Strict note-type detector (no 'thought' fallback) for category-less dispatch. */
export function rawNoteType(item: BrowseItem): string | null {
  const raw = (
    item.metadata?.['x-augur-note-type'] ||
    item.metadata?.noteType ||
    item.metadata?.note_type ||
    item.typeBadge ||
    ''
  )
    .toLowerCase()
    .replace(/[\s_]+/g, '-');
  if (raw === 'audio' || raw === 'voice') return 'voice-memo';
  return NOTE_TYPE_LABELS[raw] ? raw : null;
}

export function humanizeBytes(value: string | number | undefined): string {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n) || n <= 0) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = n;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size >= 10 || unit === 0 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

export function commandQualityLabel(metadata: BrowseItem['metadata'] | undefined): string {
  const tier = metadataValue(metadata, 'qualityTier', 'quality_tier');
  const score = metadataValue(metadata, 'qualityScore', 'quality_score');
  if (!tier) return '';
  return score ? `Quality ${tier} ${score}` : `Quality ${tier}`;
}

export function commandKpiLabel(metadata: BrowseItem['metadata'] | undefined): string {
  const status = metadataValue(metadata, 'kpiStatus', 'kpi_status');
  return status && status !== 'untested' ? status : '';
}

/** Curated, ordered metadata rows that read well across every file-backed category. */
export function fileItemRows(item: BrowseItem): Array<{ label: string; value: string }> {
  const m = item.metadata ?? {};
  const toolCount = m.tool_count ?? m.toolCount ?? '';
  const modified = m.modified || m.mtime;
  const hasAgentProjection = Boolean(
    metadataValue(item.metadata, 'source_model', 'sourceModel', 'codex_model', 'codexModel')
  );
  const rows: Array<{ label: string; value: string }> = [
    ...wikiMaintenanceRows(item),
    { label: 'Role', value: m.tier || m.role || '' },
    { label: 'Mode', value: m.mode || '' },
    { label: 'Master', value: metadataValue(item.metadata, 'master_client', 'masterClient', 'x-augur-master') },
    { label: 'Source model', value: metadataValue(item.metadata, 'source_model', 'sourceModel') },
    { label: 'Source tier', value: metadataValue(item.metadata, 'source_tier', 'sourceTier') },
    { label: 'Codex model', value: metadataValue(item.metadata, 'codex_model', 'codexModel') },
    { label: 'Codex sync', value: metadataValue(item.metadata, 'codex_sync_status', 'codexSyncStatus') },
    { label: 'Codex profile', value: metadataValue(item.metadata, 'codex_profile_path', 'codexProfilePath') },
    { label: 'Model', value: hasAgentProjection ? '' : m.model || '' },
    { label: 'Language', value: m.language || '' },
    { label: 'Methods', value: m.methods || '' },
    { label: 'Test type', value: m.test_type || '' },
    { label: 'Status', value: m.status || m.runtime_status || '' },
    { label: 'Quality', value: commandQualityLabel(item.metadata) },
    { label: 'Docs', value: metadataValue(item.metadata, 'docsScore', 'docs_score') },
    { label: 'Wiring', value: metadataValue(item.metadata, 'wiringScore', 'wiring_score') },
    { label: 'KPI', value: commandKpiLabel(item.metadata) },
    { label: 'Skill', value: m.skill || '' },
    { label: 'Bundle', value: m.bundle || '' },
    { label: 'Format', value: (m.format || '').toUpperCase() },
    { label: 'Scope', value: m.scope || m.vault_scope || '' },
    { label: 'Date', value: m.date || '' },
    { label: 'ADR', value: m.adr_number || '' },
    { label: 'Route', value: m.route || '' },
    { label: 'Tools', value: toolCount && toolCount !== '0' ? String(toolCount) : '' },
    { label: 'Size', value: humanizeBytes(m.size_bytes ?? m.sizeBytes) },
    { label: 'Path', value: item.path || item.primaryAction.target },
    { label: 'Modified', value: modified ? formatTimeAgo(modified) : '' },
  ];
  return rows.filter((row) => row.value);
}
