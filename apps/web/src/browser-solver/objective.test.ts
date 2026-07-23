import { describe, expect, it } from "vitest";

import { decodeBrowserSearchCatalog } from "./catalog";
import {
  calculateBrowserPreferenceScore,
  calculateProjectedPreferenceScore,
  compareSearchObjectives,
  createRequestProjection,
  projectedRequirementsSatisfied,
  skillLevelsSatisfyBrowserRequirements,
} from "./objective";
import { makeTestCatalog } from "./test-catalog";
import { decodeBrowserRankedSearchRequest } from "./validation";

describe("browser ranked request and objective", () => {
  it("allows required/preferred overlap and copies the request", () => {
    const input = {
      requirements: [{ skill_id: "skill:attack", min_level: 2 }],
      preferences: [{ skill_id: "skill:attack", target_level: 4 }],
      max_results: 1,
      weapon_kind: "great-sword",
    };
    const original = structuredClone(input);

    const decoded = decodeBrowserRankedSearchRequest(input);

    expect(decoded).toEqual(input);
    expect(input).toEqual(original);
    expect(decoded.requirements).not.toBe(input.requirements);
    input.requirements[0]!.min_level = 99;
    expect(decoded.requirements[0]?.min_level).toBe(2);
  });

  it.each([
    {
      value: {
        requirements: [
          { skill_id: "skill:attack", min_level: 1 },
          { skill_id: "skill:attack", min_level: 2 },
        ],
        preferences: [],
        max_results: 1,
      },
      path: "$.requirements[1].skill_id",
    },
    {
      value: {
        requirements: [],
        preferences: [
          { skill_id: "skill:attack", target_level: 1 },
          { skill_id: "skill:attack", target_level: 2 },
        ],
        max_results: 1,
      },
      path: "$.preferences[1].skill_id",
    },
    {
      value: {
        requirements: [{ skill_id: "skill:attack", min_level: 0 }],
        preferences: [],
        max_results: 1,
      },
      path: "$.requirements[0].min_level",
    },
    {
      value: {
        requirements: [],
        preferences: [],
        max_results: 2,
      },
      path: "$.max_results",
    },
    {
      value: {
        requirements: [],
        preferences: [],
        max_results: 1,
        weapon_kind: 1,
      },
      path: "$.weapon_kind",
    },
  ])("rejects invalid request values at $path", ({ value, path }) => {
    expect(() => decodeBrowserRankedSearchRequest(value)).toThrow(path);
  });

  it("projects known skills and treats unknown request skills as specified", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog());
    const request = decodeBrowserRankedSearchRequest({
      requirements: [{ skill_id: "skill:missing", min_level: 1 }],
      preferences: [
        { skill_id: "skill:attack", target_level: 3 },
        { skill_id: "skill:unknown-preference", target_level: 99 },
      ],
      max_results: 1,
    });

    const projection = createRequestProjection(catalog, request);

    expect(projection.unknown_required_skill).toBe(true);
    expect(projection.maximum_preference_score).toBe(3);
    expect(Array.from(projection.skill_indices)).toEqual([0]);
    expect(projectedRequirementsSatisfied([99], projection)).toBe(false);
  });

  it("caps each preference target but never caps actual requirement levels", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog());
    const request = decodeBrowserRankedSearchRequest({
      requirements: [{ skill_id: "skill:attack", min_level: 2 }],
      preferences: [
        { skill_id: "skill:attack", target_level: 3 },
        { skill_id: "skill:affinity", target_level: 2 },
      ],
      max_results: 1,
    });
    const projection = createRequestProjection(catalog, request);

    expect(projectedRequirementsSatisfied([10, 0], projection)).toBe(true);
    expect(calculateProjectedPreferenceScore([10, 1], projection)).toBe(4);
    const levels = [
      { skill_id: "skill:attack", level: 10 },
      { skill_id: "skill:affinity", level: 1 },
    ];
    expect(
      skillLevelsSatisfyBrowserRequirements(levels, request.requirements),
    ).toBe(true);
    expect(
      calculateBrowserPreferenceScore(levels, request.preferences),
    ).toBe(4);
  });

  it("orders by score, decoration count, variants, then lexical decoration ID rank", () => {
    const base = {
      preference_score: 4,
      decoration_count: 1,
      selected_variant_ids: [0, 1, 2, 3, 4, 5, 6],
      decoration_indices: [0],
      decoration_id_ranks: [1],
    };

    expect(
      compareSearchObjectives(
        { ...base, preference_score: 5 },
        base,
      ),
    ).toBeLessThan(0);
    expect(
      compareSearchObjectives(
        { ...base, decoration_count: 0 },
        base,
      ),
    ).toBeLessThan(0);
    expect(
      compareSearchObjectives(
        { ...base, selected_variant_ids: [0, 1, 2, 3, 4, 5, 5] },
        base,
      ),
    ).toBeLessThan(0);
    expect(
      compareSearchObjectives(
        { ...base, decoration_indices: [99], decoration_id_ranks: [0] },
        base,
      ),
    ).toBeLessThan(0);
  });
});
