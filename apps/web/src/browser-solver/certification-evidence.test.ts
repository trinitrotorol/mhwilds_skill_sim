import { describe, expect, it, vi } from "vitest";

import type {
  BrowserBenchmarkCaseReport,
  BrowserBenchmarkReport,
} from "./benchmark";
import { summarizeCertificationEvidence } from "./certification-evidence";
import type { BrowserSolverResult } from "./types";

function result(preferenceScore = 1): BrowserSolverResult {
  return {
    status: "optimal",
    candidate: {} as BrowserSolverResult["candidate"],
    selected_variant_ids: [1, 2, 3, 4, 5, 6],
    preference_score: preferenceScore,
    decoration_count: 0,
    elapsed_ms: 1,
    visited_nodes: 1,
    pruned_nodes: 0,
    complete_equipment_selections: 1,
  };
}

function caseReport(
  name: string,
  preferenceScore = 1,
  overrides: Partial<BrowserBenchmarkCaseReport> = {},
): BrowserBenchmarkCaseReport {
  return {
    name,
    request: { requirements: [], preferences: [], max_results: 1 },
    result: result(preferenceScore),
    timings_ms: { min: 1, median: 1, max: 1 },
    deterministic: true,
    parity: true,
    ...overrides,
  };
}

function report(...cases: BrowserBenchmarkCaseReport[]): BrowserBenchmarkReport {
  return {
    format_version: 1,
    source_catalog_sha256: "a".repeat(64),
    runtime: "browser",
    timeout_ms: 20_000,
    repeats: 1,
    cases,
  };
}

describe("certification benchmark evidence", () => {
  it("detects objective changes between outer suites in the same profile", () => {
    const counts = summarizeCertificationEvidence(
      [
        [
          report(caseReport("mixed-ranked", 1)),
          report(caseReport("mixed-ranked", 2)),
        ],
        [report(caseReport("mixed-ranked", 3))],
      ],
      [],
      () => undefined,
    );

    expect(counts.nondeterministicCases).toBe(1);
  });

  it("counts internal nondeterminism once per profile and case", () => {
    const counts = summarizeCertificationEvidence(
      [
        [
          report(
            caseReport("mixed-ranked", 1, { deterministic: false }),
            caseReport("other", 1),
          ),
        ],
      ],
      [],
      () => undefined,
    );
    expect(counts.nondeterministicCases).toBe(1);
  });

  it("validates every result and includes restart correctness evidence", () => {
    const invalid = caseReport("invalid");
    const restart = caseReport("mixed-ranked", 1, { parity: false });
    const validate = vi.fn((request, candidateResult) => {
      if (candidateResult === invalid.result) {
        throw new Error("invalid candidate");
      }
      expect(request.max_results).toBe(1);
    });
    const counts = summarizeCertificationEvidence(
      [[report(caseReport("valid"), invalid)]],
      [restart],
      validate,
    );

    expect(validate).toHaveBeenCalledTimes(3);
    expect(counts).toMatchObject({
      parityFailures: 1,
      invalidCandidates: 1,
      timeouts: 0,
    });
  });
});
