import { test, expect } from "@playwright/test";

test.describe("Basic smoke", () => {
  test("homepage loads and shows health", async ({ page }) => {
    await page.route("**/api/health", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "ok",
          version: "0.2.0",
          topic_count: 3,
          total_disk_usage_bytes: 1000000,
        }),
      });
    });
    await page.goto("/");
    await expect(page.locator("text=LongNovelInsight")).toBeVisible();
  });

  test("navigation works", async ({ page }) => {
    await page.goto("/");
    await page.click("a:has-text('Topics')");
    await expect(page).toHaveURL(/\/topics/);
    await page.click("a:has-text('Providers')");
    await expect(page).toHaveURL(/\/providers/);
    await page.click("a:has-text('Dashboard')");
    await expect(page).toHaveURL(/\//);
  });

  test("topics page renders", async ({ page }) => {
    await page.route("**/api/topics**", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ topics: [] }),
      });
    });
    await page.goto("/topics");
    await expect(page.locator("text=Topics")).toBeVisible();
  });

  test("providers page renders", async ({ page }) => {
    await page.route("**/api/providers**", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ providers: [] }),
      });
    });
    await page.goto("/providers");
    await expect(page.locator("text=Providers")).toBeVisible();
  });

  test("404 page for unknown routes", async ({ page }) => {
    await page.goto("/nonexistent");
    await expect(page.locator("text=404")).toBeVisible();
  });
});
