// @vitest-environment node

import { describe, expect, it, vi } from "vitest";

import { executeCertificationCli } from "./certification-cli";
import { assertWorkerThrottleApplySucceeded } from "./cpu-calibration";
import type { WorkerThrottleApplySummary } from "./worker-cdp-controller";

const REQUIRED = [
  "--catalog",
  "catalog.json",
  "--oracle",
  "oracle.json",
  "--output",
  "must-not-be-written.json",
  "--screenshot-directory",
  ".",
];

function failedApply(): WorkerThrottleApplySummary {
  return {
    requested_rate: 4,
    active_worker_count: 1,
    applied_count: 0,
    unsupported_count: 0,
    failed_count: 1,
    sessions: [
      {
        target_type: "worker",
        target_title: null,
        requested_rate: 4,
        support: "failed",
        protocol_error_code: null,
        protocol_error_message: "transport closed",
      },
    ],
  };
}

describe("certification CLI failure contract", () => {
  it("returns nonzero and never writes a final report after an apply failure", async () => {
    const write = vi.fn(async () => undefined);
    const stdout = vi.fn();
    const stderr = vi.fn();
    const exitCode = await executeCertificationCli(REQUIRED, process.cwd(), {
      run: async () => {
        assertWorkerThrottleApplySucceeded(failedApply(), "calibration");
        return { decision: { status: "GO" } };
      },
      write,
      stdout,
      stderr,
    });

    expect(exitCode).toBe(1);
    expect(write).not.toHaveBeenCalled();
    expect(stdout).not.toHaveBeenCalled();
    expect(stderr).toHaveBeenCalledWith(
      expect.stringContaining("Worker CPU throttle application failed"),
    );
  });
});
