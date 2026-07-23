/// <reference types="node" />

export type WorkerThrottleSupport = "applied" | "unsupported" | "failed";

export interface WorkerThrottleSessionResult {
  readonly target_type: "worker";
  readonly target_title: string | null;
  readonly requested_rate: number;
  readonly support: WorkerThrottleSupport;
  readonly protocol_error_code: number | null;
  readonly protocol_error_message: string | null;
}

export interface WorkerThrottleApplySummary {
  readonly requested_rate: number;
  readonly active_worker_count: number;
  readonly applied_count: number;
  readonly unsupported_count: number;
  readonly failed_count: number;
  readonly sessions: readonly WorkerThrottleSessionResult[];
}

export interface WorkerCdpTransport {
  send(message: string): void;
  close(): Promise<void>;
  onMessage(listener: (message: unknown) => void): () => void;
  onClose(listener: () => void): () => void;
  onError(listener: () => void): () => void;
}

export interface WorkerCdpControllerOptions {
  readonly port?: number;
  readonly transport?: WorkerCdpTransport;
  readonly commandTimeoutMs?: number;
}

export interface WorkerCdpController {
  captureWorkerAttachCursor(): number;
  waitForWorkersDetached(timeoutMs?: number): Promise<void>;
  waitForWorkerAfter(
    cursor: number,
    timeoutMs?: number,
  ): Promise<WorkerThrottleSessionResult>;
  setRate(rate: number): Promise<WorkerThrottleApplySummary>;
  sampleWorkerHeap(): Promise<unknown | null>;
  close(): Promise<void>;
}

export class WorkerCdpAttachmentTimeoutError extends Error {
  constructor() {
    super("timed out waiting for a newly attached Worker");
    this.name = "WorkerCdpAttachmentTimeoutError";
  }
}

interface CdpProtocolErrorShape {
  readonly code: number;
  readonly message: string;
}

interface PendingCommand {
  readonly sessionId: string | null;
  readonly resolve: (value: unknown) => void;
  readonly reject: (error: Error) => void;
  readonly timeout: ReturnType<typeof setTimeout>;
}

interface WorkerSession {
  readonly sessionId: string;
  readonly targetTitle: string | null;
  readonly sequence: number;
  state: "configuring" | "ready";
  detached: boolean;
  resumeAttempted: boolean;
  lastApply: WorkerThrottleSessionResult | null;
  configuration: Promise<void> | null;
}

interface WorkerWaiter {
  readonly cursor: number;
  readonly resolve: (value: WorkerThrottleSessionResult) => void;
  readonly reject: (error: Error) => void;
  readonly timeout: ReturnType<typeof setTimeout>;
}

interface WorkersDetachedWaiter {
  readonly resolve: () => void;
  readonly reject: (error: Error) => void;
  readonly timeout: ReturnType<typeof setTimeout>;
}

class CdpProtocolCommandError extends Error {
  readonly code: number;

  constructor(error: CdpProtocolErrorShape) {
    super(error.message);
    this.name = "CdpProtocolCommandError";
    this.code = error.code;
  }
}

class CdpDetachedError extends Error {
  constructor() {
    super("worker detached during CDP command");
    this.name = "CdpDetachedError";
  }
}

class CdpControllerClosedError extends Error {
  constructor() {
    super("Worker CDP controller is closed");
    this.name = "CdpControllerClosedError";
  }
}

const DEFAULT_COMMAND_TIMEOUT_MS = 10_000;
const MAX_CPU_THROTTLE_RATE = 64;
const MAX_DIAGNOSTIC_LENGTH = 500;

function finitePort(value: number | undefined): number {
  if (
    value === undefined ||
    !Number.isSafeInteger(value) ||
    value < 1 ||
    value > 65_535
  ) {
    throw new TypeError("port must be an integer between 1 and 65535");
  }
  return value;
}

function validTimeout(value: number | undefined, fallback: number): number {
  const timeout = value ?? fallback;
  if (!Number.isFinite(timeout) || timeout <= 0) {
    throw new TypeError("timeout must be a finite positive number");
  }
  return timeout;
}

function validRate(rate: number): number {
  if (
    typeof rate !== "number" ||
    !Number.isFinite(rate) ||
    rate < 1 ||
    rate > MAX_CPU_THROTTLE_RATE
  ) {
    throw new TypeError(
      `CPU throttle rate must be a finite number between 1 and ${MAX_CPU_THROTTLE_RATE}`,
    );
  }
  return rate;
}

export function sanitizeCdpProtocolMessage(value: unknown): string {
  if (typeof value !== "string") {
    return "CDP command failed";
  }
  const line = value.split(/\r?\n/u, 1)[0]!.replace(/\s+/gu, " ").trim();
  if (line.length === 0) {
    return "CDP command failed";
  }
  return line.slice(0, MAX_DIAGNOSTIC_LENGTH);
}

export function classifyWorkerThrottleError(
  error: CdpProtocolErrorShape,
): Exclude<WorkerThrottleSupport, "applied"> {
  if (error.code === -32601) {
    return "unsupported";
  }
  if (error.code !== -32000 && error.code !== -32001) {
    return "failed";
  }

  const message = sanitizeCdpProtocolMessage(error.message);
  const methodNotFound =
    /^(?:method )?['"]?Emulation\.setCPUThrottlingRate['"]? (?:was not found|wasn't found|not found)\.?$/iu;
  const pageOnly =
    /^(?:command (?:is only supported|can only be executed) on (?:a )?page targets?|operation is only supported for pages, not workers)\.?$/iu;
  const domainUnavailable =
    /^emulation domain is (?:not available|unsupported) (?:for|on) (?:this )?target(?: type)?\.?$/iu;
  const targetUnsupported =
    /^(?:the )?target type .+ does not support (?:the )?emulation(?: domain)?\.?$/iu;
  return methodNotFound.test(message) ||
    pageOnly.test(message) ||
    domainUnavailable.test(message) ||
    targetUnsupported.test(message)
    ? "unsupported"
    : "failed";
}

function publicResult(
  session: WorkerSession,
  requestedRate: number,
  support: WorkerThrottleSupport,
  protocolErrorCode: number | null,
  protocolErrorMessage: string | null,
): WorkerThrottleSessionResult {
  return Object.freeze({
    target_type: "worker" as const,
    target_title: session.targetTitle,
    requested_rate: requestedRate,
    support,
    protocol_error_code: protocolErrorCode,
    protocol_error_message: protocolErrorMessage,
  });
}

function failedResult(
  session: WorkerSession,
  requestedRate: number,
  error: unknown,
): WorkerThrottleSessionResult {
  if (error instanceof CdpProtocolCommandError) {
    const message = sanitizeCdpProtocolMessage(error.message);
    return publicResult(
      session,
      requestedRate,
      classifyWorkerThrottleError({ code: error.code, message }),
      error.code,
      message,
    );
  }
  return publicResult(
    session,
    requestedRate,
    "failed",
    null,
    sanitizeCdpProtocolMessage(error instanceof Error ? error.message : error),
  );
}

function summary(
  requestedRate: number,
  entries: readonly {
    readonly sequence: number;
    readonly result: WorkerThrottleSessionResult;
  }[],
): WorkerThrottleApplySummary {
  const sessions = entries
    .slice()
    .sort((left, right) => left.sequence - right.sequence)
    .map(({ result }) => result);
  return Object.freeze({
    requested_rate: requestedRate,
    active_worker_count: sessions.length,
    applied_count: sessions.filter(({ support }) => support === "applied").length,
    unsupported_count: sessions.filter(({ support }) => support === "unsupported")
      .length,
    failed_count: sessions.filter(({ support }) => support === "failed").length,
    sessions: Object.freeze(sessions),
  });
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

class BrowserWebSocketTransport implements WorkerCdpTransport {
  readonly #socket: WebSocket;

  constructor(socket: WebSocket) {
    this.#socket = socket;
  }

  send(message: string): void {
    this.#socket.send(message);
  }

  async close(): Promise<void> {
    if (this.#socket.readyState === WebSocket.CLOSED) {
      return;
    }
    await new Promise<void>((resolveClose) => {
      const timeout = setTimeout(resolveClose, 1_000);
      this.#socket.addEventListener(
        "close",
        () => {
          clearTimeout(timeout);
          resolveClose();
        },
        { once: true },
      );
      this.#socket.close();
    });
  }

  onMessage(listener: (message: unknown) => void): () => void {
    const handler = (event: MessageEvent): void => listener(event.data);
    this.#socket.addEventListener("message", handler);
    return () => this.#socket.removeEventListener("message", handler);
  }

  onClose(listener: () => void): () => void {
    this.#socket.addEventListener("close", listener);
    return () => this.#socket.removeEventListener("close", listener);
  }

  onError(listener: () => void): () => void {
    this.#socket.addEventListener("error", listener);
    return () => this.#socket.removeEventListener("error", listener);
  }
}

async function discoverBrowserEndpoint(port: number): Promise<string> {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (!response.ok) {
        throw new Error("CDP endpoint returned an unsuccessful response");
      }
      const value = asRecord(await response.json());
      if (typeof value?.webSocketDebuggerUrl === "string") {
        return value.webSocketDebuggerUrl;
      }
    } catch {
      // Endpoint startup is retried; command and session failures are never hidden.
    }
    await new Promise<void>((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw new Error("Chromium CDP endpoint unavailable");
}

async function connectBrowserTransport(port: number): Promise<WorkerCdpTransport> {
  const endpoint = await discoverBrowserEndpoint(port);
  const socket = new WebSocket(endpoint);
  await new Promise<void>((resolveOpen, rejectOpen) => {
    const handleOpen = (): void => {
      socket.removeEventListener("error", handleError);
      resolveOpen();
    };
    const handleError = (): void => {
      socket.removeEventListener("open", handleOpen);
      rejectOpen(new Error("CDP websocket failed"));
    };
    socket.addEventListener("open", handleOpen, { once: true });
    socket.addEventListener("error", handleError, { once: true });
  });
  return new BrowserWebSocketTransport(socket);
}

class WorkerCdpControllerImplementation implements WorkerCdpController {
  readonly #transport: WorkerCdpTransport;
  readonly #commandTimeoutMs: number;
  readonly #pending = new Map<number, PendingCommand>();
  readonly #workers = new Map<string, WorkerSession>();
  readonly #pages = new Set<string>();
  readonly #configurationTasks = new Set<Promise<void>>();
  readonly #workerWaiters = new Set<WorkerWaiter>();
  readonly #workersDetachedWaiters = new Set<WorkersDetachedWaiter>();
  readonly #unsubscribe: (() => void)[];
  #messageId = 0;
  #currentRate = 1;
  #attachSequence = 0;
  #failure: Error | null = null;
  #closing = false;
  #closed = false;
  #closePromise: Promise<void> | null = null;
  #rateTail: Promise<void> = Promise.resolve();

  constructor(transport: WorkerCdpTransport, commandTimeoutMs: number) {
    this.#transport = transport;
    this.#commandTimeoutMs = commandTimeoutMs;
    this.#unsubscribe = [
      transport.onMessage((message) => this.#handleMessage(message)),
      transport.onClose(() => {
        if (!this.#closing && !this.#closed) {
          this.#fail(new Error("CDP transport closed unexpectedly"));
        }
      }),
      transport.onError(() => {
        if (!this.#closing && !this.#closed) {
          this.#fail(new Error("CDP transport failed"));
        }
      }),
    ];
  }

  async initialize(): Promise<void> {
    await this.#send("Target.setAutoAttach", {
      autoAttach: true,
      waitForDebuggerOnStart: true,
      flatten: true,
    });
  }

  captureWorkerAttachCursor(): number {
    this.#assertUsable();
    return this.#attachSequence;
  }

  waitForWorkersDetached(
    timeoutMs = this.#commandTimeoutMs,
  ): Promise<void> {
    this.#assertUsable();
    const waitTimeout = validTimeout(timeoutMs, this.#commandTimeoutMs);
    if (this.#workers.size === 0) {
      return Promise.resolve();
    }
    return new Promise<void>((resolveWait, rejectWait) => {
      const waiter: WorkersDetachedWaiter = {
        resolve: resolveWait,
        reject: rejectWait,
        timeout: setTimeout(() => {
          this.#workersDetachedWaiters.delete(waiter);
          rejectWait(new Error("timed out waiting for Workers to detach"));
        }, waitTimeout),
      };
      this.#workersDetachedWaiters.add(waiter);
    });
  }

  waitForWorkerAfter(
    cursor: number,
    timeoutMs = this.#commandTimeoutMs,
  ): Promise<WorkerThrottleSessionResult> {
    this.#assertUsable();
    if (!Number.isSafeInteger(cursor) || cursor < 0) {
      return Promise.reject(
        new TypeError("worker attach cursor must be a nonnegative safe integer"),
      );
    }
    const waitTimeout = validTimeout(timeoutMs, this.#commandTimeoutMs);
    const existing = this.#readyWorkerAfter(cursor);
    if (existing !== undefined && existing.lastApply !== null) {
      return Promise.resolve(existing.lastApply);
    }
    return new Promise<WorkerThrottleSessionResult>((resolveWait, rejectWait) => {
      const waiter: WorkerWaiter = {
        cursor,
        resolve: resolveWait,
        reject: rejectWait,
        timeout: setTimeout(() => {
          this.#workerWaiters.delete(waiter);
          rejectWait(new WorkerCdpAttachmentTimeoutError());
        }, waitTimeout),
      };
      this.#workerWaiters.add(waiter);
    });
  }

  setRate(rate: number): Promise<WorkerThrottleApplySummary> {
    const requestedRate = validRate(rate);
    this.#assertUsable();
    const operation = this.#rateTail.then(() =>
      this.#applyRequestedRate(requestedRate),
    );
    this.#rateTail = operation.then(
      () => undefined,
      () => undefined,
    );
    return operation;
  }

  async sampleWorkerHeap(): Promise<unknown | null> {
    this.#assertUsable();
    const session = [...this.#workers.values()]
      .filter(({ detached, state }) => !detached && state === "ready")
      .sort((left, right) => right.sequence - left.sequence)[0];
    if (session === undefined) {
      return null;
    }
    await this.#send("HeapProfiler.collectGarbage", {}, session.sessionId);
    return this.#send("Runtime.getHeapUsage", {}, session.sessionId);
  }

  close(): Promise<void> {
    if (this.#closePromise !== null) {
      return this.#closePromise;
    }
    this.#closing = true;
    const error = new CdpControllerClosedError();
    this.#rejectPending(error);
    this.#rejectWorkerWaiters(error);
    this.#rejectWorkersDetachedWaiters(error);
    this.#closePromise = (async () => {
      try {
        await this.#transport.close();
      } finally {
        this.#closed = true;
        for (const unsubscribe of this.#unsubscribe) {
          unsubscribe();
        }
      }
    })();
    return this.#closePromise;
  }

  async #applyRequestedRate(
    requestedRate: number,
  ): Promise<WorkerThrottleApplySummary> {
    this.#assertUsable();
    this.#currentRate = requestedRate;
    const results = new Map<
      string,
      { readonly sequence: number; readonly result: WorkerThrottleSessionResult }
    >();
    const attempted = new Set<string>();

    while (!this.#closing && !this.#closed) {
      const configuring = [...this.#workers.values()].filter(
        ({ detached, state }) => !detached && state === "configuring",
      );
      if (configuring.length > 0) {
        await Promise.all(
          configuring.map(({ configuration }) => configuration).filter(
            (configuration): configuration is Promise<void> =>
              configuration !== null,
          ),
        );
      }
      if (this.#failure !== null) {
        break;
      }

      const ready = [...this.#workers.values()].filter(
        ({ detached, sessionId, state }) =>
          !detached && state === "ready" && !attempted.has(sessionId),
      );
      if (ready.length === 0) {
        break;
      }
      const applied = await Promise.all(
        ready.map(async (session) => {
          attempted.add(session.sessionId);
          const result = await this.#applyWorkerRate(session, requestedRate);
          session.lastApply = result;
          return { session, result };
        }),
      );
      for (const { session, result } of applied) {
        results.set(session.sessionId, { sequence: session.sequence, result });
      }
      if (applied.some(({ result }) => result.support === "failed")) {
        break;
      }
    }

    for (const session of this.#workers.values()) {
      if (
        !session.detached &&
        session.lastApply?.requested_rate === requestedRate &&
        !results.has(session.sessionId)
      ) {
        results.set(session.sessionId, {
          sequence: session.sequence,
          result: session.lastApply,
        });
      }
    }
    if (this.#closing || this.#closed) {
      throw new CdpControllerClosedError();
    }
    const result = summary(requestedRate, [...results.values()]);
    if (result.failed_count > 0) {
      this.#fail(new Error("Worker CPU throttle application failed"));
    }
    return result;
  }

  async #applyWorkerRate(
    session: WorkerSession,
    requestedRate: number,
  ): Promise<WorkerThrottleSessionResult> {
    if (session.detached || !this.#workers.has(session.sessionId)) {
      return failedResult(session, requestedRate, new CdpDetachedError());
    }
    try {
      await this.#send(
        "Emulation.setCPUThrottlingRate",
        { rate: requestedRate },
        session.sessionId,
      );
      return publicResult(session, requestedRate, "applied", null, null);
    } catch (error) {
      return failedResult(session, requestedRate, error);
    }
  }

  #handleMessage(message: unknown): void {
    let value: Record<string, unknown> | null;
    try {
      value = asRecord(
        typeof message === "string" ? (JSON.parse(message) as unknown) : message,
      );
    } catch {
      this.#fail(new Error("CDP transport returned malformed JSON"));
      return;
    }
    if (value === null) {
      this.#fail(new Error("CDP transport returned a malformed message"));
      return;
    }

    if (value.id !== undefined) {
      this.#handleResponse(value);
      return;
    }
    if (typeof value.method !== "string") {
      this.#fail(new Error("CDP transport returned a malformed event"));
      return;
    }
    if (value.method === "Target.detachedFromTarget") {
      this.#handleDetach(value.params);
      return;
    }
    if (value.method === "Target.attachedToTarget") {
      this.#handleAttach(value.params);
    }
  }

  #handleResponse(value: Record<string, unknown>): void {
    if (!Number.isSafeInteger(value.id)) {
      this.#fail(new Error("CDP transport returned a malformed response ID"));
      return;
    }
    const id = value.id as number;
    const command = this.#pending.get(id);
    if (command === undefined) {
      return;
    }
    this.#pending.delete(id);
    clearTimeout(command.timeout);

    if (value.error !== undefined) {
      const error = asRecord(value.error);
      if (
        error === null ||
        typeof error.code !== "number" ||
        !Number.isFinite(error.code) ||
        typeof error.message !== "string"
      ) {
        command.reject(new Error("CDP transport returned a malformed error"));
        return;
      }
      command.reject(
        new CdpProtocolCommandError({
          code: error.code,
          message: sanitizeCdpProtocolMessage(error.message),
        }),
      );
      return;
    }
    if (!Object.hasOwn(value, "result")) {
      command.reject(new Error("CDP transport returned a malformed response"));
      return;
    }
    command.resolve(value.result);
  }

  #handleDetach(paramsValue: unknown): void {
    const params = asRecord(paramsValue);
    const sessionId =
      params !== null && typeof params.sessionId === "string"
        ? params.sessionId
        : null;
    if (sessionId === null) {
      this.#fail(new Error("CDP detach event omitted its session"));
      return;
    }
    const worker = this.#workers.get(sessionId);
    if (worker !== undefined) {
      worker.detached = true;
      this.#workers.delete(sessionId);
      if (this.#workers.size === 0) {
        this.#resolveWorkersDetachedWaiters();
      }
    }
    this.#pages.delete(sessionId);
    for (const [id, command] of this.#pending) {
      if (command.sessionId === sessionId) {
        this.#pending.delete(id);
        clearTimeout(command.timeout);
        command.reject(new CdpDetachedError());
      }
    }
  }

  #handleAttach(paramsValue: unknown): void {
    const params = asRecord(paramsValue);
    const targetInfo = asRecord(params?.targetInfo);
    const sessionId =
      typeof params?.sessionId === "string" && params.sessionId.length > 0
        ? params.sessionId
        : null;
    const targetType =
      typeof targetInfo?.type === "string" ? targetInfo.type : null;
    if (sessionId === null || targetType === null) {
      this.#fail(new Error("CDP attach event omitted target metadata"));
      return;
    }
    if (this.#workers.has(sessionId) || this.#pages.has(sessionId)) {
      this.#fail(new Error("CDP attached the same session more than once"));
      return;
    }

    if (targetType === "worker") {
      const session: WorkerSession = {
        sessionId,
        targetTitle:
          typeof targetInfo?.title === "string" &&
          targetInfo.title.trim().length > 0
            ? sanitizeCdpProtocolMessage(targetInfo.title)
            : null,
        sequence: ++this.#attachSequence,
        state: "configuring",
        detached: false,
        resumeAttempted: false,
        lastApply: null,
        configuration: null,
      };
      this.#workers.set(sessionId, session);
      const configuration = this.#configureWorker(session);
      session.configuration = configuration;
      this.#trackConfiguration(configuration);
      return;
    }

    if (targetType === "page") {
      this.#pages.add(sessionId);
      this.#trackConfiguration(this.#configurePage(sessionId));
      return;
    }
    this.#trackConfiguration(this.#resumeSession(sessionId));
  }

  async #configureWorker(session: WorkerSession): Promise<void> {
    let unexpectedFailure: WorkerThrottleSessionResult | null = null;
    while (!session.detached) {
      const requestedRate = this.#currentRate;
      const result = await this.#applyWorkerRate(session, requestedRate);
      session.lastApply = result;
      if (result.support === "failed") {
        unexpectedFailure = result;
        break;
      }
      if (requestedRate === this.#currentRate) {
        break;
      }
    }

    let resumeFailure: Error | null = null;
    try {
      await this.#resumeWorker(session);
    } catch (error) {
      resumeFailure =
        error instanceof Error ? error : new Error("failed to resume Worker");
    }
    if (unexpectedFailure !== null) {
      throw new Error(
        `Worker CPU throttle setup failed: ${unexpectedFailure.protocol_error_message ?? "unknown failure"}`,
      );
    }
    if (resumeFailure !== null) {
      throw resumeFailure;
    }
    if (session.detached) {
      throw new CdpDetachedError();
    }
    session.state = "ready";
    this.#resolveWorkerWaiters();
  }

  async #configurePage(sessionId: string): Promise<void> {
    let setupFailure: Error | null = null;
    try {
      await this.#send(
        "Target.setAutoAttach",
        {
          autoAttach: true,
          waitForDebuggerOnStart: true,
          flatten: true,
        },
        sessionId,
      );
    } catch (error) {
      setupFailure =
        error instanceof Error ? error : new Error("page auto-attach failed");
    }
    try {
      await this.#resumeSession(sessionId);
    } catch (error) {
      if (setupFailure === null) {
        setupFailure =
          error instanceof Error ? error : new Error("page resume failed");
      }
    }
    if (setupFailure !== null) {
      throw setupFailure;
    }
  }

  #resumeWorker(session: WorkerSession): Promise<void> {
    if (session.resumeAttempted) {
      return Promise.reject(new Error("Worker resume was attempted twice"));
    }
    session.resumeAttempted = true;
    if (session.detached) {
      return Promise.reject(new CdpDetachedError());
    }
    return this.#resumeSession(session.sessionId);
  }

  #resumeSession(sessionId: string): Promise<void> {
    return this.#send("Runtime.runIfWaitingForDebugger", {}, sessionId).then(
      () => undefined,
    );
  }

  #trackConfiguration(configuration: Promise<void>): void {
    this.#configurationTasks.add(configuration);
    void configuration.then(
      () => {
        this.#configurationTasks.delete(configuration);
      },
      (error: unknown) => {
        this.#configurationTasks.delete(configuration);
        this.#fail(
          error instanceof Error
            ? error
            : new Error("CDP target configuration failed"),
        );
      },
    );
  }

  #readyWorkerAfter(cursor: number): WorkerSession | undefined {
    return [...this.#workers.values()]
      .filter(
        ({ detached, sequence, state }) =>
          !detached && state === "ready" && sequence > cursor,
      )
      .sort((left, right) => left.sequence - right.sequence)[0];
  }

  #resolveWorkerWaiters(): void {
    for (const waiter of this.#workerWaiters) {
      const session = this.#readyWorkerAfter(waiter.cursor);
      if (session === undefined || session.lastApply === null) {
        continue;
      }
      this.#workerWaiters.delete(waiter);
      clearTimeout(waiter.timeout);
      waiter.resolve(session.lastApply);
    }
  }

  #send(
    method: string,
    params: Readonly<Record<string, unknown>> = {},
    sessionId?: string,
  ): Promise<unknown> {
    this.#assertUsable();
    return new Promise<unknown>((resolveCommand, rejectCommand) => {
      const id = ++this.#messageId;
      const timeout = setTimeout(() => {
        this.#pending.delete(id);
        rejectCommand(new Error(`CDP command timed out: ${method}`));
      }, this.#commandTimeoutMs);
      this.#pending.set(id, {
        sessionId: sessionId ?? null,
        resolve: resolveCommand,
        reject: rejectCommand,
        timeout,
      });
      try {
        this.#transport.send(
          JSON.stringify({
            id,
            method,
            params,
            ...(sessionId === undefined ? {} : { sessionId }),
          }),
        );
      } catch (error) {
        this.#pending.delete(id);
        clearTimeout(timeout);
        rejectCommand(
          error instanceof Error ? error : new Error("CDP transport send failed"),
        );
      }
    });
  }

  #assertUsable(): void {
    if (this.#closing || this.#closed) {
      throw new CdpControllerClosedError();
    }
    if (this.#failure !== null) {
      throw this.#failure;
    }
  }

  #fail(error: Error): void {
    if (this.#failure !== null || this.#closing || this.#closed) {
      return;
    }
    this.#failure = error;
    this.#rejectPending(error);
    this.#rejectWorkerWaiters(error);
    this.#rejectWorkersDetachedWaiters(error);
  }

  #rejectPending(error: Error): void {
    for (const command of this.#pending.values()) {
      clearTimeout(command.timeout);
      command.reject(error);
    }
    this.#pending.clear();
  }

  #rejectWorkerWaiters(error: Error): void {
    for (const waiter of this.#workerWaiters) {
      clearTimeout(waiter.timeout);
      waiter.reject(error);
    }
    this.#workerWaiters.clear();
  }

  #resolveWorkersDetachedWaiters(): void {
    for (const waiter of this.#workersDetachedWaiters) {
      clearTimeout(waiter.timeout);
      waiter.resolve();
    }
    this.#workersDetachedWaiters.clear();
  }

  #rejectWorkersDetachedWaiters(error: Error): void {
    for (const waiter of this.#workersDetachedWaiters) {
      clearTimeout(waiter.timeout);
      waiter.reject(error);
    }
    this.#workersDetachedWaiters.clear();
  }
}

export async function createWorkerCdpController(
  options: WorkerCdpControllerOptions,
): Promise<WorkerCdpController> {
  const commandTimeoutMs = validTimeout(
    options.commandTimeoutMs,
    DEFAULT_COMMAND_TIMEOUT_MS,
  );
  const transport =
    options.transport ??
    (await connectBrowserTransport(finitePort(options.port)));
  const controller = new WorkerCdpControllerImplementation(
    transport,
    commandTimeoutMs,
  );
  try {
    await controller.initialize();
    return controller;
  } catch (error) {
    await controller.close();
    throw error;
  }
}
