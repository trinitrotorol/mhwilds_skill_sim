import { decodeBrowserSearchCatalog } from "./catalog";
import type {
  BrowserSolverWorkerErrorCode,
  BrowserSolverWorkerErrorResponse,
  BrowserSolverWorkerResponse,
} from "./protocol";
import { solveBrowserRankedSearch } from "./solver";
import type {
  BrowserRankedSearchRequest,
  BrowserSolverOptions,
  BrowserSolverResult,
  DecodedBrowserCatalog,
} from "./types";
import { validateBrowserSolverResult } from "./validation";

const ERROR_MESSAGES: Readonly<Record<BrowserSolverWorkerErrorCode, string>> =
  Object.freeze({
    "invalid-message": "Invalid browser solver worker message",
    "not-initialized": "Browser solver worker is not initialized",
    "already-initialized": "Browser solver worker is already initialized",
    "invalid-catalog": "Invalid browser solver catalog",
    "duplicate-search-id": "Browser solver search ID is already active",
    "unknown-search-id": "Browser solver search ID is not active",
    "search-failed": "Browser solver search failed",
  });

interface ActiveSearch {
  cancelled: boolean;
}

type CatalogDecoder = (value: unknown) => DecodedBrowserCatalog;
type Solver = (
  catalog: DecodedBrowserCatalog,
  request: BrowserRankedSearchRequest,
  options?: BrowserSolverOptions,
) => BrowserSolverResult | Promise<BrowserSolverResult>;
type ResultValidator = (
  catalog: DecodedBrowserCatalog,
  request: BrowserRankedSearchRequest,
  result: BrowserSolverResult,
) => void;

export interface BrowserSolverWorkerDependencies {
  readonly decodeCatalog?: CatalogDecoder;
  readonly solve?: Solver;
  readonly validateResult?: ResultValidator;
  readonly yieldBeforeSearch?: () => Promise<void>;
}

export type BrowserSolverWorkerPostMessage = (
  response: BrowserSolverWorkerResponse,
) => void;

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function hasExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
): boolean {
  const keys = Object.keys(value);
  return (
    keys.length === expected.length &&
    expected.every((key) => Object.hasOwn(value, key))
  );
}

function validSearchId(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value.trim() === value
  );
}

function validTimeout(value: unknown): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= 0
  );
}

function defaultYieldBeforeSearch(): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, 0);
  });
}

function errorResponse(
  code: BrowserSolverWorkerErrorCode,
  searchId?: string,
): BrowserSolverWorkerErrorResponse {
  const response: BrowserSolverWorkerErrorResponse = {
    type: "error",
    code,
    message: ERROR_MESSAGES[code],
  };
  return searchId === undefined
    ? response
    : { ...response, search_id: searchId };
}

export interface BrowserSolverWorkerRuntime {
  handleMessage(value: unknown): Promise<void>;
}

export function createBrowserSolverWorkerRuntime(
  postMessage: BrowserSolverWorkerPostMessage,
  dependencies: BrowserSolverWorkerDependencies = {},
): BrowserSolverWorkerRuntime {
  const decodeCatalog = dependencies.decodeCatalog ?? decodeBrowserSearchCatalog;
  const solve = dependencies.solve ?? solveBrowserRankedSearch;
  const validateResult =
    dependencies.validateResult ?? validateBrowserSolverResult;
  const yieldBeforeSearch =
    dependencies.yieldBeforeSearch ?? defaultYieldBeforeSearch;
  const activeSearches = new Map<string, ActiveSearch>();
  let catalog: DecodedBrowserCatalog | null = null;
  let initializationAttempted = false;

  const handleInit = (message: Record<string, unknown>): void => {
    if (!hasExactKeys(message, ["type", "catalog"])) {
      postMessage(errorResponse("invalid-message"));
      return;
    }
    if (initializationAttempted) {
      postMessage(errorResponse("already-initialized"));
      return;
    }
    initializationAttempted = true;
    try {
      catalog = decodeCatalog(message.catalog);
    } catch {
      postMessage(errorResponse("invalid-catalog"));
      return;
    }
    postMessage({
      type: "ready",
      source_catalog_sha256: catalog.source_catalog.sha256,
    });
  };

  const handleSearch = async (
    message: Record<string, unknown>,
  ): Promise<void> => {
    const searchId = validSearchId(message.search_id)
      ? message.search_id
      : undefined;
    if (
      !hasExactKeys(message, [
        "type",
        "search_id",
        "request",
        "timeout_ms",
      ]) ||
      searchId === undefined ||
      !validTimeout(message.timeout_ms)
    ) {
      postMessage(errorResponse("invalid-message", searchId));
      return;
    }
    if (catalog === null) {
      postMessage(errorResponse("not-initialized", searchId));
      return;
    }
    if (activeSearches.has(searchId)) {
      postMessage(errorResponse("duplicate-search-id", searchId));
      return;
    }

    const active: ActiveSearch = { cancelled: false };
    activeSearches.set(searchId, active);
    await yieldBeforeSearch();
    if (activeSearches.get(searchId) !== active) {
      return;
    }

    try {
      const request = message.request as BrowserRankedSearchRequest;
      const initializedCatalog = catalog;
      const result = await solve(initializedCatalog, request, {
        timeoutMs: message.timeout_ms,
        shouldCancel: () => active.cancelled,
        onProgress: (progress) => {
          if (
            activeSearches.get(searchId) === active &&
            !active.cancelled
          ) {
            postMessage({
              type: "progress",
              search_id: searchId,
              progress,
            });
          }
        },
      });
      validateResult(initializedCatalog, request, result);
      if (activeSearches.get(searchId) === active) {
        postMessage({ type: "result", search_id: searchId, result });
      }
    } catch {
      if (activeSearches.get(searchId) === active) {
        postMessage(errorResponse("search-failed", searchId));
      }
    } finally {
      if (activeSearches.get(searchId) === active) {
        activeSearches.delete(searchId);
      }
    }
  };

  const handleCancel = (message: Record<string, unknown>): void => {
    const searchId = validSearchId(message.search_id)
      ? message.search_id
      : undefined;
    if (
      !hasExactKeys(message, ["type", "search_id"]) ||
      searchId === undefined
    ) {
      postMessage(errorResponse("invalid-message", searchId));
      return;
    }
    const active = activeSearches.get(searchId);
    if (active === undefined) {
      postMessage(errorResponse("unknown-search-id", searchId));
      return;
    }
    active.cancelled = true;
  };

  return Object.freeze({
    async handleMessage(value: unknown): Promise<void> {
      if (!isPlainObject(value) || typeof value.type !== "string") {
        postMessage(errorResponse("invalid-message"));
        return;
      }
      switch (value.type) {
        case "init":
          handleInit(value);
          return;
        case "search":
          await handleSearch(value);
          return;
        case "cancel":
          handleCancel(value);
          return;
        default:
          postMessage(errorResponse("invalid-message"));
      }
    },
  });
}

interface DedicatedWorkerScopeLike {
  readonly document?: unknown;
  postMessage(value: BrowserSolverWorkerResponse): void;
  addEventListener(
    type: "message",
    listener: (event: { readonly data: unknown }) => void,
  ): void;
}

const possibleWorkerScope =
  globalThis as unknown as Partial<DedicatedWorkerScopeLike>;

if (
  possibleWorkerScope.document === undefined &&
  typeof possibleWorkerScope.postMessage === "function" &&
  typeof possibleWorkerScope.addEventListener === "function"
) {
  const runtime = createBrowserSolverWorkerRuntime((response) => {
    possibleWorkerScope.postMessage?.(response);
  });
  possibleWorkerScope.addEventListener("message", (event) => {
    void runtime.handleMessage(event.data);
  });
}
