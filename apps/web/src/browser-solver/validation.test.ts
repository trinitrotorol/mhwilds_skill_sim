import { describe, expect, it } from "vitest";

import { decodeBrowserSearchCatalog } from "./catalog";
import { solveBrowserRankedSearch } from "./solver";
import { makeTestCatalog } from "./test-catalog";
import {
  BrowserSolverValidationError,
  validateBrowserSolverResult,
  validateRankedBuildCandidate,
} from "./validation";

function validBuild() {
  const catalog = decodeBrowserSearchCatalog(makeTestCatalog());
  const request = {
    requirements: [{ skill_id: "skill:attack", min_level: 2 }],
    preferences: [{ skill_id: "skill:affinity", target_level: 1 }],
    max_results: 1,
  } as const;
  const result = solveBrowserRankedSearch(catalog, request);
  if (result.candidate === null) {
    throw new Error("test setup did not find a candidate");
  }
  return { catalog, request, result };
}

describe("browser solver independent validation", () => {
  it("validates full candidate shape, skill levels, score, and count", () => {
    const { catalog, request, result } = validBuild();

    const summary = validateRankedBuildCandidate(
      catalog,
      request,
      result.candidate!,
      result.selected_variant_ids,
    );

    expect(summary).toEqual({
      preference_score: 1,
      decoration_count: 1,
      skill_levels: [
        { skill_id: "skill:attack", level: 2 },
        { skill_id: "skill:affinity", level: 1 },
      ],
    });
    expect(() =>
      validateBrowserSolverResult(catalog, request, result),
    ).not.toThrow();
  });

  it("rejects selected variant IDs with a missing or wrong part", () => {
    const { catalog, request, result } = validBuild();
    const missing = structuredClone(result);
    missing.selected_variant_ids.pop();
    expect(() =>
      validateBrowserSolverResult(catalog, request, missing),
    ).toThrow("$.selected_variant_ids");

    const wrongPart = structuredClone(result);
    wrongPart.selected_variant_ids[1] = 0;
    expect(() =>
      validateBrowserSolverResult(catalog, request, wrongPart),
    ).toThrow("expected head equipment");
  });

  it("rejects equipment response data that does not match its variant", () => {
    const { catalog, request, result } = validBuild();
    const changed = structuredClone(result);
    changed.candidate!.equipment[0]!.display_name = "Forged response";

    expect(() =>
      validateBrowserSolverResult(catalog, request, changed),
    ).toThrow("$.candidate.equipment");
  });

  it("independently rejects a candidate outside the weapon-kind filter", () => {
    const catalog = decodeBrowserSearchCatalog(
      makeTestCatalog({
        equipment: {
          weapon: [
            {
              equipment_id: "equipment:great-sword",
              weapon_kind: "great-sword",
            },
            {
              equipment_id: "equipment:bow",
              weapon_kind: "bow",
            },
          ],
        },
      }),
    );
    const bowRequest = {
      requirements: [],
      preferences: [],
      max_results: 1,
      weapon_kind: "bow",
    } as const;
    const bowResult = solveBrowserRankedSearch(catalog, bowRequest);

    expect(() =>
      validateBrowserSolverResult(
        catalog,
        { ...bowRequest, weapon_kind: "great-sword" },
        bowResult,
      ),
    ).toThrow("$.candidate.equipment[0].weapon_kind");
  });

  it("rejects invalid slot kind, level, and double slot use", () => {
    const { catalog, request, result } = validBuild();
    const incompatible = structuredClone(result);
    incompatible.candidate!.placements[0]!.equipment_id =
      "equipment:weapon";
    expect(() =>
      validateBrowserSolverResult(catalog, request, incompatible),
    ).toThrow("incompatible");

    const duplicated = structuredClone(result);
    duplicated.candidate!.placements.push(
      structuredClone(duplicated.candidate!.placements[0]!),
    );
    expect(() =>
      validateBrowserSolverResult(catalog, request, duplicated),
    ).toThrow("more than once");
  });

  it("rejects wrong full levels, preference score, and decoration count", () => {
    const { catalog, request, result } = validBuild();
    const levels = structuredClone(result);
    levels.candidate!.skill_levels[0]!.level += 1;
    expect(() =>
      validateBrowserSolverResult(catalog, request, levels),
    ).toThrow("$.candidate.skill_levels");

    const candidateScore = structuredClone(result);
    candidateScore.candidate!.preference_score += 1;
    expect(() =>
      validateBrowserSolverResult(catalog, request, candidateScore),
    ).toThrow("$.candidate.preference_score");

    const resultScore = structuredClone(result);
    resultScore.preference_score! += 1;
    expect(() =>
      validateBrowserSolverResult(catalog, request, resultScore),
    ).toThrow("$.preference_score");

    const count = structuredClone(result);
    count.decoration_count! += 1;
    expect(() =>
      validateBrowserSolverResult(catalog, request, count),
    ).toThrow("$.decoration_count");
  });

  it("rejects candidate/status/null consistency errors", () => {
    const { catalog, request, result } = validBuild();
    const infeasibleWithCandidate = structuredClone(result);
    infeasibleWithCandidate.status = "infeasible";
    expect(() =>
      validateBrowserSolverResult(
        catalog,
        request,
        infeasibleWithCandidate,
      ),
    ).toThrow("infeasible status cannot include a candidate");

    const optimalWithoutCandidate = structuredClone(result);
    optimalWithoutCandidate.candidate = null;
    optimalWithoutCandidate.selected_variant_ids = [];
    optimalWithoutCandidate.preference_score = null;
    optimalWithoutCandidate.decoration_count = null;
    expect(() =>
      validateBrowserSolverResult(
        catalog,
        request,
        optimalWithoutCandidate,
      ),
    ).toThrow("optimal status requires a candidate");
  });

  it("accepts a valid partial incumbent on cancellation", () => {
    const catalog = decodeBrowserSearchCatalog(
      makeTestCatalog({
        equipment: {
          head: [
            {
              equipment_id: "equipment:head:first",
              slots: [["armor", 2]],
            },
            {
              equipment_id: "equipment:head:second",
              skills: [[0, 1]],
            },
          ],
        },
      }),
    );
    const request = {
      requirements: [],
      preferences: [{ skill_id: "skill:attack", target_level: 10 }],
      max_results: 1,
    } as const;
    let checks = 0;
    const result = solveBrowserRankedSearch(catalog, request, {
      shouldCancel: () => ++checks >= 14,
    });

    expect(result.status).toBe("cancelled");
    expect(result.candidate).not.toBeNull();
    expect(() =>
      validateBrowserSolverResult(catalog, request, result),
    ).not.toThrow();
  });

  it("uses stable path-bearing validation errors", () => {
    const { catalog, request, result } = validBuild();
    const bad = structuredClone(result);
    bad.visited_nodes = -1;

    expect(() => validateBrowserSolverResult(catalog, request, bad)).toThrow(
      BrowserSolverValidationError,
    );
    expect(() => validateBrowserSolverResult(catalog, request, bad)).toThrow(
      "$.visited_nodes",
    );
  });
});
