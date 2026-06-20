/**
 * @jest-environment node
 */
import fs from 'fs/promises';

import { parseSkillSlug, readSkillMeta, resolveSkillInfo } from '@/lib/server/skillsLookup';
import { getManagedSkillDirs } from '@/lib/plugin-discovery/paths';

jest.mock('fs/promises', () => ({
  readdir: jest.fn(),
  readFile: jest.fn(),
}));

jest.mock('@/lib/server/repo', () => ({
  getRepoRoot: jest.fn(() => '/repo'),
}));

jest.mock('@/lib/plugin-discovery/paths', () => ({
  getProjectBrainSkillsRoot: jest.fn((repoRoot: string) => `${repoRoot}/project-brain/capabilities/skills`),
  getSharedVaultSkillsRoot: jest.fn((repoRoot: string) => `${repoRoot}/project-brain/capabilities/skills`),
  getManagedSkillDirs: jest.fn(),
}));

type MockDirent = { name: string; isDirectory: () => boolean };

function dirent(name: string, isDir: boolean = true): MockDirent {
  return {
    name,
    isDirectory: () => isDir,
  };
}

describe('resolveSkillInfo', () => {
  const mockReaddir = fs.readdir as unknown as jest.Mock;
  const mockReadFile = fs.readFile as unknown as jest.Mock;
  const mockGetManagedSkillDirs = getManagedSkillDirs as jest.Mock;

  function mockManagedDirs(dirsInScanOrder: Array<[string, string]>) {
    mockGetManagedSkillDirs.mockReturnValue(Object.fromEntries(dirsInScanOrder));
  }

  beforeEach(() => {
    jest.clearAllMocks();
    mockReaddir.mockReset();
    mockReadFile.mockReset();
    mockGetManagedSkillDirs.mockReset();
    mockManagedDirs([['augur', '/repo/project-brain/capabilities/skills']]);
  });

  it('matches by normalized folder name in project-brain/capabilities/skills/', async () => {
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [dirent('My_Skill')];
      return [];
    });
    mockReadFile.mockRejectedValue(new Error('missing SKILL.md'));

    const result = await resolveSkillInfo('my-skill');

    expect(result).toEqual({
      path: 'My_Skill',
      absolutePath: '/repo/project-brain/capabilities/skills/My_Skill',
      baseDir: 'project-brain/capabilities/skills',
      canonicalId: 'My_Skill',
      folderName: 'My_Skill',
      source: 'skill-md',
    });
  });

  it('matches by SKILL.md frontmatter name', async () => {
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [dirent('folder-name')];
      return [];
    });
    mockReadFile.mockResolvedValueOnce('---\nname: Fancy_Skill\n---\nDescription');

    const result = await resolveSkillInfo('fancy_skill');

    expect(result).toEqual({
      path: 'folder-name',
      absolutePath: '/repo/project-brain/capabilities/skills/folder-name',
      baseDir: 'project-brain/capabilities/skills',
      canonicalId: 'Fancy_Skill',
      folderName: 'folder-name',
      source: 'skill-md',
    });
  });

  it('matches by nested skill-package SKILL.md name', async () => {
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [dirent('folder-two')];
      return [];
    });
    mockReadFile
      .mockRejectedValueOnce(new Error('no top-level skill'))
      .mockResolvedValueOnce('---\nname: Nested_Tool\n---\nDesc');

    const result = await resolveSkillInfo('nested_tool');

    expect(result).toEqual({
      path: 'folder-two',
      absolutePath: '/repo/project-brain/capabilities/skills/folder-two',
      baseDir: 'project-brain/capabilities/skills',
      canonicalId: 'Nested_Tool',
      folderName: 'folder-two',
      source: 'skill-package',
    });
  });

  it('matches skill in flat project-brain/capabilities/skills directory', async () => {
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [dirent('other-skill'), dirent('target-skill')];
      return [];
    });
    mockReadFile.mockRejectedValue(new Error('missing skill file'));

    const result = await resolveSkillInfo('target-skill');

    expect(result).toEqual({
      path: 'target-skill',
      absolutePath: '/repo/project-brain/capabilities/skills/target-skill',
      baseDir: 'project-brain/capabilities/skills',
      canonicalId: 'target-skill',
      folderName: 'target-skill',
      source: 'skill-md',
    });
  });

  it('returns null when no skill matches', async () => {
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [dirent('not-a-match'), dirent('also-not-match')];
      return [];
    });
    mockReadFile.mockRejectedValue(new Error('missing skill file'));

    const result = await resolveSkillInfo('target-skill');
    expect(result).toBeNull();
  });

  it('returns null when project-brain skills root cannot be read', async () => {
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') throw new Error('shared skills missing');
      return [];
    });

    const result = await resolveSkillInfo('anything');
    expect(result).toBeNull();
  });

  it('ignores repo-root skills even when a stale managed dir includes them', async () => {
    mockManagedDirs([
      ['augur-root-transitional', '/repo/skills'],
      ['augur', '/repo/project-brain/capabilities/skills'],
    ]);
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [];
      if (targetPath === '/repo/skills') return [dirent('target-skill')];
      return [];
    });
    mockReadFile.mockRejectedValue(new Error('missing skill file'));

    const result = await resolveSkillInfo('target-skill');

    expect(result).toBeNull();
    expect(mockReaddir).not.toHaveBeenCalledWith('/repo/skills', expect.anything());
  });

  it('does not surface root-only skills when managed dirs omit the transitional root fallback', async () => {
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [dirent('shared-skill')];
      if (targetPath === '/repo/skills') return [dirent('target-skill')];
      return [];
    });
    mockReadFile.mockRejectedValue(new Error('missing skill file'));

    const result = await resolveSkillInfo('target-skill');

    expect(result).toBeNull();
    expect(mockReaddir).not.toHaveBeenCalledWith('/repo/skills', expect.anything());
  });

  it('keeps project-brain matches ahead of stale repo-root skills', async () => {
    mockManagedDirs([
      ['augur-root-transitional', '/repo/skills'],
      ['augur', '/repo/project-brain/capabilities/skills'],
    ]);
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [dirent('target-skill')];
      if (targetPath === '/repo/skills') return [dirent('target-skill')];
      return [];
    });
    mockReadFile.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills/target-skill/SKILL.md') {
        return '---\nname: Shared_Target\n---\n';
      }
      if (targetPath === '/repo/skills/target-skill/SKILL.md') {
        return '---\nname: Root Target\n---\n';
      }
      throw new Error(`unexpected read: ${targetPath}`);
    });

    const result = await resolveSkillInfo('shared-target');

    expect(result).toEqual({
      path: 'target-skill',
      absolutePath: '/repo/project-brain/capabilities/skills/target-skill',
      baseDir: 'project-brain/capabilities/skills',
      canonicalId: 'Shared_Target',
      folderName: 'target-skill',
      source: 'skill-md',
    });
    expect(mockReaddir).not.toHaveBeenCalledWith('/repo/skills', expect.anything());
  });

  it('resolves configured private-vault skills after project-brain misses', async () => {
    mockManagedDirs([
      ['augur-vault', '/private-vault/skills'],
      ['augur', '/repo/project-brain/capabilities/skills'],
    ]);
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [];
      if (targetPath === '/private-vault/skills') return [dirent('private-skill')];
      return [];
    });
    mockReadFile.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/private-vault/skills/private-skill/SKILL.md') {
        return '---\nname: Private Skill\n---\n';
      }
      throw new Error(`unexpected read: ${targetPath}`);
    });

    const result = await resolveSkillInfo('private-skill');

    expect(result).toEqual({
      path: 'private-skill',
      absolutePath: '/private-vault/skills/private-skill',
      baseDir: '/private-vault/skills',
      canonicalId: 'Private Skill',
      folderName: 'private-skill',
      source: 'skill-md',
    });
  });

  it('returns null without probing stale repo-root skills', async () => {
    mockManagedDirs([
      ['augur-root-transitional', '/repo/skills'],
      ['augur', '/repo/project-brain/capabilities/skills'],
    ]);
    mockReaddir.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills') return [];
      if (targetPath === '/repo/skills') throw new Error('root skills missing');
      return [];
    });

    const result = await resolveSkillInfo('target-skill');

    expect(result).toBeNull();
    expect(mockReaddir).not.toHaveBeenCalledWith('/repo/skills', expect.anything());
  });

  it('reads skill metadata from project-brain/capabilities/skills', async () => {
    mockReaddir.mockResolvedValue([]);
    mockReadFile.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills/demo/SKILL.md') {
        return [
          '---',
          'name: Demo',
          'description: Demo skill',
          'x-augur-hub: workspace',
          'x-augur-mcp-tools:',
          '  - demo-tool',
          '---',
          '',
        ].join('\n');
      }
      throw new Error(`unexpected read: ${targetPath}`);
    });

    const result = await readSkillMeta('demo');

    expect(result).toMatchObject({
      title: 'Demo',
      tabLabel: 'Demo',
      description: 'Demo skill',
      mcpTools: ['demo-tool'],
    });
    expect(mockReadFile).toHaveBeenCalledWith(
      '/repo/project-brain/capabilities/skills/demo/SKILL.md',
      'utf8',
    );
  });

  it('does not read metadata from repo-root skills while project-brain/capabilities/skills is empty', async () => {
    mockManagedDirs([
      ['augur-root-transitional', '/repo/skills'],
      ['augur', '/repo/project-brain/capabilities/skills'],
    ]);
    mockReaddir.mockResolvedValue([]);
    mockReadFile.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills/demo/SKILL.md') {
        throw new Error('shared skill missing');
      }
      if (targetPath === '/repo/skills/demo/SKILL.md') {
        return [
          '---',
          'name: Demo',
          'description: Root demo skill',
          'x-augur-hub: dev',
          '---',
          '',
        ].join('\n');
      }
      throw new Error(`unexpected read: ${targetPath}`);
    });

    const result = await readSkillMeta('demo');

    expect(result).toBeNull();
    expect(mockReadFile).not.toHaveBeenCalledWith(
      '/repo/skills/demo/SKILL.md',
      'utf8',
    );
  });

  it('does not read root metadata once managed dirs disable transitional root fallback', async () => {
    mockReadFile.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills/demo/SKILL.md') {
        throw new Error('shared skill missing');
      }
      if (targetPath === '/repo/skills/demo/SKILL.md') {
        return [
          '---',
          'name: Demo',
          'description: Root demo skill',
          'x-augur-hub: dev',
          '---',
          '',
        ].join('\n');
      }
      throw new Error(`unexpected read: ${targetPath}`);
    });

    const result = await readSkillMeta('demo');

    expect(result).toBeNull();
    expect(mockReadFile).not.toHaveBeenCalledWith(
      '/repo/skills/demo/SKILL.md',
      'utf8',
    );
  });

  describe('parseSkillSlug', () => {
    it('passes a bare folder name through unchanged', () => {
      expect(parseSkillSlug('geo-technical')).toEqual({
        name: 'geo-technical',
        sourceRoot: null,
        hadPrefix: false,
      });
    });

    it('extracts the bare name and source from a skill:<source>:<name> id', () => {
      expect(parseSkillSlug('skill:external-client:geo-technical')).toEqual({
        name: 'geo-technical',
        sourceRoot: 'external-client',
        hadPrefix: true,
      });
    });

    it('decodes percent-encoded colons that survived as route params', () => {
      // The reported bug: Next.js delivered params.skill with %3a still embedded,
      // turning the title into "Skill%3aexternal Client%3ageo Technical".
      expect(parseSkillSlug('skill%3aexternal-client%3ageo-technical')).toEqual({
        name: 'geo-technical',
        sourceRoot: 'external-client',
        hadPrefix: true,
      });
    });

    it('handles upper-case percent encoding', () => {
      expect(parseSkillSlug('skill%3Aproject-brain%3Ageo-prospect')).toEqual({
        name: 'geo-prospect',
        sourceRoot: 'project-brain',
        hadPrefix: true,
      });
    });

    it('keeps the last segment when the prefix is not a skill capability id', () => {
      expect(parseSkillSlug('foo:bar')).toEqual({
        name: 'bar',
        sourceRoot: null,
        hadPrefix: true,
      });
    });

    it('extracts the bare name from a private-vault capability id', () => {
      // The reported bug: /browse?skill=skill%3Aprivate-vault%3Avault round-tripped
      // through useSearchParams as "skill:private-vault:vault" and was passed raw
      // to /api/skill-meta/[skillId], which 404'd on the prefixed id.
      expect(parseSkillSlug('skill:private-vault:vault')).toEqual({
        name: 'vault',
        sourceRoot: 'private-vault',
        hadPrefix: true,
      });
    });

    it('survives a malformed percent sequence by treating it as opaque text', () => {
      // decodeURIComponent throws on a lone %, so make sure the helper degrades
      // gracefully instead of bubbling the URIError into the route handler.
      expect(parseSkillSlug('busted%name')).toEqual({
        name: 'busted%name',
        sourceRoot: null,
        hadPrefix: false,
      });
    });
  });

  it('reads skill metadata from configured private-vault roots', async () => {
    mockManagedDirs([
      ['augur-vault', '/private-vault/skills'],
      ['augur', '/repo/project-brain/capabilities/skills'],
    ]);
    mockReaddir.mockResolvedValue([]);
    mockReadFile.mockImplementation(async (targetPath: string) => {
      if (targetPath === '/repo/project-brain/capabilities/skills/demo/SKILL.md') {
        throw new Error('shared skill missing');
      }
      if (targetPath === '/private-vault/skills/demo/SKILL.md') {
        return [
          '---',
          'name: Private Demo',
          'description: Private demo skill',
          'x-augur-hub: life',
          '---',
          '',
        ].join('\n');
      }
      throw new Error(`unexpected read: ${targetPath}`);
    });

    const result = await readSkillMeta('demo');

    expect(result).toMatchObject({
      title: 'Private Demo',
      tabLabel: 'Private Demo',
      description: 'Private demo skill',
    });
    expect(mockReadFile).toHaveBeenCalledWith(
      '/private-vault/skills/demo/SKILL.md',
      'utf8',
    );
  });
});
