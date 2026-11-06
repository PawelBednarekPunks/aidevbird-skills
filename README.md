# 🦅 AiDevBird Skills (`aidevbird-skills`)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![X Profile EN](https://img.shields.io/badge/X-@aidevbird-black.svg?logo=x)](https://x.com/aidevbird)
[![X Profile PL](https://img.shields.io/badge/X-@aidevbird__pl-black.svg?logo=x)](https://x.com/aidevbird_pl)
[![Agent Skills Standard](https://img.shields.io/badge/Standard-Agent%20Skills-brightgreen.svg)](https://github.com/agentskills/agentskills)

Curated, zero-fluff **AI Agent Skills** designed for real-world engineering teams, autonomous coding agents, and high-craft software development.

Maintained by **[AiDevBird](https://x.com/aidevbird)** (EN: [@aidevbird](https://x.com/aidevbird), PL: [@aidevbird_pl](https://x.com/aidevbird_pl)).

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
3. Run `./scripts/install.sh --check` to verify frontmatter.
4. Submit a Pull Request.

---

## 📄 License

Licensed under the [MIT License](LICENSE). Free to use in personal, open-source, and commercial agent workflows.
