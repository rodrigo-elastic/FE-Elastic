/*
  filename: meeting_northwind.spec.ts
  description: /meeting.html?id=northwind-mtg-prev-001 smoke. Verifies the meeting title contains Northwind Pay, the four Kibana style tabs (Brief / Post / Live / Context) are wired, each tab swap reveals the matching panel, the Field Assistant mini panel renders inside the Brief tab, and the Post tab exposes >=4 suggested prompt buttons via the Field Assistant.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("meeting page northwind-mtg-prev-001", () => {
  test("loads, swaps tabs, renders Field Assistant + suggestions", async ({ page }) => {
    await page.goto("/meeting.html?id=northwind-mtg-prev-001");

    // Title hydrates from the API.
    const title = page.locator("#meeting-title");
    await expect(title).toContainText("Northwind", { timeout: 15_000 });

    // Four tabs visible.
    const tabs = page.locator(".tabs .tab");
    expect(await tabs.count()).toBe(4);
    for (const key of ["brief", "post", "live", "context"]) {
      await expect(page.locator(`.tab[data-tab="${key}"]`)).toBeVisible();
    }

    // Click each tab and assert the matching panel is no longer hidden.
    for (const key of ["post", "live", "context", "brief"]) {
      await page.locator(`.tab[data-tab="${key}"]`).click();
      await expect(page.locator(`#panel-${key}`)).toBeVisible();
    }

    // Brief tab is currently active. The Field Assistant mini panel mounts into #abm-brief.
    await page.locator('.tab[data-tab="brief"]').click();
    const briefAssistant = page.locator("#abm-brief");
    await expect(briefAssistant).toBeVisible({ timeout: 15_000 });
    await expect(briefAssistant.locator(".abm-title")).toContainText("Field Assistant");

    // Post tab: the abm-post Field Assistant exposes a row of suggested prompt chips.
    await page.locator('.tab[data-tab="post"]').click();
    const postAssistant = page.locator("#abm-post");
    await expect(postAssistant).toBeVisible({ timeout: 15_000 });
    const chips = postAssistant.locator(".abm-chip");
    expect(await chips.count()).toBeGreaterThanOrEqual(4);
  });
});
