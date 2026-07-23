import type {
  BrowserRankedSearchRequest,
  BrowserSolverResult,
} from "./types";
import { decodeBrowserRankedSearchRequest } from "./validation";

export const BROWSER_SOLVER_BENCHMARK_CATALOG_URL =
  "/__browser-solver-benchmark/catalog.json";
export const BROWSER_SOLVER_BENCHMARK_ORACLE_URL =
  "/__browser-solver-benchmark/oracle.json";

export type BrowserBenchmarkRuntime = "node" | "browser";

export interface BrowserBenchmarkTimings {
  readonly min: number;
  readonly median: number;
  readonly max: number;
}

export interface BrowserBenchmarkCaseReport {
  readonly name: string;
  readonly request: BrowserRankedSearchRequest;
  readonly result: BrowserSolverResult;
  readonly timings_ms: BrowserBenchmarkTimings;
  readonly deterministic: boolean;
  readonly parity: boolean | null;
}

export interface BrowserBenchmarkReport {
  readonly format_version: 1;
  readonly source_catalog_sha256: string;
  readonly runtime: BrowserBenchmarkRuntime;
  readonly timeout_ms: number;
  readonly repeats: number;
  readonly cases: ReadonlyArray<BrowserBenchmarkCaseReport>;
  readonly environment?: Readonly<Record<string, unknown>>;
}

interface OracleCase {
  readonly name: string;
  readonly request: BrowserRankedSearchRequest;
  readonly status: "optimal" | "infeasible" | "timed-out";
  readonly candidate_exists: boolean;
  readonly preference_score: number | null;
  readonly decoration_count: number | null;
}

export interface BenchmarkRunContext {
  readonly name: string;
  readonly runIndex: number;
  readonly warmup: boolean;
}

export interface RunBrowserBenchmarkOptions {
  readonly sourceCatalogSha256: string;
  readonly oracleValue: unknown;
  readonly runtime: BrowserBenchmarkRuntime;
  readonly timeoutMs: number;
  readonly repeats: number;
  readonly runCase: (
    request: BrowserRankedSearchRequest,
    context: BenchmarkRunContext,
  ) => BrowserSolverResult | Promise<BrowserSolverResult>;
  readonly validateResult?: (
    request: BrowserRankedSearchRequest,
    result: BrowserSolverResult,
  ) => void;
  readonly now?: () => number;
  readonly environment?: Readonly<Record<string, unknown>>;
  readonly onCaseComplete?: (
    report: BrowserBenchmarkCaseReport,
  ) => void;
}

function plainObject(
  value: unknown,
  path: string,
): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError(`${path} must be an object`);
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    throw new TypeError(`${path} must be a plain object`);
  }
  return value as Record<string, unknown>;
}

function nonnegativeInteger(value: unknown, path: string): number {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < 0
  ) {
    throw new TypeError(`${path} must be a nonnegative safe integer`);
  }
  return value;
}

function nullableObjective(value: unknown, path: string): number | null {
  return value === null ? null : nonnegativeInteger(value, path);
}

function decodeOracleCases(
  value: unknown,
  sourceCatalogSha256: string,
): readonly OracleCase[] {
  const report = plainObject(value, "oracle");
  if (report.format_version !== 1) {
    throw new TypeError("oracle.format_version must be exactly 1");
  }
  if (report.source_catalog_sha256 !== sourceCatalogSha256) {
    throw new Error("oracle source Catalog hash does not match");
  }
  if (!Array.isArray(report.cases)) {
    throw new TypeError("oracle.cases must be an array");
  }
  return report.cases.map((caseValue, index) => {
    const path = `oracle.cases[${index}]`;
    const item = plainObject(caseValue, path);
    if (
      typeof item.name !== "string" ||
      item.name.length === 0 ||
      item.name.trim() !== item.name
    ) {
      throw new TypeError(`${path}.name must be a non-empty trimmed string`);
    }
    if (
      item.status !== "optimal" &&
      item.status !== "infeasible" &&
      item.status !== "timed-out"
    ) {
      throw new TypeError(`${path}.status is invalid`);
    }
    if (typeof item.candidate_exists !== "boolean") {
      throw new TypeError(`${path}.candidate_exists must be boolean`);
    }
    const preferenceScore = nullableObjective(
      item.preference_score,
      `${path}.preference_score`,
    );
    const decorationCount = nullableObjective(
      item.decoration_count,
      `${path}.decoration_count`,
    );
    if (
      item.candidate_exists !==
      (preferenceScore !== null && decorationCount !== null)
    ) {
      throw new TypeError(`${path} has inconsistent objective fields`);
    }
    if (item.status === "optimal" && !item.candidate_exists) {
      throw new TypeError(`${path} optimal status requires a candidate`);
    }
    if (item.status === "infeasible" && item.candidate_exists) {
      throw new TypeError(`${path} infeasible status forbids a candidate`);
    }
    return Object.freeze({
      name: item.name,
      request: decodeBrowserRankedSearchRequest(item.request),
      status: item.status,
      candidate_exists: item.candidate_exists,
      preference_score: preferenceScore,
      decoration_count: decorationCount,
    });
  });
}

function validateBenchmarkNumber(
  value: number,
  name: string,
  positive: boolean,
): void {
  if (
    !Number.isSafeInteger(value) ||
    (positive ? value < 1 : value < 0)
  ) {
    throw new TypeError(
      `${name} must be a ${positive ? "positive" : "nonnegative"} safe integer`,
    );
  }
}

function roundedMilliseconds(value: number): number {
  if (!Number.isFinite(value) || value < 0) {
    throw new Error("benchmark clock returned an invalid elapsed time");
  }
  return Math.round(value * 1_000_000) / 1_000_000;
}

export function calculateMedian(values: readonly number[]): number {
  if (values.length === 0) {
    throw new TypeError("median requires at least one value");
  }
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  const upper = sorted[middle];
  if (upper === undefined) {
    throw new Error("median input unexpectedly became empty");
  }
  if (sorted.length % 2 === 1) {
    return upper;
  }
  const lower = sorted[middle - 1];
  if (lower === undefined) {
    throw new Error("median input is missing its lower midpoint");
  }
  return (lower + upper) / 2;
}

function deterministicSignature(result: BrowserSolverResult): string {
  return JSON.stringify({
    status: result.status,
    candidate: result.candidate,
    selected_variant_ids: result.selected_variant_ids,
    preference_score: result.preference_score,
    decoration_count: result.decoration_count,
  });
}

function objectiveParity(
  result: BrowserSolverResult,
  oracle: OracleCase,
): boolean | null {
  const completed =
    result.status === "optimal" || result.status === "infeasible";
  const oracleCompleted =
    oracle.status === "optimal" || oracle.status === "infeasible";
  if (!completed || !oracleCompleted) {
    return null;
  }
  const candidateExists = result.candidate !== null;
  return (
    result.status === oracle.status &&
    candidateExists === oracle.candidate_exists &&
    result.preference_score === oracle.preference_score &&
    result.decoration_count === oracle.decoration_count
  );
}

export async function runBrowserSolverBenchmark(
  options: RunBrowserBenchmarkOptions,
): Promise<BrowserBenchmarkReport> {
  validateBenchmarkNumber(options.timeoutMs, "timeoutMs", false);
  validateBenchmarkNumber(options.repeats, "repeats", true);
  if (!/^[0-9a-f]{64}$/u.test(options.sourceCatalogSha256)) {
    throw new TypeError(
      "sourceCatalogSha256 must be a lowercase 64-character SHA-256",
    );
  }
  const oracleCases = decodeOracleCases(
    options.oracleValue,
    options.sourceCatalogSha256,
  );
  const now = options.now ?? (() => performance.now());
  const reports: BrowserBenchmarkCaseReport[] = [];

  for (const oracle of oracleCases) {
    const warmup = await options.runCase(oracle.request, {
      name: oracle.name,
      runIndex: -1,
      warmup: true,
    });
    options.validateResult?.(oracle.request, warmup);

    const results: BrowserSolverResult[] = [];
    const timings: number[] = [];
    for (let runIndex = 0; runIndex < options.repeats; runIndex += 1) {
      const startedAt = now();
      const result = await options.runCase(oracle.request, {
        name: oracle.name,
        runIndex,
        warmup: false,
      });
      const elapsed = roundedMilliseconds(now() - startedAt);
      options.validateResult?.(oracle.request, result);
      results.push(result);
      timings.push(elapsed);
    }
    const first = results[0];
    if (first === undefined) {
      throw new Error("benchmark produced no measured result");
    }
    const firstSignature = deterministicSignature(first);
    const report: BrowserBenchmarkCaseReport = {
      name: oracle.name,
      request: oracle.request,
      result: first,
      timings_ms: {
        min: Math.min(...timings),
        median: calculateMedian(timings),
        max: Math.max(...timings),
      },
      deterministic: results.every(
        (result) => deterministicSignature(result) === firstSignature,
      ),
      parity: objectiveParity(first, oracle),
    };
    reports.push(report);
    options.onCaseComplete?.(report);
  }

  const base: BrowserBenchmarkReport = {
    format_version: 1,
    source_catalog_sha256: options.sourceCatalogSha256,
    runtime: options.runtime,
    timeout_ms: options.timeoutMs,
    repeats: options.repeats,
    cases: reports,
  };
  return options.environment === undefined
    ? base
    : { ...base, environment: options.environment };
}
