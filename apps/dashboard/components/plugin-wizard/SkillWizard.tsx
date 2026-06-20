"use client";

import { useState } from "react";
import { useMcpMutation } from "@/lib/mcp/useMcpMutation";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { AlertCircle, Zap, Settings, Check } from "lucide-react";

interface SkillWizardProps {
  bundle: string;
  skill: string;
  skillTitle?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSetupComplete?: () => void;
  editorPath?: string;
}

type WizardStep = "choose" | "scaffolding" | "success";

export function SkillWizard({
  bundle,
  skill,
  skillTitle = skill
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase()),
  open,
  onOpenChange,
  onSetupComplete,
  editorPath,
}: SkillWizardProps) {
  const [step, setStep] = useState<WizardStep>("choose");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { mutate: scaffoldSkill } = useMcpMutation<{ error?: string }, { bundle: string; skill_name: string; title: string; description: string }>(
    "skill-action",
    { staticArgs: { action: "scaffold" } },
  );

  const { mutate: mountPlugins } = useMcpMutation<Record<string, unknown>, { bundle: string; skill_name: string }>(
    "skill-action",
    { staticArgs: { action: "mount" } },
  );

  const { mutate: openEditor } = useMcpMutation<Record<string, unknown>, { path: string }>(
    "open-file",
  );

  const handleQuickSetup = async () => {
    setLoading(true);
    setError(null);

    try {
      await scaffoldSkill({
        bundle,
        skill_name: skill,
        title: skillTitle,
        description: `${skillTitle} skill`,
      });

      try {
        await mountPlugins({ bundle, skill_name: skill });
      } catch {
        // Scaffold succeeded but mount failed — still consider it a success
        console.warn(
          "Scaffold succeeded but mount may need manual intervention",
        );
      }

      setStep("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
    } finally {
      setLoading(false);
    }
  };

  const handleConfigureManually = async () => {
    try {
      if (editorPath) {
        await openEditor({
          path: `plugins/${bundle}/skills/${skill}`,
        });
      }
    } catch {
      // Silently fail if editor open isn't available
    }

    handleIgnore();
  };

  const handleIgnore = () => {
    // Acknowledge the event if this was triggered from plugin watcher
    // The parent component handles the actual acknowledgement
    onOpenChange(false);
    setStep("choose");
    setError(null);
  };

  const handleClose = () => {
    onOpenChange(false);
    setStep("choose");
    setError(null);
  };

  const handleContinue = () => {
    onSetupComplete?.();
    handleClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        {step === "choose" && (
          <>
            <DialogHeader>
              <DialogTitle>Set Up New Skill</DialogTitle>
              <DialogDescription>
                New skill detected:{" "}
                <span className="font-medium text-[var(--text-primary)]">
                  {skillTitle}
                </span>
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4 py-4">
              {/* Quick Setup Option */}
              <button type="button"
                onClick={handleQuickSetup}
                disabled={loading}
                className="w-full p-4 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-secondary)] transition-colors text-left"
              >
                <div className="flex items-start gap-3">
                  <Zap className="size-5 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="font-medium text-[var(--text-primary)]">
                      Quick Setup
                    </p>
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Auto-generates SKILL.md metadata and a starter page.
                      We&apos;ll mount the skill immediately.
                    </p>
                  </div>
                </div>
              </button>

              {/* Configure Manually Option */}
              <button type="button"
                onClick={handleConfigureManually}
                disabled={loading}
                className="w-full p-4 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-secondary)] transition-colors text-left"
              >
                <div className="flex items-start gap-3">
                  <Settings className="size-5 text-amber-500 mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="font-medium text-[var(--text-primary)]">
                      Configure Manually
                    </p>
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Open the skill folder in your editor to set up from
                      scratch.
                    </p>
                  </div>
                </div>
              </button>

              {/* Error Display */}
              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                  <AlertCircle className="size-4 text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-400">{error}</p>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="ghost" onClick={handleIgnore} disabled={loading}>
                Ignore
              </Button>
              <Button
                variant="solid"
                onClick={handleQuickSetup}
                isLoading={loading}
                loadingText="Setting up..."
              >
                Quick Setup
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "scaffolding" && (
          <>
            <DialogHeader>
              <DialogTitle>Setting Up Skill</DialogTitle>
            </DialogHeader>

            <div className="py-8 flex items-center justify-center">
              <div className="text-center">
                <div className="motion-safe:animate-spin rounded-full size-8 border-b-2 border-[var(--accent-primary)] mx-auto mb-4"></div>
                <p className="text-sm text-[var(--text-muted)]">
                  Creating skill scaffold…
                </p>
              </div>
            </div>
          </>
        )}

        {step === "success" && (
          <>
            <DialogHeader>
              <DialogTitle>Skill Ready</DialogTitle>
              <DialogDescription>
                Your skill has been set up successfully
              </DialogDescription>
            </DialogHeader>

            <div className="py-6 flex flex-col items-center">
              <div className="size-12 rounded-full bg-[var(--accent-success)]/20 flex items-center justify-center mb-4">
                <Check className="size-6 text-[var(--accent-success)]" />
              </div>
              <p className="text-center text-[var(--text-primary)] mb-4">
                <span className="font-medium">{skillTitle}</span> is ready to
                use!
              </p>
              <p className="text-xs text-[var(--text-muted)] text-center">
                The skill has been scaffolded and mounted. Visit the plugin page
                to start customizing.
              </p>
            </div>

            <DialogFooter>
              <Button
                variant="solid"
                onClick={handleContinue}
                className="w-full"
              >
                Open skill page
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
