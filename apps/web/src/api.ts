import type {
  CatalogMetadataResponse,
  RankedSearchRequestPayload,
  RankedSearchResponse,
} from "./types";

const API_BASE_URL = `${import.meta.env.BASE_URL}api`;
const API_NOT_CONFIGURED_DETAIL = "search API is not configured";

interface RequestOptions {
  signal?: AbortSignal;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | null;
  readonly userMessage: string;

  constructor(status: number, detail: string | null, userMessage?: string) {
    const message =
      userMessage ?? detail ?? `Search API request failed with status ${status}.`;
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.userMessage = message;
  }
}

export function isSearchApiNotConfiguredError(error: unknown): error is ApiError {
  return (
    error instanceof ApiError &&
    error.status === 503 &&
    error.detail === API_NOT_CONFIGURED_DETAIL
  );
}

function extractStringDetail(value: unknown): string | null {
  if (typeof value !== "object" || value === null || !("detail" in value)) {
    return null;
  }

  return typeof value.detail === "string" ? value.detail : null;
}

async function readErrorDetail(response: Response): Promise<string | null> {
  const body = await response.text();

  try {
    const value: unknown = JSON.parse(body);
    return extractStringDetail(value);
  } catch {
    return null;
  }
}

async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, init);

  if (!response.ok) {
    const detail = await readErrorDetail(response);
    throw new ApiError(response.status, detail);
  }

  try {
    const value: unknown = await response.json();
    return value as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }

    throw new ApiError(
      response.status,
      null,
      `Search API returned invalid JSON with status ${response.status}.`,
    );
  }
}

export async function fetchCatalogMetadata(
  options?: RequestOptions,
): Promise<CatalogMetadataResponse> {
  return requestJson<CatalogMetadataResponse>(`${API_BASE_URL}/catalog/metadata`, {
    method: "GET",
    headers: {
      Accept: "application/json",
    },
    credentials: "omit",
    signal: options?.signal,
  });
}

export async function searchRankedBuilds(
  payload: RankedSearchRequestPayload,
  options?: RequestOptions,
): Promise<RankedSearchResponse> {
  return requestJson<RankedSearchResponse>(`${API_BASE_URL}/search/cp-sat/ranked`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    credentials: "omit",
    body: JSON.stringify(payload),
    signal: options?.signal,
  });
}
