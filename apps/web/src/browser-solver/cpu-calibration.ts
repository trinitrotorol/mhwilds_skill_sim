import { calculateMedian } from "./benchmark";

export interface CalibrationSamples {
  readonly rate_1_ms: readonly number[];
  readonly rate_4_ms: readonly number[];
  readonly rate_ratio: number | null;
}

function validTiming(value: number): boolean {
  return Number.isFinite(value) && value > 0;
}

export function summarizeCalibration(
  rate1: readonly number[],
  rate4: readonly number[],
): CalibrationSamples {
  if (
    rate1.length !== 3 ||
    rate4.length !== 3 ||
    !rate1.every(validTiming) ||
    !rate4.every(validTiming)
  ) {
    return { rate_1_ms: [...rate1], rate_4_ms: [...rate4], rate_ratio: null };
  }
  return {
    rate_1_ms: [...rate1],
    rate_4_ms: [...rate4],
    rate_ratio: calculateMedian(rate4) / calculateMedian(rate1),
  };
}

export function cpuThrottleVerified(worker: CalibrationSamples): boolean {
  return (
    worker.rate_ratio !== null &&
    worker.rate_ratio >= 2.5 &&
    worker.rate_ratio <= 6.5
  );
}

export function runPageCalibration(iterations: number): number {
  const startedAt = performance.now();
  let checksum = 0x12345678;
  for (let index = 0; index < iterations; index += 1) {
    checksum = Math.imul(checksum ^ index, 1664525) + 1013904223;
  }
  if (!Number.isFinite(checksum)) {
    throw new Error("calibration checksum is invalid");
  }
  return performance.now() - startedAt;
}
