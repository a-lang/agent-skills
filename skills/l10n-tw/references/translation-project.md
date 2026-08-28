# Translation Project 專案品質驗收規範

本文件適用於**來源檔來自 [Translation Project](https://translationproject.org/)（TP）平台**的翻譯任務。
當 Agent 要翻譯的 POT／PO 檔來自 TP（例如從 TP 網站下載、或專案宣告為 TP 管轄）時，
翻譯完成的品質驗收流程除遵循 `SKILL.md`「通用驗證步驟」與「品質自檢清單」外，
**必須**額外符合以下條件。

## 一、{PACKAGE-NAME} 判定

檔頭樣板中的 `{PACKAGE-NAME}` **僅含專案名稱，不含版本號碼**。
判定來源依序：

1. Agent 已知的專案名（例如 TP 官網所列）
2. 檔頭 `Project-Id-Version` 欄位 → 取第一個 token（`wget 1.21.4` → `wget`）
3. POT／PO 檔名 → 去除版本尾碼（`wget-1.21.4.pot` → `wget`；`coreutils-9.4.pot` → `coreutils`）

> 樣板中 `This file is distributed under the same license as the {PACKAGE-NAME} package.`
> 不得出現版本字樣（如 `wget 1.21.4`）。

## 二、品質驗收條件

### 1. 檔頭開頭註解須符合 TP 格式

標頭的開頭註解需符合以下格式（`{PACKAGE-NAME}` 置換成專案名稱，**其餘保持不變**）：

```po
# SOME DESCRIPTIVE TITLE.
# Copyright (C) 2026 Free Software Foundation, Inc.
# This file is distributed under the same license as the {PACKAGE-NAME} package.
# AUTHOR NAME <EMAIL@ADDRESS>, 2026.
#
```

- `SOME DESCRIPTIVE TITLE.`、`Free Software Foundation, Inc.`、`AUTHOR NAME <EMAIL@ADDRESS>` 等字樣保持不變
- 年份以當前年份為準（本文件範例為 2026）
- 四行註解後接一個空的 `#` 行，再接 `msgid ""`

### 2. 檔頭 msgstr 欄位須符合 TP 格式

生成 PO 時**務必**加上：

```bash
--team "Chinese (traditional) <zh-l10n@lists.slat.org>"
```

檔頭必須包含：

- `Language-Team: Chinese (traditional) <zh-l10n@lists.slat.org>`
- `Project-Id-Version: {PACKAGE-NAME} <版本>`（版本號碼可保留，名稱部分不可含版本）

### 3. CLI 求助文字的輸出需做對齊檢查

依 `SKILL.md`「通用驗證步驟」第 4 項「對齊檢查（CLI 求助文字）」執行
`po_align_check.py`，退出碼必須為 0；退出碼 1 時依報告逐條調整補空格數後重新驗證。

### 4. 翻譯者注意事項

更多翻譯者要注意的事項，可參考：<https://translationproject.org/html/translators.html>

重點摘要：

- **檔頭開頭註解**：每支 PO 檔以四行（或以上）註解開頭，順序為：標題行 → 版權行 →
  授權聲明行 → 作者行。`PACKAGE` 置換為專案名稱（全小寫）；`YEAR` 置換為當前年份
- **檔頭欄位**：TP robot 對檔頭欄位內容「非常挑剔」，務必填妥 `Project-Id-Version`、
  `PO-Revision-Date`、`Last-Translator`、`Language-Team`
- **提交前驗證**：使用 `msgfmt -cv yourfile.po` 檢查格式
- **著作權聲明**：部分 TP 專案要求翻譯者簽署免責聲明（disclaimer），提交前請確認
- **團隊流程**：翻譯完成後可先送交團隊郵遞清單審閱，再透過 sendpo.sh 等機制提交給 TP robot

## 三、TP 品質驗收清單

進入交付前（依 `SKILL.md`「品質自檢清單」GATE）逐項檢查：

- [ ] 檔頭開頭註解符合 TP 樣板（僅 `{PACKAGE-NAME}` 置換，其餘不變）
- [ ] 檔頭含 `Language-Team: Chinese (traditional) <zh-l10n@lists.slat.org>`
- [ ] 生成 PO 時有加 `--team "Chinese (traditional) <zh-l10n@lists.slat.org>"`
- [ ] `po_align_check.py` 退出碼 0（CLI 求助文字對齊）
- [ ] 已參考 <https://translationproject.org/html/translators.html> 的翻譯者注意事項