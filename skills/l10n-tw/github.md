# GitHub Operations — zh_TW 翻譯專案常用操作

### Remote 命名慣例

| Remote     | URL                                | 用途                   |
| ---------- | ---------------------------------- | -------------------- |
| `origin`   | `github.com/<user>/<project>.git`  | fork — push 目標       |
| `upstream` | `github.com/<owner>/<project>.git` | 原始 repo — fetch only |

### Setup 序列

```bash
gh repo fork <owner>/<project> --remote-name fork
git remote -v                        # 確認 fork remote 有無正確建立
git remote rename origin upstream    # 原 origin → upstream
git remote add origin https://github.com/<user>/<project>.git
git remote remove fork               # 清除 gh 多餘的 remote
```

### Branch 命名

- 全小寫、連字號
- 無 `feat/` 前綴
- 單一專案 repo：`zh-tw-translation`
- Monorepo（如 cinnamon-spices-extensions）：`<extension>-zh-tw`（如 `transparent-panels-zh-tw`）
- 一個 branch 對一個 PR，不疊加

### Commit 格式

- Monorepo（如 cinnamon-spices-extensions）：`Add zh_TW translation for <extension>`
- 單一專案 repo：`Add zh_TW translation`
- 一個 commit 對應一個 PR，不疊加

### PR 格式

- **Title**：單一專案 repo → `i18n: Add zh_TW translation`（若上游要求）
  - Monorepo → `Add zh_TW translation for <extension>`
- **Body**：簡潔、事實導向，不廢話
  ```
  Add Traditional Chinese (zh_TW) translation.

  - N msgid translated (100% coverage)
  - Generated from upstream po/<project>.pot (POT-Creation-Date: YYYY-MM-DD)
  - LINGUAS updated to register the new locale
  ```
- Commit & PR title 應一致（特定專案 repo 適用）
- **語言**：預設使用簡單英文撰寫（commit message、PR title/body）。除非使用者特別要求，不使用中文

### Push & PR

```bash
git push -u origin zh-tw-translation
# 先展示 push 結果給使用者確認
gh pr create --repo <owner>/<project> \
  --head <user>:zh-tw-translation \
  --title "i18n: Add zh_TW translation" \
  --body "..."
```
