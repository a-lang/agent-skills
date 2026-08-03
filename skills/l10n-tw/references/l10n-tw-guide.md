# 自由軟體正體中文化工作流程規範與指引

本文件合併自社群共筆：

- [自由軟體正體中文化工作流程規範](https://hackmd.io/@l10n-tw/translation_guidelines)
- [自由軟體正體中文化翻譯風格指引](https://hackmd.io/@l10n-tw/translation_style_guide)

---

## 一、基本守則

1. **信實傳遞文化背景** — 貼切表達原作者的意思，同時以自身語言流暢表達
2. **調整語序** — 英文句法與中文句法經常前後相反，請適當調整，不逐句逐字對照
3. **句子意譯、術語直譯** — 句子以整體意譯為主；關鍵術語以情境限定下的直譯為原則。
   Menu 依情境譯為「選單」而非「菜單」；Render 譯為「算繪」而非「渲染」
4. **原文不清則補入脈絡** — 依上下文和註解推斷，填補訊息。"print error" →「列印發生錯誤」
5. **補入即止** — 不衍生多餘解釋
6. **約定俗成語直譯** — Bug → 臭蟲、Patch → 補丁、Virus → 病毒、Worm → 蠕蟲
7. **專業黑話維持原文或改寫** — lint 維持原文或改稱「梳理」，linter →「梳理器」
8. **多人專案減少個人風格** — 以「譯完原文關鍵詞意義，並整體貼切表達」為主
9. **前後一致** — 相同術語必須使用相同譯詞，盡可能一對一對應
10. **敬語** — 程式介面用「您」；網頁可用「你」
11. **禁止直接使用機器/AI 翻譯成果** — 可用來輔助理解，但不得未經思考直接提交
12. **禁止簡轉繁不做轉換** — 可參考簡體翻譯輔助理解，但必須逐條從 POT 重新翻譯

---

## 二、翻譯風格與術語訂立

### 核心心法

> **句子結構以整體意譯為佳，並以流暢的中文表達。**
> **句中關鍵詞或術語，先以情境限定直譯為基本原則出發。**

### 常見翻譯風格

| 風格 | 說明 | 範例 |
|------|------|-------|
| **直譯** | 情境對應下的對等形式翻譯 | Menu → 選單（對等直譯）；Menu → 菜單（不對等直譯） |
| **意譯** | 理解後換句話說，精確對應但限特定情境 | Help → 說明 |
| **改寫（作用理解式）** | 依操作經驗重新發想，跳脫原文 | Breadcrumb → 網址導覽標記 |
| **直譯加改寫** | 合譯法，保留原文譬喻再加說明 | Breadcrumb → 麵包屑導覽 |
| **維持原文** | 極專業或無共同脈絡的詞 | mipmap 維持原文 |

### 術語翻譯訂立三步驟

1. **理解** — 查詢 Wikipedia、英英字典、程式文件、Release Note，先弄懂詞語的原理與概念
2. **貼近** — 參考劍橋英漢字典、教育部國語辭典、樂詞網等，逼近出適當中文詞語
3. **發想** — 先了解英文單字的泛化概念，定下詞眼為骨幹，添補他字為肉
   - Dodge → 遮亮（遮+亮）、Burn → 曝深（曝+深）

### 譯詞識讀要求

翻譯的識讀性目標，應以國中程度為主。例如 Regular expression 不採用冷僻的「正則表達式」，而建議譯為「常規表達式」。

### 避免重複對應

相同術語前後一致、一對一對應，避免同一個中文詞彙重複與多個不同的英文術語對應。

### 英語模糊泛用 vs 中文限定特化

英文詞語常有「模糊泛用」特性（一詞多義），而中文詞語則有「限定特化」特性（定語指向）。
翻譯時應區別英文詞的不同情境，對應翻譯成不同的中文詞，而非拿一個已限定特化的中文詞重新定義。

---

## 三、譯文格式規範

### 3.1 標點符號

1. 英文逗號 `,` → 中文「，」或「、」
2. 英文句號 `.` → 中文「。」（多數情況）
3. GUI 程式中 `"%s"` → 「%s」（全形引號）；CLI 程式中同樣使用全形引號「」
4. 命令列範例若為英文語境（如 `"command -p arg"`），引號可保留原樣
5. 英文 `:` → 全形「：」（非標點分隔符則保留半形，如時間 `12:30`）
6. 半形小括號 `()` 內若為中文 → 全形（）；內為英文 → 半形 `()`
   - 半形括號前後有中英文字時加空格；前後為標點或捷徑字元時不加
7. 刪節號 `...` 可保持不變；選項內文用一個 `…`，內文可用兩個 `……`
8. 破折號 `--` 可保持不變或使用全形破折號 ——
9. 選單路徑用上下引號括起，如「系統 > 管理」；不建議用 `[]` 方括號
10. 軟體名稱用書名號《》，功能選項用「」
11. `A, B, or C` 類語句 → 「A、B、C 等」
12. `%q` 標記不需另加引號

### 3.2 空格排版

- 中文與英文、中文與阿拉伯數字之間**加入一個半形空格**
- 半形括號和半形引號與中英文字鄰接處**加入空格**
- 斜體 `<em>` 前後若連接文字則加空格；連接標點則不加
- 空格置於 HTML 標籤外側

```po
msgstr "正在安裝 %1 的驅動程式"
msgstr "原始創意和作者 (KDE1)"
```

### 3.3 選單快捷鍵字元

- 捷徑字元一律大寫，用小括號括起放在選單文字後面
- KDE 前綴 `&` → `清除(&L)`
- GNOME 前綴 `_` → `設定(_S)...`
- 若翻譯保留原文單詞且該單詞含快捷鍵，則保留原文方式：
  - `_CDDB Now` → `立刻取得 _CDDB`

### 3.4 變數位置交換

必要時調整變數順序以符合中文語法。

**KDE qt-format：**
```po
msgid "%1 articles match rule %2"
msgstr "符合規則 %2 的文章有 %1 個"
```

**GNOME c-format：** 用 `%1$d` 標明原文位置
```po
msgid "%d articles match rule %d"
msgstr "符合規則 %2$d 的文章有 %1$d 個"
```

**進度條常見格式：**
```
%1 of %2, %3 remaining → %1 / %2，剩餘 %3 個
%1 of %2, %3 remaining → 第 %1 個，共 %2 個，剩餘 %3
```

### 3.5 開發者註解

`#. TRANSLATORS:` 開頭的行是給翻譯者的提示，請在翻譯過程中留意。

```po
#. TRANSLATORS: ls output needs to be aligned for ease of reading,
#. so be wary of using variable width fields from the locale.
msgid "%b %e %Y"
msgstr "%Y年%b%e日"
```

### 3.6 程式語言格式與 msgctxt

- `c-format`、`python-format`、`qt-format` 等標記代表該字串需按指定語言格式輸出
- `msgctxt` 給出字串所處的不同情境，同一 msgid 可因不同 msgctxt 有不同的譯文

### 3.7 換列位置

原文有 `#, c-format` 標記或 `\n` 強制換列時，需手動調整譯文換列。譯文長度儘量不大於原文長度。

```po
#, c-format
msgid ""
"Error opening file '%s':\n"
"%s"
msgstr ""
"開啟檔案「%s」時發生錯誤：\n"
"%s"
```

### 3.8 translator-credits 條目

```po
msgid "translator-credits"
msgstr ""
"Telsa Gwynne <hobbit@aloss.ukuug.org.uk>, 2011.\n"
"Dafydd Harries <daf@muse.19inch.net>, 2012."
```

### 3.9 特殊字元

**轉義字元：** `\n`（換列）、`\\`（反斜線）、`\t`（製表符）、`\"`（半形雙引號）

**XML 保留字元：**
- `&lt;` → `<`
- `&gt;` → `>`
- `&amp;` → `&`

**TRUE 和 FALSE：** 出現於 gtk+ 和 Gconf 時不要翻譯。

### 3.10 日期與時間表示法

**基本原則：** 年月日順序，年份四位數，月日帶前導零，24 小時制。

**常見格式對照：**

| 原文 msgid | 建議譯文 |
|-----------|---------|
| `%A` | `%A`（保留，strftime 會自動輸出中文星期） |
| `%a %b %e` | `%b%e日（%a）` |
| `%A, %B %e, %Y` | `%Y年%b%e日%A` |
| `%d %B %Y` | `%Y年%b%d日` |
| `%l:%M:%S %p` | `%p%l:%M:%S` |
| `%R:%S` | `%R:%S`（不變） |

### 3.11 CLI 程式對齊

CLI 參數對齊應使用 Tab 製表符，而非空格。請多測試實際執行結果。

### 3.12 模糊譯文（`#, fuzzy`）

`#, fuzzy` 標記表示譯文由工具猜測或譯者無把握。**必須修正譯文後移除 fuzzy 標記**，否則該條目不會顯示在程式介面上。

```po
#, fuzzy
msgid "Get Tagged Articles"
msgstr "取得文章"
```
修正後：
```po
msgid "Get Tagged Articles"
msgstr "取得已標籤文章"
```

清除時注意保留 `c-format` 等其他標記。

### 3.13 已淘汰譯文

以 `#~` 開頭，由 `msgmerge` 自動產生。建議保留，因為未來版本可能重新使用。

---

## 四、PO 檔頭格式規範

### 編碼

一律使用 UTF-8。確保檔頭 `charset=UTF-8` 與檔案實際編碼一致。

### 檔頭範例

```po
# Chinese translations for <project> package
# Copyright (C) <year> Free Software Foundation, Inc.
# This file is distributed under the same license as the <project> package.
# <Translator Name> <email>, <year>.
#
msgid ""
msgstr ""
"Project-Id-Version: <project> <version>\n"
"Report-Msgid-Bugs-To: \n"
"POT-Creation-Date: 2024-01-01 12:00+0000\n"
"PO-Revision-Date: 2024-06-01 10:00+0800\n"
"Last-Translator: Your Name <email>\n"
"Language-Team: Chinese (traditional) <zh-l10n@lists.slat.org>\n"
"Language: zh_TW\n"
"MIME-Version: 1.0\n"
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"
"Plural-Forms: nplurals=1; plural=0;\n"
```

**重點：**
- `Project-Id-Version`：填入專案名稱與版本
- `PO-Revision-Date`：翻譯完成時間 (`+0800` 表示台北時區)
- `Last-Translator`：你的名字與 email
- `Language-Team`：翻譯小組郵遞清單
- `Plural-Forms`：正體中文用 `nplurals=1; plural=0;`
- 確認 `#, fuzzy` 已從檔頭移除

---

## 五、語言地區表示法

### Traditional Chinese 的譯法

- 台灣：**正體中文**
- 香港：**繁體中文**

### 語言列表翻譯

| 原文 | 建議譯文 |
|------|---------|
| Chinese | 漢語 |
| Chinese (Simplified Han script) | 漢語（簡化漢字） |
| Chinese (Traditional Han script) | 漢語（正體漢字） |
| Chinese (Simplified Han script, Singapore) | 漢語（簡化漢字，新加坡） |
| Chinese (Traditional Han script, Hong Kong) | 漢語（正體漢字，香港） |
| Chinese (traditional) / Chinese (simplified) | 漢語（正體字）/ 漢語（簡體字） |
| Minnan (Traditional Han script) | 閩南語（傳統漢字） |
| Minnan (Pe̍h-ōe-jī) | 閩南語（白話字） |
| Minnan (Tâi-lô) | 閩南語（臺羅拼音） |
| Literary Chinese | 漢語文言文 |

### 其他語言文字體系

| 原文 | 建議譯文 |
|------|---------|
| Japanese | 日本語（或日語） |
| Vietnamese | 越南語 |
| Serbian Latin / Serbian Cyrillic | 塞爾維亞語拉丁字 / 塞爾維亞語西里爾字 |
| Norwegian Bokmål | 挪威語書面文（推薦）或 挪威語巴克摩文 |
| Norwegian Nynorsk | 挪威語新挪威文（推薦）或 挪威語耐諾斯克文 |

原則：先直接翻譯語言名稱，有文字體系變異時再補上「某某字」。
