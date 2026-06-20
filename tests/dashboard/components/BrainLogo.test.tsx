/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import BrainLogo from "@/components/BrainLogo";

const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

jest.mock("@/features/components/AugurIcon", () => ({
  __esModule: true,
  default: ({ className }: { className?: string }) => (
    <svg data-testid="augur-icon" className={className} />
  ),
}));

describe("BrainLogo", () => {
  beforeEach(() => {
    mockPush.mockReset();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it("uses theme-aware accent variables for the logo chip", () => {
    render(<BrainLogo />);

    const chip = screen.getByTestId("augur-icon").parentElement;
    expect(chip).toHaveClass(
      "bg-[linear-gradient(135deg,var(--accent-primary),var(--accent-secondary))]",
    );
  });

  it("navigates to the neural view after three quick clicks", () => {
    render(<BrainLogo />);

    const logo = screen.getByText("Augur").closest("button");
    expect(logo).not.toBeNull();

    fireEvent.click(logo!);
    fireEvent.click(logo!);
    fireEvent.click(logo!);

    expect(mockPush).not.toHaveBeenCalled();

    jest.advanceTimersByTime(400);

    expect(mockPush).toHaveBeenCalledWith("/workspace/overview");
  });
});
