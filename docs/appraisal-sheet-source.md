# Appraisal charm rule source

The checker and both search engines use the same normalized rule catalog.
Rules are generated from numerical game facts, not independently entered in
the UI or copied from another application's implementation.

## Attribution and reproduction

The primary public source is the community
[[MHWilds] Amulet Tables spreadsheet](https://docs.google.com/spreadsheets/d/1fpkamu1VzEpX8dZqecygW1GflKyvdY2975Y0d9SUt04/edit).
It credits **Dtlnor** for mining and **Aki at Wiggler** for grouping. The
[Japanese reference shared by あんかー](https://x.com/the_anchor7/status/1955990911713993025)
led back to this original source. The service uses the original English skill
names only as a transient exact join to MHDB's `gameId`; canonical persistent
IDs remain `mhdb:skill:<gameId>`. The localized names come from the existing
normalized MHDB catalog.

`scripts/sync_appraisal_sheet.py` downloads the two public CSV tabs (pattern
gid `0`, skill-group gid `1054141820`) and the MHDB English skill list. It
extracts the numerical group membership, skill levels, rarity, slot kind/level
and group combinations. It rejects ambiguous names, unknown names, duplicate
rows, changed headers, malformed slots and any level that the canonical
catalog does not support. It does not guess spelling aliases.

No spreadsheet formulas, source code, narrative text, styling or images are
included in the published catalog. No explicit redistribution license for
the source spreadsheet or other referenced apps is asserted. Public access
is not treated as a blanket code or document reuse license. Downloaded source
files and generated catalogs stay in ignored cache/build directories.

From the parent repository, with the repository-local environment ready:

```sh
sh scripts/pyw -m scripts.sync_appraisal_sheet \
  .build/catalog.json .cache/appraisal-source .build/appraisal-rules.json
sh scripts/pyw -m scripts.merge_appraisal_rules \
  .build/catalog.json .build/appraisal-rules.json .build/catalog-with-appraisal.json
```

For an offline reproduction, supply all three options to the first command:
`--patterns-csv`, `--groups-csv`, `--english-skills-json`. Each acquisition
writes source URLs, retrieval timestamp, SHA-256 hashes, catalog hash and
generated rules hash to `metadata.json`. Parsing and validation complete
before the existing valid generated rules are replaced. All published release
records should retain or refer to this metadata.

The actual source checked on 2026-10-06 yielded 10 groups and 100 expanded
rarity/slot patterns. Group option counts were 37, 43, 40, 21, 37, 37, 34,
15, 15 and 9. That represents 2,134,102 raw group-choice combinations, or
2,076,040 after rejecting duplicate skill choices, before cross-pattern
deduplication. These observations identify that source snapshot and are not
hardcoded as future game rules. The browser must not pre-generate this huge
cartesian product.

## Distinct skill choices

Each listed group contributes one **distinct** skill choice. Repeated group
IDs are permitted in a pattern, but the same skill cannot be selected twice;
two level-1 rolls must not be collapsed into a level-2 skill.

This corrects the earlier inherited aggregation assumption. Primary
corroboration is the [Charm Editor author's pinned statement](https://www.nexusmods.com/monsterhunterwilds/mods/3067?tab=posts)
and the [Talisman Explorer author's implementation](https://github.com/aevanko/talisman-explorer/blob/main/index.html),
which rejects repeated base skill identities before emitting a charm. These
implementations were inspected for factual verification only; their code and
assets were not incorporated. Regression tests cover the rule in the checker
validator and both solver paths.
