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

The existing routes before this release are:

- `trinitrotorol.com/game-guide/mhwilds-skill-sim`
- `trinitrotorol.com/game-guide/mhwilds-skill-sim/*`

Add only the corresponding two `mhwilds-inventory-checker` routes after verifying
the combined version. Do not replace them with a broader game-guide route.
The existing workers.dev origin also serves both application paths. The release
manifest reports the exact parent/checker SHAs, catalog revision, input hashes,
timestamp and enabled features. Never deploy an artifact marked `fixture: true`.

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
