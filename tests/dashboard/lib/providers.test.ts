import {
  PROVIDER_REGISTRY,
  estimateCost,
  formatPricing,
  getManualKeyProviders,
  getOAuthProviders,
  getProvider,
  getProviderBgClass,
  getProviderColorClass,
  getProviderList,
} from '@/lib/remote/providers';

describe('remote provider registry helpers', () => {
  it('returns available providers and resolves providers by id', () => {
    const available = Object.values(PROVIDER_REGISTRY).filter((provider) => provider.available);
    const providers = getProviderList();

    expect(providers).toHaveLength(available.length);
    expect(providers.map((provider) => provider.id)).toEqual(
      expect.arrayContaining(available.map((provider) => provider.id))
    );

    expect(getProvider('openai')).toMatchObject({
      id: 'openai',
      name: 'OpenAI',
    });
  });

  it('splits oauth and manual providers correctly', () => {
    const oauthProviders = getOAuthProviders();
    const manualProviders = getManualKeyProviders();

    expect(oauthProviders.length).toBeGreaterThan(0);
    expect(manualProviders.length).toBeGreaterThan(0);

    expect(oauthProviders.every((provider) => provider.authMethod === 'oauth')).toBe(true);
    expect(manualProviders.every((provider) => provider.authMethod === 'manual')).toBe(true);
  });

  it('formats pricing for paid and free tiers', () => {
    expect(formatPricing({ inputPer1M: 3, outputPer1M: 15 })).toBe('$3.00 in / $15.00 out');
    expect(formatPricing({ inputPer1M: 0.25, outputPer1M: 0 })).toBe('$0.25 in / Free out');
  });

  it('estimates provider cost and handles unknown providers', () => {
    expect(estimateCost('openai', 1_000_000, 500_000)).toBeCloseTo(7.5, 5);
    expect(estimateCost('unknown-provider' as any, 1_000_000, 1_000_000)).toBe(0);
  });

  it('returns provider tailwind classes with fallback values', () => {
    expect(getProviderColorClass('glama')).toBe('text-cyan-400');
    expect(getProviderBgClass('anthropic')).toContain('border-amber-500/20');

    expect(getProviderColorClass('unknown-provider' as any)).toBe('text-slate-400');
    expect(getProviderBgClass('unknown-provider' as any)).toBe('bg-slate-500/10 border-slate-500/20');
  });
});
