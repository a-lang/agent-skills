# AGENTS.md — agent-skills

**Agent Skills 儲存庫**，每個技能自含說明與工具。

## 結構

```
skills/<skill-name>/
├── SKILL.md       # 技能入口（SOP 與情境流程，必讀）
├── AGENTS.md      # 該技能的開發規則與指令（若有）
├── scripts/       # 工具腳本（從技能目錄執行）
└── *.md           # 技能文件
```

每個技能目錄自含 SKILL.md，可直接複製或符號連結安裝到支援 Agent Skills 的平台。

## 技能開發指引

- **新增技能**：建立 `skills/<skill-name>/`，以 `SKILL.md` 為入口
- **本地掛載測試**：`ln -s ../../skills/<skill-name> .opencode/skills/<skill-name>`
- **Python 腳本**：一律 `uv run python3 ...`，虛擬環境共用根目錄 `.venv`
- **各技能細節**：見各技能目錄內的 `SKILL.md` 與 `AGENTS.md`，頂層不重述
