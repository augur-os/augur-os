import { injectAugurBridge } from "@/lib/artifacts/injectBridge";
test("injects the shim before </body>", () => {
  const out = injectAugurBridge("<html><body><h1>hi</h1></body></html>");
  expect(out).toContain("window.augur");
  expect(out.indexOf("window.augur")).toBeLessThan(out.indexOf("</body>"));
});
test("appends the shim when no </body> present", () => {
  const out = injectAugurBridge("<h1>fragment</h1>");
  expect(out).toContain("window.augur");
  expect(out.trim().endsWith("</script>")).toBe(true);
});
test("exposes only ask and runAction", () => {
  const out = injectAugurBridge("<body></body>");
  expect(out).toContain("ask:");
  expect(out).toContain("runAction:");
  expect(out).not.toContain("modelContext");
});
