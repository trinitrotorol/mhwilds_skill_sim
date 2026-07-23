# MHWILDS スキルシミュレータ Web

ranked CP-SAT検索APIを利用する、React + TypeScript + Vite製のWebクライアントです。

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

Viteはapplication API prefix
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

Task 067 の自動 certification は Playwright Chromium と CDP を使用します。
Chromium だけをインストールし、repository root の ignored `.build` へ入力と
出力を置いて実行します。

```console
npm --prefix apps/web run install:browser-solver-chromium
npm --prefix apps/web run certify:browser-solver -- \
  --catalog ../../.build/browser-solver/browser-catalog.json \
  --oracle ../../.build/browser-solver/oracle.json \
  --output ../../.build/browser-solver/browser-certification.json \
  --screenshot-directory ../../.build/browser-solver/certification-screenshots \
  --repeats 5 \
  --timeout-ms 20000
```

この runner は local benchmark document だけを cross-origin isolated にし、
desktop 1x、低速 mobile 相当 profile の requested 4x、page/Worker calibration、
CDP heap、5-cycle retention、cancel/restart を記録します。requested 4x は実端末
測定ではなく、Worker calibration gateを通過した場合だけ4x certificationとして
扱います。JSON report と screenshot は commitしません。

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

production base pathは`/game-guide/mhwilds-skill-sim/`です。build結果は
`apps/web/dist/game-guide/mhwilds-skill-sim/`へ生成され、Cloudflare WorkerのStatic Assetsとして配信されます。

production backendが未設定でmetadata endpointから規定の503 responseが返った場合、画面はmock結果を生成せず「検索APIを準備しています」と表示します。

production APIは、既存frontend routeよりspecificな
`trinitrotorol.com/game-guide/mhwilds-skill-sim/api/*`を専用Worker
`mhwilds-skill-sim-api`へ割り当てます。このAPI Workerが未deploy、またはspecific routeが未設定の場合は、既存frontend WorkerがAPI pathを受けて従来の503 fallbackを返します。productionで`API_ORIGIN`を設定する必要はありません。

frontendの既存Cloudflare Git integrationは維持し、APIは別のmanual GitHub Actions workflow
`.github/workflows/deploy-cloudflare-api.yml`からだけdeployします。deploy後はhealth、non-emptyなCatalog metadata、empty requirements/preferencesかつ`max_results=1`のranked検索を確認し、公開画面をdesktop `1440 x 900`とmobile `390 x 844`の実browserで検証します。

`apps/web/dist/`は生成物です。Gitへcommitしません。
