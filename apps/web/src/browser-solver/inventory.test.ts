import { describe, expect, it } from "vitest";
import { decodeBrowserSearchCatalog } from "./catalog";
import { decodeInventorySearchSnapshot, type InventorySearchSnapshot } from "./inventory";
import { solveBrowserRankedSearch } from "./solver";
import { makeTestCatalog } from "./test-catalog";
import { validateBrowserSolverResult } from "./validation";

function inventory(overrides: Partial<InventorySearchSnapshot> = {}): InventorySearchSnapshot {
  return { schema_version: 1, catalog_revision: "0".repeat(64), decorations: [], fixed_charms: [{ equipment_id: "equipment:charm", quantity: 1 }], appraisal_charms: [], ...overrides };
}

describe("finite inventory and K best browser search", () => {
  it.each([0, 1, 2])("honors exact decoration boundary quantity=%i including omitted IDs", (quantity) => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog({ equipment: { head: [{ equipment_id: "head", slots: [["armor", 2], ["armor", 2]] }] } }));
    const request = { requirements: [{ skill_id: "skill:attack", min_level: 3 }], preferences: [], max_results: 3, inventory: inventory({ decorations: quantity ? [{ decoration_id: "decoration:z-attack", quantity }] : [] }) };
    const result = solveBrowserRankedSearch(catalog, request);
    expect(result.status).toBe(quantity === 2 ? "optimal" : "infeasible");
    expect(result.candidate?.placements.length ?? 0).toBe(quantity === 2 ? 2 : 0);
    validateBrowserSolverResult(catalog, request, result);
  });

  it("retains a dominated decoration after the stronger owned jewel is consumed", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog({ equipment: { head: [{ equipment_id: "head", slots: [["armor", 2], ["armor", 2]] }] } }));
    const result = solveBrowserRankedSearch(catalog, { requirements: [{ skill_id: "skill:attack", min_level: 3 }], preferences: [{ skill_id: "skill:affinity", target_level: 1 }], max_results: 1, inventory: inventory({ decorations: [{ decoration_id: "decoration:a-compound", quantity: 1 }, { decoration_id: "decoration:z-attack", quantity: 1 }] }) });
    expect(result.status).toBe("optimal");
    expect(result.candidate?.placements.map((item) => item.decoration_id).sort()).toEqual(["decoration:a-compound", "decoration:z-attack"]);
  });

  it("never substitutes a theoretical or unowned fixed charm", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog({ equipment: { charm: [{ equipment_id: "equipment:charm" }, { equipment_id: "generated:appraisal-charm:rarity-8:example", skills: [[0, 5]] }] } }));
    expect(solveBrowserRankedSearch(catalog, { requirements: [{ skill_id: "skill:attack", min_level: 5 }], preferences: [], max_results: 1, inventory: inventory() }).status).toBe("infeasible");
    expect(solveBrowserRankedSearch(catalog, { requirements: [], preferences: [], max_results: 1, inventory: inventory({ fixed_charms: [] }) }).status).toBe("infeasible");
  });

  it("returns all distinct equivalent equipment selections in lexicographic top-K order", () => {
    const raw = makeTestCatalog({ equipment: {
      head: [{ equipment_id: "head:a" }, { equipment_id: "head:b" }],
      chest: [{ equipment_id: "chest:a" }, { equipment_id: "chest:b" }],
      charm: [{ equipment_id: "charm:a" }, { equipment_id: "charm:b" }],
    } });
    const catalog = decodeBrowserSearchCatalog(raw);
    const request = { requirements: [], preferences: [], max_results: 20 };
    const result = solveBrowserRankedSearch(catalog, request);
    const expected = raw.equipment_by_part.head.flatMap((head) => raw.equipment_by_part.chest.flatMap((chest) => raw.equipment_by_part.charm.map((charm) => [0, head.variant_id, chest.variant_id, raw.equipment_by_part.arms[0]!.variant_id, raw.equipment_by_part.waist[0]!.variant_id, raw.equipment_by_part.legs[0]!.variant_id, charm.variant_id])));
    expect(result.selected_variant_ids_by_candidate).toEqual(expected);
    expect(result.exhausted).toBe(true);
    validateBrowserSolverResult(catalog, request, result);
    const limited = solveBrowserRankedSearch(catalog, { ...request, max_results: 3 });
    expect(limited.selected_variant_ids_by_candidate).toEqual(expected.slice(0, 3));
    expect(limited.exhausted).toBe(false);
  });

  it("matches a full small equipment oracle for ranked multi-result requests", () => {
    const raw = makeTestCatalog({ decorations: [], equipment: {
      head: [{ equipment_id: "head:0" }, { equipment_id: "head:1", skills: [[1, 1]] }, { equipment_id: "head:2", skills: [[1, 2]] }],
      chest: [{ equipment_id: "chest:0" }, { equipment_id: "chest:1", skills: [[1, 1]] }],
      charm: [{ equipment_id: "charm:0" }, { equipment_id: "charm:1", skills: [[1, 2]] }],
    } });
    const expected = raw.equipment_by_part.head.flatMap((head) => raw.equipment_by_part.chest.flatMap((chest) => raw.equipment_by_part.charm.map((charm) => ({ ids: [head.variant_id, chest.variant_id, charm.variant_id], score: Math.min(3, [head, chest, charm].reduce((sum, item) => sum + (item.skills[0]?.[1] ?? 0), 0)) })))).sort((left, right) => right.score - left.score || left.ids[0]! - right.ids[0]! || left.ids[1]! - right.ids[1]! || left.ids[2]! - right.ids[2]!);
    const catalog = decodeBrowserSearchCatalog(raw);
    const result = solveBrowserRankedSearch(catalog, { requirements: [], preferences: [{ skill_id: "skill:affinity", target_level: 3 }], max_results: 20 });
    expect(result.candidates?.map((candidate, index) => ({ ids: [result.selected_variant_ids_by_candidate![index]![1], result.selected_variant_ids_by_candidate![index]![2], result.selected_variant_ids_by_candidate![index]![6]], score: candidate.preference_score }))).toEqual(expected);
  });

  it("validates appraisal rules and preserves equal abilities on different anonymous instances", () => {
    const catalog = decodeBrowserSearchCatalog({ ...makeTestCatalog(),
      appraisal_charm_skill_groups: [{ group_id: "group:a", skills: [{ skill_id: "skill:attack", level: 2 }] }],
      appraisal_charm_patterns: [{ pattern_id: "pattern:a", rarity: 8, skill_group_ids: ["group:a"], slots: [{ kind: "armor", level: 1 }] }],
    });
    const charm = { instance_id: "owned:0", rarity: 8, skills: [{ skill_id: "skill:attack", level: 2 }], slots: [{ kind: "armor" as const, level: 1 }], quantity: 1 };
    const request = { requirements: [], preferences: [], max_results: 20, inventory: inventory({ fixed_charms: [], appraisal_charms: [charm, { ...charm, instance_id: "owned:1" }] }) };
    const result = solveBrowserRankedSearch(catalog, request);
    expect(result.candidates?.map((candidate) => candidate.equipment[6]?.equipment_id)).toEqual(["owned:0", "owned:1"]);
    expect(() => solveBrowserRankedSearch(catalog, { ...request, inventory: inventory({ appraisal_charms: [{ ...charm, rarity: 9 }] }) })).toThrow("catalog rules");
  });

  it("independently rejects inventory violations in any returned candidate", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog({ equipment: { head: [{ equipment_id: "head:a" }, { equipment_id: "head:b" }] } }));
    const request = { requirements: [], preferences: [], max_results: 2, inventory: inventory() };
    const result = solveBrowserRankedSearch(catalog, request);
    result.candidates![1]!.equipment[6]!.equipment_id = "unowned";
    expect(() => validateBrowserSolverResult(catalog, request, result)).toThrow();
  });

  it("rejects an owned charm formed by summing two rolls of the same base skill", () => {
    const catalog = decodeBrowserSearchCatalog({ ...makeTestCatalog(),
      appraisal_charm_skill_groups: [{ group_id: "g", skills: [{ skill_id: "skill:attack", level: 1 }] }],
      appraisal_charm_patterns: [{ pattern_id: "p", rarity: 8, skill_group_ids: ["g", "g"], slots: [] }],
    });
    const owned = inventory({ appraisal_charms: [{ instance_id: "owned:0", rarity: 8, skills: [{ skill_id: "skill:attack", level: 2 }], slots: [], quantity: 1 }] });
    expect(() => solveBrowserRankedSearch(catalog, { requirements: [], preferences: [], max_results: 1, inventory: owned })).toThrow("catalog rules");
  });

  it.each([-1, 0.5, Number.MAX_SAFE_INTEGER + 1, true])("rejects unsafe quantity %s", (quantity) => {
    expect(() => decodeInventorySearchSnapshot({ ...inventory(), decorations: [{ decoration_id: "jewel", quantity }] })).toThrow();
  });
  it("rejects unknown IDs and mismatching revisions without removing constraints", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog());
    const request = { requirements: [], preferences: [], max_results: 1 };
    expect(() => solveBrowserRankedSearch(catalog, { ...request, inventory: inventory({ catalog_revision: "1".repeat(64) }) })).toThrow("revision");
    expect(() => solveBrowserRankedSearch(catalog, { ...request, inventory: inventory({ decorations: [{ decoration_id: "unknown", quantity: 1 }] }) })).toThrow("unknown");
  });

  it("retains validated partial K candidates without claiming optimality after interruption", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog({ equipment: { head: [{ equipment_id: "head:a" }, { equipment_id: "head:b" }] } }));
    const request = { requirements: [], preferences: [], max_results: 20, inventory: inventory() };
    let foundCandidate = false;
    const result = solveBrowserRankedSearch(catalog, request, {
      shouldCancel: () => foundCandidate,
      onProgress: (progress) => { if (progress.preference_score !== null) foundCandidate = true; },
    });
    expect(result.status).toBe("cancelled");
    expect(result.exhausted).toBe(false);
    expect(result.candidates).toHaveLength(1);
    validateBrowserSolverResult(catalog, request, result);
    const restarted = solveBrowserRankedSearch(catalog, request);
    expect(restarted.candidates).toHaveLength(2);
    expect(restarted.status).toBe("optimal");
  });
});
