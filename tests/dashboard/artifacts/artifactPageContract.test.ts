import { readFileSync } from "node:fs";
import path from "node:path";

describe("artifact page contract", () => {
  it("does not resolve artifact metadata through server MCP during page render", () => {
    const source = readFileSync(
      path.join(process.cwd(), "app/artifact/[slug]/page.tsx"),
      "utf8",
    );

    expect(source).toContain("ArtifactRouteClient");
    expect(source).not.toContain("@/lib/artifacts/server");
    expect(source).not.toContain("getArtifactBySlug");
  });
});
