# MHWILDS スキルシミュレータ Cloudflare Worker

## 目的

Worker `mhwilds-skill-sim`は、React/Viteのbuild outputをCloudflare Static Assetsから配信し、同一originの限定API pathに対する503 fallbackを維持します。production APIは、よりspecificな別routeから専用API Workerへ送られます。placeholder HTMLやSPA fallbackは使用しません。

配信pathは次の2種類です。

```text
/game-guide/mhwilds-skill-sim/
/game-guide/mhwilds-skill-sim/assets/*
```

slashなしのapplication pathはslash付きへ308 redirectします。root、既存guide、unknown child pathはこのWorkerでは処理せず404にします。

## ローカル検証

```text
node --test cloudflare/mhwilds-skill-sim/src/index.test.mjs
npx --yes wrangler@4.110.0 deploy --dry-run --config wrangler.jsonc --outdir .wrangler/dry-run
```

Wranglerのdry-runはcustom build、Static Assets、Worker bundleを検証しますが、Cloudflareへdeployしません。custom buildは各`wrangler deploy`で次を実行します。

```text
npm --prefix apps/web ci --no-audit --no-fund
npm --prefix apps/web run build
```

毎回lockfileからdeterministicなinstallを行い、その直後に新しいStatic Assetsを生成するため、Dashboard側に別のBuild commandは設定しません。

## Cloudflare Builds設定

Cloudflare DashboardのWorker `mhwilds-skill-sim` で次を設定します。

```text
Git repository: trinitrotorol/mhwilds_skill_sim
Production branch: master
Root directory: 空欄
Build command: 空欄
Deploy command: npx wrangler@4.110.0 deploy
```

既存のGitHub connectionやCustom Routeを変更する必要はありません。

## API proxy

公開するAPI mappingは次の3件だけです。query stringとmethodを維持し、CookieとAuthorizationはbackendへ転送しません。

```text
GET  /game-guide/mhwilds-skill-sim/api/health
GET  /game-guide/mhwilds-skill-sim/api/catalog/metadata
POST /game-guide/mhwilds-skill-sim/api/search/cp-sat/ranked
```

productionでは、既存frontend routeよりspecificな
`trinitrotorol.com/game-guide/mhwilds-skill-sim/api/*`を専用Worker
`mhwilds-skill-sim-api`へ割り当てます。specific routeが先にmatchするため、このfrontend Workerの`API_ORIGIN`設定は不要です。API Workerが未deploy、またはspecific routeが未設定の場合は、このWorkerがAPI pathを受けて従来どおり503と`search API is not configured`を返し、React UIは「検索APIを準備しています」とretry buttonを表示します。

frontendの既存Cloudflare Git integrationは維持します。API deployは別のmanual GitHub Actions workflow `.github/workflows/deploy-cloudflare-api.yml`だけから実行し、pushによる自動API deployは行いません。

## Public URL

deploy後、両方のURLでReact画面を確認します。

```text
https://trinitrotorol.com/game-guide/mhwilds-skill-sim/
https://mhwilds-skill-sim.trinitrotorol.workers.dev/game-guide/mhwilds-skill-sim/
```

slashなしURLがqueryを維持して308になること、HTMLとgenerated JS/CSSが200になることを確認します。API Workerのdeploy後はhealthとnon-emptyなCatalog metadataが200であること、empty requirements/preferencesかつ`max_results=1`のranked検索がcandidateを返すことも確認します。API Worker未deploy時は従来の503 fallbackを確認します。

## Actual browser smoke

custom-domain pageを実際のbrowserで開き、desktop相当`1440 x 900`とmobile相当`390 x 844`の両方で次を確認します。

```text
- React画面がrenderされる
- headerと検索formが表示され、API Worker deploy後は「検索APIを準備しています」が表示されない（未deploy時は準備中表示とretry buttonが表示される）
- layout崩れ、horizontal overflow、JS/CSS load failureがない
- keyboard focusを操作できる
- consoleにuncaught errorがない
- networkでhealth、metadata、ranked検索が成功する（API Worker未deploy時は意図した503 JSONを返す）
- 古いplaceholderだけの表示ではない
```

最後に既存guideが引き続き有効であることを確認します。

```text
https://trinitrotorol.com/game-guide/exponential-idle-minigame-guide
```
