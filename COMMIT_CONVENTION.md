# Commit Message Convention

手動で作成するコミットメッセージは、次の形式に統一します。

```text
type: short imperative summary
```

例:

```text
solver: validate generated build results
data: update decoration slot rules
ui: improve skill filter controls
test: add regression case for weapon slots
docs: document commit message convention
chore: clean obsolete files
```

ルール:

- `type` は小文字にします。
- summary は英語の命令形で短く書きます。
- 末尾に句点は付けません。
- 手動コミットでは `[add]` や `[delete]` のような独自プレフィックスは使いません。
- Merge commit、revert commit、bot やサービスが自動生成したコミットは、生成元の形式をそのまま使って構いません。

よく使う `type`:

- `solver`: スキル検索、ビルド生成、検証ロジックの変更
- `data`: スキル、装飾品、装備などのデータ変更
- `ui`: React UI、表示、操作性の変更
- `test`: テストの追加や修正
- `docs`: ドキュメント変更
- `chore`: 仕様に直接影響しない整理
