/*
  filename: dashboard.spec.ts
  description: Smoke test for the FE Copilot dashboard at /. Asserts the H1, four stat cards (companies, upcoming, past, briefs) populate from the API, the persistent left rail exposes >=5 page links + 8 tool links, and the Quick Research entry tab is the active form.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("dashboard /", () => {
  test("loads, renders stats, sidebar, and QR tab", async ({ page }) => {
    await page.goto("/");

    // H1 with the two spans concatenated.
    const h1 = page.locator("main h1").first();
    await expect(h1).toContainText("Three agents.");
    await expect(h1).toContainText("One pre-meeting flow.");

    // Stat cards must hydrate to a non placeholder value within 10s.
    const statIds = ["#stat-companies", "#stat-upcoming", "#stat-past", "#stat-briefs"];
    for (const sel of statIds) {
      const node = page.locator(sel);
      await expect(node).toBeVisible();
      await expect(node).not.toHaveText("-", { timeout: 10_000 });
      const txt = (await node.textContent())?.trim() || "";
      expect(txt.length).toBeGreaterThan(0);
    }

    // Persistent rail. Page links live under .tools-sidebar > .tools-nav:nth-child(2).
    const sidebar = page.locator(".tools-sidebar");
    await expect(sidebar).toBeVisible();
    const pageLinks = sidebar.locator(".tools-nav-pill.page-link");
    expect(await pageLinks.count()).toBeGreaterThanOrEqual(5);
    // Tool links are the non page-link pills.
    const toolLinks = sidebar.locator(".tools-nav-pill:not(.page-link)");
    expect(await toolLinks.count()).toBe(8);

    // QR is the default entry mode. Clicking it should keep #entry-qr visible.
    const qrTab = page.locator('.entry-tab[data-mode="qr"]');
    await qrTab.click();
    await expect(page.locator("#entry-qr")).toBeVisible();
    await expect(page.locator("#qr-form")).toBeVisible();
    await expect(page.locator("#qr-name")).toBeVisible();
  });
});
