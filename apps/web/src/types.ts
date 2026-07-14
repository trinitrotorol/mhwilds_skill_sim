export type SkillKind = "armor" | "weapon" | "set" | "group";

export interface CatalogSkillRankMetadata {
  level: number;
  required_pieces: number | null;
}

export interface CatalogSkillMetadata {
  skill_id: string;
  display_name: string | null;
  kind: SkillKind;
  max_level: number;
  ranks: CatalogSkillRankMetadata[];
}

export interface CatalogDecorationSlotMetadata {
  kind: "weapon" | "armor";
  level: number;
}

export interface SkillLevelResponse {
  skill_id: string;
  level: number;
}

export interface CatalogDecorationMetadata {
  decoration_id: string;
  display_name: string | null;
  required_slot: CatalogDecorationSlotMetadata;
  skills: SkillLevelResponse[];
}

export interface CatalogMetadataResponse {
  schema_version: number;
  skills: CatalogSkillMetadata[];
  weapon_kinds: string[];
  decorations: CatalogDecorationMetadata[];
  features: {
    artian_series_skill_assignment: boolean;
    artian_group_skill_assignment: boolean;
    theoretical_appraisal_charms: boolean;
  };
  counts: {
    skills: number;
    equipment: number;
    decorations: number;
    appraisal_charm_skill_groups: number;
    appraisal_charm_patterns: number;
  };
}

export interface RankedSearchRequirement {
  skill_id: string;
  min_level: number;
}

export interface RankedSearchPreference {
  skill_id: string;
  target_level: number;
}

export interface RankedSearchRequestPayload {
  requirements: RankedSearchRequirement[];
  preferences: RankedSearchPreference[];
  max_results: number;
  weapon_kind?: string;
}

export interface EquipmentSlotResponse {
  kind: "weapon" | "armor";
  level: number;
}

export interface EquipmentResponse {
  equipment_id: string;
  display_name: string | null;
  part: "weapon" | "head" | "chest" | "arms" | "waist" | "legs" | "charm";
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

export interface RankedSearchResponse {
  candidates: RankedBuildCandidate[];
  exhausted: boolean;
  timed_out: boolean;
}
