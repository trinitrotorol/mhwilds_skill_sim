export interface HeapUsage {
  readonly used_size: number;
  readonly total_size: number;
  readonly embedder_heap_used_size: number | null;
  readonly backing_storage_size: number | null;
}

export interface PrimaryMemorySample {
  readonly bytes: number;
  readonly breakdown: unknown;
  readonly method: "measureUserAgentSpecificMemory";
}

export interface PrimaryMemoryDiagnostics {
  readonly api_present: boolean;
  readonly is_secure_context: boolean;
  readonly window_cross_origin_isolated: boolean;
  readonly worker_cross_origin_isolated: boolean | null;
  readonly permissions_policy_allows_cross_origin_isolated: boolean | null;
  readonly exception_name: string | null;
  readonly exception_message: string | null;
  readonly headless: boolean;
}

export interface CdpHeapStageEvidence {
  readonly page: HeapUsage | null;
  readonly worker: HeapUsage | null;
  readonly worker_required: boolean;
}

export const CDP_FALLBACK_RETENTION_CYCLES = 10;
const KNOWN_UNSUPPORTED_PRIMARY_MEMORY_MESSAGES = Object.freeze([
  "Failed to execute 'measureUserAgentSpecificMemory' on 'Performance': performance.measureUserAgentSpecificMemory is not available.",
]);

function finiteNonnegative(value: unknown, name: string): number {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 0) {
    throw new TypeError(`${name} must be a finite nonnegative number`);
  }
  return value;
}

function optionalMetric(value: unknown, name: string): number | null {
  return value === undefined ? null : finiteNonnegative(value, name);
}

export function decodeHeapUsage(value: unknown): HeapUsage {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("heap usage must be an object");
  }
  const record = value as Record<string, unknown>;
  return {
    used_size: finiteNonnegative(record.usedSize, "usedSize"),
    total_size: finiteNonnegative(record.totalSize, "totalSize"),
    embedder_heap_used_size: optionalMetric(
      record.embedderHeapUsedSize,
      "embedderHeapUsedSize",
    ),
    backing_storage_size: optionalMetric(
      record.backingStorageSize,
      "backingStorageSize",
    ),
  };
}

export function decodePrimaryMemory(value: unknown): PrimaryMemorySample {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("primary memory sample must be an object");
  }
  const record = value as Record<string, unknown>;
  return {
    bytes: finiteNonnegative(record.bytes, "bytes"),
    breakdown: record.breakdown ?? null,
    method: "measureUserAgentSpecificMemory",
  };
}

function booleanMetric(value: unknown, name: string): boolean {
  if (typeof value !== "boolean") {
    throw new TypeError(`${name} must be boolean`);
  }
  return value;
}

function nullableBooleanMetric(value: unknown, name: string): boolean | null {
  return value === null ? null : booleanMetric(value, name);
}

export function sanitizeDiagnosticMessage(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string") {
    throw new TypeError("diagnostic message must be a string or null");
  }
  const firstLine = value.split(/\r?\n/u, 1)[0]!.trim();
  if (firstLine.length === 0) {
    return null;
  }
  const sanitized = firstLine
    .replace(/\b(?:file|https?):\/\/\S+/giu, "[redacted-url]")
    .replace(/\b[A-Z]:\\(?:[^\\\s]+\\)*[^\\\s]*/giu, "[redacted-path]")
    .replace(
      /(^|\s)\/(?:[^/\s]+\/)+[^/\s]*/gu,
      "$1[redacted-path]",
    )
    .replace(
      /\b(authorization|password|secret|token)\s*[:=]\s*\S+/giu,
      "$1=[redacted]",
    )
    .replace(/\s+/gu, " ")
    .trim();
  if (/^at\s/iu.test(sanitized)) {
    return "stack frame removed";
  }
  return sanitized.slice(0, 500);
}

export function decodePrimaryMemoryDiagnostics(
  value: unknown,
): PrimaryMemoryDiagnostics {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new TypeError("primary memory diagnostics must be an object");
  }
  const record = value as Record<string, unknown>;
  return {
    api_present: booleanMetric(record.api_present, "api_present"),
    is_secure_context: booleanMetric(
      record.is_secure_context,
      "is_secure_context",
    ),
    window_cross_origin_isolated: booleanMetric(
      record.window_cross_origin_isolated,
      "window_cross_origin_isolated",
    ),
    worker_cross_origin_isolated: nullableBooleanMetric(
      record.worker_cross_origin_isolated,
      "worker_cross_origin_isolated",
    ),
    permissions_policy_allows_cross_origin_isolated: nullableBooleanMetric(
      record.permissions_policy_allows_cross_origin_isolated,
      "permissions_policy_allows_cross_origin_isolated",
    ),
    exception_name: sanitizeDiagnosticMessage(record.exception_name),
    exception_message: sanitizeDiagnosticMessage(record.exception_message),
    headless: booleanMetric(record.headless, "headless"),
  };
}

export function primaryMemoryFallbackEligible(
  diagnostics: readonly PrimaryMemoryDiagnostics[],
): boolean {
  return (
    diagnostics.length > 0 &&
    diagnostics.every(
      (entry) => {
        const environmentEligible =
          entry.is_secure_context &&
          entry.window_cross_origin_isolated &&
          entry.worker_cross_origin_isolated !== false &&
          entry.permissions_policy_allows_cross_origin_isolated !== false;
        return (
          environmentEligible &&
          (!entry.api_present ||
            (entry.exception_name === "SecurityError" &&
              entry.exception_message !== null &&
              KNOWN_UNSUPPORTED_PRIMARY_MEMORY_MESSAGES.includes(
                entry.exception_message,
              )))
        );
      },
    )
  );
}

export function memoryExhaustionObserved(
  messages: readonly (string | null)[],
): boolean {
  return messages.some(
    (message) =>
      message !== null &&
      /\b(?:out of memory|oom|allocation failed|memory limit exceeded)\b/iu.test(
        message,
      ),
  );
}

export function verifiedPrimaryMemoryPeakBytes(
  samples: readonly (PrimaryMemorySample | null)[],
): number | null {
  const available = samples.flatMap((sample, index) =>
    sample === null
      ? []
      : [finiteNonnegative(sample.bytes, `samples[${index}].bytes`)],
  );
  return available.length === 0 ? null : Math.max(...available);
}

export function cdpHeapPeakBytes(
  stages: readonly CdpHeapStageEvidence[],
): number | null {
  if (stages.length === 0) {
    return null;
  }
  let peak = 0;
  for (const [index, stage] of stages.entries()) {
    if (stage.page === null || (stage.worker_required && stage.worker === null)) {
      return null;
    }
    const pageBytes = finiteNonnegative(
      stage.page.used_size,
      `stages[${index}].page.used_size`,
    );
    const workerBytes =
      stage.worker === null
        ? 0
        : finiteNonnegative(
            stage.worker.used_size,
            `stages[${index}].worker.used_size`,
          );
    peak = Math.max(peak, pageBytes + workerBytes);
  }
  return peak;
}

export function retentionPassed(
  firstPostTerminate: number,
  finalPostTerminate: number,
): boolean {
  finiteNonnegative(firstPostTerminate, "firstPostTerminate");
  finiteNonnegative(finalPostTerminate, "finalPostTerminate");
  const allowance = Math.max(32 * 1024 * 1024, firstPostTerminate * 0.2);
  return finalPostTerminate <= firstPostTerminate + allowance;
}
