import type { InventorySkill } from "./inventory";
import type {
  BrowserRankedSearchRequest, DecodedBrowserCatalog, IndexedEquipmentVariant,
  RankedBuildCandidate,
} from "./types";

export class BrowserSearchLimitError extends Error {
  constructor() { super("search exceeds the bounded browser working set; reduce search conditions"); this.name = "BrowserSearchLimitError"; }
}
const MAXIMUM_QUERY_CHARM_REPRESENTATIVES = 100_000;

function patternChoices(catalog: DecodedBrowserCatalog, index: number) {
  const rules = catalog.appraisal_rules;
  const pattern = rules?.appraisal_charm_patterns[index];
  if (!rules || !pattern) throw new Error("missing appraisal query rules");
  const groups = pattern.skill_group_ids.map((id) => {
    const group = rules.appraisal_charm_skill_groups.find((item) => item.group_id === id);
    if (!group) throw new Error("missing appraisal group");
    return group.skills;
  });
  const count = groups.reduce((total, group) => total * group.length, 1);
  if (!Number.isSafeInteger(count)) throw new BrowserSearchLimitError();
  return { pattern, groups, count };
}

function variant(catalog: DecodedBrowserCatalog, patternIndex: number, combination: number, variantId: number, skills: readonly InventorySkill[]): IndexedEquipmentVariant {
  const { pattern } = patternChoices(catalog, patternIndex);
  const indexedSkills = skills.map((skill) => [catalog.indexed.skill_index_by_id.get(skill.skill_id)!, skill.level] as const);
  const slots = pattern.slots.map((slot) => [slot.kind, slot.level] as const);
  const definition = Object.freeze({
    variant_id: variantId,
    equipment_id: `generated:appraisal-charm:rarity-${pattern.rarity}:${pattern.pattern_id}:combination-${combination}`,
    display_name: null, part: "charm" as const, weapon_kind: null,
    series_skill_id: null, group_skill_id: null, series_skill_ids: [], group_skill_ids: [],
    skills: indexedSkills, slots,
  });
  return Object.freeze({ definition, skills: Int32Array.from(indexedSkills.flat()), slots: Int32Array.from(slots.flatMap(([kind, level]) => [kind === "weapon" ? 0 : 1, level])), series_skill_ids: new Int32Array(), group_skill_ids: new Int32Array() });
}

function addVariants(catalog: DecodedBrowserCatalog, variants: readonly IndexedEquipmentVariant[]): DecodedBrowserCatalog {
  const charms = [...catalog.indexed.equipment_by_part.charm, ...variants];
  const maximumSlotLevel = charms.reduce((maximum, item) => item.definition.slots.reduce((current, slot) => Math.max(current, slot[1]), maximum), catalog.indexed.maximum_slot_level);
  return {
    ...catalog,
    equipment_by_part: { ...catalog.equipment_by_part, charm: charms.map((item) => item.definition) },
    indexed: { ...catalog.indexed, maximum_slot_level: maximumSlotLevel,
      dynamic_variants_by_id: new Map(variants.map((item) => [item.definition.variant_id, item])),
      equipment_by_part: { ...catalog.indexed.equipment_by_part, charm: charms },
    },
  };
}

/**
 * Stream legal rolls; retain K earliest distinct abilities per requested skill /
 * slot signature. Any discarded charm has K no-worse earlier equivalents for
 * every other equipment selection, and therefore cannot enter the global top K.
 * Recipe ordinal IDs retain the full rule order without sparse giant arrays.
 */
export function prepareQueryAppraisals(
  catalog: DecodedBrowserCatalog, request: BrowserRankedSearchRequest,
  shouldStop: () => boolean,
): { catalog: DecodedBrowserCatalog; interrupted: boolean } {
  if (catalog.theoretical_appraisal_mode !== "query" || request.inventory) return { catalog, interrupted: false };
  const caps = new Map<string, number>();
  for (const requirement of request.requirements) caps.set(requirement.skill_id, Math.max(caps.get(requirement.skill_id) ?? 0, requirement.min_level));
  for (const preference of request.preferences) caps.set(preference.skill_id, Math.max(caps.get(preference.skill_id) ?? 0, preference.target_level));
  const buckets = new Map<string, Set<string>>();
  const retained: IndexedEquipmentVariant[] = [];
  let offset = catalog.indexed.variants_by_id.length;
  let steps = 0;
  let interrupted = false;
  const rules = catalog.appraisal_rules;
  if (!rules) throw new Error("appraisal query catalog is missing rules");
  for (let index = 0; index < rules.appraisal_charm_patterns.length; index += 1) {
    if (shouldStop()) { interrupted = true; break; }
    const { pattern, groups, count } = patternChoices(catalog, index);
    if (!Number.isSafeInteger(offset + count)) throw new BrowserSearchLimitError();
    const multipliers = groups.map((_, depth) => groups.slice(depth + 1).reduce((total, group) => total * group.length, 1));
    const selected: InventorySkill[] = [];
    const selectedIds = new Set<string>();
    const visit = (depth: number, ordinal: number) => {
      if (interrupted) return;
      steps += 1;
      if (steps % 1024 === 0 && shouldStop()) { interrupted = true; return; }
      if (depth === groups.length) {
        const full = selected.map((skill) => [skill.skill_id, skill.level] as const).sort((a, b) => a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0);
        const projection = full.filter(([id]) => caps.has(id)).map(([id, level]) => [id, Math.min(level, caps.get(id)!)]);
        const key = JSON.stringify([projection, pattern.slots]);
        const bucket = buckets.get(key) ?? new Set<string>();
        if (bucket.size >= request.max_results) return;
        const signature = JSON.stringify(full);
        if (bucket.has(signature)) return;
        if (retained.length >= MAXIMUM_QUERY_CHARM_REPRESENTATIVES) throw new BrowserSearchLimitError();
        bucket.add(signature);
        buckets.set(key, bucket);
        retained.push(variant(catalog, index, ordinal + 1, offset + ordinal, selected));
        return;
      }
      const group = groups[depth]!;
      for (let choice = 0; choice < group.length; choice += 1) {
        const skill = group[choice]!;
        if (selectedIds.has(skill.skill_id)) continue;
        selectedIds.add(skill.skill_id);
        selected.push(skill);
        visit(depth + 1, ordinal + choice * multipliers[depth]!);
        selected.pop();
        selectedIds.delete(skill.skill_id);
        if (interrupted) return;
      }
    };
    visit(0, 0);
    offset += count;
    if (interrupted) break;
  }
  return { catalog: addVariants(catalog, retained), interrupted };
}

/** Independent recipe reconstruction: does not reuse projected search buckets. */
export function catalogForQueryResultValidation(catalog: DecodedBrowserCatalog, candidates: readonly RankedBuildCandidate[]): DecodedBrowserCatalog {
  if (catalog.theoretical_appraisal_mode !== "query") return catalog;
  const variants = new Map<string, IndexedEquipmentVariant>();
  for (const candidate of candidates) {
    const charm = candidate.equipment.find((item) => item.part === "charm");
    if (!charm || !charm.equipment_id.startsWith("generated:appraisal-charm:")) continue;
    if (variants.has(charm.equipment_id)) continue;
    let offset = catalog.indexed.variants_by_id.length;
    let found = false;
    for (let index = 0; index < (catalog.appraisal_rules?.appraisal_charm_patterns.length ?? 0); index += 1) {
      const { pattern, groups, count } = patternChoices(catalog, index);
      const prefix = `generated:appraisal-charm:rarity-${pattern.rarity}:${pattern.pattern_id}:combination-`;
      if (charm.equipment_id.startsWith(prefix)) {
        const suffix = charm.equipment_id.slice(prefix.length);
        const number = Number(suffix);
        if (!/^[1-9][0-9]*$/u.test(suffix) || !Number.isSafeInteger(number) || number > count) throw new Error("invalid appraisal recipe ordinal");
        let remainder = number - 1;
        const selected: InventorySkill[] = [];
        for (let depth = groups.length - 1; depth >= 0; depth -= 1) {
          const group = groups[depth]!;
          selected.unshift(group[remainder % group.length]!);
          remainder = Math.floor(remainder / group.length);
        }
        if (new Set(selected.map((skill) => skill.skill_id)).size !== selected.length) throw new Error("appraisal recipe repeats base skill");
        variants.set(charm.equipment_id, variant(catalog, index, number, offset + number - 1, selected));
        found = true;
        break;
      }
      offset += count;
    }
    if (!found) throw new Error("unknown appraisal recipe");
  }
  // Validation needs only returned recipes, never the full theoretical space.
  return addVariants(catalog, [...variants.values()]);
}
