/**
 * POST /api/adrs/extract
 *
 * Extracts an ADR's markdown body to a runtime temp directory and returns
 * the absolute path. Two paths:
 *
 *  - Live ADRs (state="live" in project-brain/decisions/adrs/adrs-index.json) — render the
 *    JSON entry inline as a thin-wrapper ADR file (no zip lookup needed).
 *  - Archived ADRs — call ``.github/scripts/adr_archive.py extract``,
 *    which unzips the body and any spec/plan companions.
 *
 * NOTE — AGENTS.md/CLAUDE.md rule 11 normally prohibits direct local
 * execution from dashboard routes. This route is a sanctioned exception per
 * ADR-642 because (a) the live-render path is read-only filesystem I/O and
 * (b) the archive-extract path uses execFile without a shell.
 */
import path from "path";
// eslint-disable-next-line no-restricted-imports -- @fs-exempt: ADR-642 renders live ADR markdown into runtime temp storage
import { promises as fs } from "fs";
// eslint-disable-next-line no-restricted-imports -- @spawn-exempt: ADR-642 shells out to the archive extractor without invoking a shell
import { execFile } from "child_process";
import { NextResponse } from "next/server";

import { AUGUR_PYTHON, AUGUR_ROOT, AUGUR_STATE_DIR } from "@/lib/paths";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const EXTRACT_TIMEOUT_MS = 30_000;

const ADR_NUMBER_PATTERN = /^ADR-\d{1,6}$/i;

function normaliseAdrNumber(input: unknown): string | null {
  if (typeof input !== "string") return null;
  const trimmed = input.trim();
  if (!trimmed) return null;
  // Accept "ADR-042", "adr-42", "42", "0042"
  const match = trimmed.match(/^(?:adr-)?(\d+)$/i);
  if (!match) return null;
  const padded = match[1].padStart(3, "0");
  const candidate = `ADR-${padded}`;
  if (!ADR_NUMBER_PATTERN.test(candidate)) return null;
  return candidate;
}

interface CentralIndexEntry {
  adr_number?: string;
  title?: string;
  state?: string;
  status?: string;
  date?: string;
  deciders?: string[];
  related?: string[];
  hub?: string | null;
  tags?: string[];
  decision_summary?: string;
  status_notes?: string;
  impact?: Record<string, unknown>;
  spec_file?: string | null;
  plan_file?: string | null;
  superseded_by?: string | null;
}

function slugifyTitle(title: string): string {
  return (
    title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "") || "untitled"
  );
}

function renderLiveAdrMarkdown(entry: CentralIndexEntry, adrNumber: string): string {
  const num = adrNumber.replace(/^ADR-/i, "");
  const title = entry.title || `ADR-${num}`;
  const fmLines = ["---"];
  fmLines.push(`status: ${entry.status || "Proposed"}`);
  fmLines.push(`date: ${entry.date || ""}`);
  if (entry.deciders && entry.deciders.length) {
    fmLines.push("deciders:");
    for (const d of entry.deciders) fmLines.push(`  - ${d}`);
  } else {
    fmLines.push("deciders: []");
  }
  if (entry.related && entry.related.length) {
    fmLines.push("related:");
    for (const r of entry.related) fmLines.push(`  - ${r}`);
  } else {
    fmLines.push("related: []");
  }
  fmLines.push(`hub: ${entry.hub == null ? "null" : entry.hub}`);
  if (entry.tags && entry.tags.length) {
    fmLines.push("tags:");
    for (const t of entry.tags) fmLines.push(`  - ${t}`);
  } else {
    fmLines.push("tags: []");
  }
  if (entry.spec_file) fmLines.push(`spec_file: ${entry.spec_file}`);
  if (entry.plan_file) fmLines.push(`plan_file: ${entry.plan_file}`);
  fmLines.push(`superseded_by: ${entry.superseded_by ?? "null"}`);
  fmLines.push("---", "");

  const sections: string[] = [`# ADR-${num}: ${title}`, ""];
  if (entry.decision_summary) {
    sections.push("## Decision summary", "", entry.decision_summary, "");
  }
  if (entry.status_notes) {
    sections.push("## Status notes", "", entry.status_notes, "");
  }
  const impact = entry.impact;
  const hasImpact =
    impact &&
    typeof impact === "object" &&
    Object.values(impact).some(
      (v) => Array.isArray(v) && (v as unknown[]).length > 0,
    );
  if (hasImpact && impact) {
    sections.push("## Impact Manifest", "", "```yaml");
    for (const [k, v] of Object.entries(impact)) {
      if (!Array.isArray(v) || v.length === 0) continue;
      sections.push(`${k}:`);
      for (const item of v as unknown[]) sections.push(`  - ${String(item)}`);
    }
    sections.push("```", "");
  }
  return fmLines.join("\n") + sections.join("\n").replace(/\s+$/, "") + "\n";
}

async function readCentralIndex(): Promise<CentralIndexEntry[]> {
  const indexPath = path.join(AUGUR_ROOT, "docs", "adrs", "adrs-index.json");
  try {
    const raw = await fs.readFile(indexPath, "utf8");
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((e): e is CentralIndexEntry => e && typeof e === "object");
  } catch {
    return [];
  }
}

async function writeLiveAdrToRuntime(
  entry: CentralIndexEntry,
  adrNumber: string,
): Promise<string> {
  const num = adrNumber.replace(/^ADR-/i, "");
  const slug = entry.title ? slugifyTitle(entry.title) : "untitled";
  const filename = `ADR-${num}-${slug}.md`;
  const destDir = path.join(AUGUR_STATE_DIR, "adr-extracts", `ADR-${num}`);
  await fs.mkdir(destDir, { recursive: true });
  const destPath = path.join(destDir, filename);
  await fs.writeFile(destPath, renderLiveAdrMarkdown(entry, adrNumber), "utf8");
  return destPath;
}

function runExtract(adrNumber: string): Promise<{ stdout: string; stderr: string }> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(AUGUR_ROOT, ".github", "scripts", "adr_archive.py");
    // Use execFile (no shell) per security guidance: arguments are passed as
    // an array, never interpolated into a shell string.
    execFile(
      AUGUR_PYTHON,
      [scriptPath, "extract", adrNumber],
      {
        cwd: AUGUR_ROOT,
        timeout: EXTRACT_TIMEOUT_MS,
        maxBuffer: 1024 * 1024,
      },
      (error, stdout, stderr) => {
        if (error) {
          const err = error as NodeJS.ErrnoException & { stderr?: string };
          err.stderr = stderr;
          reject(err);
          return;
        }
        resolve({ stdout: String(stdout), stderr: String(stderr) });
      },
    );
  });
}

async function appendRecentView(adrNumber: string, archived: boolean): Promise<void> {
  const logDir = path.join(AUGUR_STATE_DIR, "adrs");
  const logFile = path.join(logDir, "recent-views.jsonl");
  await fs.mkdir(logDir, { recursive: true });
  const line =
    JSON.stringify({
      adr_number: adrNumber,
      ts: new Date().toISOString(),
      archived,
    }) + "\n";
  await fs.appendFile(logFile, line, "utf8");
}

export async function POST(req: Request) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Request body must be JSON" },
      { status: 400 },
    );
  }

  const rawNumber =
    body && typeof body === "object" && body !== null
      ? (body as Record<string, unknown>).adr_number
      : null;

  const adrNumber = normaliseAdrNumber(rawNumber);
  if (!adrNumber) {
    return NextResponse.json(
      { error: "adr_number is required and must be like 'ADR-042'" },
      { status: 400 },
    );
  }

  // Resolve from the central index first — live entries render inline
  // without needing the shell extract step.
  const centralEntries = await readCentralIndex();
  const matched = centralEntries.find((e) => e.adr_number === adrNumber);
  if (matched && matched.state === "live") {
    let extractedPath: string;
    try {
      extractedPath = await writeLiveAdrToRuntime(matched, adrNumber);
    } catch (error) {
      const err = error as NodeJS.ErrnoException;
      return NextResponse.json(
        { error: err.message || "Failed to render live ADR" },
        { status: 500 },
      );
    }
    try {
      await appendRecentView(adrNumber, false);
    } catch {
      /* recent-views log is advisory */
    }
    return NextResponse.json({ path: extractedPath });
  }

  let result: { stdout: string; stderr: string };
  try {
    result = await runExtract(adrNumber);
  } catch (error) {
    const err = error as NodeJS.ErrnoException & { stderr?: string };
    const message = err.stderr || err.message || "Failed to extract archived ADR";
    return NextResponse.json(
      { error: message },
      { status: 500 },
    );
  }

  const extracted = result.stdout.trim().split("\n").pop()?.trim() ?? "";
  if (!extracted) {
    return NextResponse.json(
      { error: "Extract script produced no path" },
      { status: 500 },
    );
  }

  // Best-effort append; don't fail the request if logging hiccups.
  try {
    await appendRecentView(adrNumber, true);
  } catch {
    /* recent-views log is advisory; ignore failures */
  }

  return NextResponse.json({ path: extracted });
}
