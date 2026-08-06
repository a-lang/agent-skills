# l10n-tw

適用大部分 AI Agent 平台的正體中文（zh-TW）在地化 **Agent Skill**。

基於 [Agent Skills 開放標準](https://agentskills.io/specification)：一個含 `SKILL.md` 的目錄，隨附翻譯規範文件與 10 支 Python 工具腳本。可原封不動安裝到 Claude Code、OpenCode、Gemini CLI、Cursor、GitHub Copilot、Codex 等支援 Agent Skills 的平台。

## 特點

- **完整 SOP** — `SKILL.md` 內建翻譯流程：情境決策表（來源格式 × 規模 × 既有翻譯去留）、前置預檢、批次翻譯、驗證閘門、交付流程
- **品質保證** — `po_verify.py` + `msgfmt` 雙重驗證，100% 覆蓋率、無 fuzzy 標記、格式字串正確
- **翻譯規範** — 附 `references/l10n-tw-guide.md`（翻譯守則與格式規範）、`references/terminology.md`（用語對照）、`references/locale.md`（語言環境命名策略）
- **工具鏈齊全** — 預檢、POT 萃取、翻譯生成、批次合併、用語正規化、回歸測試一應俱全
- **跨平台** — 標準 `SKILL.md` 格式，可安裝於大部分支援 Agent Skills 的 AI Agent 平台
- **規則明確** — 翻譯前必須與使用者確認翻譯計畫，交付前展示產出與 PR 草稿（Gate 流程）
- **遵循 l10n.tw 官方作業規範** — 翻譯守則、風格與格式規範以台灣 l10n.tw 社群訂立的標準為依據

## 規範來源

本技能遵循 l10n.tw 社群的作業規範，翻譯守則、風格與格式規範皆以其為準：

| 規範 | 說明 |
|---|---|
| [自由軟體正體中文化工作流程規範](https://hackmd.io/@l10n-tw/translation_guidelines) | 基本守則、譯文格式規範（標點／空格排版／快捷鍵字元／變數位置／日期時間）、PO 檔頭格式、模糊與已淘汰譯文處理 |
| [自由軟體正體中文化翻譯風格指引](https://hackmd.io/@l10n-tw/translation_style_guide) | 術語訂立方法（理解→貼近→發想）、直譯／意譯／改寫等翻譯風格、情境限定對等直譯原則 |

上述規範已整理為技能內的 `references/l10n-tw-guide.md`（詳見該檔開頭的參考文件清單）。

## 目錄結構

```
l10n-tw/                       # 技能目錄（安裝時複製或連結此目錄）
├── README.md                  # 技能說明（本文件）
├── AGENTS.md                  # 技能開發規則與指令
├── SKILL.md                   # 技能入口：SOP 流程說明
├── references/
│   ├── l10n-tw-guide.md       # 翻譯規範與指引（必讀）
│   ├── terminology.md         # 用語對照表
│   ├── locale.md              # 語言環境命名策略
│   ├── github.md              # GitHub 操作參考
│   └── gettext-tools.md       # gettext 工具組參考
└── scripts/                   # 10 支 Python 工具腳本
```

## 安裝

安裝 = 把本技能目錄（儲存庫 `skills/l10n-tw/`，即本文件所在目錄）放入你所用平台的 skills 目錄。方式有**複製**與**符號連結**兩種：

- **複製** — 安裝後與儲存庫完全獨立，不受後續更新影響
- **符號連結** — 多平台共享同一份技能，更新僅需 `git pull` 儲存庫一處

### 1. 前置需求

- `uv`（Python 套件管理，`uv pip install polib` 供回歸測試使用）
- `gettext`（提供 `msgfmt` 做 PO 格式驗證）

### 2. 取得技能

先取得儲存庫（已 clone 者可略過；以下指令皆從**儲存庫根目錄**執行）：

```bash
git clone https://github.com/a-lang/agent-skills
cd agent-skills
```

### 3. 安裝（複製或符號連結）

```bash
# 複製（例如安裝到 OpenCode 個人目錄）
cp -r skills/l10n-tw ~/.config/opencode/skills/

# 或符號連結（範例：安裝到 Claude Code 專案目錄）
ln -s "$PWD/skills/l10n-tw" .claude/skills/l10n-tw
```

### 各平台安裝位置

| 平台 | 個人（全域） | 專案 |
|---|---|---|
| Claude Code | `~/.claude/skills/` | `.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/` | `.opencode/skills/` |
| Gemini CLI | `~/.gemini/skills/` | `.gemini/skills/` |
| Cursor | `~/.cursor/skills/` | `.cursor/skills/` |
| GitHub Copilot / VS Code | `~/.copilot/skills/` | `.github/skills/` |
| Codex | `~/.codex/skills/` | `.codex/skills/` |
| 開放標準（多平台共通） | `~/.agents/skills/` | `.agents/skills/` |

> Cursor、Copilot 與 Codex 亦相容 `.claude/skills/` 位置；`~/.agents/skills/` 是跨平台共通的「新興標準」位置，多數平台皆會掃描。

### 4. 指令安裝（替代方案）

**Gemini CLI** 也支援指令安裝：

```bash
gemini skills link /path/to/skills/l10n-tw --scope user
```

**跨平台工具**（skills.sh 生態系，自動偵測已安裝的 agent、以符號連結安裝；可用 `--skill l10n-tw` 只裝本技能、`-a <agent>` 指定平台、`-y` 跳過互動確認）：

```bash
# 專案模式（預設）：安裝至目前專案（如 .claude/skills/），可隨專案提交與團隊共享
npx skills add https://github.com/a-lang/agent-skills --skill l10n-tw

# 全域模式（-g）：安裝至使用者目錄（如 ~/.claude/skills/），跨專案可用
npx skills add https://github.com/a-lang/agent-skills --skill l10n-tw -g
```

### 5. 安裝後驗證

在技能目錄執行，確認環境完備：

```bash
uv run python3 scripts/po_verify.py --help   # 確認 uv 與腳本可執行
msgfmt --version                             # 確認 gettext 可用
```

> **注意**：技能目錄內的 `.env`（翻譯者身份設定）已被 `.gitignore` 排除，clone 不會帶入；需要永久保留翻譯者身份時請自行建立（見「翻譯者身份」章節）。

## 使用方式

安裝後，直接以自然語言告知 AI 要翻譯的專案即可，例如：

> 幫我把 `foo.pot` 翻譯成正體中文

AI 會依 `SKILL.md` 的 SOP 進行：確認翻譯計畫 → 預檢來源檔 → 翻譯 → 生成與驗證 PO → 交付。

核心指令（在技能目錄執行）：

```bash
uv run python3 scripts/po_preflight.py <source.pot_or_po>   # 來源檔預檢
uv run python3 scripts/po_gen.py <t.pot> -t <potstem>-translations.py -o out-zh_TW.po
uv run python3 scripts/po_verify.py <t.pot> <out.po> --comments
uv run python3 scripts/regression_test.py --root <projects-dir>   # 回歸測試（--root 必填）
```

詳細情境流程見 `SKILL.md`。

### 翻譯者身份（Last-Translator）

生成 PO 時，翻譯者身份依序從以下來源解析：CLI `--translator` 參數 → `L10N_TW_TRANSLATOR` 環境變數 → `.env` 設定檔；皆無時，AI 會詢問翻譯者姓名與 email，並確認是否寫入 `.env` 永久保存，供以後的翻譯任務自動套用。永久保留也可自行寫入 `.env`（已被 `.gitignore` 排除，不會被提交）：

```bash
echo 'L10N_TW_TRANSLATOR=Name <name@example.org>' >> .env
```
