// Shared {{placeholder}} parsing/substitution (ADR-748).
// Extracted verbatim from components/browse/PromptCard.tsx so the Browse
// prompt-card Trigger button can reuse identical semantics.

const PLACEHOLDER_PATTERN = /{{\s*([A-Za-z_][A-Za-z0-9_]*)\s*}}/g;

export function extractVariables(promptBody: string): string[] {
  const variables: string[] = [];
  const seen = new Set<string>();
  let match: RegExpExecArray | null;

  PLACEHOLDER_PATTERN.lastIndex = 0; // reset before reuse — /g regex is stateful
  while ((match = PLACEHOLDER_PATTERN.exec(promptBody))) {
    const name = match[1].trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    variables.push(name);
  }

  return variables;
}

export function resolvePromptBody(
  promptBody: string,
  values: Record<string, string>,
): string {
  return promptBody.replace(PLACEHOLDER_PATTERN, (match, rawName: string) => {
    const name = rawName.trim();
    return Object.prototype.hasOwnProperty.call(values, name)
      ? values[name]
      : match;
  });
}
