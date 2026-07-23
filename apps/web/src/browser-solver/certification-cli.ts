/// <reference types="node" />

import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import {
  mkdir,
  readFile,
  rename,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import net from "node:net";
import { dirname, isAbsolute, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { promisify } from "node:util";

import { chromium, type Browser, type BrowserContext, type Page } from "playwright";
import { createServer, type ViteDevServer } from "vite";

import type {
  BrowserBenchmarkCaseReport,
  BrowserBenchmarkReport,
} from "./benchmark";
import { decodeBrowserSearchCatalog } from "./catalog";
import { summarizeCertificationEvidence } from "./certification-evidence";
import {
  decideCertification,
  parseCertificationArguments,
  statistics,
  type CertificationArguments,
} from "./certification";
import {
  CDP_FALLBACK_RETENTION_CYCLES,
  cdpHeapPeakBytes,
  decodeHeapUsage,
  decodePrimaryMemory,
  decodePrimaryMemoryDiagnostics,
  memoryExhaustionObserved,
  primaryMemoryFallbackEligible,
  sanitizeDiagnosticMessage,
  verifiedPrimaryMemoryPeakBytes,
} from "./cdp-memory";
import {
  assertWorkerThrottleApplySucceeded,
  collectCalibrationSamples,
  summarizeCalibration,
  summarizeWorkerCalibration,
} from "./cpu-calibration";
import { validateBrowserSolverResult } from "./validation";
import {
  createWorkerCdpController,
  WorkerCdpAttachmentTimeoutError,
  type WorkerCdpController,
  type WorkerThrottleApplySummary,
} from "./worker-cdp-controller";

const execFileAsync = promisify(execFile);
const CALIBRATION_ITERATIONS = 50_000_000;

async function availablePort(): Promise<number> {
  const server = net.createServer();
  await new Promise<void>((resolveReady, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolveReady);
  });
  const address = server.address();
  if (address === null || typeof address === "string") {
    throw new Error("failed to allocate CDP port");
  }
  await new Promise<void>((resolveClose) => server.close(() => resolveClose()));
  return address.port;
}


declare global {
  interface Performance {
    measureUserAgentSpecificMemory?: () => Promise<unknown>;
  }
}

function absolute(path: string, cwd: string): string {
  return isAbsolute(path) ? path : resolve(cwd, path);
}

function resolvedArguments(
  args: CertificationArguments,
  cwd: string,
): CertificationArguments {
  return {
    ...args,
    catalog: absolute(args.catalog, cwd),
    oracle: absolute(args.oracle, cwd),
    output: absolute(args.output, cwd),
    screenshotDirectory: absolute(args.screenshotDirectory, cwd),
  };
}

async function sha256(path: string): Promise<string> {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

async function atomicJson(path: string, value: unknown): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.tmp`;
  try {
    await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, "utf8");
    await rename(temporary, path);
  } finally {
    await rm(temporary, { force: true });
  }
}

async function bridge(page: Page): Promise<void> {
  await page.waitForFunction(
    () =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__?.version === 1,
    undefined,
    { timeout: 30_000 },
  );
  await page.evaluate(async () => {
    const api = window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__;
    if (api === undefined || api.version !== 1) {
      throw new Error("certification bridge version 1 is unavailable");
    }
    await api.waitUntilReady();
  });
}

async function newProfile(
  browser: Browser,
  baseUrl: string,
  mobile: boolean,
): Promise<{
  context: BrowserContext;
  page: Page;
  session: Awaited<ReturnType<BrowserContext["newCDPSession"]>>;
}> {
  const context = await browser.newContext({
    viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 900 },
    deviceScaleFactor: mobile ? 2 : 1,
    isMobile: mobile,
    hasTouch: mobile,
  });
  const page = await context.newPage();
  const startupErrors: string[] = [];
  page.on("pageerror", (error) => startupErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") startupErrors.push(message.text());
  });
  const session = await context.newCDPSession(page);
  await session.send("Emulation.setCPUThrottlingRate", { rate: mobile ? 4 : 1 });
  await page.goto(`${baseUrl}/solver-benchmark.html?certification=1`, {
    waitUntil: "domcontentloaded",
  });
  try {
    await bridge(page);
  } catch (error) {
    throw new Error(
      `certification bridge startup failed at ${page.url()}: ${startupErrors.join(" | ") || (error instanceof Error ? error.message : "unknown")}`,
      { cause: error },
    );
  }
  return { context, page, session };
}

async function pageCalibration(page: Page): Promise<number> {
  return page.evaluate((iterations) => {
    const startedAt = performance.now();
    let checksum = 0x12345678;
    for (let index = 0; index < iterations; index += 1) {
      checksum = Math.imul(checksum ^ index, 1664525) + 1013904223;
    }
    if (!Number.isFinite(checksum)) throw new Error("invalid checksum");
    return performance.now() - startedAt;
  }, CALIBRATION_ITERATIONS);
}

async function workerCalibration(page: Page): Promise<number> {
  return page.evaluate(
    (iterations) =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runWorkerCalibration(
        iterations,
      ),
    CALIBRATION_ITERATIONS,
  );
}

async function calibrate(
  page: Page,
  session: Awaited<ReturnType<BrowserContext["newCDPSession"]>>,
  workerThrottle: WorkerCdpController,
) {
  const page1: number[] = [];
  const page4: number[] = [];
  const worker1: number[] = [];
  const worker4: number[] = [];
  let rate1Apply: WorkerThrottleApplySummary | null = null;
  let rate4Apply: WorkerThrottleApplySummary | null = null;
  for (const rate of [1, 4] as const) {
    await page.evaluate(
      () =>
        window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.terminateWorker(),
    );
    await workerThrottle.waitForWorkersDetached();
    const attachCursor = workerThrottle.captureWorkerAttachCursor();
    await session.send("Emulation.setCPUThrottlingRate", { rate });
    const recreation = page.evaluate(
      () => window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.recreateWorker(),
    );
    await Promise.all([
      workerThrottle.waitForWorkerAfter(attachCursor).catch((error: unknown) => {
        if (error instanceof WorkerCdpAttachmentTimeoutError) {
          return null;
        }
        throw error;
      }),
      recreation,
    ]);
    const apply = await workerThrottle.setRate(rate);
    assertWorkerThrottleApplySucceeded(apply, `rate ${rate} calibration`);
    if (rate === 1) {
      rate1Apply = apply;
    } else {
      rate4Apply = apply;
    }
    const samples = await collectCalibrationSamples(
      () => pageCalibration(page),
      () => workerCalibration(page),
    );
    (rate === 1 ? page1 : page4).push(...samples.page);
    (rate === 1 ? worker1 : worker4).push(...samples.worker);
  }
  if (rate1Apply === null || rate4Apply === null) {
    throw new Error("Worker CPU calibration apply summaries are incomplete");
  }
  return {
    page: summarizeCalibration(page1, page4),
    worker: summarizeWorkerCalibration(
      rate1Apply,
      rate4Apply,
      worker1,
      worker4,
    ),
  };
}

async function primaryMemory(
  page: Page,
  headless: boolean,
  workerCrossOriginIsolated: boolean | null,
) {
  const observation = await page.evaluate(
    async ({ isHeadless, workerIsolated }) => {
      const permissionPolicyAllows = (() => {
        try {
          const policy = (
            document as Document & {
              readonly permissionsPolicy?: {
                allowsFeature(feature: string): boolean;
              };
            }
          ).permissionsPolicy;
          return policy === undefined
            ? null
            : policy.allowsFeature("cross-origin-isolated");
        } catch {
          return null;
        }
      })();
      const measure = performance.measureUserAgentSpecificMemory;
      const diagnostics = {
        api_present: measure !== undefined,
        is_secure_context: isSecureContext,
        window_cross_origin_isolated: window.crossOriginIsolated,
        worker_cross_origin_isolated: workerIsolated,
        permissions_policy_allows_cross_origin_isolated:
          permissionPolicyAllows,
        exception_name: null as string | null,
        exception_message: null as string | null,
        headless: isHeadless,
      };
      if (measure === undefined) {
        return { value: null, diagnostics };
      }
      try {
        return {
          value: await measure.call(performance),
          diagnostics,
        };
      } catch (error) {
        return {
          value: null,
          diagnostics: {
            ...diagnostics,
            exception_name:
              error instanceof Error ? error.name : "UnknownError",
            exception_message:
              error instanceof Error ? error.message : "memory sample failed",
          },
        };
      }
    },
    { isHeadless: headless, workerIsolated: workerCrossOriginIsolated },
  );
  return {
    sample:
      observation.value === null
        ? null
        : decodePrimaryMemory(observation.value),
    diagnostics: decodePrimaryMemoryDiagnostics(observation.diagnostics),
  };
}

async function supportingMemory(
  session: Awaited<ReturnType<BrowserContext["newCDPSession"]>>,
  workerThrottle: WorkerCdpController,
) {
  const warnings: string[] = [];
  try {
    await session.send("HeapProfiler.collectGarbage");
  } catch (error) {
    warnings.push(
      `page garbage collection failed: ${
        sanitizeDiagnosticMessage(
          error instanceof Error ? error.message : "unknown",
        ) ?? "unknown"
      }`,
    );
  }
  let pageHeap: ReturnType<typeof decodeHeapUsage> | null = null;
  try {
    pageHeap = decodeHeapUsage(await session.send("Runtime.getHeapUsage"));
  } catch (error) {
    warnings.push(
      `page heap unavailable: ${
        sanitizeDiagnosticMessage(
          error instanceof Error ? error.message : "unknown",
        ) ?? "unknown"
      }`,
    );
  }
  let workerHeap: ReturnType<typeof decodeHeapUsage> | null = null;
  try {
    const rawWorkerHeap = await workerThrottle.sampleWorkerHeap();
    if (rawWorkerHeap === null) {
      warnings.push("dedicated Worker target was not attached");
    } else {
      workerHeap = decodeHeapUsage(rawWorkerHeap);
    }
  } catch (error) {
    warnings.push(
      `Worker heap unavailable: ${
        sanitizeDiagnosticMessage(
          error instanceof Error ? error.message : "unknown",
        ) ?? "unknown"
      }`,
    );
  }
  return {
    page: pageHeap,
    worker: workerHeap,
    worker_attached: workerHeap !== null,
    warnings,
  };
}

async function sampleMemory(
  name: string,
  page: Page,
  session: Awaited<ReturnType<BrowserContext["newCDPSession"]>>,
  workerThrottle: WorkerCdpController,
  headless: boolean,
) {
  const workerCrossOriginIsolated = await page.evaluate(
    () =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__?.getState()
        .worker_cross_origin_isolated ?? null,
  );
  return {
    name,
    primary: await primaryMemory(
      page,
      headless,
      workerCrossOriginIsolated,
    ),
    cdp: await supportingMemory(session, workerThrottle),
  };
}

function mixed(report: BrowserBenchmarkReport): BrowserBenchmarkCaseReport {
  const result = report.cases.find(({ name }) => name === "mixed-ranked");
  if (result === undefined) throw new Error("mixed-ranked report is missing");
  return result;
}

function strictlyIncreasing(values: readonly (number | null)[]): boolean {
  return (
    values.length > 1 &&
    values.every(
      (value, index) =>
        value !== null &&
        (index === 0 ||
          (values[index - 1] !== null && value > values[index - 1]!)),
    )
  );
}

async function runCertification(args: CertificationArguments): Promise<unknown> {
  await Promise.all([stat(args.catalog), stat(args.oracle)]);
  const [catalogRaw, oracleRaw, compactHash] = await Promise.all([
    readFile(args.catalog, "utf8"),
    readFile(args.oracle, "utf8"),
    sha256(args.catalog),
  ]);
  const catalog = decodeBrowserSearchCatalog(JSON.parse(catalogRaw) as unknown);
  const oracle = JSON.parse(oracleRaw) as { cases: readonly unknown[] };
  process.env.MHWILDS_BROWSER_SOLVER_CATALOG = args.catalog;
  process.env.MHWILDS_BROWSER_SOLVER_ORACLE = args.oracle;
  const server: ViteDevServer = await createServer({
    configFile: resolve(process.cwd(), "vite.config.ts"),
    base: "/",
    server: { host: "127.0.0.1", port: 0, strictPort: false },
  });
  let browser: Browser | null = null;
  let workerThrottle: WorkerCdpController | null = null;
  try {
    await server.listen();
    const address = server.httpServer?.address();
    if (address === null || typeof address === "string" || address === undefined) {
      throw new Error("Vite did not allocate a local port");
    }
    const baseUrl = `http://127.0.0.1:${address.port}`;
    const cdpPort = await availablePort();
    const headless = !args.headed;
    browser = await chromium.launch({
      headless,
      args: [
        "--enable-precise-memory-info",
        `--remote-debugging-port=${cdpPort}`,
      ],
    });
    workerThrottle = await createWorkerCdpController({ port: cdpPort });
    const browserVersion = browser.version();
    const errors: string[] = [];
    const crashes: string[] = [];
    const requestsFailed: string[] = [];
    const attachDiagnostics = (page: Page): void => {
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text());
      });
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("crash", () => crashes.push("page crash"));
      page.on("requestfailed", (request) =>
        requestsFailed.push(`${request.method()} ${request.url()}`),
      );
    };

    const calibrationProfile = await newProfile(browser, baseUrl, false);
    attachDiagnostics(calibrationProfile.page);
    const cpuCalibration = await calibrate(
      calibrationProfile.page,
      calibrationProfile.session,
      workerThrottle,
    );
    const calibrationState = await calibrationProfile.page.evaluate(
      () => window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.getState(),
    );
    await calibrationProfile.context.close();
    await workerThrottle.waitForWorkersDetached();

    const desktopReports: BrowserBenchmarkReport[] = [];
    const desktopTotals: number[] = [];
    const desktopWorkerInit: number[] = [];
    for (let index = 0; index < args.repeats; index += 1) {
      await workerThrottle.setRate(1);
      const started = performance.now();
      const profile = await newProfile(browser, baseUrl, false);
      attachDiagnostics(profile.page);
      desktopWorkerInit.push(performance.now() - started);
      if (index === 0) {
        await profile.page.screenshot({
          path: resolve(args.screenshotDirectory, "desktop-before.png"),
          fullPage: true,
        });
      }
      const report = await profile.page.evaluate(
        (options) =>
          window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runSuite(options),
        { repeats: 1, timeout_ms: args.timeoutMs },
      );
      desktopTotals.push(performance.now() - started);
      desktopReports.push(report);
      if (index === args.repeats - 1) {
        await profile.page.screenshot({
          path: resolve(args.screenshotDirectory, "desktop-after.png"),
          fullPage: true,
        });
      }
      await profile.context.close();
      await workerThrottle.waitForWorkersDetached();
    }

    const mobileReports: BrowserBenchmarkReport[] = [];
    const mobileWorkerInit: number[] = [];
    for (let index = 0; index < args.repeats; index += 1) {
      await workerThrottle.setRate(4);
      const started = performance.now();
      const profile = await newProfile(browser, baseUrl, true);
      attachDiagnostics(profile.page);
      mobileWorkerInit.push(performance.now() - started);
      if (index === 0) {
        await profile.page.screenshot({
          path: resolve(args.screenshotDirectory, "mobile-4x-before.png"),
          fullPage: true,
        });
      }
      const report = await profile.page.evaluate(
        (options) =>
          window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runSuite(options),
        { repeats: 1, timeout_ms: args.timeoutMs },
      );
      mobileReports.push(report);
      if (index === args.repeats - 1) {
        await profile.page.screenshot({
          path: resolve(args.screenshotDirectory, "mobile-4x-after.png"),
          fullPage: true,
        });
      }
      await profile.context.close();
      await workerThrottle.waitForWorkersDetached();
    }

    const memoryContext = await browser.newContext({
      viewport: { width: 390, height: 844 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });
    const memoryPage = await memoryContext.newPage();
    attachDiagnostics(memoryPage);
    const memorySession = await memoryContext.newCDPSession(memoryPage);
    await workerThrottle.setRate(4);
    await memorySession.send("Emulation.setCPUThrottlingRate", { rate: 4 });
    await memoryPage.goto(
      `${baseUrl}/solver-benchmark.html?certification-blank=1`,
    );
    const stages = [
      await sampleMemory(
        "baseline",
        memoryPage,
        memorySession,
        workerThrottle,
        headless,
      ),
    ];
    await memoryPage.goto(`${baseUrl}/solver-benchmark.html?certification=1`);
    await bridge(memoryPage);
    stages.push(
      await sampleMemory(
        "worker-init",
        memoryPage,
        memorySession,
        workerThrottle,
        headless,
      ),
    );
    await memoryPage.evaluate((timeoutMs) =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runCase({
        case_name: "mixed-ranked",
        repeats: 1,
        timeout_ms: timeoutMs,
      }), args.timeoutMs);
    stages.push(
      await sampleMemory(
        "post-mixed-ranked",
        memoryPage,
        memorySession,
        workerThrottle,
        headless,
      ),
    );
    await memoryPage.evaluate((timeoutMs) =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runSuite({
        repeats: 1,
        timeout_ms: timeoutMs,
      }), args.timeoutMs);
    stages.push(
      await sampleMemory(
        "full-suite",
        memoryPage,
        memorySession,
        workerThrottle,
        headless,
      ),
    );
    await memoryPage.evaluate(() =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.terminateWorker(),
    );
    await workerThrottle.waitForWorkersDetached();
    stages.push(
      await sampleMemory(
        "post-terminate",
        memoryPage,
        memorySession,
        workerThrottle,
        headless,
      ),
    );
    const retention: Array<Awaited<ReturnType<typeof sampleMemory>>> = [];
    for (
      let cycle = 1;
      cycle <= CDP_FALLBACK_RETENTION_CYCLES;
      cycle += 1
    ) {
      await memoryPage.evaluate(() =>
        window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.recreateWorker(),
      );
      await memoryPage.evaluate((timeoutMs) =>
        window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runCase({
          case_name: "mixed-ranked",
          repeats: 1,
          timeout_ms: timeoutMs,
        }), args.timeoutMs);
      await memoryPage.evaluate(() =>
        window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.terminateWorker(),
      );
      await workerThrottle.waitForWorkersDetached();
      retention.push(
        await sampleMemory(
          `retention-${cycle}-post-terminate`,
          memoryPage,
          memorySession,
          workerThrottle,
          headless,
        ),
      );
    }
    stages.push(retention[retention.length - 1]!);

    await memoryPage.evaluate(() =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.recreateWorker(),
    );
    const cancelStarted = performance.now();
    const cancelledPromise = memoryPage.evaluate((timeoutMs) =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runCase({
        case_name: "mixed-ranked",
        repeats: 1,
        timeout_ms: timeoutMs,
      }), args.timeoutMs);
    await memoryPage.waitForFunction(() => {
      const state =
        window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.getState();
      return state.progress !== null;
    }, undefined, { timeout: args.timeoutMs });
    const cancelProgress = await memoryPage.evaluate(
      () => window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.getState().progress,
    );
    await memoryPage.evaluate(() =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.cancel(),
    );
    await cancelledPromise.catch(() => null);
    await memoryPage.evaluate(() =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.terminateWorker(),
    );
    await workerThrottle.waitForWorkersDetached();
    await memoryPage.evaluate(() =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.recreateWorker(),
    );
    const readyElapsed = performance.now() - cancelStarted;
    const restartCase = await memoryPage.evaluate((timeoutMs) =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runCase({
        case_name: "mixed-ranked",
        repeats: 1,
        timeout_ms: timeoutMs,
      }), args.timeoutMs);
    await memoryPage.screenshot({
      path: resolve(args.screenshotDirectory, "mobile-4x-cancelled.png"),
      fullPage: true,
    });
    const retainedAfterCancel = await sampleMemory(
      "cancel-restart",
      memoryPage,
      memorySession,
      workerThrottle,
      headless,
    );
    const finalWorkerHealth = await workerThrottle.setRate(4);
    assertWorkerThrottleApplySucceeded(
      finalWorkerHealth,
      "cancel/restart health check",
    );
    await memoryContext.close();
    await workerThrottle.waitForWorkersDetached();

    const desktopMixed = desktopReports.map(
      (report) => mixed(report).timings_ms.median,
    );
    const mobileCases = mobileReports.flatMap((report) =>
      report.cases.filter(({ name }) => name !== "impossible-stress"),
    );
    const primaryBytes = (name: string): number | null =>
      stages.find((stage) => stage.name === name)?.primary.sample?.bytes ?? null;
    const retentionSamples = retention;
    const firstRetention = retentionSamples[0]?.primary.sample?.bytes ?? null;
    const finalRetention =
      retentionSamples[retentionSamples.length - 1]?.primary.sample?.bytes ?? null;
    const primaryRetentionValues = retentionSamples.map(
      (sample) => sample.primary.sample?.bytes ?? null,
    );
    const allMemorySamples = [
      ...stages,
      ...retentionSamples,
      retainedAfterCancel,
    ];
    const primaryMemoryAvailable = allMemorySamples.every(
      (sample) => sample.primary.sample !== null,
    );
    const unavailablePrimaryDiagnostics = allMemorySamples.flatMap((sample) =>
      sample.primary.sample === null ? [sample.primary.diagnostics] : [],
    );
    const primaryFallbackEligible =
      !primaryMemoryAvailable &&
      primaryMemoryFallbackEligible(unavailablePrimaryDiagnostics);
    const verifiedPrimaryMemoryPeak = verifiedPrimaryMemoryPeakBytes(
      allMemorySamples.map((sample) => sample.primary.sample),
    );
    const cdpMemoryPeak = cdpHeapPeakBytes([
      ...stages.map((stage) => ({
        page: stage.cdp.page,
        worker: stage.cdp.worker,
        worker_required:
          stage.name === "worker-init" ||
          stage.name === "post-mixed-ranked" ||
          stage.name === "full-suite",
      })),
      ...retentionSamples.map((sample) => ({
        page: sample.cdp.page,
        worker: sample.cdp.worker,
        worker_required: false,
      })),
      {
        page: retainedAfterCancel.cdp.page,
        worker: retainedAfterCancel.cdp.worker,
        worker_required: true,
      },
    ]);
    const cdpRetentionValues = retentionSamples.map(
      (sample) => sample.cdp.page?.used_size ?? null,
    );
    const firstCdpRetention = cdpRetentionValues[0] ?? null;
    const finalCdpRetention =
      cdpRetentionValues[cdpRetentionValues.length - 1] ?? null;
    const allCounts = summarizeCertificationEvidence(
      [desktopReports, mobileReports],
      [restartCase],
      (request, result) =>
        validateBrowserSolverResult(catalog, request, result),
    );
    const mobileAcceptanceTimeouts = mobileCases.filter(
      ({ result }) => result.status === "timed-out",
    ).length;
    const browserMemoryExhaustion = memoryExhaustionObserved([
      ...errors,
      ...crashes,
      ...allMemorySamples.flatMap(({ primary }) => [
        primary.diagnostics.exception_name,
        primary.diagnostics.exception_message,
      ]),
    ]);
    const decision = decideCertification({
      workerCalibration: cpuCalibration.worker,
      desktopMixedMs: desktopMixed,
      mobileCaseMediansMs: mobileCases.map(({ timings_ms }) => timings_ms.median),
      mobileCaseMaxMs: mobileCases.map(({ timings_ms }) => timings_ms.max),
      mobileAcceptanceCaseCount: mobileCases.length,
      mobileAcceptanceTimeouts,
      workerInitMedianMs: statistics(mobileWorkerInit).median,
      ...allCounts,
      errors: errors.length,
      tabCrashes: crashes.length,
      browserMemoryExhaustion,
      primaryMemoryAvailable,
      primaryMemoryFallbackEligible: primaryFallbackEligible,
      postMixedBytes: primaryBytes("post-mixed-ranked"),
      fullSuitePeakBytes: primaryBytes("full-suite"),
      postInitIncrementBytes:
        primaryBytes("worker-init") !== null && primaryBytes("baseline") !== null
          ? primaryBytes("worker-init")! - primaryBytes("baseline")!
          : null,
      firstPostTerminateBytes: firstRetention,
      finalPostTerminateBytes: finalRetention,
      retentionContinuouslyIncreasing: strictlyIncreasing(
        primaryRetentionValues,
      ),
      cdpMemoryStagesComplete: cdpMemoryPeak !== null,
      cdpMemoryPeakBytes: cdpMemoryPeak,
      cdpRetentionCycleCount: retentionSamples.length,
      cdpFirstPostTerminatePageBytes: firstCdpRetention,
      cdpFinalPostTerminatePageBytes: finalCdpRetention,
      cdpRetentionContinuouslyIncreasing:
        strictlyIncreasing(cdpRetentionValues),
      verifiedTotalMemoryPeakBytes:
        verifiedPrimaryMemoryPeak,
      cancelRestartPassed:
        cancelProgress !== null &&
        restartCase.result.status === "optimal" &&
        restartCase.parity === true,
    });
    const { stdout: commitSha } = await execFileAsync("git", ["rev-parse", "HEAD"]);
    const { stdout: gitStatus } = await execFileAsync("git", ["status", "--porcelain"]);
    return {
      format_version: 2,
      source: {
        commit_sha: commitSha.trim(),
        git_dirty: gitStatus.trim().length > 0,
        catalog_source_sha256: catalog.source_catalog.sha256,
        compact_catalog_sha256: compactHash,
        catalog_bytes: Buffer.byteLength(catalogRaw),
        oracle_case_count: oracle.cases.length,
      },
      environment: {
        os: `${os.platform()} ${os.release()}`,
        architecture: os.arch(),
        cpu_model: os.cpus()[0]?.model ?? null,
        logical_cpu_count: os.cpus().length,
        total_memory_bytes: os.totalmem(),
        node_version: process.version,
        playwright_version: JSON.parse(
          await readFile(resolve(process.cwd(), "node_modules/playwright/package.json"), "utf8"),
        ).version,
        chromium_version: browserVersion,
        headless,
      },
      cpu_calibration: {
        page: cpuCalibration.page,
        worker: cpuCalibration.worker,
        page_cross_origin_isolated: calibrationState.cross_origin_isolated,
        worker_cross_origin_isolated:
          calibrationState.worker_cross_origin_isolated,
        cpu_throttle_verified: cpuCalibration.worker.verified,
      },
      desktop: {
        profile: "desktop 1x",
        suites: desktopReports,
        suite_total_ms: desktopTotals,
        mixed_ranked_across_suites: statistics(desktopMixed),
        worker_init_ms: statistics(desktopWorkerInit),
      },
      mobile_4x: {
        profile: `${headless ? "headless" : "headed"} Chromium requested low-speed mobile-equivalent 4x profile; not a real device`,
        suites: mobileReports,
        worker_init_ms: statistics(mobileWorkerInit),
        acceptance_case_count: mobileCases.length,
        acceptance_timeout_count: mobileAcceptanceTimeouts,
      },
      memory: {
        method: "measureUserAgentSpecificMemory",
        primary: {
          all_samples_available: primaryMemoryAvailable,
          cdp_fallback_eligible: primaryFallbackEligible,
          verified_peak_bytes: verifiedPrimaryMemoryPeak,
        },
        stages,
        retention_cycles: retention,
        headed_retry: {
          status: headless ? "not-attempted" : "primary-run-was-headed",
        },
        cdp_fallback: {
          stages_complete: cdpMemoryPeak !== null,
          peak_combined_used_bytes: cdpMemoryPeak,
          retention_cycle_count: retentionSamples.length,
          first_post_terminate_page_used_bytes: firstCdpRetention,
          final_post_terminate_page_used_bytes: finalCdpRetention,
        },
      },
      cancel_restart: {
        passed:
          cancelProgress !== null &&
          restartCase.result.status === "optimal" &&
          restartCase.parity === true,
        progress_at_cancel: cancelProgress,
        cancel_to_ready_ms: readyElapsed,
        restart_case: restartCase,
        retained_memory: retainedAfterCancel,
      },
      evidence_counts: allCounts,
      decision: {
        ...decision,
        diagnostics: {
          console_page_errors: errors,
          tab_crashes: crashes,
          request_failures: requestsFailed,
          browser_memory_exhaustion: browserMemoryExhaustion,
        },
      },
    };
  } finally {
    await workerThrottle?.close();
    await browser?.close();
    await server.close();
  }
}

export async function executeCertificationCli(
  argv: readonly string[],
  cwd = process.cwd(),
  dependencies: {
    readonly run: (args: CertificationArguments) => Promise<unknown>;
    readonly write: (path: string, value: unknown) => Promise<void>;
    readonly stdout: (value: string) => void;
    readonly stderr: (value: string) => void;
  } = {
    run: runCertification,
    write: atomicJson,
    stdout: (value) => process.stdout.write(value),
    stderr: (value) => process.stderr.write(value),
  },
): Promise<number> {
  try {
    const args = resolvedArguments(parseCertificationArguments(argv), cwd);
    await mkdir(args.screenshotDirectory, { recursive: true });
    const report = await dependencies.run(args);
    await dependencies.write(args.output, report);
    dependencies.stdout(
      `${JSON.stringify({ output: args.output, decision: (report as { decision: { status: string } }).decision.status })}\n`,
    );
    return 0;
  } catch (error) {
    dependencies.stderr(
      `browser solver certification failed: ${error instanceof Error ? error.message : "unknown error"}\n`,
    );
    return 1;
  }
}

const entryPath = process.argv[1];
if (
  entryPath !== undefined &&
  import.meta.url === pathToFileURL(resolve(entryPath)).href
) {
  let interrupted = false;
  const interrupt = (): void => {
    if (!interrupted) {
      interrupted = true;
      process.exitCode = 130;
    }
  };
  process.once("SIGINT", interrupt);
  process.once("SIGTERM", interrupt);
  process.exitCode = await executeCertificationCli(process.argv.slice(2));
}
