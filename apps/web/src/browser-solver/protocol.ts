import type {
  BrowserRankedSearchRequest,
  BrowserSolverProgress,
  BrowserSolverResult,
} from "./types";

export interface BrowserSolverWorkerInitRequest {
  readonly type: "init";
  readonly catalog: unknown;
}

export interface BrowserSolverWorkerSearchRequest {
  readonly type: "search";
  readonly search_id: string;
  readonly request: BrowserRankedSearchRequest;
  readonly timeout_ms: number;
}

export interface BrowserSolverWorkerCancelRequest {
  readonly type: "cancel";
  readonly search_id: string;
}

export interface BrowserSolverWorkerCalibrationRequest {
  readonly type: "calibrate";
  readonly calibration_id: string;
  readonly iterations: number;
}

export type BrowserSolverWorkerRequest =
  | BrowserSolverWorkerInitRequest
  | BrowserSolverWorkerSearchRequest
  | BrowserSolverWorkerCalibrationRequest
  | BrowserSolverWorkerCancelRequest;

export interface BrowserSolverWorkerReadyResponse {
  readonly type: "ready";
  readonly source_catalog_sha256: string;
}

export interface BrowserSolverWorkerProgressResponse {
  readonly type: "progress";
  readonly search_id: string;
  readonly progress: BrowserSolverProgress;
}

export interface BrowserSolverWorkerResultResponse {
  readonly type: "result";
  readonly search_id: string;
  readonly result: BrowserSolverResult;
}

export interface BrowserSolverWorkerCalibrationResponse {
  readonly type: "calibration";
  readonly calibration_id: string;
  readonly elapsed_ms: number;
  readonly checksum: number;
  readonly cross_origin_isolated: boolean;
}

export type BrowserSolverWorkerErrorCode =
  | "invalid-message"
  | "not-initialized"
  | "already-initialized"
  | "invalid-catalog"
  | "duplicate-search-id"
  | "unknown-search-id"
  | "search-failed";

export interface BrowserSolverWorkerErrorResponse {
  readonly type: "error";
  readonly code: BrowserSolverWorkerErrorCode;
  readonly message: string;
  readonly search_id?: string;
}

export type BrowserSolverWorkerResponse =
  | BrowserSolverWorkerReadyResponse
  | BrowserSolverWorkerProgressResponse
  | BrowserSolverWorkerResultResponse
  | BrowserSolverWorkerCalibrationResponse
  | BrowserSolverWorkerErrorResponse;
