/**
 * Tests for attention pattern detection — ADR-160
 */

import { detectAttention, detectError } from '@/lib/chat/attentionPatterns';

describe('detectAttention', () => {
  it('detects lines ending with ?', () => {
    expect(detectAttention('Continue with merge?')).toBe(true);
    expect(detectAttention('Are you sure? ')).toBe(true);
  });

  it('detects (y/n) prompts', () => {
    expect(detectAttention('Proceed (y/n)?')).toBe(true);
    expect(detectAttention('Delete file (Y/N)')).toBe(true);
  });

  it('detects [Y/n] and [y/N] prompts', () => {
    expect(detectAttention('Install packages? [Y/n]')).toBe(true);
    expect(detectAttention('Remove old files? [y/N]')).toBe(true);
  });

  it('detects continue? prompts', () => {
    expect(detectAttention('Do you want to continue?')).toBe(true);
  });

  it('detects press enter prompts', () => {
    expect(detectAttention('Press enter to continue')).toBe(true);
    expect(detectAttention('press ENTER to proceed')).toBe(true);
  });

  it('detects waiting for input', () => {
    expect(detectAttention('Waiting for input...')).toBe(true);
  });

  it('detects permission denied', () => {
    expect(detectAttention('Error: Permission denied')).toBe(true);
  });

  it('detects process signals', () => {
    expect(detectAttention('Process received SIGTERM')).toBe(true);
    expect(detectAttention('Process killed by SIGKILL')).toBe(true);
  });

  it('detects "Do you want to proceed"', () => {
    expect(detectAttention('Do you want to proceed with the update?')).toBe(true);
  });

  it('detects "Are you sure"', () => {
    expect(detectAttention('Are you sure you want to delete this?')).toBe(true);
  });

  it('returns false for normal output', () => {
    expect(detectAttention('Compiling TypeScript...')).toBe(false);
    expect(detectAttention('Build complete in 2.5s')).toBe(false);
    expect(detectAttention('Running 12 test suites...')).toBe(false);
    expect(detectAttention('All tests passed')).toBe(false);
    expect(detectAttention('')).toBe(false);
  });
});

describe('detectError', () => {
  it('detects Error: prefix', () => {
    expect(detectError('Error: Module not found')).toBe(true);
  });

  it('detects fatal: prefix', () => {
    expect(detectError('fatal: not a git repository')).toBe(true);
  });

  it('detects Python tracebacks', () => {
    expect(detectError('Traceback (most recent call last):')).toBe(true);
  });

  it('detects unhandled promise rejections', () => {
    expect(detectError('UnhandledPromiseRejection: TypeError')).toBe(true);
  });

  it('detects connection errors', () => {
    expect(detectError('connect ECONNREFUSED 127.0.0.1:3000')).toBe(true);
    expect(detectError('connect ETIMEDOUT 10.0.0.1:443')).toBe(true);
  });

  it('returns false for normal output', () => {
    expect(detectError('Running server on port 3000')).toBe(false);
    expect(detectError('Compilation successful')).toBe(false);
    expect(detectError('')).toBe(false);
  });
});
