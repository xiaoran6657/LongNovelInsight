import { expect, test } from "@playwright/test";

import {
  formatBytes,
  formatDateTime,
  formatJsonPreview,
} from "../src/utils/format";

test("formatBytes covers byte and binary unit boundaries", () => {
  expect(formatBytes(0)).toBe("0 B");
  expect(formatBytes(1023)).toBe("1023 B");
  expect(formatBytes(1024)).toBe("1.0 KB");
  expect(formatBytes(1024 ** 2)).toBe("1.0 MB");
  expect(formatBytes(1024 ** 3)).toBe("1.0 GB");
  expect(formatBytes(1024 ** 4)).toBe("1024.0 GB");
});

test("formatJsonPreview handles null, objects, boundaries, and truncation", () => {
  expect(formatJsonPreview(null)).toBe("—");
  expect(formatJsonPreview(undefined)).toBe("—");
  expect(formatJsonPreview({ value: 1 })).toBe('{"value":1}');
  expect(formatJsonPreview("exact", 5)).toBe("exact");
  expect(formatJsonPreview("longer", 5)).toBe("longe…");

  const circular: { self?: unknown } = {};
  circular.self = circular;
  expect(formatJsonPreview(circular)).toBe("[object Object]");
});

test("formatDateTime preserves invalid input and recognizes explicit offsets", () => {
  expect(formatDateTime("not-a-date")).toBe("not-a-date");
  expect(formatDateTime("2026-07-13T12:30:00+08:00")).not.toBe(
    "2026-07-13T12:30:00+08:00",
  );
});