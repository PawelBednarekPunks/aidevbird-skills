# Skill Style

Every skill in this repo is written to cost as few tokens as possible while staying precise.

## Budget

| Part | Loaded | Target |
| :--- | :--- | :--- |
| `description` | Every session, for every installed skill | 1–2 sentences, ≤ 300 characters |
| `SKILL.md` body | Only when the skill triggers | ≤ 80 lines |
| `references/*.md` | Only when the body says to read them | As long as needed |
| `scripts/*` | Never — only their output | Prefer them for anything deterministic |

## Rules

- `description`: what it does + when to use it. No technology lists, no adjectives.
- Body: steps and hard rules. No intro paragraph, no "When to Use" (that is the description), no emoji headings, no `---` separators.
- Don't explain what the agent already knows (what JSON is, how git works). Write only the decisions and traps.
- One example, not three. Show the output shape once.
- If a check can be a script (checksum, totals, file validation), ship the script and tell the agent to run it.
- Write everything from scratch. Do not copy text, examples or code from other skill repositories.
