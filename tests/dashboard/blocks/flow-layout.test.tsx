import React from "react";
import { render, screen } from "@testing-library/react";
import { FlowLayout } from "@/lib/blocks/flow-layout";
import type { BlockSize } from "@/lib/blocks/flow-types";

function Block({ label }: { label: string }) {
  return <div data-testid={`block-${label}`}>{label}</div>;
}

describe("FlowLayout", () => {
  it("renders each full block in its own row", () => {
    const sizes: BlockSize[] = ["full", "full", "full"];
    render(
      <FlowLayout sizes={sizes}>
        {[
          <Block key="a" label="a" />,
          <Block key="b" label="b" />,
          <Block key="c" label="c" />,
        ]}
      </FlowLayout>,
    );

    const rows = screen.getAllByTestId("flow-row");
    expect(rows).toHaveLength(3);

    // Each row has exactly one cell
    rows.forEach((row) => {
      const cells = row.querySelectorAll("[data-testid='flow-cell']");
      expect(cells).toHaveLength(1);
    });
  });

  it("places two half blocks in the same row", () => {
    const sizes: BlockSize[] = ["half", "half"];
    render(
      <FlowLayout sizes={sizes}>
        {[
          <Block key="a" label="a" />,
          <Block key="b" label="b" />,
        ]}
      </FlowLayout>,
    );

    const rows = screen.getAllByTestId("flow-row");
    expect(rows).toHaveLength(1);

    const cells = rows[0].querySelectorAll("[data-testid='flow-cell']");
    expect(cells).toHaveLength(2);
    expect(cells[0]).toHaveAttribute("data-size", "half");
    expect(cells[1]).toHaveAttribute("data-size", "half");
  });

  it("places three third blocks in the same row", () => {
    const sizes: BlockSize[] = ["third", "third", "third"];
    render(
      <FlowLayout sizes={sizes}>
        {[
          <Block key="a" label="a" />,
          <Block key="b" label="b" />,
          <Block key="c" label="c" />,
        ]}
      </FlowLayout>,
    );

    const rows = screen.getAllByTestId("flow-row");
    expect(rows).toHaveLength(1);

    const cells = rows[0].querySelectorAll("[data-testid='flow-cell']");
    expect(cells).toHaveLength(3);
    cells.forEach((cell) => {
      expect(cell).toHaveAttribute("data-size", "third");
    });
  });

  it("keeps an orphan half block at half-width (not stretched)", () => {
    const sizes: BlockSize[] = ["half"];
    render(
      <FlowLayout sizes={sizes}>
        {[<Block key="a" label="a" />]}
      </FlowLayout>,
    );

    const rows = screen.getAllByTestId("flow-row");
    expect(rows).toHaveLength(1);

    const cell = rows[0].querySelector("[data-testid='flow-cell']");
    expect(cell).toHaveAttribute("data-size", "half");
    // Check it's styled at 50%, not stretched to 100%
    expect(cell).toHaveStyle({
      flexBasis: "calc(50.0000% - 0.5rem)",
      maxWidth: "calc(50.0000% - 0.5rem)",
    });
  });

  it("wraps half to next row when preceded by third (third + half > 1.0 would not fit, but 0.333 + 0.5 = 0.833 fits)", () => {
    // third (0.333) + half (0.5) = 0.833 — fits in one row
    const sizes: BlockSize[] = ["third", "half"];
    render(
      <FlowLayout sizes={sizes}>
        {[
          <Block key="a" label="a" />,
          <Block key="b" label="b" />,
        ]}
      </FlowLayout>,
    );

    const rows = screen.getAllByTestId("flow-row");
    expect(rows).toHaveLength(1);

    const cells = rows[0].querySelectorAll("[data-testid='flow-cell']");
    expect(cells).toHaveLength(2);
    expect(cells[0]).toHaveAttribute("data-size", "third");
    expect(cells[1]).toHaveAttribute("data-size", "half");
  });

  it("wraps half to next row when it does not fit (half + half + half)", () => {
    // half (0.5) + half (0.5) fills row 1, third half wraps to row 2
    const sizes: BlockSize[] = ["half", "half", "half"];
    render(
      <FlowLayout sizes={sizes}>
        {[
          <Block key="a" label="a" />,
          <Block key="b" label="b" />,
          <Block key="c" label="c" />,
        ]}
      </FlowLayout>,
    );

    const rows = screen.getAllByTestId("flow-row");
    expect(rows).toHaveLength(2);

    expect(rows[0].querySelectorAll("[data-testid='flow-cell']")).toHaveLength(2);
    expect(rows[1].querySelectorAll("[data-testid='flow-cell']")).toHaveLength(1);
  });

  it("renders nothing for empty blocks array", () => {
    const { container } = render(
      <FlowLayout sizes={[]}>
        {[]}
      </FlowLayout>,
    );

    expect(container.innerHTML).toBe("");
    expect(screen.queryByTestId("flow-layout")).toBeNull();
  });

  it("handles mixed sizes: full + third + third + third + half + half", () => {
    const sizes: BlockSize[] = ["full", "third", "third", "third", "half", "half"];
    render(
      <FlowLayout sizes={sizes}>
        {[
          <Block key="a" label="a" />,
          <Block key="b" label="b" />,
          <Block key="c" label="c" />,
          <Block key="d" label="d" />,
          <Block key="e" label="e" />,
          <Block key="f" label="f" />,
        ]}
      </FlowLayout>,
    );

    const rows = screen.getAllByTestId("flow-row");
    // Row 1: full (1.0)
    // Row 2: third + third + third (1.0)
    // Row 3: half + half (1.0)
    expect(rows).toHaveLength(3);

    expect(rows[0].querySelectorAll("[data-testid='flow-cell']")).toHaveLength(1);
    expect(rows[1].querySelectorAll("[data-testid='flow-cell']")).toHaveLength(3);
    expect(rows[2].querySelectorAll("[data-testid='flow-cell']")).toHaveLength(2);
  });
});
