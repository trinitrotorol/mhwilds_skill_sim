import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  fetchCatalogMetadata,
  isSearchApiNotConfiguredError,
  searchRankedBuilds,
} from "./api";
import type {
  CatalogMetadataResponse,
  RankedSearchRequestPayload,
  RankedSearchResponse,
} from "./types";

const METADATA_URL = "/game-guide/mhwilds-skill-sim/api/catalog/metadata";
const RANKED_URL = "/game-guide/mhwilds-skill-sim/api/search/cp-sat/ranked";

const metadataResponse: CatalogMetadataResponse = {
  schema_version: 1,
  skills: [],
  weapon_kinds: ["great-sword"],
  decorations: [],
  features: {
    artian_series_skill_assignment: false,
    artian_group_skill_assignment: false,
    theoretical_appraisal_charms: false,
  },
  counts: {
    skills: 0,
    equipment: 0,
    decorations: 0,
    appraisal_charm_skill_groups: 0,
    appraisal_charm_patterns: 0,
  },
};

const rankedResponse: RankedSearchResponse = {
  candidates: [],
  exhausted: true,
  timed_out: false,
};

const payload: RankedSearchRequestPayload = {
  requirements: [{ skill_id: "skill.required", min_level: 1 }],
  preferences: [{ skill_id: "skill.preferred", target_level: 2 }],
  max_results: 3,
  weapon_kind: "great-sword",
};

function jsonResponse(value: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(value), {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
}

describe("API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("fetches metadata from the exact same-origin application URL", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(metadataResponse));

    await expect(fetchCatalogMetadata()).resolves.toEqual(metadataResponse);

    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith(
      METADATA_URL,
      expect.objectContaining({
        method: "GET",
        headers: { Accept: "application/json" },
      }),
    );
  });

  it("forwards the metadata AbortSignal", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(metadataResponse));
    const controller = new AbortController();

    await fetchCatalogMetadata({ signal: controller.signal });

    expect(fetch).toHaveBeenCalledWith(
      METADATA_URL,
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("posts the unchanged payload to the exact ranked URL", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(rankedResponse));
    const before = JSON.stringify(payload);
    const controller = new AbortController();

    await expect(
      searchRankedBuilds(payload, { signal: controller.signal }),
    ).resolves.toEqual(rankedResponse);

    expect(JSON.stringify(payload)).toBe(before);
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith(RANKED_URL, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      credentials: "omit",
      body: before,
      signal: controller.signal,
    });
  });

  it("uses a backend string detail for non-2xx errors", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: "requirements are invalid" }, { status: 422 }),
    );

    const error = await fetchCatalogMetadata().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 422,
      detail: "requirements are invalid",
      message: "requirements are invalid",
      userMessage: "requirements are invalid",
    });
  });

  it("identifies the Worker API-unconfigured 503 response", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse({ detail: "search API is not configured" }, { status: 503 }),
    );

    const error = await fetchCatalogMetadata().catch((caught: unknown) => caught);

    expect(isSearchApiNotConfiguredError(error)).toBe(true);
  });

  it.each([
    ["non-JSON", "service unavailable"],
    ["non-string detail", JSON.stringify({ detail: { message: "no" } })],
  ])("uses a stable status message for a %s error", async (_label, body) => {
    vi.mocked(fetch).mockResolvedValue(new Response(body, { status: 502 }));

    await expect(fetchCatalogMetadata()).rejects.toMatchObject({
      status: 502,
      detail: null,
      message: "Search API request failed with status 502.",
    });
  });

  it("rejects a successful response whose body is not JSON", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("not JSON", { status: 200 }));

    await expect(fetchCatalogMetadata()).rejects.toMatchObject({
      status: 200,
      detail: null,
      message: "Search API returned invalid JSON with status 200.",
    });
  });

  it("passes an AbortError through unchanged", async () => {
    const abortError = new DOMException("The operation was aborted", "AbortError");
    vi.mocked(fetch).mockRejectedValue(abortError);

    const error = await fetchCatalogMetadata().catch((caught: unknown) => caught);

    expect(error).toBe(abortError);
  });

  it("does not add cookies, tokens, authorization, logs, or alerts", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(metadataResponse));
    const consoleSpy = vi.spyOn(console, "log");
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => undefined);

    await fetchCatalogMetadata();

    const init = vi.mocked(fetch).mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(init?.credentials).toBe("omit");
    expect(headers.has("Cookie")).toBe(false);
    expect(headers.has("Authorization")).toBe(false);
    expect(headers.has("X-API-Key")).toBe(false);
    expect(consoleSpy).not.toHaveBeenCalled();
    expect(alertSpy).not.toHaveBeenCalled();
  });
});
