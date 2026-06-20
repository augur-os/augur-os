import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import type { BrowseItem } from "@/lib/browse/types";
import { BrowseCard } from "@/components/shared/BrowseCard";

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), prefetch: jest.fn(), back: jest.fn() }),
}));

jest.mock("@/lib/mcp/client", () => ({ mcpCall: jest.fn().mockResolvedValue({}) }));

const item: BrowseItem = {
  id: "wiki-card",
  title: "Wiki Card",
  description: "A useful wiki page",
  hub: "workspace",
  icon: "FileText",
  primaryAction: { label: "Read", type: "open-file", target: "/tmp/wiki.md" },
};

describe("BrowseCard pin controls", () => {
  it("renders inactive pin control and calls toggle", () => {
    const onTogglePin = jest.fn();
    render(<BrowseCard item={item} isPinned={false} onTogglePin={onTogglePin} />);

    fireEvent.click(screen.getByRole("button", { name: "Pin Wiki Card" }));

    expect(onTogglePin).toHaveBeenCalledTimes(1);
  });

  it("renders active pin control and overflow unpin action", () => {
    const onTogglePin = jest.fn();
    render(<BrowseCard item={item} isPinned onTogglePin={onTogglePin} />);

    expect(screen.getByRole("button", { name: "Unpin Wiki Card" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Unpin" }));

    expect(onTogglePin).toHaveBeenCalledTimes(1);
  });
});
