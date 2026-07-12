import { test, expect } from "@playwright/test";

const TOPIC_ID = "test-topic-v4";
const WORK_ID = "test-work-1";
const WORK_ID_2 = "test-work-2";
const WORK_RUN_ID = "test-work-run-1";
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

async function mockCrossWorkViews(page: Parameters<typeof test>[1]["page"]) {
  await page.route(
    (url) => url.origin === API_HOST && url.pathname === `/api/topics/${TOPIC_ID}/entities`,
    (route, request) => {
      const workId = new URL(request.url()).searchParams.get("work_id");
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          entities: [
            {
              id: workId ? "work-entity" : "all-entity",
              entity_type: "character",
              canonical_name: workId ? "Book One Hero" : "All Works Hero",
              aliases: [],
              work_ids: workId ? [workId] : [WORK_ID, WORK_ID_2],
              mention_count: 1,
              evidence_count: 1,
              confidence: 0.9,
              merge_strategy: "exact",
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      });
    },
  );

  await page.route(
    (url) =>
      url.origin === API_HOST &&
      url.pathname === `/api/topics/${TOPIC_ID}/graphs/characters`,
    (route, request) => {
      const workId = new URL(request.url()).searchParams.get("work_id");
      const prefix = workId ? "Book One" : "All Works";
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          graph_type: "character",
          nodes: [
            { id: "a", label: `${prefix} A`, type: "character", work_ids: [], mention_count: 1, evidence_count: 1, confidence: 0.9 },
            { id: "b", label: `${prefix} B`, type: "character", work_ids: [], mention_count: 1, evidence_count: 1, confidence: 0.9 },
          ],
          edges: [
            { id: "a-b", source: "a", target: "b", relation_type: "ally", weight: 1, confidence: 0.9, work_ids: [] },
          ],
          stats: {},
          snapshot_id: "snapshot-1",
          generated_at: "2025-01-01T00:00:00Z",
        }),
      });
    },
  );

  await page.route(
    (url) => url.origin === API_HOST && url.pathname === `/api/topics/${TOPIC_ID}/timeline`,
    (route, request) => {
      const workId = new URL(request.url()).searchParams.get("work_id");
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              id: workId ? "work-event" : "all-event",
              work_id: workId,
              title: workId ? "Book One Event" : "All Works Event",
              summary: null,
              sequence_index: 1,
              time_label: null,
              participants: [],
              locations: [],
              evidence: [],
              confidence: 0.9,
              created_at: "2025-01-01T00:00:00Z",
            },
          ],
          total: 1,
          limit: 100,
          offset: 0,
        }),
      });
    },
  );
}

async function mockWorkAnalysis(
  page: Parameters<typeof test>[1]["page"],
  status: "parsed" | "analyzed",
) {
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/works`), (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      works: [
        { id: WORK_ID, topic_id: TOPIC_ID, title: "Book One", subtitle: null, author: "Author A", series_index: 1, description: null, status, metadata_json: null, created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z" },
        { id: WORK_ID_2, topic_id: TOPIC_ID, title: "Book Two", subtitle: null, author: null, series_index: 2, description: null, status: "empty", metadata_json: null, created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z" },
      ],
    }),
  }));
  await page.route(apiRoute(`/api/works/${WORK_ID}/documents/current`), (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      id: "work-doc-1", topic_id: TOPIC_ID, work_id: WORK_ID,
      original_filename: "book-one.txt", file_type: "txt", encoding: "utf-8",
      file_size_bytes: 1024, char_count: 5000, status: "parsed",
      created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
    }),
  }));
  await page.route(apiRoute(`/api/works/${WORK_ID}/chapters`), (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ chapters: [] }),
  }));
  await page.route(
    (url) => url.origin === API_HOST && url.pathname === `/api/works/${WORK_ID}/chunks`,
    (route) => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ chunks: [] }),
    }),
  );
}

async function mockWorkRunStatus(page: Parameters<typeof test>[1]["page"]) {
  await page.route(apiRoute(`/api/analysis/runs/${WORK_RUN_ID}`), (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      run: {
        id: WORK_RUN_ID, topic_id: TOPIC_ID, work_id: WORK_ID, mode: "preview",
        status: "running", progress_current: 1, progress_total: 5,
        extraction_total: 3, extraction_succeeded: 1, extraction_failed: 0,
        merge_total: 1, merge_succeeded: 0, merge_failed: 0,
        final_total: 1, final_succeeded: 0, final_failed: 0,
        total_tokens: 0, prompt_tokens: 0, completion_tokens: 0, reasoning_tokens: 0,
        usage_unavailable_attempts: 0, model_used: "m", error_message: null,
        started_at: "2025-01-01T00:00:00Z", finished_at: null,
        created_at: "2025-01-01T00:00:00Z",
      },
      extractions: [],
      merge: { total: 1, succeeded: 0, failed: 0, outputs: [], warnings: [] },
      final: { total: 1, succeeded: 0, failed: 0, outputs: [] },
    }),
  }));
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/analysis/runs`), (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      runs: [{
        id: WORK_RUN_ID, mode: "preview", status: "running",
        extraction_succeeded: 1, extraction_failed: 0, merge_succeeded: 0,
        merge_failed: 0, total_tokens: 0, model_used: "m", work_id: WORK_ID,
        started_at: "2025-01-01T00:00:00Z", finished_at: null,
        created_at: "2025-01-01T00:00:00Z",
      }],
      total: 1,
    }),
  }));
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/analysis/outputs`), (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ outputs: [], count: 0 }),
  }));
}

test.describe("v0.4 Works", () => {
  test("Work preview analysis requires confirmation and hands the run to Overview", async ({ page }) => {
    await mockV04Topic(page);
    await mockWorkAnalysis(page, "parsed");
    await mockWorkRunStatus(page);
    let createCalls = 0;
    let requestBody: Record<string, unknown> = {};
    await page.route(apiRoute(`/api/works/${WORK_ID}/analysis/runs`), (route, request) => {
      createCalls += 1;
      requestBody = request.postDataJSON() || {};
      route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          run: {
            id: WORK_RUN_ID, topic_id: TOPIC_ID, mode: "preview",
            status: "pending", progress_total: 5,
          },
          status_url: `/api/analysis/runs/${WORK_RUN_ID}`,
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await page.getByRole("button", { name: "Works", exact: true }).click();
    await page.getByRole("button", { name: "1. Book One", exact: true }).click();
    const runButton = page.getByRole("button", { name: "Run Preview Analysis", exact: true });
    await expect(runButton).toBeVisible();
    await runButton.click();
    await expect(page.getByText(/consume API credits/i)).toBeVisible();
    expect(createCalls).toBe(0);

    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(page.getByText(/consume API credits/i)).not.toBeVisible();
    expect(createCalls).toBe(0);

    await runButton.click();
    const statusRequest = page.waitForRequest(
      (request) => new URL(request.url()).pathname === `/api/analysis/runs/${WORK_RUN_ID}`,
    );
    await Promise.all([
      page.waitForResponse(
        (response) =>
          new URL(response.url()).pathname === `/api/works/${WORK_ID}/analysis/runs` &&
          response.request().method() === "POST",
      ),
      page.getByRole("button", { name: /confirm preview analysis/i }).click(),
    ]);
    expect(createCalls).toBe(1);
    expect(requestBody).toEqual({
      mode: "preview", limit_chunks: 3, requested_types: ["characters"],
    });

    await statusRequest;
    await expect(page.getByRole("heading", { name: "Analysis (v2)" })).toBeVisible();
    await expect(page.getByText("Polling...", { exact: true })).toBeVisible();
    expect(
      await page.evaluate(
        (key) => sessionStorage.getItem(key),
        `activeAnalysisRun_${TOPIC_ID}`,
      ),
    ).toBe(WORK_RUN_ID);
  });

  test("analyzed Work still offers preview analysis rerun", async ({ page }) => {
    await mockV04Topic(page);
    await mockWorkAnalysis(page, "analyzed");
    await page.goto(`/topics/${TOPIC_ID}`);
    await page.getByRole("button", { name: "Works", exact: true }).click();
    await page.getByRole("button", { name: "1. Book One", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Run Preview Analysis", exact: true }),
    ).toBeVisible();
  });

  test("selected Work filters the entity registry", async ({ page }) => {
    await mockV04Topic(page);
    await mockCrossWorkViews(page);
    await page.goto(`/topics/${TOPIC_ID}`);
    await page.getByRole("button", { name: "Entities", exact: true }).click();
    await expect(page.getByText("All Works Hero")).toBeVisible();

    const responsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname.endsWith(`/topics/${TOPIC_ID}/entities`) && url.searchParams.get("work_id") === WORK_ID;
    });
    await page.getByRole("button", { name: "1. Book One", exact: true }).click();
    await responsePromise;
    await expect(page.getByText("Book One Hero")).toBeVisible();
    await expect(page.getByText("All Works Hero")).not.toBeVisible();
  });

  test("selected Work filters the character graph", async ({ page }) => {
    await mockV04Topic(page);
    await mockCrossWorkViews(page);
    await page.goto(`/topics/${TOPIC_ID}`);
    await page.getByRole("button", { name: "Graph", exact: true }).click();
    await expect(page.getByText("All Works A")).toBeVisible();

    const responsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname.endsWith(`/topics/${TOPIC_ID}/graphs/characters`) && url.searchParams.get("work_id") === WORK_ID;
    });
    await page.getByRole("button", { name: "1. Book One", exact: true }).click();
    await responsePromise;
    await expect(page.getByText("Book One A")).toBeVisible();
    await expect(page.getByText("All Works A")).not.toBeVisible();
  });

  test("selected Work filters the timeline", async ({ page }) => {
    await mockV04Topic(page);
    await mockCrossWorkViews(page);
    await page.goto(`/topics/${TOPIC_ID}`);
    await page.getByRole("button", { name: "Timeline", exact: true }).click();
    await expect(page.getByText("All Works Event")).toBeVisible();

    const responsePromise = page.waitForResponse((response) => {
      const url = new URL(response.url());
      return url.pathname.endsWith(`/topics/${TOPIC_ID}/timeline`) && url.searchParams.get("work_id") === WORK_ID;
    });
    await page.getByRole("button", { name: "1. Book One", exact: true }).click();
    await responsePromise;
    await expect(page.getByText("Book One Event")).toBeVisible();
    await expect(page.getByText("All Works Event")).not.toBeVisible();
  });

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
    await Promise.all([
      page.waitForResponse(
        (resp) =>
          resp.url().includes(`/api/topics/${TOPIC_ID}/works`) &&
          resp.request().method() === "POST",
      ),
      page.locator("button", { hasText: "Create Work" }).click(),
    ]);

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
    await Promise.all([
      page.waitForResponse(
        (resp) =>
          resp.url().includes(`/api/works/${WORK_ID}`) &&
          resp.request().method() === "PATCH",
      ),
      page.locator("button", { hasText: "Save" }).click(),
    ]);

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
    await Promise.all([
      page.waitForResponse(
        (resp) =>
          resp.url().includes(`/api/works/${WORK_ID}`) &&
          resp.request().method() === "DELETE",
      ),
      page.locator("button", { hasText: "×" }).first().click(),
    ]);

    expect(deleteCalled).toBe(true);
  });

});
