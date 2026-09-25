import { defineConfig, devices } from "@playwright/test";

const python = process.env.EMBODIED_PYTHON || "python";
const root = process.env.EMBODIED_PROJECT_ROOT || "../..";

export default defineConfig({
  testDir: "./tests",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  workers: 2,
  use: { baseURL: "http://127.0.0.1:8162", trace: "retain-on-failure" },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["iPhone 13"] } },
  ],
  webServer: [
    { command: `"${python}" -m embodied.api`, cwd: root, url: "http://127.0.0.1:8161/healthz", reuseExistingServer: !process.env.CI, timeout: 60_000, env: { PYTHONPATH: "src" } },
    { command: "npm run start", url: "http://127.0.0.1:8162", reuseExistingServer: !process.env.CI, timeout: 120_000 },
  ],
});
