import { browseItemKey } from "@/lib/browse/overlay";
import type { BrowseItem } from "@/lib/browse/types";

function makeItem(overrides: Partial<BrowseItem>): BrowseItem {
  return {
    id: "item",
    title: "Item",
    description: "",
    hub: "system",
    primaryAction: { label: "Open", type: "navigate", target: "/" },
    ...overrides,
  } as BrowseItem;
}

describe("browseItemKey", () => {
  it("folds the path into non-overlay keys so colliding ids never drop distinct files", () => {
    // documents/scripts/tests can emit filename-stem ids that collide across
    // distinct files (four README.md, many bootstrap_paths.py). Keying by bare
    // id would make useBrowseState's dedup silently drop the twins, so the path
    // is folded in: same id + different path => different key.
    const a = makeItem({ id: "README", path: "/a/README.md" });
    const b = makeItem({ id: "README", path: "/b/README.md" });
    expect(browseItemKey(a, "documents")).not.toBe(browseItemKey(b, "documents"));
    // Same id + same path is still a genuine duplicate => identical key.
    const c = makeItem({ id: "README", path: "/a/README.md" });
    expect(browseItemKey(a, "documents")).toBe(browseItemKey(c, "documents"));
  });

  it("disambiguates same-id items across overlay scopes (the duplicate-key bug)", () => {
    // Two genuinely distinct cards that share item.id but live in different
    // overlay scopes — overlay dedup keeps BOTH, so the React key must differ.
    const shared = makeItem({ id: "summary", path: "/shared/summary.md", metadata: { vault_scope: "shared" } });
    const priv = makeItem({ id: "summary", path: "/private/summary.md", metadata: { vault_scope: "private" } });

    for (const view of ["notes", "wiki", "skills"]) {
      const a = browseItemKey(shared, view);
      const b = browseItemKey(priv, view);
      expect(a).not.toBe(b);
    }
  });

  it("yields a stable, identical key for items with identical overlay identity", () => {
    const a = makeItem({ id: "manifest", path: "/p/manifest.json", metadata: { vault_scope: "shared", source_root: "x" } });
    const b = makeItem({ id: "manifest", path: "/p/manifest.json", metadata: { vault_scope: "shared", source_root: "x" } });
    expect(browseItemKey(a, "notes")).toBe(browseItemKey(b, "notes"));
  });

  it("produces unique keys for every item that survives overlay dedup", () => {
    // Mirror the useBrowseState dedup, then assert keys are collision-free —
    // exactly the invariant BrowseDisplayRenderer relies on for React keys.
    const raw = [
      makeItem({ id: "summary", path: "/a/summary.md", metadata: { vault_scope: "shared" } }),
      makeItem({ id: "summary", path: "/b/summary.md", metadata: { vault_scope: "private" } }),
      makeItem({ id: "manifest", path: "/a/manifest.json", metadata: { vault_scope: "shared" } }),
      makeItem({ id: "manifest", path: "/b/manifest.json", metadata: { vault_scope: "private" } }),
    ];
    const view = "notes";
    const seen = new Set<string>();
    const deduped = raw.filter((item) => {
      const key = browseItemKey(item, view);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    const keys = deduped.map((item) => browseItemKey(item, view));
    expect(new Set(keys).size).toBe(keys.length);
    expect(deduped.length).toBe(4);
  });
});
