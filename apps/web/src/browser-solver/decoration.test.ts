import { describe, expect, it } from "vitest";

import { decodeBrowserSearchCatalog } from "./catalog";
import {
  createDecorationProjection,
  reconstructDecorationPlacements,
  solveProjectedDecorations,
} from "./decoration";
import { createRequestProjection } from "./objective";
import { makeTestCatalog } from "./test-catalog";
import { decodeBrowserRankedSearchRequest } from "./validation";

function solveDecorations(
  requestValue: unknown,
  baseLevels: number[],
  slots: Array<readonly ["weapon" | "armor", number]>,
) {
  const catalog = decodeBrowserSearchCatalog(makeTestCatalog());
  const request = decodeBrowserRankedSearchRequest(requestValue);
  const projection = createRequestProjection(catalog, request);
  const decorations = createDecorationProjection(catalog, projection);
  return {
    catalog,
    projection,
    outcome: solveProjectedDecorations(
      projection,
      decorations,
      baseLevels,
      slots,
    ),
  };
}

describe("exact decoration dynamic programming", () => {
  it("uses lexical decoration ID order rather than Catalog insertion order", () => {
    const { catalog, outcome } = solveDecorations(
      {
        requirements: [{ skill_id: "skill:attack", min_level: 2 }],
        preferences: [],
        max_results: 1,
      },
      [1],
      [["armor", 2]],
    );

    expect(outcome.interrupted).toBe(false);
    expect(
      outcome.solution?.decoration_indices.map(
        (index) => catalog.decorations[index]?.decoration_id,
      ),
    ).toEqual(["decoration:a-compound"]);
  });

  it("keeps weapon and armor slots strictly separated", () => {
    const { catalog, outcome } = solveDecorations(
      {
        requirements: [{ skill_id: "skill:attack", min_level: 1 }],
        preferences: [],
        max_results: 1,
      },
      [0],
      [["weapon", 2]],
    );

    expect(
      outcome.solution?.decoration_indices.map(
        (index) => catalog.decorations[index]?.decoration_id,
      ),
    ).toEqual(["decoration:weapon-attack"]);
  });

  it("counts every skill on a compound decoration", () => {
    const { catalog, outcome } = solveDecorations(
      {
        requirements: [{ skill_id: "skill:attack", min_level: 2 }],
        preferences: [{ skill_id: "skill:affinity", target_level: 1 }],
        max_results: 1,
      },
      [1, 0],
      [["armor", 2]],
    );

    expect(outcome.solution?.preference_score).toBe(1);
    expect(
      outcome.solution?.decoration_indices.map(
        (index) => catalog.decorations[index]?.decoration_id,
      ),
    ).toEqual(["decoration:a-compound"]);
  });

  it("cannot use one slot twice even though decorations are reusable", () => {
    const { outcome } = solveDecorations(
      {
        requirements: [{ skill_id: "skill:attack", min_level: 3 }],
        preferences: [],
        max_results: 1,
      },
      [1],
      [["armor", 2]],
    );

    expect(outcome.solution).toBeNull();
  });

  it("reconstructs high-level decorations first into the lowest compatible slot", () => {
    const input = makeTestCatalog({
      equipment: {
        chest: [
          {
            equipment_id: "equipment:chest",
            slots: [["armor", 1]],
          },
        ],
      },
    });
    const catalog = decodeBrowserSearchCatalog(input);
    const selected = [
      catalog.indexed.equipment_by_part.weapon[0]!,
      catalog.indexed.equipment_by_part.head[0]!,
      catalog.indexed.equipment_by_part.chest[0]!,
      catalog.indexed.equipment_by_part.arms[0]!,
      catalog.indexed.equipment_by_part.waist[0]!,
      catalog.indexed.equipment_by_part.legs[0]!,
      catalog.indexed.equipment_by_part.charm[0]!,
    ];

    const placements = reconstructDecorationPlacements(
      catalog,
      selected,
      [0, 1],
    );

    expect(placements).toEqual([
      {
        equipment_id: "equipment:head",
        slot_index: 0,
        decoration_id: "decoration:a-compound",
      },
      {
        equipment_id: "equipment:chest",
        slot_index: 0,
        decoration_id: "decoration:z-attack",
      },
    ]);
  });

  it("honors an injected stop predicate inside decoration DP", () => {
    let checks = 0;
    const { outcome } = solveDecorations(
      {
        requirements: [{ skill_id: "skill:attack", min_level: 10 }],
        preferences: [{ skill_id: "skill:affinity", target_level: 10 }],
        max_results: 1,
      },
      [0, 0],
      Array.from({ length: 20 }, () => ["armor", 2] as const),
    );
    // The small helper call above proves regular completion. Exercise the stop
    // path separately with enough transitions to cross the fixed interval.
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog());
    const request = decodeBrowserRankedSearchRequest({
      requirements: [{ skill_id: "skill:attack", min_level: 10 }],
      preferences: [{ skill_id: "skill:affinity", target_level: 10 }],
      max_results: 1,
    });
    const projection = createRequestProjection(catalog, request);
    const interrupted = solveProjectedDecorations(
      projection,
      createDecorationProjection(catalog, projection),
      [0, 0],
      Array.from({ length: 20 }, () => ["armor", 2] as const),
      () => {
        checks += 1;
        return true;
      },
    );

    expect(outcome.interrupted).toBe(false);
    expect(interrupted.interrupted).toBe(true);
    expect(checks).toBe(1);
  });
});
