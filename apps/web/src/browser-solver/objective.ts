import type {
  BrowserRankedSearchRequest,
  BrowserRankedSearchRequirement,
  BrowserRankedSearchPreference,
  DecodedBrowserCatalog,
  SkillLevelResponse,
} from "./types";

export interface RequestProjection {
  readonly skill_indices: Int32Array;
  readonly catalog_to_projection: Int32Array;
  readonly requirement_levels: Float64Array;
  readonly preference_targets: Float64Array;
  readonly level_caps: Float64Array;
  readonly unknown_required_skill: boolean;
  readonly maximum_preference_score: number;
}

export interface SearchObjective {
  readonly preference_score: number;
  readonly decoration_count: number;
  readonly selected_variant_ids: readonly number[];
  readonly decoration_indices: readonly number[];
  readonly decoration_id_ranks: readonly number[];
}

function safeSum(left: number, right: number, field: string): number {
  const result = left + right;
  if (!Number.isSafeInteger(result)) {
    throw new RangeError(`${field} exceeds the safe integer range`);
  }
  return result;
}

export function createRequestProjection(
  catalog: DecodedBrowserCatalog,
  request: BrowserRankedSearchRequest,
): RequestProjection {
  const requirementsByIndex = new Map<number, number>();
  const preferencesByIndex = new Map<number, number>();
  let unknownRequiredSkill = false;
  let maximumPreferenceScore = 0;

  for (const requirement of request.requirements) {
    const skillIndex = catalog.indexed.skill_index_by_id.get(
      requirement.skill_id,
    );
    if (skillIndex === undefined) {
      unknownRequiredSkill = true;
    } else {
      requirementsByIndex.set(skillIndex, requirement.min_level);
    }
  }
  for (const preference of request.preferences) {
    const skillIndex = catalog.indexed.skill_index_by_id.get(
      preference.skill_id,
    );
    if (skillIndex !== undefined) {
      preferencesByIndex.set(skillIndex, preference.target_level);
      maximumPreferenceScore = safeSum(
        maximumPreferenceScore,
        preference.target_level,
        "maximum preference score",
      );
    }
  }

  const skillIndices = Array.from(
    new Set([...requirementsByIndex.keys(), ...preferencesByIndex.keys()]),
  ).sort((left, right) => left - right);
  const catalogToProjection = new Int32Array(catalog.skills.length);
  catalogToProjection.fill(-1);
  const requirementLevels = new Float64Array(skillIndices.length);
  const preferenceTargets = new Float64Array(skillIndices.length);
  const levelCaps = new Float64Array(skillIndices.length);
  for (let index = 0; index < skillIndices.length; index += 1) {
    const skillIndex = skillIndices[index];
    if (skillIndex === undefined) {
      throw new Error("request projection index is missing");
    }
    catalogToProjection[skillIndex] = index;
    requirementLevels[index] = requirementsByIndex.get(skillIndex) ?? 0;
    preferenceTargets[index] = preferencesByIndex.get(skillIndex) ?? 0;
    levelCaps[index] = Math.max(
      requirementLevels[index] ?? 0,
      preferenceTargets[index] ?? 0,
    );
  }

  return Object.freeze({
    skill_indices: Int32Array.from(skillIndices),
    catalog_to_projection: catalogToProjection,
    requirement_levels: requirementLevels,
    preference_targets: preferenceTargets,
    level_caps: levelCaps,
    unknown_required_skill: unknownRequiredSkill,
    maximum_preference_score: maximumPreferenceScore,
  });
}

export function projectedRequirementsSatisfied(
  levels: ArrayLike<number>,
  projection: RequestProjection,
): boolean {
  for (let index = 0; index < projection.requirement_levels.length; index += 1) {
    if (
      (levels[index] ?? 0) <
      (projection.requirement_levels[index] ?? 0)
    ) {
      return false;
    }
  }
  return !projection.unknown_required_skill;
}

export function calculateProjectedPreferenceScore(
  levels: ArrayLike<number>,
  projection: RequestProjection,
): number {
  let score = 0;
  for (let index = 0; index < projection.preference_targets.length; index += 1) {
    score = safeSum(
      score,
      Math.min(
        levels[index] ?? 0,
        projection.preference_targets[index] ?? 0,
      ),
      "preference score",
    );
  }
  return score;
}

function skillLevelMap(
  skillLevels: ReadonlyArray<SkillLevelResponse>,
): ReadonlyMap<string, number> {
  const result = new Map<string, number>();
  for (const skillLevel of skillLevels) {
    result.set(skillLevel.skill_id, skillLevel.level);
  }
  return result;
}

export function skillLevelsSatisfyBrowserRequirements(
  skillLevels: ReadonlyArray<SkillLevelResponse>,
  requirements: ReadonlyArray<BrowserRankedSearchRequirement>,
): boolean {
  const levels = skillLevelMap(skillLevels);
  return requirements.every(
    (requirement) =>
      (levels.get(requirement.skill_id) ?? 0) >= requirement.min_level,
  );
}

export function calculateBrowserPreferenceScore(
  skillLevels: ReadonlyArray<SkillLevelResponse>,
  preferences: ReadonlyArray<BrowserRankedSearchPreference>,
): number {
  const levels = skillLevelMap(skillLevels);
  let score = 0;
  for (const preference of preferences) {
    score = safeSum(
      score,
      Math.min(
        levels.get(preference.skill_id) ?? 0,
        preference.target_level,
      ),
      "preference score",
    );
  }
  return score;
}

export function compareNumberArraysLexicographically(
  left: readonly number[],
  right: readonly number[],
): number {
  const length = Math.min(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    const leftValue = left[index];
    const rightValue = right[index];
    if (leftValue === undefined || rightValue === undefined) {
      throw new Error("lexicographic comparison encountered a missing value");
    }
    if (leftValue !== rightValue) {
      return leftValue < rightValue ? -1 : 1;
    }
  }
  return left.length - right.length;
}

/**
 * Return a negative value when `left` ranks ahead of `right`.
 */
export function compareSearchObjectives(
  left: SearchObjective,
  right: SearchObjective,
): number {
  if (left.preference_score !== right.preference_score) {
    return right.preference_score - left.preference_score;
  }
  if (left.decoration_count !== right.decoration_count) {
    return left.decoration_count - right.decoration_count;
  }
  const variantOrder = compareNumberArraysLexicographically(
    left.selected_variant_ids,
    right.selected_variant_ids,
  );
  if (variantOrder !== 0) {
    return variantOrder;
  }
  return compareNumberArraysLexicographically(
    left.decoration_id_ranks,
    right.decoration_id_ranks,
  );
}
