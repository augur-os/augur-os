'use client';

import React, { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useMcpMutation } from '@/lib/mcp/useMcpMutation';
import { InstallSuccess } from './InstallSuccess';
import { StepHeader } from './StepHeader';

interface ImportFromNotionProps {
  onBack: () => void;
  onClose: () => void;
}

export function ImportFromNotion({ onBack, onClose }: ImportFromNotionProps) {
  const [path, setPath] = useState('');
  const [targetSkill, setTargetSkill] = useState('');
  const [done, setDone] = useState(false);

  const { mutate: execute, loading: importing, error } = useMcpMutation<Record<string, unknown>>(
    'import-notion',
    {
      invalidates: ['browse-index'],
      onSuccess: () => {
        setDone(true);
        toast.success('Notion export imported');
      },
    },
  );

  const handleImport = useCallback(async () => {
    if (!path.trim()) return;
    await execute({
      source_path: path.trim(),
      ...(targetSkill.trim() ? { target_skill: targetSkill.trim() } : {}),
    });
  }, [path, targetSkill, execute]);

  if (done) {
    return (
      <InstallSuccess
        headline="Notion export imported"
        skills={[{ name: targetSkill || 'notion-import', toolCount: 0 }]}
        onClose={onClose}
        onViewInBrowse={onClose}
      />
    );
  }

  return (
    <div>
      <StepHeader title="Import from Notion" onBack={onBack} />

      <div className="mb-3">
        <label htmlFor="notion-export-path" className="mb-1.5 block text-xs text-muted-foreground">
          Notion export path <span className="text-muted-foreground/40">(ZIP file or directory)</span>
        </label>
        <Input
          id="notion-export-path"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="/path/to/notion-export.zip"
        />
      </div>

      <div className="mb-4">
        <label htmlFor="notion-target-skill" className="mb-1.5 block text-xs text-muted-foreground">
          Target skill <span className="text-muted-foreground/40">(optional: auto-detected from content)</span>
        </label>
        <Input
          id="notion-target-skill"
          value={targetSkill}
          onChange={(e) => setTargetSkill(e.target.value)}
          placeholder="e.g. eisenhower, career, finance"
        />
      </div>

      <p className="mb-4 rounded-lg bg-muted p-3 text-xs text-muted-foreground">
        Supported formats: Eisenhower matrices, career data, finance goals, health tracking, and generic tasks.
        Format is auto-detected from content structure.
      </p>

      {error && <p className="mb-3 text-xs text-destructive">{error}</p>}

      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="outline" onClick={onBack}>
          Cancel
        </Button>
        <Button
          variant="success"
          onClick={handleImport}
          disabled={!path.trim()}
          isLoading={importing}
        >
          Import
        </Button>
      </div>
    </div>
  );
}
