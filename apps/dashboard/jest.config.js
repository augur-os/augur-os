const os = require("os");
const path = require("path");
const nextJest = require("next/jest");

function expandHome(input) {
  if (!input) return input;
  if (input === "~") return os.homedir();
  if (input.startsWith("~/")) return path.join(os.homedir(), input.slice(2));
  return input;
}

function resolveStateDir() {
  const stateEnv =
    process.env.AUGUR_STATE ||
    process.env.AUGUR_RUNTIME ||
    process.env.AUGUR_RUNTIME_DIR;

  if (stateEnv && stateEnv.trim()) {
    return path.resolve(expandHome(stateEnv.trim()));
  }

  if (process.platform === "darwin") {
    return path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Augur",
      "state",
    );
  }
  if (process.platform === "win32") {
    return path.join(
      process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"),
      "Augur",
      "state",
    );
  }

  const xdgStateHome =
    process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state");
  return path.join(xdgStateHome, "augur");
}

const createJestConfig = nextJest({
  // Provide the path to your Next.js app to load next.config.js and .env files in your test environment
  dir: "./",
});

// Add any custom config to be passed to Jest
const customJestConfig = {
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  testEnvironment: "jest-environment-jsdom",
  // Output coverage to runtime directory (not in source tree)
  coverageDirectory: path.join(resolveStateDir(), "coverage"),
  coverageReporters: ["json", "lcov", "text", "clover", "json-summary"],
  coverageThreshold: {
    global: {
      statements: 60,
      branches: 50,
      functions: 65,
      lines: 60,
    },
  },
  // Tests unified under root tests/ directory
  roots: ["<rootDir>/../../tests/dashboard"],
  // Ensure tests in tests/dashboard/ can resolve modules from the dashboard's node_modules
  moduleDirectories: ["node_modules", "<rootDir>/node_modules"],
  moduleNameMapper: {
    // Auto-wrap @testing-library/react render() in a QueryClientProvider so
    // components using React Query hooks (useMcpQuery / useMcpPoll) render in tests.
    "^@testing-library/react$":
      "<rootDir>/../../tests/dashboard/__mocks__/testing-library-react.tsx",
    // Handle module aliases (this will be automatically configured for you soon)
    "^@/(.*)$": "<rootDir>/$1",
    "react-markdown":
      "<rootDir>/../../tests/dashboard/__mocks__/react-markdown.tsx",
    "remark-gfm":
      "<rootDir>/../../tests/dashboard/__mocks__/react-markdown.tsx", // Mock remark-gfm too if needed to same stub
    "rehype-highlight":
      "<rootDir>/../../tests/dashboard/__mocks__/rehype-highlight.tsx",
  },
  transformIgnorePatterns: [
    "node_modules/(?!(react-markdown|rehype-highlight|rehype|remark|unist|vfile|unified|micromark|devlop|estree|mdast|hast|property|space|comma|ccount|decode|character|bail|is-plain|trough|trim|github-slugger|clsx)/)",
  ],
  testPathIgnorePatterns: ["/node_modules/", "/visual/"],
};

// createJestConfig is exported this way to ensure that next/jest can load the Next.js config which is async
module.exports = createJestConfig(customJestConfig);
