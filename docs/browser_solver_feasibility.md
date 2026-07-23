# Browser ranked solver feasibility

## 1. Summary decision

判定は **CONDITIONAL**。

compact Catalog、TypeScript exact top-1 solver、Web Worker、Python CP-SAT
oracle の correctness は tiny / live とも一致した。live の全 acceptance case は
Node と実ブラウザで完了し、candidate validation failure、parity mismatch、
timeout、非決定的結果は 0 件だった。

一方、mobile 測定は 390 × 844 の viewport-only であり、CDP CPU 4x
throttling または実端末測定ではない。ブラウザの memory API も利用できず、
desktop の `mixed-ranked` には full-page 再実行間の変動があった。このため
GO の必要条件をすべて満たしたとは扱わない。

## 2. Scope

この spike で実装した範囲は次のとおり。

- 正規化 Catalog から local benchmark 用 compact browser Catalog を決定的に生成
- Python の既存 ranked CP-SAT solver で top-1 oracle を生成
- TypeScript で hard requirements、preferences、weapon filter、set/group skill、
  compound decoration を扱う exact top-1 search を実装
- pure solver を Node で、同じ solver を dedicated Web Worker で実行
- tiny Catalog と live MHDB Catalog で parity、validation、性能を測定
- local development 専用 benchmark page と exact 2 URL の Vite dev middleware を追加

公開 React UI、既存 API client、Cloud Run、Cloudflare routing、public route、
自動 fallback は変更していない。production build の input に benchmark page を
追加していない。

## 3. Commit / Catalog hash

- 基準 HEAD: `cf067ee4cdd0448b07b2dc2fda2c24bbb216a1e9`
- 実装 commit message: `solver: evaluate browser ranked search`
- 実装 commit SHA は文書自身を commit へ含めるため事前記載せず、push 後の
  completion report で local / origin / remote の一致を報告する
- live source Catalog SHA-256:
  `1f66350e95e35969ffa81e4699ad3e278002a1613b54c5285e17b2ce7a1e0145`
- compact Catalog file SHA-256:
  `381cbece967b58f781b3db8660fd8c447dadb801e687a7573c21e26f2b7123c0`
- tiny source Catalog SHA-256:
  `4710e639a3d4e4dd96a518ba0955aefcc1678a6cf81c1fb728bffdacf00f63f5`

## 4. Candidate expansion counts

live source equipment 2,085 件から 37,701 variants を生成した。limit 500,000
に対する preflight estimate を full expansion 前に検査している。

| part | variants |
| --- | ---: |
| weapon | 36,804 |
| head | 164 |
| chest | 140 |
| arms | 135 |
| waist | 137 |
| legs | 138 |
| charm | 183 |
| total | 37,701 |

generated appraisal charm は live Catalog では 0 件。skills は 179
（armor 71 / weapon 66 / set 25 / group 17）、decorations は 361 件だった。

compact JSON の top-level insertion order は
`format_version`、`source_catalog`、`skills`、`equipment_by_part`、
`decorations`。skill と decoration は数値 index 参照、equipment variant ID は
part-major で global contiguous、slot は kind/level、set/group は
primary/additional membership と必要部位数を保持する。display name は永続 ID
として使用しない。

## 5. Raw / gzip size

| artifact | raw bytes | gzip bytes |
| --- | ---: | ---: |
| live normalized source Catalog | 1,440,348 | 未測定 |
| live compact browser Catalog | 11,432,578 | 408,045 |
| tiny compact browser Catalog | 6,439 | 935 |

gzip は `mtime=0` の決定的な測定。live compact は GO 目安 8 MiB 以下。

## 6. Tiny parity

`data/fixtures/tiny_catalog.json` から CLI で fixture を再生成した。

- source equipment 9、generated appraisal charm 8、expanded 17
- part counts: weapon 1 / head 2 / chest 1 / arms 1 / waist 1 / legs 1 /
  charm 10
- skills 6、decorations 5
- Python oracle: 7/7 optimal、timeout 0
- Node TypeScript: 7/7 parity、deterministic 7/7
- Python report validator: valid candidate 7、parity failure 0
- `weapon-filter` は tiny Catalog に対象 kind がないため oracle workload から省略

## 7. Live workload

timeout は Python 30 秒/case、Node と browser は 10,000 ms/search。
Node と browser は warm-up 1 回を測定外とし、各 case を 3 回測定した。

| case | workload |
| --- | --- |
| empty | requirement / preference なし |
| normal-required | normal skill level 1 を必須 |
| normal-preferred | normal skill level 1 を選好 |
| mixed-ranked | normal skill 1 必須 + 2 skills を level 1 まで選好 |
| series-required | series skill level 1 を必須 |
| group-preferred | group skill level 1 を選好 |
| weapon-filter | `weapon_kind=bow` |
| impossible-stress | normal skill level 4 を必須とする stress case |

`impossible-stress` は現行 ranking semantics では skill definition の
`max_level` へ集計値を cap しないため optimal になった。Task 066 の仕様どおり
この意味論は変更していない。

## 8. Python CP-SAT timings

既存 ranked CP-SAT solver を直接呼び、8/8 optimal、timeout 0、合計
46.109060 秒だった。

| case | elapsed seconds | status | score | decorations |
| --- | ---: | --- | ---: | ---: |
| empty | 1.628347 | optimal | 0 | 0 |
| normal-required | 4.635683 | optimal | 0 | 0 |
| normal-preferred | 5.880251 | optimal | 1 | 0 |
| mixed-ranked | 12.208744 | optimal | 2 | 1 |
| series-required | 8.616514 | optimal | 0 | 0 |
| group-preferred | 7.928718 | optimal | 1 | 0 |
| weapon-filter | 0.491948 | optimal | 0 | 0 |
| impossible-stress | 4.718855 | optimal | 0 | 0 |

## 9. Node TypeScript timings

Node v24.14.0、timeout 10,000 ms、3 repeats。全件 optimal、parity true、
deterministic true、timeout 0。

| case | min / median / max ms | visited | pruned | complete selections |
| --- | ---: | ---: | ---: | ---: |
| empty | 7.425 / 7.647 / 12.514 | 8 | 0 | 1 |
| normal-required | 18.536 / 18.627 / 22.431 | 9 | 0 | 2 |
| normal-preferred | 18.032 / 18.714 / 20.056 | 9 | 0 | 2 |
| mixed-ranked | 309.848 / 327.023 / 332.416 | 80,470 | 52,668 | 10,710 |
| series-required | 6.395 / 7.028 / 10.474 | 10 | 2 | 1 |
| group-preferred | 7.652 / 7.906 / 9.624 | 16 | 4 | 2 |
| weapon-filter | 1.542 / 1.599 / 3.538 | 8 | 0 | 1 |
| impossible-stress | 20.207 / 20.794 / 21.070 | 209 | 16 | 144 |

## 10. Actual browser timings

Codex in-app browser の Chrome 150.0.0.0 で live Catalog を dedicated Web
Worker に読み込み、各 case を 3 回測定した。次は最終 desktop 確認 run。

| case | min / median / max ms | status | parity | deterministic |
| --- | ---: | --- | --- | --- |
| empty | 38.1 / 42.6 / 156.6 | optimal | true | true |
| normal-required | 76.1 / 93.0 / 99.6 | optimal | true | true |
| normal-preferred | 73.5 / 90.8 / 107.7 | optimal | true | true |
| mixed-ranked | 1,955.9 / 2,272.4 / 3,002.3 | optimal | true | true |
| series-required | 74.9 / 80.3 / 85.6 | optimal | true | true |
| group-preferred | 68.2 / 69.0 / 73.5 | optimal | true | true |
| weapon-filter | 8.0 / 23.5 / 28.9 | optimal | true | true |
| impossible-stress | 129.0 / 141.1 / 182.4 | optimal | true | true |

別の complete desktop run では `mixed-ranked` が
3,869.2 / 4,142.9 / 5,108.1 ms だった。いずれも timeout/max 10 秒以内だが、
full-page run 間の性能変動として扱う。

## 11. Desktop / mobile conditions

host:

- Windows 11 Home 10.0.26200, 64-bit
- Intel 13th Gen Core i5-1334U、10 cores / 12 logical processors
- memory 16,849,256,448 bytes
- browser user agent:
  `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36`

desktop:

- viewport 1440 × 900、device pixel ratio 約 1.0
- CPU throttling なし
- Catalog fetch 11,432,578 bytes / 185.0 ms
- JSON parse 152.7 ms
- Worker init 1,020.7 ms

mobile 相当:

- viewport 390 × 844、device pixel ratio 約 1.0
- viewport-only。CDP CPU 4x throttling は利用できず、実端末性能とは表現しない
- Catalog fetch 11,432,578 bytes / 101.3 ms
- JSON parse 220.1 ms
- Worker init 799.6 ms

| case | mobile viewport-only min / median / max ms |
| --- | ---: |
| empty | 20.5 / 31.4 / 72.7 |
| normal-required | 45.9 / 71.3 / 103.1 |
| normal-preferred | 38.4 / 63.7 / 85.5 |
| mixed-ranked | 1,344.3 / 1,940.4 / 2,405.7 |
| series-required | 27.7 / 35.3 / 35.3 |
| group-preferred | 22.4 / 27.6 / 35.0 |
| weapon-filter | 5.5 / 14.9 / 20.0 |
| impossible-stress | 55.3 / 73.6 / 81.7 |

## 12. Correctness validation

- tiny: completed parity 7/7、valid candidates 7/7
- live Node: completed parity 8/8、valid candidates 8/8
- live browser: completed parity 8/8
- parity mismatch 0、candidate validation failure 0、non-deterministic case 0
- solver が返す candidate は独立 TypeScript validator を通す
- Node report はさらに Python validator で既存 Catalog/domain validation と照合
- weapon/armor decoration の kind と level、slot 重複、full skill levels、
  preference score、decoration count、weapon filter、variant ID を再検証
- set/group skill は primary/additional membership の選択部位数と
  `required_pieces` から再計算

## 13. Timeouts / cancellations

Python、Node、desktop browser、mobile viewport-only の timeout は 0。

実ブラウザで `mixed-ranked` が 44,315 nodes を訪問中に Cancel を実行し、
status `Cancelled`、完了済み 3 rows、report 未生成へ遷移した。pure solver は固定
interval で timeout/cancel を確認する。同期 search 中の Worker は raw cancel
message を処理できないため、実効 cancel は client が Worker を
terminate して同じ Catalog で再生成する。unit test で cancel 後の再検索も確認した。

## 14. Memory / Worker observations

- dedicated Web Worker のため、測定中も main page の status 更新が継続した
- worker init は desktop 1,020.7 ms、mobile viewport-only 799.6 ms で 3 秒以内
- console error 0、tab crash なし
- benchmark page の horizontal overflow は両 viewport とも false
- CPU model は page API からは `unknown`。host 情報は OS から別途取得
- browser memory measurement API は利用できず `unavailable`
- Cancel 操作は active search を停止できた

## 15. Limitations

- exact branch-and-bound の worst case は指数的で、近似 beam search ではない
- live の `mixed-ranked` は他 case より大きく、desktop full-page run 間の変動もある
- mobile は viewport-only であり、4x throttle/実端末の結論ではない
- browser memory peak は未測定
- raw Worker cancel message は同期探索を割り込めず、client terminate/restart に依存
- benchmark page と dev middleware は local-only。公開 UI からは import しない
- Cloud Run / Cloudflare / automatic fallback の比較・切替はこの Task の範囲外

## 16. GO / CONDITIONAL / NO-GO rationale

NO-GO 条件には該当しない。parity mismatch、invalid candidate、non-determinism、
tab crash、memory exhaustion はなく、gzip 408,045 bytes、expanded 37,701 で
上限を十分下回る。最終 desktop run は acceptance median 3 秒以下、max 10 秒以下、
worker init 3 秒以下を満たした。

ただし GO には mobile 4x throttle または実端末測定が必要で、今回は
viewport-only だった。memory も測定不能で、desktop run 間の性能変動がある。
したがって結論は **CONDITIONAL**。

## 17. Next recommended single task

同一 live Catalog/workload を、CDP CPU 4x throttling と browser memory measurement
が利用できる Chrome、または代表的な実 mobile 端末で再測定し、
`mixed-ranked` の run 間変動と mobile/memory の GO 条件だけを判定する。
公開 UI 統合や fallback 実装は、その判定後の別 Task とする。

## 18. Generated files

次は測定生成物であり commit しない。

- `.build/browser-solver/raw/`
- `.build/browser-solver/live-catalog.json`
- `.build/browser-solver/browser-catalog.json`
- `.build/browser-solver/oracle.json`
- `.build/browser-solver/node-report.json`
- `.build/browser-solver/tiny-browser-catalog.json`
- `.build/browser-solver/tiny-oracle.json`
- `.build/browser-solver/tiny-browser-report.json`
- `apps/web/dist/`

既存 `.gitignore` が `.build/` 全体を ignore しているため、重複する
`.build/browser-solver/` 行は追加しなかった。screenshot は commit していない。
