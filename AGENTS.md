# Agent Instructions

<!-- BEGIN LOADOUT: agent-rules (generated, do not edit) -->
## Agent Rules

This project's coding rules live as individual files under `.cursor/rules/`. Cursor loads
them automatically based on the scopes below. Other agents do not, so you have to load them
yourself.

Before editing files that match a rule's scope, read that rule file and follow it. These are
binding project conventions, not suggestions. Rules scoped `Always` apply to all work in this
repo, so read them at the start of a session.

| Rule | Scope | What it covers |
| --- | --- | --- |
| `.cursor/rules/colocated-evals.mdc` | Always | Keep agent and skill eval fixtures next to the artifact they test. Applies when adding or moving evals. |
| `.cursor/rules/commit-style.mdc` | Always | Write focused, reviewable commits with clear intent. |
| `.cursor/rules/hyperlink-everything.mdc` | Always | Make canonical identifiers and locations clickable on first mention. |
| `.cursor/rules/no-auto-merge.mdc` | Always | Never enable pull-request auto-merge. When told to watch a PR or merge when green, wait until every attached check has finished successfully, within a finite deadline. |
| `.cursor/rules/no-autonomous-external-comms.mdc` | Always | Get an explicit GO/NO-GO from the User before posting on their behalf to any third-party or public medium. Does not apply to repos the User owns. When unsure, assume permission is required. |
| `.cursor/rules/no-cursor-coauthor.mdc` | Always | Never include Cursor as a git commit co-author. |
| `.cursor/rules/pr-ready-for-review.mdc` | Always | Open GitHub PRs ready for review, never as drafts. If the change is not ready, do not open a PR; ask the user what is blocking. |
| `.cursor/rules/repo-conventions.mdc` | Always | Preserve repository conventions and verify scoped changes. |
| `.cursor/rules/ponytail.mdc` | `**/*.py`, `**/*.pyi`, `**/*.ts`, `**/*.tsx`, `**/*.js`, `**/*.jsx`, `**/*.mjs`, `**/*.cjs`, `**/*.go`, `**/*.rs`, `**/*.rb`, `**/*.java`, `**/*.kt`, `**/*.swift`, `**/*.c`, `**/*.h`, `**/*.cpp`, `**/*.hpp`, `**/*.cs`, `**/*.php`, `**/*.sh` | Ponytail, lazy senior dev mode. Always pick the simplest solution that works. |
| `.cursor/rules/pytest.mdc` | `**/test_*.py`, `**/*_test.py`, `tests/**/*.py` | Write reliable, focused pytest coverage for Python behavior. |
| `.cursor/rules/python-code-style.mdc` | `**/*.py`, `**/*.pyi` | Write simple, readable, maintainable Python that a reviewer can quickly read and understand in one pass. |

Skills are installed at `.claude/skills/`, which both Cursor and Claude Code load
automatically. You do not need to read those manually.

Managed by [loadout](https://github.com/sazlin/loadout). Run `just loadout-sync` to regenerate.
Edits inside this block are overwritten.
<!-- END LOADOUT: agent-rules -->
