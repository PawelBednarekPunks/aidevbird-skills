---
name: create-commit
description: Create exactly one verified, task-scoped git commit. Stages only the files belonging to the current task, runs the project's own lint and tests, writes a Conventional Commit message with Why/Changes/Tests body and a ticket derived from the branch name, and never pushes. Use only when the user explicitly asks to commit or invokes /create_commit.
---

# Create Commit (`create-commit`)

Create exactly one safe, reviewable commit for the user's current task.

> **Core Principle:** A commit is a claim that the change works. Stage only what belongs to the task, prove it with fresh lint/test output, and never touch the remote.

---

## 🔐 Preconditions

- Treat `/create_commit` or a direct request to commit as the required authorization. Never commit proactively.
- Run `git branch --show-current`. Stop on a detached HEAD, and stop on the default or integration branch (`main`, `master`, `develop`) unless the user explicitly said to commit there.
- Read `git status --short`, `git diff`, and `git diff --cached` before staging anything.
- Preserve all unrelated user changes. Never use `git add -A` or `git add .`.

---

## 🧱 Prepare the Commit

1. **Select files:** Identify the paths that implement the current task from the conversation and the diff.
2. **Stage explicitly:** If the file set is unambiguous, `git add <path>...` only those paths. If it is ambiguous, or already-staged files include unrelated work, stop and ask the user which files to include.
3. **Check the staged diff:** Inspect `git diff --cached` and run `git diff --cached --check`. Stop on whitespace or conflict-marker errors.
4. **Validate:** Discover the project's own commands (`package.json` scripts, `Makefile`, `nx.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, CI config) and run the lint and test targets affected by the change. Prefer scoped/affected runs over the full suite. Use fresh output from after the final code change. Stop if any command exits non-zero; report pre-existing warnings separately.

---

## 📐 Commit Message

Follow the [`conventional-commit`](../conventional-commit/SKILL.md) skill for types, casing and subject rules, with this shape:

```text
<type>(<scope>): <imperative description> [TICKET-123]

Why:
<one concise reason for the change>

Changes:
- <specific user-visible or architectural change>
- <specific test or regression coverage>

Tests:
- <command> — <result>
```

- **Ticket:** Extract a Jira-like key (`ABC-123`) from the branch name, e.g. `feature/ABC-123-login` → `[ABC-123]`. Omit the suffix when the branch has none.
- **Scope:** Use the module, package, or app name touched; omit it when none fits.
- **Body:** Required for every code-affecting commit and must contain `Why`, `Changes`, and `Tests`. Only a self-evident docs-only or formatting-only commit may omit it.
- **Changes:** 2–5 concrete outcomes from the staged diff. Do not repeat the subject.
- **Tests:** Record each validation command and its outcome. If nothing ran, write `not run` and why.
- **Wrapping:** Every body line at 100 characters or fewer.
- **Zero AI Attribution:** No `Co-Authored-By`, `Generated with`, or model watermarks — unless the repository's own instructions require them.

Pass subject and each body section as separate `-m` arguments so Git preserves paragraphs:

```bash
git commit \
  -m "fix(auth): refresh expired session token [ABC-123]" \
  -m "Why:
Users were logged out when the access token expired mid-session." \
  -m "Changes:
- Retry the failed request once after a silent token refresh.
- Cover the expired-token path with a regression test." \
  -m "Tests:
- npm test -- auth — pass.
- npm run lint — 0 errors."
```

---

## ✅ Create and Report

- Run `git commit` with the prepared message. Never use `--no-verify`. If a hook fails, fix the cause and create a new commit — do not amend.
- Do not push, open a PR, amend, rebase, or rewrite unrelated history.
- Report the commit hash, subject, included files, and validation commands with their results.
