# MHWILDS スキルシミュレータ Cloudflare Worker

## 目的

これはReact UIではありません。Cloudflare GitHub buildを通すための最小placeholder Workerです。Cloudflareのautomatic static directory detectionには依存せず、Worker entrypointはrepository rootの`wrangler.jsonc`で明示されています。

## ローカル検証

```text
node --test cloudflare/mhwilds-skill-sim/src/index.test.mjs
npx --yes wrangler@4.110.0 deploy --dry-run --config wrangler.jsonc --outdir .wrangler/dry-run
```

Wranglerのdry-runはbundleを検証しますが、Cloudflareへdeployしません。

## Cloudflare Builds設定

Cloudflare DashboardのWorker `mhwilds-skill-sim-web` で次を設定します。

```text
Git repository: trinitrotorol/mhwilds_skill_sim
Production branch: master
Root directory: 空欄
Build command: 空欄
Deploy command: npx wrangler@4.110.0 deploy
```

既存のGitHub connectionを作り直す必要はありません。設定を保存したら、最新の`master`のdeploymentをRetryします。

## workers.dev smoke test

build成功後、Cloudflare Dashboardが示すworkers.dev hostnameで次のpathを開きます。

```text
/game-guide/mhwilds-skill-sim/
```

root `/` ではなく上記pathを確認し、次が表示されることを確認します。

```text
MHWILDS スキルシミュレータ
現在準備中です。
```

## Custom Routeはbuild成功後に追加

このTaskの`wrangler.jsonc`はrouteを管理しません。build成功後、Cloudflare Dashboardで次のCustom Routeを追加します。

Zone:

```text
trinitrotorol.com
```

Routes:

```text
trinitrotorol.com/game-guide/mhwilds-skill-sim
trinitrotorol.com/game-guide/mhwilds-skill-sim/*
```

次のURLを確認します。

```text
https://trinitrotorol.com/game-guide/mhwilds-skill-sim/
```

既存URLも必ず確認します。

```text
https://trinitrotorol.com/game-guide/exponential-idle-minigame-guide
```

このTaskではDashboard routeの作成成功をrepository testで偽装しません。

## 将来

- 次のUI TaskでReact、Vite、static assetsを追加します。
- FastAPI backend hostingとAPI proxyは別タスクです。
- placeholder Workerをclient-side search実装へ拡張しません。
