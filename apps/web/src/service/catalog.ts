import { MAX_CATALOG_BYTES, parseCatalog, type CheckerCatalog } from "../../../../subprojects/inventory-checker/src/domain";
import { decodeBrowserSearchCatalog } from "../browser-solver/catalog";
import type { DecodedBrowserCatalog } from "../browser-solver/types";
import type { CatalogMetadataResponse } from "../types";

const BASE = "/game-guide/mhwilds-skill-sim/";
export interface ServiceCatalog {
  raw: unknown;
  browser: DecodedBrowserCatalog;
  checker: CheckerCatalog;
  metadata: CatalogMetadataResponse;
  remoteEnabled: boolean;
}

export async function boundedJson(path: string, signal: AbortSignal, maximum: number, fetcher = fetch): Promise<unknown> {
  const url = new URL(path, location.origin);
  if (url.origin !== location.origin || url.username || url.password || url.hash) throw new Error("カタログURLが不正です。");
  const response = await fetcher(url.href, { signal, credentials: "omit", redirect: "error", cache: "no-cache", headers: { Accept: "application/json" } });
  if (response.status !== 200 || response.redirected || (response.url && new URL(response.url).origin !== location.origin)) throw new Error(`カタログ取得エラー (${response.status})`);
  if (!/^application\/(?:[\w.+-]+\+)?json(?:\s*;|$)/i.test(response.headers.get("content-type") ?? "")) throw new Error("カタログの形式がJSONではありません。");
  const length = response.headers.get("content-length");
  if (length && (!/^\d+$/.test(length) || Number(length) > maximum)) throw new Error("カタログのサイズ上限を超えています。");
  const chunks: Uint8Array[] = [];
  let size = 0;
  if (response.body) {
    const reader = response.body.getReader();
    try {
      for (;;) {
        const chunk = await reader.read();
        if (chunk.done) break;
        size += chunk.value.byteLength;
        if (size > maximum || signal.aborted) { await reader.cancel(); throw new Error("カタログ読込を中断しました。"); }
        chunks.push(chunk.value);
      }
    } finally { reader.releaseLock(); }
  } else {
    const chunk = new TextEncoder().encode(await response.text());
    size = chunk.length;
    if (size > maximum) throw new Error("カタログのサイズ上限を超えています。");
    chunks.push(chunk);
  }
  signal.throwIfAborted();
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  return { value: JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)) as unknown, bytes };
}

function object(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error("カタログ形式が不正です。");
  return value as Record<string, unknown>;
}

export async function loadServiceCatalog(signal: AbortSignal, fetcher = fetch): Promise<ServiceCatalog> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal.addEventListener("abort", abort, { once: true });
  if (signal.aborted) abort();
  const timer = setTimeout(abort, 30_000);
  try {
    const read = async (path: string, max: number) => object(await boundedJson(path, controller.signal, max, fetcher));
    const manifest = object((await read(`${BASE}browser-solver/manifest.json`, 16_384)).value);
    if (manifest.format_version !== 1 || typeof manifest.catalog_file !== "string" || !/^catalog-[a-f0-9]{64}\.json$/.test(manifest.catalog_file)) throw new Error("カタログmanifestが不正です。");
    const [compact, checkerData, releaseData] = await Promise.all([
      read(`${BASE}browser-solver/${manifest.catalog_file}`, 25 * 1024 * 1024),
      read(`${BASE}catalog/checker-catalog.json`, MAX_CATALOG_BYTES),
      read(`${BASE}release.json`, 16_384),
    ]);
    const bytes = compact.bytes as Uint8Array<ArrayBuffer>;
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map((n) => n.toString(16).padStart(2, "0")).join("");
    if (digest !== manifest.compact_sha256 || manifest.catalog_file !== `catalog-${digest}.json` || bytes.length !== manifest.raw_bytes) throw new Error("カタログの整合性検証に失敗しました。");
    const browser = decodeBrowserSearchCatalog(compact.value);
    const checker = parseCatalog(checkerData.value);
    const release = object(releaseData.value);
    if (checker.revision !== browser.source_catalog.sha256 || checker.revision !== manifest.source_catalog_sha256 || checker.revision !== release.catalog_revision) throw new Error("カタログのリビジョンが一致しません。再読み込みしてください。");
    if (release.schema_version !== 1 || typeof release.remote_enabled !== "boolean") throw new Error("公開設定が不正です。");
    const features = object(release.features);
    if (typeof features.artian_series_skill_assignment !== "boolean" || typeof features.artian_group_skill_assignment !== "boolean" || typeof features.theoretical_appraisal_charms !== "boolean") throw new Error("公開機能設定が不正です。");
    const theoreticalAvailable = browser.source_catalog.generated_appraisal_charm_count > 0 || (object(compact.value).theoretical_appraisal_mode === "query" && checker.appraisal_charm_skill_groups.length > 0 && checker.appraisal_charm_patterns.length > 0);
    if (features.theoretical_appraisal_charms !== theoreticalAvailable) throw new Error("鑑定護石の公開設定とカタログが一致しません。");
    controller.signal.throwIfAborted();
    return {
      raw: compact.value, browser, checker, remoteEnabled: release.remote_enabled,
      metadata: {
        schema_version: checker.schema_version,
        skills: checker.skills.map((s) => ({ ...s, max_level: s.ranks.at(-1)!.level })),
        decorations: checker.decorations,
        weapon_kinds: [...new Set(browser.equipment_by_part.weapon.map((w) => w.weapon_kind).filter((w): w is string => w !== null))].sort(),
        features: { artian_series_skill_assignment: features.artian_series_skill_assignment, artian_group_skill_assignment: features.artian_group_skill_assignment, theoretical_appraisal_charms: features.theoretical_appraisal_charms },
        counts: { skills: checker.skills.length, equipment: browser.source_catalog.source_equipment_count, decorations: checker.decorations.length, appraisal_charm_skill_groups: checker.appraisal_charm_skill_groups.length, appraisal_charm_patterns: checker.appraisal_charm_patterns.length },
      },
    };
  } finally { clearTimeout(timer); signal.removeEventListener("abort", abort); }
}
