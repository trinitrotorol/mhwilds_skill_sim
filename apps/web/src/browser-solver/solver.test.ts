import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { decodeBrowserSearchCatalog } from "./catalog";
import tinyCatalogJson from "./fixtures/tiny-browser-catalog.json";
import tinyOracleJson from "./fixtures/tiny-oracle.json";
import { solveBrowserRankedSearch } from "./solver";
import {
  EQUIPMENT_PARTS,
  type BrowserRankedSearchRequest,
} from "./types";
import {
  makeTestCatalog,
  type TestCatalog,
  type TestDecoration,
  type TestVariant,
} from "./test-catalog";
import {
  decodeBrowserRankedSearchRequest,
  validateBrowserSolverResult,
} from "./validation";

const EMPTY_REQUEST = {
  requirements: [],
  preferences: [],
  max_results: 1,
} as const;

describe("solveBrowserRankedSearch", () => {
  it("returns the deterministic minimum-variant empty build", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog());

    const result = solveBrowserRankedSearch(catalog, EMPTY_REQUEST);

    expect(result.status).toBe("optimal");
    expect(result.preference_score).toBe(0);
    expect(result.decoration_count).toBe(0);
    expect(result.selected_variant_ids).toEqual([0, 1, 2, 3, 4, 5, 6]);
    expect(result.candidate?.equipment.map(({ part }) => part)).toEqual(
      EQUIPMENT_PARTS,
    );
    expect(result.candidate?.placements).toEqual([]);
    expect(result.candidate?.skill_levels).toEqual([
      { skill_id: "skill:attack", level: 1 },
    ]);
    expect(result.visited_nodes).toBeGreaterThan(0);
    expect(result.complete_equipment_selections).toBe(1);
    validateBrowserSolverResult(catalog, EMPTY_REQUEST, result);
  });

  it("returns infeasible for unknown requirements and missing parts", () => {
    const normal = decodeBrowserSearchCatalog(makeTestCatalog());
    const unknown = solveBrowserRankedSearch(normal, {
      requirements: [{ skill_id: "skill:missing", min_level: 1 }],
      preferences: [],
      max_results: 1,
    });
    expect(unknown).toMatchObject({
      status: "infeasible",
      candidate: null,
      selected_variant_ids: [],
    });

    const missingInput = makeTestCatalog();
    missingInput.equipment_by_part.charm = [];
    missingInput.source_catalog.expanded_equipment_count -= 1;
    const missing = solveBrowserRankedSearch(
      decodeBrowserSearchCatalog(missingInput),
      EMPTY_REQUEST,
    );
    expect(missing.status).toBe("infeasible");
  });

  it("satisfies hard requirements with the fewest lexical-ID decorations", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog());

    const result = solveBrowserRankedSearch(catalog, {
      requirements: [{ skill_id: "skill:attack", min_level: 2 }],
      preferences: [],
      max_results: 1,
    });

    expect(result.status).toBe("optimal");
    expect(result.decoration_count).toBe(1);
    expect(result.candidate?.placements).toEqual([
      {
        equipment_id: "equipment:head",
        slot_index: 0,
        decoration_id: "decoration:a-compound",
      },
    ]);
    expect(result.candidate?.skill_levels).toEqual([
      { skill_id: "skill:attack", level: 2 },
      { skill_id: "skill:affinity", level: 1 },
    ]);
  });

  it("ranks preference score before decoration count and variants", () => {
    const catalog = decodeBrowserSearchCatalog(
      makeTestCatalog({
        equipment: {
          head: [
            {
              equipment_id: "equipment:head:lower-id",
              slots: [["armor", 2]],
            },
            {
              equipment_id: "equipment:head:fixed",
              skills: [[1, 1]],
            },
          ],
        },
      }),
    );

    const result = solveBrowserRankedSearch(catalog, {
      requirements: [],
      preferences: [{ skill_id: "skill:affinity", target_level: 1 }],
      max_results: 1,
    });

    expect(result.preference_score).toBe(1);
    expect(result.decoration_count).toBe(0);
    expect(result.selected_variant_ids[1]).toBe(2);
    expect(result.candidate?.equipment[1]?.equipment_id).toBe(
      "equipment:head:fixed",
    );
  });

  it("applies weapon filtering and distinguishes same-ID Artian variants", () => {
    const catalog = decodeBrowserSearchCatalog(
      makeTestCatalog({
        equipment: {
          weapon: [
            {
              equipment_id: "equipment:artian",
              weapon_kind: "great-sword",
              series_skill_id: 2,
              series_skill_ids: [2],
            },
            {
              equipment_id: "equipment:artian",
              weapon_kind: "great-sword",
              group_skill_id: 3,
              group_skill_ids: [3],
              skills: [[0, 2]],
            },
            {
              equipment_id: "equipment:bow",
              weapon_kind: "bow",
              skills: [[0, 10]],
            },
          ],
          head: [
            {
              equipment_id: "equipment:head",
              series_skill_id: 2,
              series_skill_ids: [2],
            },
          ],
        },
      }),
    );

    const result = solveBrowserRankedSearch(catalog, {
      requirements: [{ skill_id: "skill:series", min_level: 1 }],
      preferences: [{ skill_id: "skill:attack", target_level: 10 }],
      max_results: 1,
      weapon_kind: "great-sword",
    });

    expect(result.status).toBe("optimal");
    expect(result.selected_variant_ids[0]).toBe(0);
    expect(result.candidate?.equipment[0]).toMatchObject({
      equipment_id: "equipment:artian",
      series_skill_id: "skill:series",
      series_skill_ids: ["skill:series"],
    });
    expect(
      result.candidate?.skill_levels.find(
        ({ skill_id }) => skill_id === "skill:series",
      )?.level,
    ).toBe(1);

    const noWeapon = solveBrowserRankedSearch(catalog, {
      ...EMPTY_REQUEST,
      weapon_kind: "hammer",
    });
    expect(noWeapon.status).toBe("infeasible");
  });

  it("activates primary/additional series and group memberships by piece count", () => {
    const catalog = decodeBrowserSearchCatalog(
      makeTestCatalog({
        equipment: {
          weapon: [
            {
              equipment_id: "equipment:weapon",
              weapon_kind: "great-sword",
              series_skill_id: 2,
              series_skill_ids: [2],
              group_skill_id: 3,
              group_skill_ids: [3],
            },
          ],
          head: [
            {
              equipment_id: "equipment:head",
              series_skill_ids: [2],
              group_skill_ids: [3],
            },
          ],
          chest: [
            {
              equipment_id: "equipment:chest",
              group_skill_ids: [3],
            },
          ],
        },
      }),
    );

    const result = solveBrowserRankedSearch(catalog, {
      requirements: [{ skill_id: "skill:series", min_level: 1 }],
      preferences: [{ skill_id: "skill:group", target_level: 1 }],
      max_results: 1,
    });

    expect(result.status).toBe("optimal");
    expect(result.preference_score).toBe(1);
    expect(result.candidate?.skill_levels).toEqual(
      expect.arrayContaining([
        { skill_id: "skill:series", level: 1 },
        { skill_id: "skill:group", level: 1 },
      ]),
    );
  });

  it("does not wrap large set piece requirements during projection", () => {
    const input = makeTestCatalog();
    input.skills[2]!.max_level = 1;
    input.skills[2]!.required_pieces = [256];
    input.equipment_by_part.head[0]!.series_skill_id = 2;
    input.equipment_by_part.head[0]!.series_skill_ids = [2];
    const catalog = decodeBrowserSearchCatalog(input);
    const request = {
      requirements: [{ skill_id: "skill:series", min_level: 1 }],
      preferences: [],
      max_results: 1,
    } as const;

    const result = solveBrowserRankedSearch(catalog, request);

    expect(result.status).toBe("infeasible");
    expect(() =>
      validateBrowserSolverResult(catalog, request, result),
    ).not.toThrow();
  });

  it("selects generated charm-like candidates and preserves exact variant IDs", () => {
    const catalog = decodeBrowserSearchCatalog(
      makeTestCatalog({
        equipment: {
          charm: [
            { equipment_id: "equipment:charm:fixed" },
            {
              equipment_id: "equipment:charm:appraisal:generated",
              skills: [[1, 2]],
            },
          ],
        },
      }),
    );

    const result = solveBrowserRankedSearch(catalog, {
      requirements: [],
      preferences: [{ skill_id: "skill:affinity", target_level: 2 }],
      max_results: 1,
    });

    expect(result.status).toBe("optimal");
    expect(result.preference_score).toBe(2);
    expect(result.selected_variant_ids[6]).toBe(7);
    expect(result.candidate?.equipment[6]?.equipment_id).toContain(
      "appraisal",
    );
  });

  it("supports deterministic timeout, cancellation, and partial incumbents", () => {
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
              slots: [["armor", 2]],
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

    const timedOut = solveBrowserRankedSearch(catalog, request, {
      timeoutMs: 0,
      now: () => 5,
    });
    expect(timedOut).toMatchObject({
      status: "timed-out",
      candidate: null,
      visited_nodes: 0,
    });

    let checks = 0;
    const cancelled = solveBrowserRankedSearch(catalog, request, {
      shouldCancel: () => {
        checks += 1;
        return checks >= 14;
      },
    });
    expect(cancelled.status).toBe("cancelled");
    expect(cancelled.candidate).not.toBeNull();
    expect(cancelled.complete_equipment_selections).toBe(1);
    validateBrowserSolverResult(catalog, request, cancelled);
  });

  it("is deterministic and does not mutate request or decoded Catalog", () => {
    const catalog = decodeBrowserSearchCatalog(makeTestCatalog());
    const request = {
      requirements: [{ skill_id: "skill:attack", min_level: 2 }],
      preferences: [{ skill_id: "skill:affinity", target_level: 1 }],
      max_results: 1,
    } satisfies BrowserRankedSearchRequest;
    const requestBefore = structuredClone(request);
    const catalogSkillBefore = catalog.skills[0]?.skill_id;

    const first = solveBrowserRankedSearch(catalog, request);
    const second = solveBrowserRankedSearch(catalog, request);

    expect(first.candidate).toEqual(second.candidate);
    expect(first.selected_variant_ids).toEqual(second.selected_variant_ids);
    expect(first.preference_score).toBe(second.preference_score);
    expect(first.decoration_count).toBe(second.decoration_count);
    expect(request).toEqual(requestBefore);
    expect(catalog.skills[0]?.skill_id).toBe(catalogSkillBefore);
  });

  it("matches a brute-force oracle for bonus, compound, filter, and tie cases", () => {
    const input = differentialCatalog();
    const catalog = decodeBrowserSearchCatalog(input);
    const request = {
      requirements: [
        { skill_id: "skill:attack", min_level: 2 },
        { skill_id: "skill:series", min_level: 1 },
      ],
      preferences: [
        { skill_id: "skill:affinity", target_level: 2 },
        { skill_id: "skill:group", target_level: 1 },
      ],
      max_results: 1,
      weapon_kind: "great-sword",
    } as const;

    const expected = bruteForceTopOne(input, request);
    const actual = solveBrowserRankedSearch(catalog, request);

    expect(expected).not.toBeNull();
    expect(actual.status).toBe("optimal");
    expect({
      preferenceScore: actual.preference_score,
      decorationCount: actual.decoration_count,
      variantIds: actual.selected_variant_ids,
      decorationIds: actual.candidate?.placements
        .map(({ decoration_id }) => decoration_id)
        .sort(),
    }).toEqual(expected);
  });

  it("matches every generated tiny Python CP-SAT oracle objective", () => {
    const catalog = decodeBrowserSearchCatalog(tinyCatalogJson);
    const oracle = tinyOracleJson as {
      cases: Array<{
        name: string;
        request: unknown;
        status: "optimal" | "infeasible" | "timed-out";
        candidate_exists: boolean;
        preference_score: number | null;
        decoration_count: number | null;
      }>;
    };

    for (const oracleCase of oracle.cases) {
      const request = decodeBrowserRankedSearchRequest(oracleCase.request);
      const result = solveBrowserRankedSearch(catalog, request, {
        timeoutMs: 10_000,
      });

      expect(result.status, oracleCase.name).toBe(oracleCase.status);
      expect(result.candidate !== null, oracleCase.name).toBe(
        oracleCase.candidate_exists,
      );
      expect(result.preference_score, oracleCase.name).toBe(
        oracleCase.preference_score,
      );
      expect(result.decoration_count, oracleCase.name).toBe(
        oracleCase.decoration_count,
      );
      validateBrowserSolverResult(catalog, request, result);
    }
  });

  it("does not materialize a naive Cartesian equipment product", async () => {
    const source = await readFile(
      resolve(process.cwd(), "src/browser-solver/solver.ts"),
      "utf8",
    );

    expect(source).not.toContain(".flatMap(");
    expect(source).not.toMatch(/\bcartesian\b/iu);
  });
});

interface BruteObjective {
  preferenceScore: number;
  decorationCount: number;
  variantIds: number[];
  decorationIds: string[];
}

function differentialCatalog(): TestCatalog {
  return makeTestCatalog({
    equipment: {
      weapon: [
        {
          equipment_id: "equipment:artian",
          weapon_kind: "great-sword",
          series_skill_id: 2,
          series_skill_ids: [2],
          slots: [["weapon", 1]],
        },
        {
          equipment_id: "equipment:artian",
          weapon_kind: "great-sword",
          group_skill_id: 3,
          group_skill_ids: [3],
          skills: [[0, 1]],
          slots: [["weapon", 1]],
        },
        {
          equipment_id: "equipment:bow",
          weapon_kind: "bow",
          skills: [[0, 9]],
        },
      ],
      head: [
        {
          equipment_id: "equipment:head:series",
          series_skill_ids: [2],
          slots: [["armor", 2]],
        },
        {
          equipment_id: "equipment:head:group",
          group_skill_ids: [3],
          skills: [[1, 1]],
          slots: [["armor", 1]],
        },
      ],
      chest: [
        {
          equipment_id: "equipment:chest:series",
          series_skill_ids: [2],
          skills: [[0, 1]],
        },
        {
          equipment_id: "equipment:chest:group",
          group_skill_ids: [3],
          slots: [["armor", 2]],
        },
      ],
      arms: [
        {
          equipment_id: "equipment:arms",
          group_skill_ids: [3],
        },
      ],
    },
    decorations: [
      {
        decoration_id: "decoration:z-weapon-attack",
        display_name: null,
        required_slot: ["weapon", 1],
        skills: [[0, 1]],
      },
      {
        decoration_id: "decoration:a-compound",
        display_name: null,
        required_slot: ["armor", 2],
        skills: [
          [0, 1],
          [1, 1],
        ],
      },
      {
        decoration_id: "decoration:m-attack",
        display_name: null,
        required_slot: ["armor", 1],
        skills: [[0, 1]],
      },
      {
        decoration_id: "decoration:b-affinity",
        display_name: null,
        required_slot: ["armor", 1],
        skills: [[1, 1]],
      },
    ],
  });
}

function cartesianEquipment(
  input: TestCatalog,
  request: BrowserRankedSearchRequest,
): TestVariant[][] {
  let selections: TestVariant[][] = [[]];
  for (const part of EQUIPMENT_PARTS) {
    const candidates = input.equipment_by_part[part].filter(
      (variant) =>
        part !== "weapon" ||
        request.weapon_kind === undefined ||
        variant.weapon_kind === request.weapon_kind,
    );
    selections = selections.flatMap((selection) =>
      candidates.map((candidate) => [...selection, candidate]),
    );
  }
  return selections;
}

function enumerateDecorationAssignments(
  equipment: readonly TestVariant[],
  decorations: readonly TestDecoration[],
): Array<Array<TestDecoration | null>> {
  const slots = equipment.flatMap((variant) =>
    variant.slots.map(([kind, level]) => ({ kind, level })),
  );
  let assignments: Array<Array<TestDecoration | null>> = [[]];
  for (const slot of slots) {
    const choices: Array<TestDecoration | null> = [
      null,
      ...decorations.filter(
        ({ required_slot: [kind, level] }) =>
          kind === slot.kind && level <= slot.level,
      ),
    ];
    assignments = assignments.flatMap((assignment) =>
      choices.map((choice) => [...assignment, choice]),
    );
  }
  return assignments;
}

function aggregateBruteLevels(
  input: TestCatalog,
  equipment: readonly TestVariant[],
  decorations: readonly (TestDecoration | null)[],
): Map<string, number> {
  const totals = new Map<string, number>();
  const add = (skillIndex: number, level: number) => {
    const skillId = input.skills[skillIndex]?.skill_id;
    if (skillId === undefined) {
      throw new Error("brute-force skill index is invalid");
    }
    totals.set(skillId, (totals.get(skillId) ?? 0) + level);
  };
  for (const variant of equipment) {
    for (const [skillIndex, level] of variant.skills) {
      add(skillIndex, level);
    }
  }
  for (let skillIndex = 0; skillIndex < input.skills.length; skillIndex += 1) {
    const skill = input.skills[skillIndex]!;
    if (skill.kind !== "set" && skill.kind !== "group") {
      continue;
    }
    const pieces = equipment.filter((variant) =>
      (skill.kind === "set"
        ? variant.series_skill_ids
        : variant.group_skill_ids
      ).includes(skillIndex),
    ).length;
    let level = 0;
    for (let rank = 0; rank < skill.required_pieces.length; rank += 1) {
      if ((skill.required_pieces[rank] ?? Number.POSITIVE_INFINITY) <= pieces) {
        level = rank + 1;
      }
    }
    if (level > 0) {
      add(skillIndex, level);
    }
  }
  for (const decoration of decorations) {
    if (decoration !== null) {
      for (const [skillIndex, level] of decoration.skills) {
        add(skillIndex, level);
      }
    }
  }
  return totals;
}

function compareNumbers(left: readonly number[], right: readonly number[]): number {
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    if (left[index] !== right[index]) {
      return (left[index] ?? 0) - (right[index] ?? 0);
    }
  }
  return left.length - right.length;
}

function compareStrings(left: readonly string[], right: readonly string[]): number {
  for (let index = 0; index < Math.min(left.length, right.length); index += 1) {
    const leftValue = left[index]!;
    const rightValue = right[index]!;
    if (leftValue !== rightValue) {
      return leftValue < rightValue ? -1 : 1;
    }
  }
  return left.length - right.length;
}

function bruteRanksAhead(left: BruteObjective, right: BruteObjective): boolean {
  if (left.preferenceScore !== right.preferenceScore) {
    return left.preferenceScore > right.preferenceScore;
  }
  if (left.decorationCount !== right.decorationCount) {
    return left.decorationCount < right.decorationCount;
  }
  const variants = compareNumbers(left.variantIds, right.variantIds);
  return (
    variants < 0 ||
    (variants === 0 &&
      compareStrings(left.decorationIds, right.decorationIds) < 0)
  );
}

function bruteForceTopOne(
  input: TestCatalog,
  request: BrowserRankedSearchRequest,
): BruteObjective | null {
  let best: BruteObjective | null = null;
  for (const equipment of cartesianEquipment(input, request)) {
    for (const assignment of enumerateDecorationAssignments(
      equipment,
      input.decorations,
    )) {
      const levels = aggregateBruteLevels(input, equipment, assignment);
      if (
        !request.requirements.every(
          ({ skill_id, min_level }) =>
            (levels.get(skill_id) ?? 0) >= min_level,
        )
      ) {
        continue;
      }
      const decorationIds = assignment
        .filter((value): value is TestDecoration => value !== null)
        .map(({ decoration_id }) => decoration_id)
        .sort();
      const candidate: BruteObjective = {
        preferenceScore: request.preferences.reduce(
          (score, { skill_id, target_level }) =>
            score + Math.min(levels.get(skill_id) ?? 0, target_level),
          0,
        ),
        decorationCount: decorationIds.length,
        variantIds: equipment.map(({ variant_id }) => variant_id),
        decorationIds,
      };
      if (best === null || bruteRanksAhead(candidate, best)) {
        best = candidate;
      }
    }
  }
  return best;
}
