import { describe, expect, it } from "vitest";

import { decodeBrowserSearchCatalog } from "./catalog";
import { solveBrowserRankedSearch } from "./solver";
import { makeTestCatalog } from "./test-catalog";
import {
  BrowserSolverValidationError,
  equalJsonValue,
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
  it("accepts skill totals in Python contribution order and rejects duplicate or altered totals", () => {
    const { catalog, request, result } = validBuild();
    result.candidate!.skill_levels.reverse();
    expect(() => validateBrowserSolverResult(catalog, request, result)).not.toThrow();
    const duplicate = structuredClone(result);
    duplicate.candidate!.skill_levels.push({ ...duplicate.candidate!.skill_levels[0]! });
    expect(() => validateBrowserSolverResult(catalog, request, duplicate)).toThrow("duplicate skill ID");
    result.candidate!.skill_levels[0]!.level += 1;
    expect(() => validateBrowserSolverResult(catalog, request, result)).toThrow("computed skill totals");
  });
  it("accepts legal tied jewel assignments and order while preserving slot validation", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog({
      equipment: { head: [{ equipment_id: "head", slots: [["armor", 1], ["armor", 1]] }] },
      decorations: [
        { decoration_id: "z", display_name: null, required_slot: ["armor", 1], skills: [[0, 1]] },
        { decoration_id: "a", display_name: null, required_slot: ["armor", 1], skills: [[1, 1]] },
      ],
    }));
    const request = { requirements: [{ skill_id: "skill:attack", min_level: 2 }, { skill_id: "skill:affinity", min_level: 1 }], preferences: [], max_results: 1 };
    const result = solveBrowserRankedSearch(catalog, request);
    expect(result.candidate?.placements).toHaveLength(2);
    for (const placement of result.candidate!.placements) placement.slot_index = 1 - placement.slot_index;
    // Python's catalog-order tie puts z before a; browser's own tie puts a first.
    result.candidate!.placements.reverse();
    expect(() => validateBrowserSolverResult(catalog, request, result)).not.toThrow();
    result.candidate!.placements[1]!.slot_index = result.candidate!.placements[0]!.slot_index;
    expect(() => validateBrowserSolverResult(catalog, request, result)).toThrow("more than once");
  });
  it("accepts recursively reordered JSON object keys but rejects altered values and arrays", () => {
    const { catalog, request, result } = validBuild();
    const reverseKeys = (value: unknown): unknown => {
      if (Array.isArray(value)) return value.map(reverseKeys);
      if (value !== null && typeof value === "object") {
        return Object.fromEntries(Object.entries(value).reverse().map(([key, child]) => [key, reverseKeys(child)]));
      }
      return value;
    };
    const reordered = reverseKeys(result) as typeof result;
    expect(equalJsonValue(result, reordered)).toBe(true);
    expect(() => validateBrowserSolverResult(catalog, request, reordered)).not.toThrow();
    reordered.candidate!.equipment[0]!.display_name = "altered";
    expect(() => validateBrowserSolverResult(catalog, request, reordered)).toThrow("$.candidate.equipment");
    expect(equalJsonValue({ a: 1 }, { a: 1, b: null })).toBe(false);
    expect(equalJsonValue([1, 2], [2, 1])).toBe(false);
    expect(equalJsonValue([], {})).toBe(false);
  });
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
