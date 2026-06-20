import type {
  CapabilityProfileItem,
  CapabilityProfileSection,
  SkillAction,
  SkillCommand,
  SkillPrompt,
} from "@/lib/browse/types";

interface CapabilityTool {
  name: string;
  description?: string;
}

interface CapabilityIntegration {
  id: string;
  label: string;
  status?: string;
}

export interface BuildCapabilityProfileInput {
  skillId: string;
  description: string;
  tools?: CapabilityTool[];
  actions?: SkillAction[];
  prompts?: SkillPrompt[];
  commands?: SkillCommand[];
  integrations?: CapabilityIntegration[];
  health?: { status: string; lastCheck?: string; errors24h?: number };
}

function section(
  id: CapabilityProfileSection["id"],
  title: string,
  kind: CapabilityProfileSection["kind"],
  items: CapabilityProfileItem[],
): CapabilityProfileSection | null {
  return items.length > 0 ? { id, title, kind, items } : null;
}

function compact(sections: Array<CapabilityProfileSection | null>): CapabilityProfileSection[] {
  return sections.filter((item): item is CapabilityProfileSection => item !== null);
}

export function buildCapabilityProfileSections(input: BuildCapabilityProfileInput): CapabilityProfileSection[] {
  return compact([
    section("summary", "Summary", "summary", [
      { label: input.skillId, description: input.description },
    ]),
    section("tools", "Tools", "tools", (input.tools ?? []).map((tool) => ({
      label: tool.name,
      description: tool.description,
    }))),
    section("actions", "Actions", "actions", (input.actions ?? []).map((action) => ({
      label: action.label,
      description: action.description,
      metadata: { dispatch: action.dispatch },
    }))),
    section("prompts", "Prompts", "prompts", (input.prompts ?? []).map((prompt) => ({
      label: prompt.label,
      description: prompt.description || prompt.prompt,
    }))),
    section("commands", "Commands", "commands", (input.commands ?? []).map((command) => ({
      label: command.label,
      description: command.description || command.command,
    }))),
    section("integrations", "Integrations", "integrations", (input.integrations ?? []).map((integration) => ({
      label: integration.label,
      description: integration.status,
      metadata: { id: integration.id },
    }))),
    section("health", "Health", "health", input.health ? [{
      label: input.health.status,
      description: input.health.lastCheck,
      metadata: input.health.errors24h != null ? { errors24h: String(input.health.errors24h) } : undefined,
    }] : []),
  ]);
}
