---
name: conventional-commit
description: Write a Conventional Commits v1.0.0 message for the current changes. Use when writing or checking a commit message or PR title.
---

# Conventional Commit

Format:

```text
<type>(<scope>): <description>

[body: why, not what]

[footer: BREAKING CHANGE: ..., Closes #123]
```

Types: `feat` new behavior · `fix` bug fix · `refactor` no behavior change · `perf` speed ·
`docs` docs only · `test` tests only · `build` deps/build · `ci` pipelines · `chore` other upkeep · `style` formatting.

Rules:
- Base it on `git diff --cached` (or `git diff` if nothing is staged), not on the conversation.
- Imperative, present tense: "add", not "added"/"adds". Lowercase header, no trailing period, ≤ 72 chars.
- Scope = module, package or app touched. Omit if none fits.
- Breaking change: `!` after type/scope and a `BREAKING CHANGE:` footer.
- One logical change per commit. If the diff mixes two, say so and propose a split.
- No AI attribution (`Co-Authored-By`, "Generated with") unless the repo's own rules require it.

Example: `fix(auth): refresh expired token before retrying request`
