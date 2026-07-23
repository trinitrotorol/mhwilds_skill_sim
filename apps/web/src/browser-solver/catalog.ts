import {
  EQUIPMENT_PARTS,
  SKILL_KINDS,
  SLOT_KINDS,
  type BrowserCatalogDecoration,
  type BrowserCatalogEquipmentVariant,
  type BrowserCatalogIndexes,
  type BrowserCatalogSkill,
  type BrowserCatalogSource,
  type CatalogSlot,
  type DecodedBrowserCatalog,
  type EquipmentPart,
  type IndexedDecoration,
  type IndexedEquipmentVariant,
  type IndexedSkillLevel,
  type SkillKind,
  type SlotKind,
} from "./types";

const LOWERCASE_SHA256 = /^[0-9a-f]{64}$/u;
const WEAPON_KINDS = new Set([
  "bow",
  "charge-blade",
  "dual-blades",
  "great-sword",
  "gunlance",
  "hammer",
  "heavy-bowgun",
  "hunting-horn",
  "insect-glaive",
  "lance",
  "light-bowgun",
  "long-sword",
  "switch-axe",
  "sword-shield",
]);

const TOP_LEVEL_KEYS = [
  "format_version",
  "source_catalog",
  "skills",
  "equipment_by_part",
  "decorations",
] as const;
const SOURCE_KEYS = [
  "schema_version",
  "sha256",
  "source_equipment_count",
  "generated_appraisal_charm_count",
  "expanded_equipment_count",
  "decoration_count",
  "skill_count",
] as const;
const SKILL_KEYS = [
  "skill_id",
  "display_name",
  "kind",
  "max_level",
  "required_pieces",
] as const;
const EQUIPMENT_KEYS = [
  "variant_id",
  "equipment_id",
  "display_name",
  "part",
  "weapon_kind",
  "series_skill_id",
  "group_skill_id",
  "series_skill_ids",
  "group_skill_ids",
  "skills",
  "slots",
] as const;
const DECORATION_KEYS = [
  "decoration_id",
  "display_name",
  "required_slot",
  "skills",
] as const;

export class BrowserCatalogDecodeError extends Error {
  constructor(path: string, message: string) {
    super(`${path}: ${message}`);
    this.name = "BrowserCatalogDecodeError";
  }
}

function fail(path: string, message: string): never {
  throw new BrowserCatalogDecodeError(path, message);
}

function asPlainObject(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    fail(path, "expected an object");
  }
  const prototype = Object.getPrototypeOf(value);
  if (prototype !== Object.prototype && prototype !== null) {
    fail(path, "expected a plain object");
  }
  return value as Record<string, unknown>;
}

function assertExactKeys(
  value: Record<string, unknown>,
  expected: readonly string[],
  path: string,
): void {
  const actual = Object.keys(value);
  for (const key of expected) {
    if (!Object.hasOwn(value, key)) {
      fail(`${path}.${key}`, "missing required field");
    }
  }
  for (const key of actual) {
    if (!expected.includes(key)) {
      fail(`${path}.${key}`, "unexpected field");
    }
  }
}

function asArray(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    fail(path, "expected an array");
  }
  return value;
}

function asInteger(
  value: unknown,
  path: string,
  minimum: number,
): number {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < minimum
  ) {
    fail(path, `expected a safe integer >= ${minimum}`);
  }
  return value;
}

function asIdentifier(value: unknown, path: string): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.trim() !== value
  ) {
    fail(path, "expected a non-empty trimmed string");
  }
  return value;
}

function asDisplayName(value: unknown, path: string): string | null {
  if (value === null) {
    return null;
  }
  return asIdentifier(value, path);
}

function asNullableIndex(
  value: unknown,
  path: string,
  skillCount: number,
): number | null {
  if (value === null) {
    return null;
  }
  const index = asInteger(value, path, 0);
  if (index >= skillCount) {
    fail(path, `skill index ${index} is out of range`);
  }
  return index;
}

function decodeSource(value: unknown): BrowserCatalogSource {
  const object = asPlainObject(value, "$.source_catalog");
  assertExactKeys(object, SOURCE_KEYS, "$.source_catalog");
  const sha256 = object.sha256;
  if (typeof sha256 !== "string" || !LOWERCASE_SHA256.test(sha256)) {
    fail(
      "$.source_catalog.sha256",
      "expected a lowercase 64-character SHA-256 hex string",
    );
  }
  return Object.freeze({
    schema_version: asInteger(
      object.schema_version,
      "$.source_catalog.schema_version",
      1,
    ),
    sha256,
    source_equipment_count: asInteger(
      object.source_equipment_count,
      "$.source_catalog.source_equipment_count",
      0,
    ),
    generated_appraisal_charm_count: asInteger(
      object.generated_appraisal_charm_count,
      "$.source_catalog.generated_appraisal_charm_count",
      0,
    ),
    expanded_equipment_count: asInteger(
      object.expanded_equipment_count,
      "$.source_catalog.expanded_equipment_count",
      0,
    ),
    decoration_count: asInteger(
      object.decoration_count,
      "$.source_catalog.decoration_count",
      0,
    ),
    skill_count: asInteger(
      object.skill_count,
      "$.source_catalog.skill_count",
      0,
    ),
  });
}

function decodeSkills(value: unknown): readonly BrowserCatalogSkill[] {
  const entries = asArray(value, "$.skills");
  const seenIds = new Set<string>();
  return Object.freeze(
    entries.map((entry, index) => {
      const path = `$.skills[${index}]`;
      const object = asPlainObject(entry, path);
      assertExactKeys(object, SKILL_KEYS, path);
      const skillId = asIdentifier(object.skill_id, `${path}.skill_id`);
      if (seenIds.has(skillId)) {
        fail(`${path}.skill_id`, `duplicate skill ID ${JSON.stringify(skillId)}`);
      }
      seenIds.add(skillId);

      const kindValue = object.kind;
      if (
        typeof kindValue !== "string" ||
        !SKILL_KINDS.includes(kindValue as SkillKind)
      ) {
        fail(`${path}.kind`, "expected armor, weapon, set, or group");
      }
      const kind = kindValue as SkillKind;
      const maxLevel = asInteger(object.max_level, `${path}.max_level`, 1);
      const requiredPieces = Object.freeze(
        asArray(object.required_pieces, `${path}.required_pieces`).map(
          (required, rankIndex) =>
            asInteger(
              required,
              `${path}.required_pieces[${rankIndex}]`,
              1,
            ),
        ),
      );
      if (kind === "armor" || kind === "weapon") {
        if (requiredPieces.length !== 0) {
          fail(
            `${path}.required_pieces`,
            `${kind} skills must have no piece requirements`,
          );
        }
      } else {
        if (requiredPieces.length !== maxLevel) {
          fail(
            `${path}.required_pieces`,
            "set/group piece requirements must match max_level",
          );
        }
        for (let rankIndex = 1; rankIndex < requiredPieces.length; rankIndex += 1) {
          const previous = requiredPieces[rankIndex - 1];
          const current = requiredPieces[rankIndex];
          if (previous === undefined || current === undefined || current <= previous) {
            fail(
              `${path}.required_pieces[${rankIndex}]`,
              "piece requirements must be strictly increasing",
            );
          }
        }
      }

      return Object.freeze({
        skill_id: skillId,
        display_name: asDisplayName(
          object.display_name,
          `${path}.display_name`,
        ),
        kind,
        max_level: maxLevel,
        required_pieces: requiredPieces,
      });
    }),
  );
}

function decodeSkillLevels(
  value: unknown,
  path: string,
  skillCount: number,
  allowEmpty: boolean,
): readonly IndexedSkillLevel[] {
  const entries = asArray(value, path);
  if (!allowEmpty && entries.length === 0) {
    fail(path, "must not be empty");
  }
  const seen = new Set<number>();
  return Object.freeze(
    entries.map((entry, index) => {
      const entryPath = `${path}[${index}]`;
      const pair = asArray(entry, entryPath);
      if (pair.length !== 2) {
        fail(entryPath, "expected [skill_index, level]");
      }
      const skillIndex = asInteger(pair[0], `${entryPath}[0]`, 0);
      if (skillIndex >= skillCount) {
        fail(`${entryPath}[0]`, `skill index ${skillIndex} is out of range`);
      }
      if (seen.has(skillIndex)) {
        fail(`${entryPath}[0]`, `duplicate skill index ${skillIndex}`);
      }
      seen.add(skillIndex);
      const level = asInteger(pair[1], `${entryPath}[1]`, 1);
      return Object.freeze([skillIndex, level]) as IndexedSkillLevel;
    }),
  );
}

function decodeSlot(value: unknown, path: string): CatalogSlot {
  const pair = asArray(value, path);
  if (pair.length !== 2) {
    fail(path, "expected [slot_kind, level]");
  }
  const kindValue = pair[0];
  if (
    typeof kindValue !== "string" ||
    !SLOT_KINDS.includes(kindValue as SlotKind)
  ) {
    fail(`${path}[0]`, "expected weapon or armor");
  }
  return Object.freeze([
    kindValue as SlotKind,
    asInteger(pair[1], `${path}[1]`, 1),
  ]) as CatalogSlot;
}

function decodeMemberships(
  value: unknown,
  path: string,
  skills: readonly BrowserCatalogSkill[],
  expectedKind: "set" | "group",
): readonly number[] {
  const entries = asArray(value, path);
  const seen = new Set<number>();
  return Object.freeze(
    entries.map((entry, index) => {
      const skillIndex = asInteger(entry, `${path}[${index}]`, 0);
      const skill = skills[skillIndex];
      if (skill === undefined) {
        fail(`${path}[${index}]`, `skill index ${skillIndex} is out of range`);
      }
      if (skill.kind !== expectedKind) {
        fail(
          `${path}[${index}]`,
          `expected a ${expectedKind} skill reference`,
        );
      }
      if (seen.has(skillIndex)) {
        fail(`${path}[${index}]`, `duplicate skill index ${skillIndex}`);
      }
      seen.add(skillIndex);
      return skillIndex;
    }),
  );
}

function decodeEquipment(
  value: unknown,
  skills: readonly BrowserCatalogSkill[],
): {
  readonly raw: Readonly<
    Record<EquipmentPart, readonly BrowserCatalogEquipmentVariant[]>
  >;
  readonly indexedByPart: Readonly<
    Record<EquipmentPart, readonly IndexedEquipmentVariant[]>
  >;
  readonly variantsById: readonly IndexedEquipmentVariant[];
  readonly maximumSlotLevel: number;
} {
  const object = asPlainObject(value, "$.equipment_by_part");
  assertExactKeys(object, EQUIPMENT_PARTS, "$.equipment_by_part");
  const raw = {} as Record<
    EquipmentPart,
    readonly BrowserCatalogEquipmentVariant[]
  >;
  const indexedByPart = {} as Record<
    EquipmentPart,
    readonly IndexedEquipmentVariant[]
  >;
  const variantsById: IndexedEquipmentVariant[] = [];
  let expectedVariantId = 0;
  let maximumSlotLevel = 0;

  for (const part of EQUIPMENT_PARTS) {
    const partPath = `$.equipment_by_part.${part}`;
    const entries = asArray(object[part], partPath);
    const rawPart: BrowserCatalogEquipmentVariant[] = [];
    const indexedPart: IndexedEquipmentVariant[] = [];
    for (let index = 0; index < entries.length; index += 1) {
      const path = `${partPath}[${index}]`;
      const entry = asPlainObject(entries[index], path);
      assertExactKeys(entry, EQUIPMENT_KEYS, path);
      const variantId = asInteger(entry.variant_id, `${path}.variant_id`, 0);
      if (variantId !== expectedVariantId) {
        fail(
          `${path}.variant_id`,
          `expected contiguous variant ID ${expectedVariantId}`,
        );
      }
      expectedVariantId += 1;
      const entryPart = entry.part;
      if (
        typeof entryPart !== "string" ||
        !EQUIPMENT_PARTS.includes(entryPart as EquipmentPart)
      ) {
        fail(`${path}.part`, "unknown equipment part");
      }
      if (entryPart !== part) {
        fail(`${path}.part`, `expected ${part}`);
      }

      const weaponKindValue = entry.weapon_kind;
      let weaponKind: string | null;
      if (weaponKindValue === null) {
        weaponKind = null;
      } else {
        weaponKind = asIdentifier(weaponKindValue, `${path}.weapon_kind`);
        if (!WEAPON_KINDS.has(weaponKind)) {
          fail(`${path}.weapon_kind`, "unknown weapon kind");
        }
      }
      if (part !== "weapon" && weaponKind !== null) {
        fail(`${path}.weapon_kind`, "only weapon equipment may have a weapon kind");
      }

      const seriesSkillId = asNullableIndex(
        entry.series_skill_id,
        `${path}.series_skill_id`,
        skills.length,
      );
      if (
        seriesSkillId !== null &&
        skills[seriesSkillId]?.kind !== "set"
      ) {
        fail(`${path}.series_skill_id`, "expected a set skill reference");
      }
      const groupSkillId = asNullableIndex(
        entry.group_skill_id,
        `${path}.group_skill_id`,
        skills.length,
      );
      if (
        groupSkillId !== null &&
        skills[groupSkillId]?.kind !== "group"
      ) {
        fail(`${path}.group_skill_id`, "expected a group skill reference");
      }
      const seriesSkillIds = decodeMemberships(
        entry.series_skill_ids,
        `${path}.series_skill_ids`,
        skills,
        "set",
      );
      const groupSkillIds = decodeMemberships(
        entry.group_skill_ids,
        `${path}.group_skill_ids`,
        skills,
        "group",
      );
      if (
        seriesSkillId !== null &&
        !seriesSkillIds.includes(seriesSkillId)
      ) {
        fail(
          `${path}.series_skill_ids`,
          "must include series_skill_id",
        );
      }
      if (groupSkillId !== null && !groupSkillIds.includes(groupSkillId)) {
        fail(`${path}.group_skill_ids`, "must include group_skill_id");
      }

      const skillLevels = decodeSkillLevels(
        entry.skills,
        `${path}.skills`,
        skills.length,
        true,
      );
      const slots = Object.freeze(
        asArray(entry.slots, `${path}.slots`).map((slot, slotIndex) => {
          const decoded = decodeSlot(slot, `${path}.slots[${slotIndex}]`);
          maximumSlotLevel = Math.max(maximumSlotLevel, decoded[1]);
          return decoded;
        }),
      );
      const definition: BrowserCatalogEquipmentVariant = Object.freeze({
        variant_id: variantId,
        equipment_id: asIdentifier(
          entry.equipment_id,
          `${path}.equipment_id`,
        ),
        display_name: asDisplayName(
          entry.display_name,
          `${path}.display_name`,
        ),
        part,
        weapon_kind: weaponKind,
        series_skill_id: seriesSkillId,
        group_skill_id: groupSkillId,
        series_skill_ids: seriesSkillIds,
        group_skill_ids: groupSkillIds,
        skills: skillLevels,
        slots,
      });
      const indexed: IndexedEquipmentVariant = Object.freeze({
        definition,
        skills: Int32Array.from(skillLevels.flatMap(([skill, level]) => [
          skill,
          level,
        ])),
        series_skill_ids: Int32Array.from(seriesSkillIds),
        group_skill_ids: Int32Array.from(groupSkillIds),
        slots: Int32Array.from(
          slots.flatMap(([kind, level]) => [kind === "weapon" ? 0 : 1, level]),
        ),
      });
      rawPart.push(definition);
      indexedPart.push(indexed);
      variantsById.push(indexed);
    }
    raw[part] = Object.freeze(rawPart);
    indexedByPart[part] = Object.freeze(indexedPart);
  }

  return Object.freeze({
    raw: Object.freeze(raw),
    indexedByPart: Object.freeze(indexedByPart),
    variantsById: Object.freeze(variantsById),
    maximumSlotLevel,
  });
}

function decodeDecorations(
  value: unknown,
  skills: readonly BrowserCatalogSkill[],
): {
  readonly raw: readonly BrowserCatalogDecoration[];
  readonly indexed: readonly IndexedDecoration[];
  readonly indexById: ReadonlyMap<string, number>;
  readonly maximumSlotLevel: number;
} {
  const entries = asArray(value, "$.decorations");
  const seenIds = new Set<string>();
  const raw: BrowserCatalogDecoration[] = [];
  const indexed: IndexedDecoration[] = [];
  const indexById = new Map<string, number>();
  let maximumSlotLevel = 0;
  for (let index = 0; index < entries.length; index += 1) {
    const path = `$.decorations[${index}]`;
    const object = asPlainObject(entries[index], path);
    assertExactKeys(object, DECORATION_KEYS, path);
    const decorationId = asIdentifier(
      object.decoration_id,
      `${path}.decoration_id`,
    );
    if (seenIds.has(decorationId)) {
      fail(
        `${path}.decoration_id`,
        `duplicate decoration ID ${JSON.stringify(decorationId)}`,
      );
    }
    seenIds.add(decorationId);
    indexById.set(decorationId, index);
    const requiredSlot = decodeSlot(
      object.required_slot,
      `${path}.required_slot`,
    );
    maximumSlotLevel = Math.max(maximumSlotLevel, requiredSlot[1]);
    const skillLevels = decodeSkillLevels(
      object.skills,
      `${path}.skills`,
      skills.length,
      false,
    );
    const definition: BrowserCatalogDecoration = Object.freeze({
      decoration_id: decorationId,
      display_name: asDisplayName(
        object.display_name,
        `${path}.display_name`,
      ),
      required_slot: requiredSlot,
      skills: skillLevels,
    });
    raw.push(definition);
    indexed.push(
      Object.freeze({
        definition,
        decoration_index: index,
        required_slot_kind: requiredSlot[0] === "weapon" ? 0 : 1,
        required_slot_level: requiredSlot[1],
        skills: Int32Array.from(
          skillLevels.flatMap(([skill, level]) => [skill, level]),
        ),
      }),
    );
  }
  return Object.freeze({
    raw: Object.freeze(raw),
    indexed: Object.freeze(indexed),
    indexById,
    maximumSlotLevel,
  });
}

/**
 * Decode and index a compact browser Catalog without retaining or mutating any
 * mutable array from the input value.
 */
export function decodeBrowserSearchCatalog(
  value: unknown,
): DecodedBrowserCatalog {
  const object = asPlainObject(value, "$");
  assertExactKeys(object, TOP_LEVEL_KEYS, "$");
  if (object.format_version !== 1) {
    fail("$.format_version", "expected exact format version 1");
  }
  const source = decodeSource(object.source_catalog);
  const skills = decodeSkills(object.skills);
  const skillIndexById = new Map<string, number>(
    skills.map((skill, index) => [skill.skill_id, index]),
  );
  const equipment = decodeEquipment(object.equipment_by_part, skills);
  const decorations = decodeDecorations(object.decorations, skills);

  if (source.skill_count !== skills.length) {
    fail(
      "$.source_catalog.skill_count",
      `expected ${skills.length} from skills`,
    );
  }
  if (source.decoration_count !== decorations.raw.length) {
    fail(
      "$.source_catalog.decoration_count",
      `expected ${decorations.raw.length} from decorations`,
    );
  }
  if (source.expanded_equipment_count !== equipment.variantsById.length) {
    fail(
      "$.source_catalog.expanded_equipment_count",
      `expected ${equipment.variantsById.length} from equipment_by_part`,
    );
  }

  const indexes: BrowserCatalogIndexes = Object.freeze({
    skill_index_by_id: skillIndexById,
    decoration_index_by_id: decorations.indexById,
    variants_by_id: equipment.variantsById,
    equipment_by_part: equipment.indexedByPart,
    decorations: decorations.indexed,
    maximum_slot_level: Math.max(
      equipment.maximumSlotLevel,
      decorations.maximumSlotLevel,
    ),
  });
  return Object.freeze({
    format_version: 1 as const,
    source_catalog: source,
    skills,
    equipment_by_part: equipment.raw,
    decorations: decorations.raw,
    indexed: indexes,
  });
}
