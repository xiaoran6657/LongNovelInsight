import { test, expect } from "@playwright/test";

const TOPIC_ID = "test-topic-1";
const PROVIDER_ID = "test-provider-1";
const API_HOST = "http://127.0.0.1:8000";

function apiRoute(pathPattern: string | RegExp) {
  if (typeof pathPattern === "string") {
    return (url: URL) => url.origin === API_HOST && url.pathname === pathPattern;
  }
  return (url: URL) => url.origin === API_HOST && pathPattern.test(url.pathname + url.search);
}

/** Shared mocks for a parsed EPUB topic ready for v0.3 feature testing. */
async function mockParsedEpubTopic(page: Parameters<typeof test>[1]["page"]) {
  // Catch-all for unhandled API calls
  await page.route((url) => url.origin === API_HOST, (route) => {
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({}) });
  });

  // Topic detail
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}`), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        id: TOPIC_ID, name: "EPUB Test Topic", description: null,
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
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/provider-config/effective`), (route) => {
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

  // EPUB document
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/documents/current`), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        id: "doc-1", topic_id: TOPIC_ID,
        original_filename: "novel.epub", stored_filename: "novel.epub",
        file_type: "epub", encoding: null, content_type: "application/epub+zip",
        file_size_bytes: 500000, char_count: 200000,
        metadata_json: JSON.stringify({
          source_format: "EPUB 3.0",
          title: "Test Novel",
          creator: "Test Author",
          language: "en",
          publisher: "Test Publisher",
          identifier: "urn:isbn:9780000000001",
        }),
        status: "parsed", storage_path: "/tmp/novel.epub",
        created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
      }),
    });
  });

  // Document metadata
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/documents/current/metadata`), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        id: "doc-1", topic_id: TOPIC_ID,
        original_filename: "novel.epub", file_type: "epub",
        encoding: null, file_size_bytes: 500000, char_count: 200000,
        status: "parsed",
        metadata: {
          source_format: "EPUB 3.0",
          title: "Test Novel",
          creator: "Test Author",
          language: "en",
          publisher: "Test Publisher",
          identifier: "urn:isbn:9780000000001",
        },
        created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
      }),
    });
  });

  // Chapters
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/chapters`), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        chapters: [
          { id: "ch-1", topic_id: TOPIC_ID, title: "Chapter 1", chapter_index: 0, source_href: "OEBPS/ch01.xhtml", nav_order: 1, char_count: 10000 },
          { id: "ch-2", topic_id: TOPIC_ID, title: "Chapter 2", chapter_index: 1, source_href: "OEBPS/ch02.xhtml", nav_order: 2, char_count: 12000 },
          { id: "ch-3", topic_id: TOPIC_ID, title: "Chapter 3", chapter_index: 2, source_href: "OEBPS/ch03.xhtml", nav_order: 3, char_count: 8000 },
        ],
      }),
    });
  });

  // Chunks meta
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/chunks/meta`), (route) => {
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        topic_id: TOPIC_ID, document_id: "doc-1",
        chunk_count: 30, chapter_count: 3, total_chars: 200000,
        estimated_tokens: 100000,
        first_chunk_index: 0, last_chunk_index: 29,
        first_global_chunk_index: 0, last_global_chunk_index: 29,
        chunks_by_chapter: [
          { chapter_index: 0, title: "Chapter 1", chunk_count: 10, char_count: 60000, estimated_tokens: 30000 },
          { chapter_index: 1, title: "Chapter 2", chunk_count: 10, char_count: 80000, estimated_tokens: 40000 },
          { chapter_index: 2, title: "Chapter 3", chunk_count: 10, char_count: 60000, estimated_tokens: 30000 },
        ],
      }),
    });
  });

  // Stored provider config
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/provider-config`), (route) => {
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

  // Analysis runs (empty)
  await page.route(apiRoute(`/api/topics/${TOPIC_ID}/analysis/runs`), (route) => {
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ runs: [] }) });
  });
}

// ── Tests ──

test.describe("v0.3 – EPUB metadata", () => {
  test("renders EPUB file type badge and metadata card", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByText("novel.epub")).toBeVisible({ timeout: 10000 });

    // EPUB badge — inside the file info line
    const fileLine = page.getByText("File: novel.epub");
    await expect(fileLine).toBeVisible();
    await expect(fileLine.locator("span", { hasText: "EPUB" })).toBeVisible();

    // Document Metadata card
    await expect(page.getByText("Document Metadata")).toBeVisible();
    await expect(page.getByText("Test Novel")).toBeVisible();
    await expect(page.getByText("Test Author")).toBeVisible();

    // EPUB Chapter Tree — scoped to the chapter tree card heading
    const treeHeading = page.getByText("EPUB Chapter Tree");
    await expect(treeHeading).toBeVisible();
    // Chapter titles are rendered inside the chapter tree; use { exact: true } to avoid matching
    // "Ch. 1 — Chapter 1" text from other panels
    await expect(page.getByText("Chapter 1", { exact: true }).first()).toBeVisible();
  });
});

test.describe("v0.3 – Topic search", () => {
  test("renders search results with method badge and score", async ({ page }) => {
    await mockParsedEpubTopic(page);

    // Search endpoint
    await page.route(apiRoute(`/api/topics/${TOPIC_ID}/search`), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          query: "hero",
          results: [
            {
              chunk_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0001",
              topic_id: TOPIC_ID,
              chapter_index: 0,
              chunk_index: 3,
              title: "The Hero Appears",
              snippet: "The hero walked through the village gate, cloak billowing in the wind.",
              score: 0.85,
              method: "fts",
            },
            {
              chunk_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0002",
              topic_id: TOPIC_ID,
              chapter_index: 1,
              chunk_index: 7,
              title: "At the Inn",
              snippet: "heroic deeds were discussed over mugs of ale.",
              score: 0.42,
              method: "keyword_fallback",
            },
          ],
          trace_id: null,
        }),
      });
    });

    // Locator endpoint (for Open button)
    await page.route(apiRoute(/\/api\/topics\/test-topic-1\/chunks\/.*\/locator/), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          chunk_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0001",
          chapter_index: 0,
          chunk_index: 3,
          locator: {
            href: "OEBPS/ch01.xhtml",
            chapter_title: "Chapter 1",
            chapter_index: 0,
            chunk_index: 3,
          },
          excerpt: "The hero walked through the village gate, cloak billowing in the wind. The townsfolk stopped to stare.",
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible({ timeout: 10000 });

    // Enter query and submit
    const searchInput = page.locator("input[placeholder='Search within this topic...']");
    await searchInput.fill("hero");
    await searchInput.press("Enter");

    // Results should appear
    await expect(page.getByText("2 results")).toBeVisible({ timeout: 5000 });

    // Method badges
    await expect(page.getByText("fts").first()).toBeVisible();
    await expect(page.getByText("keyword_fallback").first()).toBeVisible();

    // Score
    await expect(page.getByText("Score: 0.85")).toBeVisible();

    // Snippet
    await expect(page.getByText(/hero walked through/)).toBeVisible();

    // Open button should appear
    await expect(page.getByRole("button", { name: "Open" }).first()).toBeVisible();
  });

  test("shows empty state when no results", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.route(apiRoute(`/api/topics/${TOPIC_ID}/search`), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ query: "zzz_nonexistent", results: [], trace_id: null }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible({ timeout: 10000 });

    const searchInput = page.locator("input[placeholder='Search within this topic...']");
    await searchInput.fill("zzz_nonexistent");
    await searchInput.press("Enter");

    await expect(page.getByText("No results found.")).toBeVisible({ timeout: 5000 });
  });

  test("debug retrieval drawer shows method checkboxes with semantic_rerank disabled", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.route(apiRoute(`/api/topics/${TOPIC_ID}/search`), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          query: "test",
          results: [{ chunk_id: "ch-1", topic_id: TOPIC_ID, chapter_index: 0, chunk_index: 0, title: "T", snippet: "x", score: 1.0, method: "fts" }],
          trace_id: null,
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible({ timeout: 10000 });

    // Search first
    const searchInput = page.locator("input[placeholder='Search within this topic...']");
    await searchInput.fill("test");
    await searchInput.press("Enter");

    // Debug retrieval button should appear
    await expect(page.getByRole("button", { name: "Debug retrieval" })).toBeVisible({ timeout: 5000 });

    // Click to open debug drawer
    await page.getByRole("button", { name: "Debug retrieval" }).click();

    // Method checkboxes should be visible
    await expect(page.getByText("Semantic Rerank")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("(off)")).toBeVisible();

    // The semantic_rerank checkbox should be disabled — find the label with "(off)"
    const srLabel = page.getByText("Semantic Rerank");
    await expect(srLabel).toBeVisible();
    // The associated input should be disabled
    const srCheckbox = page.locator("label").filter({ hasText: "Semantic Rerank" }).locator("input[type='checkbox']");
    await expect(srCheckbox).toBeDisabled();
  });
});

test.describe("v0.3 – Entity evidence", () => {
  test("renders entity evidence results with atoms, chunks, and outputs", async ({ page }) => {
    await mockParsedEpubTopic(page);

    // Entity evidence endpoint
    await page.route(
      apiRoute(new RegExp(`/api/topics/${TOPIC_ID}/entities/`)),
      (route) => {
        route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({
            entity_id: "char_hero",
            canonical_name: "Hero",
            atoms: [
              {
                id: "atom-1",
                atom_type: "character",
                stable_id: "char_hero",
                canonical_name: "Hero",
                title: "The Protagonist",
                summary: "Main hero of the story, a young warrior from the northern village.",
                confidence: 0.92,
                evidence_quotes: ["The hero drew his sword.", "He had saved the village twice before."],
                chapter_index: 0,
                chunk_index: 3,
              },
            ],
            chunks: [
              {
                id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0001",
                chapter_index: 0,
                chunk_index: 3,
                excerpt: "The hero walked through the village gate, cloak billowing.",
                locator: { href: "OEBPS/ch01.xhtml", chapter_title: "Chapter 1", chapter_index: 0, chunk_index: 3 },
              },
            ],
            outputs: [
              {
                id: "out-1",
                output_type: "characters",
                title: "Characters Analysis",
                excerpt: "Hero: The main protagonist, characterized by bravery and loyalty.",
              },
            ],
          }),
        });
      },
    );

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Entity Evidence" })).toBeVisible({ timeout: 10000 });

    // Enter entity ID and lookup
    const input = page.locator("input[placeholder*='char_liubei']");
    await input.fill("char_hero");
    await page.getByRole("button", { name: "Lookup" }).click();

    // Results should appear — use the entity header which shows "canonical_name entity_id"
    await expect(page.getByText("Hero char_hero")).toBeVisible({ timeout: 5000 });
    // Section labels (use exact + count to avoid ambiguity with SimilarScenesPanel description)
    await expect(page.getByText("Atoms (1)")).toBeVisible();
    await expect(page.getByText("Source Chunks (1)")).toBeVisible();
    await expect(page.getByText("Related Outputs (1)")).toBeVisible();

    // Atom content — "character" badge (exact match to avoid description text)
    await expect(page.getByText("character", { exact: true })).toBeVisible();
    await expect(page.getByText("The Protagonist")).toBeVisible();
    await expect(page.getByText(/young warrior/)).toBeVisible();

    // Evidence quotes
    await expect(page.getByText("The hero drew his sword.")).toBeVisible();

    // Chunk content
    await expect(page.getByText(/cloak billowing/)).toBeVisible();
  });

  test("shows empty state for unknown entity", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.route(
      apiRoute(new RegExp(`/api/topics/${TOPIC_ID}/entities/`)),
      (route) => {
        route.fulfill({
          status: 200, contentType: "application/json",
          body: JSON.stringify({
            entity_id: "nonexistent",
            canonical_name: null,
            atoms: [],
            chunks: [],
            outputs: [],
          }),
        });
      },
    );

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Entity Evidence" })).toBeVisible({ timeout: 10000 });

    const input = page.locator("input[placeholder*='char_liubei']");
    await input.fill("nonexistent");
    await page.getByRole("button", { name: "Lookup" }).click();

    await expect(page.getByText("No evidence found for this entity.")).toBeVisible({ timeout: 5000 });
  });
});

test.describe("v0.3 – Similar scenes", () => {
  test("renders similar scenes results with scores", async ({ page }) => {
    await mockParsedEpubTopic(page);

    // Similar scenes endpoint
    await page.route(
      apiRoute(`/api/topics/${TOPIC_ID}/similar-scenes`),
      (route) => {
        const url = new URL(route.request().url());
        if (url.searchParams.get("query") === "battle") {
          route.fulfill({
            status: 200, contentType: "application/json",
            body: JSON.stringify({
              results: [
                {
                  chunk_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0001",
                  chapter_index: 0,
                  chunk_index: 5,
                  title: "The First Battle",
                  snippet: "Swords clashed in the morning light as the two armies met on the plain.",
                  score: 0.78,
                  locator: { href: "OEBPS/ch01.xhtml", chapter_title: "Chapter 1", chapter_index: 0, chunk_index: 5 },
                },
              ],
            }),
          });
        } else {
          route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ results: [] }) });
        }
      },
    );

    // Locator endpoint
    await page.route(apiRoute(/\/api\/topics\/test-topic-1\/chunks\/.*\/locator/), (route) => {
      route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          chunk_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0001",
          chapter_index: 0,
          chunk_index: 5,
          locator: { href: "OEBPS/ch01.xhtml", chapter_title: "Chapter 1" },
          excerpt: "Swords clashed in the morning light as the two armies met on the plain.",
        }),
      });
    });

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Similar Scenes" })).toBeVisible({ timeout: 10000 });

    // Verify mode tabs
    await expect(page.getByRole("button", { name: "By Query" })).toBeVisible();
    await expect(page.getByRole("button", { name: "By Chunk ID" })).toBeVisible();

    // Enter query and submit
    const input = page.locator("input[placeholder='Describe a scene to find similar ones...']");
    await input.fill("battle");
    await input.press("Enter");

    // Results should appear
    await expect(page.getByText("Results")).toBeVisible({ timeout: 5000 });
    await expect(page.getByText("The First Battle")).toBeVisible();
    await expect(page.getByText("Score: 0.780")).toBeVisible();
    await expect(page.getByText(/Swords clashed/)).toBeVisible();
  });

  test("switches to chunk ID mode", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.route(
      apiRoute(`/api/topics/${TOPIC_ID}/similar-scenes`),
      (route) => {
        route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ results: [] }) });
      },
    );

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Similar Scenes" })).toBeVisible({ timeout: 10000 });

    // Switch to chunk ID mode
    await page.getByRole("button", { name: "By Chunk ID" }).click();

    // Placeholder should change
    await expect(page.locator("input[placeholder='Paste a chunk ID...']")).toBeVisible();
  });
});

test.describe("v0.3 – Empty and idle states", () => {
  test("search panel shows idle message before first search", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Search" })).toBeVisible({ timeout: 10000 });

    // No search performed yet — idle message should show (but TopicSearchPanel
    // only shows idle state when !hasSearched and no pending mutation)
  });

  test("entity evidence panel shows idle state before lookup", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Entity Evidence" })).toBeVisible({ timeout: 10000 });

    // Idle text should be visible
    await expect(page.getByText("Enter an entity ID above.")).toBeVisible();
  });

  test("similar scenes panel shows idle state", async ({ page }) => {
    await mockParsedEpubTopic(page);

    await page.goto(`/topics/${TOPIC_ID}`);
    await expect(page.getByRole("heading", { name: "Similar Scenes" })).toBeVisible({ timeout: 10000 });

    // Idle hint for By Query mode
    await expect(page.getByText("Enter a phrase or scene description")).toBeVisible();
  });
});
