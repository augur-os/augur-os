import type { BrowseCardAction, BrowsePrimaryAction, CLIToolStatus } from "./types";
import { firstString, normalizeSkillOwnership, wikiMarkdownLink } from "./transforms.shared";

export function resolveIndexPrimaryAction(
  entry: Record<string, any>,
  category: string,
  entryId: string,
  type: string,
  itemId: string,
): BrowsePrimaryAction {
  let primaryAction: BrowsePrimaryAction;
  switch (category) {
    case "skills":
      primaryAction = {
        label: "View",
        type: "navigate",
        target: `/browse/${entry.id}`,
      };
      break;
    case "commands":
      primaryAction = {
        label: "Copy",
        type: "copy",
        target: `/${entry.id}`,
      };
      break;
    case "prompts":
      primaryAction = {
        label: "Open Template",
        type: "open-file",
        target: entry.source_path || "",
      };
      break;
    case "integrations":
      if (entry.metadata?.registry === "external_mcp_registry" && firstString(entry.metadata?.setup_url, entry.setup_url)) {
        primaryAction = {
          label: "Copy Setup",
          type: "copy",
          target: firstString(entry.metadata?.setup_url, entry.setup_url) || "",
        };
      } else if (entry.metadata?.registry === "external_mcp_registry" && firstString(entry.metadata?.check_command, entry.check_command)) {
        primaryAction = {
          label: "Copy Check",
          type: "copy",
          target: firstString(entry.metadata?.check_command, entry.check_command) || "",
        };
      } else {
        primaryAction = {
          label: "Help",
          type: "run-action",
          target: `${entry.id || entryId} --help`,
        };
      }
      break;
    case "pages":
      primaryAction = {
        label: "Open",
        type: "navigate",
        target: entry.route || entry.metadata?.route || `/workspace/${entry.name || ""}`,
      };
      break;
    case "tests":
      primaryAction = {
        label: "Run Test",
        type: "run-action",
        target: `Run test: ${entry.source_path || entryId}`,
      };
      break;
    case "api-routes": {
      const methods = entry.metadata?.methods || entry.methods || "";
      const routePath = entry.source_path || entryId;
      primaryAction = {
        label: "Test Route",
        type: "run-action",
        target: `Test API route ${methods} ${routePath}`,
      };
      break;
    }
    case "logs":
      if (type === "job-ledger" || entry.metadata?.category === "job-ledger") {
        primaryAction = {
          label: "Inspect Jobs",
          type: "mcp-tool",
          target: "jobs-list",
        };
      } else {
        primaryAction = {
          label: "Tail Recent",
          type: "open-file",
          target: entry.metadata?.latest_file_path || entry.source_path || "",
        };
      }
      break;
    case "mcp-servers":
      primaryAction = {
        label: "Open Manifest",
        type: "open-file",
        target: firstString(entry.source_path, entry.metadata?.source_path) || "",
      };
      break;
    case "wiki":
      primaryAction = {
        label: "Read Wiki",
        type: "open-file",
        target: entry.source_path || "",
      };
      break;
    case "background-routines":
      primaryAction = {
        label: "Reveal",
        type: "open-file",
        target: entry.source_path || "",
      };
      break;
    case "vault":
      primaryAction = {
        label: type === "email-drop" ? "Open Email" : "Open",
        type: "open-file",
        target: entry.source_path || "",
      };
      break;
    case "adrs": {
      // ADR-642: live entries live in adrs-index.json with a synthetic
      // ``index://ADR-NNN`` path; archived entries keep ``archive://ADR-NNN``
      // and need an extract step. Both surface through the same
      // extract-and-open-adr action because there is no on-disk file for
      // either — the dashboard renders the JSON entry inline.
      const isArchived = entry.archived === true
        || (typeof entry.source_path === "string" && entry.source_path.startsWith("archive://"))
        || entry.metadata?.archived === true
        || (typeof entry.metadata?.archived === "string"
            && entry.metadata.archived.toLowerCase() === "true");
      const sourcePath = typeof entry.source_path === "string" ? entry.source_path : "";
      const isLiveIndexEntry = sourcePath.startsWith("index://");
      const adrNum = String(entry.adr_number || "").replace(/^ADR-/i, "");
      const adrLabel = adrNum
        ? `ADR-${adrNum.padStart(3, "0")}`
        : (sourcePath.startsWith("archive://") || sourcePath.startsWith("index://")
            ? sourcePath.replace(/^(archive|index):\/\//, "")
            : "");
      if (isArchived) {
        primaryAction = {
          label: "Open ADR",
          type: "extract-and-open-adr",
          target: adrLabel,
        };
      } else if (isLiveIndexEntry) {
        primaryAction = {
          label: "Open ADR",
          type: "extract-and-open-adr",
          target: adrLabel,
        };
      } else {
        primaryAction = {
          label: "Open ADR",
          type: "open-file",
          target: entry.source_path || entry.path || "",
        };
      }
      break;
    }
    default:
      primaryAction = {
        label: "Open",
        type: "open-file",
        target: entry.source_path || "",
      };
  }
  return primaryAction;
}

export function resolveIndexActions(
  entry: Record<string, any>,
  category: string,
  entryId: string,
  type: string,
  itemId: string,
): BrowseCardAction[] | undefined {
  let actions: BrowseCardAction[] | undefined;

  switch (category) {
    case "commands":
      actions = [
        { id: `help-${entryId}`, label: "Show Help", icon: "Terminal", type: "run-action", target: `/${entryId} --help` },
        { id: `open-${entryId}`, label: "Open File", icon: "FolderOpen", type: "open-file", target: entry.source_path || "" },
      ];
      break;
    case "skills": {
      const fallbackOwnership = !!(entry.source_path && String(entry.source_path).includes("/skills/"))
        || entry.source === "augur"
        ? "augur"
        : "external";
      const ownership = normalizeSkillOwnership(
        entry.ownership ?? entry.metadata?.ownership ?? entry.source,
        fallbackOwnership,
      );
      const isManaged = ownership === "augur" || ownership === "adopted";
      if (isManaged) {
        actions = [
          { id: `improve-${entryId}`, label: "Improve", icon: "Sparkles", type: "run-action", target: `/harden ${entryId}` },
          { id: `remove-${entryId}`, label: "Remove", icon: "Trash", type: "run-mcp", target: `remove-skill:${entryId}`, variant: "danger" },
        ];
      } else {
        actions = [
          { id: `install-${entryId}`, label: "Install in IDE", icon: "CheckCircle2", type: "run-mcp", target: `install-skill:${entryId}` },
          { id: `catalog-${entryId}`, label: "Add to Catalog", icon: "BookmarkPlus", type: "run-mcp", target: `add-to-catalog:${entryId}` },
        ];
      }
      break;
    }
    case "documents":
      actions = [
        { id: `remove-${entry.source_path || entryId}`, label: "Unlink File", icon: "Trash", type: "run-mcp", target: `unlink-doc:${entry.source_path || ""}`, variant: "danger" },
      ];
      break;
    case "tests":
      if (entry.source_path) {
        actions = [
          { id: `reveal-${entryId}`, label: "Reveal", icon: "FolderOpen", type: "open-file", target: entry.source_path },
        ];
      }
      break;
    case "api-routes":
      if (entry.source_path) {
        actions = [
          { id: `reveal-${entryId}`, label: "Reveal", icon: "FolderOpen", type: "open-file", target: entry.source_path },
        ];
      }
      break;
    case "integrations": {
      actions = [];
      const cliArr = entry.cli_tools as CLIToolStatus[] | undefined;
      const installedNames = (cliArr || [])
        .flatMap((ct: CLIToolStatus) => (ct.installed ? [ct.name] : []))
        .join(",");
      if (installedNames) {
        actions.push(
          { id: `cli-help-${entryId}`, label: "CLI --help", icon: "Terminal", type: "cli-help", target: installedNames },
        );
      }
      const checkCommand = firstString(entry.metadata?.check_command, entry.check_command);
      if (checkCommand) {
        actions.push(
          { id: `copy-check-${entryId}`, label: "Copy Check", icon: "Copy", type: "copy", target: checkCommand },
        );
      }
      const setupUrl = firstString(entry.metadata?.setup_url, entry.setup_url);
      if (setupUrl) {
        actions.push(
          { id: `copy-setup-${entryId}`, label: "Copy Setup", icon: "Copy", type: "copy", target: setupUrl },
        );
      }
      if (entry.source_path) {
        actions.push(
          { id: `reveal-${entryId}`, label: "Reveal Config", icon: "FolderOpen", type: "open-file", target: entry.source_path },
        );
      }
      if (actions.length === 0) actions = undefined;
      break;
    }
    case "logs": {
      const isJobLedger = type === "job-ledger" || entry.metadata?.category === "job-ledger";
      const logsRootPath = entry.metadata?.logs_root_path || "";
      const jobsRootPath = entry.metadata?.jobs_root_path || logsRootPath;
      const latestFolderPath = entry.metadata?.latest_folder_path || "";
      const latestFilePath = entry.metadata?.latest_file_path || entry.source_path || "";
      const logActions: BrowseCardAction[] = isJobLedger
        ? [
            { id: `jobs-root-${entryId}`, label: "Open Jobs Root", icon: "FolderOpen", type: "open-file", target: jobsRootPath },
            { id: `folder-${entryId}`, label: "Open Latest Job", icon: "FolderOpen", type: "open-file", target: latestFolderPath },
            { id: `reveal-${entryId}`, label: "Reveal Latest Events", icon: "FolderOpen", type: "open-file", target: latestFilePath },
            { id: `copy-${entryId}`, label: "Copy Latest Path", icon: "Copy", type: "copy", target: latestFilePath },
          ]
        : [
            { id: `logs-root-${entryId}`, label: "Open Logs Root", icon: "FolderOpen", type: "open-file", target: logsRootPath },
            { id: `folder-${entryId}`, label: "Open Recent Folder", icon: "FolderOpen", type: "open-file", target: latestFolderPath },
            { id: `reveal-${entryId}`, label: "Reveal Latest", icon: "FolderOpen", type: "open-file", target: latestFilePath },
            { id: `copy-${entryId}`, label: "Copy Latest Path", icon: "Copy", type: "copy", target: latestFilePath },
          ];
      const filteredLogActions = logActions.filter((action) => Boolean(action.target));
      actions = filteredLogActions.length > 0 ? filteredLogActions : undefined;
      break;
    }
    case "wiki": {
      const sourcePath = entry.source_path || "";
      const wikiActions: BrowseCardAction[] = [
        { id: `reveal-${entryId}`, label: "Reveal Source", icon: "FolderOpen", type: "reveal-file", target: sourcePath },
        { id: `copy-path-${entryId}`, label: "Copy Path", icon: "Copy", type: "copy", target: sourcePath },
        { id: `copy-markdown-link-${entryId}`, label: "Copy Markdown Link", icon: "Link", type: "copy", target: wikiMarkdownLink(entry, itemId) },
        { id: `prepare-wiki-update-${entryId}`, label: "Prepare Wiki Update", icon: "RefreshCw", type: "mcp-tool", target: "wiki-update", args: { limit: 20 } },
        { id: `reindex-wiki-${entryId}`, label: "Reindex Wiki", icon: "SearchCheck", type: "mcp-tool", target: "wiki-reindex" },
      ];
      actions = wikiActions.filter((action) => Boolean(action.target));
      break;
    }
    case "background-routines": {
      const localActions: BrowseCardAction[] = [];
      if (entry.source_path) {
        localActions.push({
          id: `reveal-${entryId}`,
          label: "Reveal",
          icon: "FolderOpen",
          type: "open-file",
          target: entry.source_path,
        });
      }
      const serverActions = Array.isArray(entry.actions)
        ? (entry.actions as BrowseCardAction[])
        : [];
      const merged = [...localActions, ...serverActions];
      if (merged.length > 0) {
        actions = merged;
      }
      break;
    }
    case "prompts":
      actions = [
        {
          id: `trigger-${entryId}`,
          label: "Trigger",
          icon: "Play",
          type: "run-action",
          target: entry.source_path || "",
        },
      ];
      break;
  }
  return actions;
}
