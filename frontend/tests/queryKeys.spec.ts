import { QueryClient } from "@tanstack/react-query";
import { expect, test } from "@playwright/test";

import { queryKeys } from "../src/queryKeys";

test("shared Topic Detail and Chat resources use canonical keys", () => {
  expect(queryKeys.topics.detail("topic-1")).toEqual(["topic", "topic-1"]);
  expect(queryKeys.providers.presets).toEqual(["provider-presets"]);
  expect(queryKeys.topicConfig.effective("topic-1")).toEqual([
    "effective-config",
    "topic-1",
  ]);
  expect(queryKeys.topicConfig.stored("topic-1")).toEqual([
    "provider-config",
    "topic-1",
  ]);
  expect(queryKeys.topics.detail(undefined)).toEqual(
    queryKeys.topics.detail(null),
  );
});

test("chunk list options are canonical and preserve response shape", () => {
  const input = { limit: 20, includeText: true };
  const key = queryKeys.chunks.list("topic-1", input);

  expect(key).toEqual([
    "chunks",
    "topic-1",
    "list",
    { includeText: true, limit: 20, offset: null },
  ]);
  expect(queryKeys.chunks.list("topic-1", { includeText: true, limit: 20 })).toEqual(
    queryKeys.chunks.list("topic-1", { limit: 20, includeText: true }),
  );
  expect(queryKeys.chunks.list("topic-1", { includeText: false, limit: 20 })).not.toEqual(
    key,
  );
  expect(input).toEqual({ limit: 20, includeText: true });
});

test("Topic chunk prefix invalidates every list shape for that Topic only", async () => {
  const client = new QueryClient();
  const topicOneSummary = queryKeys.chunks.list("topic-1", {
    includeText: false,
    limit: 20,
  });
  const topicOneText = queryKeys.chunks.list("topic-1", {
    includeText: true,
    limit: 20,
  });
  const topicTwoText = queryKeys.chunks.list("topic-2", {
    includeText: true,
    limit: 20,
  });
  client.setQueryData(topicOneSummary, "summary");
  client.setQueryData(topicOneText, "text");
  client.setQueryData(topicTwoText, "other");

  await client.invalidateQueries({
    queryKey: queryKeys.chunks.all("topic-1"),
    refetchType: "none",
  });

  expect(client.getQueryState(topicOneSummary)?.isInvalidated).toBe(true);
  expect(client.getQueryState(topicOneText)?.isInvalidated).toBe(true);
  expect(client.getQueryState(topicTwoText)?.isInvalidated).toBe(false);
});

test("chat message invalidation remains isolated by session", async () => {
  const client = new QueryClient();
  const first = queryKeys.chat.messages("session-1");
  const second = queryKeys.chat.messages("session-2");
  client.setQueryData(first, ["first"]);
  client.setQueryData(second, ["second"]);

  await client.invalidateQueries({ queryKey: first, refetchType: "none" });

  expect(client.getQueryState(first)?.isInvalidated).toBe(true);
  expect(client.getQueryState(second)?.isInvalidated).toBe(false);
});