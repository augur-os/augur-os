/**
 * RAG Projects Service
 *
 * OWNER: knowledge plugin
 * CONSUMERS: capture, knowledge
 *
 * Source: skills/knowledge/augur/lib/rag-projects.ts
 * Import via: direct relative path from skill source
 */
import crypto from 'crypto';
import fs from 'fs/promises';
import path from 'path';
import yaml from 'yaml';

import { AUGUR_ROOT } from '../../paths';
import type { RagProject, RagProjectSettings, RagSource } from '@/lib/shared-types';

// RAG data directory (markdown-based RAG)
const RAG_DATA_DIR = path.join(AUGUR_ROOT, 'services', 'rag');

type RagProjectsFile = {
  version: number;
  projects: Array<{
    id?: unknown;
    name?: unknown;
    created_at?: unknown;
    updated_at?: unknown;
  }>;
};

type RagSettingsFile = Partial<RagProjectSettings> & { version?: unknown };

type RagSourcesFile = {
  version: number;
  sources: Array<{
    path?: unknown;
    kind?: unknown;
    added_at?: unknown;
  }>;
};

const PROJECTS_FILE = path.join(RAG_DATA_DIR, 'projects.yaml');
const PROJECTS_DIR = path.join(RAG_DATA_DIR, 'projects');

export const DEFAULT_RAG_PROJECT_SETTINGS: RagProjectSettings = {
  index_mode: 'manual',
  limits: {
    max_file_size_mb: 50,
    max_total_size_mb: 2000,
    max_files: 1000,
  },
};

function toSafeString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function coercePositiveInt(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return fallback;
  const rounded = Math.round(value);
  return rounded > 0 ? rounded : fallback;
}

function normalizeIndexMode(value: unknown): RagProjectSettings['index_mode'] {
  return value === 'auto' ? 'auto' : 'manual';
}

function normalizeSettings(raw: RagSettingsFile | null): RagProjectSettings {
  const limits = (raw?.limits ?? {}) as Partial<RagProjectSettings['limits']>;
  return {
    index_mode: normalizeIndexMode(raw?.index_mode),
    limits: {
      max_file_size_mb: coercePositiveInt(limits?.max_file_size_mb, DEFAULT_RAG_PROJECT_SETTINGS.limits.max_file_size_mb),
      max_total_size_mb: coercePositiveInt(limits?.max_total_size_mb, DEFAULT_RAG_PROJECT_SETTINGS.limits.max_total_size_mb),
      max_files: coercePositiveInt(limits?.max_files, DEFAULT_RAG_PROJECT_SETTINGS.limits.max_files),
    },
  };
}

function slugifyName(value: string): string {
  const trimmed = value.trim().toLowerCase();
  if (!trimmed) return '';
  const slug = trimmed
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+/, '')
    .replace(/-+$/, '')
    .replace(/-{2,}/g, '-');
  return slug;
}

function uniqueProjectId(base: string, existing: Set<string>): string {
  const normalized = base.trim();
  if (normalized && !existing.has(normalized)) return normalized;

  let candidate = normalized || crypto.randomBytes(3).toString('hex');
  while (existing.has(candidate)) {
    candidate = `${normalized || 'rag'}-${crypto.randomBytes(3).toString('hex')}`;
  }
  return candidate;
}

function projectDir(projectId: string): string {
  return path.join(PROJECTS_DIR, projectId);
}

export function projectSourcesFilePath(projectId: string): string {
  return path.join(projectDir(projectId), 'sources.yaml');
}

export function projectSettingsFilePath(projectId: string): string {
  return path.join(projectDir(projectId), 'settings.yaml');
}

export function projectDataDir(projectId: string): string {
  return projectDir(projectId);
}

export async function readProjectSettings(projectId: string): Promise<RagProjectSettings> {
  try {
    const raw = await fs.readFile(projectSettingsFilePath(projectId), 'utf8');
    const parsed = yaml.parse(raw) as RagSettingsFile | null;
    return normalizeSettings(parsed);
  } catch {
    return { ...DEFAULT_RAG_PROJECT_SETTINGS, limits: { ...DEFAULT_RAG_PROJECT_SETTINGS.limits } };
  }
}

export async function writeProjectSettings(projectId: string, settings: RagProjectSettings): Promise<void> {
  await fs.mkdir(projectDir(projectId), { recursive: true });
  const payload = { version: 1, ...settings };
  await fs.writeFile(projectSettingsFilePath(projectId), yaml.stringify(payload), 'utf8');
}

async function readProjectsFile(): Promise<RagProjectsFile> {
  try {
    const raw = await fs.readFile(PROJECTS_FILE, 'utf8');
    const parsed = yaml.parse(raw) as RagProjectsFile | null;
    if (!parsed || typeof parsed !== 'object') return { version: 1, projects: [] };
    return {
      version: 1,
      projects: Array.isArray(parsed.projects) ? parsed.projects : [],
    };
  } catch {
    return { version: 1, projects: [] };
  }
}

async function writeProjectsFile(file: RagProjectsFile): Promise<void> {
  await fs.mkdir(RAG_DATA_DIR, { recursive: true });
  await fs.writeFile(PROJECTS_FILE, yaml.stringify(file), 'utf8');
}

export async function listRagProjects(): Promise<RagProject[]> {
  const file = await readProjectsFile();
  const projects: RagProject[] = [];

  for (const entry of file.projects) {
    if (!entry || typeof entry !== 'object') continue;
    const id = toSafeString(entry.id);
    const name = toSafeString(entry.name);
    if (!id || !name) continue;

    const created_at = toSafeString(entry.created_at) || new Date().toISOString();
    const updated_at = toSafeString(entry.updated_at) || undefined;
    const settings = await readProjectSettings(id);

    projects.push({
      id,
      name,
      created_at,
      updated_at,
      index_mode: settings.index_mode,
      limits: settings.limits,
    });
  }

  projects.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }));
  return projects;
}

export async function createRagProject(name: string): Promise<RagProject> {
  const trimmed = name.trim();
  if (!trimmed) {
    throw new Error('Project name is required');
  }

  const file = await readProjectsFile();
  const existingIds = new Set(
    file.projects
      .map((project) => toSafeString(project?.id))
      .filter(Boolean),
  );

  const base = slugifyName(trimmed);
  const projectId = uniqueProjectId(base, existingIds);
  const timestamp = new Date().toISOString();

  file.projects.push({
    id: projectId,
    name: trimmed,
    created_at: timestamp,
    updated_at: timestamp,
  });

  await writeProjectsFile(file);

  const settings = { ...DEFAULT_RAG_PROJECT_SETTINGS, limits: { ...DEFAULT_RAG_PROJECT_SETTINGS.limits } };
  await writeProjectSettings(projectId, settings);

  const sourcesFile: RagSourcesFile = { version: 1, sources: [] };
  await fs.mkdir(projectDir(projectId), { recursive: true });
  await fs.writeFile(projectSourcesFilePath(projectId), yaml.stringify(sourcesFile), 'utf8');

  return {
    id: projectId,
    name: trimmed,
    created_at: timestamp,
    updated_at: timestamp,
    index_mode: settings.index_mode,
    limits: settings.limits,
  };
}

export async function updateRagProjectSettings(
  projectId: string,
  updates: Partial<RagProjectSettings>,
): Promise<RagProjectSettings> {
  const file = await readProjectsFile();
  const exists = file.projects.some((project) => toSafeString(project?.id) === projectId);
  if (!exists) {
    throw new Error('Project not found');
  }

  const current = await readProjectSettings(projectId);
  const next = normalizeSettings({
    ...current,
    ...updates,
    limits: {
      ...current.limits,
      ...(updates.limits ?? {}),
    },
  });

  await writeProjectSettings(projectId, next);

  let updated = false;
  const nextProjects = file.projects.map((project) => {
    if (!project || typeof project !== 'object') return project;
    const id = toSafeString(project.id);
    if (id !== projectId) return project;
    updated = true;
    return {
      ...project,
      updated_at: new Date().toISOString(),
    };
  });
  if (updated) {
    await writeProjectsFile({ version: 1, projects: nextProjects });
  }

  return next;
}

export async function readProjectSources(projectId: string): Promise<RagSource[]> {
  try {
    const raw = await fs.readFile(projectSourcesFilePath(projectId), 'utf8');
    const parsed = yaml.parse(raw) as RagSourcesFile | null;
    if (!parsed || typeof parsed !== 'object') return [];
    if (!Array.isArray(parsed.sources)) return [];
    return parsed.sources
      .map((source) => {
        if (!source || typeof source !== 'object') return null;
        const pathValue = toSafeString(source.path);
        if (!pathValue) return null;
        const kind = source.kind === 'file' ? 'file' : 'dir';
        return {
          path: pathValue,
          kind,
          added_at: toSafeString(source.added_at) || new Date().toISOString(),
        } satisfies RagSource;
      })
      .filter((source): source is RagSource => Boolean(source));
  } catch {
    return [];
  }
}

export async function writeProjectSources(projectId: string, sources: RagSource[]): Promise<void> {
  await fs.mkdir(projectDir(projectId), { recursive: true });
  const file: RagSourcesFile = { version: 1, sources };
  await fs.writeFile(projectSourcesFilePath(projectId), yaml.stringify(file), 'utf8');
}
