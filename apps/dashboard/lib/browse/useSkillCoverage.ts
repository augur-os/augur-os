"use client";

/**
 * useSkillCoverage — fetches the ADR-741 `skill-resolvable-report` once and
 * returns it indexed for the browse file-card transforms to join against.
 *
 * The report has no browse view of its own (see skillCoverage.ts header):
 * findings ride existing skill and mcp-tool cards. This hook is the single
 * fetch seam; BrowsePageInner owns it and threads the index down.
 */

import { useMemo } from "react";
import { useMcpQuery } from "@/lib/mcp/useMcpQuery";
import {
  buildCoverageIndex,
  parseReport,
  type CoverageIndex,
} from "@/lib/browse/skillCoverage";

export interface UseSkillCoverageResult {
  index: CoverageIndex;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useSkillCoverage(): UseSkillCoverageResult {
  const { data, loading, error, refetch } = useMcpQuery<unknown>(
    "skill-resolvable-report",
    "skill-resolvable-report",
    "static",
  );

  const index = useMemo(() => buildCoverageIndex(parseReport(data)), [data]);

  return { index, loading, error, refetch };
}
