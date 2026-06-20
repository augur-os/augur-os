import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import DisabledSkillPage from "@/components/DisabledSkillPage";
import { CORE_SKILLS, readDisabledSkills } from "@/lib/server/skillsState";
import {
  resolveSkillInfo,
  normalizeSlug,
  parseSkillSlug,
  readSkillMeta,
} from "@/lib/server/skillsLookup";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { ConfigPage } from "@/components/plugin/ConfigPage";
import { buildDefaultPageConfig } from "@/lib/blocks/build-default-page-config";
import { buildCapabilityProfileSections } from "@/lib/capabilities/profile";
import { SkillDetailTabs } from "@/components/browse/SkillDetailTabs";
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function SkillHelpPage({
  params,
}: {
  params: { skill: string };
}) {
  const { skill } = await params;
  const { name: lookupName, sourceRoot } = parseSkillSlug(skill);
  const disabled = await readDisabledSkills();

  // TODO_BUG: sourceRoot is parsed but not yet consumed. External-client skills
  // (source_root = "external-client" / "plugin-cache") resolve to null below and
  // fall through to the default block set, which calls Augur-managed MCP tools
  // that return empty for non-managed skills. Pass 2 should branch on sourceRoot
  // to render index-entry data + adopt/reveal actions instead of generic
  // health/vault-notes blocks. Design call: option A in conversation 2026-05-18.
  void sourceRoot;
  const resolved = await resolveSkillInfo(lookupName);
  const canonicalId = resolved?.canonicalId || lookupName;
  const normalizedCanonical = normalizeSlug(canonicalId);
  const normalizedDisabled = new Set(Array.from(disabled).map(normalizeSlug));

  if (
    !CORE_SKILLS.has(canonicalId) &&
    normalizedDisabled.has(normalizedCanonical)
  ) {
    return <DisabledSkillPage skill={lookupName} title={canonicalId} />;
  }

  const meta = await readSkillMeta(normalizedCanonical);
  const config = buildDefaultPageConfig(normalizedCanonical, meta ?? undefined);
  const prompts = meta?.prompts ?? [];
  const commands = meta?.commands ?? [];
  const capabilityProfileSections = buildCapabilityProfileSections({
    skillId: normalizedCanonical,
    description:
      meta?.description ?? config.description ?? config.title ?? normalizedCanonical,
    tools: (meta?.mcpTools ?? []).map((name) => ({ name })),
    prompts,
    commands,
  });

  return (
    <div className="space-y-6">
      <header className="space-y-4">
        <nav className="flex items-center gap-3 text-sm flex-wrap">
          <Link href="/browse">
            <Button variant="outline" size="sm" className="h-8">
              <ArrowLeft className="size-4 mr-1" />
              Browse
            </Button>
          </Link>
          <span className="text-[var(--text-muted)]">/</span>
          <span className="text-[var(--text-muted)]">
            {normalizedCanonical}
          </span>
        </nav>

        <div className="flex flex-wrap items-center gap-2">
          <h1 className="mr-2 text-3xl font-semibold tracking-tight text-[var(--text-primary)]">
            {config.title}
          </h1>
          <Badge
            variant="outline"
            size="md"
            title={
              config.title !== normalizedCanonical
                ? `Canonical ID: ${normalizedCanonical} | Display name: ${config.title}`
                : `Canonical ID: ${normalizedCanonical}`
            }
          >
            ID: {normalizedCanonical}
          </Badge>
        </div>
        {meta?.description && (
          <p className="max-w-3xl text-sm leading-6 text-[var(--text-secondary)]">
            {meta.description}
          </p>
        )}
      </header>

      <SkillDetailTabs
        skillId={normalizedCanonical}
        skillLabel={config.title}
        prompts={prompts}
        commands={commands}
        capabilityProfileSections={capabilityProfileSections}
        overviewContent={<ConfigPage config={config} skillId={normalizedCanonical} />}
      />
    </div>
  );
}
