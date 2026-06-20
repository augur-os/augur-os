'use client';

import React, { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useMcpMutation } from '@/lib/mcp/useMcpMutation';
import { InstallSuccess } from './InstallSuccess';
import { StepHeader } from './StepHeader';

interface ImportDataFolderProps {
  onBack: () => void;
  onClose: () => void;
}

interface ScanResult {
  hub_id: string;
  file_count: number;
  file_types: Record<string, number>;
  total_size_bytes: number;
  message: string;
}

export function ImportDataFolder({ onBack, onClose }: ImportDataFolderProps) {
  const [path, setPath] = useState('');
  const [hubId, setHubId] = useState('');
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [done, setDone] = useState(false);

  const { mutate: scan, loading: scanning, error: scanError } = useMcpMutation<ScanResult>(
    'import-data',
    {
      staticArgs: { execute: false },
      select: (raw: unknown) => raw as ScanResult,
    },
  );

  const { mutate: execute, loading: importing } = useMcpMutation<Record<string, unknown>>(
    'import-data',
    {
      invalidates: ['browse-index'],
      onSuccess: () => {
        setDone(true);
        toast.success('Data folder imported');
      },
    },
  );

  const handleScan = useCallback(async () => {
    if (!path.trim()) return;
    const result = await scan({ source_path: path.trim(), hub_id: hubId.trim() });
    if (result) {
      setScanResult(result);
      if (result.hub_id && !hubId) setHubId(result.hub_id);
    }
  }, [path, hubId, scan]);

  const handleImport = useCallback(async () => {
    await execute({ source_path: path.trim(), hub_id: hubId.trim(), execute: true });
  }, [path, hubId, execute]);

  if (done) {
    return (
      <InstallSuccess
        headline="Data folder imported"
        skills={[{ name: hubId || 'imported-data', toolCount: 0 }]}
        onClose={onClose}
        onViewInBrowse={onClose}
      />
    );
  }

  return (
    <div>
      <StepHeader title="Import Data Folder" onBack={onBack} />

      <div className="mb-3">
        <label htmlFor="import-folder-path" className="mb-1.5 block text-xs text-muted-foreground">Folder path</label>
        <div className="flex gap-2">
          <Input
            id="import-folder-path"
            className="flex-1"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="/path/to/data/folder"
          />
          <Button
            variant="solid"
            onClick={handleScan}
            disabled={!path.trim()}
            isLoading={scanning}
          >
            Scan
          </Button>
        </div>
        {scanError && <p className="mt-1 text-xs text-destructive">{scanError}</p>}
      </div>

      <div className="mb-4">
        <label htmlFor="import-folder-hub" className="mb-1.5 block text-xs text-muted-foreground">
          Hub ID <span className="text-muted-foreground/40">(auto-detected from folder name)</span>
        </label>
        <Input
          id="import-folder-hub"
          value={hubId}
          onChange={(e) => setHubId(e.target.value)}
          placeholder="my-data"
        />
      </div>

      {scanResult && (
        <div className="mb-4 rounded-lg border border-border bg-card p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="size-2 rounded-full bg-yellow-400" />
            <span className="text-sm font-semibold text-foreground">Scan Results</span>
          </div>
          <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
            <span className="text-muted-foreground/60">Files found</span>
            <span className="text-muted-foreground">
              {scanResult.file_count} files
              {scanResult.file_types &&
                ` (${Object.entries(scanResult.file_types)
                  .map(([ext, count]) => `${count} ${ext}`)
                  .join(', ')})`}
            </span>
            <span className="text-muted-foreground/60">Total size</span>
            <span className="text-muted-foreground">
              {(scanResult.total_size_bytes / 1024 / 1024).toFixed(1)} MB
            </span>
          </div>
        </div>
      )}

      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="outline" onClick={onBack}>
          Cancel
        </Button>
        <Button
          variant="success"
          onClick={handleImport}
          disabled={!scanResult}
          isLoading={importing}
        >
          Import
        </Button>
      </div>
    </div>
  );
}
