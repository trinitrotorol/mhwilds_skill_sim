import { describe, expect, it } from "vitest";
import { prepareQueryAppraisals } from "./appraisal-query";
import { decodeBrowserSearchCatalog } from "./catalog";
import { solveBrowserRankedSearch } from "./solver";
import { makeTestCatalog } from "./test-catalog";
import { validateBrowserSolverResult } from "./validation";

function queryCatalog() {
  const raw = makeTestCatalog({ decorations: [] });
  raw.skills.push(...["guard", "luck"].map((id) => ({ skill_id: `skill:${id}`, display_name: id, kind: "armor" as const, max_level: 5, required_pieces: [] })));
  raw.source_catalog.skill_count = raw.skills.length;
  return decodeBrowserSearchCatalog({ ...raw, theoretical_appraisal_mode: "query",
    appraisal_charm_skill_groups: [{ group_id: "g", skills: ["attack", "affinity", "guard", "luck"].map((id) => ({ skill_id: `skill:${id}`, level: 1 })) }],
    appraisal_charm_patterns: [{ pattern_id: "p", rarity: 8, skill_group_ids: ["g", "g"], slots: [] }],
  });
}

describe("bounded request-specific theoretical appraisal generation", () => {
  it("retains only K representatives of irrelevant skills and preserves canonical recipe order", () => {
    const catalog = queryCatalog();
    const request = { requirements: [], preferences: [], max_results: 3 };
    const prepared = prepareQueryAppraisals(catalog, request, () => false);
    expect(prepared.catalog.indexed.dynamic_variants_by_id?.size).toBe(3);
    const result = solveBrowserRankedSearch(catalog, request);
    expect(result.candidates?.map((candidate) => candidate.equipment[6]!.equipment_id)).toEqual([
      "equipment:charm",
      "generated:appraisal-charm:rarity-8:p:combination-2",
      "generated:appraisal-charm:rarity-8:p:combination-3",
    ]);
    validateBrowserSolverResult(catalog, request, result);
    expect(catalog.indexed.dynamic_variants_by_id).toBeUndefined();
  });

  it("agrees with all legal distinct pairs when requirements select a later projected class", () => {
    const catalog = queryCatalog();
    const request = { requirements: [{ skill_id: "skill:luck", min_level: 1 }], preferences: [], max_results: 20 };
    const result = solveBrowserRankedSearch(catalog, request);
    expect(result.candidates?.map((candidate) => candidate.equipment[6]!.equipment_id)).toEqual([
      "generated:appraisal-charm:rarity-8:p:combination-4",
      "generated:appraisal-charm:rarity-8:p:combination-8",
      "generated:appraisal-charm:rarity-8:p:combination-12",
    ]);
    expect(result.exhausted).toBe(true);
  });

  it("does not claim completion when enumeration is interrupted", () => {
    const result = solveBrowserRankedSearch(queryCatalog(), { requirements: [], preferences: [], max_results: 20 }, { timeoutMs: 0 });
    expect(result).toMatchObject({ status: "timed-out", exhausted: false, timed_out: true, candidates: [] });
  });

  it("independently rejects a recipe that repeats a base skill", () => {
    const catalog = queryCatalog();
    const request = { requirements: [{ skill_id: "skill:luck", min_level: 1 }], preferences: [], max_results: 20 };
    const result = solveBrowserRankedSearch(catalog, request);
    result.candidates![0]!.equipment[6]!.equipment_id = "generated:appraisal-charm:rarity-8:p:combination-1";
    expect(() => validateBrowserSolverResult(catalog, request, result)).toThrow("repeats base skill");
  });
});
