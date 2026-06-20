import path from "path";

import {
  getManagedSkillDirs,
  getProjectBrainSkillsRoot,
} from "@/lib/plugin-discovery/paths";

export type ManagedSkillSource = {
  absoluteRoot: string;
  displayBaseDir: string;
};

const RETIRED_REPO_ROOT_SKILL_SEGMENTS = ["skills"];

function normalizePath(value: string): string {
  return path.resolve(value);
}

function samePath(left: string, right: string): boolean {
  return normalizePath(left) === normalizePath(right);
}

function isRepoRootSkillsDir(repoRoot: string, absoluteRoot: string): boolean {
  return samePath(
    absoluteRoot,
    path.join(repoRoot, ...RETIRED_REPO_ROOT_SKILL_SEGMENTS),
  );
}

function sourceForDir(
  repoRoot: string,
  absoluteRoot: string,
): ManagedSkillSource {
  const projectSkillsRoot = getProjectBrainSkillsRoot(repoRoot);
  const displayBaseDir =
    samePath(absoluteRoot, projectSkillsRoot)
      ? "project-brain/capabilities/skills"
      : absoluteRoot;

  return {
    absoluteRoot,
    displayBaseDir,
  };
}

function dedupeSources(
  repoRoot: string,
  roots: string[],
): ManagedSkillSource[] {
  const seen = new Set<string>();
  const sources: ManagedSkillSource[] = [];

  for (const root of roots) {
    const absoluteRoot = normalizePath(root);
    if (isRepoRootSkillsDir(repoRoot, absoluteRoot)) continue;
    if (seen.has(absoluteRoot)) continue;
    seen.add(absoluteRoot);
    sources.push(sourceForDir(repoRoot, absoluteRoot));
  }

  return sources;
}

export function getManagedSkillSourcesInScanOrder(
  repoRoot: string,
): ManagedSkillSource[] {
  return dedupeSources(repoRoot, Object.values(getManagedSkillDirs(repoRoot)));
}

export function getManagedSkillSourcesInPriorityOrder(
  repoRoot: string,
): ManagedSkillSource[] {
  return [...getManagedSkillSourcesInScanOrder(repoRoot)].reverse();
}
