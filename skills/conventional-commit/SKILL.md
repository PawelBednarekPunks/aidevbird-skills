---
name: conventional-commit
description: Format standard, machine-readable Conventional Commits (v1.0.0) from git status or active changes. Enforces standard types, optional scope, imperative present tense, and zero AI attribution. Use when authoring git commit messages or validating branch history.
---

# Conventional Commit (`conventional-commit`)

Generate clean, semantic git commit messages adhering strictly to the **Conventional Commits v1.0.0** specification.

---

## ⚡ When to Use

* When drafting commit messages for staged git changes.
* When squashing or preparing Pull Request titles.
* When asked to *"Write a commit message"* or *"Commit these changes"*.

---

## 📐 Conventional Commit Format

```text
<type>(<optional-scope>): <description>

[optional body explaining motivation and context]

[optional footer(s), e.g., BREAKING CHANGE: ... or Closes #123]
```

### Allowed Types

| Type | When to Use |
| :--- | :--- |
| **`feat`** | A new feature or user-facing functionality. |
| **`fix`** | A bug fix or patch. |
| **`refactor`** | Code change that neither fixes a bug nor adds a feature. |
| **`perf`** | Performance optimization or latency reduction. |
| **`docs`** | Documentation changes only (README, docstrings, markdown). |
| **`test`** | Adding missing tests or correcting existing tests. |
| **`chore`** | Maintenance, tooling configuration, dependency bumps. |
| **`ci`** | Changes to CI/CD pipelines and automation scripts. |

---

## 🔍 Generation Rules

1. **Imperative & Present Tense:** Always write *"add feature"*, never *"added feature"* or *"adds feature"*.
2. **Casing & Punctuation:**
   * Entire header `<type>(<scope>): <description>` must be lowercase.
   * Do not end the description with a period (`.`).
   * Keep the first line under 72 characters.
3. **Scope:** Use the module, package, or component name as the scope (e.g., `feat(auth): ...`, `fix(ui): ...`).
4. **Breaking Changes:**
   * Add `!` after the type/scope for breaking changes: `feat(api)!: drop v1 endpoints`.
   * Include `BREAKING CHANGE: <explanation>` in the footer.
5. **Zero AI Attribution:** Never append `Co-Authored-By`, `Generated with AI`, or model watermarks.
