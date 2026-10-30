# ticket-pilot - returned from QA, implementation, open questions, code review

Part of the ticket-pilot skill. The ground rules from SKILL.md apply.

## Issue returned from QA

Recognise it by history: it was in QA (or later) and is now assigned back with a new tester comment.
1. Read everything since the last QA transition: comments, screenshots, videos. Videos: open the attachment in the browser and step through frames (`video.currentTime` + screenshot) - never download.
2. `two-stage` project (code only on `devel`): fix on the **same branch**. `direct` project (old branch already merged and deleted): **new branch from `origin/main`**: `bugfix/<nr>-<short-desc>`.
3. Analysis and estimate of the fixes as in Step 2 → the user accepts → "take" → normal flow.

## Implementation (after "take <nr>")

"take <nr>" = estimate accepted: write the estimate to the tracker (unless it was already filled), status → in progress, mirror the status in `state.json → issues.<nr>.status` (the dashboard reads it). Then:

1. A worktree with a branch from the current `origin/main`: `feature/<nr>-…` / `bugfix/<nr>-…` (for a frontend/backend split use the **parent** number). Before every push check `git branch --show-current` - the user may have renamed it. Brief = `analyses/<nr>.md` + the issue context.
2. **One implementer agent** implements the whole list per the plan. Checks: `npx tsc --noEmit -p tsconfig.app.json` must pass, ESLint must report **no new** errors - check only with `{{ROOT}}/bin/eslint-new.sh <worktree>` (it diffs against `origin/main`), build `npx ng build`, specs where `specs: true`. In the worktree first `ln -s ../../../node_modules node_modules` if missing.
   **Permissions in the cron session:** background subagents get a denial instead of a prompt, so: call `npx`/`npm` bare (they are on PATH), no `PATH=…`, no full paths to binaries, no shell variables or `$?` (use `&& echo OK || echo FAIL`), no `git --no-pager` / `git -c`, one command per call (no `;`/`&&` chains with `ls`/`echo`, no pipes), project scripts always by full path. Pass this on to subagents.
   Deviation from the plan only when the plan does not work in practice - note what and why in `analyses/<nr>.md` (review will judge it). A deviation that changes scope, estimate or needs a business/backend decision → stop and ask the user (`chat.py say --question`).
3. Commit (one short sentence, see "Release queue"), then straight to "Code review". The user is **not** shown the diff.
4. Report after the fact: branch, commit, deviations.

## Open questions (backend / business) during work

Open questions do not block the start.
- **Start with assumptions:** for each open question take the safest, easiest-to-change assumption (working field name, text from the mockup, the more restrictive variant). Save it in `analyses/<nr>.md` → "Assumptions" and in `issues.<nr>.openQuestions: [{ q, to, assumption, askedAt }]`.
- **Exception - do not start:** when the answer decides the whole approach (a different answer = rewriting > 25% of the code or a different estimate) → set `waitingFor`, ask, take the next issue.
- **An answer arrives** (pasted by the user, or visible in backend code): save it in `beAnswers` / `bizAnswers`, remove it from `openQuestions`; if it differs from the assumption → fix on the branch (implementer + review of the change only), push.
- **Commit, review, push and a draft MR - yes; merge to `devel` - NO** while `openQuestions` is not empty (unless the user said "leave it as is" for a question).
- A question shared by several issues - one list, one answer closes it everywhere.

## TODOs in code

Every `// TODO` in the issue's code must map to an open question - list them in `issues.<nr>.todosInCode` (`file`, `todo`, `closesWith`). When an answer closes the question, remove the TODO in the same fix. The reviewer flags a TODO whose question is already closed (`bug`). No TODO without an open question may reach `devel`.

## Code review (after implementation, before release)

A **fresh, independent reviewer** agent that did not take part in the implementation gets: the `origin/main...<branch>` diff, the issue context and the accepted "to do" list - **not** the author's notes or reasoning. Every issue gets a review, even a tiny one.

**The reviewer is the last gate before release** - its acceptance lets the issue ship without the user reading the code. So first it builds a **requirements matrix**: from a FRESHLY fetched issue + parent description (comments, mockups, linked issues) + backend answers + the "to do" list it lists every requirement and rates it `done` / `partial` / `missing` / `wrong` with `file:line` evidence (for UI: exactly what the user sees - texts, validation, empty and error states, permissions). Anything but `done` is a `bug` finding; unverifiable requirements are `risk`.

Reviewer rules (put them in the brief):
- only concrete defects in the diff: `file:line`, scenario (input → wrong result), category `bug` / `risk` / `minor`;
- the scope is closed - no rewrites, no different approach, no refactors outside the diff, no taste changes.

**Author vs reviewer agreement.** The author rates every finding `accept` / `reject` + why. Agreement = accepted / all (without `minor`).
- **≥ 75% and the fixes change ≤ 25% of the diff's lines** → apply the accepted fixes, then **one** re-review of the changed parts only. Rejected findings go to the report with reasons.
- **< 75%**, fixes > 25%, or "the approach is wrong" → **arbiter** (decides each finding; can side with the reviewer only within the accepted scope).
- **The user steps in only on a real dispute** - the arbiter could not decide or the decision changes scope/estimate.

**A resolved review = consent to release** (if `openQuestions` is empty; otherwise push + draft MR and wait). Go straight to "Release queue" (the backend condition still applies).

**Push right after a resolved review**, also when waiting for the backend or answers - and on the **first** push open a **draft MR → devel** (title = branch name, empty description, assigned to me) via push options: `-o merge_request.create -o merge_request.target=devel -o "merge_request.title=Draft: <branch>"`. GitLab ticks "Delete source branch" by default for push-option MRs - open the MR right away, **untick it** and verify (the branch must survive the `devel` merge). Never force-push. Set `branchPushed: true`.
