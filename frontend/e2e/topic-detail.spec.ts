import { test, expect } from "@playwright/test";

const TOPIC_ID = "test-topic-1";
const PROVIDER_ID = "test-provider-1";
const API_HOST = "http://127.0.0.1:8000";

/** Match only requests targeting the API backend, not Vite dev server. */
function apiRoute(pathPattern: string | RegExp) {
  if (typeof pathPattern === "string") {
    return (url: URL) => url.origin === API_HOST && url.pathname === pathPattern;
  }
  return (url: URL) => url.origin === API_HOST && pathPattern.test(url.pathname + url.search);
}

// ── Tests ──

test.describe("Topic detail – provider config override", () => {
  test("saving max tokens persists value in form (no stale cache rollback)", async ({ page }) => {
    let storedMaxTokens = 2048;

    // Catch-all: fulfill any unhandled API call so nothing leaks to a real backend
    await page.route((url) => url.origin === API_HOST, (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
    });

    // Topic detail
    await page.route(apiRoute("/api/topics/test-topic-1"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          id: TOPIC_ID, name: "Test Topic", description: null,
          provider_id: PROVIDER_ID, storage_bytes: 0, status: "active",
          document: null, analysis_summary: {}, disk_usage_bytes: 0,
          created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
        }),
      });
    });

    // Topics list
    await page.route(apiRoute("/api/topics"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ topics: [] }) });
    });

    // Providers
    await page.route(apiRoute("/api/providers"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          providers: [{
            id: PROVIDER_ID, name: "Test Provider", provider_type: "deepseek",
            base_url: "https://api.deepseek.com", model_name: "deepseek-chat",
            context_window: 65536, max_output_tokens: 8192, temperature: 0.1,
            is_default: true, masked_api_key: "sk-***",
            created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
          }],
        }),
      });
    });

    // Effective config
    await page.route(apiRoute("/api/topics/test-topic-1/provider-config/effective"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          provider_id: PROVIDER_ID, provider_name: "Test Provider",
          provider_key: "deepseek", base_url: "https://api.deepseek.com",
          model_name: "deepseek-chat", context_window: 65536,
          max_output_tokens: 8192, temperature: 0.1,
          thinking_mode: "disabled", reasoning_effort: null,
          analysis_parallelism: 3, supports_json_output: true,
          supports_thinking: true, is_ready: true, missing_fields: [], warnings: [],
        }),
      });
    });

    // Provider presets
    await page.route(apiRoute("/api/provider-presets"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ presets: [] }) });
    });

    // No document
    await page.route(apiRoute("/api/topics/test-topic-1/documents/current"), (route) => {
      route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "No document" }) });
    });

    // Stored provider config — mutable via PUT
    await page.route(apiRoute("/api/topics/test-topic-1/provider-config"), (route) => {
      if (route.request().method() === "PUT") {
        const body = JSON.parse(route.request().postData() || "{}");
        if (body.max_output_tokens_override != null) storedMaxTokens = body.max_output_tokens_override;
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
        return;
      }
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          config: {
            topic_id: TOPIC_ID,
            max_output_tokens_override: storedMaxTokens,
            model_name_override: null,
            temperature_override: null,
            thinking_mode_override: null,
            analysis_parallelism_override: null,
          },
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);

    // Wait for the config form to render
    await expect(page.getByLabel("Max tokens value")).toBeVisible({ timeout: 10000 });

    const input = page.getByLabel("Max tokens value");
    await expect(input).toHaveValue("2048");

    // Change to 4096 (TokenRangeSlider commits on blur)
    await input.fill("4096");
    await input.blur();

    // Save — register the response listener before the click so we never miss it
    const saveBtn = page.getByRole("button", { name: "Save" });
    await expect(saveBtn).toBeVisible();

    const putResp = page.waitForResponse((resp) =>
      resp.url().includes("/provider-config") && resp.request().method() === "PUT"
    );
    await saveBtn.click();
    await putResp;
    await page.waitForLoadState("networkidle");

    // Should still show 4096, not rolled back to stale 2048
    await expect(page.getByLabel("Max tokens value")).toHaveValue("4096");
  });
});

test.describe("Topic detail – chapter range validation", () => {
  test("chapter range out of bounds disables Run button", async ({ page }) => {
    // Catch-all
    await page.route((url) => url.origin === API_HOST, (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
    });

    // Topic detail
    await page.route(apiRoute("/api/topics/test-topic-1"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          id: TOPIC_ID, name: "Test Topic", description: null,
          provider_id: PROVIDER_ID, storage_bytes: 0, status: "active",
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
        body: JSON.stringify({
          providers: [{
            id: PROVIDER_ID, name: "Test Provider", provider_type: "deepseek",
            base_url: "https://api.deepseek.com", model_name: "deepseek-chat",
            context_window: 65536, max_output_tokens: 8192, temperature: 0.1,
            is_default: true, masked_api_key: "sk-***",
            created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
          }],
        }),
      });
    });

    await page.route(apiRoute("/api/topics/test-topic-1/provider-config/effective"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          provider_id: PROVIDER_ID, provider_name: "Test Provider",
          provider_key: "deepseek", base_url: "https://api.deepseek.com",
          model_name: "deepseek-chat", context_window: 65536,
          max_output_tokens: 8192, temperature: 0.1,
          thinking_mode: "disabled", reasoning_effort: null,
          analysis_parallelism: 3, supports_json_output: true,
          supports_thinking: true, is_ready: true, missing_fields: [], warnings: [],
        }),
      });
    });

    await page.route(apiRoute("/api/provider-presets"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ presets: [] }) });
    });

    // Parsed document
    await page.route(apiRoute("/api/topics/test-topic-1/documents/current"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          id: "doc-1", topic_id: TOPIC_ID,
          original_filename: "test.txt", stored_filename: "test.txt",
          file_type: "text/plain", content_type: null, encoding: "utf-8",
          file_size_bytes: 10000, char_count: 8000, storage_path: "/tmp/test.txt",
          status: "parsed", created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
        }),
      });
    });

    // Stored provider config
    await page.route(apiRoute("/api/topics/test-topic-1/provider-config"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          config: {
            topic_id: TOPIC_ID,
            max_output_tokens_override: null,
            model_name_override: null,
            temperature_override: null,
            thinking_mode_override: null,
            analysis_parallelism_override: null,
          },
        }),
      });
    });

    // Chunks meta: 3 chapters (indices 0-2), 100 chunks (indices 0-99)
    await page.route(apiRoute("/api/topics/test-topic-1/chunks/meta"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          topic_id: TOPIC_ID, document_id: "doc-1",
          chunk_count: 100, chapter_count: 3, total_chars: 200000,
          estimated_tokens: 100000,
          first_chunk_index: 0, last_chunk_index: 99,
          first_global_chunk_index: 0, last_global_chunk_index: 99,
          chunks_by_chapter: [
            { chapter_index: 0, title: "Ch 1", chunk_count: 30, char_count: 60000, estimated_tokens: 30000 },
            { chapter_index: 1, title: "Ch 2", chunk_count: 40, char_count: 80000, estimated_tokens: 40000 },
            { chapter_index: 2, title: "Ch 3", chunk_count: 30, char_count: 60000, estimated_tokens: 30000 },
          ],
        }),
      });
    });

    // Register the response listener before goto so it catches any early responses
    const chunksMetaResp = page.waitForResponse((resp) => resp.url().includes("/chunks/meta") && resp.status() === 200);
    await page.goto(`/topics/${TOPIC_ID}`);
    await chunksMetaResp;
    await page.waitForTimeout(500);

    // Wait for analysis panel heading
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Select "Range" analysis mode
    await page.getByLabel("Range").check();

    // Select chapter-based range
    await page.getByLabel("By chapter index").check();

    // Enter out-of-bounds chapter (max valid index is 2)
    await page.getByLabel("Chapter start:").fill("10");

    // Run button should be disabled
    await expect(page.getByRole("button", { name: "Start v2 analysis run" })).toBeDisabled();

    // Out-of-range warning should be visible
    await expect(page.getByText("Start out of range")).toBeVisible();
  });
});
