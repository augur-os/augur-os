/**
 * @jest-environment node
 *
 * Regression test for B6: "Add Note → Text → Save as Note" persistence.
 * The text-note capture builds a markdown File routed through the ingest upload
 * path (previously it was a silent no-op that only queued a local item).
 */
import { describe, it, expect } from "@jest/globals";
import { textNoteFilename, textNoteFile } from "@/lib/browse/textNote";

describe("textNoteFilename", () => {
  it("derives a slugged .md name from the first line", () => {
    expect(textNoteFilename("Harbor Lattice Plan\nbody text")).toBe("harbor-lattice-plan.md");
  });

  it("falls back to note.md for empty/punctuation-only text", () => {
    expect(textNoteFilename("")).toBe("note.md");
    expect(textNoteFilename("!!!")).toBe("note.md");
  });

  it("trims slug to a bounded length", () => {
    const long = "a".repeat(200);
    const name = textNoteFilename(long);
    expect(name.endsWith(".md")).toBe(true);
    expect(name.length).toBeLessThanOrEqual(51); // 48 slug + ".md"
  });
});

describe("textNoteFile", () => {
  it("produces a markdown File carrying the full text", async () => {
    const file = textNoteFile("Cobalt Ledger\nfull body");
    expect(file.name).toBe("cobalt-ledger.md");
    expect(file.type).toBe("text/markdown");
    expect(await file.text()).toBe("Cobalt Ledger\nfull body");
  });
});
