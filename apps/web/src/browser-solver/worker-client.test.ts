import { describe, expect, it, vi } from "vitest";

import type {
  BrowserSolverWorkerRequest,
  BrowserSolverWorkerResponse,
} from "./protocol";
import type {
  BrowserRankedSearchRequest,
  BrowserSolverResult,
} from "./types";
import { BrowserSolverWorkerClient } from "./worker-client";

const REQUEST: BrowserRankedSearchRequest = Object.freeze({
  requirements: Object.freeze([]),
  preferences: Object.freeze([]),
  max_results: 1,
});

function result(): BrowserSolverResult {
  return {
    status: "infeasible",
    candidate: null,
    selected_variant_ids: [],
    preference_score: null,
    decoration_count: null,
    elapsed_ms: 1,
    visited_nodes: 2,
    pruned_nodes: 3,
    complete_equipment_selections: 4,
  };
}

class FakeWorker {
  readonly posted: BrowserSolverWorkerRequest[] = [];
  terminated = false;
  #messageListeners: Array<(event: MessageEvent<unknown>) => void> = [];
  #errorListeners: Array<(event: ErrorEvent) => void> = [];

  postMessage(message: BrowserSolverWorkerRequest): void {
    this.posted.push(message);
  }

  terminate(): void {
    this.terminated = true;
  }

  addEventListener(
    type: "message" | "error",
    listener:
      | ((event: MessageEvent<unknown>) => void)
      | ((event: ErrorEvent) => void),
  ): void {
    if (type === "message") {
      this.#messageListeners.push(
        listener as (event: MessageEvent<unknown>) => void,
      );
    } else {
      this.#errorListeners.push(listener as (event: ErrorEvent) => void);
    }
  }

  emit(response: BrowserSolverWorkerResponse): void {
    for (const listener of this.#messageListeners) {
      listener(new MessageEvent("message", { data: response }));
    }
  }

  fail(): void {
    for (const listener of this.#errorListeners) {
      listener(new ErrorEvent("error"));
    }
  }
}

function ready(worker: FakeWorker): void {
  worker.emit({
    type: "ready",
    source_catalog_sha256: "a".repeat(64),
  });
}

describe("BrowserSolverWorkerClient", () => {
  it("initializes and resolves a valid search response", async () => {
    const worker = new FakeWorker();
    const client = new BrowserSolverWorkerClient(() => worker);
    const initialization = client.initialize({ fixture: true });
    expect(worker.posted).toEqual([
      { type: "init", catalog: { fixture: true } },
    ]);
    ready(worker);
    await initialization;

    const progress = vi.fn();
    const search = client.search(REQUEST, {
      searchId: "case-1",
      timeoutMs: 123,
      onProgress: progress,
    });
    await Promise.resolve();
    expect(worker.posted.at(-1)).toEqual({
      type: "search",
      search_id: "case-1",
      request: REQUEST,
      timeout_ms: 123,
    });
    worker.emit({
      type: "progress",
      search_id: "case-1",
      progress: {
        elapsed_ms: 0.5,
        visited_nodes: 1,
        pruned_nodes: 0,
        complete_equipment_selections: 0,
        preference_score: null,
        decoration_count: null,
      },
    });
    worker.emit({ type: "result", search_id: "case-1", result: result() });

    await expect(search).resolves.toEqual(result());
    expect(progress).toHaveBeenCalledTimes(1);
  });

  it("rejects search before initialization and repeated initialization", async () => {
    const worker = new FakeWorker();
    const client = new BrowserSolverWorkerClient(() => worker);

    await expect(client.search(REQUEST)).rejects.toThrow("not initialized");
    const initialization = client.initialize({});
    ready(worker);
    await initialization;
    await expect(client.initialize({})).rejects.toThrow(
      "already initialized",
    );
  });

  it("routes stable worker errors to the matching search", async () => {
    const worker = new FakeWorker();
    const client = new BrowserSolverWorkerClient(() => worker);
    const initialization = client.initialize({});
    ready(worker);
    await initialization;

    const search = client.search(REQUEST, { searchId: "bad" });
    await Promise.resolve();
    worker.emit({
      type: "error",
      code: "search-failed",
      message: "Browser solver search failed",
      search_id: "bad",
    });

    await expect(search).rejects.toThrow("Browser solver search failed");
  });

  it("terminates and recreates the worker for effective synchronous cancel", async () => {
    const workers: FakeWorker[] = [];
    let clock = 10;
    const client = new BrowserSolverWorkerClient(
      () => {
        const worker = new FakeWorker();
        workers.push(worker);
        return worker;
      },
      () => clock,
    );
    const initialization = client.initialize({ fixture: true });
    const firstWorker = workers[0];
    expect(firstWorker).toBeDefined();
    ready(firstWorker!);
    await initialization;

    const search = client.search(REQUEST, { searchId: "cancel-me" });
    await Promise.resolve();
    clock = 16.5;
    expect(client.cancel("other")).toBe(false);
    expect(client.cancel("cancel-me")).toBe(true);

    await expect(search).resolves.toEqual({
      status: "cancelled",
      candidate: null,
      selected_variant_ids: [],
      preference_score: null,
      decoration_count: null,
      elapsed_ms: 6.5,
      visited_nodes: 0,
      pruned_nodes: 0,
      complete_equipment_selections: 0,
    });
    expect(firstWorker!.posted.at(-1)).toEqual({
      type: "cancel",
      search_id: "cancel-me",
    });
    expect(firstWorker!.terminated).toBe(true);

    const secondWorker = workers[1];
    expect(secondWorker?.posted).toEqual([
      { type: "init", catalog: { fixture: true } },
    ]);
    ready(secondWorker!);
    const next = client.search(REQUEST, { searchId: "next" });
    await Promise.resolve();
    secondWorker!.emit({
      type: "result",
      search_id: "next",
      result: result(),
    });
    await expect(next).resolves.toEqual(result());
  });

  it("ignores stale results from a terminated worker", async () => {
    const workers: FakeWorker[] = [];
    const client = new BrowserSolverWorkerClient(() => {
      const worker = new FakeWorker();
      workers.push(worker);
      return worker;
    });
    const initialization = client.initialize({});
    ready(workers[0]!);
    await initialization;

    const cancelled = client.search(REQUEST, { searchId: "old" });
    await Promise.resolve();
    client.cancel("old");
    await cancelled;
    workers[0]!.emit({
      type: "result",
      search_id: "old",
      result: result(),
    });

    ready(workers[1]!);
    const current = client.search(REQUEST, { searchId: "current" });
    await Promise.resolve();
    workers[1]!.emit({
      type: "result",
      search_id: "current",
      result: result(),
    });
    await expect(current).resolves.toEqual(result());
  });

  it("rejects concurrent searches and fails pending work on worker error", async () => {
    const worker = new FakeWorker();
    const client = new BrowserSolverWorkerClient(() => worker);
    const initialization = client.initialize({});
    ready(worker);
    await initialization;

    const first = client.search(REQUEST, { searchId: "first" });
    await Promise.resolve();
    await expect(
      client.search(REQUEST, { searchId: "second" }),
    ).rejects.toThrow("already active");
    worker.fail();
    await expect(first).rejects.toThrow("encountered an error");
  });

  it("disposes idempotently and rejects pending work", async () => {
    const worker = new FakeWorker();
    const client = new BrowserSolverWorkerClient(() => worker);
    const initialization = client.initialize({});
    ready(worker);
    await initialization;
    const search = client.search(REQUEST);
    await Promise.resolve();

    client.dispose();
    client.dispose();

    expect(worker.terminated).toBe(true);
    await expect(search).rejects.toThrow("was disposed");
    await expect(client.search(REQUEST)).rejects.toThrow("was disposed");
  });
});
