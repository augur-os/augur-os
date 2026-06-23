import { transformIndexEntry } from "@/lib/browse/transforms";
import { browseItemKey, matchesOverlayScope, overlayScope } from "@/lib/browse/overlay";

function findPromoteAction(item: ReturnType<typeof transformIndexEntry>) {
  return item.actions?.find((action) => action.label === "Promote");
}

describe("Browse overlay transforms", () => {
  it("keeps shared and private wiki ids distinct and promotes only private wiki entries", () => {
    const sourcePath = "/Users/test/Au-vault/wiki/concepts/shared-topic.md";
    const shared = transformIndexEntry(
      {
        id: "wiki:shared:concepts/shared-topic",
        title: "Shared Topic",
        description: "Shared wiki page",
        source_path: sourcePath,
        metadata: {
          vault_scope: "shared",
          promotion_state: "shared",
        },
      },
      "wiki",
    );
    const privateItem = transformIndexEntry(
      {
        id: "wiki:private:concepts/shared-topic",
        title: "Shared Topic",
        description: "Private wiki page",
        source_path: sourcePath,
        metadata: {
          vault_scope: "private",
          promotion_state: "private",
          roles: "research, owner",
          domains: "brain,wiki",
        },
      },
      "wiki",
    );

    expect(shared.id).toBe("wiki:shared:concepts/shared-topic");
    expect(privateItem.id).toBe("wiki:private:concepts/shared-topic");
    expect(shared.id).not.toBe(privateItem.id);
    expect(findPromoteAction(shared)).toBeUndefined();

    expect(findPromoteAction(privateItem)).toEqual({
      id: "promote-wiki:private:concepts/shared-topic",
      label: "Promote",
      icon: "UploadCloud",
      type: "mcp-tool",
      target: "promote-browse-item",
      args: {
        category: "wiki",
        title: "Shared Topic",
        source_path: sourcePath,
        description: "Private wiki page",
        roles: ["research", "owner"],
        domains: ["brain", "wiki"],
      },
    });
  });

  it("promotes private notes routed through vault but not shared notes", () => {
    const privateNote = transformIndexEntry(
      {
        id: "vault:private:notes/project-alpha.md",
        title: "Project Alpha",
        description: "Private planning note",
        source_path: "/Users/test/Au-vault/notes/project-alpha.md",
        metadata: {
          journey_category: "notes",
          vault_scope: "private",
          promotion_state: "private",
        },
      },
      "vault",
    );
    const sharedNote = transformIndexEntry(
      {
        id: "vault:shared:notes/project-alpha.md",
        title: "Project Alpha",
        description: "Shared planning note",
        source_path: "/Users/test/Au-vault/notes/project-alpha.md",
        metadata: {
          journey_category: "notes",
          vault_scope: "shared",
          promotion_state: "shared",
        },
      },
      "vault",
    );

    expect(privateNote.id).toBe("vault:private:notes/project-alpha.md");
    expect(findPromoteAction(privateNote)).toEqual(
      expect.objectContaining({
        id: "promote-vault:private:notes/project-alpha.md",
        label: "Promote",
        icon: "UploadCloud",
        type: "mcp-tool",
        target: "promote-browse-item",
        args: expect.objectContaining({
          category: "notes",
          source_path: "/Users/test/Au-vault/notes/project-alpha.md",
        }),
      }),
    );

    expect(sharedNote.id).toBe("vault:shared:notes/project-alpha.md");
    expect(findPromoteAction(sharedNote)).toBeUndefined();
  });

  it("preserves overlay metadata from top-level entry fields and nested metadata", () => {
    const item = transformIndexEntry(
      {
        id: "vault:private:sources/example.md",
        title: "Example Source",
        source_path: "/Users/test/Au-vault/sources/example.md",
        vault_scope: "private",
        vault_root: "/Users/test/Au-vault",
        metadata: {
          journey_category: "sources",
          promotion_state: "private",
          source_root: "sources/web",
        },
      },
      "vault",
    );

    expect(item.metadata).toEqual(
      expect.objectContaining({
        vault_scope: "private",
        vault_root: "/Users/test/Au-vault",
        promotion_state: "private",
        source_root: "sources/web",
      }),
    );
  });

  it("treats promotion packets as packet scope even when stored in the shared vault", () => {
    const packet = transformIndexEntry(
      {
        id: "vault:shared:inbox/promotions/packet-a/synthesis",
        title: "Packet A",
        source_path: "/Users/test/project/project-brain/inbox/promotions/packet-a/synthesis.md",
        metadata: {
          journey_category: "inbox",
          vault_scope: "shared",
          promotion_state: "packet",
        },
      },
      "vault",
    );

    expect(overlayScope(packet.metadata)).toBe("packet");
    expect(matchesOverlayScope(packet, "packet")).toBe(true);
    expect(matchesOverlayScope(packet, "shared")).toBe(false);
  });

  it("keeps overlay item keys distinct for duplicated source ids", () => {
    const shared = {
      id: "daily-note",
      title: "Daily Note",
      description: "Shared note",
      hub: "workspace",
      type: "vault",
      path: "notes/daily.md",
      metadata: {
        vault_scope: "shared",
        source_root: "vault",
      },
    };
    const privateItem = {
      ...shared,
      description: "Private note",
      metadata: {
        vault_scope: "private",
        source_root: "private",
      },
    };

    expect(browseItemKey(shared, "notes")).not.toBe(browseItemKey(privateItem, "notes"));
    // Non-overlay modes fold the path into the key (not the scope), so two items
    // with the same id and same path collapse to one — and the path discriminator
    // is present so distinct-path same-id files never drop.
    expect(browseItemKey(shared, "pages")).toBe("daily-note::notes/daily.md");
    expect(browseItemKey(shared, "pages")).toBe(browseItemKey(privateItem, "pages"));
  });
});
