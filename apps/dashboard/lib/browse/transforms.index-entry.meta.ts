import {
  copyMeta,
  displayWikiTags,
  firstString,
  formatLogCount,
  formatWikiPageKind,
  normalizeSkillOwnership,
  normalizeStringList,
  skillNameFromPath,
  wikiPageKind,
} from "./transforms.shared";
import { formatRelativeTime, humanizeTokens } from "./routine-format";

export function resolveIndexTypeBadge(
  entry: Record<string, any>,
  category: string,
  type: string,
  itemId: string,
): string {
  let typeBadge: string;
  switch (category) {
    case "commands":
      typeBadge = entry.metadata?.category || entry.category || "APP";
      break;
    case "logs":
      typeBadge = entry.metadata?.category === "job-ledger" && entry.metadata?.job_count
        ? `${entry.metadata.job_count} ${entry.metadata.job_count === "1" ? "job" : "jobs"}`
        : entry.metadata?.source_count
        ? `${entry.metadata.source_count} ${entry.metadata.source_count === "1" ? "source" : "sources"}`
        : "runtime";
      break;
    case "documents":
      typeBadge = (entry.source_path || "").split(".").pop() || "file";
      break;
    case "pages": {
      const pt = entry.metadata?.pageType || "custom";
      typeBadge = pt === "yaml" ? "YAML" : pt === "auto" ? "Auto" : "Custom";
      break;
    }
    case "background-routines":
      typeBadge = entry.metadata?.source_kind || entry.metadata?.source || type;
      break;
    case "mcp-servers":
      typeBadge = firstString(entry.tier, entry.metadata?.tier) || "mcp-server";
      break;
    case "wiki":
      typeBadge = formatWikiPageKind(entry, itemId);
      break;
    case "integrations":
      typeBadge = firstString(
        entry.service_type,
        entry.metadata?.service_type,
        entry.integration_type,
        entry.metadata?.integration_type,
      ) || entry.metadata?.status || type;
      break;
    case "vault":
      typeBadge = type === "email-drop"
        ? "Email"
        : firstString(
          entry.metadata?.["x-augur-note-type"],
          entry.metadata?.noteType,
          entry.metadata?.note_type,
          entry.metadata?.visibility,
          entry.metadata?.status,
          type,
        ) || type;
      break;
    case "system-metadata":
      typeBadge = firstString(
        entry.metadata?.artifact_type,
        entry.artifact_type,
        entry.metadata?.status,
        type,
      ) || type;
      break;
    default:
      typeBadge = entry.metadata?.visibility || entry.metadata?.status || type;
  }
  return typeBadge;
}

export function resolveIndexDescription(
  entry: Record<string, any>,
  category: string,
  typeBadge: string,
  itemId: string,
  _skill: string,
): string {
  let description: string;
  switch (category) {
    case "skills":
      // description = SKILL.md description frontmatter — real prose, usually set
      description = entry.description || "Augur skill";
      break;
    case "pages":
      // Scanner now writes "Title — type block". Use it, fall back to constructed.
      if (entry.description && entry.description !== entry.title) {
        description = entry.description;
      } else {
        description = _skill
          ? `${_skill} · ${entry.metadata?.block_type || "page"}`
          : `${entry.metadata?.block_type || "page"}`;
      }
      break;
    case "documents": {
      const catalogSummary = firstString(
        entry.metadata?.catalogSummary,
        entry.metadata?.catalog_summary,
        entry.catalogSummary,
        entry.catalog_summary,
      );
      if (catalogSummary) {
        description = catalogSummary;
        break;
      }
      const docPath = entry.source_path || "";
      const format = entry.metadata?.format || "";
      const shortPath = docPath
        .replace(/^.*?\/Documents\/Augur\//, "")
        .replace(/^.*?\/Vault\/Augur\//, "")
        .replace(/^.*?\/Augur\//, "");
      const parts = shortPath.split("/").filter(Boolean);
      const readablePath = parts.length > 0 ? parts.join(" / ") : docPath.split("/").pop() || "document";
      description = format ? `${format.toUpperCase()} · ${readablePath}` : readablePath;
      break;
    }
    case "mcp-tools":
      // description = first docstring line — useful when set, empty otherwise
      description = entry.description || (_skill ? `${_skill} tool` : "MCP tool");
      break;
    case "mcp-servers":
      description = firstString(
        entry.description,
        entry.command,
        entry.metadata?.command,
        entry.args,
        entry.metadata?.args,
      ) || "";
      break;
    case "vault": {
      // description = frontmatter title — often empty. Fall back to readable path.
      if (entry.description) {
        description = entry.description;
      } else {
        const vaultPath = (entry.source_path || "")
          .replace(/^.*?\/Vault\/Augur\//, "")
          .replace(/^.*?\/Augur\//, "");
        description = vaultPath.split("/").filter(Boolean).join(" / ") || "note";
      }
      break;
    }
    case "integrations":
      // description = subtitle or "CLI bridge: tool1, tool2" — usually useful
      description = entry.description || (entry.metadata?.cli_tools ? `CLI: ${entry.metadata.cli_tools}` : "integration");
      break;
    case "prompts":
      // description = first body line — often a TODO stub or leaked XML tag. Fall back to skill context.
      description = (entry.description && !entry.description.includes("TODO") && !entry.description.startsWith("<"))
        ? entry.description
        : (_skill ? `Prompt template · ${_skill}` : "Prompt template");
      break;
    case "commands":
      // description = command doc frontmatter description
      description = entry.description || `${typeBadge} command`;
      break;
    case "logs":
      if (entry.metadata?.category === "job-ledger") {
        description = [
          entry.description || "Runtime job ledger",
          entry.metadata?.state_counts ? `states: ${entry.metadata.state_counts}` : "",
          entry.metadata?.total_size_human,
        ].filter(Boolean).join(" · ");
      } else {
        description = [
          entry.description || "Runtime log source",
          formatLogCount(entry.metadata?.file_count),
          entry.metadata?.total_size_human,
        ].filter(Boolean).join(" · ");
      }
      break;
    case "background-routines": {
      const cadence = entry.metadata?.cadence || entry.metadata?.schedule || "";
      const lastRun = entry.metadata?.lastRun || entry.metadata?.last_run_at || "";
      const sourceKind = entry.metadata?.source_kind || entry.metadata?.source || "";
      const cost = entry.metadata?.tokensPerDay || entry.metadata?.estimated_tokens_per_day || "";
      const status = entry.metadata?.status || "";
      const costSegment = cost ? `${humanizeTokens(cost)} tokens/day` : "";
      description = [
        cadence,
        `last: ${formatRelativeTime(lastRun)}`,
        sourceKind,
        costSegment,
        status,
      ].filter(Boolean).join(" · ");
      break;
    }
    case "agents":
      // description = role/description/instructions from scanner or fallback
      if (entry.description) {
        description = entry.description;
      } else {
        const tier = entry.metadata?.tier || entry.tier;
        const mode = entry.metadata?.mode || entry.mode;
        description = tier ? `${tier} agent · ${mode || "mcp"}` : (_skill ? `${_skill} agent` : "agent");
      }
      break;
    case "pages":
      // Scanner now reads problem_statement/purpose from SKILL.md config
      if (entry.description && entry.description !== entry.title) {
        description = entry.description;
      } else {
        description = _skill ? `${_skill} · dashboard page` : "dashboard page";
      }
      break;
    case "adrs":
      // description = first # heading from body — the real ADR title. Very useful.
      description = entry.description || `Architecture Decision Record`;
      break;
    case "tests":
      // Scanner now extracts docstrings. Use them, fall back to constructed.
      if (entry.description) {
        description = entry.description;
      } else {
        description = _skill
          ? `${entry.metadata?.test_type || "test"} · ${_skill}`
          : `${entry.metadata?.test_type || "test"}`;
      }
      break;
    case "api-routes": {
      // Build useful description: METHOD /api/path — description
      const apiPath = (entry.source_path || "").replace(/^.*?\/api\//, "/api/").replace(/\/route\.ts$/, "");
      const apiMethods = entry.metadata?.methods || "";
      if (entry.description) {
        description = entry.description;
      } else if (apiMethods && apiPath) {
        description = `${apiMethods} ${apiPath}`;
      } else {
        description = apiPath ? `API endpoint · ${apiPath}` : "API route";
      }
      break;
    }
    case "scripts":
      // description = always empty from scanner. Build from metadata.
      description = _skill
        ? `${entry.metadata?.language || "script"} · ${_skill}`
        : `${entry.metadata?.language || "script"}`;
      break;
    case "wiki":
      description = entry.description || `${formatWikiPageKind(entry, itemId)} wiki page`;
      break;
    default:
      description = entry.description || "";
  }
  return description;
}

export function buildIndexEnrichedMeta(
  entry: Record<string, any>,
  category: string,
  type: string,
  itemId: string,
): Record<string, string> {
  // Build enriched metadata from entry.metadata + category-specific derived fields
  const enrichedMeta: Record<string, string> = entry.metadata
    ? { ...entry.metadata }
    : {};

  copyMeta(enrichedMeta, "vault_scope", firstString(entry.vault_scope, entry.metadata?.vault_scope));
  copyMeta(enrichedMeta, "vault_root", firstString(entry.vault_root, entry.metadata?.vault_root));
  copyMeta(enrichedMeta, "promotion_state", firstString(entry.promotion_state, entry.metadata?.promotion_state));
  copyMeta(enrichedMeta, "source_root", firstString(entry.source_root, entry.metadata?.source_root));

  switch (category) {
    case "skills":
      copyMeta(
        enrichedMeta,
        "masterClient",
        entry.masterClient
          ?? entry.master_client
          ?? entry.master
          ?? enrichedMeta.masterClient
          ?? enrichedMeta.master
          ?? enrichedMeta.master_client
          ?? enrichedMeta.skill_client,
      );
      copyMeta(enrichedMeta, "plugin", entry.plugin);
      copyMeta(enrichedMeta, "source", entry.source);
      copyMeta(enrichedMeta, "category", entry.category);
      copyMeta(enrichedMeta, "group", entry.group);
      copyMeta(enrichedMeta, "release", entry.release);
      copyMeta(
        enrichedMeta,
        "skillType",
        firstString(entry.skillType, entry.skill_type, enrichedMeta.skillType, enrichedMeta.skill_type),
      );
      if (!Object.prototype.hasOwnProperty.call(enrichedMeta, "skillTags")) {
        if (entry.skillTags && typeof entry.skillTags === "string") {
          enrichedMeta.skillTags = entry.skillTags;
        } else if (Array.isArray(entry.tags)) {
          const tags = entry.tags.join(",");
          if (tags) enrichedMeta.skillTags = tags;
        }
      }
      const skillClients = normalizeStringList(
        entry.skillClients ?? entry.skill_clients ?? enrichedMeta.skillClients ?? enrichedMeta.skill_clients,
      );
      copyMeta(enrichedMeta, "skillClients", skillClients.join(","));
      if (!Object.prototype.hasOwnProperty.call(enrichedMeta, "masterClient")) {
        copyMeta(enrichedMeta, "masterClient", skillClients[0]);
      }
      if (!Object.prototype.hasOwnProperty.call(enrichedMeta, "masterClient") && enrichedMeta.client_sources) {
        const clientSources = normalizeStringList(enrichedMeta.client_sources);
        copyMeta(enrichedMeta, "masterClient", clientSources[0]);
      }

      copyMeta(
        enrichedMeta,
        "ownership",
        normalizeSkillOwnership(
          entry.ownership ?? entry.source ?? enrichedMeta.ownership,
          entry.source === "private-vault" || enrichedMeta.source_root === "private-vault"
            ? "user"
            : !!(entry.source_path && String(entry.source_path).includes("/skills/")) ? "augur" : "external",
        ),
      );

      copyMeta(
        enrichedMeta,
        "qualityTier",
        firstString(entry.qualityTier, entry.quality_tier, enrichedMeta.qualityTier, enrichedMeta.quality_tier),
      );
      copyMeta(
        enrichedMeta,
        "qualityScore",
        firstString(entry.qualityScore, entry.quality_score, enrichedMeta.qualityScore, enrichedMeta.quality_score),
      );
      copyMeta(
        enrichedMeta,
        "mcpToolCount",
        firstString(entry.mcpToolCount, entry.mcp_tool_count, enrichedMeta.mcpToolCount, enrichedMeta.mcp_tool_count),
      );
      copyMeta(
        enrichedMeta,
        "actionCount",
        firstString(entry.actionCount, entry.action_count, enrichedMeta.actionCount, enrichedMeta.action_count),
      );
      copyMeta(
        enrichedMeta,
        "pageCount",
        firstString(entry.pageCount, entry.page_count, enrichedMeta.pageCount, enrichedMeta.page_count),
      );
      copyMeta(
        enrichedMeta,
        "hasDashboardPage",
        firstString(
          entry.hasDashboardPage,
          entry.has_dashboard_page,
          enrichedMeta.hasDashboardPage,
          enrichedMeta.has_dashboard_page,
        ),
      );
      copyMeta(
        enrichedMeta,
        "dashboardPath",
        firstString(entry.dashboardPath, entry.dashboard_path, enrichedMeta.dashboardPath, enrichedMeta.dashboard_path),
      );
      copyMeta(
        enrichedMeta,
        "needsSetup",
        firstString(entry.needsSetup, entry.needs_setup, enrichedMeta.needsSetup, enrichedMeta.needs_setup),
      );
      copyMeta(
        enrichedMeta,
        "enabled",
        firstString(entry.enabled, enrichedMeta.enabled),
      );
      copyMeta(
        enrichedMeta,
        "updateAvailable",
        firstString(entry.updateAvailable, entry.update_available, enrichedMeta.updateAvailable, enrichedMeta.update_available),
      );
      copyMeta(
        enrichedMeta,
        "adoptionReady",
        firstString(entry.adoptionReady, entry.adoption_ready, enrichedMeta.adoptionReady, enrichedMeta.adoption_ready),
      );
      copyMeta(enrichedMeta, "hasDocs", firstString(entry.hasDocs, entry.has_docs, enrichedMeta.hasDocs, enrichedMeta.has_docs));

      // Canonical skill name (the SKILL.md `name:` — directory name). The browse
      // item id is `skill:<source>:<name>`, so the last segment is the canonical
      // name. ADR-741 check-resolvable keys findings by this name; the coverage
      // join (lib/browse/skillCoverage.ts) reads `skillName` from metadata.
      copyMeta(
        enrichedMeta,
        "skillName",
        firstString(
          entry.name,
          entry.metadata?.skillName,
          entry.metadata?.skill_name,
          skillNameFromPath(firstString(entry.source_path, entry.path, entry.metadata?.source_path)),
          entry.title,
        )
          || (itemId.includes(":") ? itemId.split(":").pop() : itemId),
      );

      if (!Object.prototype.hasOwnProperty.call(enrichedMeta, "hasDashboardPage")) {
        const parsedPageCount = Number(firstString(entry.pageCount, entry.page_count, enrichedMeta.pageCount, enrichedMeta.page_count));
        if (enrichedMeta.dashboardPath || (Number.isFinite(parsedPageCount) && parsedPageCount > 0)) {
          enrichedMeta.hasDashboardPage = "true";
        }
      }

      const clientSources = normalizeStringList(entry.client_sources ?? enrichedMeta.clientSources);
      if (clientSources.length > 0 && !Object.prototype.hasOwnProperty.call(enrichedMeta, "clientSources")) {
        enrichedMeta.clientSources = clientSources.join(",");
      }
      break;
    case "documents": {
      const docExt = (entry.source_path || "").split(".").pop() || "";
      if (docExt) enrichedMeta.fileType = docExt;
      copyMeta(enrichedMeta, "catalogSummary", firstString(entry.catalogSummary, entry.catalog_summary));
      copyMeta(enrichedMeta, "provider", firstString(entry.provider, entry.metadata?.provider));
      copyMeta(enrichedMeta, "indexStatus", firstString(entry.indexStatus, entry.index_status, entry.metadata?.indexStatus, entry.metadata?.index_status));
      copyMeta(enrichedMeta, "attachedBrainIds", firstString(entry.attachedBrainIds, entry.attached_brain_ids, entry.metadata?.attachedBrainIds, entry.metadata?.attached_brain_ids));
      copyMeta(enrichedMeta, "remoteRevision", firstString(entry.remoteRevision, entry.remote_revision, entry.metadata?.remoteRevision, entry.metadata?.remote_revision));
      copyMeta(enrichedMeta, "indexedRevision", firstString(entry.indexedRevision, entry.indexed_revision, entry.metadata?.indexedRevision, entry.metadata?.indexed_revision));
      break;
    }
    case "mcp-tools":
      if (!enrichedMeta.enabled) enrichedMeta.enabled = entry.enabled === false ? "false" : "true";
      break;
    case "mcp-servers":
      copyMeta(enrichedMeta, "tier", firstString(entry.tier, enrichedMeta.tier));
      copyMeta(enrichedMeta, "command", firstString(entry.command, enrichedMeta.command));
      copyMeta(enrichedMeta, "bundle", firstString(entry.bundle, enrichedMeta.bundle));
      copyMeta(enrichedMeta, "status", firstString(entry.status, enrichedMeta.status) || "configured");
      copyMeta(
        enrichedMeta,
        "runtimeStatus",
        firstString(entry.runtimeStatus, entry.runtime_status, enrichedMeta.runtimeStatus, enrichedMeta.runtime_status),
      );
      copyMeta(
        enrichedMeta,
        "runtimePids",
        firstString(entry.runtimePids, entry.runtime_pids, enrichedMeta.runtimePids, enrichedMeta.runtime_pids),
      );
      copyMeta(
        enrichedMeta,
        "runningClients",
        firstString(entry.runningClients, entry.running_clients, enrichedMeta.runningClients, enrichedMeta.running_clients),
      );
      copyMeta(
        enrichedMeta,
        "runtimeProcessCount",
        firstString(
          entry.runtimeProcessCount,
          entry.runtime_process_count,
          enrichedMeta.runtimeProcessCount,
          enrichedMeta.runtime_process_count,
        ),
      );
      copyMeta(
        enrichedMeta,
        "staleRuntime",
        firstString(entry.staleRuntime, entry.stale_runtime, enrichedMeta.staleRuntime, enrichedMeta.stale_runtime),
      );
      break;
    case "vault": {
      const vaultExt = (entry.source_path || "").split(".").pop() || "";
      if (vaultExt) enrichedMeta.fileType = vaultExt;
      // Ensure format is set (scanner provides it; fallback to extension)
      if (!enrichedMeta.format && vaultExt) enrichedMeta.format = vaultExt;
      copyMeta(
        enrichedMeta,
        "noteType",
        firstString(
          entry.metadata?.["x-augur-note-type"],
          entry.metadata?.noteType,
          entry.metadata?.note_type,
        ),
      );
      // Inbox is a note state (ratified spec §6): carry the marker so the Notes
      // toolbar state-chip can filter on it.
      if (enrichedMeta.journey_category === "inbox") {
        enrichedMeta.noteState = "inbox";
      }
      break;
    }
    case "prompts": {
      const promptParts = (entry.source_path || "").split("/");
      const sIdx = promptParts.indexOf("skills");
      if (sIdx >= 0 && sIdx + 1 < promptParts.length) {
        enrichedMeta.skill = promptParts[sIdx + 1];
      }
      if (entry.source) enrichedMeta.source = String(entry.source);
      // `body` + `placeholders` + `source` are emitted by index_prompts() (ADR-748 Task 5b).
      if (typeof entry.body === "string" && entry.body) enrichedMeta.prompt = entry.body;
      const ph = entry.metadata?.placeholders ?? entry.placeholders;
      if (Array.isArray(ph)) enrichedMeta.placeholders = ph.join(",");
      else if (typeof ph === "string" && ph) enrichedMeta.placeholders = ph;
      break;
    }
    case "pages":
      enrichedMeta.pageType = entry.metadata?.pageType || "custom";
      break;
    case "logs":
      if (entry.metadata?.category) enrichedMeta.category = entry.metadata.category;
      if (entry.metadata?.jobs_root_path) enrichedMeta.jobs_root_path = entry.metadata.jobs_root_path;
      if (entry.metadata?.job_count) enrichedMeta.jobCount = entry.metadata.job_count;
      if (entry.metadata?.active_job_count) enrichedMeta.activeJobs = entry.metadata.active_job_count;
      if (entry.metadata?.terminal_job_count) enrichedMeta.terminalJobs = entry.metadata.terminal_job_count;
      if (entry.metadata?.latest_job_id) enrichedMeta.latestJob = entry.metadata.latest_job_id;
      if (entry.metadata?.state_counts) enrichedMeta.stateCounts = entry.metadata.state_counts;
      if (entry.metadata?.file_count) enrichedMeta.fileCount = entry.metadata.file_count;
      if (entry.metadata?.source_count) enrichedMeta.sourceCount = entry.metadata.source_count;
      if (entry.metadata?.total_size_human) enrichedMeta.totalSize = entry.metadata.total_size_human;
      if (entry.metadata?.total_size_bytes) enrichedMeta.total_size_bytes = entry.metadata.total_size_bytes;
      if (entry.metadata?.latest_file_name) enrichedMeta.latestFile = entry.metadata.latest_file_name;
      if (entry.metadata?.latest_relative_path) enrichedMeta.latestRelativePath = entry.metadata.latest_relative_path;
      if (entry.metadata?.latest_folder_path) enrichedMeta.latest_folder_path = entry.metadata.latest_folder_path;
      if (entry.metadata?.latest_file_path) enrichedMeta.latest_file_path = entry.metadata.latest_file_path;
      if (entry.metadata?.logs_root_path) enrichedMeta.logs_root_path = entry.metadata.logs_root_path;
      break;
    case "background-routines":
      copyMeta(enrichedMeta, "source_kind", firstString(entry.source_kind, entry.metadata?.source_kind, enrichedMeta.source_kind));
      copyMeta(enrichedMeta, "spawn_kind", firstString(entry.spawn_kind, entry.metadata?.spawn_kind, enrichedMeta.spawn_kind));
      copyMeta(enrichedMeta, "status", firstString(entry.status, entry.metadata?.status, enrichedMeta.status));
      copyMeta(enrichedMeta, "cadence", firstString(entry.cadence, entry.metadata?.cadence, enrichedMeta.cadence));
      copyMeta(enrichedMeta, "nextRun", firstString(entry.nextRun, entry.next_run_at, entry.metadata?.nextRun, enrichedMeta.nextRun));
      copyMeta(enrichedMeta, "lastRun", firstString(entry.lastRun, entry.last_run_at, entry.metadata?.lastRun, enrichedMeta.lastRun));
      copyMeta(enrichedMeta, "tokensPerDay", firstString(entry.tokensPerDay, entry.metadata?.tokensPerDay, enrichedMeta.tokensPerDay));
      copyMeta(enrichedMeta, "tokensPerRun", firstString(entry.tokensPerRun, entry.metadata?.tokensPerRun, enrichedMeta.tokensPerRun));
      break;
    case "agents":
      if (entry.mode) enrichedMeta.mode = entry.mode;
      if (entry.tier) enrichedMeta.tier = entry.tier;
      break;
    case "wiki": {
      const pageKind = wikiPageKind(entry, itemId);
      const pageTags = displayWikiTags(entry, itemId);
      enrichedMeta.pageType = pageKind;
      if (pageTags.length > 0) {
        enrichedMeta.pageTags = pageTags.join(",");
      }
      break;
    }
    case "adrs": {
      if (entry.date) enrichedMeta.date = entry.date;
      if (entry.status) enrichedMeta.status = entry.status;
      // ADR-608 Phase 2: propagate the archived flag onto metadata so the
      // browse list-item can render the "archived" chip without re-reading
      // the synthetic source_path (archive://ADR-NNN). The flag may arrive
      // as boolean true, the string "true", or the Python-stringified "True"
      // depending on which serialization path the entry took (live MCP tool
      // vs. unified RAG index reading from YAML frontmatter).
      const metaArchivedRaw = entry.metadata?.archived;
      const archivedFlag = entry.archived === true
        || metaArchivedRaw === true
        || (typeof metaArchivedRaw === "string" && metaArchivedRaw.toLowerCase() === "true")
        || (typeof entry.source_path === "string" && entry.source_path.startsWith("archive://"));
      if (archivedFlag) {
        enrichedMeta.archived = "true";
      }
      if (entry.adr_number) enrichedMeta.adr_number = String(entry.adr_number);
      break;
    }
  }
  return enrichedMeta;
}
