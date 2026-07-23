import { calculateMedian } from "./benchmark";
import type { WorkerThrottleApplySummary } from "./worker-cdp-controller";

export interface CalibrationSamples {
  readonly rate_1_ms: readonly number[];
  readonly rate_4_ms: readonly number[];
  readonly rate_ratio: number | null;
}

export type WorkerCalibrationMeasurementStatus =
  | "verified"
  | "unsupported"
  | "failed"
  | "not-attached"
  | "unverified";

export type WorkerCalibrationFailureKind = "harness-or-transport";

export interface WorkerCalibrationSamples {
  readonly rate_1_ms: readonly number[];
  readonly rate_4_ms: readonly number[];
}

export interface WorkerCalibrationSummary {
  readonly rate_1_apply: WorkerThrottleApplySummary;
  readonly rate_4_apply: WorkerThrottleApplySummary;
  readonly calibration_samples: WorkerCalibrationSamples;
  readonly median_ratio: number | null;
  readonly verified: boolean;
  readonly measurement_status: WorkerCalibrationMeasurementStatus;
  readonly failure_kind: WorkerCalibrationFailureKind | null;
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

function validCount(value: number): boolean {
  return Number.isSafeInteger(value) && value >= 0;
}

function validateApplySummary(
  summary: WorkerThrottleApplySummary,
  expectedRate: number,
): void {
  if (
    summary.requested_rate !== expectedRate ||
    !validCount(summary.active_worker_count) ||
    !validCount(summary.applied_count) ||
    !validCount(summary.unsupported_count) ||
    !validCount(summary.failed_count) ||
    summary.sessions.length !== summary.active_worker_count ||
    summary.applied_count +
      summary.unsupported_count +
      summary.failed_count !==
      summary.active_worker_count
  ) {
    throw new TypeError("Worker throttle apply summary is stale or inconsistent");
  }
  const counted = {
    applied: 0,
    unsupported: 0,
    failed: 0,
  };
  for (const session of summary.sessions) {
    if (
      session.target_type !== "worker" ||
      session.requested_rate !== expectedRate
    ) {
      throw new TypeError(
        "Worker throttle session result is stale or inconsistent",
      );
    }
    counted[session.support] += 1;
  }
  if (
    counted.applied !== summary.applied_count ||
    counted.unsupported !== summary.unsupported_count ||
    counted.failed !== summary.failed_count
  ) {
    throw new TypeError("Worker throttle apply counts are inconsistent");
  }
}

function applyStatus(
  summary: WorkerThrottleApplySummary,
): Exclude<WorkerCalibrationMeasurementStatus, "verified"> | "applied" {
  if (summary.failed_count > 0) {
    return "failed";
  }
  if (summary.active_worker_count === 0) {
    return "not-attached";
  }
  if (
    summary.unsupported_count > 0 ||
    summary.applied_count !== summary.active_worker_count
  ) {
    return "unsupported";
  }
  return "applied";
}

function ratioVerified(ratio: number | null): boolean {
  return ratio !== null && ratio >= 2.5 && ratio <= 6.5;
}

export async function collectCalibrationSamples(
  pageSample: () => Promise<number>,
  workerSample: () => Promise<number>,
): Promise<{
  readonly page: readonly number[];
  readonly worker: readonly number[];
}> {
  await pageSample();
  await workerSample();
  const page: number[] = [];
  const worker: number[] = [];
  for (let index = 0; index < 3; index += 1) {
    page.push(await pageSample());
    worker.push(await workerSample());
  }
  return { page, worker };
}

export function summarizeWorkerCalibration(
  rate1Apply: WorkerThrottleApplySummary,
  rate4Apply: WorkerThrottleApplySummary,
  rate1: readonly number[],
  rate4: readonly number[],
): WorkerCalibrationSummary {
  validateApplySummary(rate1Apply, 1);
  validateApplySummary(rate4Apply, 4);
  const samples = summarizeCalibration(rate1, rate4);
  if (samples.rate_ratio === null) {
    throw new TypeError(
      "Worker CPU calibration requires three valid samples at each rate",
    );
  }
  const rate1Status = applyStatus(rate1Apply);
  const rate4Status = applyStatus(rate4Apply);
  let measurementStatus: WorkerCalibrationMeasurementStatus;
  let failureKind: WorkerCalibrationFailureKind | null = null;
  if (rate1Status === "failed" || rate4Status === "failed") {
    measurementStatus = "failed";
    failureKind = "harness-or-transport";
  } else if (
    rate1Status === "not-attached" ||
    rate4Status === "not-attached"
  ) {
    measurementStatus = "not-attached";
  } else if (
    rate1Status === "unsupported" ||
    rate4Status === "unsupported"
  ) {
    measurementStatus = "unsupported";
  } else {
    measurementStatus = ratioVerified(samples.rate_ratio)
      ? "verified"
      : "unverified";
  }
  const verified = measurementStatus === "verified";
  return {
    rate_1_apply: rate1Apply,
    rate_4_apply: rate4Apply,
    calibration_samples: {
      rate_1_ms: samples.rate_1_ms,
      rate_4_ms: samples.rate_4_ms,
    },
    median_ratio: samples.rate_ratio,
    verified,
    measurement_status: measurementStatus,
    failure_kind: failureKind,
  };
}

export function cpuThrottleVerified(
  worker: WorkerCalibrationSummary,
): boolean {
  return worker.measurement_status === "verified" && worker.verified;
}

export function assertWorkerThrottleApplySucceeded(
  summary: WorkerThrottleApplySummary,
  context: string,
): void {
  if (summary.failed_count > 0) {
    throw new Error(`${context} Worker CPU throttle application failed`);
  }
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
