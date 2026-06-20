'use client';

import { useMemo } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { BLOCK_REGISTRY } from '@/lib/blocks/generated-block-registry';
import type { BlockManifest } from '@/lib/blocks/types';
import { buildCapabilityProfileSections } from '@/lib/capabilities/profile';
import { parseSkillSlug } from '@/lib/browse/skillSlug';
import type { SkillDetail, SkillAction, SkillCommand, SkillOwnership, SkillPrompt, SkillUpstream } from './types';

interface SkillMetaResponse {
  skill?: {
    id: string;
    hub: string;
    title: string;
    icon: string;
    description?: string;
    problemStatement?: string;
    source?: string;
    ownership?: SkillOwnership;
    upstream?: SkillUpstream | string;
    updateAvailable?: boolean;
  };
  actions?: SkillAction[];
  mcpTools?: Array<{ name: string; description?: string; schema?: Record<string, unknown> }>;
  prompts?: SkillPrompt[];
  commands?: SkillCommand[];
  health?: { status: string; lastCheck?: string; errors24h?: number };
  skillDoc?: { hasSkillMd: boolean; skillDoc?: string };
}

function normalizeOwnership(value: unknown): SkillOwnership {
  const ownership = typeof value === 'string' ? value.trim().toLowerCase() : '';
  if (ownership === 'external' || ownership === 'adopted' || ownership === 'user') return ownership;
  return 'augur';
}

function normalizeUpstream(value: unknown): SkillUpstream | undefined {
  if (!value) return undefined;
  if (typeof value === 'string') {
    const upstreamSource = value.trim();
    return upstreamSource ? { source: upstreamSource } : undefined;
  }
  if (typeof value !== 'object' || Array.isArray(value)) return undefined;

  const upstream = Object.entries(value as Record<string, unknown>).reduce<SkillUpstream>((acc, [key, rawValue]) => {
    if (rawValue === null || rawValue === undefined) return acc;
    if (typeof rawValue === 'string') {
      const trimmed = rawValue.trim();
      if (trimmed) acc[key] = trimmed;
      return acc;
    }
    if (typeof rawValue === 'number' || typeof rawValue === 'boolean') {
      acc[key] = String(rawValue);
      return acc;
    }
    return acc;
  }, {});

  return Object.keys(upstream).length > 0 ? upstream : undefined;
}

export function useSkillDetail(skillId: string | null): {
  detail: SkillDetail | null;
  loading: boolean;
  error: string | null;
} {
  // URL inputs can arrive as raw capability ids (`skill:<source>:<name>`) from
  // either the `/browse/[skill]` route param or the `?skill=<id>` query param.
  // Normalise to the bare folder name so `/api/skill-meta/[skillId]` and the
  // BLOCK_REGISTRY filter both see the value they actually index by.
  const lookupId = skillId ? parseSkillSlug(skillId).name : null;
  const { data, isLoading: loading, error: queryError } = useQuery<SkillMetaResponse>({
    queryKey: ['skill-detail', lookupId ?? '__none__'],
    queryFn: () => fetch(`/api/skill-meta/${encodeURIComponent(lookupId!)}`).then(r => {
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      return r.json();
    }),
    enabled: !!lookupId,
    staleTime: 600_000,
    placeholderData: keepPreviousData,
  });
  const error = queryError ? queryError.message : null;

  const blocks = useMemo<BlockManifest[]>(() => {
    if (!lookupId) return [];
    return Object.values(BLOCK_REGISTRY).filter(
      (block) => block.skill === lookupId,
    );
  }, [lookupId]);

  const detail = useMemo<SkillDetail | null>(() => {
    if (!lookupId || !data?.skill) return null;
    const upstream = normalizeUpstream(data.skill.upstream);
    const description = data.skill.description?.trim() || data.skill.title || lookupId;
    const actions = (data.actions ?? []).map((a: any) => ({
      id: a.id,
      label: a.title || a.label || a.id,
      icon: a.icon,
      description: a.description,
      dispatch: a.dispatch || 'ide',
      mcp_tools: a.mcp_tools,
    }));
    const prompts = data.prompts ?? [];
    const commands = data.commands ?? [];
    return {
      skillId: lookupId,
      hub: data.skill.hub,
      title: data.skill.title,
      icon: data.skill.icon,
      description,
      problemStatement: data.skill.problemStatement,
      ownership: normalizeOwnership(data.skill.ownership),
      source: data.skill.source,
      upstream,
      updateAvailable: data.skill.updateAvailable,
      blocks,
      actions,
      prompts,
      commands,
      capabilityProfileSections: buildCapabilityProfileSections({
        skillId: lookupId,
        description,
        tools: data.mcpTools ?? [],
        actions,
        prompts,
        commands,
        health: data.health,
      }),
      health: data.health,
      skillDoc: data.skillDoc?.skillDoc,
    };
  }, [lookupId, data, blocks]);

  return { detail, loading: !!lookupId && loading, error };
}
