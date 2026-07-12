import { test, expect } from "@playwright/test";

const API_HOST = "http://127.0.0.1:8000";
const TOPIC_ID = "chat-topic";
const SESSION_ID = "chat-session";
const USER_ID = "user-old";
const ASSISTANT_ID = "assistant-old";

function apiPath(path: string) {
  return (url: URL) => url.origin === API_HOST && url.pathname === path;
}

const originalMessages = [
  {
    id: USER_ID, session_id: SESSION_ID, role: "user", content: "Original question",
    evidence_json: null, uncertainty: null, prompt_tokens: 0, completion_tokens: 0,
    total_tokens: 0, model_used: null, created_at: "2025-01-01T00:00:00Z",
  },
  {
    id: ASSISTANT_ID, session_id: SESSION_ID, role: "assistant", content: "Original answer",
    evidence_json: null, uncertainty: null, prompt_tokens: 10, completion_tokens: 10,
    total_tokens: 20, model_used: "test", created_at: "2025-01-01T00:00:01Z",
  },
];

const revisedMessages = [
  {
    ...originalMessages[0], id: "user-new", content: "Revised question",
    created_at: "2025-01-01T00:01:00Z",
  },
  {
    ...originalMessages[1], id: "assistant-new", content: "Revised answer",
    created_at: "2025-01-01T00:01:01Z",
  },
];

async function mockChatPage(page: Parameters<typeof test>[1]["page"]) {
  await page.route(apiPath(`/api/topics/${TOPIC_ID}`), (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      id: TOPIC_ID, name: "Chat Topic", description: null, provider_id: "provider-1",
      storage_bytes: 0, status: "active", document: null, analysis_summary: {},
      disk_usage_bytes: 0, created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    }),
  }));
  await page.route(apiPath(`/api/topics/${TOPIC_ID}/chat/sessions`), (route) => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      sessions: [{
        id: SESSION_ID, topic_id: TOPIC_ID, title: "Test Session",
        created_at: "2025-01-01T00:00:00Z", updated_at: "2025-01-01T00:00:00Z",
      }],
    }),
  }));
  await page.route(apiPath(`/api/topics/${TOPIC_ID}/provider-config`), (route) => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ config: null }),
  }));
}

async function openLatestEdit(page: Parameters<typeof test>[1]["page"]) {
  await page.goto(`/topics/${TOPIC_ID}/chat`);
  await page.getByText("Test Session", { exact: true }).click();
  await expect(page.getByText("Original answer", { exact: true })).toBeVisible();
  await page.getByText("Original question", { exact: true }).hover();
  await page.getByRole("button", { name: "Edit" }).click();
  const editor = page.locator(".chat-messages textarea");
  await editor.fill("Revised question");
  return editor;
}

test.describe("Chat edit and resend", () => {
  test("failed resend preserves the original exchange and revised editor text", async ({ page }) => {
    await mockChatPage(page);
    let deleteCalls = 0;
    await page.route(apiPath(`/api/chat/sessions/${SESSION_ID}/messages`), (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ messages: originalMessages, total: 2 }),
    }));
    await page.route(
      apiPath(`/api/chat/sessions/${SESSION_ID}/messages/${USER_ID}/resend`),
      (route) => route.fulfill({
        status: 502,
        contentType: "application/json",
        body: JSON.stringify({ detail: "The LLM could not produce a revised response" }),
      }),
    );
    await page.route((url) => url.origin === API_HOST && url.pathname.includes("/messages/"), (route) => {
      if (route.request().method() === "DELETE") deleteCalls += 1;
      route.fallback();
    });

    const editor = await openLatestEdit(page);
    await page.getByRole("button", { name: "Resend", exact: true }).click();

    await expect(page.getByRole("alert")).toContainText("The original exchange was kept");
    await expect(editor).toHaveValue("Revised question");
    await expect(page.getByText("Original answer", { exact: true })).toBeVisible();
    expect(deleteCalls).toBe(0);
  });

  test("successful resend uses the atomic endpoint and refreshes the pair", async ({ page }) => {
    await mockChatPage(page);
    let replaced = false;
    let requestBody: Record<string, unknown> = {};
    let deleteCalls = 0;
    await page.route(apiPath(`/api/chat/sessions/${SESSION_ID}/messages`), (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        messages: replaced ? revisedMessages : originalMessages,
        total: 2,
      }),
    }));
    await page.route(
      apiPath(`/api/chat/sessions/${SESSION_ID}/messages/${USER_ID}/resend`),
      (route, request) => {
        requestBody = request.postDataJSON() || {};
        replaced = true;
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(revisedMessages[1]),
        });
      },
    );
    await page.route((url) => url.origin === API_HOST && url.pathname.includes("/messages/"), (route) => {
      if (route.request().method() === "DELETE") deleteCalls += 1;
      route.fallback();
    });

    await openLatestEdit(page);
    await page.getByRole("button", { name: "Resend", exact: true }).click();

    await expect(page.getByText("Revised answer", { exact: true })).toBeVisible();
    await expect(page.getByText("Original answer", { exact: true })).toHaveCount(0);
    expect(requestBody).toEqual({
      content: "Revised question",
      expected_assistant_message_id: ASSISTANT_ID,
    });
    expect(deleteCalls).toBe(0);
  });
});
