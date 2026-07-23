import { describe, expect, it } from "vitest";

import {
  decodeHeapUsage,
  decodePrimaryMemory,
  retentionPassed,
} from "./cdp-memory";

describe("CDP and primary memory decoding", () => {
  it("decodes page or Worker heap without assuming optional metrics", () => {
    expect(decodeHeapUsage({ usedSize: 1, totalSize: 2 })).toEqual({
      used_size: 1,
      total_size: 2,
      embedder_heap_used_size: null,
      backing_storage_size: null,
    });
  });

  it("keeps an unknown primary breakdown shape", () => {
    const breakdown = [{ bytes: 3, attribution: ["worker"] }];
    expect(decodePrimaryMemory({ bytes: 4, breakdown })).toEqual({
      bytes: 4,
      breakdown,
      method: "measureUserAgentSpecificMemory",
    });
  });

  it("enforces the five-cycle retention boundary", () => {
    expect(retentionPassed(100 * 1024 * 1024, 132 * 1024 * 1024)).toBe(true);
    expect(retentionPassed(100 * 1024 * 1024, 132 * 1024 * 1024 + 1)).toBe(false);
  });

  it("rejects invalid metrics", () => {
    expect(() => decodeHeapUsage({ usedSize: -1, totalSize: 2 })).toThrow();
    expect(() => decodePrimaryMemory({ bytes: Number.NaN })).toThrow();
  });
});
