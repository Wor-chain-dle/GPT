---
name: cleanup
description: Clean up the GPT local checkout after a developer has merged a feature PR.
---

# GPT Post-Merge Cleanup

Follow `AGENTS.md` and use `--repo Wor-chain-dle/GPT` for repository-aware CLI calls.

1. Check the worktree and identify the merged PR, its head, base, and merge commit.
   Preserve unrelated changes. Confirm the merge rather than relying on branch names.
2. Fetch, switch to the PR's base branch, and update with a fast-forward-only pull.
3. Verify that the merged work is present. Squash merges can have different commit
   ancestry; use the actual PR merge state and relevant content/commit checks.
4. Delete the merged local feature branch with `git branch -d` when safe. If Git
   refuses, report the condition instead of force-deleting without authorization.
5. Prune stale origin refs and report the resulting branch and worktree state.

Do not merge the PR, delete an active release branch, or discard local edits.
