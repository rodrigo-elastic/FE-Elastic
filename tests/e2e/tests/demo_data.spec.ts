/*
  filename: demo_data.spec.ts
  description: /demo-data.html smoke. Asserts the page lists 5 scenario cards (black-friday, credential-stuffing, noisy-microservice, gdpr-audit-timeline, supply-chain-attack), each card exposes a Seed button + the two dashboard buttons, and the underlying API returns the same five entries. Never clicks Seed (live mutation).
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { test, expect } from "@playwright/test";

test.describe("demo data /demo-data.html", () => {
  test("lists 5 scenario cards with seed + dashboard buttons", async ({ page, request }) => {
    await page.goto("/demo-data.html");

    const grid = page.locator("#dd-grid");
    await expect(grid).toBeVisible();

    // Cards hydrate from /api/v1/demo-data/scenarios. Wait for at least one card.
    const cards = grid.locator(".dd-card");
    await expect(cards.first()).toBeVisible({ timeout: 15_000 });
    expect(await cards.count()).toBe(5);

    // Each card must expose the three action buttons by label.
    for (let i = 0; i < 5; i++) {
      const card = cards.nth(i);
      await expect(card.locator("button", { hasText: "Seed scenario" })).toHaveCount(1);
      await expect(card.locator("a", { hasText: "Open [FE] dashboard" })).toHaveCount(1);
      await expect(card.locator("a", { hasText: "Open [Customer] dashboard" })).toHaveCount(1);
      // Seed button is enabled but we never click it.
      await expect(card.locator("button", { hasText: "Seed scenario" })).toBeEnabled();
    }

    // Cross check the API. Five canonical scenario ids must come back.
    const res = await request.get("/api/v1/demo-data/scenarios");
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(Array.isArray(body.scenarios)).toBe(true);
    expect(body.scenarios.length).toBe(5);
    const ids = body.scenarios.map((s: any) => s.id).sort();
    expect(ids).toEqual([
      "black-friday-outage",
      "credential-stuffing",
      "gdpr-audit-timeline",
      "noisy-microservice",
      "supply-chain-attack",
    ]);
  });
});
