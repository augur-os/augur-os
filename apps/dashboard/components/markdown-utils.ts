function cleanMarkdown(markdown: string): string {
  const withoutFrontmatter = markdown.replace(
    /^\s*---\r?\n[\s\S]*?\r?\n---\r?\n?/,
    "",
  );
  return withoutFrontmatter.replace(/<!--[\s\S]*?-->/g, "").trimStart();
}

function normalizeCallouts(markdown: string): string {
  return markdown.replace(
    /^>\s*\[!(\w+)\]\s*(.*)$/gm,
    (_match, kind: string, title: string) => {
      const label = kind.charAt(0).toUpperCase() + kind.slice(1).toLowerCase();
      const suffix = title?.trim() ? `: ${title.trim()}` : "";
      return `> **${label}${suffix}**`;
    },
  );
}

function normalizeWikiLinks(markdown: string): string {
  return markdown.replace(
    /\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
    (_match, target: string, label?: string) => {
      const text = (label || target).trim();
      const slug = target
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
      return `[${text}](#wiki-${slug})`;
    },
  );
}

export function prepareMarkdown(markdown: string): string {
  return normalizeWikiLinks(normalizeCallouts(cleanMarkdown(markdown)));
}
