import React from "react";
import { render, screen } from "@testing-library/react";
import { Select } from "./Select";

describe("Select", () => {
  it("renders correctly", () => {
    render(<Select>Test Content</Select>);
    const element = screen.getByText("Test Content");
    expect(element).toBeInTheDocument();
  });

  it("applies variant classes", () => {
    render(
      <Select variant="outline" data-testid="select">
        Test
      </Select>,
    );
    const element = screen.getByTestId("select");
    expect(element.className).toContain("border");
  });
});
