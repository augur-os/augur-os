import { ViewStorage } from '@/lib/blocks/view-storage';
import fs from 'fs';
import path from 'path';
import os from 'os';
import { getHubViewId } from '@/lib/blocks/utils';

describe('ViewStorage', () => {
  let storage: ViewStorage;
  let tmpDir: string;

  beforeEach(() => {
    tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'views-'));
    storage = new ViewStorage(tmpDir);
  });

  afterEach(() => {
    fs.rmSync(tmpDir, { recursive: true });
  });

  it('creates and reads a view', () => {
    const view = storage.create({ title: 'Morning', pinned: true });
    expect(view.id).toBeDefined();
    expect(view.title).toBe('Morning');

    const loaded = storage.get(view.id);
    expect(loaded?.title).toBe('Morning');
  });

  it('lists all views', () => {
    storage.create({ title: 'Morning', pinned: true });
    storage.create({ title: 'Work', pinned: false });
    const list = storage.list();
    expect(list).toHaveLength(2);
  });

  it('updates a view', () => {
    const view = storage.create({ title: 'Morning', pinned: false });
    storage.update(view.id, { title: 'Morning Routine', pinned: true });
    const loaded = storage.get(view.id);
    expect(loaded?.title).toBe('Morning Routine');
    expect(loaded?.pinned).toBe(true);
  });

  it('deletes a view', () => {
    const view = storage.create({ title: 'Temp', pinned: false });
    storage.delete(view.id);
    expect(storage.get(view.id)).toBeNull();
    expect(storage.list()).toHaveLength(0);
  });

  it('adds and removes block instances', () => {
    const view = storage.create({ title: 'Test', pinned: false });
    storage.addBlock(view.id, {
      instanceId: 'recipes-1',
      blockId: 'lifestyle:recipes',
      config: { filter: 'recent' },
      position: { x: 0, y: 0, w: 6, h: 4 },
    });

    const loaded = storage.get(view.id);
    expect(loaded?.blocks).toHaveLength(1);
    expect(loaded?.blocks[0].blockId).toBe('lifestyle:recipes');

    storage.removeBlock(view.id, 'recipes-1');
    const after = storage.get(view.id);
    expect(after?.blocks).toHaveLength(0);
  });

  it('materializes canonical hub overview views as empty persisted state', () => {
    const viewId = getHubViewId('life');

    const created = storage.getOrCreateHubOverview(viewId);
    const loaded = storage.get(viewId);

    expect(created.id).toBe(viewId);
    expect(created.title).toBe('life Overview');
    expect(created.blocks).toEqual([]);
    expect(loaded?.id).toBe(viewId);
    expect(loaded?.blocks).toEqual([]);
  });
});
