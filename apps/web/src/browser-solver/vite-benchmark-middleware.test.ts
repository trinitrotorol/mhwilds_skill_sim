/// <reference types="node" />

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import type { UserConfig } from "vite";
import { describe, expect, it, vi } from "vitest";

import viteConfig, {
  LOCAL_API_PROXY_PATTERN,
  rewriteLocalApiPath,
} from "../../vite.config";
import {
  BROWSER_SOLVER_BENCHMARK_CATALOG_URL,
  BROWSER_SOLVER_BENCHMARK_ORACLE_URL,
} from "./benchmark";
import { createBrowserSolverBenchmarkMiddleware } from "./vite-benchmark-middleware";
import {
  BROWSER_SOLVER_BENCHMARK_DOCUMENT_PATH,
  BROWSER_SOLVER_ISOLATION_HEADERS,
} from "./vite-benchmark-middleware";

interface CapturedResponse {
  statusCode: number;
  readonly headers: Record<string, string>;
  body: string | Uint8Array | undefined;
  setHeader(name: string, value: string): void;
  end(body?: string | Uint8Array): void;
}

function response(): CapturedResponse {
  return {
    statusCode: 0,
    headers: {},
    body: undefined,
    setHeader(name, value) {
      this.headers[name] = value;
    },
    end(body) {
      this.body = body;
    },
  };
}

async function flushPromises(): Promise<void> {
  await Promise.resolve();
  await Promise.resolve();
}

describe("browser solver benchmark Vite middleware", () => {
  it.each([
    [BROWSER_SOLVER_BENCHMARK_CATALOG_URL, "catalog-path", "catalog"],
    [BROWSER_SOLVER_BENCHMARK_ORACLE_URL, "oracle-path", "oracle"],
  ])("serves only the mapped JSON artifact at %s", async (url, path, body) => {
    const read = vi.fn(async () => new TextEncoder().encode(body));
    const middleware = createBrowserSolverBenchmarkMiddleware({
      catalogPath: "catalog-path",
      oraclePath: "oracle-path",
      readFile: read,
    });
    const captured = response();
    const next = vi.fn();

    middleware({ method: "GET", url }, captured, next);
    await flushPromises();

    expect(read).toHaveBeenCalledWith(path);
    expect(next).not.toHaveBeenCalled();
    expect(captured.statusCode).toBe(200);
    expect(captured.headers).toEqual({
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    });
    expect(new TextDecoder().decode(captured.body as Uint8Array)).toBe(body);
  });

  it.each([
    "/__browser-solver-benchmark/catalog.json?download=1",
    "/__browser-solver-benchmark/../secret.json",
    "/__browser-solver-benchmark/oracle.json/extra",
    "/.build/browser-solver/browser-catalog.json",
    "/solver-benchmark-other.html",
  ])("passes through a non-exact URL: %s", (url) => {
    const read = vi.fn();
    const middleware = createBrowserSolverBenchmarkMiddleware({
      catalogPath: "catalog-path",
      oraclePath: "oracle-path",
      readFile: read,
    });
    const next = vi.fn();

    middleware({ method: "GET", url }, response(), next);

    expect(read).not.toHaveBeenCalled();
    expect(next).toHaveBeenCalledOnce();
  });

  it("adds isolation headers only to the exact benchmark document", () => {
    const middleware = createBrowserSolverBenchmarkMiddleware({
      catalogPath: "catalog-path",
      oraclePath: "oracle-path",
    });
    const captured = response();
    const next = vi.fn();
    middleware(
      { method: "GET", url: BROWSER_SOLVER_BENCHMARK_DOCUMENT_PATH },
      captured,
      next,
    );
    expect(captured.headers).toEqual(BROWSER_SOLVER_ISOLATION_HEADERS);
    expect(next).toHaveBeenCalledOnce();
  });

  it("does not serve the files for a non-GET request", () => {
    const read = vi.fn();
    const middleware = createBrowserSolverBenchmarkMiddleware({
      catalogPath: "catalog-path",
      oraclePath: "oracle-path",
      readFile: read,
    });
    const next = vi.fn();

    middleware(
      { method: "POST", url: BROWSER_SOLVER_BENCHMARK_CATALOG_URL },
      response(),
      next,
    );

    expect(read).not.toHaveBeenCalled();
    expect(next).toHaveBeenCalledOnce();
  });

  it("returns no-store JSON 404 when an artifact is absent", async () => {
    const missing = Object.assign(new Error("missing"), { code: "ENOENT" });
    const middleware = createBrowserSolverBenchmarkMiddleware({
      catalogPath: "catalog-path",
      oraclePath: "oracle-path",
      readFile: () => Promise.reject(missing),
    });
    const captured = response();
    const next = vi.fn();

    middleware(
      { method: "GET", url: BROWSER_SOLVER_BENCHMARK_CATALOG_URL },
      captured,
      next,
    );
    await flushPromises();

    expect(captured.statusCode).toBe(404);
    expect(captured.headers["Cache-Control"]).toBe("no-store");
    expect(captured.headers["Content-Type"]).toContain("application/json");
    expect(String(captured.body)).not.toContain("catalog-path");
    expect(next).not.toHaveBeenCalled();
  });

  it("passes unexpected filesystem errors to Vite", async () => {
    const failure = new Error("disk failure");
    const middleware = createBrowserSolverBenchmarkMiddleware({
      catalogPath: "catalog-path",
      oraclePath: "oracle-path",
      readFile: () => Promise.reject(failure),
    });
    const next = vi.fn();

    middleware(
      { method: "GET", url: BROWSER_SOLVER_BENCHMARK_CATALOG_URL },
      response(),
      next,
    );
    await flushPromises();

    expect(next).toHaveBeenCalledWith(failure);
  });

  it("keeps production build and existing API proxy boundaries unchanged", async () => {
    const config = viteConfig as UserConfig;
    expect(config.base).toBe("/game-guide/mhwilds-skill-sim/");
    expect(config.build).toEqual({
      outDir: "dist/game-guide/mhwilds-skill-sim",
      emptyOutDir: true,
      sourcemap: false,
    });
    expect(config.server?.proxy).toEqual({
      [LOCAL_API_PROXY_PATTERN]: {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: rewriteLocalApiPath,
      },
    });
    const configSource = await readFile(
      resolve(process.cwd(), "vite.config.ts"),
      "utf8",
    );
    expect(configSource).not.toContain("solver-benchmark.html");
    expect(configSource).not.toContain("rollupOptions");
  });
});
