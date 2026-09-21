# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues in [`Chigo55/multi-product-label-inspection`](https://github.com/Chigo55/multi-product-label-inspection). Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`, filtering comments by `jq` and also fetching labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Infer the repo from `git remote -v`; `gh` does this automatically when run inside a clone.

## 작업 흐름: 이슈 → Orca 워크트리 → PR

1. 이슈를 확인하거나 만든다 (`gh issue create`).
2. 워크트리를 만든다:
   `orca worktree create --repo id:b9e07235-5b2c-497d-a76a-a87f74b8a471 --name <이슈번호>-<slug> --issue <이슈번호> --no-parent --json`.
   브랜치는 `Chigo55/<이슈번호>-<slug>`, 기준은 `origin/main`, 위치는
   `C:/Users/Jeongih/orca/workspaces/multi-product-label-inspection/`이다.
3. 워크트리에서 `uv sync`를 실행한다 (`.venv`는 워크트리마다 따로 생긴다).
4. 커밋은 conventional commits를 따르고 본문에 `Refs #N`을 넣는다. 끝내기 전에
   `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyrefly check`,
   `uv run pytest -rs`를 통과시킨다 (실데이터 테스트까지 skip 없이).
5. `git push -u origin <branch>` 후 `gh pr create --base main`으로 PR을 만든다.
   본문에 Summary / Test plan / `Closes #N`을 넣는다.
6. `gh pr merge <PR번호> --merge --delete-branch`로 머지한다 (merge commit).
7. 메인 체크아웃에서 `git pull --ff-only`를 실행한 다음
   `orca worktree rm --worktree id:<repoId>::<path> --json`으로 워크트리를 지운다.

### 로컬 자원과 실험

데이터(`datasets/public`, `datasets/custom`)·`mlflow.db`·`mlartifacts/`는 메인 체크아웃에만 있고
코드는 `src.utils.paths.SHARED_ROOT`로 찾는다. 인용할 run은 커밋된 깨끗한 트리(`git_dirty=False`)에서
돌린다. merge commit이 커밋을 보존하므로 브랜치에서 기록한 `git_commit`도 머지 후 유효하다.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List external PRs for triage**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments` then keep only `authorAssociation` of `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE` (drop `OWNER`/`MEMBER`/`COLLABORATOR`).
- **Comment / label / close**: `gh pr comment`, `gh pr edit --add-label`/`--remove-label`, `gh pr close`.

GitHub shares one number space across issues and PRs, so a bare `#42` may be either: resolve with `gh pr view 42` and fall back to `gh issue view 42`.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
