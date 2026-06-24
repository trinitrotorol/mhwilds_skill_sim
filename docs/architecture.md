# Project Architecture

## Purpose

このプロジェクトは、Monster Hunter Wilds のスキルシミュレータです。

今後の実装では、正確なビルド検証と検索ロジックを UI から分離して実装します。React などの表示層には検索ロジックを書かず、ビルドの正当性検証と候補探索を独立した層として扱います。

## Planned Top-Level Layout

将来的なトップレベル構成は次の責務で分けます。現時点では、これらのディレクトリは作成しません。

```text
src/mhwilds_skill_sim/
├─ domain/       純粋な型とゲームルール
├─ catalog/      正規化JSONの読み込み
├─ validation/   ビルドの正当性検証
├─ solver/       全探索と将来のCP-SAT検索
└─ api/          将来のHTTP境界

data/
├─ fixtures/     テスト用極小データ
├─ raw/          外部取得データのスナップショット
└─ normalized/   アプリが利用する正規化データ

apps/
└─ web/          将来のReactアプリ
```

`domain` は純粋な型とゲームルールを定義します。外部フレームワークや入出力境界には依存させません。

`catalog` は外部データ形式をアプリ内で利用する正規化 JSON 形式へ変換し、その読み込みを担当します。

`validation` は装備、スロット、装飾品、スキルなどを組み合わせたビルドの正当性検証を担当します。

`solver` は候補生成と最適化を担当します。初期は小規模な全探索を想定し、将来的に CP-SAT 検索を追加します。

`api` は将来の HTTP 入出力の境界だけを担当します。検索や検証の中核ロジックは下位層へ委譲します。

`web` は将来の React アプリとして、表示と操作だけを担当します。

## Dependency Direction

依存方向は次の一方向に限定します。

```text
domain
  ↑
catalog / validation
  ↑
solver
  ↑
api
  ↑
web
```

依存ルールは次のとおりです。

- `domain` 層は他の層を import しない。
- 上位層から下位層への依存だけを許可する。
- 循環依存を作らない。

## Layer Rules

- React 内に検索ロジックを書かない。
- solver が返す `BuildResult` は `validate_build` を通す。
- `domain` 層に FastAPI、Pydantic、OR-Tools、React 関連、外部 API クライアントを入れない。
- `catalog` 層は外部データ形式をアプリ内の正規化形式へ変換する。
- `validation` 層はビルドの正当性検証を担当する。
- `solver` 層は候補生成と最適化を担当する。
- `api` 層は HTTP 入出力の境界だけを担当する。
- `web` 層は表示と操作だけを担当する。

## Development Order

今後の実装は次の順序で進めます。

1. domain の型
2. slot 適合判定
3. decoration 定義
4. equipment 定義
5. 極小 fixture データ
6. catalog 読み込み
7. スキル集計
8. decoration 配置検証
9. `validate_build`
10. 小規模全探索 solver
11. CP-SAT solver
12. API
13. React UI

## Current Non-Goals

現時点では、次のものは実装しません。

- React
- FastAPI
- OR-Tools
- 外部 API 取り込み
- 実ゲームデータ
- ダメージ計算
- Docker
- CI
