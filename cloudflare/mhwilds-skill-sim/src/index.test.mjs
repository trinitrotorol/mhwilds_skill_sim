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
  ({ default: worker } = await import("./index.mjs"));
} finally {
  globalThis.fetch = originalFetch;
  process.stdout.write = originalStdoutWrite;
}

const ORIGIN = "https://preview.example.test:8787";
const APPLICATION_PATH = "/game-guide/mhwilds-skill-sim";
const APPLICATION_PATH_WITH_SLASH = `${APPLICATION_PATH}/`;
const QUERY = "?source=test%20value&source=second&empty=";

test("module exposes one Worker fetch handler without import side effects", () => {
  assert.equal(importNetworkCalls, 0);
  assert.equal(importStdoutWrites, 0);
  assert.equal(typeof worker, "object");
  assert.notEqual(worker, null);
  assert.equal(typeof worker.fetch, "function");
  assert.deepEqual(Object.keys(worker), ["fetch"]);
});

test("GET redirects the slashless path and preserves origin and query", async () => {
  const response = await worker.fetch(
    new Request(`${ORIGIN}${APPLICATION_PATH}${QUERY}`),
  );

  assert.equal(response.status, 308);
  assert.equal(
    response.headers.get("location"),
    `${ORIGIN}${APPLICATION_PATH_WITH_SLASH}${QUERY}`,
  );
});

test("HEAD redirects to the same slash-appended URL", async () => {
  const response = await worker.fetch(
    new Request(`${ORIGIN}${APPLICATION_PATH}${QUERY}`, { method: "HEAD" }),
  );

  assert.equal(response.status, 308);
  assert.equal(
    response.headers.get("location"),
    `${ORIGIN}${APPLICATION_PATH_WITH_SLASH}${QUERY}`,
  );
  assert.equal(response.body, null);
  assert.equal(await response.text(), "");
});

test("GET serves the Japanese placeholder page with security headers", async () => {
  const response = await worker.fetch(
    new Request(`${ORIGIN}${APPLICATION_PATH_WITH_SLASH}`),
  );

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "text/html; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");

  const html = await response.text();
  assert.match(html, /^<!doctype html>/);
  assert.match(html, /<html lang="ja">/);
  assert.match(html, /<title>MHWILDS スキルシミュレータ<\/title>/);
  assert.match(html, /<h1>MHWILDS スキルシミュレータ<\/h1>/);
  assert.match(html, /現在準備中です。/);
  assert.doesNotMatch(html, /https?:\/\//i);
  assert.doesNotMatch(html, /<(?:form|img|link|script)\b/i);
});

test("HEAD serves page headers with an empty body", async () => {
  const response = await worker.fetch(
    new Request(`${ORIGIN}${APPLICATION_PATH_WITH_SLASH}`, { method: "HEAD" }),
  );

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "text/html; charset=utf-8");
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.equal(response.headers.get("referrer-policy"), "no-referrer");
  assert.equal(response.body, null);
  assert.equal(await response.text(), "");
});

test("unhandled paths return plain-text 404 responses", async () => {
  const paths = [
    "/",
    "/game-guide/",
    "/game-guide/exponential-idle-minigame-guide",
    `${APPLICATION_PATH_WITH_SLASH}unknown`,
  ];

  for (const path of paths) {
    const response = await worker.fetch(new Request(`${ORIGIN}${path}`));
    assert.equal(response.status, 404, path);
    assert.equal(
      response.headers.get("content-type"),
      "text/plain; charset=utf-8",
      path,
    );
    assert.equal(response.headers.get("cache-control"), "no-store", path);
  }
});

test("unsupported methods take priority and do not consume the request body", async () => {
  const request = new Request(`${ORIGIN}${APPLICATION_PATH}`, {
    method: "POST",
    body: "payload",
  });
  const response = await worker.fetch(request);

  assert.equal(response.status, 405);
  assert.equal(response.headers.get("allow"), "GET, HEAD");
  assert.equal(response.headers.get("content-type"), "text/plain; charset=utf-8");
  assert.equal(request.bodyUsed, false);
});

test("calls do not mutate input and return independent response bodies", async () => {
  const request = new Request(`${ORIGIN}${APPLICATION_PATH_WITH_SLASH}?source=test`, {
    headers: { "X-Test": "unchanged" },
  });
  const snapshot = {
    url: request.url,
    method: request.method,
    headers: [...request.headers],
  };

  const first = await worker.fetch(request);
  const firstBody = await first.text();
  const second = await worker.fetch(request);
  assert.equal(second.bodyUsed, false);
  const secondBody = await second.text();

  assert.notEqual(first, second);
  assert.equal(firstBody, secondBody);
  assert.match(secondBody, /現在準備中です。/);
  assert.equal(request.url, snapshot.url);
  assert.equal(request.method, snapshot.method);
  assert.deepEqual([...request.headers], snapshot.headers);
  assert.equal(request.bodyUsed, false);
});
