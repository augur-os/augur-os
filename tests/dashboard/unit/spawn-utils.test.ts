/**
 * @jest-environment node
 */
import { EventEmitter } from 'events';
import { spawn } from 'child_process';

import { runCommand, runJsonCommand } from '@/lib/server/spawn';

jest.mock('child_process', () => ({
  spawn: jest.fn(),
}));

type MockStream = EventEmitter & { setEncoding: jest.Mock };
type MockProc = EventEmitter & {
  stdout?: MockStream;
  stderr?: MockStream;
  kill: jest.Mock;
};

function makeStream(): MockStream {
  const stream = new EventEmitter() as MockStream;
  stream.setEncoding = jest.fn();
  return stream;
}

function makeProc(): MockProc {
  const proc = new EventEmitter() as MockProc;
  proc.stdout = makeStream();
  proc.stderr = makeStream();
  proc.kill = jest.fn();
  return proc;
}

describe('spawn utils', () => {
  const mockSpawn = spawn as unknown as jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useRealTimers();
  });

  it('runCommand resolves with collected output on close', async () => {
    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const promise = runCommand('echo', ['hello'], {
      cwd: '/tmp',
      env: { TEST_FLAG: '1' },
      timeout: 5000,
    });

    expect(mockSpawn).toHaveBeenCalledWith(
      'echo',
      ['hello'],
      expect.objectContaining({
        cwd: '/tmp',
        stdio: ['ignore', 'pipe', 'pipe'],
      })
    );
    const spawnEnv = mockSpawn.mock.calls[0][2].env as Record<string, string>;
    expect(spawnEnv.TEST_FLAG).toBe('1');
    expect(proc.stdout?.setEncoding).toHaveBeenCalledWith('utf8');
    expect(proc.stderr?.setEncoding).toHaveBeenCalledWith('utf8');

    proc.stdout?.emit('data', 'hello ');
    proc.stderr?.emit('data', 'warn ');
    proc.stdout?.emit('data', 'world');
    proc.emit('close', 0);

    await expect(promise).resolves.toEqual({
      stdout: 'hello world',
      stderr: 'warn ',
      exitCode: 0,
    });
  });

  it('runCommand rejects on process error', async () => {
    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const promise = runCommand('bad', []);
    const error = new Error('spawn failed');
    proc.emit('error', error);

    await expect(promise).rejects.toThrow('spawn failed');
  });

  it('runCommand kills process and rejects on timeout', async () => {
    jest.useFakeTimers();
    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const promise = runCommand('sleep', ['10'], { timeout: 25 });
    jest.advanceTimersByTime(25);

    await expect(promise).rejects.toThrow('Command timed out after 25ms');
    expect(proc.kill).toHaveBeenCalled();
  });

  it('runJsonCommand parses JSON output on success', async () => {
    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const promise = runJsonCommand<{ ok: boolean }>('cmd', []);
    proc.stdout?.emit('data', '{"ok":true}\n');
    proc.emit('close', 0);

    await expect(promise).resolves.toEqual({ ok: true });
  });

  it('runJsonCommand throws when exit code is non-zero', async () => {
    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const promise = runJsonCommand('cmd', []);
    proc.stderr?.emit('data', 'failed');
    proc.emit('close', 2);

    await expect(promise).rejects.toThrow('failed');
  });

  it('runJsonCommand throws when command returns empty output', async () => {
    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const promise = runJsonCommand('cmd', []);
    proc.stdout?.emit('data', '   \n');
    proc.emit('close', 0);

    await expect(promise).rejects.toThrow('No output from command');
  });

  it('runJsonCommand throws on invalid JSON', async () => {
    const proc = makeProc();
    mockSpawn.mockReturnValue(proc);

    const promise = runJsonCommand('cmd', []);
    proc.stdout?.emit('data', '{not-json}');
    proc.emit('close', 0);

    await expect(promise).rejects.toThrow();
  });
});
