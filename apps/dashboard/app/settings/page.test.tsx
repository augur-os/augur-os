import Page from "./page";
import { redirect } from "next/navigation";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => "/",
  useSearchParams: () => ({ get: jest.fn() }),
}));

describe("Page", () => {
  beforeEach(() => {
    (redirect as jest.Mock).mockClear();
  });

  it("renders without crashing", async () => {
    const element = await Page({ searchParams: Promise.resolve({}) });
    expect(element).toBeTruthy();
  });

  it("redirects legacy skills tab to the consolidated Connections route", async () => {
    await Page({ searchParams: Promise.resolve({ tab: "skills" }) });
    expect(redirect).toHaveBeenCalledWith("/settings/integrations");
  });

  it("redirects legacy providers tab to the consolidated AI & Models route", async () => {
    await Page({ searchParams: Promise.resolve({ tab: "providers" }) });
    expect(redirect).toHaveBeenCalledWith("/settings/ai");
  });

  it("redirects legacy dispatch tab to the consolidated Connections route", async () => {
    await Page({ searchParams: Promise.resolve({ tab: "dispatch" }) });
    expect(redirect).toHaveBeenCalledWith("/settings/integrations");
  });

  it("does not redirect legacy integrations tab to browse integrations", async () => {
    const element = await Page({ searchParams: Promise.resolve({ tab: "integrations" }) });
    expect(element).toBeTruthy();
    expect(redirect).not.toHaveBeenCalledWith("/browse?category=integrations");
  });
});
