import { describe, expect, it } from "vitest";

import {
  cpuThrottleVerified,
  summarizeCalibration,
} from "./cpu-calibration";

describe("CPU calibration", () => {
  it("uses exactly three samples and their median ratio", () => {
    const result = summarizeCalibration([12, 10, 11], [44, 40, 42]);
    expect(result.rate_ratio).toBeCloseTo(42 / 11);
    expect(cpuThrottleVerified(result)).toBe(true);
  });

  it.each([
    [[10, 10, 10], [20, 20, 20]],
    [[10, 10, 10], [70, 70, 70]],
    [[10, 10], [40, 40, 40]],
    [[0, 10, 10], [40, 40, 40]],
    [[Number.NaN, 10, 10], [40, 40, 40]],
  ])("rejects invalid or out-of-range samples", (rate1, rate4) => {
    expect(cpuThrottleVerified(summarizeCalibration(rate1, rate4))).toBe(false);
  });
});
