import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { AUGUR_DOCUMENTS_DIR, AUGUR_VAULT_DIR, USER_HOME } from "@/lib/paths";
import { readMediaFile } from "@/lib/server/vaultMedia";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MEDIA_TYPES = new Map<string, string>([
  [".aac", "audio/aac"],
  [".flac", "audio/flac"],
  [".m4a", "audio/mp4"],
  [".m4v", "video/mp4"],
  [".mp3", "audio/mpeg"],
  [".mov", "video/quicktime"],
  [".mp4", "video/mp4"],
  [".ogg", "audio/ogg"],
  [".wav", "audio/wav"],
  [".webm", "audio/webm"],
]);

function expandTilde(value: string): string {
  if (value === "~") return USER_HOME;
  if (value.startsWith("~/") || value.startsWith("~\\")) {
    return path.join(USER_HOME, value.slice(2));
  }
  return value;
}

function normalizeForCompare(value: string): string {
  const resolved = path.resolve(value);
  return process.platform === "win32" ? resolved.toLowerCase() : resolved;
}

function isInsideRoot(filePath: string, root: string): boolean {
  const file = normalizeForCompare(filePath);
  const base = normalizeForCompare(root);
  return file === base || file.startsWith(`${base}${path.sep}`);
}

function allowedMediaRoots(): string[] {
  return [
    AUGUR_VAULT_DIR,
    AUGUR_DOCUMENTS_DIR,
    path.join(USER_HOME, "Desktop"),
    path.join(USER_HOME, "Documents"),
    path.join(USER_HOME, "Downloads"),
    path.join(USER_HOME, "Music"),
    path.join(USER_HOME, "Videos"),
  ];
}

function bufferToResponseBody(body: Buffer): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(body.length);
  bytes.set(body);
  return bytes;
}

export async function GET(request: NextRequest) {
  const rawPath = request.nextUrl.searchParams.get("path");
  if (!rawPath) {
    return NextResponse.json({ error: "Missing path" }, { status: 400 });
  }

  const filePath = path.resolve(expandTilde(rawPath));
  const ext = path.extname(filePath).toLowerCase();
  const contentType = MEDIA_TYPES.get(ext);
  if (!contentType) {
    return NextResponse.json({ error: "Unsupported media type" }, { status: 415 });
  }

  if (!allowedMediaRoots().some((root) => isInsideRoot(filePath, root))) {
    return NextResponse.json({ error: "Path is outside allowed media roots" }, { status: 403 });
  }

  try {
    const { body, range, size } = await readMediaFile(filePath, request.headers.get("range"));
    const headers = new Headers({
      "Accept-Ranges": "bytes",
      "Cache-Control": "private, max-age=60",
      "Content-Type": contentType,
      "X-Content-Type-Options": "nosniff",
    });

    if (range) {
      headers.set("Content-Range", `bytes ${range.start}-${range.end}/${size}`);
      headers.set("Content-Length", String(body.length));
      return new NextResponse(bufferToResponseBody(body), { status: 206, headers });
    }

    headers.set("Content-Length", String(body.length));
    return new NextResponse(bufferToResponseBody(body), { headers });
  } catch (error) {
    if (error instanceof Error && error.message === "Media path is not a file") {
      return NextResponse.json({ error: "Media path is not a file" }, { status: 404 });
    }
    return NextResponse.json({ error: "Media file not found" }, { status: 404 });
  }
}
