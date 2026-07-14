const API_PATH_PREFIX = "/game-guide/mhwilds-skill-sim/api";
const HEALTH_PATH = `${API_PATH_PREFIX}/health`;
const METADATA_PATH = `${API_PATH_PREFIX}/catalog/metadata`;
const RANKED_PATH = `${API_PATH_PREFIX}/search/cp-sat/ranked`;

const ROUTES = new Map([
  [HEALTH_PATH, { methods: ["GET", "HEAD"], upstreamPath: "/health" }],
  [
    METADATA_PATH,
    { methods: ["GET", "HEAD"], upstreamPath: "/catalog/metadata" },
  ],
  [
    RANKED_PATH,
    { methods: ["POST"], upstreamPath: "/search/cp-sat/ranked" },
  ],
]);

const CONTAINER_INSTANCE_NAME = "production";
const CONTAINER_REQUEST_ORIGIN = "http://container.invalid";
const MAX_SEARCH_BODY_BYTES = 64 * 1024;

const ERROR_DETAILS = {
  invalidBody: "invalid search request body",
  notFound: "API route not found",
  methodNotAllowed: "method not allowed",
  bodyTooLarge: "search request body is too large",
  unsupportedMediaType: "content type must be application/json",
  rateLimited: "search rate limit exceeded",
  invalidConfiguration: "search API configuration is invalid",
  unavailable: "search API is temporarily unavailable",
};

const SECURITY_HEADERS = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};

function responseHeaders(contentType = null) {
  const headers = new Headers(SECURITY_HEADERS);
  if (contentType !== null) {
    headers.set("Content-Type", contentType);
  }
  return headers;
}

function jsonError(request, status, detail, extraHeaders = undefined) {
  const headers = responseHeaders("application/json; charset=utf-8");
  if (extraHeaders !== undefined) {
    for (const [name, value] of Object.entries(extraHeaders)) {
      headers.set(name, value);
    }
  }
  return new Response(
    request.method === "HEAD" ? null : JSON.stringify({ detail }),
    { status, headers },
  );
}

function methodNotAllowed(request, methods) {
  return jsonError(request, 405, ERROR_DETAILS.methodNotAllowed, {
    Allow: methods.join(", "),
  });
}

function isJsonContentType(request) {
  const contentType = request.headers.get("Content-Type");
  if (contentType === null) {
    return false;
  }
  return contentType.split(";", 1)[0].trim().toLowerCase() === "application/json";
}

async function checkSearchRateLimit(request, env) {
  const limiter = env?.SEARCH_RATE_LIMITER;
  if (limiter === null || typeof limiter !== "object") {
    return { error: true };
  }
  if (typeof limiter.limit !== "function") {
    return { error: true };
  }

  const clientIp = request.headers.get("CF-Connecting-IP") || "unknown";
  let outcome;
  try {
    outcome = await limiter.limit({ key: `ranked:${clientIp}` });
  } catch {
    return { error: true };
  }

  if (
    outcome === null ||
    typeof outcome !== "object" ||
    typeof outcome.success !== "boolean"
  ) {
    return { error: true };
  }
  return { error: false, allowed: outcome.success };
}

async function cancelReader(reader) {
  try {
    await reader.cancel();
  } catch {
    // The stable 413 response takes precedence over a cancellation failure.
  }
}

async function readSearchBody(request) {
  if (request.body === null) {
    return { bytes: new Uint8Array(0) };
  }

  let reader;
  try {
    reader = request.body.getReader();
  } catch {
    return { invalid: true };
  }

  const chunks = [];
  let totalBytes = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      if (!(value instanceof Uint8Array)) {
        return { invalid: true };
      }
      totalBytes += value.byteLength;
      if (totalBytes > MAX_SEARCH_BODY_BYTES) {
        await cancelReader(reader);
        return { tooLarge: true };
      }
      chunks.push(value);
    }
  } catch {
    return { invalid: true };
  }

  const bytes = new Uint8Array(totalBytes);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return { bytes };
}

function createContainerRequest(request, url, route, bodyBytes) {
  const headers = new Headers();
  for (const name of ["Accept", "Content-Type"]) {
    const value = request.headers.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }

  const upstreamUrl = `${CONTAINER_REQUEST_ORIGIN}${route.upstreamPath}${url.search}`;
  const init = {
    method: request.method === "HEAD" ? "GET" : request.method,
    headers,
    redirect: "manual",
  };
  if (request.method === "POST") {
    init.body = bodyBytes;
  }
  return new Request(upstreamUrl, init);
}

function getContainerStub(env) {
  const namespace = env?.SEARCH_API;
  if (namespace === null || typeof namespace !== "object") {
    return null;
  }
  if (typeof namespace.getByName !== "function") {
    return null;
  }

  let stub;
  try {
    stub = namespace.getByName(CONTAINER_INSTANCE_NAME);
  } catch {
    return null;
  }
  if (stub === null || typeof stub !== "object" || typeof stub.fetch !== "function") {
    return null;
  }
  return stub;
}

function proxyResponse(request, upstreamResponse) {
  const headers = responseHeaders(upstreamResponse.headers.get("Content-Type"));
  return new Response(request.method === "HEAD" ? null : upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers,
  });
}

async function handleRequest(request, env) {
  const url = new URL(request.url);
  const route = ROUTES.get(url.pathname);
  if (route === undefined) {
    return jsonError(request, 404, ERROR_DETAILS.notFound);
  }
  if (!route.methods.includes(request.method)) {
    return methodNotAllowed(request, route.methods);
  }

  let bodyBytes;
  if (url.pathname === RANKED_PATH) {
    const rateLimit = await checkSearchRateLimit(request, env);
    if (rateLimit.error) {
      return jsonError(request, 500, ERROR_DETAILS.invalidConfiguration);
    }
    if (!rateLimit.allowed) {
      return jsonError(request, 429, ERROR_DETAILS.rateLimited, {
        "Retry-After": "60",
      });
    }
    if (!isJsonContentType(request)) {
      return jsonError(request, 415, ERROR_DETAILS.unsupportedMediaType);
    }

    const body = await readSearchBody(request);
    if (body.tooLarge) {
      return jsonError(request, 413, ERROR_DETAILS.bodyTooLarge);
    }
    if (body.invalid) {
      return jsonError(request, 400, ERROR_DETAILS.invalidBody);
    }
    bodyBytes = body.bytes;
  }

  const stub = getContainerStub(env);
  if (stub === null) {
    return jsonError(request, 500, ERROR_DETAILS.invalidConfiguration);
  }

  let upstreamRequest;
  try {
    upstreamRequest = createContainerRequest(request, url, route, bodyBytes);
  } catch {
    return jsonError(request, 500, ERROR_DETAILS.invalidConfiguration);
  }

  let upstreamResponse;
  try {
    upstreamResponse = await stub.fetch(upstreamRequest);
  } catch {
    return jsonError(request, 503, ERROR_DETAILS.unavailable);
  }
  if (!(upstreamResponse instanceof Response)) {
    return jsonError(request, 503, ERROR_DETAILS.unavailable);
  }
  return proxyResponse(request, upstreamResponse);
}

export default {
  fetch: handleRequest,
};
