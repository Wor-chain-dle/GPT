# Wor-chain-dle GPT Agent Guide

This is the canonical, tool-neutral development guide for `Wor-chain-dle/GPT`.
Tool-specific entrypoints must delegate shared rules to this file.

## Project Goal And Scope

Build and train a model from scratch using the principles of large language models
to solve Wor-chain-dle.

- Do not record discussion candidates as decisions. Add model architecture,
  tokenization, training, framework, or hardware choices only after the developer
  has confirmed them.
- Development uses Python 3.12 and uv with `pyproject.toml` and `uv.lock`.
  Experiment recording uses backend-independent protocols and an optional MLflow
  adapter. No model, training framework, or publishing automation is configured.
- Keep README focused on the project goal and actual setup and usage.
- Do not change the web, engine, or Organization profile repository incidentally.

## Branches And Merge Rules

- `main`: stable branch. Changes arrive through reviewed PRs; do not develop
  features directly on it.
- `release/v{version}`: release integration branch created from `main`. Use a full
  semantic version selected for this project, independently of web/engine versions.
- Feature branches start from the target release branch and PR back into it.
  Use descriptive names such as `feature/...`, `fix/...`, `docs/...`, `refactor/...`,
  `test/...`, or `chore/...`.
- Release branches PR into `main`. Release PR titles are exactly `Release v{version}`.
- PRs into release branches use squash. PRs into `main` use merge commits,
  preserving ancestry, including initial bootstrap PRs.
- PR merges are always performed by the developer, never by agents.
- Prefer follow-up commits after review starts instead of amending published history.
  Tiny local-only fixes before review may be amended.
- Before a first release branch is selected, initial workflow/documentation setup
  may PR into `main`. Do not invent a release version for bootstrap work.

## GitHub Rulesets

These settings follow the original `Ootzk/Wor-chain-dle` repository:

- `Protect main`: targets the default branch; prevents deletion and force pushes;
  requires PRs, merge commits, and the GitHub Actions `test` check with the branch
  up to date. No bypass actors.
- `Features to release`: targets `refs/heads/release/*`; prevents deletion and
  force pushes; requires PRs and squash merges. Repository administrators retain
  the original always-bypass setting.
- Neither Ruleset requires a positive approval count; developer review and merge
  ownership still apply.
- Enable automatic deletion of merged head branches, as in the original repository.
- Do not weaken a required check or bypass review to get a change merged.

## Commits

- Use `<type>: <summary>` or `<type>(<scope>): <summary>` subjects, preferably within
  72 characters. Types include `feat`, `fix`, `docs`, `refactor`, `test`, `style`,
  `build`, `ci`, `chore`, and `perf`.
- Group related changes into coherent commits and keep unrelated work separate.
- Explain incompatible public changes in the body and use `!` or a
  `BREAKING CHANGE:` footer where appropriate.
- Inspect staged changes before committing. Do not include credentials, private
  data, unrelated edits, or generated training artifacts by accident.
- Do not force-push, discard user work, or rewrite published commits without
  explicit authorization. Commit/push when requested or authorized by the task.

## Issues And Pull Requests

- Track planned work with issues where practical. Group ad hoc changes into PRs.
- Prefer connected GitHub tools when they work. For CLI commands that infer a repo,
  always pass `--repo Wor-chain-dle/GPT`.
- Inspect the branch, working tree, base, commits, and diff before creating a PR.
  Do not create PRs with `main` as the head branch.
- Feature PRs are Draft unless the developer requests ready-for-review.
- Feature PR titles use a conventional prefix and should fit within 70 characters.
- Assignee: `Ootzk`.
- Milestone: the agreed target release version. Create it first if missing; do not
  copy another repository's version. Unscheduled/bootstrap work can remain without
  a milestone until a release is selected.
- Use the shared label taxonomy below. Create relevant missing labels when needed;
  keep labels on new/ongoing work rather than relabeling completed history.
- Bodies describe the concrete change and verification, with Summary and Test plan
  sections as useful. Distinguish checks run from checks not run.
- Include related issues as `Closes #number`. For external issues use a fully
  qualified repository reference to avoid closing an unrelated GPT issue.
- Feature PRs into release branches may not close issues automatically. The release
  PR must list every completed issue with `Closes #number`; its body is the source
  for GitHub Release notes when release automation is introduced.

| Label | Use |
| --- | --- |
| `development: enhancement` | New standalone capabilities |
| `development: reorganize` | Repositioning or reorganizing existing user-facing features |
| `development: content` | Content added to existing systems |
| `development: refactor` | Internal restructuring without intended behavior changes |
| `development: devops` | Tooling, CI, environment, and agent workflows |
| `🐛 bug` | Bug fixes |
| `📝 documentation` | Documentation |
| `💥 breaking change` | Incompatible public behavior or contracts |
| `🔖 versioning` | Required on release-to-main PRs |

## Version Management

- Use full semver and a `v` prefix in release branch names, milestones, tags, and
  prose. Use bare semver where an existing manifest expects it.
- The package version source is `pyproject.toml`; refresh `uv.lock` when it changes.
- Update existing version sources consistently. Do not copy the web-only
  `PATCH_NOTES_VERSION` or deployment workflow here.
- The current target is v0.1.0 on `release/v0.1.0`.
  Do not create tags, publish artifacts, or claim automatic releases merely because
  a branch reaches `main`.

## Verification And Workflow Files

- `.github/workflows/ci.yml` supplies the `test` check on PRs and main/release pushes.
  It installs locked dependencies and checks Ruff formatting/lint and pytest.
  Tests verify tracking configuration, lifecycle, metrics, and artifacts with
  temporary stores; they do not use private tracking servers or credentials.
- `uv sync --locked --extra mlflow` prepares the environment. Use `uv run --locked`
  for checks and `uv run --locked --extra mlflow --env-file .env wcd-check-tracking`
  for an explicit remote connection check. This is not a model/training benchmark.
- Documentation-only work needs whitespace and reference checks, not a training run.
- For code behavior changes, add meaningful tests and run the applicable checks.
  Report only actual measured outcomes.
- Reusable repository workflows live in `.agents/skills/`; use `pr`, `cleanup`, and
  `bump-version` for their respective tasks. Claude wrappers live in `.claude/skills/`.
- After a developer merge, update the target branch, safely delete the merged local
  branch, and prune stale remote refs. Account for squash ancestry when verifying
  merge status; do not force-delete blindly.
- Communicate in Korean. Keep summaries focused on changes, verification, and
  remaining work.

## Experiment Tracking Boundaries

- Callers depend on `tracking.interfaces`, not the MLflow SDK. Add future backend
  adapters behind these protocols and select them through configuration.
- Never hard-code server addresses or credentials in source, docs, tests, workflow
  files, or lockfiles. Use ignored `.env` files or process environment; GitHub
  workflows obtain private connection/auth values from Secrets.
- Never log raw environment variables or credential files as artifacts. Use explicit
  metadata allowlists. Connection-check runs must be labeled as such.
- Keep MLflow optional (`--extra mlflow`). Do not introduce a training framework,
  model architecture, or remote training dependency as part of tracking setup.
