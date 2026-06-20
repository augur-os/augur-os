import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

import { CapabilityDriftBadge } from "@/features/browse/CapabilityDriftBadge";

describe("CapabilityDriftBadge", () => {
  it("renders nothing when drift is empty", () => {
    const { container } = render(<CapabilityDriftBadge drift={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders one tag per drift dimension", () => {
    render(
      <CapabilityDriftBadge
        drift={["blocked_present", "unexpected_client"]}
      />,
    );
    expect(screen.getByText("blocked present")).toBeInTheDocument();
    expect(screen.getByText("unexpected client")).toBeInTheDocument();
  });

  it("uses the failure palette title for Augur regressions", () => {
    render(<CapabilityDriftBadge drift={["direct_mcp_exposure"]} />);
    expect(screen.getByText("direct MCP exposure")).toHaveAttribute(
      "title",
      "Augur regression",
    );
  });

  it("uses the advisory palette title for non-failure dimensions", () => {
    render(<CapabilityDriftBadge drift={["duplicate_external_skill"]} />);
    expect(screen.getByText("duplicate external")).toHaveAttribute(
      "title",
      "Advisory drift",
    );
  });

  it("falls back to the raw drift key when label is unknown", () => {
    render(<CapabilityDriftBadge drift={["future_dimension"]} />);
    expect(screen.getByText("future_dimension")).toBeInTheDocument();
  });
});
