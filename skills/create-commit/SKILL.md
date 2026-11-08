---
name: create-commit
description: Create one verified, task-scoped git commit (only task files, lint and tests first, never pushes). Use only when the user asks to commit or runs /create_commit.
---

# Create Commit

Preconditions — stop if any fails:
- The user asked to commit. Never commit on your own.
- `git branch --show-current` is not empty (detached HEAD) and not `main`/`master`/`develop`, unless the user said to commit there.
- You read `git status --short`, `git diff` and `git diff --cached` first.

Steps:
1. Stage only the paths of the current task with `git add <path>...`. Never `git add -A` or `git add .`. If the set is unclear, or already-staged files are unrelated, ask.
2. `git diff --cached --check` — stop on whitespace or conflict markers.
3. Find the project's own lint and test commands (`package.json`, `Makefile`, `nx.json`, `pyproject.toml`, `Cargo.toml`, CI config). Run the ones affected by the change, after the last edit. Stop on non-zero exit.
4. Write the message using the `conventional-commit` skill, in this shape:

```text
<type>(<scope>): <description> [ABC-123]

Why:
<one reason>

Changes:
- <2–5 concrete outcomes from the staged diff>

Tests:
- <command> — <result>   (or "not run — <why>")
```

- Ticket: Jira-style key from the branch name (`feature/ABC-123-x` → `[ABC-123]`); omit if none.
- Body required for code changes; a trivial docs/format commit may skip it. Lines ≤ 100 chars.
- Pass subject and each section as separate `-m` arguments.

5. `git commit`. Never `--no-verify`. If a hook fails, fix and commit again — don't amend.
6. Report hash, subject, files and test results. Do not push, amend, rebase or open a PR.
