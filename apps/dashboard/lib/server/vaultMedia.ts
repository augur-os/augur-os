import { open } from "node:fs/promises";

export interface MediaByteRange {
  start: number;
  end: number;
}

export interface MediaReadResult {
  body: Buffer;
  range: MediaByteRange | null;
  size: number;
}

function parseMediaRange(range: string | null, size: number): MediaByteRange | null {
  const match = range?.match(/^bytes=(\d*)-(\d*)$/);
  if (!match) return null;
  const [, rawStart, rawEnd] = match;
  if (!rawStart && !rawEnd) return null;
  const start = rawStart ? Number(rawStart) : Math.max(0, size - Number(rawEnd));
  const end = rawEnd ? Number(rawEnd) : size - 1;
  if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start || start >= size) {
    return null;
  }
  return { start, end: Math.min(end, size - 1) };
}

export async function readMediaFile(filePath: string, rangeHeader: string | null): Promise<MediaReadResult> {
  const fileHandle = await open(filePath, "r");
  try {
    const info = await fileHandle.stat();
    if (!info.isFile()) {
      throw new Error("Media path is not a file");
    }

    const range = parseMediaRange(rangeHeader, info.size);
    if (!range) {
      return {
        body: await fileHandle.readFile(),
        range,
        size: info.size,
      };
    }

    const body = Buffer.alloc(range.end - range.start + 1);
    await fileHandle.read(body, 0, body.length, range.start);
    return { body, range, size: info.size };
  } finally {
    await fileHandle.close();
  }
}
