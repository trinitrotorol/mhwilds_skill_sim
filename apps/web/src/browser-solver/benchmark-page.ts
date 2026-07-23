import {
  BROWSER_SOLVER_BENCHMARK_CATALOG_URL,
  BROWSER_SOLVER_BENCHMARK_ORACLE_URL,
  runBrowserSolverBenchmark,
  type BrowserBenchmarkCaseReport,
  type BrowserBenchmarkReport,
} from "./benchmark";
import "./benchmark-page.css";
import { BrowserSolverWorkerClient } from "./worker-client";

declare global {
  interface Window {
    __MHWILDS_BROWSER_SOLVER_BENCHMARK__?: BrowserBenchmarkReport;
    __MHWILDS_BROWSER_SOLVER_CERTIFICATION__?: BrowserSolverCertificationBridge;
  }
}

export interface CertificationBridgeState {
  readonly version: 1;
  readonly ready: boolean;
  readonly active_search_id: string | null;
  readonly progress: Readonly<Record<string, number | null>> | null;
  readonly cross_origin_isolated: boolean;
  readonly worker_cross_origin_isolated: boolean | null;
}

export interface BrowserSolverCertificationBridge {
  readonly version: 1;
  getState(): CertificationBridgeState;
  waitUntilReady(): Promise<void>;
  runSuite(options: {
    repeats: number;
    timeout_ms: number;
  }): Promise<BrowserBenchmarkReport>;
  runCase(options: {
    case_name: string;
    repeats: number;
    timeout_ms: number;
  }): Promise<BrowserBenchmarkCaseReport>;
  cancel(): void;
  terminateWorker(): Promise<void>;
  recreateWorker(): Promise<void>;
  runWorkerCalibration(iterations: number): Promise<number>;
}

interface FetchedJson {
  readonly value: unknown;
  readonly bytes: number;
  readonly fetchMs: number;
  readonly parseMs: number;
}

const statusElement = requiredElement("benchmark-status");
const measurementsElement = requiredElement("benchmark-measurements");
const resultsElement = requiredElement("benchmark-results");
const reportJsonElement = requiredElement("benchmark-report-json");
const runButton = requiredButton("run-benchmark");
const cancelButton = requiredButton("cancel-benchmark");
const downloadButton = requiredButton("download-report");

const consoleErrors: string[] = [];
let abortController: AbortController | null = null;
let workerClient: BrowserSolverWorkerClient | null = null;
let activeSearchId: string | null = null;
let cancellationRequested = false;
let latestReport: BrowserBenchmarkReport | null = null;

window.addEventListener("error", (event) => {
  consoleErrors.push(event.message);
});
window.addEventListener("unhandledrejection", (event) => {
  consoleErrors.push(
    event.reason instanceof Error
      ? event.reason.message
      : String(event.reason),
  );
});

function requiredElement(id: string): HTMLElement {
  const element = document.getElementById(id);
  if (element === null) {
    throw new Error(`missing benchmark element #${id}`);
  }
  return element;
}

function requiredButton(id: string): HTMLButtonElement {
  const element = requiredElement(id);
  if (!(element instanceof HTMLButtonElement)) {
    throw new Error(`benchmark element #${id} must be a button`);
  }
  return element;
}

function setStatus(message: string): void {
  statusElement.textContent = message;
}

function formatMilliseconds(value: number): string {
  return `${value.toFixed(3)} ms`;
}

function textCell(row: HTMLTableRowElement, value: string): void {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.append(cell);
}

function renderCase(report: BrowserBenchmarkCaseReport): void {
  const row = document.createElement("tr");
  textCell(row, report.name);
  textCell(row, report.result.status);
  textCell(row, formatMilliseconds(report.timings_ms.min));
  textCell(row, formatMilliseconds(report.timings_ms.median));
  textCell(row, formatMilliseconds(report.timings_ms.max));
  textCell(row, String(report.result.preference_score ?? "—"));
  textCell(row, String(report.result.decoration_count ?? "—"));
  textCell(row, String(report.result.visited_nodes));
  textCell(row, String(report.result.pruned_nodes));
  textCell(row, report.parity === null ? "—" : report.parity ? "yes" : "no");
  textCell(row, report.deterministic ? "yes" : "no");
  resultsElement.append(row);
}

function addMeasurement(name: string, value: string): void {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = name;
  description.textContent = value;
  wrapper.append(term, description);
  measurementsElement.append(wrapper);
}

function renderMeasurements(
  environment: Readonly<Record<string, unknown>>,
): void {
  measurementsElement.replaceChildren();
  addMeasurement(
    "Catalog fetch",
    `${String(environment.catalog_fetch_bytes)} bytes / ${formatMilliseconds(
      Number(environment.catalog_fetch_ms),
    )}`,
  );
  addMeasurement(
    "JSON parse",
    formatMilliseconds(Number(environment.json_parse_ms)),
  );
  addMeasurement(
    "Worker init",
    formatMilliseconds(Number(environment.worker_init_ms)),
  );
  addMeasurement(
    "Viewport",
    `${window.innerWidth} × ${window.innerHeight} @ ${window.devicePixelRatio}x`,
  );
  addMeasurement(
    "CPU throttling",
    environment.cpu_throttling_rate === null
      ? "not declared"
      : `${String(environment.cpu_throttling_rate)}x`,
  );
  addMeasurement("User agent", navigator.userAgent);
}

async function fetchJson(
  url: string,
  signal: AbortSignal,
): Promise<FetchedJson> {
  const fetchStartedAt = performance.now();
  const response = await fetch(url, {
    cache: "no-store",
    credentials: "same-origin",
    signal,
  });
  if (!response.ok) {
    throw new Error(`${url} returned HTTP ${response.status}`);
  }
  const contents = await response.arrayBuffer();
  const fetchMs = performance.now() - fetchStartedAt;
  const parseStartedAt = performance.now();
  const value = JSON.parse(new TextDecoder().decode(contents)) as unknown;
  return {
    value,
    bytes: contents.byteLength,
    fetchMs,
    parseMs: performance.now() - parseStartedAt,
  };
}

function sourceCatalogSha256(catalogValue: unknown): string {
  if (
    typeof catalogValue !== "object" ||
    catalogValue === null ||
    Array.isArray(catalogValue)
  ) {
    throw new TypeError("browser Catalog must be an object");
  }
  const source = (catalogValue as Record<string, unknown>).source_catalog;
  if (
    typeof source !== "object" ||
    source === null ||
    Array.isArray(source)
  ) {
    throw new TypeError("browser Catalog source_catalog must be an object");
  }
  const sha256 = (source as Record<string, unknown>).sha256;
  if (typeof sha256 !== "string" || !/^[0-9a-f]{64}$/u.test(sha256)) {
    throw new TypeError("browser Catalog source hash is invalid");
  }
  return sha256;
}

function positiveQueryInteger(name: string, fallback: number): number {
  const value = new URLSearchParams(window.location.search).get(name);
  if (value === null) {
    return fallback;
  }
  if (!/^[1-9][0-9]*$/u.test(value)) {
    throw new TypeError(`${name} must be a positive integer`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new TypeError(`${name} exceeds the safe integer range`);
  }
  return parsed;
}

function declaredCpuThrottlingRate(): number | null {
  const value = new URLSearchParams(window.location.search).get(
    "cpu_throttling_rate",
  );
  if (value === null) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function cancellationError(): Error {
  return new Error("Benchmark cancelled");
}

async function runBenchmark(): Promise<void> {
  runButton.disabled = true;
  cancelButton.disabled = false;
  downloadButton.disabled = true;
  resultsElement.replaceChildren();
  measurementsElement.replaceChildren();
  latestReport = null;
  reportJsonElement.textContent = "";
  delete window.__MHWILDS_BROWSER_SOLVER_BENCHMARK__;
  cancellationRequested = false;
  abortController = new AbortController();
  workerClient = new BrowserSolverWorkerClient();

  try {
    const timeoutMs = positiveQueryInteger("timeout_ms", 10_000);
    const repeats = positiveQueryInteger("repeats", 3);
    setStatus("Fetching local benchmark artifacts…");
    const [catalogFetch, oracleFetch] = await Promise.all([
      fetchJson(
        BROWSER_SOLVER_BENCHMARK_CATALOG_URL,
        abortController.signal,
      ),
      fetchJson(
        BROWSER_SOLVER_BENCHMARK_ORACLE_URL,
        abortController.signal,
      ),
    ]);
    if (cancellationRequested) {
      throw cancellationError();
    }

    setStatus("Initializing solver Worker…");
    const workerStartedAt = performance.now();
    await workerClient.initialize(catalogFetch.value);
    const workerInitMs = performance.now() - workerStartedAt;
    const environment: Record<string, unknown> = {
      user_agent: navigator.userAgent,
      platform: navigator.platform,
      hardware_concurrency: navigator.hardwareConcurrency,
      cpu_model: "unknown",
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
        device_pixel_ratio: window.devicePixelRatio,
      },
      cpu_throttling_rate: declaredCpuThrottlingRate(),
      catalog_fetch_bytes: catalogFetch.bytes,
      catalog_fetch_ms: catalogFetch.fetchMs,
      oracle_fetch_bytes: oracleFetch.bytes,
      json_parse_ms: catalogFetch.parseMs + oracleFetch.parseMs,
      worker_init_ms: workerInitMs,
      memory_measurement: "unavailable",
      horizontal_overflow: false,
      console_errors: [],
      tab_crash: false,
    };
    renderMeasurements(environment);

    const report = await runBrowserSolverBenchmark({
      sourceCatalogSha256: sourceCatalogSha256(catalogFetch.value),
      oracleValue: oracleFetch.value,
      runtime: "browser",
      timeoutMs,
      repeats,
      environment,
      runCase: async (request, context) => {
        if (cancellationRequested) {
          throw cancellationError();
        }
        activeSearchId = `${context.name}:${
          context.warmup ? "warmup" : context.runIndex
        }`;
        setStatus(
          `${context.name} — ${
            context.warmup
              ? "warm-up"
              : `run ${context.runIndex + 1}/${repeats}`
          }`,
        );
        const result = await workerClient!.search(request, {
          searchId: activeSearchId,
          timeoutMs,
          onProgress: (progress) => {
            setStatus(
              `${context.name} — visited ${progress.visited_nodes.toLocaleString()} nodes`,
            );
          },
        });
        activeSearchId = null;
        if (cancellationRequested || result.status === "cancelled") {
          throw cancellationError();
        }
        return result;
      },
      onCaseComplete: renderCase,
    });
    environment.horizontal_overflow =
      document.documentElement.scrollWidth >
      document.documentElement.clientWidth;
    environment.console_errors = [...consoleErrors];
    latestReport = report;
    window.__MHWILDS_BROWSER_SOLVER_BENCHMARK__ = report;
    reportJsonElement.textContent = JSON.stringify(report);
    downloadButton.disabled = false;
    const parityFailures = report.cases.filter(
      ({ parity }) => parity === false,
    ).length;
    const incomplete = report.cases.filter(
      ({ result }) =>
        result.status === "timed-out" || result.status === "cancelled",
    ).length;
    setStatus(
      `Complete — ${report.cases.length} cases, ${parityFailures} parity failures, ${incomplete} incomplete`,
    );
  } catch (error) {
    if (cancellationRequested || (error instanceof DOMException && error.name === "AbortError")) {
      setStatus("Cancelled");
    } else {
      const message =
        error instanceof Error ? error.message : "Unknown benchmark error";
      setStatus(`Failed — ${message}`);
      console.error(error);
    }
  } finally {
    activeSearchId = null;
    workerClient?.dispose();
    workerClient = null;
    abortController = null;
    runButton.disabled = false;
    cancelButton.disabled = true;
  }
}

runButton.addEventListener("click", () => {
  void runBenchmark();
});

cancelButton.addEventListener("click", () => {
  cancellationRequested = true;
  abortController?.abort();
  if (activeSearchId !== null) {
    workerClient?.cancel(activeSearchId);
  }
  setStatus("Cancelling…");
  cancelButton.disabled = true;
});

downloadButton.addEventListener("click", () => {
  if (latestReport === null) {
    return;
  }
  const blob = new Blob(
    [`${JSON.stringify(latestReport, null, 2)}\n`],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "browser-solver-browser-report.json";
  link.click();
  URL.revokeObjectURL(url);
});

function createCertificationBridge(): BrowserSolverCertificationBridge {
  let catalogValue: unknown;
  let oracleValue: unknown;
  let client: BrowserSolverWorkerClient | null = null;
  let ready = false;
  let activeId: string | null = null;
  let progress: Readonly<Record<string, number | null>> | null = null;
  let workerIsolated: boolean | null = null;

  const initialize = async (): Promise<void> => {
    if (ready) {
      return;
    }
    const controller = new AbortController();
    const [catalog, oracle] = await Promise.all([
      fetchJson(BROWSER_SOLVER_BENCHMARK_CATALOG_URL, controller.signal),
      fetchJson(BROWSER_SOLVER_BENCHMARK_ORACLE_URL, controller.signal),
    ]);
    catalogValue = catalog.value;
    oracleValue = oracle.value;
    client = new BrowserSolverWorkerClient();
    await client.initialize(catalogValue);
    const calibration = await client.calibrate(1);
    workerIsolated = calibration.cross_origin_isolated;
    ready = true;
  };

  const initialization = initialize().catch((error: unknown) => {
    ready = false;
    throw new Error(
      error instanceof Error ? error.message : "certification bridge failed",
    );
  });

  const run = async (
    selectedCase: string | null,
    repeats: number,
    timeoutMs: number,
  ): Promise<BrowserBenchmarkReport> => {
    await initialization;
    if (client === null) {
      throw new Error("certification Worker is unavailable");
    }
    const source = sourceCatalogSha256(catalogValue);
    let selectedOracle = oracleValue;
    if (selectedCase !== null) {
      const oracle = oracleValue as {
        readonly format_version: 1;
        readonly source_catalog_sha256: string;
        readonly cases: readonly { readonly name: string }[];
      };
      const cases = oracle.cases.filter(({ name }) => name === selectedCase);
      if (cases.length !== 1) {
        throw new Error("unknown certification case");
      }
      selectedOracle = { ...oracle, cases };
    }
    return runBrowserSolverBenchmark({
      sourceCatalogSha256: source,
      oracleValue: selectedOracle,
      runtime: "browser",
      timeoutMs,
      repeats,
      runCase: async (request, context) => {
        activeId = `certification:${context.name}:${context.warmup ? "warmup" : context.runIndex}`;
        progress = null;
        const result = await client!.search(request, {
          searchId: activeId,
          timeoutMs,
          onProgress: (value) => {
            progress = { ...value };
          },
        });
        activeId = null;
        return result;
      },
    });
  };

  return Object.freeze({
    version: 1 as const,
    getState: () => ({
      version: 1 as const,
      ready,
      active_search_id: activeId,
      progress,
      cross_origin_isolated: window.crossOriginIsolated,
      worker_cross_origin_isolated: workerIsolated,
    }),
    waitUntilReady: () => initialization,
    runSuite: (options: { repeats: number; timeout_ms: number }) =>
      run(null, options.repeats, options.timeout_ms),
    runCase: async (options: {
      case_name: string;
      repeats: number;
      timeout_ms: number;
    }) => {
      const report = await run(
        options.case_name,
        options.repeats,
        options.timeout_ms,
      );
      const result = report.cases[0];
      if (result === undefined) {
        throw new Error("certification case produced no report");
      }
      return result;
    },
    cancel: () => {
      if (activeId !== null) {
        client?.cancel(activeId);
        activeId = null;
      }
    },
    terminateWorker: async () => {
      client?.dispose();
      client = null;
      ready = false;
      activeId = null;
    },
    recreateWorker: async () => {
      client?.dispose();
      client = new BrowserSolverWorkerClient();
      await client.initialize(catalogValue);
      const calibration = await client.calibrate(1);
      workerIsolated = calibration.cross_origin_isolated;
      ready = true;
    },
    runWorkerCalibration: async (iterations: number) => {
      await initialization;
      if (client === null) {
        throw new Error("certification Worker is unavailable");
      }
      const result = await client.calibrate(iterations);
      workerIsolated = result.cross_origin_isolated;
      return result.elapsed_ms;
    },
  });
}

const pageParameters = new URLSearchParams(window.location.search);
if (pageParameters.has("certification")) {
  window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__ =
    createCertificationBridge();
} else if (!pageParameters.has("certification-blank")) {
  void runBenchmark();
}
