# Service verification record

Recorded on 2026-10-06 in the isolated service checkout. This records observed
checks, not a claim that the release has already been published.

## Source and build identity

- Checker submodule: `c841bfb5c2f561cf8532aebc64dbd2611d3ef716`.
  Its [CI run](https://github.com/trinitrotorol/mhwilds_inventory_checker/actions/runs/37425357917)
  passed; PR #2 merged as `bd9e682a1312a0fcfaa266e1d9a14541e5291dbc`.
  The earlier checker integration also passed
  [CI](https://github.com/trinitrotorol/mhwilds_inventory_checker/actions/runs/37423995380)
  before PR #1 merged as `d96ee7376d81e939161862bdeb459e476d48da18`.
- The local combined build uses real data (`fixture: false`), with catalog
  revision `4f42c616622c8b8606e043326e0bfd0905017b698b7aa6c5a862a58a477bad1c`:
  179 skills, 361 decorations, 183 fixed charms and 100 appraisal patterns.
- The local build's parent base is `0a633e221053d03a3d7faa2921e75cff6813bc24`
  with uncommitted changes. It is a validation artifact, not the final clean
  release artifact. The parent commit, parent CI, clean rebuild and deployment
  remain pending. Release manifests record both source SHAs and dirty flags.

## Checks

| Check | Observed result |
| --- | --- |
| Final standard `make test` | 4,316 tests passed in 238.54 seconds; collected from `tests` only |
| Final `make lint` | Passed; 154 Python files formatted correctly |
| Final `make data-check` | Passed; 8 fixture JSON files |
| Parent full web suite before the final remote compatibility fixes | 26 files / 289 tests passed |
| Final remote validation and shared solver parity regressions | 3 files / 41 tests passed |
| Parent TypeScript and ESLint after those fixes | Passed |
| Frontend Worker suite | 34 tests passed |
| Dedicated API Worker and deployment configuration suite | 55 tests passed |
| Shared Python inventory ranking oracle after response fixtures changed | 5 tests passed |
| Fresh-browser real-asset functional/accessibility smoke | Pending |
| Public deployment and both production URL checks | Pending |

The final Python command is plain `make test`; the Makefile passes
`--capture=sys` so WSL does not require unsupported file-descriptor capture in
the repository-local temporary directory. Its complete local log is
`.build/verification/make-test-final.log`. The web targeted run was:

```sh
sh scripts/npmw --prefix apps/web test -- --environment node \
  src/browser-solver/validation.test.ts \
  src/browser-solver/inventory-parity.test.ts src/service/search.test.ts
sh scripts/npmw --prefix apps/web run typecheck
sh scripts/npmw --prefix apps/web run lint
```

The 41 targeted cases are not an additional full-suite count. They include real
Python API responses for five inventory cases and a theoretical charm request,
finite decoration quantities, owned charm identities, ranking, independent
recipe reconstruction, legal placement permutations and skill totals in a
different order. Altered values, duplicate skills/occupied slots, forged charm
recipes and invalid inventory rankings remain rejected. The checker race fix
tests real storage events while another tab has an uncommitted quantity edit.

## Source facts and limits

Appraisal facts come from the original Dtlnor/Aki spreadsheet, joined to MHDB
stable skill IDs. The observed snapshot has 10 skill groups and 100 expanded
patterns, representing 2,076,040 distinct-base-skill choices before
cross-pattern deduplication. [The source record](../appraisal-sheet-source.md)
documents attribution, reproducible acquisition and the duplicate-skill rule.
The release manifest records source URLs and SHA-256 hashes. No third-party
application code, prose, styles or images are redistributed; public availability
is not asserted to grant a blanket redistribution license.

Production browser catalogs omit the huge theoretical charm list. The worker
creates bounded, query-specific representatives and returns up to 20 distinct
equipment results. Time/state limits are explicit; an interrupted or bounded
search does not claim a proved exhaustive ranking. Every returned candidate is
independently validated, including inventory quantities and slot kinds. Shared
fixtures check full equipment ranks against Python, rather than score alone.

The legacy unrestricted Python search still materializes theoretical charm
candidates. Its performance on the complete current rule catalog is not
certified. Remote search remains disabled in both release configuration and
the dedicated API's default-closed server gate; no Container was deployed.
Local Node timings are not mobile-browser certification.

The [environment audit](environment-audit.md) records the disclosed earlier
package-manager workflow deviation and the replacement repository-local browser
runtime procedure. Browser smoke evidence belongs in `.build/service-smoke`;
production acceptance still requires the steps in
[deployment and recovery](deployment.md).
