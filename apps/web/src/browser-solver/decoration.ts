import {
  calculateProjectedPreferenceScore,
  compareNumberArraysLexicographically,
  projectedRequirementsSatisfied,
  type RequestProjection,
} from "./objective";
import type {
  CatalogSlot,
  DecodedBrowserCatalog,
  DecorationPlacementResponse,
  IndexedEquipmentVariant,
} from "./types";

export const DECORATION_CONTROL_CHECK_INTERVAL = 1_024;

export interface ProjectedDecoration {
  readonly decoration_index: number;
  readonly decoration_id: string;
  readonly decoration_id_rank: number;
  readonly required_slot_kind: 0 | 1;
  readonly required_slot_level: number;
  readonly contributions: Float64Array;
}

export interface DecorationProjection {
  readonly decorations: ReadonlyArray<ProjectedDecoration>;
  readonly id_rank_by_decoration_index: Int32Array;
}

export interface DecorationSolution {
  readonly decoration_indices: ReadonlyArray<number>;
  readonly decoration_id_ranks: ReadonlyArray<number>;
  readonly projected_levels: Float64Array;
  readonly preference_score: number;
}

export interface DecorationSearchOutcome {
  readonly solution: DecorationSolution | null;
  readonly interrupted: boolean;
}

interface PlanState {
  readonly levels: Float64Array;
  readonly decorations: readonly number[];
}

function contributionsDominate(
  left: ProjectedDecoration,
  right: ProjectedDecoration,
): boolean {
  if (
    left.required_slot_kind !== right.required_slot_kind ||
    left.required_slot_level > right.required_slot_level ||
    left.decoration_id > right.decoration_id
  ) {
    return false;
  }
  for (let index = 0; index < left.contributions.length; index += 1) {
    if (
      (left.contributions[index] ?? 0) <
      (right.contributions[index] ?? 0)
    ) {
      return false;
    }
  }
  return true;
}

export function createDecorationProjection(
  catalog: DecodedBrowserCatalog,
  projection: RequestProjection,
): DecorationProjection {
  const candidates: Array<Omit<ProjectedDecoration, "decoration_id_rank">> = [];
  for (const decoration of catalog.indexed.decorations) {
    const contributions = new Float64Array(projection.skill_indices.length);
    let relevant = false;
    for (let index = 0; index < decoration.skills.length; index += 2) {
      const catalogSkillIndex = decoration.skills[index];
      const level = decoration.skills[index + 1];
      if (catalogSkillIndex === undefined || level === undefined) {
        throw new Error("indexed decoration skill pair is incomplete");
      }
      const projectedIndex =
        projection.catalog_to_projection[catalogSkillIndex] ?? -1;
      if (projectedIndex >= 0) {
        contributions[projectedIndex] = level;
        relevant = true;
      }
    }
    if (!relevant) {
      continue;
    }
    candidates.push(Object.freeze({
      decoration_index: decoration.decoration_index,
      decoration_id: decoration.definition.decoration_id,
      required_slot_kind: decoration.required_slot_kind,
      required_slot_level: decoration.required_slot_level,
      contributions,
    }));
  }
  candidates.sort((left, right) =>
    left.decoration_id < right.decoration_id
      ? -1
      : left.decoration_id > right.decoration_id
        ? 1
        : 0,
  );
  const decorations: ProjectedDecoration[] = [];
  const idRankByDecorationIndex = new Int32Array(
    catalog.indexed.decorations.length,
  );
  for (let rank = 0; rank < candidates.length; rank += 1) {
    const raw = candidates[rank];
    if (raw === undefined) {
      throw new Error("projected decoration is missing");
    }
    idRankByDecorationIndex[raw.decoration_index] = rank;
    const candidate: ProjectedDecoration = Object.freeze({
      ...raw,
      decoration_id_rank: rank,
    });
    // Catalog order is decoration-ID tie order. An earlier decoration that is
    // no harder to place and contributes at least as much makes this one
    // unusable in an optimal deterministic plan.
    if (
      decorations.some((existing) =>
        contributionsDominate(existing, candidate),
      )
    ) {
      continue;
    }
    decorations.push(candidate);
  }
  return Object.freeze({
    decorations: Object.freeze(decorations),
    id_rank_by_decoration_index: idRankByDecorationIndex,
  });
}

function stateKey(levels: ArrayLike<number>): string {
  let result = "";
  for (let index = 0; index < levels.length; index += 1) {
    if (index > 0) {
      result += ",";
    }
    result += String(levels[index] ?? 0);
  }
  return result;
}

function insertSorted(
  values: readonly number[],
  value: number,
  ranks: ArrayLike<number>,
): readonly number[] {
  let low = 0;
  let high = values.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    const middleValue = values[middle];
    if (
      middleValue !== undefined &&
      (ranks[middleValue] ?? Number.POSITIVE_INFINITY) <=
        (ranks[value] ?? Number.POSITIVE_INFINITY)
    ) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  const result = values.slice();
  result.splice(low, 0, value);
  return result;
}

function planRanksAhead(
  left: PlanState,
  right: PlanState,
  ranks: ArrayLike<number>,
): boolean {
  if (left.decorations.length !== right.decorations.length) {
    return left.decorations.length < right.decorations.length;
  }
  return compareDecorationPlans(left.decorations, right.decorations, ranks) < 0;
}

function compareDecorationPlans(
  left: readonly number[],
  right: readonly number[],
  ranks: ArrayLike<number>,
): number {
  return compareNumberArraysLexicographically(
    left.map((index) => ranks[index] ?? Number.POSITIVE_INFINITY),
    right.map((index) => ranks[index] ?? Number.POSITIVE_INFINITY),
  );
}

function canonicalSlots(slots: ReadonlyArray<CatalogSlot>): CatalogSlot[] {
  return slots
    .slice()
    .sort(
      (left, right) =>
        (left[0] === right[0] ? 0 : left[0] === "weapon" ? -1 : 1) ||
        left[1] - right[1],
    );
}

export function solveProjectedDecorations(
  projection: RequestProjection,
  decorationProjection: DecorationProjection,
  baseLevels: ArrayLike<number>,
  slots: ReadonlyArray<CatalogSlot>,
  shouldStop?: () => boolean,
): DecorationSearchOutcome {
  const initialLevels = new Float64Array(projection.skill_indices.length);
  for (let index = 0; index < initialLevels.length; index += 1) {
    initialLevels[index] = Math.min(
      baseLevels[index] ?? 0,
      projection.level_caps[index] ?? 0,
    );
  }
  let states = new Map<string, PlanState>([
    [
      stateKey(initialLevels),
      Object.freeze({
        levels: initialLevels,
        decorations: Object.freeze([] as number[]),
      }),
    ],
  ]);
  let transitions = 0;
  for (const [slotKind, slotLevel] of canonicalSlots(slots)) {
    const encodedKind = slotKind === "weapon" ? 0 : 1;
    const next = new Map(states);
    for (const state of states.values()) {
      for (const decoration of decorationProjection.decorations) {
        transitions += 1;
        if (
          transitions % DECORATION_CONTROL_CHECK_INTERVAL === 0 &&
          shouldStop?.()
        ) {
          return Object.freeze({ solution: null, interrupted: true });
        }
        if (
          decoration.required_slot_kind !== encodedKind ||
          decoration.required_slot_level > slotLevel
        ) {
          continue;
        }
        const levels = new Float64Array(state.levels);
        let changed = false;
        for (let index = 0; index < levels.length; index += 1) {
          const capped = Math.min(
            (levels[index] ?? 0) + (decoration.contributions[index] ?? 0),
            projection.level_caps[index] ?? 0,
          );
          if (capped !== levels[index]) {
            changed = true;
            levels[index] = capped;
          }
        }
        if (!changed) {
          continue;
        }
        const candidate: PlanState = Object.freeze({
          levels,
          decorations: Object.freeze(
            insertSorted(
              state.decorations,
              decoration.decoration_index,
              decorationProjection.id_rank_by_decoration_index,
            ) as number[],
          ),
        });
        const key = stateKey(levels);
        const incumbent = next.get(key);
        if (
          incumbent === undefined ||
          planRanksAhead(
            candidate,
            incumbent,
            decorationProjection.id_rank_by_decoration_index,
          )
        ) {
          next.set(key, candidate);
        }
      }
    }
    states = next;
  }

  let best: DecorationSolution | null = null;
  for (const state of states.values()) {
    if (!projectedRequirementsSatisfied(state.levels, projection)) {
      continue;
    }
    const score = calculateProjectedPreferenceScore(state.levels, projection);
    const candidate: DecorationSolution = Object.freeze({
      decoration_indices: state.decorations,
      decoration_id_ranks: Object.freeze(
        state.decorations.map(
          (index) =>
            decorationProjection.id_rank_by_decoration_index[index] ??
            Number.POSITIVE_INFINITY,
        ),
      ),
      projected_levels: state.levels,
      preference_score: score,
    });
    if (
      best === null ||
      score > best.preference_score ||
      (score === best.preference_score &&
        (candidate.decoration_indices.length <
          best.decoration_indices.length ||
          (candidate.decoration_indices.length ===
            best.decoration_indices.length &&
            compareDecorationPlans(
              candidate.decoration_indices,
              best.decoration_indices,
              decorationProjection.id_rank_by_decoration_index,
            ) < 0)))
    ) {
      best = candidate;
    }
  }
  return Object.freeze({ solution: best, interrupted: false });
}

interface AvailableSlot {
  readonly equipment_index: number;
  readonly slot_index: number;
  readonly kind: 0 | 1;
  readonly level: number;
}

export function reconstructDecorationPlacements(
  catalog: DecodedBrowserCatalog,
  selectedEquipment: ReadonlyArray<IndexedEquipmentVariant>,
  decorationIndices: ReadonlyArray<number>,
): DecorationPlacementResponse[] {
  const available: AvailableSlot[] = [];
  for (
    let equipmentIndex = 0;
    equipmentIndex < selectedEquipment.length;
    equipmentIndex += 1
  ) {
    const equipment = selectedEquipment[equipmentIndex];
    if (equipment === undefined) {
      throw new Error("selected equipment is missing");
    }
    for (let slotIndex = 0; slotIndex < equipment.slots.length / 2; slotIndex += 1) {
      const kind = equipment.slots[slotIndex * 2];
      const level = equipment.slots[slotIndex * 2 + 1];
      if ((kind !== 0 && kind !== 1) || level === undefined) {
        throw new Error("indexed equipment slot pair is incomplete");
      }
      available.push(
        Object.freeze({ equipment_index: equipmentIndex, slot_index: slotIndex, kind, level }),
      );
    }
  }

  const instances = decorationIndices
    .map((decorationIndex) => {
      const decoration = catalog.indexed.decorations[decorationIndex];
      if (decoration === undefined) {
        throw new Error(`unknown decoration index ${decorationIndex}`);
      }
      return decoration;
    })
    .sort(
      (left, right) =>
        right.required_slot_level - left.required_slot_level ||
        (left.definition.decoration_id < right.definition.decoration_id
          ? -1
          : left.definition.decoration_id > right.definition.decoration_id
            ? 1
            : 0),
    );
  const used = new Set<string>();
  const placed: Array<{
    readonly equipment_index: number;
    readonly slot_index: number;
    readonly placement: DecorationPlacementResponse;
  }> = [];
  for (const decoration of instances) {
    let selected: AvailableSlot | null = null;
    for (const slot of available) {
      if (
        used.has(`${slot.equipment_index}:${slot.slot_index}`) ||
        slot.kind !== decoration.required_slot_kind ||
        slot.level < decoration.required_slot_level
      ) {
        continue;
      }
      if (
        selected === null ||
        slot.level < selected.level ||
        (slot.level === selected.level &&
          (slot.equipment_index < selected.equipment_index ||
            (slot.equipment_index === selected.equipment_index &&
              slot.slot_index < selected.slot_index)))
      ) {
        selected = slot;
      }
    }
    if (selected === null) {
      throw new Error("decoration plan cannot be reconstructed into equipment slots");
    }
    used.add(`${selected.equipment_index}:${selected.slot_index}`);
    const equipment = selectedEquipment[selected.equipment_index];
    if (equipment === undefined) {
      throw new Error("decoration target equipment is missing");
    }
    placed.push({
      equipment_index: selected.equipment_index,
      slot_index: selected.slot_index,
      placement: {
        equipment_id: equipment.definition.equipment_id,
        slot_index: selected.slot_index,
        decoration_id: decoration.definition.decoration_id,
      },
    });
  }
  placed.sort(
    (left, right) =>
      left.equipment_index - right.equipment_index ||
      left.slot_index - right.slot_index,
  );
  return placed.map(({ placement }) => placement);
}
