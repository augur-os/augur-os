import type {
  BlockManifest,
  BlockInstance,
  BlockProps,
  View,
  ConfigSchema,
  ConfigField,
} from '../types';

describe('Block types', () => {
  it('should define a valid BlockManifest', () => {
    const manifest: BlockManifest = {
      id: 'lifestyle:recipes',
      type: 'data-list',
      title: 'Recipes',
      icon: 'ChefHat',
      expandTo: '/lifestyle/recipes',
      configSchema: {
        filter: { type: 'enum', options: ['all', 'favorites', 'recent'], default: 'recent' },
        limit: { type: 'number', default: 5 },
      },
      dataSource: { mcpTool: 'list-recipes' },
      hub: 'lifestyle',
      skill: 'lifestyle',
    };
    expect(manifest.id).toBe('lifestyle:recipes');
    expect(manifest.type).toBe('data-list');
  });

  it('should define a valid BlockInstance', () => {
    const instance: BlockInstance = {
      instanceId: 'cal-1',
      blockId: 'google-workspace:calendar',
      config: { days: 1, calendars: ['work'] },
      position: { x: 0, y: 0, w: 6, h: 4 },
    };
    expect(instance.position.w).toBe(6);
  });

  it('should define a valid View', () => {
    const view: View = {
      id: 'morning',
      title: 'Morning',
      pinned: true,
      createdAt: '2026-03-09',
      updatedAt: '2026-03-09',
      layout: { columns: 12, rowHeight: 80 },
      blocks: [],
    };
    expect(view.layout.columns).toBe(12);
  });
});
