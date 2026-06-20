/**
 * Tests for agentBubbleStore — ADR-160
 */

import { useAgentBubbleStore, MAX_BUBBLES } from '@/lib/stores/agentBubbleStore';

// Reset store between tests
beforeEach(() => {
  useAgentBubbleStore.setState({ bubbles: [], queue: [] });
});

function makeBubble(overrides: Record<string, unknown> = {}) {
  return {
    actionId: 'test-action',
    actionLabel: 'Test Action',
    status: 'running' as const,
    isExpanded: false,
    startedAt: Date.now(),
    ...overrides,
  };
}

describe('agentBubbleStore', () => {
  describe('addBubble', () => {
    it('adds a bubble and returns its ID', () => {
      const id = useAgentBubbleStore.getState().addBubble(makeBubble());
      expect(id).toBeTruthy();
      expect(useAgentBubbleStore.getState().bubbles).toHaveLength(1);
      expect(useAgentBubbleStore.getState().bubbles[0].id).toBe(id);
    });

    it('returns null when at max capacity', () => {
      for (let i = 0; i < MAX_BUBBLES; i++) {
        useAgentBubbleStore.getState().addBubble(makeBubble({ actionId: `action-${i}` }));
      }
      expect(useAgentBubbleStore.getState().bubbles).toHaveLength(MAX_BUBBLES);

      const id = useAgentBubbleStore.getState().addBubble(makeBubble({ actionId: 'overflow' }));
      expect(id).toBeNull();
      expect(useAgentBubbleStore.getState().bubbles).toHaveLength(MAX_BUBBLES);
    });

    it('assigns unique IDs to each bubble', () => {
      const id1 = useAgentBubbleStore.getState().addBubble(makeBubble());
      const id2 = useAgentBubbleStore.getState().addBubble(makeBubble());
      expect(id1).not.toBe(id2);
    });
  });

  describe('removeBubble', () => {
    it('removes a bubble by ID', () => {
      const id = useAgentBubbleStore.getState().addBubble(makeBubble());
      expect(useAgentBubbleStore.getState().bubbles).toHaveLength(1);

      useAgentBubbleStore.getState().removeBubble(id!);
      expect(useAgentBubbleStore.getState().bubbles).toHaveLength(0);
    });

    it('does not affect other bubbles', () => {
      const id1 = useAgentBubbleStore.getState().addBubble(makeBubble({ actionLabel: 'First' }));
      useAgentBubbleStore.getState().addBubble(makeBubble({ actionLabel: 'Second' }));

      useAgentBubbleStore.getState().removeBubble(id1!);
      const remaining = useAgentBubbleStore.getState().bubbles;
      expect(remaining).toHaveLength(1);
      expect(remaining[0].actionLabel).toBe('Second');
    });
  });

  describe('updateBubble', () => {
    it('updates a bubble status', () => {
      const id = useAgentBubbleStore.getState().addBubble(makeBubble());

      useAgentBubbleStore.getState().updateBubble(id!, { status: 'attention' });
      expect(useAgentBubbleStore.getState().bubbles[0].status).toBe('attention');
    });

    it('updates multiple fields at once', () => {
      const id = useAgentBubbleStore.getState().addBubble(makeBubble());

      useAgentBubbleStore.getState().updateBubble(id!, {
        status: 'complete',
        completedAt: 12345,
      });

      const bubble = useAgentBubbleStore.getState().bubbles[0];
      expect(bubble.status).toBe('complete');
      expect(bubble.completedAt).toBe(12345);
    });
  });

  describe('toggleExpanded', () => {
    it('toggles expanded state', () => {
      const id = useAgentBubbleStore.getState().addBubble(makeBubble({ isExpanded: false }));

      useAgentBubbleStore.getState().toggleExpanded(id!);
      expect(useAgentBubbleStore.getState().bubbles[0].isExpanded).toBe(true);

      useAgentBubbleStore.getState().toggleExpanded(id!);
      expect(useAgentBubbleStore.getState().bubbles[0].isExpanded).toBe(false);
    });
  });

  describe('getBubbleCount', () => {
    it('returns correct count', () => {
      expect(useAgentBubbleStore.getState().getBubbleCount()).toBe(0);

      useAgentBubbleStore.getState().addBubble(makeBubble());
      expect(useAgentBubbleStore.getState().getBubbleCount()).toBe(1);

      useAgentBubbleStore.getState().addBubble(makeBubble());
      expect(useAgentBubbleStore.getState().getBubbleCount()).toBe(2);
    });
  });

  describe('queue', () => {
    it('enqueues and dequeues in FIFO order', () => {
      useAgentBubbleStore.getState().enqueue({ actionId: 'a1', actionLabel: 'First', prompt: 'p1' });
      useAgentBubbleStore.getState().enqueue({ actionId: 'a2', actionLabel: 'Second', prompt: 'p2' });

      expect(useAgentBubbleStore.getState().getQueueCount()).toBe(2);

      const first = useAgentBubbleStore.getState().dequeue();
      expect(first?.actionLabel).toBe('First');
      expect(useAgentBubbleStore.getState().getQueueCount()).toBe(1);

      const second = useAgentBubbleStore.getState().dequeue();
      expect(second?.actionLabel).toBe('Second');
      expect(useAgentBubbleStore.getState().getQueueCount()).toBe(0);
    });

    it('dequeue returns null when empty', () => {
      const result = useAgentBubbleStore.getState().dequeue();
      expect(result).toBeNull();
    });
  });

  describe('capacity enforcement', () => {
    it('enforces max 5 concurrent bubbles', () => {
      for (let i = 0; i < MAX_BUBBLES; i++) {
        const id = useAgentBubbleStore.getState().addBubble(makeBubble({ actionId: `a-${i}` }));
        expect(id).toBeTruthy();
      }

      expect(useAgentBubbleStore.getState().bubbles).toHaveLength(MAX_BUBBLES);

      // 6th should fail
      const overflow = useAgentBubbleStore.getState().addBubble(makeBubble({ actionId: 'overflow' }));
      expect(overflow).toBeNull();
      expect(useAgentBubbleStore.getState().bubbles).toHaveLength(MAX_BUBBLES);
    });
  });
});
