import fs from "fs";
import path from "path";
import yaml from "js-yaml";
import { AUGUR_STATE_DIR } from "@/lib/paths";
import type { View, BlockInstance } from "./types";
import { parseHubViewId } from "./utils";

export { getHubViewId } from "./utils";

export class ViewStorage {
  private dir: string;

  constructor(dir?: string) {
    this.dir = dir || path.join(AUGUR_STATE_DIR, "views");
    if (!fs.existsSync(this.dir)) {
      fs.mkdirSync(this.dir, { recursive: true });
    }
  }

  private filePath(id: string): string {
    return path.join(this.dir, `${id}.yaml`);
  }

  list(): View[] {
    const files = fs.readdirSync(this.dir).filter((f) => f.endsWith(".yaml"));
    return files
      .map((f) => this.readFile(path.join(this.dir, f)))
      .filter((v): v is View => v !== null);
  }

  get(id: string): View | null {
    return this.readFile(this.filePath(id));
  }

  getOrCreateHubOverview(id: string): View {
    const existing = this.get(id);
    if (existing) {
      return existing;
    }

    const hubId = parseHubViewId(id);
    if (!hubId) {
      throw new Error(`View '${id}' is not a canonical hub overview id`);
    }

    return this.create({
      id,
      title: `${hubId} Overview`,
      blocks: [],
    });
  }

  create(input: {
    id?: string;
    title: string;
    pinned?: boolean;
    icon?: string;
    blocks?: BlockInstance[];
    layout?: View["layout"];
  }): View {
    const view: View = {
      id: input.id ?? crypto.randomUUID().slice(0, 8),
      title: input.title,
      icon: input.icon,
      pinned: input.pinned ?? false,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      layout: input.layout ?? { columns: 12, rowHeight: 80 },
      blocks: input.blocks ?? [],
    };
    this.writeFile(view);
    return view;
  }

  update(
    id: string,
    updates: Partial<
      Pick<View, "title" | "icon" | "pinned" | "blocks" | "layout">
    >,
  ): View | null {
    const view = this.get(id);
    if (!view) return null;

    const updated = {
      ...view,
      ...updates,
      updatedAt: new Date().toISOString(),
    };
    this.writeFile(updated);
    return updated;
  }

  delete(id: string): boolean {
    const fp = this.filePath(id);
    if (!fs.existsSync(fp)) return false;
    fs.unlinkSync(fp);
    return true;
  }

  addBlock(viewId: string, block: BlockInstance): View | null {
    const view = this.get(viewId);
    if (!view) return null;
    view.blocks.push(block);
    view.updatedAt = new Date().toISOString();
    this.writeFile(view);
    return view;
  }

  removeBlock(viewId: string, instanceId: string): View | null {
    const view = this.get(viewId);
    if (!view) return null;
    view.blocks = view.blocks.filter((b) => b.instanceId !== instanceId);
    view.updatedAt = new Date().toISOString();
    this.writeFile(view);
    return view;
  }

  private readFile(fp: string): View | null {
    if (!fs.existsSync(fp)) return null;
    const content = fs.readFileSync(fp, "utf-8");
    return yaml.load(content) as View;
  }

  private writeFile(view: View): void {
    fs.writeFileSync(
      this.filePath(view.id),
      yaml.dump(view, { lineWidth: 120 }),
      "utf-8",
    );
  }
}
