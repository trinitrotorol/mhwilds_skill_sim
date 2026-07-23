import { describe, expect, it } from "vitest";

import {
  MIB,
  decideCertification,
  parseCertificationArguments,
  statistics,
} from "./certification";
import { summarizeWorkerCalibration } from "./cpu-calibration";
import type {
  WorkerThrottleApplySummary,
  WorkerThrottleSupport,
} from "./worker-cdp-controller";

const required = [
  "--catalog", "catalog.json",
  "--oracle", "oracle.json",
  "--output", "report.json",
  "--screenshot-directory", "screenshots",
];

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
        target_title: null,
        requested_rate: rate,
        support,
        protocol_error_code: support === "applied" ? null : -32_601,
        protocol_error_message:
          support === "applied" ? null : "CDP command failed",
      },
    ],
  };
}

function workerCalibration(
  support: WorkerThrottleSupport | "not-attached" = "applied",
  ratio = 4,
) {
  return summarizeWorkerCalibration(
    applySummary(1),
    applySummary(4, support),
    [10, 10, 10],
    [ratio * 10, ratio * 10, ratio * 10],
  );
}

function goInput() {
  return {
    workerCalibration: workerCalibration(),
    desktopMixedMs: [1000, 1100, 1200, 1050, 1150],
    mobileCaseMediansMs: [4000, 4000, 4000, 4000, 4000],
    mobileCaseMaxMs: [6000, 6000, 6000, 6000, 6000],
    mobileAcceptanceCaseCount: 5,
    mobileAcceptanceTimeouts: 0,
    workerInitMedianMs: 1000,
    parityFailures: 0,
    invalidCandidates: 0,
    nondeterministicCases: 0,
    timeouts: 0,
    errors: 0,
    tabCrashes: 0,
    browserMemoryExhaustion: false,
    primaryMemoryAvailable: true,
    primaryMemoryFallbackEligible: false,
    postMixedBytes: 100,
    fullSuitePeakBytes: 120,
    postInitIncrementBytes: 20,
    firstPostTerminateBytes: 80,
    finalPostTerminateBytes: 82,
    retentionContinuouslyIncreasing: false,
    cdpMemoryStagesComplete: false,
    cdpMemoryPeakBytes: null,
    cdpRetentionCycleCount: 0,
    cdpFirstPostTerminatePageBytes: null,
    cdpFinalPostTerminatePageBytes: null,
    cdpRetentionContinuouslyIncreasing: false,
    verifiedTotalMemoryPeakBytes: 120,
    cancelRestartPassed: true,
  };
}

function cdpFallbackInput() {
  return {
    ...goInput(),
    primaryMemoryAvailable: false,
    primaryMemoryFallbackEligible: true,
    postMixedBytes: null,
    fullSuitePeakBytes: null,
    postInitIncrementBytes: null,
    firstPostTerminateBytes: null,
    finalPostTerminateBytes: null,
    retentionContinuouslyIncreasing: false,
    cdpMemoryStagesComplete: true,
    cdpMemoryPeakBytes: 256 * MIB,
    cdpRetentionCycleCount: 10,
    cdpFirstPostTerminatePageBytes: 100 * MIB,
    cdpFinalPostTerminatePageBytes: 132 * MIB,
    cdpRetentionContinuouslyIncreasing: false,
    verifiedTotalMemoryPeakBytes: 256 * MIB,
  };
}

describe("certification CLI arguments", () => {
  it("applies defaults and accepts headed", () => {
    expect(parseCertificationArguments([...required, "--headed"])).toMatchObject({
      repeats: 5,
      timeoutMs: 20_000,
      headed: true,
    });
  });

  it.each([
    { argv: [...required, "--repeats", "2"] },
    { argv: [...required, "--timeout-ms", "999"] },
    { argv: [...required, "--catalog", "again"] },
    { argv: [...required, "--unknown", "value"] },
  ])("rejects invalid arguments", ({ argv }) => {
    expect(() => parseCertificationArguments(argv)).toThrow();
  });
});

describe("certification decision", () => {
  it("returns GO only when every gate passes", () => {
    expect(decideCertification(goInput()).status).toBe("GO");
  });

  it("returns CONDITIONAL for unavailable primary memory", () => {
    const input = {
      ...goInput(),
      primaryMemoryAvailable: false,
      primaryMemoryFallbackEligible: false,
      postMixedBytes: null,
      fullSuitePeakBytes: null,
      postInitIncrementBytes: null,
      firstPostTerminateBytes: null,
      finalPostTerminateBytes: null,
      verifiedTotalMemoryPeakBytes: null,
    };
    expect(decideCertification(input).status).toBe("CONDITIONAL");
  });

  it.each([
    { parityFailures: 1 },
    { invalidCandidates: 1 },
    { nondeterministicCases: 1 },
    { tabCrashes: 1 },
    { browserMemoryExhaustion: true },
    { verifiedTotalMemoryPeakBytes: 512 * MIB + 1 },
  ])("returns NO-GO for a hard failure", (change) => {
    expect(decideCertification({ ...goInput(), ...change }).status).toBe("NO-GO");
  });

  it.each([
    { workerCalibration: workerCalibration("unsupported") },
    { workerCalibration: workerCalibration("not-attached") },
    { workerCalibration: workerCalibration("applied", 2) },
    {
      mobileCaseMediansMs: [8001, 4000, 4000, 4000, 4000],
      mobileCaseMaxMs: [8001, 6000, 6000, 6000, 6000],
    },
  ])("returns CONDITIONAL for incomplete measurement evidence", (change) => {
    expect(decideCertification({ ...goInput(), ...change }).status).toBe(
      "CONDITIONAL",
    );
  });

  it("uses a strict majority timeout as NO-GO only with verified 4x evidence", () => {
    expect(
      decideCertification({
        ...goInput(),
        timeouts: 3,
        mobileAcceptanceTimeouts: 3,
      }).status,
    ).toBe("NO-GO");
    expect(
      decideCertification({
        ...goInput(),
        timeouts: 2,
        mobileAcceptanceTimeouts: 2,
      }).status,
    ).toBe("CONDITIONAL");
    expect(
      decideCertification({
        ...goInput(),
        workerCalibration: workerCalibration("unsupported"),
        timeouts: 3,
        mobileAcceptanceTimeouts: 3,
      }).status,
    ).toBe("CONDITIONAL");
  });

  it("accepts complete CDP fallback evidence at both boundaries", () => {
    const decision = decideCertification(cdpFallbackInput());
    expect(decision.status).toBe("GO");
    expect(decision.warnings).toContain(
      "primary memory measurement unavailable; complete CDP fallback accepted",
    );
  });

  it("keeps complete CDP evidence CONDITIONAL after an unexpected primary failure", () => {
    expect(
      decideCertification({
        ...cdpFallbackInput(),
        primaryMemoryFallbackEligible: false,
      }).status,
    ).toBe("CONDITIONAL");
  });

  it.each([
    { cdpMemoryPeakBytes: 256 * MIB + 1 },
    { cdpFinalPostTerminatePageBytes: 132 * MIB + 1 },
    { cdpRetentionCycleCount: 9 },
    { cdpMemoryStagesComplete: false },
  ])("keeps an incomplete CDP fallback CONDITIONAL", (change) => {
    expect(
      decideCertification({ ...cdpFallbackInput(), ...change }).status,
    ).toBe("CONDITIONAL");
  });

  it("treats verified continuous retention above 128 MiB as NO-GO", () => {
    expect(
      decideCertification({
        ...goInput(),
        primaryMemoryAvailable: false,
        firstPostTerminateBytes: 100 * MIB,
        finalPostTerminateBytes: 228 * MIB + 1,
        retentionContinuouslyIncreasing: true,
      }).status,
    ).toBe("NO-GO");
  });

  it("treats verified CDP continuous retention above 128 MiB as NO-GO", () => {
    expect(
      decideCertification({
        ...cdpFallbackInput(),
        cdpMemoryStagesComplete: false,
        cdpFirstPostTerminatePageBytes: 100 * MIB,
        cdpFinalPostTerminatePageBytes: 228 * MIB + 1,
        cdpRetentionContinuouslyIncreasing: true,
      }).status,
    ).toBe("NO-GO");
  });

  it("requires nonempty and internally consistent mobile evidence for GO", () => {
    expect(
      decideCertification({
        ...goInput(),
        mobileCaseMediansMs: [],
        mobileCaseMaxMs: [],
        mobileAcceptanceCaseCount: 0,
      }).status,
    ).toBe("CONDITIONAL");
    expect(
      decideCertification({
        ...goInput(),
        mobileCaseMaxMs: [],
      }).status,
    ).toBe("CONDITIONAL");
  });

  it("does not cross hard memory boundaries at the exact limit", () => {
    expect(
      decideCertification({
        ...goInput(),
        verifiedTotalMemoryPeakBytes: 512 * MIB,
      }).status,
    ).toBe("GO");
    expect(
      decideCertification({
        ...goInput(),
        firstPostTerminateBytes: 100 * MIB,
        finalPostTerminateBytes: 228 * MIB,
        retentionContinuouslyIncreasing: true,
      }).status,
    ).not.toBe("NO-GO");
  });

  it("preserves its input and returns checks in stable order", () => {
    const input = goInput();
    const before = JSON.stringify(input);
    const decision = decideCertification(input);
    expect(JSON.stringify(input)).toBe(before);
    expect(decision.checks.map(({ name }) => name)).toEqual([
      "cpu_throttle_verified",
      "desktop_stability",
      "mobile_performance",
      "correctness",
      "runtime_health",
      "memory_limits",
      "retention",
      "cancel_restart",
    ]);
  });

  it("calculates variability and handles a zero median ratio", () => {
    expect(statistics([1, 2, 3])).toMatchObject({ min: 1, median: 2, max: 3 });
    expect(statistics([0, 0, 0]).max_median_ratio).toBeNull();
  });
});
