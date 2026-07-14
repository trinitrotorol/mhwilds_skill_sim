import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPOSITORY_ROOT = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../..",
);

async function readRepositoryFile(relativePath) {
  return readFile(resolve(REPOSITORY_ROOT, relativePath), "utf8");
}

function normalizeNewlines(value) {
  return value.replaceAll("\r\n", "\n");
}

function assertKeys(value, expected, label) {
  assert.deepEqual(Object.keys(value), expected, `${label} key order changed`);
}

test("API Wrangler configuration is exact and contains no secrets", async () => {
  const source = await readRepositoryFile("wrangler.api.jsonc");
  const config = JSON.parse(source);

  assertKeys(
    config,
    [
      "name",
      "main",
      "compatibility_date",
      "workers_dev",
      "routes",
      "containers",
      "durable_objects",
      "migrations",
      "ratelimits",
      "observability",
    ],
    "wrangler.api.jsonc",
  );
  assertKeys(config.routes[0], ["pattern", "zone_name"], "API route");
  assertKeys(
    config.containers[0],
    ["class_name", "image", "max_instances", "instance_type"],
    "Container",
  );
  assertKeys(config.durable_objects, ["bindings"], "Durable Objects");
  assertKeys(
    config.durable_objects.bindings[0],
    ["name", "class_name"],
    "Durable Object binding",
  );
  assertKeys(
    config.migrations[0],
    ["tag", "new_sqlite_classes"],
    "Durable Object migration",
  );
  assertKeys(
    config.ratelimits[0],
    ["name", "namespace_id", "simple"],
    "rate limit binding",
  );
  assertKeys(config.ratelimits[0].simple, ["limit", "period"], "rate limit");
  assertKeys(config.observability, ["enabled"], "observability");

  assert.deepEqual(config, {
    name: "mhwilds-skill-sim-api",
    main: "cloudflare/mhwilds-skill-sim-api/src/index.mjs",
    compatibility_date: "2026-07-14",
    workers_dev: false,
    routes: [
      {
        pattern: "trinitrotorol.com/game-guide/mhwilds-skill-sim/api/*",
        zone_name: "trinitrotorol.com",
      },
    ],
    containers: [
      {
        class_name: "SearchApiContainer",
        image: "./Dockerfile.api",
        max_instances: 1,
        instance_type: "basic",
      },
    ],
    durable_objects: {
      bindings: [
        {
          name: "SEARCH_API",
          class_name: "SearchApiContainer",
        },
      ],
    },
    migrations: [
      {
        tag: "v1",
        new_sqlite_classes: ["SearchApiContainer"],
      },
    ],
    ratelimits: [
      {
        name: "SEARCH_RATE_LIMITER",
        namespace_id: "65065",
        simple: {
          limit: 5,
          period: 60,
        },
      },
    ],
    observability: {
      enabled: true,
    },
  });

  assert.equal("assets" in config, false);
  assert.equal("vars" in config, false);
  assert.doesNotMatch(
    source,
    /"(?:account_id|zone_id|api_token|token|secret|vars)"\s*:/i,
  );
});

test("existing frontend Wrangler configuration remains unchanged", async () => {
  const frontendConfig = JSON.parse(
    await readRepositoryFile("wrangler.jsonc"),
  );

  assertKeys(
    frontendConfig,
    [
      "name",
      "main",
      "compatibility_date",
      "workers_dev",
      "build",
      "assets",
    ],
    "wrangler.jsonc",
  );
  assert.deepEqual(frontendConfig, {
    name: "mhwilds-skill-sim",
    main: "cloudflare/mhwilds-skill-sim/src/index.mjs",
    compatibility_date: "2026-07-14",
    workers_dev: true,
    build: {
      command:
        "npm --prefix apps/web ci --no-audit --no-fund && npm --prefix apps/web run build",
    },
    assets: {
      directory: "apps/web/dist",
      binding: "ASSETS",
      run_worker_first: true,
    },
  });
  assert.equal("routes" in frontendConfig, false);
  assert.equal("containers" in frontendConfig, false);
  assert.notEqual(frontendConfig.name, "mhwilds-skill-sim-api");
});

test("Docker image and build context follow the production allowlist", async () => {
  const dockerfile = normalizeNewlines(
    await readRepositoryFile("Dockerfile.api"),
  );
  const dockerignore = normalizeNewlines(
    await readRepositoryFile(".dockerignore"),
  );
  const gitignore = normalizeNewlines(await readRepositoryFile(".gitignore"));

  assert.match(
    dockerfile,
    /^FROM python:3\.12\.13-slim@sha256:c3d81d25b3154142b0b42eb1e61300024426268edeb5b5a26dd7ddf64d9daf28$/m,
  );
  assert.doesNotMatch(dockerfile, /(?:latest|alpine)/i);
  assert.match(dockerfile, /^WORKDIR \/app$/m);
  assert.match(dockerfile, /\bPYTHONDONTWRITEBYTECODE=1\b/);
  assert.match(dockerfile, /\bPYTHONUNBUFFERED=1\b/);

  const copyInstructions = [...dockerfile.matchAll(/^COPY\s+(.+)$/gm)].map(
    (match) => match[1],
  );
  assert.deepEqual(copyInstructions, [
    "pyproject.toml ./",
    "src/ ./src/",
    "scripts/ ./scripts/",
    ".build/production/catalog.json ./catalog.json",
  ]);
  assert.doesNotMatch(dockerfile, /^COPY\s+\.\s/m);
  assert.doesNotMatch(dockerfile, /(?:data\/|fixtures|tests|apps\/web)/i);

  assert.match(
    dockerfile,
    /python -m pip install --no-cache-dir \./,
  );
  assert.doesNotMatch(dockerfile, /(?:--editable|\s-e(?:\s|$))/m);
  assert.match(dockerfile, /groupadd --gid 10001 app/);
  assert.match(dockerfile, /useradd --uid 10001 --gid 10001 --no-create-home/);
  assert.match(dockerfile, /--shell \/usr\/sbin\/nologin app/);
  assert.match(dockerfile, /^USER 10001:10001$/m);
  assert.doesNotMatch(dockerfile, /^USER\s+(?:root|0(?::0)?)$/mi);
  assert.match(dockerfile, /^EXPOSE 8080$/m);
  assert.match(
    dockerfile,
    /HEALTHCHECK .*CMD \["python", "-c", ".*urllib\.request.*127\.0\.0\.1:8080\/health.*"\]/s,
  );
  assert.doesNotMatch(dockerfile, /(?:curl|wget)/i);
  assert.match(
    dockerfile,
    /^ENTRYPOINT \["python", "-m", "scripts\.serve_api", "\/app\/catalog\.json", "--host", "0\.0\.0\.0", "--port", "8080"\]$/m,
  );
  assert.doesNotMatch(
    dockerfile,
    /^(?:ARG|ENV)\s+.*(?:TOKEN|SECRET|ACCOUNT|ZONE|CLOUDFLARE|GITHUB)/gim,
  );

  assert.deepEqual(dockerignore.trimEnd().split("\n"), [
    "**",
    "!pyproject.toml",
    "!Dockerfile.api",
    "!src/",
    "!src/**",
    "!scripts/",
    "!scripts/**",
    "!.build/",
    "!.build/production/",
    "!.build/production/catalog.json",
    "**/__pycache__/",
    "**/*.py[cod]",
  ]);
  assert.match(dockerignore, /^\*\*\/__pycache__\/$/m);
  assert.match(dockerignore, /^\*\*\/\*\.py\[cod\]$/m);
  assert.doesNotMatch(
    dockerignore,
    /^!(?:\.git|tests|apps|data|node_modules|\.github)(?:\/|$)/m,
  );
  assert.equal(gitignore.trimEnd().split("\n").at(-1), ".build/");
  assert.equal(
    gitignore.split("\n").filter((line) => line === ".build/").length,
    1,
  );
});

test("deployment workflow is manual, bounded, and complete", async () => {
  const workflow = normalizeNewlines(
    await readRepositoryFile(".github/workflows/deploy-cloudflare-api.yml"),
  );

  assert.match(workflow, /^on:\n {2}workflow_dispatch:\n(?:\n|$)/m);
  assert.doesNotMatch(
    workflow,
    /^ {2}(?:push|pull_request|pull_request_target|schedule|workflow_call):/m,
  );

  const permissionsStart = workflow.indexOf("permissions:\n");
  const concurrencyStart = workflow.indexOf("\nconcurrency:\n");
  assert.notEqual(permissionsStart, -1);
  assert.ok(concurrencyStart > permissionsStart);
  assert.equal(
    workflow
      .slice(permissionsStart + "permissions:\n".length, concurrencyStart)
      .trim(),
    "contents: read",
  );
  assert.match(workflow, /^concurrency:\n {2}group: \S+\n {2}cancel-in-progress: false$/m);
  assert.match(workflow, /^ {4}runs-on: ubuntu-latest$/m);
  const timeout = workflow.match(/^ {4}timeout-minutes: (\d+)$/m);
  assert.ok(timeout);
  assert.ok(Number(timeout[1]) <= 60);

  const accountSecretLines = workflow
    .split("\n")
    .filter((line) => line.includes("CLOUDFLARE_ACCOUNT_ID:"));
  const tokenSecretLines = workflow
    .split("\n")
    .filter((line) => line.includes("CLOUDFLARE_API_TOKEN:"));
  assert.ok(accountSecretLines.length >= 1);
  assert.ok(tokenSecretLines.length >= 1);
  assert.ok(
    accountSecretLines.every(
      (line) =>
        line.trim() ===
        "CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
    ),
  );
  assert.ok(
    tokenSecretLines.every(
      (line) =>
        line.trim() ===
        "CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}",
    ),
  );

  assert.match(workflow, /actions\/setup-python@/);
  assert.match(workflow, /python-version: "3\.12"/);
  assert.match(workflow, /python -m pip install "\.\[dev\]"/);
  assert.match(workflow, /python -m pytest/);
  assert.match(workflow, /python -m scripts\.sync_mhdb_catalog/);
  assert.match(workflow, /\$RUNNER_TEMP\/mhdb-raw/);
  assert.match(workflow, /\.build\/production\/catalog\.json/);
  assert.match(workflow, /from mhwilds_skill_sim\.catalog\.loader import load_catalog/);
  assert.match(workflow, /catalog\.schema_version != 1/);
  assert.match(workflow, /len\(catalog\.skills\)/);
  assert.match(workflow, /len\(catalog\.equipment\)/);
  assert.match(workflow, /len\(catalog\.decorations\)/);
  assert.match(
    workflow,
    /search_catalog_ranked_build_candidates_with_cp_sat_from_payload/,
  );
  assert.match(workflow, /"requirements": \[\]/);
  assert.match(workflow, /"preferences": \[\]/);
  assert.match(workflow, /"max_results": 1/);

  assert.match(workflow, /npm --prefix cloudflare\/mhwilds-skill-sim-api ci/);
  assert.match(
    workflow,
    /npm --prefix cloudflare\/mhwilds-skill-sim-api run test/,
  );
  assert.match(workflow, /docker version/);
  assert.match(workflow, /docker info/);
  assert.match(workflow, /docker build/);
  assert.match(workflow, /--platform linux\/amd64/);
  assert.match(workflow, /--file Dockerfile\.api/);
  assert.match(workflow, /--memory 1g/);
  assert.match(workflow, /--cpus 0\.25/);
  assert.match(workflow, /127\.0\.0\.1:18080\/health/);
  assert.match(workflow, /127\.0\.0\.1:18080\/catalog\/metadata/);
  assert.match(workflow, /127\.0\.0\.1:18080\/search\/cp-sat\/ranked/);
  assert.match(workflow, /docker exec .* id -u/);
  assert.match(workflow, /\.State\.Health.*\.State\.Health\.Status/);
  assert.match(workflow, /docker logs/);
  assert.match(workflow, /^ {8}if: always\(\)$/m);
  assert.match(workflow, /docker rm --force/);

  assert.match(
    workflow,
    /npx --yes wrangler@4\.110\.0 deploy --config wrangler\.api\.jsonc/,
  );
  assert.match(
    workflow,
    /npx --yes wrangler@4\.110\.0 containers list --config wrangler\.api\.jsonc/,
  );
  assert.match(workflow, /deadline=\$\(\(SECONDS \+ 600\)\)/);
  assert.match(workflow, /health_status.*= "200"/s);
  assert.match(workflow, /\$API_BASE_URL\/health/);
  assert.match(workflow, /\$API_BASE_URL\/catalog\/metadata/);
  assert.match(workflow, /\$API_BASE_URL\/search\/cp-sat\/ranked/);
  assert.match(workflow, /public ranked response must contain one candidate/);
  assert.doesNotMatch(workflow, /actions\/upload-artifact|upload-pages-artifact/i);
  assert.doesNotMatch(workflow, /\bcat\s+\.build\/production\/catalog\.json\b/);
});
