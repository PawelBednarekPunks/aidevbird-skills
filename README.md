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

| Skill | Category | Description |
| :--- | :--- | :--- |
| **[`clean-git-summary`](./skills/clean-git-summary/SKILL.md)** | **Git & Review** | Generates a concise, 3-block technical summary of staged changes or diffs before committing or opening a PR. No AI preambles or filler. |
| **[`conventional-commit`](./skills/conventional-commit/SKILL.md)** | **Git & Hygiene** | Enforces strict **Conventional Commits v1.0.0** (`feat`, `fix`, `refactor`, `perf`, `chore`) with imperative tone and zero AI attribution watermarks. |
| **[`create-commit`](./skills/create-commit/SKILL.md)** | **Git & Hygiene** | Creates one verified, task-scoped commit: stages only task files, runs the project's lint/tests, writes a `Why / Changes / Tests` body with a ticket from the branch name. Never pushes. |

---

## ⌨️ Slash Commands

Thin [Claude Code commands](./commands/) that invoke the matching skill. Installed into `.claude/commands` (or `~/.claude/commands` with `--global`); skip them with `--no-commands`.

| Command | Skill | What it does |
| :--- | :--- | :--- |
| **[`/create_commit`](./commands/create_commit.md)** | `create-commit` | One verified Conventional Commit for the current task. Optional hint: `/create_commit only src/auth`. |
| **[`/git_summary`](./commands/git_summary.md)** | `clean-git-summary` | 3-block summary of the working tree, or of `<base>...HEAD` with `/git_summary main`. Read-only. |

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
2. Add your skill in `skills/<skill-name>/SKILL.md`.
3. Optionally add a slash command in `commands/<command_name>.md` that invokes the skill.
4. Run `./scripts/install.sh --check` to verify frontmatter.
5. Submit a Pull Request.

---

## 📄 License

Licensed under the [MIT License](LICENSE). Free to use in personal, open-source, and commercial agent workflows.
