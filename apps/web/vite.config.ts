import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

import { APPLICATION_BASE_PATH } from "./src/lib/paths";

const APPLICATION_API_PREFIX = `${APPLICATION_BASE_PATH}api`;

const ALLOWED_LOCAL_API_PATHS = new Set([
  `${APPLICATION_API_PREFIX}/health`,
  `${APPLICATION_API_PREFIX}/catalog/metadata`,
  `${APPLICATION_API_PREFIX}/search/cp-sat/ranked`,
]);

export const LOCAL_API_PROXY_PATTERN =
  `^${APPLICATION_API_PREFIX}/(?:health|catalog/metadata|search/cp-sat/ranked)(?:\\?.*)?$`;

export function rewriteLocalApiPath(requestPath: string): string {
  const queryStart = requestPath.indexOf("?");
  const pathname = queryStart === -1 ? requestPath : requestPath.slice(0, queryStart);

  if (!ALLOWED_LOCAL_API_PATHS.has(pathname)) {
    return requestPath;
  }

  const query = queryStart === -1 ? "" : requestPath.slice(queryStart);
  return `${pathname.slice(APPLICATION_API_PREFIX.length)}${query}`;
}

export default defineConfig({
  base: APPLICATION_BASE_PATH,
  plugins: [react()],
  build: {
    outDir: "dist/game-guide/mhwilds-skill-sim",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    proxy: {
      [LOCAL_API_PROXY_PATTERN]: {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: rewriteLocalApiPath,
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
