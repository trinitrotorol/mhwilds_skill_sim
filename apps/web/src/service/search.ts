import { toSearchInventory } from "../../../../subprojects/inventory-checker/src/domain";
import { createInventoryStore } from "../../../../subprojects/inventory-checker/src/storage";
import { ApiError, searchRankedBuilds as remoteSearch } from "../api";
import { BrowserSolverWorkerClient } from "../browser-solver/worker-client";
import { decodeBrowserRankedSearchRequest, equipmentVariantToResponse, equalJsonValue, validateBrowserSolverResult, validateRankedBuildCandidate } from "../browser-solver/validation";
import { applyInventoryToCatalog, validateCandidateInventory } from "../browser-solver/inventory";
import { catalogForQueryResultValidation } from "../browser-solver/appraisal-query";
import { compareNumberArraysLexicographically } from "../browser-solver/objective";
import type { BrowserRankedSearchRequest, BrowserSolverProgress } from "../browser-solver/types";
import type { RankedSearchRequestPayload, RankedSearchResponse } from "../types";
import { loadServiceCatalog, type ServiceCatalog } from "./catalog";

export type Engine = "browser" | "auto";
export interface InventoryAcknowledgment { raw: string; catalogRevision: string }
export interface SearchOptions {
  signal?: AbortSignal;
  engine?: Engine;
  owned?: boolean;
  acknowledgeExclusions?: InventoryAcknowledgment | null;
  onProgress?: (progress: BrowserSolverProgress) => void;
  onEngine?: (engine: "browser" | "remote") => void;
}
export function eligibleFallback(error: unknown): boolean {
  return error instanceof ApiError
    ? error.status === 429 || error.status >= 500
    : error instanceof TypeError || (error instanceof DOMException && error.name === "TimeoutError");
}

export class SearchCoordinator {
  #catalog: ServiceCatalog | null = null;
  #generation = 0;
  #active: AbortController | null = null;
  constructor(
    readonly load = loadServiceCatalog,
    readonly makeWorker = () => new BrowserSolverWorkerClient(),
    readonly remote = remoteSearch,
    readonly store = createInventoryStore(),
  ) {}

  async catalog(signal = new AbortController().signal): Promise<ServiceCatalog> {
    signal.throwIfAborted();
    if (this.#catalog) return this.#catalog;
    const catalog = await this.load(signal);
    signal.throwIfAborted();
    this.#catalog = catalog;
    return catalog;
  }

  async search(payload: RankedSearchRequestPayload, options: SearchOptions = {}): Promise<RankedSearchResponse> {
    this.#active?.abort();
    this.#active = new AbortController();
    const signal = options.signal ? AbortSignal.any([options.signal, this.#active.signal]) : this.#active.signal;
    const generation = ++this.#generation;
    const assertCurrent = () => { signal.throwIfAborted(); if (generation !== this.#generation) throw new DOMException("新しい検索を開始しました。", "AbortError"); };
    // Freeze the user's inputs before any catalog/network wait. A checker update
    // during loading belongs to the next search, never this request.
    const request: BrowserRankedSearchRequest = structuredClone(payload);
    const inventoryState = options.owned ? this.store.read() : null;
    const acknowledgment = options.acknowledgeExclusions ? { ...options.acknowledgeExclusions } : null;
    if (inventoryState && (inventoryState.status !== "ready" || !inventoryState.profile)) throw new Error(inventoryState.error ?? "所持品が未登録です。チェッカーで登録してください。");
    const catalog = await this.catalog(signal);
    assertCurrent();
    if (inventoryState?.profile) {
      const accepted = acknowledgment?.raw === inventoryState.raw && acknowledgment?.catalogRevision === catalog.checker.revision;
      const adapted = toSearchInventory(inventoryState.profile, catalog.checker, { acknowledgeCatalogChange: accepted, excludeInvalid: accepted });
      if (adapted.status !== "ready") throw new Error(`所持品の確認が必要です。${adapted.warnings.join(" ")}`);
      Object.assign(request, { inventory: structuredClone(adapted.snapshot) });
    }
    decodeBrowserRankedSearchRequest(request);
    // The immutable snapshot is reused across engines. Remote remains fail-closed
    // unless the server-issued release configuration explicitly enables it.
    if (options.engine === "auto" && catalog.remoteEnabled) {
      const remoteSignal = AbortSignal.any([signal, AbortSignal.timeout(12_000)]);
      let responseReceived = false;
      try {
        options.onEngine?.("remote");
        const result = await this.remote({ ...request, requirements: [...request.requirements], preferences: [...request.preferences] }, { signal: remoteSignal });
        responseReceived = true;
        assertCurrent();
        if (!result || typeof result !== "object" || !Array.isArray(result.candidates) || result.candidates.length > request.max_results || typeof result.exhausted !== "boolean" || typeof result.timed_out !== "boolean" || (result.exhausted && result.timed_out)) throw new Error("検索結果の形式が不正です。");
        const validationCatalog = request.inventory ? applyInventoryToCatalog(catalog.browser, request.inventory) : catalogForQueryResultValidation(catalog.browser, result.candidates);
        const validationVariants = [...validationCatalog.indexed.variants_by_id, ...(validationCatalog.indexed.dynamic_variants_by_id?.values() ?? [])];
        const signatures = new Set<string>();
        let previous: { candidate: RankedSearchResponse["candidates"][number]; ids: number[] } | null = null;
        for (const candidate of result.candidates) {
          if (!candidate || typeof candidate !== "object" || !Array.isArray(candidate.equipment)) throw new Error("検索結果の装備が不正です。");
          const ids = candidate.equipment.map((equipment) => {
            if (!equipment || typeof equipment !== "object" || typeof equipment.equipment_id !== "string") throw new Error("検索結果の装備が不正です。");
            const variant = validationVariants.find((item) => item.definition.equipment_id === equipment.equipment_id && equalJsonValue(equipmentVariantToResponse(validationCatalog, item), equipment));
            if (!variant) throw new Error("検索結果の装備がカタログと一致しません。");
            return variant.definition.variant_id;
          });
          const signature = JSON.stringify(ids);
          if (signatures.has(signature)) throw new Error("検索結果が重複しています。");
          signatures.add(signature);
          validateRankedBuildCandidate(validationCatalog, request, candidate, ids);
          if (request.inventory) validateCandidateInventory(candidate, request.inventory);
          if (previous) {
            // Legacy CP-SAT promises score/count ordering, with unspecified
            // equal-objective ties. Inventory CP-SAT additionally resolves the
            // catalog equipment order, matching the browser engine.
            const order = previous.candidate.preference_score - candidate.preference_score || candidate.placements.length - previous.candidate.placements.length || (request.inventory ? -compareNumberArraysLexicographically(previous.ids, ids) : 0);
            if (order < 0) throw new Error("検索結果の順位が不正です。");
          }
          previous = { candidate, ids };
        }
        return result;
      } catch (error) { assertCurrent(); if (responseReceived || (!eligibleFallback(error) && !remoteSignal.aborted)) throw error; }
    }
    assertCurrent();
    options.onEngine?.("browser");
    const worker = this.makeWorker();
    const abort = () => worker.dispose();
    signal.addEventListener("abort", abort, { once: true });
    try {
      assertCurrent();
      await worker.initialize(catalog.raw);
      assertCurrent();
      const result = await worker.search(request, { timeoutMs: 15_000, onProgress: options.onProgress });
      assertCurrent();
      if (result.status === "cancelled") throw new DOMException("中断しました。", "AbortError");
      validateBrowserSolverResult(catalog.browser, request, result);
      return {
        candidates: result.candidates ?? (result.candidate ? [result.candidate] : []),
        exhausted: result.exhausted ?? result.status === "infeasible",
        timed_out: result.timed_out ?? result.status === "timed-out",
      };
    } finally { signal.removeEventListener("abort", abort); worker.dispose(); }
  }
}

const service = new SearchCoordinator();
export function fetchServiceCatalog(signal?: AbortSignal) { return service.catalog(signal); }
export async function fetchCatalogMetadata(options?: { signal?: AbortSignal }) {
  return (await service.catalog(options?.signal)).metadata;
}
export function searchRankedBuilds(payload: RankedSearchRequestPayload, options?: SearchOptions) {
  return service.search(payload, options);
}
