'use client';

import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface StepHeaderProps {
  title: string;
  onBack: () => void;
  trailingText?: string;
}

export function StepHeader({ title, onBack, trailingText }: StepHeaderProps) {
  return (
    <div className="mb-5 flex items-center gap-2">
      <Button variant="ghost" size="icon-sm" onClick={onBack}>
        <ArrowLeft className="size-4" />
      </Button>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {trailingText && (
        <span className="ml-auto max-w-[200px] truncate text-xs text-muted-foreground">
          {trailingText}
        </span>
      )}
    </div>
  );
}
