import { expect, test } from "@playwright/test";

test("shows real mission evidence across all architecture surfaces", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Mission architecture/ })).toBeVisible();
  await expect(page.getByText("Verified", { exact: true })).toBeVisible();
  for (const name of ["TF & clock", "Topic / QoS", "World model", "Goal & policy", "Plan trace", "Skill timeline", "Safety & faults", "Sensor / control latency", "Replay & evidence"]) {
    const control = page.getByRole("button", { name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) });
    await control.click();
    await expect(control).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByText("RECORD SHA-256")).toBeVisible();
  const viewport = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
  expect(viewport.scroll).toBeLessThanOrEqual(viewport.client);
});

test("replays a synthetic mission and keeps focus visible", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const replay = page.getByRole("button", { name: "Replay synthetic mission" });
  await replay.focus();
  await expect(replay).toBeFocused();
  await replay.click();
  await expect(page.getByRole("heading", { name: "Replay & evidence" })).toBeVisible();
  await expect(page.getByText("RECORD SHA-256")).toBeVisible();
});
