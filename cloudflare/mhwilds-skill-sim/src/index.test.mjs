import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const originalFetch = globalThis.fetch;
const originalStdoutWrite = process.stdout.write;
let importNetworkCalls = 0;
let importStdoutWrites = 0;
let worker;

globalThis.fetch = async () => {
  importNetworkCalls += 1;
  throw new Error("module import attempted network access");
};
process.stdout.write = () => {
  importStdoutWrites += 1;
  return true;
};

try {
  ({ default: worker } = await import("./index.mjs"));
} finally {
  globalThis.fetch = originalFetch;
  process.stdout.write = originalStdoutWrite;
}

const ORIGIN = "https://preview.example.test:8787";
const API_ORIGIN = "https://api.example.test";
const APPLICATION_PATH = "/game-guide/mhwilds-skill-sim";
const APPLICATION_PATH_WITH_SLASH = `${APPLICATION_PATH}/`;
const ASSET_PATH = `${APPLICATION_PATH}/assets/index-Abc_def9.js`;
const API_PATH = `${APPLICATION_PATH}/api`;
const HEALTH_PATH = `${API_PATH}/health`;
const METADATA_PATH = `${API_PATH}/catalog/metadata`;
const RANKED_PATH = `${API_PATH}/search/cp-sat/ranked`;
const QUERY = "?source=test%20value&source=second&empty=";

function assertSecurityHeaders(response) {
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
}

function createAssets(handler) {
  const calls = [];
  return {
    calls,
    binding: {
      async fetch(request) {
        calls.push(request);
        return handler(request);
      },
    },
  };
}

async function withFetchMock(mockFetch, callback) {
  const previousFetch = globalThis.fetch;
  globalThis.fetch = mockFetch;
  try {
    return await callback();
  } finally {
    globalThis.fetch = previousFetch;
  }
}

test("module exposes only one Worker fetch handler without import side effects", () => {
  assert.equal(importNetworkCalls, 0);
  assert.equal(importStdoutWrites, 0);
  assert.equal(typeof worker, "object");
  assert.notEqual(worker, null);
  assert.equal(typeof worker.fetch, "function");
  assert.deepEqual(Object.keys(worker), ["fetch"]);
});

test("slashless GET redirects with origin and query intact", async () => {
  const response = await worker.fetch(
    new Request(`${ORIGIN}${APPLICATION_PATH}${QUERY}`),
    {},
  );

  assert.equal(response.status, 308);
  assert.equal(
    response.headers.get("location"),
    `${ORIGIN}${APPLICATION_PATH_WITH_SLASH}${QUERY}`,
  );
  assert.equal(response.headers.get("cache-control"), "no-store");
  assertSecurityHeaders(response);
  assert.equal(await response.text(), "");
});

test("slashless HEAD redirects with an empty body", async () => {
  const response = await worker.fetch(
    new Request(`${ORIGIN}${APPLICATION_PATH}${QUERY}`, { method: "HEAD" }),
    {},
  );

  assert.equal(response.status, 308);
  assert.equal(
    response.headers.get("location"),
    `${ORIGIN}${APPLICATION_PATH_WITH_SLASH}${QUERY}`,
  );
  assert.equal(response.body, null);
  assert.equal(await response.text(), "");
});

test("canonical GET forwards the identical request and preserves the asset response", async () => {
  const assets = createAssets(
    () =>
      new Response("<!doctype html><title>React</title>", {
        status: 203,
        statusText: "Asset HTML",
        headers: {
          "Content-Type": "text/html; charset=utf-8",
          "Cache-Control": "public, max-age=99",
          "X-Asset-Header": "preserved",
        },
      }),
  );
  const request = new Request(`${ORIGIN}${APPLICATION_PATH_WITH_SLASH}${QUERY}`);
  const response = await worker.fetch(request, { ASSETS: assets.binding });

  assert.equal(assets.calls.length, 1);
  assert.equal(assets.calls[0], request);
  assert.equal(assets.calls[0].url, request.url);
  assert.equal(assets.calls[0].method, "GET");
  assert.equal(response.status, 203);
  assert.equal(response.statusText, "Asset HTML");
  assert.equal(response.headers.get("content-type"), "text/html; charset=utf-8");
  assert.equal(response.headers.get("x-asset-header"), "preserved");
  assert.equal(response.headers.get("cache-control"), "no-cache");
  assertSecurityHeaders(response);
  assert.equal(await response.text(), "<!doctype html><title>React</title>");
});

test("canonical HEAD is forwarded once and returns no body", async () => {
  const assets = createAssets(
    () =>
      new Response("asset binding supplied a body", {
        status: 200,
        headers: { "Content-Type": "text/html; charset=utf-8" },
      }),
  );
  const request = new Request(`${ORIGIN}${APPLICATION_PATH_WITH_SLASH}`, {
    method: "HEAD",
  });
  const response = await worker.fetch(request, { ASSETS: assets.binding });

  assert.equal(assets.calls.length, 1);
  assert.equal(assets.calls[0], request);
  assert.equal(assets.calls[0].method, "HEAD");
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "text/html; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "no-cache");
  assert.equal(response.body, null);
  assert.equal(await response.text(), "");
});

test("fingerprinted asset GET is forwarded and receives immutable caching", async () => {
  const assets = createAssets(
    () =>
      new Response("export default 'asset';", {
        status: 200,
        headers: {
          "Content-Type": "text/javascript; charset=utf-8",
          "Cache-Control": "no-store",
        },
      }),
  );
  const request = new Request(`${ORIGIN}${ASSET_PATH}${QUERY}`);
  const response = await worker.fetch(request, { ASSETS: assets.binding });

  assert.equal(assets.calls.length, 1);
  assert.equal(assets.calls[0], request);
  assert.equal(assets.calls[0].url, `${ORIGIN}${ASSET_PATH}${QUERY}`);
  assert.equal(response.status, 200);
  assert.equal(
    response.headers.get("content-type"),
    "text/javascript; charset=utf-8",
  );
  assert.equal(
    response.headers.get("cache-control"),
    "public, max-age=31536000, immutable",
  );
  assertSecurityHeaders(response);
  assert.equal(await response.text(), "export default 'asset';");
});

test("non-fingerprinted asset is never assigned immutable caching", async () => {
  const assets = createAssets(
    () =>
      new Response("body", {
        headers: { "Cache-Control": "public, max-age=31536000, immutable" },
      }),
  );
  const response = await worker.fetch(
    new Request(`${ORIGIN}${APPLICATION_PATH}/assets/app.js`),
    { ASSETS: assets.binding },
  );

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-cache");
});

test("asset status, body, and content type are preserved for error responses", async () => {
  const assets = createAssets(
    () =>
      new Response("asset missing", {
        status: 404,
        headers: { "Content-Type": "application/problem+json" },
      }),
  );
  const response = await worker.fetch(new Request(`${ORIGIN}${ASSET_PATH}`), {
    ASSETS: assets.binding,
  });

  assert.equal(response.status, 404);
  assert.equal(response.headers.get("content-type"), "application/problem+json");
  assert.equal(response.headers.get("cache-control"), "no-cache");
  assert.equal(await response.text(), "asset missing");
});

test("missing, invalid, failed, or malformed ASSETS bindings return stable 500", async (t) => {
  const cases = [
    ["missing", {}],
    ["missing env", undefined],
    ["invalid", { ASSETS: {} }],
    ["non-function", { ASSETS: { fetch: true } }],
    [
      "throws",
      {
        ASSETS: {
          async fetch() {
            throw new Error("binding details must not escape");
          },
        },
      },
    ],
    ["non-Response", { ASSETS: { async fetch() { return "not a response"; } } }],
  ];

  for (const [name, env] of cases) {
    await t.test(name, async () => {
      const response = await worker.fetch(
        new Request(`${ORIGIN}${APPLICATION_PATH_WITH_SLASH}`),
        env,
      );
      assert.equal(response.status, 500);
      assert.equal(response.headers.get("content-type"), "text/plain; charset=utf-8");
      assert.equal(response.headers.get("cache-control"), "no-store");
      assertSecurityHeaders(response);
      assert.equal(await response.text(), "Static assets are unavailable\n");
    });
  }
});

test("root, existing guide, and unknown application children remain 404", async () => {
  const paths = [
    "/",
    "/game-guide/",
    "/game-guide/exponential-idle-minigame-guide",
    `${APPLICATION_PATH}/unknown`,
    `${APPLICATION_PATH}/assets-other/index-Abcdef12.js`,
  ];

  for (const path of paths) {
    const response = await worker.fetch(new Request(`${ORIGIN}${path}`), {});
    assert.equal(response.status, 404, path);
    assert.equal(
      response.headers.get("content-type"),
      "text/plain; charset=utf-8",
      path,
    );
    assert.equal(response.headers.get("cache-control"), "no-store", path);
    assertSecurityHeaders(response);
    assert.equal(await response.text(), "Not Found\n", path);
  }
});

test("static POST returns 405 without calling ASSETS or consuming its body", async () => {
  const assets = createAssets(() => new Response("must not be called"));
  const request = new Request(`${ORIGIN}${ASSET_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: "payload",
  });
  const response = await worker.fetch(request, { ASSETS: assets.binding });

  assert.equal(response.status, 405);
  assert.equal(response.headers.get("allow"), "GET, HEAD");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(await response.text(), "Method Not Allowed\n");
  assert.equal(assets.calls.length, 0);
  assert.equal(request.bodyUsed, false);
});

test("all three public API routes return the exact unconfigured response", async () => {
  const requests = [
    new Request(`${ORIGIN}${HEALTH_PATH}`),
    new Request(`${ORIGIN}${METADATA_PATH}${QUERY}`),
    new Request(`${ORIGIN}${RANKED_PATH}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }),
  ];

  let fetchCalls = 0;
  await withFetchMock(
    async () => {
      fetchCalls += 1;
      throw new Error("unconfigured API attempted network access");
    },
    async () => {
      for (const request of requests) {
        const response = await worker.fetch(request, {});
        assert.equal(response.status, 503, request.url);
        assert.equal(
          response.headers.get("content-type"),
          "application/json; charset=utf-8",
          request.url,
        );
        assert.equal(response.headers.get("cache-control"), "no-store", request.url);
        assertSecurityHeaders(response);
        assert.equal(
          await response.text(),
          '{"detail":"search API is not configured"}',
          request.url,
        );
      }
    },
  );
  assert.equal(fetchCalls, 0);
});

test("unconfigured API HEAD response has status and headers but no body", async () => {
  const response = await worker.fetch(
    new Request(`${ORIGIN}${HEALTH_PATH}`, { method: "HEAD" }),
    {},
  );

  assert.equal(response.status, 503);
  assert.equal(response.headers.get("content-type"), "application/json; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.body, null);
  assert.equal(await response.text(), "");
});

test("configured GET API routes map exactly and preserve query strings", async () => {
  const cases = [
    [HEALTH_PATH, "/health"],
    [METADATA_PATH, "/catalog/metadata"],
  ];

  for (const [publicPath, upstreamPath] of cases) {
    let upstreamRequest;
    await withFetchMock(
      async (request) => {
        upstreamRequest = request;
        return new Response(`response:${upstreamPath}`, {
          status: 206,
          statusText: "Partial API",
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "X-Upstream": "not-forwarded",
            "Cache-Control": "public, max-age=600",
            "Set-Cookie": "session=upstream-secret; Secure",
            "WWW-Authenticate": "Bearer realm=upstream",
            "Access-Control-Allow-Origin": "*",
          },
        });
      },
      async () => {
        const request = new Request(`${ORIGIN}${publicPath}${QUERY}`, {
          headers: {
            Accept: "application/json",
            "Content-Type": "application/vnd.test+json",
            Cookie: "session=browser-secret",
            Authorization: "Bearer browser-secret",
            Host: "attacker.example",
            "X-Unrelated": "not-forwarded",
          },
        });
        const snapshot = {
          url: request.url,
          method: request.method,
          headers: [...request.headers],
          bodyUsed: request.bodyUsed,
        };
        const response = await worker.fetch(request, { API_ORIGIN });

        assert.equal(response.status, 206);
        assert.equal(response.statusText, "Partial API");
        assert.equal(
          response.headers.get("content-type"),
          "application/json; charset=utf-8",
        );
        assert.equal(response.headers.get("x-upstream"), null);
        assert.equal(response.headers.get("set-cookie"), null);
        assert.equal(response.headers.get("www-authenticate"), null);
        assert.equal(response.headers.get("access-control-allow-origin"), null);
        assert.equal(response.headers.get("cache-control"), "no-store");
        assertSecurityHeaders(response);
        assert.equal(await response.text(), `response:${upstreamPath}`);

        assert.equal(upstreamRequest.url, `${API_ORIGIN}${upstreamPath}${QUERY}`);
        assert.equal(upstreamRequest.method, "GET");
        assert.equal(upstreamRequest.body, null);
        assert.equal(upstreamRequest.redirect, "manual");
        assert.equal(upstreamRequest.headers.get("accept"), "application/json");
        assert.equal(
          upstreamRequest.headers.get("content-type"),
          "application/vnd.test+json",
        );
        assert.equal(upstreamRequest.headers.get("cookie"), null);
        assert.equal(upstreamRequest.headers.get("authorization"), null);
        assert.equal(upstreamRequest.headers.get("host"), null);
        assert.equal(upstreamRequest.headers.get("x-unrelated"), null);
        assert.equal(new URL(upstreamRequest.url).host, "api.example.test");

        assert.equal(request.url, snapshot.url);
        assert.equal(request.method, snapshot.method);
        assert.deepEqual([...request.headers], snapshot.headers);
        assert.equal(request.bodyUsed, snapshot.bodyUsed);
      },
    );
  }
});

test("configured ranked POST streams its body and selected headers only", async () => {
  let upstreamRequest;
  await withFetchMock(
    async (request) => {
      upstreamRequest = request;
      assert.equal(await request.text(), '{"weapon_kind":"great-sword"}');
      return new Response('{"candidates":[]}', {
        status: 202,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const request = new Request(`${ORIGIN}${RANKED_PATH}${QUERY}`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          Cookie: "session=browser-secret",
          Authorization: "Bearer browser-secret",
          "CF-Connecting-IP": "must-not-forward",
        },
        body: '{"weapon_kind":"great-sword"}',
      });
      const response = await worker.fetch(request, { API_ORIGIN });

      assert.equal(upstreamRequest.url, `${API_ORIGIN}/search/cp-sat/ranked${QUERY}`);
      assert.equal(upstreamRequest.method, "POST");
      assert.equal(upstreamRequest.redirect, "manual");
      assert.equal(upstreamRequest.headers.get("accept"), "application/json");
      assert.equal(upstreamRequest.headers.get("content-type"), "application/json");
      assert.equal(upstreamRequest.headers.get("cookie"), null);
      assert.equal(upstreamRequest.headers.get("authorization"), null);
      assert.equal(upstreamRequest.headers.get("cf-connecting-ip"), null);
      assert.equal(response.status, 202);
      assert.equal(response.headers.get("content-type"), "application/json");
      assert.equal(response.headers.get("cache-control"), "no-store");
      assert.equal(await response.text(), '{"candidates":[]}');
    },
  );
});

test("configured API HEAD keeps the method and strips the response body", async () => {
  let upstreamRequest;
  await withFetchMock(
    async (request) => {
      upstreamRequest = request;
      return new Response("mock fetch supplied a body", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const response = await worker.fetch(
        new Request(`${ORIGIN}${METADATA_PATH}`, { method: "HEAD" }),
        { API_ORIGIN },
      );
      assert.equal(upstreamRequest.method, "HEAD");
      assert.equal(upstreamRequest.url, `${API_ORIGIN}/catalog/metadata`);
      assert.equal(response.status, 200);
      assert.equal(response.body, null);
      assert.equal(await response.text(), "");
    },
  );
});

test("upstream redirects are not followed or exposed to the browser", async () => {
  let upstreamRequest;
  await withFetchMock(
    async (request) => {
      upstreamRequest = request;
      return new Response(null, {
        status: 307,
        headers: { Location: "https://other-origin.example/escape" },
      });
    },
    async () => {
      const response = await worker.fetch(new Request(`${ORIGIN}${HEALTH_PATH}`), {
        API_ORIGIN,
      });
      assert.equal(upstreamRequest.redirect, "manual");
      assert.equal(response.status, 307);
      assert.equal(response.headers.get("location"), null);
      assert.equal(response.headers.get("cache-control"), "no-store");
    },
  );
});

test("invalid API origins fail closed without exposing or fetching their value", async () => {
  const invalidOrigins = [
    "http://api.example.test",
    "https://api.example.test/backend",
    "https://api.example.test/foo/..",
    "https://api.example.test/?token=secret",
    "https://api.example.test/#secret",
    "https://user:password@api.example.test",
    "api.example.test",
    " https://api.example.test ",
    123,
  ];
  let fetchCalls = 0;

  await withFetchMock(
    async () => {
      fetchCalls += 1;
      return new Response("must not fetch");
    },
    async () => {
      for (const API_ORIGIN of invalidOrigins) {
        const response = await worker.fetch(new Request(`${ORIGIN}${HEALTH_PATH}`), {
          API_ORIGIN,
        });
        assert.equal(response.status, 500, String(API_ORIGIN));
        assert.equal(response.headers.get("cache-control"), "no-store");
        assert.equal(
          await response.text(),
          '{"detail":"search API configuration is invalid"}',
          String(API_ORIGIN),
        );
      }
    },
  );
  assert.equal(fetchCalls, 0);
});

test("same-origin API configuration is rejected as a proxy loop", async () => {
  let fetchCalls = 0;
  await withFetchMock(
    async () => {
      fetchCalls += 1;
      return new Response("must not fetch");
    },
    async () => {
      const response = await worker.fetch(new Request(`${ORIGIN}${HEALTH_PATH}`), {
        API_ORIGIN: ORIGIN,
      });
      assert.equal(response.status, 500);
      assert.equal(
        await response.text(),
        '{"detail":"search API configuration is invalid"}',
      );
    },
  );
  assert.equal(fetchCalls, 0);
});

test("wrong API methods return route-specific 405 responses without fetching", async () => {
  const cases = [
    [HEALTH_PATH, "POST", "GET, HEAD", "payload"],
    [METADATA_PATH, "PUT", "GET, HEAD", "payload"],
    [RANKED_PATH, "GET", "POST", undefined],
    [RANKED_PATH, "HEAD", "POST", undefined],
  ];
  let fetchCalls = 0;

  await withFetchMock(
    async () => {
      fetchCalls += 1;
      return new Response("must not fetch");
    },
    async () => {
      for (const [path, method, allow, body] of cases) {
        const request = new Request(`${ORIGIN}${path}`, { method, body });
        const response = await worker.fetch(request, { API_ORIGIN });
        assert.equal(response.status, 405, `${method} ${path}`);
        assert.equal(response.headers.get("allow"), allow, `${method} ${path}`);
        assert.equal(response.headers.get("cache-control"), "no-store");
        assert.equal(request.bodyUsed, false, `${method} ${path}`);
        if (method === "HEAD") {
          assert.equal(response.body, null);
        } else {
          assert.equal(await response.text(), "Method Not Allowed\n");
        }
      }
    },
  );
  assert.equal(fetchCalls, 0);
});

test("unrelated and lookalike API paths are never proxied", async () => {
  const paths = [
    API_PATH,
    `${API_PATH}/`,
    `${API_PATH}/health/`,
    `${API_PATH}/health/extra`,
    `${API_PATH}/catalog`,
    `${API_PATH}/search/cp-sat`,
    `${API_PATH}/proxy?url=https://attacker.example`,
    `${APPLICATION_PATH}/api-other/health`,
  ];
  let fetchCalls = 0;

  await withFetchMock(
    async () => {
      fetchCalls += 1;
      return new Response("must not fetch");
    },
    async () => {
      for (const path of paths) {
        const response = await worker.fetch(new Request(`${ORIGIN}${path}`), {
          API_ORIGIN,
        });
        assert.equal(response.status, 404, path);
        assert.equal(await response.text(), "Not Found\n", path);
      }
    },
  );
  assert.equal(fetchCalls, 0);
});

test("fetch failures and malformed fetch results never become successes", async (t) => {
  const cases = [
    [
      "rejection",
      async () => {
        throw new Error("upstream host and secret details");
      },
    ],
    ["non-Response", async () => ({ status: 200, body: "fake" })],
  ];

  for (const [name, mockFetch] of cases) {
    await t.test(name, async () => {
      await withFetchMock(mockFetch, async () => {
        const response = await worker.fetch(new Request(`${ORIGIN}${HEALTH_PATH}`), {
          API_ORIGIN,
        });
        assert.equal(response.status, 502);
        assert.equal(response.headers.get("content-type"), "application/json; charset=utf-8");
        assert.equal(response.headers.get("cache-control"), "no-store");
        assert.equal(
          await response.text(),
          '{"detail":"search API request failed"}',
        );
      });
    });
  }
});

test("repeated API responses are independent", async () => {
  let fetchCalls = 0;
  await withFetchMock(
    async () => {
      fetchCalls += 1;
      return new Response('{"status":"ok"}', {
        headers: { "Content-Type": "application/json" },
      });
    },
    async () => {
      const request = new Request(`${ORIGIN}${HEALTH_PATH}`);
      const first = await worker.fetch(request, { API_ORIGIN });
      const second = await worker.fetch(request, { API_ORIGIN });

      assert.notEqual(first, second);
      assert.equal(await first.text(), '{"status":"ok"}');
      assert.equal(second.bodyUsed, false);
      assert.equal(await second.text(), '{"status":"ok"}');
      assert.equal(request.bodyUsed, false);
    },
  );
  assert.equal(fetchCalls, 2);
});

test("wrangler config preserves Worker identity and declares one safe asset collection", async () => {
  const configText = await readFile(
    new URL("../../../wrangler.jsonc", import.meta.url),
    "utf8",
  );
  const config = JSON.parse(configText);

  assert.equal(config.name, "mhwilds-skill-sim");
  assert.equal(config.main, "cloudflare/mhwilds-skill-sim/src/index.mjs");
  assert.equal(config.compatibility_date, "2026-07-14");
  assert.equal(config.workers_dev, true);
  assert.deepEqual(config.build, {
    command:
      "npm --prefix apps/web ci --no-audit --no-fund && npm --prefix apps/web run build",
  });
  assert.deepEqual(config.assets, {
    directory: "apps/web/dist",
    binding: "ASSETS",
    run_worker_first: true,
  });

  assert.equal(Object.hasOwn(config, "routes"), false);
  assert.equal(Object.hasOwn(config, "route"), false);
  assert.equal(Object.hasOwn(config, "account_id"), false);
  assert.equal(Object.hasOwn(config, "zone_id"), false);
  assert.equal(Object.hasOwn(config, "token"), false);
  assert.equal(Object.hasOwn(config, "vars"), false);
  assert.doesNotMatch(configText, /API_ORIGIN/);
  assert.doesNotMatch(configText, /not_found_handling/);
});
