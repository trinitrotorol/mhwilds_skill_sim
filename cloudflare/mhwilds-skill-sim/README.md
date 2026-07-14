# MHWILDS スキルシミュレータ Cloudflare Worker

## 目的

Worker `mhwilds-skill-sim`は、React/Viteのbuild outputをCloudflare Static Assetsから配信し、同一originの限定API pathだけを将来のFastAPI backendへ中継します。placeholder HTMLやSPA fallbackは使用しません。

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

現在の本番環境では`API_ORIGIN`は未設定です。その間、APIは503と`search API is not configured`を返し、React UIは「検索APIを準備しています」とretry buttonを表示します。

将来backendを用意した後、`API_ORIGIN`をCloudflareのWorker環境変数として設定します。値はpath、query、fragment、credentialsを含まない別originのabsolute HTTPS originに限定し、repositoryや`wrangler.jsonc`へ値をcommitしません。route/domain設定の変更は不要です。

## Public URL

deploy後、両方のURLでReact画面を確認します。

```text
https://trinitrotorol.com/game-guide/mhwilds-skill-sim/
https://mhwilds-skill-sim.trinitrotorol.workers.dev/game-guide/mhwilds-skill-sim/
```

slashなしURLがqueryを維持して308になること、HTMLとgenerated JS/CSSが200になること、API未設定の503をUIが準備中状態として扱うことも確認します。

## Actual browser smoke

custom-domain pageを実際のbrowserで開き、desktop相当`1440 x 900`とmobile相当`390 x 844`の両方で次を確認します。

```text
- React画面がrenderされる
- header、「検索APIを準備しています」、retry buttonが表示される
- layout崩れ、horizontal overflow、JS/CSS load failureがない
- keyboard focusを操作できる
- consoleにuncaught errorがない
- networkで限定APIが意図した503 JSONを返す
- 古いplaceholderだけの表示ではない
```

最後に既存guideが引き続き有効であることを確認します。

```text
https://trinitrotorol.com/game-guide/exponential-idle-minigame-guide
```
