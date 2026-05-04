/*
  filename: agent_builder.spec.ts
  description: /agent-builder.html smoke. Asserts the status pill flips to Live within 10s of /agent-builder/status returning, six or more suggested prompt chips render, the composer textarea + Send button wire up, and clicking New Thread clears the chat history.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("agent builder /agent-builder.html", () => {
  test("loads, shows Live pill, chips, composer, reset clears chat", async ({ page }) => {
    await page.goto("/agent-builder.html");

    // Status pill flips to Live within 10s once /agent-builder/status responds.
    const pill = page.locator("#ab-pill-status");
    await expect(pill).toHaveText("Live", { timeout: 10_000 });

    // Suggested prompts: at least six chips.
    const chips = page.locator(".ab-suggested .ab-chip");
    expect(await chips.count()).toBeGreaterThanOrEqual(6);

    // Composer + send.
    const input = page.locator("#ab-input");
    const send = page.locator("#ab-send");
    await expect(input).toBeVisible();
    await expect(send).toBeVisible();
    await expect(send).toBeEnabled();

    // Seed the chat with a fake message so the New Thread button has something to clear.
    await page.evaluate(() => {
      const chat = document.querySelector("#ab-chat");
      if (chat) {
        const div = document.createElement("div");
        div.className = "ab-msg ab-msg-user";
        div.textContent = "fake message for clear test";
        chat.appendChild(div);
      }
    });
    await expect(page.locator("#ab-chat")).toContainText("fake message for clear test");

    // Click New Thread; the reset handler swaps in the empty placeholder.
    await page.locator("#ab-reset").click();
    await expect(page.locator("#ab-chat")).not.toContainText("fake message for clear test");
    await expect(page.locator("#ab-chat")).toContainText("New thread started");
  });
});
