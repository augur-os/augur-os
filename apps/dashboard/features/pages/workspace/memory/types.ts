import type { LucideIcon } from 'lucide-react';
import type { BrainDataSource, BrainDataSources, BrainOperationNotice } from './contracts';

export interface MemoryStats {
  totalDecisions: number;
  totalPatterns: number;
  totalPreferences: number;
  dailyLogs: number;
  lastCurated: string | null;
  recentDecisions: DecisionEntry[];
  categoryCounts?: Record<string, number>;
}

export interface DecisionEntry {
  topic: string;
  decision: string;
  category: string;
  date: string;
  confidence: string;
}

export interface MemorySearchResult {
  content: string;
  source: string;
  category: string;
  date: string;
  relevance: number;
  file_path?: string;
  line_number?: number;
}

export interface MemorySearchFilters {
  category?: string | null;
  source?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
}

export interface PluginCategory {
  id: string;
  name: string;
  icon: string;
  color: string;
  bundle: string;
  count?: number;
}

export interface HumanApiProfile {
  exists: boolean;
  role: string;
  expertise: string[];
  communicationStyle: string;
  successCriteria: string[];
  contextGaps: string[];
  lastUpdated: string | null;
  rawContent: string;
}

export interface DailyLogsPayload {
  logs: DailyLogInfo[];
  source?: BrainDataSource | null;
  generatedAt?: string | null;
  error?: string | null;
  success?: boolean;
  details?: unknown;
}

export interface DailyLogContentPayload {
  content: string;
  preview?: string | null;
  kindCounts?: Record<string, number> | null;
  source?: BrainDataSource | null;
  generatedAt?: string | null;
  error?: string | null;
  success?: boolean;
  details?: unknown;
}

export interface DailyLogInfo {
  date: string;
  hasLog: boolean;
  entryCount: number;
  preview?: string | null;
  kindCounts?: Record<string, number> | null;
  modifiedAt?: string | null;
}

export interface MemoryWorkspaceItem {
  id: string;
  label: string;
  description: string;
  kind: 'markdown' | 'html' | 'yaml' | 'json' | 'text' | 'file' | 'directory';
  path: string;
  exists: boolean;
  sizeBytes: number | null;
  modifiedAt: string | null;
  entryCount?: number;
  source?: string;
  relativePath?: string;
}

export interface MemoryWorkspace {
  rootPath: string;
  files: MemoryWorkspaceItem[];
  allFiles?: MemoryWorkspaceItem[];
}

export interface MemoryReport {
  exists: boolean;
  path: string;
  title: string | null;
  modifiedAt: string | null;
  sizeBytes: number | null;
  html: string | null;
}

export interface MemoryBootstrapPayload {
  stats: MemoryStats;
  categories: PluginCategory[];
  workspace: MemoryWorkspace | null;
  report: MemoryReport | null;
  sources?: BrainDataSources;
}

export interface WikiRewriteCandidate {
  page: string;
  title: string;
  hub: string;
  quality_score: number;
  reasons: string[];
}

export interface WikiMaintenanceSummary {
  avgQualityScore: number;
  rewriteCandidates: number;
  avgOutgoingLinksPerPage: number;
  isolatedPages: number;
}

export interface MemoryStatItem {
  label: string;
  valueKey: keyof Pick<MemoryStats, 'totalDecisions' | 'totalPatterns' | 'totalPreferences' | 'dailyLogs'>;
  icon: LucideIcon;
  color: string;
}

export type { BrainDataSource, BrainDataSources, BrainOperationNotice };
