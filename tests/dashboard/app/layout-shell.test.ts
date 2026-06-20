import fs from "fs";
import path from "path";

describe("dashboard root shell", () => {
  it("does not mount the Airplane route control in the desktop sidebar", () => {
    const layoutPath = path.join(
      process.cwd(),
      "app",
      "layout.tsx",
    );
    const source = fs.readFileSync(layoutPath, "utf8");

    expect(source).not.toContain("components/shared/AirplanePill");
    expect(source).not.toContain("<AirplanePill");
  });
});
