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

export function retentionPassed(
  firstPostTerminate: number,
  finalPostTerminate: number,
): boolean {
  const allowance = Math.max(32 * 1024 * 1024, firstPostTerminate * 0.2);
  return finalPostTerminate <= firstPostTerminate + allowance;
}
