import assert from "node:assert/strict";
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
  ({ default: worker } = await import("./handler.mjs"));
} finally {
  globalThis.fetch = originalFetch;
  process.stdout.write = originalStdoutWrite;
}

const ORIGIN = "https://public.example.test";
const API_PREFIX = "/game-guide/mhwilds-skill-sim/api";
const HEALTH_PATH = `${API_PREFIX}/health`;
const METADATA_PATH = `${API_PREFIX}/catalog/metadata`;
const RANKED_PATH = `${API_PREFIX}/search/cp-sat/ranked`;
const QUERY = "?source=test%20value&source=second&empty=";
const encoder = new TextEncoder();

function assertSecurityHeaders(response) {
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
}

async function assertJsonError(response, status, detail) {
  assert.equal(response.status, status);
  assert.equal(response.headers.get("content-type"), "application/json; charset=utf-8");
  assertSecurityHeaders(response);
  if (response.body === null) {
    assert.equal(await response.text(), "");
  } else {
    assert.deepEqual(await response.json(), { detail });
  }
}

function createHarness(options = {}) {
  const events = [];
  const instanceNames = [];
  const containerRequests = [];
  const limiterCalls = [];
  const responseFactory =
    options.responseFactory ??
    (() =>
      new Response('{"ok":true}', {
        headers: { "Content-Type": "application/json" },
      }));

  const stub = options.stub ?? {
    async fetch(request) {
      events.push("container");
      containerRequests.push(request);
      if (options.fetchError !== undefined) {
        throw options.fetchError;
      }
      if (Object.hasOwn(options, "fetchResult")) {
        return options.fetchResult;
      }
      return responseFactory(request);
    },
  };
  const namespace = options.namespace ?? {
    getByName(name) {
      events.push("getByName");
      instanceNames.push(name);
      return stub;
    },
  };
  const limiter = options.limiter ?? {
    async limit(input) {
      events.push("limit");
      limiterCalls.push(input);
      if (options.limitError !== undefined) {
        throw options.limitError;
      }
      return options.limitResult ?? { success: true };
    },
  };

  return {
    env: { SEARCH_API: namespace, SEARCH_RATE_LIMITER: limiter },
    events,
    instanceNames,
    containerRequests,
    limiterCalls,
  };
}

function postRequest(body = "{}", headers = {}) {
  return new Request(`${ORIGIN}${RANKED_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body,
    duplex: "half",
  });
}

test("handler module has one fetch handler and no import side effects", () => {
  assert.equal(importNetworkCalls, 0);
  assert.equal(importStdoutWrites, 0);
  assert.deepEqual(Object.keys(worker), ["fetch"]);
  assert.equal(typeof worker.fetch, "function");
});

test("health and metadata GET map exactly, preserve query, and share production", async (t) => {
  for (const [publicPath, upstreamPath] of [
    [HEALTH_PATH, "/health"],
    [METADATA_PATH, "/catalog/metadata"],
  ]) {
    await t.test(publicPath, async () => {
      const harness = createHarness();
      const response = await worker.fetch(
        new Request(`${ORIGIN}${publicPath}${QUERY}`),
        harness.env,
      );

      assert.equal(response.status, 200);
      assert.equal(await response.text(), '{"ok":true}');
      assert.deepEqual(harness.instanceNames, ["production"]);
      assert.equal(harness.containerRequests.length, 1);
      assert.equal(
        new URL(harness.containerRequests[0].url).pathname,
        upstreamPath,
      );
      assert.equal(new URL(harness.containerRequests[0].url).search, QUERY);
      assert.equal(harness.containerRequests[0].method, "GET");
      assert.deepEqual(harness.limiterCalls, []);
    });
  }
});

test("health and metadata HEAD use backend GET once and return no body", async (t) => {
  for (const publicPath of [HEALTH_PATH, METADATA_PATH]) {
    await t.test(publicPath, async () => {
      const harness = createHarness({
        responseFactory: () =>
          new Response("upstream supplied a body", {
            status: 203,
            statusText: "Metadata Head",
            headers: { "Content-Type": "application/json" },
          }),
      });
      const response = await worker.fetch(
        new Request(`${ORIGIN}${publicPath}`, { method: "HEAD" }),
        harness.env,
      );

      assert.equal(harness.containerRequests.length, 1);
      assert.equal(harness.containerRequests[0].method, "GET");
      assert.equal(response.status, 203);
      assert.equal(response.statusText, "Metadata Head");
      assert.equal(response.body, null);
      assert.equal(await response.text(), "");
    });
  }
});

test("ranked POST maps exactly, rate limits first, and uses one production instance", async () => {
  const harness = createHarness();
  const response = await worker.fetch(
    postRequest('{"max_results":1}', { "CF-Connecting-IP": "203.0.113.8" }),
    harness.env,
  );

  assert.equal(response.status, 200);
  assert.deepEqual(harness.events, ["limit", "getByName", "container"]);
  assert.deepEqual(harness.limiterCalls, [{ key: "ranked:203.0.113.8" }]);
  assert.deepEqual(harness.instanceNames, ["production"]);
  assert.equal(harness.containerRequests.length, 1);
  assert.equal(
    new URL(harness.containerRequests[0].url).pathname,
    "/search/cp-sat/ranked",
  );
  assert.equal(await harness.containerRequests[0].text(), '{"max_results":1}');
});

test("unknown API, frontend, guide, and arbitrary paths are stable 404 without proxying", async () => {
  const paths = [
    API_PREFIX,
    `${API_PREFIX}/`,
    `${API_PREFIX}/search`,
    `${API_PREFIX}/search/cp-sat`,
    `${API_PREFIX}/openapi.json`,
    `${API_PREFIX}/docs`,
    `${API_PREFIX}/anything`,
    "/game-guide/mhwilds-skill-sim/",
    "/game-guide/exponential-idle-minigame-guide",
    "/",
    "/proxy?url=https://internal.example",
  ];
  const harness = createHarness();

  for (const path of paths) {
    const response = await worker.fetch(new Request(`${ORIGIN}${path}`), harness.env);
    await assertJsonError(response, 404, "API route not found");
  }
  assert.deepEqual(harness.containerRequests, []);
  assert.deepEqual(harness.limiterCalls, []);
});

test("wrong methods and OPTIONS return exact Allow without reading bodies", async () => {
  const cases = [
    [HEALTH_PATH, "POST", "GET, HEAD", "payload"],
    [HEALTH_PATH, "OPTIONS", "GET, HEAD", undefined],
    [METADATA_PATH, "PUT", "GET, HEAD", "payload"],
    [METADATA_PATH, "OPTIONS", "GET, HEAD", undefined],
    [RANKED_PATH, "GET", "POST", undefined],
    [RANKED_PATH, "HEAD", "POST", undefined],
    [RANKED_PATH, "OPTIONS", "POST", undefined],
  ];
  const harness = createHarness();

  for (const [path, method, allow, body] of cases) {
    const request = new Request(`${ORIGIN}${path}`, { method, body, duplex: "half" });
    const response = await worker.fetch(request, harness.env);
    assert.equal(response.headers.get("allow"), allow);
    await assertJsonError(response, 405, "method not allowed");
    assert.equal(request.bodyUsed, false);
  }
  assert.deepEqual(harness.events, []);
});

test("application/json media type is case-insensitive and permits parameters", async () => {
  for (const contentType of [
    "application/json",
    "Application/JSON; Charset=UTF-8",
    " application/json ; charset=utf-8",
  ]) {
    const harness = createHarness();
    const response = await worker.fetch(
      postRequest("{}", { "Content-Type": contentType }),
      harness.env,
    );
    assert.equal(response.status, 200, contentType);
    assert.equal(harness.containerRequests.length, 1, contentType);
  }
});

test("missing and non-JSON content types return 415 without reading or proxying", async () => {
  const cases = [undefined, "text/plain", "application/problem+json", "application/jsonx"];
  for (const contentType of cases) {
    const harness = createHarness();
    const headers = contentType === undefined ? {} : { "Content-Type": contentType };
    const request = new Request(`${ORIGIN}${RANKED_PATH}`, {
      method: "POST",
      headers,
      body: new Uint8Array([123, 125]),
    });
    const response = await worker.fetch(request, harness.env);
    await assertJsonError(response, 415, "content type must be application/json");
    assert.equal(request.bodyUsed, false);
    assert.equal(harness.containerRequests.length, 0);
    assert.deepEqual(harness.events, ["limit"]);
  }
});

test("ranked body bytes are forwarded identically without JSON parsing", async () => {
  const original = new Uint8Array([0, 123, 34, 255, 10, 125]);
  let forwarded;
  const harness = createHarness({
    responseFactory: async (request) => {
      forwarded = new Uint8Array(await request.arrayBuffer());
      return new Response(null, { status: 204 });
    },
  });
  const request = new Request(`${ORIGIN}${RANKED_PATH}${QUERY}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: original,
  });
  const response = await worker.fetch(request, harness.env);

  assert.equal(response.status, 204);
  assert.deepEqual(forwarded, original);
  assert.equal(new URL(harness.containerRequests[0].url).search, QUERY);
  assert.equal(request.bodyUsed, true);
});

test("empty JSON body is forwarded to the backend", async () => {
  const harness = createHarness();
  const request = new Request(`${ORIGIN}${RANKED_PATH}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  const response = await worker.fetch(request, harness.env);

  assert.equal(response.status, 200);
  assert.equal(harness.containerRequests.length, 1);
  assert.deepEqual(new Uint8Array(await harness.containerRequests[0].arrayBuffer()), new Uint8Array());
});

test("exactly 64 KiB is accepted and 64 KiB plus one byte is rejected", async () => {
  const acceptedHarness = createHarness();
  const accepted = new Uint8Array(64 * 1024);
  const acceptedResponse = await worker.fetch(postRequest(accepted), acceptedHarness.env);
  assert.equal(acceptedResponse.status, 200);
  assert.equal((await acceptedHarness.containerRequests[0].arrayBuffer()).byteLength, 64 * 1024);

  const rejectedHarness = createHarness();
  const rejectedRequest = postRequest(new Uint8Array(64 * 1024 + 1));
  const rejectedResponse = await worker.fetch(rejectedRequest, rejectedHarness.env);
  await assertJsonError(rejectedResponse, 413, "search request body is too large");
  assert.equal(rejectedHarness.containerRequests.length, 0);
  assert.equal(rejectedHarness.instanceNames.length, 0);
});

test("body limit counts multibyte UTF-8 bytes rather than JavaScript characters", async () => {
  const body = "あ".repeat(21_846);
  assert.ok(body.length < 64 * 1024);
  assert.ok(encoder.encode(body).byteLength > 64 * 1024);
  const harness = createHarness();
  const response = await worker.fetch(postRequest(body), harness.env);

  await assertJsonError(response, 413, "search request body is too large");
  assert.equal(harness.containerRequests.length, 0);
});

test("chunked body is read once and reconstructed in order", async () => {
  const chunks = [encoder.encode('{"a":'), encoder.encode("1"), encoder.encode("}")];
  let index = 0;
  const stream = new ReadableStream({
    pull(controller) {
      if (index === chunks.length) {
        controller.close();
        return;
      }
      controller.enqueue(chunks[index]);
      index += 1;
    },
  });
  const harness = createHarness();
  const request = postRequest(stream);
  const response = await worker.fetch(request, harness.env);

  assert.equal(response.status, 200);
  assert.equal(index, chunks.length);
  assert.equal(await harness.containerRequests[0].text(), '{"a":1}');
  assert.equal(request.bodyUsed, true);
});

test("oversized chunked body returns 413 and never obtains a container", async () => {
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(40 * 1024));
      controller.enqueue(new Uint8Array(25 * 1024));
      controller.close();
    },
  });
  const harness = createHarness();
  const response = await worker.fetch(postRequest(stream), harness.env);

  await assertJsonError(response, 413, "search request body is too large");
  assert.deepEqual(harness.events, ["limit"]);
});

test("stream read failure returns stable 400 without exposing the exception", async () => {
  const stream = new ReadableStream({
    pull() {
      throw new Error("raw body reader secret");
    },
  });
  const harness = createHarness();
  const response = await worker.fetch(postRequest(stream), harness.env);

  await assertJsonError(response, 400, "invalid search request body");
  assert.equal(harness.containerRequests.length, 0);
});

test("request forwarding uses an exact header allowlist and preserves input metadata", async () => {
  const harness = createHarness();
  const request = postRequest("{}", {
    Accept: "application/json",
    Authorization: "Bearer browser-secret",
    Cookie: "session=browser-secret",
    "Proxy-Authorization": "Basic secret",
    "CF-Connecting-IP": "2001:db8::1",
    "CF-Ray": "secret-ray",
    "X-Forwarded-For": "192.0.2.1",
    "X-Real-IP": "192.0.2.2",
    Host: "attacker.example",
    "X-Unrelated": "private",
  });
  const snapshot = {
    url: request.url,
    method: request.method,
    headers: [...request.headers],
  };
  await worker.fetch(request, harness.env);

  const forwarded = harness.containerRequests[0];
  assert.deepEqual([...forwarded.headers], [
    ["accept", "application/json"],
    ["content-type", "application/json"],
  ]);
  assert.equal(forwarded.headers.get("host"), null);
  assert.equal(forwarded.headers.get("content-length"), null);
  assert.equal(request.url, snapshot.url);
  assert.equal(request.method, snapshot.method);
  assert.deepEqual([...request.headers], snapshot.headers);
});

test("response preserves status, statusText, body, and Content-Type only", async () => {
  const harness = createHarness({
    responseFactory: () =>
      new Response("streamed response", {
        status: 206,
        statusText: "Partial API",
        headers: {
          "Content-Type": "application/problem+json",
          "Set-Cookie": "session=upstream-secret; Secure",
          "Access-Control-Allow-Origin": "*",
          Server: "internal-server",
          "X-Internal": "hidden",
          "Cache-Control": "public, max-age=600",
        },
      }),
  });
  const response = await worker.fetch(new Request(`${ORIGIN}${HEALTH_PATH}`), harness.env);

  assert.equal(response.status, 206);
  assert.equal(response.statusText, "Partial API");
  assert.equal(await response.text(), "streamed response");
  assert.equal(response.headers.get("content-type"), "application/problem+json");
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(response.headers.get("access-control-allow-origin"), null);
  assert.equal(response.headers.get("server"), null);
  assert.equal(response.headers.get("x-internal"), null);
  assertSecurityHeaders(response);
});

test("ranked rate limiter allows, blocks with Retry-After, and runs before body reading", async () => {
  const allowedHarness = createHarness({ limitResult: { success: true } });
  const allowedResponse = await worker.fetch(postRequest("{}"), allowedHarness.env);
  assert.equal(allowedResponse.status, 200);
  assert.deepEqual(allowedHarness.events, ["limit", "getByName", "container"]);

  const blockedHarness = createHarness({ limitResult: { success: false } });
  const blockedRequest = postRequest("must remain unread");
  const blockedResponse = await worker.fetch(blockedRequest, blockedHarness.env);
  await assertJsonError(blockedResponse, 429, "search rate limit exceeded");
  assert.equal(blockedResponse.headers.get("retry-after"), "60");
  assert.equal(blockedRequest.bodyUsed, false);
  assert.deepEqual(blockedHarness.events, ["limit"]);
});

test("rate limit key has a stable unknown IP bucket", async () => {
  const harness = createHarness();
  await worker.fetch(postRequest("{}"), harness.env);
  assert.deepEqual(harness.limiterCalls, [{ key: "ranked:unknown" }]);
});

test("health and metadata bypass the ranked limiter even when it is invalid", async () => {
  for (const path of [HEALTH_PATH, METADATA_PATH]) {
    const harness = createHarness();
    harness.env.SEARCH_RATE_LIMITER = null;
    const response = await worker.fetch(new Request(`${ORIGIN}${path}`), harness.env);
    assert.equal(response.status, 200);
    assert.equal(harness.containerRequests.length, 1);
  }
});

test("missing, invalid, throwing, and malformed rate limiters fail closed", async (t) => {
  const cases = [
    ["missing", undefined],
    ["null", null],
    ["non-object", true],
    ["missing limit", {}],
    ["non-function limit", { limit: true }],
    ["throws", { async limit() { throw new Error("limiter secret"); } }],
    ["null outcome", { async limit() { return null; } }],
    ["missing success", { async limit() { return {}; } }],
    ["non-boolean success", { async limit() { return { success: 1 }; } }],
  ];

  for (const [name, limiter] of cases) {
    await t.test(name, async () => {
      const harness = createHarness();
      harness.env.SEARCH_RATE_LIMITER = limiter;
      const request = postRequest("unread");
      const response = await worker.fetch(request, harness.env);
      await assertJsonError(response, 500, "search API configuration is invalid");
      assert.equal(request.bodyUsed, false);
      assert.equal(harness.containerRequests.length, 0);
      assert.equal(harness.instanceNames.length, 0);
    });
  }
});

test("missing or invalid container namespace and stub return stable 500", async (t) => {
  const cases = [
    ["missing env", undefined],
    ["missing binding", {}],
    ["null binding", { SEARCH_API: null }],
    ["non-object binding", { SEARCH_API: true }],
    ["missing getByName", { SEARCH_API: {} }],
    ["non-function getByName", { SEARCH_API: { getByName: true } }],
    ["null stub", { SEARCH_API: { getByName() { return null; } } }],
    ["missing stub fetch", { SEARCH_API: { getByName() { return {}; } } }],
    ["non-function stub fetch", { SEARCH_API: { getByName() { return { fetch: true }; } } }],
    ["getByName throws", { SEARCH_API: { getByName() { throw new Error("deployment secret"); } } }],
  ];

  for (const [name, env] of cases) {
    await t.test(name, async () => {
      const response = await worker.fetch(new Request(`${ORIGIN}${HEALTH_PATH}`), env);
      await assertJsonError(response, 500, "search API configuration is invalid");
    });
  }
});

test("container fetch throw and non-Response results return stable 503", async (t) => {
  const cases = [
    ["throws", { fetchError: new Error("container deployment id secret") }],
    ["non-Response", { fetchResult: { status: 200, body: "fake" } }],
  ];

  for (const [name, options] of cases) {
    await t.test(name, async () => {
      const harness = createHarness(options);
      const response = await worker.fetch(new Request(`${ORIGIN}${HEALTH_PATH}`), harness.env);
      await assertJsonError(response, 503, "search API is temporarily unavailable");
      assert.equal(harness.containerRequests.length, 1);
    });
  }
});

test("HEAD errors never include a body", async () => {
  const missingBindingResponse = await worker.fetch(
    new Request(`${ORIGIN}${HEALTH_PATH}`, { method: "HEAD" }),
    {},
  );
  await assertJsonError(missingBindingResponse, 500, "search API configuration is invalid");
  assert.equal(missingBindingResponse.body, null);

  const methodResponse = await worker.fetch(
    new Request(`${ORIGIN}${RANKED_PATH}`, { method: "HEAD" }),
    {},
  );
  await assertJsonError(methodResponse, 405, "method not allowed");
  assert.equal(methodResponse.headers.get("allow"), "POST");
  assert.equal(methodResponse.body, null);
});

test("repeated calls are independent and each makes one container call", async () => {
  let sequence = 0;
  const harness = createHarness({
    responseFactory: () => {
      sequence += 1;
      return new Response(String(sequence), { headers: { "Content-Type": "text/plain" } });
    },
  });
  const request = new Request(`${ORIGIN}${HEALTH_PATH}`);
  const first = await worker.fetch(request, harness.env);
  const second = await worker.fetch(request, harness.env);

  assert.notEqual(first, second);
  assert.equal(await first.text(), "1");
  assert.equal(second.bodyUsed, false);
  assert.equal(await second.text(), "2");
  assert.equal(harness.containerRequests.length, 2);
  assert.deepEqual(harness.instanceNames, ["production", "production"]);
  assert.equal(request.bodyUsed, false);
});
