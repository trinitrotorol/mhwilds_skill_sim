/// <reference types="node" />

import { readFile as readFileFromDisk } from "node:fs/promises";

import {
  BROWSER_SOLVER_BENCHMARK_CATALOG_URL,
  BROWSER_SOLVER_BENCHMARK_ORACLE_URL,
} from "./benchmark";

interface BenchmarkMiddlewareRequest {
  readonly method?: string;
  readonly url?: string;
}

interface BenchmarkMiddlewareResponse {
  statusCode: number;
  setHeader(name: string, value: string): void;
  end(body?: string | Uint8Array): void;
}

type BenchmarkMiddlewareNext = (error?: unknown) => void;
type ReadFile = (path: string) => Promise<Uint8Array>;

export interface BrowserSolverBenchmarkMiddlewareOptions {
  readonly catalogPath: string;
  readonly oraclePath: string;
  readonly readFile?: ReadFile;
}

export const BROWSER_SOLVER_BENCHMARK_DOCUMENT_PATH =
  "/solver-benchmark.html";

export const BROWSER_SOLVER_ISOLATION_HEADERS = Object.freeze({
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "require-corp",
  "Permissions-Policy": "cross-origin-isolated=(self)",
  "Cache-Control": "no-store",
});

export type BrowserSolverBenchmarkMiddleware = (
  request: BenchmarkMiddlewareRequest,
  response: BenchmarkMiddlewareResponse,
  next: BenchmarkMiddlewareNext,
) => void;

function isMissingFile(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    error.code === "ENOENT"
  );
}

function setJsonHeaders(response: BenchmarkMiddlewareResponse): void {
  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "no-store");
}

export function createBrowserSolverBenchmarkMiddleware(
  options: BrowserSolverBenchmarkMiddlewareOptions,
): BrowserSolverBenchmarkMiddleware {
  const paths = new Map<string, string>([
    [BROWSER_SOLVER_BENCHMARK_CATALOG_URL, options.catalogPath],
    [BROWSER_SOLVER_BENCHMARK_ORACLE_URL, options.oraclePath],
  ]);
  const readFile = options.readFile ?? readFileFromDisk;

  return (request, response, next): void => {
    if (request.method !== "GET" || request.url === undefined) {
      next();
      return;
    }
    const queryStart = request.url.indexOf("?");
    const pathname =
      queryStart === -1 ? request.url : request.url.slice(0, queryStart);
    if (pathname === BROWSER_SOLVER_BENCHMARK_DOCUMENT_PATH) {
      for (const [name, value] of Object.entries(
        BROWSER_SOLVER_ISOLATION_HEADERS,
      )) {
        response.setHeader(name, value);
      }
      next();
      return;
    }
    if (pathname === "/src/browser-solver/worker.ts") {
      response.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
      response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
      response.setHeader("Cache-Control", "no-store");
      next();
      return;
    }
    const path = paths.get(request.url);
    if (path === undefined) {
      next();
      return;
    }
    void readFile(path)
      .then((contents) => {
        response.statusCode = 200;
        setJsonHeaders(response);
        response.end(contents);
      })
      .catch((error: unknown) => {
        if (isMissingFile(error)) {
          response.statusCode = 404;
          setJsonHeaders(response);
          response.end('{"error":"benchmark artifact not found"}\n');
          return;
        }
        next(error);
      });
  };
}
