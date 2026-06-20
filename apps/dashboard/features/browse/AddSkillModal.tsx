'use client';

import React, { useState, useCallback } from 'react';
import { toast } from 'sonner';
import { Dialog, DialogContent } from '@/components/ui/Dialog';
import { runCliExecPrompt } from '@/lib/browse/cliExecClient';
import { AddSkillCards, type AddSkillStep } from './AddSkillCards';
import { InstallFromUrl } from './InstallFromUrl';
import { ImportDataFolder } from './ImportDataFolder';
import { ImportFromNotion } from './ImportFromNotion';
import { PromoteClientSkill } from './PromoteClientSkill';

interface AddSkillModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddSkillModal({ open, onOpenChange }: AddSkillModalProps) {
  const [step, setStep] = useState<AddSkillStep>('cards');

  const handleClose = useCallback(() => {
    onOpenChange(false);
    // Reset to cards after close animation
    setTimeout(() => setStep('cards'), 200);
  }, [onOpenChange]);

  const handleIdeDispatch = useCallback(
    (_actionId: string, prompt: string) => {
      handleClose();
      const toastId = toast.loading('Running Add Skill prompt...');
      void runCliExecPrompt(prompt)
        .then(() => toast.success('Add Skill prompt completed', { id: toastId }))
        .catch((error) => {
          const message = error instanceof Error ? error.message : 'Add Skill prompt failed';
          toast.error(message, { id: toastId });
        });
    },
    [handleClose],
  );

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (nextOpen) {
        onOpenChange(true);
        return;
      }
      handleClose();
    },
    [handleClose, onOpenChange],
  );

  const handleBack = useCallback(() => setStep('cards'), []);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        {step === 'cards' && (
          <AddSkillCards onSelectStep={setStep} onIdeDispatch={handleIdeDispatch} />
        )}
        {step === 'install-url' && (
          <InstallFromUrl onBack={handleBack} onClose={handleClose} />
        )}
        {step === 'import-data' && (
          <ImportDataFolder onBack={handleBack} onClose={handleClose} />
        )}
        {step === 'import-notion' && (
          <ImportFromNotion onBack={handleBack} onClose={handleClose} />
        )}
        {step === 'promote' && (
          <PromoteClientSkill onBack={handleBack} onClose={handleClose} />
        )}
      </DialogContent>
    </Dialog>
  );
}
