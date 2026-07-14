import { describe, expect, it } from "vitest";

import {
  LOCAL_API_PROXY_PATTERN,
  rewriteLocalApiPath,
} from "../../vite.config";

const APPLICATION_API_PREFIX = "/game-guide/mhwilds-skill-sim/api";

describe("local API proxy boundary", () => {
  const pattern = new RegExp(LOCAL_API_PROXY_PATTERN);

  it.each([
    ["/health", "/health"],
    ["/catalog/metadata", "/catalog/metadata"],
    ["/search/cp-sat/ranked", "/search/cp-sat/ranked"],
    ["/health?check=one%20two&check=three", "/health?check=one%20two&check=three"],
  ])("matches and rewrites the exact endpoint %s", (suffix, expected) => {
    const publicPath = `${APPLICATION_API_PREFIX}${suffix}`;

    expect(pattern.test(publicPath)).toBe(true);
    expect(rewriteLocalApiPath(publicPath)).toBe(expected);
  });

  it.each([
    "",
    "/",
    "/search",
    "/search/cp-sat",
    "/search/cp-sat/ranked/extra",
    "/catalog/metadata/",
    "/health/extra",
    "/https://attacker.example/",
  ])("does not match or rewrite the unknown suffix %s", (suffix) => {
    const publicPath = `${APPLICATION_API_PREFIX}${suffix}`;

    expect(pattern.test(publicPath)).toBe(false);
    expect(rewriteLocalApiPath(publicPath)).toBe(publicPath);
  });
});
