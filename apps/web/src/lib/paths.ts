export const APPLICATION_BASE_PATH = "/game-guide/mhwilds-skill-sim/";

export function resolveApplicationBasePath(value: string | undefined): string {
  const path = value ?? APPLICATION_BASE_PATH;
  if (!/^\/(?:[a-zA-Z0-9_-]+\/)+$/.test(path)) {
    throw new Error("Application base must be an absolute directory path with a trailing slash");
  }
  return path;
}

export function inventoryHref(base: string, search: string): string {
  if (base === "/skill-sim/") return "/inventory/";
  const legacy = new URLSearchParams(search).get("legacy") === "1";
  return `/game-guide/mhwilds-inventory-checker/${legacy ? "?legacy=1" : ""}`;
}
