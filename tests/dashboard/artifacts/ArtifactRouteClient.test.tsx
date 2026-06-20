/**
 * @jest-environment jsdom
 */
import { render, screen, waitFor } from "@testing-library/react";
import { ArtifactRouteClient } from "@/app/artifact/[slug]/ArtifactRouteClient";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

jest.mock("@/app/artifact/[slug]/ArtifactChrome", () => ({
  ArtifactChrome: ({
    artifact,
    rawSrc,
  }: {
    artifact: { title: string };
    rawSrc: string;
  }) => (
    <div data-testid="artifact-chrome" data-raw-src={rawSrc}>
      {artifact.title}
    </div>
  ),
}));

const mockMcpCall = mcpCall as jest.MockedFunction<typeof mcpCall>;

describe("ArtifactRouteClient", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("loads artifact metadata through the dashboard MCP API before rendering chrome", async () => {
    mockMcpCall.mockResolvedValueOnce({
      artifacts: [
        {
          slug: "augur-ai-stack-apple-vs-intel",
          title: "Augur AI Stack - Apple vs Intel",
          kind: "saved",
          hub: "venture-augur",
          path: "/tmp/artifact.html",
          url: "file:///tmp/artifact.html",
        },
      ],
    });

    render(<ArtifactRouteClient slug="augur-ai-stack-apple-vs-intel" />);

    expect(screen.getByText("Opening artifact")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("artifact-chrome")).toHaveTextContent(
        "Augur AI Stack - Apple vs Intel",
      );
    });
    expect(screen.getByTestId("artifact-chrome")).toHaveAttribute(
      "data-raw-src",
      "/api/artifact/augur-ai-stack-apple-vs-intel/raw",
    );
    expect(mockMcpCall).toHaveBeenCalledWith(
      "artifacts-list",
      {},
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("rejects invalid slugs without calling MCP", async () => {
    render(<ArtifactRouteClient slug="../not-an-artifact" />);

    expect(await screen.findByText("Artifact not found")).toBeInTheDocument();
    expect(mockMcpCall).not.toHaveBeenCalled();
  });
});
