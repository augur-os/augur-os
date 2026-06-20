/**
 * @jest-environment node
 */

import {
  getPromptTemplate,
  invalidatePromptCache,
  loadPromptTemplates,
} from '@/scripts/skill-scripts/prompts/discovery';

jest.mock('@/lib/paths', () => ({
  getDiscoveredSkills: jest.fn().mockReturnValue(['career']),
  getSkillAugurDataPath: jest.fn().mockReturnValue('/tmp/vault/career/career'),
  getSkillPluginPath: jest.fn().mockReturnValue('/tmp/augur/project-brain/capabilities/skills/career-ops'),
}));

const mockReaddir = jest.fn();
const mockReadFile = jest.fn();

jest.mock('fs/promises', () => ({
  readdir: (...args: unknown[]) => mockReaddir(...args),
  readFile: (...args: unknown[]) => mockReadFile(...args),
}));

function makeDirent(name: string, type: 'file' | 'dir') {
  return {
    name,
    isDirectory: () => type === 'dir',
    isFile: () => type === 'file',
  };
}

function setupPromptFiles({
  assets = {},
  vault = {},
}: {
  assets?: Record<string, string>;
  vault?: Record<string, string>;
}) {
  const assetFileNames = Object.keys(assets).map((name) => `${name}.md`);
  const vaultFileNames = Object.keys(vault).map((name) => `${name}.md`);

  mockReaddir.mockImplementation((dir: string, options?: { withFileTypes?: boolean }) => {
    const asDirents = Boolean(options?.withFileTypes);

    if (dir === '/tmp/augur/project-brain/capabilities/skills/career-ops/assets/prompts') {
      return Promise.resolve(asDirents ? [] : []);
    }
    if (dir === '/tmp/augur/project-brain/capabilities/skills/career-ops/assets/seed-data/prompts') {
      const entries = assetFileNames.map((name) => makeDirent(name, 'file'));
      return Promise.resolve(asDirents ? entries : assetFileNames);
    }
    if (dir === '/tmp/augur/project-brain/capabilities/skills/career-ops/assets/seed-data') {
      const entries = assetFileNames.length > 0 ? [makeDirent('prompts', 'dir')] : [];
      return Promise.resolve(asDirents ? entries : entries.map((entry) => entry.name));
    }
    if (dir === '/tmp/vault/career/career') {
      const entries = vaultFileNames.length > 0 ? [makeDirent('prompts', 'dir')] : [];
      return Promise.resolve(asDirents ? entries : entries.map((entry) => entry.name));
    }
    if (dir === '/tmp/vault/career/career/prompts') {
      const entries = vaultFileNames.map((name) => makeDirent(name, 'file'));
      return Promise.resolve(asDirents ? entries : vaultFileNames);
    }
    return Promise.reject(new Error(`ENOENT: ${dir}`));
  });

  mockReadFile.mockImplementation((filePath: string) => {
    for (const [name, content] of Object.entries(vault)) {
      if (filePath === `/tmp/vault/career/career/prompts/${name}.md`) {
        return Promise.resolve(content);
      }
    }
    for (const [name, content] of Object.entries(assets)) {
      if (filePath === `/tmp/augur/project-brain/capabilities/skills/career-ops/assets/seed-data/prompts/${name}.md`) {
        return Promise.resolve(content);
      }
    }
    return Promise.reject(new Error(`ENOENT: ${filePath}`));
  });
}

describe('prompt discovery', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    invalidatePromptCache();
  });

  it('falls back to asset prompts when no vault override exists', async () => {
    setupPromptFiles({
      assets: {
        welcome: `---\naction: welcome\n---\nHello from assets`,
      },
    });

    const template = await getPromptTemplate('welcome');

    expect(template?.body).toContain('Hello from assets');
  });

  it('prefers vault prompts over asset defaults by relative path', async () => {
    setupPromptFiles({
      assets: {
        welcome: `---\naction: welcome\n---\nHello from assets`,
      },
      vault: {
        welcome: `---\naction: welcome\n---\nHello from vault`,
      },
    });

    const templates = await loadPromptTemplates();

    expect(templates.get('welcome')?.body).toContain('Hello from vault');
  });
});
