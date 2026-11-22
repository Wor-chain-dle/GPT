---
name: bump-version
description: Update established GPT version sources consistently for an explicitly selected release.
---

# GPT Version Update

Follow `AGENTS.md`. Use the target version from the developer's request or established
release context; ask only if the target is missing. Do not infer it from web/engine.

1. Inspect the branch, worktree, and existing version sources. There are no version
   files in the initial repository; do not invent packaging or model configuration.
2. If no established version source exists, explain that a bump has no current
   files to update. Otherwise use the project's existing version tooling and update
   all established sources consistently.
3. Review the diff and run checks appropriate to those files.
4. Report changed sources and the full target semver. Use `v` in prose/release labels
   and the manifest's expected format in code/config.

Do not create a commit or tag, push, or publish unless the developer authorizes it.
