/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import UnifiedActionsFab from "@/features/components/UnifiedActionsFab";

const mockOpenChat = jest.fn();

jest.mock("@/lib/stores/chatStore", () => ({
  useChatStore: () => ({
    isOpen: false,
    cliProcess: null,
    openChat: mockOpenChat,
  }),
}));

describe("UnifiedActionsFab", () => {
  beforeEach(() => {
    mockOpenChat.mockReset();
  });

  it("is hidden on desktop breakpoints so desktop relies on the action bar", () => {
    render(<UnifiedActionsFab />);

    const fab = screen.getByRole("button", { name: "Open chat" });
    expect(fab.className).toContain("md:hidden");
  });

  it("opens IDE chat when pressed", () => {
    const dispatchSpy = jest.spyOn(window, "dispatchEvent");
    render(<UnifiedActionsFab />);

    fireEvent.click(screen.getByRole("button", { name: "Open chat" }));

    expect(mockOpenChat).toHaveBeenCalledWith({ mode: "ide" });
    expect(dispatchSpy).toHaveBeenCalled();
    dispatchSpy.mockRestore();
  });
});
