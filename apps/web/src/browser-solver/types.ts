export const EQUIPMENT_PARTS = [
  "weapon",
  "head",
  "chest",
  "arms",
  "waist",
  "legs",
  "charm",
] as const;

export const SKILL_KINDS = ["armor", "weapon", "set", "group"] as const;
export const SLOT_KINDS = ["weapon", "armor"] as const;

export type EquipmentPart = (typeof EQUIPMENT_PARTS)[number];
export type SkillKind = (typeof SKILL_KINDS)[number];
export type SlotKind = (typeof SLOT_KINDS)[number];

export interface BrowserRankedSearchRequirement {
  readonly skill_id: string;
  readonly min_level: number;
}

export interface BrowserRankedSearchPreference {
  readonly skill_id: string;
  readonly target_level: number;
}

export interface BrowserRankedSearchRequest {
  readonly requirements: ReadonlyArray<BrowserRankedSearchRequirement>;
  readonly preferences: ReadonlyArray<BrowserRankedSearchPreference>;
  readonly max_results: 1;
  readonly weapon_kind?: string;
}

export interface BrowserCatalogSource {
  readonly schema_version: number;
  readonly sha256: string;
  readonly source_equipment_count: number;
  readonly generated_appraisal_charm_count: number;
  readonly expanded_equipment_count: number;
  readonly decoration_count: number;
  readonly skill_count: number;
}

export interface BrowserCatalogSkill {
  readonly skill_id: string;
  readonly display_name: string | null;
  readonly kind: SkillKind;
  readonly max_level: number;
  readonly required_pieces: ReadonlyArray<number>;
}

export type IndexedSkillLevel = readonly [skillIndex: number, level: number];
export type CatalogSlot = readonly [kind: SlotKind, level: number];

export interface BrowserCatalogEquipmentVariant {
  readonly variant_id: number;
  readonly equipment_id: string;
  readonly display_name: string | null;
  readonly part: EquipmentPart;
  readonly weapon_kind: string | null;
  readonly series_skill_id: number | null;
  readonly group_skill_id: number | null;
  readonly series_skill_ids: ReadonlyArray<number>;
  readonly group_skill_ids: ReadonlyArray<number>;
  readonly skills: ReadonlyArray<IndexedSkillLevel>;
  readonly slots: ReadonlyArray<CatalogSlot>;
}

export interface BrowserCatalogDecoration {
  readonly decoration_id: string;
  readonly display_name: string | null;
  readonly required_slot: CatalogSlot;
  readonly skills: ReadonlyArray<IndexedSkillLevel>;
}

/**
 * Numeric representation used by the search hot loops. Pairs are interleaved:
 * `[index0, level0, index1, level1, ...]`.
 */
export interface IndexedEquipmentVariant {
  readonly definition: BrowserCatalogEquipmentVariant;
  readonly skills: Int32Array;
  readonly series_skill_ids: Int32Array;
  readonly group_skill_ids: Int32Array;
  /** Slot kind is encoded as 0 for weapon and 1 for armor. */
  readonly slots: Int32Array;
}

export interface IndexedDecoration {
  readonly definition: BrowserCatalogDecoration;
  readonly decoration_index: number;
  /** Slot kind is encoded as 0 for weapon and 1 for armor. */
  readonly required_slot_kind: 0 | 1;
  readonly required_slot_level: number;
  readonly skills: Int32Array;
}

export interface BrowserCatalogIndexes {
  readonly skill_index_by_id: ReadonlyMap<string, number>;
  readonly decoration_index_by_id: ReadonlyMap<string, number>;
  readonly variants_by_id: ReadonlyArray<IndexedEquipmentVariant>;
  readonly equipment_by_part: Readonly<
    Record<EquipmentPart, ReadonlyArray<IndexedEquipmentVariant>>
  >;
  readonly decorations: ReadonlyArray<IndexedDecoration>;
  readonly maximum_slot_level: number;
}

export interface DecodedBrowserCatalog {
  readonly format_version: 1;
  readonly source_catalog: BrowserCatalogSource;
  readonly skills: ReadonlyArray<BrowserCatalogSkill>;
  readonly equipment_by_part: Readonly<
    Record<EquipmentPart, ReadonlyArray<BrowserCatalogEquipmentVariant>>
  >;
  readonly decorations: ReadonlyArray<BrowserCatalogDecoration>;
  readonly indexed: BrowserCatalogIndexes;
}

export interface SkillLevelResponse {
  skill_id: string;
  level: number;
}

export interface EquipmentSlotResponse {
  kind: SlotKind;
  level: number;
}

export interface EquipmentResponse {
  equipment_id: string;
  display_name: string | null;
  part: EquipmentPart;
  weapon_kind: string | null;
  series_skill_id: string | null;
  group_skill_id: string | null;
  series_skill_ids: string[];
  group_skill_ids: string[];
  skills: SkillLevelResponse[];
  slots: EquipmentSlotResponse[];
}

export interface DecorationPlacementResponse {
  equipment_id: string;
  slot_index: number;
  decoration_id: string;
}

export interface RankedBuildCandidate {
  equipment: EquipmentResponse[];
  placements: DecorationPlacementResponse[];
  skill_levels: SkillLevelResponse[];
  preference_score: number;
}

export type BrowserSolverStatus =
  | "optimal"
  | "infeasible"
  | "timed-out"
  | "cancelled";

export interface BrowserSolverResult {
  status: BrowserSolverStatus;
  candidate: RankedBuildCandidate | null;
  selected_variant_ids: number[];
  preference_score: number | null;
  decoration_count: number | null;
  elapsed_ms: number;
  visited_nodes: number;
  pruned_nodes: number;
  complete_equipment_selections: number;
}

export interface BrowserSolverProgress {
  readonly elapsed_ms: number;
  readonly visited_nodes: number;
  readonly pruned_nodes: number;
  readonly complete_equipment_selections: number;
  readonly preference_score: number | null;
  readonly decoration_count: number | null;
}

export interface BrowserSolverOptions {
  readonly timeoutMs?: number;
  readonly now?: () => number;
  readonly shouldCancel?: () => boolean;
  readonly onProgress?: (progress: BrowserSolverProgress) => void;
}

export interface CandidateValidationSummary {
  readonly preference_score: number;
  readonly decoration_count: number;
  readonly skill_levels: ReadonlyArray<SkillLevelResponse>;
}
