---
description: Summarize the current git diff in the 3-block technical format (no commit)
argument-hint: "[optional base: branch, tag or commit]"
---

# Git Summary

## Purpose

Concise, zero-fluff technical summary of the current changes — for a pre-commit check or a PR
description. Read-only: does not stage or commit anything.

## Usage

```bash
/git_summary
/git_summary main
```

## Instructions

Use the `clean-git-summary` skill (Skill tool) and follow its workflow exactly. If an argument is
given, summarize `git diff $ARGUMENTS...HEAD` instead of the working tree: $ARGUMENTS
