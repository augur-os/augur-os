const ARTIFACT_SLUG_RE = /^[a-z0-9][a-z0-9-]*$/;

export function normalizeArtifactSlug(slug: string): string | null {
  try {
    const normalized = decodeURIComponent(slug).trim();
    return ARTIFACT_SLUG_RE.test(normalized) ? normalized : null;
  } catch {
    return null;
  }
}
