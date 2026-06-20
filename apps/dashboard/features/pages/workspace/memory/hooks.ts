'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { usePageActionsData } from '@/features/hooks/usePageActionsData';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import { mcpCall } from '@/lib/mcp/client';
import {
  asBrainDataSource,
  assertMcpSuccess,
  formatOperationError,
  makeNotice,
} from './contracts';
import { formatDateKey } from '../daily-logs/date-utils';
import type {
  BrainDataSources,
  BrainOperationNotice,
  DailyLogContentPayload,
  DailyLogsPayload,
  MemoryBootstrapPayload,
  MemoryStats,
  PluginCategory,
  HumanApiProfile,
  DailyLogInfo,
  MemorySearchFilters,
  MemorySearchResult,
  MemoryWorkspace,
  MemoryReport,
  WikiMaintenanceSummary,
  WikiRewriteCandidate,
} from './types';

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function asBrainDataSourceValue(value: unknown) {
  return asBrainDataSource(value);
}

function asNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return fallback;
}

function normalizeDecisionEntries(value: unknown): MemoryStats['recentDecisions'] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((entry): entry is MemoryStats['recentDecisions'][number] => !!entry && typeof entry === 'object') as MemoryStats['recentDecisions'];
}

function normalizeCategoryCounts(value: unknown): MemoryStats['categoryCounts'] {
  if (!isRecord(value)) {
    return undefined;
  }

  const categoryCounts = Object.entries(value).reduce<Record<string, number>>((acc, [key, count]) => {
    const numeric = asNumber(count, Number.NaN);
    if (Number.isFinite(numeric)) {
      acc[key] = numeric;
    }
    return acc;
  }, {});

  return Object.keys(categoryCounts).length > 0 ? categoryCounts : undefined;
}

function normalizeMemoryStats(value: unknown): MemoryStats | null {
  if (!isRecord(value)) {
    return null;
  }

  const statsSource = isRecord(value.stats) ? value.stats : value;

  return {
    totalDecisions: asNumber(statsSource.totalDecisions),
    totalPatterns: asNumber(statsSource.totalPatterns),
    totalPreferences: asNumber(statsSource.totalPreferences),
    dailyLogs: asNumber(statsSource.dailyLogs),
    lastCurated: asString(statsSource.lastCurated),
    recentDecisions: normalizeDecisionEntries(statsSource.recentDecisions),
    categoryCounts: normalizeCategoryCounts(statsSource.categoryCounts),
  };
}

function normalizeCategories(value: unknown): PluginCategory[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is PluginCategory => !!item && typeof item === 'object') as PluginCategory[];
}

function normalizeWorkspacePayload(value: unknown): MemoryWorkspace | null {
  if (!isRecord(value)) {
    return null;
  }

  const workspace = isRecord(value.workspace) ? value.workspace : value;
  if (typeof workspace.rootPath !== 'string' || !Array.isArray(workspace.files)) {
    return null;
  }

  return {
    rootPath: workspace.rootPath,
    files: workspace.files.filter((item): item is MemoryWorkspace['files'][number] => !!item && typeof item === 'object') as MemoryWorkspace['files'],
  };
}

function normalizeReportPayload(value: unknown): MemoryReport | null {
  if (!isRecord(value)) {
    return null;
  }

  const report = isRecord(value.report) ? value.report : value;
  if (typeof report.path !== 'string') {
    return null;
  }

  return {
    exists: Boolean(report.exists),
    path: report.path,
    title: asString(report.title),
    modifiedAt: asString(report.modifiedAt),
    sizeBytes: typeof report.sizeBytes === 'number' ? report.sizeBytes : null,
    html: asString(report.html),
  };
}

function normalizeBootstrapPayload(value: unknown): MemoryBootstrapPayload | null {
  if (!isRecord(value)) {
    return null;
  }

  const stats = normalizeMemoryStats(value);
  if (!Array.isArray(value.categories)) {
    return null;
  }

  const categories = normalizeCategories(value.categories);

  if (!stats) {
    return null;
  }

  return {
    stats,
    categories,
    workspace: normalizeWorkspacePayload(value.workspace),
    report: normalizeReportPayload(value.report),
    sources: isRecord(value.sources) ? (value.sources as BrainDataSources) : undefined,
  };
}

function toBootstrapPayload(value: unknown): MemoryBootstrapPayload | null {
  return normalizeBootstrapPayload(value);
}

function toWikiMaintenanceSummary(value: unknown): WikiMaintenanceSummary {
  if (!value || typeof value !== 'object') {
    return {
      avgQualityScore: 0,
      rewriteCandidates: 0,
      avgOutgoingLinksPerPage: 0,
      isolatedPages: 0,
    };
  }

  const obj = value as { stats?: Record<string, unknown> };
  const stats = obj.stats;
  if (!stats || typeof stats !== 'object') {
    return {
      avgQualityScore: 0,
      rewriteCandidates: 0,
      avgOutgoingLinksPerPage: 0,
      isolatedPages: 0,
    };
  }

  return {
    avgQualityScore: Number(stats.avg_quality_score ?? 0),
    rewriteCandidates: Number(stats.rewrite_candidates ?? 0),
    avgOutgoingLinksPerPage: Number(stats.avg_outgoing_links_per_page ?? 0),
    isolatedPages: Number(stats.isolated_pages ?? 0),
  };
}

function toWikiRewriteCandidates(value: unknown): { candidates: WikiRewriteCandidate[]; total: number } {
  if (!value || typeof value !== 'object') {
    return { candidates: [], total: 0 };
  }

  const obj = value as { candidates?: unknown; total?: unknown; count?: unknown };
  const candidates = Array.isArray(obj.candidates)
    ? (obj.candidates.filter((item): item is WikiRewriteCandidate => !!item && typeof item === 'object') as WikiRewriteCandidate[])
    : [];

  return {
    candidates,
    total: Number(obj.total ?? obj.count ?? candidates.length),
  };
}

export function useMemoryDashboardData() {
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [categories, setCategories] = useState<PluginCategory[]>([]);
  const [workspace, setWorkspace] = useState<MemoryWorkspace | null>(null);
  const [report, setReport] = useState<MemoryReport | null>(null);
  const [sources, setSources] = useState<BrainDataSources | undefined>(undefined);
  const [isStatsLoading, setIsStatsLoading] = useState(true);
  const [isWorkspaceLoading, setIsWorkspaceLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<BrainOperationNotice | null>(null);
  const bootstrapLoaded = useRef(false);

  const applyBootstrap = useCallback((payload: MemoryBootstrapPayload | null) => {
    if (!payload) return;
    setStats(payload.stats);
    setWorkspace(payload.workspace);
    setReport(payload.report);
    setSources(payload.sources);
    const categoriesWithCounts = payload.categories.map((category) => ({
      ...category,
      count: asNumber(category.count, payload.stats.categoryCounts?.[category.id] || 0),
    }));
    setCategories(categoriesWithCounts);
  }, []);

  const refreshAll = useCallback(async () => {
    setError(null);
    setNotice(null);
    setIsStatsLoading(true);
    setIsWorkspaceLoading(true);
    try {
      const data = assertMcpSuccess(await mcpCall<unknown>('knowledge-memory-read', { mode: 'bootstrap' }), 'Load memory bootstrap');
      const payload = toBootstrapPayload(data);
      if (!payload) {
        throw new Error('Invalid memory dashboard payload');
      }
      applyBootstrap(payload);
      bootstrapLoaded.current = true;
      setNotice(makeNotice('success', 'Memory dashboard loaded.'));
    } catch (error) {
      const message = formatOperationError('Load memory dashboard', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    } finally {
      setIsStatsLoading(false);
      setIsWorkspaceLoading(false);
    }
  }, [applyBootstrap]);

  useEffect(() => {
    if (bootstrapLoaded.current) return;
    void refreshAll();
  }, [refreshAll]);

  const refreshStats = useCallback(async () => {
    setIsStatsLoading(true);
    setError(null);
    setNotice(null);
    try {
      const [statsData, categoriesData] = await Promise.all([
        mcpCall<unknown>('knowledge-memory-read', { mode: 'stats' }),
        mcpCall<unknown>('knowledge-memory-read', { mode: 'categories' }),
      ]);
      const normalizedStats = normalizeMemoryStats(assertMcpSuccess(statsData, 'Load memory stats'));
      const normalizedCategoriesPayload = assertMcpSuccess(categoriesData, 'Load memory categories');
      if (!normalizedStats) {
        throw new Error('Invalid memory stats payload');
      }
      const categorySource = isRecord(normalizedCategoriesPayload) && Array.isArray(normalizedCategoriesPayload.categories)
        ? normalizedCategoriesPayload.categories
        : [];
      setStats(normalizedStats);
      const categoriesWithCounts = normalizeCategories(categorySource).map((category) => ({
        ...category,
        count: asNumber(category.count, normalizedStats.categoryCounts?.[category.id] || 0),
      }));
      setCategories(categoriesWithCounts);
      if (isRecord(normalizedCategoriesPayload) && isRecord(normalizedCategoriesPayload.sources)) {
        setSources(normalizedCategoriesPayload.sources as BrainDataSources);
      }
      setNotice(makeNotice('success', 'Memory stats refreshed.'));
    } catch (error) {
      const message = formatOperationError('Refresh memory stats', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    } finally {
      setIsStatsLoading(false);
    }
  }, []);

  const refreshWorkspace = useCallback(async () => {
    setIsWorkspaceLoading(true);
    setError(null);
    setNotice(null);
    try {
      const [workspaceData, reportData] = await Promise.all([
        mcpCall<unknown>('knowledge-memory-read', { mode: 'workspace' }),
        mcpCall<unknown>('knowledge-memory-read', { mode: 'report' }),
      ]);
      const normalizedWorkspace = assertMcpSuccess(workspaceData, 'Load memory workspace');
      const normalizedReport = assertMcpSuccess(reportData, 'Load memory report');
      if (isRecord(normalizedWorkspace)) {
        setWorkspace((normalizedWorkspace.workspace as MemoryWorkspace | null) ?? null);
        if (isRecord(normalizedWorkspace.sources)) {
          setSources(normalizedWorkspace.sources as BrainDataSources);
        }
      }
      if (isRecord(normalizedReport)) {
        setReport((normalizedReport.report as MemoryReport | null) ?? null);
        if (isRecord(normalizedReport.sources)) {
          setSources(normalizedReport.sources as BrainDataSources);
        }
      }
      setNotice(makeNotice('success', 'Memory workspace refreshed.'));
    } catch (error) {
      const message = formatOperationError('Refresh memory workspace', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    } finally {
      setIsWorkspaceLoading(false);
    }
  }, []);

  const openWorkspaceFile = useCallback(async (fileId: string) => {
    setError(null);
    setNotice(null);
    try {
      const response = await mcpCall<unknown>('knowledge-memory-workspace-open', { fileId });
      assertMcpSuccess(response, 'Open memory workspace file');
      setNotice(makeNotice('success', `Opened workspace file ${fileId}.`));
    } catch (error) {
      const message = formatOperationError('Open memory workspace file', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    }
  }, []);

  return {
    stats,
    categories,
    workspace,
    report,
    sources,
    error,
    notice,
    isStatsLoading,
    isWorkspaceLoading,
    refreshAll,
    refreshStats,
    refreshWorkspace,
    openWorkspaceFile,
  };
}

export function useProfile() {
  const [profile, setProfile] = useState<HumanApiProfile | null>(null);
  const [editedProfile, setEditedProfile] = useState<HumanApiProfile | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<BrainOperationNotice | null>(null);

  const fetchProfile = useCallback(async () => {
    try {
      setError(null);
      const data = assertMcpSuccess(await mcpCall<unknown>('knowledge-memory-profile', {}), 'Load profile');
      if (isRecord(data)) {
        const nextProfile = data as unknown as HumanApiProfile;
        setProfile(nextProfile);
        setEditedProfile(nextProfile);
      }
    } catch (error) {
      const message = formatOperationError('Load profile', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchProfile();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchProfile]);

  const saveProfile = async () => {
    if (!editedProfile) return false;
    setIsSaving(true);
    setError(null);
    setNotice(null);
    try {
      const response = await mcpCall<unknown>('knowledge-memory-profile', { action: 'update', ...editedProfile });
      assertMcpSuccess(response, 'Save profile');
      setProfile(editedProfile);
      setIsEditing(false);
      setNotice(makeNotice('success', 'Profile saved.'));
      return true;
    } catch (error) {
      const message = formatOperationError('Save profile', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    } finally {
      setIsSaving(false);
    }
    return false;
  };

  const regenerateProfile = async () => {
    setIsRegenerating(true);
    try {
      setError(null);
      setNotice(null);
      const response = await mcpCall<unknown>('memory-profile-regenerate');
      assertMcpSuccess(response, 'Regenerate profile');
      await fetchProfile();
      setNotice(makeNotice('success', 'Profile regenerated.'));
      return true;
    } catch (error) {
      const message = formatOperationError('Regenerate profile', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    } finally {
      setIsRegenerating(false);
    }
    return false;
  };

  const cancelEdit = () => {
    setEditedProfile(profile);
    setIsEditing(false);
  };

  return {
    profile, editedProfile, setEditedProfile,
    isEditing, setIsEditing, isSaving, isRegenerating,
    saveProfile, regenerateProfile, cancelEdit,
    notice,
    error,
  };
}

export function useMemoryWorkspace() {
  const [workspace, setWorkspace] = useState<MemoryWorkspace | null>(null);
  const [report, setReport] = useState<MemoryReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [openingFileId, setOpeningFileId] = useState<string | null>(null);
  const [notice, setNotice] = useState<BrainOperationNotice | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkspace = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setNotice(null);
    try {
      const [workspaceData, reportData] = await Promise.all([
        mcpCall<unknown>('knowledge-memory-read', { mode: 'workspace' }),
        mcpCall<unknown>('knowledge-memory-read', { mode: 'report' }),
      ]);
      const normalizedWorkspace = assertMcpSuccess(workspaceData, 'Load memory workspace');
      const normalizedReport = assertMcpSuccess(reportData, 'Load memory report');
      setWorkspace(normalizeWorkspacePayload(normalizedWorkspace));
      setReport(normalizeReportPayload(normalizedReport));
      setNotice(makeNotice('success', 'Memory workspace loaded.'));
    } catch (error) {
      const message = formatOperationError('Load memory workspace', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchWorkspace();
  }, [fetchWorkspace]);

  const openWorkspaceFile = async (fileId: string) => {
    setOpeningFileId(fileId);
    setError(null);
    setNotice(null);
    try {
      const response = await mcpCall<unknown>('knowledge-memory-workspace-open', { fileId });
      assertMcpSuccess(response, 'Open memory workspace file');
      setNotice(makeNotice('success', `Opened workspace file ${fileId}.`));
    } catch (error) {
      const message = formatOperationError('Open memory workspace file', error);
      console.error(message);
      setError(message);
      setNotice(makeNotice('error', message));
    } finally {
      setOpeningFileId(null);
    }
  };

  return {
    workspace,
    report,
    isLoading,
    openingFileId,
    refreshWorkspace: fetchWorkspace,
    openWorkspaceFile,
    notice,
    error,
  };
}

export function useMemoryReportAction(pathname: string | null) {
  const { buttons } = usePageActionsData({ pathname });
  return buttons.find((button) => button.id === 'regenerate-memory-report') ?? null;
}

export function useWikiMaintenanceData() {
  const reportQuery = useMcpQuery<WikiMaintenanceSummary>(
    'wiki-maintenance-report',
    'wiki-report-data',
    'user-data',
    {
      args: { lightweight: true },
      select: (raw) => toWikiMaintenanceSummary(raw),
    },
  );
  const candidateQuery = useMcpQuery<{ candidates: WikiRewriteCandidate[]; total: number }>(
    'wiki-rewrite-candidates',
    'wiki-rewrite-candidates',
    'user-data',
    {
      args: { limit: 5 },
      select: (raw) => toWikiRewriteCandidates(raw),
    },
  );

  return {
    summary: reportQuery.data,
    candidates: candidateQuery.data?.candidates ?? [],
    totalCandidates: candidateQuery.data?.total ?? 0,
    isLoading: reportQuery.loading || candidateQuery.loading,
    error: reportQuery.error || candidateQuery.error,
    refetch: () => {
      reportQuery.refetch();
      candidateQuery.refetch();
    },
  };
}

export function useDailyLogs() {
  const [calendarMonth, setCalendarMonth] = useState(new Date());
  const [selectedLog, setSelectedLog] = useState<string | null>(null);
  const [openingSelectedLog, setOpeningSelectedLog] = useState(false);
  const [openLogError, setOpenLogError] = useState<string | null>(null);

  // Fetch list of daily logs (mount-time, cached)
  const { data: logsData, error: listError, loading: isListLoading } = useMcpQuery<DailyLogsPayload>(
    'daily-logs-list',
    'knowledge-memory-daily-logs',
    'user-data',
    {
      select: (raw) => {
        const payload = assertMcpSuccess(raw, 'Load daily logs');
        if (!isRecord(payload) || !Array.isArray(payload.logs)) {
          throw new Error('Invalid daily log list payload');
        }
        return {
          logs: payload.logs.filter((log): log is DailyLogInfo => !!log && typeof log === 'object') as DailyLogInfo[],
          source: asBrainDataSourceValue(payload.source),
          generatedAt: asString(payload.generatedAt),
          error: asString(payload.error),
          success: typeof payload.success === 'boolean' ? payload.success : undefined,
          details: payload.details,
        };
      },
    },
  );
  const dailyLogs = logsData?.logs ?? [];

  // Fetch content for selected date (on-demand, cached by date)
  const { data: logData, error: contentError, loading: isContentLoading } = useMcpQuery<DailyLogContentPayload>(
    ['daily-log-content', selectedLog ?? ''],
    'knowledge-memory-daily-logs-read',
    'user-data',
    {
      args: { date: selectedLog ?? '' },
      enabled: !!selectedLog,
      select: (raw) => {
        const payload = assertMcpSuccess(raw, 'Load daily log content');
        if (!isRecord(payload) || typeof payload.content !== 'string') {
          throw new Error('Invalid daily log content payload');
        }
        return {
          content: payload.content,
          preview: asString(payload.preview),
          kindCounts: isRecord(payload.kindCounts)
            ? Object.entries(payload.kindCounts).reduce<Record<string, number>>((acc, [key, value]) => {
                if (typeof value === 'number') {
                  acc[key] = value;
                }
                return acc;
              }, {})
            : null,
          source: asBrainDataSourceValue(payload.source),
          generatedAt: asString(payload.generatedAt),
          error: asString(payload.error),
          success: typeof payload.success === 'boolean' ? payload.success : undefined,
          details: payload.details,
        };
      },
    },
  );
  const logContent = logData?.content ?? '';
  const source = logData?.source ?? logsData?.source ?? null;
  const generatedAt = logData?.generatedAt ?? logsData?.generatedAt ?? null;
  const logError = logData?.error ?? logsData?.error ?? contentError ?? listError ?? null;
  const isLogLoading = isListLoading || isContentLoading;

  const fetchLogContent = (date: string) => {
    setSelectedLog(date);
  };

  const clearSelection = () => {
    setSelectedLog(null);
  };

  const openSelectedLog = async () => {
    if (!selectedLog) return;
    setOpeningSelectedLog(true);
    setOpenLogError(null);
    try {
      const response = await mcpCall<unknown>('knowledge-memory-daily-logs-open', { date: selectedLog });
      assertMcpSuccess(response, 'Open selected daily log');
    } catch (error) {
      const message = formatOperationError('Open selected daily log', error);
      console.error(message);
      setOpenLogError(message);
    } finally {
      setOpeningSelectedLog(false);
    }
  };

  const hasLogForDate = (date: Date) => {
    const dateStr = formatDateKey(date);
    return dailyLogs.some(log => log.date === dateStr && log.hasLog);
  };

  const getLogEntryCount = (date: Date) => {
    const dateStr = formatDateKey(date);
    const log = dailyLogs.find(l => l.date === dateStr);
    return log?.entryCount || 0;
  };

  const getCalendarDays = () => {
    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startPadding = firstDay.getDay();
    const days: (Date | null)[] = [];

    for (let i = 0; i < startPadding; i++) {
      days.push(null);
    }
    for (let d = 1; d <= lastDay.getDate(); d++) {
      days.push(new Date(year, month, d));
    }
    return days;
  };

  return {
    calendarMonth, setCalendarMonth,
    dailyLogs, selectedLog, logContent,
    source,
    generatedAt,
    logError,
    isLogLoading,
    openSelectedLog,
    openingSelectedLog,
    openLogError,
    fetchLogContent, clearSelection,
    hasLogForDate, getLogEntryCount, getCalendarDays,
  };
}

export function useMemorySearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<MemorySearchResult[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [openingResultPath, setOpeningResultPath] = useState<string | null>(null);
  const [openResultError, setOpenResultError] = useState<string | null>(null);

  const handleSearch = async (
    queryOverride?: string,
    filters?: MemorySearchFilters,
  ) => {
    const query = (queryOverride ?? searchQuery).trim();
    if (!query) return;
    if (queryOverride && queryOverride !== searchQuery) {
      setSearchQuery(queryOverride);
    }
    setIsSearching(true);
    setSearchError(null);
    setHasSearched(true);
    try {
      const data = await mcpCall<unknown>('memory-search', {
        query,
        mode: 'hybrid',
        top_k: 10,
        ...(filters?.category ? { category: filters.category } : {}),
        ...(filters?.source ? { source: filters.source } : {}),
        ...(filters?.dateFrom ? { date_from: filters.dateFrom } : {}),
        ...(filters?.dateTo ? { date_to: filters.dateTo } : {}),
      });
      const payload = assertMcpSuccess(data, 'Search memory');
      if (!isRecord(payload)) {
        throw new Error('Invalid memory search payload');
      }
      if (typeof payload.error === 'string' && payload.error.trim()) {
        throw new Error(payload.error);
      }
      const results = Array.isArray(payload.results)
        ? (payload.results.filter((result): result is MemorySearchResult => !!result && typeof result === 'object') as MemorySearchResult[])
        : [];
      setSearchResults(results);
    } catch (error) {
      const message = formatOperationError('Search memory', error);
      console.error(message);
      setSearchError(message);
    } finally {
      setIsSearching(false);
    }
  };

  const openSearchResult = async (result: MemorySearchResult) => {
    if (!result.file_path) {
      return;
    }

    setOpeningResultPath(result.file_path);
    setOpenResultError(null);
    try {
      const response = await mcpCall<unknown>('knowledge-memory-workspace-open', {
        path: result.file_path,
      });
      assertMcpSuccess(response, 'Open memory search result');
    } catch (error) {
      const message = formatOperationError('Open memory search result', error);
      console.error(message);
      setOpenResultError(message);
    } finally {
      setOpeningResultPath(null);
    }
  };

  return {
    searchQuery,
    setSearchQuery,
    isSearching,
    searchResults,
    hasSearched,
    searchError,
    handleSearch,
    openSearchResult,
    openingResultPath,
    openResultError,
  };
}
