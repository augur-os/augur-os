/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SkillNavSettingsCard } from "@/app/settings/components/SkillNavSettingsCard";

const mockMutate = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: () => ({
    data: {
      skills: [
        {
          skill: "health",
          bundle: "life",
          hub: "life",
          navVisible: true,
          reason: "Health tools",
          canToggle: true,
        },
        {
          skill: "knowledge",
          bundle: "brain",
          hub: "workspace",
          navVisible: false,
          reason: "Knowledge tools",
          canToggle: true,
        },
      ],
    },
    loading: false,
    error: null,
    refetch: jest.fn(),
  }),
}));

jest.mock("@/lib/mcp/useMcpMutation", () => ({
  useMcpMutation: () => ({
    mutate: mockMutate,
    loading: false,
    error: null,
  }),
}));

describe("SkillNavSettingsCard", () => {
  beforeEach(() => {
    mockMutate.mockReset();
  });

  it("renders sidebar skill toggles in settings", () => {
    render(<SkillNavSettingsCard />);

    expect(screen.getByText("Sidebar Skills")).toBeInTheDocument();
    expect(screen.getByText("health")).toBeInTheDocument();
    expect(screen.getByText("knowledge")).toBeInTheDocument();
  });

  it("writes skill-nav-toggle when toggled", () => {
    render(<SkillNavSettingsCard />);

    fireEvent.click(
      screen.getByRole("button", { name: "Hide health in sidebar" }),
    );

    expect(mockMutate).toHaveBeenCalledWith({
      scope: "skill-nav-toggle",
      skill: "health",
      visible: false,
    });
  });
});
