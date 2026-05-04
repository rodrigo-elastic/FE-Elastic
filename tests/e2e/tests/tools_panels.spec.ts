/*
  filename: tools_panels.spec.ts
  description: /tools.html smoke. Confirms the eight collapsible tool panels render (POC, SPL to ES|QL, Compliance, Cost, Capacity, Stack, Code, Troubleshoot), the persistent rail shows 8 tool links with the 08 ordinal on the last entry, and the Troubleshoot panel mounts its required textarea + Diagnose button.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("tools page /tools.html", () => {
  test("renders 8 panels, 8 sidebar tools, troubleshoot composer", async ({ page }) => {
    await page.goto("/tools.html");

    // 8 collapsible tool panels.
    const panels = page.locator("details.tool-panel");
    expect(await panels.count()).toBe(8);
    const expectedIds = [
      "tool-poc",
      "tool-spl",
      "tool-compliance",
      "tool-cost",
      "tool-capacity",
      "tool-stack",
      "tool-code",
      "tool-troubleshoot",
    ];
    for (const id of expectedIds) {
      await expect(page.locator(`#${id}`)).toBeVisible();
    }

    // Sidebar tools count = 8, last ordinal is 08.
    const sidebar = page.locator(".tools-sidebar");
    const toolLinks = sidebar.locator(".tools-nav-pill:not(.page-link)");
    expect(await toolLinks.count()).toBe(8);
    const nums = await sidebar.locator(".tools-nav-num").allTextContents();
    expect(nums).toContain("08");

    // Click the Troubleshoot panel via the rail; it should open and expose the textarea + Diagnose button.
    await page.locator('.tools-sidebar a[href$="#tool-troubleshoot"], .tools-sidebar a[href="#tool-troubleshoot"]').first().click();
    const ts = page.locator("#tool-troubleshoot");
    await expect(ts).toHaveAttribute("open", "");
    await expect(ts.locator("#ts-error")).toBeVisible();
    await expect(ts.locator('button[type="submit"]')).toContainText("Diagnose");
  });
});
