/**
 * Remote LLM Providers - Provider Registry
 *
 * Central registry of all supported LLM providers with their configurations,
 * pricing data, and capabilities. This serves as the single source of truth
 * for provider metadata.
 */

import type { ProviderDefinition, ProviderId } from "./types";

// =============================================================================
// Provider Definitions
// =============================================================================

export const PROVIDER_REGISTRY: Record<ProviderId, ProviderDefinition> = {
  glama: {
    id: "glama",
    name: "Glama",
    description:
      "Zero markup gateway with OAuth. Pay provider prices directly, no hidden fees.",
    authMethod: "oauth",
    baseUrl: "https://glama.ai/api/gateway/openai/v1",
    oauthUrl: "https://glama.ai/oauth/authorize",
    defaultModel: "anthropic/claude-sonnet-4",
    pricing: {
      inputPer1M: 3.0,
      outputPer1M: 15.0,
      model: "Claude Sonnet 4 (no markup)",
    },
    apiKeyEnv: "GLAMA_API_KEY",
    available: true,
    icon: "Sparkle",
    brandColor: "#06b6d4", // Cyan
    websiteUrl: "https://glama.ai",
  },

  openrouter: {
    id: "openrouter",
    name: "OpenRouter",
    description:
      "Multi-provider gateway with OAuth. Access 100+ models (5.5% fee).",
    authMethod: "oauth",
    baseUrl: "https://openrouter.ai/api/v1",
    oauthUrl: "https://openrouter.ai/auth",
    defaultModel: "anthropic/claude-sonnet-4",
    pricing: {
      inputPer1M: 3.17,
      outputPer1M: 15.83,
      model: "Claude Sonnet 4 (+5.5%)",
    },
    apiKeyEnv: "OPENROUTER_API_KEY",
    available: true,
    icon: "Layers",
    brandColor: "#6366f1", // Indigo
    websiteUrl: "https://openrouter.ai",
  },

  anthropic: {
    id: "anthropic",
    name: "Anthropic",
    description: "Direct access to Claude models with lowest latency.",
    authMethod: "manual",
    baseUrl: "https://api.anthropic.com/v1",
    defaultModel: "claude-sonnet-4-20250514",
    pricing: {
      inputPer1M: 3.0,
      outputPer1M: 15.0,
      model: "Claude Sonnet 4",
    },
    apiKeyEnv: "ANTHROPIC_API_KEY",
    available: true,
    icon: "Sparkles",
    brandColor: "#d97706", // Amber (Anthropic orange)
    websiteUrl: "https://console.anthropic.com",
  },

  openai: {
    id: "openai",
    name: "OpenAI",
    description: "GPT models including GPT-4o and o1 reasoning models.",
    authMethod: "manual",
    baseUrl: "https://api.openai.com/v1",
    defaultModel: "gpt-4o",
    pricing: {
      inputPer1M: 2.5,
      outputPer1M: 10.0,
      model: "GPT-4o",
    },
    apiKeyEnv: "OPENAI_API_KEY",
    available: true,
    icon: "Cpu",
    brandColor: "#10b981", // Emerald (OpenAI green)
    websiteUrl: "https://platform.openai.com",
  },

  gemini: {
    id: "gemini",
    name: "Google Gemini",
    description: "Google's Gemini models with multimodal capabilities.",
    authMethod: "manual",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta",
    defaultModel: "gemini-pro",
    pricing: {
      inputPer1M: 1.25,
      outputPer1M: 5.0,
      model: "Gemini Pro",
    },
    apiKeyEnv: "GOOGLE_AI_API_KEY",
    available: true,
    icon: "Gem",
    brandColor: "#3b82f6", // Blue (Google blue)
    websiteUrl: "https://aistudio.google.com",
  },

  groq: {
    id: "groq",
    name: "Groq",
    description:
      "Ultra-fast inference with custom LPU hardware. Best for speed.",
    authMethod: "manual",
    baseUrl: "https://api.groq.com/openai/v1",
    defaultModel: "llama-3.3-70b-versatile",
    pricing: {
      inputPer1M: 0.59,
      outputPer1M: 0.79,
      model: "Llama 3.3 70B",
    },
    apiKeyEnv: "GROQ_API_KEY",
    available: true,
    icon: "Zap",
    brandColor: "#f97316", // Orange (Groq orange)
    websiteUrl: "https://console.groq.com",
  },

  together: {
    id: "together",
    name: "Together.ai",
    description: "Open-source models with competitive pricing and fine-tuning.",
    authMethod: "manual",
    baseUrl: "https://api.together.xyz/v1",
    defaultModel: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    pricing: {
      inputPer1M: 0.88,
      outputPer1M: 0.88,
      model: "Llama 3.3 70B Turbo",
    },
    apiKeyEnv: "TOGETHER_API_KEY",
    available: true,
    icon: "Users",
    brandColor: "#8b5cf6", // Violet
    websiteUrl: "https://api.together.ai",
  },

  custom: {
    id: "custom",
    name: "Custom Provider",
    description: "Configure your own OpenAI-compatible endpoint.",
    authMethod: "manual",
    baseUrl: "",
    defaultModel: "",
    pricing: {
      inputPer1M: 0,
      outputPer1M: 0,
      model: "Custom",
    },
    apiKeyEnv: "CUSTOM_LLM_API_KEY",
    available: true,
    icon: "Settings",
    brandColor: "#64748b", // Slate
  },
};

// =============================================================================
// Helper Functions
// =============================================================================

/**
 * Get all available providers as an array
 */
export function getProviderList(): ProviderDefinition[] {
  return Object.values(PROVIDER_REGISTRY).filter((p) => p.available);
}

/**
 * Get a specific provider by ID
 */
export function getProvider(id: ProviderId): ProviderDefinition | undefined {
  return PROVIDER_REGISTRY[id];
}

/**
 * Get providers that support OAuth
 */
export function getOAuthProviders(): ProviderDefinition[] {
  return getProviderList().filter((p) => p.authMethod === "oauth");
}

/**
 * Get providers that require manual API key entry
 */
export function getManualKeyProviders(): ProviderDefinition[] {
  return getProviderList().filter((p) => p.authMethod === "manual");
}

/**
 * Format pricing for display
 * e.g., "$3.00 / $15.00 per 1M tokens"
 */
export function formatPricing(pricing: {
  inputPer1M: number;
  outputPer1M: number;
}): string {
  const formatPrice = (price: number) => {
    if (price === 0) return "Free";
    if (price < 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(2)}`;
  };

  return `${formatPrice(pricing.inputPer1M)} in / ${formatPrice(pricing.outputPer1M)} out`;
}

/**
 * Estimate cost for a given token count
 */
export function estimateCost(
  providerId: ProviderId,
  inputTokens: number,
  outputTokens: number,
): number {
  const provider = getProvider(providerId);
  if (!provider) return 0;

  const inputCost = (inputTokens / 1_000_000) * provider.pricing.inputPer1M;
  const outputCost = (outputTokens / 1_000_000) * provider.pricing.outputPer1M;

  return inputCost + outputCost;
}

/**
 * Get the Tailwind color class for a provider's brand color
 */
export function getProviderColorClass(providerId: ProviderId): string {
  const colorMap: Record<ProviderId, string> = {
    glama: "text-cyan-400",
    openrouter: "text-indigo-400",
    anthropic: "text-amber-400",
    openai: "text-emerald-400",
    gemini: "text-blue-400",
    groq: "text-orange-400",
    together: "text-violet-400",
    custom: "text-slate-400",
  };
  return colorMap[providerId] || "text-slate-400";
}

/**
 * Get the background color class for a provider card
 */
export function getProviderBgClass(providerId: ProviderId): string {
  const colorMap: Record<ProviderId, string> = {
    glama: "bg-cyan-500/10 border-cyan-500/20 hover:border-cyan-500/40",
    openrouter:
      "bg-indigo-500/10 border-indigo-500/20 hover:border-indigo-500/40",
    anthropic: "bg-amber-500/10 border-amber-500/20 hover:border-amber-500/40",
    openai:
      "bg-emerald-500/10 border-emerald-500/20 hover:border-emerald-500/40",
    gemini: "bg-blue-500/10 border-blue-500/20 hover:border-blue-500/40",
    groq: "bg-orange-500/10 border-orange-500/20 hover:border-orange-500/40",
    together:
      "bg-violet-500/10 border-violet-500/20 hover:border-violet-500/40",
    custom: "bg-slate-500/10 border-slate-500/20 hover:border-slate-500/40",
  };
  return colorMap[providerId] || "bg-slate-500/10 border-slate-500/20";
}
