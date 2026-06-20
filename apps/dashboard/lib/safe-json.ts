/**
 * Parse a fetch Response as JSON with content-type guard.
 *
 * When the Turbopack dev cache is corrupted, API routes return
 * the Next.js HTML 404 page instead of JSON.  Calling res.json()
 * on that HTML produces the cryptic:
 *   SyntaxError: Unexpected token '<', "<!DOCTYPE "... is not valid JSON
 *
 * This helper detects the HTML response and returns `null` with a
 * single quiet warning instead of throwing.
 */
export async function safeJson<T = unknown>(res: Response): Promise<T | null> {
  const ct = res.headers.get("content-type") ?? "";
  if (!ct.includes("application/json")) {
    if (process.env.NODE_ENV === "development") {
      console.warn(
        `[safeJson] ${res.url} returned ${ct || "no content-type"} (status ${res.status}) — expected JSON. Turbopack cache may be stale; restart dev server if this persists.`,
      );
    }
    return null;
  }
  return res.json() as Promise<T>;
}
