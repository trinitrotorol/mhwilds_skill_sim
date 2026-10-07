# サービスUIの参照方針

ユーザーの2026-10-06追加指定により、チェッカーとシミュレーターのWeb UIは
[デジタル庁デザインシステム](https://design.digital.go.jp/dads/)を参考にした独自実装とした。
行政機関のロゴ・名称の流用や、公式サービス・完全準拠という表示は行わない。

- [カラー](https://design.digital.go.jp/dads/foundations/color/): 白地と黒文字、青の主要操作、意味を持つ成功・警告・エラー色、黄色＋黒の二重フォーカス。
- [タイポグラフィ](https://design.digital.go.jp/dads/foundations/typography/): 16pxを本文・操作の基準、補助は14px以上、通常/太字の階層と十分な行高。
- [ボタン](https://design.digital.go.jp/dads/components/button/): 塗り・アウトライン・テキストの操作階層、44px以上のターゲット領域（本実装は原則48px）。
- [入力](https://design.digital.go.jp/dads/components/input-text/): 常時見えるラベルと、入力に関連付けたエラー表示。

既存の緑・金の配色を更新した。外部Webフォントや追加UIライブラリを読込まない。
狭い画面での縦方向への再配置、スキップリンク、キーボード操作を両アプリで維持する。
確認資料の公開版はv2.18.0（確認日2026-10-06）。実際のa11y・viewport検証結果は
リリース検証記録を参照する。

2026-10-07のサイト改善では、公開用HTMLに両アプリ固有のタイトル・説明・canonical・
Open Graph情報を設定し、サイト案内と使い方・制約・保存方法の説明を追加する。
説明はReactの操作領域の外にある通常の可視コンテンツで、JavaScript無効時にも読める。
検索エンジンだけに見せる文章や、広告・外部解析スクリプトは追加しない。
生成処理は `scripts/service_html.py`、見た目は各アプリ内へ配信する
`scripts/service-html.css` に集約する。JavaScript有効時はアプリのmain・h1を保ち、
無効時だけnoscript内にmain・h1と説明へのリンクを表示する。サイト情報は
名前のあるsectionとnavにする。canonicalはpreview環境でも本番の正規URLを指す。

WSLのWindows側ファイルシステムでVitestのDOM環境起動がタイムアウトする場合は、
`VITEST_REUSE_ENV=1 ./scripts/npmw --prefix apps/web run test` で全テストを環境再利用で実行できる。
通常実行とCIではテストファイルの分離を維持する。
