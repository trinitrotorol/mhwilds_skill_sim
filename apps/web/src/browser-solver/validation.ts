import { reconstructDecorationPlacements } from "./decoration";
import {
  calculateBrowserPreferenceScore,
  skillLevelsSatisfyBrowserRequirements,
} from "./objective";
import {
  EQUIPMENT_PARTS,
  type BrowserRankedSearchPreference,
  type BrowserRankedSearchRequest,
  type BrowserRankedSearchRequirement,
  type BrowserSolverResult,
  type CandidateValidationSummary,
  type DecodedBrowserCatalog,
  type EquipmentResponse,
  type IndexedEquipmentVariant,
  type RankedBuildCandidate,
  type SkillLevelResponse,
} from "./types";

export class BrowserSolverValidationError extends Error {
  constructor(path: string, message: string) {
    super(`${path}: ${message}`);
    this.name = "BrowserSolverValidationError";
  }
}

function fail(path: string, message: string): never {
  throw new BrowserSolverValidationError(path, message);
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

function exactKeys(
  value: Record<string, unknown>,
  required: readonly string[],
  optional: readonly string[],
  path: string,
): void {
  for (const key of required) {
    if (!Object.hasOwn(value, key)) {
      fail(`${path}.${key}`, "missing required field");
    }
  }
  const allowed = new Set([...required, ...optional]);
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) {
      fail(`${path}.${key}`, "unexpected field");
    }
  }
}

function identifier(value: unknown, path: string): string {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value.trim() !== value
  ) {
    fail(path, "expected a non-empty trimmed string");
  }
  return value;
}

function positiveInteger(value: unknown, path: string): number {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < 1
  ) {
    fail(path, "expected a positive safe integer");
  }
  return value;
}

function decodeRequirements(
  value: unknown,
): readonly BrowserRankedSearchRequirement[] {
  if (!Array.isArray(value)) {
    fail("$.requirements", "expected an array");
  }
  const seen = new Set<string>();
  return Object.freeze(
    value.map((entry, index) => {
      const path = `$.requirements[${index}]`;
      const object = asPlainObject(entry, path);
      exactKeys(object, ["skill_id", "min_level"], [], path);
      const skillId = identifier(object.skill_id, `${path}.skill_id`);
      if (seen.has(skillId)) {
        fail(`${path}.skill_id`, `duplicate skill ID ${JSON.stringify(skillId)}`);
      }
      seen.add(skillId);
      return Object.freeze({
        skill_id: skillId,
        min_level: positiveInteger(object.min_level, `${path}.min_level`),
      });
    }),
  );
}

function decodePreferences(
  value: unknown,
): readonly BrowserRankedSearchPreference[] {
  if (!Array.isArray(value)) {
    fail("$.preferences", "expected an array");
  }
  const seen = new Set<string>();
  return Object.freeze(
    value.map((entry, index) => {
      const path = `$.preferences[${index}]`;
      const object = asPlainObject(entry, path);
      exactKeys(object, ["skill_id", "target_level"], [], path);
      const skillId = identifier(object.skill_id, `${path}.skill_id`);
      if (seen.has(skillId)) {
        fail(`${path}.skill_id`, `duplicate skill ID ${JSON.stringify(skillId)}`);
      }
      seen.add(skillId);
      return Object.freeze({
        skill_id: skillId,
        target_level: positiveInteger(
          object.target_level,
          `${path}.target_level`,
        ),
      });
    }),
  );
}

export function decodeBrowserRankedSearchRequest(
  value: unknown,
): BrowserRankedSearchRequest {
  const object = asPlainObject(value, "$");
  exactKeys(
    object,
    ["requirements", "preferences", "max_results"],
    ["weapon_kind"],
    "$",
  );
  if (object.max_results !== 1) {
    fail("$.max_results", "expected exact value 1");
  }
  const weaponKind =
    object.weapon_kind === undefined
      ? undefined
      : identifier(object.weapon_kind, "$.weapon_kind");
  const decoded: BrowserRankedSearchRequest = {
    requirements: decodeRequirements(object.requirements),
    preferences: decodePreferences(object.preferences),
    max_results: 1,
  };
  if (weaponKind !== undefined) {
    return Object.freeze({ ...decoded, weapon_kind: weaponKind });
  }
  return Object.freeze(decoded);
}

function safeAdd(current: number, addition: number, field: string): number {
  const result = current + addition;
  if (!Number.isSafeInteger(result)) {
    throw new RangeError(`${field} exceeds the safe integer range`);
  }
  return result;
}

function selectedVariants(
  catalog: DecodedBrowserCatalog,
  selectedVariantIds: ReadonlyArray<number>,
): IndexedEquipmentVariant[] {
  if (selectedVariantIds.length !== EQUIPMENT_PARTS.length) {
    fail(
      "$.selected_variant_ids",
      `expected exactly ${EQUIPMENT_PARTS.length} variant IDs`,
    );
  }
  return selectedVariantIds.map((variantId, index) => {
    if (!Number.isSafeInteger(variantId) || variantId < 0) {
      fail(`$.selected_variant_ids[${index}]`, "expected a nonnegative safe integer");
    }
    const variant = catalog.indexed.variants_by_id[variantId];
    if (variant === undefined) {
      fail(`$.selected_variant_ids[${index}]`, "unknown variant ID");
    }
    if (variant.definition.part !== EQUIPMENT_PARTS[index]) {
      fail(
        `$.selected_variant_ids[${index}]`,
        `expected ${EQUIPMENT_PARTS[index]} equipment`,
      );
    }
    return variant;
  });
}

export function equipmentVariantToResponse(
  catalog: DecodedBrowserCatalog,
  variant: IndexedEquipmentVariant,
): EquipmentResponse {
  const definition = variant.definition;
  const skillId = (index: number): string => {
    const skill = catalog.skills[index];
    if (skill === undefined) {
      throw new Error(`unknown indexed skill ${index}`);
    }
    return skill.skill_id;
  };
  return {
    equipment_id: definition.equipment_id,
    display_name: definition.display_name,
    part: definition.part,
    weapon_kind: definition.weapon_kind,
    series_skill_id:
      definition.series_skill_id === null
        ? null
        : skillId(definition.series_skill_id),
    group_skill_id:
      definition.group_skill_id === null
        ? null
        : skillId(definition.group_skill_id),
    series_skill_ids: definition.series_skill_ids.map(skillId),
    group_skill_ids: definition.group_skill_ids.map(skillId),
    skills: definition.skills.map(([index, level]) => ({
      skill_id: skillId(index),
      level,
    })),
    slots: definition.slots.map(([kind, level]) => ({ kind, level })),
  };
}

export function aggregateSelectedBuildSkillLevels(
  catalog: DecodedBrowserCatalog,
  selectedEquipment: ReadonlyArray<IndexedEquipmentVariant>,
  decorationIndices: ReadonlyArray<number>,
): SkillLevelResponse[] {
  const totals = new Float64Array(catalog.skills.length);
  for (const equipment of selectedEquipment) {
    for (let index = 0; index < equipment.skills.length; index += 2) {
      const skillIndex = equipment.skills[index];
      const level = equipment.skills[index + 1];
      if (skillIndex === undefined || level === undefined) {
        throw new Error("indexed equipment skill pair is incomplete");
      }
      totals[skillIndex] = safeAdd(
        totals[skillIndex] ?? 0,
        level,
        "skill level",
      );
    }
  }

  const seriesCounts = new Uint8Array(catalog.skills.length);
  const groupCounts = new Uint8Array(catalog.skills.length);
  for (const equipment of selectedEquipment) {
    for (const skillIndex of equipment.series_skill_ids) {
      seriesCounts[skillIndex] = (seriesCounts[skillIndex] ?? 0) + 1;
    }
    for (const skillIndex of equipment.group_skill_ids) {
      groupCounts[skillIndex] = (groupCounts[skillIndex] ?? 0) + 1;
    }
  }
  for (let skillIndex = 0; skillIndex < catalog.skills.length; skillIndex += 1) {
    const skill = catalog.skills[skillIndex];
    if (skill === undefined || (skill.kind !== "set" && skill.kind !== "group")) {
      continue;
    }
    const pieces =
      skill.kind === "set"
        ? seriesCounts[skillIndex] ?? 0
        : groupCounts[skillIndex] ?? 0;
    let activatedLevel = 0;
    for (let rank = 0; rank < skill.required_pieces.length; rank += 1) {
      if ((skill.required_pieces[rank] ?? Number.POSITIVE_INFINITY) <= pieces) {
        activatedLevel = rank + 1;
      }
    }
    if (activatedLevel > 0) {
      totals[skillIndex] = safeAdd(
        totals[skillIndex] ?? 0,
        activatedLevel,
        "skill level",
      );
    }
  }

  for (const decorationIndex of decorationIndices) {
    const decoration = catalog.indexed.decorations[decorationIndex];
    if (decoration === undefined) {
      fail("$.candidate.placements", `unknown decoration index ${decorationIndex}`);
    }
    for (let index = 0; index < decoration.skills.length; index += 2) {
      const skillIndex = decoration.skills[index];
      const level = decoration.skills[index + 1];
      if (skillIndex === undefined || level === undefined) {
        throw new Error("indexed decoration skill pair is incomplete");
      }
      totals[skillIndex] = safeAdd(
        totals[skillIndex] ?? 0,
        level,
        "skill level",
      );
    }
  }

  const result: SkillLevelResponse[] = [];
  for (let skillIndex = 0; skillIndex < totals.length; skillIndex += 1) {
    const level = totals[skillIndex] ?? 0;
    if (level > 0) {
      const skill = catalog.skills[skillIndex];
      if (skill === undefined) {
        throw new Error("aggregated skill is missing from the catalog");
      }
      result.push({ skill_id: skill.skill_id, level });
    }
  }
  return result;
}

function assertJsonEqual(actual: unknown, expected: unknown, path: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    fail(path, "does not match the selected compact Catalog variant");
  }
}

function validateCandidateShape(candidate: unknown): RankedBuildCandidate {
  const object = asPlainObject(candidate, "$.candidate");
  exactKeys(
    object,
    ["equipment", "placements", "skill_levels", "preference_score"],
    [],
    "$.candidate",
  );
  if (
    !Array.isArray(object.equipment) ||
    !Array.isArray(object.placements) ||
    !Array.isArray(object.skill_levels)
  ) {
    fail("$.candidate", "equipment, placements, and skill_levels must be arrays");
  }
  if (
    typeof object.preference_score !== "number" ||
    !Number.isSafeInteger(object.preference_score) ||
    object.preference_score < 0
  ) {
    fail("$.candidate.preference_score", "expected a nonnegative safe integer");
  }
  return object as unknown as RankedBuildCandidate;
}

export function validateRankedBuildCandidate(
  catalog: DecodedBrowserCatalog,
  requestValue: BrowserRankedSearchRequest,
  candidateValue: RankedBuildCandidate,
  selectedVariantIds: ReadonlyArray<number>,
): CandidateValidationSummary {
  const request = decodeBrowserRankedSearchRequest(requestValue);
  const candidate = validateCandidateShape(candidateValue);
  const selected = selectedVariants(catalog, selectedVariantIds);
  if (
    request.weapon_kind !== undefined &&
    selected[0]?.definition.weapon_kind !== request.weapon_kind
  ) {
    fail(
      "$.candidate.equipment[0].weapon_kind",
      `expected ${request.weapon_kind}`,
    );
  }
  if (candidate.equipment.length !== EQUIPMENT_PARTS.length) {
    fail("$.candidate.equipment", "expected exactly seven equipment entries");
  }
  assertJsonEqual(
    candidate.equipment,
    selected.map((variant) => equipmentVariantToResponse(catalog, variant)),
    "$.candidate.equipment",
  );
  const equipmentIds = new Set(selected.map(({ definition }) => definition.equipment_id));
  if (equipmentIds.size !== selected.length) {
    fail("$.candidate.equipment", "selected equipment IDs must be unique");
  }

  const decorationIndices: number[] = [];
  const seenSlots = new Set<string>();
  for (let index = 0; index < candidate.placements.length; index += 1) {
    const path = `$.candidate.placements[${index}]`;
    const placement = asPlainObject(candidate.placements[index], path);
    exactKeys(
      placement,
      ["equipment_id", "slot_index", "decoration_id"],
      [],
      path,
    );
    const equipmentId = identifier(
      placement.equipment_id,
      `${path}.equipment_id`,
    );
    const equipmentIndex = selected.findIndex(
      ({ definition }) => definition.equipment_id === equipmentId,
    );
    if (equipmentIndex < 0) {
      fail(`${path}.equipment_id`, "unknown selected equipment ID");
    }
    const slotIndex = placement.slot_index;
    if (
      typeof slotIndex !== "number" ||
      !Number.isSafeInteger(slotIndex) ||
      slotIndex < 0
    ) {
      fail(`${path}.slot_index`, "expected a nonnegative safe integer");
    }
    const equipment = selected[equipmentIndex];
    if (equipment === undefined || slotIndex * 2 + 1 >= equipment.slots.length) {
      fail(`${path}.slot_index`, "slot index is out of range");
    }
    const slotKey = `${equipmentIndex}:${slotIndex}`;
    if (seenSlots.has(slotKey)) {
      fail(path, "equipment slot is used more than once");
    }
    seenSlots.add(slotKey);
    const decorationId = identifier(
      placement.decoration_id,
      `${path}.decoration_id`,
    );
    const decorationIndex =
      catalog.indexed.decoration_index_by_id.get(decorationId);
    if (decorationIndex === undefined) {
      fail(`${path}.decoration_id`, "unknown decoration ID");
    }
    const decoration = catalog.indexed.decorations[decorationIndex];
    const slotKind = equipment.slots[slotIndex * 2];
    const slotLevel = equipment.slots[slotIndex * 2 + 1];
    if (
      decoration === undefined ||
      slotKind !== decoration.required_slot_kind ||
      slotLevel === undefined ||
      slotLevel < decoration.required_slot_level
    ) {
      fail(path, "decoration is incompatible with the selected slot");
    }
    decorationIndices.push(decorationIndex);
  }
  decorationIndices.sort((left, right) => {
    const leftId = catalog.decorations[left]?.decoration_id;
    const rightId = catalog.decorations[right]?.decoration_id;
    if (leftId === undefined || rightId === undefined) {
      throw new Error("candidate decoration is missing from the catalog");
    }
    return leftId < rightId ? -1 : leftId > rightId ? 1 : 0;
  });
  assertJsonEqual(
    candidate.placements,
    reconstructDecorationPlacements(catalog, selected, decorationIndices),
    "$.candidate.placements",
  );

  const skillLevels = aggregateSelectedBuildSkillLevels(
    catalog,
    selected,
    decorationIndices,
  );
  assertJsonEqual(candidate.skill_levels, skillLevels, "$.candidate.skill_levels");
  if (!skillLevelsSatisfyBrowserRequirements(skillLevels, request.requirements)) {
    fail("$.candidate.skill_levels", "hard requirements are not satisfied");
  }
  const preferenceScore = calculateBrowserPreferenceScore(
    skillLevels,
    request.preferences,
  );
  if (candidate.preference_score !== preferenceScore) {
    fail("$.candidate.preference_score", `expected ${preferenceScore}`);
  }
  return Object.freeze({
    preference_score: preferenceScore,
    decoration_count: decorationIndices.length,
    skill_levels: Object.freeze(skillLevels),
  });
}

function nonnegativeCounter(value: unknown, path: string): void {
  if (
    typeof value !== "number" ||
    !Number.isSafeInteger(value) ||
    value < 0
  ) {
    fail(path, "expected a nonnegative safe integer");
  }
}

export function validateBrowserSolverResult(
  catalog: DecodedBrowserCatalog,
  requestValue: BrowserRankedSearchRequest,
  resultValue: BrowserSolverResult,
): void {
  const request = decodeBrowserRankedSearchRequest(requestValue);
  const result = asPlainObject(resultValue, "$");
  exactKeys(
    result,
    [
      "status",
      "candidate",
      "selected_variant_ids",
      "preference_score",
      "decoration_count",
      "elapsed_ms",
      "visited_nodes",
      "pruned_nodes",
      "complete_equipment_selections",
    ],
    [],
    "$",
  );
  if (
    result.status !== "optimal" &&
    result.status !== "infeasible" &&
    result.status !== "timed-out" &&
    result.status !== "cancelled"
  ) {
    fail("$.status", "unknown solver status");
  }
  if (
    typeof result.elapsed_ms !== "number" ||
    !Number.isFinite(result.elapsed_ms) ||
    result.elapsed_ms < 0
  ) {
    fail("$.elapsed_ms", "expected a finite nonnegative number");
  }
  nonnegativeCounter(result.visited_nodes, "$.visited_nodes");
  nonnegativeCounter(result.pruned_nodes, "$.pruned_nodes");
  nonnegativeCounter(
    result.complete_equipment_selections,
    "$.complete_equipment_selections",
  );
  if (!Array.isArray(result.selected_variant_ids)) {
    fail("$.selected_variant_ids", "expected an array");
  }

  if (result.candidate === null) {
    if (result.selected_variant_ids.length !== 0) {
      fail("$.selected_variant_ids", "must be empty without a candidate");
    }
    if (result.preference_score !== null || result.decoration_count !== null) {
      fail("$", "objective fields must be null without a candidate");
    }
    if (result.status === "optimal") {
      fail("$.status", "optimal status requires a candidate");
    }
    if (result.status === "infeasible") {
      return;
    }
  } else {
    if (result.status === "infeasible") {
      fail("$.status", "infeasible status cannot include a candidate");
    }
    const summary = validateRankedBuildCandidate(
      catalog,
      request,
      result.candidate as RankedBuildCandidate,
      result.selected_variant_ids as number[],
    );
    if (result.preference_score !== summary.preference_score) {
      fail("$.preference_score", `expected ${summary.preference_score}`);
    }
    if (result.decoration_count !== summary.decoration_count) {
      fail("$.decoration_count", `expected ${summary.decoration_count}`);
    }
  }
  // This also rejects BigInt and cyclic structures. Generated results contain
  // plain JSON values only; no parsed result depends on class identity.
  try {
    JSON.stringify(resultValue);
  } catch {
    fail("$", "result must be JSON serializable");
  }
}
