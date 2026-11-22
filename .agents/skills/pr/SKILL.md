---
name: pr
description: Create a GPT feature or release PR with the correct base, labels, assignee, and release milestone.
---

# GPT Pull Requests

Follow the repository's `AGENTS.md`. Always target `Wor-chain-dle/GPT`; pass
`--repo Wor-chain-dle/GPT` to CLI commands that infer a repository.

1. Check the current branch and worktree, then review commits and the full diff
   against the intended base. Do not create a PR with `main` as its head.
2. Feature branch: target its release branch. Before the first release is selected,
   initial documentation/workflow setup may target `main`. Do not guess a release.
3. Release branch: target `main`, title `Release v{version}`, and apply
   `🔖 versioning`. Use the branch's full semantic version.
4. For feature PRs use a concise conventional title and Draft status unless the
   developer requested ready-for-review.
5. Set change-type labels, assignee `Ootzk`, and the agreed release milestone.
   Create missing metadata where needed. Unscheduled/bootstrap work has no milestone.
6. Explain the change and actual verification. Reference related issues with
   `Closes #number`; release bodies list every issue completed in that release.
7. Push the authorized branch and create the PR. For CLI bodies, write exact
   Markdown to a temporary file and use `--body-file`.
8. Verify PR metadata and available checks, then report the URL and check status.

The developer performs merges. PRs into release branches use squash; PRs into
`main` use merge commits, including bootstrap PRs.
