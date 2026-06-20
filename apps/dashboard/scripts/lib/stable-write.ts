import fs from "fs/promises";
import yaml from "yaml";

function normalizeValue(value: unknown, volatileKeys: Set<string>): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeValue(item, volatileKeys));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([key]) => !volatileKeys.has(key))
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, child]) => [key, normalizeValue(child, volatileKeys)]),
    );
  }

  return value;
}

function semanticSignature(value: unknown, volatileKeys: string[]): string {
  return JSON.stringify(normalizeValue(value, new Set(volatileKeys)));
}

export async function writeStableJsonFile(
  outputPath: string,
  payload: unknown,
  volatileKeys: string[] = [],
): Promise<boolean> {
  const serialized = `${JSON.stringify(payload, null, 2)}\n`;

  try {
    const existingContent = await fs.readFile(outputPath, "utf8");
    const existingPayload = JSON.parse(existingContent);
    if (
      semanticSignature(existingPayload, volatileKeys) ===
      semanticSignature(payload, volatileKeys)
    ) {
      return false;
    }
  } catch {
    // Missing or invalid existing file — write the new payload.
  }

  await fs.writeFile(outputPath, serialized, "utf8");
  return true;
}

export async function writeStableYamlFile(
  outputPath: string,
  payload: unknown,
  volatileKeys: string[] = [],
): Promise<boolean> {
  const serialized = yaml.stringify(payload);

  try {
    const existingContent = await fs.readFile(outputPath, "utf8");
    const existingPayload = yaml.parse(existingContent);
    if (
      semanticSignature(existingPayload, volatileKeys) ===
      semanticSignature(payload, volatileKeys)
    ) {
      return false;
    }
  } catch {
    // Missing or invalid existing file — write the new payload.
  }

  await fs.writeFile(outputPath, serialized, "utf8");
  return true;
}
