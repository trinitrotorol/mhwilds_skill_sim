import type {
  CatalogSlot, DecodedBrowserCatalog, IndexedEquipmentVariant, RankedBuildCandidate,
} from "./types";

export interface InventorySkill { readonly skill_id: string; readonly level: number }
export interface InventorySlot { readonly kind: "weapon" | "armor"; readonly level: number }
export interface InventoryAppraisalCharm {
  readonly instance_id: string;
  readonly rarity: number;
  readonly skills: readonly InventorySkill[];
  readonly slots: readonly InventorySlot[];
  readonly quantity: number;
}
export interface InventorySearchSnapshot {
  readonly schema_version: 1;
  readonly catalog_revision: string;
  readonly decorations: readonly { readonly decoration_id: string; readonly quantity: number }[];
  readonly fixed_charms: readonly { readonly equipment_id: string; readonly quantity: number }[];
  readonly appraisal_charms: readonly InventoryAppraisalCharm[];
}
export interface AppraisalRules {
  readonly appraisal_charm_skill_groups: readonly {
    readonly group_id: string; readonly skills: readonly InventorySkill[];
  }[];
  readonly appraisal_charm_patterns: readonly {
    readonly pattern_id: string; readonly rarity: number;
    readonly skill_group_ids: readonly string[]; readonly slots: readonly InventorySlot[];
  }[];
}

export class InventoryValidationError extends Error {
  constructor(message: string) { super(message); this.name = "InventoryValidationError"; }
}
export class InventoryCatalogMismatchError extends InventoryValidationError {
  constructor() { super("inventory catalog revision does not match search catalog"); this.name = "InventoryCatalogMismatchError"; }
}
function object(value: unknown, keys: readonly string[]): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value) ||
      ![Object.prototype, null].includes(Object.getPrototypeOf(value))) {
    throw new InventoryValidationError("expected plain inventory object");
  }
  const record = value as Record<string, unknown>;
  if (Object.keys(record).length !== keys.length || keys.some((key) => !Object.hasOwn(record, key))) {
    throw new InventoryValidationError("inventory fields do not match version 1 contract");
  }
  return record;
}
function identifier(value: unknown): string {
  if (typeof value !== "string" || value.length < 1 || value.length > 512 || value.trim() !== value) {
    throw new InventoryValidationError("invalid inventory identifier");
  }
  return value;
}
function integer(value: unknown, min = 0, max = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < min || value > max) {
    throw new InventoryValidationError("inventory number must be a safe integer in range");
  }
  return value;
}
function entries(value: unknown, max = 10000): unknown[] {
  if (!Array.isArray(value) || value.length > max) throw new InventoryValidationError("inventory list exceeds size limit");
  return value;
}
function unique<T>(values: readonly T[], key: (value: T) => string): readonly T[] {
  if (new Set(values.map(key)).size !== values.length) throw new InventoryValidationError("duplicate inventory identifier");
  return Object.freeze(values);
}
function skills(value: unknown): readonly InventorySkill[] {
  if (entries(value, 3).length === 0) throw new InventoryValidationError("appraisal skills must not be empty");
  return unique(entries(value, 3).map((entry) => {
    const record = object(entry, ["skill_id", "level"]);
    return Object.freeze({ skill_id: identifier(record.skill_id), level: integer(record.level, 1) });
  }), (skill) => skill.skill_id);
}
function slots(value: unknown): readonly InventorySlot[] {
  const result = entries(value, 4).map((entry) => {
    const record = object(entry, ["kind", "level"]);
    if (record.kind !== "weapon" && record.kind !== "armor") throw new InventoryValidationError("invalid slot kind");
    return Object.freeze({ kind: record.kind, level: integer(record.level, 1) });
  });
  const weapons = result.filter((slot) => slot.kind === "weapon").length;
  if (weapons > 1 || result.length - weapons > 3 || (weapons === 1 && result[0]?.kind !== "weapon")) throw new InventoryValidationError("invalid appraisal slot ordering or count");
  return Object.freeze(result);
}

/** Strict structural decoder. Catalog references and game rules are checked separately. */
export function decodeInventorySearchSnapshot(value: unknown): InventorySearchSnapshot {
  const record = object(value, ["schema_version", "catalog_revision", "decorations", "fixed_charms", "appraisal_charms"]);
  if (record.schema_version !== 1) throw new InventoryValidationError("unsupported inventory snapshot version");
  const revision = identifier(record.catalog_revision);
  if (!/^[a-f0-9]{64}$/u.test(revision)) throw new InventoryValidationError("catalog revision must be SHA256");
  const decorations = unique(entries(record.decorations).map((entry) => {
    const item = object(entry, ["decoration_id", "quantity"]);
    return Object.freeze({ decoration_id: identifier(item.decoration_id), quantity: integer(item.quantity) });
  }), (entry) => entry.decoration_id);
  const fixedCharms = unique(entries(record.fixed_charms).map((entry) => {
    const item = object(entry, ["equipment_id", "quantity"]);
    return Object.freeze({ equipment_id: identifier(item.equipment_id), quantity: integer(item.quantity) });
  }), (entry) => entry.equipment_id);
  const appraisalCharms = unique(entries(record.appraisal_charms, 1000).map((entry) => {
    const item = object(entry, ["instance_id", "rarity", "skills", "slots", "quantity"]);
    const instanceId = identifier(item.instance_id);
    if (!/^owned:\d+$/u.test(instanceId)) throw new InventoryValidationError("appraisal ID must be anonymous owned:index");
    return Object.freeze({ instance_id: instanceId, rarity: integer(item.rarity, 1), skills: skills(item.skills), slots: slots(item.slots), quantity: integer(item.quantity) });
  }), (entry) => entry.instance_id);
  return Object.freeze({ schema_version: 1, catalog_revision: revision, decorations, fixed_charms: fixedCharms, appraisal_charms: appraisalCharms });
}

export function decodeAppraisalRules(value: unknown): AppraisalRules {
  const record = object(value, ["appraisal_charm_skill_groups", "appraisal_charm_patterns"]);
  const groups = unique(entries(record.appraisal_charm_skill_groups, 1000).map((entry) => {
    const group = object(entry, ["group_id", "skills"]);
    // Groups contain alternatives, not the maximum three skills on one charm.
    const alternatives = unique(entries(group.skills, 1000).map((option) => {
      const skill = object(option, ["skill_id", "level"]);
      return Object.freeze({ skill_id: identifier(skill.skill_id), level: integer(skill.level, 1) });
    }), (skill) => skill.skill_id);
    if (alternatives.length === 0) throw new InventoryValidationError("empty appraisal skill group");
    return Object.freeze({ group_id: identifier(group.group_id), skills: alternatives });
  }), (group) => group.group_id);
  const patterns = unique(entries(record.appraisal_charm_patterns, 1000).map((entry) => {
    const pattern = object(entry, ["pattern_id", "rarity", "skill_group_ids", "slots"]);
    const groupIds = Object.freeze(entries(pattern.skill_group_ids, 3).map(identifier));
    if (groupIds.length === 0 || groupIds.some((id) => !groups.some((group) => group.group_id === id))) throw new InventoryValidationError("invalid appraisal group reference");
    return Object.freeze({ pattern_id: identifier(pattern.pattern_id), rarity: integer(pattern.rarity, 1), skill_group_ids: groupIds, slots: slots(pattern.slots) });
  }), (pattern) => pattern.pattern_id);
  return Object.freeze({ appraisal_charm_skill_groups: groups, appraisal_charm_patterns: patterns });
}

function matchesRules(charm: InventoryAppraisalCharm, catalog: DecodedBrowserCatalog): boolean {
  const rules = catalog.appraisal_rules;
  if (!rules) return false;
  const target = new Map(charm.skills.map((skill) => [skill.skill_id, skill.level]));
  if (target.size === 0 || charm.skills.some((skill) => {
    const index = catalog.indexed.skill_index_by_id.get(skill.skill_id);
    const definition = index === undefined ? undefined : catalog.skills[index];
    return !definition || !["weapon", "armor"].includes(definition.kind) || skill.level > definition.max_level;
  })) return false;
  return rules.appraisal_charm_patterns.some((pattern) => {
    if (pattern.rarity !== charm.rarity || JSON.stringify(pattern.slots) !== JSON.stringify(charm.slots)) return false;
    const remaining = new Map(target);
    const selectedSkills = new Set<string>();
    const visit = (depth: number): boolean => {
      if (depth === pattern.skill_group_ids.length) return [...remaining.values()].every((level) => level === 0);
      const group = rules.appraisal_charm_skill_groups.find((item) => item.group_id === pattern.skill_group_ids[depth]);
      return group?.skills.some((skill) => {
        const available = remaining.get(skill.skill_id) ?? 0;
        if (available < skill.level || selectedSkills.has(skill.skill_id)) return false;
        remaining.set(skill.skill_id, available - skill.level);
        selectedSkills.add(skill.skill_id);
        const matched = visit(depth + 1);
        selectedSkills.delete(skill.skill_id);
        remaining.set(skill.skill_id, available);
        return matched;
      }) ?? false;
    };
    return visit(0);
  });
}

/** Builds an isolated candidate view; the static catalog and saved profile stay unchanged. */
export function applyInventoryToCatalog(catalog: DecodedBrowserCatalog, snapshot: InventorySearchSnapshot): DecodedBrowserCatalog {
  if (snapshot.catalog_revision !== catalog.source_catalog.sha256) throw new InventoryCatalogMismatchError();
  for (const entry of snapshot.decorations) {
    if (!catalog.indexed.decoration_index_by_id.has(entry.decoration_id)) throw new InventoryValidationError(`unknown decoration ${entry.decoration_id}`);
  }
  const fixed = new Map(snapshot.fixed_charms.map((item) => [item.equipment_id, item.quantity]));
  for (const id of fixed.keys()) {
    if (id.startsWith("generated:") || !catalog.equipment_by_part.charm.some((item) => item.equipment_id === id)) throw new InventoryValidationError(`unknown fixed charm ${id}`);
  }
  const variants = catalog.indexed.variants_by_id.filter((item) => !/^owned:\d+$/u.test(item.definition.equipment_id));
  const charms = catalog.indexed.equipment_by_part.charm.filter((item) => (fixed.get(item.definition.equipment_id) ?? 0) > 0);
  for (const item of snapshot.appraisal_charms) {
    if (!matchesRules(item, catalog)) throw new InventoryValidationError(`appraisal charm ${item.instance_id} does not match catalog rules`);
    if (item.quantity === 0) continue;
    const indexedSkills = item.skills.map((skill) => [catalog.indexed.skill_index_by_id.get(skill.skill_id)!, skill.level] as const);
    const definition = Object.freeze({ variant_id: variants.length, equipment_id: item.instance_id, display_name: null, part: "charm" as const, weapon_kind: null, series_skill_id: null, group_skill_id: null, series_skill_ids: [], group_skill_ids: [], skills: indexedSkills, slots: item.slots.map((slot) => [slot.kind, slot.level] as CatalogSlot) });
    const variant: IndexedEquipmentVariant = Object.freeze({ definition, skills: Int32Array.from(indexedSkills.flat()), series_skill_ids: new Int32Array(), group_skill_ids: new Int32Array(), slots: Int32Array.from(item.slots.flatMap((slot) => [slot.kind === "weapon" ? 0 : 1, slot.level])) });
    variants.push(variant);
    charms.push(variant);
  }
  const maximumSlotLevel = charms.reduce((maximum, item) => item.definition.slots.reduce((current, slot) => Math.max(current, slot[1]), maximum), catalog.indexed.maximum_slot_level);
  return Object.freeze({ ...catalog, equipment_by_part: Object.freeze({ ...catalog.equipment_by_part, charm: Object.freeze(charms.map((item) => item.definition)) }), indexed: Object.freeze({ ...catalog.indexed, maximum_slot_level: maximumSlotLevel, variants_by_id: Object.freeze(variants), equipment_by_part: Object.freeze({ ...catalog.indexed.equipment_by_part, charm: Object.freeze(charms) }) }) });
}

export function validateCandidateInventory(candidate: RankedBuildCandidate, snapshot: InventorySearchSnapshot): void {
  const quantities = new Map(snapshot.decorations.map((entry) => [entry.decoration_id, entry.quantity]));
  const used = new Map<string, number>();
  for (const placement of candidate.placements) {
    const count = (used.get(placement.decoration_id) ?? 0) + 1;
    if (count > (quantities.get(placement.decoration_id) ?? 0)) throw new InventoryValidationError("candidate exceeds owned decoration quantity");
    used.set(placement.decoration_id, count);
  }
  const charm = candidate.equipment.find((item) => item.part === "charm");
  if (!charm || ![...snapshot.fixed_charms.map((entry) => ({ id: entry.equipment_id, quantity: entry.quantity })), ...snapshot.appraisal_charms.map((entry) => ({ id: entry.instance_id, quantity: entry.quantity }))].some((entry) => entry.id === charm.equipment_id && entry.quantity > 0)) throw new InventoryValidationError("candidate uses unowned charm");
}
