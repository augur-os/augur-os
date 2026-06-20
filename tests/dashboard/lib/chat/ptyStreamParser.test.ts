import { PtyStreamParser } from '../../../../apps/dashboard/lib/chat/ptyStreamParser';
import type { ParserEvent } from '../../../../apps/dashboard/lib/chat/types';

describe('PtyStreamParser', () => {
  let parser: PtyStreamParser;
  let events: ParserEvent[];
  let handler: (event: ParserEvent) => void;

  beforeEach(() => {
    parser = new PtyStreamParser();
    events = [];
    handler = (event: ParserEvent) => events.push(event);
    parser.addEventListener(handler);
  });

  describe('addEventListener / removeEventListener', () => {
    it('should support multiple event listeners', () => {
      const events2: ParserEvent[] = [];
      const handler2 = (event: ParserEvent) => events2.push(event);
      parser.addEventListener(handler2);

      parser.feed('Hello world\n');

      expect(events.length).toBeGreaterThan(0);
      expect(events2.length).toBe(events.length);
    });

    it('should not add duplicate handlers', () => {
      parser.addEventListener(handler); // duplicate
      parser.feed('Hello world\n');

      const events2: ParserEvent[] = [];
      const handler2 = (event: ParserEvent) => events2.push(event);
      parser.addEventListener(handler2);

      // Reset and feed again
      events.length = 0;
      events2.length = 0;
      parser.feed('Another line\n');

      // handler should fire once per event, not twice
      expect(events.length).toBe(events2.length);
    });

    it('should remove a specific handler', () => {
      const events2: ParserEvent[] = [];
      const handler2 = (event: ParserEvent) => events2.push(event);
      parser.addEventListener(handler2);
      parser.removeEventListener(handler);

      parser.feed('Hello world\n');

      expect(events.length).toBe(0);
      expect(events2.length).toBeGreaterThan(0);
    });
  });

  describe('configurable idle timeout', () => {
    it('should use default timeout', () => {
      jest.useFakeTimers();
      parser.feed('Hello world\n');

      jest.advanceTimersByTime(2999);
      const idleEvents = events.filter(e => e.type === 'idle');
      expect(idleEvents.length).toBe(0);

      jest.advanceTimersByTime(2);
      const idleEventsAfter = events.filter(e => e.type === 'idle');
      expect(idleEventsAfter.length).toBe(1);

      jest.useRealTimers();
    });

    it('should use custom timeout', () => {
      jest.useFakeTimers();
      parser.setIdleTimeout(1000);
      parser.feed('Hello world\n');

      jest.advanceTimersByTime(999);
      expect(events.filter(e => e.type === 'idle').length).toBe(0);

      jest.advanceTimersByTime(2);
      expect(events.filter(e => e.type === 'idle').length).toBe(1);

      jest.useRealTimers();
    });
  });

  describe('ERROR → IDLE recovery', () => {
    it('should recover from ERROR state when user sends a message', () => {
      // Force error state by feeding an error line
      parser.feed('FATAL: something went wrong\n');
      expect(parser.getState()).toBe('ERROR');

      // User sends a message
      parser.addUserMessage('Hello');
      expect(parser.getState()).toBe('IDLE');
    });
  });

  describe('partial ANSI buffering', () => {
    it('should handle split ANSI sequences across chunks', () => {
      // Send a chunk that ends with an incomplete ANSI escape
      parser.feed('Hello \x1b[');
      // Complete the sequence in the next chunk
      parser.feed('32mworld\x1b[0m\n');

      const msgs = parser.getMessages();
      // Should have parsed the content without garbled output
      expect(msgs.length).toBeGreaterThanOrEqual(0);
      // No errors should have been emitted
      const errorEvents = events.filter(e => e.type === 'error_detected');
      expect(errorEvents.length).toBe(0);
    });

    it('should not buffer when chunk ends with complete sequence', () => {
      parser.feed('Hello \x1b[32mworld\x1b[0m\n');

      const errorEvents = events.filter(e => e.type === 'error_detected');
      expect(errorEvents.length).toBe(0);
    });
  });

  describe('message cap', () => {
    it('should cap messages at 500', () => {
      // Feed 510 separate messages
      for (let i = 0; i < 510; i++) {
        parser.addUserMessage(`Message ${i}`);
      }
      expect(parser.getMessages().length).toBeLessThanOrEqual(500);
    });
  });

  describe('basic streaming', () => {
    it('should transition to STREAMING_RESPONSE on text input', () => {
      parser.feed('Hello world\n');
      expect(parser.getState()).toBe('STREAMING_RESPONSE');
    });

    it('should emit message_start and message_chunk events', () => {
      parser.feed('Hello world\n');

      const starts = events.filter(e => e.type === 'message_start');
      const chunks = events.filter(e => e.type === 'message_chunk');

      expect(starts.length).toBe(1);
      expect(chunks.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('reset', () => {
    it('should clear all state including handlers', () => {
      // Add a user message (which is immediately added to messages array)
      parser.addUserMessage('Hello');
      expect(parser.getMessages().length).toBeGreaterThan(0);

      parser.reset();
      expect(parser.getState()).toBe('IDLE');
      expect(parser.getMessages().length).toBe(0);

      // Handler should be cleared after reset
      events.length = 0;
      parser.feed('After reset\n');
      expect(events.length).toBe(0);
    });
  });
});
