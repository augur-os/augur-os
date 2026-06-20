/**
 * @jest-environment node
 *
 * Tests for Permissions Status API Route
 */

import { describe, it, expect, beforeEach, afterEach } from "@jest/globals";
import { GET } from "@/app/api/permissions/status/route";

// Store original platform
const originalPlatform = process.platform;

// Helper to call the API
const callApi = async (): Promise<Response> => {
  const request = new Request("http://localhost:3000/api/permissions/status");
  return GET(request);
};

// Mock spawn to avoid actual system calls
jest.mock("child_process", () => ({
  spawn: jest.fn((command: string, args: string[]) => {
    const mockProcess = {
      stdout: {
        on: jest.fn((event: string, callback: (data: string) => void) => {
          if (event === "data") {
            // Return mock responses based on command
            if (command === "osascript") {
              if (args.includes("AXIsProcessTrusted")) {
                setTimeout(() => callback("true"), 0);
              } else if (args.includes("AVCaptureDevice")) {
                setTimeout(() => callback("granted"), 0);
              } else if (args.includes("CGPreflightScreenCaptureAccess")) {
                setTimeout(() => callback("true"), 0);
              } else if (args.some((a) => a.includes("Notes"))) {
                setTimeout(() => callback("5"), 0);
              } else if (args.some((a) => a.includes("Mail"))) {
                setTimeout(() => callback("2"), 0);
              } else if (args.some((a) => a.includes("Calendar"))) {
                setTimeout(() => callback("3"), 0);
              }
            } else if (command === "which") {
              setTimeout(() => callback("/usr/local/bin/tesseract"), 0);
            } else if (command === "where") {
              // Windows tesseract check
              setTimeout(
                () =>
                  callback("C:\\Program Files\\Tesseract-OCR\\tesseract.exe"),
                0,
              ); // audit-ignore: Test mock
            } else if (command === "python3") {
              setTimeout(() => callback('{"events": []}'), 0);
            } else if (command === "powershell") {
              // Windows permission checks via PowerShell
              const script = args.find(
                (a) => a.includes("ConsentStore") || a.includes("ToastEnabled"),
              );
              if (script) {
                setTimeout(() => callback("granted"), 0);
              }
            }
          }
        }),
        setEncoding: jest.fn(),
      },
      stderr: {
        on: jest.fn(),
        setEncoding: jest.fn(),
      },
      on: jest.fn((event: string, callback: (code: number) => void) => {
        if (event === "close") {
          setTimeout(() => callback(0), 10);
        }
      }),
    };
    return mockProcess;
  }),
}));

// Mock fs for file checks
jest.mock("fs", () => ({
  existsSync: jest.fn((path: string) => {
    if (path.includes("calendar_service.py")) return true;
    if (path.includes("config.yaml")) return true;
    return false;
  }),
  readFileSync: jest.fn(() => "mock content"),
}));

describe("GET /api/permissions/status", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  afterEach(() => {
    // Restore platform
    Object.defineProperty(process, "platform", {
      value: originalPlatform,
    });
  });

  it("returns permissions array on macOS", async () => {
    // Set platform to darwin
    Object.defineProperty(process, "platform", {
      value: "darwin",
    });

    const response = await callApi();
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data.ok).toBe(true);
    expect(data.platform).toBe("darwin");
    expect(Array.isArray(data.permissions)).toBe(true);
  });

  it("returns empty permissions on unsupported platforms", async () => {
    // Set platform to linux
    Object.defineProperty(process, "platform", {
      value: "linux",
    });

    const response = await callApi();
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data.ok).toBe(true);
    expect(data.platform).toBe("linux");
    expect(data.permissions).toEqual([]);
    expect(data.message).toBe(
      "Permission checks are only available on macOS and Windows",
    );
  });

  it("includes all expected permission types on macOS", async () => {
    Object.defineProperty(process, "platform", {
      value: "darwin",
    });

    const response = await callApi();
    const data = await response.json();

    const permissionIds = data.permissions.map((p: { id: string }) => p.id);

    // Check all expected permissions are present
    expect(permissionIds).toContain("screen_recording");
    expect(permissionIds).toContain("microphone");
    expect(permissionIds).toContain("accessibility");
    expect(permissionIds).toContain("calendar");
    expect(permissionIds).toContain("apple_notes");
    expect(permissionIds).toContain("apple_mail");
    expect(permissionIds).toContain("email_imap");
    expect(permissionIds).toContain("tesseract");
  });

  it("includes Augur branding in instructions", async () => {
    Object.defineProperty(process, "platform", {
      value: "darwin",
    });

    const response = await callApi();
    const data = await response.json();

    // Check that instructions mention Augur
    const micPermission = data.permissions.find(
      (p: { id: string }) => p.id === "microphone",
    );
    expect(micPermission?.instructions).toContain("Augur");
  });

  it("categorizes permissions correctly", async () => {
    Object.defineProperty(process, "platform", {
      value: "darwin",
    });

    const response = await callApi();
    const data = await response.json();

    // Check categories
    const macosPerms = data.permissions.filter(
      (p: { category: string }) => p.category === "macos_system",
    );
    const emailPerms = data.permissions.filter(
      (p: { category: string }) => p.category === "email_calendar",
    );
    const depPerms = data.permissions.filter(
      (p: { category: string }) => p.category === "dependencies",
    );

    expect(macosPerms.length).toBeGreaterThan(0);
    expect(emailPerms.length).toBeGreaterThan(0);
    expect(depPerms.length).toBeGreaterThan(0);
  });

  it("has valid status values for all permissions", async () => {
    Object.defineProperty(process, "platform", {
      value: "darwin",
    });

    const response = await callApi();
    const data = await response.json();

    const validStatuses = ["granted", "denied", "unknown", "not_configured"];

    for (const permission of data.permissions) {
      expect(validStatuses).toContain(permission.status);
    }
  });

  // Windows-specific tests
  describe("Windows support", () => {
    it("returns permissions array on Windows", async () => {
      Object.defineProperty(process, "platform", {
        value: "win32",
      });

      const response = await callApi();
      expect(response.status).toBe(200);

      const data = await response.json();
      expect(data.ok).toBe(true);
      expect(data.platform).toBe("win32");
      expect(Array.isArray(data.permissions)).toBe(true);
    });

    it("includes Windows-specific permission types", async () => {
      Object.defineProperty(process, "platform", {
        value: "win32",
      });

      const response = await callApi();
      const data = await response.json();

      const permissionIds = data.permissions.map((p: { id: string }) => p.id);

      // Check Windows-specific permissions are present
      expect(permissionIds).toContain("microphone");
      expect(permissionIds).toContain("camera");
      expect(permissionIds).toContain("location");
      expect(permissionIds).toContain("calendar");
      expect(permissionIds).toContain("notifications");
    });

    it("categorizes Windows permissions correctly", async () => {
      Object.defineProperty(process, "platform", {
        value: "win32",
      });

      const response = await callApi();
      const data = await response.json();

      // Check categories
      const windowsPerms = data.permissions.filter(
        (p: { category: string }) => p.category === "windows_system",
      );
      const emailPerms = data.permissions.filter(
        (p: { category: string }) => p.category === "email_calendar",
      );
      const depPerms = data.permissions.filter(
        (p: { category: string }) => p.category === "dependencies",
      );

      expect(windowsPerms.length).toBeGreaterThan(0);
      expect(emailPerms.length).toBeGreaterThan(0);
      expect(depPerms.length).toBeGreaterThan(0);
    });

    it("includes Windows Settings instructions", async () => {
      Object.defineProperty(process, "platform", {
        value: "win32",
      });

      const response = await callApi();
      const data = await response.json();

      const micPermission = data.permissions.find(
        (p: { id: string }) => p.id === "microphone",
      );
      expect(micPermission?.instructions).toContain(
        "Settings > Privacy & security",
      );
    });

    it("has valid status values for all Windows permissions", async () => {
      Object.defineProperty(process, "platform", {
        value: "win32",
      });

      const response = await callApi();
      const data = await response.json();

      const validStatuses = ["granted", "denied", "unknown", "not_configured"];

      for (const permission of data.permissions) {
        expect(validStatuses).toContain(permission.status);
      }
    });
  });
});
