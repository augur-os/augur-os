/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import MobileSidebar from "@/components/MobileSidebar";

const mockUsePathname = jest.fn();

jest.mock("next/navigation", () => ({
  usePathname: () => mockUsePathname(),
}));

jest.mock("@/components/BrainLogo", () => ({
  __esModule: true,
  default: () => <div>Augur</div>,
}));

jest.mock("@/components/SidebarNav", () => ({
  __esModule: true,
  default: ({ onNavigate }: { onNavigate?: () => void }) => (
    <button type="button" onClick={onNavigate}>
      Browse
    </button>
  ),
}));

jest.mock("@/components/shared/AirplanePill", () => ({
  __esModule: true,
  default: () => <button type="button">Airplane</button>,
}));

describe("MobileSidebar", () => {
  beforeEach(() => {
    mockUsePathname.mockReturnValue("/browse");
  });

  it("closes the drawer when a navigation item is activated", () => {
    render(<MobileSidebar />);

    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getByRole("button", { name: "Close menu" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Browse" }));

    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument();
  });

  it("does not render the stale Airplane route control in the mobile shell", () => {
    render(<MobileSidebar />);

    expect(
      screen.queryByRole("button", { name: "Airplane" }),
    ).not.toBeInTheDocument();
  });

  it("closes the drawer when the pathname changes", () => {
    const { rerender } = render(<MobileSidebar />);

    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getByRole("button", { name: "Close menu" })).toBeInTheDocument();

    mockUsePathname.mockReturnValue("/settings");
    rerender(<MobileSidebar />);

    expect(screen.getByRole("button", { name: "Open menu" })).toBeInTheDocument();
  });
});
