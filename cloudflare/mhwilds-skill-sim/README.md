# MHWILDS サービス配信 Worker

`mhwilds-skill-sim` がシミュレーターと所持品チェッカーの静的ファイルを
同一オリジンで配信します。両アプリ、実カタログ、release manifest は同じ
固定submoduleのソースから一括buildします。本体は
`https://mhwilds.trinitrotorol.com`です。

- `/skill-sim/`（スキルシミュレーター）
- `/inventory/`（所持品チェッカー）
- `/` は `/skill-sim/` へ301リダイレクト

静的アセットを先に配信し、Worker優先実行は旧ページからの移転、rootと
slashなし・index.htmlのリダイレクト、限定APIパスに絞ります。
不明なファイルは404で、SPA fallbackはありません。
Content-Type、キャッシュ、CSP等は出力した`_headers`でも設定します。

検索はブラウザのWeb Workerで動作します。remote検索はrelease manifestと
両API gatewayで初期無効です。API_ORIGINだけでは通信しません。
ContainerやCloud Runはこの公開工程ではデプロイしません。

旧`.com/game-guide/mhwilds-skill-sim/`と
`.com/game-guide/mhwilds-inventory-checker/`は新URLへ301で転送し、クエリを保持します。
`?legacy=1`を付けると旧オリジンのアプリを開けます。保存データは
オリジンごとに分かれるため、旧チェッカーでJSONをダウンロードし、新チェッカーの
「JSONから復元」から取り込みます。自動移行や保存データの削除は行いません。
旧アプリ・アセット・カタログも同じ固定SHAからbuildして保持します。
旧アプリのcanonicalは新URLを指し、noindexを付けます。

## 公開と確認

固定Node/npm/Python、依存lockとCLIをリポジトリ内で使用します。
Cloudflareの本番コマンドは`sh scripts/cloudflare-publish.sh deploy`、
非本番は`sh scripts/cloudflare-publish.sh versions upload`です。
Wranglerのcustom buildは`sh scripts/build-service-release.sh`を実行します。
毎回固定子SHAを取得し、全検証に成功した新しい実データだけを公開します。

`sh scripts/cloudflare-publish.sh deploy --dry-run`でローカル出力を検証できます。
実デプロイには既存アカウントの権限と無料プランの確認が必要です。

Wranglerに専用ホストのcustom domainと、旧2ツールに限定した4routeを宣言します。
slashなしのクエリも届くよう旧routeの一方をツール名末尾の`*`にし、Workerで
類似名を404に制限します。対象外のguideやrootのWorkerは引き続き別配信です。詳細は
[運用手順](../../docs/service/deployment.md)を参照してください。

公開後は新旧両ページ、301と`?legacy=1`、release/catalog JSON、ハッシュ付きJS/CSS、slash redirect、
unknown404、ブラウザ検索、所持数制約、JSONバックアップ、キャンセル、
モバイル幅、キーボード操作を実際のURLで検証します。
既存guide、robots/sitemap/ads.txt、旧→新のJSON復元、旧データの保持も確認します。
Cloudflareの`MHWILDS apps: disable RUM`ルールは専用ホスト全体と旧2ツールを
対象にし、自動analyticsスクリプトを挿入しません。
