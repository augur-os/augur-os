import fs from "fs/promises";
import path from "path";
import yaml from "yaml";

import { AUGUR_RUNTIME_DIR } from "@/lib/paths";

export const CORE_SKILLS = new Set(["augur-mcp", "setup-manager"]);

export interface SkillState {
  disabled: Set<string>; // Fully disabled skills
  partial: Map<string, Set<string>>; // skill -> disabled capabilities
}

export function isSafeSkillSlug(value: string): boolean {
  return /^[a-z0-9][a-z0-9-]*$/.test(value);
}

export function getSkillStatePath(): string {
  return path.join(AUGUR_RUNTIME_DIR, "dashboard", "skills-state.yaml");
}

function emptySkillState(): SkillState {
  return { disabled: new Set(), partial: new Map() };
}

function parseDisabledSkills(disabledRaw: unknown): Set<string> {
  const disabled = new Set<string>();
  if (!Array.isArray(disabledRaw)) {
    return disabled;
  }

  for (const entry of disabledRaw) {
    if (typeof entry !== "string") {
      continue;
    }
    const slug = entry.trim();
    if (slug) {
      disabled.add(slug);
    }
  }
  return disabled;
}

function extractCapabilities(capabilities: unknown): Set<string> {
  const capSet = new Set<string>();
  if (!Array.isArray(capabilities)) {
    return capSet;
  }

  for (const capability of capabilities) {
    if (typeof capability !== "string") {
      continue;
    }
    const trimmed = capability.trim();
    if (trimmed) {
      capSet.add(trimmed);
    }
  }

  return capSet;
}

function parsePartialCapabilities(
  partialRaw: unknown,
): Map<string, Set<string>> {
  const partial = new Map<string, Set<string>>();
  if (
    !partialRaw ||
    typeof partialRaw !== "object" ||
    Array.isArray(partialRaw)
  ) {
    return partial;
  }

  for (const [skillId, capabilities] of Object.entries(partialRaw)) {
    const capSet = extractCapabilities(capabilities);
    if (capSet.size > 0) {
      partial.set(skillId, capSet);
    }
  }

  return partial;
}

async function loadConfigDoc() {
  const configPath = getSkillStatePath();
  let raw = "";
  try {
    raw = await fs.readFile(configPath, "utf8");
  } catch {
    raw = "";
  }

  const doc = yaml.parseDocument(raw || "");
  if (doc.errors.length) {
    const message = doc.errors[0]?.message || "Invalid YAML";
    throw new Error(`Failed to parse ${configPath}: ${message}`);
  }
  if (!doc.contents) (doc as any).contents = doc.createNode({}) as any;

  return { configPath, doc };
}

export async function readSkillState(): Promise<SkillState> {
  const configPath = getSkillStatePath();
  let raw = "";
  try {
    raw = await fs.readFile(configPath, "utf8");
  } catch {
    return emptySkillState();
  }

  let parsed: unknown;
  try {
    parsed = yaml.parse(raw) as unknown;
  } catch {
    return emptySkillState();
  }

  const root =
    parsed && typeof parsed === "object"
      ? (parsed as Record<string, unknown>)
      : {};
  const skillsState = root;

  return {
    disabled: parseDisabledSkills(skillsState.disabled),
    partial: parsePartialCapabilities(skillsState.partial),
  };
}

export async function readDisabledSkills(): Promise<Set<string>> {
  const state = await readSkillState();
  return state.disabled;
}

export async function readDisabledCapabilities(
  skillId: string,
): Promise<Set<string>> {
  const state = await readSkillState();
  return state.partial.get(skillId) || new Set();
}

function buildPartialObject(
  partial: Map<string, Set<string>>,
): Record<string, string[]> {
  const partialObj: Record<string, string[]> = {};
  for (const [skillId, caps] of partial) {
    const capsArray = Array.from(caps).sort((a, b) => a.localeCompare(b));
    if (capsArray.length > 0) {
      partialObj[skillId] = capsArray;
    }
  }
  return partialObj;
}

function writeSkillsStateToDoc(doc: any, state: SkillState): void {
  const disabledArray = Array.from(state.disabled).sort((a, b) =>
    a.localeCompare(b),
  );
  if (disabledArray.length === 0) {
    doc.delete("disabled");
  } else {
    doc.set("disabled", disabledArray);
  }

  const partialObj = buildPartialObject(state.partial);
  if (Object.keys(partialObj).length === 0) {
    doc.delete("partial");
  } else {
    doc.set("partial", partialObj);
  }
  doc.set("version", 1);
}

export async function writeSkillState(state: SkillState): Promise<void> {
  const { configPath, doc } = await loadConfigDoc();
  await fs.mkdir(path.dirname(configPath), { recursive: true });
  writeSkillsStateToDoc(doc, state);
  await fs.writeFile(configPath, doc.toString(), "utf8");
}

export async function writeDisabledSkills(
  disabled: Iterable<string>,
): Promise<void> {
  const state = await readSkillState();
  state.disabled = new Set(
    Array.from(disabled)
      .flatMap((value) => {
        const trimmed = typeof value === "string" ? value.trim() : "";
        return trimmed ? [trimmed] : [];
      }),
  );
  await writeSkillState(state);
}

export async function setSkillEnabled(
  slug: string,
  enabled: boolean,
): Promise<SkillState> {
  const state = await readSkillState();
  if (enabled) {
    state.disabled.delete(slug);
    state.partial.delete(slug); // Also clear partial when re-enabling
  } else {
    state.disabled.add(slug);
  }
  await writeSkillState(state);
  return state;
}

export async function setCapabilityEnabled(
  skillId: string,
  capability: string,
  enabled: boolean,
): Promise<SkillState> {
  const state = await readSkillState();

  let caps = state.partial.get(skillId);
  if (!caps) {
    caps = new Set();
    state.partial.set(skillId, caps);
  }

  if (enabled) {
    caps.delete(capability);
    if (caps.size === 0) {
      state.partial.delete(skillId);
    }
  } else {
    caps.add(capability);
  }

  await writeSkillState(state);
  return state;
}

export function isCapabilityEnabled(
  state: SkillState,
  skillId: string,
  capability: string,
): boolean {
  if (state.disabled.has(skillId)) return false;
  const partialCaps = state.partial.get(skillId);
  if (partialCaps && partialCaps.has(capability)) return false;
  return true;
}

export async function removeSkillFromConfig(slug: string): Promise<void> {
  const [{ configPath, doc }, state] = await Promise.all([
    loadConfigDoc(),
    readSkillState(),
  ]);
  state.disabled.delete(slug);
  state.partial.delete(slug);
  writeSkillsStateToDoc(doc, state);
  doc.deleteIn(["skills", slug]);
  await fs.mkdir(path.dirname(configPath), { recursive: true });
  await fs.writeFile(configPath, doc.toString(), "utf8");
}
