import { describe, it, expect, jest, beforeEach } from "@jest/globals";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/jest-globals";
import PermissionsTab from "./PermissionsTab";

// Mock fetch
const mockFetch = jest.fn() as jest.Mock<(...args: any[]) => Promise<any>>;
(globalThis as any).fetch = mockFetch;

// Mock window.open
const mockWindowOpen = jest.fn();
window.open = mockWindowOpen as any;

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => "/",
  useSearchParams: () => ({ get: jest.fn() }),
}));

describe("PermissionsTab", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // Never resolves
    render(<PermissionsTab />);
    expect(screen.getByText("Checking permissions...")).toBeInTheDocument();
  });

  it("renders permissions after successful fetch", async () => {
    const mockPermissions = [
      {
        id: "screen_recording",
        name: "Screen Recording",
        status: "granted",
        description: "Required for Meeting Recorder",
        category: "macos_system",
        instructions: "System Settings > Privacy & Security > Screen Recording",
      },
      {
        id: "microphone",
        name: "Microphone",
        status: "denied",
        description: "Required for voice recording",
        category: "macos_system",
        instructions: "System Settings > Privacy & Security > Microphone",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Screen Recording")).toBeInTheDocument();
    });

    expect(screen.getByText("Microphone")).toBeInTheDocument();
    // Check that both statuses are present (use getAllByText since there may be multiple)
    expect(screen.getAllByText("Granted").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Denied").length).toBeGreaterThan(0);
  });

  it("renders error state when fetch fails", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(
        screen.getByText("Failed to connect to permission status API"),
      ).toBeInTheDocument();
    });
  });

  it("renders error from API response", async () => {
    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({ ok: false, error: "Permission check failed" }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Permission check failed")).toBeInTheDocument();
    });
  });

  it("shows unsupported platform warning when platform is not darwin or win32", async () => {
    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({ ok: true, permissions: [], platform: "linux" }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Unsupported Platform")).toBeInTheDocument();
    });
  });

  it("does not show warning for Windows platform", async () => {
    const windowsPermissions = [
      {
        id: "microphone",
        name: "Microphone",
        status: "granted",
        description: "Required for voice recording",
        category: "windows_system",
        instructions: "Settings > Privacy & security > Microphone",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: windowsPermissions,
          platform: "win32",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Microphone")).toBeInTheDocument();
    });

    expect(screen.queryByText("Unsupported Platform")).not.toBeInTheDocument();
  });

  it("displays stats correctly", async () => {
    const mockPermissions = [
      {
        id: "p1",
        name: "P1",
        status: "granted",
        description: "",
        category: "macos_system",
        instructions: "",
      },
      {
        id: "p2",
        name: "P2",
        status: "granted",
        description: "",
        category: "macos_system",
        instructions: "",
      },
      {
        id: "p3",
        name: "P3",
        status: "denied",
        description: "",
        category: "macos_system",
        instructions: "",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument(); // Total
      expect(screen.getByText("2")).toBeInTheDocument(); // Granted
      expect(screen.getByText("1")).toBeInTheDocument(); // Need Attention
    });
  });

  it("shows Open Settings button for denied permissions with deep links", async () => {
    const mockPermissions = [
      {
        id: "microphone",
        name: "Microphone",
        status: "denied",
        description: "Required for voice recording",
        category: "macos_system",
        instructions: "Enable in System Settings",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Open Settings")).toBeInTheDocument();
    });
  });

  it("opens System Settings when Open Settings button is clicked", async () => {
    const mockPermissions = [
      {
        id: "microphone",
        name: "Microphone",
        status: "denied",
        description: "Required for voice recording",
        category: "macos_system",
        instructions: "Enable in System Settings",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Open Settings")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Open Settings"));

    expect(mockWindowOpen).toHaveBeenCalledWith(
      "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
      "_blank",
    );
  });

  it("shows tooltip on hover", async () => {
    const mockPermissions = [
      {
        id: "screen_recording",
        name: "Screen Recording",
        status: "denied",
        description: "Required for Meeting Recorder",
        category: "macos_system",
        instructions: "Enable in System Settings > Screen Recording",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Screen Recording")).toBeInTheDocument();
    });

    // Find the permission row and hover over it
    const permissionRow = screen
      .getByText("Screen Recording")
      .closest(".glass-panel");
    expect(permissionRow).toBeInTheDocument();

    fireEvent.mouseEnter(permissionRow!);

    await waitFor(() => {
      expect(screen.getByText("How to enable:")).toBeInTheDocument();
    });

    fireEvent.mouseLeave(permissionRow!);

    await waitFor(() => {
      expect(screen.queryByText("How to enable:")).not.toBeInTheDocument();
    });
  });

  it("refreshes permissions when Refresh button is clicked", async () => {
    const mockPermissions = [
      {
        id: "screen_recording",
        name: "Screen Recording",
        status: "granted",
        description: "Required for Meeting Recorder",
        category: "macos_system",
        instructions: "Enable in System Settings",
      },
    ];

    mockFetch.mockResolvedValue({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("Screen Recording")).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("Refresh"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });
  });

  it("groups permissions by category", async () => {
    const mockPermissions = [
      {
        id: "screen_recording",
        name: "Screen Recording",
        status: "granted",
        description: "For meetings",
        category: "macos_system",
        instructions: "",
      },
      {
        id: "calendar",
        name: "Calendar",
        status: "granted",
        description: "For scheduling",
        category: "email_calendar",
        instructions: "",
      },
      {
        id: "tesseract",
        name: "Tesseract OCR",
        status: "not_configured",
        description: "For OCR",
        category: "dependencies",
        instructions: "",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("macOS System Permissions")).toBeInTheDocument();
      expect(screen.getByText("Email & Calendar")).toBeInTheDocument();
      expect(screen.getByText("System Dependencies")).toBeInTheDocument();
    });
  });

  it('shows "How to fix" section for denied permissions', async () => {
    const mockPermissions = [
      {
        id: "microphone",
        name: "Microphone",
        status: "denied",
        description: "Required for voice recording",
        category: "macos_system",
        instructions: "Go to System Settings and enable Microphone",
      },
    ];

    mockFetch.mockResolvedValueOnce({
      json: () =>
        Promise.resolve({
          ok: true,
          permissions: mockPermissions,
          platform: "darwin",
        }),
    });

    render(<PermissionsTab />);

    await waitFor(() => {
      expect(screen.getByText("How to fix:")).toBeInTheDocument();
    });
  });

  // Windows-specific tests
  describe("Windows support", () => {
    it("renders Windows permissions after successful fetch", async () => {
      const windowsPermissions = [
        {
          id: "microphone",
          name: "Microphone",
          status: "granted",
          description: "Required for voice recording",
          category: "windows_system",
          instructions: "Settings > Privacy & security > Microphone",
        },
        {
          id: "camera",
          name: "Camera",
          status: "denied",
          description: "Required for video capture",
          category: "windows_system",
          instructions: "Settings > Privacy & security > Camera",
        },
        {
          id: "location",
          name: "Location",
          status: "granted",
          description: "Used for location-aware features",
          category: "windows_system",
          instructions: "Settings > Privacy & security > Location",
        },
      ];

      mockFetch.mockResolvedValueOnce({
        json: () =>
          Promise.resolve({
            ok: true,
            permissions: windowsPermissions,
            platform: "win32",
          }),
      });

      render(<PermissionsTab />);

      await waitFor(() => {
        expect(screen.getByText("Microphone")).toBeInTheDocument();
      });

      expect(screen.getByText("Camera")).toBeInTheDocument();
      expect(screen.getByText("Location")).toBeInTheDocument();
      expect(
        screen.getByText("Windows System Permissions"),
      ).toBeInTheDocument();
    });

    it("opens Windows Settings when Open Settings button is clicked", async () => {
      const windowsPermissions = [
        {
          id: "microphone",
          name: "Microphone",
          status: "denied",
          description: "Required for voice recording",
          category: "windows_system",
          instructions: "Settings > Privacy & security > Microphone",
        },
      ];

      mockFetch.mockResolvedValueOnce({
        json: () =>
          Promise.resolve({
            ok: true,
            permissions: windowsPermissions,
            platform: "win32",
          }),
      });

      render(<PermissionsTab />);

      await waitFor(() => {
        expect(screen.getByText("Open Settings")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Open Settings"));

      expect(mockWindowOpen).toHaveBeenCalledWith(
        "ms-settings:privacy-microphone",
        "_blank",
      );
    });

    it("groups Windows permissions correctly", async () => {
      const windowsPermissions = [
        {
          id: "microphone",
          name: "Microphone",
          status: "granted",
          description: "For voice",
          category: "windows_system",
          instructions: "",
        },
        {
          id: "email_imap",
          name: "Email/IMAP",
          status: "not_configured",
          description: "For email",
          category: "email_calendar",
          instructions: "",
        },
        {
          id: "tesseract",
          name: "Tesseract OCR",
          status: "not_configured",
          description: "For OCR",
          category: "dependencies",
          instructions: "",
        },
      ];

      mockFetch.mockResolvedValueOnce({
        json: () =>
          Promise.resolve({
            ok: true,
            permissions: windowsPermissions,
            platform: "win32",
          }),
      });

      render(<PermissionsTab />);

      await waitFor(() => {
        expect(
          screen.getByText("Windows System Permissions"),
        ).toBeInTheDocument();
        expect(screen.getByText("Email & Calendar")).toBeInTheDocument();
        expect(screen.getByText("System Dependencies")).toBeInTheDocument();
      });

      // Should NOT show macOS category since no macOS permissions
      expect(
        screen.queryByText("macOS System Permissions"),
      ).not.toBeInTheDocument();
    });

    it("shows Windows camera deep link correctly", async () => {
      const windowsPermissions = [
        {
          id: "camera",
          name: "Camera",
          status: "denied",
          description: "Required for video capture",
          category: "windows_system",
          instructions: "Settings > Privacy & security > Camera",
        },
      ];

      mockFetch.mockResolvedValueOnce({
        json: () =>
          Promise.resolve({
            ok: true,
            permissions: windowsPermissions,
            platform: "win32",
          }),
      });

      render(<PermissionsTab />);

      await waitFor(() => {
        expect(screen.getByText("Open Settings")).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText("Open Settings"));

      expect(mockWindowOpen).toHaveBeenCalledWith(
        "ms-settings:privacy-webcam",
        "_blank",
      );
    });
  });
});
