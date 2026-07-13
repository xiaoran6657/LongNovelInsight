import { expect, test } from "@playwright/test";

import {
  collectItemConfidences,
  formatConfidence,
  getRecordArray,
  getStringArray,
  hasAnyEvidence,
  inferConfidence,
  normalizeContent,
} from "../src/features/analysis/output/analysisOutputData";

test("normalizes object and serialized-object output content", () => {
  const objectContent = { characters: [{ name: "Hero" }] };

  expect(normalizeContent(objectContent)).toEqual({
    json: objectContent,
    malformed: false,
  });
  expect(normalizeContent(JSON.stringify(objectContent))).toEqual({
    json: objectContent,
    malformed: false,
  });
  expect(normalizeContent(null)).toEqual({ json: {}, malformed: false });
});

test("marks invalid and non-object output content as malformed", () => {
  expect(normalizeContent("not-json")).toEqual({ json: {}, malformed: true });
  expect(normalizeContent("[1,2,3]")).toEqual({ json: {}, malformed: true });
  expect(normalizeContent([1, 2, 3])).toEqual({ json: {}, malformed: true });
  expect(normalizeContent(42)).toEqual({ json: {}, malformed: true });
});

test("filters untrusted arrays without discarding supported primitive labels", () => {
  expect(getRecordArray([null, "bad", { name: "Hero" }, ["nested"]])).toEqual([
    { name: "Hero" },
  ]);
  expect(getStringArray([null, "", " Hero ", 7, false, { name: "bad" }])).toEqual([
    " Hero ",
    "7",
    "false",
  ]);
  expect(getStringArray("not-an-array")).toEqual([]);
});

test("derives confidence using the established precedence and evidence guard", () => {
  const itemConfidence = {
    characters: [{ confidence: 0.8 }, { confidence: 0.4 }, { confidence: Number.NaN }],
  };

  expect(collectItemConfidences(itemConfidence)).toEqual([0.8, 0.4]);
  expect(inferConfidence(0.9, itemConfidence)).toBe(0.9);
  expect(inferConfidence(0, itemConfidence)).toBeCloseTo(0.6);
  expect(inferConfidence(0.9, { insufficient_evidence: true })).toBeNull();
  expect(inferConfidence(0, {})).toBeNull();
  expect(formatConfidence(null)).toEqual({ text: "unknown", color: "#999" });
  expect(formatConfidence(0.7)).toEqual({ text: "70%", color: "#27ae60" });
});

test("detects nested evidence without treating empty evidence arrays as present", () => {
  expect(hasAnyEvidence([{ evidence_quotes: [] }, { name: "Hero" }])).toBe(false);
  expect(hasAnyEvidence([{ evidence_quotes: ["quote"] }])).toBe(true);
});
