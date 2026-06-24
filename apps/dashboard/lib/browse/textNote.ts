/**
 * Helpers for capturing a pasted text note through the file-ingest path.
 *
 * B6: "Add Note → Text → Save as Note" previously only queued a local item and
 * never persisted anything. Text notes are now turned into a markdown File and
 * routed through the same ingest path as uploads. This module isolates the
 * (pure, testable) filename derivation from the React controller.
 */

/** Derive a stable, filesystem-safe markdown filename from pasted note text. */
export function textNoteFilename(text: string): string {
  const firstLine = text.split("\n", 1)[0]?.trim() ?? "";
  const slug =
    firstLine
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 48) || "note";
  return `${slug}.md`;
}

/** Build a markdown File from pasted note text for the ingest upload path. */
export function textNoteFile(text: string): File {
  return new File([text], textNoteFilename(text), { type: "text/markdown" });
}
