const fs = require("fs");
const path = require("path");
const glob = require("glob");

const APP_DIR = path.join(__dirname, "../app");

// Template for RSC (Async)
const rscTemplate = (importPath) => `
import Page from './page';

// Mock Next.js navigation
jest.mock('next/navigation', () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => '/',
  useSearchParams: () => ({ get: jest.fn() }),
}));

// Mock API calls if possible (generic)
global.fetch = jest.fn(() =>
  Promise.resolve({
    json: () => Promise.resolve({ success: true, data: [] }),
    ok: true,
  })
);

describe('Page (RSC)', () => {
  it('renders without crashing', async () => {
    const renderPage = Page as (props: { params: Record<string, never>; searchParams: Record<string, never> }) => unknown | Promise<unknown>;
    const result = await renderPage({ params: {}, searchParams: {} });
    expect(result).toBeDefined();
  });
});
`;

// Template for Client/Sync Component
const clientTemplate = (importPath) => `
import { render, screen } from '@testing-library/react';
import Page from './page';

// Mock Next.js navigation
jest.mock('next/navigation', () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => '/',
  useSearchParams: () => ({ get: jest.fn() }),
}));

describe('Page', () => {
  it('renders without crashing', () => {
    render(<Page params={{}} searchParams={{}} />);
    expect(true).toBeTruthy();
  });
});
`;

function generateTests() {
  const pageFiles = glob.sync("**/page.tsx", { cwd: APP_DIR });

  console.log(`Found ${pageFiles.length} page.tsx files.`);
  let createdCount = 0;

  pageFiles.forEach((relPath) => {
    const absPath = path.join(APP_DIR, relPath);
    const dir = path.dirname(absPath);
    const testPath = path.join(dir, "page.test.tsx");

    if (fs.existsSync(testPath)) {
      // console.log(\`Skipping \${relPath}, test exists.\`);
      return;
    }

    const content = fs.readFileSync(absPath, "utf8");
    const isAsync = content.includes("export default async function");
    const template = isAsync ? rscTemplate : clientTemplate;

    fs.writeFileSync(testPath, template(relPath).trim());
    console.log(`Created test for ${relPath}`);
    createdCount++;
  });

  console.log(`\nSummary: Created ${createdCount} new test files.`);
}

generateTests();
