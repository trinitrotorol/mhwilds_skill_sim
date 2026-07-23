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
import {
  decideCertification,
  parseCertificationArguments,
  statistics,
  type CertificationArguments,
} from "./certification";
import { decodeHeapUsage, decodePrimaryMemory } from "./cdp-memory";
import {
  summarizeCalibration,
} from "./cpu-calibration";

const execFileAsync = promisify(execFile);
const CALIBRATION_ITERATIONS = 50_000_000;

interface WorkerThrottleController {
  setRate(rate: number): Promise<void>;
  sampleWorkerHeap(): Promise<unknown | null>;
  close(): Promise<void>;
}

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

async function createWorkerThrottleController(
  port: number,
  initialRate: number,
): Promise<WorkerThrottleController> {
  let endpoint: string | null = null;
  for (let attempt = 0; attempt < 50 && endpoint === null; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      const value = (await response.json()) as { webSocketDebuggerUrl?: string };
      endpoint = value.webSocketDebuggerUrl ?? null;
    } catch {
      await new Promise((resolveWait) => setTimeout(resolveWait, 100));
    }
  }
  if (endpoint === null) throw new Error("Chromium CDP endpoint unavailable");
  const socket = new WebSocket(endpoint);
  await new Promise<void>((resolveOpen, reject) => {
    socket.addEventListener("open", () => resolveOpen(), { once: true });
    socket.addEventListener("error", () => reject(new Error("CDP websocket failed")), {
      once: true,
    });
  });
  let rate = initialRate;
  const workerSessions = new Set<string>();
  let messageId = 0;
  const pending = new Map<
    number,
    { resolve: (value: unknown) => void; reject: (error: Error) => void }
  >();
  const send = (
    method: string,
    params: Readonly<Record<string, unknown>> = {},
    sessionId?: string,
  ): Promise<unknown> =>
    new Promise((resolveSend, reject) => {
      const id = ++messageId;
      pending.set(id, { resolve: resolveSend, reject });
      socket.send(
        JSON.stringify({
          id,
          method,
          params,
          ...(sessionId === undefined ? {} : { sessionId }),
        }),
      );
    });
  socket.addEventListener("message", (event) => {
    const value = JSON.parse(String(event.data)) as {
      id?: number;
      method?: string;
      params?: {
        sessionId?: string;
        targetInfo?: { type?: string };
      };
      error?: { message?: string };
      result?: unknown;
    };
    if (value.id !== undefined) {
      const waiter = pending.get(value.id);
      pending.delete(value.id);
      if (value.error === undefined) waiter?.resolve(value.result);
      else waiter?.reject(new Error(value.error.message ?? "CDP command failed"));
      return;
    }
    if (
      value.method === "Target.detachedFromTarget" &&
      value.params?.sessionId !== undefined
    ) {
      workerSessions.delete(value.params.sessionId);
      return;
    }
    if (
      value.method !== "Target.attachedToTarget" ||
      value.params?.sessionId === undefined
    ) {
      return;
    }
    const sessionId = value.params.sessionId;
    const configure = async (): Promise<void> => {
      if (value.params?.targetInfo?.type === "page") {
        await send(
          "Target.setAutoAttach",
          {
            autoAttach: true,
            waitForDebuggerOnStart: true,
            flatten: true,
          },
          sessionId,
        );
      }
      if (value.params?.targetInfo?.type === "worker") {
        workerSessions.add(sessionId);
      }
      await send("Runtime.runIfWaitingForDebugger", {}, sessionId);
    };
    void configure().catch(() => undefined);
  });
  await send("Target.setAutoAttach", {
    autoAttach: true,
    waitForDebuggerOnStart: true,
    flatten: true,
  });
  return {
    async setRate(nextRate) {
      rate = nextRate;
      void workerSessions;
      void rate;
    },
    async sampleWorkerHeap() {
      const sessionId = [...workerSessions].at(-1);
      if (sessionId === undefined) return null;
      await send("HeapProfiler.collectGarbage", {}, sessionId).catch(
        () => undefined,
      );
      return send("Runtime.getHeapUsage", {}, sessionId);
    },
    async close() {
      socket.close();
    },
  };
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
  workerThrottle: WorkerThrottleController,
) {
  const page1: number[] = [];
  const page4: number[] = [];
  const worker1: number[] = [];
  const worker4: number[] = [];
  for (const rate of [1, 4] as const) {
    await session.send("Emulation.setCPUThrottlingRate", { rate });
    await workerThrottle.setRate(rate);
    await page.evaluate(async () => {
      const api = window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!;
      await api.terminateWorker();
      await api.recreateWorker();
    });
    await pageCalibration(page);
    await workerCalibration(page);
    for (let index = 0; index < 3; index += 1) {
      (rate === 1 ? page1 : page4).push(await pageCalibration(page));
      (rate === 1 ? worker1 : worker4).push(await workerCalibration(page));
    }
  }
  return {
    page: summarizeCalibration(page1, page4),
    worker: summarizeCalibration(worker1, worker4),
  };
}

async function primaryMemory(page: Page) {
  try {
    const value = await page.evaluate(async () => {
      if (performance.measureUserAgentSpecificMemory === undefined) {
        throw new Error("measureUserAgentSpecificMemory unavailable");
      }
      return performance.measureUserAgentSpecificMemory();
    });
    return { sample: decodePrimaryMemory(value), error: null };
  } catch (error) {
    return {
      sample: null,
      error:
        error instanceof Error
          ? error.message.split(/\r?\n/u, 1)[0]!
          : "memory sample failed",
    };
  }
}

async function supportingMemory(
  session: Awaited<ReturnType<BrowserContext["newCDPSession"]>>,
  workerThrottle: WorkerThrottleController,
) {
  const warnings: string[] = [];
  try {
    await session.send("HeapProfiler.collectGarbage");
  } catch (error) {
    warnings.push(
      `page garbage collection failed: ${
        error instanceof Error
          ? error.message.split(/\r?\n/u, 1)[0]
          : "unknown"
      }`,
    );
  }
  const pageHeap = decodeHeapUsage(await session.send("Runtime.getHeapUsage"));
  const targets = await session.send("Target.getTargets");
  const workerTarget = targets.targetInfos.find(
    (target) =>
      target.type === "worker" && target.title.includes("mhwilds-browser-solver"),
  );
  const rawWorkerHeap = await workerThrottle.sampleWorkerHeap();
  if (workerTarget === undefined && rawWorkerHeap === null) {
    warnings.push("dedicated Worker target was not exposed to the page CDP session");
  }
  return {
    page: pageHeap,
    worker: rawWorkerHeap === null ? null : decodeHeapUsage(rawWorkerHeap),
    worker_target_id: workerTarget?.targetId ?? null,
    warnings,
  };
}

async function sampleMemory(
  name: string,
  page: Page,
  session: Awaited<ReturnType<BrowserContext["newCDPSession"]>>,
  workerThrottle: WorkerThrottleController,
) {
  return {
    name,
    primary: await primaryMemory(page),
    cdp: await supportingMemory(session, workerThrottle),
  };
}

function mixed(report: BrowserBenchmarkReport): BrowserBenchmarkCaseReport {
  const result = report.cases.find(({ name }) => name === "mixed-ranked");
  if (result === undefined) throw new Error("mixed-ranked report is missing");
  return result;
}

function reportCounts(reports: readonly BrowserBenchmarkReport[]) {
  const cases = reports.flatMap((report) => report.cases);
  return {
    parityFailures: cases.filter(({ parity }) => parity !== true).length,
    nondeterministicCases: cases.filter(({ deterministic }) => !deterministic).length,
    timeouts: cases.filter(({ result }) => result.status === "timed-out").length,
    invalidCandidates: 0,
  };
}

async function runCertification(args: CertificationArguments): Promise<unknown> {
  await Promise.all([stat(args.catalog), stat(args.oracle)]);
  const [catalogRaw, oracleRaw, compactHash] = await Promise.all([
    readFile(args.catalog, "utf8"),
    readFile(args.oracle, "utf8"),
    sha256(args.catalog),
  ]);
  const catalog = JSON.parse(catalogRaw) as {
    source_catalog: { sha256: string };
  };
  const oracle = JSON.parse(oracleRaw) as { cases: readonly unknown[] };
  process.env.MHWILDS_BROWSER_SOLVER_CATALOG = args.catalog;
  process.env.MHWILDS_BROWSER_SOLVER_ORACLE = args.oracle;
  const server: ViteDevServer = await createServer({
    configFile: resolve(process.cwd(), "vite.config.ts"),
    base: "/",
    server: { host: "127.0.0.1", port: 0, strictPort: false },
  });
  let browser: Browser | null = null;
  let workerThrottle: WorkerThrottleController | null = null;
  try {
    await server.listen();
    const address = server.httpServer?.address();
    if (address === null || typeof address === "string" || address === undefined) {
      throw new Error("Vite did not allocate a local port");
    }
    const baseUrl = `http://127.0.0.1:${address.port}`;
    const cdpPort = await availablePort();
    browser = await chromium.launch({
      headless: !args.headed,
      args: [
        "--enable-precise-memory-info",
        `--remote-debugging-port=${cdpPort}`,
      ],
    });
    workerThrottle = await createWorkerThrottleController(cdpPort, 1);
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
      await sampleMemory("baseline", memoryPage, memorySession, workerThrottle),
    ];
    await memoryPage.goto(`${baseUrl}/solver-benchmark.html?certification=1`);
    await bridge(memoryPage);
    stages.push(
      await sampleMemory("worker-init", memoryPage, memorySession, workerThrottle),
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
      ),
    );
    await memoryPage.evaluate((timeoutMs) =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.runSuite({
        repeats: 1,
        timeout_ms: timeoutMs,
      }), args.timeoutMs);
    stages.push(
      await sampleMemory("full-suite", memoryPage, memorySession, workerThrottle),
    );
    await memoryPage.evaluate(() =>
      window.__MHWILDS_BROWSER_SOLVER_CERTIFICATION__!.terminateWorker(),
    );
    stages.push(
      await sampleMemory(
        "post-terminate",
        memoryPage,
        memorySession,
        workerThrottle,
      ),
    );
    const retention: unknown[] = [];
    for (let cycle = 1; cycle <= 5; cycle += 1) {
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
      retention.push(
        await sampleMemory(
          `retention-${cycle}-post-terminate`,
          memoryPage,
          memorySession,
          workerThrottle,
        ),
      );
    }
    stages.push(retention[retention.length - 1] as Awaited<ReturnType<typeof sampleMemory>>);

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
    );
    await memoryContext.close();

    const desktopMixed = desktopReports.map(
      (report) => mixed(report).timings_ms.median,
    );
    const mobileCases = mobileReports.flatMap((report) =>
      report.cases.filter(({ name }) => name !== "impossible-stress"),
    );
    const primaryBytes = (name: string): number | null =>
      stages.find((stage) => stage.name === name)?.primary.sample?.bytes ?? null;
    const retentionSamples = retention as Array<
      Awaited<ReturnType<typeof sampleMemory>>
    >;
    const firstRetention = retentionSamples[0]?.primary.sample?.bytes ?? null;
    const finalRetention =
      retentionSamples[retentionSamples.length - 1]?.primary.sample?.bytes ?? null;
    const allCounts = reportCounts([...desktopReports, ...mobileReports]);
    const decision = decideCertification({
      workerCalibration: cpuCalibration.worker,
      desktopMixedMs: desktopMixed,
      mobileCaseMediansMs: mobileCases.map(({ timings_ms }) => timings_ms.median),
      mobileCaseMaxMs: mobileCases.map(({ timings_ms }) => timings_ms.max),
      workerInitMedianMs: statistics(mobileWorkerInit).median,
      ...allCounts,
      errors: errors.length,
      tabCrashes: crashes.length,
      primaryMemoryAvailable: stages.every((stage) => stage.primary.sample !== null),
      postMixedBytes: primaryBytes("post-mixed-ranked"),
      fullSuitePeakBytes: primaryBytes("full-suite"),
      postInitIncrementBytes:
        primaryBytes("worker-init") !== null && primaryBytes("baseline") !== null
          ? primaryBytes("worker-init")! - primaryBytes("baseline")!
          : null,
      firstPostTerminateBytes: firstRetention,
      finalPostTerminateBytes: finalRetention,
      retentionContinuouslyIncreasing: retentionSamples.every(
        (sample, index) =>
          index === 0 ||
          (sample.primary.sample?.bytes ?? -1) >
            (retentionSamples[index - 1]?.primary.sample?.bytes ?? Infinity),
      ),
      cancelRestartPassed:
        cancelProgress !== null &&
        restartCase.result.status === "optimal" &&
        restartCase.parity === true,
    });
    const { stdout: commitSha } = await execFileAsync("git", ["rev-parse", "HEAD"]);
    const { stdout: gitStatus } = await execFileAsync("git", ["status", "--porcelain"]);
    return {
      format_version: 1,
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
        headless: !args.headed,
      },
      cpu_calibration: {
        ...cpuCalibration,
        page_cross_origin_isolated: calibrationState.cross_origin_isolated,
        worker_cross_origin_isolated:
          calibrationState.worker_cross_origin_isolated,
        cpu_throttle_verified:
          cpuCalibration.worker.rate_ratio !== null &&
          cpuCalibration.worker.rate_ratio >= 2.5 &&
          cpuCalibration.worker.rate_ratio <= 6.5,
      },
      desktop: {
        profile: "desktop 1x",
        suites: desktopReports,
        suite_total_ms: desktopTotals,
        mixed_ranked_across_suites: statistics(desktopMixed),
        worker_init_ms: statistics(desktopWorkerInit),
      },
      mobile_4x: {
        profile: "headless Chromium low-speed mobile-equivalent 4x profile; not a real device",
        suites: mobileReports,
        worker_init_ms: statistics(mobileWorkerInit),
      },
      memory: {
        method: "measureUserAgentSpecificMemory",
        stages,
        retention_cycles: retention,
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
      decision: {
        ...decision,
        diagnostics: { console_page_errors: errors, tab_crashes: crashes, request_failures: requestsFailed },
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
  cwd = process.env.INIT_CWD ?? process.cwd(),
): Promise<number> {
  try {
    const args = resolvedArguments(parseCertificationArguments(argv), cwd);
    await mkdir(args.screenshotDirectory, { recursive: true });
    const report = await runCertification(args);
    await atomicJson(args.output, report);
    process.stdout.write(`${JSON.stringify({ output: args.output, decision: (report as { decision: { status: string } }).decision.status })}\n`);
    return 0;
  } catch (error) {
    process.stderr.write(
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
