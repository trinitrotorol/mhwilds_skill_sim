import { describe, expect, it } from "vitest";

import {
  BrowserCatalogDecodeError,
  decodeBrowserSearchCatalog,
} from "./catalog";
import { makeTestCatalog } from "./test-catalog";

describe("decodeBrowserSearchCatalog", () => {
  it("decodes a valid compact Catalog into independent indexed data", () => {
    const input = makeTestCatalog();
    const original = structuredClone(input);

    const first = decodeBrowserSearchCatalog(input);
    const second = decodeBrowserSearchCatalog(input);

    expect(first.source_catalog.sha256).toBe("0".repeat(64));
    expect(first.indexed.variants_by_id).toHaveLength(7);
    expect(first.indexed.variants_by_id[0]?.skills).toEqual(
      Int32Array.from([0, 1]),
    );
    expect(first.indexed.skill_index_by_id.get("skill:series")).toBe(2);
    expect(first.indexed.equipment_by_part.weapon[0]?.slots).toEqual(
      Int32Array.from([0, 2]),
    );
    expect(input).toEqual(original);
    expect(first).not.toBe(second);
    expect(first.skills).not.toBe(second.skills);
    expect(first.indexed.skill_index_by_id).not.toBe(
      second.indexed.skill_index_by_id,
    );
    expect(first.indexed.variants_by_id[0]?.skills).not.toBe(
      second.indexed.variants_by_id[0]?.skills,
    );

    input.skills[0]!.skill_id = "skill:changed";
    expect(first.skills[0]?.skill_id).toBe("skill:attack");
  });

  it("requires exact format version and lowercase source hash", () => {
    const badVersion = makeTestCatalog();
    badVersion.format_version = 2;
    expect(() => decodeBrowserSearchCatalog(badVersion)).toThrow(
      "$.format_version",
    );

    const badHash = makeTestCatalog();
    badHash.source_catalog.sha256 = "A".repeat(64);
    expect(() => decodeBrowserSearchCatalog(badHash)).toThrow(
      "$.source_catalog.sha256",
    );
  });

  it("requires globally contiguous part-major variant IDs", () => {
    const input = makeTestCatalog();
    input.equipment_by_part.head[0]!.variant_id = 0;

    expect(() => decodeBrowserSearchCatalog(input)).toThrow(
      "$.equipment_by_part.head[0].variant_id",
    );
    expect(() => decodeBrowserSearchCatalog(input)).toThrow(
      "expected contiguous variant ID 1",
    );
  });

  it("accepts an empty part array for an infeasible Catalog", () => {
    const input = makeTestCatalog();
    input.equipment_by_part.charm = [];
    input.source_catalog.expanded_equipment_count -= 1;

    const decoded = decodeBrowserSearchCatalog(input);

    expect(decoded.equipment_by_part.charm).toEqual([]);
    expect(decoded.indexed.equipment_by_part.charm).toEqual([]);
  });

  it.each([
    {
      name: "out-of-range skill reference",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.equipment_by_part.weapon[0]!.skills = [[99, 1]];
      },
      path: "$.equipment_by_part.weapon[0].skills[0][0]",
    },
    {
      name: "part mismatch",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.equipment_by_part.head[0]!.part = "chest";
      },
      path: "$.equipment_by_part.head[0].part",
    },
    {
      name: "unknown weapon kind",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.equipment_by_part.weapon[0]!.weapon_kind = "laser-sword";
      },
      path: "$.equipment_by_part.weapon[0].weapon_kind",
    },
    {
      name: "unknown slot kind",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.equipment_by_part.head[0]!.slots = [
          ["armor", 2],
          ["armor", 1],
        ];
        const invalid = input.equipment_by_part.head[0]!.slots[1]!;
        invalid[0] = "invalid" as "armor";
      },
      path: "$.equipment_by_part.head[0].slots[1][0]",
    },
    {
      name: "zero contribution level",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.decorations[0]!.skills = [[0, 0]];
      },
      path: "$.decorations[0].skills[0][1]",
    },
    {
      name: "wrong series skill kind",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.equipment_by_part.head[0]!.series_skill_ids = [0];
      },
      path: "$.equipment_by_part.head[0].series_skill_ids[0]",
    },
    {
      name: "duplicate decoration ID",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.decorations[1]!.decoration_id =
          input.decorations[0]!.decoration_id;
      },
      path: "$.decorations[1].decoration_id",
    },
    {
      name: "duplicate skill ID",
      mutate: (input: ReturnType<typeof makeTestCatalog>) => {
        input.skills[1]!.skill_id = input.skills[0]!.skill_id;
      },
      path: "$.skills[1].skill_id",
    },
  ])("rejects $name with a precise path", ({ mutate, path }) => {
    const input = makeTestCatalog();
    mutate(input);

    expect(() => decodeBrowserSearchCatalog(input)).toThrow(path);
  });

  it("rejects unexpected fields as a strict decoder", () => {
    const input = makeTestCatalog() as ReturnType<typeof makeTestCatalog> & {
      extra?: boolean;
    };
    input.extra = true;

    expect(() => decodeBrowserSearchCatalog(input)).toThrow(
      BrowserCatalogDecodeError,
    );
    expect(() => decodeBrowserSearchCatalog(input)).toThrow("$.extra");
  });
});
