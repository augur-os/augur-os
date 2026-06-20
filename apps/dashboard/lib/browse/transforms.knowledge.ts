import type { BrowseItem, BrowsePrimaryAction } from "./types";
import { classifyNoteMetadata } from "./noteClassification";
import { copyMeta, firstString, hasVaultNoteSignal } from "./transforms.shared";

// Documents
export function transformDocuments(
  files: { path: string; name?: string; hub: string }[],
): BrowseItem[] {
  return files.map((f) => {
    const fileExt = f.path.split(".").pop() || "file";
    // Show readable path: strip absolute prefix, join with " / "
    const shortPath = f.path
      .replace(/^.*?\/Documents\/Augur\//, "")
      .replace(/^.*?\/Vault\/Augur\//, "")
      .replace(/^.*?\/Augur\//, "");
    const desc = fileExt !== "file"
      ? `${fileExt.toUpperCase()} · ${shortPath.split("/").filter(Boolean).join(" / ")}`
      : shortPath.split("/").filter(Boolean).join(" / ");
    return {
      id: f.path,
      title: f.name || f.path.split("/").pop() || f.path,
      description: desc,
      icon: "FileText",
      path: f.path,
      typeBadge: fileExt,
      primaryAction: {
        label: "Open File",
        type: "open-file",
        target: f.path,
      },
      actions: [
        { id: `remove-${f.path}`, label: "Unlink File", icon: "Trash", type: "run-mcp", target: `unlink-doc:${f.path}`, variant: "danger" as const },
      ],
      metadata: { fileType: fileExt },
    };
  });
}

// Vault / Notes
export function transformVault(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path?: string;
    source_path?: string;
    file_type?: string;
    metadata?: Record<string, unknown>;
  }[],
): BrowseItem[] {
  return items.map((v) => {
    const metadata: Record<string, string> = {};
    for (const [key, value] of Object.entries(v.metadata ?? {})) {
      copyMeta(metadata, key, value);
    }
    copyMeta(metadata, "source_path", v.source_path);

    const path = firstString(
      v.path,
      v.source_path,
      metadata.source_path,
      metadata.archived_path,
      metadata.original_path,
    ) || "";
    const fileType = firstString(
      v.file_type,
      metadata.fileType,
      metadata.file_type,
      metadata.archive_mode,
    ) || "vault";
    metadata.fileType = fileType;
    const noteType = firstString(
      metadata["x-augur-note-type"],
      metadata.noteType,
      metadata.note_type,
      metadata.note_type_filter,
    );
    if (noteType) metadata.noteType = noteType;
    const classification = hasVaultNoteSignal(metadata, path)
      ? classifyNoteMetadata({
        noteType,
        metadata,
        path,
        typeBadge: fileType,
      })
      : null;
    if (classification?.noteType) metadata.noteType = classification.noteType;
    if (classification?.domain) metadata.noteDomain = classification.domain;
    if (classification?.source) metadata.noteSource = classification.source;
    if (classification?.status) metadata.noteStatus = classification.status;
    if (classification) {
      metadata.classificationConfidence = classification.classificationConfidence ?? "low";
      metadata.needsClassification = String(classification.needsClassification);
    }

    // Inbox is a note state (ratified spec §6): carry the marker regardless of classification.
    if (metadata.journey_category === "inbox") {
      metadata.noteState = "inbox";
    }

    return {
      id: v.id,
      title: v.title,
      description: v.description,
      icon: "BookOpen",
      typeBadge: classification?.noteType || noteType || fileType,
      path,
      primaryAction: {
        label: "Open Note",
        type: "open-file",
        target: path,
      },
      metadata,
    };
  });
}

// ADRs
export function transformAdrs(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
    status: string;
    date: string;
    adr_number: string;
    archived?: boolean;
  }[],
): BrowseItem[] {
  return items.map((a) => {
    const archived = a.archived === true;
    // ADR-642: every ADR is in adrs-index.json. Live entries surface with a
    // synthetic ``index://ADR-NNN`` path; archived entries keep
    // ``archive://ADR-NNN``. Both render through the same extract action
    // because neither has an on-disk markdown file.
    const isSyntheticPath =
      typeof a.path === "string" &&
      (a.path.startsWith("archive://") || a.path.startsWith("index://"));
    const adrLabel = a.adr_number
      ? `ADR-${String(a.adr_number).replace(/^ADR-/i, "").padStart(3, "0")}`
      : "";
    const primaryAction: BrowsePrimaryAction = archived || isSyntheticPath
      ? {
          label: "Open ADR",
          type: "extract-and-open-adr",
          target: adrLabel,
        }
      : {
          label: "Open ADR",
          type: "open-file",
          target: a.path,
        };
    const metadata: Record<string, string> = {
      date: a.date,
      adr_number: a.adr_number,
      status: a.status,
    };
    if (archived) {
      metadata.archived = "true";
    }
    return {
      id: a.id,
      title: a.title,
      description: a.description,
      icon: "FileText",
      typeBadge: a.status,
      path: a.path,
      primaryAction,
      metadata,
    };
  });
}
