/**
 * @jest-environment node
 *
 * Tests for PTY Stream Parser — Pattern Classification
 * ADR-047: Operation Mode Chatbot Experience
 */

import { describe, it, expect } from '@jest/globals';
import { classifyLine, detectTuiEscapes } from '@/lib/chat/parserPatterns';

// ---------------------------------------------------------------------------
// Prompt Detection
// ---------------------------------------------------------------------------

describe('classifyLine — Prompt Detection', () => {
  it('detects y/n confirmation with default Yes', () => {
    const result = classifyLine('Do you want to update the file? (Y/n)');
    expect(result.category).toBe('prompt');
    expect(result.confidence).toBeGreaterThanOrEqual(0.7);
    expect(result.extracted?.options).toEqual(['Yes', 'No']);
    expect(result.extracted?.defaultIndex).toBe(0);
  });

  it('detects y/n confirmation with default No', () => {
    const result = classifyLine('Overwrite existing data? (y/N)');
    expect(result.category).toBe('prompt');
    expect(result.extracted?.defaultIndex).toBe(1);
  });

  it('detects [yes/no] bracket format', () => {
    const result = classifyLine('Are you sure you want to proceed? [yes/no]');
    expect(result.category).toBe('prompt');
    expect(result.extracted?.options).toEqual(['Yes', 'No']);
  });

  it('detects "Press Enter to continue"', () => {
    const result = classifyLine('Press Enter to continue');
    expect(result.category).toBe('prompt');
    expect(result.extracted?.options).toEqual(['Continue']);
  });

  it('detects "Enter [field]:" free text prompt', () => {
    const result = classifyLine('Enter your name:');
    expect(result.category).toBe('prompt');
    expect(result.extracted?.options).toEqual([]);
  });

  it('detects generic question ending with ?', () => {
    const result = classifyLine('What company name should I use for the cover letter?');
    expect(result.category).toBe('prompt');
  });

  it('does NOT classify short questions as prompts', () => {
    // "Why?" is only 4 chars — too short for generic ? detection (minimum 10)
    const result = classifyLine('Why?');
    expect(result.category).toBe('none');
  });

  it('does NOT classify YAML key:value as a prompt', () => {
    const result = classifyLine('  name: John Doe');
    expect(result.category).toBe('none');
  });

  it('does NOT classify long prose ending with colon as a prompt', () => {
    const result = classifyLine(
      'This is a very long line that explains the configuration format and its various parameters and settings and options and details:'
    );
    // Either no match or low confidence
    expect(result.category === 'none' || result.confidence < 0.7).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// Tool Approval Detection
// ---------------------------------------------------------------------------

describe('classifyLine — Tool Approval Detection', () => {
  it('detects "Do you want to run [tool]?"', () => {
    const result = classifyLine('Do you want to run file-read?');
    expect(result.category).toBe('tool_approval');
    expect(result.extracted?.toolName).toBe('file-read');
  });

  it('detects "Allow [tool] to [action]"', () => {
    const result = classifyLine('Allow Bash to execute the command');
    expect(result.category).toBe('tool_approval');
    expect(result.extracted?.toolName).toBe('Bash');
    expect(result.extracted?.toolDescription).toBeDefined();
  });

  it('detects "Tool: [name]"', () => {
    const result = classifyLine('Tool: file-write');
    expect(result.category).toBe('tool_approval');
    expect(result.extracted?.toolName).toBe('file-write');
  });
});

// ---------------------------------------------------------------------------
// Error Detection
// ---------------------------------------------------------------------------

describe('classifyLine — Error Detection', () => {
  it('detects fatal "exit code N"', () => {
    const result = classifyLine('Process finished with exit code 1');
    expect(result.category).toBe('error');
    expect(result.extracted?.errorMessage).toContain('code 1');
  });

  it('detects FATAL prefix', () => {
    const result = classifyLine('FATAL: unable to connect to database');
    expect(result.category).toBe('error');
  });

  it('detects Python traceback', () => {
    const result = classifyLine('Traceback (most recent call last)');
    expect(result.category).toBe('error');
  });

  it('detects Connection refused', () => {
    const result = classifyLine('Error: Connection refused at localhost:3000');
    expect(result.category).toBe('error');
    expect(result.extracted?.errorMessage).toBeDefined();
  });

  it('detects Permission denied', () => {
    const result = classifyLine('Permission denied: /etc/shadow');
    expect(result.category).toBe('error');
  });

  it('detects command not found', () => {
    const result = classifyLine('bash: foobar: command not found');
    expect(result.category).toBe('error');
  });

  it('detects ENOENT', () => {
    const result = classifyLine('ENOENT: no such file or directory, open /tmp/foo.txt');
    expect(result.category).toBe('error');
  });

  it('detects timeout errors', () => {
    const result = classifyLine('Request timed out after 30000ms');
    expect(result.category).toBe('error');
  });

  it('classifies JS stack trace lines as noise (no state change)', () => {
    const result = classifyLine('    at Module._compile (node:internal/modules/cjs:1234:12)');
    // Noise-level errors return category 'none' (don't change parser state)
    expect(result.category).toBe('none');
  });

  it('detects warnings', () => {
    const result = classifyLine('Warning: this API is deprecated');
    expect(result.category).toBe('error');
    // It's classified as error category but with warning severity
    // (severity is determined by the pattern, not returned in PatternMatch)
  });
});

// ---------------------------------------------------------------------------
// Progress Detection
// ---------------------------------------------------------------------------

describe('classifyLine — Progress Detection', () => {
  it('detects "Step N of M" format', () => {
    const result = classifyLine('Step 2 of 5: Analyzing data');
    expect(result.category).toBe('progress');
    expect(result.extracted?.percentage).toBe(40); // 2/5 = 40%
    expect(result.extracted?.stepCurrent).toBe(2);
    expect(result.extracted?.stepTotal).toBe(5);
    expect(result.extracted?.stepLabel).toBe('Analyzing data');
  });

  it('detects percentage format', () => {
    const result = classifyLine('Processing... 75%');
    expect(result.category).toBe('progress');
    expect(result.extracted?.percentage).toBe(75);
  });

  it('detects [N/M] counter format', () => {
    const result = classifyLine('[3/10] Processing file data.csv');
    expect(result.category).toBe('progress');
    expect(result.extracted?.percentage).toBe(30);
    expect(result.extracted?.stepCurrent).toBe(3);
    expect(result.extracted?.stepTotal).toBe(10);
  });

  it('caps percentage at 100', () => {
    const result = classifyLine('Progress: 150%');
    expect(result.category).toBe('progress');
    expect(result.extracted?.percentage).toBe(100);
  });
});

// ---------------------------------------------------------------------------
// Tool Call Detection
// ---------------------------------------------------------------------------

describe('classifyLine — Tool Call Detection', () => {
  it('detects Claude Code bullet tool format', () => {
    const result = classifyLine('⏺ file-read');
    expect(result.category).toBe('tool_call');
    expect(result.extracted?.toolName).toBe('file-read');
  });

  it('detects "Running: tool" format', () => {
    const result = classifyLine('Running: execute-chain');
    expect(result.category).toBe('tool_call');
    expect(result.extracted?.toolName).toBe('execute-chain');
  });

  it('detects "[tool] name" format', () => {
    const result = classifyLine('[tool] file-write');
    expect(result.category).toBe('tool_call');
    expect(result.extracted?.toolName).toBe('file-write');
  });
});

// ---------------------------------------------------------------------------
// Thinking Detection
// ---------------------------------------------------------------------------

describe('classifyLine — Thinking Detection', () => {
  it('detects "Thinking..." pattern', () => {
    const result = classifyLine('Thinking...');
    expect(result.category).toBe('thinking');
  });

  it('detects "Processing..." pattern', () => {
    const result = classifyLine('Processing...');
    expect(result.category).toBe('thinking');
  });

  it('detects bare dots', () => {
    const result = classifyLine('...');
    expect(result.category).toBe('thinking');
  });

  it('detects hourglass emoji', () => {
    const result = classifyLine('\u23F3 Working on your request');
    expect(result.category).toBe('thinking');
  });
});

// ---------------------------------------------------------------------------
// No Match (Regular Text)
// ---------------------------------------------------------------------------

describe('classifyLine — Regular Text', () => {
  it('returns none for normal prose', () => {
    const result = classifyLine('The weather today is sunny with a high of 72 degrees.');
    expect(result.category).toBe('none');
  });

  it('returns none for empty input', () => {
    const result = classifyLine('');
    expect(result.category).toBe('none');
  });

  it('returns none for whitespace only', () => {
    const result = classifyLine('   ');
    expect(result.category).toBe('none');
  });

  it('returns none for code output', () => {
    const result = classifyLine('const x = 42;');
    expect(result.category).toBe('none');
  });
});

// ---------------------------------------------------------------------------
// TUI Escape Detection
// ---------------------------------------------------------------------------

describe('detectTuiEscapes', () => {
  it('detects alternate screen buffer ON', () => {
    expect(detectTuiEscapes('\x1b[?1049h')).toBe(true);
  });

  it('does NOT detect cursor positioning (intentionally excluded - Claude Code uses for header)', () => {
    expect(detectTuiEscapes('\x1b[10;20H')).toBe(false);
  });

  it('detects screen clear', () => {
    expect(detectTuiEscapes('\x1b[2J')).toBe(true);
  });

  it('does NOT detect cursor hide (intentionally excluded - used by normal CLIs)', () => {
    expect(detectTuiEscapes('\x1b[?25l')).toBe(false);
  });

  it('returns false for regular text', () => {
    expect(detectTuiEscapes('Hello, world!')).toBe(false);
  });

  it('returns false for simple ANSI colors (not TUI)', () => {
    // Simple color codes are handled by stripAnsi, not TUI detection
    expect(detectTuiEscapes('\x1b[32mGreen text\x1b[0m')).toBe(false);
  });
});
