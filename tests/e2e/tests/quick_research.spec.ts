/*
  filename: quick_research.spec.ts
  description: Quick Research form on /. Fills company + industry + notes, picks Haiku 4.5 model. Does NOT submit so we never burn Claude tokens. Verifies the submit button is enabled, the status text is empty pre submit, and the language picker exposes 5 locales.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("quick research form", () => {
  test("fills form, picks Haiku, and reads language picker", async ({ page }) => {
    await page.goto("/");
    await page.locator('.entry-tab[data-mode="qr"]').click();

    // Fill the form.
    await page.locator("#qr-name").fill("Test Corp");
    await page.locator("#qr-industry").fill("fintech");
    await page.locator("#qr-notes").fill("ILM tuning, ELSER, Splunk renewal in flight");

    // Pick Haiku 4.5 explicitly (value claude-haiku-4-5; default value is the empty option).
    await page.locator("#qr-model").selectOption("claude-haiku-4-5");
    await expect(page.locator("#qr-model")).toHaveValue("claude-haiku-4-5");

    // The submit button must be enabled and qr-status empty until we click submit.
    const submit = page.locator("#qr-submit");
    await expect(submit).toBeEnabled();
    const status = page.locator("#qr-status");
    await expect(status).toHaveText("");

    // Language picker has the five Elastic top-market locales.
    const langPicker = page.locator(".lang-picker");
    await expect(langPicker).toBeVisible();
    const options = langPicker.locator("option");
    expect(await options.count()).toBe(5);
    const values = await options.evaluateAll((nodes) => nodes.map((n) => (n as HTMLOptionElement).value));
    expect(values.sort()).toEqual(["de", "en", "es", "fr", "ja"]);

    // Sanity: we never submitted, so qr-status remains empty.
    await expect(status).toHaveText("");
  });
});
