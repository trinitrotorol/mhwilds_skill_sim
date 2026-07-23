import { describe, expect, it } from "vitest";

import {
  decideCertification,
  parseCertificationArguments,
  statistics,
} from "./certification";

const required = [
  "--catalog", "catalog.json",
  "--oracle", "oracle.json",
  "--output", "report.json",
  "--screenshot-directory", "screenshots",
];

function goInput() {
  return {
    workerCalibration: {
      rate_1_ms: [10, 10, 10],
      rate_4_ms: [40, 40, 40],
      rate_ratio: 4,
    },
    desktopMixedMs: [1000, 1100, 1200, 1050, 1150],
    mobileCaseMediansMs: [4000],
    mobileCaseMaxMs: [6000],
    workerInitMedianMs: 1000,
    parityFailures: 0,
    invalidCandidates: 0,
    nondeterministicCases: 0,
    timeouts: 0,
    errors: 0,
    tabCrashes: 0,
    primaryMemoryAvailable: true,
    postMixedBytes: 100,
    fullSuitePeakBytes: 120,
    postInitIncrementBytes: 20,
    firstPostTerminateBytes: 80,
    finalPostTerminateBytes: 82,
    retentionContinuouslyIncreasing: false,
    cancelRestartPassed: true,
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
    const input = { ...goInput(), primaryMemoryAvailable: false };
    expect(decideCertification(input).status).toBe("CONDITIONAL");
  });

  it.each([
    { parityFailures: 1 },
    { tabCrashes: 1 },
    {
      workerCalibration: {
        rate_1_ms: [10, 10, 10],
        rate_4_ms: [20, 20, 20],
        rate_ratio: 2,
      },
    },
  ])("returns NO-GO for a hard failure", (change) => {
    expect(decideCertification({ ...goInput(), ...change }).status).toBe("NO-GO");
  });

  it("calculates variability and handles a zero median ratio", () => {
    expect(statistics([1, 2, 3])).toMatchObject({ min: 1, median: 2, max: 3 });
    expect(statistics([0, 0, 0]).max_median_ratio).toBeNull();
  });
});
