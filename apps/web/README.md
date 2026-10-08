# MHWILDS スキルシミュレータ Web

React + TypeScript + Vite製のWebクライアントです。本番の装備検索は
ブラウザ内のWeb Workerで動作し、remote検索APIは初期無効です。

## ローカル開発

リポジトリrootで、Catalog JSONを指定してFastAPI backendを起動します。

```console
python -m scripts.serve_api path/to/catalog.json
```

別のterminalで依存packageをlockfileどおりにinstallし、Vite開発serverを起動します。

```console
npm --prefix apps/web ci
npm --prefix apps/web run dev
```

Viteの既定baseは旧URLを維持しています。`VITE_BASE_PATH=/skill-sim/`を指定すると
新しい公開先のbaseで起動・buildします。Viteは選択したbaseのapplication API prefix
`/game-guide/mhwilds-skill-sim/api`の既知のendpointだけを
`http://127.0.0.1:8000`へproxyし、backendのpathへrewriteします。browserからはproductionと同じsame-origin URLを使用するため、CORS設定は不要です。

## Browser solver feasibility benchmark

Task 066のbenchmarkはlocal development専用です。repository rootの
`.build/browser-solver/`へ、commit対象外の次の生成物を用意します。

```text
.build/browser-solver/browser-catalog.json
.build/browser-solver/oracle.json
```

Vite開発serverを起動し、`/solver-benchmark.html`を直接開きます。このpageは
compact Catalogとoracleをlocal-only middlewareから読み、exact top-1 solverを
Web Worker内で実行します。caseごとのmin / median / max、探索counter、CP-SAT
oracleとのparityを表示し、完了reportを
`window.__MHWILDS_BROWSER_SOLVER_BENCHMARK__`へ置きます。

Node benchmarkはrepository rootから実行します。

```console
npm --prefix apps/web run benchmark:browser-solver -- \
  --catalog .build/browser-solver/browser-catalog.json \
  --oracle .build/browser-solver/oracle.json \
  --output .build/browser-solver/node-report.json \
  --timeout-ms 10000 \
  --repeats 3
```

`solver-benchmark.html`、compact Catalog、oracle、benchmark reportはproduction
buildへ含めず、公開navigationやrouteにも追加しません。

Task 068 の自動 certification は Playwright Chromium と CDP を使用します。
Chromium だけをインストールし、repository root の ignored `.build` へ入力と
出力を置いて実行します。

```console
npm --prefix apps/web run install:browser-solver-chromium
npm --prefix apps/web run certify:browser-solver -- \
  --catalog ../../.build/browser-solver/browser-catalog.json \
  --oracle ../../.build/browser-solver/oracle.json \
  --output ../../.build/browser-solver/browser-certification-v2.json \
  --screenshot-directory ../../.build/browser-solver/certification-v2-screenshots \
  --repeats 5 \
  --timeout-ms 20000
```

この runner は local benchmark document だけを cross-origin isolated にし、
desktop 1x、低速 mobile 相当 profile の requested 4x、page/Worker calibration、
primary memory APIのcapability diagnostics、CDP heap、10-cycle retention、
cancel/restart をformat version 2へ記録します。dedicated Worker sessionには
`Emulation.setCPUThrottlingRate`を実送信し、`applied`、`unsupported`、`failed`
をprotocol code/message付きで区別します。apply summaryの`failed_count > 0`は
runnerをnonzeroで停止します。command applied後のratio gate外は
`measurement_status: "unverified"`としてtransport failureと区別し、solver
failureとは断定しません。この値はTask 068のratio gate外を曖昧にしないための
format version 2拡張です。測定機能が`unsupported`なだけの場合もsolver failure
と扱いません。requested 4xは実端末測定ではなく、Worker command適用と
calibration gateの両方を通過した場合だけverified 4xとして扱います。JSON report
とscreenshot は commitしません。

## 検証

リポジトリrootから次を実行します。

```console
npm --prefix apps/web run test:browser-solver
npm --prefix apps/web run test
npm --prefix apps/web run lint
npm --prefix apps/web run typecheck
npm --prefix apps/web run build
```

## Production

本体は`https://mhwilds.trinitrotorol.com/skill-sim/`です。所持品チェッカーは
同じオリジンの`/inventory/`で、保存した所持情報を共有します。
`VITE_BASE_PATH=/skill-sim/`のbuild結果は`apps/web/dist/skill-sim/`に生成します。
既定値でbuildした旧版は`apps/web/dist/game-guide/mhwilds-skill-sim/`に生成します。
一括release buildは両版と子チェッカーを同じ固定ソースから生成してStatic Assetsで配信します。

旧`.com/game-guide/mhwilds-skill-sim/`は新URLへ301転送します。
旧所持情報は自動で移せないため、旧ページの`?legacy=1`から旧チェッカーを開き、
JSONをダウンロードして新チェッカーで復元できます。旧オリジンの保存データは保持します。

実カタログ、release manifest、検索用データは同一オリジンの静的ファイルから読みます。
releaseの`remote_enabled`はfalseで、有料のContainerや別API Workerは公開しません。
旧・新baseの限定APIパスは未設定の503を返し、ブラウザ検索はそれらへ通信しません。
frontendの既存Cloudflare Git integrationは維持しています。
公開後は新旧URL、JSON移行、ブラウザ検索、モバイル幅、キーボード操作を確認します。
詳細は[配信と復旧手順](../../docs/service/deployment.md)を参照してください。

`apps/web/dist/`は生成物です。Gitへcommitしません。
