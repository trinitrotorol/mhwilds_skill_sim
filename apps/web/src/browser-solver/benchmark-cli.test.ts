/// <reference types="node" />

import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import {
  calculateMedian,
  runBrowserSolverBenchmark,
} from "./benchmark";
import {
  executeBrowserBenchmarkCli,
  parseBrowserBenchmarkCliArguments,
} from "./benchmark-cli";
import { decodeBrowserSearchCatalog } from "./catalog";
import { solveBrowserRankedSearch } from "./solver";
import { makeTestCatalog } from "./test-catalog";
import type {
  BrowserRankedSearchRequest,
  BrowserSolverResult,
} from "./types";

const REQUEST: BrowserRankedSearchRequest = {
  requirements: [],
  preferences: [],
  max_results: 1,
};

const temporaryDirectories: string[] = [];

afterEach(async () => {
  await Promise.all(
    temporaryDirectories.splice(0).map((path) =>
      rm(path, { recursive: true, force: true }),
    ),
  );
});

async function temporaryDirectory(): Promise<string> {
  const path = await mkdtemp(join(tmpdir(), "mhwilds-browser-benchmark-"));
  temporaryDirectories.push(path);
  return path;
}

function oracleFor(
  result: BrowserSolverResult,
  sourceCatalogSha256: string,
): Record<string, unknown> {
  return {
    format_version: 1,
    source_catalog_sha256: sourceCatalogSha256,
    timeout_seconds: 30,
    omitted_cases: [],
    cases: [
      {
        name: "empty",
        request: REQUEST,
        elapsed_seconds: 0,
        status: result.status,
        candidate_exists: result.candidate !== null,
        preference_score: result.preference_score,
        decoration_count: result.decoration_count,
        equipment_signature: null,
      },
    ],
  };
}

describe("browser solver benchmark CLI", () => {
  it("parses every exact argument once", () => {
    expect(
      parseBrowserBenchmarkCliArguments([
        "--catalog",
        "catalog.json",
        "--oracle",
        "oracle.json",
        "--output",
        "report.json",
        "--timeout-ms",
        "10000",
        "--repeats",
        "3",
      ]),
    ).toEqual({
      catalog: "catalog.json",
      oracle: "oracle.json",
      output: "report.json",
      timeoutMs: 10_000,
      repeats: 3,
    });
  });

  it.each([
    [[]],
    [["--catalog", "catalog.json"]],
    [["--unknown", "value"]],
    [["--repeats", "0"]],
    [["--repeats", "1.5"]],
    [["--catalog", "a", "--catalog", "b"]],
  ])("rejects invalid arguments %#", (argv) => {
    expect(() => parseBrowserBenchmarkCliArguments(argv)).toThrow();
  });

  it("calculates odd and even medians without changing the input", () => {
    const values = [9, 1, 4, 2];
    expect(calculateMedian(values)).toBe(3);
    expect(calculateMedian([7, 3, 5])).toBe(5);
    expect(values).toEqual([9, 1, 4, 2]);
  });

  it("writes the ordered report, repeats results, and prints a summary", async () => {
    const directory = await temporaryDirectory();
    const catalogPath = join(directory, "catalog.json");
    const oraclePath = join(directory, "oracle.json");
    const outputPath = join(directory, "nested", "report.json");
    const catalogValue = makeTestCatalog();
    const catalog = decodeBrowserSearchCatalog(catalogValue);
    const expected = solveBrowserRankedSearch(catalog, REQUEST);
    await writeFile(catalogPath, JSON.stringify(catalogValue), "utf8");
    await writeFile(
      oraclePath,
      JSON.stringify(oracleFor(expected, catalog.source_catalog.sha256)),
      "utf8",
    );
    const stdout: string[] = [];
    const stderr: string[] = [];

    const exitCode = await executeBrowserBenchmarkCli(
      [
        "--catalog",
        catalogPath,
        "--oracle",
        oraclePath,
        "--output",
        outputPath,
        "--timeout-ms",
        "10000",
        "--repeats",
        "3",
      ],
      {
        stdout: (value) => stdout.push(value),
        stderr: (value) => stderr.push(value),
      },
    );

    expect(exitCode).toBe(0);
    expect(stderr).toEqual([]);
    const report = JSON.parse(await readFile(outputPath, "utf8")) as Record<
      string,
      unknown
    >;
    expect(Object.keys(report)).toEqual([
      "format_version",
      "source_catalog_sha256",
      "runtime",
      "timeout_ms",
      "repeats",
      "cases",
    ]);
    expect(report.runtime).toBe("node");
    expect(report.repeats).toBe(3);
    expect(report.cases).toEqual([
      expect.objectContaining({
        name: "empty",
        request: REQUEST,
        result: expect.objectContaining({
          status: expected.status,
          candidate: expected.candidate,
          selected_variant_ids: expected.selected_variant_ids,
          preference_score: expected.preference_score,
          decoration_count: expected.decoration_count,
          visited_nodes: expected.visited_nodes,
          pruned_nodes: expected.pruned_nodes,
          complete_equipment_selections:
            expected.complete_equipment_selections,
        }),
        timings_ms: {
          min: expect.any(Number),
          median: expect.any(Number),
          max: expect.any(Number),
        },
        deterministic: true,
        parity: true,
      }),
    ]);
    expect(JSON.parse(stdout[0]!)).toEqual(
      expect.objectContaining({
        case_count: 1,
        parity_failure_count: 0,
        nondeterministic_case_count: 0,
        output: outputPath,
      }),
    );
  });

  it("resolves npm --prefix relative paths from the invocation directory", async () => {
    const directory = await temporaryDirectory();
    const buildDirectory = join(directory, ".build", "browser-solver");
    const catalogPath = join(buildDirectory, "catalog.json");
    const oraclePath = join(buildDirectory, "oracle.json");
    const outputPath = join(buildDirectory, "report.json");
    const catalogValue = makeTestCatalog();
    const catalog = decodeBrowserSearchCatalog(catalogValue);
    const expected = solveBrowserRankedSearch(catalog, REQUEST);
    await mkdir(buildDirectory, { recursive: true });
    await writeFile(catalogPath, JSON.stringify(catalogValue), {
      encoding: "utf8",
      flag: "wx",
    });
    await writeFile(
      oraclePath,
      JSON.stringify(oracleFor(expected, catalog.source_catalog.sha256)),
      { encoding: "utf8", flag: "wx" },
    );

    const exitCode = await executeBrowserBenchmarkCli(
      [
        "--catalog",
        ".build/browser-solver/catalog.json",
        "--oracle",
        ".build/browser-solver/oracle.json",
        "--output",
        ".build/browser-solver/report.json",
        "--timeout-ms",
        "10000",
        "--repeats",
        "1",
      ],
      { stdout: () => undefined, stderr: () => undefined },
      directory,
    );

    expect(exitCode).toBe(0);
    await expect(readFile(outputPath, "utf8")).resolves.toContain(
      '"runtime":"node"',
    );
  });

  it("returns nonzero after writing a parity mismatch report", async () => {
    const directory = await temporaryDirectory();
    const catalogPath = join(directory, "catalog.json");
    const oraclePath = join(directory, "oracle.json");
    const outputPath = join(directory, "report.json");
    const catalogValue = makeTestCatalog();
    const catalog = decodeBrowserSearchCatalog(catalogValue);
    const expected = solveBrowserRankedSearch(catalog, REQUEST);
    const oracle = oracleFor(expected, catalog.source_catalog.sha256);
    const cases = oracle.cases as Array<Record<string, unknown>>;
    cases[0]!.preference_score = (expected.preference_score ?? 0) + 1;
    await writeFile(catalogPath, JSON.stringify(catalogValue), "utf8");
    await writeFile(oraclePath, JSON.stringify(oracle), "utf8");

    const exitCode = await executeBrowserBenchmarkCli(
      [
        "--catalog",
        catalogPath,
        "--oracle",
        oraclePath,
        "--output",
        outputPath,
        "--timeout-ms",
        "10000",
        "--repeats",
        "2",
      ],
      { stdout: () => undefined, stderr: () => undefined },
    );

    expect(exitCode).toBe(2);
    const report = JSON.parse(await readFile(outputPath, "utf8")) as {
      cases: Array<{ parity: boolean | null }>;
    };
    expect(report.cases[0]?.parity).toBe(false);
  });

  it("rejects a source hash mismatch and does not write output", async () => {
    const directory = await temporaryDirectory();
    const catalogPath = join(directory, "catalog.json");
    const oraclePath = join(directory, "oracle.json");
    const outputPath = join(directory, "report.json");
    const catalogValue = makeTestCatalog();
    const catalog = decodeBrowserSearchCatalog(catalogValue);
    const expected = solveBrowserRankedSearch(catalog, REQUEST);
    await writeFile(catalogPath, JSON.stringify(catalogValue), "utf8");
    await writeFile(
      oraclePath,
      JSON.stringify(oracleFor(expected, "f".repeat(64))),
      "utf8",
    );
    const stderr: string[] = [];

    const exitCode = await executeBrowserBenchmarkCli(
      [
        "--catalog",
        catalogPath,
        "--oracle",
        oraclePath,
        "--output",
        outputPath,
        "--timeout-ms",
        "10000",
        "--repeats",
        "1",
      ],
      { stdout: () => undefined, stderr: (value) => stderr.push(value) },
    );

    expect(exitCode).toBe(1);
    expect(stderr.join("")).toContain("hash does not match");
    await expect(readFile(outputPath)).rejects.toMatchObject({ code: "ENOENT" });
  });

  it("treats invalid browser candidates as execution failures", async () => {
    const invalidResult: BrowserSolverResult = {
      status: "optimal",
      candidate: null,
      selected_variant_ids: [],
      preference_score: null,
      decoration_count: null,
      elapsed_ms: 0,
      visited_nodes: 0,
      pruned_nodes: 0,
      complete_equipment_selections: 0,
    };
    const oracle = {
      ...oracleFor(invalidResult, "0".repeat(64)),
      cases: [
        {
          name: "empty",
          request: REQUEST,
          status: "infeasible",
          candidate_exists: false,
          preference_score: null,
          decoration_count: null,
        },
      ],
    };

    await expect(
      runBrowserSolverBenchmark({
        sourceCatalogSha256: "0".repeat(64),
        oracleValue: oracle,
        runtime: "node",
        timeoutMs: 10_000,
        repeats: 1,
        runCase: () => invalidResult,
        validateResult: () => {
          throw new Error("invalid browser candidate");
        },
      }),
    ).rejects.toThrow("invalid browser candidate");
  });

  it("uses no live network API", async () => {
    const source = await readFile(
      resolve(process.cwd(), "src/browser-solver/benchmark-cli.ts"),
      "utf8",
    );
    expect(source).not.toContain("fetch(");
    expect(source).not.toContain("http://");
    expect(source).not.toContain("https://");
  });
});
