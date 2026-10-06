import { createHash, webcrypto } from "node:crypto";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { makeTestCatalog } from "../browser-solver/test-catalog";
import { boundedJson, loadServiceCatalog } from "./catalog";

const signal = () => new AbortController().signal;
const json = (value: unknown, init?: ResponseInit) => new Response(JSON.stringify(value), { ...init, headers: { "content-type": "application/json", ...init?.headers } });

function releaseFixture() {
  const compact = makeTestCatalog();
  const bytes = JSON.stringify(compact);
  const hash = createHash("sha256").update(bytes).digest("hex");
  const checker = {
    schema_version: 1, revision: compact.source_catalog.sha256,
    generated_at: "2026-10-06T00:00:00Z",
    skills: compact.skills.map((skill) => ({
      skill_id: skill.skill_id, display_name: skill.display_name, kind: skill.kind,
      ranks: Array.from({ length: skill.max_level }, (_, i) => ({ level: i + 1, required_pieces: skill.required_pieces[i] ?? null })),
    })),
    decorations: compact.decorations.map((decoration) => ({
      decoration_id: decoration.decoration_id, display_name: decoration.display_name,
      required_slot: { kind: decoration.required_slot[0], level: decoration.required_slot[1] },
      skills: decoration.skills.map(([index, level]) => ({ skill_id: compact.skills[index]!.skill_id, level })),
    })),
    fixed_charms: compact.equipment_by_part.charm.map((charm) => ({
      equipment_id: charm.equipment_id, display_name: charm.display_name,
      skills: charm.skills.map(([index, level]) => ({ skill_id: compact.skills[index]!.skill_id, level })),
      slots: charm.slots.map(([kind, level]) => ({ kind, level })),
    })),
    appraisal_charm_skill_groups: [], appraisal_charm_patterns: [],
  };
  const manifest = { format_version: 1, catalog_file: `catalog-${hash}.json`, compact_sha256: hash, source_catalog_sha256: checker.revision, raw_bytes: new TextEncoder().encode(bytes).length };
  const release = { schema_version: 1, remote_enabled: false, catalog_revision: checker.revision, features: { artian_series_skill_assignment: false, artian_group_skill_assignment: false, theoretical_appraisal_charms: false } };
  const fetcher = vi.fn(async (input: RequestInfo | URL) => {
    const path = new URL(String(input)).pathname;
    if (path.endsWith("manifest.json")) return json(manifest);
    if (path.endsWith(manifest.catalog_file)) return json(compact);
    if (path.endsWith("checker-catalog.json")) return json(checker);
    if (path.endsWith("release.json")) return json(release);
    return new Response("missing", { status: 404 });
  });
  return { manifest, checker, release, fetcher };
}

beforeEach(() => { vi.stubGlobal("crypto", webcrypto); });
afterEach(() => { vi.unstubAllGlobals(); });

describe("bounded production catalog loading", () => {
  it("loads only same-origin public catalogs and verifies their revision and hash", async () => {
    const fixture = releaseFixture();
    const result = await loadServiceCatalog(signal(), fixture.fetcher);
    expect(result.remoteEnabled).toBe(false);
    expect(result.metadata.skills).toHaveLength(4);
    expect(result.metadata.features).toEqual(fixture.release.features);
    expect(fixture.fetcher).toHaveBeenCalledTimes(4);
    for (const [url, options] of fixture.fetcher.mock.calls as unknown as [string, RequestInit][]) {
      expect(new URL(url).origin).toBe(location.origin);
      expect(options).toMatchObject({ credentials: "omit", redirect: "error" });
    }
  });

  it("reads actual assignment availability instead of assuming every catalog has Artian weapons", async () => {
    const fixture = releaseFixture();
    fixture.release.features.artian_group_skill_assignment = true;
    const result = await loadServiceCatalog(signal(), fixture.fetcher);
    expect(result.metadata.features.artian_series_skill_assignment).toBe(false);
    expect(result.metadata.features.artian_group_skill_assignment).toBe(true);
  });

  it("rejects published appraisal support when catalog rules are unavailable", async () => {
    const fixture = releaseFixture();
    fixture.release.features.theoretical_appraisal_charms = true;
    await expect(loadServiceCatalog(signal(), fixture.fetcher)).rejects.toThrow("鑑定護石");
  });

  it.each(["../other.json#fragment", "https://other.invalid/catalog.json", "https://name:password@other.invalid/catalog.json"])("rejects untrusted URL %s before fetching", async (url) => {
    const fetcher = vi.fn();
    await expect(boundedJson(url, signal(), 50, fetcher)).rejects.toThrow("URL");
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([204, 302, 404, 500])("rejects non-200 HTTP %s", async (status) => {
    await expect(boundedJson("/catalog.json", signal(), 50, async () => new Response(null, { status }))).rejects.toThrow("取得");
  });

  it("rejects HTML and excessive declared or streamed bytes", async () => {
    await expect(boundedJson("/catalog.json", signal(), 20, async () => new Response("<html>", { headers: { "content-type": "text/html" } }))).rejects.toThrow("JSON");
    await expect(boundedJson("/catalog.json", signal(), 20, async () => json({}, { headers: { "content-length": "100" } }))).rejects.toThrow("サイズ");
    await expect(boundedJson("/catalog.json", signal(), 20, async () => json({ long: "a".repeat(40) }))).rejects.toThrow("中断");
  });

  it("rejects invalid UTF-8 and cancelled reads", async () => {
    await expect(boundedJson("/catalog.json", signal(), 50, async () => new Response(new Uint8Array([0xff]), { headers: { "content-type": "application/json" } }))).rejects.toThrow();
    const controller = new AbortController(); controller.abort();
    await expect(boundedJson("/catalog.json", controller.signal, 50, async () => json({}))).rejects.toThrow();
  });

  it.each(["compact_sha256", "raw_bytes", "source_catalog_sha256"])("rejects altered manifest %s", async (key) => {
    const fixture = releaseFixture();
    Object.assign(fixture.manifest, { [key]: key === "raw_bytes" ? 1 : "f".repeat(64) });
    await expect(loadServiceCatalog(signal(), fixture.fetcher)).rejects.toThrow(/整合性|リビジョン/);
  });

  it("rejects release revision drift and unsafe manifest paths", async () => {
    const drift = releaseFixture(); drift.release.catalog_revision = "f".repeat(64);
    await expect(loadServiceCatalog(signal(), drift.fetcher)).rejects.toThrow("リビジョン");
    const unsafe = releaseFixture(); unsafe.manifest.catalog_file = "../checker-catalog.json";
    await expect(loadServiceCatalog(signal(), unsafe.fetcher)).rejects.toThrow("manifest");
    expect(unsafe.fetcher).toHaveBeenCalledTimes(1);
  });
});
