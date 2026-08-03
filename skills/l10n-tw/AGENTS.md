# AGENTS.md — l10n-tw

l10n-tw 技能的開發規則與指令。

## 這是什麼

入口點是 `SKILL.md`，其中包含 SOP。助手腳本在 `scripts/` 中。

## 指令

所有指令都在 `scripts/` 中，並從**技能目錄**執行（技能目錄＝儲存庫的 `skills/l10n-tw/`）。
詳細情境流程（來源格式、既有翻譯去留、大／小專案）請見 `SKILL.md`。

```bash
# 來源檔預檢：翻譯前先驗證 POT／PO 格式（編碼/檔頭/fuzzy/重複/msgfmt）
uv run python3 scripts/po_preflight.py <path/to/source.pot_or_po>

# 生成 PO：POT + translations.py → PO
uv run python3 scripts/po_gen.py <path/to/template.pot> -t <path/to/translations.py> -o <path/to/output-zh_TW.po>

# 驗證：檢查是否 100% 覆蓋、無模糊標記、註解保留
uv run python3 scripts/po_verify.py <path/to/template.pot> <path/to/output.po> --comments

# 回歸測試：重新生成所有專案並比對已提交的 PO（在修改腳本後執行）
uv run python3 scripts/regression_test.py

# 從既有繁體中文 PO 抽出 translations.py
uv run python3 scripts/po_to_translations.py <path/to/old-zh_TW.po> -o <path/to/translations.py>

# 合併多個批次 JSON 為 translations.py
uv run python3 scripts/merge_batches.py <batch1.json> <batch2.json> ... -o <path/to/translations.py>

# 依 references/terminology.md 統一用語
uv run python3 scripts/fix_terminology.py <path/to/translations.py>
```

- `po_verify.py`：退出碼 0 = 沒問題，1 = 有問題
- `po_preflight.py`：退出碼 0 = 來源檔乾淨，1 = 發現問題（軟停止，回報使用者決定修正或繼續）
- `po_gen.py` 接受 `.py`（匯出 `TRANSLATIONS` dict）或 `.json`（透過 `-j`）作為翻譯來源
- 腳本使用 `python3`，無需手動啟用 venv —— `uv run` 自動處理
- 回歸測試自動探索 (POT, translations 檔) 專案對：優先 `<potstem>-translations.py`，未配對的 POT 回退到預設 `translations.py`

## 專案目錄慣例

專案目錄是動態的，以要翻譯的 PO 或 POT 檔所在目錄為主，不綁定技能目錄下的固定位置。所有非暫存產出檔案（`translations.py`、生成的 PO）須與來源 POT 或 PO 位於同一層目錄。若專案另有指定工作目錄，以指定目錄為優先。

## 閘門（審查點）——依 SKILL.md

所有四項操作在執行前都需要使用者確認：
1. 翻譯計畫（來源格式／條數／情境流程／既有翻譯去留／提交方式／翻譯者身份）
2. 生成的 PO 檔案輸出
3. git diff + commit message
4. PR title + body 草稿

## 語言環境命名

遵循上游規則——請勿猜測。檢查現有的 PO 檔案名稱或 `LINGUAS`。詳見 `references/locale.md`。

## Python 虛擬環境

使用 `uv` 管理。`.venv` 位於儲存庫根目錄（建立與安裝套件時從儲存庫根執行）：

```bash
uv venv              # 建立 .venv（首次）
uv pip install polib # 安裝回歸測試所需套件
uv run python3 ...   # 在 venv 內執行，無需手動 activate
```

`polib` 是回歸測試 (`regression_test.py`) 所需的唯一非標準函式庫套件。
