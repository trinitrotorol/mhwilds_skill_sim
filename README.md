# MHWILDS スキルシミュレーター

日本語のスキル検索と所持品チェッカーを同じオリジンで提供します。
装飾品の所持数と固定・鑑定護石を保存し、その内容を装備検索へ反映します。
計算はブラウザのWeb Workerで実行し、最大20候補と探索終了状態を表示します。
途中結果は全探索済みとして扱いません。サーバー計算は初期設定で無効です。

## 利用

所持品チェッカーで登録してから、相互リンクでシミュレーターへ移動し
「所持品を考慮する」を選択してください。記載のない装飾品は0個です。
保存場所は端末・ブラウザ・オリジンごとです。定期的にJSONを保存してください。
バックアップはプレビュー後に復元または統合でき、統合数量は同IDの最大値です。
別タブの更新、壊れた保存データ、現在のカタログにないIDを警告して保護します。

## 開発と標準検証

Linux/WSLで固定Node/npmを各リポジトリの`.venv`へ導入します。
可変キャッシュは`.cache`、生成物は`.build`に置きます。

```sh
git submodule update --init
./scripts/bootstrap.sh
sh scripts/pyw -m pip install -r requirements-service.txt
sh scripts/pyw -m pip install --no-deps -e .
./scripts/npmw --prefix apps/web ci
(cd subprojects/inventory-checker && ./scripts/bootstrap.sh && ./scripts/npmw ci)
sh scripts/verify-service.sh
```

標準コマンドは`make test`、`make lint`、`make data-check`です。
pytestはWSLのリポジトリ内一時領域でも安定するsys captureを使用します。
Webのtest/lint/buildと子のverifyも実行します。子は単独で検証・buildできます。
共有APIの正本は子の`integration/README.md`、JSON Schemaは`contracts/`です。

## 実カタログと一括build

```sh
sh scripts/pyw -m scripts.build_service
```

MHDB日本語カタログと、Dtlnor・Akiの鑑定護石解析表を取得・検証します。
名前は取り込み時の照合だけに使い、永続参照はMHDB由来IDです。
失敗時にfixtureへ切り替えず、直前の正常な配信artifactを保持します。
生成時の入力・hash・出典は`.build/service-staging`、公開用出力は
`.build/service-assets`、release manifestは各出力の`release.json`です。

テストfixtureは明示したローカルsmokeに限定します。

```sh
sh scripts/pyw -m scripts.build_service --fixture --source data/fixtures/tiny_catalog.json
```

子のmainへのpushだけでは公開版は変わりません。子の検証済みSHAをpushし、
親submoduleをそのSHAへ更新して全検証・clean build後に公開します。
公開/rollback判断と進捗は子の`docs/service/`を参照してください。
