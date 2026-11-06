---
name: clean-git-summary
description: Generate a concise, high-signal, zero-fluff 3-bullet technical summary of git diffs before commits or PR reviews. Use when summarizing staged changes, reviewing unstaged work, or preparing PR descriptions.
---

# Clean Git Summary (`clean-git-summary`)

Produce a crisp, engineer-to-engineer technical summary of changes in a git repository. Eliminates conversational filler, marketing adjectives, and robotic AI preambles.

---

## ⚡ When to Use

* Before creating a git commit to verify exact changes.
* When drafting pull request descriptions or changelogs.
* When a human or another agent asks: *"What changed in this branch?"* or *"Summarize the current diff"*.

---

## 🔍 Execution Workflow

1. **Inspect Git Status & Diff:**
   Run git commands to extract the active diff:
   ```bash
   # Check modified files
   git status --short

   # If staged changes exist, inspect them:
   git diff --staged

   # If unstaged changes exist, inspect them:
   git diff
   ```

2. **Synthesize the Delta:**
   * Focus on **functional and architectural differences**, not cosmetic line changes.
   * Ignore generated files, lockfiles, and minified bundles unless they represent intentional configuration changes.

3. **Output in the Standard 3-Block Format:**

```markdown
### ⚡ Core Changes
- Bullet point describing the primary behavioral or architectural change.
- Secondary structural adjustment or refactor.

### 📁 Touched Scope
- `path/to/module/`: Brief mention of updated logic.
- `path/to/config/`: New flags or dependency updates.

### ⚠️ Risk & Breaking Changes
- **Breaking Changes:** None (or description of API / schema contract shifts).
- **Migration Required:** No (or steps needed to deploy).
```

---

## 🚫 Hard Rules

* **Zero AI Attribution:** Never mention AI models, session links, or automated assistant disclaimers.
* **Imperative / Present Tense:** Write *"Add endpoint"* rather than *"Added endpoint"* or *"This PR adds..."*.
* **Keep It Dense:** Maximum 3 to 6 bullet points total. If the diff is large, group by module rather than listing every file.
