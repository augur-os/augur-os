import type { BrowseItem } from "./types";

// Tests
export function transformTests(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
    test_type: string;
  }[],
): BrowseItem[] {
  return items.map((t) => ({
    id: t.id,
    title: t.title,
    description: t.description,
    icon: "FlaskConical",
    typeBadge: t.test_type,
    path: t.path,
    primaryAction: {
      label: "Run Test",
      type: "run-action",
      target: `Run test: ${t.path}`,
    },
    actions: [
      { id: `reveal-${t.id}`, label: "Reveal", icon: "FolderOpen", type: "open-file" as const, target: t.path },
    ],
  }));
}

// API Routes
export function transformApiRoutes(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
    methods: string[];
  }[],
): BrowseItem[] {
  return items.map((r) => {
    const methodStr = r.methods.join(", ");
    const desc = r.description || `${methodStr} endpoint · ${r.path.replace(/^.*?\/api\//, "/api/")}`;
    return {
      id: r.id,
      title: r.title,
      description: desc,
      icon: "Route",
      typeBadge: methodStr,
      path: r.path,
      primaryAction: {
        label: "Test Route",
        type: "run-action",
        target: `Test API route ${methodStr} ${r.path}`,
      },
      actions: [
        { id: `reveal-${r.id}`, label: "Reveal", icon: "FolderOpen", type: "open-file" as const, target: r.path },
      ],
    };
  });
}

// Scripts
export function transformScripts(
  items: {
    id: string;
    title: string;
    description: string;
    hub: string;
    path: string;
    language: string;
  }[],
): BrowseItem[] {
  return items.map((s) => ({
    id: s.id,
    title: s.title,
    description: s.description,
    icon: "Terminal",
    typeBadge: s.language,
    path: s.path,
    primaryAction: {
      label: "Run Script",
      type: "run-mcp",
      target: `Run script: ${s.path}`,
    },
  }));
}
