#!/usr/bin/env node
/**
 * Dynamic broken link scanner for all dashboard pages.
 *
 * Discovery strategy (zero hardcoding):
 *   1. Walk apps/dashboard/app/ for page.tsx to find ALL routes
 *   2. Convert file paths to URL routes
 *   3. Fetch each page, extract <a href> links
 *   4. Deduplicate and batch-test all unique internal links
 *   5. Output JSON report for the ops module
 *
 * Usage:
 *   node skills/routine-codebase/scripts/check_links.mjs [--json]
 */

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
function resolveProjectRoot() {
  if (process.env.AUTO_TEST_LINKS_PROJECT_ROOT) {
    return path.resolve(process.env.AUTO_TEST_LINKS_PROJECT_ROOT);
  }

  let current = __dirname;
  while (true) {
    if (fs.existsSync(path.join(current, "apps", "dashboard", "app"))) {
      return current;
    }
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }

  return path.resolve(__dirname, "../../../..");
}

const PROJECT_ROOT = resolveProjectRoot();
const APP_DIR = path.join(PROJECT_ROOT, "apps/dashboard/app");
const BASE = process.env.BASE_URL || "http://localhost:3000";
const TIMEOUT = parseInt(process.env.REQUEST_TIMEOUT || "8000", 10);
const LINK_BATCH_SIZE = parseInt(process.env.LINK_BATCH_SIZE || "4", 10);
const JSON_MODE = process.argv.includes("--json");

if (process.argv.includes("--print-project-root")) {
  console.log(PROJECT_ROOT);
  process.exit(0);
}

// --- 1. Discover all page routes from filesystem ---

async function* walkDir(dir) {
  const entries = await fs.promises.readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      yield* walkDir(full);
    } else if (entry.name === "page.tsx") {
      yield full;
    }
  }
}

async function discoverRoutes() {
  const routes = [];

  for await (const entry of walkDir(APP_DIR)) {
    const rel = path.relative(APP_DIR, entry);
    const segments = rel.split(path.sep);

    // Remove "page.tsx" from end
    segments.pop();

    // Skip api routes, special Next.js dirs, and route groups (parenthesized)
    if (segments.some((s) => s === "api" || s.startsWith("_") || s.startsWith("("))) continue;

    // Build route
    const route = "/" + segments.join("/");

    // Skip dynamic routes (contain [param]) — can't test without real params
    if (route.includes("[")) continue;

    // Skip root
    if (route === "/") continue;

    routes.push(route);
  }

  return routes.sort();
}

// --- 2. Extract internal links from HTML ---

function extractLinks(html) {
  const hrefs = new Set();
  const re = /href="([^"]+)"/g;
  let m;
  while ((m = re.exec(html)) !== null) {
    const href = m[1];
    if (
      href.startsWith("/") &&
      !href.startsWith("//") &&
      !href.startsWith("/#") &&
      !href.startsWith("/api/") &&
      !href.startsWith("/_next/")
    ) {
      const clean = href.split("?")[0].split("#")[0];
      if (clean && clean !== "/") hrefs.add(clean);
    }
  }
  return [...hrefs];
}

// --- 3. Test a URL ---

async function requestStatus(url, method, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(BASE + url, {
      method,
      redirect: "follow",
      signal: controller.signal,
    });
    clearTimeout(timer);
    return resp.status;
  } catch (e) {
    clearTimeout(timer);
    if (e.name === "AbortError") return "TIMEOUT";
    return "ERR";
  }
}

async function testUrl(url) {
  // HEAD is cheap when supported, but cold Next app routes can legitimately
  // time out on first compile. Treat HEAD timeout as inconclusive and retry
  // with GET before calling the link broken.
  const headStatus = await requestStatus(url, "HEAD", TIMEOUT);
  if (headStatus === 200) return 200;
  if (headStatus !== "TIMEOUT" && headStatus !== "ERR" && headStatus !== 405) {
    return headStatus;
  }

  const getTimeout = Math.max(TIMEOUT * 2, 15000);
  for (let attempt = 0; attempt < 2; attempt++) {
    const getStatus = await requestStatus(url, "GET", getTimeout);
    if (getStatus === 200) return 200;
    if (getStatus !== "TIMEOUT" && getStatus !== "ERR") {
      return getStatus;
    }
    if (attempt === 0) {
      await new Promise((r) => setTimeout(r, 500));
    }
  }

  return headStatus === "TIMEOUT" ? "TIMEOUT" : "ERR";
}

// --- 4. Main ---

async function main() {
  const routes = await discoverRoutes();
  if (!JSON_MODE) console.log(`Discovered ${routes.length} page routes\n`);

  const pageResults = [];
  const allLinks = new Set();

  for (const route of routes) {
    if (!JSON_MODE) process.stdout.write(`  ${route}...`);
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), TIMEOUT);
      const resp = await fetch(BASE + route, { signal: controller.signal });
      clearTimeout(timer);

      if (!resp.ok) {
        if (!JSON_MODE) console.log(` ${resp.status}`);
        pageResults.push({ route, status: resp.status, links: [], broken: [] });
        continue;
      }
      const html = await resp.text();
      const links = extractLinks(html);
      links.forEach((l) => allLinks.add(l));
      pageResults.push({ route, status: 200, links, broken: [] });
      if (!JSON_MODE) console.log(` ${links.length} links`);
    } catch (e) {
      // Retry once for transient Turbopack compilation failures
      try {
        await new Promise((r) => setTimeout(r, 500));
        const retryCtrl = new AbortController();
        const retryTimer = setTimeout(() => retryCtrl.abort(), TIMEOUT);
        const retryResp = await fetch(BASE + route, { signal: retryCtrl.signal });
        clearTimeout(retryTimer);
        if (retryResp.ok) {
          const html = await retryResp.text();
          const links = extractLinks(html);
          links.forEach((l) => allLinks.add(l));
          pageResults.push({ route, status: 200, links, broken: [] });
          if (!JSON_MODE) console.log(` 200 (retry)`);
          continue;
        }
        if (!JSON_MODE) console.log(` ${retryResp.status} (retry)`);
        pageResults.push({ route, status: retryResp.status, links: [], broken: [] });
      } catch {
        if (!JSON_MODE) console.log(` ERR`);
        pageResults.push({ route, status: "ERR", links: [], broken: [] });
      }
    }
  }

  // Test all unique links in parallel batches
  if (!JSON_MODE) console.log(`\nTesting ${allLinks.size} unique links...\n`);
  const linkStatus = new Map();
  const batch = [...allLinks];

  for (let i = 0; i < batch.length; i += LINK_BATCH_SIZE) {
    const chunk = batch.slice(i, i + LINK_BATCH_SIZE);
    const results = await Promise.all(
      chunk.map(async (url) => [url, await testUrl(url)])
    );
    for (const [url, s] of results) linkStatus.set(url, s);
    if (!JSON_MODE)
      process.stdout.write(
        `  ${Math.min(i + LINK_BATCH_SIZE, batch.length)}/${batch.length}\r`
      );
  }
  if (!JSON_MODE) console.log();

  // Map broken links back to pages
  for (const page of pageResults) {
    if (page.status !== 200) continue;
    for (const link of page.links) {
      const s = linkStatus.get(link);
      if (s !== 200) {
        page.broken.push({ link, status: s });
      }
    }
  }

  // Build report
  const totalLinks = pageResults.reduce((n, p) => n + p.links.length, 0);
  const totalBroken = pageResults.reduce((n, p) => n + p.broken.length, 0);
  const unreachablePages = pageResults.filter((p) => p.status !== 200).length;
  const brokenPages = pageResults.filter(
    (p) => p.status !== 200 || p.broken.length > 0
  );

  const uniqueBroken = new Map();
  for (const p of pageResults) {
    for (const b of p.broken) {
      if (!uniqueBroken.has(b.link)) uniqueBroken.set(b.link, b.status);
    }
  }

  const report = {
    summary: {
      pages_scanned: routes.length,
      pages_unreachable: unreachablePages,
      total_links: totalLinks,
      unique_links: allLinks.size,
      broken_links: totalBroken,
      unique_broken: uniqueBroken.size,
      broken_pct:
        totalLinks > 0
          ? parseFloat(((totalBroken / totalLinks) * 100).toFixed(1))
          : 0,
      pages_with_issues: brokenPages.length,
    },
    unreachable_pages: pageResults
      .filter((p) => p.status !== 200)
      .map((p) => ({ route: p.route, status: p.status })),
    unique_broken_links: [...uniqueBroken]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([link, status]) => ({ link, status })),
    broken_by_page: brokenPages
      .filter((p) => p.broken.length > 0)
      .map((p) => ({ route: p.route, broken: p.broken })),
  };

  if (JSON_MODE) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    console.log("=".repeat(70));
    console.log("BROKEN LINKS REPORT");
    console.log("=".repeat(70));
    console.log(`Pages scanned:     ${report.summary.pages_scanned}`);
    console.log(`Pages unreachable: ${report.summary.pages_unreachable}`);
    console.log(`Total links:       ${report.summary.total_links}`);
    console.log(`Unique links:      ${report.summary.unique_links}`);
    console.log(
      `Broken:            ${report.summary.broken_links} (${report.summary.broken_pct}%)`
    );
    console.log(`Pages with issues: ${report.summary.pages_with_issues}`);
    console.log("=".repeat(70));

    if (report.unreachable_pages.length > 0) {
      console.log("\nUNREACHABLE PAGES:");
      for (const p of report.unreachable_pages)
        console.log(`  ${p.status} ${p.route}`);
    }

    if (report.unique_broken_links.length > 0) {
      console.log(
        `\nUNIQUE BROKEN LINKS (${report.unique_broken_links.length}):`
      );
      for (const b of report.unique_broken_links)
        console.log(`  ${b.status} ${b.link}`);
    }

    if (report.broken_by_page.length > 0) {
      console.log("\nBROKEN BY PAGE:");
      for (const p of report.broken_by_page) {
        console.log(`\n  ${p.route}`);
        for (const b of p.broken) console.log(`    ${b.status} ${b.link}`);
      }
    }
  }

  process.exit(
    report.summary.broken_links > 0 || report.summary.pages_unreachable > 0
      ? 1
      : 0
  );
}

main().catch((e) => {
  console.error(e);
  process.exit(2);
});
