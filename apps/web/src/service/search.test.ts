import { describe, expect, it, vi } from "vitest";
import { createInventoryStore } from "../../../../subprojects/inventory-checker/src/storage";
import { exportProfile, type InventoryProfile } from "../../../../subprojects/inventory-checker/src/domain";
import { ApiError } from "../api";
import { decodeBrowserSearchCatalog } from "../browser-solver/catalog";
import raw from "../browser-solver/fixtures/tiny-browser-catalog.json";
import inventoryOracle from "../browser-solver/fixtures/inventory-oracle.json";
import { solveBrowserRankedSearch } from "../browser-solver/solver";
import { makeTestCatalog } from "../browser-solver/test-catalog";
import type { BrowserSolverWorkerClient } from "../browser-solver/worker-client";
import type { BrowserRankedSearchRequest } from "../browser-solver/types";
import type { ServiceCatalog } from "./catalog";
import { eligibleFallback, SearchCoordinator } from "./search";

const browser = decodeBrowserSearchCatalog(raw);
function catalog(remoteEnabled = false): ServiceCatalog {
  return {
    raw, browser, remoteEnabled,
    checker: { schema_version: 1, revision: browser.source_catalog.sha256, generated_at: "2026-10-06T00:00:00Z", skills: [], decorations: [], fixed_charms: [], appraisal_charm_skill_groups: [], appraisal_charm_patterns: [] },
    metadata: { schema_version: 1, skills: [], decorations: [], weapon_kinds: [], features: { artian_series_skill_assignment: false, artian_group_skill_assignment: false, theoretical_appraisal_charms: false }, counts: { skills: 0, equipment: 0, decorations: 0, appraisal_charm_skill_groups: 0, appraisal_charm_patterns: 0 } },
  };
}
function fakeWorker() {
  return {
    initialize: vi.fn(async () => undefined),
    search: vi.fn(async (request: BrowserRankedSearchRequest) => solveBrowserRankedSearch(browser, request)),
    dispose: vi.fn(),
  };
}
const payload = { requirements: [], preferences: [], max_results: 2 };

describe("production search coordinator", () => {
  it.each(inventoryOracle.cases)("accepts genuine Python inventory API responses for $name", async (testCase) => {
    const worker = fakeWorker();
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, vi.fn().mockResolvedValue(testCase.python_response));
    await expect(service.search(testCase.request, { engine: "auto" })).resolves.toEqual(testCase.python_response);
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("still requires deterministic equipment ties for the inventory CP-SAT path", async () => {
    const testCase = inventoryOracle.cases.find((entry) => entry.name === "fixed-only")!;
    const response = { ...testCase.python_response, candidates: [...testCase.python_response.candidates].reverse() };
    const worker = fakeWorker();
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, vi.fn().mockResolvedValue(response));
    await expect(service.search(testCase.request, { engine: "auto" })).rejects.toThrow("順位");
    expect(worker.initialize).not.toHaveBeenCalled();
  });
  it("uses browser without any remote request when release disables remote", async () => {
    const worker = fakeWorker();
    const remote = vi.fn();
    const service = new SearchCoordinator(async () => catalog(), () => worker as unknown as BrowserSolverWorkerClient, remote);
    const result = await service.search(payload, { engine: "auto" });
    expect(result.candidates).toHaveLength(2);
    expect(remote).not.toHaveBeenCalled();
    expect(worker.dispose).toHaveBeenCalledOnce();
  });

  it.each([429, 500, 503])("falls back on eligible remote HTTP %s using the same request", async (status) => {
    const worker = fakeWorker();
    const remote = vi.fn().mockRejectedValue(new ApiError(status, "temporary failure"));
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, remote);
    await service.search(payload, { engine: "auto" });
    expect(remote.mock.calls[0]?.[0]).toEqual(worker.search.mock.calls[0]?.[0]);
  });

  it.each([400, 409, 422])("preserves HTTP %s without hiding invalid input or mismatch", async (status) => {
    const worker = fakeWorker();
    const error = new ApiError(status, "invalid request");
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, vi.fn().mockRejectedValue(error));
    await expect(service.search(payload, { engine: "auto" })).rejects.toBe(error);
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("does not fall back after the user cancels a remote request", async () => {
    const worker = fakeWorker();
    const controller = new AbortController();
    const remote = vi.fn(async () => { controller.abort(); throw new TypeError("network"); });
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, remote);
    await expect(service.search(payload, { engine: "auto", signal: controller.signal })).rejects.toMatchObject({ name: "AbortError" });
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("never treats an empty profile as unlimited inventory", async () => {
    const worker = fakeWorker();
    const store = createInventoryStore({ storage: { getItem: () => null, setItem: () => undefined }, locks: null });
    const service = new SearchCoordinator(async () => catalog(), () => worker as unknown as BrowserSolverWorkerClient, vi.fn(), store);
    await expect(service.search(payload, { owned: true })).rejects.toThrow("未登録");
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("rejects tampered remote candidates before rendering", async () => {
    const service = new SearchCoordinator(async () => catalog(true), undefined, vi.fn().mockResolvedValue({ candidates: [{ equipment: [], placements: [], skill_levels: [], preference_score: 0 }], exhausted: true, timed_out: false }));
    await expect(service.search(payload, { engine: "auto" })).rejects.toThrow();
  });

  it("distinguishes transport, input and cancellation errors", () => {
    expect(eligibleFallback(new TypeError("fetch failed"))).toBe(true);
    expect(eligibleFallback(new DOMException("cancel", "AbortError"))).toBe(false);
    expect(eligibleFallback(new Error("invalid result"))).toBe(false);
  });

  it("freezes profile and request before waiting for the catalog", async () => {
    const original: InventoryProfile = { schema_version: 1, profile_id: "private-profile", catalog_revision: browser.source_catalog.sha256, updated_at: "2026-10-06T00:00:00Z", decorations: [], fixed_charms: [], appraisal_charms: [] };
    let stored = exportProfile(original);
    const store = createInventoryStore({ storage: { getItem: () => stored, setItem: (_, value) => { stored = value; } }, locks: null });
    let finish!: (value: ServiceCatalog) => void;
    const pendingCatalog = new Promise<ServiceCatalog>((resolve) => { finish = resolve; });
    const worker = fakeWorker();
    const service = new SearchCoordinator(() => pendingCatalog, () => worker as unknown as BrowserSolverWorkerClient, vi.fn(), store);
    const mutable = { requirements: [], preferences: [], max_results: 2 };
    const request = service.search(mutable, { owned: true });
    stored = exportProfile({ ...original, decorations: [{ decoration_id: "new-unknown-entry", quantity: 8 }] });
    mutable.max_results = 1;
    finish(catalog());
    await request;
    expect(worker.search.mock.calls[0]?.[0].max_results).toBe(2);
    expect(worker.search.mock.calls[0]?.[0].inventory?.decorations).toEqual([]);
    expect(JSON.stringify(worker.search.mock.calls[0]?.[0])).not.toContain("private-profile");
    expect(JSON.stringify(worker.search.mock.calls[0]?.[0])).not.toContain("updated_at");
  });

  it("binds exclusion consent to the exact stored profile and catalog revision", async () => {
    const profile: InventoryProfile = { schema_version: 1, profile_id: "private-profile", catalog_revision: browser.source_catalog.sha256, updated_at: "2026-10-06T00:00:00Z", decorations: [{ decoration_id: "unknown-entry", quantity: 1 }], fixed_charms: [], appraisal_charms: [] };
    let stored = exportProfile(profile);
    const old = stored;
    const store = createInventoryStore({ storage: { getItem: () => stored, setItem: (_, value) => { stored = value; } }, locks: null });
    const worker = fakeWorker();
    const service = new SearchCoordinator(async () => catalog(), () => worker as unknown as BrowserSolverWorkerClient, vi.fn(), store);
    stored = exportProfile({ ...profile, decorations: [{ decoration_id: "unknown-entry", quantity: 2 }] });
    await expect(service.search(payload, { owned: true, acknowledgeExclusions: { raw: old, catalogRevision: browser.source_catalog.sha256 } })).rejects.toThrow("確認が必要");
    await expect(service.search(payload, { owned: true, acknowledgeExclusions: { raw: stored, catalogRevision: "old-revision" } })).rejects.toThrow("確認が必要");
    expect(worker.search).not.toHaveBeenCalled();
    await service.search(payload, { owned: true, acknowledgeExclusions: { raw: stored, catalogRevision: browser.source_catalog.sha256 } });
    expect(worker.search.mock.calls[0]?.[0].inventory?.decorations).toEqual([]);
  });

  it("rejects remote rank reversal and null responses without masking them as transport errors", async () => {
    const rankingRaw = makeTestCatalog({ decorations: [], equipment: { head: [{ equipment_id: "head:0" }, { equipment_id: "head:1", skills: [[1, 1]] }] } });
    const rankingCatalog = { ...catalog(true), raw: rankingRaw, browser: decodeBrowserSearchCatalog(rankingRaw) };
    const request = { ...payload, preferences: [{ skill_id: "skill:affinity", target_level: 1 }] };
    const solved = solveBrowserRankedSearch(rankingCatalog.browser, request);
    const candidates = [...(solved.candidates ?? [])].reverse();
    expect(candidates).toHaveLength(2);
    const worker = fakeWorker();
    const remote = vi.fn().mockResolvedValueOnce({ candidates, exhausted: solved.exhausted, timed_out: false }).mockResolvedValueOnce(null);
    const service = new SearchCoordinator(async () => rankingCatalog, () => worker as unknown as BrowserSolverWorkerClient, remote);
    await expect(service.search(request, { engine: "auto" })).rejects.toThrow("順位");
    await expect(service.search(request, { engine: "auto" })).rejects.toThrow("形式");
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("accepts valid equal-objective legacy CP-SAT ties in either equipment order", async () => {
    const solved = solveBrowserRankedSearch(browser, payload);
    const result = { candidates: [...solved.candidates!].reverse(), exhausted: solved.exhausted, timed_out: false };
    const worker = fakeWorker();
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, vi.fn().mockResolvedValue(result));
    await expect(service.search(payload, { engine: "auto" })).resolves.toEqual(result);
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("independently reconstructs valid remote theoretical charms omitted from a query catalog", async () => {
    const compact = structuredClone(raw);
    compact.equipment_by_part.charm = compact.equipment_by_part.charm.filter((item) => !item.equipment_id.startsWith("generated:"));
    compact.source_catalog.generated_appraisal_charm_count = 0;
    compact.source_catalog.expanded_equipment_count = Object.values(compact.equipment_by_part).reduce((sum, part) => sum + part.length, 0);
    const queryRaw = { ...compact, theoretical_appraisal_mode: "query" };
    const queryCatalog = { ...catalog(true), raw: queryRaw, browser: decodeBrowserSearchCatalog(queryRaw) };
    const request = inventoryOracle.theoretical.request;
    const result = inventoryOracle.theoretical.python_response;
    expect(result.candidates).toHaveLength(2);
    expect(result.candidates.every((candidate) => candidate.equipment[6]!.equipment_id.startsWith("generated:"))).toBe(true);
    const worker = fakeWorker();
    const remote = vi.fn().mockResolvedValue(result);
    const service = new SearchCoordinator(async () => queryCatalog, () => worker as unknown as BrowserSolverWorkerClient, remote);
    await expect(service.search(request, { engine: "auto" })).resolves.toEqual(result);
    const forged = structuredClone(result);
    forged.candidates![0]!.equipment[6]!.equipment_id = "generated:appraisal-charm:rarity-8:fixture:appraisal-pattern:r8-b-a-j-w1-a1-a1:combination-1";
    remote.mockResolvedValueOnce(forged);
    await expect(service.search(request, { engine: "auto" })).rejects.toThrow("repeats base skill");
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("does not mistake malformed nested remote equipment for a network failure", async () => {
    const worker = fakeWorker();
    const remote = vi.fn().mockResolvedValue({ candidates: [{ equipment: [null], placements: [], skill_levels: [], preference_score: 0 }], exhausted: true, timed_out: false });
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, remote);
    await expect(service.search(payload, { engine: "auto" })).rejects.toThrow("装備が不正");
    expect(worker.initialize).not.toHaveBeenCalled();
  });

  it("accepts valid remote equipment with differently ordered JSON object keys", async () => {
    const solved = solveBrowserRankedSearch(browser, payload);
    const reverseKeys = (value: unknown): unknown => Array.isArray(value) ? value.map(reverseKeys) : value && typeof value === "object" ? Object.fromEntries(Object.entries(value).reverse().map(([key, nested]) => [key, reverseKeys(nested)])) : value;
    const result = reverseKeys({ candidates: solved.candidates, exhausted: solved.exhausted, timed_out: false });
    const worker = fakeWorker();
    const service = new SearchCoordinator(async () => catalog(true), () => worker as unknown as BrowserSolverWorkerClient, vi.fn().mockResolvedValue(result));
    await expect(service.search(payload, { engine: "auto" })).resolves.toEqual(result);
    expect(worker.initialize).not.toHaveBeenCalled();
  });
});
