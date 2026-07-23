import type {
  BrowserSolverWorkerErrorResponse,
  BrowserSolverWorkerRequest,
  BrowserSolverWorkerResponse,
} from "./protocol";
import type {
  BrowserRankedSearchRequest,
  BrowserSolverProgress,
  BrowserSolverResult,
} from "./types";

interface WorkerLike {
  postMessage(message: BrowserSolverWorkerRequest): void;
  terminate(): void;
  addEventListener(
    type: "message",
    listener: (event: MessageEvent<unknown>) => void,
  ): void;
  addEventListener(
    type: "error",
    listener: (event: ErrorEvent) => void,
  ): void;
}

export type BrowserSolverWorkerFactory = () => WorkerLike;

export interface BrowserSolverClientSearchOptions {
  readonly timeoutMs?: number;
  readonly searchId?: string;
  readonly onProgress?: (progress: BrowserSolverProgress) => void;
}

interface PendingSearch {
  readonly startedAt: number;
  readonly resolve: (result: BrowserSolverResult) => void;
  readonly reject: (error: Error) => void;
  readonly onProgress:
    | ((progress: BrowserSolverProgress) => void)
    | undefined;
}

interface PendingCalibration {
  readonly resolve: (value: WorkerCalibrationResult) => void;
  readonly reject: (error: Error) => void;
}

export interface WorkerCalibrationResult {
  readonly elapsed_ms: number;
  readonly checksum: number;
  readonly cross_origin_isolated: boolean;
}

type ClientState =
  | "new"
  | "initializing"
  | "ready"
  | "failed"
  | "disposed";

function defaultWorkerFactory(): WorkerLike {
  return new Worker(new URL("./worker.ts", import.meta.url), {
    type: "module",
    name: "mhwilds-browser-solver",
  }) as unknown as WorkerLike;
}

function asWorkerResponse(value: unknown): BrowserSolverWorkerResponse | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const response = value as Partial<BrowserSolverWorkerResponse>;
  if (
    response.type !== "ready" &&
    response.type !== "progress" &&
    response.type !== "result" &&
    response.type !== "calibration" &&
    response.type !== "error"
  ) {
    return null;
  }
  return response as BrowserSolverWorkerResponse;
}

function errorFromResponse(
  response: BrowserSolverWorkerErrorResponse,
): Error {
  return new Error(response.message);
}

function cancelledResult(elapsedMs: number): BrowserSolverResult {
  return {
    status: "cancelled",
    candidate: null,
    selected_variant_ids: [],
    preference_score: null,
    decoration_count: null,
    elapsed_ms: elapsedMs,
    visited_nodes: 0,
    pruned_nodes: 0,
    complete_equipment_selections: 0,
  };
}

export class BrowserSolverWorkerClient {
  readonly #workerFactory: BrowserSolverWorkerFactory;
  readonly #now: () => number;
  readonly #pending = new Map<string, PendingSearch>();
  readonly #pendingCalibrations = new Map<string, PendingCalibration>();
  #state: ClientState = "new";
  #worker: WorkerLike | null = null;
  #catalog: unknown;
  #initializationPromise: Promise<void> | null = null;
  #resolveInitialization: (() => void) | null = null;
  #rejectInitialization: ((error: Error) => void) | null = null;
  #workerGeneration = 0;
  #searchSequence = 0;

  constructor(
    workerFactory: BrowserSolverWorkerFactory = defaultWorkerFactory,
    now: () => number = () => performance.now(),
  ) {
    this.#workerFactory = workerFactory;
    this.#now = now;
  }

  initialize(catalog: unknown): Promise<void> {
    if (this.#state !== "new") {
      return Promise.reject(
        new Error("Browser solver worker client is already initialized"),
      );
    }
    this.#catalog = catalog;
    return this.#spawnWorker();
  }

  async search(
    request: BrowserRankedSearchRequest,
    options: BrowserSolverClientSearchOptions = {},
  ): Promise<BrowserSolverResult> {
    await this.#ready();
    if (this.#pending.size !== 0) {
      throw new Error("A browser solver search is already active");
    }
    const timeoutMs = options.timeoutMs ?? 10_000;
    if (
      typeof timeoutMs !== "number" ||
      !Number.isFinite(timeoutMs) ||
      timeoutMs < 0
    ) {
      throw new TypeError("timeoutMs must be a finite nonnegative number");
    }
    const searchId = options.searchId ?? `search-${++this.#searchSequence}`;
    if (
      searchId.length === 0 ||
      searchId.trim() !== searchId
    ) {
      throw new TypeError("searchId must be a non-empty trimmed string");
    }
    if (this.#pending.has(searchId)) {
      throw new Error("Browser solver search ID is already active");
    }

    return new Promise<BrowserSolverResult>((resolve, reject) => {
      this.#pending.set(searchId, {
        startedAt: this.#now(),
        resolve,
        reject,
        onProgress: options.onProgress,
      });
      this.#worker?.postMessage({
        type: "search",
        search_id: searchId,
        request,
        timeout_ms: timeoutMs,
      });
    });
  }

  cancel(searchId: string): boolean {
    const pending = this.#pending.get(searchId);
    if (pending === undefined || this.#worker === null) {
      return false;
    }

    this.#worker.postMessage({ type: "cancel", search_id: searchId });
    this.#worker.terminate();
    this.#worker = null;
    this.#workerGeneration += 1;
    this.#pending.delete(searchId);
    pending.resolve(
      cancelledResult(Math.max(0, this.#now() - pending.startedAt)),
    );

    if (this.#state !== "disposed") {
      const restart = this.#spawnWorker();
      void restart.catch(() => undefined);
    }
    return true;
  }

  async calibrate(iterations: number): Promise<WorkerCalibrationResult> {
    await this.#ready();
    if (!Number.isSafeInteger(iterations) || iterations < 1) {
      throw new TypeError("iterations must be a positive safe integer");
    }
    const calibrationId = `calibration-${++this.#searchSequence}`;
    return new Promise((resolve, reject) => {
      this.#pendingCalibrations.set(calibrationId, { resolve, reject });
      this.#worker?.postMessage({
        type: "calibrate",
        calibration_id: calibrationId,
        iterations,
      });
    });
  }

  dispose(): void {
    if (this.#state === "disposed") {
      return;
    }
    this.#state = "disposed";
    this.#workerGeneration += 1;
    this.#worker?.terminate();
    this.#worker = null;
    const error = new Error("Browser solver worker client was disposed");
    this.#rejectInitialization?.(error);
    this.#clearInitialization();
    for (const pending of this.#pending.values()) {
      pending.reject(error);
    }
    this.#pending.clear();
    for (const pending of this.#pendingCalibrations.values()) {
      pending.reject(error);
    }
    this.#pendingCalibrations.clear();
  }

  async #ready(): Promise<void> {
    if (this.#state === "ready") {
      return;
    }
    if (
      this.#state === "initializing" &&
      this.#initializationPromise !== null
    ) {
      return this.#initializationPromise;
    }
    if (this.#state === "disposed") {
      throw new Error("Browser solver worker client was disposed");
    }
    throw new Error("Browser solver worker client is not initialized");
  }

  #spawnWorker(): Promise<void> {
    if (this.#state === "disposed") {
      return Promise.reject(
        new Error("Browser solver worker client was disposed"),
      );
    }
    const generation = ++this.#workerGeneration;
    const worker = this.#workerFactory();
    this.#worker = worker;
    this.#state = "initializing";
    this.#initializationPromise = new Promise<void>((resolve, reject) => {
      this.#resolveInitialization = resolve;
      this.#rejectInitialization = reject;
    });

    worker.addEventListener("message", (event) => {
      if (generation === this.#workerGeneration) {
        this.#handleResponse(event.data);
      }
    });
    worker.addEventListener("error", (event) => {
      if (generation === this.#workerGeneration) {
        this.#failWorker(
          new Error(
            typeof event.message !== "string" || event.message.length === 0
              ? "Browser solver worker encountered an error"
              : `Browser solver worker error: ${event.message}`,
          ),
        );
      }
    });
    worker.postMessage({ type: "init", catalog: this.#catalog });
    return this.#initializationPromise;
  }

  #handleResponse(value: unknown): void {
    const response = asWorkerResponse(value);
    if (response === null) {
      return;
    }
    switch (response.type) {
      case "ready":
        if (this.#state === "initializing") {
          this.#state = "ready";
          this.#resolveInitialization?.();
          this.#clearInitialization();
        }
        return;
      case "progress": {
        this.#pending.get(response.search_id)?.onProgress?.(
          response.progress,
        );
        return;
      }
      case "result": {
        const pending = this.#pending.get(response.search_id);
        if (pending !== undefined) {
          this.#pending.delete(response.search_id);
          pending.resolve(response.result);
        }
        return;
      }
      case "calibration": {
        const pending = this.#pendingCalibrations.get(response.calibration_id);
        if (pending !== undefined) {
          this.#pendingCalibrations.delete(response.calibration_id);
          pending.resolve({
            elapsed_ms: response.elapsed_ms,
            checksum: response.checksum,
            cross_origin_isolated: response.cross_origin_isolated,
          });
        }
        return;
      }
      case "error": {
        const error = errorFromResponse(response);
        if (response.search_id !== undefined) {
          const pending = this.#pending.get(response.search_id);
          if (pending !== undefined) {
            this.#pending.delete(response.search_id);
            pending.reject(error);
          }
          return;
        }
        if (this.#state === "initializing") {
          this.#failWorker(error);
        }
      }
    }
  }

  #failWorker(error: Error): void {
    this.#state = "failed";
    this.#worker?.terminate();
    this.#worker = null;
    this.#rejectInitialization?.(error);
    this.#clearInitialization();
    for (const pending of this.#pending.values()) {
      pending.reject(error);
    }
    this.#pending.clear();
    for (const pending of this.#pendingCalibrations.values()) {
      pending.reject(error);
    }
    this.#pendingCalibrations.clear();
  }

  #clearInitialization(): void {
    this.#initializationPromise = null;
    this.#resolveInitialization = null;
    this.#rejectInitialization = null;
  }
}
