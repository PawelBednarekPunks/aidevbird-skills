---
name: clean-git-summary
description: Summarize a git diff in a short 3-block technical format. Use before a commit, for a PR description, or when asked what changed.
---

# Clean Git Summary

1. Pick the diff: staged (`git diff --cached`), else working tree (`git diff`), else `<base>...HEAD` if a base was given. Start with `git diff --stat`.
2. Skip lockfiles, generated and minified files unless the change in them is intentional.
3. Describe behavior and structure, not line edits. Group by module when many files changed.
4. Output exactly this, 3–6 bullets in total:

```markdown
### Changes
- Primary behavior or architecture change.

### Scope
- `path/to/module/`: what changed there.

### Risk
- Breaking: none | <contract that changed>
- Migration: none | <step needed>
```

Rules: imperative tone ("Add endpoint"), no preamble, no adjectives, no AI mentions. Read-only — never stage or commit.
