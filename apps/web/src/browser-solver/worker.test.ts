import { describe, expect, it, vi } from "vitest";

import type { BrowserSolverWorkerResponse } from "./protocol";
import type {
  BrowserRankedSearchRequest,
  BrowserSolverOptions,
  BrowserSolverResult,
  DecodedBrowserCatalog,
} from "./types";
import { createBrowserSolverWorkerRuntime } from "./worker";

const REQUEST: BrowserRankedSearchRequest = Object.freeze({
  requirements: Object.freeze([]),
  preferences: Object.freeze([]),
  max_results: 1,
});

const CATALOG = {
  source_catalog: { sha256: "a".repeat(64) },
} as DecodedBrowserCatalog;

function result(
  status: BrowserSolverResult["status"] = "infeasible",
): BrowserSolverResult {
  return {
    status,
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

function initMessage(): { readonly type: "init"; readonly catalog: unknown } {
  return { type: "init", catalog: { fixture: true } };
}

function searchMessage(searchId = "search-1") {
  return {
    type: "search",
    search_id: searchId,
    request: REQUEST,
    timeout_ms: 10_000,
  } as const;
}

describe("browser solver worker runtime", () => {
  it("initializes once and reports the source hash", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    const decodeCatalog = vi.fn(() => CATALOG);
    const runtime = createBrowserSolverWorkerRuntime(
      (response) => responses.push(response),
      { decodeCatalog },
    );

    await runtime.handleMessage(initMessage());
    await runtime.handleMessage(initMessage());

    expect(decodeCatalog).toHaveBeenCalledTimes(1);
    expect(responses).toEqual([
      {
        type: "ready",
        source_catalog_sha256: "a".repeat(64),
      },
      {
        type: "error",
        code: "already-initialized",
        message: "Browser solver worker is already initialized",
      },
    ]);
  });

  it("rejects search before initialization", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    const runtime = createBrowserSolverWorkerRuntime((response) => {
      responses.push(response);
    });

    await runtime.handleMessage(searchMessage());

    expect(responses).toEqual([
      {
        type: "error",
        code: "not-initialized",
        message: "Browser solver worker is not initialized",
        search_id: "search-1",
      },
    ]);
  });

  it("runs, validates, and returns a search result with progress", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    const expected = result();
    const validateResult = vi.fn();
    const solve = vi.fn(
      (
        _catalog: DecodedBrowserCatalog,
        _request: BrowserRankedSearchRequest,
        options?: BrowserSolverOptions,
      ) => {
        options?.onProgress?.({
          elapsed_ms: 0.5,
          visited_nodes: 1,
          pruned_nodes: 0,
          complete_equipment_selections: 0,
          preference_score: null,
          decoration_count: null,
        });
        return expected;
      },
    );
    const runtime = createBrowserSolverWorkerRuntime(
      (response) => responses.push(response),
      {
        decodeCatalog: () => CATALOG,
        solve,
        validateResult,
        yieldBeforeSearch: () => Promise.resolve(),
      },
    );

    await runtime.handleMessage(initMessage());
    await runtime.handleMessage(searchMessage());

    expect(solve).toHaveBeenCalledWith(
      CATALOG,
      REQUEST,
      expect.objectContaining({ timeoutMs: 10_000 }),
    );
    expect(validateResult).toHaveBeenCalledWith(CATALOG, REQUEST, expected);
    expect(responses.slice(1)).toEqual([
      {
        type: "progress",
        search_id: "search-1",
        progress: {
          elapsed_ms: 0.5,
          visited_nodes: 1,
          pruned_nodes: 0,
          complete_equipment_selections: 0,
          preference_score: null,
          decoration_count: null,
        },
      },
      { type: "result", search_id: "search-1", result: expected },
    ]);
  });

  it("returns and validates a stable timed-out result", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    const expected = result("timed-out");
    const validateResult = vi.fn();
    const runtime = createBrowserSolverWorkerRuntime(
      (response) => responses.push(response),
      {
        decodeCatalog: () => CATALOG,
        solve: () => expected,
        validateResult,
        yieldBeforeSearch: () => Promise.resolve(),
      },
    );

    await runtime.handleMessage(initMessage());
    await runtime.handleMessage(searchMessage("timeout"));

    expect(validateResult).toHaveBeenCalledWith(CATALOG, REQUEST, expected);
    expect(responses).toContainEqual({
      type: "result",
      search_id: "timeout",
      result: expected,
    });
  });

  it("rejects a duplicate active search ID", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    let release!: () => void;
    const blocked = new Promise<void>((resolve) => {
      release = resolve;
    });
    const runtime = createBrowserSolverWorkerRuntime(
      (response) => responses.push(response),
      {
        decodeCatalog: () => CATALOG,
        solve: async () => {
          await blocked;
          return result();
        },
        validateResult: () => undefined,
        yieldBeforeSearch: () => Promise.resolve(),
      },
    );
    await runtime.handleMessage(initMessage());

    const first = runtime.handleMessage(searchMessage("same"));
    await Promise.resolve();
    await runtime.handleMessage(searchMessage("same"));
    release();
    await first;

    expect(responses).toContainEqual({
      type: "error",
      code: "duplicate-search-id",
      message: "Browser solver search ID is already active",
      search_id: "same",
    });
  });

  it("cancels only the matching active search", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    let release!: () => void;
    const blocked = new Promise<void>((resolve) => {
      release = resolve;
    });
    const runtime = createBrowserSolverWorkerRuntime(
      (response) => responses.push(response),
      {
        decodeCatalog: () => CATALOG,
        solve: async (
          _catalog,
          _request,
          options,
        ): Promise<BrowserSolverResult> => {
          await blocked;
          return result(options?.shouldCancel?.() ? "cancelled" : "optimal");
        },
        validateResult: () => undefined,
        yieldBeforeSearch: () => Promise.resolve(),
      },
    );
    await runtime.handleMessage(initMessage());

    const active = runtime.handleMessage(searchMessage("active"));
    await Promise.resolve();
    await runtime.handleMessage({ type: "cancel", search_id: "other" });
    await runtime.handleMessage({ type: "cancel", search_id: "active" });
    release();
    await active;

    expect(responses).toContainEqual({
      type: "error",
      code: "unknown-search-id",
      message: "Browser solver search ID is not active",
      search_id: "other",
    });
    expect(responses).toContainEqual({
      type: "result",
      search_id: "active",
      result: result("cancelled"),
    });
  });

  it("sanitizes thrown errors and remains reusable", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    const solve = vi
      .fn()
      .mockImplementationOnce(() => {
        throw new Error("secret detail\nsecret stack");
      })
      .mockImplementationOnce(() => result());
    const runtime = createBrowserSolverWorkerRuntime(
      (response) => responses.push(response),
      {
        decodeCatalog: () => CATALOG,
        solve,
        validateResult: () => undefined,
        yieldBeforeSearch: () => Promise.resolve(),
      },
    );
    await runtime.handleMessage(initMessage());

    await runtime.handleMessage(searchMessage("first"));
    await runtime.handleMessage(searchMessage("second"));

    const serialized = JSON.stringify(responses);
    expect(serialized).not.toContain("secret");
    expect(responses).toContainEqual({
      type: "error",
      code: "search-failed",
      message: "Browser solver search failed",
      search_id: "first",
    });
    expect(responses).toContainEqual({
      type: "result",
      search_id: "second",
      result: result(),
    });
  });

  it("rejects malformed messages with stable errors", async () => {
    const responses: BrowserSolverWorkerResponse[] = [];
    const runtime = createBrowserSolverWorkerRuntime((response) => {
      responses.push(response);
    });

    await runtime.handleMessage(null);
    await runtime.handleMessage({ type: "unknown", stack: "secret" });

    expect(responses).toEqual([
      {
        type: "error",
        code: "invalid-message",
        message: "Invalid browser solver worker message",
      },
      {
        type: "error",
        code: "invalid-message",
        message: "Invalid browser solver worker message",
      },
    ]);
  });
});
