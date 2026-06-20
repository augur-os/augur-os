import {
  NOTE_DOMAIN_LABELS,
  NOTE_SOURCE_LABELS,
  classifyNoteMetadata,
  classificationBadgesForItem,
  hasExplicitNoteClassificationSignal,
  noteClassificationForItem,
  noteStatusOptionsForDomain,
} from "@/lib/browse/noteClassification";
import type { BrowseItem } from "@/lib/browse/types";

function item(metadata: Record<string, string>, path = "/vault/notes/example.md"): BrowseItem {
  return {
    id: path,
    title: "Example",
    description: "Example note",
    hub: "workspace",
    icon: "BookOpen",
    path,
    typeBadge: metadata.noteType ?? metadata["x-augur-note-type"] ?? "url",
    primaryAction: { label: "Open Note", type: "open-file", target: path },
    metadata,
  };
}

function itemWithoutTypeBadge(metadata: Record<string, string>, path: string): BrowseItem {
  return {
    id: path,
    title: "Example",
    description: "Example note",
    hub: "workspace",
    icon: "BookOpen",
    path,
    primaryAction: { label: "Open Note", type: "open-file", target: path },
    metadata,
  };
}

describe("classifyNoteMetadata", () => {
  it("classifies GitHub repositories as saved projects", () => {
    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { canonical_url: "https://github.com/openai/codex" },
      path: "/vault/notes/codex.md",
    })).toEqual({
      noteType: "url",
      domain: "projects",
      source: "github",
      status: "saved",
      classificationConfidence: "high",
      needsClassification: false,
    });
  });

  it("classifies GitHub issues and pull requests as evaluating projects", () => {
    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://github.com/openai/codex/issues/42" },
      path: "/vault/notes/issue.md",
    }).status).toBe("evaluating");

    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://github.com/openai/codex/pull/42" },
      path: "/vault/notes/pr.md",
    }).status).toBe("evaluating");
  });

  it("classifies LinkedIn jobs and profiles separately", () => {
    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://www.linkedin.com/jobs/view/123456" },
      path: "/vault/notes/job.md",
    })).toMatchObject({
      domain: "jobs",
      source: "linkedin",
      status: "saved",
      classificationConfidence: "high",
    });

    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://www.linkedin.com/in/some-person/" },
      path: "/vault/notes/person.md",
    })).toMatchObject({
      domain: "people",
      source: "linkedin",
      status: null,
      classificationConfidence: "high",
    });
  });

  it("classifies websites, docs, and articles with deterministic URL rules", () => {
    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://example.com/careers/engineering" },
      path: "/vault/notes/company.md",
    })).toMatchObject({ domain: "companies", source: "website", status: null });

    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://docs.python.org/3/library/urllib.parse.html" },
      path: "/vault/notes/docs.md",
    })).toMatchObject({ domain: "research", source: "website", status: null });

    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://martinfowler.com/articles/example.html" },
      path: "/vault/notes/article.md",
    })).toMatchObject({ domain: "reading", source: "website", status: "queued" });
  });

  it("uses low-confidence research fallback for generic pages and local files", () => {
    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: { url: "https://example.net/random-page" },
      path: "/vault/notes/random.md",
    })).toMatchObject({
      domain: "research",
      source: "website",
      status: null,
      classificationConfidence: "low",
      needsClassification: true,
    });

    expect(classifyNoteMetadata({
      noteType: "file",
      metadata: {},
      path: "/vault/documents/spec.pdf",
    })).toMatchObject({
      domain: "research",
      source: "local-file",
      status: null,
      classificationConfidence: "low",
      needsClassification: true,
    });

    expect(classifyNoteMetadata({
      noteType: "file",
      metadata: { url: "https://github.com/openai/codex" },
      path: "/vault/documents/codex.pdf",
    })).toMatchObject({
      domain: "research",
      source: "local-file",
      status: null,
      classificationConfidence: "low",
      needsClassification: true,
    });
  });

  it("trusts known Augur frontmatter over URL guesses", () => {
    expect(classifyNoteMetadata({
      noteType: "url",
      metadata: {
        "x-augur-domain": "jobs",
        "x-augur-source": "linkedin",
        "x-augur-status": "applied",
        "x-augur-classification-confidence": "high",
        url: "https://github.com/openai/codex",
      },
      path: "/vault/notes/curated.md",
    })).toMatchObject({
      domain: "jobs",
      source: "linkedin",
      status: "applied",
      classificationConfidence: "high",
      needsClassification: false,
    });
  });

  it("preserves project-specific note metadata as filterable classification values", () => {
    expect(classifyNoteMetadata({
      noteType: "thought",
      metadata: {
        "x-augur-domain": "augur-browse",
        "x-augur-source": "codex-session",
        "x-augur-status": "needs-review",
        "x-augur-classification-confidence": "high",
      },
      path: "/vault/notes/augur/notes-filters.md",
    })).toMatchObject({
      noteType: "thought",
      domain: "augur-browse",
      source: "codex-session",
      status: "needs-review",
      classificationConfidence: "high",
      needsClassification: false,
    });
  });

  it("preserves note-specific classification frontmatter aliases from the live Notes index", () => {
    expect(classifyNoteMetadata({
      noteType: "file",
      metadata: {
        "x-augur-note-domain": "augur-browse",
        "x-augur-note-source": "codex-session",
        "x-augur-note-status": "needs-review",
        "x-augur-classification-confidence": "high",
      },
      path: "/vault/notes/augur/notes-filters.md",
    })).toMatchObject({
      noteType: "file",
      domain: "augur-browse",
      source: "codex-session",
      status: "needs-review",
      classificationConfidence: "high",
      needsClassification: false,
    });
  });
});

describe("noteClassificationForItem", () => {
  it("normalizes BrowseItem metadata aliases", () => {
    expect(noteClassificationForItem(item({
      noteType: "url",
      noteDomain: "project",
      noteSource: "github",
      noteStatus: "watching",
      classificationConfidence: "medium",
    }))).toMatchObject({
      noteType: "url",
      domain: "projects",
      source: "github",
      status: "watching",
      classificationConfidence: "medium",
    });
  });

  it("does not treat generic Browse source as note classification source", () => {
    expect(noteClassificationForItem(item({
      noteType: "url",
      source: "private-vault",
      canonical_url: "https://github.com/openai/codex",
    }))).toMatchObject({
      noteType: "url",
      domain: "projects",
      source: "github",
      status: "saved",
      classificationConfidence: "high",
    });

    expect(noteClassificationForItem(item({
      noteType: "url",
      source: "github",
      url: "https://example.net/random-page",
    }))).toMatchObject({
      noteType: "url",
      domain: "research",
      source: "website",
      status: null,
      classificationConfidence: "low",
    });
  });

  it("recognizes note_type_filter as an explicit note type key", () => {
    expect(noteClassificationForItem(item({
      note_type_filter: "file",
    }))).toMatchObject({ noteType: "file" });
  });

  it("normalizes URL note type aliases from Browse state", () => {
    for (const alias of ["article", "webpage", "source"]) {
      expect(noteClassificationForItem(item({
        noteType: alias,
      }))).toMatchObject({ noteType: "url" });
    }
  });

  it("normalizes file note type aliases from Browse state", () => {
    for (const alias of ["document", "markdown"]) {
      expect(noteClassificationForItem(item({
        noteType: alias,
      }))).toMatchObject({ noteType: "file" });
    }
  });

  it("normalizes thought note type aliases from Browse state", () => {
    for (const alias of ["text", "note"]) {
      expect(noteClassificationForItem(item({
        noteType: alias,
      }))).toMatchObject({ noteType: "thought" });
    }
  });

  it("infers URL, file, and prompt note types from Browse paths", () => {
    expect(noteClassificationForItem(itemWithoutTypeBadge({}, "/vault/sources/urls/example.md")))
      .toMatchObject({ noteType: "url" });
    expect(noteClassificationForItem(itemWithoutTypeBadge({}, "/vault/sources/files/report.pdf")))
      .toMatchObject({ noteType: "file" });
    expect(noteClassificationForItem(itemWithoutTypeBadge({}, "/vault/prompts/research.md")))
      .toMatchObject({ noteType: "prompt" });
  });

  it("infers URL note type from URL metadata fields", () => {
    expect(noteClassificationForItem(itemWithoutTypeBadge({
      canonical_url: "https://example.com",
    }, "/vault/notes/canonical.md"))).toMatchObject({ noteType: "url" });
    expect(noteClassificationForItem(itemWithoutTypeBadge({
      source_domain: "example.com",
    }, "/vault/notes/source-domain.md"))).toMatchObject({ noteType: "url" });
  });

  it("detects only explicit note classification signals", () => {
    for (const metadata of [
      { "x-augur-note-type": "url" },
      { noteType: "url" },
      { note_type: "url" },
      { note_type_filter: "url" },
      { "x-augur-domain": "projects" },
      { "x-augur-source": "github" },
      { "x-augur-status": "evaluating" },
      { "x-augur-note-domain": "projects" },
      { "x-augur-note-source": "github" },
      { "x-augur-note-status": "evaluating" },
      { "x-augur-classification-confidence": "high" },
    ]) {
      expect(hasExplicitNoteClassificationSignal({ metadata })).toBe(true);
    }

    for (const metadata of [
      { source_domain: "github.com", url: "https://github.com/openai/codex" },
      { noteDomain: "projects", noteSource: "github", classificationConfidence: "high" },
      { needsClassification: "false" },
    ]) {
      expect(hasExplicitNoteClassificationSignal({ metadata })).toBe(false);
    }
  });

  it("builds ordered badge labels", () => {
    const badges = classificationBadgesForItem(item({
      noteType: "url",
      noteDomain: "projects",
      noteSource: "github",
      noteStatus: "evaluating",
    }));

    expect(badges.map((badge) => badge.label)).toEqual([
      "URL",
      "Project",
      "GitHub",
      "Evaluating",
    ]);
  });

  it("labels custom classification badges from their metadata values", () => {
    const badges = classificationBadgesForItem(item({
      noteType: "thought",
      noteDomain: "augur-browse",
      noteSource: "codex-session",
      noteStatus: "needs-review",
    }));

    expect(badges.map((badge) => badge.label)).toEqual([
      "Thought",
      "Augur Browse",
      "Codex Session",
      "Needs Review",
    ]);
  });

  it("adds needs-classification as the trailing low-confidence badge", () => {
    const badges = classificationBadgesForItem(item({
      noteType: "url",
      url: "https://example.net/random-page",
    }));

    expect(badges.map((badge) => badge.label)).toEqual([
      "URL",
      "Research",
      "Website",
      "Needs classification",
    ]);
  });

  it("exposes status options only for lifecycle domains", () => {
    expect(noteStatusOptionsForDomain("jobs").map((option) => option.id)).toEqual([
      "saved",
      "applied",
      "interviewing",
      "offer",
      "rejected",
      "archived",
    ]);
    expect(noteStatusOptionsForDomain("projects").map((option) => option.id)).toEqual([
      "saved",
      "evaluating",
      "watching",
      "active",
      "archived",
    ]);
    expect(noteStatusOptionsForDomain("reading").map((option) => option.id)).toEqual([
      "queued",
      "reading",
      "finished",
      "archived",
    ]);
    expect(noteStatusOptionsForDomain("companies")).toEqual([]);
    expect(noteStatusOptionsForDomain("people")).toEqual([]);
    expect(noteStatusOptionsForDomain("research")).toEqual([]);
  });

  it("keeps public labels stable", () => {
    expect(NOTE_DOMAIN_LABELS.projects).toBe("Project");
    expect(NOTE_SOURCE_LABELS["local-file"]).toBe("Local file");
  });
});
