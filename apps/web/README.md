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

## 検証

リポジトリrootから次を実行します。

```console
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
