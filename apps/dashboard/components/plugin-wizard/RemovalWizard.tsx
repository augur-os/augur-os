"use client";

const EMPTY_ARRAY: never[] = [];

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
import {
  AlertCircle,
  Trash2,
  RotateCcw,
  Zap,
  Check,
  Sparkles,
} from "lucide-react";

interface Dependency {
  skill: string;
  bundle: string;
  required: boolean;
}

interface RemovalWizardProps {
  bundle: string;
  skill: string;
  skillTitle?: string;
  dependentSkills?: Dependency[];
  canRestore?: boolean;
  /** When true, the skill is already removed from the filesystem (watcher event).
   *  Primary action becomes "Clean Up" (mount cleanup only) instead of "Remove" (archive). */
  alreadyRemoved?: boolean;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCleanupComplete?: () => void;
  onRestoreComplete?: () => void;
}

type WizardStep = "confirm" | "cleaning" | "success";

function DependencyNotice({
  dependencies,
  required,
}: {
  dependencies: Dependency[];
  required: boolean;
}) {
  if (dependencies.length === 0) return null;

  const Icon = required ? AlertCircle : Zap;
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
      <Icon className={`size-5 ${required ? "text-[var(--accent-warning)]" : "text-[var(--accent-primary)]"} mt-0.5 flex-shrink-0`} />
      <div className="flex-1">
        <p className="font-medium text-sm text-[var(--text-primary)] mb-1">
          {required ? "Required Dependencies" : "Optional Dependencies"}
        </p>
        <p className="text-xs text-[var(--text-muted)]">
          {dependencies.length} skill{dependencies.length !== 1 ? "s" : ""}{" "}
          {required ? "depend on this and may break:" : "optionally use this:"}
        </p>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {dependencies.map((dep) => (
            <span
              key={`${dep.bundle}/${dep.skill}`}
              className={`text-[10px] font-mono px-1.5 py-0.5 rounded border border-[var(--border-color)] bg-[var(--bg-primary)] ${required ? "text-[var(--text-secondary)]" : "text-[var(--text-muted)]"}`}
            >
              {dep.bundle}/{dep.skill}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export function RemovalWizard({
  bundle,
  skill,
  skillTitle = skill
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase()),
  dependentSkills = EMPTY_ARRAY,
  canRestore = false,
  alreadyRemoved = false,
  open,
  onOpenChange,
  onCleanupComplete,
  onRestoreComplete,
}: RemovalWizardProps) {
  const [step, setStep] = useState<WizardStep>("confirm");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const requiredDependents = dependentSkills.filter((d) => d.required);
  const optionalDependents = dependentSkills.filter((d) => !d.required);
  const hasDependents = dependentSkills.length > 0;

  const { mutate: uninstallSkill } = useMcpMutation<{ error?: string }, { bundle: string; skill: string }>(
    "skill-action",
    { staticArgs: { action: "uninstall" } },
  );

  const { mutate: mountPlugins } = useMcpMutation<Record<string, unknown>, { cleanup?: boolean; bundle?: string; skill?: string }>(
    "skill-action",
    { staticArgs: { action: "mount" } },
  );

  const { mutate: restoreSkill } = useMcpMutation<{ error?: string }, { bundle: string; skill: string }>(
    "skill-action",
    { staticArgs: { action: "restore" } },
  );

  const handleCleanup = async () => {
    setLoading(true);
    setError(null);
    setStep("cleaning");

    try {
      if (!alreadyRemoved) {
        await uninstallSkill({ bundle, skill });
      }

      try {
        await mountPlugins({ cleanup: true });
      } catch {
        console.warn("Cleanup may need manual attention");
      }

      setStep("success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      setStep("confirm");
    } finally {
      setLoading(false);
    }
  };

  const handleRestore = async () => {
    setLoading(true);
    setError(null);
    setStep("cleaning");

    try {
      await restoreSkill({ bundle, skill });

      try {
        await mountPlugins({ bundle, skill });
      } catch {
        console.warn("Restore succeeded but mount may need manual attention");
      }

      setStep("success");
      onRestoreComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      setStep("confirm");
    } finally {
      setLoading(false);
    }
  };

  const handleIgnore = () => {
    onOpenChange(false);
    setStep("confirm");
    setError(null);
  };

  const handleClose = () => {
    onOpenChange(false);
    setStep("confirm");
    setError(null);
  };

  const handleContinue = () => {
    onCleanupComplete?.();
    handleClose();
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-md">
        {step === "confirm" && (
          <>
            <DialogHeader>
              <DialogTitle>
                {alreadyRemoved ? "Clean Up Removed Skill" : "Remove Skill"}
              </DialogTitle>
              <DialogDescription>
                {alreadyRemoved ? "Cleaning up" : "Removing"}{" "}
                <span className="font-medium text-[var(--text-primary)]">
                  {skillTitle}
                </span>
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 px-6 py-4">
              <DependencyNotice dependencies={requiredDependents} required />
              <DependencyNotice dependencies={optionalDependents} required={false} />

              {/* Safe removal message */}
              {!hasDependents && (
                <div className="flex items-center gap-3 p-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)]">
                  <Check className="size-5 text-[var(--accent-success)] flex-shrink-0" />
                  <p className="text-sm text-[var(--text-secondary)]">
                    No other skills depend on this one. It&apos;s safe to{" "}
                    {alreadyRemoved ? "clean up" : "remove"}.
                  </p>
                </div>
              )}

              {/* Error Display */}
              {error && (
                <div className="flex items-start gap-2 p-3 rounded-lg border border-[var(--accent-danger)]/20 bg-[var(--accent-danger)]/5">
                  <AlertCircle className="size-4 text-[var(--accent-danger)] flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-[var(--accent-danger)]">{error}</p>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button variant="ghost" onClick={handleIgnore} disabled={loading}>
                {alreadyRemoved ? "Ignore" : "Keep Skill"}
              </Button>
              {canRestore && (
                <Button
                  variant="outline"
                  onClick={handleRestore}
                  disabled={loading}
                  isLoading={loading}
                  loadingText="Restoring..."
                  leftIcon={<RotateCcw className="size-4" />}
                >
                  Restore
                </Button>
              )}
              <Button
                variant={alreadyRemoved ? "solid" : "danger"}
                onClick={handleCleanup}
                isLoading={loading}
                loadingText={alreadyRemoved ? "Cleaning up..." : "Removing..."}
                leftIcon={
                  alreadyRemoved ? (
                    <Sparkles className="size-4" />
                  ) : (
                    <Trash2 className="size-4" />
                  )
                }
              >
                {alreadyRemoved ? "Clean Up" : "Remove"}
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "cleaning" && (
          <>
            <DialogHeader>
              <DialogTitle>
                {alreadyRemoved ? "Cleaning Up" : "Removing Skill"}
              </DialogTitle>
            </DialogHeader>

            <div className="py-8 flex items-center justify-center">
              <div className="text-center">
                <div className="motion-safe:animate-spin rounded-full size-8 border-b-2 border-[var(--accent-primary)] mx-auto mb-4" />
                <p className="text-sm text-[var(--text-muted)]">
                  {alreadyRemoved
                    ? "Cleaning up stale routes..."
                    : "Archiving skill and cleaning up..."}
                </p>
              </div>
            </div>
          </>
        )}

        {step === "success" && (
          <>
            <DialogHeader>
              <DialogTitle>
                {alreadyRemoved ? "Cleanup Complete" : "Skill Removed"}
              </DialogTitle>
              <DialogDescription>
                {alreadyRemoved
                  ? "Stale routes have been cleaned up"
                  : "The skill has been safely archived"}
              </DialogDescription>
            </DialogHeader>

            <div className="py-6 flex flex-col items-center">
              <div className="size-12 rounded-full bg-[var(--accent-success)]/20 flex items-center justify-center mb-4">
                <Check className="size-6 text-[var(--accent-success)]" />
              </div>
              <p className="text-center text-[var(--text-primary)] mb-2">
                <span className="font-medium">{skillTitle}</span>{" "}
                {alreadyRemoved ? "has been cleaned up" : "has been removed"}
              </p>
              {!alreadyRemoved && (
                <p className="text-xs text-[var(--text-muted)] text-center mb-2">
                  Archived to{" "}
                  <span className="font-mono text-[var(--text-secondary)]">
                    plugins/.archive/
                  </span>{" "}
                  and can be restored from settings.
                </p>
              )}
              {requiredDependents.length > 0 && (
                <p className="text-xs text-[var(--accent-warning)] text-center">
                  Review the {requiredDependents.length} affected skill
                  {requiredDependents.length !== 1 ? "s" : ""} to ensure they
                  still work.
                </p>
              )}
            </div>

            <DialogFooter>
              <Button
                variant="solid"
                onClick={handleContinue}
                className="w-full"
              >
                Review changes
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
