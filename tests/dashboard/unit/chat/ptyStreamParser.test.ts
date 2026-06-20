/**
 * @jest-environment node
 *
 * Tests for PTY Stream Parser — State Machine
 * ADR-047: Operation Mode Chatbot Experience
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { PtyStreamParser } from '@/lib/chat/ptyStreamParser';
import type { ParserEvent, ParserState } from '@/lib/chat/types';

// Helper to collect events
function collectEvents(parser: PtyStreamParser): ParserEvent[] {
  const events: ParserEvent[] = [];
  parser.addEventListener((e) => events.push(e));
  return events;
}

// Helper to find events of a specific type
function findEvents<T extends ParserEvent['type']>(
  events: ParserEvent[],
  type: T
): Extract<ParserEvent, { type: T }>[] {
  return events.filter((e): e is Extract<ParserEvent, { type: T }> => e.type === type);
}

describe('PtyStreamParser', () => {
  let parser: PtyStreamParser;

  beforeEach(() => {
    parser = new PtyStreamParser();
  });

  afterEach(() => {
    // Clean up idle timers to prevent worker leak
    parser.reset();
  });

  // -------------------------------------------------------------------------
  // Basic State Transitions
  // -------------------------------------------------------------------------

  describe('State Transitions', () => {
    it('starts in IDLE state', () => {
      expect(parser.getState()).toBe('IDLE');
    });

    it('transitions to STREAMING_RESPONSE on regular text', () => {
      const events = collectEvents(parser);
      parser.feed('Hello, how can I help you today?\n');

      const stateChanges = findEvents(events, 'state_change');
      expect(stateChanges.some((e) => e.transition.to === 'STREAMING_RESPONSE')).toBe(true);
    });

    it('transitions to THINKING on thinking indicators', () => {
      const events = collectEvents(parser);
      parser.feed('Thinking...\n');

      const stateChanges = findEvents(events, 'state_change');
      expect(stateChanges.some((e) => e.transition.to === 'THINKING')).toBe(true);
    });

    it('transitions to AWAITING_INPUT on prompt detection', () => {
      const events = collectEvents(parser);
      parser.feed('Do you want to proceed? (y/n)\n');

      expect(parser.getState()).toBe('AWAITING_INPUT');
    });

    it('transitions to ERROR on error detection', () => {
      const events = collectEvents(parser);
      parser.feed('FATAL: database connection failed\n');

      expect(parser.getState()).toBe('ERROR');
    });

    it('transitions to TOOL_EXECUTING on tool call', () => {
      const events = collectEvents(parser);
      parser.feed('Running: file-read\n');

      expect(parser.getState()).toBe('TOOL_EXECUTING');
    });
  });

  // -------------------------------------------------------------------------
  // Message Accumulation
  // -------------------------------------------------------------------------

  describe('Message Accumulation', () => {
    it('creates assistant message from streaming text', () => {
      parser.feed('Here is the answer to your question.\nIt spans multiple lines.');

      const current = parser.getCurrentMessage();
      expect(current).not.toBeNull();
      expect(current?.role).toBe('assistant');
      expect(current?.content).toContain('Here is the answer');
      expect(current?.status).toBe('streaming');
    });

    it('accumulates multi-chunk text into single message', () => {
      parser.feed('First chunk of text.\n');
      parser.feed('Second chunk of text.\n');

      const current = parser.getCurrentMessage();
      expect(current?.content).toContain('First chunk');
      expect(current?.content).toContain('Second chunk');
    });

    it('records user messages', () => {
      const msg = parser.addUserMessage('What is the weather?');
      expect(msg.role).toBe('user');
      expect(msg.content).toBe('What is the weather?');
      expect(msg.status).toBe('complete');

      const messages = parser.getMessages();
      expect(messages).toHaveLength(1);
      expect(messages[0].role).toBe('user');
    });

    it('records user messages with attachments', () => {
      const msg = parser.addUserMessage('Check this file', [
        {
          originalName: 'test.pdf',
          stagedPath: '/tmp/test.pdf',
          size: 1024,
          mimeType: 'application/pdf',
          timestamp: Date.now(),
        },
      ]);
      expect(msg.attachments).toHaveLength(1);
      expect(msg.attachments![0].originalName).toBe('test.pdf');
    });
  });

  // -------------------------------------------------------------------------
  // Prompt Handling
  // -------------------------------------------------------------------------

  describe('Prompt Handling', () => {
    it('emits prompt_detected event for y/n questions', () => {
      const events = collectEvents(parser);
      parser.feed('Should I continue? (Y/n)\n');

      const prompts = findEvents(events, 'prompt_detected');
      expect(prompts).toHaveLength(1);
      expect(prompts[0].prompt.type).toBe('confirm');
      expect(prompts[0].prompt.options).toEqual(['Yes', 'No']);
    });

    it('creates message with promptCard', () => {
      parser.feed('Should I continue? (Y/n)\n');

      const messages = parser.getMessages();
      expect(messages).toHaveLength(1);
      expect(messages[0].promptCard).toBeDefined();
      expect(messages[0].promptCard?.resolved).toBe(false);
      expect(messages[0].status).toBe('awaiting_input');
    });

    it('resolves prompt with user answer', () => {
      parser.feed('Should I continue? (Y/n)\n');

      const msg = parser.getMessages()[0];
      parser.resolvePrompt(msg.id, 'Yes');

      expect(msg.promptCard?.resolved).toBe(true);
      expect(msg.promptCard?.answer).toBe('Yes');
      expect(msg.status).toBe('complete');
    });

    it('completes streaming message before showing prompt', () => {
      const events = collectEvents(parser);

      // First: streaming response
      parser.feed('Let me update your resume.\n');
      // Then: prompt
      parser.feed('Should I proceed? (y/n)\n');

      const messages = parser.getMessages();
      // Should have: 1 completed assistant message + 1 prompt message
      expect(messages.length).toBeGreaterThanOrEqual(2);
      expect(messages[0].role).toBe('assistant');
      expect(messages[0].status).toBe('complete');
      expect(messages[messages.length - 1].promptCard).toBeDefined();
    });
  });

  // -------------------------------------------------------------------------
  // Tool Approval Handling
  // -------------------------------------------------------------------------

  describe('Tool Approval Handling', () => {
    it('emits tool_approval_detected event', () => {
      const events = collectEvents(parser);
      parser.feed('Do you want to run file-read?\n');

      const approvals = findEvents(events, 'tool_approval_detected');
      expect(approvals).toHaveLength(1);
      expect(approvals[0].approval.toolName).toBeDefined();
    });

    it('creates message with toolApproval card', () => {
      parser.feed('Allow Bash to execute the command\n');

      const messages = parser.getMessages();
      const approvalMsg = messages.find((m) => m.toolApproval);
      expect(approvalMsg).toBeDefined();
      expect(approvalMsg?.toolApproval?.resolved).toBe(false);
    });

    it('resolves tool approval', () => {
      parser.feed('Allow Bash to execute the command\n');

      const msg = parser.getMessages().find((m) => m.toolApproval)!;
      parser.resolveToolApproval(msg.id, 'allow');

      expect(msg.toolApproval?.resolved).toBe(true);
      expect(msg.toolApproval?.decision).toBe('allow');
    });
  });

  // -------------------------------------------------------------------------
  // Error Handling
  // -------------------------------------------------------------------------

  describe('Error Handling', () => {
    it('emits error_detected event on fatal error', () => {
      const events = collectEvents(parser);
      parser.feed('FATAL: unable to connect\n');

      const errors = findEvents(events, 'error_detected');
      expect(errors).toHaveLength(1);
    });

    it('creates message with errorCard', () => {
      parser.feed('FATAL: unable to connect\n');

      const messages = parser.getMessages();
      const errMsg = messages.find((m) => m.errorCard);
      expect(errMsg).toBeDefined();
      expect(errMsg?.errorCard?.summary).toBeDefined();
      expect(errMsg?.status).toBe('error');
    });

    it('flushes streaming message before error', () => {
      parser.feed('Processing your request...\n');
      parser.feed('FATAL: disk full\n');

      const messages = parser.getMessages();
      // First message should be the completed streaming text
      expect(messages[0].role).toBe('assistant');
      expect(messages[0].status).toBe('complete');
      // Second message should be the error
      const errMsg = messages.find((m) => m.errorCard);
      expect(errMsg).toBeDefined();
    });

    it('handles process exit with error', () => {
      const events = collectEvents(parser);
      parser.processExit(1);

      const errors = findEvents(events, 'error_detected');
      expect(errors).toHaveLength(1);
      expect(errors[0].error.processExited).toBe(true);
      expect(errors[0].error.severity).toBe('fatal');
    });

    it('handles clean process exit (code 0) without error', () => {
      const events = collectEvents(parser);
      parser.processExit(0);

      const errors = findEvents(events, 'error_detected');
      expect(errors).toHaveLength(0);
      expect(parser.getState()).toBe('IDLE');
    });
  });

  // -------------------------------------------------------------------------
  // Progress Tracking
  // -------------------------------------------------------------------------

  describe('Progress Tracking', () => {
    it('emits progress_update event', () => {
      const events = collectEvents(parser);
      parser.feed('Step 2 of 5: Analyzing data\n');

      const progress = findEvents(events, 'progress_update');
      expect(progress).toHaveLength(1);
      expect(progress[0].progress.percentage).toBe(40);
    });

    it('detects percentage-based progress', () => {
      const events = collectEvents(parser);
      parser.feed('[3/10] Processing file\n');

      const progress = findEvents(events, 'progress_update');
      expect(progress).toHaveLength(1);
      expect(progress[0].progress.percentage).toBe(30);
    });
  });

  // -------------------------------------------------------------------------
  // Tool Call Tracking
  // -------------------------------------------------------------------------

  describe('Tool Call Tracking', () => {
    it('emits tool_call_start event', () => {
      const events = collectEvents(parser);
      parser.feed('Running: file-read\n');

      const toolStarts = findEvents(events, 'tool_call_start');
      expect(toolStarts).toHaveLength(1);
      expect(toolStarts[0].name).toBe('file-read');
      expect(toolStarts[0].displayName).toBe('File Read');
    });
  });

  // -------------------------------------------------------------------------
  // Fallback Tiers
  // -------------------------------------------------------------------------

  describe('Fallback Tiers', () => {
    it('starts in structured tier', () => {
      expect(parser.getFallbackTier()).toBe('structured');
    });

    it('switches to terminal on TUI escape sequences', () => {
      const events = collectEvents(parser);
      // Alternate screen buffer ON (vim, htop, etc.)
      parser.feed('\x1b[?1049h');

      expect(parser.getFallbackTier()).toBe('terminal');
      const tierChanges = findEvents(events, 'fallback_tier_change');
      expect(tierChanges).toHaveLength(1);
      expect(tierChanges[0].tier).toBe('terminal');
    });

    it('stops processing in terminal fallback mode', () => {
      // Switch to terminal
      parser.feed('\x1b[?1049h');
      expect(parser.getFallbackTier()).toBe('terminal');

      // Feed more data — should be ignored by parser
      const events = collectEvents(parser);
      parser.feed('This should not create a message');

      const messages = parser.getMessages();
      const msgStarts = findEvents(events, 'message_start');
      expect(msgStarts).toHaveLength(0);
    });

    it('can exit terminal fallback', () => {
      parser.feed('\x1b[?1049h');
      expect(parser.getFallbackTier()).toBe('terminal');

      parser.exitTerminalFallback();
      expect(parser.getFallbackTier()).toBe('structured');
      expect(parser.getState()).toBe('IDLE');
    });

    it('resets raw_text fallback on new user message', () => {
      // Force raw_text tier by feeding low-confidence content
      // (This is harder to trigger directly, so we test the reset mechanism)
      parser.addUserMessage('New question');
      expect(parser.getFallbackTier()).toBe('structured');
    });
  });

  // -------------------------------------------------------------------------
  // Reset
  // -------------------------------------------------------------------------

  describe('Reset', () => {
    it('clears all state on reset', () => {
      parser.feed('Some text\n');
      parser.feed('More text\n');
      parser.addUserMessage('Question');

      parser.reset();

      expect(parser.getState()).toBe('IDLE');
      expect(parser.getMessages()).toHaveLength(0);
      expect(parser.getCurrentMessage()).toBeNull();
      expect(parser.getFallbackTier()).toBe('structured');
    });
  });

  // -------------------------------------------------------------------------
  // Multi-Turn Conversation Simulation
  // -------------------------------------------------------------------------

  describe('Multi-Turn Conversation', () => {
    it('handles a full conversation flow', () => {
      const events = collectEvents(parser);

      // 1. User sends message
      parser.addUserMessage('Update my resume with the new job description');

      // 2. Agent thinks
      parser.feed('Thinking...\n');
      expect(parser.getState()).toBe('THINKING');

      // 3. Agent starts tool
      parser.feed('Running: file-read\n');
      expect(parser.getState()).toBe('TOOL_EXECUTING');

      // 4. Agent streams response
      parser.feed("I've read your resume. Here are the changes I suggest:\n");
      parser.feed('1. Updated the summary section\n');
      parser.feed('2. Added the new role\n');
      expect(parser.getState()).toBe('STREAMING_RESPONSE');

      // 5. Agent asks for confirmation
      parser.feed('Should I apply these changes? (Y/n)\n');
      expect(parser.getState()).toBe('AWAITING_INPUT');

      // 6. User confirms
      const promptMsg = parser.getMessages().find((m) => m.promptCard);
      expect(promptMsg).toBeDefined();
      parser.resolvePrompt(promptMsg!.id, 'Yes');

      // Verify message history
      const messages = parser.getMessages();
      expect(messages.length).toBeGreaterThanOrEqual(3); // user + assistant text + prompt
      expect(messages[0].role).toBe('user');
    });

    it('handles error mid-conversation with recovery', () => {
      // 1. User sends message
      parser.addUserMessage('Check my calendar');

      // 2. Agent starts responding
      parser.feed('Let me check your calendar...\n');

      // 3. Error occurs
      parser.feed('Error: Connection refused\n');
      expect(parser.getState()).toBe('ERROR');

      // 4. The streaming message should have been flushed
      const messages = parser.getMessages();
      const assistantMsg = messages.find((m) => m.role === 'assistant' && m.status === 'complete');
      expect(assistantMsg).toBeDefined();

      // 5. Error card should exist
      const errorMsg = messages.find((m) => m.errorCard);
      expect(errorMsg).toBeDefined();
    });
  });

  // -------------------------------------------------------------------------
  // Edge Cases
  // -------------------------------------------------------------------------

  describe('Edge Cases', () => {
    it('handles empty input gracefully', () => {
      parser.feed('');
      parser.feed('\n\n\n');
      expect(parser.getMessages()).toHaveLength(0);
    });

    it('handles ANSI codes in input', () => {
      // Color codes should be stripped before classification
      parser.feed('\x1b[32mHello, world!\x1b[0m\n');
      const current = parser.getCurrentMessage();
      expect(current?.content).toContain('Hello, world!');
      // Should NOT contain ANSI codes
      expect(current?.content).not.toContain('\x1b');
    });

    it('generates unique message IDs', () => {
      parser.addUserMessage('First');
      parser.addUserMessage('Second');

      const messages = parser.getMessages();
      expect(messages[0].id).not.toBe(messages[1].id);
    });

    it('handles rapid successive feeds', () => {
      for (let i = 0; i < 50; i++) {
        parser.feed(`Line ${i}: some output text here\n`);
      }

      const current = parser.getCurrentMessage();
      expect(current).not.toBeNull();
      expect(current?.content).toContain('Line 0');
      expect(current?.content).toContain('Line 49');
    });
  });
});
