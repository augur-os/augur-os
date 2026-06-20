/**
 * @jest-environment node
 */
import {
  openFile,
  deleteFile
} from '@/app/actions';

import path from 'path';

// Mock dependencies
jest.mock('child_process', () => ({
  spawn: jest.fn(() => ({
    once: jest.fn((event, cb) => {
      if (event === 'exit') cb(0); // success
    }),
    unref: jest.fn(),
  })),
}));

jest.mock('fs/promises', () => ({
  stat: jest.fn(),
  unlink: jest.fn().mockResolvedValue(undefined),
}));

jest.mock('@/lib/auth/server-action', () => ({
  auth: jest.fn().mockResolvedValue({
    isRemote: false,
    role: 'admin',
    scopes: ['*'],
    userId: 'dev-user',
  }),
}));

// Mock paths to control allowed roots
jest.mock('@/lib/paths', () => ({
  AUGUR_ROOT: '/allowed/data',
}));

// Mock os.homedir and platform
jest.mock('os', () => ({
  ...jest.requireActual('os'),
  homedir: () => '/home/user',
  platform: () => 'darwin', // Simulate mac for most tests
}));

describe('Server Actions', () => {
  const mockStat = require('fs/promises').stat;

  beforeEach(() => {
    jest.clearAllMocks();
    mockStat.mockResolvedValue({ isFile: () => true, isDirectory: () => false });
  });

  describe('Path Safety (assertPathAllowedForOpen/Delete)', () => {
    it('should allow opening files in data dir', async () => {
      const result = await openFile('/allowed/data/test.txt');
      expect(result.success).toBe(true);
    });

    it('should block opening files outside allowed roots', async () => {
      // /etc/passwd is likely outside
      const result = await openFile('/etc/passwd');
      expect(result.success).toBe(false);
      if (!result.success) {
        expect(result.error).toContain('Failed to open file');
      }
    });

    it('should block traversal escaping allowed roots', async () => {
      const result = await openFile('/allowed/data/../../etc/passwd');
      expect(result.success).toBe(false);
    });
    
    it('should allow delete in data dir', async () => {
        const result = await deleteFile('/allowed/data/temp.txt');
        expect(result.success).toBe(true);
    });

    it('should block delete outside allowed roots', async () => {
        const result = await deleteFile('/home/user/important.txt'); 
        // /home/user is NOT in allowed roots for delete (only data dir)
        expect(result.success).toBe(false);
    });
  });
});
