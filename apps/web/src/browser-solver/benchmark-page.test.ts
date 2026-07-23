/// <reference types="node" />

import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("local browser solver benchmark page", () => {
  it("contains the local-only banner and Worker benchmark entry point", async () => {
    const [html, source] = await Promise.all([
      readFile(resolve(process.cwd(), "solver-benchmark.html"), "utf8"),
      readFile(
        resolve(process.cwd(), "src/browser-solver/benchmark-page.ts"),
        "utf8",
      ),
    ]);

    expect(html).toContain("Browser Solver Feasibility Benchmark");
    expect(html).toContain("Local development only");
    expect(html).toContain('id="benchmark-report-json" hidden');
    expect(html).toContain("./src/browser-solver/benchmark-page.ts");
    expect(html).not.toMatch(/https?:\/\//u);
    expect(source).toMatch(
      /latestReport = null;\s+reportJsonElement\.textContent = "";\s+delete window\.__MHWILDS_BROWSER_SOLVER_BENCHMARK__/u,
    );
    expect(source).toContain("__MHWILDS_BROWSER_SOLVER_CERTIFICATION__");
    expect(source).toContain("version: 1 as const");
  });

  it("is not linked from the production HTML or React application", async () => {
    const [productionHtml, applicationSource] = await Promise.all([
      readFile(resolve(process.cwd(), "index.html"), "utf8"),
      readFile(resolve(process.cwd(), "src/App.tsx"), "utf8"),
    ]);

    expect(productionHtml).not.toContain("solver-benchmark");
    expect(applicationSource).not.toContain("solver-benchmark");
    expect(applicationSource).not.toContain("browser-solver");
  });
});
