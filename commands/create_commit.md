---
description: Create one verified, task-scoped Conventional Commit (lint + tests first, never pushes)
argument-hint: "[optional hint: files, scope or ticket]"
---

# Create Commit

## Purpose

Create exactly one verified commit for the current task: only task-related files, fresh lint and
test results, Conventional Commit message with a ticket from the branch name. Never pushes.

## Usage

```bash
/create_commit
/create_commit only src/auth
```

## Instructions

Use the `create-commit` skill (Skill tool) and follow its workflow exactly. Extra hint from the
user (may be empty): $ARGUMENTS

Stop and ask before staging when the file set is ambiguous. Do not push, amend or open a PR.
