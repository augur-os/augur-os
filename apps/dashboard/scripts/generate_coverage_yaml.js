const fs = require("fs");
const path = require("path");

const coveragePath = path.resolve(__dirname, "../coverage/report.json");
/**
 * Discover the repository root by looking for data/, src/, or .git/
 */
function discoverRepoRoot(startDir) {
  let current = path.resolve(startDir);
  while (current !== path.parse(current).root) {
    if (
      fs.existsSync(path.join(current, "data")) ||
      fs.existsSync(path.join(current, "src")) ||
      fs.existsSync(path.join(current, ".git"))
    ) {
      return current;
    }
    current = path.dirname(current);
  }
  // Fallback to 3 levels up from scripts/
  return path.resolve(__dirname, "..", "..", "..");
}

const repoRoot = discoverRepoRoot(__dirname);
const dataDir = process.env.AUGUR_ROOT || repoRoot;
const outputPath = path.join(
  dataDir,
  "plugins",
  "crew",
  "analyst",
  "actions",
  "coverage-metrics.yaml",
);

if (!fs.existsSync(coveragePath)) {
  console.error("Coverage report not found at " + coveragePath);
  process.exit(1);
}

const report = JSON.parse(fs.readFileSync(coveragePath, "utf8"));
const metrics = {};

report.testResults.forEach((result) => {
  const filePath = result.name;
  let pageName = path.basename(filePath);

  // Attempt to map to a more readable name
  if (filePath.includes("/app/")) {
    const parts = filePath.split("/app/")[1].split("/");
    pageName =
      parts.slice(0, -1).join("/") +
      "/" +
      parts[parts.length - 1].replace(".test.tsx", "").replace(".test.ts", "");
  } else if (filePath.includes("/components/")) {
    pageName = "Component: " + path.basename(filePath).replace(".test.tsx", "");
  } else if (filePath.includes("/tests/api/")) {
    pageName = "API: " + path.basename(filePath).replace(".test.ts", "");
  }

  const testCount = result.assertionResults.length;

  if (!metrics[pageName]) {
    metrics[pageName] = { tests: 0, status: "passing" };
  }
  metrics[pageName].tests += testCount;
  if (result.status !== "passed") {
    metrics[pageName].status = "failed";
  }
});

const yamlLines = ["page_coverage:"];
for (const [page, data] of Object.entries(metrics)) {
  yamlLines.push(`  - name: "${page}"`);
  yamlLines.push(`    test_count: ${data.tests}`);
  yamlLines.push(`    status: "${data.status}"`);
}

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, yamlLines.join("\n"));
console.log(`Generated coverage metrics at ${outputPath}`);
