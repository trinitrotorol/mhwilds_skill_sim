# MHWILDS サービス配信 Worker

`mhwilds-skill-sim` がシミュレーターと所持品チェッカーの静的ファイルを
同一オリジンで配信します。両アプリ、実カタログ、release manifest は同じ
固定submoduleのソースから一括buildします。

- `/game-guide/mhwilds-skill-sim/`
- `/game-guide/mhwilds-inventory-checker/`

静的アセットを先に配信し、Worker実行はslashなしのリダイレクトと限定API
パスに絞ります。不明なファイルは404で、SPA fallbackはありません。
Content-Type、キャッシュ、CSP等は出力した`_headers`でも設定します。

検索はブラウザのWeb Workerで動作します。remote検索はrelease manifestと
両API gatewayで初期無効です。API_ORIGINだけでは通信しません。
ContainerやCloud Runはこの公開工程ではデプロイしません。

## 公開と確認

固定Node/npm/Python、依存lockとCLIをリポジトリ内で使用します。
Cloudflareの本番コマンドは`sh scripts/cloudflare-publish.sh deploy`、
非本番は`sh scripts/cloudflare-publish.sh versions upload`です。
Wranglerのcustom buildは`sh scripts/build-service-release.sh`を実行します。
毎回固定子SHAを取得し、全検証に成功した新しい実データだけを公開します。

`sh scripts/cloudflare-publish.sh deploy --dry-run`でローカル出力を検証できます。
実デプロイには既存アカウントの権限と無料プランの確認が必要です。

既存のskill-sim用2routeを保持し、checker用のslashなしと`/*`だけを加えます。
対象外のguideやrootのWorkerを変更しません。詳細は
[運用手順](../../docs/service/deployment.md)を参照してください。

公開後は両ページ、release/catalog JSON、ハッシュ付きJS/CSS、slash redirect、
unknown404、ブラウザ検索、所持数制約、JSONバックアップ、キャンセル、
モバイル幅、キーボード操作を実際のURLで検証します。
既存guideが引き続き有効であることも確認します。
