"use client";

import { useState } from "react";
import {
  Layers,
  Sparkle,
  Sparkles,
  Cpu,
  Gem,
  Zap,
  Users,
  Settings,
  CheckCircle,
  XCircle,
  Key,
  ExternalLink,
  Loader2,
  Globe,
} from "lucide-react";
import type { ProviderDefinition, ProviderConfig } from "@/lib/remote/types";
import { getProviderColorClass } from "@/lib/remote/providers";
import { GlassCard } from "@/components/ui/GlassCard";
import { Button } from "@/components/ui/Button";

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  Layers,
  Sparkle,
  Sparkles,
  Cpu,
  Gem,
  Zap,
  Users,
  Settings,
};

interface ProviderCardProps {
  provider: ProviderDefinition;
  config?: ProviderConfig;
  onConfigure: (providerId: string) => void;
  onTest?: (
    providerId: string,
  ) => Promise<{ success: boolean; latencyMs?: number; error?: string }>;
}

function ProviderStatusBadge({
  isConfigured,
  isEnabled,
}: {
  isConfigured: boolean;
  isEnabled: boolean;
}) {
  if (!isConfigured) {
    return null;
  }

  if (isEnabled) {
    return (
      <div className="absolute top-3 right-3">
        <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-[var(--accent-success)]/20 text-[var(--accent-success)] text-xs font-medium">
          <CheckCircle className="size-3" />
          <span>Active</span>
        </div>
      </div>
    );
  }

  return (
    <div className="absolute top-3 right-3">
      <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-[var(--bg-hover)] text-[var(--text-muted)] text-xs font-medium">
        <XCircle className="size-3" />
        <span>Disabled</span>
      </div>
    </div>
  );
}

function PricingBlock({ provider }: { provider: ProviderDefinition }) {
  return (
    <div className="mb-4 p-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-[var(--text-muted)] uppercase tracking-wide">
          Pricing (per 1M tokens)
        </span>
        <span className="text-xs text-[var(--text-muted)]">
          {provider.pricing.model}
        </span>
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <span
          className={`text-lg font-bold ${getProviderColorClass(provider.id)}`}
        >
          ${provider.pricing.inputPer1M.toFixed(2)}
        </span>
        <span className="text-sm text-[var(--text-muted)]">in</span>
        <span className="text-[var(--text-muted)] mx-1">/</span>
        <span
          className={`text-lg font-bold ${getProviderColorClass(provider.id)}`}
        >
          ${provider.pricing.outputPer1M.toFixed(2)}
        </span>
        <span className="text-sm text-[var(--text-muted)]">out</span>
      </div>
    </div>
  );
}

function AuthMethodBadge({
  authMethod,
}: {
  authMethod: ProviderDefinition["authMethod"];
}) {
  if (authMethod === "oauth") {
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--accent-info)]/20 text-[var(--accent-info)] text-xs font-medium">
        <ExternalLink className="size-3" />
        <span>OAuth</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--accent-warning)]/20 text-[var(--accent-warning)] text-xs font-medium">
      <Key className="size-3" />
      <span>API Key</span>
    </div>
  );
}

function ProviderWebsiteLink({ websiteUrl }: { websiteUrl?: string }) {
  if (!websiteUrl) {
    return null;
  }

  return (
    <a
      href={websiteUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] text-xs font-medium transition-colors"
    >
      <Globe className="size-3" />
      <span>Website</span>
    </a>
  );
}

function LastTestedLabel({ lastTested }: { lastTested?: string }) {
  if (!lastTested) {
    return null;
  }

  return (
    <div className="text-xs text-[var(--text-muted)]">
      Tested {new Date(lastTested).toLocaleDateString()}
    </div>
  );
}

function TestResultBanner({
  result,
}: {
  result: { success: boolean; latencyMs?: number; error?: string } | null;
}) {
  if (!result) {
    return null;
  }

  if (result.success) {
    return (
      <div className="mb-4 p-3 rounded-lg text-sm bg-[var(--accent-success)]/10 border border-[var(--accent-success)]/20 text-[var(--accent-success)]">
        <div className="flex items-center gap-2">
          <CheckCircle className="size-4" />
          <span>Connected successfully</span>
          {result.latencyMs && (
            <span className="text-[var(--text-muted)]">
              ({result.latencyMs}ms)
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="mb-4 p-3 rounded-lg text-sm bg-[var(--accent-danger)]/10 border border-[var(--accent-danger)]/20 text-[var(--accent-danger)]">
      <div className="flex items-center gap-2">
        <XCircle className="size-4" />
        <span>{result.error || "Connection failed"}</span>
      </div>
    </div>
  );
}

function TestConnectionButton({
  show,
  testing,
  onClick,
}: {
  show: boolean;
  testing: boolean;
  onClick: () => void;
}) {
  if (!show) {
    return null;
  }

  return (
    <Button
      onClick={onClick}
      disabled={testing}
      variant="outline"
      size="icon"
      className="w-10"
    >
      {testing ? <Loader2 className="size-4 animate-spin" /> : "Test"}
    </Button>
  );
}

export default function ProviderCard({
  provider,
  config,
  onConfigure,
  onTest,
}: ProviderCardProps) {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{
    success: boolean;
    latencyMs?: number;
    error?: string;
  } | null>(null);

  const Icon = iconMap[provider.icon] || Settings;
  const isConfigured = Boolean(config?.hasApiKey);
  const isEnabled = config?.enabled ?? false;

  const handleTest = async () => {
    if (!onTest || !isConfigured) {
      return;
    }

    setTesting(true);
    setTestResult(null);

    try {
      const result = await onTest(provider.id);
      setTestResult(result);
    } catch (error) {
      setTestResult({
        success: false,
        error: error instanceof Error ? error.message : "Test failed",
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <GlassCard
      className={`p-5 transition-all duration-300 ${
        isEnabled ? "ring-1 ring-emerald-500/30 border-emerald-500/20" : ""
      }`}
    >
      <ProviderStatusBadge isConfigured={isConfigured} isEnabled={isEnabled} />

      <div className="flex items-start gap-4 mb-4">
        <div
          className="size-12 rounded-xl flex items-center justify-center bg-gradient-to-br from-[var(--bg-hover)] to-transparent border border-[var(--border-color)]"
          style={{ backgroundColor: `${provider.brandColor}15` }}
        >
          <Icon className={`w-6 h-6 ${getProviderColorClass(provider.id)}`} />
        </div>

        <div className="flex-1 min-w-0 pr-16">
          <h3 className="text-lg font-semibold text-[var(--text-primary)] truncate">
            {provider.name}
          </h3>
          <p className="text-sm text-[var(--text-muted)] line-clamp-2 mt-0.5">
            {provider.description}
          </p>
        </div>
      </div>

      <PricingBlock provider={provider} />

      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <AuthMethodBadge authMethod={provider.authMethod} />
        <ProviderWebsiteLink websiteUrl={provider.websiteUrl} />
        <LastTestedLabel lastTested={config?.lastTested} />
      </div>

      <TestResultBanner result={testResult} />

      <div className="flex items-center gap-2">
        <Button
          onClick={() => onConfigure(provider.id)}
          variant={isConfigured ? "outline" : "solid"}
          className="flex-1"
        >
          {isConfigured ? "Configure" : "Set Up"}
        </Button>

        <TestConnectionButton
          show={Boolean(isConfigured && onTest)}
          testing={testing}
          onClick={handleTest}
        />
      </div>
    </GlassCard>
  );
}
