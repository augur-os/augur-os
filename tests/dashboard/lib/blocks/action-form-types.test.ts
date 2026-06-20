import type { RowAction } from "@/lib/blocks/types";
import type { BlockConfig, ShowIfExpression } from "@/lib/blocks/flow-types";

describe("Action form type extensions", () => {
  it("RowAction accepts fields array", () => {
    const action: RowAction = {
      id: "edit",
      icon: "Pencil",
      label: "Edit",
      dispatch: "fire",
      fields: [
        { name: "title", label: "Title", type: "text", required: true },
      ],
      refetch: ["stats-block"],
    };
    expect(action.fields).toHaveLength(1);
    expect(action.refetch).toEqual(["stats-block"]);
  });

  it("RowAction accepts confirmText for dangerous actions", () => {
    const action: RowAction = {
      id: "delete",
      icon: "Trash",
      label: "Delete",
      dispatch: "fire",
      confirmText: "DELETE",
      fields: [],
    };
    expect(action.confirmText).toBe("DELETE");
  });

  it("BlockConfig accepts id and showIf", () => {
    const showIf: ShowIfExpression = { blockHasData: "other-block" };
    const config: BlockConfig = {
      type: "stat-grid",
      id: "my-stats",
      showIf,
    };
    expect(config.id).toBe("my-stats");
    expect(config.showIf).toEqual({ blockHasData: "other-block" });
  });

  it("ShowIfExpression supports configFlag", () => {
    const showIf: ShowIfExpression = { configFlag: "dev_mode" };
    const config: BlockConfig = { type: "markdown", showIf };
    expect(config.showIf).toEqual({ configFlag: "dev_mode" });
  });
});
