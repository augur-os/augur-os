import { resolveBlockComponent, getBlockManifest } from '@/lib/blocks/block-resolver';

describe('block-resolver', () => {
  it('resolves known block types to components', () => {
    const types = [
      'stat-card', 'stat-grid', 'data-list', 'data-table',
      'action-bar', 'card-grid', 'chart', 'markdown',
      'calendar', 'activity-feed', 'notes', 'embed',
      'ops-board', 'progress',
    ];

    for (const type of types) {
      const component = resolveBlockComponent(type);
      expect(component).toBeDefined();
    }
  });

  it('returns null for unknown block type', () => {
    const component = resolveBlockComponent('nonexistent');
    expect(component).toBeNull();
  });

  it('returns null for unknown block manifest', () => {
    const manifest = getBlockManifest('nonexistent:block');
    expect(manifest).toBeNull();
  });
});
