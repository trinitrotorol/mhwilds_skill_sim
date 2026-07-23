import {
  EQUIPMENT_PARTS,
  type EquipmentPart,
  type SkillKind,
  type SlotKind,
} from "./types";

export interface TestSkill {
  skill_id: string;
  display_name: string | null;
  kind: SkillKind;
  max_level: number;
  required_pieces: number[];
}

export interface TestVariantInput {
  equipment_id: string;
  display_name?: string | null;
  weapon_kind?: string | null;
  series_skill_id?: number | null;
  group_skill_id?: number | null;
  series_skill_ids?: number[];
  group_skill_ids?: number[];
  skills?: Array<[number, number]>;
  slots?: Array<[SlotKind, number]>;
}

export interface TestVariant extends TestVariantInput {
  variant_id: number;
  display_name: string | null;
  part: EquipmentPart;
  weapon_kind: string | null;
  series_skill_id: number | null;
  group_skill_id: number | null;
  series_skill_ids: number[];
  group_skill_ids: number[];
  skills: Array<[number, number]>;
  slots: Array<[SlotKind, number]>;
}

export interface TestDecoration {
  decoration_id: string;
  display_name: string | null;
  required_slot: [SlotKind, number];
  skills: Array<[number, number]>;
}

export interface TestCatalog {
  format_version: number;
  source_catalog: {
    schema_version: number;
    sha256: string;
    source_equipment_count: number;
    generated_appraisal_charm_count: number;
    expanded_equipment_count: number;
    decoration_count: number;
    skill_count: number;
  };
  skills: TestSkill[];
  equipment_by_part: Record<EquipmentPart, TestVariant[]>;
  decorations: TestDecoration[];
}

const DEFAULT_SKILLS: TestSkill[] = [
  {
    skill_id: "skill:attack",
    display_name: "Attack",
    kind: "armor",
    max_level: 10,
    required_pieces: [],
  },
  {
    skill_id: "skill:affinity",
    display_name: "Affinity",
    kind: "armor",
    max_level: 10,
    required_pieces: [],
  },
  {
    skill_id: "skill:series",
    display_name: "Series",
    kind: "set",
    max_level: 2,
    required_pieces: [2, 4],
  },
  {
    skill_id: "skill:group",
    display_name: "Group",
    kind: "group",
    max_level: 1,
    required_pieces: [3],
  },
];

const DEFAULT_EQUIPMENT: Record<
  EquipmentPart,
  TestVariantInput[]
> = {
  weapon: [
    {
      equipment_id: "equipment:weapon",
      weapon_kind: "great-sword",
      skills: [[0, 1]],
      slots: [["weapon", 2]],
    },
  ],
  head: [
    {
      equipment_id: "equipment:head",
      slots: [["armor", 2]],
    },
  ],
  chest: [{ equipment_id: "equipment:chest" }],
  arms: [{ equipment_id: "equipment:arms" }],
  waist: [{ equipment_id: "equipment:waist" }],
  legs: [{ equipment_id: "equipment:legs" }],
  charm: [{ equipment_id: "equipment:charm" }],
};

const DEFAULT_DECORATIONS: TestDecoration[] = [
  {
    decoration_id: "decoration:z-attack",
    display_name: "Z Attack",
    required_slot: ["armor", 1],
    skills: [[0, 1]],
  },
  {
    decoration_id: "decoration:a-compound",
    display_name: "A Compound",
    required_slot: ["armor", 2],
    skills: [
      [0, 1],
      [1, 1],
    ],
  },
  {
    decoration_id: "decoration:weapon-attack",
    display_name: "Weapon Attack",
    required_slot: ["weapon", 1],
    skills: [[0, 1]],
  },
  {
    decoration_id: "decoration:affinity",
    display_name: "Affinity",
    required_slot: ["armor", 1],
    skills: [[1, 1]],
  },
];

export function makeTestCatalog(options: {
  skills?: TestSkill[];
  equipment?: Partial<Record<EquipmentPart, TestVariantInput[]>>;
  decorations?: TestDecoration[];
} = {}): TestCatalog {
  const skills = structuredClone(options.skills ?? DEFAULT_SKILLS);
  const decorations = structuredClone(
    options.decorations ?? DEFAULT_DECORATIONS,
  );
  const equipmentByPart = {} as Record<EquipmentPart, TestVariant[]>;
  let variantId = 0;
  for (const part of EQUIPMENT_PARTS) {
    const inputs = structuredClone(
      options.equipment?.[part] ?? DEFAULT_EQUIPMENT[part],
    );
    equipmentByPart[part] = inputs.map((input) => ({
      variant_id: variantId++,
      equipment_id: input.equipment_id,
      display_name: input.display_name ?? null,
      part,
      weapon_kind: input.weapon_kind ?? null,
      series_skill_id: input.series_skill_id ?? null,
      group_skill_id: input.group_skill_id ?? null,
      series_skill_ids: input.series_skill_ids ?? [],
      group_skill_ids: input.group_skill_ids ?? [],
      skills: input.skills ?? [],
      slots: input.slots ?? [],
    }));
  }
  return {
    format_version: 1,
    source_catalog: {
      schema_version: 1,
      sha256: "0".repeat(64),
      source_equipment_count: variantId,
      generated_appraisal_charm_count: 0,
      expanded_equipment_count: variantId,
      decoration_count: decorations.length,
      skill_count: skills.length,
    },
    skills,
    equipment_by_part: equipmentByPart,
    decorations,
  };
}
