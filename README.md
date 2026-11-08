# 🦅 AiDevBird Skills (`aidevbird-skills`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![X Profile](https://img.shields.io/badge/X-@aidevbird-black.svg?logo=x)](https://x.com/aidevbird)
[![Agent Skills Standard](https://img.shields.io/badge/Standard-Agent%20Skills-brightgreen.svg)](https://github.com/agentskills/agentskills)

Curated, zero-fluff **AI Agent Skills** designed for real-world engineering teams, autonomous coding agents, and high-craft software development.

Maintained by **[AiDevBird](https://x.com/aidevbird)** ([@aidevbird](https://x.com/aidevbird)).

---

## ⚡ Quick Start: Installation

Compatible with **Claude Code**, **OpenBot**, **Cursor**, **Codex**, **Antigravity**, **Gemini**, and **GitHub Copilot**.

### Option 1: Standard Skills CLI (`npx skills`)

```bash
npx skills add PawelBednarekPunks/aidevbird-skills
```

### Option 2: Clone & One-Line Installer

```bash
git clone https://github.com/PawelBednarekPunks/aidevbird-skills.git
cd aidevbird-skills

# Install all skills globally (~/.agents/skills)
./scripts/install.sh --global

# Or install into a specific project repository (.agents/skills)
./scripts/install.sh /path/to/project
```

---

## 📚 Available Skills

Every skill is written to be **token-lean**: a description under 300 characters (it loads in every session), a short body, and scripts for anything deterministic. See [STYLE.md](STYLE.md).

| Skill | Category | Description |
| :--- | :--- | :--- |
| **[`clean-git-summary`](./skills/clean-git-summary/SKILL.md)** | **Git** | 3-block technical summary of a diff for commits and PR descriptions. |
| **[`conventional-commit`](./skills/conventional-commit/SKILL.md)** | **Git** | Conventional Commits v1.0.0 messages: imperative, scoped, no AI watermarks. |
| **[`create-commit`](./skills/create-commit/SKILL.md)** | **Git** | One verified, task-scoped commit: only task files, lint and tests first, ticket from the branch. Never pushes. |
| **[`angular-conventions`](./skills/angular-conventions/SKILL.md)** | **Frontend** | Modern Angular (v18+): signals, standalone, OnPush, `inject()`, built-in control flow. |
| **[`xlsx-toolkit`](./skills/xlsx-toolkit/SKILL.md)** | **Office** | Create, edit and check Excel/CSV files with live formulas. Ships `inspect_xlsx.py` to find formula errors. |
| **[`invoice-processing`](./skills/invoice-processing/SKILL.md)** | **Finance** | Invoices → JSON → spreadsheet. `validate_invoice.py` checks totals, VAT, Polish NIP, IBAN and duplicates. |
| **[`appstore-payouts-to-excel`](./skills/appstore-payouts-to-excel/SKILL.md)** | **Finance · Indie** | App Store Connect reports → Excel by currency, country and app, converted at NBP rates. |
| **[`ksef-invoice`](./skills/ksef-invoice/README.md)** | **Finance · 🇵🇱** | Polish KSeF e-invoices (FA(3) XML): invoices, corrections, advances and final settlements, validated against the official Ministry of Finance XSD. [Poradnik po polsku](./skills/ksef-invoice/README.md). |

---

## ⌨️ Slash Commands

Thin [Claude Code commands](./commands/) that invoke the matching skill. Installed into `.claude/commands` (or `~/.claude/commands` with `--global`); skip them with `--no-commands`.

| Command | Skill | What it does |
| :--- | :--- | :--- |
| **[`/create_commit`](./commands/create_commit.md)** | `create-commit` | One verified Conventional Commit for the current task. Optional hint: `/create_commit only src/auth`. |
| **[`/git_summary`](./commands/git_summary.md)** | `clean-git-summary` | 3-block summary of the working tree, or of `<base>...HEAD` with `/git_summary main`. Read-only. |

---

## 🐦 Mac Apps by AiDevBird

Native Swift 6 macOS utilities from the same workshop — private by design, one-time Pro purchase, no subscription.

| App | What it does | Links |
| :--- | :--- | :--- |
| **Prunebird** | Clean AI agent caches, orphaned git worktrees and stale dev dependencies, and see or kill the local servers holding your ports. Lives in the menu bar. | [Mac App Store](https://apps.apple.com/app/prunebird-dev-port-cleaner/id6827096807?mt=12) · [prunebird.com](https://prunebird.com) |
| **Panebird** | Window manager: snap windows to halves, thirds and corners with one shortcut or a drag to the edge, and keep each task's apps together in nests. | [Mac App Store](https://apps.apple.com/app/panebird-window-manager/id6821859372?mt=12) · [panebird.com](https://panebird.com) |

---

## 🛠️ Verification & Testing

Validate metadata and folder naming across all skills in the repository:

```bash
npm run check
# or
./scripts/install.sh --check
```

---

## 🤝 Contributing

We welcome community-driven, pragmatic skills that solve real developer pain points.
1. Fork the repository.
2. Add your skill in `skills/<skill-name>/SKILL.md`, following [STYLE.md](STYLE.md). Written from scratch — no text copied from other skill repos.
3. Optionally add a slash command in `commands/<command_name>.md` that invokes the skill.
4. Run `./scripts/install.sh --check` to verify frontmatter.
5. Submit a Pull Request.

---

## 📄 License

Licensed under the [MIT License](LICENSE). Free to use in personal, open-source, and commercial agent workflows.
