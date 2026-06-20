import { validateBrowseActionsDoc } from "@/lib/browse/itemActionSchema";

const validCategories = new Set(["wiki", "notes", "agent-profiles"]);
const validIcons = new Set(["MessageSquare", "RefreshCw", "Search", "Sparkles"]);

function validate(doc: unknown) {
  return validateBrowseActionsDoc(doc, { validCategories, validIcons });
}

describe("validateBrowseActionsDoc", () => {
  it("accepts ai and direct item actions", () => {
    const result = validate({
      categories: {
        wiki: [
          {
            id: "wiki-update",
            label: "Update",
            icon: "RefreshCw",
            kind: "ai",
            template: "Update {title} at {path}",
          },
          {
            id: "wiki-dead-links",
            label: "Find dead links",
            icon: "Search",
            kind: "direct",
            tool: "dream-dead-citations",
            args: { page: "{path}" },
            invalidates: ["browse-index"],
          },
        ],
      },
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.doc.categories.wiki).toHaveLength(2);
    }
  });

  it("accepts item predicates for note-only actions", () => {
    const result = validate({
      categories: {
        notes: [
          {
            id: "note-enrich",
            label: "Enrich",
            icon: "Sparkles",
            kind: "ai",
            template: "Enrich {title}",
            when: { noteTypes: ["url", "file"] },
          },
        ],
      },
    });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.doc.categories.notes[0].when).toEqual({ noteTypes: ["url", "file"] });
    }
  });

  it("rejects invalid kind and missing required fields", () => {
    const result = validate({
      categories: {
        wiki: [
          { id: "bad-kind", label: "Bad", icon: "Search", kind: "shell" },
          { id: "no-template", label: "No template", icon: "Search", kind: "ai" },
          { id: "no-tool", label: "No tool", icon: "Search", kind: "direct" },
        ],
      },
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.join("\n")).toContain("bad-kind");
      expect(result.errors.join("\n")).toContain("template");
      expect(result.errors.join("\n")).toContain("tool");
    }
  });

  it("rejects unknown categories, unknown icons, and duplicate ids", () => {
    const result = validate({
      categories: {
        drafts: [
          {
            id: "note-summarize",
            label: "Summarize",
            icon: "BookOpen",
            kind: "ai",
            template: "Summarize {title}",
          },
        ],
        wiki: [
          {
            id: "wiki-update",
            label: "Update",
            icon: "RefreshCw",
            kind: "ai",
            template: "Update {title}",
          },
          {
            id: "wiki-update",
            label: "Duplicate",
            icon: "MissingIcon",
            kind: "ai",
            template: "Update {title}",
          },
        ],
      },
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.join("\n")).toContain("unknown category");
      expect(result.errors.join("\n")).toContain("unknown icon");
      expect(result.errors.join("\n")).toContain("duplicate action id");
    }
  });

  it("rejects invalid item predicates", () => {
    const result = validate({
      categories: {
        notes: [
          {
            id: "note-enrich",
            label: "Enrich",
            icon: "Sparkles",
            kind: "ai",
            template: "Enrich {title}",
            when: { noteTypes: ["url", 42] },
          },
        ],
      },
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.join("\n")).toContain("when.noteTypes");
    }
  });

  it("normalizes file extension and media kind filters", () => {
    const result = validateBrowseActionsDoc(
      {
        categories: {
          documents: [
            {
              id: "media-transcript",
              label: "Transcript",
              icon: "Mic",
              kind: "ai",
              template: "Transcribe {path}",
              when: {
                fileExtensions: ["MP3", ".m4a"],
                mediaKinds: ["audio", "video"],
              },
            },
          ],
        },
      },
      { validCategories: new Set(["documents"]), validIcons: new Set(["Mic"]) },
    );

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.doc.categories.documents[0].when).toEqual({
        fileExtensions: ["mp3", "m4a"],
        mediaKinds: ["audio", "video"],
      });
    }
  });
});
