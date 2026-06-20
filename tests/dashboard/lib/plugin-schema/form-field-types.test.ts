import type { FormField } from "@/lib/plugin-schema/types";

describe("FormField type extensions", () => {
  it("accepts file type with accept property", () => {
    const field: FormField = {
      name: "upload",
      label: "Upload",
      type: "file",
      required: true,
      accept: [".csv", ".xlsx"],
    };
    expect(field.type).toBe("file");
    expect(field.accept).toEqual([".csv", ".xlsx"]);
  });

  it("accepts toggle type", () => {
    const field: FormField = {
      name: "enabled",
      label: "Enabled",
      type: "toggle",
      defaultValue: false,
    };
    expect(field.type).toBe("toggle");
  });
});
