/**
 * @jest-environment node
 *
 * Tests for hub role resolution (ADR-187 Phase 2).
 *
 * Note: assembleHubs() was deleted in ADR-802 Phase 2 (x-augur-hub teardown).
 * The assembleHubs ownership tests were removed along with the function.
 * resolveHubRole() still exists to compute primary/extension per skill config.
 */

import { describe, it, expect } from '@jest/globals';
import { resolveHubRole } from '@/lib/plugin-discovery/scanner';

describe('ADR-187: resolveHubRole', () => {
  it('returns primary for hub with id and owner: true', () => {
    expect(resolveHubRole({ hub: { id: 'career', owner: true } })).toBe('primary');
  });

  it('returns extension for hub with id and owner: false', () => {
    expect(resolveHubRole({ hub: { id: 'career', owner: false } })).toBe('extension');
  });

  it('returns primary for hub with id and no owner field (backwards compat)', () => {
    expect(resolveHubRole({ hub: { id: 'career' } })).toBe('primary');
  });

  it('returns extension for no hub block', () => {
    expect(resolveHubRole({ contributes_to: 'career' })).toBe('extension');
  });

  it('returns extension for undefined hub', () => {
    expect(resolveHubRole({})).toBe('extension');
  });
});
