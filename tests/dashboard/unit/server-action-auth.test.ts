/**
 * @jest-environment node
 */

import { auth } from "@/lib/auth/server-action";
import { JWT_COOKIE_NAME, verifyToken } from "@/lib/auth/jwt";
import { cookies, headers } from "next/headers";

jest.mock("next/headers", () => ({
  cookies: jest.fn(),
  headers: jest.fn(),
}));

jest.mock("@/lib/auth/jwt", () => ({
  JWT_COOKIE_NAME: "augur-session",
  verifyToken: jest.fn(),
}));

const mockCookies = cookies as jest.MockedFunction<typeof cookies>;
const mockHeaders = headers as jest.MockedFunction<typeof headers>;
const mockVerifyToken = verifyToken as jest.MockedFunction<typeof verifyToken>;

function headerStore(values: Record<string, string | null>) {
  return {
    get: (name: string) => values[name.toLowerCase()] ?? null,
  };
}

function cookieStore(value?: string) {
  return {
    get: (name: string) =>
      name === JWT_COOKIE_NAME && value ? { name, value } : undefined,
  };
}

describe("server action auth", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("allows local dashboard calls as the dev user", async () => {
    mockHeaders.mockResolvedValue(headerStore({ "x-remote-user": null }) as any);
    mockCookies.mockResolvedValue(cookieStore() as any);

    await expect(auth()).resolves.toEqual({
      isRemote: false,
      role: "admin",
      scopes: ["*"],
      userId: "dev-user",
    });
    expect(mockVerifyToken).not.toHaveBeenCalled();
  });

  it("rejects remote calls without the dashboard JWT cookie", async () => {
    mockHeaders.mockResolvedValue(headerStore({ "x-remote-user": "true" }) as any);
    mockCookies.mockResolvedValue(cookieStore() as any);

    await expect(auth()).rejects.toThrow("Authentication required");
  });

  it("rejects remote calls with an invalid dashboard JWT", async () => {
    mockHeaders.mockResolvedValue(headerStore({ "x-remote-user": "true" }) as any);
    mockCookies.mockResolvedValue(cookieStore("bad-token") as any);
    mockVerifyToken.mockResolvedValue(null);

    await expect(auth()).rejects.toThrow("Invalid or expired token");
  });

  it("returns the verified remote session payload", async () => {
    mockHeaders.mockResolvedValue(headerStore({ "x-remote-user": "true" }) as any);
    mockCookies.mockResolvedValue(cookieStore("valid-token") as any);
    mockVerifyToken.mockResolvedValue({
      userId: "remote-user",
      role: "admin",
      scopes: ["files:read"],
    } as any);

    await expect(auth()).resolves.toEqual({
      isRemote: true,
      role: "admin",
      scopes: ["files:read"],
      userId: "remote-user",
    });
    expect(mockVerifyToken).toHaveBeenCalledWith("valid-token");
  });
});
