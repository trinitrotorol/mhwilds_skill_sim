/** Fresh-context browser acceptance checks against one locally built real release.
 * Run from the repository root: sh scripts/nodew apps/web/scripts/service-smoke.mjs
 * Optional: --assets .build/service-assets --output .build/service-smoke
 * Remote: --base-url https://trinitrotorol.com (must already be verified).
 * For a verified workers.dev URL, also set SERVICE_SMOKE_VERIFIED_ORIGIN to
 * that exact HTTPS origin copied from the Cloudflare deployment response.
 * No user browser profiles, remote APIs or persistent browser contexts are used.
 */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, realpath, stat, mkdir, writeFile, symlink } from "node:fs/promises";
import { resolve, relative, extname, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const args = process.argv.slice(2);
function option(name, fallback) {
  const index = args.indexOf(name);
  if (index === -1) return fallback;
  assert(args[index + 1] && !args[index + 1].startsWith("--"), `${name} requires a value`);
  return args[index + 1];
}
assert(args.length % 2 === 0 && args.every((arg, index) => index % 2 === 1 || ["--assets", "--output", "--base-url"].includes(arg)), "Unknown argument or missing value");
const remoteBase = option("--base-url", null);
assert(!remoteBase || !args.includes("--assets"), "Choose either remote deployment or local assets");
const assets = remoteBase ? null : await realpath(resolve(ROOT, option("--assets", ".build/service-assets")));
const output = resolve(ROOT, option("--output", ".build/service-smoke"));
assert(relative(ROOT, output) && !relative(ROOT, output).startsWith(".."), "Output must remain in the repository");
await mkdir(output, { recursive: true });
process.env.PLAYWRIGHT_BROWSERS_PATH ??= resolve(ROOT, ".cache/ms-playwright");
const browserLibraries = resolve(ROOT, ".venv/browser-libs/usr/lib/x86_64-linux-gnu");
if (process.platform === "linux" && await stat(browserLibraries).then((value) => value.isDirectory(), () => false)) {
  process.env.LD_LIBRARY_PATH = [browserLibraries, process.env.LD_LIBRARY_PATH].filter(Boolean).join(":");
}
if (process.platform === "linux" && !process.env.FONTCONFIG_FILE && await stat("/mnt/c/Windows/Fonts/meiryo.ttc").then((value) => value.isFile(), () => false)) {
  const fontCache = resolve(ROOT, ".cache/fontconfig");
  const fontDirectory = resolve(ROOT, ".venv/browser-fonts");
  await mkdir(fontCache, { recursive: true });
  await mkdir(fontDirectory, { recursive: true });
  for (const name of ["meiryo.ttc", "meiryob.ttc"]) {
    const target = `/mnt/c/Windows/Fonts/${name}`;
    const link = resolve(fontDirectory, name);
    await symlink(target, link).catch(async (error) => { if (error.code !== "EEXIST" || await realpath(link) !== await realpath(target)) throw error; });
  }
  const config = resolve(output, "fontconfig.xml");
  const escapedCache = fontCache.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  const escapedDirectory = fontDirectory.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
  await writeFile(config, `<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>/usr/share/fonts</dir><dir>${escapedDirectory}</dir><cachedir>${escapedCache}</cachedir></fontconfig>`);
  process.env.FONTCONFIG_FILE = config;
}
const { chromium } = await import("playwright");
const { default: AxeBuilder } = await import("@axe-core/playwright");
const paths = { checker: "/game-guide/mhwilds-inventory-checker/", sim: "/game-guide/mhwilds-skill-sim/" };
const storageKey = "mhwilds.inventory.profile.v1";
let origin, server, release;
if (remoteBase) {
  const url = new URL(remoteBase);
  assert(url.protocol === "https:" && !url.username && !url.password && !url.search && !url.hash && !url.port && url.pathname === "/", "Deployment must be a bare HTTPS origin");
  assert(url.hostname === "trinitrotorol.com" || (url.hostname.endsWith(".workers.dev") && url.origin === process.env.SERVICE_SMOKE_VERIFIED_ORIGIN), "Deployment origin must be the known production domain or exact verified workers.dev origin");
  origin = url.origin;
  const response = await fetch(`${origin}${paths.sim}release.json`, { redirect: "error", signal: AbortSignal.timeout(30_000), headers: { Accept: "application/json" } });
  assert.equal(response.status, 200, "Remote release manifest unavailable");
  assert(/^application\/json(?:;|$)/i.test(response.headers.get("content-type") ?? ""), "Remote release must be JSON");
  const body = await response.text();
  assert(Buffer.byteLength(body) <= 65536, "Remote manifest is too large");
  release = JSON.parse(body);
  assert.deepEqual(release.source_dirty, { parent: false, checker: false }, "Published release must identify clean committed sources");
} else {
  release = JSON.parse(await readFile(resolve(assets, `.${paths.sim}release.json`), "utf8"));
}
assert.equal(release.fixture, false, "Acceptance must use a real release, not a fixture catalog");
assert.equal(release.remote_enabled, false, "This smoke intentionally verifies the no-cost local-search release");
assert(release.appraisal_rules_available, "Real appraisal rules are required");

// Apply the same static response headers emitted for production, including CSP.
if (!remoteBase) {
const headerRules = [];
for (const line of (await readFile(resolve(assets, "_headers"), "utf8")).split(/\r?\n/)) {
  if (line.startsWith("/")) headerRules.push({ path: line.trim(), headers: {} });
  else if (/^\s+[^:]+:/.test(line) && headerRules.length) {
    const index = line.indexOf(":");
    headerRules.at(-1).headers[line.slice(0, index).trim()] = line.slice(index + 1).trim();
  }
}
const contentTypes = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2", ".ico": "image/x-icon" };
server = createServer(async (request, response) => {
  try {
    if (!["GET", "HEAD"].includes(request.method)) { response.writeHead(405).end(); return; }
    const pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
    const candidate = resolve(assets, `.${pathname}`, pathname.endsWith("/") ? "index.html" : "");
    const path = await realpath(candidate);
    if (path !== assets && !path.startsWith(`${assets}${sep}`)) { response.writeHead(403).end(); return; }
    if (!(await stat(path)).isFile()) { response.writeHead(404).end(); return; }
    const bytes = await readFile(path);
    const headers = { "Content-Type": contentTypes[extname(path)] ?? "application/octet-stream", "Content-Length": bytes.length };
    for (const rule of headerRules) if (rule.path.endsWith("*") ? pathname.startsWith(rule.path.slice(0, -1)) : pathname === rule.path) Object.assign(headers, rule.headers);
    response.writeHead(200, headers);
    response.end(request.method === "HEAD" ? undefined : bytes);
  } catch { response.writeHead(404).end(); }
});
await new Promise((resolveListen) => server.listen(0, "127.0.0.1", resolveListen));
origin = `http://127.0.0.1:${server.address().port}`;
}
const report = { started_at: new Date().toISOString(), origin, release, checks: [], layouts: [], accessibility: [], network: [], console_errors: [], page_errors: [], failures: [] };
let browser;
let activePage;
async function step(name, callback) {
  const start = Date.now();
  try { const evidence = await callback(); report.checks.push({ name, passed: true, ms: Date.now() - start, evidence }); console.log(`PASS ${name}`); }
  catch (error) { report.checks.push({ name, passed: false, ms: Date.now() - start, error: String(error) }); throw error; }
}
async function track(context) {
  // Observe worker messages without changing their contents, timing or delivery.
  await context.addInitScript(() => {
    window.__smokeWorker = { requests: [], results: [], terminations: 0 };
    const NativeWorker = window.Worker;
    window.Worker = class extends NativeWorker {
      constructor(...args) {
        super(...args);
        this.addEventListener("message", (event) => {
          if (event.data?.type === "result") window.__smokeWorker.results.push(structuredClone(event.data.result));
        });
      }
      postMessage(message, ...rest) {
        if (message?.type === "search") window.__smokeWorker.requests.push(structuredClone(message.request));
        return super.postMessage(message, ...rest);
      }
      terminate() { window.__smokeWorker.terminations += 1; return super.terminate(); }
    };
  });
  context.on("request", (request) => {
    const body = request.postData() ?? "";
    report.network.push({ url: request.url(), method: request.method(), type: request.resourceType(), body_bytes: Buffer.byteLength(body), contains_private_fields: /profile_id|updated_at|Smoke private label/.test(body) });
  });
  context.on("page", (page) => {
    page.on("pageerror", (error) => report.page_errors.push(String(error)));
    page.on("console", (message) => { if (message.type() === "error") report.console_errors.push({ page: page.url(), text: message.text() }); });
    page.setDefaultTimeout(60_000);
  });
}
async function ready(page, kind) {
  await page.goto(`${origin}${paths[kind]}`, { waitUntil: "networkidle" });
  console.log("Navigation ready", kind);
  if (kind === "checker") {
    await page.locator('.quantity-control input').first().waitFor({ state: "attached" });
    console.log("Checker input readiness", await page.locator('.quantity-control input').first().evaluate((element) => ({ label: element.getAttribute('aria-label'), type: element.type, width: element.getBoundingClientRect().width, height: element.getBoundingClientRect().height, visibility: getComputedStyle(element).visibility })));
    await page.getByRole("textbox", { name: /の所持数$/ }).first().waitFor();
  }
  else await page.getByRole("button", { name: "検索する", exact: true }).waitFor();
}
async function rawProfile(page) { return page.evaluate((key) => localStorage.getItem(key), storageKey); }
async function profile(page) { return JSON.parse(await rawProfile(page)); }
async function saved(page) { await page.getByText("このブラウザに保存済み", { exact: true }).waitFor(); }
async function quantity(page, value) {
  const input = page.getByRole("textbox", { name: /の所持数$/ }).first();
  await input.fill(String(value)); await input.press("Enter"); await saved(page);
}
async function layout(page, name, settings = {}) {
  await page.evaluate(() => document.fonts.ready);
  const dimensions = await page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    const overflowingContainers = [...document.querySelectorAll("dialog[open], fieldset, .inventory-row, .filter-bar, .form-card, .candidate-card, .summary-card")].filter((element) => element.clientWidth && element.scrollWidth > element.clientWidth + 1).map((element) => ({ tag: element.tagName, class: element.className, width: element.clientWidth, scrollWidth: element.scrollWidth }));
    return { width, scrollWidth: document.documentElement.scrollWidth, dpr: devicePixelRatio, overflowingContainers, offenders: [...document.querySelectorAll("body *")].filter((element) => {
      const rect = element.getBoundingClientRect(); const style = getComputedStyle(element);
      return rect.width && style.visibility !== "hidden" && style.display !== "none" && (rect.right > width + 1 || rect.left < -1) && !element.classList.contains("skip-link");
    }).slice(0, 12).map((element) => ({ tag: element.tagName, class: element.className, text: element.textContent?.trim().slice(0, 70) })) };
  });
  report.layouts.push({ name, ...settings, ...dimensions });
  await page.screenshot({ path: resolve(output, `${name}.png`), fullPage: false });
  assert(dimensions.scrollWidth <= dimensions.width + 1, `${name}: horizontal overflow ${JSON.stringify(dimensions)}`);
  assert.equal(dimensions.overflowingContainers.length, 0, `${name}: internal horizontal overflow ${JSON.stringify(dimensions.overflowingContainers)}`);
}
async function accessibility(page, name) {
  const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const violations = result.violations.map(({ id, impact, description, helpUrl, nodes }) => ({ id, impact, description, helpUrl, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) }));
  report.accessibility.push({ name, violations, incomplete: result.incomplete.map(({ id }) => id), passes: result.passes.length });
  assert(!violations.some((violation) => ["critical", "serious"].includes(violation.impact)), `${name}: serious/critical accessibility violations ${JSON.stringify(violations)}`);
}
async function importBackup(page, filename) {
  await page.getByLabel("復元するJSONファイル").setInputFiles(filename);
  await page.getByRole("dialog", { name: "バックアップの取込確認" }).waitFor();
}

try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "ja-JP", acceptDownloads: true });
  await track(context);
  const checker = await context.newPage(); activePage = checker;
  let decorationId, charmId, backupPath, persisted;
  await step("checker real catalog, quantity above one, persistence", async () => {
    await ready(checker, "checker");
    assert.equal(await rawProfile(checker), null);
    await layout(checker, "checker-full-list-1440");
    decorationId = (await checker.locator(".inventory-row .item-id").first().innerText()).trim();
    await checker.getByRole("searchbox", { name: "名称・ID・スキルで検索" }).fill(decorationId);
    await quantity(checker, 3);
    assert.equal((await profile(checker)).decorations.find((item) => item.decoration_id === decorationId).quantity, 3);
    await checker.reload({ waitUntil: "networkidle" });
    await checker.getByRole("searchbox", { name: "名称・ID・スキルで検索" }).fill(decorationId);
    assert.equal(await checker.getByRole("textbox", { name: /の所持数$/ }).first().inputValue(), "3");
    return { decorationId, quantity: 3 };
  });
  await step("cross-tab propagation preserves a newer saved quantity over an older draft", async () => {
    const peer = await context.newPage();
    try {
      await ready(peer, "checker");
      await peer.getByRole("searchbox", { name: "名称・ID・スキルで検索" }).fill(decorationId);
      const draft = checker.getByRole("textbox", { name: /の所持数$/ }).first();
      await draft.fill("2");
      await quantity(peer, 5);
      await checker.waitForFunction(({ key, id }) => JSON.parse(localStorage.getItem(key)).decorations.find((item) => item.decoration_id === id)?.quantity === 5, { key: storageKey, id: decorationId });
      assert.equal(await draft.inputValue(), "2", "External updates must preserve visible unfinished input for review");
      await draft.press("Tab");
      await checker.locator('.field-error, [role="alert"]').filter({ hasText: /更新|競合|編集開始/ }).first().waitFor();
      assert.equal((await profile(checker)).decorations.find((item) => item.decoration_id === decorationId).quantity, 5);
      await checker.screenshot({ path: resolve(output, "checker-cross-tab-conflict.png"), fullPage: false });
      await checker.reload({ waitUntil: "networkidle" });
      await checker.getByRole("searchbox", { name: "名称・ID・スキルで検索" }).fill(decorationId);
      assert.equal(await checker.getByRole("textbox", { name: /の所持数$/ }).first().inputValue(), "5");
      await quantity(checker, 3);
      await peer.waitForFunction(({ key, id }) => JSON.parse(localStorage.getItem(key)).decorations.find((item) => item.decoration_id === id)?.quantity === 3, { key: storageKey, id: decorationId });
      await peer.getByRole("textbox", { name: /の所持数$/ }).first().waitFor();
      assert.equal(await peer.getByRole("textbox", { name: /の所持数$/ }).first().inputValue(), "3");
    } finally { await peer.close(); }
  });
  await step("fixed charm quantity persists", async () => {
    await checker.getByRole("button", { name: "固定護石", exact: true }).click();
    charmId = (await checker.locator(".inventory-row .item-id").first().innerText()).trim();
    await checker.getByRole("searchbox", { name: "名称・ID・スキルで検索" }).fill(charmId);
    await quantity(checker, 2);
    assert.equal((await profile(checker)).fixed_charms.find((item) => item.equipment_id === charmId).quantity, 2);
  });
  await step("appraisal rule template, keyboard dialog, edit and quantity", async () => {
    await checker.getByRole("button", { name: "鑑定護石", exact: true }).click();
    await checker.getByRole("button", { name: "＋ 鑑定護石を登録", exact: true }).click();
    await checker.getByLabel("ルールから入力を開始").selectOption({ index: 1 });
    await checker.getByLabel("表示ラベル（任意）").fill("Smoke private label — NOT FOR NETWORK");
    await checker.getByRole("textbox", { name: "所持数", exact: true }).fill("2");
    await checker.getByText("登録可能な能力です", { exact: true }).waitFor();
    await checker.setViewportSize({ width: 320, height: 900 });
    await layout(checker, "checker-appraisal-dialog-320");
    await accessibility(checker, "checker-appraisal-dialog");
    await checker.getByRole("button", { name: "この護石を保存" }).click();
    await saved(checker);
    await checker.setViewportSize({ width: 1440, height: 900 });
    await checker.getByRole("button", { name: /Smoke private label.*を編集$/ }).click();
    await checker.getByRole("textbox", { name: "所持数", exact: true }).fill("3");
    await checker.getByRole("button", { name: "この護石を保存" }).click();
    await saved(checker);
    assert.equal((await profile(checker)).appraisal_charms[0].quantity, 3);
    await checker.getByRole("button", { name: /Smoke private label.*を編集$/ }).click();
    await checker.keyboard.press("Escape");
    assert.equal(await checker.getByRole("dialog").count(), 0);
    assert.match(await checker.evaluate(() => document.activeElement?.getAttribute("aria-label") ?? ""), /を編集$/);
  });
  await step("download backup, preview before writes, max merge and repeat idempotency", async () => {
    const downloading = checker.waitForEvent("download");
    await checker.getByRole("button", { name: "JSONをダウンロード", exact: true }).click();
    const download = await downloading;
    assert.match(download.suggestedFilename(), /v1.*\.json$/);
    backupPath = resolve(output, "synthetic-browser-profile.v1.json");
    await download.saveAs(backupPath);
    const original = JSON.parse(await readFile(backupPath, "utf8"));
    assert.equal(original.appraisal_charms[0].quantity, 3);
    await checker.getByRole("button", { name: "装飾品", exact: true }).click();
    await quantity(checker, 1);
    const beforePreview = await rawProfile(checker);
    await importBackup(checker, backupPath);
    assert.equal(await rawProfile(checker), beforePreview);
    await layout(checker, "checker-import-preview-1440");
    await accessibility(checker, "checker-import-preview");
    await checker.getByRole("button", { name: "統合して保存", exact: true }).click();
    await saved(checker);
    const once = await rawProfile(checker);
    assert.equal(JSON.parse(once).decorations.find((item) => item.decoration_id === decorationId).quantity, 3);
    await importBackup(checker, backupPath);
    await checker.getByRole("button", { name: "統合して保存", exact: true }).click();
    await saved(checker);
    assert.equal(await rawProfile(checker), once, "Repeated backup merge must not add quantities or rewrite timestamps");
    persisted = await profile(checker);
  });
  const sim = await context.newPage(); activePage = sim;
  await step("same-origin inventory, browser search top20, anonymous worker snapshot", async () => {
    await ready(sim, "sim");
    await sim.getByLabel("所持品を考慮する", { exact: true }).check();
    await sim.getByRole("list", { name: "所持品の状態" }).getByText(/所持品の保存日時/).waitFor();
    await sim.getByLabel("表示件数", { exact: true }).fill("20");
    await sim.getByLabel("計算方法", { exact: true }).selectOption("auto");
    await sim.getByRole("button", { name: "検索する", exact: true }).click();
    await sim.getByRole("heading", { name: "検索結果", exact: true }).waitFor({ timeout: 45_000 });
    const captured = await sim.evaluate(() => window.__smokeWorker);
    const request = captured.requests.at(-1);
    assert.equal(request.max_results, 20);
    assert.deepEqual(Object.keys(request.inventory).sort(), ["schema_version", "catalog_revision", "decorations", "fixed_charms", "appraisal_charms"].sort());
    const snapshot = JSON.stringify(request.inventory);
    for (const privateValue of [persisted.profile_id, persisted.updated_at, persisted.appraisal_charms[0].instance_id, persisted.appraisal_charms[0].label]) assert(!snapshot.includes(privateValue), "Search snapshot leaked personal bookkeeping");
    assert.match(request.inventory.appraisal_charms[0].instance_id, /^owned:\d+$/);
    const result = captured.results.at(-1);
    const candidates = result?.candidates ?? [];
    assert.equal(candidates.length, 20, `Unconstrained owned top20 search should yield20 candidates: ${JSON.stringify(result)}`);
    assert.equal(await sim.locator(".candidate-card").count(), 20);
    const quantities = new Map(request.inventory.decorations.map((entry) => [entry.decoration_id, entry.quantity]));
    const charms = new Set([...request.inventory.fixed_charms.map((entry) => entry.equipment_id), ...request.inventory.appraisal_charms.map((entry) => entry.instance_id)]);
    for (const candidate of candidates) {
      const used = new Map();
      for (const placement of candidate.placements) used.set(placement.decoration_id, (used.get(placement.decoration_id) ?? 0) + 1);
      for (const [id, count] of used) assert(count <= (quantities.get(id) ?? 0), "Result uses unowned decoration quantity");
      assert(charms.has(candidate.equipment.find((item) => item.part === "charm").equipment_id), "Result uses an unowned charm");
    }
    await writeFile(resolve(output, "owned-search-evidence.json"), JSON.stringify({ request, result }, null, 2));
    return { max_results: request.max_results, candidates: candidates.length, status: result.status, timed_out: result.timed_out, workerTerminations: captured.terminations };
  });
  await step("both applications responsive widths and serious/critical accessibility", async () => {
    for (const [kind, page] of [["checker", checker], ["sim", sim]]) {
      activePage = page;
      for (const [width, height] of [[1440, 900], [1024, 768], [768, 1024], [390, 844], [320, 568]]) {
        await page.setViewportSize({ width, height });
        await page.evaluate(() => scrollTo(0, 0));
        await layout(page, `${kind}-${width}`, { height });
        await page.locator(kind === "checker" ? ".inventory-panel" : ".search-form").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(output, `${kind}-${width}-form.png`), fullPage: false });
        if (kind === "sim") {
          await page.locator(".candidate-card").first().scrollIntoViewIfNeeded();
          await page.screenshot({ path: resolve(output, `${kind}-${width}-result.png`), fullPage: false });
        }
      }
      await accessibility(page, `${kind}-320`);
    }
  });
  await step("200 percent zoom equivalent layout and device scale", async () => {
    // At 200% browser zoom a 1440px physical window has a720 CSS-pixel viewport
    // and DPR2. Reproduce those metrics without changing application CSS.
    const zoomContext = await browser.newContext({ viewport: { width: 720, height: 450 }, deviceScaleFactor: 2, locale: "ja-JP" });
    await track(zoomContext);
    try {
      for (const kind of ["checker", "sim"]) {
        const page = await zoomContext.newPage(); activePage = page;
        await ready(page, kind);
        if (kind === "checker") await page.getByRole("searchbox", { name: "名称・ID・スキルで検索" }).fill(decorationId);
        await layout(page, `${kind}-zoom-200`, { zoom: 2, physicalWindowWidth: 1440, method: "equivalent CSS viewport and DPR; no page CSS mutation" });
        await accessibility(page, `${kind}-zoom-200`);
        await page.close();
      }
    } finally { await zoomContext.close(); }
  });
  await step("visible service context and canonical metadata without JavaScript", async () => {
    const requiredLinks = ["/", "/game-guide/", "/game-guide/mhwilds-guide/", "/about/", "/privacy/", "/contact/"];
    const metadata = [];
    const noScriptContext = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 320, height: 568 }, locale: "ja-JP" });
    await track(noScriptContext);
    try {
      for (const [kind, page] of [["checker", checker], ["sim", sim]]) {
        assert.equal(await page.locator("main").count(), 1, `${kind}: exactly one application main landmark`);
        assert.equal(await page.locator("h1").count(), 1, `${kind}: exactly one application h1`);
        await page.locator("#service-overview").scrollIntoViewIfNeeded();
        await page.screenshot({ path: resolve(output, `${kind}-320-service-context.png`), fullPage: false });
        const noScriptPage = await noScriptContext.newPage(); activePage = noScriptPage;
        const response = await noScriptPage.goto(`${origin}${paths[kind]}`, { waitUntil: "load" });
        assert.equal(response.status(), 200);
        assert.equal(await noScriptPage.locator("#root > *").count(), 0, "Application JavaScript is disabled for this check");
        assert.equal(await noScriptPage.locator("main").count(), 1, `${kind}: one no-JavaScript main landmark`);
        assert.equal(await noScriptPage.locator("h1").count(), 1, `${kind}: one no-JavaScript application heading`);
        assert(await noScriptPage.getByRole("heading", { level: 1 }).isVisible());
        assert(await noScriptPage.locator("#service-overview").isVisible());
        assert(await noScriptPage.locator(".service-script-notice").isVisible());
        const title = await noScriptPage.title();
        const description = await noScriptPage.locator('meta[name="description"]').getAttribute("content");
        const canonical = `https://trinitrotorol.com${paths[kind]}`;
        assert(title.includes("モンハンワイルズ"));
        assert(description.length > 50);
        assert.equal(await noScriptPage.locator('link[rel="canonical"]').getAttribute("href"), canonical);
        assert.equal(await noScriptPage.locator('meta[property="og:url"]').getAttribute("content"), canonical);
        assert.equal(await noScriptPage.locator('meta[property="og:title"]').getAttribute("content"), title);
        const hrefs = await noScriptPage.locator("a[href]").evaluateAll((links) => links.map((link) => link.getAttribute("href")));
        for (const href of requiredLinks) assert(hrefs.includes(href), `${kind}: missing crawlable ${href}`);
        assert(hrefs.includes(paths[kind === "checker" ? "sim" : "checker"]));
        await layout(noScriptPage, `${kind}-320-no-javascript`);
        await noScriptPage.locator("#service-overview").scrollIntoViewIfNeeded();
        await noScriptPage.screenshot({ path: resolve(output, `${kind}-320-no-javascript-guide.png`), fullPage: false });
        metadata.push({ kind, title, description, canonical, noJavaScript: true, requiredLinks });
        await noScriptPage.close();
      }
    } finally { await noScriptContext.close(); }
    assert.notEqual(metadata[0].title, metadata[1].title);
    assert.notEqual(metadata[0].description, metadata[1].description);
    return metadata;
  });
  activePage = sim;
  await step("cancel active search and stay responsive", async () => {
    await sim.setViewportSize({ width: 1440, height: 900 });
    await sim.getByLabel("所持品を考慮する", { exact: true }).uncheck();
    await sim.getByRole("button", { name: "優先スキルを追加", exact: true }).click();
    await sim.getByLabel("優先スキル 1 のスキル", { exact: true }).selectOption({ index: 1 });
    const count = await sim.evaluate(() => window.__smokeWorker.requests.length);
    await sim.getByRole("button", { name: "検索する", exact: true }).click();
    await sim.waitForFunction((previous) => window.__smokeWorker.requests.length > previous, count);
    await sim.getByRole("button", { name: "検索を中断", exact: true }).click();
    await sim.getByText(/検索を中断しました/).waitFor();
    assert(await sim.getByRole("button", { name: "検索する", exact: true }).isEnabled());
    assert.equal(await sim.locator(".candidate-card").count(), 0);
    await sim.getByRole("button", { name: "優先スキルを削除", exact: true }).click();
    await layout(sim, "sim-cancelled-1440");
  });
  await step("no outbound APIs, private data, uncaught errors or CSP failures", async () => {
    const unexpected = report.network.filter((request) => /^https?:/.test(request.url) && (!request.url.startsWith(`${origin}/`) || /\/api\//.test(request.url) || !["GET", "HEAD"].includes(request.method) || request.body_bytes || request.contains_private_fields));
    assert.deepEqual(unexpected, []);
    assert.deepEqual(report.page_errors, []);
    assert.deepEqual(report.console_errors, []);
    return { requests: report.network.length, apiRequests: 0, requestBodies: 0 };
  });
  await context.close();
} catch (error) {
  report.failures.push(error?.stack ?? String(error));
  if (activePage && !activePage.isClosed()) {
    await activePage.screenshot({ path: resolve(output, "failure.png"), fullPage: false }).catch(() => {});
    await writeFile(resolve(output, "failure-page.txt"), await activePage.locator("body").innerText().catch(() => "")).catch(() => {});
  }
  process.exitCode = 1;
  console.error(String(error));
} finally {
  report.finished_at = new Date().toISOString();
  report.passed = report.failures.length === 0;
  await writeFile(resolve(output, "report.json"), JSON.stringify(report, null, 2));
  await browser?.close();
  if (server) await new Promise((resolveClose) => server.close(resolveClose));
  console.log(`Report: ${relative(ROOT, output)}/report.json`);
}
