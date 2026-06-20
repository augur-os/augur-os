import Image from "next/image";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { useMemo } from "react";

import { prepareMarkdown } from "@/components/markdown-utils";
import type { Components } from "react-markdown";

const passthroughImageLoader = ({ src }: { src: string }) => src;

function resolveRelativePath(basePath: string, relativePath: string): string {
  if (
    relativePath.startsWith("http") ||
    relativePath.startsWith("/") ||
    relativePath.startsWith("#") ||
    relativePath.startsWith("data:")
  ) {
    return relativePath;
  }

  const baseParts = basePath.split("/").filter(Boolean);
  if (baseParts.length > 0 && baseParts[baseParts.length - 1].includes(".")) {
    baseParts.pop();
  }

  const relParts = relativePath.split("/");
  for (const part of relParts) {
    if (part === ".") continue;
    if (part === "..") {
      if (baseParts.length > 0) baseParts.pop();
    } else {
      baseParts.push(part);
    }
  }

  return baseParts.join("/");
}

const staticComponents: Partial<Components> = {
  h1: ({ children, ...props }) => (
    <h1
      className="text-2xl font-semibold text-[var(--text-primary)] mt-2 mb-4 leading-tight"
      {...props}
    >
      {children}
    </h1>
  ),
  h2: ({ children, ...props }) => (
    <h2
      className="text-xl font-semibold text-[var(--text-primary)] mt-8 mb-3"
      {...props}
    >
      {children}
    </h2>
  ),
  h3: ({ children, ...props }) => (
    <h3
      className="text-lg font-semibold text-[var(--text-primary)] mt-6 mb-2"
      {...props}
    >
      {children}
    </h3>
  ),
  h4: ({ children, ...props }) => (
    <h4
      className="text-base font-semibold text-[var(--text-primary)] mt-5 mb-2"
      {...props}
    >
      {children}
    </h4>
  ),
  p: ({ children, ...props }) => (
    <p className="text-[var(--text-secondary)] leading-relaxed my-3" {...props}>
      {children}
    </p>
  ),
  ul: ({ children, ...props }) => (
    <ul
      className="list-disc pl-6 space-y-1 my-3 text-[var(--text-secondary)]"
      {...props}
    >
      {children}
    </ul>
  ),
  ol: ({ children, ...props }) => (
    <ol
      className="list-decimal pl-6 space-y-1 my-3 text-[var(--text-secondary)]"
      {...props}
    >
      {children}
    </ol>
  ),
  li: ({ children, ...props }) => (
    <li className="leading-relaxed" {...props}>
      {children}
    </li>
  ),
  hr: (props) => (
    <hr className="border-[var(--border-color)] my-6" {...props} />
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border border-[var(--accent-primary)]/25 bg-[var(--bg-secondary)]/65 px-4 py-2 my-4 text-[var(--text-secondary)] rounded-md"
      {...props}
    >
      {children}
    </blockquote>
  ),
  code: ({ children, className, ...props }) => (
    <code
      className={`font-mono text-sm bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded px-1.5 py-0.5 ${
        className ?? ""
      }`}
      {...props}
    >
      {children}
    </code>
  ),
  pre: ({ children, ...props }) => (
    <pre
      className="overflow-x-auto rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-color)] p-4 my-4 text-[var(--text-secondary)] [&>code]:bg-transparent [&>code]:border-0 [&>code]:p-0"
      {...props}
    >
      {children}
    </pre>
  ),
  table: ({ children, ...props }) => (
    <div className="overflow-x-auto my-4">
      <table
        className="min-w-full text-sm border border-[var(--border-color)] rounded-lg overflow-hidden"
        {...props}
      >
        {children}
      </table>
    </div>
  ),
  thead: ({ children, ...props }) => (
    <thead
      className="bg-[var(--bg-secondary)] text-[var(--text-primary)]"
      {...props}
    >
      {children}
    </thead>
  ),
  tbody: ({ children, ...props }) => (
    <tbody className="divide-y divide-[var(--border-color)]" {...props}>
      {children}
    </tbody>
  ),
  tr: ({ children, ...props }) => (
    <tr className="hover:bg-[var(--bg-hover)] transition-colors" {...props}>
      {children}
    </tr>
  ),
  th: ({ children, ...props }) => (
    <th
      className="text-left font-semibold px-3 py-2 border-b border-[var(--border-color)]"
      {...props}
    >
      {children}
    </th>
  ),
  td: ({ children, ...props }) => (
    <td className="align-top px-3 py-2 text-[var(--text-secondary)]" {...props}>
      {children}
    </td>
  ),
};

export default function Markdown({
  markdown,
  basePath,
}: {
  markdown: string;
  basePath?: string;
}) {
  const components = useMemo<Components>(
    () => ({
      ...staticComponents,
      a: ({ children, href, ...props }) => {
        const isExternal =
          typeof href === "string" && /^https?:\/\//i.test(href);
        let finalHref = href;

        if (
          href &&
          typeof href === "string" &&
          !isExternal &&
          !href.startsWith("/") &&
          !href.startsWith("#") &&
          basePath
        ) {
          const resolved = resolveRelativePath(basePath, href);
          if (
            resolved.match(/\.(md|ts|tsx|py|js|jsx|yaml|yml|json|txt|sh)$/i)
          ) {
            finalHref = `/files?path=${encodeURIComponent(resolved)}`;
          } else {
            finalHref = `/api/files/raw?path=${encodeURIComponent(resolved)}`;
          }
        }

        return (
          <a
            href={finalHref}
            className="text-[var(--accent-info)] hover:opacity-80 hover:underline underline-offset-2"
            target={isExternal ? "_blank" : undefined}
            rel={isExternal ? "noreferrer" : undefined}
            {...props}
          >
            {children}
          </a>
        );
      },
      img: ({ src, alt }) => {
        let finalSrc = src;
        if (
          src &&
          typeof src === "string" &&
          !src.startsWith("http") &&
          !src.startsWith("/") &&
          !src.startsWith("data:") &&
          basePath
        ) {
          const resolved = resolveRelativePath(basePath, src);
          finalSrc = `/api/files/raw?path=${encodeURIComponent(resolved)}`;
        }
        if (typeof finalSrc !== "string" || !finalSrc) return null;
        return (
          <Image
            loader={passthroughImageLoader}
            src={finalSrc}
            alt={alt ?? ""}
            unoptimized
            width={1200}
            height={800}
            sizes="100vw"
            style={{ maxWidth: "100%", height: "auto" }}
            className="max-w-full h-auto rounded-lg my-4 border border-[var(--border-color)]"
          />
        );
      },
    }),
    [basePath],
  );

  const content = useMemo(() => prepareMarkdown(markdown), [markdown]);

  return (
    <div className="augur-markdown text-[var(--text-secondary)]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
