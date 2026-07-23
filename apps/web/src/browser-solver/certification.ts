import { calculateMedian } from "./benchmark";
import { cpuThrottleVerified, type CalibrationSamples } from "./cpu-calibration";
import { retentionPassed } from "./cdp-memory";

export const MIB = 1024 * 1024;

export interface CertificationArguments {
  readonly catalog: string;
  readonly oracle: string;
  readonly output: string;
  readonly screenshotDirectory: string;
  readonly repeats: number;
  readonly timeoutMs: number;
  readonly headed: boolean;
}

const VALUE_ARGUMENTS = new Map([
  ["--catalog", "catalog"],
  ["--oracle", "oracle"],
  ["--output", "output"],
  ["--screenshot-directory", "screenshotDirectory"],
] as const);

function boundedInteger(
  value: string,
  name: string,
  minimum: number,
  maximum: number,
): number {
  if (!/^[1-9][0-9]*$/u.test(value)) {
    throw new TypeError(`${name} must be a positive exact integer`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new TypeError(`${name} must be between ${minimum} and ${maximum}`);
  }
  return parsed;
}

export function parseCertificationArguments(
  argv: readonly string[],
): CertificationArguments {
  const values = new Map<string, string>();
  let repeats = 5;
  let timeoutMs = 20_000;
  let headed = false;
  for (let index = 0; index < argv.length; index += 1) {
    const name = argv[index]!;
    if (name === "--headed") {
      if (headed) throw new TypeError("duplicate argument: --headed");
      headed = true;
      continue;
    }
    if (
      !VALUE_ARGUMENTS.has(name as never) &&
      name !== "--repeats" &&
      name !== "--timeout-ms"
    ) {
      throw new TypeError(`unknown argument: ${name}`);
    }
    if (values.has(name)) throw new TypeError(`duplicate argument: ${name}`);
    const value = argv[++index];
    if (value === undefined || value.startsWith("--")) {
      throw new TypeError(`missing value for ${name}`);
    }
    values.set(name, value);
  }
  for (const required of VALUE_ARGUMENTS.keys()) {
    if (!values.has(required)) throw new TypeError(`missing ${required}`);
  }
  if (values.has("--repeats")) {
    repeats = boundedInteger(values.get("--repeats")!, "--repeats", 3, 10);
  }
  if (values.has("--timeout-ms")) {
    timeoutMs = boundedInteger(
      values.get("--timeout-ms")!,
      "--timeout-ms",
      1_000,
      60_000,
    );
  }
  return {
    catalog: values.get("--catalog")!,
    oracle: values.get("--oracle")!,
    output: values.get("--output")!,
    screenshotDirectory: values.get("--screenshot-directory")!,
    repeats,
    timeoutMs,
    headed,
  };
}

export function statistics(values: readonly number[]) {
  if (values.length === 0 || values.some((value) => !Number.isFinite(value))) {
    throw new TypeError("statistics require finite values");
  }
  const median = calculateMedian(values);
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance =
    values.reduce((sum, value) => sum + (value - mean) ** 2, 0) /
    values.length;
  return {
    min: Math.min(...values),
    median,
    max: Math.max(...values),
    coefficient_of_variation: mean === 0 ? null : Math.sqrt(variance) / mean,
    max_median_ratio: median === 0 ? null : Math.max(...values) / median,
  };
}

export interface DecisionInput {
  readonly workerCalibration: CalibrationSamples;
  readonly desktopMixedMs: readonly number[];
  readonly mobileCaseMediansMs: readonly number[];
  readonly mobileCaseMaxMs: readonly number[];
  readonly workerInitMedianMs: number;
  readonly parityFailures: number;
  readonly invalidCandidates: number;
  readonly nondeterministicCases: number;
  readonly timeouts: number;
  readonly errors: number;
  readonly tabCrashes: number;
  readonly primaryMemoryAvailable: boolean;
  readonly postMixedBytes: number | null;
  readonly fullSuitePeakBytes: number | null;
  readonly postInitIncrementBytes: number | null;
  readonly firstPostTerminateBytes: number | null;
  readonly finalPostTerminateBytes: number | null;
  readonly retentionContinuouslyIncreasing: boolean;
  readonly cancelRestartPassed: boolean;
}

export function decideCertification(input: DecisionInput) {
  const failures: string[] = [];
  const warnings: string[] = [];
  const checks: Array<{ name: string; passed: boolean }> = [];
  const check = (name: string, passed: boolean): void => {
    checks.push({ name, passed });
    if (!passed) failures.push(name);
  };
  const desktop = statistics(input.desktopMixedMs);
  check("cpu_throttle_verified", cpuThrottleVerified(input.workerCalibration));
  check(
    "desktop_stability",
    desktop.max <= 10_000 &&
      desktop.median <= 3_000 &&
      (desktop.max_median_ratio ?? Infinity) <= 3,
  );
  check(
    "mobile_performance",
    input.mobileCaseMediansMs.every((value) => value <= 8_000) &&
      input.mobileCaseMaxMs.every((value) => value <= 20_000) &&
      input.workerInitMedianMs <= 3_000,
  );
  check(
    "correctness",
    input.parityFailures === 0 &&
      input.invalidCandidates === 0 &&
      input.nondeterministicCases === 0,
  );
  check(
    "runtime_health",
    input.timeouts === 0 && input.errors === 0 && input.tabCrashes === 0,
  );
  check("primary_memory_available", input.primaryMemoryAvailable);
  check(
    "memory_limits",
    input.postMixedBytes !== null &&
      input.postMixedBytes <= 256 * MIB &&
      input.fullSuitePeakBytes !== null &&
      input.fullSuitePeakBytes <= 256 * MIB &&
      input.postInitIncrementBytes !== null &&
      input.postInitIncrementBytes <= 192 * MIB,
  );
  check(
    "retention",
    input.firstPostTerminateBytes !== null &&
      input.finalPostTerminateBytes !== null &&
      retentionPassed(
        input.firstPostTerminateBytes,
        input.finalPostTerminateBytes,
      ),
  );
  check("cancel_restart", input.cancelRestartPassed);

  const noGo =
    input.parityFailures > 0 ||
    input.invalidCandidates > 0 ||
    input.nondeterministicCases > 0 ||
    input.tabCrashes > 0 ||
    (input.fullSuitePeakBytes ?? 0) > 512 * MIB ||
    (input.retentionContinuouslyIncreasing &&
      input.firstPostTerminateBytes !== null &&
      input.finalPostTerminateBytes !== null &&
      input.finalPostTerminateBytes >
        input.firstPostTerminateBytes + 128 * MIB) ||
    !cpuThrottleVerified(input.workerCalibration);
  if (!input.primaryMemoryAvailable) {
    warnings.push("primary memory measurement unavailable");
  }
  return {
    status: noGo ? ("NO-GO" as const) : failures.length === 0 ? ("GO" as const) : ("CONDITIONAL" as const),
    checks,
    failures,
    warnings,
  };
}
