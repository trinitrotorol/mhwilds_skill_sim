# Service deployment and recovery

Both static applications belong to the existing Cloudflare Worker
`mhwilds-skill-sim`. No server inventory storage or paid compute is required.
The user authenticated the Cloudflare dashboard on 2026-10-06. The account's
current plan is Workers Free ($0), with 3,000 build minutes/month and 0 used when
checked. Static requests are free; exceeding free Worker limits fails closed
instead of automatically upgrading. Containers and remote search remain off.

The existing Git connection is `trinitrotorol/mhwilds_skill_sim`, production
branch `master`, root `/`. Build command is blank because Wrangler invokes the
repository build. Production command: `sh scripts/cloudflare-publish.sh deploy`.
Non-production command: `sh scripts/cloudflare-publish.sh versions upload`.
The latter uploads a version without making it the active production deployment.
The CLI is pinned in cloudflare/mhwilds-skill-sim-api/package-lock.json; this
dependency path does not enable or deploy the API Worker or a Container.

Cloudflare Builds has `SKIP_DEPENDENCY_INSTALL=1` enabled (verified 2026-10-06),
so automatic package installation cannot run before the repository-local
toolchain and cache wrappers. See [Skip dependency install](https://developers.cloudflare.com/workers/ci-cd/builds/build-image/#skip-dependency-install).
Both release entrypoints prefer `/usr/bin:/bin` before bootstrap, selecting the
existing distro Python instead of inherited virtualenvs or HOME-managed language
shims. Each wrapper still selects its own repository-local Node/Python; no OS or
global packages are installed. Cloudflare's [build environment](https://developers.cloudflare.com/workers/ci-cd/builds/build-image/#build-environment)
is Ubuntu 24.04.

The canonical service is `https://mhwilds.trinitrotorol.com`:

- `/` redirects to `/skill-sim/`.
- `/skill-sim/` is the simulator and `/inventory/` is the inventory checker.
- `/robots.txt`, `/sitemap.xml` and `/ads.txt` are static files for this host.

Wrangler owns the custom domain and preserves the old root-domain routes:

- `trinitrotorol.com/game-guide/mhwilds-skill-sim*`
- `trinitrotorol.com/game-guide/mhwilds-skill-sim/*`
- `trinitrotorol.com/game-guide/mhwilds-inventory-checker*`
- `trinitrotorol.com/game-guide/mhwilds-inventory-checker/*`

The first pattern in each pair includes queries on slashless URLs; the Worker
still rejects unrelated and lookalike application paths. Do not broaden these
routes to all of `game-guide`. Only the page redirects and API endpoints use
`run_worker_first`; real files remain assets-first. Old public page URLs return
301 redirects with their queries preserved. The existing workers.dev origin also
serves both application paths. The release
manifest reports the exact parent/checker SHAs, catalog revision, input hashes,
timestamp and enabled features. Never deploy an artifact marked `fixture: true`.

Inventory is origin-scoped browser storage. The build therefore keeps both old
applications, their catalogs, and their assets available. Opening an old page
with `?legacy=1` serves its original-origin app with `noindex` and a canonical
link to the new site. Old app navigation retains this query. Both origins show
instructions to download JSON from the old checker and import it on the new
checker using its existing merge/replace confirmation. There is no automatic
transfer, server storage, or deletion of saved data. Keep this export path after
the move; redirects must never prevent users from recovering their local data.

`build_service` builds each app twice from the same pinned child SHA. The parent
uses `VITE_BASE_PATH`, while the child additionally uses `VITE_SIM_BASE_PATH` for
catalog and simulator links. Omitted variables keep the old build defaults.
Catalog bytes and release provenance are identical for both origins. Never
rewrite generated JavaScript bundles to change origins or paths. Root-domain
guides, privacy and contact links are absolute; no ads or analytics scripts are
added by this migration.

The zone Configuration Rule `MHWILDS apps: disable RUM` excludes the entire
`mhwilds.trinitrotorol.com` hostname as well as both legacy tool paths on
`trinitrotorol.com` from automatic Cloudflare Web Analytics injection. The rule
was verified active on 2026-10-08 with no injected analytics in live subdomain
HTML. Keep this host exclusion when changing routes; the strict application CSP
is not a substitute for disabling injection. Other root-domain pages retain
their existing analytics configuration.

Smoke checks default to new paths. Run `sh scripts/nodew
apps/web/scripts/service-smoke.mjs --base-url https://mhwilds.trinitrotorol.com`
after release. Use `--base-url https://trinitrotorol.com` for old-origin checks;
it adds `?legacy=1` to page visits only. Locally, use `--legacy` to test the old
build. The guide at `https://trinitrotorol.com/game-guide/mhwilds-guide/#migration`
explains the user-facing JSON migration.

Release order: verify and push child; merge checked child PR; pin its exact SHA in
parent; run make test, make lint, make data-check and all web/Worker checks; build
both apps from tracked clean source; run fresh-browser functional/a11y smoke;
verify CI and the uploaded version; merge parent; confirm the active version and
both public URLs, including static catalogs and fallback-free browser search.

For rollback, restore the previous known-good Worker version from Deployments.
That restores both application assets and catalogs together. Inventory remains
in users' browsers and must never be reset during a rollback. Preserve exported
JSON and warn about catalog drift; exclude obsolete entries only with explicit
user acknowledgement. Use a new normal Git revert if source rollback is needed;
never rewrite published history. Do not enable REMOTE_SEARCH_ENABLED until a
separately documented zero-additional-cost guard covers the entire backend path.

References: [Build limits](https://developers.cloudflare.com/workers/ci-cd/builds/limits-and-pricing/),
[version uploads](https://developers.cloudflare.com/workers/ci-cd/builds/),
[static asset billing](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/).
