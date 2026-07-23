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
    worker.addEventListener("error", () => {
      if (generation === this.#workerGeneration) {
        this.#failWorker(
          new Error("Browser solver worker encountered an error"),
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
  }

  #clearInitialization(): void {
    this.#initializationPromise = null;
    this.#resolveInitialization = null;
    this.#rejectInitialization = null;
  }
}
