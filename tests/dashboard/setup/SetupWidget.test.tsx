/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import type { SetupStatus } from "@/features/setup/types";

const mockUseSetupStatus = jest.fn();
const mockMcpCall = jest.fn();
const mockWriteText = jest.fn();

jest.mock("@/features/setup/hooks", () => ({
  useSetupStatus: () => mockUseSetupStatus(),
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

function status(overrides: Partial<SetupStatus> = {}): SetupStatus {
  return {
    version: 1,
    computed_at: "2026-05-12T00:00:00Z",
    total: 11,
    completed: 2,
    pct: 18,
    state: "card",
    ever_completed: false,
    phases: [
      {
        id: "foundation",
        label: "Foundation",
        total: 3,
        completed: 1,
        pct: 33,
        items: [
          {
            id: "vault",
            label: "Vault connected",
            description: "Vault path resolves.",
            status: "done",
            action: { type: "route", route: "/settings", label: "Open settings" },
            last_checked: "2026-05-12T00:00:00Z",
          },
          {
            id: "first-ask",
            label: "First /ask answered",
            description: "At least one successful /ask query.",
            status: "pending",
            action: { type: "command", command: "/ask", label: "Try /ask" },
            last_checked: "2026-05-12T00:00:00Z",
          },
        ],
      },
    ],
    ...overrides,
  };
}

beforeEach(() => {
  mockUseSetupStatus.mockReset();
  mockMcpCall.mockReset();
  mockWriteText.mockReset();
  mockWriteText.mockResolvedValue(undefined);
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: mockWriteText },
  });
});

it("renders the full setup card with phase progress and pending actions", async () => {
  const user = userEvent.setup();
  mockUseSetupStatus.mockReturnValue({
    data: status(),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="settings" />);

  expect(screen.getByRole("heading", { name: "Setup progress" })).toBeInTheDocument();
  expect(screen.getByText("2/11")).toBeInTheDocument();
  expect(screen.getByText("Foundation")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: /try \/ask/i }));
  expect(screen.getByRole("status")).toHaveTextContent("Copied /ask");
});

it("renders compact bar from 60 to 99 percent", async () => {
  mockUseSetupStatus.mockReturnValue({
    data: status({ completed: 8, pct: 73, state: "bar" }),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="sidebar" />);

  expect(screen.getByRole("button", { name: /setup 73 percent/i })).toBeInTheDocument();
});

it("opens sidebar setup progress in a readable flyout", async () => {
  const user = userEvent.setup();
  mockUseSetupStatus.mockReturnValue({
    data: status({ completed: 8, pct: 73, state: "bar" }),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="sidebar" />);

  await user.click(screen.getByRole("button", { name: /setup 73 percent/i }));
  const flyout = screen.getByTestId("setup-sidebar-flyout");
  expect(flyout.parentElement).toBe(document.body);
  expect(flyout).toHaveClass("fixed", "z-[9999]", "bg-[var(--bg-primary)]", "md:w-[30rem]");
  expect(screen.getByRole("heading", { name: "Setup progress" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /minimize/i })).toBeInTheDocument();
});

it("renders quiet chip when setup is complete", async () => {
  mockUseSetupStatus.mockReturnValue({
    data: status({ completed: 11, pct: 100, state: "chip", ever_completed: true }),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="sidebar" />);

  expect(screen.getByLabelText(/setup complete/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Setup complete" })).toHaveTextContent("Setup complete");
});

it("surfaces alert state when previously complete setup regresses", async () => {
  mockUseSetupStatus.mockReturnValue({
    data: status({ pct: 91, state: "alert", ever_completed: true }),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="sidebar" />);

  expect(screen.getByRole("button", { name: "Setup needs attention" })).toBeInTheDocument();
});

it("lets users expand and minimize the completed setup chip", async () => {
  const user = userEvent.setup();
  mockUseSetupStatus.mockReturnValue({
    data: status({ completed: 11, pct: 100, state: "chip", ever_completed: true }),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="sidebar" />);

  await user.click(screen.getByRole("button", { name: "Setup complete" }));
  expect(screen.getByRole("heading", { name: "Setup progress" })).toBeInTheDocument();
  expect(screen.getByText(/all setup checks are complete/i)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /minimize/i }));
  expect(screen.getByRole("button", { name: "Setup complete" })).toBeInTheDocument();
});

it("lets users expand and minimize the setup attention chip", async () => {
  const user = userEvent.setup();
  mockUseSetupStatus.mockReturnValue({
    data: status({ pct: 91, state: "alert", ever_completed: true }),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="sidebar" />);

  await user.click(screen.getByRole("button", { name: "Setup needs attention" }));
  expect(screen.getByText(/some setup evidence changed/i)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /minimize/i }));
  expect(screen.getByRole("button", { name: "Setup needs attention" })).toBeInTheDocument();
});

it("keeps setup item labels and descriptions readable beside actions", async () => {
  mockUseSetupStatus.mockReturnValue({
    data: status(),
    loading: false,
    error: null,
    refresh: jest.fn(),
  });
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  const { container } = render(<SetupWidget variant="settings" />);

  expect(screen.getByText("First /ask answered")).not.toHaveClass("truncate");
  expect(screen.getByText("At least one successful /ask query.")).not.toHaveClass("line-clamp-2");
  expect(screen.getByTestId("setup-full-card")).toHaveClass("bg-[var(--bg-primary)]");
  expect(container.innerHTML).not.toContain("surface-");
  expect(container.innerHTML).not.toContain("accent-color");
});

it("persists skip through the setup MCP tool and refreshes status", async () => {
  const refresh = jest.fn();
  mockUseSetupStatus.mockReturnValue({
    data: status(),
    loading: false,
    error: null,
    refresh,
  });
  mockMcpCall.mockResolvedValue({ success: true });
  const user = userEvent.setup();
  const { SetupWidget } = await import("@/features/setup/SetupWidget");

  render(<SetupWidget variant="settings" />);
  await user.click(screen.getByRole("button", { name: /skip first \/ask answered/i }));

  expect(mockMcpCall).toHaveBeenCalledWith("set-setup-skipped", {
    item_id: "first-ask",
    skipped: true,
  });
  expect(refresh).toHaveBeenCalled();
});
