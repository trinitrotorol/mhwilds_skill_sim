import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeEach, expect, vi } from "vitest";

import { APPLICATION_BASE_PATH } from "../lib/paths";

vi.stubEnv("BASE_URL", APPLICATION_BASE_PATH);

const originalConsoleError = console.error;
let consoleErrors: unknown[][] = [];

beforeEach(() => {
  consoleErrors = [];
  console.error = (...data: unknown[]) => {
    consoleErrors.push(data);
  };
});

afterEach(() => {
  cleanup();
  console.error = originalConsoleError;
  expect(consoleErrors, "unexpected console.error output").toEqual([]);
});

afterAll(() => {
  console.error = originalConsoleError;
  vi.unstubAllEnvs();
});
