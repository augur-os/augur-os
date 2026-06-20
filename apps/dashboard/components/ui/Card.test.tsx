import React from "react";
import { render, screen } from "@testing-library/react";
import { Card } from "./Card";

describe("Card", () => {
  it("renders correctly", () => {
    render(<Card>Test Content</Card>);
    const element = screen.getByText("Test Content");
    expect(element).toBeInTheDocument();
  });

  it("applies default border class", () => {
    render(<Card data-testid="card">Test</Card>);
    const element = screen.getByTestId("card");
    expect(element.className).toContain("border");
  });
});
