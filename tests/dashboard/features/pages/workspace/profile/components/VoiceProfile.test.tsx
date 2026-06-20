/**
 * @jest-environment jsdom
 */
import React from "react";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { VoiceProfile } from "@/features/pages/workspace/profile/components/VoiceProfile";
import { useVoiceProfile } from "@/features/pages/workspace/profile/hooks/useVoiceProfile";

jest.mock("@/features/pages/workspace/profile/hooks/useVoiceProfile", () => ({
  VOICE_PROFILE_LANGUAGES: ["en", "he"],
  useVoiceProfile: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

jest.mock("@/features/components/DashboardWidget", () => {
  const MockDashboardWidget = ({
    title,
    children,
    maxHeight,
    scrollable,
  }: {
    title: string;
    children: React.ReactNode;
    maxHeight?: string | number | null;
    scrollable?: boolean;
  }) => (
    <section
      aria-label={title}
      data-max-height={maxHeight === null ? "none" : String(maxHeight ?? "default")}
      data-scrollable={String(scrollable ?? true)}
    >
      {children}
    </section>
  );
  return {
    __esModule: true,
    default: MockDashboardWidget,
  };
});

const mockedUseVoiceProfile = useVoiceProfile as jest.Mock;
let clipboardWriteText: jest.Mock;

const completeEnSlot = {
  in_progress: false,
  answered: 100,
  total: 100,
  percentage: 100,
  complete: true,
  started_at: "2026-05-01T09:00:00Z",
  last_answered_at: "2026-05-01T11:00:00Z",
  about_me: {
    exists: true,
    last_updated_at: "2026-05-02T12:00:00Z",
    age_days: 14,
    size_bytes: 2048,
  },
};

const completeHeSlot = {
  ...completeEnSlot,
  about_me: {
    exists: true,
    last_updated_at: "2026-05-03T12:00:00Z",
    age_days: 8,
    size_bytes: 2200,
  },
};

const inProgressEnSlot = {
  in_progress: true,
  answered: 23,
  total: 100,
  percentage: 23,
  complete: false,
  started_at: "2026-05-01T09:00:00Z",
  last_answered_at: "2026-05-01T09:45:00Z",
  about_me: {
    exists: false,
    last_updated_at: null,
    age_days: null,
    size_bytes: null,
  },
};

const inProgressHeSlot = {
  ...inProgressEnSlot,
  answered: 42,
  percentage: 42,
};

function mockVoiceProfileState(overrides: Partial<ReturnType<typeof useVoiceProfile>> = {}) {
  mockedUseVoiceProfile.mockReturnValue({
    status: { en: null, he: null },
    profiles: { en: null, he: null },
    loading: false,
    error: null,
    refresh: jest.fn(),
    ...overrides,
  });
}

describe("VoiceProfile", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    clipboardWriteText = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      writable: true,
      value: {
        writeText: clipboardWriteText,
      },
    });
  });

  it("renders a single not-started CTA when neither English nor Hebrew exists", async () => {
    mockVoiceProfileState();

    render(<VoiceProfile />);

    expect(screen.getByText(/voice profile captures how you think/i)).toBeInTheDocument();
    expect(screen.getByText(/english or hebrew supported/i)).toBeInTheDocument();
    expect(screen.queryAllByTestId("voice-profile-language-card")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: /copy \/profile interview/i }));
    await waitFor(() => expect(clipboardWriteText).toHaveBeenCalledWith("/profile interview"));
  });

  it("renders one English in-progress card with progress and count", () => {
    mockVoiceProfileState({
      status: { en: inProgressEnSlot, he: null },
    });

    render(<VoiceProfile />);

    const card = screen.getByTestId("voice-profile-card-en");
    expect(within(card).getByText("EN")).toBeInTheDocument();
    expect(within(card).getByText(/23 of 100 questions answered/i)).toBeInTheDocument();
    expect(within(card).getByRole("progressbar", { name: /english interview progress/i })).toHaveAttribute(
      "aria-valuenow",
      "23",
    );
    expect(screen.queryByTestId("voice-profile-card-he")).not.toBeInTheDocument();
  });

  it("renders one English completed card with markdown, age, and language-scoped update action", async () => {
    mockVoiceProfileState({
      status: { en: completeEnSlot, he: null },
      profiles: {
        en: {
          success: true,
          language: "en",
          content: "# English Voice\n\n## Beliefs\n\nDirect and concise.",
          metadata: { last_updated_at: "2026-05-02T12:00:00Z", age_days: 14, size_bytes: 2048 },
        },
        he: null,
      },
    });

    render(<VoiceProfile />);

    const card = screen.getByTestId("voice-profile-card-en");
    expect(within(card).getByText("EN")).toBeInTheDocument();
    expect(within(card).getByText(/# English Voice/i)).toBeInTheDocument();
    expect(within(card).getByText(/age: 14 days/i)).toBeInTheDocument();

    fireEvent.click(within(card).getByRole("button", { name: /copy \/profile update en/i }));
    await waitFor(() => expect(clipboardWriteText).toHaveBeenCalledWith("/profile update en"));
  });

  it("uses natural widget height when rendering completed profile markdown", () => {
    mockVoiceProfileState({
      status: { en: completeEnSlot, he: null },
      profiles: {
        en: {
          success: true,
          language: "en",
          content: "# English Voice\n\n" + "Long profile paragraph.\n\n".repeat(20),
          metadata: { last_updated_at: "2026-05-02T12:00:00Z", age_days: 14, size_bytes: 4096 },
        },
        he: null,
      },
    });

    render(<VoiceProfile />);

    expect(screen.getByLabelText("Voice Profile")).toHaveAttribute("data-scrollable", "false");
    expect(screen.getByLabelText("Voice Profile")).toHaveAttribute("data-max-height", "none");
  });

  it("renders one Hebrew completed card with markdown and Hebrew language badge", () => {
    mockVoiceProfileState({
      status: { en: null, he: completeHeSlot },
      profiles: {
        en: null,
        he: {
          success: true,
          language: "he",
          content: "# פרופיל קול\n\nכתיבה בעברית.",
          metadata: { last_updated_at: "2026-05-03T12:00:00Z", age_days: 8, size_bytes: 2200 },
        },
      },
    });

    render(<VoiceProfile />);

    const card = screen.getByTestId("voice-profile-card-he");
    expect(within(card).getByText("HE")).toBeInTheDocument();
    expect(within(card).getByText(/# פרופיל קול/i)).toBeInTheDocument();
    expect(within(card).getByText(/age: 8 days/i)).toBeInTheDocument();
  });

  it("renders one Hebrew in-progress card with progress and count", () => {
    mockVoiceProfileState({
      status: { en: null, he: inProgressHeSlot },
    });

    render(<VoiceProfile />);

    const card = screen.getByTestId("voice-profile-card-he");
    expect(within(card).getByText("HE")).toBeInTheDocument();
    expect(within(card).getByText(/42 of 100 questions answered/i)).toBeInTheDocument();
    expect(within(card).getByRole("progressbar", { name: /hebrew interview progress/i })).toHaveAttribute(
      "aria-valuenow",
      "42",
    );
  });

  it("renders two stacked cards when languages have mixed states", () => {
    mockVoiceProfileState({
      status: { en: completeEnSlot, he: inProgressHeSlot },
      profiles: {
        en: {
          success: true,
          language: "en",
          content: "# English Voice\n\nComplete.",
          metadata: { last_updated_at: "2026-05-02T12:00:00Z", age_days: 14, size_bytes: 2048 },
        },
        he: null,
      },
    });

    render(<VoiceProfile />);

    expect(screen.getAllByTestId("voice-profile-language-card")).toHaveLength(2);
    expect(screen.getByTestId("voice-profile-card-en")).toHaveTextContent(/complete/i);
    expect(screen.getByTestId("voice-profile-card-he")).toHaveTextContent(/42 of 100 questions answered/i);
  });

  it("shows an amber stale banner when a completed profile is older than 180 days", () => {
    mockVoiceProfileState({
      status: {
        en: {
          ...completeEnSlot,
          about_me: {
            ...completeEnSlot.about_me,
            age_days: 181,
          },
        },
        he: null,
      },
      profiles: {
        en: {
          success: true,
          language: "en",
          content: "# English Voice\n\nNeeds refresh.",
          metadata: { last_updated_at: "2025-11-01T12:00:00Z", age_days: 181, size_bytes: 2048 },
        },
        he: null,
      },
    });

    render(<VoiceProfile />);

    expect(screen.getByRole("alert")).toHaveTextContent(/consider running \/profile update en/i);
  });
});
