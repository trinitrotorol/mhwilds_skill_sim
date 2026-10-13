# Search Console の非公開レポート

`scripts/search_console_metrics.py` は、確認済みの `sc-domain:trinitrotorol.com` を対象に
Google 検索の表示回数・クリック数・CTR・平均掲載順位を読み取ります。
標準ライブラリのみを使用し、無料の Search Console API の範囲内で動作します。
有料サービスやプラン変更は不要です。クォータ制限は有限回の再試行後に停止し、課金による拡張は行いません。

許可する API は `sites.list` と `searchAnalytics.query` だけです。サイト登録、所有権、
サイトマップ、インデックス、広告設定は変更しません。この CLI はサイトビルドにも含めません。

## 認可と保存先

Google Cloud の既存プロジェクトで **Google Search Console API** を有効にし、OAuth の
Data Access に `https://www.googleapis.com/auth/webmasters.readonly` だけを追加します。
同じ Desktop app クライアントを使えますが、Search Console の読み取り許可は別に取得します。
Google が本人のログインや追加認証を求める場合は、本人が完了してから進めます。

AdSense の稼働を保つため、以下は AdSense の暗号化ファイルからクライアント登録情報だけを
読み込みます。AdSense の refresh token を Search Console に送ったり、別用途で使用したりしません。
Search Console の新しいトークンは、同じ非公開ディレクトリの **別名ファイル** に保存します。

この PC の例は、リポジトリのルートで次のとおりです。

```powershell
$metricsPython = 'C:\Users\trini\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$metricsState = 'C:\Users\trini\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\trinitrotorol\site-metrics'
& $metricsPython scripts/search_console_metrics.py --state-dir $metricsState auth --client-from-adsense-state-dir $metricsState
```

認可 URL をブラウザで開き、本人が Search Console の読み取りだけを許可します。
待機は最大 5 分、PKCE S256 と state、`127.0.0.1` のランダムポートを使用します。
`sites.list` が対象プロパティと利用可能な権限を返すことを確認してから保存します。
所有者・フルユーザー・制限付きユーザーを識別して保持し、未確認ユーザーでは保存しません。
要求外の scope が返った場合も保存せず停止します。

クライアント JSON を別途利用する場合は、`auth --client-config 'C:\private\client.json'` を使えます。
二つのクライアント読込オプションは同時指定できません。クライアント JSON、認可コード、
トークンをログやチャット、Git に貼り付けないでください。

`--state-dir` は全コマンドで必須です。Windows Store 版 Codex の仮想化では通常の AppData 指定が
別の実体へ転送される場合があるため、この PC では上記の実体パスを統一して使用します。
同じ Windows ユーザー・ネイティブ Windows Python で実行します。
Windows では DPAPI CurrentUser、Linux ではファイル 0600・ディレクトリ 0700 を使用します。
Git、公開フォルダー、シンボリックリンクへの保存は拒否します。

- `search-console-credentials.json`: Search Console 専用の認可情報
- `search-console-latest-report.json`: Search Console 専用の最終成功レポート

AdSense の `credentials.json` / `latest-report.json` は上書きしません。
Search Console は短命の access token を保存せず、独立した refresh token で更新します。
失敗時には最後の成功レポートを維持し、認可失効を `auth_required` として返します。

## 月曜・木曜の取得

```powershell
& $metricsPython scripts/search_console_metrics.py --state-dir $metricsState status
& $metricsPython scripts/search_console_metrics.py --state-dir $metricsState collect
```

`status` はローカル設定だけを確認します。`collect` の成功が実際の API 接続確認です。
終了コード 0 は成功、2 は対応が必要、130 は中断です。標準出力に検索語・ページ別実績や秘密情報は出しません。
取得に失敗した場合、以前のファイルを今回のレポートと扱わず、終了状態と `collected_at` を確認します。

月曜・木曜 09:00 日本時間の既存定期実行では、AdSense の取得にこのコマンドを追加します。
この時刻は実行予定です。Search Console の集計日付は **America/Los_Angeles（太平洋時間）** です。
夏時間を扱う IANA タイムゾーンデータが必要です。上記の同梱 Windows Python では利用できることを
確認しています。データベースがない環境では停止し、固定 UTC-8 や日本時間へ置き換えません。

API データの遅延を考慮し、太平洋時間の当日から **3 日前** を共通の終了日とします。
開始日・終了日はともに含み、その終了日から直近 7 日／前の 7 日／直近 28 日／前の 28 日を取得します。
全リクエストは `dataState: final`、検索タイプは `web` です。
直近 10 日の日付別 final リクエストも行い、最後に実績が返った日を
`freshness.latest_observed_final_date` に記録します。ただし、実績がない日も省略されるため、
その日まで全データが確定しているという保証ではありません。
比較窓を「最後に実績があった日」へ自動で移動せず、低トラフィック時の窓の偏りを避けます。

## レポートの見方

`schema_version: 1` の `sections` は次の三つに分かれます。

| section | 対象 | 集計の注意 |
| --- | --- | --- |
| `property` | ドメインプロパティ全体。全サブドメイン・プロトコルを含む | `root` と `mhwilds` に重複する |
| `root` | `trinitrotorol.com` の HTTP/HTTPS ページ | ページのホストを完全一致で抽出 |
| `mhwilds` | `mhwilds.trinitrotorol.com` の HTTP/HTTPS ページ | ページのホストを完全一致で抽出 |

各 section に四期間の `overall`・`top_queries`・`top_pages` があります。
全体集計は dimension なしで API に直接要求し、上位行の足し算から作りません。
`property` の全体は `byProperty`、ホストのページフィルターとページ別集計は `auto` を要求し、
返された `response_aggregation_type` を保存します。
**三つの section を合算しません。** ドメイン全体を二つのホストの合計と見なすこともできません。
対象範囲に加えてプロパティ集計とページ集計の数え方が異なるためです。
比較する場合は同じ section・同じ返却集計方式・同じ長さの期間を使います。

検索語・ページの上位リストはクリック順の最大 100 行です。100 行に達したかを記録しますが、
少ない行数でも API 内部の上位行制限があり、常に `non_exhaustive: true` とします。
匿名化された検索語は検索語別リストに含まれません。上位行の合計をサイト全体と見なしません。
受信したページ URL が対象ドメイン／指定ホストから外れていれば保存前に停止します。

クリック・表示回数・CTR・平均掲載順位は API が返した期間値をそのまま保持します。
日次 CTR・順位の単純平均は禁止です。CTR は 0–1 の比率で、同じ集計方式の重複しないデータを
再計算するときは合計クリック数／合計表示回数を使います。順位には表示回数の重みが必要です。
この CLI 自体は top rows から再集計せず、別途取得した `overall` を使います。

空データは `status: empty` / `rows: []` で、ゼロの値を補いません。
日付の欠落や `metadata` はそのまま扱い、`coverage_confirmed: false` として完全性を断定しません。
最新の観測日が古い、データ量が少ない、または想定外の未確定 metadata がある場合は、
短期変動をサイト改善の確実な効果と判断しないでください。
Search Console の検索実績だけで全訪問数や全ページのインデックス状態を説明することもできません。

認可情報・取得レポート・検索語や個別実績は非公開で扱い、公開 PR に記載しません。
無料範囲でできる公開ページの動作・リンク・検索用メタデータ等の確認と併せて改善判断に使います。

## 検証と資料

```sh
sh scripts/pyw -m pytest --capture=sys tests/scripts/test_search_console_metrics.py
make test
make lint
make data-check
```

単体テストは偽の transport・callback サーバー・時計を用い、Google への通信や実際の認可を行いません。
初回の本人認可と `collect` は別途必要です。Testing の refresh token は期限が短いため、
継続運用の OAuth 公開状態・失効時の対応は [AdSense の手順](adsense-metrics.md) も参照してください。

- [Search Analytics query API](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)
- [Sites list API](https://developers.google.com/webmaster-tools/v1/sites/list)
- [Data limits and extraction](https://developers.google.com/webmaster-tools/v1/how-tos/all-your-data)
- [Search Console API limits](https://developers.google.com/webmaster-tools/limits)
