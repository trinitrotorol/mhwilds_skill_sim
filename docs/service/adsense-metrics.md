# AdSense の非公開レポート

`scripts/adsense_metrics.py` は AdSense Management API v2 の読み取り専用 CLI です。
Web サイトのビルドやブラウザから呼び出しません。広告の設置、広告設定、支払いの変更は行いません。
外部 Python パッケージは不要です（Python 3.11 以上）。

## 初回の接続

1. 専用の Google Cloud プロジェクトで **AdSense Management API** を有効にします。
2. Google Auth Platform でアプリ名・連絡先・対象ユーザーを設定します。
   個人用の Google アカウントは External、Testing 中は自分を Test user に登録します。
3. Data Access は `https://www.googleapis.com/auth/adsense.readonly` のみにします。
4. **Desktop app** の OAuth クライアントを作成し、JSON を非公開のローカルフォルダーに保存します。
   Web application、API キー、サービスアカウントはこの CLI では使いません。
5. 通常利用する Windows ユーザーで、ネイティブ Windows Python を使って以下を実行します。

```powershell
& 'C:\Users\trini\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/adsense_metrics.py auth --client-config 'C:\private\adsense-desktop-client.json'
```

CLI が表示する Google の URL をブラウザで開き、対象の AdSense アカウントを選んで
読み取り専用アクセスを許可します。認可待機は最大 5 分です。CLI はログインや同意操作を代行しません。
PKCE S256 とランダムな state を使用し、コールバックは `127.0.0.1` のランダムポートだけで受けます。
認可コードは画面・ログに出しません。Google の `accounts.list` に
`accounts/pub-6343181736493400` が実際に返ることを確認してから保存します。
異なるアカウントを自動選択することはありません。

Windows の既定保存先は `%LOCALAPPDATA%\trinitrotorol\site-metrics` です。
`credentials.json` のクライアント情報と refresh token は Windows DPAPI CurrentUser で暗号化します。
同じ Windows ユーザーで実行してください。短命の access token は保存しません。
認可済みのローカル保存を確認後、ダウンロードした平文クライアント JSON は安全に削除できます。
認可情報や JSON 本文をチャット、Git、公開フォルダーに貼り付けないでください。

Linux の既定先は `$XDG_STATE_HOME/trinitrotorol/site-metrics`、未設定なら
`~/.local/state/trinitrotorol/site-metrics` です。フォルダーは 0700、ファイルは 0600 で保存します。
Windows と WSL は別の保存先・暗号化方式なので、Windows の定期実行に WSL を混ぜません。

## 定期取得と状態

```powershell
& 'C:\Users\trini\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/adsense_metrics.py status
& 'C:\Users\trini\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/adsense_metrics.py collect
```

`status` は保存済み設定をローカルで確認するだけで、認可の有効性や API 接続成功を意味しません。
`collect` の成功が接続確認です。終了コード 0 は成功、2 は要対応、130 は中断です。
失敗時は `auth_required`、`access_denied`、`network_error` などの短い状態だけを出力します。
トークン・認可コード・Google のエラー本文は出力しません。`invalid_grant` は再認可が必要な状態であり、
アクセス数や収益がゼロになったと解釈しません。

成功時のレポートは同じ非公開フォルダーの `latest-report.json` に原子的に保存します。
取得失敗では前回の成功レポートを上書きしません。必ず今回の終了状態と `collected_at` を確認し、
古い成功ファイルを今回の実績として扱わないでください。標準出力は取得時刻・件数・注意情報の件数だけです。
明示的な保存先は `collect --output C:\private\report.json`、状態フォルダーは
`--state-dir C:\private\site-metrics collect` で指定できます。
Git リポジトリ内（無視ファイルを含む）、`public`・`dist`・`service-assets`、シンボリックリンクは拒否します。

月曜・木曜 09:00 **日本時間** のチャット定期実行からこの `collect` を実行します。
スケジュールの時刻と集計の日付のタイムゾーンは別です。
集計は AdSense アカウントの `timeZone.id` と `ACCOUNT_TIME_ZONE` を使用し、
当日を除く直近 7 日・その前の 7 日・直近 28 日・その前の 28 日を取得します。
Windows に IANA タイムゾーンデータがない場合も `Asia/Tokyo` と UTC は扱えます。
他のタイムゾーンを勝手に日本時間へ置き換えず、データベース不足として停止します。

取得対象のホストは以下だけです。

- `trinitrotorol.com`
- `mhwilds.trinitrotorol.com`
- `trinitrotorol.github.io`

`sites.list` の `state`・`autoAdsEnabled` を保存するのもこのリストに一致するサイトだけです。
サブドメインが sites 一覧に独立表示されなくても、3 ホストのレポートはそれぞれ完全一致の
`DOMAIN_CODE` フィルターで取得します。別のサイトのレポートを保存しません。

取得する指標は見積もり収益・ページビュー・広告表示回数・クリック数・ページ RPM・ページ CTR・
広告リクエストのカバレッジです。通貨コードと API の値はそのまま保存します。
CTR・カバレッジの `METRIC_RATIO` は 0–1 の比率です。パーセント表示するときだけ 100 倍します。
ホストごとの期間集計を直接要求するため、日次 CTR/RPM を単純平均しません。
空データ、API エラー、実績 0 は区別します。警告、実際の集計期間、打ち切りの有無を残します。
`comparable: false`（空データ・期間不一致・打ち切り）のレポートを完全な期間比較に使いません。
`comparable: true` でも警告の意味と母数を確認し、少数のクリック変動を確定的な効果と見なしません。

AdSense は広告に関する計測です。広告のないツールの全利用状況や検索流入はわかりません。
サイト改善では公開ページの動作・表示・リンク等も確認し、レポートの不足をサイト全体の利用ゼロと
取り違えないでください。認可失効・新しい問題・改善結果など、対応が必要な変化だけを通知します。

## Testing と認可の期限

External アプリが Testing の場合、今回の AdSense scope の refresh token は原則 7 日で期限切れになります。
週 2 回の継続取得には Testing のまま繰り返し認可するより、専用の個人利用アプリを Production にする
運用が適しています。Production にしても検証済みアプリになるわけではありません。
個人・少人数で使うアプリは Google の検証例外に該当する場合がありますが、未検証表示やユーザー上限等は残ります。
公開配布する場合は同じ前提を使わず、必要な検証を確認してください。
Production でも利用者の取り消し、長期未利用、アカウント側の変更等で失効し得ます。
CLI は失効を通知する状態を返し、自動で追加権限を取得しません。

公式資料:

- [Installed app OAuth / loopback / PKCE](https://developers.google.com/identity/protocols/oauth2/native-app)
- [OAuth token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)
- [OAuth verification exceptions](https://developers.google.com/identity/protocols/oauth2/production-readiness/policy-compliance)
- [AdSense reports.generate](https://developers.google.com/adsense/management/reference/rest/v2/accounts.reports/generate)
- [AdSense account timezone](https://developers.google.com/adsense/management/reference/rest/v2/accounts)
- [AdSense report filters](https://developers.google.com/adsense/management/reporting/filtering)
- [AdSense ReportResult](https://developers.google.com/adsense/management/reference/rest/v2/ReportResult)

## 開発時の検証

```sh
sh scripts/pyw -m pytest tests/scripts/test_adsense_metrics.py
make lint
```

テストは偽の HTTP transport と固定時計を用い、Google 接続や認可情報の作成を行いません。
初回接続時には本番の `collect` で指標の組み合わせとアカウントの利用可能状態を確認してください。
