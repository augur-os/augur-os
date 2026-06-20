/**
 * @jest-environment node
 */

import fs from "fs/promises";
import os from "os";
import path from "path";

import {
  collectConventionPages,
  buildHubRegistries,
  generateRegistries,
} from "@/scripts/mount/generate-registry";

describe("generate-registry", () => {
  it("builds dashboard-local plugin page imports", () => {
    const registries = buildHubRegistries(
      [
        {
          hubId: "workspace",
          slug: "memory",
          sourceDir: "/repo/apps/dashboard/features/pages/workspace/memory",
        },
      ],
      { workspace: "/workspace/memory" },
      "/repo/apps/dashboard/app",
      "/repo",
    );

    expect(registries).toEqual([
      {
        hubId: "workspace",
        defaultPath: "/workspace/memory",
        entries: [
          {
            slug: "memory",
            importPath: "@/features/pages/workspace/memory/page",
          },
        ],
      },
    ]);
  });

  it("builds nested memory subpage imports", () => {
    const registries = buildHubRegistries(
      [
        {
          hubId: "workspace",
          slug: "daily-logs",
          sourceDir: "/repo/apps/dashboard/features/pages/workspace/daily-logs",
        },
        {
          hubId: "workspace",
          slug: "settings",
          sourceDir: "/repo/apps/dashboard/features/pages/workspace/settings",
        },
        {
          hubId: "workspace",
          slug: "profile",
          sourceDir: "/repo/apps/dashboard/features/pages/workspace/profile",
        },
      ],
      { workspace: "/workspace/memory" },
      "/repo/apps/dashboard/app",
      "/repo",
    );

    expect(registries).toEqual([
      {
        hubId: "workspace",
        defaultPath: "/workspace/memory",
        entries: [
          {
            slug: "daily-logs",
            importPath: "@/features/pages/workspace/daily-logs/page",
          },
          {
            slug: "profile",
            importPath: "@/features/pages/workspace/profile/page",
          },
          {
            slug: "settings",
            importPath: "@/features/pages/workspace/settings/page",
          },
        ],
      },
    ]);
  });

  it("builds flat workspace sibling page imports", () => {
    const registries = buildHubRegistries(
      [
        {
          hubId: "workspace",
          slug: "agents",
          sourceDir: "/repo/apps/dashboard/features/pages/workspace/agents",
        },
        {
          hubId: "workspace",
          slug: "harness",
          sourceDir: "/repo/apps/dashboard/features/pages/workspace/harness",
        },
      ],
      { workspace: "/workspace/memory" },
      "/repo/apps/dashboard/app",
      "/repo",
    );

    expect(registries).toEqual([
      {
        hubId: "workspace",
        defaultPath: "/workspace/memory",
        entries: [
          {
            slug: "agents",
            importPath: "@/features/pages/workspace/agents/page",
          },
          {
            slug: "harness",
            importPath: "@/features/pages/workspace/harness/page",
          },
        ],
      },
    ]);
  });

  it("collects declared flat feature pages from non-skill folders", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-convention-pages-"));
    const hubDir = path.join(
      repoRoot,
      "apps",
      "dashboard",
      "features",
      "pages",
      "workspace",
    );

    await fs.mkdir(path.join(hubDir, "memory"), { recursive: true });
    await fs.writeFile(
      path.join(hubDir, "memory", "page.tsx"),
      "export default function Page() { return null; }",
      "utf8",
    );

    const entries = await collectConventionPages(
      hubDir,
      "workspace",
      new Set(),
      new Set(["knowledge"]),
      new Map([["memory", "knowledge"]]),
    );

    expect(entries).toHaveLength(1);
    expect(entries[0]).toMatchObject({
      hubId: "workspace",
      slug: "memory",
      sourceDir: path.join(hubDir, "memory"),
    });

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("renders the workspace overview for empty slug and 404s unknown slugs", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-generate-registry-"));
    const appDir = path.join(repoRoot, "apps", "dashboard", "app");

    await generateRegistries(appDir, [
      {
        hubId: "workspace",
        defaultPath: "/workspace/memory",
        entries: [
          {
            slug: "memory",
            importPath: "@/features/pages/workspace/memory/page",
          },
        ],
      },
    ]);

    const pagePath = path.join(
      appDir,
      "workspace",
      "[[...slug]]",
      "page.tsx",
    );
    const content = await fs.readFile(pagePath, "utf8");

    expect(content).toContain("const { slug } = await props.params;");
    expect(content).toContain("const path = slug?.join('/') ?? '';");
    expect(content).toContain("import { BrainOverviewHome } from '@/features/pages/workspace/overview/BrainOverviewHome';");
    expect(content).toContain("if (!path) {");
    expect(content).toContain("return <BrainOverviewHome />;");
    expect(content).toContain("const page = renderDynamicPage(path);");
    expect(content).toContain("notFound();");

    // Hub root page.tsx is NOT generated — the optional catch-all handles /{hub}
    const hubIndexPath = path.join(appDir, "workspace", "page.tsx");
    await expect(fs.stat(hubIndexPath)).rejects.toThrow();

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("does not import the workspace overview from non-workspace catch-all pages", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-generate-registry-"));
    const appDir = path.join(repoRoot, "apps", "dashboard", "app");

    await generateRegistries(appDir, [
      {
        hubId: "studio",
        defaultPath: "/studio/vault",
        entries: [
          {
            slug: "vault",
            importPath: "@/lib/configs/studio-vault",
          },
        ],
      },
    ]);

    const pagePath = path.join(
      appDir,
      "studio",
      "[[...slug]]",
      "page.tsx",
    );
    const content = await fs.readFile(pagePath, "utf8");

    expect(content).not.toContain("BrainOverviewHome");
    expect(content).not.toContain("@/features/pages/workspace/overview/BrainOverviewHome");
    expect(content).toContain("if (!path) {");
    expect(content).toContain("notFound();");

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("removes stale hub catch-all directories that no longer have registry entries", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-stale-registry-"));
    const appDir = path.join(repoRoot, "apps", "dashboard", "app");
    const staleDir = path.join(appDir, "system", "[[...slug]]");

    await fs.mkdir(staleDir, { recursive: true });
    await fs.writeFile(
      path.join(staleDir, "registry.ts"),
      "export const PAGES = { 'auto-dir-alignment': () => import('@/lib/configs/system-auto-dir-alignment') };",
      "utf8",
    );
    await fs.writeFile(path.join(staleDir, "page.tsx"), "export default function Page() { return null; }", "utf8");

    await generateRegistries(appDir, [
      {
        hubId: "workspace",
        defaultPath: "/workspace/memory",
        entries: [
          {
            slug: "memory",
            importPath: "@/features/pages/workspace/memory/page",
          },
        ],
      },
    ]);

    await expect(fs.stat(staleDir)).rejects.toThrow();

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("removes stale generated hub root files for hubs that are no longer assembled", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-stale-hub-root-"));
    const appDir = path.join(repoRoot, "apps", "dashboard", "app");
    const hubDir = path.join(appDir, "studio");
    const nextTypesDir = path.join(
      repoRoot,
      "apps",
      "dashboard",
      ".next",
      "dev",
      "types",
      "app",
      "studio",
    );

    await fs.mkdir(hubDir, { recursive: true });
    await fs.mkdir(nextTypesDir, { recursive: true });
    await fs.writeFile(
      path.join(hubDir, "page.tsx"),
      `export default function FallbackHubRootPage() {
  return <div>Fallback empty hub</div>;
}
`,
      "utf8",
    );
    await fs.writeFile(
      path.join(hubDir, "layout.tsx"),
      `/**
 * AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
 */
import { HubTabNav } from '@/components/plugin/HubTabNav';

export default function HubLayout({ children }: { children: React.ReactNode }) {
  return <div><HubTabNav hubId="studio" />{children}</div>;
}
`,
      "utf8",
    );
    await fs.writeFile(path.join(nextTypesDir, "page.ts"), "export {};", "utf8");

    await generateRegistries(appDir, [], []);

    await expect(fs.stat(path.join(hubDir, "page.tsx"))).rejects.toThrow();
    await expect(fs.stat(path.join(hubDir, "layout.tsx"))).rejects.toThrow();
    await expect(fs.stat(nextTypesDir)).rejects.toThrow();

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("creates overview root pages for assembled hubs without page entries", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-empty-hub-registry-"));
    const appDir = path.join(repoRoot, "apps", "dashboard", "app");

    await generateRegistries(appDir, [], ["life"]);

    const pagePath = path.join(appDir, "life", "page.tsx");
    const pageContent = await fs.readFile(pagePath, "utf8");

    expect(pageContent).toContain("import { notFound } from 'next/navigation';");
    expect(pageContent).toContain("export default function FallbackHubRootPage() {");
    expect(pageContent).toContain("notFound();");
    expect(pageContent).not.toContain("HubOverviewPage");
    await expect(
      fs.stat(path.join(appDir, "life", "[[...slug]]")),
    ).rejects.toThrow();

    await fs.rm(repoRoot, { recursive: true, force: true });
  });

  it("does not generate routes for hubs that were not assembled", async () => {
    const repoRoot = await fs.mkdtemp(path.join(os.tmpdir(), "augur-missing-hub-registry-"));
    const appDir = path.join(repoRoot, "apps", "dashboard", "app");

    await generateRegistries(appDir, [], []);

    await expect(
      fs.stat(path.join(appDir, "studio", "page.tsx")),
    ).rejects.toThrow();

    await fs.rm(repoRoot, { recursive: true, force: true });
  });
});
