#!/usr/bin/env bash
# ==============================================================================
# AiDevBird Skills Installer (scripts/install.sh)
#
# Installs open-source AI Agent Skills globally or into a specific project.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_DIR="$REPO_ROOT/skills"
COMMANDS_DIR="$REPO_ROOT/commands"

PACKS="git dev all"

pack_skills() {
  case "$1" in
    git)
      echo "clean-git-summary conventional-commit create-commit" ;;
    dev)
      echo "clean-git-summary conventional-commit create-commit" ;;
    all)
      discover_skills ;;
    *)
      return 1 ;;
  esac
}

discover_skills() {
  local d out=""
  for d in "$SKILLS_DIR"/*/; do
    [[ -d "$d" ]] || continue
    local s
    s="$(basename "$d")"
    [[ -f "$SKILLS_DIR/$s/SKILL.md" ]] && out="$out $s"
  done
  echo "${out# }"
}

discover_commands() {
  local f out=""
  for f in "$COMMANDS_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    out="$out $(basename "$f" .md)"
  done
  echo "${out# }"
}

frontmatter_field() {
  local file="$1" field="$2"
  awk -v f="$field:" '
    BEGIN { in_fm=0 }
    NR==1 && /^---/ { in_fm=1; next }
    in_fm && /^---/ { exit }
    in_fm && $0 ~ ("^" f) { sub("^" f "[[:space:]]*", ""); print; exit }
  ' "$file"
}

validate_skill() {
  local skill="$1" dir="$SKILLS_DIR/$1" file name desc rc=0
  file="$dir/SKILL.md"
  if [[ ! -f "$file" ]]; then echo "$skill: missing SKILL.md"; return 1; fi
  [[ "$(head -n1 "$file")" == "---" ]] || { echo "$skill: SKILL.md has no YAML frontmatter"; return 1; }
  name="$(frontmatter_field "$file" name | tr -d "\"'")"
  desc="$(frontmatter_field "$file" description)"
  [[ -n "$name" ]] || { echo "$skill: frontmatter has no 'name'"; rc=1; }
  [[ -z "$name" || "$name" == "$skill" ]] || { echo "$skill: frontmatter name '$name' does not match directory"; rc=1; }
  [[ -n "$desc" ]] || { echo "$skill: frontmatter has no 'description'"; rc=1; }
  return $rc
}

validate_command() {
  local cmd="$1" file="$COMMANDS_DIR/$1.md"
  [[ -f "$file" ]] || { echo "/$cmd: missing $cmd.md"; return 1; }
  [[ "$(head -n1 "$file")" == "---" ]] || { echo "/$cmd: no YAML frontmatter"; return 1; }
  [[ -n "$(frontmatter_field "$file" description)" ]] || { echo "/$cmd: frontmatter has no 'description'"; return 1; }
}

usage() {
  cat <<USAGE
Usage:
  $0 --global                 Install all skills (~/.agents/skills) and commands (~/.claude/commands)
  $0 /path/to/project         Install into a specific project (.agents/skills, .claude/commands)
  $0 --skill <name> --global  Install a specific skill (no commands)
  $0 --no-commands --global   Install skills only, skip slash commands
  $0 --list                   List all available skills and commands
  $0 --check                  Validate skill and command metadata
USAGE
}

TARGET=""; ONLY_SKILL=""; ACTION="install"; WITH_COMMANDS=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global|-g) TARGET="--global"; shift ;;
    --skill)     ONLY_SKILL="$2"; shift 2 ;;
    --no-commands) WITH_COMMANDS=0; shift ;;
    --list)      ACTION="list"; shift ;;
    --check)     ACTION="check"; shift ;;
    -h|--help)   usage; exit 0 ;;
    *)           TARGET="$1"; shift ;;
  esac
done

if [[ "$ACTION" == "list" ]]; then
  echo "Available skills: $(discover_skills)"
  echo "Available commands: $(discover_commands | sed -E 's/(^| )/\1\//g')"
  exit 0
fi

if [[ "$ACTION" == "check" ]]; then
  echo "==> Validating skills in $SKILLS_DIR"
  for s in $(discover_skills); do
    validate_skill "$s" && echo "  ✔ $s"
  done
  for c in $(discover_commands); do
    validate_command "$c" && echo "  ✔ /$c"
  done
  echo "==> All skills OK"
  exit 0
fi

[[ -n "$TARGET" ]] || { usage; exit 1; }

if [[ "$TARGET" == "--global" ]]; then
  DEST_DIR="$HOME/.agents/skills"
  CMD_DEST_DIR="$HOME/.claude/commands"
else
  DEST_DIR="$TARGET/.agents/skills"
  CMD_DEST_DIR="$TARGET/.claude/commands"
fi

mkdir -p "$DEST_DIR"

SKILLS_TO_INSTALL="${ONLY_SKILL:-$(discover_skills)}"

for s in $SKILLS_TO_INSTALL; do
  validate_skill "$s"
  rm -rf "$DEST_DIR/$s"
  cp -R "$SKILLS_DIR/$s" "$DEST_DIR/$s"
  echo "✔ Installed $s -> $DEST_DIR/$s"
done

if [[ -n "$ONLY_SKILL" ]]; then WITH_COMMANDS=0; fi

if [[ "$WITH_COMMANDS" == 1 ]]; then
  mkdir -p "$CMD_DEST_DIR"
  for c in $(discover_commands); do
    validate_command "$c"
    cp "$COMMANDS_DIR/$c.md" "$CMD_DEST_DIR/$c.md"
    echo "✔ Installed /$c -> $CMD_DEST_DIR/$c.md"
  done
fi

echo "Done! Installed skills into $DEST_DIR"
[[ "$WITH_COMMANDS" == 1 ]] && echo "      Installed commands into $CMD_DEST_DIR"
exit 0
