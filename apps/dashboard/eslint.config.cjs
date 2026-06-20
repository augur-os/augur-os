const nextCoreWebVitals = require("eslint-config-next/core-web-vitals");
const nextTypescript = require("eslint-config-next/typescript");
const unusedImports = require("eslint-plugin-unused-imports");

module.exports = [
  {
    ignores: ["scripts/dist/**", "node_modules.bak*/**"],
  },
  ...nextCoreWebVitals,
  ...nextTypescript,
  {
    plugins: {
      "unused-imports": unusedImports,
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-require-imports": "off",
      "unused-imports/no-unused-imports": "error",
      "unused-imports/no-unused-vars": "off",
    },
  },
  // ADR-453: Block direct fs access in API routes (CLAUDE.md rule #11)
  // ADR-466: Block subprocess execution in API routes (CLAUDE.md rule #11)
  {
    files: ["**/api/**/route.ts"],
    rules: {
      "no-restricted-imports": ["error", {
        paths: [
          { name: "fs", message: "Use MCP tools instead of direct fs access in API routes (CLAUDE.md rule #11). Use @fs-exempt marker for legitimate exceptions." },
          { name: "fs/promises", message: "Use MCP tools instead of direct fs access in API routes (CLAUDE.md rule #11)." },
          { name: "node:fs", message: "Use MCP tools instead of direct fs access in API routes (CLAUDE.md rule #11)." },
          { name: "node:fs/promises", message: "Use MCP tools instead of direct fs access in API routes (CLAUDE.md rule #11)." },
          { name: "child_process", message: "API routes must not spawn subprocesses. Use MCP tools instead (CLAUDE.md rule #11). Add // @spawn-exempt: <reason> for legitimate exceptions (ADR-466)." },
          { name: "node:child_process", message: "API routes must not spawn subprocesses. Use MCP tools instead (CLAUDE.md rule #11). Add // @spawn-exempt: <reason> for legitimate exceptions (ADR-466)." },
          { name: "node-pty", message: "API routes must not use PTY. Use MCP tools instead (CLAUDE.md rule #11). Add // @spawn-exempt: <reason> for legitimate exceptions (ADR-466)." },
        ]
      }]
    }
  },
  // ADR-490: Enforce @/ (framework) never imports @/features/ directly.
  // Only framework code is checked — generated registries are excluded.
  {
    files: ["components/**/*.ts", "components/**/*.tsx", "lib/**/*.ts", "lib/**/*.tsx", "hooks/**/*.ts", "hooks/**/*.tsx"],
    ignores: ["**/generated-*", "**/lib/configs/**"],
    rules: {
      "no-restricted-imports": ["error", {
        patterns: [{
          group: ["@/features/*"],
          message: "Framework code (@/) must not import from @/features/. Move the consumer into features/, or extract a framework-safe primitive into @/. (ADR-490)"
        }]
      }]
    }
  },
];
