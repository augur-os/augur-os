'use client';

import { useMemo } from 'react';
import { useMcpQuery } from '@/lib/mcp/useMcpQuery';
import type { Routine } from './types';

interface ScheduledExecutionDetailResponse {
  success?: boolean;
  detail?: Routine;
  error?: string;
}

export function useScheduledExecutionDetail(executionId: string | null): {
  detail: Routine | null;
  loading: boolean;
  error: string | null;
} {
  const {
    data,
    loading,
    error: queryError,
  } = useMcpQuery<ScheduledExecutionDetailResponse>(
    ['background-routine-detail', executionId ?? '__none__'],
    'get-background-routine-detail',
    'config',
    {
      args: executionId ? { routine_id: executionId } : {},
      enabled: !!executionId,
    },
  );

  const detail = useMemo(() => {
    if (!executionId || !data?.success || !data.detail) return null;
    return data.detail;
  }, [executionId, data]);

  const error = queryError || (data && data.success === false ? data.error || 'Failed to load background routine detail' : null);

  return {
    detail,
    loading: !!executionId && loading,
    error,
  };
}
