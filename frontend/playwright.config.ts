import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  timeout: 90000,
  workers: 1,
  expect: { timeout: 15000 },
  use: {
    baseURL: "http://127.0.0.1:5174",
    headless: true,
    trace: "off",
    screenshot: "off",
  },
  reporter: "list",
});
