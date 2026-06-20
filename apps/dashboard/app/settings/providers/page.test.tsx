import { render, screen } from "@testing-library/react";
import ProvidersSettingsPage from "./page";

jest.mock("@/features/pages/settings/providers/ProvidersPage", () => ({
  __esModule: true,
  default: () => <div data-testid="providers-ui">Providers UI</div>,
}));

describe("Settings providers route", () => {
  it("renders the canonical providers page at /settings/providers", () => {
    render(<ProvidersSettingsPage />);
    expect(screen.getByTestId("providers-ui")).toBeInTheDocument();
  });
});
