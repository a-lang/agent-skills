# Locale 命名策略

繁體中文的 PO 檔名有兩套標準並存，取決於上游專案用哪一套。

## BCP 47（現代標準）— `zh_Hant`

**IETF BCP 47** 認為繁體 vs 簡體是 **script（文字）差異**，不是 region（地區）差異。因此用 script subtag 表達：

| 語系 | BCP 47 | 覆蓋範圍 |
|------|--------|---------|
| 繁體中文 | `zh-Hant` | 臺灣、香港、澳門所有正體中文使用者 |
| 簡體中文 | `zh-Hans` | 中國、新加坡、馬來西亞所有簡體中文使用者 |

使用此標準的專案：**GNOME／Weblate 生態系**（Burn-My-Windows 上游、Parabolic）

## GNU gettext（傳統）— `zh_TW`

GNU gettext 的 locale 格式是 `ll_CC`（語言\_國家），使用地區代碼：

| 語系 | GNU gettext | 代表 |
|------|------------|------|
| 繁體中文 | `zh_TW` | 臺灣正體 |
| 簡體中文 | `zh_CN` | 中國簡體 |

使用此標準的專案：**Cinnamon Spices**（歷史遺留，但為該專案慣例）

## 實戰原則

> **跟著上游走，不幫上游決定標準。**

| 狀況 | 做法 |
|------|------|
| 上游用 `zh_TW` | 用 `zh_TW`（如 Cinnamon Spices） |
| 上游用 `zh_Hant` | 用 `zh_Hant`（如 Weblate 專案） |
| 不確定 | 查 `LINGUAS` 或既有 PO 檔名來判斷 |

兩種命名都可以運作，重點是保持一致。
