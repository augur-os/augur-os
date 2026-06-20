import {
  buildFolderContextOptions,
  itemMatchesFolderContext,
  selectedFolderLabel,
  type FolderContextResponse,
} from "@/lib/browse/folderContext";

const response: FolderContextResponse = {
  success: true,
  context: { scope: "all", label: "All Brains" },
  options: [
    { id: "all", scope: "all", label: "All Brains", state: "ready" },
    { id: "brain:personal", scope: "brain", brain_id: "personal", label: "Personal", state: "ready", count: 639 },
    { id: "brain:project-augur", scope: "brain", brain_id: "project-augur", label: "Augur project", state: "repairable", count: 24 },
    { id: "detected:project-client", scope: "detected", brain_id: "project-client", label: "Client project", state: "unregistered" },
  ],
};

describe("Browse folder context helpers", () => {
  it("keeps all/personal/project/detected options in dropdown order", () => {
    const options = buildFolderContextOptions(response);

    expect(options.map((option) => option.id)).toEqual([
      "all",
      "brain:personal",
      "brain:project-augur",
      "detected:project-client",
      "add-folder",
    ]);
    expect(options[2].badge).toBe("Repair");
    expect(options[3].badge).toBe("Initialize");
  });

  it("always disables missing options", () => {
    const options = buildFolderContextOptions({
      options: [
        { id: "brain:missing", scope: "brain", brain_id: "missing", label: "Missing", state: "missing", disabled: false },
      ],
    });

    expect(options[0].disabled).toBe(true);
  });

  it("keeps Unassigned as a selectable repair option", () => {
    const options = buildFolderContextOptions({
      options: [
        { id: "all", scope: "all", label: "All Brains", state: "ready" },
        { id: "unassigned", scope: "unassigned", label: "Unassigned", state: "available", badge: "Repair" },
      ],
    });

    expect(options.map((option) => option.id)).toEqual(["all", "unassigned", "add-folder"]);
    expect(options[1].badge).toBe("Repair");
  });

  it("labels selected all and named folder contexts", () => {
    expect(selectedFolderLabel({ scope: "all", label: "All Brains" })).toBe("All Brains");
    expect(selectedFolderLabel({ scope: "brain", brain_id: "project-augur", label: "Augur project" })).toBe("Augur project");
  });

  it("filters items by selected brain context", () => {
    const personal = { metadata: { brain_id: "personal" } };
    const project = { metadata: { brain_id: "project-augur" } };

    expect(itemMatchesFolderContext(personal, { scope: "all", label: "All Brains" })).toBe(true);
    expect(itemMatchesFolderContext(project, { scope: "brain", brain_id: "project-augur", label: "Augur project" })).toBe(true);
    expect(itemMatchesFolderContext(personal, { scope: "brain", brain_id: "project-augur", label: "Augur project" })).toBe(false);
  });

  it("matches document attachment ids before brain_id", () => {
    const item = {
      metadata: {
        attachedBrainIds: "project-y,personal",
        brain_id: "personal",
      },
    };

    expect(
      itemMatchesFolderContext(item, {
        scope: "brain",
        label: "Project Y",
        brain_id: "project-y",
      }),
    ).toBe(true);
  });

  it("matches snake_case document attachment ids before brain_id", () => {
    const item = {
      metadata: {
        attached_brain_ids: "['project-y', 'personal']",
        brain_id: "personal",
      },
    };

    expect(
      itemMatchesFolderContext(item, {
        scope: "brain",
        label: "Project Y",
        brain_id: "project-y",
      }),
    ).toBe(true);
  });

  it("matches array-shaped attached brain ids before brain_id", () => {
    const item = {
      metadata: {
        attached_brain_ids: ["project-y", "personal"],
        brain_id: "personal",
      },
    };

    expect(
      itemMatchesFolderContext(item as any, {
        scope: "brain",
        label: "Project Y",
        brain_id: "project-y",
      }),
    ).toBe(true);
  });

  it("routes only unassigned document items to the Unassigned repair scope", () => {
    const unassigned = { metadata: { indexStatus: "unassigned" } };
    const assigned = { metadata: { attachedBrainIds: "personal", brain_id: "personal" } };

    expect(itemMatchesFolderContext(unassigned, { scope: "unassigned", label: "Unassigned" })).toBe(true);
    expect(itemMatchesFolderContext(assigned, { scope: "unassigned", label: "Unassigned" })).toBe(false);
    expect(
      itemMatchesFolderContext(unassigned, {
        scope: "brain",
        label: "Personal",
        brain_id: "personal",
      }),
    ).toBe(false);
  });

  it("routes snake_case unassigned document metadata to the repair scope", () => {
    const unassigned = { metadata: { index_status: "unassigned", brain_id: "personal" } };

    expect(itemMatchesFolderContext(unassigned, { scope: "unassigned", label: "Unassigned" })).toBe(true);
    expect(
      itemMatchesFolderContext(unassigned, {
        scope: "brain",
        label: "Personal",
        brain_id: "personal",
      }),
    ).toBe(false);
  });

  it("does not match unregistered active brain contexts", () => {
    const project = { metadata: { brain_id: "project-client" } };

    expect(
      itemMatchesFolderContext(project, {
        scope: "brain",
        brain_id: "project-client",
        label: "Client",
        state: "unregistered",
      }),
    ).toBe(false);
  });
});
