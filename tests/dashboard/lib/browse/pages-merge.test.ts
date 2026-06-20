import {
  extractIndexedArtifacts,
  mergePagesSources,
  type ArtifactEntry,
  type IndexedPageEntry,
  type LiveTabEntry,
} from "@/lib/browse/pages-merge";

describe("mergePagesSources", () => {
  it("returns empty when both inputs are empty", () => {
    expect(mergePagesSources([], [])).toEqual([]);
  });

  it("tags live entries with kind=live", () => {
    const live: LiveTabEntry[] = [
      { label: "Brain Inbox", href: "/workspace/inbox", hub: "workspace", icon: "Inbox", pageType: "yaml" },
    ];

    const out = mergePagesSources(live, []);

    expect(out).toHaveLength(1);
    expect(out[0].metadata?.kind).toBe("live");
    expect(out[0].path).toBe("/workspace/inbox");
    expect(out[0].primaryAction.target).toBe("/workspace/inbox");
  });

  it("tags artifacts with their kind from sidecar", () => {
    const artifacts: ArtifactEntry[] = [
      {
        slug: "spec-x",
        title: "Spec X",
        kind: "generated",
        hub: "career",
        url: "/artifact/spec-x",
        path: "/abs/path/spec-x.html",
        tags: [],
        promoted_at: "2026-05-10T00:00:00Z",
        created_at: "2026-05-08T00:00:00Z",
      },
    ];

    const out = mergePagesSources([], artifacts);

    expect(out).toHaveLength(1);
    expect(out[0].metadata?.kind).toBe("generated");
    expect(out[0].title).toBe("Spec X");
    expect(out[0].primaryAction.target).toBe("/artifact/spec-x");
  });

  it("round-trips an owning skill onto artifact metadata", () => {
    const withSkill: ArtifactEntry[] = [
      {
        slug: "rag-report",
        title: "RAG Report",
        kind: "generated",
        hub: "brain",
        url: "/artifact/rag-report",
        path: "/abs/path/rag-report.html",
        tags: [],
        promoted_at: "",
        created_at: "",
        skill: "rag",
      },
    ];

    expect(mergePagesSources([], withSkill)[0].metadata?.skill).toBe("rag");

    const withoutSkill: ArtifactEntry[] = [
      { ...withSkill[0], slug: "no-owner", url: "/artifact/no-owner", skill: undefined },
    ];

    expect(mergePagesSources([], withoutSkill)[0].metadata?.skill).toBeUndefined();
  });

  it("merges both sources preserving live first then artifacts", () => {
    const out = mergePagesSources(
      [{ label: "Live", href: "/brain", hub: "workspace", icon: "X", pageType: "tsx" }],
      [
        {
          slug: "a",
          title: "A",
          kind: "saved",
          hub: "career",
          url: "/artifact/a",
          path: "/p/a.html",
          tags: [],
          promoted_at: "",
          created_at: "",
        },
      ],
    );

    expect(out.map((item) => item.metadata?.kind)).toEqual(["live", "saved"]);
  });

  it("attaches sourcePath to live pages from indexed page entries by route", () => {
    const out = mergePagesSources(
      [
        {
          label: "Inbox",
          href: "/workspace/inbox",
          hub: "workspace",
          icon: "Inbox",
          pageType: "tsx",
          skillId: "ingest",
        },
      ],
      [],
      [
        {
          route: "/workspace/inbox",
          source_path: "/Users/me/Projects/Augur/project-brain/capabilities/skills/ingest/SKILL.md",
        },
      ],
    );

    expect(out[0].metadata?.sourcePath).toBe(
      "/Users/me/Projects/Augur/project-brain/capabilities/skills/ingest/SKILL.md",
    );
  });

  it("prefers an absolute indexed source path over a relative source path for the same route", () => {
    const out = mergePagesSources(
      [
        {
          label: "Inbox",
          href: "/workspace/inbox",
          hub: "workspace",
          icon: "Inbox",
          pageType: "tsx",
          skillId: "ingest",
        },
      ],
      [],
      [
        {
          route: "/workspace/inbox",
          source_path: "/Users/me/Projects/Augur/project-brain/capabilities/skills/ingest/SKILL.md",
        },
        {
          route: "/workspace/inbox",
          source_path: "project-brain/capabilities/skills/ingest/SKILL.md",
        },
      ],
    );

    expect(out[0].metadata?.sourcePath).toBe(
      "/Users/me/Projects/Augur/project-brain/capabilities/skills/ingest/SKILL.md",
    );
  });
});

describe("extractIndexedArtifacts", () => {
  const indexedArtifact: IndexedPageEntry = {
    id: "memory-architecture",
    title: "Memory Architecture",
    hub: "dev",
    tags: ["memory"],
    source_path: "/abs/docs/dev/artifacts/memory-architecture.html",
    metadata: {
      kind: "generated",
      slug: "memory-architecture",
      url: "/artifact/memory-architecture",
      path: "/abs/docs/dev/artifacts/memory-architecture.html",
      promoted_at: "2026-06-01T00:00:00Z",
      created_at: "2026-06-01T00:00:00Z",
    },
  };
  const indexedLivePage: IndexedPageEntry = {
    id: "vault",
    title: "vault",
    route: "/private-vault/vault",
    source_path: "/abs/skills/vault/SKILL.md",
    metadata: { skill: "vault", pageType: "yaml" },
  };

  it("extracts artifact entries by metadata.kind", () => {
    const out = extractIndexedArtifacts([indexedArtifact, indexedLivePage]);
    expect(out).toHaveLength(1);
    expect(out[0]).toMatchObject({
      slug: "memory-architecture",
      title: "Memory Architecture",
      kind: "generated",
      hub: "dev",
      url: "/artifact/memory-architecture",
      path: "/abs/docs/dev/artifacts/memory-architecture.html",
      tags: ["memory"],
    });
  });

  it("ignores live page entries and tolerates undefined input", () => {
    expect(extractIndexedArtifacts([indexedLivePage])).toEqual([]);
    expect(extractIndexedArtifacts(undefined)).toEqual([]);
  });

  it("round-trips through mergePagesSources as artifact cards", () => {
    const artifacts = extractIndexedArtifacts([indexedArtifact]);
    const out = mergePagesSources([], artifacts, [indexedArtifact]);
    expect(out).toHaveLength(1);
    expect(out[0].id).toBe("artifact:memory-architecture");
    expect(out[0].metadata?.kind).toBe("generated");
    expect(out[0].primaryAction.target).toBe("/artifact/memory-architecture");
  });
});
