import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { TabbedSectionRenderer } from "@/components/plugin/sections/TabbedSectionRenderer";
import { fetchFromSource } from "@/lib/plugin-schema/data-fetcher";

jest.mock("@/lib/plugin-schema/data-fetcher", () => ({
  fetchFromSource: jest.fn(),
}));

const mockedFetchFromSource = jest.mocked(fetchFromSource);

describe("TabbedSectionRenderer", () => {
  beforeEach(() => {
    mockedFetchFromSource.mockReset();
    window.history.replaceState(null, "", "/life/finance");
  });

  it("renders object-shaped summary payloads as a single tab item", async () => {
    mockedFetchFromSource.mockResolvedValue({
      success: true,
      data: { netWorth: 62200, savingsRate: 73.3 },
    });
    const renderContent = jest.fn(() => null);

    render(
      <TabbedSectionRenderer
        sectionId="finance-tabs"
        tabs={[{ id: "summary", label: "Summary", source: "finance-summary" }]}
        renderContent={renderContent}
      />,
    );

    await waitFor(() => {
      expect(renderContent).toHaveBeenCalledWith(
        [{ netWorth: 62200, savingsRate: 73.3 }],
        "summary",
      );
    });
  });

  it("unwraps nested collection payloads for non-summary tabs", async () => {
    mockedFetchFromSource.mockImplementation(async (source) => {
      if (source === "finance-summary") {
        return { success: true, data: { netWorth: 62200 } };
      }

      if (source === "finance-transactions") {
        return {
          success: true,
          data: {
            transactions: [
              { description: "Salary", amount: 4500 },
              { description: "Groceries", amount: 85.5 },
            ],
            total: 2,
          },
        };
      }

      throw new Error(`Unexpected source: ${source}`);
    });

    const user = userEvent.setup();
    const renderContent = jest.fn(() => null);

    render(
      <TabbedSectionRenderer
        sectionId="finance-tabs"
        tabs={[
          { id: "summary", label: "Summary", source: "finance-summary" },
          { id: "transactions", label: "Transactions", source: "finance-transactions" },
        ]}
        renderContent={renderContent}
      />,
    );

    await waitFor(() => {
      expect(renderContent).toHaveBeenCalledWith([{ netWorth: 62200 }], "summary");
    });
    await user.click(screen.getByRole("button", { name: "Transactions" }));

    await waitFor(() => {
      expect(renderContent).toHaveBeenCalledWith(
        [
          { description: "Salary", amount: 4500 },
          { description: "Groceries", amount: 85.5 },
        ],
        "transactions",
      );
    });
  });
});
