/*
  filename: fe_brain.spec.ts
  description: /fe-brain.html smoke. Status pill flips to Live, composer + Send + suggested chips render, then we click a suggested chip and submit. We wait up to 60s for either the answer card OR the friendly error block to surface; either outcome is acceptable so we never block the suite on a slow corpus.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("fe brain /fe-brain.html", () => {
  test("loads, runs a docs query, gracefully tolerates slow / empty corpus", async ({ page }) => {
    await page.goto("/fe-brain.html");

    // Status pill flips to Live.
    const pill = page.locator("#fb-pill-status");
    await expect(pill).toHaveText("Live", { timeout: 10_000 });

    // Composer + send + suggested chips.
    await expect(page.locator("#fb-input")).toBeVisible();
    await expect(page.locator("#fb-send")).toBeVisible();
    const chips = page.locator(".ab-suggested .ab-chip");
    expect(await chips.count()).toBeGreaterThanOrEqual(3);

    // Click the first suggested chip; the page populates the composer and auto fires search().
    await chips.first().click();
    await expect(page.locator("#fb-input")).not.toHaveValue("");

    // Either the answer card (.fb-answer) or the friendly error (.fb-error) must appear.
    // The loading panel (.fb-loading) is acceptable mid flight but should resolve in <60s.
    const answer = page.locator(".fb-answer");
    const err = page.locator(".fb-error");
    await expect(answer.or(err)).toBeVisible({ timeout: 55_000 });
  });
});
