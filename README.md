# agent-skills

**Agent Skills 儲存庫**，每個技能自含說明與工具。

## 技能


| 技能      | 說明             | 目錄                |
| ------- | -------------- | ----------------- |
| l10n-tw | 正體中文（zh-TW）在地化 | `skills/l10n-tw/` |


## 快速安裝

```bash
# 專案模式（預設）：安裝至目前專案（如 .claude/skills/），可隨專案提交與團隊共享
npx skills add https://github.com/a-lang/agent-skills --skill l10n-tw

# 全域模式（-g）：安裝至使用者目錄（如 ~/.claude/skills/），跨專案可用
npx skills add https://github.com/a-lang/agent-skills --skill l10n-tw -g
```

## 開發

技能結構與開發規則見頂層 `AGENTS.md`。

## 翻譯成果

以 l10n-tw 技能完成的正體中文（zh-TW）翻譯統計（截至 2026-08-04）：


| 專案                                                               | 檔   | 條數     | 字元      |
| ---------------------------------------------------------------- | --- | ------ | ------- |
| Fedora（mate-desktop、sssd、input-pad、rpminspect、entangle、virt-top） | 16  | 12,991 | 534,347 |
| GNOME（amberol/apostrophe/boatswain）                              | 3   | 494    | 4,253   |
| font-manager                                                     | 2   | 791    | 11,476  |
| lutris                                                           | 1   | 1,772  | 31,697  |
| TranslationProject（a2ps/anubis/msmtp）                            | 3   | 787    | 17,193  |
| 合計                                                               | 25  | 16,835 | 598,966 |


### 語系檔條數前三高


| 排名  | 語系檔                               | 條數    |
| --- | --------------------------------- | ----- |
| 1   | mate-user-guide-content-zh_TW.po  | 3,225 |
| 2   | sssd-sssd-manpage-master-zh_TW.po | 2,799 |
| 3   | lutris-zh_TW.po                   | 1,772 |


