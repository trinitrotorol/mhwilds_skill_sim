const APPLICATION_PATH = "/skill-sim";
const APPLICATION_PATH_WITH_SLASH = `${APPLICATION_PATH}/`;
const CHECKER_PATH = "/inventory";
const LEGACY_APPLICATION_PATH = "/game-guide/mhwilds-skill-sim";
const LEGACY_CHECKER_PATH = "/game-guide/mhwilds-inventory-checker";
const CANONICAL_ORIGIN = "https://mhwilds.trinitrotorol.com";
const APPLICATION_PATHS = [APPLICATION_PATH, LEGACY_APPLICATION_PATH];
const PAGE_PATHS = [...APPLICATION_PATHS, CHECKER_PATH, LEGACY_CHECKER_PATH];
const LEGACY_PAGES = new Map([
  [LEGACY_APPLICATION_PATH, APPLICATION_PATH],
  [LEGACY_CHECKER_PATH, CHECKER_PATH],
]);

const API_PATH_PREFIX = `${APPLICATION_PATH}/api`;
const API_ROUTES = new Map([
  [`${API_PATH_PREFIX}/health`, { method: "GET", upstreamPath: "/health" }],
  [
    `${API_PATH_PREFIX}/catalog/metadata`,
    { method: "GET", upstreamPath: "/catalog/metadata" },
  ],
  [
    `${API_PATH_PREFIX}/search/cp-sat/ranked`,
    { method: "POST", upstreamPath: "/search/cp-sat/ranked" },
  ],
]);
for (const [path, route] of [...API_ROUTES]) {
  API_ROUTES.set(path.replace(APPLICATION_PATH, LEGACY_APPLICATION_PATH), route);
}

const SECURITY_HEADERS = {
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};

const STATIC_ASSETS_UNAVAILABLE = "Static assets are unavailable\n";
const API_NOT_CONFIGURED = "search API is not configured";
const API_CONFIGURATION_INVALID = "search API configuration is invalid";
const API_REQUEST_FAILED = "search API request failed";

function withSecurityHeaders(headers = undefined) {
  const result = new Headers(headers);
  for (const [name, value] of Object.entries(SECURITY_HEADERS)) {
    result.set(name, value);
  }
  return result;
}

function plainTextResponse(request, body, status, extraHeaders = undefined) {
  const headers = withSecurityHeaders(extraHeaders);
  headers.set("Content-Type", "text/plain; charset=utf-8");
  headers.set("Cache-Control", "no-store");
  return new Response(request.method === "HEAD" ? null : body, {
    status,
    headers,
  });
}

function jsonErrorResponse(request, detail, status) {
  const headers = withSecurityHeaders();
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.set("Cache-Control", "no-store");
  return new Response(
    request.method === "HEAD" ? null : JSON.stringify({ detail }),
    { status, headers },
  );
}

function methodNotAllowed(request, allowedMethods) {
  return plainTextResponse(request, "Method Not Allowed\n", 405, {
    Allow: allowedMethods.join(", "),
  });
}

function notFound(request) {
  return plainTextResponse(request, "Not Found\n", 404);
}

function isFingerprintedAsset(pathname) {
  return (
    PAGE_PATHS.some((path) => pathname.startsWith(`${path}/assets/`)) &&
    /\/[^/]+-[A-Za-z0-9_-]{8,}\.[^/]+$/.test(pathname)
  );
}

function staticCacheControl(pathname, status) {
  if (pathname === APPLICATION_PATH_WITH_SLASH) {
    return "no-cache";
  }
  if (status >= 200 && status < 300 && isFingerprintedAsset(pathname)) {
    return "public, max-age=31536000, immutable";
  }
  return "no-cache";
}

async function serveStaticAsset(request, env, pathname) {
  if (!env?.ASSETS || typeof env.ASSETS.fetch !== "function") {
    return plainTextResponse(request, STATIC_ASSETS_UNAVAILABLE, 500);
  }

  let assetResponse;
  try {
    assetResponse = await env.ASSETS.fetch(request);
  } catch {
    return plainTextResponse(request, STATIC_ASSETS_UNAVAILABLE, 500);
  }

  if (!(assetResponse instanceof Response)) {
    return plainTextResponse(request, STATIC_ASSETS_UNAVAILABLE, 500);
  }

  const headers = withSecurityHeaders(assetResponse.headers);
  headers.set(
    "Cache-Control",
    staticCacheControl(pathname, assetResponse.status),
  );
  return new Response(request.method === "HEAD" ? null : assetResponse.body, {
    status: assetResponse.status,
    statusText: assetResponse.statusText,
    headers,
  });
}

function parseApiOrigin(value, requestOrigin) {
  if (
    typeof value !== "string" ||
    value.length === 0 ||
    value !== value.trim() ||
    value.includes("?") ||
    value.includes("#") ||
    !/^https:\/\/[^/?#]+\/?$/i.test(value)
  ) {
    return false;
  }

  let apiUrl;
  try {
    apiUrl = new URL(value);
  } catch {
    return false;
  }

  if (
    apiUrl.protocol !== "https:" ||
    apiUrl.username !== "" ||
    apiUrl.password !== "" ||
    apiUrl.pathname !== "/" ||
    apiUrl.search !== "" ||
    apiUrl.hash !== ""
  ) {
    return false;
  }

  if (apiUrl.origin === requestOrigin) {
    return false;
  }

  return apiUrl.origin;
}

function createUpstreamRequest(request, upstreamUrl) {
  const headers = new Headers();
  for (const name of ["Accept", "Content-Type"]) {
    const value = request.headers.get(name);
    if (value !== null) {
      headers.set(name, value);
    }
  }

  const init = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method === "POST" && request.body !== null) {
    init.body = request.body;
    init.duplex = "half";
  }
  return new Request(upstreamUrl, init);
}

async function proxyApiRequest(request, env, url, route) {
  if (env?.REMOTE_SEARCH_ENABLED !== "true") {
    return jsonErrorResponse(request, API_NOT_CONFIGURED, 503);
  }
  const configuredOrigin = env?.API_ORIGIN;
  if (
    configuredOrigin === undefined ||
    configuredOrigin === null ||
    configuredOrigin === ""
  ) {
    return jsonErrorResponse(request, API_NOT_CONFIGURED, 503);
  }

  const apiOrigin = parseApiOrigin(configuredOrigin, url.origin);
  if (apiOrigin === false) {
    return jsonErrorResponse(request, API_CONFIGURATION_INVALID, 500);
  }

  const upstreamUrl = `${apiOrigin}${route.upstreamPath}${url.search}`;
  const upstreamRequest = createUpstreamRequest(request, upstreamUrl);

  let upstreamResponse;
  try {
    upstreamResponse = await fetch(upstreamRequest);
  } catch {
    return jsonErrorResponse(request, API_REQUEST_FAILED, 502);
  }

  if (!(upstreamResponse instanceof Response)) {
    return jsonErrorResponse(request, API_REQUEST_FAILED, 502);
  }

  const headers = withSecurityHeaders();
  const contentType = upstreamResponse.headers.get("Content-Type");
  if (contentType !== null) {
    headers.set("Content-Type", contentType);
  }
  headers.set("Cache-Control", "no-store");
  return new Response(request.method === "HEAD" ? null : upstreamResponse.body, {
    status: upstreamResponse.status,
    statusText: upstreamResponse.statusText,
    headers,
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const apiRoute = API_ROUTES.get(url.pathname);

    if (apiRoute !== undefined) {
      const allowedMethods =
        apiRoute.method === "GET" ? ["GET", "HEAD"] : [apiRoute.method];
      if (!allowedMethods.includes(request.method)) {
        return methodNotAllowed(request, allowedMethods);
      }
      return proxyApiRequest(request, env, url, apiRoute);
    }

    const legacyPath = [...LEGACY_PAGES.keys()].find((path) =>
      [path, `${path}/`, `${path}/index.html`].includes(url.pathname),
    );
    if (legacyPath && (url.searchParams.get("legacy") !== "1" || url.origin === CANONICAL_ORIGIN)) {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(request, ["GET", "HEAD"]);
      }
      return new Response(null, {
        status: 301,
        headers: withSecurityHeaders({
          Location: `${CANONICAL_ORIGIN}${LEGACY_PAGES.get(legacyPath)}/${url.search}`,
          // The export escape hatch depends on the query; do not cache across it.
          "Cache-Control": "no-store",
        }),
      });
    }

    if (url.pathname === "/" || url.pathname === "/index.html") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(request, ["GET", "HEAD"]);
      }
      return new Response(null, {
        status: 301,
        headers: withSecurityHeaders({ Location: `${url.origin}${APPLICATION_PATH}/${url.search}`, "Cache-Control": "no-store" }),
      });
    }

    const pagePath = PAGE_PATHS.find((path) => url.pathname === path || url.pathname === `${path}/index.html`);
    if (pagePath) {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(request, ["GET", "HEAD"]);
      }
      url.pathname = `${pagePath}/`;
      return new Response(null, {
        status: 308,
        headers: withSecurityHeaders({
          Location: url.toString(),
          "Cache-Control": "no-store",
        }),
      });
    }

    if (
      PAGE_PATHS.some((path) => url.pathname === `${path}/` || url.pathname.startsWith(`${path}/assets/`)) ||
      APPLICATION_PATHS.some((path) =>
        [`${path}/release.json`, `${path}/catalog/checker-catalog.json`, `${path}/browser-solver/manifest.json`].includes(url.pathname) ||
        new RegExp(`^${path}/browser-solver/catalog-[a-f0-9]{64}\\.json$`).test(url.pathname)
      ) ||
      ["/robots.txt", "/sitemap.xml", "/ads.txt"].includes(url.pathname)
    ) {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return methodNotAllowed(request, ["GET", "HEAD"]);
      }
      return serveStaticAsset(request, env, url.pathname);
    }

    return notFound(request);
  },
};
