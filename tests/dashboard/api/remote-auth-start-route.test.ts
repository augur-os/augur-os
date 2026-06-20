/**
 * @jest-environment node
 */

import { GET, POST } from "@/app/api/remote/auth/start/[provider]/route";

jest.mock("@/lib/remote/oauth", () => ({
  generateCodeVerifier: jest.fn(() => "mock-verifier"),
  generateCodeChallenge: jest.fn(async () => "mock-challenge"),
  generateState: jest.fn(() => "mock-state"),
  buildAuthorizationUrl: jest.fn(() => "https://provider.example/authorize"),
}));

describe("POST /api/remote/auth/start/[provider]", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("normalizes settings provider referer to canonical settings return URL", async () => {
    const request = new Request(
      "http://localhost:3000/api/remote/auth/start/glama",
      {
        method: "POST",
        headers: { referer: "http://localhost:3000/settings/providers" },
      },
    );

    const response = await POST(request, { params: Promise.resolve({ provider: "glama" }) });

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ url: "https://provider.example/authorize" });

    const setCookie = response.headers.get("set-cookie");
    expect(setCookie).toContain("oauth_session=");
    const encodedSession = setCookie?.match(/oauth_session=([^;]+)/)?.[1];
    expect(encodedSession).toBeTruthy();
    const session = JSON.parse(decodeURIComponent(encodedSession ?? "")) as { returnUrl?: string };
    expect(session.returnUrl).toBe("/settings/providers");
  });

  it("rejects cross-origin POST requests before creating an oauth session", async () => {
    const request = new Request(
      "http://localhost:3000/api/remote/auth/start/glama",
      {
        method: "POST",
        headers: { origin: "https://attacker.example" },
      },
    );

    const response = await POST(request, { params: Promise.resolve({ provider: "glama" }) });

    expect(response.status).toBe(403);
    await expect(response.json()).resolves.toEqual({ error: "Invalid request origin" });
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("does not start oauth from GET", async () => {
    const response = GET();

    expect(response.status).toBe(405);
    expect(response.headers.get("allow")).toBe("POST");
  });
});
