"use client";

import { useState, useEffect, useRef } from "react";
import {
  X,
  ExternalLink,
  Eye,
  EyeOff,
  CheckCircle,
  AlertTriangle,
  Loader2,
  Info,
  Copy,
  Check,
  Globe,
} from "lucide-react";
import type { ProviderDefinition, ProviderConfig } from "@/lib/remote/types";
import { Button } from "@/components/ui/Button";

interface ProviderConfigModalProps {
  provider: ProviderDefinition;
  config?: ProviderConfig;
  isOpen: boolean;
  onClose: () => void;
  onSave: (config: Partial<ProviderConfig>) => Promise<void>;
  onStartOAuth?: (providerId: string) => void | Promise<void>;
}

interface FormState {
  apiKey: string;
  showApiKey: boolean;
  defaultModel: string;
  enabled: boolean;
  error: string | null;
  copied: boolean;
  saving: boolean;
}

function createInitialState(
  provider: ProviderDefinition,
  config?: ProviderConfig,
): FormState {
  return {
    apiKey: "",
    showApiKey: false,
    defaultModel: config?.defaultModel || provider.defaultModel,
    enabled: config?.enabled ?? true,
    error: null,
    copied: false,
    saving: false,
  };
}

function ModalHeader({
  provider,
  onClose,
}: {
  provider: ProviderDefinition;
  onClose: () => void;
}) {
  const subtitle =
    provider.authMethod === "oauth"
      ? "Connect via OAuth"
      : "Enter your API key";

  return (
    <div className="flex items-center justify-between p-6 border-b border-[var(--border-color)]">
      <div>
        <h2 className="text-xl font-semibold text-[var(--text-primary)]">
          Configure {provider.name}
        </h2>
        <p className="text-sm text-[var(--text-muted)] mt-1">{subtitle}</p>
      </div>
      <button type="button"
        onClick={onClose}
        aria-label="Close configuration modal"
        className="p-2 rounded-lg hover:bg-[var(--bg-hover)] transition-colors"
      >
        <X className="size-5 text-[var(--text-muted)]" />
      </button>
    </div>
  );
}

function OAuthConnectedState({
  provider,
  onStartOAuth,
}: {
  provider: ProviderDefinition;
  onStartOAuth?: (providerId: string) => void | Promise<void>;
}) {
  return (
    <div className="p-4 rounded-lg bg-[var(--accent-success)]/10 border border-[var(--accent-success)]/20">
      <div className="flex items-start gap-3">
        <CheckCircle className="size-5 text-[var(--accent-success)] mt-0.5" />
        <div className="flex-1">
          <p className="font-medium text-[var(--accent-success)]">
            Connected via OAuth
          </p>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Your {provider.name} account is connected and ready to use.
          </p>
          <button type="button"
            onClick={() => onStartOAuth?.(provider.id)}
            className="mt-3 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] underline transition-colors"
          >
            Reconnect with different account
          </button>
        </div>
      </div>
    </div>
  );
}

function OAuthDisconnectedState({
  provider,
  onStartOAuth,
}: {
  provider: ProviderDefinition;
  onStartOAuth?: (providerId: string) => void | Promise<void>;
}) {
  return (
    <>
      <div className="p-4 rounded-lg bg-[var(--accent-info)]/10 border border-[var(--accent-info)]/20">
        <div className="flex items-start gap-3">
          <ExternalLink className="size-5 text-[var(--accent-info)] mt-0.5" />
          <div>
            <p className="font-medium text-[var(--accent-info)]">
              One-Click Setup
            </p>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Connect securely via OAuth. You&apos;ll be redirected to{" "}
              {provider.name} to authorize access.
            </p>
          </div>
        </div>
      </div>

      <button type="button"
        onClick={() => onStartOAuth?.(provider.id)}
        className="w-full px-4 py-3 rounded-lg font-medium bg-gradient-to-r from-[var(--accent-primary)] to-[var(--accent-secondary)] text-[var(--accent-foreground)] hover:opacity-90 transition-opacity flex items-center justify-center gap-2"
      >
        <ExternalLink className="size-4" />
        Connect with {provider.name}
      </button>
    </>
  );
}

function OAuthSection({
  provider,
  hasApiKey,
  onStartOAuth,
}: {
  provider: ProviderDefinition;
  hasApiKey: boolean;
  onStartOAuth?: (providerId: string) => void | Promise<void>;
}) {
  if (provider.authMethod !== "oauth") {
    return null;
  }

  return (
    <div className="space-y-4">
      {hasApiKey ? (
        <OAuthConnectedState provider={provider} onStartOAuth={onStartOAuth} />
      ) : (
        <OAuthDisconnectedState
          provider={provider}
          onStartOAuth={onStartOAuth}
        />
      )}

      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-[var(--border-color)]" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="px-2 bg-[var(--bg-primary)] text-[var(--text-muted)]">
            {hasApiKey
              ? "or update API key manually"
              : "or enter API key manually"}
          </span>
        </div>
      </div>
    </div>
  );
}

function ApiKeyLabel({ hasApiKey }: { hasApiKey: boolean }) {
  return hasApiKey ? "(currently set)" : "(not configured)";
}

function ApiKeyHint({ copied }: { copied: boolean }) {
  if (copied) {
    return (
      <>
        <Check className="size-3" />
        Copied!
      </>
    );
  }

  return (
    <>
      <Copy className="size-3" />
      Copy export command
    </>
  );
}

function ApiKeySection({
  provider,
  hasApiKey,
  apiKey,
  showApiKey,
  copied,
  onApiKeyChange,
  onToggleShowApiKey,
  onCopyEnvVar,
}: {
  provider: ProviderDefinition;
  hasApiKey: boolean;
  apiKey: string;
  showApiKey: boolean;
  copied: boolean;
  onApiKeyChange: (value: string) => void;
  onToggleShowApiKey: () => void;
  onCopyEnvVar: () => void;
}) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label htmlFor={`provider-api-key-${provider.id}`} className="block">
          <span className="text-sm font-medium text-[var(--text-primary)]">
            API Key
          </span>
          <span className="text-xs text-[var(--text-muted)] ml-2">
            <ApiKeyLabel hasApiKey={hasApiKey} />
          </span>
        </label>
        {provider.websiteUrl && (
          <a
            href={provider.websiteUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          >
            <Globe className="size-3" />
            <span>Get API Key</span>
            <ExternalLink className="size-3" />
          </a>
        )}
      </div>

      <div className="relative">
        <input
          id={`provider-api-key-${provider.id}`}
          type={showApiKey ? "text" : "password"}
          value={apiKey}
          onChange={(e) => onApiKeyChange(e.target.value)}
          placeholder={hasApiKey ? "••••••••••••••••" : "Enter your API key"}
          aria-label="API key"
          className="w-full px-4 py-3 pr-12 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 focus:border-[var(--accent-primary)]/50 transition-all font-mono text-sm"
        />
        <button
          type="button"
          onClick={onToggleShowApiKey}
          aria-label={showApiKey ? "Hide API key" : "Show API key"}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 rounded hover:bg-[var(--bg-hover)] transition-colors"
        >
          {showApiKey ? (
            <EyeOff className="size-4 text-[var(--text-muted)]" />
          ) : (
            <Eye className="size-4 text-[var(--text-muted)]" />
          )}
        </button>
      </div>

      <div className="p-3 rounded-lg bg-[var(--accent-warning)]/10 border border-[var(--accent-warning)]/20">
        <div className="flex items-start gap-2">
          <Info className="size-4 text-[var(--accent-warning)] mt-0.5 flex-shrink-0" />
          <div className="text-sm">
            <p className="text-[var(--accent-warning)] font-medium">
              Recommended: Use environment variable
            </p>
            <p className="text-[var(--text-muted)] mt-1">
              Set{" "}
              <code className="px-1.5 py-0.5 rounded bg-[var(--bg-secondary)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)]">
                {provider.apiKeyEnv}
              </code>{" "}
              in your environment for better security.
            </p>
            <button type="button"
              onClick={onCopyEnvVar}
              className="mt-2 flex items-center gap-1.5 text-xs text-[var(--accent-warning)] hover:opacity-80 transition-opacity"
            >
              <ApiKeyHint copied={copied} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ModelSection({
  provider,
  defaultModel,
  onChange,
}: {
  provider: ProviderDefinition;
  defaultModel: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="space-y-3">
      <label htmlFor={`provider-default-model-${provider.id}`} className="block">
        <span className="text-sm font-medium text-[var(--text-primary)]">
          Default Model
        </span>
      </label>
      <input
        id={`provider-default-model-${provider.id}`}
        type="text"
        value={defaultModel}
        onChange={(e) => onChange(e.target.value)}
        placeholder={provider.defaultModel}
        aria-label="Default model"
        className="w-full px-4 py-3 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]/50 focus:border-[var(--accent-primary)]/50 transition-all font-mono text-sm"
      />
      <p className="text-xs text-[var(--text-muted)]">
        The model to use by default. Leave blank to use {provider.defaultModel}.
      </p>
    </div>
  );
}

function EnabledSection({
  enabled,
  onToggle,
}: {
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-center justify-between p-4 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)]">
      <div>
        <p className="font-medium text-[var(--text-primary)]">
          Enable Provider
        </p>
        <p className="text-sm text-[var(--text-muted)]">
          Allow this provider to be used for remote execution
        </p>
      </div>
      <button type="button"
        onClick={onToggle}
        role="switch"
        aria-checked={enabled}
        aria-label="Enable provider"
        className={`
          relative w-12 h-7 rounded-full transition-colors
          ${enabled ? "bg-[var(--accent-success)]" : "bg-[var(--bg-hover)] border border-[var(--border-color)]"}
        `}
      >
        <span
          className={`
            absolute top-1 size-5 rounded-full bg-white shadow-sm transition-transform
            ${enabled ? "left-6" : "left-1"}
          `}
        />
      </button>
    </div>
  );
}

function ErrorBanner({ error }: { error: string | null }) {
  if (!error) {
    return null;
  }

  return (
    <div className="p-4 rounded-lg bg-[var(--accent-danger)]/10 border border-[var(--accent-danger)]/20">
      <div className="flex items-start gap-2">
        <AlertTriangle className="size-4 text-[var(--accent-danger)] mt-0.5" />
        <p className="text-sm text-[var(--accent-danger)]">{error}</p>
      </div>
    </div>
  );
}

function Footer({
  saving,
  onClose,
  onSave,
}: {
  saving: boolean;
  onClose: () => void;
  onSave: () => void;
}) {
  return (
    <div className="flex items-center justify-end gap-3 p-6 border-t border-[var(--border-color)]">
      <Button variant="outline" onClick={onClose}>
        Cancel
      </Button>
      <Button onClick={onSave} disabled={saving}>
        {saving ? (
          <>
            <Loader2 className="size-4 animate-spin mr-2" />
            Saving…
          </>
        ) : (
          <>
            <CheckCircle className="size-4 mr-2" />
            Save Configuration
          </>
        )}
      </Button>
    </div>
  );
}

export default function ProviderConfigModal({
  provider,
  config,
  isOpen,
  onClose,
  onSave,
  onStartOAuth,
}: ProviderConfigModalProps) {
  const [form, setForm] = useState<FormState>(() =>
    createInitialState(provider, config),
  );
  const copyTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);

  useEffect(() => {
    if (isOpen) {
      const timer = window.setTimeout(() => {
        setForm(createInitialState(provider, config));
      }, 0);
      return () => window.clearTimeout(timer);
    }
  }, [isOpen, config, provider]);

  useEffect(() => () => clearTimeout(copyTimerRef.current), []);

  const updateForm = (patch: Partial<FormState>) => {
    setForm((current) => ({ ...current, ...patch }));
  };

  const handleSave = async () => {
    updateForm({ saving: true, error: null });

    try {
      await onSave({
        id: provider.id,
        enabled: form.enabled,
        defaultModel: form.defaultModel,
        ...(form.apiKey ? { apiKey: form.apiKey } : {}),
      });
      onClose();
    } catch (err) {
      updateForm({
        error:
          err instanceof Error ? err.message : "Failed to save configuration",
      });
    } finally {
      updateForm({ saving: false });
    }
  };

  const handleCopyEnvVar = () => {
    navigator.clipboard.writeText(
      `export ${provider.apiKeyEnv}="your-api-key-here"`,
    );
    updateForm({ copied: true });
    clearTimeout(copyTimerRef.current);
    copyTimerRef.current = setTimeout(() => updateForm({ copied: false }), 2000);
  };

  const handleStartOAuth = async (providerId: string) => {
    updateForm({ error: null });
    try {
      await onStartOAuth?.(providerId);
    } catch (err) {
      updateForm({
        error: err instanceof Error ? err.message : "Failed to start OAuth",
      });
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="glass-panel w-full max-w-lg max-h-[90vh] flex flex-col rounded-2xl border border-[var(--border-color)] shadow-2xl">
        <ModalHeader provider={provider} onClose={onClose} />

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          <OAuthSection
            provider={provider}
            hasApiKey={Boolean(config?.hasApiKey)}
            onStartOAuth={handleStartOAuth}
          />

          <ApiKeySection
            provider={provider}
            hasApiKey={Boolean(config?.hasApiKey)}
            apiKey={form.apiKey}
            showApiKey={form.showApiKey}
            copied={form.copied}
            onApiKeyChange={(value) => updateForm({ apiKey: value })}
            onToggleShowApiKey={() =>
              updateForm({ showApiKey: !form.showApiKey })
            }
            onCopyEnvVar={handleCopyEnvVar}
          />

          <ModelSection
            provider={provider}
            defaultModel={form.defaultModel}
            onChange={(value) => updateForm({ defaultModel: value })}
          />

          <EnabledSection
            enabled={form.enabled}
            onToggle={() => updateForm({ enabled: !form.enabled })}
          />

          <ErrorBanner error={form.error} />
        </div>

        <Footer saving={form.saving} onClose={onClose} onSave={handleSave} />
      </div>
    </div>
  );
}
