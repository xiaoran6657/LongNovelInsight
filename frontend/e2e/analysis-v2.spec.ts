import { test, expect } from "@playwright/test";

const TOPIC_ID = "test-topic-1";
const PROVIDER_ID = "test-provider-1";
const RUN_ID = "run-test-001";
const API_HOST = "http://127.0.0.1:8000";

function apiRoute(pathPattern: string | RegExp) {
  if (typeof pathPattern === "string") {
    return (url: URL) => url.origin === API_HOST && url.pathname === pathPattern;
  }
  return (url: URL) => url.origin === API_HOST && pathPattern.test(url.pathname + url.search);
}

/** aria-label-based selector for the v2 analysis run button. */
const RUN_BTN = { name: "Start v2 analysis run" };

/** aria-label-based selector for the cancel button. */
const CANCEL_BTN = { name: "Cancel current analysis run" };

/** Shared mocks for a parsed topic with a bound provider ready for v2 analysis. */
async function mockParsedTopic(page: Parameters<typeof test>[1]["page"]) {
  // Catch-all for unhandled API calls
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

  // Providers list
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

  // Effective provider config
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

  // Chunks meta
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
}

// ── Tests ──

test.describe("Analysis v2 – mode selection", () => {
  test("renders all four analysis modes", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // All four modes should be visible
    await expect(page.getByLabel("Preview")).toBeVisible();
    await expect(page.getByLabel("Range")).toBeVisible();
    await expect(page.getByLabel("Full")).toBeVisible();
    await expect(page.getByLabel("Incremental")).toBeVisible();

    // Incremental should be disabled (no previous run)
    await expect(page.getByLabel("Incremental")).toBeDisabled();
  });

  test("preview mode shows limit chunks input", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Preview should be selected by default
    await expect(page.getByLabel("Preview")).toBeChecked();

    // Limit chunks input should be visible in the v2 AnalysisModeSelector
    // (LegacyAnalysisPanel also has one; both default to different values)
    const limitInput = page.getByRole("spinbutton", { name: /Limit chunks:/ }).first();
    await expect(limitInput).toBeVisible();
  });

  test("full mode shows confirmation before running", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Switch to Full
    await page.getByLabel("Full").check();

    // Click Run — should show confirmation, not immediately create a run
    await page.getByRole("button", RUN_BTN).click();

    // Confirmation dialog should appear
    await expect(page.getByText("Confirm full analysis of ALL 100 chunks?")).toBeVisible();
    await expect(page.getByRole("button", { name: "Confirm full analysis of all chunks" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();

    // Cancel should hide confirmation
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(page.getByText("Confirm full analysis of ALL 100 chunks?")).not.toBeVisible();
  });
});

test.describe("Analysis v2 – create and monitor run", () => {
  test("creating a run shows status display with progress", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      if (route.request().method() === "POST") {
        route.fulfill({
          status: 201, contentType: "application/json",
          body: JSON.stringify({
            run: {
              id: RUN_ID, topic_id: TOPIC_ID, mode: "preview",
              status: "pending", progress_total: 100,
            },
            status_url: `/api/analysis/runs/${RUN_ID}`,
          }),
        });
        return;
      }
      // Return list with the run (so History panel renders it too)
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [{
            id: RUN_ID, mode: "preview", status: "running",
            extraction_succeeded: 3, extraction_failed: 0,
            merge_succeeded: 0, merge_failed: 0,
            total_tokens: 15000, model_used: "deepseek-chat",
            started_at: "2025-01-01T00:00:00Z", finished_at: null,
            created_at: "2025-01-01T00:00:00Z",
          }],
        }),
      });
    });

    // Run detail (polling) — running, then succeeds after 3 polls
    let pollCount = 0;
    await page.route(apiRoute(`/api/analysis/runs/${RUN_ID}`), (route) => {
      pollCount++;
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          run: {
            id: RUN_ID, topic_id: TOPIC_ID, mode: "preview",
            status: pollCount >= 3 ? "succeeded" : "running",
            progress_current: pollCount >= 3 ? 100 : pollCount * 30,
            progress_total: 100,
            extraction_total: 5, extraction_succeeded: pollCount >= 3 ? 5 : pollCount,
            extraction_failed: 0,
            merge_total: 6, merge_succeeded: pollCount >= 3 ? 6 : 0,
            merge_failed: 0,
            final_total: 6, final_succeeded: pollCount >= 3 ? 6 : 0,
            final_failed: 0,
            total_tokens: 25000, model_used: "deepseek-chat",
            error_message: null,
            started_at: "2025-01-01T00:00:00Z", finished_at: pollCount >= 3 ? "2025-01-01T00:05:00Z" : null,
          },
          extractions: [],
          merge: { total: 6, succeeded: pollCount >= 3 ? 6 : 0, failed: 0, outputs: [], warnings: [] },
          final: { total: 6, succeeded: pollCount >= 3 ? 6 : 0, failed: 0, outputs: [] },
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Create run
    await page.getByRole("button", RUN_BTN).click();
    await page.waitForTimeout(500);

    // Should see status display
    await expect(page.getByText("Polling...")).toBeVisible({ timeout: 10000 });

    // Cancel button should be visible while running
    await expect(page.getByRole("button", CANCEL_BTN)).toBeVisible();

    // Stage progress bars should appear (use exact match to avoid duplicates)
    await expect(page.getByText("Overall Progress")).toBeVisible();
    await expect(page.getByText("Extraction", { exact: true })).toBeVisible();
  });

  test("cancel button stops a running analysis", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      if (route.request().method() === "POST") {
        route.fulfill({
          status: 201, contentType: "application/json",
          body: JSON.stringify({
            run: { id: RUN_ID, topic_id: TOPIC_ID, mode: "preview", status: "pending", progress_total: 100 },
            status_url: `/api/analysis/runs/${RUN_ID}`,
          }),
        });
        return;
      }
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    // Run detail — running state
    await page.route(apiRoute(`/api/analysis/runs/${RUN_ID}`), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          run: {
            id: RUN_ID, topic_id: TOPIC_ID, mode: "preview",
            status: "running", progress_current: 30, progress_total: 100,
            extraction_total: 5, extraction_succeeded: 2, extraction_failed: 0,
            merge_total: 6, merge_succeeded: 0, merge_failed: 0,
            final_total: 6, final_succeeded: 0, final_failed: 0,
            total_tokens: 8000, model_used: "deepseek-chat",
            error_message: null, started_at: "2025-01-01T00:00:00Z", finished_at: null,
          },
          extractions: [],
          merge: { total: 6, succeeded: 0, failed: 0, outputs: [], warnings: [] },
          final: { total: 6, succeeded: 0, failed: 0, outputs: [] },
        }),
      });
    });

    // Cancel endpoint
    await page.route(apiRoute(`/api/analysis/runs/${RUN_ID}/cancel`), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ run: { id: RUN_ID, status: "cancelled" } }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Create run
    await page.getByRole("button", RUN_BTN).click();
    await expect(page.getByText("Polling...")).toBeVisible({ timeout: 5000 });

    // Click cancel and verify the cancel POST was sent
    const cancelResp = page.waitForResponse(
      (resp) => resp.url().includes("/cancel") && resp.request().method() === "POST"
    );
    await page.getByRole("button", CANCEL_BTN).click();
    await cancelResp;
  });
});

test.describe("Analysis v2 – run history", () => {
  test("displays run history list with status badges", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [
            {
              id: "run-001", mode: "full", status: "succeeded",
              extraction_succeeded: 100, extraction_failed: 0,
              merge_succeeded: 6, merge_failed: 0,
              total_tokens: 120000, model_used: "deepseek-chat",
              started_at: "2025-05-20T10:00:00Z", finished_at: "2025-05-20T10:30:00Z",
              created_at: "2025-05-20T10:00:00Z",
            },
            {
              id: "run-002", mode: "preview", status: "partial_success",
              extraction_succeeded: 3, extraction_failed: 2,
              merge_succeeded: 4, merge_failed: 2,
              total_tokens: 15000, model_used: "deepseek-chat",
              started_at: "2025-05-21T14:00:00Z", finished_at: "2025-05-21T14:05:00Z",
              created_at: "2025-05-21T14:00:00Z",
            },
            {
              id: "run-003", mode: "range", status: "failed",
              extraction_succeeded: 0, extraction_failed: 10,
              merge_succeeded: 0, merge_failed: 6,
              total_tokens: 5000, model_used: null,
              started_at: "2025-05-22T09:00:00Z", finished_at: "2025-05-22T09:01:00Z",
              created_at: "2025-05-22T09:00:00Z",
            },
          ],
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Run history section with heading containing "Run History"
    await expect(page.getByText(/Run History/)).toBeVisible();

    // Three run mode badges should be visible
    await expect(page.getByText("succeeded").first()).toBeVisible();
    await expect(page.getByText("partial_success").first()).toBeVisible();
    await expect(page.getByText("failed").first()).toBeVisible();
  });

  test("retry and resume buttons appear for partial_success runs in history", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      if (route.request().method() === "POST" && route.request().url().includes("/retry-failed")) {
        route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({ run: { id: "run-002", status: "running" }, message: "Retrying" }),
        });
        return;
      }
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [{
            id: "run-002", mode: "preview", status: "partial_success",
            extraction_succeeded: 3, extraction_failed: 2,
            merge_succeeded: 4, merge_failed: 2,
            total_tokens: 15000, model_used: "deepseek-chat",
            started_at: "2025-05-21T14:00:00Z", finished_at: "2025-05-21T14:05:00Z",
            created_at: "2025-05-21T14:00:00Z",
          }],
        }),
      });
    });

    // Run detail
    await page.route(apiRoute("/api/analysis/runs/run-002"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          run: {
            id: "run-002", topic_id: TOPIC_ID, mode: "preview",
            status: "partial_success", progress_current: 80, progress_total: 100,
            extraction_total: 5, extraction_succeeded: 3, extraction_failed: 2,
            merge_total: 6, merge_succeeded: 4, merge_failed: 2,
            final_total: 6, final_succeeded: 4, final_failed: 2,
            total_tokens: 15000, model_used: "deepseek-chat",
            error_message: null,
            started_at: "2025-05-21T14:00:00Z", finished_at: "2025-05-21T14:05:00Z",
          },
          extractions: [
            { id: "ex-1", chunk_id: "chunk-001", status: "failed", attempt_count: 3, error_message: "LLM timeout" },
          ],
          merge: { total: 6, succeeded: 4, failed: 2, outputs: [], warnings: ["Incomplete merge for themes"] },
          final: { total: 6, succeeded: 4, failed: 2, outputs: [] },
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Run history should show the partial_success run with Retry/Resume buttons
    await expect(page.getByRole("button", { name: "Retry Failed" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Resume" })).toBeVisible();
  });
});

test.describe("Analysis v2 – stage progress and failed extractions", () => {
  test("shows failed extraction details for partial_success run", async ({ page }) => {
    await mockParsedTopic(page);

    // One completed partial_success run in history
    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [{
            id: "run-fail", mode: "full", status: "partial_success",
            extraction_succeeded: 98, extraction_failed: 2,
            merge_succeeded: 5, merge_failed: 1,
            total_tokens: 100000, model_used: "deepseek-chat",
            started_at: "2025-05-20T10:00:00Z", finished_at: "2025-05-20T10:30:00Z",
            created_at: "2025-05-20T10:00:00Z",
          }],
        }),
      });
    });

    // Run detail — partial_success with failed extractions
    await page.route(apiRoute("/api/analysis/runs/run-fail"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          run: {
            id: "run-fail", topic_id: TOPIC_ID, mode: "full",
            status: "partial_success", progress_current: 98, progress_total: 100,
            extraction_total: 100, extraction_succeeded: 98, extraction_failed: 2,
            merge_total: 6, merge_succeeded: 5, merge_failed: 1,
            final_total: 6, final_succeeded: 5, final_failed: 1,
            total_tokens: 100000, model_used: "deepseek-chat",
            error_message: null,
            started_at: "2025-05-20T10:00:00Z", finished_at: "2025-05-20T10:30:00Z",
          },
          extractions: [
            { id: "ex-f1", chunk_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0001", status: "failed", attempt_count: 3, error_message: "LLM timeout after 3 retries" },
            { id: "ex-f2", chunk_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0002", status: "failed", attempt_count: 1, error_message: "Invalid JSON response" },
          ],
          merge: {
            total: 6, succeeded: 5, failed: 1, outputs: [],
            warnings: ["Dropped 3 duplicate characters during merge", "Unresolved event reference in causality"],
          },
          final: { total: 6, succeeded: 5, failed: 1, outputs: [] },
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Click the run in history to select it (id "run-fail" is 8 chars, fits aria-label exactly)
    await page.getByRole("button", { name: /Run run-fail/ }).click();

    // Wait for the status card to appear with stage progress
    await expect(page.getByText("Overall Progress")).toBeVisible({ timeout: 10000 });

    // Should show failed extraction summaries
    await expect(page.getByText(/Failed Extractions/)).toBeVisible();

    // The run is partial_success — "Retry Failed" text visible in the status card
    await expect(page.getByText("Retry Failed").first()).toBeVisible({ timeout: 10000 });
  });
});

test.describe("Analysis v2 – outputs panel", () => {
  test("shows outputs filtered by selected run", async ({ page }) => {
    await mockParsedTopic(page);

    // Runs list — one succeeded run
    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [{
            id: "run-done", mode: "preview", status: "succeeded",
            extraction_succeeded: 5, extraction_failed: 0,
            merge_succeeded: 6, merge_failed: 0,
            total_tokens: 20000, model_used: "deepseek-chat",
            started_at: "2025-05-20T10:00:00Z", finished_at: "2025-05-20T10:05:00Z",
            created_at: "2025-05-20T10:00:00Z",
          }],
        }),
      });
    });

    // Run detail — succeeded
    await page.route(apiRoute("/api/analysis/runs/run-done"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          run: {
            id: "run-done", topic_id: TOPIC_ID, mode: "preview",
            status: "succeeded", progress_current: 100, progress_total: 100,
            extraction_total: 5, extraction_succeeded: 5, extraction_failed: 0,
            merge_total: 6, merge_succeeded: 6, merge_failed: 0,
            final_total: 6, final_succeeded: 6, final_failed: 0,
            total_tokens: 20000, model_used: "deepseek-chat",
            error_message: null,
            started_at: "2025-05-20T10:00:00Z", finished_at: "2025-05-20T10:05:00Z",
          },
          extractions: [],
          merge: { total: 6, succeeded: 6, failed: 0, outputs: [], warnings: [] },
          final: { total: 6, succeeded: 6, failed: 0, outputs: [] },
        }),
      });
    });

    // Outputs filtered by run
    await page.route(apiRoute("/api/topics/test-topic-1/analysis/outputs"), (route) => {
      const url = route.request().url();
      if (url.includes("run_id=run-done")) {
        route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({
            outputs: [
              { id: "out-1", topic_id: TOPIC_ID, run_id: "run-done", output_type: "characters", title: "Characters", content_json: JSON.stringify({ characters: [] }), created_at: "2025-05-20T10:04:00Z" },
              { id: "out-2", topic_id: TOPIC_ID, run_id: "run-done", output_type: "events", title: "Events", content_json: JSON.stringify({ events: [] }), created_at: "2025-05-20T10:04:30Z" },
            ],
            count: 2,
          }),
        });
      } else {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ outputs: [], count: 0 }) });
      }
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Click the run in history
    await page.getByRole("button", { name: /Run run-done/ }).click();

    // Outputs section should show "Run Outputs"
    await expect(page.getByRole("heading", { name: "Run Outputs" })).toBeVisible({ timeout: 5000 });

    // Should show output count — use regex to match "2 output(s)"
    await expect(page.getByText(/2 output/)).toBeVisible();
  });

  test("shows missing types warning when outputs are incomplete", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [{
            id: "run-ptl", mode: "preview", status: "partial_success",
            extraction_succeeded: 5, extraction_failed: 0,
            merge_succeeded: 3, merge_failed: 3,
            total_tokens: 10000, model_used: "deepseek-chat",
            started_at: "2025-05-20T10:00:00Z", finished_at: "2025-05-20T10:05:00Z",
            created_at: "2025-05-20T10:00:00Z",
          }],
        }),
      });
    });

    await page.route(apiRoute("/api/analysis/runs/run-ptl"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          run: {
            id: "run-ptl", topic_id: TOPIC_ID, mode: "preview",
            status: "partial_success", progress_current: 50, progress_total: 100,
            extraction_total: 5, extraction_succeeded: 5, extraction_failed: 0,
            merge_total: 6, merge_succeeded: 3, merge_failed: 3,
            final_total: 6, final_succeeded: 3, final_failed: 3,
            total_tokens: 10000, model_used: "deepseek-chat",
            error_message: null,
            started_at: "2025-05-20T10:00:00Z", finished_at: "2025-05-20T10:05:00Z",
          },
          extractions: [],
          merge: { total: 6, succeeded: 3, failed: 3, outputs: [], warnings: [] },
          final: { total: 6, succeeded: 3, failed: 3, outputs: [] },
        }),
      });
    });

    // Only 3 of 6 output types returned
    await page.route(apiRoute("/api/topics/test-topic-1/analysis/outputs"), (route) => {
      const url = route.request().url();
      if (url.includes("run_id=run-ptl")) {
        route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({
            outputs: [
              { id: "out-1", topic_id: TOPIC_ID, run_id: "run-ptl", output_type: "characters", title: "Characters", content_json: JSON.stringify({}), created_at: "2025-05-20T10:04:00Z" },
              { id: "out-2", topic_id: TOPIC_ID, run_id: "run-ptl", output_type: "overview", title: "Overview", content_json: JSON.stringify({}), created_at: "2025-05-20T10:04:00Z" },
              { id: "out-3", topic_id: TOPIC_ID, run_id: "run-ptl", output_type: "events", title: "Events", content_json: JSON.stringify({}), created_at: "2025-05-20T10:04:00Z" },
            ],
            count: 3,
          }),
        });
      } else {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ outputs: [], count: 0 }) });
      }
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // "run-ptl" is 7 chars, under the 8-char slice limit in the aria-label
    await page.getByRole("button", { name: /Run run-ptl/ }).click();
    await expect(page.getByRole("heading", { name: "Run Outputs" })).toBeVisible({ timeout: 5000 });

    // Missing types warning should show
    await expect(page.getByText("Missing types:")).toBeVisible();
  });

  test("output type filter filters displayed outputs", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    // 6 outputs of different types (latest only mode → shows groupLatest)
    await page.route(apiRoute("/api/topics/test-topic-1/analysis/outputs"), (route) => {
      const url = route.request().url();
      if (url.includes("latest_only=true")) {
        route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({
            outputs: [
              { id: "o-1", topic_id: TOPIC_ID, run_id: null, output_type: "causality", title: "Causality", content_json: JSON.stringify({}), created_at: "2025-05-20T10:00:00Z" },
              { id: "o-2", topic_id: TOPIC_ID, run_id: null, output_type: "characters", title: "Characters", content_json: JSON.stringify({}), created_at: "2025-05-20T10:00:00Z" },
              { id: "o-3", topic_id: TOPIC_ID, run_id: null, output_type: "events", title: "Events", content_json: JSON.stringify({}), created_at: "2025-05-20T10:00:00Z" },
              { id: "o-4", topic_id: TOPIC_ID, run_id: null, output_type: "overview", title: "Overview", content_json: JSON.stringify({}), created_at: "2025-05-20T10:00:00Z" },
              { id: "o-5", topic_id: TOPIC_ID, run_id: null, output_type: "relations", title: "Relations", content_json: JSON.stringify({}), created_at: "2025-05-20T10:00:00Z" },
              { id: "o-6", topic_id: TOPIC_ID, run_id: null, output_type: "themes", title: "Themes", content_json: JSON.stringify({}), created_at: "2025-05-20T10:00:00Z" },
            ],
            count: 6,
          }),
        });
      } else {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ outputs: [], count: 0 }) });
      }
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Outputs" })).toBeVisible({ timeout: 10000 });

    // Should show 6 outputs
    await expect(page.getByText(/6 output/)).toBeVisible();

    // The output type filter is a <select> with output type option values.
    // Find it by looking for the select that has an option "characters".
    const filterSelect = page.locator("select", { has: page.locator("option[value='characters']") });
    await filterSelect.selectOption("characters");

    // After filtering, verify the filter is set to "characters" in the select
    await expect(filterSelect).toHaveValue("characters");
  });
});

test.describe("Analysis v2 – cost projection", () => {
  test("shows token cost projection for preview mode", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Cost projection card heading
    await expect(page.getByRole("heading", { name: "Cost Estimate" })).toBeVisible();

    // Token breakdown labels (use .first() — there are duplicates from the legacy panel)
    await expect(page.locator("strong", { hasText: "Chunks:" }).first()).toBeVisible();
    await expect(page.locator("strong", { hasText: "Total tokens:" }).first()).toBeVisible();

    // Credit warning should be visible (appears in both v2 and legacy panels)
    await expect(page.getByText(/may consume API credits/).first()).toBeVisible();
  });
});

test.describe("Analysis v2 – range selection", () => {
  test("range mode shows chunk/chapter range inputs", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Switch to Range mode
    await page.getByLabel("Range").check();

    // Range selection card should appear with chunk/chapter toggle
    await expect(page.getByRole("heading", { name: "Range Selection" })).toBeVisible();
    await expect(page.getByLabel("By chunk index")).toBeVisible();
    await expect(page.getByLabel("By chapter index")).toBeVisible();

    // Inputs should be present
    await expect(page.getByLabel("Chunk start:")).toBeVisible();
    await expect(page.getByLabel(/end/).first()).toBeVisible();
  });

  test("invalid range disables run button and shows error", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Switch to Range mode
    await page.getByLabel("Range").check();

    // Enter invalid range (start > end)
    await page.getByLabel("Chunk start:").fill("50");
    await page.getByLabel(/^end:/).fill("10");

    // Error should appear
    await expect(page.getByText("Start must be ≤ end.")).toBeVisible();

    // Run button should be disabled
    await expect(page.getByRole("button", RUN_BTN)).toBeDisabled();
  });

  test("range by chapter shows chapter-specific labels", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    await page.getByLabel("Range").check();

    // Switch to chapter mode
    await page.getByLabel("By chapter index").check();

    // Labels should change to chapter
    await expect(page.getByLabel("Chapter start:")).toBeVisible();

    // Available info should show chapters
    await expect(page.getByText("Available: chapters 0–2")).toBeVisible();
  });

  test("clear button resets range selection", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    await page.getByLabel("Range").check();

    // Enter values
    await page.getByLabel("Chunk start:").fill("5");
    await page.getByLabel(/^end:/).fill("15");

    // Clear button should appear
    const clearBtn = page.getByRole("button", { name: "Clear" });
    await expect(clearBtn).toBeVisible();

    // Click clear
    await clearBtn.click();

    // Inputs should be empty
    await expect(page.getByLabel("Chunk start:")).toHaveValue("");
  });
});

test.describe("Analysis v2 – incremental mode", () => {
  test("incremental mode is enabled when previous run exists", async ({ page }) => {
    await mockParsedTopic(page);

    // Previous run exists
    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [{
            id: "run-prev", mode: "full", status: "succeeded",
            extraction_succeeded: 80, extraction_failed: 0,
            merge_succeeded: 6, merge_failed: 0,
            total_tokens: 90000, model_used: "deepseek-chat",
            started_at: "2025-05-19T10:00:00Z", finished_at: "2025-05-19T10:30:00Z",
            created_at: "2025-05-19T10:00:00Z",
          }],
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Incremental mode should now be enabled
    await expect(page.getByLabel("Incremental")).not.toBeDisabled();
  });
});

test.describe("Analysis v2 – error states", () => {
  test("shows error message when run creation fails", async ({ page }) => {
    await mockParsedTopic(page);

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      if (route.request().method() === "POST") {
        route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({ detail: "A run is already in progress for this topic." }),
        });
        return;
      }
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Try to create run
    await page.getByRole("button", RUN_BTN).click();

    // Error message should appear
    await expect(page.getByText("A run is already in progress for this topic.")).toBeVisible({ timeout: 5000 });
  });

  test("run detail 404 auto-clears active run", async ({ page }) => {
    await mockParsedTopic(page);

    // Runs list references a run
    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          runs: [{
            id: "run-gone", mode: "preview", status: "failed",
            extraction_succeeded: 0, extraction_failed: 5,
            merge_succeeded: 0, merge_failed: 6,
            total_tokens: 3000, model_used: null,
            started_at: "2025-05-18T10:00:00Z", finished_at: "2025-05-18T10:01:00Z",
            created_at: "2025-05-18T10:00:00Z",
          }],
        }),
      });
    });

    // Run detail returns 404 — component auto-clears activeRunId
    await page.route(apiRoute("/api/analysis/runs/run-gone"), (route) => {
      route.fulfill({
        status: 404,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Analysis run not found." }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Click the run
    await page.getByRole("button", { name: /Run run-gone/ }).click();
    await page.waitForTimeout(500);

    // After clicking a 404 run, the Outputs panel should still show "Outputs" not "Run Outputs"
    // because activeRunId was auto-cleared
    await expect(page.getByRole("heading", { name: "Outputs" })).toBeVisible({ timeout: 5000 });
  });

  test("shows provider incomplete warning when config is not ready", async ({ page }) => {
    // Build mocks manually to override effective config
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

    // Effective config not ready (missing API key)
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
          supports_thinking: true, is_ready: false, missing_fields: ["api_key"], warnings: ["API key is not configured"],
        }),
      });
    });

    await page.route(apiRoute("/api/provider-presets"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ presets: [] }) });
    });

    await page.route(apiRoute("/api/topics/test-topic-1/documents/current"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          id: "doc-1", topic_id: TOPIC_ID, original_filename: "test.txt",
          stored_filename: "test.txt", file_type: "text/plain", content_type: null,
          encoding: "utf-8", file_size_bytes: 10000, char_count: 8000,
          storage_path: "/tmp/test.txt", status: "parsed",
          created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
        }),
      });
    });

    await page.route(apiRoute("/api/topics/test-topic-1/provider-config"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          config: {
            topic_id: TOPIC_ID, max_output_tokens_override: null,
            model_name_override: null, temperature_override: null,
            thinking_mode_override: null, analysis_parallelism_override: null,
          },
        }),
      });
    });

    // Chunks meta (needed for page to render fully)
    await page.route(apiRoute("/api/topics/test-topic-1/chunks/meta"), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          topic_id: TOPIC_ID, document_id: "doc-1",
          chunk_count: 100, chapter_count: 3, total_chars: 200000,
          estimated_tokens: 100000,
          first_chunk_index: 0, last_chunk_index: 99,
          first_global_chunk_index: 0, last_global_chunk_index: 99,
          chunks_by_chapter: [],
        }),
      });
    });

    await page.route(apiRoute("/api/topics/test-topic-1/analysis/runs"), (route) => {
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible({ timeout: 10000 });

    // Should show provider config incomplete warning
    await expect(page.getByText("Provider config is incomplete.")).toBeVisible();
  });
});
