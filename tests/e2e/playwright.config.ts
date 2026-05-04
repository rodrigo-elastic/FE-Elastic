/*
  filename: playwright.config.ts
  description: Playwright config for FE Copilot e2e suite. Targets the running backend on 127.0.0.1:8123, chromium-only for speed, list reporter, 4 workers, 60s per test.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  reporter: "list",
  workers: 4,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: "http://127.0.0.1:8123",
    viewport: { width: 1440, height: 2400 },
    actionTimeout: 10_000,
    navigationTimeout: 20_000,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 2400 } },
    },
  ],
});
