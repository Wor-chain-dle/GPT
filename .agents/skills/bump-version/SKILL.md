---
name: bump-version
description: Update established GPT version sources consistently for an explicitly selected release.
---

# GPT Version Update

Follow `AGENTS.md`. Use the target version from the developer's request or established
release context; ask only if the target is missing. Do not infer it from web/engine.

1. Inspect the branch, worktree, and established version source: `pyproject.toml`.
2. Run `uv version <version>` and `uv lock` to update the project version and its
   lockfile entry together. Do not introduce model configuration or change
   sibling repository versions as part of this bump.
3. Review the diff and run checks appropriate to those files.
4. Report changed sources and the full target semver. Use `v` in prose/release labels
   and the manifest's expected format in code/config.

Do not create a commit or tag, push, or publish unless the developer authorizes it.
