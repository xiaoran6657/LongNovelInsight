import { test, expect } from "@playwright/test";

const TOPIC_ID = "test-topic-v4";
const WORK_ID = "test-work-1";
const WORK_ID_2 = "test-work-2";
const API_HOST = "http://127.0.0.1:8000";

function apiRoute(pathPattern: string | RegExp) {
  if (typeof pathPattern === "string") {
    return (url: URL) => url.origin === API_HOST && url.pathname === pathPattern;
  }
  return (url: URL) => url.origin === API_HOST && pathPattern.test(url.pathname + url.search);
}

async function mockV04Topic(page: Parameters<typeof test>[1]["page"]) {
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}`), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        id: TOPIC_ID, name: "v0.4 Test Topic", description: null,
        provider_id: "p1", storage_bytes: 0, status: "active",
        document: null, analysis_summary: {}, disk_usage_bytes: 0,
        created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
      }),
    });
  });

  await page.route(apiRoute("/api/topics"), (route) => {
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ topics: [] }) });
  });

  await page.route(apiRoute("/api/providers"), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ providers: [{ id: "p1", name: "P", model_name: "m", base_url: "http://m", masked_api_key: "sk-...", is_default: true }] }),
    });
  });

  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/works`), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        works: [
          { id: WORK_ID, topic_id: TOPIC_ID, title: "Book One", subtitle: null, author: "Author A", series_index: 1, description: null, status: "empty", metadata_json: null, created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z" },
          { id: WORK_ID_2, topic_id: TOPIC_ID, title: "Book Two", subtitle: null, author: null, series_index: 2, description: null, status: "empty", metadata_json: null, created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z" },
        ],
      }),
    });
  });

  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/documents/current`), (route) => {
    route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No document uploaded" }) });
  });

  await page.route(apiRoute("/api/provider-presets"), (route) => {
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ presets: [] }) });
  });

  await page.route((url) => url.origin === API_HOST && url.pathname.includes("/provider-config/effective"), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        provider_id: "p1", provider_name: "P", model_name: "m",
        max_output_tokens: 4096, thinking_mode: "disabled",
        analysis_parallelism: 3, is_ready: true,
        missing_fields: [], warnings: [],
      }),
    });
  });

  await page.route((url) => url.origin === API_HOST && url.pathname.includes("/provider-config") && !url.pathname.includes("effective"), (route) => {
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/chunks/meta`), (route) => {
    route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({ detail: "Document is not parsed" }) });
  });
}

test.describe("v0.4 Works", () => {
  test("create work form opens and closes", async ({ page }) => {
    await mockV04Topic(page);
    await page.goto(`/topics/${TOPIC_ID}`);
    await page.waitForLoadState("networkidle");
    await page.locator("button", { hasText: "Works" }).click();
    await page.locator("button", { hasText: "+ New Work" }).click();
    await expect(page.locator('input[placeholder="Title (required)"]')).toBeVisible();
    await page.locator("button", { hasText: "Cancel" }).click();
    await expect(page.locator('input[placeholder="Title (required)"]')).not.toBeVisible();
  });

  test("edit work form opens and closes", async ({ page }) => {
    await mockV04Topic(page);
    await page.goto(`/topics/${TOPIC_ID}`);
    await page.waitForLoadState("networkidle");
    await page.locator("button", { hasText: "Works" }).click();
    await page.locator("button", { hasText: "Edit" }).first().click();
    await expect(page.locator('input[placeholder="Title"]')).toBeVisible();
    await page.locator("button", { hasText: "Cancel" }).click();
    await expect(page.locator('input[placeholder="Title"]')).not.toBeVisible();
  });

  test("delete non-empty work shows 409", async ({ page }) => {
    await mockV04Topic(page);
    await page.route(apiRoute(`/api/topics/${TOPIC_ID}/works`), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          works: [
            { id: WORK_ID, topic_id: TOPIC_ID, title: "Parsed Book", subtitle: null, author: null, series_index: 1, description: null, status: "parsed", metadata_json: null, created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z" },
          ],
        }),
      });
    });
    await page.route(apiRoute(`/api/works/${WORK_ID}`), (route) => {
      if (route.request().method() === "DELETE") {
        route.fulfill({
          status: 409, contentType: "application/json",
          body: JSON.stringify({ detail: "Deleting non-empty works is not supported in v0.4.0; remove the Topic or reset data manually." }),
        });
      } else {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
      }
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await page.waitForLoadState("networkidle");
    await page.locator("button", { hasText: "Works" }).click();
    page.on("dialog", (dialog) => dialog.accept());
    await page.locator("button", { hasText: "×" }).first().click();
    await expect(page.locator("text=not supported")).toBeVisible();
  });

  test("create work sends correct POST body", async ({ page }) => {
    await mockV04Topic(page);
    let requestBody: Record<string, unknown> = {};
    await page.route(apiRoute(`/api/topics/${TOPIC_ID}/works`), (route, request) => {
      if (request.method() === "POST") {
        requestBody = request.postDataJSON() || {};
      }
      route.fulfill({
        status: 201, contentType: "application/json",
        body: JSON.stringify({
          id: "new-work", topic_id: TOPIC_ID, title: requestBody.title || "Untitled",
          subtitle: null, author: null, series_index: null, description: null,
          status: "empty", metadata_json: null,
          created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await page.waitForLoadState("networkidle");
    await page.locator("button", { hasText: "Works" }).click();
    await page.locator("button", { hasText: "+ New Work" }).click();
    await page.fill('input[placeholder="Title (required)"]', "Test Novel");
    await page.fill('input[placeholder="Author"]', "Author X");
    await page.fill('input[placeholder="Series #"]', "1");
    await page.locator("button", { hasText: "Create Work" }).click();
    await page.waitForTimeout(500);

    expect(requestBody.title).toBe("Test Novel");
    expect(requestBody.author).toBe("Author X");
    expect(requestBody.series_index).toBe(1);
  });

  test("edit work sends PATCH with correct body", async ({ page }) => {
    await mockV04Topic(page);
    let patchBody: Record<string, unknown> = {};
    await page.route(apiRoute(`/api/works/${WORK_ID}`), (route, request) => {
      if (request.method() === "PATCH") {
        patchBody = request.postDataJSON() || {};
      }
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          id: WORK_ID, topic_id: TOPIC_ID, title: "Updated", subtitle: null, author: null,
          series_index: null, description: null, status: "empty", metadata_json: null,
          created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await page.waitForLoadState("networkidle");
    await page.locator("button", { hasText: "Works" }).click();
    await page.locator("button", { hasText: "Edit" }).first().click();
    await page.fill('input[placeholder="Title"]', "Updated Title");
    await page.fill('input[placeholder="Author"]', "New Author");
    await page.locator("button", { hasText: "Save" }).click();
    await page.waitForTimeout(500);

    expect(patchBody.title).toBe("Updated Title");
    expect(patchBody.author).toBe("New Author");
  });

  test("delete empty work calls DELETE and succeeds", async ({ page }) => {
    await mockV04Topic(page);
    let deleteCalled = false;
    await page.route(apiRoute(`/api/works/${WORK_ID}`), (route, request) => {
      if (request.method() === "DELETE") {
        deleteCalled = true;
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ deleted: true }) });
      } else {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
      }
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await page.waitForLoadState("networkidle");
    await page.locator("button", { hasText: "Works" }).click();
    page.on("dialog", (dialog) => dialog.accept());
    await page.locator("button", { hasText: "×" }).first().click();
    await page.waitForTimeout(500);

    expect(deleteCalled).toBe(true);
  });
});
