const APPLICATION_PATH = "/game-guide/mhwilds-skill-sim";
const APPLICATION_PATH_WITH_SLASH = `${APPLICATION_PATH}/`;

const PAGE_HEADERS = {
  "Content-Type": "text/html; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};

const TEXT_HEADERS = {
  "Content-Type": "text/plain; charset=utf-8",
  "Cache-Control": "no-store",
};

const PLACEHOLDER_HTML = `<!doctype html>
<html lang="ja">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>MHWILDS スキルシミュレータ</title>
    <style>
      body {
        margin: 0;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      main {
        max-width: 48rem;
        margin: 0 auto;
        padding: 3rem 1rem;
        overflow-wrap: anywhere;
      }
    </style>
  </head>
  <body>
    <main>
      <h1>MHWILDS スキルシミュレータ</h1>
      <p>現在準備中です。</p>
    </main>
  </body>
</html>`;

export default {
  async fetch(request) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method Not Allowed\n", {
        status: 405,
        headers: {
          ...TEXT_HEADERS,
          Allow: "GET, HEAD",
        },
      });
    }

    const url = new URL(request.url);

    if (url.pathname === APPLICATION_PATH) {
      url.pathname = APPLICATION_PATH_WITH_SLASH;
      return new Response(null, {
        status: 308,
        headers: { Location: url.toString() },
      });
    }

    if (url.pathname === APPLICATION_PATH_WITH_SLASH) {
      return new Response(request.method === "HEAD" ? null : PLACEHOLDER_HTML, {
        status: 200,
        headers: PAGE_HEADERS,
      });
    }

    return new Response(request.method === "HEAD" ? null : "Not Found\n", {
      status: 404,
      headers: TEXT_HEADERS,
    });
  },
};
