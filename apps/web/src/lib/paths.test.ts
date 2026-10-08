import { describe, expect, it } from "vitest";
import { APPLICATION_BASE_PATH, inventoryHref, resolveApplicationBasePath } from "./paths";

describe("application deployment paths", () => {
  it("keeps the legacy build default and accepts the subdomain path", () => {
    expect(resolveApplicationBasePath(undefined)).toBe(APPLICATION_BASE_PATH);
    expect(resolveApplicationBasePath("/skill-sim/")).toBe("/skill-sim/");
  });

  it.each(["https://other.test/", "//other.test/", "/../", "/skill-sim", "/a/?b=1"])("rejects unsafe build path %s", (path) => {
    expect(() => resolveApplicationBasePath(path)).toThrow("Application base");
  });

  it("keeps old saved inventory accessible when switching legacy apps", () => {
    expect(inventoryHref(APPLICATION_BASE_PATH, "?legacy=1&other=x")).toBe("/game-guide/mhwilds-inventory-checker/?legacy=1");
    expect(inventoryHref(APPLICATION_BASE_PATH, "?legacy=0")).toBe("/game-guide/mhwilds-inventory-checker/");
    expect(inventoryHref("/skill-sim/", "?legacy=1")).toBe("/inventory/");
  });
});
