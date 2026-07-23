/// <reference types="node" />

import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, resolve } from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

import {
  runBrowserSolverBenchmark,
  type BrowserBenchmarkReport,
} from "./benchmark";
import { decodeBrowserSearchCatalog } from "./catalog";
import { solveBrowserRankedSearch } from "./solver";
import { validateBrowserSolverResult } from "./validation";

export interface BrowserBenchmarkCliArguments {
  readonly catalog: string;
  readonly oracle: string;
  readonly output: string;
  readonly timeoutMs: number;
  readonly repeats: number;
}

interface BenchmarkCliIo {
  readonly stdout: (value: string) => void;
  readonly stderr: (value: string) => void;
}

const ARGUMENTS = new Set([
  "--catalog",
  "--oracle",
  "--output",
  "--timeout-ms",
  "--repeats",
]);

function positiveInteger(value: string, name: string): number {
  if (!/^[1-9][0-9]*$/u.test(value)) {
    throw new TypeError(`${name} must be a positive integer`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new TypeError(`${name} exceeds the safe integer range`);
  }
  return parsed;
}

export function parseBrowserBenchmarkCliArguments(
  argv: readonly string[],
): BrowserBenchmarkCliArguments {
  const values = new Map<string, string>();
  for (let index = 0; index < argv.length; index += 2) {
    const name = argv[index];
    const value = argv[index + 1];
    if (
      name === undefined ||
      value === undefined ||
      !ARGUMENTS.has(name) ||
      value.startsWith("--")
    ) {
      throw new TypeError("invalid browser solver benchmark arguments");
    }
    if (values.has(name)) {
      throw new TypeError(`duplicate browser solver benchmark argument ${name}`);
    }
    values.set(name, value);
  }
  if (values.size !== ARGUMENTS.size) {
    throw new TypeError(
      "required arguments: --catalog --oracle --output --timeout-ms --repeats",
    );
  }
  return Object.freeze({
    catalog: values.get("--catalog")!,
    oracle: values.get("--oracle")!,
    output: values.get("--output")!,
    timeoutMs: positiveInteger(values.get("--timeout-ms")!, "--timeout-ms"),
    repeats: positiveInteger(values.get("--repeats")!, "--repeats"),
  });
}

async function readJson(path: string): Promise<unknown> {
  return JSON.parse(await readFile(path, "utf8")) as unknown;
}

function summary(report: BrowserBenchmarkReport, output: string) {
  return {
    format_version: report.format_version,
    runtime: report.runtime,
    source_catalog_sha256: report.source_catalog_sha256,
    case_count: report.cases.length,
    repeats: report.repeats,
    parity_failure_count: report.cases.filter(
      ({ parity }) => parity === false,
    ).length,
    nondeterministic_case_count: report.cases.filter(
      ({ deterministic }) => !deterministic,
    ).length,
    timed_out_count: report.cases.filter(
      ({ result }) => result.status === "timed-out",
    ).length,
    output,
  };
}

export async function executeBrowserBenchmarkCli(
  argv: readonly string[],
  io: BenchmarkCliIo = {
    stdout: (value) => process.stdout.write(value),
    stderr: (value) => process.stderr.write(value),
  },
  invocationDirectory = process.env.INIT_CWD ?? process.cwd(),
): Promise<number> {
  try {
    const args = parseBrowserBenchmarkCliArguments(argv);
    const catalogPath = resolveCliPath(args.catalog, invocationDirectory);
    const oraclePath = resolveCliPath(args.oracle, invocationDirectory);
    const outputPath = resolveCliPath(args.output, invocationDirectory);
    const catalogValue = await readJson(catalogPath);
    const oracleValue = await readJson(oraclePath);
    const catalog = decodeBrowserSearchCatalog(catalogValue);
    const report = await runBrowserSolverBenchmark({
      sourceCatalogSha256: catalog.source_catalog.sha256,
      oracleValue,
      runtime: "node",
      timeoutMs: args.timeoutMs,
      repeats: args.repeats,
      runCase: (request) =>
        solveBrowserRankedSearch(catalog, request, {
          timeoutMs: args.timeoutMs,
        }),
      validateResult: (request, result) => {
        validateBrowserSolverResult(catalog, request, result);
      },
    });
    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(outputPath, `${JSON.stringify(report)}\n`, "utf8");
    const reportSummary = summary(report, args.output);
    io.stdout(`${JSON.stringify(reportSummary)}\n`);
    return reportSummary.parity_failure_count === 0 &&
      reportSummary.nondeterministic_case_count === 0
      ? 0
      : 2;
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "unknown benchmark error";
    io.stderr(`browser solver benchmark failed: ${message}\n`);
    return 1;
  }
}

function resolveCliPath(path: string, invocationDirectory: string): string {
  return isAbsolute(path) ? path : resolve(invocationDirectory, path);
}

const entryPath = process.argv[1];
if (
  entryPath !== undefined &&
  import.meta.url === pathToFileURL(resolve(entryPath)).href
) {
  process.exitCode = await executeBrowserBenchmarkCli(process.argv.slice(2));
}
