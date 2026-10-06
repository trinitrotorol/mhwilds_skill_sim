import { describe, expect, it } from "vitest";
import { decodeBrowserSearchCatalog } from "./catalog";
import catalogJson from "./fixtures/tiny-browser-catalog.json";
import oracle from "./fixtures/inventory-oracle.json";
import { solveBrowserRankedSearch } from "./solver";
import { decodeBrowserRankedSearchRequest, validateBrowserSolverResult } from "./validation";

describe("shared CP-SAT/browser inventory top-K oracle", () => {
  it.each(oracle.cases)("matches all equipment ranks and objectives for $name", (testCase) => {
    const catalog = decodeBrowserSearchCatalog(catalogJson);
    const request = decodeBrowserRankedSearchRequest(testCase.request);
    const result = solveBrowserRankedSearch(catalog, request);
    expect(result.status).toBe(testCase.expected.length ? "optimal" : "infeasible");
    expect(result.exhausted).toBe(testCase.exhausted);
    expect(result.candidates?.map((candidate) => ({
      equipment_ids: candidate.equipment.map((item) => item.equipment_id),
      preference_score: candidate.preference_score,
      decoration_count: candidate.placements.length,
    }))).toEqual(testCase.expected);
    validateBrowserSolverResult(catalog, request, result);
  });
});
