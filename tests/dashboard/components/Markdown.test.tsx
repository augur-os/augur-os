import { render, screen } from "@testing-library/react";

import Markdown from "@/components/Markdown";

describe("Markdown", () => {
  it("strips generated headers and frontmatter before rendering", () => {
    render(
      <Markdown
        markdown={`---
title: Hidden Metadata
---
<!--
AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY
Source: skills/example/SKILL.md
-->

# Visible Heading

Body text`}
      />,
    );

    const rendered = screen.getByTestId("react-markdown");
    expect(rendered).toHaveTextContent("Visible Heading");
    expect(rendered).toHaveTextContent("Body text");
    expect(rendered).not.toHaveTextContent("AUTO-GENERATED");
    expect(rendered).not.toHaveTextContent("Hidden Metadata");
  });
});
