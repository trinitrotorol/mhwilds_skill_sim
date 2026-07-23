import {
  createDecorationProjection,
  reconstructDecorationPlacements,
  solveProjectedDecorations,
  type DecorationProjection,
  type DecorationSolution,
} from "./decoration";
import {
  calculateProjectedPreferenceScore,
  compareSearchObjectives,
  createRequestProjection,
  type RequestProjection,
  type SearchObjective,
} from "./objective";
import {
  EQUIPMENT_PARTS,
  type BrowserRankedSearchRequest,
  type BrowserSolverOptions,
  type BrowserSolverProgress,
  type BrowserSolverResult,
  type BrowserSolverStatus,
  type CatalogSlot,
  type DecodedBrowserCatalog,
  type IndexedEquipmentVariant,
  type RankedBuildCandidate,
} from "./types";
import {
  aggregateSelectedBuildSkillLevels,
  decodeBrowserRankedSearchRequest,
  equipmentVariantToResponse,
  validateBrowserSolverResult,
} from "./validation";

export const SEARCH_CONTROL_CHECK_INTERVAL = 1_024;
const DEFAULT_TIMEOUT_MS = 10_000;
const COUNTER_MAX = Number.MAX_SAFE_INTEGER;

interface BonusProjection {
  readonly catalog_skill_indices: Int32Array;
  readonly projected_indices: Int32Array;
  readonly required_pieces: ReadonlyArray<ReadonlyArray<number>>;
  readonly catalog_to_bonus: Int32Array;
}

interface ProjectedVariant {
  readonly equipment: IndexedEquipmentVariant;
  readonly fixed_levels: Float64Array;
  readonly memberships: Uint8Array;
  readonly slot_capacities: Uint16Array;
  readonly slot_count: number;
}

interface PreparedSearch {
  readonly candidates_by_part: ReadonlyArray<
    ReadonlyArray<ProjectedVariant>
  >;
  readonly remaining_max_fixed: ReadonlyArray<Float64Array>;
  readonly remaining_max_memberships: ReadonlyArray<Uint8Array>;
  readonly remaining_max_slot_count: Uint16Array;
  readonly max_decoration_contribution: Float64Array;
}

interface Incumbent {
  readonly selected_equipment: ReadonlyArray<IndexedEquipmentVariant>;
  readonly decoration_solution: DecorationSolution;
  readonly objective: SearchObjective;
}

interface MutableCounters {
  visited_nodes: number;
  pruned_nodes: number;
  complete_equipment_selections: number;
}

function incrementCounter(value: number): number {
  return value >= COUNTER_MAX ? COUNTER_MAX : value + 1;
}

function defaultNow(): number {
  return globalThis.performance?.now() ?? Date.now();
}

function validateOptions(options: BrowserSolverOptions): {
  readonly timeoutMs: number;
  readonly now: () => number;
  readonly shouldCancel: () => boolean;
  readonly onProgress: ((progress: BrowserSolverProgress) => void) | undefined;
} {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  if (
    typeof timeoutMs !== "number" ||
    !Number.isFinite(timeoutMs) ||
    timeoutMs < 0
  ) {
    throw new TypeError("timeoutMs must be a finite nonnegative number");
  }
  if (options.now !== undefined && typeof options.now !== "function") {
    throw new TypeError("now must be a function");
  }
  if (
    options.shouldCancel !== undefined &&
    typeof options.shouldCancel !== "function"
  ) {
    throw new TypeError("shouldCancel must be a function");
  }
  if (
    options.onProgress !== undefined &&
    typeof options.onProgress !== "function"
  ) {
    throw new TypeError("onProgress must be a function");
  }
  return Object.freeze({
    timeoutMs,
    now: options.now ?? defaultNow,
    shouldCancel: options.shouldCancel ?? (() => false),
    onProgress: options.onProgress,
  });
}

function readClock(now: () => number): number {
  const value = now();
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError("now must return a finite number");
  }
  return value;
}

function createBonusProjection(
  catalog: DecodedBrowserCatalog,
  projection: RequestProjection,
): BonusProjection {
  const catalogSkillIndices: number[] = [];
  const projectedIndices: number[] = [];
  const requiredPieces: ReadonlyArray<number>[] = [];
  const catalogToBonus = new Int32Array(catalog.skills.length);
  catalogToBonus.fill(-1);
  for (
    let projectedIndex = 0;
    projectedIndex < projection.skill_indices.length;
    projectedIndex += 1
  ) {
    const catalogSkillIndex = projection.skill_indices[projectedIndex];
    if (catalogSkillIndex === undefined) {
      throw new Error("projected skill index is missing");
    }
    const skill = catalog.skills[catalogSkillIndex];
    if (skill === undefined || (skill.kind !== "set" && skill.kind !== "group")) {
      continue;
    }
    const bonusIndex = catalogSkillIndices.length;
    catalogToBonus[catalogSkillIndex] = bonusIndex;
    catalogSkillIndices.push(catalogSkillIndex);
    projectedIndices.push(projectedIndex);
    requiredPieces.push(Object.freeze([...skill.required_pieces]));
  }
  return Object.freeze({
    catalog_skill_indices: Int32Array.from(catalogSkillIndices),
    projected_indices: Int32Array.from(projectedIndices),
    required_pieces: Object.freeze(requiredPieces),
    catalog_to_bonus: catalogToBonus,
  });
}

function slotCapacities(
  equipment: IndexedEquipmentVariant,
  maximumSlotLevel: number,
  relevant: boolean,
): Uint16Array {
  if (!relevant) {
    return new Uint16Array(0);
  }
  const capacities = new Uint16Array(maximumSlotLevel * 2);
  for (let index = 0; index < equipment.slots.length; index += 2) {
    const kind = equipment.slots[index];
    const level = equipment.slots[index + 1];
    if ((kind !== 0 && kind !== 1) || level === undefined) {
      throw new Error("indexed equipment slot pair is incomplete");
    }
    for (let threshold = 1; threshold <= level; threshold += 1) {
      const capacityIndex = kind * maximumSlotLevel + threshold - 1;
      capacities[capacityIndex] = (capacities[capacityIndex] ?? 0) + 1;
    }
  }
  return capacities;
}

function projectVariant(
  equipment: IndexedEquipmentVariant,
  projection: RequestProjection,
  bonusProjection: BonusProjection,
  maximumSlotLevel: number,
  slotsRelevant: boolean,
): ProjectedVariant {
  const fixedLevels = new Float64Array(projection.skill_indices.length);
  for (let index = 0; index < equipment.skills.length; index += 2) {
    const catalogSkillIndex = equipment.skills[index];
    const level = equipment.skills[index + 1];
    if (catalogSkillIndex === undefined || level === undefined) {
      throw new Error("indexed equipment skill pair is incomplete");
    }
    const projectedIndex =
      projection.catalog_to_projection[catalogSkillIndex] ?? -1;
    if (projectedIndex >= 0) {
      fixedLevels[projectedIndex] = Math.min(
        (fixedLevels[projectedIndex] ?? 0) + level,
        projection.level_caps[projectedIndex] ?? 0,
      );
    }
  }
  const memberships = new Uint8Array(
    bonusProjection.catalog_skill_indices.length,
  );
  for (const catalogSkillIndex of equipment.series_skill_ids) {
    const bonusIndex =
      bonusProjection.catalog_to_bonus[catalogSkillIndex] ?? -1;
    if (bonusIndex >= 0) {
      memberships[bonusIndex] = 1;
    }
  }
  for (const catalogSkillIndex of equipment.group_skill_ids) {
    const bonusIndex =
      bonusProjection.catalog_to_bonus[catalogSkillIndex] ?? -1;
    if (bonusIndex >= 0) {
      memberships[bonusIndex] = 1;
    }
  }
  return Object.freeze({
    equipment,
    fixed_levels: fixedLevels,
    memberships,
    slot_capacities: slotCapacities(
      equipment,
      maximumSlotLevel,
      slotsRelevant,
    ),
    slot_count: equipment.slots.length / 2,
  });
}

function numericArrayKey(values: ArrayLike<number>): string {
  let result = "";
  for (let index = 0; index < values.length; index += 1) {
    if (index > 0) {
      result += ",";
    }
    result += String(values[index] ?? 0);
  }
  return result;
}

function projectedVariantKey(candidate: ProjectedVariant): string {
  return `${numericArrayKey(candidate.fixed_levels)}|${numericArrayKey(
    candidate.memberships,
  )}|${numericArrayKey(candidate.slot_capacities)}`;
}

function arrayDominates(
  left: ArrayLike<number>,
  right: ArrayLike<number>,
): boolean {
  for (let index = 0; index < left.length; index += 1) {
    if ((left[index] ?? 0) < (right[index] ?? 0)) {
      return false;
    }
  }
  return true;
}

function projectedVariantDominates(
  left: ProjectedVariant,
  right: ProjectedVariant,
): boolean {
  return (
    left.equipment.definition.variant_id <=
      right.equipment.definition.variant_id &&
    arrayDominates(left.fixed_levels, right.fixed_levels) &&
    arrayDominates(left.memberships, right.memberships) &&
    arrayDominates(left.slot_capacities, right.slot_capacities)
  );
}

function preparePartCandidates(
  catalog: DecodedBrowserCatalog,
  request: BrowserRankedSearchRequest,
  projection: RequestProjection,
  bonusProjection: BonusProjection,
  decorationProjection: DecorationProjection,
  checkControl: () => boolean,
): ReadonlyArray<ReadonlyArray<ProjectedVariant>> {
  const result: Array<ReadonlyArray<ProjectedVariant>> = [];
  let steps = 0;
  const slotsRelevant = decorationProjection.decorations.length > 0;
  for (const part of EQUIPMENT_PARTS) {
    const exactSignatures = new Set<string>();
    const unique: ProjectedVariant[] = [];
    for (const equipment of catalog.indexed.equipment_by_part[part]) {
      steps += 1;
      if (
        steps % SEARCH_CONTROL_CHECK_INTERVAL === 0 &&
        checkControl()
      ) {
        return Object.freeze(result);
      }
      if (
        part === "weapon" &&
        request.weapon_kind !== undefined &&
        equipment.definition.weapon_kind !== request.weapon_kind
      ) {
        continue;
      }
      const projected = projectVariant(
        equipment,
        projection,
        bonusProjection,
        catalog.indexed.maximum_slot_level,
        slotsRelevant,
      );
      const key = projectedVariantKey(projected);
      if (exactSignatures.has(key)) {
        continue;
      }
      exactSignatures.add(key);
      unique.push(projected);
    }

    const frontier: ProjectedVariant[] = [];
    for (const candidate of unique) {
      steps += 1;
      if (
        steps % SEARCH_CONTROL_CHECK_INTERVAL === 0 &&
        checkControl()
      ) {
        return Object.freeze(result);
      }
      if (
        frontier.some((existing) =>
          projectedVariantDominates(existing, candidate),
        )
      ) {
        continue;
      }
      frontier.push(candidate);
    }
    result.push(Object.freeze(frontier));
  }
  return Object.freeze(result);
}

function prepareRemainingBounds(
  candidatesByPart: ReadonlyArray<ReadonlyArray<ProjectedVariant>>,
  projection: RequestProjection,
  bonusProjection: BonusProjection,
  decorationProjection: DecorationProjection,
): Omit<PreparedSearch, "candidates_by_part"> {
  const depthCount = EQUIPMENT_PARTS.length;
  const remainingMaxFixed = Array.from(
    { length: depthCount + 1 },
    () => new Float64Array(projection.skill_indices.length),
  );
  const remainingMaxMemberships = Array.from(
    { length: depthCount + 1 },
    () => new Uint8Array(bonusProjection.catalog_skill_indices.length),
  );
  const remainingMaxSlotCount = new Uint16Array(depthCount + 1);
  for (let depth = depthCount - 1; depth >= 0; depth -= 1) {
    const nextFixed = remainingMaxFixed[depth + 1];
    const nextMemberships = remainingMaxMemberships[depth + 1];
    const currentFixed = remainingMaxFixed[depth];
    const currentMemberships = remainingMaxMemberships[depth];
    if (
      nextFixed === undefined ||
      nextMemberships === undefined ||
      currentFixed === undefined ||
      currentMemberships === undefined
    ) {
      throw new Error("remaining-bound buffer is missing");
    }
    currentFixed.set(nextFixed);
    currentMemberships.set(nextMemberships);
    const candidates = candidatesByPart[depth] ?? [];
    let maximumSlots = 0;
    for (const candidate of candidates) {
      maximumSlots = Math.max(maximumSlots, candidate.slot_count);
    }
    for (let index = 0; index < currentFixed.length; index += 1) {
      let partMaximum = 0;
      for (const candidate of candidates) {
        partMaximum = Math.max(
          partMaximum,
          candidate.fixed_levels[index] ?? 0,
        );
      }
      currentFixed[index] = Math.min(
        projection.level_caps[index] ?? 0,
        (nextFixed[index] ?? 0) + partMaximum,
      );
    }
    for (let index = 0; index < currentMemberships.length; index += 1) {
      let partMaximum = 0;
      for (const candidate of candidates) {
        partMaximum = Math.max(
          partMaximum,
          candidate.memberships[index] ?? 0,
        );
      }
      currentMemberships[index] =
        (nextMemberships[index] ?? 0) + partMaximum;
    }
    remainingMaxSlotCount[depth] =
      (remainingMaxSlotCount[depth + 1] ?? 0) + maximumSlots;
  }

  const maxDecorationContribution = new Float64Array(
    projection.skill_indices.length,
  );
  for (const decoration of decorationProjection.decorations) {
    for (let index = 0; index < maxDecorationContribution.length; index += 1) {
      maxDecorationContribution[index] = Math.max(
        maxDecorationContribution[index] ?? 0,
        decoration.contributions[index] ?? 0,
      );
    }
  }
  return Object.freeze({
    remaining_max_fixed: Object.freeze(remainingMaxFixed),
    remaining_max_memberships: Object.freeze(remainingMaxMemberships),
    remaining_max_slot_count: remainingMaxSlotCount,
    max_decoration_contribution: maxDecorationContribution,
  });
}

function activatedBonusLevel(
  requiredPieces: ArrayLike<number>,
  pieceCount: number,
): number {
  let level = 0;
  for (let index = 0; index < requiredPieces.length; index += 1) {
    if ((requiredPieces[index] ?? Number.POSITIVE_INFINITY) <= pieceCount) {
      level = index + 1;
    }
  }
  return level;
}

function levelsWithBonuses(
  fixedLevels: ArrayLike<number>,
  memberships: ArrayLike<number>,
  projection: RequestProjection,
  bonusProjection: BonusProjection,
): Float64Array {
  const levels = Float64Array.from(fixedLevels);
  for (
    let bonusIndex = 0;
    bonusIndex < bonusProjection.projected_indices.length;
    bonusIndex += 1
  ) {
    const projectedIndex = bonusProjection.projected_indices[bonusIndex];
    const requirements = bonusProjection.required_pieces[bonusIndex];
    if (projectedIndex === undefined || requirements === undefined) {
      throw new Error("bonus projection entry is missing");
    }
    levels[projectedIndex] = Math.min(
      projection.level_caps[projectedIndex] ?? 0,
      (levels[projectedIndex] ?? 0) +
        activatedBonusLevel(
          requirements,
          memberships[bonusIndex] ?? 0,
        ),
    );
  }
  return levels;
}

function upperBoundLevels(
  depth: number,
  fixedLevels: ArrayLike<number>,
  memberships: ArrayLike<number>,
  selectedSlotCount: number,
  prepared: PreparedSearch,
  projection: RequestProjection,
  bonusProjection: BonusProjection,
): Float64Array {
  const remainingFixed = prepared.remaining_max_fixed[depth];
  const remainingMemberships = prepared.remaining_max_memberships[depth];
  if (remainingFixed === undefined || remainingMemberships === undefined) {
    throw new Error("remaining search bound is missing");
  }
  const upperFixed = new Float64Array(projection.skill_indices.length);
  for (let index = 0; index < upperFixed.length; index += 1) {
    upperFixed[index] = Math.min(
      projection.level_caps[index] ?? 0,
      (fixedLevels[index] ?? 0) + (remainingFixed[index] ?? 0),
    );
  }
  const upperMemberships = new Uint8Array(memberships.length);
  for (let index = 0; index < memberships.length; index += 1) {
    upperMemberships[index] =
      (memberships[index] ?? 0) + (remainingMemberships[index] ?? 0);
  }
  const levels = levelsWithBonuses(
    upperFixed,
    upperMemberships,
    projection,
    bonusProjection,
  );
  const possibleSlotCount =
    selectedSlotCount + (prepared.remaining_max_slot_count[depth] ?? 0);
  for (let index = 0; index < levels.length; index += 1) {
    levels[index] = Math.min(
      projection.level_caps[index] ?? 0,
      (levels[index] ?? 0) +
        possibleSlotCount *
          (prepared.max_decoration_contribution[index] ?? 0),
    );
  }
  return levels;
}

function upperBoundCanSatisfyRequirements(
  upperLevels: ArrayLike<number>,
  projection: RequestProjection,
): boolean {
  for (let index = 0; index < projection.requirement_levels.length; index += 1) {
    if (
      (upperLevels[index] ?? 0) <
      (projection.requirement_levels[index] ?? 0)
    ) {
      return false;
    }
  }
  return true;
}

function appendCapped(
  target: Float64Array,
  contribution: ArrayLike<number>,
  caps: ArrayLike<number>,
): void {
  for (let index = 0; index < target.length; index += 1) {
    target[index] = Math.min(
      caps[index] ?? 0,
      (target[index] ?? 0) + (contribution[index] ?? 0),
    );
  }
}

function appendMemberships(
  target: Uint8Array,
  contribution: ArrayLike<number>,
): void {
  for (let index = 0; index < target.length; index += 1) {
    target[index] = (target[index] ?? 0) + (contribution[index] ?? 0);
  }
}

function appendCapacities(
  target: Uint16Array,
  contribution: ArrayLike<number>,
): void {
  for (let index = 0; index < target.length; index += 1) {
    target[index] = (target[index] ?? 0) + (contribution[index] ?? 0);
  }
}

function stateKey(
  fixedLevels: ArrayLike<number>,
  memberships: ArrayLike<number>,
  capacities: ArrayLike<number>,
  bonusProjection: BonusProjection,
): string {
  const cappedMemberships = new Uint8Array(memberships.length);
  for (let index = 0; index < memberships.length; index += 1) {
    const requirements = bonusProjection.required_pieces[index];
    const maximumUsefulPieces =
      requirements?.[requirements.length - 1] ?? EQUIPMENT_PARTS.length;
    cappedMemberships[index] = Math.min(
      memberships[index] ?? 0,
      maximumUsefulPieces,
    );
  }
  return `${numericArrayKey(fixedLevels)}|${numericArrayKey(
    cappedMemberships,
  )}|${numericArrayKey(capacities)}`;
}

function selectedSlots(
  selected: ReadonlyArray<IndexedEquipmentVariant>,
): CatalogSlot[] {
  const result: CatalogSlot[] = [];
  for (const equipment of selected) {
    result.push(...equipment.definition.slots);
  }
  return result;
}

function prefixRanksAfterIncumbent(
  selected: ReadonlyArray<IndexedEquipmentVariant>,
  incumbent: Incumbent,
): boolean {
  for (let index = 0; index < selected.length; index += 1) {
    const candidateId = selected[index]?.definition.variant_id;
    const incumbentId =
      incumbent.objective.selected_variant_ids[index];
    if (candidateId === undefined || incumbentId === undefined) {
      return false;
    }
    if (candidateId !== incumbentId) {
      return candidateId > incumbentId;
    }
  }
  return false;
}

function buildCandidate(
  catalog: DecodedBrowserCatalog,
  request: BrowserRankedSearchRequest,
  incumbent: Incumbent,
): RankedBuildCandidate {
  const decorationIndices = incumbent.decoration_solution.decoration_indices;
  const skillLevels = aggregateSelectedBuildSkillLevels(
    catalog,
    incumbent.selected_equipment,
    decorationIndices,
  );
  const candidate: RankedBuildCandidate = {
    equipment: incumbent.selected_equipment.map((equipment) =>
      equipmentVariantToResponse(catalog, equipment),
    ),
    placements: reconstructDecorationPlacements(
      catalog,
      incumbent.selected_equipment,
      decorationIndices,
    ),
    skill_levels: skillLevels,
    preference_score: incumbent.objective.preference_score,
  };
  // The public result is checked independently from the projected hot-loop
  // state below, including every slot and full (un-capped) skill level.
  const resultScore = candidate.skill_levels.reduce((score, level) => {
    const preference = request.preferences.find(
      ({ skill_id }) => skill_id === level.skill_id,
    );
    return (
      score +
      (preference === undefined
        ? 0
        : Math.min(level.level, preference.target_level))
    );
  }, 0);
  if (resultScore !== candidate.preference_score) {
    throw new Error("projected and reconstructed preference scores disagree");
  }
  return candidate;
}

/**
 * Exact top-1 ranked search over the already-expanded compact Catalog.
 */
export function solveBrowserRankedSearch(
  catalog: DecodedBrowserCatalog,
  requestValue: BrowserRankedSearchRequest,
  optionsValue: BrowserSolverOptions = {},
): BrowserSolverResult {
  const request = decodeBrowserRankedSearchRequest(requestValue);
  const options = validateOptions(optionsValue);
  const start = readClock(options.now);
  const counters: MutableCounters = {
    visited_nodes: 0,
    pruned_nodes: 0,
    complete_equipment_selections: 0,
  };
  let incumbent: Incumbent | null = null;
  let interruptedStatus: "timed-out" | "cancelled" | null = null;
  let controlChecks = 0;

  const elapsed = (): number => Math.max(0, readClock(options.now) - start);
  const progress = (): BrowserSolverProgress =>
    Object.freeze({
      elapsed_ms: elapsed(),
      visited_nodes: counters.visited_nodes,
      pruned_nodes: counters.pruned_nodes,
      complete_equipment_selections: counters.complete_equipment_selections,
      preference_score: incumbent?.objective.preference_score ?? null,
      decoration_count: incumbent?.objective.decoration_count ?? null,
    });
  const checkControl = (forceClock = false): boolean => {
    if (interruptedStatus !== null) {
      return true;
    }
    if (options.shouldCancel()) {
      interruptedStatus = "cancelled";
      return true;
    }
    controlChecks += 1;
    if (
      forceClock ||
      controlChecks % SEARCH_CONTROL_CHECK_INTERVAL === 0
    ) {
      if (elapsed() >= options.timeoutMs) {
        interruptedStatus = "timed-out";
        return true;
      }
      options.onProgress?.(progress());
    }
    return false;
  };

  const finish = (
    completedStatus: "optimal" | "infeasible",
  ): BrowserSolverResult => {
    const status: BrowserSolverStatus =
      interruptedStatus ?? completedStatus;
    const candidate =
      incumbent === null ? null : buildCandidate(catalog, request, incumbent);
    const result: BrowserSolverResult = {
      status,
      candidate,
      selected_variant_ids:
        incumbent?.objective.selected_variant_ids.slice() ?? [],
      preference_score: incumbent?.objective.preference_score ?? null,
      decoration_count: incumbent?.objective.decoration_count ?? null,
      elapsed_ms: elapsed(),
      visited_nodes: counters.visited_nodes,
      pruned_nodes: counters.pruned_nodes,
      complete_equipment_selections: counters.complete_equipment_selections,
    };
    validateBrowserSolverResult(catalog, request, result);
    return result;
  };

  if (checkControl(true)) {
    return finish("infeasible");
  }
  const projection = createRequestProjection(catalog, request);
  if (projection.unknown_required_skill) {
    return finish("infeasible");
  }
  const bonusProjection = createBonusProjection(catalog, projection);
  const decorationProjection = createDecorationProjection(catalog, projection);
  const candidatesByPart = preparePartCandidates(
    catalog,
    request,
    projection,
    bonusProjection,
    decorationProjection,
    () => checkControl(true),
  );
  if (interruptedStatus !== null || checkControl(true)) {
    return finish("infeasible");
  }
  if (
    candidatesByPart.length !== EQUIPMENT_PARTS.length ||
    candidatesByPart.some((candidates) => candidates.length === 0)
  ) {
    return finish("infeasible");
  }
  const bounds = prepareRemainingBounds(
    candidatesByPart,
    projection,
    bonusProjection,
    decorationProjection,
  );
  if (checkControl(true)) {
    return finish("infeasible");
  }
  const prepared: PreparedSearch = Object.freeze({
    candidates_by_part: candidatesByPart,
    ...bounds,
  });

  const selected: IndexedEquipmentVariant[] = [];
  const fixedLevels = new Float64Array(projection.skill_indices.length);
  const memberships = new Uint8Array(
    bonusProjection.catalog_skill_indices.length,
  );
  const capacities = new Uint16Array(
    decorationProjection.decorations.length === 0
      ? 0
      : catalog.indexed.maximum_slot_level * 2,
  );
  let selectedSlotCount = 0;
  const seenByDepth = Array.from(
    { length: EQUIPMENT_PARTS.length + 1 },
    () => new Set<string>(),
  );
  const decorationCache = new Map<string, DecorationSolution | null>();
  let provenGlobalOptimum = false;

  const visit = (depth: number): void => {
    if (interruptedStatus !== null || provenGlobalOptimum) {
      return;
    }
    counters.visited_nodes = incrementCounter(counters.visited_nodes);
    if (checkControl()) {
      return;
    }
    const key = stateKey(
      fixedLevels,
      memberships,
      capacities,
      bonusProjection,
    );
    const seen = seenByDepth[depth];
    if (seen === undefined) {
      throw new Error("search memo depth is missing");
    }
    if (seen.has(key)) {
      counters.pruned_nodes = incrementCounter(counters.pruned_nodes);
      return;
    }
    seen.add(key);

    const upperLevels = upperBoundLevels(
      depth,
      fixedLevels,
      memberships,
      selectedSlotCount,
      prepared,
      projection,
      bonusProjection,
    );
    if (!upperBoundCanSatisfyRequirements(upperLevels, projection)) {
      counters.pruned_nodes = incrementCounter(counters.pruned_nodes);
      return;
    }
    const upperScore = calculateProjectedPreferenceScore(
      upperLevels,
      projection,
    );
    if (incumbent !== null) {
      if (upperScore < incumbent.objective.preference_score) {
        counters.pruned_nodes = incrementCounter(counters.pruned_nodes);
        return;
      }
      if (
        upperScore === incumbent.objective.preference_score &&
        incumbent.objective.decoration_count === 0 &&
        prefixRanksAfterIncumbent(selected, incumbent)
      ) {
        counters.pruned_nodes = incrementCounter(counters.pruned_nodes);
        return;
      }
    }

    if (depth === EQUIPMENT_PARTS.length) {
      if (checkControl(true)) {
        return;
      }
      counters.complete_equipment_selections = incrementCounter(
        counters.complete_equipment_selections,
      );
      const baseLevels = levelsWithBonuses(
        fixedLevels,
        memberships,
        projection,
        bonusProjection,
      );
      const decorationKey = `${numericArrayKey(
        baseLevels,
      )}|${numericArrayKey(capacities)}`;
      let solution = decorationCache.get(decorationKey);
      if (solution === undefined && !decorationCache.has(decorationKey)) {
        const outcome = solveProjectedDecorations(
          projection,
          decorationProjection,
          baseLevels,
          selectedSlots(selected),
          () => checkControl(true),
        );
        if (outcome.interrupted) {
          return;
        }
        solution = outcome.solution;
        decorationCache.set(decorationKey, solution);
      }
      if (solution === null || solution === undefined) {
        return;
      }
      const selectedVariantIds = selected.map(
        ({ definition }) => definition.variant_id,
      );
      const objective: SearchObjective = Object.freeze({
        preference_score: solution.preference_score,
        decoration_count: solution.decoration_indices.length,
        selected_variant_ids: Object.freeze(selectedVariantIds),
        decoration_indices: solution.decoration_indices,
        decoration_id_ranks: solution.decoration_id_ranks,
      });
      if (
        incumbent === null ||
        compareSearchObjectives(objective, incumbent.objective) < 0
      ) {
        incumbent = Object.freeze({
          selected_equipment: Object.freeze(selected.slice()),
          decoration_solution: solution,
          objective,
        });
        if (
          objective.preference_score === projection.maximum_preference_score &&
          objective.decoration_count === 0
        ) {
          provenGlobalOptimum = true;
        }
      }
      checkControl(true);
      return;
    }

    const candidates = prepared.candidates_by_part[depth];
    if (candidates === undefined) {
      throw new Error("part candidates are missing");
    }
    for (const candidate of candidates) {
      if (interruptedStatus !== null || provenGlobalOptimum) {
        break;
      }
      const previousFixed = Float64Array.from(fixedLevels);
      const previousMemberships = Uint8Array.from(memberships);
      const previousCapacities = Uint16Array.from(capacities);
      const previousSlotCount = selectedSlotCount;
      appendCapped(
        fixedLevels,
        candidate.fixed_levels,
        projection.level_caps,
      );
      appendMemberships(memberships, candidate.memberships);
      appendCapacities(capacities, candidate.slot_capacities);
      selectedSlotCount += candidate.slot_count;
      selected.push(candidate.equipment);
      visit(depth + 1);
      selected.pop();
      fixedLevels.set(previousFixed);
      memberships.set(previousMemberships);
      capacities.set(previousCapacities);
      selectedSlotCount = previousSlotCount;
    }
  };

  visit(0);
  return finish(incumbent === null ? "infeasible" : "optimal");
}
