/**
 * @jest-environment node
 */
import fs from 'fs/promises';
import yaml from 'yaml';

import {
  CORE_SKILLS,
  getSkillStatePath,
  isCapabilityEnabled,
  isSafeSkillSlug,
  readDisabledCapabilities,
  readDisabledSkills,
  readSkillState,
  removeSkillFromConfig,
  setCapabilityEnabled,
  setSkillEnabled,
  writeDisabledSkills,
  writeSkillState,
} from '@/lib/server/skillsState';

jest.mock('fs/promises', () => ({
  readFile: jest.fn(),
  writeFile: jest.fn(),
  mkdir: jest.fn(),
}));

jest.mock('@/lib/paths', () => ({
  AUGUR_RUNTIME_DIR: '/mock/runtime',
}));

describe('skillsState', () => {
  const mockReadFile = fs.readFile as unknown as jest.Mock;
  const mockWriteFile = fs.writeFile as unknown as jest.Mock;
  let configText = '';

  beforeEach(() => {
    jest.clearAllMocks();
    configText = '';
    mockReadFile.mockImplementation(async () => configText);
    mockWriteFile.mockImplementation(async (_path: string, content: string) => {
      configText = content;
    });
  });

  it('exports expected constants and runtime state path', () => {
    expect(CORE_SKILLS.has('augur-mcp')).toBe(true);
    expect(CORE_SKILLS.has('setup-manager')).toBe(true);
    expect(getSkillStatePath()).toBe('/mock/runtime/dashboard/skills-state.yaml');
  });

  it('validates safe skill slugs', () => {
    expect(isSafeSkillSlug('skill-1')).toBe(true);
    expect(isSafeSkillSlug('Skill-1')).toBe(false);
    expect(isSafeSkillSlug('bad_skill')).toBe(false);
    expect(isSafeSkillSlug('')).toBe(false);
  });

  it('returns empty state when config file is missing or invalid', async () => {
    mockReadFile.mockRejectedValueOnce(new Error('missing file'));
    const missing = await readSkillState();
    expect(missing.disabled.size).toBe(0);
    expect(missing.partial.size).toBe(0);

    configText = '::invalid-yaml::';
    const invalid = await readSkillState();
    expect(invalid.disabled.size).toBe(0);
    expect(invalid.partial.size).toBe(0);
  });

  it('reads disabled skills and partial capabilities with trimming', async () => {
    configText = [
      'version: 1',
      'disabled:',
      '  - skill-a',
      '  - "  skill-b  "',
      '  - ""',
      'partial:',
      '  skill-c:',
      '    - cap1',
      '    - " cap2 "',
      '    - ""',
      '  skill-empty: []',
    ].join('\n');

    const state = await readSkillState();
    expect(Array.from(state.disabled)).toEqual(expect.arrayContaining(['skill-a', 'skill-b']));
    expect(state.partial.get('skill-c')).toEqual(new Set(['cap1', 'cap2']));
    expect(state.partial.has('skill-empty')).toBe(false);

    await expect(readDisabledSkills()).resolves.toEqual(new Set(['skill-a', 'skill-b']));
    await expect(readDisabledCapabilities('skill-c')).resolves.toEqual(new Set(['cap1', 'cap2']));
    await expect(readDisabledCapabilities('missing')).resolves.toEqual(new Set());
  });

  it('writes sorted disabled and partial state to runtime file', async () => {
    configText = 'skills:\n  ingest:\n    is_new_to_dashboard: true\n';
    await writeSkillState({
      disabled: new Set(['zeta', 'alpha']),
      partial: new Map([
        ['skill-b', new Set(['cap2', 'cap1'])],
        ['skill-empty', new Set()],
      ]),
    });

    const parsed = yaml.parse(configText) as any;
    expect(parsed.version).toBe(1);
    expect(parsed.skills.ingest.is_new_to_dashboard).toBe(true);
    expect(parsed.disabled).toEqual(['alpha', 'zeta']);
    expect(parsed.partial['skill-b']).toEqual(['cap1', 'cap2']);
    expect(parsed.partial['skill-empty']).toBeUndefined();
  });

  it('keeps only version when state becomes empty after write', async () => {
    configText = 'disabled:\n  - keep\n';
    await writeSkillState({
      disabled: new Set(),
      partial: new Map(),
    });

    const parsed = yaml.parse(configText) as any;
    expect(parsed.version).toBe(1);
    expect(parsed.disabled).toBeUndefined();
    expect(parsed.partial).toBeUndefined();
  });

  it('writeDisabledSkills normalizes and writes values', async () => {
    configText = 'disabled:\n  - old\n';
    await writeDisabledSkills(['  one  ', '', 'two', '   ', 'one']);

    const parsed = yaml.parse(configText) as any;
    expect(parsed.disabled).toEqual(['one', 'two']);
  });

  it('setSkillEnabled disables and re-enables skill (clears partial on enable)', async () => {
    configText = [
      'disabled: []',
      'partial:',
      '  skill-x:',
      '    - cap1',
    ].join('\n');

    const disabledState = await setSkillEnabled('skill-x', false);
    expect(disabledState.disabled.has('skill-x')).toBe(true);

    const enabledState = await setSkillEnabled('skill-x', true);
    expect(enabledState.disabled.has('skill-x')).toBe(false);
    expect(enabledState.partial.has('skill-x')).toBe(false);
  });

  it('setCapabilityEnabled toggles capability and cleans empty partial entries', async () => {
    configText = 'disabled: []\n';

    const disabled = await setCapabilityEnabled('skill-y', 'capA', false);
    expect(disabled.partial.get('skill-y')).toEqual(new Set(['capA']));

    const enabled = await setCapabilityEnabled('skill-y', 'capA', true);
    expect(enabled.partial.has('skill-y')).toBe(false);
  });

  it('isCapabilityEnabled checks full and partial disable state', () => {
    const state = {
      disabled: new Set(['skill-a']),
      partial: new Map([['skill-b', new Set(['cap2'])]]),
    };
    expect(isCapabilityEnabled(state, 'skill-a', 'cap1')).toBe(false);
    expect(isCapabilityEnabled(state, 'skill-b', 'cap2')).toBe(false);
    expect(isCapabilityEnabled(state, 'skill-b', 'cap3')).toBe(true);
    expect(isCapabilityEnabled(state, 'skill-c', 'cap1')).toBe(true);
  });

  it('removeSkillFromConfig removes skill entries and cleans state', async () => {
    configText = [
      'version: 1',
      'skills:',
      '  remove-me:',
      '    is_new_to_dashboard: true',
      '  keep-me:',
      '    is_new_to_dashboard: false',
      'disabled:',
      '  - remove-me',
      '  - keep-disabled',
      'partial:',
      '  remove-me:',
      '    - cap1',
      '  keep-me:',
      '    - cap2',
    ].join('\n');

    await removeSkillFromConfig('remove-me');
    const parsed = yaml.parse(configText) as any;

    expect(parsed.skills['remove-me']).toBeUndefined();
    expect(parsed.skills['keep-me']).toEqual({ is_new_to_dashboard: false });
    expect(parsed.disabled).toEqual(['keep-disabled']);
    expect(parsed.partial['remove-me']).toBeUndefined();
    expect(parsed.partial['keep-me']).toEqual(['cap2']);
  });

  it('throws a descriptive error when runtime YAML cannot be parsed for writes', async () => {
    configText = 'disabled: [unclosed';
    await expect(
      writeSkillState({
        disabled: new Set(['x']),
        partial: new Map(),
      })
    ).rejects.toThrow('Failed to parse /mock/runtime/dashboard/skills-state.yaml');
  });
});
