# Project invariants

- React内に検索ロジックを書かない。
- solverが返す全BuildResultはvalidate_buildを通す。
- 武器装飾品は武器スロットにしか配置できない。
- 防具装飾品は防具スロットにしか配置できない。
- セット・グループスキルは必要部位数から計算する。
- 表示名を永続IDとして使用しない。
- バグ修正には必ず回帰テストを追加する。

# Required commands

- `make test`
- `make lint`
- `make data-check`

# Git changes

- git の状態を変更する操作を行う前に、必ず `COMMIT_CONVENTION.md` を確認する。
- 手動コミットを作成する場合は、`COMMIT_CONVENTION.md` の形式に従う。
- 手動コミットを作成したら、特別な指示がない限り毎回リモートへ push する。
