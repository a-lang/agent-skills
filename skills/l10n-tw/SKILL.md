---
name: l10n-tw
description: 開源專案正體中文在地化的 SOP 與工具。
---
# PO Translation — Chinese Localization Project

開源專案正體中文在地化的 SOP 與工具。

## 參考文件

翻譯前務必閱讀 [`l10n-tw-guide.md`](l10n-tw-guide.md)，內含：

- **基本守則** — 12 條翻譯品質規範（禁止機器翻譯直接提交、禁止簡轉繁不做轉換等）
- **翻譯風格與術語訂立方法** — 情境限定直譯原則、術語發想三步驟
- **譯文格式規範** — 標點符號、空格排版、快捷鍵字元、變數位置交換、日期時間格式等
- **PO 檔頭格式規範** — 檔頭必填欄位與範例
- **語言地區表示法** — 正體中文 vs 繁體中文、各語言文字體系譯法

## 目錄結構

```
l10n-tw/
├── SKILL.md                        # 本文件 — 流程說明
├── l10n-tw-guide.md                # 翻譯規範與指引（必讀）
├── terminology.md                  # 用語對照表
├── github.md                       # GitHub 操作參考
├── locale.md                       # 語言環境命名策略
├── scripts/
│   ├── po_gen.py                   # POT + translations.py → PO
│   ├── po_verify.py                # POT ↔ PO 驗證比對
│   ├── po_preflight.py             # 來源檔預檢（編碼/檔頭/fuzzy/重複）
│   ├── po_to_pot.py                # 任意 PO → POT（萃取模板）
│   ├── po_to_translations.py       # PO → translations.py（保留舊譯文）
│   ├── fix_terminology.py          # 依 terminology.md 修正 translations.py
│   ├── extract_batch.py            # 批次翻譯：PO/POT → 待翻譯 JSON
│   ├── merge_batches.py            # 批次 JSON → translations.py
│   ├── apply_translations.py       # 批次 JSON → 直接套用至 PO（替代路徑）
│   └── regression_test.py          # 回歸測試
└── ...                             # 專案目錄動態，位於 PO/POT 所在目錄
```

> **目錄約定**：專案目錄是**動態**的，以要翻譯的 PO 或 POT 檔所在目錄為主，不綁定
> `skills/l10n-tw/` 下的固定位置。所有非暫存產出檔案（`translations.py`、生成的 PO）
> 須與來源 POT 或 PO 位於同一層目錄。
>
> **翻譯檔命名**：單一專案目錄沿用 `translations.py`；若同一目錄有多個專案
> （多個 POT），使用 `<potstem>-translations.py` 配對 `<potstem>.pot`。
> `regression_test.py` 依此規則探索：優先 `<potstem>-translations.py`，
> 未配對的 POT 才回退到預設 `translations.py`。

## 核心概念

1. **所有專案的最終產出是 PO 檔**，但中間的**單一真相來源是 `translations.py`**。
2. **POT 或 PO 只是起點**：讀取後都轉成 `translations.py`，再統一產出 PO。
3. **無論來源格式或專案大小**，最後都走 `fix_terminology.py` → `po_gen.py` → `po_verify.py` + `msgfmt`。

> 批次 JSON 只是大型專案的工作草稿，最終仍須合併回 `translations.py`，
> 才能讓 `regression_test.py` 掃到並回測。

## 快速決策表

先確認三個問題：來源格式、來源語言、專案規模。然後照表執行對應流程。


| 來源格式 | 來源語言 | 規模  | 既有翻譯 | 流程                                                                                                                               |
| ---- | ---- | --- | ---- | -------------------------------------------------------------------------------------------------------------------------------- |
| POT  | —    | 小   | 無    | 手建 `translations.py` → `fix_terminology.py` → `po_gen.py` → `po_verify.py`                                                       |
| POT  | —    | 大   | 無    | `extract_batch.py` → 填 `batchN.json` → `merge_batches.py` → `fix_terminology.py` → `po_gen.py` → `po_verify.py`                  |
| PO   | 繁體中文 | 小   | 保留   | `po_to_translations.py` → `fix_terminology.py` → 手動補洞 → `po_gen.py` → `po_verify.py`                                             |
| PO   | 繁體中文 | 小   | 不保留  | 同 POT 小專案                                                                                                                        |
| PO   | 繁體中文 | 大   | 保留   | `extract_batch.py --all` → 審修 `batchN.json` → `merge_batches.py` → `fix_terminology.py` → `po_gen.py` → `po_verify.py`           |
| PO   | 繁體中文 | 大   | 不保留  | 同 POT 大專案                                                                                                                        |
| PO   | 其他語言 | 小   | 不保留  | `po_to_pot.py` → 手建 `translations.py` → `fix_terminology.py` → `po_gen.py` → `po_verify.py`                                      |
| PO   | 其他語言 | 大   | 不保留  | `po_to_pot.py` → `extract_batch.py` → 填 `batchN.json` → `merge_batches.py` → `fix_terminology.py` → `po_gen.py` → `po_verify.py` |


**規模門檻**：建議 **2000 條 msgid** 以下使用單一 `translations.py`；超過則考慮批次流程。
（實際上 2000 條以下仍可用單一檔案管理，視編輯便利性調整。）

---

## 情境 A：來源是 POT

### A1. 小專案（&lt; 2000 條）

1. 建立專案目錄，放入 `template.pot`。
2. 在相同目錄建立 `translations.py`：
  ```python
   TRANSLATIONS = {
       "msgid 原文": "正體中文翻譯",
       "Another string": "另一個字串",
       "Showing <b>%d</b> result": ["顯示 <b>%d</b> 條結果"],
   }
  ```
  - `msgid` 用 ASCII 單引號 `'` 包起。
  - 多行字串用 real `\n`。
  - 複數條目用 Python list。
3. 執行通用驗證步驟（見下方）。

### A2. 大專案（≥ 2000 條）

1. 切批：依 POT 行號範圍 `[start, end]`（1-based，含兩端）提取待翻譯條目。
  ```bash
   uv run python3 skills/l10n-tw/scripts/extract_batch.py \
     <path/to/template.pot> <batch1.json> <start1> <end1>
  ```
2. 在每個 `batchN.json` 填入譯文：`{"msgid": "正體中文翻譯"}`。
  - 不要修改 msgid 與 XML 標籤。
3. 合併為 `translations.py`：
  ```bash
   uv run python3 skills/l10n-tw/scripts/merge_batches.py \
     batch1.json batch2.json ... -o translations.py
  ```
4. 執行通用驗證步驟。

---

## 情境 B：來源是 PO（繁體中文）

先確認是否保留既有翻譯。若上游也同時提供新的 POT，請以新 POT 作為 `po_gen.py` 的輸入，
舊 PO 只當翻譯來源。

### B1. 小專案 + 保留既有翻譯

1. 從舊 PO 抽出非空譯文：
  ```bash
   uv run python3 skills/l10n-tw/scripts/po_to_translations.py \
     <path/to/old-zh_TW.po> -o translations.py
  ```
2. 執行通用驗證步驟。`po_gen.py` 會報告 missing 條目，依新 POT 補翻。

### B2. 小專案 + 不保留

同 [A1. 小專案](#a1-小專案小於-2000-條)。

### B3. 大專案 + 保留既有翻譯

1. 用 `--all` 從舊 PO 抽出全部條目（保留既有 msgstr）：
  ```bash
   uv run python3 skills/l10n-tw/scripts/extract_batch.py --all \
     <path/to/old-zh_TW.po> <batch1.json> <start1> <end1>
  ```
2. 逐批審修、補翻。
3. 合併為 `translations.py`（同 A2 步驟 3）。
4. 執行通用驗證步驟。

### B4. 大專案 + 不保留

同 [A2. 大專案](#a2-大專案大於等於-2000-條)。

---

## 情境 C：來源是 PO（其他語言）

其他語言的 PO 不保留其譯文，只當作取得 POT 與 msgid 清單的來源。

### C1. 小專案

1. 萃取 POT：
  ```bash
   uv run python3 skills/l10n-tw/scripts/po_to_pot.py \
     <path/to/source.po> -o <path/to/project.pot>
  ```
2. 手建 `translations.py`（同 A1 步驟 2）。
3. 執行通用驗證步驟。

### C2. 大專案

1. 萃取 POT（同 C1 步驟 1）。
2. 切批、填譯文、合併（同 A2 步驟 1–3）。
3. 執行通用驗證步驟。

---

## 通用驗證步驟

無論哪個情境，完成翻譯後都依序執行：

### 1. 用語修正

```bash
uv run python3 skills/l10n-tw/scripts/fix_terminology.py \
  <path/to/translations.py>
```

預設會讀取同層的 `terminology.md`；若要指定其他術語表，用
`--terms <path/to/terminology.md>`。

> 特別是從既有 PO 起步時，簡轉繁會帶入中國用語，必須跑過一次。

**完成標準**：輸出顯示「All target terms cleaned」，無剩餘禁用用語。

### 2. 生成 PO

```bash
uv run python3 skills/l10n-tw/scripts/po_gen.py \
  <path/to/template.pot> \
  -t <path/to/translations.py> \
  -o <path/to/output.zh_TW.po>
```

> 輸出路徑原則上應與來源 POT 同層目錄；專案另有指定工作目錄時，依指定目錄輸出。
>
> **Translation Project 專案**：標頭須符合 TP 格式，生成時務必加上
> `--team "Chinese (traditional) <zh-l10n@lists.slat.org>"`。

**完成標準**：輸出顯示「All entries translated」，無 missing，且輸出檔案位於與 POT 相同（或專案指定）的目錄。

### 3. 驗證 PO

```bash
uv run python3 skills/l10n-tw/scripts/po_verify.py \
  <path/to/template.pot> <path/to/output.po> --comments

msgfmt --statistics -cv <path/to/output.po> -o /dev/null
```

確認：

- Entry count matches（無遺漏、無多餘）
- Coverage 100%
- No fuzzy markers
- 註解行保留
- `msgfmt` 無 c-format 錯誤
- 格式符合 `l10n-tw-guide.md` 規範

**完成標準**：`po_verify.py` 與 `msgfmt` 皆退出碼 0。

### 4. 回歸測試（修改腳本後必跑）

```bash
uv run python3 skills/l10n-tw/scripts/regression_test.py
```

**完成標準**：所有專案顯示 `[OK]`。

---

## 腳本參考


| 腳本                      | 用途       | 輸入                                 | 輸出                     |
| ----------------------- | -------- | ---------------------------------- | ---------------------- |
| `po_gen.py`             | 生成 PO    | `template.pot` + `translations.py` | `zh_TW.po`             |
| `po_verify.py`          | 驗證 PO    | `template.pot` + `zh_TW.po`        | 報告 + exit code         |
| `po_preflight.py`       | 來源檔預檢    | 來源 `.pot`／`.po`                    | 報告 + exit code         |
| `po_to_pot.py`          | 萃取 POT   | 任意 PO                              | 無翻譯的 POT               |
| `po_to_translations.py` | 抽出舊譯文    | 繁體中文 PO                            | `translations.py`      |
| `extract_batch.py`      | 切批       | PO 或 POT                           | `batchN.json`          |
| `merge_batches.py`      | 合併批次     | 多個 `batchN.json`                   | `translations.py`      |
| `apply_translations.py` | 直接套用至 PO | `batchN.json` + 既有 PO              | 更新後的 PO                |
| `fix_terminology.py`    | 用語正規化    | `translations.py`                  | 修正後的 `translations.py` |
| `regression_test.py`    | 回歸測試     | 所有專案                               | 比對報告                   |


### 替代路徑：apply_translations.py

`merge_batches.py` + `po_gen.py` 是標準流程；若你偏好直接編輯 PO 檔，
也可用 `apply_translations.py` 把 `batchN.json` 直接套用至既有 PO：

```bash
uv run python3 skills/l10n-tw/scripts/apply_translations.py \
  <batchN.json> -o <path/to/output.po>
```

注意：此路徑不產出 `translations.py`，因此 `regression_test.py` 不會涵蓋這些專案。

---

## Gettext 工具參考

本專案的 `po_gen.py` 與 `po_verify.py` 封裝了大部分 gettext 操作，以下列出手動使用 gettext 工具組的常見情境與命令，供參考與除錯使用。

### 安裝 gettext

```bash
# Linux (Debian/Ubuntu)
sudo apt install gettext

# macOS
brew install gettext

# Windows (Scoop)
scoop install gettext
```

驗證安裝：`gettext -V`

### PO 檔結構說明

每筆翻譯條目包含以下部分：

```po
#. Translators: 開發者留給翻譯者的提示
#: src/main.c:123
msgctxt "ContextMenu"       # 區別相同 msgid 的不同情境（選用）
msgid "Split"               # 原文（不可修改）
msgstr "分屏"               # 譯文
```

- `msgid`：原文，**不可修改**。即使有明顯錯誤也應回報上游，而非直接修改
- `msgstr`：你的翻譯
- `msgctxt`：當相同英文在不同情境需不同譯文時使用
- `#.`：開發者註解（`TRANSLATORS:` 開頭提示尤為重要）
- `#:`：原始碼位置參考
- `#` （無後綴句點）：譯者自行留下的註解，僅供同語種譯者參考

### 常用命令

#### msgfmt — PO 格式編譯產出 messages.mo

```bash
msgfmt --statistics -cv zh_TW.po
```

- 編譯 PO → MO 檔（預設輸出 `messages.mo`）
- `--statistics`：統計已翻譯/未翻譯/模糊條目數
- `-c`：驗證 C 語言格式字串（`%s`、`%d` 是否正確對應）
- `-v`：詳細輸出

若輸出 `0 translated messages, 0 untranslated, 0 fuzzy` 以外的訊息，表示 PO 檔有問題。

#### msgmerge — POT 合併與格式標準化

```bash
msgmerge --no-wrap -U zh_TW.po new.pot
```

- 將既有 `.po` 與新版 `.pot` 合併，保留已翻譯條目
- `--no-wrap`：不自動換列
- `-U`：直接更新檔案

適用於需要手動更新現有 `.po` 的情境（`po_gen.py` 已自動處理此流程）。

#### msginit — 新建 PO 檔

```bash
msginit -i template.pot -l zh_TW.UTF-8 -o zh_TW.po
```

- 從 POT 產生初始 PO 檔，自動填入檔頭資訊
- `-i`：輸入 POT 檔
- `-l`：語言代碼（建議加上 `.UTF-8` 確保編碼正確）
- `-o`：輸出檔名

#### iconv / msgconv — 編碼轉換

```bash
# iconv（通用編碼轉換）
iconv -f big5 -t utf-8 input.po > output.po

# msgconv（專用於 PO 檔）
msgconv -t utf-8 input.po -o output.po
```

現代專案已全面使用 UTF-8，通常不需要此步驟。

### 格式字串與變數位置交換

GNOME `c-format` 專案中，交換變數位置需標明原文順序：

```po
msgid "%d articles match rule %d"
msgstr "符合規則 %2$d 的文章有 %1$d 個"
```

KDE `qt-format` 則直接交換：

```po
msgid "%1 articles match rule %2"
msgstr "符合規則 %2 的文章有 %1 個"
```

詳見 [`l10n-tw-guide.md`](l10n-tw-guide.md#34-變數位置交換) 的完整說明。

---

## Workflow

### 制定翻譯計畫

動手翻譯前，先與使用者**共同**制定翻譯計畫：把以下事項整理成一份計畫摘要，**展示給使用者確認後**，才進入 Phase 1。不要跳過此步驟直接開始翻譯。

1. **來源格式與條數** — 確認來源是 POT 或 PO、來源語言、需翻譯的條數；≥ 2000 條時採用批次翻譯（每批 100–160 條）
2. **情境與流程選定** — 對照「快速決策表」點出將走的情境（A／B／C）與規模（小／大）
3. **既有翻譯去留** — 來源為正體中文 PO 且部分已有翻譯時，確認保留或重新翻譯
  - 保留：使用本文件「情境 B」對應流程
  - 重新翻譯：使用「情境 A」或「情境 C」流程
4. **提交方式** — 確認完成後如何交付：手動上傳（如 Weblate 網頁上傳 PO）、git commit + PR（慣例見 `github.md`）、或其他管道
5. **分批切割**（大專案適用） — 列出預計批次範圍
6. **翻譯者身份（Last-Translator）** — 產出 PO 前確認翻譯者身份，來源依序為：
  - `--translator` 參數 → `L10N_TW_TRANSLATOR` 環境變數 → `skills/l10n-tw/.env` 設定檔
  - 三者皆無時**詢問使用者如何處置**：提供姓名與 email（可選擇寫入 `skills/l10n-tw/.env` 永久保留，該檔已被 `.gitignore` 排除），或本次以佔位符 `Translator Name <translator@example.org>` 進行（交付前須另行處理）

**[GATE] 翻譯計畫確認** — 將上述摘要展示給使用者，明確等使用者確認後才開始 Phase 1。計畫未經確認，不得進行翻譯。

- **完成標準：** 來源格式、條數、情境/流程、是否批次、既有翻譯去留、提交方式、翻譯者身份皆經使用者確認

### Phase 1 — 前置準備

1. **Reconnaissance** — 確認 i18n 框架（gettext / GResource XML / Blueprint）、locale 命名慣例（看既有 .po 檔名或 LINGUAS）、POT msgid 數量
  - **完成標準：** i18n 框架已確認、locale 命名已確認、POT msgid 數量已記錄
2. **Fork** — 透過 `gh repo fork <upstream> --remote-name fork`，再重構 remote（origin=fork, upstream=upstream）。遠端命名慣例見 `github.md`
  - **完成標準：** `git remote -v` 顯示正確的 origin 與 upstream
3. **取得 POT** — 從上游取得最新的 POT；若上游沒有 POT，只有既有 PO 檔，則用 `po_to_pot.py` 萃取
  - **完成標準：** 專案工作目錄中存在 `<project>.pot`
4. **來源檔格式驗證** — 建立 `translations.py` 之前，先確認來源 POT／PO 內容格式符合規範，否則後續 `po_gen.py`／`po_verify.py`／`po_to_pot.py`／`po_to_translations.py` 會失敗或靜默產出錯誤結果。
  ```bash
   uv run python3 skills/l10n-tw/scripts/po_preflight.py <path/to/source.pot_or_po>
  ```

   `po_preflight.py` 會檢查：編碼與 BOM、檔頭條目、必填檔頭欄位（`Content-Type`、`Plural-Forms` 等）、`msgfmt --statistics -cv` 格式合法性、檔頭／條目級 `#, fuzzy` 旗標、重複 `(msgctxt, msgid)`、過時 `#~` 條目、行尾。檔頭格式基準見 [`l10n-tw-guide.md`](l10n-tw-guide.md)「四、PO 檔頭格式規範」。
  - **異常處置（軟停止）** — 腳本退出碼 1 時，把回報的異常清單展示給使用者，由使用者決定先修正來源檔或以現況繼續；不強制中止流程
  - **完成標準：** `po_preflight.py` 退出碼 0；若退出碼 1，所有異常已展示給使用者並取得處置決定
5. **建立專案目錄** — 將 `<project>.pot` 放入專案目錄，建立 `translations.py`。預設所有非暫存產出檔案（`translations.py`、生成的 PO）與 POT 位於同一層
  - 專案目錄預設與來源檔案 `<project>.pot` 或 `<project>.po` 同一層
  - 如果另有指定工作目錄者，以指定目錄為優先。
  - **完成標準：** 專案目錄包含 `<project>.pot` 與 `translations.py`

### Phase 2 — 翻譯

6. **依情境選擇流程** — 對照「快速決策表」選擇 A、B、C 情境，並依規模選擇小／大專案流程。
  - 翻譯品質要求：用語一致性參考 `terminology.md`、格式規範與風格指引參考 `l10n-tw-guide.md`、禁止直接從 zh_CN 轉換。
  - **完成標準：** 所有 msgid 皆有翻譯，無直接從 zh_CN 轉換的內容，符合 `l10n-tw-guide.md` 規範

### Phase 3 — 生成與驗證

7. 執行「通用驗證步驟」：用語修正 → `po_gen.py` → `po_verify.py` + `msgfmt` → `regression_test.py`
  - `msgfmt` 驗證用參數：`-o /dev/null`，避免產生暫存檔 `messages.mo`
  - **完成標準：** `po_verify.py` 與 `msgfmt` 皆退出碼 0，且回歸測試所有專案 `[OK]`

### Phase 4 — 交付（事先詢問）

交付前須先確認使用者選擇哪種方式。

- **方式一：commit/PR** — 適用 git repo
  1. **[GATE] Show PO to user** — 展示產出的 PO 成品要先審核，**確認後才能繼續下一步**
  2. **Branch** — 命名 `zh-tw-translation`；monorepo 用 `<project>-zh-tw` 避免混淆。慣例見 `github.md`
    - **完成標準：** branch 已建立，名稱符合慣例
  3. **[GATE] Show diff + commit message** — `git diff --cached` 展示變更，同時展示 commit message（`git commit -m "..."`），等確認後才能 commit
  4. **[GATE] Show PR draft** — 展示 PR title + body 草稿，等確認後才能 push 與 `gh pr create`
- **方式二：手動上傳** — 適用 Weblate 等其他翻譯平台
  - 只輸出 PO 檔，不做其他後續處理

---

## GitHub Operations

遠端設定、分支命名、commit/PR 格式等詳細操作請見 [`github.md`](github.md)。

## 重要慣例

- **LINGUAS 檔案**：插入字母順序（zh_TW 在 zh_CN 後面）。注意 line ending：GNOME 專案可能用 CRLF
- **用語一致性**：參考 `terminology.md`。credential=憑證、folder=資料夾、open=開啟、configure=設定
- **語言環境命名**：跟著上游走，不幫上游決定標準。請見 [`locale.md`](locale.md) 了解 zh_TW 與 zh_Hant 的選擇原則
- **不要直接從 zh_CN 轉換**：簡→繁會帶入中國用語（軟件/文件/信息），逐條從 POT 翻
- **翻譯品質守則**：翻譯前詳閱 [`l10n-tw-guide.md`](l10n-tw-guide.md)，特別是基本守則（禁止機器/AI 直接提交、禁止簡轉繁、用語前後一致等）
- **產出檔案目錄**：專案目錄動態，以要翻譯的 PO/POT 所在目錄為主；產出檔案（`translations.py`、生成的 PO）與來源 POT 位於同一層目錄
- **驗證暫存檔清理**：若任務中沒有要輸出 `.mo` 檔，純為驗證用途而產生的 `messages.mo`（`msgfmt` 預設輸出）應於作業後清理

---

## 已知坑

1. **多行 msgid** — PO 標準格式把長字串跨多行續寫。`po_gen.py` 有對應支援，但 `po_verify` 若回報 MISSING/EXTRA 時先確認是否為多行 msgid 問題
2. `**More Colors...` vs `More Colors…`** — 三個點（ASCII `...`）與 Unicode 省略號 `…` 是不同的 msgid，兩者都要有對應翻譯
3. `**translations.py` 與 committed PO 可能 drift** — 手動編輯 PO 後 `translations.py` 不會自動同步。修改技能腳本後應執行 `regression_test.py`，由 drift 導致的差異須回寫到 `translations.py` 再重新生成 PO
4. `**#` 開頭的 fuzzy flag** — 產生 PO 後須確認 header 的 `#, fuzzy` 已移除
5. **execute_code 不載入 env** — 需要 gh CLI / git 操作時要用 terminal 工具
6. **跳脫字元** — `\n`、`\"`、`\\` 在 PO 裡有特殊意義
7. **翻譯用語一致性** — 同一專案內不要同一個英文詞用不同中文翻法
8. **Locale 命名混亂** — `zh_TW`（GNU gettext 傳統） vs `zh_Hant`（BCP 47 現代標準），依上游決定。詳見 `locale.md`
9. **舊 PO 譯文可能與新 POT 對不上** — 上游更新後 msgid 可能變動；轉成 `translations.py` 後用 `po_gen.py` 的 missing 報告補洞
10. **批次流程一定要合併回 `translations.py`** — 若停留在 `apply_translations.py` 產出的 PO，`regression_test.py` 不會涵蓋

