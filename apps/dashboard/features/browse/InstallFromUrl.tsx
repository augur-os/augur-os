'use client';

import Image from 'next/image';
import { useReducer, useCallback } from 'react';
import { ExternalLink, AlertTriangle, ShieldAlert, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { useMcpMutation } from '@/lib/mcp/useMcpMutation';
import { InstallSuccess } from './InstallSuccess';
import { StepHeader } from './StepHeader';
import type { SecurityCheck, SecurityStatus, Overlap, SourceInfo, BundleSkill } from './types';
import { HUB_IDS } from './types';

interface SkillManifest {
  name: string;
  description?: string;
  capabilities?: { name: string }[];
  suggested_bundle?: string;
}

interface AnalysisResult {
  manifest: SkillManifest;
  security: { checks: SecurityCheck[]; overall: SecurityStatus };
  overlaps: Overlap[];
  source: SourceInfo;
  is_bundle: boolean;
  bundle_skills?: BundleSkill[];
  bundle_total?: number;
}

type InternalStep = 'input' | 'review' | 'configure' | 'success';

interface InstallFromUrlProps {
  onBack: () => void;
  onClose: () => void;
}

interface InstalledSkillSummary {
  name: string;
  toolCount: number;
}

interface InstallFromUrlState {
  internalStep: InternalStep;
  url: string;
  intent: string;
  analysis: AnalysisResult | null;
  targetBundle: string;
  skillName: string;
  installedSkills: InstalledSkillSummary[];
}

type InstallFromUrlAction =
  | { type: 'set-step'; step: InternalStep }
  | { type: 'set-url'; url: string }
  | { type: 'set-intent'; intent: string }
  | { type: 'analysis-success'; analysis: AnalysisResult }
  | { type: 'set-target-bundle'; targetBundle: string }
  | { type: 'set-skill-name'; skillName: string }
  | { type: 'install-success'; skill: InstalledSkillSummary };

const INITIAL_INSTALL_FROM_URL_STATE: InstallFromUrlState = {
  internalStep: 'input',
  url: '',
  intent: '',
  analysis: null,
  targetBundle: '',
  skillName: '',
  installedSkills: [],
};

const passthroughImageLoader = ({ src }: { src: string }) => src;

function installFromUrlReducer(
  state: InstallFromUrlState,
  action: InstallFromUrlAction,
): InstallFromUrlState {
  switch (action.type) {
    case 'set-step':
      return { ...state, internalStep: action.step };
    case 'set-url':
      return { ...state, url: action.url };
    case 'set-intent':
      return { ...state, intent: action.intent };
    case 'analysis-success':
      return {
        ...state,
        analysis: action.analysis,
        skillName: action.analysis.manifest?.name || '',
        targetBundle: action.analysis.manifest?.suggested_bundle || '',
        internalStep: 'review',
      };
    case 'set-target-bundle':
      return { ...state, targetBundle: action.targetBundle };
    case 'set-skill-name':
      return { ...state, skillName: action.skillName };
    case 'install-success':
      return {
        ...state,
        installedSkills: [action.skill],
        internalStep: 'success',
      };
    default:
      return state;
  }
}

function normalizeAnalysis(raw: unknown): AnalysisResult {
  const data = raw as Record<string, unknown>;
  return {
    manifest: (data.manifest ?? {}) as SkillManifest,
    security: (data.security ?? { checks: [], overall: 'pass' }) as AnalysisResult['security'],
    overlaps: (data.overlaps ?? []) as Overlap[],
    source: (data.source ?? {}) as SourceInfo,
    is_bundle: Boolean(data.is_bundle),
    bundle_skills: (data.bundle_skills ?? []) as BundleSkill[],
    bundle_total: (data.bundle_total ?? 0) as number,
  };
}

export function InstallFromUrl({ onBack, onClose }: InstallFromUrlProps) {
  const [state, dispatch] = useReducer(
    installFromUrlReducer,
    INITIAL_INSTALL_FROM_URL_STATE,
  );
  const { analysis, internalStep, intent, installedSkills, skillName, targetBundle, url } = state;
  const { mutate: analyze, loading: analyzing, error: analyzeError } = useMcpMutation<AnalysisResult>(
    'install-skill',
    {
      staticArgs: { dry_run: true },
      select: normalizeAnalysis,
    },
  );
  const { mutate: install, loading: installing } = useMcpMutation<Record<string, unknown>>(
    'install-skill',
    {
      invalidates: ['browse-index'],
      onSuccess: () => {
        const name = skillName || analysis?.manifest?.name || 'skill';
        const toolCount = analysis?.manifest?.capabilities?.length ?? 0;
        dispatch({ type: 'install-success', skill: { name, toolCount } });
        toast.success(`${name} installed`);
      },
    },
  );

  const handleAnalyze = useCallback(async () => {
    if (!url.trim()) return;
    const result = await analyze({ source: url.trim(), intent: intent.trim() });
    if (result) {
      dispatch({ type: 'analysis-success', analysis: result });
    }
  }, [url, intent, analyze]);

  const handleInstall = useCallback(async () => {
    await install({
      source: url.trim(),
      dry_run: false,
      execute: true,
      target_bundle: targetBundle,
      target_skill: skillName,
      intent: intent.trim(),
    });
  }, [url, targetBundle, skillName, intent, install]);

  if (internalStep === 'success') {
    return (
      <InstallSuccess
        headline={`${installedSkills.length} skill${installedSkills.length !== 1 ? 's' : ''} installed`}
        subtitle={
          analysis?.source?.author
            ? `from ${analysis.manifest?.name} by ${analysis.source.author}`
            : undefined
        }
        skills={installedSkills}
        source={analysis?.source}
        onClose={onClose}
        onViewInBrowse={onClose}
      />
    );
  }

  return (
    <div>
      <StepHeader
        title="Install from URL"
        onBack={internalStep === 'input' ? onBack : () => dispatch({ type: 'set-step', step: 'input' })}
        trailingText={analysis?.source?.url?.replace('https://', '')}
      />
      {internalStep === 'input' && (
        <InstallInputStep
          url={url}
          intent={intent}
          analyzing={analyzing}
          analyzeError={analyzeError}
          onUrlChange={(nextUrl) => dispatch({ type: 'set-url', url: nextUrl })}
          onIntentChange={(nextIntent) => dispatch({ type: 'set-intent', intent: nextIntent })}
          onAnalyze={handleAnalyze}
        />
      )}
      {internalStep === 'review' && analysis && (
        <InstallReviewStep
          analysis={analysis}
          url={url}
          onBack={onBack}
          onConfigure={() => dispatch({ type: 'set-step', step: 'configure' })}
        />
      )}
      {internalStep === 'configure' && analysis && (
        <InstallConfigureStep
          analysis={analysis}
          installing={installing}
          skillName={skillName}
          targetBundle={targetBundle}
          onBack={() => dispatch({ type: 'set-step', step: 'review' })}
          onInstall={handleInstall}
          onSkillNameChange={(nextSkillName) =>
            dispatch({ type: 'set-skill-name', skillName: nextSkillName })
          }
          onTargetBundleChange={(nextTargetBundle) =>
            dispatch({ type: 'set-target-bundle', targetBundle: nextTargetBundle })
          }
        />
      )}
    </div>
  );
}

function InstallInputStep({
  url,
  intent,
  analyzing,
  analyzeError,
  onUrlChange,
  onIntentChange,
  onAnalyze,
}: {
  url: string;
  intent: string;
  analyzing: boolean;
  analyzeError: string | null;
  onUrlChange: (url: string) => void;
  onIntentChange: (intent: string) => void;
  onAnalyze: () => void;
}) {
  return (
    <div>
      <div className="mb-3">
        <label htmlFor="install-source-url" className="mb-1.5 block text-xs text-muted-foreground">
          GitHub URL, registry URL, or local path
        </label>
        <Input
          id="install-source-url"
          value={url}
          onChange={(event) => onUrlChange(event.target.value)}
          placeholder="https://github.com/user/skill-bundle"
        />
      </div>
      <div className="mb-4">
        <label htmlFor="install-intent" className="mb-1.5 block text-xs text-muted-foreground">
          What do you need? <span className="text-muted-foreground/40">(optional: helps filter and configure)</span>
        </label>
        <textarea
          id="install-intent"
          aria-label="Installation intent"
          value={intent}
          onChange={(event) => onIntentChange(event.target.value)}
          placeholder="Describe what you're looking for..."
          rows={3}
          className="flex w-full rounded-md border border-[var(--border-color)] bg-[var(--bg-secondary)] px-3 py-2 text-sm text-[var(--text-primary)] shadow-sm placeholder:text-[var(--text-muted)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--accent-primary)] disabled:cursor-not-allowed disabled:opacity-50 resize-y"
        />
      </div>
      <div className="flex justify-end">
        <Button variant="solid" onClick={onAnalyze} disabled={!url.trim()} isLoading={analyzing}>
          Analyze
        </Button>
      </div>
      {analyzeError && <p className="mt-2 text-xs text-destructive">{analyzeError}</p>}
    </div>
  );
}

function InstallReviewStep({
  analysis,
  url,
  onBack,
  onConfigure,
}: {
  analysis: AnalysisResult;
  url: string;
  onBack: () => void;
  onConfigure: () => void;
}) {
  return (
    <div>
      <SourceBanner analysis={analysis} url={url} />
      <SecurityReview analysis={analysis} />
      <BundleSkillsList analysis={analysis} />
      <OverlapWarnings overlaps={analysis.overlaps} />
      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="outline" onClick={onBack}>
          Cancel
        </Button>
        <Button variant="solid" onClick={onConfigure}>
          Configure
        </Button>
      </div>
    </div>
  );
}

function SourceBanner({ analysis, url }: { analysis: AnalysisResult; url: string }) {
  return (
    <div className="mb-4 rounded-lg border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-3">
        {analysis.source.avatar_url ? (
          <Image
            loader={passthroughImageLoader}
            src={analysis.source.avatar_url}
            alt=""
            unoptimized
            width={40}
            height={40}
            className="size-10 rounded-lg"
          />
        ) : (
          <div className="flex size-10 items-center justify-center rounded-lg bg-primary/20 text-primary font-bold">
            {(analysis.source.author || '?')[0].toUpperCase()}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-foreground">
              {analysis.manifest.name || 'Unknown'}
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span>by {analysis.source.author || 'Unknown'}</span>
            <span className="text-muted-foreground/30">|</span>
            <span>{analysis.source.license || 'Unknown'}</span>
            {(analysis.source.stars ?? 0) > 0 && (
              <>
                <span className="text-muted-foreground/30">|</span>
                <span>{analysis.source.stars} stars</span>
              </>
            )}
          </div>
        </div>
        {analysis.source.url?.includes('github.com') && (
          <a
            href={analysis.source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ExternalLink className="size-3.5" />
            View on GitHub
          </a>
        )}
      </div>
      <div className="rounded-md bg-background p-2 font-mono text-[11px] text-muted-foreground/60 truncate">
        {url}
      </div>
    </div>
  );
}

function SecurityReview({ analysis }: { analysis: AnalysisResult }) {
  return (
    <div className={`mb-4 rounded-lg border p-4 ${securityTone(analysis.security.overall)}`}>
      <div className="mb-2 flex items-center gap-2">
        {analysis.security.overall === 'pass' ? (
          <ShieldCheck className="size-4 text-green-500" />
        ) : (
          <ShieldAlert className="size-4 text-yellow-500" />
        )}
        <span className="text-sm font-semibold text-foreground">Security Review</span>
      </div>
      <div className="space-y-1">
        {analysis.security.checks.map((check) => (
          <SecurityCheckRow key={check.id} check={check} />
        ))}
      </div>
    </div>
  );
}

function securityTone(status: SecurityStatus) {
  if (status === 'danger') {
    return 'border-red-500/50 bg-red-950/20';
  }
  if (status === 'review') {
    return 'border-yellow-500/50 bg-yellow-950/20';
  }
  return 'border-green-500/50 bg-green-950/20';
}

function SecurityCheckRow({ check }: { check: SecurityCheck }) {
  const dotClass =
    check.status === 'pass'
      ? 'bg-green-500'
      : check.status === 'review'
        ? 'bg-yellow-500'
        : 'bg-red-500';
  const textClass =
    check.status === 'pass'
      ? 'text-green-400'
      : check.status === 'review'
        ? 'text-yellow-400'
        : 'text-red-400';

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className={`h-1.5 w-1.5 rounded-full ${dotClass}`} />
      <span className={textClass}>{check.detail}</span>
    </div>
  );
}

function BundleSkillsList({ analysis }: { analysis: AnalysisResult }) {
  if (!analysis.is_bundle || !analysis.bundle_skills?.length) {
    return null;
  }

  return (
    <div className="mb-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold text-foreground">
          Bundle: {analysis.bundle_total} skills
        </span>
      </div>
      <div className="space-y-1.5">
        {analysis.bundle_skills.map((skill) => (
          <div key={skill.name} className="flex items-center gap-3 rounded-lg border border-border bg-card p-3">
            <div className="flex-1 min-w-0">
              <span className="text-sm font-semibold text-foreground">{skill.name}</span>
              {skill.description && (
                <p className="mt-0.5 text-xs text-muted-foreground truncate">
                  {skill.description}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OverlapWarnings({ overlaps }: { overlaps: Overlap[] }) {
  if (overlaps.length === 0) {
    return null;
  }

  return (
    <div className="mb-4 rounded-lg border border-yellow-500/50 bg-yellow-950/20 p-4">
      <div className="mb-2 flex items-center gap-2">
        <AlertTriangle className="size-4 text-yellow-500" />
        <span className="text-sm font-semibold text-foreground">Overlap Detected</span>
      </div>
      {overlaps.map((overlap) => (
        <p key={`${overlap.incoming_skill}::${overlap.existing_skill}`} className="text-xs text-yellow-400">
          <strong>{overlap.incoming_skill}</strong> overlaps with <strong>{overlap.existing_skill}</strong>
          {overlap.conflicting_tools.length > 0 && (
            <>: conflicting tools: {overlap.conflicting_tools.join(', ')}</>
          )}
        </p>
      ))}
    </div>
  );
}

function InstallConfigureStep({
  analysis,
  installing,
  skillName,
  targetBundle,
  onBack,
  onInstall,
  onSkillNameChange,
  onTargetBundleChange,
}: {
  analysis: AnalysisResult;
  installing: boolean;
  skillName: string;
  targetBundle: string;
  onBack: () => void;
  onInstall: () => void;
  onSkillNameChange: (skillName: string) => void;
  onTargetBundleChange: (targetBundle: string) => void;
}) {
  return (
    <div>
      <div className="mb-4">
        <label htmlFor="install-target-hub" className="mb-1.5 block text-xs text-muted-foreground">
          Target hub
        </label>
        <Select id="install-target-hub" value={targetBundle} onChange={(event) => onTargetBundleChange(event.target.value)}>
          <option value="">auto-detect</option>
          {HUB_IDS.map((hub) => (
            <option key={hub} value={hub}>{hub}</option>
          ))}
        </Select>
      </div>
      <div className="mb-4">
        <label htmlFor="install-skill-name" className="mb-1.5 block text-xs text-muted-foreground">
          Skill name
        </label>
        <Input
          id="install-skill-name"
          value={skillName}
          onChange={(event) => onSkillNameChange(event.target.value)}
        />
      </div>
      <InstallSummary analysis={analysis} skillName={skillName} targetBundle={targetBundle} />
      <div className="flex justify-end gap-2 border-t border-border pt-3">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <Button variant="success" onClick={onInstall} isLoading={installing}>
          Install Skill
        </Button>
      </div>
    </div>
  );
}

function InstallSummary({
  analysis,
  skillName,
  targetBundle,
}: {
  analysis: AnalysisResult;
  skillName: string;
  targetBundle: string;
}) {
  return (
    <div className="mb-4 rounded-lg border border-border bg-card p-4 text-xs">
      <span className="font-semibold text-muted-foreground">Summary</span>
      <div className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <span className="text-muted-foreground/60">Install to</span>
        <span className="text-muted-foreground">project-brain/capabilities/skills/{skillName}/</span>
        <span className="text-muted-foreground/60">Hub</span>
        <span className="text-muted-foreground">{targetBundle || 'auto-detect'}</span>
        <span className="text-muted-foreground/60">MCP tools</span>
        <span className="text-muted-foreground">
          {analysis.manifest.capabilities?.length ?? 0} tools
        </span>
        {analysis.overlaps.length > 0 && (
          <>
            <span className="text-muted-foreground/60">Warnings</span>
            <span className="text-yellow-400">
              {analysis.overlaps.length} overlap{analysis.overlaps.length !== 1 ? 's' : ''}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
