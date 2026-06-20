/**
 * @jest-environment node
 *
 * Tests for skill config schema validation (ADR-187 Phase 1).
 */

import { describe, it, expect } from '@jest/globals';
import {
  validateSkillConfig,
  formatValidationErrors,
  PageSchema,
  HubSchema,
  NavModeSchema,
} from '@/lib/plugin-schema/validation';

describe('ADR-187: skill config schema validation', () => {
  describe('PageSchema', () => {
    it('accepts valid page definition', () => {
      const result = PageSchema.safeParse({
        id: 'pipeline',
        title: 'Pipeline',
        icon: 'Briefcase',
        order: 60,
      });
      expect(result.success).toBe(true);
    });

    it('rejects page with empty id', () => {
      const result = PageSchema.safeParse({
        id: '',
        title: 'Pipeline',
      });
      expect(result.success).toBe(false);
    });

    it('rejects page with empty title', () => {
      const result = PageSchema.safeParse({
        id: 'pipeline',
        title: '',
      });
      expect(result.success).toBe(false);
    });

    it('rejects page with order out of range', () => {
      const result = PageSchema.safeParse({
        id: 'pipeline',
        title: 'Pipeline',
        order: 1000,
      });
      expect(result.success).toBe(false);
    });

    it('rejects page with negative order', () => {
      const result = PageSchema.safeParse({
        id: 'pipeline',
        title: 'Pipeline',
        order: -1,
      });
      expect(result.success).toBe(false);
    });

    it('accepts valid state values', () => {
      for (const state of ['mock', 'dev', 'mature']) {
        const result = PageSchema.safeParse({
          id: 'test',
          title: 'Test',
          state,
        });
        expect(result.success).toBe(true);
      }
    });

    it('rejects invalid state value', () => {
      const result = PageSchema.safeParse({
        id: 'test',
        title: 'Test',
        state: 'unknown',
      });
      expect(result.success).toBe(false);
    });
  });

  describe('HubSchema', () => {
    it('accepts valid hub definition with owner: true', () => {
      const result = HubSchema.safeParse({
        id: 'career',
        title: 'Career',
        subtitle: 'Job search',
        icon: 'Briefcase',
        owner: true,
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.owner).toBe(true);
      }
    });

    it('defaults owner to false when omitted', () => {
      const result = HubSchema.safeParse({
        id: 'career',
      });
      expect(result.success).toBe(true);
      if (result.success) {
        expect(result.data.owner).toBe(false);
      }
    });

    it('rejects hub with empty id', () => {
      const result = HubSchema.safeParse({
        id: '',
        owner: true,
      });
      expect(result.success).toBe(false);
    });

    it('accepts hub with nav_order', () => {
      const result = HubSchema.safeParse({
        id: 'career',
        nav_order: 60,
        owner: true,
      });
      expect(result.success).toBe(true);
    });

    it('accepts hub with overview config', () => {
      const result = HubSchema.safeParse({
        id: 'career',
        owner: true,
        overview: {
          search: true,
          layout: 'masonry',
        },
      });
      expect(result.success).toBe(true);
    });

    it('rejects invalid overview layout', () => {
      const result = HubSchema.safeParse({
        id: 'career',
        owner: true,
        overview: {
          layout: 'invalid_layout',
        },
      });
      expect(result.success).toBe(false);
    });
  });

  describe('NavModeSchema', () => {
    it('accepts valid nav_mode values', () => {
      for (const mode of ['inline', 'nested', 'hidden']) {
        const result = NavModeSchema.safeParse(mode);
        expect(result.success).toBe(true);
      }
    });

    it('rejects invalid nav_mode', () => {
      const result = NavModeSchema.safeParse('inlin');
      expect(result.success).toBe(false);
    });

    it('accepts undefined (optional)', () => {
      const result = NavModeSchema.safeParse(undefined);
      expect(result.success).toBe(true);
    });
  });

  describe('validateSkillConfig', () => {
    it('returns null for valid config', () => {
      const config = {
        contributes_to: 'career',
        hub: {
          id: 'career',
          owner: true,
          title: 'Career',
        },
        contributions: {
          pages: [
            { id: 'pipeline', title: 'Pipeline', order: 60 },
          ],
        },
      };
      expect(validateSkillConfig(config, '/test/SKILL.md')).toBeNull();
    });

    // ADR-802 Phase 2: contributes_to is now optional; discovery uses
    // x-augur-dashboard-pages contribution signals instead.

    it('returns null for config with hub but no contributes_to (now optional)', () => {
      const config = {
        hub: { id: 'career' },
      };
      expect(validateSkillConfig(config, '/test/SKILL.md')).toBeNull();
    });

    it('returns errors for invalid nav_mode', () => {
      const config = {
        contributes_to: 'career',
        nav_mode: 'inlin',
      };
      const errors = validateSkillConfig(config, '/test/SKILL.md');
      expect(errors).not.toBeNull();
      expect(errors!.some(e => e.field === 'nav_mode')).toBe(true);
    });

    it('returns errors for invalid page in contributions', () => {
      const config = {
        contributes_to: 'career',
        contributions: {
          pages: [
            { id: '', title: 'Missing ID' },
          ],
        },
      };
      const errors = validateSkillConfig(config, '/test/SKILL.md');
      expect(errors).not.toBeNull();
    });

    it('passes through unknown fields (passthrough mode)', () => {
      const config = {
        contributes_to: 'career',
        custom_field: 'value',
        mcp: { tools: ['tool1'] },
      };
      expect(validateSkillConfig(config, '/test/SKILL.md')).toBeNull();
    });
  });

  describe('formatValidationErrors', () => {
    it('formats errors with file path and field', () => {
      const errors = [
        { path: '/test/SKILL.md', field: 'nav_mode', message: 'Invalid value' },
      ];
      const output = formatValidationErrors(errors);
      expect(output).toContain('/test/SKILL.md');
      expect(output).toContain('nav_mode');
      expect(output).toContain('Invalid value');
    });
  });
});
