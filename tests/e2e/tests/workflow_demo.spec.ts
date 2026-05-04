/*
  filename: workflow_demo.spec.ts
  description: /workflow-demo.html smoke. Confirms the status panel hydrates with rule_id and connector_id fields, the Sync Workflow + Fire Demo Transcript buttons mount, and the Recent Webhook Fires container renders even when empty. Does not click Fire (live mutation).
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("workflow demo /workflow-demo.html", () => {
  test("loads, status hydrates, control buttons present, fires list renders", async ({ page }) => {
    await page.goto("/workflow-demo.html");

    // Status panel renders rule_id and connector_id keys (regardless of registered/not).
    const status = page.locator("#wf-status");
    await expect(status).toBeVisible();
    await expect(status).toContainText("Rule id", { timeout: 15_000 });
    await expect(status).toContainText("Connector id");

    // Buttons by id, with stable text labels from workflow-demo.html.
    await expect(page.locator("#wf-sync")).toBeVisible();
    await expect(page.locator("#wf-sync")).toContainText("Sync workflow");
    await expect(page.locator("#wf-fire")).toBeVisible();
    await expect(page.locator("#wf-fire")).toContainText("Fire demo transcript");

    // Recent fires panel renders. May be empty (wf-empty placeholder) or populated.
    const fires = page.locator("#wf-fires");
    await expect(fires).toBeVisible();
    const placeholder = fires.locator(".wf-empty");
    const fireRows = fires.locator(".wf-fire");
    const placeholderCount = await placeholder.count();
    const rowCount = await fireRows.count();
    expect(placeholderCount + rowCount).toBeGreaterThan(0);
  });
});
