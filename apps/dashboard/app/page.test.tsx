import { describe, it, expect, jest } from "@jest/globals";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => "/",
  useSearchParams: () => ({ get: jest.fn() }),
}));

// Mock server-side calendar fetch to avoid spawning processes in tests
jest.mock("child_process", () => ({
  spawn: jest.fn(() => ({
    stdout: { on: jest.fn() },
    stderr: { on: jest.fn() },
    on: jest.fn((event: string, cb: (code: number) => void) => {
      if (event === "close") cb(0);
    }),
  })),
}));

describe("Page", () => {
  it("renders without crashing", async () => {
    // Import Page dynamically to ensure mocks are set up
    const Page = (await import("./page")).default;
    const element = await Page({ searchParams: Promise.resolve({}) });
    expect(element).toBeTruthy();
  });
});
