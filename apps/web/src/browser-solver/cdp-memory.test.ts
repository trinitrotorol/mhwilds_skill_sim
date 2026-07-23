import { describe, expect, it } from "vitest";

import {
  CDP_FALLBACK_RETENTION_CYCLES,
  cdpHeapPeakBytes,
  decodeHeapUsage,
  decodePrimaryMemory,
  decodePrimaryMemoryDiagnostics,
  memoryExhaustionObserved,
  primaryMemoryFallbackEligible,
  retentionPassed,
  sanitizeDiagnosticMessage,
  verifiedPrimaryMemoryPeakBytes,
} from "./cdp-memory";

function heap(usedSize: number) {
  return decodeHeapUsage({ usedSize, totalSize: usedSize });
}

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

  it("enforces both retention allowance branches at their boundaries", () => {
    expect(retentionPassed(100 * 1024 * 1024, 132 * 1024 * 1024)).toBe(true);
    expect(retentionPassed(100 * 1024 * 1024, 132 * 1024 * 1024 + 1)).toBe(false);
    expect(retentionPassed(200 * 1024 * 1024, 240 * 1024 * 1024)).toBe(true);
    expect(retentionPassed(200 * 1024 * 1024, 240 * 1024 * 1024 + 1)).toBe(false);
  });

  it("records SecurityError capability diagnostics without a stack", () => {
    expect(
      decodePrimaryMemoryDiagnostics({
        api_present: true,
        is_secure_context: true,
        window_cross_origin_isolated: false,
        worker_cross_origin_isolated: false,
        permissions_policy_allows_cross_origin_isolated: false,
        exception_name: "SecurityError",
        exception_message:
          "Memory measurement is unavailable\n    at C:\\secret\\runner.ts:1",
        headless: true,
        stack: "C:\\secret\\runner.ts",
      }),
    ).toEqual({
      api_present: true,
      is_secure_context: true,
      window_cross_origin_isolated: false,
      worker_cross_origin_isolated: false,
      permissions_policy_allows_cross_origin_isolated: false,
      exception_name: "SecurityError",
      exception_message: "Memory measurement is unavailable",
      headless: true,
    });
  });

  it("distinguishes a missing API and unknown permission policy", () => {
    expect(
      decodePrimaryMemoryDiagnostics({
        api_present: false,
        is_secure_context: false,
        window_cross_origin_isolated: false,
        worker_cross_origin_isolated: null,
        permissions_policy_allows_cross_origin_isolated: null,
        exception_name: null,
        exception_message: "measureUserAgentSpecificMemory unavailable",
        headless: false,
      }),
    ).toMatchObject({
      api_present: false,
      is_secure_context: false,
      worker_cross_origin_isolated: null,
      permissions_policy_allows_cross_origin_isolated: null,
      exception_name: null,
      headless: false,
    });
  });

  it("accepts CDP fallback only for a known unavailable primary capability", () => {
    const base = {
      api_present: true,
      is_secure_context: true,
      window_cross_origin_isolated: true,
      worker_cross_origin_isolated: true,
      permissions_policy_allows_cross_origin_isolated: null,
      exception_name: "SecurityError",
      exception_message:
        "Failed to execute 'measureUserAgentSpecificMemory' on 'Performance': performance.measureUserAgentSpecificMemory is not available.",
      headless: true,
    };
    expect(primaryMemoryFallbackEligible([base])).toBe(true);
    expect(
      primaryMemoryFallbackEligible([
        { ...base, api_present: false, exception_name: null },
      ]),
    ).toBe(true);
    expect(
      primaryMemoryFallbackEligible([
        { ...base, exception_name: "OperationError" },
      ]),
    ).toBe(false);
    expect(
      primaryMemoryFallbackEligible([
        { ...base, window_cross_origin_isolated: false },
      ]),
    ).toBe(false);
    expect(
      primaryMemoryFallbackEligible([
        {
          ...base,
          permissions_policy_allows_cross_origin_isolated: false,
        },
      ]),
    ).toBe(false);
    expect(primaryMemoryFallbackEligible([])).toBe(false);
  });

  it("recognizes OOM diagnostics without treating capability errors as OOM", () => {
    expect(
      memoryExhaustionObserved([
        null,
        "SecurityError: memory measurement is unavailable",
      ]),
    ).toBe(false);
    expect(
      memoryExhaustionObserved(["OperationError: allocation failed"]),
    ).toBe(true);
  });

  it("retains a verified primary peak when other samples are unavailable", () => {
    const sample = decodePrimaryMemory({
      bytes: 512 * 1024 * 1024 + 1,
      breakdown: [],
    });
    expect(verifiedPrimaryMemoryPeakBytes([null, sample, null])).toBe(
      512 * 1024 * 1024 + 1,
    );
    expect(verifiedPrimaryMemoryPeakBytes([null, null])).toBeNull();
  });

  it("sanitizes one line and removes paths, URLs, secrets, and stack frames", () => {
    expect(
      sanitizeDiagnosticMessage(
        "denied at C:\\Users\\name\\profile token=abc\nat worker.ts:2",
      ),
    ).toBe("denied at [redacted-path] token=[redacted]");
    expect(sanitizeDiagnosticMessage("at C:\\private\\worker.ts:2")).toBe(
      "stack frame removed",
    );
    expect(
      sanitizeDiagnosticMessage("failed at file:///C:/private/worker.ts"),
    ).toBe("failed at [redacted-url]");
  });

  it("requires complete page and active Worker heap stages for a CDP peak", () => {
    const stages = [
      { page: heap(10), worker: null, worker_required: false },
      { page: heap(20), worker: heap(30), worker_required: true },
    ];
    expect(cdpHeapPeakBytes(stages)).toBe(50);
    expect(cdpHeapPeakBytes([])).toBeNull();
    expect(
      cdpHeapPeakBytes([
        ...stages,
        { page: heap(40), worker: null, worker_required: true },
      ]),
    ).toBeNull();
    expect(CDP_FALLBACK_RETENTION_CYCLES).toBe(10);
  });

  it("rejects invalid metrics", () => {
    expect(() => decodeHeapUsage({ usedSize: -1, totalSize: 2 })).toThrow();
    expect(() => decodePrimaryMemory({ bytes: Number.NaN })).toThrow();
    expect(() =>
      decodePrimaryMemoryDiagnostics({
        api_present: "yes",
      }),
    ).toThrow();
    expect(() => retentionPassed(-1, 0)).toThrow();
  });
});
