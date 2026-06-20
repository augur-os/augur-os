import Page from "./page";

// The page is a thin server component that mounts the client SetupWidget.
// A shallow construction is enough to guard the route from regressions.
jest.mock("@/features/setup/SetupWidget", () => ({
  SetupWidget: () => null,
}));

describe("SetupPage", () => {
  it("renders without crashing", () => {
    const element = Page();
    expect(element).toBeTruthy();
  });
});
