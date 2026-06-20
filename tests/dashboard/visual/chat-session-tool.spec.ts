import { test, expect } from "@playwright/test";

test("update-chat-session is callable from a normal dashboard page context", async ({
  page,
}) => {
  await page.goto("/workspace/memory", { waitUntil: "domcontentloaded" });

  const response = await page.request.post("/api/mcp/tool", {
    headers: {
      referer: "http://localhost:3000/workspace/memory",
      "content-type": "application/json",
    },
    data: {
      tool: "update-chat-session",
      args: {
        isActive: true,
        mode: "ide",
        status: "idle",
        context: { page: "/workspace/memory" },
      },
    },
  });

  expect(response.ok()).toBe(true);
  const body = await response.json();
  expect(body).toMatchObject({
    isActive: true,
    mode: "ide",
  });
});
