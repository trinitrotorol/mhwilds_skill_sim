import { describe, expect, it } from "vitest";

import {
  assertWorkerThrottleApplySucceeded,
  collectCalibrationSamples,
  cpuThrottleVerified,
  summarizeCalibration,
  summarizeWorkerCalibration,
} from "./cpu-calibration";
import type {
  WorkerThrottleApplySummary,
  WorkerThrottleSupport,
} from "./worker-cdp-controller";

function applySummary(
  rate: 1 | 4,
  support: WorkerThrottleSupport | "not-attached" = "applied",
): WorkerThrottleApplySummary {
  if (support === "not-attached") {
    return {
      requested_rate: rate,
      active_worker_count: 0,
      applied_count: 0,
      unsupported_count: 0,
      failed_count: 0,
      sessions: [],
    };
  }
  return {
    requested_rate: rate,
    active_worker_count: 1,
    applied_count: support === "applied" ? 1 : 0,
    unsupported_count: support === "unsupported" ? 1 : 0,
    failed_count: support === "failed" ? 1 : 0,
    sessions: [
      {
        target_type: "worker",
        target_title: "solver Worker",
        requested_rate: rate,
        support,
        protocol_error_code: support === "applied" ? null : -32_601,
        protocol_error_message:
          support === "applied" ? null : "CDP command failed",
      },
    ],
  };
}

describe("CPU calibration", () => {
  it("uses exactly three samples and their median ratio", () => {
    const result = summarizeCalibration([12, 10, 11], [44, 40, 42]);
    expect(result.rate_ratio).toBeCloseTo(42 / 11);
    const worker = summarizeWorkerCalibration(
      applySummary(1),
      applySummary(4),
      result.rate_1_ms,
      result.rate_4_ms,
    );
    expect(worker.calibration_samples).toEqual({
      rate_1_ms: [12, 10, 11],
      rate_4_ms: [44, 40, 42],
    });
    expect(worker.median_ratio).toBeCloseTo(42 / 11);
    expect(worker.measurement_status).toBe("verified");
    expect(cpuThrottleVerified(worker)).toBe(true);
  });

  it.each([
    [[10, 10], [40, 40, 40]],
    [[0, 10, 10], [40, 40, 40]],
    [[Number.NaN, 10, 10], [40, 40, 40]],
  ])("rejects invalid samples as a runner failure", (rate1, rate4) => {
    expect(() =>
      summarizeWorkerCalibration(
        applySummary(1),
        applySummary(4),
        rate1,
        rate4,
      ),
    ).toThrow("three valid samples");
  });

  it.each([
    ["unsupported", "unsupported"],
    ["failed", "failed"],
    ["not-attached", "not-attached"],
  ] as const)(
    "distinguishes an %s apply outcome",
    (support, expectedStatus) => {
      const result = summarizeWorkerCalibration(
        applySummary(1),
        applySummary(4, support),
        [10, 10, 10],
        [40, 40, 40],
      );
      expect(result.measurement_status).toBe(expectedStatus);
      expect(result.failure_kind).toBe(
        support === "failed" ? "harness-or-transport" : null,
      );
      expect(result.verified).toBe(false);
    },
  );

  it("keeps an applied but out-of-range ratio distinct from harness failure", () => {
    const result = summarizeWorkerCalibration(
      applySummary(1),
      applySummary(4),
      [10, 10, 10],
      [20, 20, 20],
    );
    expect(result.rate_4_apply.applied_count).toBe(1);
    expect(result.median_ratio).toBe(2);
    expect(result.measurement_status).toBe("unverified");
    expect(result.failure_kind).toBeNull();
    expect(result.verified).toBe(false);
  });

  it("throws for apply failures while allowing unsupported evidence", () => {
    expect(() =>
      assertWorkerThrottleApplySucceeded(
        applySummary(4, "failed"),
        "calibration",
      ),
    ).toThrow("calibration Worker CPU throttle application failed");
    expect(() =>
      assertWorkerThrottleApplySucceeded(
        applySummary(4, "unsupported"),
        "calibration",
      ),
    ).not.toThrow();
  });

  it("excludes one warm-up and records exactly three paired samples", async () => {
    const calls: string[] = [];
    const pageValues = [999, 12, 10, 11];
    const workerValues = [888, 44, 40, 42];
    const samples = await collectCalibrationSamples(
      async () => {
        calls.push("page");
        return pageValues.shift()!;
      },
      async () => {
        calls.push("worker");
        return workerValues.shift()!;
      },
    );

    expect(calls).toEqual([
      "page",
      "worker",
      "page",
      "worker",
      "page",
      "worker",
      "page",
      "worker",
    ]);
    expect(samples).toEqual({
      page: [12, 10, 11],
      worker: [44, 40, 42],
    });
  });

  it("rejects a stale apply summary without changing the inputs", () => {
    const stale = applySummary(4);
    const rate1 = Object.freeze([12, 10, 11]);
    const rate4 = Object.freeze([44, 40, 42]);
    expect(() =>
      summarizeWorkerCalibration(stale, applySummary(4), rate1, rate4),
    ).toThrow("stale");
    expect(rate1).toEqual([12, 10, 11]);
    expect(rate4).toEqual([44, 40, 42]);
  });
});
