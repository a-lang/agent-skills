# Gettext 工具參考

本專案的 `po_gen.py` 與 `po_verify.py` 封裝了大部分 gettext 操作，以下列出手動使用 gettext 工具組的常見情境與命令，供參考與除錯使用。

## 安裝 gettext

```bash
# Linux (Debian/Ubuntu)
sudo apt install gettext

# macOS
brew install gettext

# Windows (Scoop)
scoop install gettext
```

驗證安裝：`gettext -V`

## PO 檔結構說明

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

## 常用命令

### msgfmt — PO 格式編譯產出 messages.mo

```bash
msgfmt --statistics -cv zh_TW.po
```

- 編譯 PO → MO 檔（預設輸出 `messages.mo`）
- `--statistics`：統計已翻譯/未翻譯/模糊條目數
- `-c`：驗證 C 語言格式字串（`%s`、`%d` 是否正確對應）
- `-v`：詳細輸出

若輸出 `0 translated messages, 0 untranslated, 0 fuzzy` 以外的訊息，表示 PO 檔有問題。

### msgmerge — POT 合併與格式標準化

```bash
msgmerge --no-wrap -U zh_TW.po new.pot
```

- 將既有 `.po` 與新版 `.pot` 合併，保留已翻譯條目
- `--no-wrap`：不自動換列
- `-U`：直接更新檔案

適用於需要手動更新現有 `.po` 的情境（`po_gen.py` 已自動處理此流程）。

### msginit — 新建 PO 檔

```bash
msginit -i template.pot -l zh_TW.UTF-8 -o zh_TW.po
```

- 從 POT 產生初始 PO 檔，自動填入檔頭資訊
- `-i`：輸入 POT 檔
- `-l`：語言代碼（建議加上 `.UTF-8` 確保編碼正確）
- `-o`：輸出檔名

### iconv / msgconv — 編碼轉換

```bash
# iconv（通用編碼轉換）
iconv -f big5 -t utf-8 input.po > output.po

# msgconv（專用於 PO 檔）
msgconv -t utf-8 input.po -o output.po
```

現代專案已全面使用 UTF-8，通常不需要此步驟。

## 格式字串與變數位置交換

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
