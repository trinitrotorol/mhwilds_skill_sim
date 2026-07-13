# CP-SAT 検索性能プローブ

## 目的

`scripts.profile_cp_sat_search` は、正規化済み Catalog と検索 request を同じ
プロセスで読み込み、CP-SAT 複数候補検索の測定結果を JSON で出力する
read-only のオフラインツールです。HTTP やネットワークの往復時間を含めず、
Catalog の規模、検索時間、探索状態を同じ条件で比較できます。

このツールは性能改善そのものや、絶対的な性能合否基準を定義するものでは
ありません。

## request JSON

request は既存の `POST /search/cp-sat` と同じ形式です。

```json
{
  "requirements": [
    {"skill_id": "skill:attack-boost", "min_level": 1}
  ],
  "max_results": 3,
  "weapon_kind": null
}
```

- `requirements` は必要スキルの `skill_id` と最小レベルです。同じ
  `skill_id` を重複して指定できません。
- `max_results` は返す候補数の上限で、0 以上の整数です。
- `weapon_kind` は省略でき、武器種の文字列または `null` を指定します。
- 検索予算は request に追加せず、CLI の `--timeout-seconds` で指定します。

## tiny fixture での実行

次は POSIX shell で一時 request を作り、リポジトリの tiny fixture を測る例です。
tiny fixture の武器には武器種が設定されていないため、この例では
`weapon_kind` を省略します。

```bash
PROFILE_DIR="$(mktemp -d)"
cat > "$PROFILE_DIR/request.json" <<'JSON'
{
  "requirements": [
    {"skill_id": "skill:attack-boost", "min_level": 1}
  ],
  "max_results": 3
}
JSON

python -m scripts.profile_cp_sat_search \
  data/fixtures/tiny_catalog.json \
  "$PROFILE_DIR/request.json" \
  --timeout-seconds 10 \
  --pretty
echo "$?"
```

`--pretty` を省略すると、同じ report を内部改行のない1行の compact JSON
（末尾改行あり）として出力します。

## 一時的な実 Catalog での実行

外部ネットワークを利用できる場合は、既存の `scripts.sync_mhdb_catalog` で
現行 MHDB snapshot と正規化 Catalog をリポジトリ外の一時ディレクトリへ
生成できます。同期処理の timeout と probe の検索 timeout は別の予算です。

```bash
PROFILE_DIR="$(mktemp -d)"
cat > "$PROFILE_DIR/request.json" <<'JSON'
{
  "requirements": [],
  "max_results": 10
}
JSON

python -m scripts.sync_mhdb_catalog \
  "$PROFILE_DIR/raw" \
  "$PROFILE_DIR/catalog.json" \
  --locale ja \
  --timeout-seconds 30

python -m scripts.profile_cp_sat_search \
  "$PROFILE_DIR/catalog.json" \
  "$PROFILE_DIR/request.json" \
  --timeout-seconds 10 \
  --pretty
```

実際の要件を測る場合は、生成した Catalog に含まれる永続 `skill_id` を request
へ指定します。表示名を ID の代わりに使用しません。

## report

標準出力には次の4セクションをこの順序で含む JSON document が1個出ます。

- `catalog`
  - `schema_version`: 正規化 Catalog の schema version。
  - `equipment_count`: Catalog に格納された装備定義数。
  - `decoration_count`: 装飾品定義数。
  - `skill_count`: スキル定義数。
  - `appraisal_charm_skill_group_count`: 鑑定護石スキルグループ定義数。
  - `appraisal_charm_pattern_count`: 鑑定護石パターン定義数。
- `request`
  - decoder で検証した `requirements`、`max_results`、`weapon_kind` と、
    float に正規化した `timeout_seconds`。
- `timing_seconds`
  - `catalog_load`: Catalog loader の実行時間。
  - `search`: CP-SAT solver 呼び出しの実行時間。
  - `total`: Catalog load、request の読み込みと decode、solver search の合計時間。
- `result`
  - `candidate_count`: solver が返した候補数。候補総数ではなく、候補本文も
    report には含みません。
  - `exhausted`: 条件を満たす追加候補がないことを証明できたか。
  - `timed_out`: 期限までに探索を完了できなかったか。

各 timing は秒単位で小数点以下6桁へ丸めます。`total` には同期処理、HTTP、
network、候補本文の serialization、標準出力への書き込み時間を含みません。
Catalog load と request decode を含むため、`total` は検索 timeout より長くなる
場合があります。

`exhausted` と `timed_out` が同時に `true` になることはありません。両方が
`false` の場合は、通常は `max_results` に到達して停止しており、全候補を
列挙済みとは限りません。timeout 時も途中までに得た候補数を含む report を
標準出力へ出します。

## exit code

- `0`: `timed_out` が `false`。
- `2`: `timed_out` が `true`。report は通常どおり標準出力へ出ます。

## 比較条件と生成物

性能を比較するときは、同じ hardware、同じ Catalog snapshot、同じ request、
同じ `--timeout-seconds` を使用してください。実行ごとの時間差だけで絶対的な
性能合否を判断しないでください。

同期で生成した raw snapshot、正規化 Catalog、request、保存した profile 出力は
一時生成物です。このツールはそれらを自動でリポジトリへ commit しません。
一時生成物を手動で commit することも避けてください。
