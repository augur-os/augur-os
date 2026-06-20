import Link from "next/link";

import Markdown from "@/components/Markdown";
import DisabledSkillPage from "@/components/DisabledSkillPage";
import { getSkillAugurDataPath } from "@/lib/paths";
import { CORE_SKILLS, readDisabledSkills } from "@/lib/server/skillsState";
import {
  resolveSkillInfo,
  normalizeSlug,
  parseSkillSlug,
  stripAutoHeader,
} from "@/lib/server/skillsLookup";
import { getRepoRoot } from "@/lib/server/repo";
import { loadSkillReadme } from "@/lib/server/skillReadme";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function extractTitle(markdown: string, fallback: string) {
  const content = stripAutoHeader(markdown);
  const match = content.match(/^#\s+(.+)$/m);
  return match?.[1]?.trim() || fallback;
}

export default async function SkillPage({
  params,
}: {
  params: { skill: string };
}) {
  const { skill } = await params;
  const { name: lookupName } = parseSkillSlug(skill);
  const [disabled, resolved] = await Promise.all([
    readDisabledSkills(),
    resolveSkillInfo(lookupName),
  ]);
  const canonicalId = resolved?.canonicalId || lookupName;
  const normalizedCanonical = normalizeSlug(canonicalId);
  const normalizedDisabled = new Set(Array.from(disabled).map(normalizeSlug));

  if (
    !CORE_SKILLS.has(canonicalId) &&
    normalizedDisabled.has(normalizedCanonical)
  ) {
    return <DisabledSkillPage skill={lookupName} title={canonicalId} />;
  }

  const { sourcePath, markdown } = await loadSkillReadme(getRepoRoot(), lookupName);
  const title = extractTitle(markdown, canonicalId);
  const body = stripAutoHeader(markdown);
  const dataDir = getSkillAugurDataPath(canonicalId);

  return (
    <div className="space-y-6">
      <header className="space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            href="/browse"
            className="ui-button ui-button-sm"
            title="Skills index"
          >
            ← Skills
          </Link>
          <Link
            href={`/browse/${encodeURIComponent(lookupName)}`}
            className="ui-button ui-button-sm"
            title="View skill documentation"
          >
            Docs for {lookupName}
          </Link>
          <span className="page-meta">{sourcePath}</span>
        </div>
        <h1 className="page-title">{title}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <span
            className="ui-chip ui-chip-muted"
            title={
              title !== normalizedCanonical
                ? `Canonical ID: ${normalizedCanonical} | Display name: ${title}`
                : `Canonical ID: ${normalizedCanonical}`
            }
          >
            ID: {normalizedCanonical}
          </span>
        </div>
        <p className="page-subtitle">
          Data folder:{" "}
          <span className="font-mono text-[var(--text-secondary)] break-all" title={dataDir}>{dataDir}</span>
        </p>
        <p className="text-xs text-[var(--text-muted)]">
          Status endpoint:{" "}
          <span className="font-mono">/api/settings/skills</span>
        </p>
      </header>

      <div className="glass-panel p-6 overflow-auto">
        <Markdown markdown={body} basePath={sourcePath} />
      </div>
    </div>
  );
}
