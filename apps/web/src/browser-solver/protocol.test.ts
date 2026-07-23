import { describe, expect, it } from "vitest";

import type {
  BrowserSolverWorkerRequest,
  BrowserSolverWorkerResponse,
} from "./protocol";

function requestKind(request: BrowserSolverWorkerRequest): string {
  switch (request.type) {
    case "init":
    case "search":
    case "calibrate":
    case "cancel":
      return request.type;
  }
}

function responseKind(response: BrowserSolverWorkerResponse): string {
  switch (response.type) {
    case "ready":
    case "progress":
    case "result":
    case "calibration":
    case "error":
      return response.type;
  }
}

describe("browser solver worker protocol", () => {
  it("has exhaustive request and response discriminants", () => {
    expect(
      requestKind({ type: "init", catalog: { format_version: 1 } }),
    ).toBe("init");
    expect(
      responseKind({
        type: "error",
        code: "invalid-message",
        message: "stable",
      }),
    ).toBe("error");
  });
});
